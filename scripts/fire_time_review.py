"""Paired contrasts across all five lags and an exploratory pre-event comparison."""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import haversine_distances

from extend_fusion import angle, bearing

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LAGS = [0, 6, 12, 24, 48]


def day_bootstrap(frame):
    days = frame.index.get_level_values("time").normalize()
    sums = frame.groupby(days).sum().to_numpy()
    sizes = frame.groupby(days).size().to_numpy()
    draws = np.random.default_rng(20261116).integers(len(sizes), size=(5000, len(sizes)))
    return sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)[:, None]


def pre_event(wide):
    cities = pd.read_csv(DATA / "cleaned/case_city_grid.csv").dropna(subset="source_group").sort_values("city")
    obs = pd.read_parquet(DATA / "integrated/yrd_ground_era5_hour.parquet")
    pm = obs.pivot(index="time", columns="city", values="pm25").reindex(columns=cities.city).asfreq("h")
    wind = obs.pivot(index="time", columns="city", values="wind_from_deg")
    # Use complete, disjoint six-hour windows for every included city.
    recent = pm.shift(1).rolling(6).mean()
    change = recent - recent.shift(6)
    baseline = pm.shift(1).rolling(24, min_periods=12).mean()
    coords = cities[["lat", "lon"]].to_numpy()
    rows = []
    for time, lat, lon in wide.index:
        dist = 6371 * haversine_distances(np.radians([[lat, lon]]), np.radians(coords))[0]
        direction = wind.at[time, cities.city.iloc[dist.argmin()]]
        az = bearing(lat, lon, coords[:, 0], coords[:, 1])
        ring = (dist >= 30) & (dist <= 200)
        down = ring & (angle(az, direction + 180) <= 45)
        up = ring & (angle(az, direction) <= 45)
        def contrast(values):
            return values.iloc[down].mean() - values.iloc[up].mean()
        post = contrast(pm.loc[time + pd.Timedelta(hours=12)] - baseline.loc[time])
        np.testing.assert_allclose(post, wide.at[(time, lat, lon), 12], atol=1e-5)
        rows.append(contrast(change.loc[time]))
    return pd.DataFrame({"pre": rows}, index=wide.index).dropna()


def main():
    pairs = pd.read_csv(DATA / "integrated/fire_wind_sector_contrasts.csv.gz", parse_dates=["time"])
    wide = pairs.pivot(index=["time", "lat_grid", "lon_grid"], columns="lag", values="delta_pm25")[LAGS].dropna()
    differences = pd.DataFrame({f"{a}h−{b}h": wide[a] - wide[b] for b, a in combinations(LAGS, 2)})
    means = differences.mean().to_numpy()
    draws = day_bootstrap(differences)
    se = draws.std(axis=0, ddof=1)
    critical = np.quantile(np.max(np.abs((draws - means) / se), axis=1), .95)
    result = pd.DataFrame({"comparison": differences.columns, "mean": means,
                           "point_low": np.quantile(draws, .025, axis=0), "point_high": np.quantile(draws, .975, axis=0),
                           "family_low": means-critical*se, "family_high": means+critical*se})
    result.to_csv(ROOT / "results/火点时点配对差.csv", index=False)
    print("Common events, anchor days:", len(wide), wide.index.get_level_values("time").normalize().nunique())
    print(result.round(2).to_string(index=False))
    pre = pre_event(wide)
    low, high = np.quantile(day_bootstrap(pre), [.025, .975])
    print("Pre-event: (-6..-1h) minus (-12..-7h), downwind minus upwind; events, days, mean, CI:")
    print(len(pre), pre.index.get_level_values("time").normalize().nunique(), pre.pre.mean(), low, high)
    print("Rebuilt all +12 h contrasts from city-hour records, tolerance 1e-5.")


if __name__ == "__main__":
    main()
