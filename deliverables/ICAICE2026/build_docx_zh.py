# -*- coding: utf-8 -*-
"""生成中文稿 Word（单栏）。公式为真 OMML 对象，可在 Word 中直接编辑。"""
from __future__ import annotations

import os
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as CEN          # noqa: E402  英文参考文献复用
import content_zh as C         # noqa: E402
from build_docx import omml_from_tokens  # noqa: E402  公式内核复用

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "中文稿_变电运维个性化Agent.docx")

BY_NUM = {int(t["num"]): t for t in C.TABLES}

BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
CODE_RE = re.compile(r"`([^`]+?)`", re.S)


def run(p, text, size=10.5, bold=False, italic=False,
        ascii_font="Times New Roman", ea_font="宋体"):
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.name = ascii_font
    rPr = r._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:eastAsia"), ea_font)
    return r


def rich(p, text, size=10.5, ea_font="宋体"):
    """**加粗** 与 `等宽代码`。"""
    pos = 0
    segs = []
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            segs.append(("n", text[pos:m.start()]))
        segs.append(("b", m.group(1)))
        pos = m.end()
    if pos < len(text):
        segs.append(("n", text[pos:]))
    for kind, seg in segs:
        p2 = 0
        for m in CODE_RE.finditer(seg):
            if m.start() > p2:
                run(p, seg[p2:m.start()], size=size, bold=(kind == "b"), ea_font=ea_font)
            run(p, m.group(1), size=size - 0.5, bold=(kind == "b"),
                ascii_font="Consolas", ea_font="Consolas")
            p2 = m.end()
        if p2 < len(seg):
            run(p, seg[p2:], size=size, bold=(kind == "b"), ea_font=ea_font)


def eq_paragraph(doc, tokens, num):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p._p.append(omml_from_tokens(tokens))
    run(p, "\t（%d）" % num, size=10.5)


TEXT_WIDTH_PT = 450.0   # 正文净宽（Letter 8.5in − 左右各 1.1in ≈ 453.6pt，留 3pt 余量）

LATIN_RUN = re.compile(r"[A-Za-z0-9_\-\.\+/=%<>:,]+")

# Times New Roman 的字符宽度表（em/1000）。用实测表代替估算，避免「差 1pt 就折行」。
_TNR = {
    "A": 722, "B": 667, "C": 667, "D": 722, "E": 611, "F": 556, "G": 722, "H": 722,
    "I": 333, "J": 389, "K": 722, "L": 611, "M": 889, "N": 722, "O": 722, "P": 556,
    "Q": 722, "R": 667, "S": 556, "T": 611, "U": 722, "V": 722, "W": 944, "X": 722,
    "Y": 722, "Z": 611, "a": 444, "b": 500, "c": 444, "d": 500, "e": 444, "f": 333,
    "g": 500, "h": 500, "i": 278, "j": 278, "k": 500, "l": 278, "m": 778, "n": 500,
    "o": 500, "p": 500, "q": 500, "r": 333, "s": 389, "t": 278, "u": 500, "v": 500,
    "w": 722, "x": 500, "y": 500, "z": 444, "0": 500, "1": 500, "2": 500, "3": 500,
    "4": 500, "5": 500, "6": 500, "7": 500, "8": 500, "9": 500, " ": 250, "_": 500,
    ".": 250, "-": 333, "/": 278, "=": 564, "+": 564, ":": 278, ",": 250,
    "(": 333, ")": 333, "%": 833, "<": 564, ">": 564,
}


def _text_pt(text, size=8.5):
    """按 Times New Roman 的字宽表估算一段文本的排版宽度（中文按全角）。"""
    total = 0.0
    for ch in str(text):
        if ord(ch) > 127:
            total += size
        else:
            total += size * _TNR.get(ch, 500) / 1000.0
    return total


def _atom_pt(text, size=8.5):
    """一段文本里最长「不可断片段」的宽度（pt）。

    中文可在任意两字之间折行，不构成约束；真正会逼 Word 在词内折行的是规则编号这类西文长串。
    """
    return max([_text_pt(run, size) for run in LATIN_RUN.findall(str(text))], default=0.0)


