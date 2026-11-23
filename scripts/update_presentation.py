#!/usr/bin/env python3
"""
PPT 视觉与结构精修脚本：
- 用版面结构展现逻辑层级，重点数据/关键词使用异色与更大字号突出；
- 彻底去除文本框左侧纯色长条；
- 减少冗余注释性长句，彻底去除用“·”点号拼接的文字；
- 保留原南大模板页眉/Logo/页码框架，并同步两处 PPT 版本。
"""
import shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
RESULT_DIR = REPO.parent / "03_实验结果"
FIG_DIR = REPO / "visualization" / "final_v2"

SRC_PPT = RESULT_DIR / "长三角城市重污染过程.pptx"
BACKUP_PPT = RESULT_DIR / "长三角城市重污染过程_优化前备份.pptx"
REPO_PPT = REPO / "docs" / "课堂展示.pptx"

C_PURPLE = RGBColor(0x6B, 0x02, 0x61)
C_DARK = RGBColor(0x30, 0x2B, 0x33)
C_MUTED = RGBColor(0x68, 0x61, 0x6B)
C_SLATE = RGBColor(0x54, 0x6C, 0x7C)
C_TEAL = RGBColor(0x2A, 0x7B, 0x88)
C_AMBER = RGBColor(0xC8, 0x6D, 0x2D)
C_BG_SOFT = RGBColor(0xF6, 0xF3, 0xF7)
C_BG_GRAY = RGBColor(0xF5, 0xF6, 0xF8)
C_LINE = RGBColor(0xDF, 0xDA, 0xE2)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT_CN = "PingFang SC"


def clear_content_shapes(slide, keep_indices=range(7)):
    to_remove = [sh for idx, sh in enumerate(slide.shapes) if idx not in keep_indices]
    for sh in to_remove:
        sp = sh._element
        sp.getparent().remove(sp)


def set_slide_title(slide, text):
    sh = slide.shapes[5]
    tf = sh.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.name = FONT_CN
    r.font.size = Pt(22)
    r.font.bold = True
    r.font.color.rgb = C_DARK


def add_rich_text(slide, left, top, width, height, runs, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE):
    """runs: list of (text, size_pt, bold, color_rgb)"""
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    for text, sz, bold, col in runs:
        r = p.add_run()
        r.text = text
        r.font.name = FONT_CN
        r.font.size = Pt(sz)
        r.font.bold = bold
        r.font.color.rgb = col
    return tb


def add_hline(slide, left, top, width, color=C_LINE):
    ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.012))
    ln.fill.solid()
    ln.fill.fore_color.rgb = color
    ln.line.fill.background()


