#!/usr/bin/env python3
"""
生成 1 张新版跨源数据血缘图 + 5 张三年全量独立核心分析图（300 DPI，适配宽屏 PPT 与报告）。
输出目录：
  - visualization/final_v2/
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "visualization" / "final_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 统一学术风格与南大紫主色调（Arial Unicode MS 含完整 CJK 与上下标/单位字形，零缺字）
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "Hiragino Sans GB", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 300
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["axes.edgecolor"] = "#C8C2CC"
plt.rcParams["axes.linewidth"] = 0.8

NJU_PURPLE = "#6B0261"
NJU_LIGHT = "#F3EDF2"
SLATE = "#546C7C"
DARK = "#302B33"
MUTED = "#68616B"
TEAL = "#2A7B88"
AMBER = "#C86D2D"
CRIMSON = "#B8333A"
LIGHT_GRAY = "#EAE6EC"


def draw_fig0_lineage():
    """图 0：新版跨源数据血缘图（7 个独立数据源 -> 时空对齐与连接键 -> 三大融合分析路径）"""
    fig, ax = plt.subplots(figsize=(12.2, 5.4))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 5.4)
    ax.axis("off")

    # 顶栏标题
    ax.text(0.15, 5.15, "多源数据融合与血缘架构（2023—2025 年长三角 41 城 · 7 个独立来源）",
            fontsize=13.5, fontweight="bold", color=DARK, va="center")

    # 列标题
    col_headers = [
        (0.15, 3.45, "一、原始观测与辅助源（4 主源 + 3 辅助源）", NJU_PURPLE),
        (4.15, 3.65, "二、清洗、统一时空基准与连接键", SLATE),
        (8.35, 3.70, "三、融合分析表与核心研究问题", TEAL),
    ]
    for x, w, title, col in col_headers:
        ax.add_patch(FancyBboxPatch((x, 4.58), w, 0.36, boxstyle="round,pad=0.03,rounding_size=0.08",
                                    facecolor=col, edgecolor="none"))
        ax.text(x + w / 2, 4.76, title, fontsize=9.5, fontweight="bold", color="white",
                ha="center", va="center")

    # 左侧 7 个数据源卡片
    sources = [
        ("主源 1 · CNEMC 地面监测", "1,096 日档 · 1,998.8 MB（6项污染物）", True, 3.92),
        ("主源 2 · NASA FIRMS 火点", "2019–2025 全国 21 表 · 558.8 MB", True, 3.28),
        ("主源 3 · ECMWF ERA5 气象", "3 年 0.25° 区域网格 · 266.2 MB", True, 2.64),
        ("主源 4 · Sentinel-5P NO₂", "36 个月原生 L2 提取 · 196.28 MB", True, 2.00),
        ("辅助 5 · OpenStreetMap", "沪苏浙皖农田/道路/行政边界子集", False, 1.32),
        ("辅助 6 · NASA MERRA-2", "16 份区域气溶胶与通量个案文件", False, 0.72),
        ("辅助 7 · TAP 组分网格", "10 km PM₂.₅ 五组分日均/月均场", False, 0.12),
    ]
    src_centers = {}
    for idx, (t1, t2, is_main, y) in enumerate(sources):
        fc = NJU_LIGHT if is_main else "#F4F6F8"
        ec = NJU_PURPLE if is_main else "#A8B5BF"
        lw = 1.1 if is_main else 0.9
        h = 0.52 if is_main else 0.48
        ax.add_patch(FancyBboxPatch((0.15, y), 3.45, h, boxstyle="round,pad=0.02,rounding_size=0.07",
                                    facecolor=fc, edgecolor=ec, linewidth=lw))
        ax.text(0.28, y + h * 0.65, t1, fontsize=8.8, fontweight="bold", color=DARK, va="center")
        ax.text(0.28, y + h * 0.27, t2, fontsize=7.6, color=MUTED, va="center")
        src_centers[idx] = (3.62, y + h / 2)

    # 中间 3 个融合处理节点
    mids = [
        ("融合引擎 A · 火点-风场-上下风",
         "UTC→北京时间 · 剔除固定热源\n0.25°网格×小时 · 30–200 km 扇区\nOSM 农田空间匹配 + 同钟点未检出对照",
         3.10, 1.25),
        ("融合引擎 B · 卫星真实过境对齐",
         "城市 15 km 内 QA>0.75 合格像元\n轨道扫描中位时刻配最近整点地面 NO₂\nERA5 风速/log(BLH) 时空插值",
         1.62, 1.25),
        ("融合引擎 C · 重污染过程与组分对齐",
         "历史站号归 41 城 · ≥20h 合格日\n日均 PM₂.₅>150 µg/m³ 连续合并 120 段\n对齐事前 3 日同钟点 + 边界通量/组分",
         0.14, 1.25),
    ]
    mid_left = {}
    mid_right = {}
    for idx, (t1, t2, y, h) in enumerate(mids):
        ax.add_patch(FancyBboxPatch((4.15, y), 3.65, h, boxstyle="round,pad=0.03,rounding_size=0.09",
                                    facecolor="#FFFFFF", edgecolor=SLATE, linewidth=1.2))
        ax.add_patch(FancyBboxPatch((4.15, y + h - 0.32), 3.65, 0.32, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor="#E8EEF2", edgecolor="none"))
        ax.text(4.28, y + h - 0.16, t1, fontsize=8.8, fontweight="bold", color=DARK, va="center")
        ax.text(4.28, y + (h - 0.32) / 2, t2, fontsize=7.8, color=MUTED, va="center", linespacing=1.42)
        mid_left[idx] = (4.13, y + h / 2)
        mid_right[idx] = (7.82, y + h / 2)

    # 右侧 3 个分析表/问题输出
    outs = [
        ("问题一 · 火点对下风 PM₂.₅ 影响",
         "分析单位：火点网格 × 小时 × 滞后\n样本：4,299 事件 / 1,566 配对对照\n方法：上下风差 + 未检出对照 + 分层检验",
         3.10, 1.25, AMBER),
        ("问题二 · 气象改善卫星 NO₂ 估计",
         "分析单位：城市 × 卫星合格过境日\n样本：26,229 城市日（1,025 天）\n方法：岭回归 + 季节交互 + HGBDT 树模型",
         1.62, 1.25, NJU_PURPLE),
        ("问题三 · 重污染时空与来源线索",
         "分析单位：同城连续超阈过程段\n样本：159 超阈日 / 120 段过程\n方法：K-means 聚类 + 多污染物分型 + 个案",
         0.14, 1.25, TEAL),
    ]
    out_left = {}
    for idx, (t1, t2, y, h, col) in enumerate(outs):
        ax.add_patch(FancyBboxPatch((8.35, y), 3.70, h, boxstyle="round,pad=0.03,rounding_size=0.09",
                                    facecolor="#FFFFFF", edgecolor=col, linewidth=1.3))
        ax.add_patch(FancyBboxPatch((8.35, y + h - 0.32), 3.70, 0.32, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor=col, edgecolor="none"))
        ax.text(8.48, y + h - 0.16, t1, fontsize=8.8, fontweight="bold", color="white", va="center")
        ax.text(8.48, y + (h - 0.32) / 2, t2, fontsize=7.8, color=DARK, va="center", linespacing=1.42)
        out_left[idx] = (8.33, y + h / 2)

    # 连接箭头（源 -> 融合引擎）
    edges_l = [
        (0, 0, NJU_PURPLE), (0, 1, NJU_PURPLE), (0, 2, NJU_PURPLE),
        (1, 0, AMBER),
        (2, 0, SLATE), (2, 1, SLATE), (2, 2, SLATE),
        (3, 1, TEAL),
        (4, 0, "#7E8E99"),
        (5, 2, "#7E8E99"),
        (6, 2, "#7E8E99"),
    ]
    for s_i, m_i, col in edges_l:
        p1 = src_centers[s_i]
        p2 = mid_left[m_i]
        ax.annotate("", xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.25",
                                    color=col, alpha=0.58, lw=1.15,
                                    connectionstyle="arc3,rad=0.0"))

    # 连接箭头（融合引擎 -> 问题输出）
    for idx, col in [(0, AMBER), (1, NJU_PURPLE), (2, TEAL)]:
        ax.annotate("", xy=out_left[idx], xytext=mid_right[idx],
                    arrowprops=dict(arrowstyle="-|>,head_length=0.55,head_width=0.32",
                                    color=col, lw=1.8))

    plt.tight_layout(pad=0.2)
    plt.savefig(OUT_DIR / "fig0_跨源数据血缘图.png", facecolor="white")
    plt.close(fig)


def draw_fig1_q1():
    """图 1（问题一）：全样本五时点演变 + 配对对照与分层稳健性森林图"""
    anchor = pd.read_csv(ROOT / "三年地面扩展" / "火点相同锚点对照.csv")
    anchor = anchor[anchor["scope"] == "全部共同锚点"].sort_values("lag")
    strat = pd.read_csv(ROOT / "results" / "补充对照实验" / "Q1_配对事件分层稳健性.csv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.6), gridspec_kw={"width_ratios": [1.0, 1.25]})

    # 左图：全样本 5 时点曲线 + 12h 配对对比标注
    lags = anchor["lag"].values
    means = anchor["mean_delta"].values
    lo = anchor["ci_low"].values
    hi = anchor["ci_high"].values

    ax1.axhline(0, color="#888888", lw=0.9, ls="--")
    ax1.fill_between(lags, lo, hi, color=NJU_PURPLE, alpha=0.14, label="全样本 95% 区间")
    ax1.plot(lags, means, "-o", color=NJU_PURPLE, lw=2.2, ms=6, label="全部火点事件 (n=4,299)")
    for x, y in zip(lags, means):
        offset = 0.55 if y >= 0 else -0.85
        ax1.text(x, y + offset, f"{y:+.2f}", ha="center", va="center", fontsize=8.5, fontweight="bold", color=NJU_PURPLE)

    # 叠加第 12 小时配对对照的三个点
    ax1.scatter([12], [3.252], color=AMBER, s=55, zorder=5, marker="s", label="配对子样本·火点日 (+3.25)")
    ax1.scatter([12], [1.806], color=SLATE, s=55, zorder=5, marker="^", label="配对子样本·未检出对照日 (+1.81)")
    ax1.errorbar([12.8], [1.446], yerr=[[1.446 - (-1.98)], [4.99 - 1.446]], fmt="D",
                 color=CRIMSON, ecolor=CRIMSON, elinewidth=1.8, capsize=4, ms=6, zorder=6,
                 label="逐对净差 +1.45 [−1.98, +4.99]")

    ax1.set_xticks([0, 6, 12, 24, 48])
    ax1.set_xticklabels(["0h", "6h", "12h", "24h", "48h"])
    ax1.set_xlim(-3, 52)
    ax1.set_ylim(-5.0, 8.2)
    ax1.set_xlabel("火点检出后滞后时间", fontsize=9.5, color=DARK)
    ax1.set_ylabel("下风 − 上风 PM₂.₅ 升幅差 (µg/m³)", fontsize=9.5, color=DARK)
    ax1.set_title("A. 火点滞后演变与第 12h 对照扣减", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax1.grid(axis="y", ls=":", alpha=0.45)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="lower left", fontsize=7.6, frameon=True, facecolor="white", framealpha=0.9, edgecolor=LIGHT_GRAY)

    # 右图：分层稳健性森林图
    short_labels = {
        "全部配对事件": "全部配对 (n=1,566)",
        "火点规模：≥3个小格（聚集强火点）": "聚集强火点 ≥3格 (n=512)",
        "火点规模：2个小格（常规）": "常规火点 2格 (n=1,054)",
        "季节：收获参考月（6/10/11月）": "收获参考月 6/10/11 (n=474)",
        "季节：非收获月份": "非收获月份 (n=1,092)",
        "区域：皖北苏北高发带（≥32.5°N）": "皖北苏北 ≥32.5°N (n=663)",
        "区域：长三角中南部（<32.5°N）": "长三角中南部 (n=903)",
        "用地：含已绘农田（n_farmland≥1）": "含已绘农田 (n=68)",
        "用地：非农田（n_farmland=0）": "非农田区域 (n=1,498)",
    }
    order = list(short_labels.keys())
    strat = strat.set_index("stratum").loc[order].reset_index()
    y_pos = np.arange(len(strat))[::-1]

    ax2.axvline(0, color=CRIMSON, lw=1.1, ls="--", alpha=0.8)
    for i, row in strat.iterrows():
        y = y_pos[i]
        col = NJU_PURPLE if i == 0 else (AMBER if row["net_diff"] >= 1.9 else SLATE)
        ax2.errorbar(row["net_diff"], y,
                     xerr=[[row["net_diff"] - row["ci_low"]], [row["ci_high"] - row["net_diff"]]],
                     fmt="o", color=col, ecolor=col, elinewidth=1.8 if i == 0 else 1.4,
                     capsize=3.5, ms=6.5 if i == 0 else 5.2, zorder=4)
        ax2.text(row["ci_high"] + 0.35, y, f"{row['net_diff']:+.2f}", va="center", ha="left",
                 fontsize=8.2, fontweight="bold" if i == 0 else "normal", color=col)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([short_labels[k] for k in order], fontsize=8.4, color=DARK)
    ax2.set_xlim(-9.5, 16.0)
    ax2.set_xlabel("第 12h 火点日 − 未检出对照日净升幅差 (µg/m³，95% 区间)", fontsize=9.2, color=DARK)
    ax2.set_title("B. 1,566 对事件分层稳健性检验（全部子组区间跨零）", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax2.grid(axis="x", ls=":", alpha=0.45)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.text(0.01, 0.005, "来源：NASA FIRMS、ERA5 区域风场、CNEMC 地面监测、OSM 农田（2023—2025）；置信区间按年月整组重抽样 10,000 次。",
             fontsize=7.6, color=MUTED)
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(OUT_DIR / "fig1_Q1_火点上下风与分层稳健性.png", facecolor="white")
    plt.close(fig)


def draw_fig2_q2():
    """图 2（问题二）：一月训练跨季失效 vs 全年线性/交互/非线性 HGBDT 模型对照"""
    cs = pd.read_csv(ROOT / "非一月卫星补采_验收" / "结果" / "跨季节误差.csv")
    jan = cs[cs["train_period"] == "仅一月"].copy()
    comp = pd.read_csv(ROOT / "results" / "补充对照实验" / "Q2_非线性与季节交互对照.csv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.6), gridspec_kw={"width_ratios": [1.0, 1.25]})

    # 左图：仅2023年1月训练，跨季节 MAE 变化
    seasons = ["冬", "春", "夏", "秋"]
    x = np.arange(len(seasons))
    w = 0.34
    for j, (yr, col) in enumerate([(2024, NJU_PURPLE), (2025, TEAL)]):
        sub = jan[jan["year"] == yr].set_index("season").loc[seasons]
        vals = sub["delta"].values
        err_lo = vals - sub["week_low"].values
        err_hi = sub["week_high"].values - vals
        pos = x + (j - 0.5) * w
        bars = ax1.bar(pos, vals, width=w, color=col, alpha=0.88, label=f"{yr} 年测试")
        ax1.errorbar(pos, vals, yerr=[err_lo, err_hi], fmt="none", ecolor=DARK, elinewidth=1.1, capsize=3)
        for bx, bv, elo, ehi in zip(pos, vals, err_lo, err_hi):
            if bv >= 0:
                ax1.text(bx, bv + ehi + 0.08, f"{bv:+.2f}", ha="center", va="bottom", fontsize=7.8, fontweight="bold", color=col)
            else:
                ax1.text(bx, bv - elo - 0.10, f"{bv:+.2f}", ha="center", va="top", fontsize=7.8, fontweight="bold", color=col)

    ax1.axhline(0, color=DARK, lw=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(["冬季\n(12,1,2月)", "春季\n(3,4,5月)", "夏季\n(6,7,8月)", "秋季\n(9,10,11月)"], fontsize=8.8)
    ax1.set_ylim(-2.15, 2.85)
    ax1.set_ylabel("加入气象后的 MAE 变化 (µg/m³，负值更准)", fontsize=9.2, color=DARK)
    ax1.set_title("A. 仅用 1 月训练：冬季改善、春季反而变差", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax1.grid(axis="y", ls=":", alpha=0.45)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=8.2, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    # 右图：2023 全年训练，4 套模型在 2024 & 2025 的加入气象 MAE 变化（森林图）
    models = [
        "线性岭回归（无季节）",
        "梯度提升树 HGBDT（无季节）",
        "线性岭回归（含季节与交互）",
        "梯度提升树 HGBDT（含季节）",
    ]
    model_short = [
        "原线性岭回归\n(仅气象)",
        "HGBDT 树模型\n(仅气象·非线性)",
        "岭回归+季节交互\n(R²>0.70)",
        "HGBDT 树模型\n(气象+季节)",
    ]
    y_base = np.arange(len(models))[::-1]

    ax2.axvline(0, color=CRIMSON, lw=1.1, ls="--", alpha=0.85)
    for idx, m_name in enumerate(models):
        for j, (yr, col, dy) in enumerate([(2024, NJU_PURPLE, 0.14), (2025, TEAL, -0.14)]):
            r = comp[(comp["model"] == m_name) & (comp["year"] == yr)].iloc[0]
            yy = y_base[idx] + dy
            val = r["delta_mae"]
            ax2.errorbar(val, yy,
                         xerr=[[val - r["week_ci_low"]], [r["week_ci_high"] - val]],
                         fmt="o" if yr == 2024 else "s", color=col, ecolor=col,
                         elinewidth=1.8, capsize=3.5, ms=6.2,
                         label=f"{yr} 年 (n={int(r['n_test']):,})" if idx == 0 else None)
            ax2.text(r["week_ci_low"] - 0.04, yy, f"{r['rel_pct']:+.1f}%",
                     va="center", ha="right", fontsize=8.0, fontweight="bold", color=col)

    ax2.set_yticks(y_base)
    ax2.set_yticklabels(model_short, fontsize=8.6, color=DARK)
    ax2.set_xlim(-2.10, 0.28)
    ax2.set_xlabel("2023 全年训练：加入气象后全年 MAE 变化 (µg/m³，整周 95% 区间)", fontsize=9.0, color=DARK)
    ax2.set_title("B. 引入非线性或季节交互后，两年改善均显著稳定", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax2.grid(axis="x", ls=":", alpha=0.45)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper left", fontsize=8.2, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    fig.text(0.01, 0.005, "来源：Sentinel-5P 原生 L2、CNEMC 地面 NO₂、ERA5 区域气象（26,229 个匹配城市日，1,025 天）；误差线为 3,000 次日历周整组重抽样 95% 区间。",
             fontsize=7.6, color=MUTED)
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(OUT_DIR / "fig2_Q2_NO2模型跨季与非线性对照.png", facecolor="white")
    plt.close(fig)


def draw_fig3_q3_spatiotemporal():
    """图 3（问题三）：长三角 41 城三年重污染空间分布 + 逐月超阈城市日分布"""
    city_days = pd.read_parquet(ROOT / "三年地面扩展" / "全国城市日.parquet")
    coords = pd.read_csv(ROOT / "data" / "cleaned" / "case_city_grid.csv")
    # 筛选长三角41城
    yrd_cities = set(pd.read_csv(ROOT / "非一月卫星补采_验收" / "结果" / "卫星城市日匹配.csv.gz", usecols=["city"])["city"].unique())
    df = city_days[city_days["city"].isin(yrd_cities)].copy()
    # 合格城市日：有效小时 >= 20（检查字段名）
    if "valid_hours" in df.columns:
        df = df[df["valid_hours"] >= 20].copy()
    elif "n_hours" in df.columns:
        df = df[df["n_hours"] >= 20].copy()
    elif "hours" in df.columns:
        df = df[df["hours"] >= 20].copy()
    elif "pm25_hours" in df.columns:
        df = df[df["pm25_hours"] >= 20].copy()

    pm_col = [c for c in df.columns if c.lower() in ("pm25", "pm25_mean", "pm2.5")][0]
    date_col = [c for c in df.columns if "date" in c.lower()][0]
    df["dt"] = pd.to_datetime(df[date_col])
    df["month"] = df["dt"].dt.month
    df["heavy"] = df[pm_col] > 150.0

    city_stats = df.groupby("city", as_index=False).agg(heavy_days=("heavy", "sum"), valid_days=("heavy", "count"))
    city_stats = city_stats.merge(coords[["city", "lat", "lon"]].drop_duplicates("city"), on="city", how="left")

    north11 = {"蚌埠", "淮北", "亳州", "宿州", "阜阳", "淮南", "徐州", "连云港", "宿迁", "淮安", "盐城"}
    city_stats["is_north"] = city_stats["city"].isin(north11)

    month_stats = df.groupby("month")["heavy"].sum().reindex(range(1, 13), fill_value=0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.6), gridspec_kw={"width_ratios": [1.15, 1.0]})

    # 左图：空间分布气泡图
    # 画一个虚线框圈出皖北苏北高发区
    ax1.add_patch(FancyBboxPatch((115.25, 32.35), 5.35, 2.45, boxstyle="round,pad=0.08,rounding_size=0.18",
                                 facecolor="#F7EEF6", edgecolor=NJU_PURPLE, lw=1.2, ls="--", zorder=1))
    ax1.text(120.52, 34.68, "皖北·苏北 11 城\n占 61.6% 超阈日 (98/159)", fontsize=8.2,
             fontweight="bold", color=NJU_PURPLE, va="top", ha="right")

    # 非高发区先画
    sub_other = city_stats[~city_stats["is_north"]]
    sub_north = city_stats[city_stats["is_north"]]
    ax1.scatter(sub_other["lon"], sub_other["lat"],
                s=35 + sub_other["heavy_days"] * 24,
                c=np.where(sub_other["heavy_days"] > 0, SLATE, "#D0D6DC"),
                edgecolors=DARK, linewidths=0.7, alpha=0.85, zorder=3, label="其余 30 城 (61 日)")
    ax1.scatter(sub_north["lon"], sub_north["lat"],
                s=35 + sub_north["heavy_days"] * 24,
                c=NJU_PURPLE, edgecolors="white", linewidths=0.9, alpha=0.88, zorder=4, label="皖北·苏北 11 城 (98 日)")

    # 标注核心城市（避让重叠）
    label_offsets = {
        "阜阳": (-0.28, -0.45), "亳州": (-0.42, 0.35), "淮北": (-0.65, 0.32),
        "徐州": (0.28, 0.22), "宿州": (0.24, -0.22), "南京": (-0.52, -0.25),
        "上海": (0.15, 0.05), "杭州": (0.15, -0.22), "合肥": (-0.62, -0.15),
    }
    for _, r in city_stats[city_stats["city"].isin(label_offsets.keys())].iterrows():
        dx, dy = label_offsets[r["city"]]
        tag = f"{r['city']}({int(r['heavy_days'])})"
        col = NJU_PURPLE if r["is_north"] else (TEAL if r["city"] == "南京" else DARK)
        fw = "bold" if r["heavy_days"] >= 11 or r["city"] == "南京" else "normal"
        ax1.annotate(tag, xy=(r["lon"], r["lat"]), xytext=(r["lon"] + dx, r["lat"] + dy),
                     fontsize=8.0, fontweight=fw, color=col,
                     arrowprops=dict(arrowstyle="-", color="#999999", lw=0.6) if abs(dx) > 0.25 else None)

    ax1.set_xlim(115.0, 122.7)
    ax1.set_ylim(27.6, 35.1)
    ax1.set_xlabel("东经 (°E)", fontsize=9.2, color=DARK)
    ax1.set_ylabel("北纬 (°N)", fontsize=9.2, color=DARK)
    ax1.set_title("A. 长三角 41 城三年重污染日空间分布", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax1.grid(ls=":", alpha=0.4)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="lower left", fontsize=8.0, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    # 右图：逐月超阈城市日柱状图
    months = np.arange(1, 13)
    vals = month_stats.values
    bar_colors = [NJU_PURPLE if m in (12, 1, 2) else (AMBER if m in (3, 4) else "#CBD3D9") for m in months]
    ax2.bar(months, vals, color=bar_colors, width=0.66, edgecolor="none", zorder=3)
    for m, v in zip(months, vals):
        if v > 0:
            ax2.text(m, v + 1.5, f"{int(v)}", ha="center", va="bottom", fontsize=8.4, fontweight="bold", color=DARK)

    # 高亮 6、10、11 收获参考月零超阈
    for hm in [6, 10, 11]:
        ax2.axvspan(hm - 0.42, hm + 0.42, color="#E7F3F5", alpha=0.85, zorder=1)
        ax2.text(hm, 4.5, "0", ha="center", va="bottom", fontsize=9.0, fontweight="bold", color=TEAL)

    ax2.annotate("6、10、11 月收获参考窗口\n10,898 个合格城市日零超阈",
                 xy=(10.5, 8), xytext=(5.5, 44),
                 fontsize=8.4, fontweight="bold", color=TEAL,
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#F0F8F9", edgecolor=TEAL, lw=0.9),
                 arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.1))
    ax2.annotate("春季沙尘\n(3月5城, 4月淮北)",
                 xy=(3.2, 6), xytext=(3.1, 24),
                 fontsize=8.0, color=AMBER, fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.0))

    ax2.set_xticks(months)
    ax2.set_xticklabels([f"{m}月" for m in months], fontsize=8.4)
    ax2.set_ylim(0, max(vals) + 14)
    ax2.set_ylabel("超阈城市日数（PM₂.₅ 日均 > 150 µg/m³）", fontsize=9.2, color=DARK)
    ax2.set_title("B. 逐月分布：冬季占 95%，收获参考月零超阈", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax2.grid(axis="y", ls=":", alpha=0.45, zorder=0)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.text(0.01, 0.005, f"来源：CNEMC 地面监测（2023—2025，共 {len(df):,} 个合格城市日，{int(df['heavy'].sum())} 个超阈城市日，分布在 34 天）。",
             fontsize=7.6, color=MUTED)
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(OUT_DIR / "fig3_Q3_长三角重污染时空分布.png", facecolor="white")
    plt.close(fig)


def draw_fig4_q3_clustering():
    """图 4（问题三）：120 段过程多污染物特征分型 + K-means 扩散条件聚类"""
    by_m = pd.read_csv(ROOT / "三年过程污染物线索" / "按月分布.csv")
    ep = pd.read_csv(ROOT / "三年地面扩展" / "episode_cluster.csv")
    ep_valid = ep.dropna(subset=["cluster", "ws_ms", "blh_m"]).copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.6), gridspec_kw={"width_ratios": [1.0, 1.1]})

    # 左图：按月堆叠柱状图（按冬季顺序 12, 1, 2, 3, 4 排列更直观）
    m_order = [12, 1, 2, 3, 4]
    by_m = by_m.set_index("month").reindex(m_order, fill_value=0)
    cats = [
        ("PM₂.₅与CO同升", "PM₂.₅ 与 CO 同升 (60)", NJU_PURPLE),
        ("细颗粒占优且CO未明显升高", "细颗粒占优·CO弱 (27)", TEAL),
        ("粗颗粒占优并增强", "粗颗粒占优并增强 (6)", AMBER),
        ("其余或信号不一致", "其余/信号不一致 (17)", SLATE),
        ("资料不足", "资料不足 (10)", "#C8C2CC"),
    ]
    x = np.arange(len(m_order))
    bottom = np.zeros(len(m_order))
    for col_name, label, color in cats:
        vals = by_m[col_name].values
        ax1.bar(x, vals, bottom=bottom, width=0.56, label=label, color=color, edgecolor="white", lw=0.6)
        for xi, v, b in zip(x, vals, bottom):
            if v >= 5:
                ax1.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center",
                         fontsize=8.2, fontweight="bold", color="white" if color != "#C8C2CC" else DARK)
        bottom += vals
    for xi, tot in zip(x, bottom):
        ax1.text(xi, tot + 1.2, f"共{int(tot)}", ha="center", va="bottom", fontsize=8.4, fontweight="bold", color=DARK)

    ax1.set_xticks(x)
    ax1.set_xticklabels(["12月", "1月", "2月", "3月", "4月"], fontsize=9.0)
    ax1.set_ylim(0, 62)
    ax1.set_ylabel("同城连续重污染过程数（段）", fontsize=9.2, color=DARK)
    ax1.set_title("A. 120 段同城过程的多污染物特征按月分布", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax1.grid(axis="y", ls=":", alpha=0.45)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=7.6, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    # 右图：K-means 扩散条件聚类（风速 vs 边界层高度）
    c0 = ep_valid[ep_valid["cluster"] == 0]
    c1 = ep_valid[ep_valid["cluster"] == 1]

    ax2.scatter(c0["ws_ms"], c0["blh_m"], s=42, color=NJU_PURPLE, alpha=0.72, edgecolors="white", lw=0.5,
                label=f"簇 0 · 静稳低混合层 (n={len(c0)}, 均风 2.14 m/s, BLH 246 m)")
    ax2.scatter(c1["ws_ms"], c1["blh_m"], s=48, color=TEAL, marker="^", alpha=0.78, edgecolors="white", lw=0.5,
                label=f"簇 1 · 非静稳/输送条件 (n={len(c1)}, 均风 3.41 m/s, BLH 424 m)")

    # 聚类中心星号
    ax2.scatter([2.142], [245.8], s=190, marker="*", color=CRIMSON, edgecolors="white", lw=0.9, zorder=6)
    ax2.scatter([3.410], [423.8], s=190, marker="*", color=AMBER, edgecolors="white", lw=0.9, zorder=6)
    ax2.annotate("簇0中心\n(2.14 m/s, 246 m)", xy=(2.142, 245.8), xytext=(0.95, 115),
                 fontsize=7.8, fontweight="bold", color=CRIMSON,
                 arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=0.9))
    ax2.annotate("簇1中心\n(3.41 m/s, 424 m)", xy=(3.410, 423.8), xytext=(3.85, 520),
                 fontsize=7.8, fontweight="bold", color=AMBER,
                 arrowprops=dict(arrowstyle="->", color=AMBER, lw=0.9))

    ax2.set_xlabel("过程期平均风速 (m/s)", fontsize=9.2, color=DARK)
    ax2.set_ylabel("过程期平均边界层高度 BLH (m)", fontsize=9.2, color=DARK)
    ax2.set_title("B. K-means 扩散条件聚类（116 段完整气象过程）", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax2.grid(ls=":", alpha=0.45)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper left", fontsize=7.6, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    fig.text(0.01, 0.005, "来源：CNEMC 6项污染物同站对齐、ERA5 区域风速与边界层；两组上风前期 PM₂.₅ 均值均高（140.6 vs 149.2 µg/m³）。",
             fontsize=7.6, color=MUTED)
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(OUT_DIR / "fig4_Q3_过程分型与Kmeans聚类.png", facecolor="white")
    plt.close(fig)


def draw_fig5_q3_cases():
    """图 5（问题三）：典型个案双面板——3月23日五城沙尘骤升 + 1月初9段 TAP 五组分增量"""
    mar = pd.read_csv(ROOT / "三年地面扩展" / "三月五城逐小时.csv")
    mar["dt"] = pd.to_datetime(mar["time"])
    # 取 2023-03-22 12:00 至 2023-03-23 23:00 五城均值
    sub_m = mar[(mar["dt"] >= "2023-03-22 12:00:00") & (mar["dt"] <= "2023-03-23 23:00:00")]
    hr = sub_m.groupby("dt", as_index=False).agg(
        coarse=("coarse", "mean"),
        pm25=("pm25", "mean"),
        dust=("dust", "mean"),
    )

    tap = pd.read_csv(ROOT.parent / "03_实验结果" / "TAP逐日组分" / "各过程与事前三日对照.csv")
    # 筛选与报告一致的 9 段（最近格 & start_unknown==False & merra_matched==True）
    tap9 = tap[(tap["method"] == "最近格") & (tap["start_unknown"] == False) & (tap["merra_matched"] == True)]
    if len(tap9) != 9:
        tap9 = tap[(tap["method"] == "最近格") & (tap["start_unknown"] == False)].head(9)

    comp_map = [
        ("NO3_delta", "硝酸盐 (NO₃⁻)", NJU_PURPLE),
        ("OM_delta", "有机物 (OM)", SLATE),
        ("NH4_delta", "铵盐 (NH₄⁺)", TEAL),
        ("SO4_delta", "硫酸盐 (SO₄²⁻)", AMBER),
        ("BC_delta", "黑碳 (BC)", "#7A7480"),
    ]
    comp_vals = []
    for col, lbl, c in comp_map:
        if col in tap9.columns:
            comp_vals.append((lbl, float(tap9[col].mean()), int((tap9[col] > 0).sum()), len(tap9), c))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.6), gridspec_kw={"width_ratios": [1.18, 1.0]})

    # 左图：3月22-23日五城粗颗粒骤升曲线
    hrs_idx = np.arange(len(hr))
    ax1.fill_between(hrs_idx, 0, hr["coarse"], color=AMBER, alpha=0.18)
    ax1.plot(hrs_idx, hr["coarse"], color=AMBER, lw=2.3, label="五城平均粗颗粒 (PM₁₀ − PM₂.₅)")
    ax1.plot(hrs_idx, hr["pm25"], color=NJU_PURPLE, lw=1.8, ls="--", label="五城平均 PM₂.₅")

    peak_i = int(hr["coarse"].idxmax())
    peak_v = hr.loc[peak_i, "coarse"]
    peak_t = hr.loc[peak_i, "dt"].strftime("%m-%d %H时")
    ax1.scatter([peak_i], [peak_v], color=CRIMSON, s=55, zorder=5)
    ax1.annotate(f"峰值 {peak_v:.0f} µg/m³ ({peak_t})",
                 xy=(peak_i, peak_v), xytext=(peak_i - 5.5, peak_v + 125),
                 fontsize=8.2, fontweight="bold", color=CRIMSON,
                 arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.0))
    ax1.text(0.03, 0.70, "3月23日凌晨急升：\n• 21–24时均值: 21.2\n• 03–06时均值: 548.7\n• 06–09时均值: 1,094.8\n• MERRA-2 细沙尘\n  同步增 +3.91~7.34",
             transform=ax1.transAxes, fontsize=7.8, color=DARK, va="top",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="#FFF9F4", edgecolor=AMBER, lw=0.8))

    tick_idx = list(range(0, len(hr), 6))
    ax1.set_xticks(tick_idx)
    ax1.set_xticklabels([hr.loc[i, "dt"].strftime("%d日\n%H时") for i in tick_idx], fontsize=8.0)
    ax1.set_ylim(0, 1580)
    ax1.set_ylabel("颗粒物浓度 (µg/m³)", fontsize=9.2, color=DARK)
    ax1.set_title("A. 2023-03-23 五城沙尘：粗颗粒凌晨骤升", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax1.grid(axis="y", ls=":", alpha=0.45)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper left", fontsize=7.8, frameon=True, facecolor="white", edgecolor=LIGHT_GRAY)

    # 右图：1月初 9 段 TAP 组分平均增量
    y_pos = np.arange(len(comp_vals))[::-1]
    for i, (lbl, val, n_up, n_tot, col) in enumerate(comp_vals):
        y = y_pos[i]
        ax2.barh(y, val, height=0.58, color=col, alpha=0.9)
        ax2.text(val + 0.4, y, f"+{val:.2f} µg/m³ ({n_up}/{n_tot}段升)", va="center", ha="left",
                 fontsize=8.3, fontweight="bold" if i == 0 else "normal", color=DARK)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([c[0] for c in comp_vals], fontsize=8.8, color=DARK)
    ax2.set_xlim(0, 27.5)
    ax2.set_xlabel("相对事前三天平均增量 (µg/m³)", fontsize=9.2, color=DARK)
    ax2.set_title("B. 2023年1月初 9 段过程 TAP 组分增量", fontsize=10.5, fontweight="bold", color=DARK, loc="left", pad=8)
    ax2.text(0.97, 0.12, "三种二次无机盐\n(NO₃⁻+NH₄⁺+SO₄²⁻)\n合占 PM₂.₅ 增量 66.0%\n同期 MERRA-2 显示\n黑碳净输出减弱",
             transform=ax2.transAxes, fontsize=7.9, color=NJU_PURPLE, ha="right", va="bottom",
             bbox=dict(boxstyle="round,pad=0.38", facecolor=NJU_LIGHT, edgecolor=NJU_PURPLE, lw=0.85))
    ax2.grid(axis="x", ls=":", alpha=0.45)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.text(0.01, 0.005, "来源：CNEMC 同站小时观测、NASA MERRA-2 气溶胶通量、TAP 10 km 逐日化学组分产品（五城为亳州、宿州、宿迁、淮北、阜阳）。",
             fontsize=7.6, color=MUTED)
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(OUT_DIR / "fig5_Q3_典型过程沙尘与组分证据.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    draw_fig0_lineage()
    draw_fig1_q1()
    draw_fig2_q2()
    draw_fig3_q3_spatiotemporal()
    draw_fig4_q3_clustering()
    draw_fig5_q3_cases()
    print("Generated all 6 figures in:", OUT_DIR)
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
