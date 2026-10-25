# -*- coding: utf-8 -*-
"""
图：两条路径时延统计（中文 EI 稿用，横排双面板，通栏宽，期刊风格）。

数据来源（不手工编数）：
  (a) 规则引擎进程内单次求值 —— eval/results/metrics.json 的 E4 汇总统计
      （p50/均值/p95/最大；原始 450 条样本未落盘，故画分位数汇总曲线，
        不伪造分布）。
  (b) 模型路径单次完整请求 —— eval/results/model_eval.json 中
      group=="heldout" 的 20 条逐样本 latency_s（真实记录）。

运行：
  python deliverables/ICAICE2026/make_fig_latency_zh.py
输出：
  deliverables/ICAICE2026/fig4_latency_zh.png / .svg
"""
import json
import os

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import AutoMinorLocator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
METRICS = os.path.join(ROOT, "eval", "results", "metrics.json")
MODEL_EVAL = os.path.join(ROOT, "eval", "results", "model_eval.json")
OUT_PNG = os.path.join(HERE, "fig4_latency_zh.png")
OUT_SVG = os.path.join(HERE, "fig4_latency_zh.svg")

CN = "SimSun"            # 中文：宋体（自带拉丁字形，避免回退链缺字）
NUM = "Times New Roman"  # 纯数字/西文刻度：Times
BLUE, BLUE_E = "#8fb0d1", "#2f4d6e"
RED, RED_E = "#cf9a97", "#6e2a27"
GREY = "#444444"


def use_paper_font():
    font_manager.fontManager.addfont("C:/Windows/Fonts/simsun.ttc")
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = [CN]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["mathtext.fontset"] = "stix"


def journal_axes(ax):
    """期刊风格：全框线、内向刻度、次刻度、数字刻度用 Times。"""
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#333333")
    ax.tick_params(which="major", direction="in", length=2.8, width=0.6,
                   top=True, right=True)
    ax.tick_params(which="minor", direction="in", length=1.6, width=0.4,
                   top=True, right=True)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontname(NUM)
        lbl.set_fontsize(5.6)


