#!/usr/bin/env python3
"""
与 14 页最终版 PPT 完全对齐的最终版研究报告生成器（纯 Python 标准库，零外部依赖）：
输出：
  1. 标准 OOXML Word 文档（.docx，含完整样式、专业表格、6 张 300 DPI 高清内嵌图及编号图注）：
     - 过程文件/03_实验结果/长三角城市重污染过程研究报告_最终版.docx
     - 过程文件/03_实验结果/长三角城市重污染过程研究报告_修订版.docx（自动备份原版）
     - 过程文件/06_GitHub仓库/docs/长三角城市重污染日实验总说明.docx
  2. Markdown 报告：过程文件/06_GitHub仓库/docs/项目报告.md
  3. 自包含 HTML 报告：过程文件/06_GitHub仓库/docs/项目报告.html
"""
import base64
import shutil
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
RESULT_DIR = REPO.parent / "03_实验结果"
FIG_DIR = REPO / "visualization" / "final_v2"

OUT_FINAL_DOCX = RESULT_DIR / "长三角城市重污染过程研究报告_最终版.docx"
OUT_REVISED_DOCX = RESULT_DIR / "长三角城市重污染过程研究报告_修订版.docx"
BACKUP_REVISED_DOCX = RESULT_DIR / "长三角城市重污染过程研究报告_修订版_优化前备份.docx"
OUT_REPO_DOCX = REPO / "docs" / "长三角城市重污染日实验总说明.docx"
OUT_REPO_MD = REPO / "docs" / "项目报告.md"
OUT_REPO_HTML = REPO / "docs" / "项目报告.html"


def png_size(path: Path):
    with open(path, "rb") as f:
        header = f.read(24)
    w, h = struct.unpack(">II", header[16:24])
    return w, h


