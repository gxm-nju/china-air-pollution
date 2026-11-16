from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
data = pd.read_csv(root/'结果/跨季节误差.csv')
for name in ('PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', 'Arial Unicode MS'):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        plt.rcParams['font.family'] = name
        break
plt.rcParams['axes.unicode_minus'] = False
fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.7), sharex=True, sharey=True)
fig.subplots_adjust(left=.09, right=.97, bottom=.23, top=.76, wspace=.15)
seasons = ['春', '夏', '秋', '冬']
for ax, period, title in zip(axes, ['仅一月','全年'], ['用 2023 年 1 月训练','用 2023 年全年训练']):
    for year, offset, color in [(2024,-.12,'#4c7185'),(2025,.12,'#aa7059')]:
        observed = data.query('year==@year and train_period==@period').set_index('season').reindex(seasons)
        y = np.arange(4) + offset
        x = observed.delta.to_numpy()
        ax.hlines(y, observed.week_low, observed.week_high, color=color, lw=2)
        ax.scatter(x, y, color=color, s=46, label=str(year), zorder=3)
    ax.axvline(0, color='#6d6965', lw=1)
    ax.set_title(title, fontsize=13, loc='left')
    ax.set_yticks(np.arange(4), [s+'季' for s in seasons])
    ax.grid(axis='x', alpha=.15)
    ax.spines[['top','right','left']].set_visible(False)
    ax.tick_params(axis='y', length=0)
axes[0].invert_yaxis()
fig.legend(*axes[0].get_legend_handles_labels(), loc='upper right', bbox_to_anchor=(.98,.88), frameon=False, ncol=2)
fig.text(.09,.92,'加入气象后，卫星估计地面 NO₂ 的误差在哪些季节下降？',size=19,weight='bold')
fig.text(.09,.13,'横轴为加入气象后的平均绝对误差减去仅用卫星的误差（µg/m³）。负值表示预测更准。',size=10.5)
fig.text(.09,.065,'长三角 41 城，2024—2025 年分季节测试。线段为按日历周重抽样的 95% 区间。来源：Sentinel-5P L2、地面站、ERA5。',size=9.5)
fig.savefig(root/'结果/气象对各季节NO2估计的影响.png', dpi=170, facecolor='white')
