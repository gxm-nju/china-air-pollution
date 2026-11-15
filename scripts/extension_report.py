"""Build the standalone execution report from verified tables and figures."""
from pathlib import Path
from html import escape
import json,base64
import pandas as pd
from ground import ROOT
E=ROOT/'扩展实验';A=E/'跨期分析';Q=E/'核验';D=E/'规模核算';M=E/'多源复算/results';B=ROOT/'多源数据与实验'
def read(p):return pd.read_csv(p)
def table(f):return '<div class="table">'+f.to_html(index=False,border=0,na_rep='缺数据',float_format=lambda x:f'{x:,.2f}')+'</div>'
def pic(name,caption):
    p=next((E/'图表').glob(name+'*.png'))
    return '<figure><img alt="'+escape(caption)+'" src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"><figcaption>'+escape(caption)+'</figcaption></figure>'
def main():
    g=read(A/'地面结果分组.csv');overall=g[g.样本=='全部'].set_index('区域')
    q=read(A/'逐日补采队列.csv');fy=read(M/'火点相同锚点对照.csv')
    years=read(A/'春节比较.csv');roster=read(A/'站点匹配明细.csv')
    ev=read(A/'全国重污染过程.csv');cent=read(M/'episode_centers.csv');net=read(M/'nanjing_network_best.csv').head(6)
    vals=read(D/'五源实际体量.csv');cov=read(D/'来源逐月覆盖.csv');coverage=read(Q/'站点200条含区划补核.csv').补核判定.value_counts().rename_axis('站点抽样结论').reset_index(name='条数')
    no2=read(M/'no2_model_metrics.csv');no2=no2[no2.shift_h==0].drop(columns='shift_h');facts=json.loads((M/'fusion_summary.json').read_text())
    ff=read(M/'火点耕地口径.csv').iloc[0];hrs=read(A/'逐日质量.csv')
    f12=fy.query("scope=='全部共同锚点' and lag==12").iloc[0];c12=fy.query("scope!='全部共同锚点' and lag==12").iloc[0]
    s3=json.loads((M/'no2_summary.json').read_text())
    old=json.loads((ROOT/'results/summary.json').read_text());nx=read(Q/'南京12日独立抽查.csv')
    origin=read(B/'results/ground_date_inventory.csv');fire=read(Q/'火点200条空间核验.csv')
    yrd=overall.loc['长三角41城'];nj=overall.loc['南京'];nation=overall.loc['全国']
    observed=pd.DatetimeIndex(sorted(q.loc[q.ground,'date'])).to_series().reset_index(drop=True)
    intervals=[(v.min().strftime('%Y-%m-%d'),v.max().strftime('%Y-%m-%d')) for _,v in observed.groupby(observed.diff().ne(pd.Timedelta(days=1)).cumsum())]
    coverage_text='、'.join(a+' 至 '+b if a!=b else a for a,b in intervals)
    if len(intervals)>12:coverage_text=f'{len(intervals)} 段不连续日期，详见逐日补采队列'
    page=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中国城市重污染日从哪里来 · 独立实验执行报告</title><style>
    *{box-sizing:border-box}body{margin:0;background:#efeee7;color:#1e3333;font:16px/1.73 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}main{max-width:1020px;margin:30px auto;background:#fff;padding:4% 5%;border-top:6px solid #23665e}h1{font-size:clamp(29px,4.5vw,46px);line-height:1.2;letter-spacing:-.04em}h2{font-size:24px;margin-top:2em;padding-top:12px;border-top:1px solid #bfcfc9}h3{font-size:19px}p{margin:.75em 0}.date,figcaption{color:#506761;font-size:14px}figure{margin:1.3em 0}img{max-width:100%;height:auto;display:block}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dae1db;padding:.45em .65em}th{color:#194941;background:#eef4f0}.table{overflow-x:auto}a{color:#066657}code{word-break:break-all;background:#edf2ef;padding:.1em .25em}strong{color:#0c554b}@media print{body,main{background:#fff;margin:0;padding:0}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}main{max-width:none}}</style><main>''',
    '<p class="date">2026 年 11 月 15 日 · 大数据系统中期项目 · Mac 工作区复算</p><h1>中国城市重污染日从哪里来</h1><p>独立实验执行报告</p>',
    f'<p>实测的 {int(q.ground.sum())} 天里，长三角 41 城有 {int(yrd.合格城市日):,} 个合格城市日。其中 {int(yrd.重污染城市日)} 个日均 PM₂.₅ 超过 150 µg/m³，合并为 {int(ev.yrd41.sum())} 段同城连续过程。南京有 {int(nj.合格城市日)} 个合格日，最高日均浓度为 {nj.最高城市日均PM25:.2f} µg/m³。覆盖不连续，以上次数仅适用于已观测日期。</p>',
    '<h2>计划覆盖到哪里</h2>',
    f'<p>原计划见 <code>docs/项目计划书.pdf</code>。原十月试验和此前三个压缩包已归入同一工程。复核了 49 项原始试验输入和归档内 589 条 SHA-256；另有一份校验表。新结果保存到“扩展实验”。</p>',
    f'<p><b>地面</b>　全国站点日文件 {int(q.ground.sum())}/1,096。目前样本覆盖 {coverage_text}。另有 2025 年 11 月 26—27 日城市级沙尘案例，单列 PM₁₀，不增加站点日文件计数。</p>',
    f'<p><b>ERA5</b>　长三角 41 个城市代表点共 {facts["era5_cityhours"]:,} 城市小时，风速、风向、气温、地面气压齐全。边界层有效 {facts["era5_valid_blh"]:,} 城市小时，北京时间 2024 年 1 月 1 日 08 时至 7 月 1 日 07 时连续缺测。原十月五变量网格按 UTC 整月提供，在北京时间从 10 月 1 日 08 时起。计划要求的东部全网格三年资料仍缺；代表点缺口没有插值填补。</p>',
    f'<p><b>Sentinel-5P</b>　2023 年一季度有连续 {s3["source_days"]} 份 KNMI 日级 L3 区域数组；另有 2024 年 10 月 1 日一对 L2 柱浓度及 QA 栅格。L2 缺该轨的像元时标，其余日期的东部逐轨 L2 尚待采集。当前 KNMI 同系列公开说明覆盖至 2023 年 11 月，2024—2025 需用相应 L2 产品。</p>',
    '<p><b>FIRMS 和地图</b>　2019—2025 每年三颗传感器的中国年表均已校验，共 21 份。OSM 有 2026 年 11 月快照，全国与沪苏浙皖分省文件空间重叠。模型用道路和工业面，抽样另用行政区面、已标注农田面。2026 年地图只作回顾性参照。</p>',
    pic('01','地面与 L3 按日，气象按代表点城市小时作分母。FIRMS 的 21 份年表齐备；OSM 是单次快照。'),
    '<h2>站号合并与抽样核验</h2>',
    f'<p>2,026 个输入站号中，{int(roster.city.notna().sum()):,} 个归入城市。其余包括 65 个名录缺失和 1 个城市冲突（2591A）。已把海门、江阴、昆山等县级旧名归到研究期地级市；跨名录坐标相差超过 10 公里的 {int(roster.coord_diff_km.gt(10).sum())} 个站点已保留差值，历史迁址日期有待核实。{escape((D/"有效站点行数.txt").read_text().strip())}。</p>',
    table(coverage),f'<p>随机种子 20261115。从原表头的 2,026 个站号抽 200 个，包括无名录的站号；其中 186 个直接得到行政区名称支持，3 个由福建省县区代码追溯至厦门、漳州。站点样本共 189/200 有市级证据，或 189/190 个有坐标站点。火点沿用归档固定的 200 个时空格，全部重新算回原始小格；{int(fire["图上地级区"].notna().sum())} 个匹配到 OSM 地级边界，另 1 个可定位到直辖市重庆，3 个缺可用行政边界。2 个格的四角跨地级边界。全国抽样的 200 个火点格中心均未命中 OSM 已绘制农田，地图空白与真实非农田无法区分。地图逐条浏览文件在 <code>扩展实验/核验/400条地图抽样复核.html</code>。以上为计算机空间核验与区划资料复查，计划书要求的逐条人工读图尚待完成。</p>',
    '<h2>问题一 · 火点之后，上下风城市的浓度如何变化</h2>',
    f'<p>原始全国火点 6,977,065 条，归档清洗后保留 4,086,779 条，合并为 3,322,855 个 0.01° × 30 分钟格。以研究日期及华东窗口筛得 {int(ff.input_slots):,} 个格时，排除曾出现固定热源标记的同位置小格后剩 {int(ff.after_static):,} 个，{int(ff.within_tagged_farmland_slots)} 个中心命中已绘制农田。独立十月处理程序的宽口径质控计数还含跨北京时间年界的记录；主模型使用同一套归档事件表。</p>',
    f'<p>锚点要求同一 0.25° 格、同一小时至少有两个不同火点小格。用 50 公里内最近城市的风向确定上下风，以 30—200 公里、45° 扇区、风速至少 1 m/s 筛选；比较各城相对事件前 24 小时自身基线的增幅。五个滞后都有上下风样本的共同锚点有 {int(f12.grids_hours)} 个、跨 {int(f12.anchor_days)} 日。第 12 小时的平均差为 {f12.mean_delta:+.2f} µg/m³，按锚定日自举的 95% 区间为 [{f12.ci_low:.2f}, {f12.ci_high:.2f}]。限定两个火点格中心在农田面中后仅 {int(c12.grids_hours)} 个共同锚点，第 12 小时为 {c12.mean_delta:+.2f}，区间 [{c12.ci_low:.2f}, {c12.ci_high:.2f}]。这组数据无法识别实际作物、秸秆燃烧或因果贡献率。</p>',
    pic('02','相同锚点用于所有滞后。点为平均差，误差线为按锚定日期分组自举区间，单位 µg/m³。'),
    pic('04','全国 FIRMS 取长三角周边火点，地面来自 CNEMC 公开日档。圆点为城市代表点；该月长三角没有达本研究阈值的城市日。'),
    '<h2>问题二 · 气象能否改善地面 NO₂ 预测</h2>',
    f'<p>41 城 × 90 天共有 {s3["eligible_citydays"]:,} 个候选城市日，L3 有效 {s3["valid_satellite"]:,} 个，与地面、气象及 OSM 对齐后剩 {s3["matched"]:,} 个，跨 {s3["days"]} 个日期及 {s3["grids"]} 个卫星格。卫星柱单位为 10¹⁵ molecules/cm²，地面单位为 µg/m³。有效地方太阳时按 24 × 时间比例 + 8 − 经度/15 换算北京小时，另做 ±1 小时敏感性。随机抽查 200 条，从 NPZ 独立复算其格点、时刻、柱浓度。L3 时刻代表格内有效观测。十月 L2 只有轨道起止时刻，使用 QA &gt; 75% 的浓度，仅保留轨道起、止整点配对的敏感性结果。L2 的逐像元 UTC、L3 的有效地方太阳时和地面小时各自保留。</p>',
    table(no2.rename(columns={'scheme':'留出方式','model':'特征','n':'测试观测','mae':'MAE (µg/m³)','r2':'测试 R²'})),
    '<p>按卫星格点留出时，加入气象后误差降低。在 1—2 月训练、3 月测试时误差上升，因此不能将空间留出的改善当作跨月预测能力或气象的因果解释比例。</p>',
    pic('03','同柱浓度四分位内比较。横轴为 ERA5 边界层高度，纵轴为与 L3 有效时刻对齐的地面浓度。'),
    '<h2>问题三 · 长三角重污染过程与春节</h2>',
    table(g),f'<p>城市日由站点小时先作城市均值，日均至少有 20 个有效小时，严格大于 150 µg/m³ 才入选。城市间无站数加权。全国观测到 {int(nation.重污染城市日)} 个超阈值城市日和 {len(ev)} 段同城连续过程。相邻日缺测时的过程边界已标记。长三角 {int(ev.yrd41.sum())} 段中 {facts["eligible_episode_clusters"]} 段具备聚类所需的风速、边界层、上风城市前期 PM₂.₅。两组都出现较高的上风浓度。把组间差别解读为气象条件差异，现有观测不能给出本地累积和跨城传输各自的比例。</p>',
    table(cent.rename(columns={'cluster':'组','ws_ms':'风速 m/s','blh_m':'边界层 m','upwind_pm25_prev6':'上风前6小时 PM₂.₅','n':'过程数'})),
    table(years),'<p>2023 年春节三段长三角样本分别为 287、287、286 个城市日，节中日均 PM₂.₅ 高于节前。2024 和 2025 年原始站点日档未覆盖节期。上海市生态环境局另报告 2024 年春节出现 1 个重度污染日；2025 年除夕至元宵的 16 日平均 PM₂.₅ 为 33 µg/m³、优良率 100%。两种春节时间口径已单独存档，未混入 8 天法定假期的统计。</p>',
    pic('05','取去趋势后小时差分、接收地风向及 1—6 小时滞后。相同样本内选择各城市最强滞后，属于探索性关联。'),
    '<h2>真实体量与复现</h2>',table(vals),
    f'<p>五源去除相同哈希后的原始输入共 {int(vals.iloc[:,1].sum()):,} 字节。这一列仍含全国地图与四省地图的地理重叠、十月卫星整轨及不同尺度的气象导出。按实际使用的上述五个互不重复的研究子集取物理文件大小，保守合计 <b>{int(vals.iloc[:,2].sum()):,} 字节</b>。原始输入与加工后压缩子集是两种口径；目前不足以验证课程的 2 GB 有效数据要求。中间表、图、辅助区划、归档 ZIP 和全球传输文件均未累加到有效量。</p>',
    f'<p>十月复跑与原试验所有汇总指标对齐，包括全国 {old["national_exceedances"]} 个重污染城市日和 {old["national_episodes"]} 段过程。全国集合采用合并名录后的数值见上表。另从原始 CSV 独立复算南京 {len(nx)} 个随机日，逐城小时核对原十月气象，并通过 HTTP 断点拼接离线回归测试。运行环境、逐源清单、抽查明细和执行日志均随工程保存。</p>',
    '<h2>仍缺的数据和取得路径</h2>',
    f'<p>地面尚缺 {int((~q.ground).sum())} 天，其中 2024 和 2025 年春节前后优先队列共 {int((q.priority.eq(1) & ~q.ground).sum())} 天。其次是其余冬季缺档 {int((q.priority.eq(2) & ~q.ground).sum())} 天。发布方提供年度站点 ZIP 和按日 CSV。本次执行环境可检索发布页，批量下载路径无法连接这些外部原始数据主机。未启动会反复失败的旧任务。真实站点年度包可用 <code>scripts/import_station_zip.py</code> 校验导入。其余东部全网格 ERA5 和 L2 柱、QA、像元时标须能直连各发布服务。未使用付费服务。</p>',
    '<p>在本工程运行 <code>./离线复算.command</code> 可重建分析、抽样质检与五张图。<code>扩展实验/下载计划_full.csv</code> 记录逐文件状态；<code>扩展实验/卫星轨道补采_full.csv</code> 按月列出 L2 任务。早期归档报告保留原样。</p>',
    '<h2>来源</h2><p><a href="https://quotsoft.net/air/">全国空气质量日档与年度包</a> · <a href="https://www.earthdata.nasa.gov/sites/default/files/imported/VIIRS_activefire_User_Guide.pdf">NASA 火点字段</a> · <a href="https://temis.pmc.knmi.cloud/airpollution/no2col/cci-no2-tropomi.php">KNMI L3 数据</a> · <a href="https://catalogue.ceda.ac.uk/uuid/f8a220b2ba184d89bc40028bc4a8b2e7/">CEDA 有效太阳时字段</a> · <a href="https://sentinels.copernicus.eu/documents/247904/2474726/Sentinel-5P-Level-2-Product-User-Manual-Nitrogen-Dioxide.pdf">Sentinel-5P L2 时间字段</a> · <a href="https://open-meteo.com/en/docs/historical-weather-api">ERA5 代表点导出</a> · <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a> · <a href="https://mzt.fj.gov.cn/gk/tzgg/202601/t20260105_7071220.htm">福建省民政厅区划代码</a> · <a href="https://mzt.jiangsu.gov.cn/art/2023/4/25/art_78635_10994579.html">江苏省民政厅区划代码</a> · <a href="https://sthj.sh.gov.cn/hbzhywpt5333/20250711/2c80ae29acdb4c4fab947f136d03271b.html">上海市生态环境局春节答复</a>。逐文件来源、哈希及研究窗口见工程内清单。</p></main></html>']
    target=ROOT/'中国城市重污染日_独立实验执行报告.html';target.write_text('\n'.join(page));print(target.name,target.stat().st_size)
if __name__=='__main__':main()
