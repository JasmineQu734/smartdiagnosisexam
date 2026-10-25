# -*- coding: utf-8 -*-
"""生成中文 EI 会议投稿版（A4 单栏，目标 4–6 页）。

排版内核复用 build_docx_zh（列宽按字宽表实测、固定布局、tblPr 按 schema 排序），
只把页面与字号改为会议稿的紧凑口径。
"""
from __future__ import annotations

import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_docx_zh as B          # noqa: E402
import content_conf as C           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "投稿版_中文EI会议_规则增强.docx")

# A4 21cm − 左右各 2.2cm = 16.6cm ≈ 470.5pt，留 2pt 余量
B.TEXT_WIDTH_PT = 481.0

FIG_W = {1: 6.3, 2: 9.2, 3: 8.4}   # 单位 cm，按图自身宽高比定高；2、3 按设计尺寸 1:1 打印
BY_NUM = {t["num"]: t for t in C.TABLES}


def add_fig(doc, num, name, caption):
    path = os.path.join(HERE, name)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(FIG_W[num]))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    B.run(cap, "图 %d　" % num, size=9, bold=True)
    B.run(cap, caption, size=9)


def build():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(B.qn("w:eastAsia"), "宋体")
    st.paragraph_format.space_after = Pt(2)
    st.paragraph_format.line_spacing = 1.0

    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.0)
    sec.right_margin = Cm(2.0)

    # 题名、作者、单位
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    B.run(p, C.TITLE, size=17, bold=True, ea_font="黑体")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    B.run(p, C.AUTHORS, size=11)
    for line in C.AFFIL.split("\n"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        B.run(p, line, size=9)

    # 摘要与关键词
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(8)
    B.run(p, "摘要：", size=9.5, bold=True, ea_font="黑体")
    B.rich(p, C.ABSTRACT, size=9.5)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    B.run(p, "关键词：", size=9.5, bold=True, ea_font="黑体")
    B.run(p, C.KEYWORDS, size=9.5)

    # 正文
    for kind, val in C.BODY:
        if kind == "h1":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.keep_with_next = True
            B.run(p, val, size=12, bold=True, ea_font="黑体")
        elif kind == "h2":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.keep_with_next = True
            B.run(p, val, size=10.5, bold=True, ea_font="黑体")
        elif kind == "p":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Pt(20)
            B.rich(p, val, size=10.0)
        elif kind == "eq":
            B.eq_paragraph(doc, C.EQ_MAP[val], val)
        elif kind == "table":
            B.add_table(doc, BY_NUM[val], keep=False, size=8.0)
        elif kind == "fig1":
            add_fig(doc, 1, "fig1_architecture_zh.png", val)
        elif kind == "fig2":
            add_fig(doc, 2, "fig2_guardrail_zh.png", val)
        elif kind == "fig3":
            add_fig(doc, 3, "fig3_train_zh.png", val)

    # 参考文献
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    B.run(p, "参考文献", size=12, bold=True, ea_font="黑体")
    for i, r in enumerate(C.REFS, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Pt(18)
        p.paragraph_format.first_line_indent = Pt(-18)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        B.run(p, "[%d] " % i, size=7.2)
        B.rich(p, r, size=7.2)

    doc.save(OUT)
    print("已写出", OUT, "(%.1f KB)" % (os.path.getsize(OUT) / 1024))

    # 自检：图、表、式、文献必须与正文交叉引用一一对应
    txt = "".join(v for k, v in C.BODY if k == "p")
    for n in range(1, len(C.TABLES) + 1):
        if "表 %d" % n not in txt:
            print("  ！正文未提及表", n)
    figs = [1 for k, _v in C.BODY if k.startswith("fig")]
    ref_figs = sorted({int(x) for x in re.findall(r"图\s*(\d)", txt)})
    for n in range(1, len(figs) + 1):
        if n not in ref_figs:
            print("  ！图", n, "插入但正文未提及")
    for n in ref_figs:
        if n > len(figs):
            print("  ！正文提及图", n, "但未插入")
    for n in sorted(C.EQ_MAP):
        if "式（%d）" % n not in txt:
            print("  ！正文未提及式", n)
    used = sorted({int(x) for x in re.findall(r"\[(\d+)\]", txt)})
    if used and max(used) > len(C.REFS):
        print("  ！悬空引用", [x for x in used if x > len(C.REFS)])
    unused = [i for i in range(1, len(C.REFS) + 1) if i not in used]
    if unused:
        print("  ！文献未被正文引用", unused)


if __name__ == "__main__":
    build()
