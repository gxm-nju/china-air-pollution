import math
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.patches import FancyBboxPatch
from ground import CL,IN,OUT,YRD
F=OUT/'图表';F.mkdir(exist_ok=True)
for f in ['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/STHeiti Medium.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
    if os.path.isfile(f):
        fm.fontManager.addfont(f);plt.rcParams['font.family']=[fm.FontProperties(fname=f).get_name(),'DejaVu Sans'];break
plt.rcParams.update({'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white','axes.edgecolor':'#bebbb5','font.size':10,'savefig.dpi':165})
GREEN='#176957'; ORANGE='#b65429';INK='#263c39';MUT='#546660'
def new(title,subtitle):
    fig,ax=plt.subplots(figsize=(10.0,5.8));fig.subplots_adjust(top=.78,bottom=.22,left=.12,right=.94)
    fig.text(.066,.923,title,fontsize=20,weight='bold',color=INK);fig.text(.067,.855,subtitle,fontsize=10.5,color=MUT);return fig,ax
def save(fig,name,note):
    fig.text(.067,.052,note,fontsize=9,color=MUT);fig.savefig(F/name);plt.close(fig)
def run():
    z=pd.read_parquet(IN/'yrd_city_hour.parquet');coords=pd.read_csv(CL/'cities.csv').set_index('city').loc[YRD]
    day=z.groupby('date').agg(pm=('PM2.5','count'),met=('blh_m','count'))
    dates=day.index;sat=pd.read_parquet(CL/'satellite_city_orbit.parquet')
    sc=sat[sat.no2_mol_m2.notna()].groupby('date').city.nunique().reindex(dates)/41
    firetab=pd.read_csv(OUT/'fire_quality.csv');available=firetab.file.str.contains('2024').sum()/3
    fig,ax=new('哪些日期有可用于融合的数据？','2024 年 10 月 · 长三角 41 城 · 每列为一天，灰色表示未取得轨道数据')
    arr=np.stack([day.pm/(41*24),day.met/(41*24),np.repeat(available,len(day)),sc])
    cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#e1e3df')
    im=ax.imshow(arr,vmin=0,vmax=1,cmap=cmap,aspect='auto',interpolation='nearest');ax.set_yticks(range(4),['PM₂.₅ 城市小时','ERA5 城市小时','FIRMS 源文件','S5P 有效城市']);ax.set_xticks([0,4,9,14,19,24,30],[1,5,10,15,20,25,31]);ax.set_xlabel('十月日期');fig.colorbar(im,ax=ax,fraction=.03,pad=.03,label='覆盖比例')
    save(fig,'01_覆盖.png','地面、气象以 41×24 为每日分母；火点分母为 3 种传感器。OSM 为一次静态快照。')
    v=pd.read_csv(OUT/'Q1_火点与下风向浓度.csv')
    fig,ax=new('火点出现后，两侧城市的 PM₂.₅ 差值怎样变化？','横轴从火点所在小时开始 · 8 个火点密集日 · 上下风各选一城')
    ax.plot(v.lag_h,v.mean_diff,color='#738a93',label='同时刻：下风城市减上风城市',lw=2.3);ax.plot(v.lag_h,v.mean_adjusted,color=ORANGE,label='再减去事前 6 小时的平均差',lw=2.6)
    ax.axhline(0,color='#737b77',lw=.8);ax.set(xlim=(0,48),xlabel='火点发生后的小时数',ylabel='PM₂.₅ 平均差（µg/m³）');ax.grid(axis='y',alpha=.15);ax.legend(frameon=False)
    save(fig,'02_火点滞后.png',f'来源：FIRMS、国控站、ERA5。每个滞后有 {v.pairs.min()}–{v.pairs.max()} 组有效配对，多个火点可共用城市。')
    a=pd.read_csv(OUT/'Q2_卫星与地面配对.csv').dropna(subset=['NO2','blh_m'])
    fig,ax=new('同一轨卫星过境时，地面 NO₂ 怎样随边界层变化？','2024 年 10 月 1 日 · QA > 0.75 的 10 城 · 两端点分别按产品起止时刻所在小时配对')
    norm=Normalize(a.satellite_umol_m2.min(),a.satellite_umol_m2.max());cm=plt.get_cmap('viridis')
    for city,g in a.groupby('city'):
        g=g.sort_values('time_bjt');c=cm(norm(g.satellite_umol_m2.iloc[0]));ax.plot(g.blh_m,g.NO2,color=c,alpha=.55,lw=1.6);ax.scatter(g.blh_m.iloc[0],g.NO2.iloc[0],s=30,facecolor='white',edgecolor=c);ax.scatter(g.blh_m.iloc[-1],g.NO2.iloc[-1],s=35,color=c)
    fig.colorbar(ScalarMappable(norm=norm,cmap=cm),ax=ax,pad=.02,label='卫星对流层 NO₂ 柱（µmol/m²）')
    ax.set(xlabel='边界层高度（m）',ylabel='地面 NO₂（µg/m³）');ax.grid(alpha=.15)
    save(fig,'03_柱浓度与边界层.png','空心为轨道时窗起点小时，实心为终点小时。来源：S5P、国控站、ERA5。')
    fires=pd.read_parquet(CL/'firms/year=2024/events.parquet')
    counts=pd.read_csv(OUT/'fire_daily.csv');dt=pd.to_datetime(counts.loc[counts.fires.idxmax(),'date'])
    f=fires[(fires.time_bjt.dt.normalize()==dt)&~fires.recurring_heat_flag&fires.gx.between(114,124)&fires.gy.between(27,36)]
    day=z[z.date.eq(dt)].groupby('city')['PM2.5'].agg(['mean','count']).join(coords[['lon','lat']]);day=day[day['count']>=20]
    fig,ax=new('火点最多的一天，哪些城市的 PM₂.₅ 较高？',f'{dt:%Y 年 %m 月 %d 日} · 彩色圆点为城市站点中心，灰色叉号为筛选后的火点')
    ax.scatter(f.longitude,f.latitude,s=9,c='#81756a',alpha=.35,marker='x',linewidths=.6);im=ax.scatter(day.lon,day.lat,c=day['mean'],cmap='YlOrRd',edgecolors='#63584f',lw=.65,s=46);fig.colorbar(im,ax=ax,pad=.02,label='城市日均 PM₂.₅（µg/m³）')
    for name in ['南京','上海','合肥','阜阳','徐州']:
        if name in day.index:ax.annotate(name,(day.loc[name,'lon'],day.loc[name,'lat']),xytext=(4,4),textcoords='offset points',fontsize=8)
    ax.set(xlim=(114,124),ylim=(27,36),xlabel='东经（度）',ylabel='北纬（度）');ax.set_aspect(1/math.cos(math.radians(32)));ax.grid(alpha=.13)
    save(fig,'04_火点空间分布.png',f'来源：国控站、FIRMS。图中 {len(f)} 个筛选后事件、{len(day)} 座城市；火点未作农田分类。')
    edges=pd.read_csv(OUT/'Q3_风向滞后关联边.csv');e=edges[edges.retained];selected=e[e.downstream=='南京']
    fig,ax=new('哪些城市的小时浓度变化在南京之前出现？','十月前 20 天选滞后，后 11 天验证 · 只绘指向南京且通过预设阈值的候选边')
    names=set(selected.upstream)|{'南京'}
    if len(names)>1:
        for row in selected.itertuples():
            p=coords.loc[row.upstream];q=coords.loc['南京'];ax.annotate('',xy=(q.lon,q.lat),xytext=(p.lon,p.lat),arrowprops=dict(arrowstyle='-|>',lw=2,color=GREEN,shrinkA=6,shrinkB=8));ax.text((p.lon+q.lon)/2,(p.lat+q.lat)/2+.05,f'{row.lag_h} h · r={row.test_r:.2f}',fontsize=9)
        x=coords.loc[sorted(names)]
        ax.scatter(x.lon,x.lat,c=[ORANGE if n=='南京' else GREEN for n in x.index],s=75,zorder=3)
        for n,p in x.iterrows():ax.annotate(n,(p.lon,p.lat),xytext=(3,10),textcoords='offset points',fontsize=11)
        ax.set(xlim=(x.lon.min()-.35,x.lon.max()+.35),ylim=(x.lat.min()-.25,x.lat.max()+.35))
    ax.set(xlabel='东经（度）',ylabel='北纬（度）');ax.grid(alpha=.12)
    save(fig,'05_南京风向关联.png','来源：国控站、ERA5。r 为验证期小时一阶差分相关；箭头表达风向约束的时间关联。')
    fig,ax=plt.subplots(figsize=(10,4.6));ax.axis('off');ax.set(xlim=(0,10),ylim=(0,5))
    fig.text(.07,.91,'数据怎样汇成城市小时和污染过程？',fontsize=19,color=INK,weight='bold')
    def boxnode(x,y,width,txt,fc):
        ax.add_patch(FancyBboxPatch((x,y),width,.53,boxstyle='round,pad=.055',facecolor=fc,edgecolor='none'))
        ax.text(x+width/2,y+.26,txt,ha='center',va='center',fontsize=9)
    labs=['国控站小时浓度','NASA FIRMS 火点','ERA5 五项气象','Sentinel-5P / 质量层','OSM 道路 / 工业用地']
    mids=['站码 → 城市 / 小时','去重 → 火点网格 / 小时','0.25° 网格 / 小时','站点像元 / 轨道时窗','站点网格 / 快照']
    for i,(label,mid) in enumerate(zip(labs,mids)):
        y=3.8-i*.77;boxnode(.05,y,2.0,label,'#e5eeea');boxnode(2.72,y,2.75,mid,'#eef0ed');ax.annotate('',xy=(2.65,y+.27),xytext=(2.12,y+.27),arrowprops={'arrowstyle':'->','color':MUT});ax.annotate('',xy=(6.2,2.48),xytext=(5.55,y+.27),arrowprops={'arrowstyle':'->','color':'#a6b3ac'})
    boxnode(6.22,2.2,1.66,'城市 × 小时','#cfe4d8');boxnode(8.25,2.2,1.55,'城市日 / 过程','#f3dfcc');ax.annotate('',xy=(8.18,2.47),xytext=(7.94,2.47),arrowprops={'arrowstyle':'->','color':MUT})
    fig.savefig(F/'06_数据血缘.png');plt.close(fig)
if __name__=='__main__':run()
