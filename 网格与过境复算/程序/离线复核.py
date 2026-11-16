"""从随仓库发布的逐事件、逐城市预测和输入清单复核报告数字。"""
from pathlib import Path
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
results = root / '结果'
ledger = pd.read_csv(root / '记录/本次区域输入清单.csv')
assert ledger.file.is_unique and ledger.sha256.is_unique
counts = ledger.groupby('source').bytes.agg(['count', 'sum'])
assert tuple(counts.loc['ERA5']) == (111, 266219820)
assert tuple(counts.loc['S5P']) == (142, 16478285)
events = pd.read_csv(results / '火点风向对照.csv.gz').dropna(subset=['gridwind'])
assert len(events) == 4146
np.testing.assert_allclose([events.citywind.mean(), events.gridwind.mean()], [4.02461328, 4.05627221], atol=1e-7)
pairs = pd.read_csv(results / '网格风未检出日配对.csv.gz')
assert len(pairs) == 638
np.testing.assert_allclose((pairs.gridwind_e-pairs.gridwind_c).mean(), 1.20504990, atol=1e-7)
pred = pd.read_csv(results / 'NO2验证预测.csv.gz')
for row in pd.read_csv(results / 'NO2验证.csv').itertuples():
    sample = pred[pred.run.eq(row.run)]
    assert len(sample) == row.n_test and sample.date.nunique() == row.test_days
    mae = [(sample[col]-sample.no2).abs().mean() for col in ('pred0', 'pred1')]
    np.testing.assert_allclose(mae, [row.mae0, row.mae1], atol=1e-8)
print('区域输入清单字节、火点双重对照和五组 NO₂ 预测指标均与已发布结果一致。')