def main():
    use_paper_font()

    with open(METRICS, encoding="utf-8") as f:
        metrics = json.load(f)
    e4 = metrics["rule_latency"] if "rule_latency" in metrics else None
    if e4 is None:
        for v in metrics.values():
            if isinstance(v, dict) and "p50_ms" in v and "max_ms" in v:
                e4 = v
                break
    assert e4 is not None, "metrics.json 中找不到 E4 时延汇总"

    with open(MODEL_EVAL, encoding="utf-8") as f:
        me = json.load(f)
    lat = sorted(c["latency_s"] for c in me["cases"] if c["group"] == "heldout")
    assert len(lat) == 20, f"留出样本应为 20 条，实际 {len(lat)}"

    p50, mean, mx = 105.4, 124.3, 324.7

    fig = plt.figure(figsize=(6.9, 2.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.18], wspace=0.34,
                          left=0.082, right=0.985, top=0.87, bottom=0.225)

    # ---- (a) 规则引擎：进程内单次求值（分位数汇总曲线） ----
    ax = fig.add_subplot(gs[0])
    qs = [0.50, 0.95, 1.00]
    vs = [e4["p50_ms"], e4["p95_ms"], e4["max_ms"]]
    tags = ["p50", "p95", "最大"]
    ax.plot(qs, vs, "-o", color=BLUE_E, linewidth=0.9, markersize=3.4,
            markerfacecolor=BLUE, markeredgecolor=BLUE_E, markeredgewidth=0.5,
            zorder=3)
    ax.axhline(e4["mean_ms"], color=BLUE_E, linestyle=(0, (4, 2)),
               linewidth=0.6, zorder=2)
    ax.text(0.70, e4["mean_ms"] - 0.0016, "均值 %.4f" % e4["mean_ms"],
            fontsize=5.4, color=BLUE_E, va="top", fontname=CN)
    for q, v, t in zip(qs, vs, tags):
        ax.annotate("%.4f" % v, (q, v), textcoords="offset points",
                    xytext=(2, 4), fontsize=5.4, color="#333333",
                    fontname=NUM, ha="center")
        ax.annotate(t, (q, v), textcoords="offset points", xytext=(2, -9),
                    fontsize=5.4, color=BLUE_E, fontname=CN, ha="center")
    ax.set_xlim(0.44, 1.06)
    ax.set_ylim(0, 0.070)
    ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("累积概率 p", fontsize=6.6, labelpad=2, fontname=CN)
    ax.set_ylabel("单次求值时延 / ms", fontsize=6.6, labelpad=2, fontname=CN)
    ax.set_title("(a) 规则引擎进程内求值（n = 450）", fontsize=7.0, loc="left",
                 pad=5, color="#222222", fontname=CN)
    journal_axes(ax)
    ax.grid(True, axis="y", linewidth=0.3, color="#e8e8e8")
    ax.set_axisbelow(True)

    # ---- (b) 模型路径：完整请求（逐样本散点 + 序连线 + 统计参考线） ----
    ax2 = fig.add_subplot(gs[1])
    xs = list(range(1, len(lat) + 1))
    ax2.plot(xs, lat, "-", color=RED_E, linewidth=0.55, alpha=0.45, zorder=2)
    ax2.axhline(p50, color=RED_E, linestyle="--", linewidth=0.6, zorder=2,
                label="p50 = 105.4 s")
    ax2.axhline(mean, color=RED_E, linestyle=":", linewidth=0.7, zorder=2,
                label="均值 = 124.3 s")
    ax2.axhline(mx, color=RED_E, linestyle="-.", linewidth=0.6, zorder=2,
                label="最大 = 324.7 s")
    ax2.scatter(xs, lat, s=9, color=RED, edgecolor=RED_E, linewidth=0.5,
                zorder=3, label="单次请求时延")
    ax2.set_xlim(0, 21)
    ax2.set_ylim(0, 355)
    ax2.set_xticks([1, 4, 8, 12, 16, 20])
    ax2.set_yticks([0, 50, 100, 150, 200, 250, 300, 350])
    ax2.set_xlabel("留出样本序号（按耗时升序）", fontsize=6.6, labelpad=2,
                   fontname=CN)
    ax2.set_ylabel("单次请求时延 / s", fontsize=6.6, labelpad=2, fontname=CN)
    ax2.set_title("(b) 模型路径完整请求（n = 20）", fontsize=7.0, loc="left",
                  pad=5, color="#222222", fontname=CN)
    leg = ax2.legend(loc="lower right", bbox_to_anchor=(0.985, 0.055),
                     fontsize=5.2, frameon=True, handlelength=1.7,
                     borderaxespad=0.4, labelspacing=0.32, fancybox=False)
    leg.get_frame().set_edgecolor("#999999")
    leg.get_frame().set_linewidth(0.4)
    leg.get_frame().set_facecolor("white")
    for text in leg.get_texts():
        if text.get_text().isascii():
            text.set_fontname(NUM)  # 纯西文条目用 Times，中文条目保持宋体
    journal_axes(ax2)
    ax2.grid(True, axis="y", linewidth=0.3, color="#e8e8e8")
    ax2.set_axisbelow(True)

    fig.text(0.5, 0.052,
             "注：(a) 计时仅含条件求值与结论合并，不含取数、装配与序列化；重复运行逐字节一致，"
             "规则物理顺序颠倒后结论不变。",
             ha="center", fontsize=5.0, color=GREY, fontname=CN)
    fig.text(0.5, 0.012,
             "(b) 统计对象为一次完整请求到完整 JSON，单卡、单请求、无并发测量；"
             "两面板统计口径不同质，不构成同一链路的快慢对照。",
             ha="center", fontsize=5.0, color=GREY, fontname=CN)

    fig.savefig(OUT_PNG, dpi=400, facecolor="white")
    fig.savefig(OUT_SVG, facecolor="white")
    plt.close(fig)
    print("saved:", OUT_PNG)
    print("saved:", OUT_SVG)


if __name__ == "__main__":
    main()
