"""Render the two follow-up tests directly from their reported estimates."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Hiragino Sans GB','Noto Sans CJK SC','Noto Sans CJK JP','Arial Unicode MS','DejaVu Sans'],
                     'axes.unicode_minus':False,'font.size':12})
fig, axes = plt.subplots(2,1,figsize=(10,8),layout='constrained')
for ax in axes:
    ax.spines[['top','right','left']].set_visible(False)
    ax.spines['bottom'].set_color('#C9C4BC')
    ax.axhline(0,color='#6A6966',linewidth=1)
    ax.grid(axis='y', alpha=.15)
q = pd.read_csv(ROOT/'火点新旧样本对照.csv').query("scope == '全部共同锚点'")
x = np.arange(len(q))
for offset,tag,color,label in [(-.11,'134日','#788D9D','历史样本：811 个锚点'),(.11,'新样本','#9B665B','扩展样本：4,299 个锚点')]:
    mean = q['mean_delta_'+tag]
    axes[0].errorbar(x+offset,mean,yerr=[mean-q['ci_low_'+tag],q['ci_high_'+tag]-mean],
                     color=color,fmt='o',label=label,capsize=4)
axes[0].set_xticks(x,[f'{h} 小时' for h in q.lag])
axes[0].set_title('扩大样本后，上下风城市的浓度变化差如何改变？',loc='left')
axes[0].set_ylabel(r'PM$_{2.5}$ 平均差（$\mu g/m^3$）')
axes[0].legend(frameon=False,loc='upper right',ncols=2)
m = pd.read_csv(ROOT/'各月加入气象的配对误差变化.csv')
x = np.arange(len(m))
axes[1].bar(x,m.delta_mae,color=np.where(m.delta_mae>0,'#A87364','#637F89'),width=.55)
axes[1].errorbar(x,m.delta_mae,yerr=[m.delta_mae-m.ci_low,m.ci_high-m.delta_mae],fmt='none',ecolor='#494950',capsize=3)
axes[1].set_xticks(x,[f'{int(t[-2:])} 月' for t in m.month])
axes[1].set_title('预测下一个月的地面 NO$_2$：加入气象后，误差怎样变化？',loc='left')
axes[1].set_ylabel(r'MAE 变化（$\mu g/m^3$）')
axes[1].set_xlabel('2023 年测试月份；负值表示误差下降，误差线为按日期重抽样的 95% 区间')
fig.savefig(ROOT/'地面扩展结果.png',dpi=170)
# 两组样本分别有811与4299个锚点；共同锚点仅指每组内部五个滞后可比较。