# 结构化报告内容块：
# ('title', main, sub)
# ('meta', text)
# ('h1', text) / ('h2', text)
# ('p', text)
# ('bullet', lead, text)
# ('table', headers, rows)
# ('image', filename, caption)
# ('code', text)
BLOCKS = [
    ("title",
     "基于多源观测的长三角城市重污染过程分析与地面二氧化氮卫星估计",
     "——以 2023—2025 年长三角 41 城为例（最终研究报告）"),
    ("meta", "课程：《大数据原理与应用》中期大作业    |    开源与复现仓库：https://github.com/gxm-nju/china-air-pollution"),
    ("meta", "小组成员与分工：桂鑫铭（统筹、数据采集与三项实验）、万连勇（报告撰写与统稿）、沈择文（地面监测核验与日均复算）、孙晞皓（跨源匹配与模型核验）、钱辰昕（可视化图表与课堂展示）"),

    ("h1", "摘要与核心研究问题"),
    ("p", "总研究问题：2023—2025 年，长三角城市的重污染日集中在何时、何地？结合地面、卫星与气象观测，我们能解释哪些污染过程，又能在什么条件下更准确地监测地面 NO₂？本研究以城市日均 PM₂.₅ 严格大于 150 µg/m³ 且有效小时不少于 20 小时作为重污染日判据，整合 7 个独立数据源（4 个核心主源与 3 个辅助源），围绕以下三个核心问题展开跨源融合、统计检验与数据挖掘分析："),
    ("bullet", "问题一（火点对下风 PM₂.₅ 的影响与防伪因果检验）：",
     "全部 4,299 个火点事件在检出后第 12 小时，下风城市相对上风城市平均多升 +3.91 µg/m³（95% 区间 [+1.64, +6.38]）。但在 1,566 个匹配到风况相近、同网格同钟点未检出日的事件中，对照日自身亦存在 +1.81 µg/m³ 的升幅差（火点日为 +3.25 µg/m³），逐对相减后净增幅仅为 +1.45 µg/m³（95% 区间 [−1.98, +4.99]）。进一步按火点聚集规模、收获参考月、南北区域与农田落点进行 8 组分层稳健性检验，点估计方向均为正但 95% 区间全部跨零，说明零散火点并非长三角重污染日的主导推手。"),
    ("bullet", "问题二（气象信息改善卫星估计地面 NO₂ 的条件与模型对照）：",
     "在 36 个月、26,229 个原生 L2 卫星与地面配对城市日上，仅用 2023 年 1 月训练的线性岭回归在随后两年冬季误差下降（−0.92 / −1.03 µg/m³），但在春季反而误差上升（+0.88 / +1.70 µg/m³）。改用 2023 全年训练后，原线性岭回归在 2024、2025 年的全年 MAE 分别下降 6.2% 和 3.7%，但 2025 年按日历周重抽样 95% 区间跨零（[−0.42, +0.08]）。补充对照实验表明，该现象源于边界层高度、风速与 NO₂ 换算关系的季节非线性：在相同样本上引入季节交互项（2024/2025 误差分别下降 10.1% 和 13.7%，R² 升至 0.708 和 0.701）或改用非线性梯度提升树 HGBDT（无季节降 8.1% / 10.6%，含季节降 13.9% / 19.2%）后，两年按整周重抽样 95% 区间均严格低于零。"),
    ("bullet", "问题三（重污染时空分布、过程分型、聚类与来源线索）：",
     "三年 44,115 个合格城市日中共有 159 个超阈城市日（分布在 34 天），合并为 120 段同城连续过程，其中 114 段（95%）始于冬季（12、1、2 月），皖北苏北 11 城以 26.8% 的合格样本占比贡献了 61.6%（98/159）的超阈日；6、10、11 月三个收获参考窗口合计 10,898 个合格城市日零超阈。K-means 聚类将 116 段完整气象过程分为静稳低混合层（76 段）与输送型（40 段）两类，且两组上风前期 PM₂.₅ 均超 140 µg/m³。多污染物分型识别出 60 段 PM₂.₅ 与 CO 同升、27 段细颗粒占优（CO 弱）和 6 段春季粗颗粒增强过程；其中 3 月 23 日五城与 4 月 11 日淮北粗颗粒骤升获区域沙尘通报与 MERRA-2 印证，2023 年 1 月初 9 段冬季个案中 TAP 估计硝酸盐、铵盐、硫酸盐三种二次无机盐合占 PM₂.₅ 增量的 66.0%。"),

    ("h1", "一、多源数据来源、质量清洗与跨源血缘架构"),
    ("h2", "1.1 七个独立数据源与分层台账"),
    ("p", "为避免单源观测盲区（地面站无广域火点与垂直柱浓度、卫星无近地面浓度、火点无风场与扩散条件），本研究整合 7 个底层独立的开放数据源，划分为 4 个核心主源与 3 个按需提取的辅助源。所有原始文件均保留来源链接与 SHA-256 校验值，严守实际研究口径，不将区域外重复文件或重叠地图快照混入有效体量。"),
    ("table",
     ["独立数据源（分层）", "实际观测范围与形态", "归档体量", "在研究中的核心作用与连接键"],
     [
         ["主源 1：CNEMC 地面监测", "2023—2025 全国 1,096 日档 CSV（6 项污染物）", "1,998.8 MB", "历史站号归入长三角 41 城，聚合城市小时与合格城市日（≥20h）"],
         ["主源 2：NASA FIRMS 热异常", "2019—2025 MODIS/VIIRS 全国 21 份年表", "558.8 MB", "UTC 转北京时间，剔除固定热源，按 0.25° 网格与小时合并火点事件"],
         ["主源 3：ECMWF ERA5 气象", "2023—2025 区域 0.25° 逐小时风场与边界层", "266.2 MB", "提供风向划分上下风、风速与 log(BLH) 供 NO₂ 模型与过程聚类"],
         ["主源 4：Sentinel-5P NO₂", "2023—2025 36 个月原生 L2 区域提取（1,688 轨）", "196.28 MB", "城市 15 km 内 QA>0.75 像元，按真实扫描中位时刻配最近整点地面 NO₂"],
         ["辅助 5：OpenStreetMap", "沪苏浙皖农田、道路与行政区矢量子集", "按需子集", "空间匹配火点小格与农田用地，用于农田子组稳健性检验"],
         ["辅助 6：NASA MERRA-2", "2023 年 1 月与 3 月 16 份区域气溶胶个案", "9.31 MB", "提取近地面细沙尘与区域边界黑碳/有机碳水平净通量"],
         ["辅助 7：TAP 组分网格", "10 km PM₂.₅ 五种化学组分日均与月均场", "按需子集", "按城市代表点匹配，量化冬季个案无机盐增量及南北月均背景差异"],
     ]),
    ("h2", "1.2 三层数据处理与跨源融合架构"),
    ("p", "数据处理严格遵循 Raw → Cleaned → Integrated 三层架构：在清洗阶段完成历史站号地级市归并、UTC 至北京时间统一、同站同小时负值与倒挂（PM₁₀ < PM₂.₅）剔除、每日至少 20 个有效小时筛选，以及火点 0.01°×30 分钟去重与固定热源掩膜过滤；在融合阶段围绕实体、时间、空间与事件四重连接键，构建火点上下风对照表、卫星过境城市日表及同城连续过程表三大融合分析数据集（图 0）。"),
    ("image", "fig0_跨源数据血缘图.png", "图 0  多源数据融合与血缘架构（7 个独立来源经由三套融合引擎支撑三大研究问题）"),

    ("h1", "二、问题一：火点出现后，下风城市的 PM₂.₅ 比上风多升多少？"),
    ("h2", "2.1 上下风扇区与同网格同钟点未检出日配对设计"),
    ("p", "先排除已知固定热源（type 2），将合格热异常归入 0.01° 小格；同一小时、同一 0.25° 网格内至少出现 2 个不同小格检出火点计为一次候选事件。依据 ERA5 当时当地风向，在距火点 30—200 km 范围内分别选取上风与下风城市组。每座城市以事后某小时浓度减去自身事前 24 小时均值（至少 12 个有效小时）以消除城市背景差异，再计算下风组均值与上风组均值之差。"),
    ("p", "由于火点多在午后检出，检出后第 12 小时往往处于夜间，边界层下降本身可能导致区域浓度结构变化。为排除昼夜与气象混杂，我们在同年同月前后 14 天内为每个火点事件检索同一 0.25° 网格、同一钟点且当日及相邻两日均无火点检出、风向差 ≤30°、风速差 ≤2 m/s 的未检出对照日，保留完全相同的上下风城市集合计算逐对净差，并采用按年月整组重抽样 10,000 次估计 95% 置信区间。"),
    ("h2", "2.2 主结果与 1,566 对事件分层稳健性检验"),
    ("p", "三年共获得 4,299 个在 0、6、12、24、48 小时均有完整记录的事件（分布于 619 天），全样本第 12 小时下风比上风平均多升 +3.91 µg/m³（95% 区间 [+1.64, +6.38]）。其中 1,566 个事件成功匹配到风况相近的未检出对照日：该子样本火点日上下风升幅差为 +3.25 µg/m³，未检出对照日为 +1.81 µg/m³，逐对相减后净增幅缩小至 +1.45 µg/m³（95% 区间 [−1.98, +4.99]，跨零）。"),
    ("p", "为检验零散弱火点或空间异质性是否稀释了真实信号，本研究进一步对 1,566 对匹配事件按火点聚集规模（n_spatial）、季节（收获参考月 vs 非收获月）、南北地理带（≥32.5°N vs <32.5°N）及 OSM 农田落点开展 8 组分层稳健性检验（表 1、图 1）。结果显示，聚集强火点（≥3 小格，+2.74）、农田火点（+2.57）与收获参考月（+1.96）的点估计偏高，且 8 个子组点估计方向高度一致为正，但所有子组的按年月整组重抽样 95% 区间依然全部跨零。这表明在长三角城市尺度下，扣除昼夜与风场混杂后，零散火点未带来统计显著的额外 PM₂.₅ 升幅。"),
    ("table",
     ["分层子组（1,566 对配对事件，第 12 小时）", "配对数", "火点日均值", "未检出日均值", "逐对净差 (µg/m³)", "95% 区间（按年月重抽样）"],
     [
         ["全部配对事件", "1,566", "+3.252", "+1.806", "+1.446", "[−2.052, +5.036]（跨零）"],
         ["火点规模：≥3 个小格（聚集强火点）", "512", "+3.471", "+0.728", "+2.743", "[−3.037, +8.618]（跨零）"],
         ["火点规模：2 个小格（常规）", "1,054", "+3.146", "+2.330", "+0.816", "[−1.937, +3.653]（跨零）"],
         ["季节：收获参考月（6、10、11 月）", "474", "+2.900", "+0.944", "+1.956", "[−1.523, +5.938]（跨零）"],
         ["季节：非收获月份", "1,092", "+3.405", "+2.180", "+1.225", "[−3.435, +6.164]（跨零）"],
         ["区域：皖北苏北高发带（≥32.5°N）", "663", "+3.784", "+2.897", "+0.886", "[−2.118, +4.134]（跨零）"],
         ["区域：长三角中南部（<32.5°N）", "903", "+2.862", "+1.005", "+1.857", "[−3.676, +7.646]（跨零）"],
         ["用地：含已绘农田（n_farmland ≥ 1）", "68", "+3.392", "+0.823", "+2.569", "[−8.063, +13.276]（跨零）"],
         ["用地：非农田区域（n_farmland = 0）", "1,498", "+3.246", "+1.851", "+1.395", "[−1.906, +4.760]（跨零）"],
     ]),
    ("image", "fig1_Q1_火点上下风与分层稳健性.png", "图 1  火点滞后五时点演变、第 12h 未检出日对照扣减及 1,566 对事件分层稳健性森林图"),

    ("h1", "三、问题二：加入气象信息，卫星估计地面 NO₂ 会更准吗？"),
    ("h2", "3.1 真实扫描过境配对与一月模型跨季节失效诊断"),
    ("p", "Sentinel-5P 测量对流层 NO₂ 柱总量（单位统一为 10¹⁵ molecules/cm²），地面站测量近地面浓度（µg/m³）。在 2023—2025 年 36 个月的 1,695 条目录轨道中实际取得 1,694 轨（1,688 份非空区域文件共 196.28 MB），筛选城市代表点 15 km 内质量标记 QA > 0.75 的像元，按每轨实际扫描时刻中位数匹配最近北京整点地面 NO₂，并对 ERA5 区域风速与边界层高度 log(BLH) 进行时空插值，最终形成 26,229 个匹配城市日（覆盖 1,025 天，2023 年训练集 8,804 行，2024 年测试集 8,499 行，2025 年测试集 8,926 行）。"),
    ("p", "当仅用 2023 年 1 月（864 个城市日）训练线性岭回归（α=1）时，加入气象特征在 2024、2025 年冬季使平均绝对误差（MAE）分别下降 0.92 和 1.03 µg/m³（按日历周重抽样 95% 区间均严格低于零），但在春季误差反而上升 0.88 和 1.70 µg/m³，夏秋四次比较区间均跨零。具体来看，2025 年春季地面 NO₂ 实测均值为 13.27 µg/m³，一月训练的仅卫星模型估为 13.98 µg/m³，而加入气象后因冬季浅边界层系数外推至春季较高边界层，把预测均值拉低至 9.45 µg/m³，导致系统性低估。"),
    ("h2", "3.2 全年训练与非线性/季节交互模型对照实验"),
    ("p", "使用 2023 全年数据训练原线性岭回归后，加入气象使 2024 年全年 MAE 从 4.733 降至 4.441 µg/m³（−6.2%，按周区间 [−0.51, −0.10]），2025 年从 4.880 降至 4.702 µg/m³（−3.7%），但 2025 年按周区间为 [−0.42, +0.08]（跨零）。为检验该不确定性是否源于全局线性假设过于简化，我们在完全相同的 26,229 个城市日与 3,000 次按日历周重抽样框架下，补充了三组对照模型：含季节周期项（sin/cos 日序）与气象交互项的岭回归，以及非线性梯度提升树（HistGradientBoostingRegressor，分无季节与含季节两套特征）。"),
    ("table",
     ["模型与特征设定（2023 全年训练）", "测试年", "不含气象 MAE", "含气象 MAE", "相对降幅", "按周 95% 区间 (µg/m³)", "含气象 R²"],
     [
         ["原线性岭回归（无季节）", "2024", "4.733", "4.441", "−6.17%", "[−0.513, −0.102]（显著）", "0.631"],
         ["原线性岭回归（无季节）", "2025", "4.880", "4.702", "−3.66%", "[−0.422, +0.079]（跨零）", "0.624"],
         ["线性岭回归（含季节与气象交互）", "2024", "4.294", "3.861", "−10.08%", "[−0.704, −0.184]（显著）", "0.708"],
         ["线性岭回归（含季节与气象交互）", "2025", "4.641", "4.007", "−13.66%", "[−0.948, −0.375]（显著）", "0.701"],
         ["梯度提升树 HGBDT（仅气象·无季节）", "2024", "4.620", "4.249", "−8.05%", "[−0.642, −0.164]（显著）", "0.649"],
         ["梯度提升树 HGBDT（仅气象·无季节）", "2025", "4.685", "4.189", "−10.59%", "[−0.732, −0.284]（显著）", "0.673"],
         ["梯度提升树 HGBDT（气象+季节）", "2024", "4.607", "3.965", "−13.94%", "[−1.259, −0.248]（显著）", "0.662"],
         ["梯度提升树 HGBDT（气象+季节）", "2025", "5.073", "4.099", "−19.20%", "[−1.598, −0.489]（显著）", "0.651"],
     ]),
    ("p", "对照结果清晰证实了机制假设：只要允许气象对柱浓度—地面浓度换算关系呈现季节交互或非线性（哪怕 HGBDT 不引入任何日历季节特征），加入风速与边界层高度在 2024 和 2025 两年均能实现 8.1%—19.2% 的稳定误差下降，按周重抽样 95% 区间全部严格低于零，且含季节交互的岭回归 R² 在两年均突破 0.70（图 2）。"),
    ("image", "fig2_Q2_NO2模型跨季与非线性对照.png", "图 2  仅一月训练跨季失效（左）与 2023 全年训练四套模型对照（右，误差线为 3,000 次整周重抽样 95% 区间）"),

    ("h1", "四、问题三：重污染集中在哪里，哪些过程能找到来源线索？"),
    ("h2", "4.1 时空格局：高度冬聚、高度北聚与收获参考月零超阈"),
    ("p", "2023—2025 年长三角 41 城共获得 44,115 个合格城市日，其中 159 个日均 PM₂.₅ 严格超过 150 µg/m³（2023 年 89 日、2024 年 50 日、2025 年 20 日），分布在 34 个不同日期，按同城连续超阈合并为 120 段城市过程（114 段始于 12、1、2 月，占 95%）。空间上，皖北 6 市（蚌埠、淮北、亳州、宿州、阜阳、淮南）与苏北 5 市（徐州、连云港、宿迁、淮安、盐城）仅占全区合格城市日的 26.8%（11,837/44,115），却集中了 61.6%（98/159）的超阈城市日，其中阜阳 17 日、徐州 12 日、亳州与淮北各 11 日；南京 1,077 个合格日中最高日均 129.16 µg/m³，无超阈日。与此同时，每年 6、10、11 月三个收获参考窗口合计 10,898 个合格城市日中，超阈次数为零（图 3），与问题一火点对照结论相互呼应。"),
    ("image", "fig3_Q3_长三角重污染时空分布.png", "图 3  2023—2025 年长三角 41 城重污染日空间分布（左）与逐月分布（右）"),

    ("h2", "4.2 120 段过程的多污染物特征分型与 K-means 扩散条件聚类"),
    ("p", "针对 120 段同城连续过程，我们直接回溯 73 份原始地面日档，以过程开始前三个日历日相同钟点为基线，对同站同小时有效的 PM₂.₅、PM₁₀ 与 CO 进行逐段筛查。110 段具备充足基线的过程中，主规则识别出：60 段 PM₂.₅ 与 CO 同升（全部始于冬季，1 月 28 段、12 月 26 段、2 月 6 段）、27 段细颗粒占优且 CO 未明显升高、6 段春季粗颗粒占优并增强（3 月 23 日五城与 4 月 11 日淮北），另有 17 段其余或信号不一致、10 段位于 2023 年 1 月初起点而基线不足。在宽松、主规则、严格三档门槛敏感性检验中，82/110 段标签保持不变，全部 6 段粗颗粒过程在三档下均稳定保留。"),
    ("p", "为进一步刻画重污染发生时的气象扩散背景，我们对 116 段具备完整 ERA5 风速、边界层高度与上风城市前期 PM₂.₅ 浓度的过程开展 K-means 聚类（图 4）：簇 0（76 段）表现为典型静稳低混合层（平均风速 2.14 m/s，边界层高度 246 m）；簇 1（40 段）表现为较高风速与较高混合层（平均风速 3.41 m/s，边界层高度 424 m）。值得注意的是，两组过程的上风城市前期 PM₂.₅ 均值均超过 140 µg/m³（140.60 vs 149.22 µg/m³），说明强背景累积或区域输送在两类扩散条件下均普遍存在，不能仅凭静稳或风速单因素武断区分本地与外来贡献。"),
    ("image", "fig4_Q3_过程分型与Kmeans聚类.png", "图 4  120 段同城过程的多污染物特征按月分型（左）与 116 段过程 K-means 扩散条件聚类（右）"),

    ("h2", "4.3 典型过程的多源外部佐证：春季沙尘与冬季二次无机盐累积"),
    ("p", "春季沙尘个案：2023 年 3 月 23 日，亳州、宿州、宿迁、淮北与阜阳五城同时超阈。同站小时观测显示，五城平均粗颗粒（PM₁₀ − PM₂.₅）从 3 月 22 日 21—24 时的 21.2 µg/m³，在 23 日 03—06 时急升至 548.7 µg/m³，06—09 时达 1,094.8 µg/m³（单小时峰值 1,344 µg/m³）。上海市环境监测中心与上海中心气象台当日通报沙尘气团影响苏皖鲁豫，NASA MERRA-2 亦显示五城近地面细沙尘较前 72 小时增加 3.91—7.34 µg/m³。另一段 4 月 11 日淮北粗颗粒过程（增量 +546.15 µg/m³）亦获濉溪县生态环境分局激光雷达沙尘通报印证。"),
    ("p", "冬季颗粒物累积个案：2023 年 1 月初共有 9 段起点明确的城市过程（其中 7 段始于 1 月 6 日）同时具备 MERRA-2 与 TAP 组分数据。TAP 10 km 逐日网格显示，硝酸盐平均增幅最大（+17.98 µg/m³，9/9 段升高），有机物（+11.53）、铵盐（+10.18）、硫酸盐（+9.72）与黑碳（+2.49）同步上升；硝酸盐、铵盐与硫酸盐三种二次无机盐合计增加 37.88 µg/m³，占 TAP 估计 PM₂.₅ 总增量（57.36 µg/m³）的 66.0%（15 km 半径敏感性复算为 65.0%）。同期 MERRA-2 区域边界通量显示，1 月 6 日黑碳净输出由 −7.26 减弱至 −4.34 kg/s，与区域内污染物留存相符（图 5）。此外，2023 年一季度 TAP 月均场显示，皖北苏北 11 城 1—3 月的月均硝酸盐（18.69、13.25、13.04 µg/m³）持续高于其余 30 城（11.24、8.77、8.02 µg/m³），说明区域二次无机盐背景差异具有持续性。"),
    ("image", "fig5_Q3_典型过程沙尘与组分证据.png", "图 5  2023-03-23 五城沙尘粗颗粒骤升曲线（左）与 2023 年 1 月初 9 段过程 TAP 五组分平均增量（右）"),

    ("h1", "五、结果核验、复现说明、AI 使用反思与研究局限"),
    ("h2", "5.1 原始日均独立复算与一键复现入口"),
    ("p", "为保证核心统计口径无误，独立复算脚本直接读取原始站点 CSV，按“站小时 → 城市小时 → 有效小时 ≥20 的城市日均”三步重算抽检样本：南京 2023-01-22（24h，61.22 µg/m³，合格未超阈）、徐州 2024-02-10（24h，336.03 µg/m³，合格超阈）与南京 2025-06-15（9h，13.29 µg/m³，因不足 20h 从分母剔除），三例有效小时数、浓度值及判定均与发布表逐项一致。"),
    ("code", "python reproduce.py\npython scripts/supplement_experiments.py\npython visualization/generate_final_figures.py"),
    ("h2", "5.2 AI 辅助研究与人工核验反思"),
    ("p", "本项目全流程由五人小组主导研究设计与人工纠偏，ChatGPT / Codex 辅助编写批量采集、清洗对齐、建模与绘图脚本，详细日志与提示词见仓库 AI_USAGE.md。本轮研究沉淀出三点核心经验："),
    ("bullet", "纠偏时空对齐假设：",
     "初期自动化脚本曾尝试按固定午后时刻配对卫星与地面；经人工复核后改为按每轨真实扫描中位时刻配最近整点，并进一步推动了三年跨季节检验及非线性/季节交互对照实验。"),
    ("bullet", "识破伪因果陷阱：",
     "全样本火点 +3.91 µg/m³ 表面高度显著；小组主动质疑夜间边界层下降带来的混杂，设计同网格同钟点未检出对照与 8 组分层检验，最终还原出更严谨的净效应判断。"),
    ("bullet", "严守数据口径与全链路可复现：",
     "坚持按实际研究用途核算体量，拒绝将全国与分省重叠 OSM 快照或区域外数据凑入规模；所有原始文件保留 SHA-256 哈希与可复现脚本，确保每一处图表数字均可独立回溯。"),
    ("h2", "5.3 研究局限与结论边界"),
    ("bullet", "卫星过境条件边界：",
     "问题二结论适用于云筛选（QA > 0.75）通过且地面与气象均可匹配的午后过境时刻，不能直接外推至厚云覆盖或夜间时段。"),
    ("bullet", "热异常与燃烧物区分：",
     "FIRMS 主动火点探测反映地表热异常而非直接识别燃烧物，且后期 OSM 农田快照与历史观测年份存在时间差。"),
    ("bullet", "冬季源解析粒度：",
     "常规六项地面污染物（含 CO 同升）与模式组分产品可提供强有力的过程线索，但精确量化冬季本地排放与跨区域输送的贡献比例，仍需结合长期实测颗粒物化学组分与排放清单模拟。"),

    ("h1", "六、主要数据与文献出处"),
    ("bullet", "数据发布方：",
     "CNEMC 公开归档（quotsoft.net/air）；NASA FIRMS 国家年度火点包；ECMWF/Copernicus ERA5（Open-Meteo 与 NSF NCAR GDEX）；Copernicus Sentinel-5P TROPOMI OFFL L2；OpenStreetMap（Geofabrik，ODbL）；NASA GES DISC MERRA-2；TAP 中国高分辨率 PM₂.₅ 化学组分数据集（10 km）。"),
    ("bullet", "方法与外部通报：",
     "Zhang 等（2022）多示踪二次 PM₂.₅ 估计方法；生态环境部《环境空气颗粒物来源解析监测技术方法指南》；上海发布 2023 年 3 月 23 日区域沙尘监测通报；濉溪县生态环境分局 2023 年 4 月 11 日沙尘激光雷达通报。"),
]


