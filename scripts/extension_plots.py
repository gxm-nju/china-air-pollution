from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import fontManager,FontProperties
from ground import ROOT,YRD
E=ROOT/'扩展实验';G=E/'图表';M=E/'多源复算';B=ROOT/'多源数据与实验'
def configure():
    font=Path('/Library/Fonts/Arial Unicode.ttf')
    if font.exists():fontManager.addfont(str(font));plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    else:
        available={f.name for f in font_manager.fontManager.ttflist}
        for family in ('PingFang SC','Noto Sans CJK SC','Microsoft YaHei'):
            if family in available:
                plt.rcParams['font.family']=family
                break
    plt.rcParams['axes.unicode_minus']=False
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
def done(fig,name):
    fig.tight_layout();fig.savefig(G/(name+'.png'),dpi=150,bbox_inches='tight',facecolor='white');plt.close(fig)
def main(public=False):
    global G
    if public:
        G=ROOT/"reproduced/figures"
    configure();G.mkdir(parents=True,exist_ok=True)
    cov=pd.read_csv(ROOT/'metadata/来源逐月覆盖.csv' if public else E/'规模核算/来源逐月覆盖.csv')
    rows=[cov['地面日数']/cov['月份日数'],cov['ERA5四要素有效城市小时']/cov['月份日数']/984,cov['ERA5边界层有效城市小时']/cov['月份日数']/984,cov['L3研究窗口日数']/cov['月份日数']]
    fig,ax=plt.subplots(figsize=(10,2.7));im=ax.imshow(rows,aspect='auto',vmin=0,vmax=1,cmap='YlGnBu')
    ax.set_yticks(range(4),['地面站点日文件','ERA5 四要素','ERA5 边界层','卫星 L3 日窗口']);ax.set_xticks(range(0,36,3),cov['月份'][::3],rotation=30,ha='right')
    ax.set_title('历史 134 日基线：2023—2025 年逐月覆盖率');fig.colorbar(im,ax=ax,shrink=.8);done(fig,'01_逐月覆盖')
    q=pd.read_csv(ROOT/'results/火点相同锚点对照.csv' if public else M/'results/火点相同锚点对照.csv');fig,ax=plt.subplots(figsize=(8,3.4))
    for i,(k,v) in enumerate(q.groupby('scope',sort=False)):
        color=['#137b75','#a65931'][i];x=v.lag.to_numpy()+i*.5
        ax.errorbar(x,v.mean_delta,yerr=[v.mean_delta-v.ci_low,v.ci_high-v.mean_delta],label=k,marker='o',color=color,capsize=4)
    ax.axhline(0,color='#7b827c',lw=.7);ax.set(xlabel='距观测火点的时间（小时）',ylabel='增幅之差（µg/m³）',title='历史 134 日基线：下风与上风城市的 PM₂.₅ 增幅差');ax.legend(fontsize=9);done(fig,'02_火点滞后')
    sat=(pd.read_parquet(ROOT/'data/integrated/no2_four_sources.parquet') if public else pd.read_csv(M/'data/integrated/no2_four_sources.csv'));sat['柱浓度组']=pd.qcut(sat.column_1e15,4,labels=['Q1','Q2','Q3','Q4'])
    fig,axes=plt.subplots(1,4,figsize=(10,3.1),sharex=True,sharey=True)
    for ax,(k,v) in zip(axes,sat.groupby('柱浓度组',observed=True)):
        ax.scatter(v.blh_m,v.no2,s=4,alpha=.21,color='#137b75');ax.set_title(f'{k} · n={len(v)}');ax.set_xlabel('边界层高度 (m)')
    axes[0].set_ylabel('地面 NO₂ (µg/m³)');fig.suptitle('2023 年第一季度 · 按卫星 NO₂ 柱浓度四分位分组');done(fig,'03_柱浓度与地面')
    loc=pd.read_csv(ROOT/'data/cleaned/case_city_grid.csv' if public else B/'data/cleaned/case_city_grid.csv').dropna(subset=['source_group'])
    fire=pd.read_parquet(ROOT/'data/integrated/火点格中心与农田.parquet' if public else M/'data/integrated/火点格中心与农田.parquet');fire=fire[fire.time.dt.to_period('M')==pd.Period('2024-10')]
    dd=pd.read_parquet(ROOT/'data/integrated/全国城市日.parquet' if public else E/'跨期分析/全国城市日.parquet');dd=dd[dd.yrd41&dd.qualified&dd.date.dt.to_period('M').eq(pd.Period('2024-10'))]
    coords=loc.merge(dd.groupby('city').pm25.max(),on='city');fig,ax=plt.subplots(figsize=(6.7,4.4))
    ax.scatter((fire.lon_bin+.5)/100,(fire.lat_bin+.5)/100,s=1,color='#b77854',alpha=.24,label='火点时空格中心')
    pt=ax.scatter(coords.lon,coords.lat,c=coords.pm25,s=24,edgecolors='#193e40',linewidths=.5,cmap='viridis');fig.colorbar(pt,ax=ax,label='城市最高日均 PM₂.₅（µg/m³）');ax.set(xlabel='东经（°）',ylabel='北纬（°）',title='2024 年 10 月 · 长三角及外围火点与城市浓度');ax.legend(fontsize=8);done(fig,'04_秋季火点空间分布')
    net=pd.read_csv(ROOT/'results/nanjing_network_best.csv' if public else M/'results/nanjing_network_best.csv').nlargest(6,'r');places=loc.set_index('city');nj=places.loc['南京'];fig,ax=plt.subplots(figsize=(7,4))
    for r in net.itertuples():
        c=places.loc[r.source];ax.annotate('',xy=(nj.lon,nj.lat),xytext=(c.lon,c.lat),arrowprops=dict(arrowstyle='->',color='#387b78',alpha=.8,lw=r.r*4))
        ax.scatter(c.lon,c.lat,c='#397e79',s=18);ax.annotate(f'{r.source} · {r.lag}h',(c.lon,c.lat),xytext=(4,5),textcoords='offset points',fontsize=9)
    ax.scatter(nj.lon,nj.lat,c='#ba6041',s=40);ax.annotate('南京',(nj.lon,nj.lat),xytext=(4,-12),textcoords='offset points');ax.margins(.21)
    ax.set(title='历史探索：风向筛选后与南京相关性最高的六座城市',xlabel='东经（°）',ylabel='北纬（°）');done(fig,'05_南京候选网络')
if __name__=='__main__':main()
