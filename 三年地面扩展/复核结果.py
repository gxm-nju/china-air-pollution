"""Offline recomputation from the published intermediate data of the three-year extension."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent


def ground():
    frame = pd.read_parquet(HERE / "全国城市日.parquet")
    assert not frame.duplicated(["city", "date"]).any()
    qualified = frame[frame.valid_hours >= 20]
    expected = pd.read_csv(HERE / "分年地区汇总.csv")
    for row in expected.itertuples():
        area = {"全国":qualified, "长三角41城":qualified[qualified.yrd41], "南京":qualified[qualified.city.eq("南京")]}[row.范围]
        if row.时期 != "合计":
            area = area[area.date.dt.year.eq(int(row.时期))]
        heavy = area[area.pm25.gt(150)]
        assert (len(area), len(heavy), heavy.date.nunique()) == (row.合格城市日, row.超阈值城市日, row.超阈值实际日期数)
    print("地面年表通过，12 组地区和年份对照一致")


def fire():
    frame = pd.read_csv(HERE / "fire_wind_sector_contrasts.csv.gz")
    keys = ["time", "lat_grid", "lon_grid"]
    assert not frame.duplicated([*keys, "lag"]).any()
    common = frame[frame.groupby(keys).lag.transform("nunique").eq(5)]
    for row in pd.read_csv(HERE / "火点相同锚点对照.csv").itertuples():
        subset = common[common.lag.eq(row.lag)]
        if row.scope != "全部共同锚点":
            subset = subset[subset.n_farmland.ge(2)]
        assert len(subset) == row.grids_hours and subset.time.str[:10].nunique() == row.anchor_days
        np.testing.assert_allclose(subset.delta_pm25.mean(), row.mean_delta, atol=1e-5)
    print("火点五时点均值、样本数与日期数复算一致")


def satellite():
    data = pd.read_parquet(HERE / "模型实际使用的城市小时.parquet")
    columns = {"仅卫星":["column_1e15"],"卫星和气象":["column_1e15","ws_ms","log_blh"],
               "卫星气象和地图":["column_1e15","ws_ms","log_blh","road_km_per_km2","industrial_area_ratio"]}
    scores = pd.read_csv(HERE / "滚动留出月指标.csv")
    for row in scores.itertuples():
        test,train = data[data.month == row.month], data[data.month < row.month]
        assert (len(train), len(test)) == (row.n_train, row.n_test)
        fields = columns[row.model]
        fit = make_pipeline(StandardScaler(),Ridge(alpha=1.)).fit(train[fields],train.no2)
        np.testing.assert_allclose(mean_absolute_error(test.no2,fit.predict(test[fields])),row.mae,rtol=1e-8)
    print(f"卫星 {len(scores)} 组滚动留出 MAE 复算一致")


def review():
    city = pd.read_parquet(HERE / "全国城市日.parquet").query("yrd41 and qualified")
    harvest = city[city.date.dt.month.isin([6,10,11])]
    north = city[city.city.isin("蚌埠 淮北 亳州 宿州 阜阳 淮南 徐州 连云港 宿迁 淮安 盐城".split())]
    assert (len(harvest),harvest.heavy.sum(),len(north),north.heavy.sum()) == (10898,0,11837,98)
    pairs = pd.read_csv(HERE / "同网格未检出日配对.csv.gz",parse_dates=["time","control_time"])
    assert len(pairs) == 1566 and (pairs.time.dt.hour == pairs.control_time.dt.hour).all()
    np.testing.assert_allclose(pairs.event - pairs.control,pairs.difference,atol=1e-12)
    np.testing.assert_allclose(pairs[["event","control","difference"]].mean(),[3.2522393,1.8061311,1.4461082],atol=1e-6)
    dust = pd.read_csv(HERE / "三月五城逐小时.csv",parse_dates=["time"])
    suqian = dust[dust.city.eq("宿迁")]
    baseline = suqian[suqian.time.dt.day < 23].dust
    current = suqian[suqian.time.dt.day == 23].dust
    assert (len(baseline),len(current)) == (72,24)
    np.testing.assert_allclose(current.mean()-baseline.mean(),3.9139782,atol=1e-7)
    ledger = pd.read_csv(HERE / "更新原始输入校验.csv.gz").drop_duplicates("sha256")
    subtotal = ledger.groupby("source").bytes.sum()
    assert (subtotal["卫星"],subtotal["气象"],subtotal.sum()) == (40688405,85150365,4558091453)
    print("季节、地理分布、未检出日配对、三月细沙尘和来源字节均通过")


if __name__ == "__main__":
    ground()
    fire()
    satellite()
    review()
