#!/usr/bin/env python3
"""
轻量级补充对照实验：
1. 问题二（NO2 卫星估计）：线性岭回归 vs 季节交互岭回归 vs 非线性梯度提升树（HGBDT）
   保持与主实验完全一致的 2023 训练 -> 2024 / 2025 测试口径，及 3000 次按日历周重抽样 95% 区间。
2. 问题一（火点与上下风 PM2.5）：基于 1,566 个配对事件，按火点聚集规模（n_spatial）、
   季节（收获参考月 vs 其他）、地理南北（>=32.5N vs <32.5N）及农田落点做分层稳健性检验，
   采用与主实验一致的按年月整组重抽样 10,000 次计算 95% 区间。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "results" / "补充对照实验"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def block_bootstrap_diff(df_test: pd.DataFrame, err0: np.ndarray, err1: np.ndarray,
                         block_col: str, n_boot: int = 3000, seed: int = 42):
    """计算 mean(err1 - err0) 的块重抽样 95% 置信区间（负值表示模型1更准）。"""
    diff = err1 - err0
    tmp = pd.DataFrame({"block": df_test[block_col].values, "diff": diff})
    grouped = tmp.groupby("block", sort=False)["diff"].agg(["sum", "count"])
    sums = grouped["sum"].values
    cnts = grouped["count"].values
    n_blocks = len(sums)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_blocks, size=(n_boot, n_blocks))
    boot_means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.mean(diff)), float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5))


def block_bootstrap_mean(values: np.ndarray, blocks: np.ndarray, n_boot: int = 10000, seed: int = 42):
    tmp = pd.DataFrame({"block": blocks, "val": values})
    grouped = tmp.groupby("block", sort=False)["val"].agg(["sum", "count"])
    sums = grouped["sum"].values
    cnts = grouped["count"].values
    n_blocks = len(sums)
    if n_blocks < 2:
        m = float(np.mean(values))
        return m, m, m
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_blocks, size=(n_boot, n_blocks))
    boot_means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.mean(values)), float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5))


def run_q2_experiments():
    p = ROOT / "非一月卫星补采_验收" / "结果" / "卫星城市日匹配.csv.gz"
    df = pd.read_csv(p)
    df = df.dropna(subset=["l2", "no2", "grid_ws", "grid_log_blh"]).copy()
    df["dt"] = pd.to_datetime(df["date"])
    df["year"] = df["dt"].dt.year
    df["month"] = df["dt"].dt.month
    doy = df["dt"].dt.dayofyear.values
    df["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    df["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    # 交互特征
    df["l2_x_blh"] = df["l2"] * df["grid_log_blh"]
    df["l2_x_ws"] = df["l2"] * df["grid_ws"]
    df["l2_x_sin"] = df["l2"] * df["sin_doy"]
    df["l2_x_cos"] = df["l2"] * df["cos_doy"]
    df["blh_x_sin"] = df["grid_log_blh"] * df["sin_doy"]
    df["blh_x_cos"] = df["grid_log_blh"] * df["cos_doy"]

    iso = df["dt"].dt.isocalendar()
    df["year_week"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)

    season_map = {12: "冬", 1: "冬", 2: "冬", 3: "春", 4: "春", 5: "春",
                  6: "夏", 7: "夏", 8: "夏", 9: "秋", 10: "秋", 11: "秋"}
    df["season"] = df["month"].map(season_map)

    train = df[df["year"] == 2023].copy()

    specs = [
        ("线性岭回归（无季节）",
         make_pipeline(StandardScaler(), Ridge(alpha=1.0)), ["l2"],
         make_pipeline(StandardScaler(), Ridge(alpha=1.0)), ["l2", "grid_ws", "grid_log_blh"]),
        ("线性岭回归（含季节与交互）",
         make_pipeline(StandardScaler(), Ridge(alpha=1.0)), ["l2", "sin_doy", "cos_doy", "l2_x_sin", "l2_x_cos"],
         make_pipeline(StandardScaler(), Ridge(alpha=1.0)), ["l2", "grid_ws", "grid_log_blh", "sin_doy", "cos_doy",
                                                              "l2_x_blh", "l2_x_ws", "l2_x_sin", "l2_x_cos", "blh_x_sin", "blh_x_cos"]),
        ("梯度提升树 HGBDT（无季节）",
         HistGradientBoostingRegressor(max_depth=4, max_iter=150, learning_rate=0.05, min_samples_leaf=30, random_state=42),
         ["l2"],
         HistGradientBoostingRegressor(max_depth=4, max_iter=150, learning_rate=0.05, min_samples_leaf=30, random_state=42),
         ["l2", "grid_ws", "grid_log_blh"]),
        ("梯度提升树 HGBDT（含季节）",
         HistGradientBoostingRegressor(max_depth=4, max_iter=150, learning_rate=0.05, min_samples_leaf=30, random_state=42),
         ["l2", "sin_doy", "cos_doy"],
         HistGradientBoostingRegressor(max_depth=4, max_iter=150, learning_rate=0.05, min_samples_leaf=30, random_state=42),
         ["l2", "grid_ws", "grid_log_blh", "sin_doy", "cos_doy"]),
    ]

    rows = []
    season_rows = []
    for name, m0, f0, m1, f1 in specs:
        m0.fit(train[f0].values, train["no2"].values)
        m1.fit(train[f1].values, train["no2"].values)
        for yr in [2024, 2025]:
            te = df[df["year"] == yr].copy()
            y = te["no2"].values
            p0 = m0.predict(te[f0].values)
            p1 = m1.predict(te[f1].values)
            e0 = np.abs(y - p0)
            e1 = np.abs(y - p1)
            mae0 = float(mean_absolute_error(y, p0))
            mae1 = float(mean_absolute_error(y, p1))
            r2_0 = float(r2_score(y, p0))
            r2_1 = float(r2_score(y, p1))
            delta, w_lo, w_hi = block_bootstrap_diff(te, e0, e1, "year_week", n_boot=3000, seed=42)
            rel_pct = (mae1 - mae0) / mae0 * 100.0
            rows.append({
                "model": name, "year": yr, "n_test": len(te),
                "mae_no_met": round(mae0, 4), "mae_with_met": round(mae1, 4),
                "delta_mae": round(delta, 4), "rel_pct": round(rel_pct, 2),
                "week_ci_low": round(w_lo, 4), "week_ci_high": round(w_hi, 4),
                "r2_no_met": round(r2_0, 4), "r2_with_met": round(r2_1, 4),
            })
            # 分季节
            for s in ["冬", "春", "夏", "秋"]:
                sub = te[te["season"] == s]
                idx_s = sub.index
                mask = te.index.isin(idx_s)
                d_s, lo_s, hi_s = block_bootstrap_diff(sub, e0[mask], e1[mask], "year_week", n_boot=3000, seed=42)
                season_rows.append({
                    "model": name, "year": yr, "season": s, "n": len(sub),
                    "mae_no_met": round(float(e0[mask].mean()), 4),
                    "mae_with_met": round(float(e1[mask].mean()), 4),
                    "delta_mae": round(d_s, 4),
                    "week_ci_low": round(lo_s, 4), "week_ci_high": round(hi_s, 4),
                })

    res_df = pd.DataFrame(rows)
    res_season = pd.DataFrame(season_rows)
    res_df.to_csv(OUT_DIR / "Q2_非线性与季节交互对照.csv", index=False)
    res_season.to_csv(OUT_DIR / "Q2_分季节模型对照.csv", index=False)
    print("=== Q2 Model Comparison ===")
    print(res_df.to_string(index=False))
    return res_df, res_season


def run_q1_stratified():
    p_pair = ROOT / "三年地面扩展" / "同网格未检出日配对.csv.gz"
    p_all = ROOT / "三年地面扩展" / "fire_wind_sector_contrasts.csv.gz"
    df_pair = pd.read_csv(p_pair)
    df_all = pd.read_csv(p_all)
    df_12 = df_all[df_all["lag"] == 12][["time", "lat_grid", "lon_grid", "nslots", "n_spatial", "n_farmland", "n_up", "n_down"]].drop_duplicates()

    m = df_pair.merge(df_12, on=["time", "lat_grid", "lon_grid"], how="left")
    m["dt"] = pd.to_datetime(m["time"])
    m["ym"] = m["dt"].dt.strftime("%Y-%m")
    m["month"] = m["dt"].dt.month

    strata = [
        ("全部配对事件", pd.Series(True, index=m.index)),
        ("火点规模：2个小格（常规）", m["n_spatial"] == 2),
        ("火点规模：≥3个小格（聚集强火点）", m["n_spatial"] >= 3),
        ("季节：收获参考月（6/10/11月）", m["month"].isin([6, 10, 11])),
        ("季节：非收获月份", ~m["month"].isin([6, 10, 11])),
        ("区域：皖北苏北高发带（≥32.5°N）", m["lat_grid"] >= 32.5),
        ("区域：长三角中南部（<32.5°N）", m["lat_grid"] < 32.5),
        ("用地：含已绘农田（n_farmland≥1）", m["n_farmland"] >= 1),
        ("用地：非农田（n_farmland=0）", m["n_farmland"] == 0),
    ]

    rows = []
    for label, mask in strata:
        sub = m[mask].dropna(subset=["difference"])
        ev_mean, _, _ = block_bootstrap_mean(sub["event"].values, sub["ym"].values, n_boot=2000)
        ct_mean, _, _ = block_bootstrap_mean(sub["control"].values, sub["ym"].values, n_boot=2000)
        net_mean, lo, hi = block_bootstrap_mean(sub["difference"].values, sub["ym"].values, n_boot=10000)
        rows.append({
            "stratum": label,
            "n_pairs": len(sub),
            "n_months": sub["ym"].nunique(),
            "event_mean": round(ev_mean, 3),
            "control_mean": round(ct_mean, 3),
            "net_diff": round(net_mean, 3),
            "ci_low": round(lo, 3),
            "ci_high": round(hi, 3),
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "Q1_配对事件分层稳健性.csv", index=False)
    print("\n=== Q1 Stratified Robustness (1,566 paired events, 12h) ===")
    print(out.to_string(index=False))
    return out


if __name__ == "__main__":
    run_q2_experiments()
    run_q1_stratified()
