# 数据来源、采集与关联

2026 年 11 月 15 日完成本批归档复核与复算。下表区分观测发生时间、地图快照日期及文件核验时间。五行各算一个主来源；同一卫星的 L2 和 L3、来自同一监测网的不同镜像均合并计数。

| 主来源与访问方式 | 实际观测、类型与采集 | 字段、单位与关联方式 | 追溯与使用条件 |
|---|---|---|---|
| 中国环境监测总站（CNEMC），王晓雷公开日档 | 全国 134 个日文件，CSV 宽表。2023-01-01 至 04-01、12-01 至 12-12，2024-10 全月。可按日或年度包取得 | date、hour 为北京时间，type 指污染物，站号为列。PM₂.₅、NO₂ 单位 µg/m³。站号归到地级市，再聚合城市小时 | [发布页](https://quotsoft.net/air/) · [前期日档记录](logs/ground_downloads.csv) · [全部 134 天的校验](metadata/地面文件校验.csv)。共享课堂用测量摘样并注明观测与归档来源；发布页未给出通用再许可。 |
| NASA FIRMS，MODIS、VIIRS/S-NPP、VIIRS/NOAA-20 | 中国 2019—2025 年 21 份年度点表。按传感器和年从国家归档包提取中国成员。共有 6,977,065 条原始探测 | latitude、longitude、acq_date、acq_time（UTC）、confidence、type、frp（MW）。换北京时间后按 0.01°、半小时去重，按风向匹配城市 | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/country/) · [年度包网址、成员、摘要](logs/fire_downloads.csv)。保留 NASA FIRMS 以及传感器署名，具体产品版本见年表。 |
| ECMWF / Copernicus ERA5，Open-Meteo 与 NSF NCAR GDEX 分发 | 41 城 2023—2025 年代表点小时导出，另有 2024-10 网格 NetCDF。共 1,078,464 个代表点城市小时，边界层缺 179,088 小时 | location_id 对应请求坐标和返回格；气温 °C、气压 hPa、风速 m/s、风向为来向角度、边界层 m。点表 UTC+8；网格 UTC 转北京时间 | [代表点原始请求](metadata/era5_url.txt) · [点表与单位说明](https://open-meteo.com/en/docs/historical-weather-api) · [Open-Meteo 条款](https://open-meteo.com/en/terms) · [网格请求及摘要](logs/原始文件校验与来源.csv)。保留 ECMWF/C3S 与分发方署名。 |
| Copernicus Sentinel-5P / TROPOMI，KNMI 日产品及一轨 L2 | 2023 年第一季度 90 个东部日窗口，0.5° 栅格。KNMI 月包按日提取 44×40 格；另有 2024-10-01 L2 柱与质量两层 | NO₂ 柱单位 10¹⁵ molecules/cm²；observations 与有效时间比例用于筛选。城市取最近格，将有效地方太阳时换算为北京时间、按最近小时配对 | [KNMI 产品](https://temis.pmc.knmi.cloud/airpollution/no2col/cci-no2-tropomi.php) · [CEDA 产品与许可记录](https://catalogue.ceda.ac.uk/uuid/f8a220b2ba184d89bc40028bc4a8b2e7/) · [月包](logs/satellite_downloads.csv) · [日窗口](logs/satellite_daily_windows.csv)。保留产品名称、版本与生产机构；全球月包仅计传输。 |
| © OpenStreetMap contributors，Geofabrik 分发 | 2026-11-14 的沪苏浙皖快照，并存有重叠的全国快照。PBF 节点、道路、工业与农田面和行政区边界 | 道路长度密度 km/km²、工业面比例、火点小格中心是否落在已绘制农田内。按坐标空间连接；地图绘制年份晚于污染观测 | [© OpenStreetMap contributors，ODbL](https://www.openstreetmap.org/copyright) · [Geofabrik](https://download.geofabrik.de/asia/china.html) · [各省快照日期、字节、摘要](logs/osm_downloads.csv)。地图衍生数据保留 ODbL 署名及条款。latest 链接会变化，历史版本以摘要为准。 |

辅助材料包括站点名录、历史地名归并和国务院节假日安排。[站点元数据](https://zenodo.org/records/10892980) · [历史县市归并](docs/历史名录地级归并.csv) · [节假日、调休和逐年政府网址](data/raw/spring_festival_rules.csv)。上海市公开答复只作旁证，未替代缺失站点日档。

## 从原始样本到研究记录

| 数据层 | 随库文件 | 一行或一个格代表什么 |
|---|---|---|
| 原始测量摘样 | data/raw/ground、era5、firms | 2023-01-22 地面 CSV 保留研究城市能匹配的站号和两种污染物；气象保留该日 41×24 小时的原值；火点三表按原始 UTC 日截取。该火点样例的日期边界与北京时间日不同。 |
| 原始区域栅格与索引 | data/raw/s5p、osm | 每个 NPZ 是一天的东部区域和原产品的五个字段。OSM 提供原始索引及 SHA-256；道路与工业空间特征另存清洗表。 |
| 清洗与对齐 | data/cleaned | station_city 按站号关联城市。era5_requested_city_grid 按 location_id 关联请求城市。case_city_grid 提供城市坐标，osm_city_features 提供地图特征。 |
| 融合表 | data/integrated | 城市×北京时间小时、城市×有效卫星日、火点网格×小时×滞后，以及全国城市日。浓度保留原始单位，模型的 MAE 与地面 NO₂ 同单位。 |
| 输出与检查 | results、metadata、logs | 输出保留分母、分组和误差区间；metadata 记录逐月有效覆盖、逐日缺口及抽样；logs 记录文件获取、核验和运行。 |

## 复算、取数和体量

1. 直接运行 [reproduce.py](reproduce.py)，重建春节当天地面与气象融合样例及三组主要结果。发布文件校验在 [release_sha256.csv](metadata/release_sha256.csv)。
2. 若需取得更多原始文件，在 macOS/Linux 用 `python scripts/collect.py full --plan-only` 生成冬季优先队列；用 `python scripts/collect.py full --groups air` 等命令分源采集。采集器保存断点、状态与校验记录。卫星月包的逐日裁剪脚本为 [satellite_windows.py](多源数据与实验/scripts/satellite_windows.py)，需要 GDAL Python 绑定。点位 ERA5 可用上表的原始请求重取，四省 PBF 在索引中。历史镜像失效或快照变化时需记录差异；遇访问限制按发布方要求操作。
3. [历史原始清单](metadata/原始文件按内容去重.csv)保留研究工程内的原文件相对路径，与本仓库的代表性样本目录不同。原始输入按内容去重总计 2,799,760,907 字节，保守研究子集 79,249,804 字节。各源两种尺度见[实际体量表](metadata/五源实际体量.csv)。独立归档、全球月包、图表和中间表没有叠加计入有效规模。