def fit_to_text_width(tb, rows, header):
    """按内容长度加权分配列宽，同时保证任何一列都装得下最长的不可断片段。"""
    weights = []
    for index, name in enumerate(header):
        longest = max([len(str(name))] + [len(str(row[index])) for row in rows]) if rows else len(str(name))
        # 中文按 1.9 倍宽计，短的列给个下限，避免挤成竖排
        weights.append(min(max(longest * 1.6, 7.0), 46.0))

    limits = [_atom_pt(name, 8.5) for name in header]
    # 表头不能再被压成竖排：中文表头至少按「一行放得下」给宽度
    for index, name in enumerate(header):
        limits[index] = max(limits[index], _text_pt(name, 8.5))
    for row in rows:
        for index, value in enumerate(row):
            limits[index] = max(limits[index], _atom_pt(value, 8.5))
            # 中文虽可逐字折行，但每行至少容纳 6 个汉字，避免「规则配置层」排成竖列
            cjk = sum(1 for ch in str(value) if ord(ch) > 127)
            limits[index] = max(limits[index], min(cjk, 6) * 8.5)
    # 加 6pt 给单元格左右内边距（各 2.85pt），否则「刚好装下」会被挤成两行
    limits = [min(v + 6.0, TEXT_WIDTH_PT * 0.62) for v in limits]

    total = sum(weights)
    base = [TEXT_WIDTH_PT * weight / total for weight in weights]
    widths = [max(width, low) for width, low in zip(base, limits)]
    spill = sum(widths) - TEXT_WIDTH_PT
    if spill > 0:
        # 只压缩还有余量的列，已经被钉到下限的列不再动，避免长编号再次被折断
        slack = [i for i, w in enumerate(widths) if w - limits[i] > 1e-9]
        room = sum(widths[i] - limits[i] for i in slack)
        if room > 0:
            take = min(1.0, spill / room)
            for i in slack:
                widths[i] -= (widths[i] - limits[i]) * take
        scale = TEXT_WIDTH_PT / sum(widths)
        widths = [width * scale for width in widths]
    for column, width in zip(tb.columns, widths):
        column.width = Pt(width)
    # 关键：固定布局下 Word 优先按 tcW（单元格宽）排版，只设 gridCol 会被均分
    for row in tb.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Pt(width)
    tblPr = tb._tbl.tblPr
    for el in tblPr.findall(qn("w:tblW")):
        tblPr.remove(el)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(int(TEXT_WIDTH_PT * 20)))
    tbl_w.set(qn("w:type"), "dxa")
    tblPr.append(tbl_w)


TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
    "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription",
    "tblPrChange",
]


def _sort_tblPr(tb):
    """OOXML 对 tblPr 子元素顺序有严格要求；顺序错了 Word 会静默忽略（列宽因此被均分）。"""
    tblPr = tb._tbl.tblPr
    rank = {name: index for index, name in enumerate(TBLPR_ORDER)}
    children = list(tblPr)
    children.sort(key=lambda el: rank.get(el.tag.split("}")[-1], len(TBLPR_ORDER)))
    for el in children:
        tblPr.append(el)


def _fixed_layout(tb):
    """告诉 Word 按给定列宽排版；缺了它，Word 会按内容重新分配列宽，长编号还会被折断。"""
    tblPr = tb._tbl.tblPr
    for el in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(el)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    # 单元格左右内边距收到 2.85pt（默认 5.76pt），把省下的宽度让给内容
    for el in tblPr.findall(qn("w:tblCellMar")):
        tblPr.remove(el)
    margin = OxmlElement("w:tblCellMar")
    for side, twips in (("left", 57), ("right", 57), ("top", 14), ("bottom", 14)):
        node = OxmlElement("w:%s" % side)
        node.set(qn("w:w"), str(twips))
        node.set(qn("w:type"), "dxa")
        margin.append(node)
    tblPr.append(margin)


def _mark_row(row, repeat=False):
    """跨页时重复表头，并禁止单行被拆到两页。"""
    trPr = row._tr.get_or_add_trPr()
    if repeat:
        el = OxmlElement("w:tblHeader")
        el.set(qn("w:val"), "true")
        trPr.append(el)
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_table(doc, t, keep=False, size=8.5):
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(8)
    cap.paragraph_format.space_after = Pt(2)
    run(cap, "表 %s　" % t["num"], size=9, bold=True)
    run(cap, t["caption"], size=9)

    tb = doc.add_table(rows=1, cols=len(t["header"]))
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    tb.autofit = False
    for i, h in enumerate(t["header"]):
        c = tb.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        run(p, h, size=size, bold=True)
    _mark_row(tb.rows[0], repeat=True)
    for row in t["rows"]:
        cells = tb.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            rich(p, str(v), size=size)
        _mark_row(tb.rows[-1])
    fit_to_text_width(tb, t["rows"], t["header"])
    _fixed_layout(tb)
    _sort_tblPr(tb)
    if keep:
        # 表题与整表保持在同一页：除末行外都施加「与下段同页」
        cap.paragraph_format.keep_with_next = True
        for row in tb.rows[:-1]:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True
    # 表后留白：用 4pt 定高空段占位，避免默认行高吃掉整行版面
    tail = doc.add_paragraph()
    tail.paragraph_format.space_after = Pt(2)
    tail.paragraph_format.line_spacing = Pt(4)


