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


if __name__ == "__main__":
    ground()
    fire()
    satellite()
