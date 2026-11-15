"""Offline reproduction from released measurements and intermediate tables. Python 3.12."""
import argparse
import csv
import hashlib
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"

def check_release():
    with (ROOT / "metadata/release_sha256.csv").open(encoding="utf-8") as src:
        files = list(csv.DictReader(src))
    for item in files:
        path = ROOT / item["path"]
        with path.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if digest != item["sha256"] or path.stat().st_size != int(item["bytes"]):
            raise ValueError(f"文件与发布记录不一致 {path}")
    print(f"发布文件校验通过 {len(files)} 项")

def rebuild_day(out):
    raw = pd.read_csv(DATA / "raw/ground/20230122.csv.gz")
    stations = pd.read_csv(DATA / "cleaned/station_city.csv")[["station", "city"]]
    long = raw.melt(id_vars=["date", "hour", "type"], var_name="station", value_name="value")
    long["value"] = long.value.where(long.value >= 0)
    long["time"] = pd.to_datetime(long.date.astype(str)) + pd.to_timedelta(long.hour, unit="h")
    long = long.merge(stations, on="station", validate="many_to_one")
    group = long.groupby(["time", "city", "type"]).value
    values = group.mean().unstack().rename(columns={"PM2.5": "pm25", "NO2": "no2"})
    support = group.count().unstack().rename(columns={"PM2.5": "n_PM2.5", "NO2": "no2_n"})
    clean = values.join(support).dropna(subset=["pm25","no2"],how="all").reset_index()
    clean.to_csv(out / "cleaned_city_hour.csv", index=False)
    weather = pd.read_csv(DATA / "raw/era5/20230122.csv", parse_dates=["time"])
    weather.columns = ["location_id","time","t2m_c","sp_hpa","ws_ms","wind_from_deg","blh_m"]
    dims = pd.read_csv(DATA / "cleaned/era5_requested_city_grid.csv")
    if not dims.utc_offset_seconds.eq(28800).all():raise ValueError("北京时区校验失败")
    weather = weather.merge(dims[["location_id","city"]],on="location_id",validate="many_to_one")
    merged = clean.merge(weather,on=["city","time"],validate="one_to_one")
    merged.to_csv(out / "integrated_city_hour.csv", index=False)
    full = pd.read_parquet(DATA / "integrated/yrd_ground_era5_hour.parquet")
    fields=["pm25","no2","n_PM2.5","no2_n","t2m_c","sp_hpa","ws_ms","wind_from_deg","blh_m"]
    reference = full[full.time.dt.normalize()==pd.Timestamp("2023-01-22")].set_index(["city","time"]).sort_index()
    rebuilt = merged.set_index(["city","time"]).sort_index()
    pd.testing.assert_frame_equal(rebuilt[fields],reference[fields],check_dtype=False,check_names=False,rtol=1e-10,atol=1e-10)
    print(f"春节样例从站点原始读数重建 {len(rebuilt)} 个城市小时，9 个字段与研究表一致")

def fire_results(out):
    pairs=pd.read_csv(DATA/"integrated/fire_wind_sector_contrasts.csv.gz")
    keys=["time","lat_grid","lon_grid"]
    common=pairs[pairs.groupby(keys).lag.transform("nunique").eq(5)]
    rows=[]
    for scope,frame in [("全部共同锚点",common),("含两个已绘制农田格的共同锚点",common[common.n_farmland>=2])]:
        for lag,g in frame.groupby("lag"):
            rows.append(dict(scope=scope,lag=lag,grids_hours=len(g),anchor_days=g.time.str[:10].nunique(),mean_delta=g.delta_pm25.mean()))
    actual=pd.DataFrame(rows)
    expected=pd.read_csv(RESULTS/"火点相同锚点对照.csv")[actual.columns]
    pd.testing.assert_frame_equal(actual,expected,check_dtype=False,atol=1e-5,rtol=0)
    actual.to_csv(out/"fire_lags.csv",index=False)
    print("Q1 两种农田口径 × 五个滞后的样本数、日期数和平均差复现")

def satellite_results(out):
    # Reuse the same scientific code; only its data and output paths are redirected.
    from scripts import extend_satellite as model
    import shutil
    model.BASE=ROOT
    model.C,model.I,model.O=[out/p for p in ["satellite_cleaned","satellite_integrated","satellite_results"]]
    for folder in [model.C,model.I,model.O]:folder.mkdir(exist_ok=True)
    shutil.copyfile(DATA/"integrated/yrd_ground_era5_hour.parquet",model.I/"yrd_ground_era5_hour.parquet")
    model.main()
    cols=["shift_h","scheme","model","n","mae","r2"]
    a=pd.read_csv(model.O/"no2_model_metrics.csv")[cols]
    b=pd.read_csv(RESULTS/"no2_model_metrics.csv")[cols]
    pd.testing.assert_frame_equal(a,b,rtol=1e-8,atol=1e-8)
    print(f"Q2 从 90 日卫星窗口生成有效时刻并重训岭回归，{len(a)} 组留出指标一致")

def pollution_days(out):
    d=pd.read_parquet(DATA/"integrated/全国城市日.parquet").sort_values(["city","date"])
    good=d.valid_hours>=20
    high=d[good & (d.pm25>150)].copy()
    high["id"]=(high.city.ne(high.city.shift())|high.date.diff().ne(pd.Timedelta(days=1))).cumsum()
    events=high.groupby(["city","id","yrd41"]).agg(start=("date","min"),end=("date","max"),days=("date","size")).reset_index()
    ref=pd.read_csv(RESULTS/"全国重污染过程.csv",parse_dates=["start","end"])
    cols=["city","yrd41","start","end","days"]
    pd.testing.assert_frame_equal(events[cols].reset_index(drop=True),ref[cols].reset_index(drop=True),check_dtype=False)
    expected=pd.read_csv(RESULTS/"地面结果分组.csv").query("样本=='全部'").set_index("区域")
    for label,mask in [("全国",pd.Series(True,index=d.index)),("长三角41城",d.yrd41),("南京",d.city=="南京")]:
        assert int((good&mask).sum())==expected.at[label,"合格城市日"]
        assert int((good&mask&(d.pm25>150)).sum())==expected.at[label,"重污染城市日"]
    events.to_csv(out/"episodes.csv",index=False)
    print(f"Q3 全国 {len(events)} 段、长三角 {events.yrd41.sum()} 段过程，与逐次事件表一致")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=ROOT/"reproduced")
    args=parser.parse_args()
    check_release()
    args.out.mkdir(parents=True,exist_ok=True)
    rebuild_day(args.out);fire_results(args.out);satellite_results(args.out);pollution_days(args.out)
