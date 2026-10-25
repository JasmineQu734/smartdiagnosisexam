# -*- coding: utf-8 -*-
"""生成 IEEEtran .tex（Overleaf 可直接编译）。"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as C  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.tex")
BY_NUM = {int(t["num"]): t for t in C.TABLES}


def tex_escape(s: str) -> str:
    s = s.replace("\\", r"\textbackslash{}")
    for ch in "&%$#_{}":
        s = s.replace(ch, "\\" + ch)
    s = s.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")
    # 常见 Unicode
    s = (s.replace("—", "---").replace("–", "--").replace("“", "``").replace("”", "''")
          .replace("‘", "`").replace("’", "'").replace("≤", "$\\le$").replace("≥", "$\\ge$")
          .replace("∈", "$\\in$").replace("∧", "$\\wedge$").replace("¬", "$\\neg$")
          .replace("θ", "$\\theta$").replace("ρ", "$\\rho$").replace("×", "$\\times$")
          .replace("·", "$\\cdot$").replace("…", "\\ldots").replace("¹", "$^1$")
          .replace("µ", "$\\mu$").replace("→", "$\\to$"))
    return s


def markup(s: str) -> str:
    """*italic* -> \\textit{}，**bold** -> \\textbf{}。先处理粗体再处理斜体。"""
    s = tex_escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s, flags=re.S)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\\textit{\1}", s, flags=re.S)
    return s


def eq_tokens(tokens) -> str:
    """把 token DSL 转成 LaTeX 数学。"""
    out = []

    def walk(t):
        if isinstance(t, str):
            out.append(tex_escape(t).replace(r"\textbackslash{}", ""))
            return
        kind = t[0]
        if kind == "i":
            out.append(r"\mathit{" + tex_escape(t[1]) + "}")
        elif kind == "sub":
            out.append("_{")
            for x in t[1]:
                walk_plain(x)
            out.append("}")
        elif kind == "sup":
            out.append("^{")
            for x in t[1]:
                walk_plain(x)
            out.append("}")
        elif kind == "frac":
            out.append(r"\frac{")
            for x in t[1]:
                walk(x)
            out.append("}{")
            for x in t[2]:
                walk(x)
            out.append("}")

    def walk_plain(t):
        if isinstance(t, str):
            out.append(r"\mathrm{" + tex_escape(t) + "}")
        else:
            walk(t)

    for t in tokens:
        walk(t)
    return " ".join(out)


def table(t) -> str:
    ncol = len(t["header"])
    col = "l" * ncol
    if sum(len(str(r)) for r in t["header"]) > 90:
        col = "p{2.6cm}" * ncol
    L = [r"\begin{table}[!t]", r"\caption{" + markup(t["caption"]) + "}",
         r"\label{tab" + str(t["num"]) + "}", r"\centering",
         r"\begin{tabular}{@{}" + col + r"@{}}", r"\toprule"]
    L.append(" & ".join(r"\textbf{" + markup(h) + "}" for h in t["header"]) + r" \\")
    L.append(r"\midrule")
    for row in t["rows"]:
        L.append(" & ".join(markup(str(c)) for c in row) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(L)


def figure(name: str, caption: str) -> str:
    return "\n".join([
        r"\begin{figure}[!t]", r"\centering",
        r"\includegraphics[width=\columnwidth]{" + os.path.splitext(name)[0] + "}",
        r"\caption{" + markup(caption) + "}",
        r"\label{fig" + name.split("_")[0].replace("fig", "") + "}",
        r"\end{figure}"])



def mono(line: str) -> str:
    line = line.replace("\\", r"\textbackslash{}")
    for ch in "&%$#_{}":
        line = line.replace(ch, "\\" + ch)
    return (line.replace("<", r"$<$").replace(">", r"$>$")
                .replace("|", r"$|$").replace("~", r"$\sim$"))


def table(t) -> str:
    import math
    n = len(t["header"])
    weights = []
    for i in range(n):
        longest = max([len(str(t["header"][i]))] + [len(str(r[i])) for r in t["rows"]])
        weights.append(math.sqrt(max(longest, 4)))
    total = sum(weights)
    ratios = [max(0.955 * w / total, 0.955 * 0.12) for w in weights]

    # p{} 列不会自动断词，长标识符会把列撑破：给每列一个「装得下最长片段」的下限
    def longest_token(text):
        best = 0
        for tok in re.split(r"[^A-Za-z0-9_\-.]+", str(text)):
            best = max(best, len(tok))
        return best

    needs = []
    for i in range(n):
        chars = max([longest_token(t["header"][i])] + [longest_token(r[i]) for r in t["rows"]])
        needs.append(min(chars * 0.017 + 0.02, 0.55))
    ratios = [max(r, nd) for r, nd in zip(ratios, needs)]
    spill = sum(ratios) - 0.955
    if spill > 0:
        slack = [i for i, r in enumerate(ratios) if r - needs[i] > 1e-6]
        room = sum(ratios[i] - needs[i] for i in slack)
        if room > 0:
            take = min(1.0, spill / room)
            for i in slack:
                ratios[i] -= (ratios[i] - needs[i]) * take
        scale = 0.955 / sum(ratios)
        ratios = [r * scale for r in ratios]
    spec = "@{}" + "".join("p{%.3f\\columnwidth}" % r for r in ratios) + "@{}"
    lines = [r"\begin{table}[t]", r"\caption{" + markup(t["caption"]) + "}",
             r"\centering", r"\footnotesize",
             r"\begin{tabular}{" + spec + "}", r"\hline"]
    lines.append(" & ".join(r"\textbf{" + markup(h) + "}" for h in t["header"]) + r" \\ \hline")
    for row in t["rows"]:
        lines.append(" & ".join(markup(str(c)) for c in row) + r" \\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def algo(spec) -> str:
    lines = [r"\begin{table}[t]", r"\centering", r"\footnotesize",
             r"\begin{tabular}{@{}p{0.96\columnwidth}@{}}", r"\hline",
             r"\textbf{" + markup(spec["title"]) + r"} \\[2pt]"]
    for line in spec["lines"]:
        lines.append(r"\texttt{" + mono(line) + r"} \\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def build_body() -> str:
    parts = []
    for kind, val in C.BODY:
        if kind == "h1":
            parts.append(r"\section{" + markup(val) + "}")
        elif kind == "h2":
            parts.append(r"\subsection{" + markup(val) + "}")
        elif kind == "p":
            parts.append(markup(val) + "\n")
        elif kind == "list":
            parts.append(r"\begin{itemize}")
            for it in val:
                parts.append(r"\item " + markup(it))
            parts.append(r"\end{itemize}")
        elif kind == "eq":
            parts.append(r"\begin{equation}" + eq_tokens(C.EQ[val]) + r"\label{eq%d}\end{equation}" % val)
        elif kind == "table":
            parts.append(table(BY_NUM[val]))
        elif kind == "algo":
            parts.append(algo(val))
        elif kind == "fig":
            parts.append(figure(*val))
    return "\n\n".join(parts)


HEAD = r"""\documentclass[conference]{IEEEtran}
\IEEEoverridecommandlockouts
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{array}
\def\BibTeX{{\rm B\kern-.05em{\sc i\kern-.025em b}\kern-.08em T\kern-.1667em\lower.7ex\hbox{E}\kern-.125emX}}

