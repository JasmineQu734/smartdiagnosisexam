# -*- coding: utf-8 -*-
"""生成两张英文版论文插图（按 IEEE 单栏宽度 3.35 in 设计，缩排后字号仍可读）。"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))

INK = "#1a1a1a"
EDGE = "#4a4a4a"
C_RULE = "#e8f0fb"      # 规则层
C_COMP = "#eef7ee"      # 计算层
C_DECI = "#fdf3e3"      # 决策层
C_MODEL = "#f5eefb"     # 模型
WHITE = "#ffffff"
W = 3.35


def box(ax, x, y, w, h, text, fc=WHITE, ec=EDGE, fs=6.4, bold=False, r=0.02):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.006,rounding_size=%s" % r,
                                linewidth=0.7, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=INK, zorder=3, linespacing=1.35,
            fontweight="bold" if bold else "normal")


def arrow(ax, p1, p2, style="-|>", color=EDGE, lw=0.8, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=6,
                                 linewidth=lw, color=color, zorder=1,
                                 connectionstyle="arc3,rad=%s" % rad,
                                 shrinkA=0, shrinkB=0))


# ---------------------------------------------------------------- Fig. 1

def fig1(path):
    """纵向单列：自上而下 7 级，颜色区分三层，避免窄栏内横向溢出。"""
    fig, ax = plt.subplots(figsize=(W, 5.15))
    ax.set_xlim(0, 1); ax.set_ylim(-0.045, 1.0); ax.axis("off")

    C_RULE_B = "#e8f0fb"
    C_COMP_B = "#e9f5e9"
    C_DECI_B = "#fdf3e3"
    C_MODEL_B = "#f5eefb"

    # (y_top, height, color, text, bold)
    rows = [
        (0.985, 0.085, "#f2f2f2",
         "Operational facts\nprofiles · exams · practical tasks · safety · reports", False),
        (0.865, 0.085, C_RULE_B,
         "Per-scene fact adapter\none fact source per scene, never a prior conclusion", True),
        (0.755, 0.075, C_RULE_B,
         "rule table (MySQL 8 JSON)  ·  22 rules  ·  5 scenes\nVALUE / KEYWORD groups · editable without release", False),
        (0.640, 0.075, C_COMP_B,
         "RuleEngine\npriority $\\downarrow$ · group convergence · skip channel · merge (Eq. 1)", False),
        (0.525, 0.075, C_MODEL_B,
         "LLM under the fixed 6-key JSON contract\nQwen2.5-3B-Instruct + 4-bit LoRA  ·  source = model", False),
        (0.410, 0.080, "#fdeeee",
         "Guardrail:  contract $\\rightarrow$ fact $\\rightarrow$ permission $\\rightarrow$ safety\n"
         "reject $\\rightarrow$ rewrite once $\\rightarrow$ fallback (source = rule)", True),
        (0.295, 0.075, C_DECI_B,
         "agent_suggestion\nsource = rule | model  ·  need_human_confirm = true", False),
        (0.180, 0.075, C_DECI_B,
         "Human decision\naccept · reject · modify", False),
        (0.065, 0.075, C_DECI_B,
         "decision_log\none run_id links rule_result $\\rightarrow$ suggestion $\\rightarrow$ decision", False),
    ]

    x, w = 0.030, 0.940
    prev_bottom = None
    for y_top, h, col, text, bold in rows:
        y = y_top - h
        box(ax, x, y, w, h, text, fc=col, fs=5.7, bold=bold, r=0.014)
        if prev_bottom is not None:
            arrow(ax, (x + w / 2, prev_bottom), (x + w / 2, y_top))
        prev_bottom = y

    # LLM 分支说明：规则层始终是兜底
    ax.text(0.5, -0.024,
            "the rule path is always the fallback; the model is an enhancement, never a dependency",
            ha="center", va="center", fontsize=5.3, color="#555555", style="italic")

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 2

def fig2(path):
    fig, ax = plt.subplots(figsize=(W, 3.5))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    box(ax, 0.27, 0.880, 0.34, 0.095, "Model output $y^{model}$", fc=C_MODEL, fs=6.2, bold=True)

    checks = [
        (0.730, "Contract valid?"),
        (0.580, "Fact consistent?"),
        (0.430, "Permission OK?"),
        (0.280, "Safety compliant?"),
    ]
    for y, label in checks:
        ax.add_patch(plt.Polygon([[0.44, y + 0.052], [0.62, y], [0.44, y - 0.052], [0.26, y]],
                                 closed=True, facecolor="#ffffff", edgecolor=EDGE,
                                 linewidth=0.7, zorder=2))
        ax.text(0.44, y, label, ha="center", va="center", fontsize=5.7, color=INK, zorder=3)

    arrow(ax, (0.44, 0.878), (0.44, 0.788))
    for y in (0.730, 0.580, 0.430):
        arrow(ax, (0.44, y - 0.054), (0.44, y - 0.098))

    box(ax, 0.70, 0.645, 0.29, 0.085, "Rewrite once\n(return the violation)", fc="#fdf3e3", fs=5.8)
    box(ax, 0.70, 0.855, 0.29, 0.085, "Accept\nsource = model", fc="#eef7ee", fs=5.8, bold=True)
    box(ax, 0.70, 0.135, 0.29, 0.085, "Fallback\nsource = rule", fc=C_RULE, fs=5.8, bold=True)
    box(ax, 0.02, 0.250, 0.22, 0.085, "High risk\n$\\rightarrow$ human confirm", fc=C_DECI, fs=5.8, bold=True)

    arrow(ax, (0.62, 0.730), (0.698, 0.688), rad=-0.15)
    arrow(ax, (0.62, 0.580), (0.698, 0.672), rad=0.15)
    arrow(ax, (0.62, 0.280), (0.698, 0.190), rad=0.15)
    arrow(ax, (0.62, 0.430), (0.700, 0.880), rad=-0.28)
    arrow(ax, (0.70, 0.688), (0.445, 0.745), rad=0.30)
    arrow(ax, (0.26, 0.280), (0.245, 0.280))

    ax.text(0.50, 0.045,
            "every outcome is persisted with the firing rule codes and an explanation",
            ha="center", va="center", fontsize=5.6, color="#555555", style="italic")

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 3

TRAINER_LOG = (r"D:/anaconda/LlamaFactory-main/LlamaFactory-main/saves"
               r"/Qwen2.5-3B-Instruct/lora/sft16_3b/trainer_log.jsonl")


def load_curve(path=TRAINER_LOG):
    """读 LLaMA-Factory 的 trainer_log.jsonl，返回 (steps, train_loss, eval_steps, eval_loss)。"""
    import json
    steps, losses, esteps, elosses = [], [], [], []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "loss" in row:
                steps.append(row["current_steps"])
                losses.append(row["loss"])
            elif "eval_loss" in row:
                # eval 每 50 步一次，日志里未带步号，按顺序反推
                esteps.append((len(esteps) + 1) * 50)
                elosses.append(row["eval_loss"])
    return steps, losses, esteps, elosses


def fig3(path):
    steps, losses, esteps, elosses = load_curve()

    fig, axes = plt.subplots(1, 2, figsize=(W, 1.72),
                             gridspec_kw={"wspace": 0.36, "width_ratios": [1.45, 1]})
    ax = axes[0]
    ax.plot(steps, losses, color="#2f6fb2", linewidth=0.9, marker="o", markersize=1.5)
    ax.set_yscale("log")
    ax.set_xlabel("optimisation step", fontsize=6.2, labelpad=1.5)
    ax.set_ylabel("training loss (log)", fontsize=6.2, labelpad=1.5)
    ax.tick_params(labelsize=5.4, length=2, pad=1.2, width=0.6)
    ax.grid(True, which="major", linewidth=0.35, color="#dcdcdc")
    ax.set_xlim(0, 310)
    ax.annotate("11.56 @ step 5", xy=(5, losses[0]), xytext=(46, 6.4),
                fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#888888"))
    ax.annotate("0.063 @ step 300", xy=(300, losses[-1]), xytext=(150, 0.155),
                fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#888888"))

    ax = axes[1]
    ax.plot(esteps, elosses, color="#c0504d", linewidth=0.9, marker="s", markersize=2.2)
    ax.set_xlabel("optimisation step", fontsize=6.2, labelpad=1.5)
    ax.set_ylabel("validation loss", fontsize=6.2, labelpad=1.5)
    ax.tick_params(labelsize=5.4, length=2, pad=1.2, width=0.6)
    ax.grid(True, linewidth=0.35, color="#dcdcdc")
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 0.0225)
    ax.annotate("0.0198", xy=(50, elosses[0]), xytext=(96, 0.0188), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#888888"))
    ax.annotate("0.0106", xy=(300, elosses[-1]), xytext=(176, 0.0062), fontsize=5.2, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#888888"))

    for plate in axes:
        for spine in ("top", "right"):
            plate.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            plate.spines[spine].set_linewidth(0.6)

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 4 / 5

def _use_cn():
    """挂一个中文字体，供图 4、图 5 的中文坐标标签使用。"""
    from matplotlib import font_manager
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(path):
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def fig4(path):
    """各场景命中率与档案级覆盖率。数据取自 eval/results/metrics.json（E1）。"""
    _use_cn()
    labels = ["个人诊断", "考试判定", "实操归因", "档案级覆盖"]
    rates = [96.7, 88.0, 84.7, 100.0]
    counts = ["145/150", "132/150", "127/150", "150/150"]

    fig, ax = plt.subplots(figsize=(W, 1.95))
    x = range(len(labels))
    bars = ax.bar(list(x), rates, width=0.52, color="#c9d8ea",
                  edgecolor="#5b7fa6", linewidth=0.5)
    bars[-1].set_color("#bfd4bf")
    bars[-1].set_edgecolor("#5d7f5d")
    for i, (b, c) in enumerate(zip(bars, counts)):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.6, "%.1f%%" % rates[i],
                ha="center", fontsize=5.6, color="#333333")
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() - 8.0, c,
                ha="center", fontsize=5.2, color="#ffffff")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=5.9)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("命中率 / %", fontsize=6.0, labelpad=1.5)
    ax.tick_params(axis="y", labelsize=5.4, length=2, pad=1.2, width=0.6)
    ax.tick_params(axis="x", length=0, pad=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.6)
    ax.grid(True, axis="y", linewidth=0.3, color="#e3e3e3")
    ax.set_axisbelow(True)
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig5(path):
    """两条路径的单次响应时间（毫秒，对数坐标）。数据取自 metrics.json(E4) 与 model_eval.json。"""
    _use_cn()
    labels = ["规则路径\np50", "规则路径\np95", "模型路径\np50", "模型路径\n均值"]
    values = [0.0105, 0.0194, 105400.0, 124300.0]
    colors = ["#c9d8ea", "#c9d8ea", "#e3a5a3", "#e3a5a3"]

    fig, ax = plt.subplots(figsize=(W, 1.95))
    x = range(len(labels))
    bars = ax.bar(list(x), values, width=0.55, color=colors,
                  edgecolor=["#5b7fa6", "#5b7fa6", "#8c3a37", "#8c3a37"], linewidth=0.5)
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 1e7)
    texts = ["0.0105", "0.0194", "105.4 s", "124.3 s"]
    for b, t in zip(bars, texts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.7, t,
                ha="center", fontsize=5.4, color="#333333")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=5.6)
    ax.set_ylabel("单次响应时间 / ms（对数）", fontsize=6.0, labelpad=1.5)
    ax.tick_params(axis="y", labelsize=5.2, length=2, pad=1.2, width=0.6)
    ax.tick_params(axis="x", length=0, pad=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.6)
    ax.grid(True, axis="y", linewidth=0.3, color="#e3e3e3")
    ax.set_axisbelow(True)
    ax.text(1.5, 3.0, "相差约 7 个数量级", ha="center", fontsize=5.2, color="#555555")
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)



# ------------------------------------------------ English variants (IEEE paper)

def fig4_en(path):
    labels = ["Personal\ndiagnosis", "Examination", "Practical\nanalysis", "Profile\ncoverage"]
    rates = [96.7, 88.0, 84.7, 100.0]
    counts = ["145/150", "132/150", "127/150", "150/150"]

    fig, ax = plt.subplots(figsize=(W, 2.0))
    x = list(range(len(labels)))
    bars = ax.bar(x, rates, width=0.54, color="#c9d8ea", edgecolor="#5b7fa6", linewidth=0.5)
    bars[-1].set_color("#bfd4bf")
    bars[-1].set_edgecolor("#5d7f5d")
    for b, r, c in zip(bars, rates, counts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, "%.1f" % r,
                ha="center", fontsize=5.6, color="#333333")
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() - 9.0, c,
                ha="center", fontsize=5.0, color="#ffffff")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=5.6)
    ax.set_ylim(0, 114)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("match rate (%)", fontsize=6.2, labelpad=1.5)
    ax.tick_params(axis="y", labelsize=5.4, length=2, pad=1.2, width=0.6)
    ax.tick_params(axis="x", length=0, pad=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.6)
    ax.grid(True, axis="y", linewidth=0.3, color="#e6e6e6")
    ax.set_axisbelow(True)
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig5_en(path):
    labels = ["rule path\np50", "rule path\np95", "model path\np50", "model path\nmean"]
    values = [0.0105, 0.0194, 105400.0, 124300.0]
    colors = ["#c9d8ea", "#c9d8ea", "#e3a5a3", "#e3a5a3"]
    edges = ["#5b7fa6", "#5b7fa6", "#8c3a37", "#8c3a37"]
    texts = ["0.0105 ms", "0.0194 ms", "105.4 s", "124.3 s"]

    fig, ax = plt.subplots(figsize=(W, 2.0))
    x = list(range(len(labels)))
    bars = ax.bar(x, values, width=0.55, color=colors, edgecolor=edges, linewidth=0.5)
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 1e8)
    for b, t in zip(bars, texts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.8, t,
                ha="center", fontsize=5.2, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=5.6)
    ax.set_ylabel("single response time (ms, log)", fontsize=6.0, labelpad=1.5)
    ax.tick_params(axis="y", labelsize=5.2, length=2, pad=1.2, width=0.6)
    ax.tick_params(axis="x", length=0, pad=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.6)
    ax.grid(True, axis="y", linewidth=0.3, color="#e6e6e6")
    ax.set_axisbelow(True)
    ax.text(1.5, 20, "about 7 orders of magnitude", ha="center", fontsize=5.0, color="#555555")
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


# ------------------------------------------------ 中文版图 1 / 图 2（单栏会议稿用）

def fig1_zh(path):
    """与 fig1 同几何、中文标注，供中文稿使用。"""
    _use_cn()
    C_RULE_B = "#e8f0fb"
    C_COMP_B = "#e9f5e9"
    C_DECI_B = "#fdf3e3"
    C_MODEL_B = "#f5eefb"
    fig, ax = plt.subplots(figsize=(2.48, 3.00))
    ax.set_xlim(0, 1); ax.set_ylim(-0.10, 1.0); ax.axis("off")

    rows = [
        (0.985, 0.105, "#f2f2f2",
         "业务事实\n人员档案 · 考试 · 实操 · 安全记录 · 检测报告", False),
        (0.845, 0.105, C_RULE_B,
         "分场景事实适配\n每场景单一来源，不读历史诊断结论", True),
        (0.705, 0.095, C_RULE_B,
         "规则表（MySQL 8 JSON）· 22 条 · 5 场景\nVALUE / KEYWORD 分组 · 修改即生效", False),
        (0.575, 0.095, C_COMP_B,
         "规则引擎\n优先级降序 · 分组收敛 · 跳过通道 · 严重度合并", False),
        (0.445, 0.095, C_MODEL_B,
         "模型：六键 JSON 契约（source = model）\nQwen2.5-3B-Instruct + 4-bit LoRA", False),
        (0.315, 0.095, "#fdeeee",
         "决策治理：四道防线与人工确认\n结构 → 数值 → 授权 → 安全；建议须人工确认", True),
        (0.185, 0.095, C_DECI_B,
         "建议 · 人工决定 · 决策日志\n同一 run_id 串联规则结果 → 建议 → 决定", False),
    ]

    x, w = 0.030, 0.940
    prev_bottom = None
    for y_top, h, col, text, bold in rows:
        y = y_top - h
        box(ax, x, y, w, h, text, fc=col, fs=5.9, bold=bold, r=0.014)
        if prev_bottom is not None:
            arrow(ax, (x + w / 2, prev_bottom), (x + w / 2, y_top))
        prev_bottom = y

    ax.text(0.5, -0.062,
            "判定由规则完成，模型只作表达；失败时可回退规则结论",
            ha="center", va="center", fontsize=5.6, color="#555555", style="italic")

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig2_zh(path):
    """四道防线与失败处置：主线自上而下，失败分支右置，与表 2 逐行对应。"""
    _use_cn()
    fig, ax = plt.subplots(figsize=(3.622, 2.46))
    ax.set_xlim(0, 1); ax.set_ylim(0.0, 1.0); ax.axis("off")

    LX, LW = 0.020, 0.560          # 主线
    RX, RW = 0.660, 0.335          # 分支
    H = 0.112
    YS = [0.860, 0.688, 0.516, 0.344, 0.172, 0.000]

    def node(y, text, fc, fs=6.4, bold=False, x=LX, w=LW):
        box(ax, x, y, w, H, text, fc=fc, fs=fs, bold=bold)

    node(YS[0], "③ 输入端授权（RoleInterceptor）\n角色决定可取哪些事实", C_DECI, fs=6.2)
    node(YS[1], "事实装配 + 规则引擎\n④ SAFETY 分组硬处置安全负例", C_RULE, fs=6.2)
    node(YS[2], "模型生成：Qwen2.5-3B + LoRA\n温度 0.2，强制 JSON 对象", C_MODEL, fs=6.2)
    node(YS[3], "① 结构契约（硬判定）\n六键完整性、枚举、等级、日期", "#ffffff", fs=6.2)
    node(YS[4], "② 数值对账（软判定）\n数字须落在事实清单内", "#ffffff", fs=6.2)
    node(YS[5], "交付　source = model\nneed_human_confirm 恒为真", "#eef7ee", bold=True)

    node(YS[0], "越权 → 403\n请求不进入事实装配", "#fdf3e3", fs=6.0, x=RX, w=RW)
    node(YS[3], "不合格 → 整份回退\nsource = rule，不重试", C_RULE, fs=6.0, x=RX, w=RW)
    node(YS[4], "未溯源 → 只留痕\n置信度封顶 0.6", "#fdf3e3", fs=6.0, x=RX, w=RW)

    for i in range(5):
        arrow(ax, (LX + LW / 2, YS[i]), (LX + LW / 2, YS[i + 1] + H))

    for i in (0, 3, 4):
        arrow(ax, (LX + LW, YS[i] + H / 2), (RX, YS[i] + H / 2))

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def fig3_zh(path):
    """训练与验证损失：左为训练损失（对数轴），右为验证损失，均取自 trainer_log.jsonl。"""
    _use_cn()
    import math

    steps, losses, esteps, elosses = load_curve()
    fig, axes = plt.subplots(1, 2, figsize=(3.307, 1.66),
                             gridspec_kw={"wspace": 0.42, "width_ratios": [1.32, 1]})

    ax = axes[0]
    ax.plot(steps, losses, color="#2f6fb2", linewidth=0.9, marker="o", markersize=1.3)
    ax.set_yscale("log")
    ax.set_ylim(0.05, 26)
    ax.axhline(math.log(151936), color="#9a9a9a", linewidth=0.6, linestyle=(0, (3, 2)))
    ax.text(112, 13.6, "词表均匀熵 ln V = 11.93", fontsize=5.4, color="#666666")
    ax.set_xlabel("优化步", fontsize=6.6, labelpad=1.5)
    ax.set_ylabel("训练损失（对数轴）", fontsize=6.6, labelpad=2.5)
    ax.tick_params(labelsize=5.6, length=2, pad=1.2, width=0.6)
    ax.grid(True, which="major", linewidth=0.32, color="#e4e4e4")
    ax.set_xlim(0, 318)
    ax.annotate("第 5 步 11.57", xy=(5, losses[0]), xytext=(40, 2.4), fontsize=5.5, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))
    ax.annotate("末步 0.063", xy=(300, losses[-1]), xytext=(126, 0.30), fontsize=5.5, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))

    ax = axes[1]
    ax.plot(esteps, elosses, color="#c0504d", linewidth=0.9, marker="s", markersize=2.0)
    ax.axvline(200, color="#9a9a9a", linewidth=0.6, linestyle=(0, (3, 2)))
    ax.text(206, 0.0186, "此后仅降 1.9%", fontsize=5.4, color="#666666")
    ax.set_xlabel("优化步", fontsize=6.6, labelpad=1.5)
    ax.set_ylabel("验证损失", fontsize=6.6, labelpad=2.0)
    ax.tick_params(labelsize=5.6, length=2, pad=1.2, width=0.6)
    ax.grid(True, linewidth=0.32, color="#e4e4e4")
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 0.0238)
    ax.annotate("0.0198", xy=(50, elosses[0]), xytext=(74, 0.0166), fontsize=5.5, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))
    ax.annotate("0.0106", xy=(300, elosses[-1]), xytext=(168, 0.0050), fontsize=5.5, color="#444444",
                arrowprops=dict(arrowstyle="-", linewidth=0.45, color="#999999"))

    for plate in axes:
        for spine in ("top", "right"):
            plate.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            plate.spines[spine].set_linewidth(0.6)

    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig1(os.path.join(HERE, "fig1_architecture.png"))
    fig2(os.path.join(HERE, "fig2_guardrail.png"))
    fig3(os.path.join(HERE, "fig3_loss.png"))
    fig4(os.path.join(HERE, "fig4_coverage.png"))
    fig5(os.path.join(HERE, "fig5_latency.png"))
    fig1_zh(os.path.join(HERE, "fig1_architecture_zh.png"))
    fig2_zh(os.path.join(HERE, "fig2_guardrail_zh.png"))
    fig3_zh(os.path.join(HERE, "fig3_train_zh.png"))
    fig4_en(os.path.join(HERE, "fig4_coverage_en.png"))
    fig5_en(os.path.join(HERE, "fig5_latency_en.png"))
    for n in ("fig1_architecture.png", "fig2_guardrail.png", "fig3_loss.png",
              "fig4_coverage.png", "fig5_latency.png"):
        p = os.path.join(HERE, n)
        print("已写出", p, "%.0f KB" % (os.path.getsize(p) / 1024))
