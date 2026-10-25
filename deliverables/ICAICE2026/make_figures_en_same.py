# -*- coding: utf-8 -*-
"""与原中文稿插图完全同框架的英文版：几何、配色、字号、布局逐项照抄 make_figures.py 的
fig1_zh / fig2_zh / fig3_zh，仅把文字换成英文（会议要求图中禁中文）。"""
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))

from make_figures import box, arrow, load_curve  # 同一套绘制助手

INK = "#1a1a1a"
EDGE = "#4a4a4a"
C_RULE = "#e8f0fb"
C_COMP = "#eef7ee"
C_DECI = "#fdf3e3"
C_MODEL = "#f5eefb"


def fig1_en_same(path):
    """同 fig1_zh 几何：2.48x3.00，7 行纵向。"""
    C_RULE_B = "#e8f0fb"
    C_COMP_B = "#e9f5e9"
    C_DECI_B = "#fdf3e3"
    C_MODEL_B = "#f5eefb"
    fig, ax = plt.subplots(figsize=(2.48, 3.00))
    ax.set_xlim(0, 1); ax.set_ylim(-0.10, 1.0); ax.axis("off")

    rows = [
        (0.985, 0.105, "#f2f2f2",
         "Operational facts\nprofiles · exams · drills · safety · reports", False),
        (0.845, 0.105, C_RULE_B,
         "Per-scene fact adapter\none source per scene, no prior diagnosis", True),
        (0.705, 0.095, C_RULE_B,
         "Rule table (MySQL 8 JSON) · 22 rules · 5 scenes\nVALUE / KEYWORD groups, effective on edit", False),
        (0.575, 0.095, C_COMP_B,
         "Rule engine\npriority desc · group merge · skip · severity merge", False),
        (0.445, 0.095, C_MODEL_B,
         "Model: six-key JSON contract (source = model)\nQwen2.5-3B-Instruct + 4-bit LoRA", False),
        (0.315, 0.095, "#fdeeee",
         "Four defense lines + human confirmation\nstructure → value → permission → safety", True),
        (0.185, 0.095, C_DECI_B,
         "Suggestion · human decision · decision log\none run_id links rule result → suggestion", False),
    ]

    x, w = 0.030, 0.940
    prev_bottom = None
    for y_top, h, col, text, bold in rows:
        y = y_top - h
        box(ax, x, y, w, h, text, fc=col, fs=5.2, bold=bold, r=0.014)
        if prev_bottom is not None:
            arrow(ax, (x + w / 2, prev_bottom), (x + w / 2, y_top))
        prev_bottom = y

    ax.text(0.5, -0.062,
            "rules decide, the model only expresses; failures fall back",
            ha="center", va="center", fontsize=4.9, color="#555555", style="italic")

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig2_en_same(path):
    """同 fig2_zh 几何：3.622x2.46，主线+右侧失败分支。"""
    fig, ax = plt.subplots(figsize=(3.622, 2.46))
    ax.set_xlim(0, 1); ax.set_ylim(0.0, 1.0); ax.axis("off")

    LX, LW = 0.020, 0.560
    RX, RW = 0.660, 0.335
    H = 0.112
    YS = [0.860, 0.688, 0.516, 0.344, 0.172, 0.000]

    def node(y, text, fc, fs=5.8, bold=False, x=LX, w=LW):
        box(ax, x, y, w, H, text, fc=fc, fs=fs, bold=bold)

    node(YS[0], "③ Input-side authorization\nRoleInterceptor decides accessible facts", C_DECI, fs=5.4)
    node(YS[1], "Fact assembly + rule engine\n④ SAFETY group hard-handles negatives", C_RULE, fs=5.4)
    node(YS[2], "Model generation: Qwen2.5-3B + LoRA\ntemperature 0.2, forced JSON object", C_MODEL, fs=5.4)
    node(YS[3], "① Structural contract (hard check)\nsix-key fields, enums, levels, dates", "#ffffff", fs=5.4)
    node(YS[4], "② Numerical reconciliation (soft check)\nnumbers must fall within fact list", "#ffffff", fs=5.4)
    node(YS[5], "Deliver   source = model\nneed_human_confirm always true", "#eef7ee", bold=True)

    node(YS[0], "Unauthorized → 403\nno fact assembly", "#fdf3e3", fs=5.4, x=RX, w=RW)
    node(YS[3], "Invalid → full rollback\nsource = rule, no retry", C_RULE, fs=5.4, x=RX, w=RW)
    node(YS[4], "Untraceable → log only\nconfidence capped 0.6", "#fdf3e3", fs=5.4, x=RX, w=RW)

    for i in range(5):
        arrow(ax, (LX + LW / 2, YS[i]), (LX + LW / 2, YS[i + 1] + H))
    for i in (0, 3, 4):
        arrow(ax, (LX + LW, YS[i] + H / 2), (RX, YS[i] + H / 2))

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig3_en_same(path):
    """同 fig3_zh 几何：1x2 损失曲线，仅改标注文字。"""
    steps, losses, esteps, elosses = load_curve()
    fig, axes = plt.subplots(1, 2, figsize=(3.307, 1.66),
                             gridspec_kw={"wspace": 0.42, "width_ratios": [1.32, 1]})

    ax = axes[0]
    ax.plot(steps, losses, color="#2f6fb2", linewidth=0.9, marker="o", markersize=1.3)
    ax.set_yscale("log")
    ax.set_ylim(0.05, 26)
    ax.axhline(math.log(151936), color="#9a9a9a", linewidth=0.6, linestyle=(0, (3, 2)))
    ax.text(112, 13.6, "vocab. entropy ln V = 11.93", fontsize=5.0, color="#666666")
    ax.set_xlabel("Optimization step", fontsize=6.2, labelpad=1.5)
    ax.set_ylabel("Training loss (log)", fontsize=6.2, labelpad=2.5)
    ax.tick_params(labelsize=5.6, length=2, pad=1.2, width=0.6)
    ax.grid(True, which="major", linewidth=0.32, color="#e4e4e4")
    ax.set_xlim(0, 318)
    ax.annotate("step 5: 11.57", xy=(5, losses[0]), xytext=(40, 2.4), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))
    ax.annotate("final: 0.063", xy=(300, losses[-1]), xytext=(126, 0.30), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))

    ax = axes[1]
    ax.plot(esteps, elosses, color="#c0504d", linewidth=0.9, marker="s", markersize=2.0)
    ax.axvline(200, color="#9a9a9a", linewidth=0.6, linestyle=(0, (3, 2)))
    ax.text(206, 0.0186, "only -1.9% after", fontsize=5.0, color="#666666")
    ax.set_xlabel("Optimization step", fontsize=6.2, labelpad=1.5)
    ax.set_ylabel("Validation loss", fontsize=6.2, labelpad=2.0)
    ax.tick_params(labelsize=5.6, length=2, pad=1.2, width=0.6)
    ax.grid(True, linewidth=0.32, color="#e4e4e4")
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 0.0238)
    ax.annotate("0.0198", xy=(50, elosses[0]), xytext=(74, 0.0166), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))
    ax.annotate("0.0106", xy=(300, elosses[-1]), xytext=(168, 0.0050), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))

    for plate in axes:
        for spine in ("top", "right"):
            plate.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            plate.spines[spine].set_linewidth(0.6)

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig1_en_same(os.path.join(HERE, "fig1_architecture_en.png"))
    fig2_en_same(os.path.join(HERE, "fig2_guardrail_en.png"))
    fig3_en_same(os.path.join(HERE, "fig3_loss_en.png"))
    print("done")