def add_algo(doc, spec):
    """算法框：1×1 单元格做底板，浅灰底 + 细边框，行内用等宽字体。"""
    tb = doc.add_table(rows=1, cols=1)
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    tb.autofit = False
    tb.columns[0].width = Pt(TEXT_WIDTH_PT)
    cell = tb.rows[0].cells[0]
    cell.text = ""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F7F7F7")
    cell._tc.get_or_add_tcPr().append(shd)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    run(p, spec["title"], size=8.8, bold=True, ea_font="黑体")
    for line in spec["lines"]:
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.12
        run(p, line, size=8.2, ascii_font="Consolas", ea_font="宋体")

    tblPr = tb._tbl.tblPr
    for el in tblPr.findall(qn("w:tblW")):
        tblPr.remove(el)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(int(TEXT_WIDTH_PT * 20)))
    tbl_w.set(qn("w:type"), "dxa")
    tblPr.append(tbl_w)
    _fixed_layout(tb)
    _sort_tblPr(tb)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_figure(doc, name, caption):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(4.3))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    m = re.match(r"fig(\d+)", name)
    run(cap, ("图 %s　" % m.group(1)) if m else "", size=9, bold=True)
    run(cap, caption, size=9)


def build():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.5

    sec = doc.sections[0]
    sec.top_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin = Inches(1.1)
    sec.right_margin = Inches(1.1)

    # 题名与作者
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    run(p, C.TITLE, size=16, bold=True, ea_font="黑体")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run(p, C.AUTHORS, size=11)
    for line in C.AFFIL.split("\n"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        run(p, line, size=9)

    # 摘要
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.first_line_indent = Pt(0)
    run(p, "摘要：", size=9.5, bold=True)
    rich(p, C.ABSTRACT, size=9.5)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    run(p, "关键词：", size=9.5, bold=True)
    run(p, C.KEYWORDS, size=9.5)

    # 正文
    for kind, val in C.BODY:
        if kind == "h1":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(6)
            run(p, val, size=12, bold=True, ea_font="黑体")
        elif kind == "h2":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            run(p, val, size=10.5, bold=True, ea_font="黑体")
        elif kind == "p":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Pt(21)   # 首行缩进 2 字符
            rich(p, val, size=10.5)
        elif kind == "list":
            for it in val:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.left_indent = Pt(21)
                p.paragraph_format.first_line_indent = Pt(-10.5)
                rich(p, "· " + it, size=10.5)
        elif kind == "eq":
            eq_paragraph(doc, C.EQ[val], val)
        elif kind == "algo":
            add_algo(doc, val)
        elif kind == "fig":
            add_figure(doc, *val)
        elif kind == "table":
            add_table(doc, BY_NUM[val])

    # 参考文献（保留英文原貌，学术惯例）
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    run(p, "参考文献", size=12, bold=True, ea_font="黑体")
    refs = getattr(C, "REFS_ZH", None) or CEN.REFS
    for i, r in enumerate(refs, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(21)
        p.paragraph_format.first_line_indent = Pt(-21)
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(2)
        run(p, "[%d] " % i, size=9)
        rich(p, r, size=9)

    doc.save(OUT)
    print("已写出", OUT, "（%.1f KB）" % (os.path.getsize(OUT) / 1024))

    # 一致性自检：每张表都必须被正文引用到，且不存在未定义的编号
    used = [val for kind, val in C.BODY if kind == "table"]
    missing = [n for n in BY_NUM if n not in used]
    if missing:
        print("  ！未在正文出现的表：", missing)
    if len(used) != len(set(used)):
        print("  ！有表被重复插入")
    stray = [val for kind, val in C.BODY if isinstance(val, str) and "__" in val]
    if stray:
        print("  ！正文仍含占位符", len(stray), "处")
    import re as _re
    body_text = "".join(val for kind, val in C.BODY if kind == "p")
    for n in range(1, len(C.TABLES) + 1):
        if "表 %d" % n not in body_text:
            print("  ！正文未提及表", n)


if __name__ == "__main__":
    build()
