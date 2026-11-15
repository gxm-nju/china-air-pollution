"""从已计算的结果表生成独立的中文 HTML 报告及可单独引用的图片。"""
from pathlib import Path
import base64
import calendar
from html import escape
import json
import platform
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LogNorm
from matplotlib.ticker import MaxNLocator
import sklearn
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'results';R=ROOT/'data/raw';I=ROOT/'data/integrated'
F=O/'figures';F.mkdir(exist_ok=True)
for system_font in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',):
    if Path(system_font).exists():
        font_manager.fontManager.addfont(system_font)
for family in ['Noto Sans CJK SC','Noto Sans CJK JP','PingFang SC','Microsoft YaHei']:
    if family in [f.name for f in font_manager.fontManager.ttflist]:
        plt.rcParams['font.family']=[family,'DejaVu Sans'];break
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'figure.dpi':130,'axes.labelcolor':'#213838','text.color':'#152e2e','xtick.color':'#395352','ytick.color':'#395352'})
teal='#00746f';red='#ad492e'
def get(name):return json.loads((O/name).read_text())
def md(name):return pd.read_csv(O/name)
def output(fig,name):
    fig.tight_layout()
    fig.savefig(F/name,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    return '<img src="data:image/png;base64,'+base64.b64encode((F/name).read_bytes()).decode()+'" alt="'+escape(name)+'">'
def table(df,fields,labels,digits=2):
    frame=df[fields].copy();frame.columns=labels
    return frame.to_html(index=False,border=0,na_rep='—',float_format=lambda x:f'{x:,.{digits}f}')
def url(link,label):
    return '<a href="'+escape(str(link),quote=True)+'">'+escape(str(label))+'</a>'
def main():
    fire,ground,fusion=get('fire_summary.json'),get('ground_summary.json'),get('fusion_summary.json')
    bullet=md('monthly_bulletins.csv');ground_q=md('ground_daily_qc.csv').query("metric=='pm25'").copy()
    ground_q['month']=ground_q.date.str[:7];ground_q=ground_q.groupby('month').nonempty_hours.sum()
    era=md('era5_coverage.csv').groupby('month').sum(numeric_only=True)
    ms=sorted(bullet.month.unique())
    denom=np.array([calendar.monthrange(*map(int,m.split('-')))[1]*24 for m in ms])
    sat_q=pd.read_csv(ROOT/'logs/satellite_daily_windows.csv',dtype={'day':str})
    sat_days=sat_q.groupby(sat_q.day.str[:4]+'-'+sat_q.day.str[4:6]).size().reindex(ms,fill_value=0)
    coverage=np.vstack([np.ones(36),np.ones(36),ground_q.reindex(ms,fill_value=0)/denom,era.ws_ms/(denom*41),era.blh_m/(denom*41),sat_days/(denom/24)])
    fig,ax=plt.subplots(figsize=(10,2.8));im=ax.imshow(coverage,vmin=0,vmax=1,cmap='YlGnBu',aspect='auto',interpolation='nearest')
    ax.set_yticks(range(6),['公报（月）','火点年档覆盖（月）','站点有值小时','ERA5 风速','ERA5 边界层','S5P 日格文件']);ax.set_xticks(range(0,36,3),[s[2:] for s in ms[::3]],rotation=35,ha='right')
    fig.colorbar(im,ax=ax,fraction=.025,pad=.025,label='覆盖比例')
    pic1=output(fig,'01_覆盖率.png')
    lags=md('fire_lag.csv')
    paired=pd.read_csv(I/'fire_wind_sector_contrasts.csv.gz')
    common=paired.pivot(index=['time','lat_grid','lon_grid'],columns='lag',values='delta_pm25').dropna()
    balanced=common.mean().rename('common_event_mean_delta').reset_index()
    balanced['common_gridhours']=len(common);balanced.to_csv(O/'fire_lag_same_events.csv',index=False)
    fig,ax=plt.subplots(figsize=(8.7,3));ax.axhline(0,color='#777',lw=.8)
    ax.fill_between(lags.lag,lags.ci_low,lags.ci_high,color='#bce2d9',alpha=.8,label='按起火日期重抽样的 95% 区间')
    ax.plot(lags.lag,lags.mean_delta,'o-',color=teal,label='各滞后可用事件')
    ax.plot(balanced.lag,balanced.common_event_mean_delta,'s--',color=red,label='五个滞后均可用的事件')
    ax.set(xlabel='滞后（小时）',ylabel='下风向减上风向（µg/m³）',xticks=lags.lag);ax.legend(fontsize=8,ncol=2)
    pic2=output(fig,'02_火点与风向滞后.png')
    n=pd.read_csv(I/'nanjing_dust_era5_hour.csv',parse_dates=['time'])
    fig,(ax,bx)=plt.subplots(2,1,figsize=(9,4.5),sharex=True,height_ratios=(2,1))
    ax.plot(n.time,n.PM10,'o-',ms=2.8,label='PM₁₀',color=red);ax.plot(n.time,n['PM2.5'],'o-',ms=2.8,label='PM₂.₅',color=teal);ax.set_ylabel('µg/m³');ax.legend()
    bx.plot(n.time,n.ws_ms,color=teal);bx.set_ylabel('风速（m/s）');bx.set_xticks(n.time.iloc[::6],n.time.iloc[::6].dt.strftime('%d日 %H时'),rotation=25,ha='right');bx.set_xlabel('北京时间，2025 年 11 月')
    pic3=output(fig,'03_南京沙尘过程.png')
    nc=md('nanjing_network_best.csv');local=pd.read_csv(ROOT/'data/cleaned/case_city_grid.csv').dropna(subset='source_group').set_index('city');nj=local.loc['南京']
    fig,ax=plt.subplots(figsize=(7.6,4.4));ax.scatter(local.lon,local.lat,c='#acbbb5',s=10);top=nc.head(6)
    for i,row in enumerate(top.itertuples()):
        a=local.loc[row.source];ax.annotate('',xy=(nj.lon,nj.lat),xytext=(a.lon,a.lat),arrowprops=dict(arrowstyle='->',color=teal,alpha=.8,lw=2.5*row.r))
        ax.annotate(row.source+' '+str(row.lag)+' h',(a.lon,a.lat),xytext=(-5,(8 if i%2 else -12)),textcoords='offset points',ha='center',fontsize=9)
    ax.scatter([nj.lon],[nj.lat],s=38,color=red);ax.annotate('南京',(nj.lon,nj.lat),xytext=(6,-10),textcoords='offset points',color=red)
    ax.set(xlabel='东经（°）',ylabel='北纬（°）',xlim=(116.65,120.05),ylim=(31.25,33.2));ax.set_aspect(1/np.cos(np.radians(32)))
    pic4=output(fig,'04_南京候选关联.png')
    fe=pd.read_csv(ROOT/'data/cleaned/fire_events/utc_2023.csv.gz',parse_dates=['local_slot'])
    start,end='2023-01-01','2023-03-31 23:59'
    sub=fe[fe.local_slot.between(start,end)&fe.lat_bin.between(2700,3499)&fe.lon_bin.between(11400,12299)]
    g=pd.read_csv(I/'ground_city_day.csv.gz');values=g[g.yrd41 & g.date.between(start,'2023-03-31')].groupby('city').pm25.mean()
    loc=local.join(values);fig,ax=plt.subplots(figsize=(8,5))
    a=ax.hist2d((sub.lon_bin+.5)/100,(sub.lat_bin+.5)/100,bins=[36,32],range=[(114,123),(27,35)],norm=LogNorm(vmin=1),cmin=1,cmap='YlOrBr')
    fig.colorbar(a[-1],ax=ax,shrink=.76,pad=.02,label='每格火点时空格数（对数色标）')
    sc=ax.scatter(loc.lon,loc.lat,c=loc.pm25,cmap='viridis',s=24,edgecolor='black',linewidth=.45);fig.colorbar(sc,ax=ax,shrink=.76,pad=.045,label='城市 PM₂.₅（µg/m³）')
    ax.set(xlabel='东经（°）',ylabel='北纬（°）');ax.set_aspect(1/np.cos(np.radians(32)));ax.annotate('南京',(nj.lon,nj.lat),xytext=(4,3),textcoords='offset points')
    pic5=output(fig,'05_第一季度火点与浓度空间分布.png')
    centers=md('episode_centers.csv');spring=md('spring_2023_windows.csv');peaks=md('fire_peak_weeks.csv').query("area=='全国'")
    b=bullet[bullet.region=='长三角'].copy();b['公报']=[url(s,'原文') for s in b.url]
    cols=['month','city_count','pm25','heavy_pct','good_pct','公报'];monthly=b[cols].copy();monthly.columns=['月份','长三角城市数','PM₂.₅ 均值','重度及以上天数占比 %','优良天数占比 %','来源']
    details=monthly.to_html(index=False,border=0,escape=False,float_format=lambda x:f'{x:g}')
    njd=md('nanjing_day.csv');stats=md('nanjing_network_best.csv').head(5)
    raw_total=sum(p.stat().st_size for p in R.rglob('*') if p.is_file())
    audited=pd.read_csv(O/'era5_coverage.csv');expected=41*1096*24
    miss=expected-audited.blh_m.sum();coverage_blh=100*(1-miss/expected)
    ctx=get('case_summary.json')
    pqa=get('parquet_qa.json')
    no=get('no2_summary.json')
    matches=pd.read_csv(I/'no2_four_sources.csv')
    fits=md('no2_model_metrics.csv').query('shift_h==0')
    fig,axes=plt.subplots(1,3,figsize=(9.6,3.4),sharey=True)
    matches['column_band']=pd.qcut(matches.column_1e15,3,labels=['较低','中间','较高'])
    for ax,(band,z) in zip(axes,matches.groupby('column_band',observed=True)):
        ax.scatter(z.blh_m,z.no2,s=8,color=teal,alpha=.22,edgecolors='none')
        cut=pd.qcut(z.blh_m,5,duplicates='drop')
        trend=z.groupby(cut,observed=True)[['blh_m','no2']].median()
        ax.plot(trend.blh_m,trend.no2,'o-',color=red,lw=1.6,ms=3.5)
        ax.set_title(f'{band}柱浓度 · n={len(z)}',fontsize=10)
        ax.set_xlabel('边界层高度（m）');ax.xaxis.set_major_locator(MaxNLocator(4))
    axes[0].set_ylabel('地面 NO₂（µg/m³）')
    pic6=output(fig,'06_同柱浓度组地面NO2与边界层.png')
    body=f"""<header><p class="kicker">大数据系统　·　中期项目实验记录</p><h1>中国城市重污染日从哪里来？</h1><p class="intro">同一场污染里，地面颗粒物、上风向火点和大气扩散条件各自提供什么证据？</p><p>研究窗口 2023.01—2025.12　｜　中国火点回溯至 2019 年　｜　运行记录 2026.11.15</p></header>
    <main><h2>本轮跑到了哪里</h2><p>下载并清洗了 7 年全国火点、103 天全国站点小时数据、36 期生态环境部公报和长三角 41 城三年逐小时 ERA5。另从 KNMI 取得 2023 年第一季度 90 幅 Sentinel‑5P 日栅格，提取沪苏浙皖四个 OSM 快照。火点对照、卫星 NO₂ 回归、过程聚类三个实验均已用真实数据跑通。五源覆盖期不同，三年全期归因仍未完成。本轮原始目录共 {raw_total:,} 字节，包含公报和站表等辅助材料。课程的 2 GB、各主源 200 MB、单源不超 80% 尚未整体验收。</p>
    <table><thead><tr><th>输入</th><th>本轮落盘与核验</th><th>用途</th></tr></thead><tbody>
    <tr><td>NASA FIRMS</td><td>21 份中国年表，558,827,644 字节</td><td>三种传感器，2019—2025 年</td></tr>
    <tr><td>监测总站数据，第三方逐日存档</td><td>103 / 1,096 天，201,040,663 字节</td><td>2023.01.01—04.01、12.01—12.12</td></tr>
    <tr><td>ERA5，经 Open-Meteo 提取</td><td>41 城 × 26,304 小时，50,172,333 字节</td><td>同一代表点取临近格点。风向、风速导出后重建 U/V</td></tr>
    <tr><td>Sentinel‑5P / KNMI CCI+ L3 fv2.0</td><td>第一季度 90 个日窗口，东部 40 × 44 格，1,407,763 字节</td><td>0.5° 日栅格，含柱浓度、有效时刻、观测数、云与不确定度</td></tr><tr><td>OpenStreetMap / Geofabrik</td><td>沪苏浙皖 4 份 2026 年 11 月静态 PBF，241,891,577 字节</td><td>41 个代表点所在的 0.25° 格内道路长度和工业用地面积</td></tr><tr><td>城市小时案例</td><td>2025.11.26—27，375 城，3 个文件 MD5 核对通过</td><td>同源监测数据的独立存档；不另计主来源</td></tr>
    <tr><td>公报、站表、春节日历</td><td>全国与长三角 72 条区域月记录；1,601 个站号；1,096 个日期</td><td>等级口径核验、站城关联和节期标记</td></tr></tbody></table>
    {pic1}<p class="caption">图 1 · 各来源的月份覆盖。地面站一行表示该月有任一非空 PM₂.₅ 读数的小时比例；火点一行表示对应年度文件已取得。ERA5 风速全期有值，边界层高度有效 {coverage_blh:.1f}%，2024 年 1 月 1 日 08 时至 7 月 1 日 07 时（北京时间）缺 {miss:,} 个城市小时。时段按导出数据逐时核对。</p>
    <h2>火点出现后，下风向城市的 PM₂.₅ 怎样变化？</h2><p>原始 {fire['raw']:,} 条探测，保留置信度达标且标为推定植被火的一般火点 {fire['retained']:,} 条。同一 0.01° 小格、同一北京时间 30 分钟内合并，得到 {fire['unique']:,} 个时空格。产品标记为其他静态热源的 {fire['static_type2']:,} 条另行计数。这里的计数单位是卫星探测格，一个实际火场可能占多格。七年中全国探测最集中的周均落在 2 月底至 4 月，地域峰值另见 fire_peak_weeks.csv。识别秸秆焚烧仍需要土地覆盖及作物收获季信息。</p>
    {table(peaks,['year','week_start','unique_slots'],['年份','全国最高周起始日（周一）','去重时空格数'],0)}
    <p>在有地面数据的 103 天，按 0.25° 网格及小时汇总，选至少两个不同小格出现火点的网格小时。从 50 km 内最近气象城市取风，选距离火点 30—200 km、在来风或去风方向 ±45° 的城市，风速要求 ≥1 m/s。各城市先扣除火点前 24 小时的自身均值（至少 12 个有效小时），再计算下风组与上风组的差。每个合格网格小时等权。</p>{pic2}
    {table(lags,['lag','grids_hours','anchor_days','mean_delta','ci_low','ci_high'],['滞后 h','可比网格小时','锚定日期数','平均差 µg/m³','区间下限','区间上限'])}
    <p class="caption">图 2 · 地面站 × FIRMS × ERA5。6、12 小时差值为正，48 小时差值接近零。阴影由锚定日期整天重抽 1,500 次获得。同日和连续污染过程存在相关性，区间仅描述该样本的重抽样波动。虚线固定为五个滞后都可比较的 {len(common)} 个网格小时；同一城市的观测可以进入多个火点对照。样本主要位于冬春。</p>
    {pic5}<p class="caption">图 3 · 2023 年 1—3 月。底图为 0.25° 格网上的火点计数，圆点为长三角 41 个城市的有效 PM₂.₅ 日均浓度的季度均值。矩形覆盖 114—123°E、27—35°N；点的颜色与底图分别读各自色标。</p>
    <h2>重污染持续多久，哪些过程有较弱的扩散条件？</h2><p>先在每小时对城市内可匹配的有效站点等权平均，再按北京时间聚合。每天至少 20 个有效小时、PM₂.₅ 日均值严格超过 150 µg/m³，才进入本项目的 PM₂.₅ 重污染日清单；相邻日归一段，断档处分开。原始站号 {ground['observed_station_ids']:,}，本表可映射 {ground['mapped_station_ids']:,}，保留 {ground['valid_pm25_stationhours']:,} 个可定位的有效 PM₂.₅ 站点小时。未映射站号保留在原档、清洗 Parquet 和未匹配清单。对 ≥6 个连续小时读数相同的 {ground['pm25_flat_hours']:,} 个站点小时作质量标记。</p>
    <p>本轮可映射的 {ground['cities']} 城共有 {ground['heavy_citydays']} / {ground['eligible_citydays']:,} 个符合阈值的城市日，合并为 {ground['episodes']} 个城市过程。长三角 41 城为 {ground['yrd_heavy']} / {ground['yrd_eligible']:,}，合并为 {ground['yrd_episodes']} 个过程。南京 {ground['nj_eligible']} 个有效日中有 {ground['nj_heavy']} 个超过阈值，最高为 {ground['nj_peak']:.2f} µg/m³（{ground['nj_peak_date']}）。</p>
    <p>在 26 个长三角过程上按风速、边界层高度和上风城市过去 6 小时的 PM₂.₅ 均值聚类。要求至少 6 个小时存在上风站城的可用值，{fusion['eligible_episode_clusters']} 个过程入模，按标准化特征做 K-means，k=2，轮廓系数 {fusion['silhouette']:.3f}。两组上风向 PM₂.₅ 均接近 150 µg/m³，差异主要落在通风与混合高度。下表不能据以给出‘本地排放’与‘外来传输’的来源占比。</p>
    {table(centers,['cluster','n','ws_ms','blh_m','upwind_pm25_prev6'],['聚类编号','过程数','风速 m/s','边界层高度 m','上风 PM₂.₅ µg/m³'])}
    <h3>2023 年春节七天</h3>{table(spring,['area','window','eligible_citydays','pm25_cityday_mean','no2_cityday_mean'],['范围','窗口','有效 PM₂.₅ 城市日','PM₂.₅ µg/m³','NO₂ µg/m³'])}
    <p>南京和长三角 41 城的 NO₂ 均值在假期都低于前后七天，PM₂.₅ 均值则高于节前。这里比较的是有效城市日的算术平均；单个春节同时受到天气、区域传输与排放变化影响，未估计停工效应。</p>
    <h3>南京与哪些城市先后变化？</h3>{pic4}{table(stats,['source','lag','n','r'],['候选先行城市','滞后 h','有效小时对','相关系数'])}
    <p class="caption">图 4 · 2023 年 103 天中的南京探索性入边，图示相关最高的 6 个候选。对 30—250 km 城市比较 PM₂.₅ 的一阶小时差分，保留南京来风指向候选城市 ±45°、风速 ≥1 m/s 的接收时刻，在 1—6 小时中取最大相关，每组至少 48 对。全表保留每个候选的所有滞后；选择峰值会抬高相关系数，箭头不证明污染来自该城市。</p>
    <h2>南京为何需要单列 PM₁₀？</h2>{pic3}{table(njd[njd.pollutant.isin(['PM2.5','PM10'])],['date','pollutant','n_valid','mean_valid','maximum'],['日期','污染物','有效小时','小时值均值 µg/m³','小时峰值 µg/m³'])}
    <p>2025 年 11 月 27 日 11 时，南京 PM₁₀ 达 600 µg/m³，附近 ERA5 格点为 316° 来风、5.55 m/s，边界层 1,320 m。该日有效小时的 PM₂.₅ 均值为 58.90 µg/m³。同日南京生态环境部门通报沙尘输送过境、PM₁₀ 短时超过 500。这给过程标注提供独立文字证据。48 小时城市文件中 {ctx['city_coords']} / {ctx['cities']} 城匹配到代表点，{ctx['city_hours_with_local_fire']} 个城市小时在相同 0.25° 格、同一小时内有已筛选火点；这种时空重合只描述共现。</p>
    <p class="caption">图 5 · 逐小时缺测位置保持断线；横轴为北京时间。公开存档为城市列。均值按当日有效小时直接计算，官方日 AQI 及首要污染物需另行核验。来源见文末监测档案、气象接口与南京发布。</p>
    <h2>与官方重污染等级对照</h2><p>36 个月中，长三角公报有 13 个月报告重度及以上污染天数比例大于零。2023 年使用 41 城，2024、2025 年使用 31 城。保留 41 城维度和逐月纳入标记，另外 10 城在后两年的公报中标为范围外。2023 年 12 月长三角占比为 4.4%，附表逐城合计 56 个城市日，其中徐州 7 天、阜阳 6 天、南京 1 天。2024 年 2 月 31 城附表合计 27 个城市日。区域百分比本身无法还原具体日期。本轮 12 月站点仅覆盖前 12 天；全污染物 AQI 等级与 PM₂.₅ 单阈值另列。</p>
    <details><summary>展开 36 个月数值与公报原文</summary>{details}</details>
    <h2>卫星 NO₂ 相近时，气象能解释多少地面差异？</h2><p>从 Sentinel‑5P 的日栅格提取柱浓度、有效地方太阳时和观测数。每座城市取代表点所在的 0.5° 格，依据有效时刻折算北京时并匹配最近整点。{no['eligible_citydays']:,} 个候选城市日中有 {no['valid_satellite']:,} 个有效卫星值；再与地面 NO₂、边界层、风速和 OSM 街道及工业用地特征同表，余 {no['matched']:,} 个观测，覆盖 {no['cities']} 城、{no['days']} 天、{no['grids']} 个独立格点。L3 使用发布方质量处理和有效观测数；包内逐日有效格数与城市有效率可查。精确逐轨 L2 的 QA 图层不在这个日产品里。</p>
    {pic6}<p class="caption">图 6 · 2023 年 1—3 月，按卫星对流层 NO₂ 柱浓度的三个等频组绘图。每点是一个已匹配城市日，折线连接组内五个边界层高度分位段的地面 NO₂ 中位数。采用同一批有效记录比较全部模型。</p>
    {table(fits,['scheme','model','n','mae','r2'],['验证方式','模型','留出预测数','MAE（µg/m³）','留出 R²'],3)}
    <p>按卫星格点分 5 折留出，加入风速与对数边界层高度后，R² 从 0.407 提升至 0.522，MAE 从 6.23 降至 5.51 µg/m³。再加入道路密度和工业用地几乎没有改变误差。改为只用 1—2 月训练、3 月检验后，加入气象使 MAE 从 5.73 上升至 6.59 µg/m³。空间留出中约 0.115 的 R² 增量不能当作跨季节通用的解释比例。Ridge 系数固定为 1，标准化仅在训练折拟合。每个卫星格内的城市整组留出，避免同一日格同时进入训练集和空间测试集。另存了匹配时刻前后各移一小时的敏感性结果、所有留出预测和格点覆盖率。</p>
    <p>四份 OSM 取自 2026 年 11 月，在每个城市代表点的 0.25° 格内裁切已标注的可通车道路与工业用地，计算 km/km² 和面积比。工业面按要素面积相加，若图层中有叠置会重复计入。它们是城市结构的静态近似，不能用于直接测量 2023 年逐日排放。OSM © OpenStreetMap contributors，ODbL 1.0。上轮原工程另有一轨卫星和一个月的试跑，此表全部数值均在本包重新计算。</p>
    <h2>复现与剩余验收</h2><p>解压后从 README.md 运行，项目保留原计划 PDF、原始数据、清洗分区、城市小时与过程表、脚本、校验值和 AI_USAGE.md。DuckDB 已从 Parquet 独立核对 {pqa['ground']['valid_pm25']:,} 个有效 PM₂.₅ 站点小时、{pqa['fire']['rows']:,} 个火点时空格和 {pqa['era5']['rows']:,} 个 ERA5 城市小时。文件完整性校验见 logs/SHA256SUMS.csv。</p>
    <ol><li>地面站还有 {ground['missing']} 个日文件待补，获取范围以 ground_date_inventory.csv 为准。确认历年站号和迁站记录，复核未匹配站点。</li><li>已有 41 城代表点气象，需补边界层缺段和完整东部网格；固定热源历史复现、耕地掩膜和秋收季识别待补。</li><li>补齐 2023 年 4 月以后的 Sentinel‑5P 样本和逐轨 QA，检验不同季节与土地利用快照的敏感性。</li><li>已抽出站点、火点各 200 条，人工地图复核尚未执行。原计划的秋收专门叠加图、全期分型和五源有效体量仍待验收。</li></ol>
    <p class="sources">数据出处　{url('https://temis.pmc.knmi.cloud/airpollution/no2col/cci-no2-tropomi.php','ESA CCI+ / KNMI')}　{url('https://essd.copernicus.org/articles/17/4627/2025/','Glissenaar 等，L3 方法')}　{url('https://download.geofabrik.de/asia/china.html','Geofabrik / OSM')}　{url('https://www.openstreetmap.org/copyright','OSM 许可')}　{url('https://firms.modaps.eosdis.nasa.gov/country/','NASA FIRMS')}　{url('https://quotsoft.net/air/','王晓雷空气质量历史档案')}　{url('https://open-meteo.com/en/docs/historical-weather-api','ERA5 / Open-Meteo')}　{url('https://zenodo.org/records/20949804','Li, Gudongze · 城市小时档案，CC BY 4.0')}　{url('https://m.thepaper.cn/newsDetail_forward_32055671','南京发布转引南京生态环境')}　{url('https://www.mee.gov.cn/hjzl/dqhj/cskqzlzkyb/202410/W020241022604712605477.pdf','长三角 31 城名单')}　{url('https://docs.datastation.skyviewor.com/data-query/china-pollution/pollution-stations-list/','公开站点清单')}</p></main>"""
    css="""*{box-sizing:border-box}body{margin:0;color:#1d3232;font:16px/1.85 -apple-system,BlinkMacSystemFont,'Noto Sans CJK SC','Microsoft YaHei',sans-serif;background:#f5f4ee}header,main{width:min(980px,100%);margin:auto;padding:30px clamp(18px,5vw,62px)}header{background:#103e3e;color:#f4f4e9;border-top:6px solid #d19861;padding-top:40px;padding-bottom:32px}header p{margin:8px 0}.kicker{color:#f0c89b;font-weight:650;letter-spacing:.12em;font-size:14px}h1{font-size:clamp(26px,4.2vw,47px);line-height:1.3;margin:15px 0}.intro{font-size:19px}main{background:#fff}h2{border-top:1px solid #cbd6d0;padding-top:24px;margin:32px 0 12px;font-size:25px;line-height:1.4}h2:first-child{border:0;margin-top:0}h3{font-size:19px;margin-top:24px}img{max-width:100%;height:auto;display:block;margin:22px auto 8px}.caption,.sources{color:#445c59;font-size:14px}table{border-collapse:collapse;font-size:14px;width:100%;margin:12px 0}th,td{padding:7px 9px;border-bottom:1px solid #dbe2da;text-align:left}th{background:#e5eeea}details{background:#f2f5f1;padding:12px}summary{cursor:pointer;font-weight:650}a{color:#00726e}ol{padding-left:1.6em}@media(max-width:620px){table{font-size:12px;display:block;overflow-x:auto}td,th{padding:5px}header,main{padding-left:15px;padding-right:15px}}@media print{body{background:white}header,main{max-width:100%}h2,h3{break-after:avoid}img,table{break-inside:avoid}}"""
    (ROOT/'中国城市重污染日_阶段实验报告.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中国城市重污染日 · 阶段实验报告</title><style>'+css+'</style>'+body+'</html>')
if __name__=='__main__':
    main()