def build_markdown():
    lines = []
    for blk in BLOCKS:
        kind = blk[0]
        if kind == "title":
            lines.append(f"# {blk[1]}\n\n**{blk[2]}**\n")
        elif kind == "meta":
            lines.append(f"> {blk[1]}\n")
        elif kind == "h1":
            lines.append(f"\n## {blk[1]}\n")
        elif kind == "h2":
            lines.append(f"\n### {blk[1]}\n")
        elif kind == "p":
            lines.append(f"{blk[1]}\n")
        elif kind == "bullet":
            lines.append(f"- **{blk[1]}**{blk[2]}\n")
        elif kind == "code":
            lines.append(f"```bash\n{blk[1]}\n```\n")
        elif kind == "table":
            headers, rows = blk[1], blk[2]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")
            for r in rows:
                lines.append("| " + " | ".join(r) + " |")
            lines.append("")
        elif kind == "image":
            fname, cap = blk[1], blk[2]
            lines.append(f"\n![{cap}](../visualization/final_v2/{fname})\n\n*{cap}*\n")
    OUT_REPO_MD.write_text("\n".join(lines), encoding="utf-8")


def build_html():
    parts = ["""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>基于多源观测的长三角城市重污染过程分析与地面二氧化氮卫星估计</title>
<style>
  body { font-family: "Times New Roman", "SimSun", "Songti SC", serif; color: #000000; line-height: 1.75; max-width: 900px; margin: 36px auto; padding: 0 28px; background: #fff; }
  h1.title { font-family: "Times New Roman", "SimHei", "Songti SC", serif; font-size: 24px; color: #000000; margin-bottom: 6px; text-align: center; font-weight: bold; }
  p.subtitle { font-size: 16px; color: #000000; text-align: center; margin-top: 0; margin-bottom: 14px; font-weight: bold; text-indent: 0; }
  p.meta { font-size: 13px; color: #000000; text-align: center; margin: 4px 0; text-indent: 0; }
  h2 { font-family: "Times New Roman", "SimHei", "Songti SC", serif; font-size: 18px; color: #000000; margin-top: 26px; margin-bottom: 10px; font-weight: bold; }
  h3 { font-family: "Times New Roman", "SimHei", "Songti SC", serif; font-size: 16px; color: #000000; margin-top: 18px; margin-bottom: 8px; font-weight: bold; }
  p { font-size: 15px; color: #000000; text-indent: 2em; margin: 8px 0; text-align: justify; }
  ul { padding-left: 0; list-style: none; margin: 8px 0; }
  li { font-size: 15px; color: #000000; text-indent: 2em; margin-bottom: 6px; text-align: justify; }
  table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 13.5px; color: #000000; border-top: 2px solid #000000; border-bottom: 2px solid #000000; }
  th { color: #000000; font-weight: bold; padding: 7px 8px; text-align: left; border-bottom: 1px solid #000000; background: #ffffff; }
  td { padding: 6px 8px; color: #000000; border: none; }
  figure { margin: 18px 0; text-align: center; }
  figure img { max-width: 100%; height: auto; }
  figcaption { font-size: 13.5px; color: #000000; margin-top: 6px; text-indent: 0; }
  pre { background: #ffffff; border: 1px solid #000000; padding: 10px 14px; font-family: "Times New Roman", "SimSun", serif; font-size: 13.5px; color: #000000; overflow-x: auto; }
</style></head><body>"""]
    in_ul = False
    for blk in BLOCKS:
        kind = blk[0]
        if in_ul and kind != "bullet":
            parts.append("</ul>")
            in_ul = False
        if kind == "title":
            parts.append(f'<h1 class="title">{escape(blk[1])}</h1>')
            parts.append(f'<p class="subtitle">{escape(blk[2])}</p>')
        elif kind == "meta":
            parts.append(f'<p class="meta">{escape(blk[1])}</p>')
        elif kind == "h1":
            parts.append(f"<h2>{escape(blk[1])}</h2>")
        elif kind == "h2":
            parts.append(f"<h3>{escape(blk[1])}</h3>")
        elif kind == "p":
            parts.append(f"<p>{escape(blk[1])}</p>")
        elif kind == "bullet":
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li><strong>{escape(blk[1])}</strong>{escape(blk[2])}</li>")
        elif kind == "code":
            parts.append(f"<pre><code>{escape(blk[1])}</code></pre>")
        elif kind == "table":
            headers, rows = blk[1], blk[2]
            parts.append("<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead><tbody>")
            for r in rows:
                parts.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in r) + "</tr>")
            parts.append("</tbody></table>")
        elif kind == "image":
            fname, cap = blk[1], blk[2]
            b64 = base64.b64encode((FIG_DIR / fname).read_bytes()).decode("ascii")
            parts.append(f'<figure><img src="data:image/png;base64,{b64}" alt="{escape(cap)}"><figcaption>{escape(cap)}</figcaption></figure>')
    if in_ul:
        parts.append("</ul>")
    parts.append("</body></html>")
    OUT_REPO_HTML.write_text("\n".join(parts), encoding="utf-8")