def add_picture_fitted(slide, img_path: Path, left, top, max_w, max_h):
    with Image.open(img_path) as im:
        iw, ih = im.size
    ratio = iw / ih
    if max_w / max_h > ratio:
        h = max_h
        w = h * ratio
        x = left + (max_w - w) / 2
        y = top
    else:
        w = max_w
        h = w / ratio
        x = left
        y = top + (max_h - h) / 2
    slide.shapes.add_picture(str(img_path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def set_notes(slide, text):
    ns = slide.notes_slide
    ns.notes_text_frame.text = text


def add_metric_columns(slide, items, top=1.06, height=0.84, show_arrows=False):
    """
    极简结构化顶栏：无边框、无左侧竖条，用字号与异色突出关键数据。
    items: list of (top_label, big_value, sub_text, value_color)
    """
    n = len(items)
    arrow_w = 0.34 if show_arrows else 0.0
    gap = 0.16 if not show_arrows else 0.04
    total_w = 12.03
    col_w = (total_w - arrow_w * (n - 1) - gap * (n - 1) * (2 if show_arrows else 1)) / n

    for i, (lbl, val, sub, vcol) in enumerate(items):
        if show_arrows:
            x = 0.65 + i * (col_w + arrow_w + 2 * gap)
        else:
            x = 0.65 + i * (col_w + gap)

        # 极淡背景块以体现结构分区（无左竖条、无重边框）
        bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(top), Inches(col_w), Inches(height))
        bg.adjustments[0] = 0.08
        bg.fill.solid()
        bg.fill.fore_color.rgb = C_BG_SOFT if i == n - 1 else C_BG_GRAY
        bg.line.fill.background()

        tb = slide.shapes.add_textbox(Inches(x + 0.16), Inches(top + 0.05), Inches(col_w - 0.30), Inches(height - 0.10))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        r_lbl = p1.add_run()
        r_lbl.text = lbl + "  "
        r_lbl.font.name = FONT_CN
        r_lbl.font.size = Pt(10.8)
        r_lbl.font.color.rgb = C_MUTED

        r_val = p1.add_run()
        r_val.text = val
        r_val.font.name = FONT_CN
        r_val.font.size = Pt(17.5)
        r_val.font.bold = True
        r_val.font.color.rgb = vcol

        if sub:
            p2 = tf.add_paragraph()
            p2.space_before = Pt(2)
            r_sub = p2.add_run()
            r_sub.text = sub
            r_sub.font.name = FONT_CN
            r_sub.font.size = Pt(10.0)
            r_sub.font.color.rgb = C_DARK

        if show_arrows and i < n - 1:
            ax = x + col_w + gap
            add_rich_text(slide, ax, top, arrow_w, height, [("→", 18, True, C_SLATE)], align=PP_ALIGN.CENTER)


def build_slide3(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "数据血缘：7 个独立来源如何连到同一城市与同一小时？")

    add_metric_columns(slide, [
        ("核心主源", "4 套", "地面 1,998.8 MB  火点 558.8 MB  气象 266.2 MB  卫星 196.28 MB", C_PURPLE),
        ("辅助来源", "3 套", "OSM 土地边界  MERRA-2 气溶胶通量  TAP 组分网格", C_SLATE),
        ("融合架构", "3 层", "Raw → Cleaned → Integrated  全源统一北京时间", C_TEAL),
    ], top=1.06, height=0.80, show_arrows=False)

    add_picture_fitted(slide, FIG_DIR / "fig0_跨源数据血缘图.png", left=0.55, top=1.94, max_w=12.23, max_h=4.92)
    set_notes(slide,
              "本页展示完整的多源数据血缘架构。我们整合 7 个独立来源（4 个核心主源与 3 个辅助源），全部统一至北京时间并按历史站号归入长三角 41 城，通过网格小时、真实卫星扫描过境与同城连续超阈三个融合引擎，支撑三个研究问题。")


def build_slide5(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "问题一　火点滞后升幅差、未检出日对照与分层稳健性")

    add_metric_columns(slide, [
        ("全样本 12h 升幅差", "+3.91 µg/m³", "4,299 个火点事件  95% 区间 [+1.64, +6.38]", C_PURPLE),
        ("同钟点未检出对照", "+1.81 µg/m³", "1,566 对中火点日 +3.25  昼夜风场本身占一半以上", C_SLATE),
        ("扣除对照后净差", "+1.45 µg/m³", "95% 区间 [−1.98, +4.99]  全部 8 个分层均跨零", C_AMBER),
    ], top=1.06, height=0.82, show_arrows=True)

    add_picture_fitted(slide, FIG_DIR / "fig1_Q1_火点上下风与分层稳健性.png", left=0.55, top=1.95, max_w=12.23, max_h=4.42)

    add_rich_text(slide, 0.65, 6.42, 12.03, 0.42, [
        ("结论  ", 12, True, C_AMBER),
        ("引入同网格同钟点未检出日排除昼夜混杂后，火点额外升幅", 11.5, False, C_DARK),
        ("不再显著", 12, True, C_AMBER),
        ("，按规模、季节、南北与农田分层均跨零。", 11.5, False, C_DARK),
    ])
    set_notes(slide,
              "如果不做对照，全样本第 12 小时下风比上风多升 3.91 微克每立方米；但引入风况相近的同网格同钟点未检出日后，对照日自身也有 +1.81，逐对相减净差仅 +1.45（区间跨零）。按聚集强火点、收获参考月、南北区域和农田分层检验，全部子组 95% 区间均跨零，说明零散火点不是长三角重污染日的主导推手。")


def build_slide8(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "问题二　引入季节交互或非线性树模型，两年误差均显著下降")

    add_metric_columns(slide, [
        ("原线性岭回归", "−6.2% / −3.7%", "2024 显著  2025 按周区间 [−0.42, +0.08] 跨零", C_SLATE),
        ("岭回归加季节交互", "−10.1% / −13.7%", "MAE 降至 3.86 / 4.01  R² 升至 0.708 / 0.701", C_PURPLE),
        ("HGBDT 非线性树", "−8.1% 至 −19.2%", "无季节亦双年显著  按周 95% 区间均严格低于零", C_TEAL),
    ], top=1.06, height=0.82, show_arrows=True)

    add_picture_fitted(slide, FIG_DIR / "fig2_Q2_NO2模型跨季与非线性对照.png", left=0.55, top=1.95, max_w=12.23, max_h=4.42)

    add_rich_text(slide, 0.65, 6.42, 12.03, 0.42, [
        ("机制  ", 12, True, C_PURPLE),
        ("一月模型春季失效源于边界层与 NO₂ 的", 11.5, False, C_DARK),
        ("季节非线性关系", 12, True, C_PURPLE),
        ("；加入季节交互或改用梯度提升树后，两年均稳定显著改善。", 11.5, False, C_DARK),
    ])
    set_notes(slide,
              "左图显示仅用 1 月训练在冬季改善、春季误差反增，提示气象效应随季节非线性变化。右图展示 26,229 个城市日上的对照实验：原线性岭回归 2025 年按周跨零；加入季节交互项（R² 突破 0.70，误差降 10.1% 和 13.7%）或换用 HGBDT 非线性树后，2024 与 2025 两年按周重抽样 95% 区间全部严格低于零。")


def build_slide9(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "问题三　重污染集中在哪里？冬季占 95%，收获参考月零超阈")

    add_metric_columns(slide, [
        ("三年超阈城市日", "159 日", "分布在 34 天（占 44,115 个合格城市日的 0.36%）", C_PURPLE),
        ("空间高度北聚", "61.6%", "皖北苏北 11 城占 98 日  南京最高 129.16 µg/m³ 无超阈", C_AMBER),
        ("收获参考月", "0 次", "6、10、11 月合计 10,898 个合格城市日零超阈", C_TEAL),
    ], top=1.06, height=0.80, show_arrows=False)

    add_picture_fitted(slide, FIG_DIR / "fig3_Q3_长三角重污染时空分布.png", left=0.55, top=1.94, max_w=12.23, max_h=4.90)
    set_notes(slide,
              "左图展示长三角 41 城三年重污染空间格局：阜阳 17 日、徐州 12 日、亳州和淮北各 11 日，皖北苏北 11 城占全区 61.6% 超阈日，南京三年无超阈日。右图显示 114/120 段始于冬季，而 6、10、11 月收获参考窗口 10,898 个合格日零超阈。")


def build_slide10(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "问题三　120 段过程的多污染物分型与 K-means 扩散聚类")

    # 双栏结构顶栏，精准对应下方左右两图
    add_metric_columns(slide, [
        ("多污染物特征分型", "60 / 27 / 6 段", "CO 同升 60 段  细粒占优 27 段  春季粗粒增强 6 段（82/110 三档稳健）", C_PURPLE),
        ("K-means 扩散条件聚类", "76 vs 40 段", "静稳低混合层（2.14 m/s, 246 m）vs 输送条件（3.41 m/s, 424 m）", C_TEAL),
    ], top=1.06, height=0.80, show_arrows=False)

    add_picture_fitted(slide, FIG_DIR / "fig4_Q3_过程分型与Kmeans聚类.png", left=0.55, top=1.94, max_w=12.23, max_h=4.90)
    set_notes(slide,
              "左图展示 120 段同城连续过程的多污染物分型：冬季以 PM2.5 与 CO 同升（60段）和细颗粒占优（27段）为主；3—4 月 6 段全部为粗颗粒占优并增强。右图展示对 116 段完整气象过程做的 K-means 聚类：76 段为静稳低混合层，40 段为较高风速与高边界层的输送条件，且两组上风前期 PM2.5 均值均超 140 µg/m³。")


def build_slide11(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "问题三　典型个案：春季沙尘骤升与冬季二次无机盐累积")

    add_metric_columns(slide, [
        ("2023-03-23 五城沙尘", "21.2 → 1,094.8 µg/m³", "地面粗颗粒凌晨飙升超 50 倍  获区域通报与 MERRA-2 印证", C_AMBER),
        ("2023 年 1 月初 9 段过程", "66.0% 无机盐增量", "TAP 硝酸盐 +17.98 增幅最大  同期黑碳净输出减弱", C_PURPLE),
    ], top=1.06, height=0.80, show_arrows=False)

    add_picture_fitted(slide, FIG_DIR / "fig5_Q3_典型过程沙尘与组分证据.png", left=0.55, top=1.94, max_w=12.23, max_h=4.90)
    set_notes(slide,
              "左图是 2023 年 3 月 23 日五城沙尘，地面粗颗粒凌晨急升，峰值达 1,344 µg/m³，与上海气象环保联合通报及 MERRA-2 细沙尘增量吻合。右图是 1 月初 9 段冬季过程，TAP 显示硝酸盐、铵盐、硫酸盐三种二次无机盐合占 PM2.5 增量的 66.0%，同期 MERRA-2 显示黑碳净输出减弱。")


def build_slide12(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "数据规模台账、复算核验与 AI 协作反思")

    # 左栏：两个极简干净表格
    left_x, left_w = 0.65, 5.95
    add_rich_text(slide, left_x, 1.08, left_w, 0.36, [
        ("7 源归档体量与分层口径", 14, True, C_PURPLE)
    ])

    tbl_shape = slide.shapes.add_table(6, 3, Inches(left_x), Inches(1.48), Inches(left_w), Inches(2.58))
    tbl = tbl_shape.table
    tbl.columns[0].width = Inches(2.05)
    tbl.columns[1].width = Inches(1.30)
    tbl.columns[2].width = Inches(2.60)
    rows_data = [
        ("独立数据源", "归档体量", "研究用途"),
        ("CNEMC 地面监测", "1,998.8 MB", "1,096 日档  44,115 合格城市日"),
        ("NASA FIRMS 火点", "558.8 MB", "2019–2025 全国季节与固定热源掩膜"),
        ("ECMWF ERA5 气象", "266.2 MB", "3 年 0.25° 区域风场与边界层"),
        ("Sentinel-5P L2", "196.28 MB", "36 个月原生 L2 区域提取  1,688 轨"),
        ("OSM / MERRA-2 / TAP", "辅助按需子集", "农田边界  16 份通量个案与组分场"),
    ]
    for r_i, row in enumerate(rows_data):
        for c_i, val in enumerate(row):
            cell = tbl.cell(r_i, c_i)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PURPLE if r_i == 0 else (C_WHITE if r_i % 2 == 1 else C_BG_SOFT)
            tf = cell.text_frame
            tf.margin_left = Inches(0.08)
            tf.margin_right = Inches(0.06)
            tf.margin_top = Inches(0.03)
            tf.margin_bottom = Inches(0.03)
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = val
            run.font.name = FONT_CN
            run.font.size = Pt(10.2 if r_i > 0 else 10.5)
            run.font.bold = (r_i == 0 or c_i == 1)
            run.font.color.rgb = C_WHITE if r_i == 0 else (C_PURPLE if c_i == 1 and r_i <= 4 else C_DARK)

    add_rich_text(slide, left_x, 4.24, left_w, 0.34, [
        ("原始 CSV 独立复算核验", 13, True, C_SLATE),
        ("  （每日 ≥20 有效小时为合格日）", 10, False, C_MUTED),
    ])

    tbl2_shape = slide.shapes.add_table(4, 4, Inches(left_x), Inches(4.62), Inches(left_w), Inches(1.58))
    tbl2 = tbl2_shape.table
    tbl2.columns[0].width = Inches(1.75)
    tbl2.columns[1].width = Inches(0.95)
    tbl2.columns[2].width = Inches(1.30)
    tbl2.columns[3].width = Inches(1.95)
    t2_rows = [
        ("城市与日期", "有效小时", "复算日均", "判定与发布表一致"),
        ("南京 2023-01-22", "24 h", "61.22 µg/m³", "合格未超阈"),
        ("徐州 2024-02-10", "24 h", "336.03 µg/m³", "合格超阈"),
        ("南京 2025-06-15", "9 h", "13.29 µg/m³", "不足 20h 剔除"),
    ]
    for r_i, row in enumerate(t2_rows):
        for c_i, val in enumerate(row):
            cell = tbl2.cell(r_i, c_i)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_SLATE if r_i == 0 else (C_WHITE if r_i % 2 == 1 else C_BG_GRAY)
            tf = cell.text_frame
            tf.margin_left = Inches(0.07)
            tf.margin_right = Inches(0.05)
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = val
            run.font.name = FONT_CN
            run.font.size = Pt(10.0)
            run.font.bold = (r_i == 0 or c_i == 2)
            run.font.color.rgb = C_WHITE if r_i == 0 else C_DARK

    # 右栏：结构化 3 条 AI 协作反思（大号异色序号 + 干净留白与细分割线，无左竖条）
    right_x, right_w = 6.95, 5.73
    add_rich_text(slide, right_x, 1.08, right_w, 0.36, [
        ("AI 协作与人工纠偏核心反思", 14, True, C_PURPLE)
    ])

    ai_items = [
        ("01", C_PURPLE, "纠偏时空对齐假设",
         "摒弃固定午后时刻配对，改为按卫星", "真实扫描中位时刻", "对齐地面，并补充非线性模型对照。"),
        ("02", C_TEAL, "识破伪因果陷阱",
         "针对全样本 +3.91 的表面显著，主动要求 AI 构建", "同网格同钟点未检出对照", "与分层稳健性检验。"),
        ("03", C_AMBER, "严守口径与全链路可复现",
         "拒绝将全国重叠快照计入有效体量，保留", "SHA-256 校验与一键复算脚本", "，确保数字可溯源。"),
    ]
    for i, (num, col, title, pre, em, post) in enumerate(ai_items):
        y = 1.62 + i * 1.56
        # 大号异色序号列
        add_rich_text(slide, right_x, y, 0.72, 1.15, [(num, 26, True, col)], align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP)
        # 右侧标题 + 重点高亮正文
        tb = slide.shapes.add_textbox(Inches(right_x + 0.76), Inches(y), Inches(right_w - 0.76), Inches(1.22))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        r1 = p1.add_run()
        r1.text = title
        r1.font.name = FONT_CN
        r1.font.size = Pt(13.5)
        r1.font.bold = True
        r1.font.color.rgb = C_DARK

        p2 = tf.add_paragraph()
        p2.space_before = Pt(5)
        for seg, b, c in [(pre, False, C_MUTED), (em, True, col), (post, False, C_MUTED)]:
            r = p2.add_run()
            r.text = seg
            r.font.name = FONT_CN
            r.font.size = Pt(11.0)
            r.font.bold = b
            r.font.color.rgb = c

        if i < 2:
            add_hline(slide, right_x, y + 1.38, right_w)

    add_rich_text(slide, 0.65, 6.40, 12.03, 0.42, [
        ("复现与分工  ", 11.5, True, C_SLATE),
        ("五人小组分别负责数据实验、报告统稿、地面核验、模型核验与展示，全部代码与样本已公开至 GitHub。", 11.0, False, C_MUTED),
    ])
    set_notes(slide,
              "本页总结数据台账、复算核验与 AI 使用心得。左侧展示 7 个独立来源的实际归档体量（Sentinel-5P 为 196.28 MB）及三例原始 CSV 的独立复算结果。右侧通过三个具体案例总结小组在 AI 协作中的核心经验：纠偏时空对齐、用对照设计识破伪因果、严守口径与全链路可复现。")


def build_slide13(slide):
    clear_content_shapes(slide)
    set_slide_title(slide, "三项研究结论")

    rows = [
        ("01", "火点与下风 PM₂.₅", C_AMBER, [
            ("全样本 12h 升幅差 ", 12.5, False, C_DARK),
            ("+3.91 µg/m³", 14.5, True, C_DARK),
            ("；扣除同钟点未检出对照后净差为 ", 12.5, False, C_DARK),
            ("+1.45 µg/m³", 14.5, True, C_AMBER),
            ("（区间含零）。\n按聚集规模、收获月、南北与农田 8 组分层检验", 12.0, False, C_MUTED),
            ("全部跨零", 12.5, True, C_AMBER),
            ("，零散火点非长三角重污染主因。", 12.0, False, C_MUTED),
        ]),
        ("02", "卫星估计地面 NO₂", C_PURPLE, [
            ("线性假设下 2025 年按周跨零；引入", 12.5, False, C_DARK),
            ("季节交互项", 13.5, True, C_PURPLE),
            ("（误差降 ", 12.5, False, C_DARK),
            ("10.1% / 13.7%", 14.5, True, C_PURPLE),
            ("，R² 突破 ", 12.5, False, C_DARK),
            ("0.70", 14.5, True, C_PURPLE),
            ("）\n或改用 ", 12.0, False, C_MUTED),
            ("HGBDT 非线性树", 12.5, True, C_TEAL),
            ("（降 8.1% 至 19.2%）后，2024 与 2025 两年按周重抽样均严格显著改善。", 12.0, False, C_MUTED),
        ]),
        ("03", "重污染时空与线索", C_TEAL, [
            ("冬季占 ", 12.5, False, C_DARK),
            ("95%", 14.5, True, C_TEAL),
            ("，皖北苏北 11 城占 ", 12.5, False, C_DARK),
            ("61.6%", 14.5, True, C_TEAL),
            ("，收获参考月 ", 12.5, False, C_DARK),
            ("0 超阈", 14.5, True, C_TEAL),
            ("；K-means 区分静稳（76段）与输送（40段）。\n春季 6 段粗颗粒过程获", 12.0, False, C_MUTED),
            ("沙尘通报与 MERRA-2 印证", 12.5, True, C_DARK),
            ("，冬季 1 月初 9 段个案中三种二次无机盐合占增量 ", 12.0, False, C_MUTED),
            ("66.0%", 13.0, True, C_PURPLE),
            ("。", 12.0, False, C_MUTED),
        ]),
    ]

    for i, (num, tag, col, runs) in enumerate(rows):
        y = 1.24 + i * 1.66
        # 左栏结构：大号异色编号 + 简洁问题标签
        add_rich_text(slide, 0.65, y, 2.55, 0.56, [(num, 30, True, col)], valign=MSO_ANCHOR.TOP)
        add_rich_text(slide, 0.65, y + 0.62, 2.55, 0.48, [(tag, 14, True, C_DARK)], valign=MSO_ANCHOR.TOP)

        # 右栏结构：带重点字号与异色的精炼结论
        tb = slide.shapes.add_textbox(Inches(3.35), Inches(y + 0.04), Inches(9.33), Inches(1.36))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.line_spacing = 1.35
        for txt, sz, b, c in runs:
            r = p.add_run()
            r.text = txt
            r.font.name = FONT_CN
            r.font.size = Pt(sz)
            r.font.bold = b
            r.font.color.rgb = c

        if i < 2:
            add_hline(slide, 0.65, y + 1.50, 12.03)

    add_rich_text(slide, 0.65, 6.32, 12.03, 0.46, [
        ("边界说明  ", 11.5, True, C_SLATE),
        ("卫星 NO₂ 结论适用于云筛选通过的午后过境时刻；冬季本地排放与区域输送的精确拆分仍需长期实测化学组分。", 11.0, False, C_MUTED),
    ])
    set_notes(slide,
              "最后总结三项核心结论：第一，火点分析通过未检出日配对与分层检验排除昼夜混杂，说明零散火点非重污染主因；第二，NO2 卫星反演通过季节交互与 HGBDT 树模型揭示非线性机制，实现双年显著改善且 R² 突破 0.70；第三，重污染高度冬聚与北聚，结合 K-means 聚类、沙尘通报及组分场形成多源证据闭环。感谢聆听！")


def remove_thin_vertical_bars(slide):
    """移除任意残留的文本框左侧纯色细竖条（保留页眉装饰块）。"""
    for sh in list(slide.shapes):
        if sh.width.inches < 0.12 and sh.height.inches > 0.35:
            sp = sh._element
            sp.getparent().remove(sp)


def add_thanks_slide(prs):
    """基于空白布局新增第 14 页：谢谢垂听（沿用南大视觉元素，极简大气）。"""
    import copy
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slides[-1].slide_layout
    slide = prs.slides.add_slide(blank_layout)

    # 复制模板页脚与右上校徽（来自 Slide 2 的形状 1,2,3,4）
    ref_slide = prs.slides[1]
    for idx in [1, 2, 3, 4]:
        el = copy.deepcopy(ref_slide.shapes[idx]._element)
        # 如果是图片，需要确保 rId 关系也复制到新 slide
        blip = el.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
        if blip is not None:
            r_embed = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if r_embed:
                rel = ref_slide.part.rels[r_embed]
                new_rId = slide.part.relate_to(rel.target_part, rel.reltype)
                blip.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"] = new_rId
        slide.shapes._spTree.append(el)

    # 顶部细紫线装饰
    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(0.0), Inches(13.333), Inches(0.08))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = C_PURPLE
    top_bar.line.fill.background()

    # 中央主标题：谢谢垂听
    add_rich_text(slide, 1.0, 2.35, 11.33, 1.10, [
        ("谢 谢 垂 听", 46, True, C_PURPLE)
    ], align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # 居中短紫线
    div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.86), Inches(3.58), Inches(1.60), Inches(0.035))
    div.fill.solid()
    div.fill.fore_color.rgb = C_PURPLE
    div.line.fill.background()

    # 副标题
    add_rich_text(slide, 1.0, 3.82, 11.33, 0.55, [
        ("敬请各位老师与同学批评指正", 20, False, C_DARK)
    ], align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # 项目名称与开源复现仓库
    add_rich_text(slide, 1.0, 4.72, 11.33, 0.45, [
        ("2023—2025 年长三角 41 城重污染过程与地面 NO₂ 卫星估计", 13, False, C_MUTED)
    ], align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rich_text(slide, 1.0, 5.18, 11.33, 0.42, [
        ("代码与复现仓库  ", 12, True, C_SLATE),
        ("https://github.com/gxm-nju/china-air-pollution", 12, False, C_TEAL),
    ], align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # 右下页码 14
    add_rich_text(slide, 11.88, 7.04, 0.75, 0.31, [
        ("14", 11, False, C_MUTED)
    ], align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE)

    set_notes(slide, "感谢各位老师和同学的聆听，我们的全部代码、数据样本、校验清单和补充对照脚本都已公开在 GitHub 仓库中，欢迎各位老师和同学提问与指正！")


def main():
    if not BACKUP_PPT.exists():
        shutil.copy2(SRC_PPT, BACKUP_PPT)

    prs = Presentation(str(BACKUP_PPT))
    build_slide3(prs.slides[2])
    build_slide5(prs.slides[4])
    build_slide8(prs.slides[7])
    build_slide9(prs.slides[8])
    build_slide10(prs.slides[9])
    build_slide11(prs.slides[10])
    build_slide12(prs.slides[11])
    build_slide13(prs.slides[12])

    for sl in prs.slides:
        remove_thin_vertical_bars(sl)

    add_thanks_slide(prs)

    prs.save(str(SRC_PPT))
    shutil.copy2(SRC_PPT, REPO_PPT)
    print("Saved refined 14-slide PPT to:")
    print(" ", SRC_PPT)
    print(" ", REPO_PPT)


if __name__ == "__main__":
    main()
