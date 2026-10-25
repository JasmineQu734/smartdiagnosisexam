# -*- coding: utf-8 -*-
"""重新生成论文全部插图，输出到桌面（600 dpi PNG + 矢量 PDF + SVG），不写回 docx。

复用 deliverables/ICAICE2026/make_figures.py 的绘图函数（数据与版式不变），
只提升输出分辨率并额外导出矢量副本，便于二次修改或印刷。
"""
from __future__ import annotations

import os
import shutil
import sys

HERE = r"E:/Intrel-Train Industrial/deliverables/ICAICE2026"
sys.path.insert(0, HERE)

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

_orig_savefig = Figure.savefig


def _savefig(self, fname, **kw):
    kw = dict(kw)
    kw["dpi"] = 600
    _orig_savefig(self, fname, **kw)
    p = str(fname)
    if p.lower().endswith(".png"):
        _orig_savefig(self, p[:-4] + ".pdf", format="pdf")
        _orig_savefig(self, p[:-4] + ".svg", format="svg")


Figure.savefig = _savefig

import make_figures as M  # noqa: E402

DESK = r"C:/Users/admin/Desktop/论文图片_重绘"
GROUPS = {
    "中文会议稿_3图": [
        ("fig1_architecture_zh.png", "图1_三层架构与规则引擎.png"),
        ("fig2_guardrail_zh.png", "图2_三层护栏.png"),
        ("fig3_train_zh.png", "图3_训练损失曲线.png"),
    ],
    "中文完整稿_5图": [
        ("fig1_architecture_zh.png", "图1_三层架构.png"),
        ("fig2_guardrail_zh.png", "图2_三层护栏.png"),
        ("fig3_loss.png", "图3_训练损失.png"),
        ("fig4_coverage.png", "图4_规则覆盖率.png"),
        ("fig5_latency.png", "图5_推理延迟.png"),
    ],
    "英文IEEE稿_4图": [
        ("fig1_architecture.png", "Fig1_architecture.png"),
        ("fig2_guardrail.png", "Fig2_guardrail.png"),
        ("fig4_coverage_en.png", "Fig3_coverage.png"),
        ("fig5_latency_en.png", "Fig4_latency.png"),
    ],
}

JOBS = [
    ("fig1_architecture.png", M.fig1),
    ("fig2_guardrail.png", M.fig2),
    ("fig3_loss.png", M.fig3),
    ("fig4_coverage.png", M.fig4),
    ("fig5_latency.png", M.fig5),
    ("fig1_architecture_zh.png", M.fig1_zh),
    ("fig2_guardrail_zh.png", M.fig2_zh),
    ("fig3_train_zh.png", M.fig3_zh),
    ("fig4_coverage_en.png", M.fig4_en),
    ("fig5_latency_en.png", M.fig5_en),
]

if __name__ == "__main__":
    if os.path.isdir(DESK):
        for g in GROUPS:
            shutil.rmtree(os.path.join(DESK, g), ignore_errors=True)
    os.makedirs(DESK, exist_ok=True)
    raw = os.path.join(DESK, "_原始文件名")
    os.makedirs(raw, exist_ok=True)

    for name, fn in JOBS:
        fn(os.path.join(raw, name))
        print("生成", name, "%.0f KB" % (os.path.getsize(os.path.join(raw, name)) / 1024))

    for group, items in GROUPS.items():
        d = os.path.join(DESK, group)
        os.makedirs(d, exist_ok=True)
        for src, dst in items:
            for ext in (".png", ".pdf", ".svg"):
                s = os.path.join(raw, os.path.splitext(src)[0] + ext)
                if os.path.exists(s):
                    t = os.path.join(d, os.path.splitext(dst)[0] + ext)
                    shutil.copy2(s, t)
    print("输出目录:", DESK)