def build_docx(out_path: Path):
    """
    纯 Python 生成标准学术规范 OOXML .docx：
    - 通体纯黑色（#000000）
    - 中文宋体（SimSun / 宋体），数字与英文 Times New Roman
    - 正文小四号（12pt），首行缩进 2 字符，1.5 倍行距，两端对齐
    - 规范 Word 标题样式（Title / Subtitle / Heading1 / Heading2），支持导航窗格与自动目录
    - 学术标准三线表（1.5pt 黑顶线、0.75pt 黑栏目线、1.5pt 黑底线，无彩色底纹）
    - 完整内嵌 6 张 300 DPI 高清图与图注
    """
    rels = []
    media_files = []
    body_xml = []

    def rpr(size_half_pt=24, bold=False, cn_font="宋体", en_font="Times New Roman"):
        b_tag = "<w:b/><w:bCs/>" if bold else ""
        return (
            f'<w:rPr>'
            f'<w:rFonts w:ascii="{en_font}" w:hAnsi="{en_font}" w:cs="{en_font}" w:eastAsia="{cn_font}"/>'
            f'{b_tag}<w:color w:val="000000"/>'
            f'<w:sz w:val="{size_half_pt}"/><w:szCs w:val="{size_half_pt}"/>'
            f'</w:rPr>'
        )

    def para(runs_xml, style=None, align=None, indent_first=False, before=0, after=80, line=360, keep_next=False):
        st = f'<w:pStyle w:val="{style}"/>' if style else ""
        jc = f'<w:jc w:val="{align}"/>' if align else ""
        ind = '<w:ind w:firstLineChars="200" w:firstLine="480"/>' if indent_first else '<w:ind w:firstLineChars="0" w:firstLine="0"/>'
        kn = "<w:keepNext/>" if keep_next else ""
        return (
            f'<w:p><w:pPr>{st}{kn}'
            f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="auto"/>'
            f'{ind}{jc}</w:pPr>{runs_xml}</w:p>'
        )

    def run(text, size_half_pt=24, bold=False, cn_font="宋体", en_font="Times New Roman"):
        return f'<w:r>{rpr(size_half_pt, bold, cn_font, en_font)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

    img_counter = 0
    for blk in BLOCKS:
        kind = blk[0]
        if kind == "title":
            # 主标题：小二号 18pt (36 half-pt) 黑体/加粗，居中
            body_xml.append(para(run(blk[1], 36, True, cn_font="黑体"), style="Title", align="center", indent_first=False, before=120, after=80, line=300))
            # 副标题：四号 14pt (28 half-pt) 加粗宋体，居中
            body_xml.append(para(run(blk[2], 28, True, cn_font="宋体"), style="Subtitle", align="center", indent_first=False, before=0, after=120, line=280))
        elif kind == "meta":
            # 元信息：五号 10.5pt (21 half-pt) 宋体，居中
            body_xml.append(para(run(blk[1], 21, False, cn_font="宋体"), align="center", indent_first=False, before=20, after=40, line=280))
        elif kind == "h1":
            # 一级标题：小三号 15pt (30 half-pt) 黑体加粗，Heading1 样式（大纲 1 级）
            body_xml.append(para(run(blk[1], 30, True, cn_font="黑体"), style="Heading1", align="left", indent_first=False, before=240, after=120, line=320, keep_next=True))
        elif kind == "h2":
            # 二级标题：四号 14pt (28 half-pt) 黑体加粗，Heading2 样式（大纲 2 级）
            body_xml.append(para(run(blk[1], 28, True, cn_font="黑体"), style="Heading2", align="left", indent_first=False, before=180, after=90, line=320, keep_next=True))
        elif kind == "p":
            # 正文：小四号 12pt (24 half-pt) 宋体 + Times New Roman，首行缩进 2 字符，两端对齐，1.5 倍行距
            body_xml.append(para(run(blk[1], 24, False, cn_font="宋体"), style="Normal", align="both", indent_first=True, before=0, after=80, line=360))
        elif kind == "bullet":
            # 要点段：首行缩进 2 字符，引导词加粗宋体，正文常规宋体，通体黑色
            r_xml = run(blk[1], 24, True, cn_font="宋体") + run(blk[2], 24, False, cn_font="宋体")
            body_xml.append(para(r_xml, style="Normal", align="both", indent_first=True, before=0, after=80, line=360))
        elif kind == "code":
            for ln in blk[1].splitlines():
                body_xml.append(para(run(ln, 21, False, cn_font="宋体", en_font="Times New Roman"), align="left", indent_first=True, before=20, after=20, line=280))
        elif kind == "table":
            headers, rows = blk[1], blk[2]
            ncols = len(headers)
            total_twips = 9360
            col_w = total_twips // ncols
            t_rows = []
            # 学术三线表表头（下框 0.75pt 黑线，白底黑字加粗）
            cells = []
            for h in headers:
                cells.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/>'
                    f'<w:tcBorders><w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/></w:tcBorders>'
                    f'<w:vAlign w:val="center"/></w:tcPr>'
                    f'{para(run(h, 21, True, cn_font="宋体"), align="left", indent_first=False, before=40, after=40, line=260)}</w:tc>'
                )
            t_rows.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(cells) + "</w:tr>")
            for row in rows:
                cells = []
                for val in row:
                    cells.append(
                        f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/>'
                        f'<w:vAlign w:val="center"/></w:tcPr>'
                        f'{para(run(val, 20, False, cn_font="宋体"), align="left", indent_first=False, before=35, after=35, line=260)}</w:tc>'
                    )
                t_rows.append("<w:tr>" + "".join(cells) + "</w:tr>")
            tbl_xml = (
                '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/>'
                '<w:tblBorders>'
                '<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
                '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
                '<w:left w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/>'
                '</w:tblBorders>'
                '<w:tblCellMar><w:top w:w="50" w:type="dxa"/><w:bottom w:w="50" w:type="dxa"/>'
                '<w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
                '</w:tblPr>' + "".join(t_rows) + '</w:tbl>'
            )
            body_xml.append(tbl_xml)
            body_xml.append(para("", indent_first=False, before=0, after=60, line=200))
        elif kind == "image":
            fname, cap = blk[1], blk[2]
            img_path = FIG_DIR / fname
            img_counter += 1
            rid = f"rIdImg{img_counter}"
            media_name = f"media/image{img_counter}.png"
            rels.append((rid, media_name))
            media_files.append((media_name, img_path.read_bytes()))
            w_px, h_px = png_size(img_path)
            cx = 5760720
            cy = int(cx * h_px / w_px)
            drawing = (
                f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{cx}" cy="{cy}"/>'
                f'<wp:docPr id="{img_counter}" name="Picture {img_counter}"/>'
                f'<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
                f'<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:nvPicPr><pic:cNvPr id="0" name="{escape(fname)}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
            )
            body_xml.append(para(drawing, align="center", indent_first=False, before=100, after=40, line=240, keep_next=True))
            # 图注：五号 10.5pt (21 half-pt) 宋体 + Times New Roman，黑色居中
            body_xml.append(para(run(cap, 21, False, cn_font="宋体"), align="center", indent_first=False, before=0, after=140, line=280))

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="宋体"/>'
        '<w:color w:val="000000"/><w:sz w:val="24"/><w:szCs w:val="24"/>'
        '</w:rPr></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/>'
        '<w:pPr><w:spacing w:after="80" w:line="360" w:lineRule="auto"/><w:ind w:firstLineChars="200" w:firstLine="480"/><w:jc w:val="both"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="宋体"/><w:color w:val="000000"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
        '</w:style>'
        '<w:style w:type="paragraph" w:styleId="Title">'
        '<w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:pPr><w:spacing w:before="120" w:after="80"/><w:ind w:firstLineChars="0" w:firstLine="0"/><w:jc w:val="center"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="黑体"/><w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>'
        '</w:style>'
        '<w:style w:type="paragraph" w:styleId="Subtitle">'
        '<w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:pPr><w:spacing w:after="120"/><w:ind w:firstLineChars="0" w:firstLine="0"/><w:jc w:val="center"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="宋体"/><w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'
        '</w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:ind w:firstLineChars="0" w:firstLine="0"/><w:outlineLvl w:val="0"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="黑体"/><w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr>'
        '</w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        '<w:pPr><w:keepNext/><w:spacing w:before="180" w:after="90"/><w:ind w:firstLineChars="0" w:firstLine="0"/><w:outlineLvl w:val="1"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="黑体"/><w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'
        '</w:style>'
        '</w:styles>'
    )

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<w:body>' + "".join(body_xml) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>'
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )

    doc_rels_items = (
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        + "".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>'
            for rid, target in rels
        )
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{doc_rels_items}</Relationships>'
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/styles.xml", styles_xml)
        z.writestr("word/document.xml", doc_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        for m_name, m_bytes in media_files:
            z.writestr(f"word/{m_name}", m_bytes)


def main():
    if OUT_REVISED_DOCX.exists() and not BACKUP_REVISED_DOCX.exists():
        shutil.copy2(OUT_REVISED_DOCX, BACKUP_REVISED_DOCX)
        print("Backed up original revised DOCX to:", BACKUP_REVISED_DOCX)

    build_docx(OUT_FINAL_DOCX)
    shutil.copy2(OUT_FINAL_DOCX, OUT_REVISED_DOCX)
    shutil.copy2(OUT_FINAL_DOCX, OUT_REPO_DOCX)
    build_markdown()
    build_html()

    print("Generated final reports:")
    for p in [OUT_FINAL_DOCX, OUT_REVISED_DOCX, OUT_REPO_DOCX, OUT_REPO_MD, OUT_REPO_HTML]:
        print(f"  {p} ({p.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