\begin{document}

\title{%(title)s}

\author{\IEEEauthorblockN{%(authors)s}
\IEEEauthorblockA{%(affil)s}}

\maketitle

\begin{abstract}
%(abstract)s
\end{abstract}

\begin{IEEEkeywords}
%(keywords)s
\end{IEEEkeywords}
"""

TAIL = r"""
\bibliographystyle{IEEEtran}
% 参考文献以 \begin{thebibliography} 内联给出，便于直接编译；如需 BibTeX 可自行拆分。
"""


def refs_block() -> str:
    L = [r"\begin{thebibliography}{00}"]
    for i, r in enumerate(C.REFS, 1):
        L.append(r"\bibitem{b%d} %s" % (i, markup(r)))
    L.append(r"\end{thebibliography}")
    L.append(r"\end{document}")
    return "\n".join(L)


def main() -> None:
    body = build_body()
    # 把表格插到其所属小节之后：简单起见统一浮动到文首之后（IEEE 惯例为 [!t]）
    tables = "\n\n".join(table(t) for t in C.TABLES)
    doc = (HEAD % {"title": tex_escape(C.TITLE), "authors": tex_escape(C.AUTHORS),
                   "affil": tex_escape(C.AFFIL).replace("\n", r"\\ "),
                   "abstract": tex_escape(C.ABSTRACT),
                   "keywords": tex_escape(C.KEYWORDS)}
           + body + "\n\n" + tables + "\n" + TAIL + "\n" + refs_block())
    open(OUT, "w", encoding="utf-8").write(doc)
    print("已写出", OUT, "（%d 字符）" % len(doc))


if __name__ == "__main__":
    main()
