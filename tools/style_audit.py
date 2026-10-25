# -*- coding: utf-8 -*-
"""中文稿文风审计：把「AI 味」拆成可测量的几项，而不是凭感觉判断。

审计三个层面：
  1. 句长分布 —— 机器文本的句长高度趋同（变异系数低），人写的句子长短悬殊；
  2. 词汇层   —— 口语标记密度（越高越像人写的叙述）与 AI 套话密度（越高越像机器）；
  3. 结构层   —— 句首多样性（人写的句首更散）与 4-gram 重复率（机器爱复用语块）。

口语化 / 学术比例按「句子级」判定：
  含第一人称经验、反问、口头插入语、破折号评价或极短评价句的句子记为口语句，
  其余为学术句。目标是口语句 30%±5%。

用法：
  python tools/style_audit.py                     # 审计 content_zh.py
  python tools/style_audit.py --json out.json     # 另存机器可读结果
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAPER = os.path.join(ROOT, "deliverables", "ICAICE2026")

# ---------------------------------------------------------------- 词表

# 口头插入语 / 评价性短语：出现即视为「人在说话」
SPOKEN_PHRASES = [
    "说白了", "老实说", "说实话", "说清楚", "得说清楚", "要说明", "别小看", "顺带", "说白了",
    "压根", "挺干净", "挺有意思", "得小心", "得盯", "不好看", "不好办", "别扭", "现形",
    "塌掉", "堵死", "死代码", "踩过", "踩坑", "翻出", "值回票价", "起了个头", "摆到明面上",
    "藏起来", "不是修辞", "半张", "站在边上", "一直工作正常", "谁也不压谁", "各判各的",
    "一个都不用动", "抄一遍", "白做", "才算数", "答不上来", "干不干净", "配不配合得来",
    "这一行", "这回事", "别拿", "别当", "别把它", "才是硬的", "挺", "远远", "硬是",
    "反过来", "换句话说", "也就是说", "这么一来", "于是", "照样", "偏偏", "干脆", "反正",
    "说白了就是", "不好受", "划不来", "划算", "别扭的地方", "麻烦就在", "问题就在",
    "该看的是", "最值钱", "够用了", "吹", "别的位置", "去不了", "没人说得清",
    "谁也不知道", "没人察觉", "没察觉", "别小看这一点", "得先交代", "容易被误读",
]

# 第一人称经验叙述（学术中文里用「我们」是可接受的，但密度过高会显得口语）
FIRST_PERSON = ["我们", "我"]

# AI 高频套话：出现在这类稿件里通常意味着模板化表达
AI_CLICHES = [
    "值得注意的是", "综上所述", "总而言之", "至关重要", "显著提升", "显著提高",
    "进一步", "此外", "然而", "首先", "其次", "最后", "一方面", "另一方面",
    "不仅", "而且", "不可或缺", "相辅相成", "深入探讨", "有效解决", "有效提升",
    "在当今", "随着", "背景下", "日益", "越来越多", "极大地", "充分体现",
    "具有重要意义", "提供了有力", "奠定了坚实基础", "为此", "从而", "进而",
    "本文认为", "可以看出", "不难发现", "众所周知", "毋庸置疑",
]

SENT_SPLIT = re.compile(r"(?<=[。！？；])")


def collect_text():
    """取正文的叙述部分（含标题、摘要、段落、列表），不含表格与公式。"""
    sys.path.insert(0, PAPER)
    import content_zh as C

    blocks = [C.TITLE, C.ABSTRACT]
    for item in C.BODY:
        if item[0] in ("h1", "h2", "p"):
            blocks.append(item[1])
        elif item[0] == "list":
            blocks.extend(item[1])
        elif item[0] == "fig":
            blocks.append(item[1][1])
    text = "\n".join(blocks)
    text = re.sub(r"\*\*|`", "", text)
    return text


def split_sentences(text):
    raw = SENT_SPLIT.split(text.replace("\n", ""))
    out = []
    for s in raw:
        s = s.strip()
        if len(s) < 4:
            continue
        out.append(s)
    return out


def is_spoken(sentence):
    """句子级口语判定：命中任一条即记为口语句。"""
    s = sentence
    if any(p in s for p in SPOKEN_PHRASES):
        return True
    if any(w in s for w in FIRST_PERSON):
        return True
    if s.endswith("？") or s.endswith("?"):
        return True
    if "——" in s:
        return True
    # 极短评价句：不超过 14 字、不含数字、不以技术名词开头
    if len(s) <= 14 and not re.search(r"\d", s):
        if s.startswith(("这", "那", "它", "别", "不", "可", "于是", "结果", "而")):
            return True
    return False


def entropy(counter):
    total = sum(counter.values())
    if not total:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counter.values() if c)


def audit():
    text = collect_text()
    sents = split_sentences(text)
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    lengths = [len(re.findall(r"[\u4e00-\u9fa5]", s)) for s in sents]
    lengths = [n for n in lengths if n > 0]

    mean = statistics.mean(lengths)
    std = statistics.pstdev(lengths)

    spoken = [s for s in sents if is_spoken(s)]
    spoken_ratio = len(spoken) / len(sents)

    def density(words):
        hits = sum(text.count(w) for w in words)
        return hits, hits / han * 1000

    sp_hits, sp_dens = density(SPOKEN_PHRASES)
    ai_hits, ai_dens = density(AI_CLICHES)
    fp_hits = sum(text.count(w) for w in FIRST_PERSON)

    # 句首多样性：取句首两个字，算香农熵（bits）
    heads = [s[:2] for s in sents if len(s) >= 2]
    head_entropy = entropy({h: heads.count(h) for h in set(heads)})

    # 4-gram 重复率：字符级 4-gram 中出现过两次以上的比例
    stripped = re.sub(r"[^\u4e00-\u9fa5]", "", text)
    grams = [stripped[i:i + 4] for i in range(len(stripped) - 3)]
    uniq = len(set(grams))
    repeat_rate = 1 - uniq / len(grams) if grams else 0

    short_ratio = sum(1 for n in lengths if n <= 10) / len(lengths)
    long_ratio = sum(1 for n in lengths if n >= 45) / len(lengths)

    result = {
        "汉字数": han,
        "句子数": len(sents),
        "平均句长": round(mean, 2),
        "句长标准差": round(std, 2),
        "句长变异系数": round(std / mean, 3),
        "最短 / 最长句": (min(lengths), max(lengths)),
        "≤10 字短句占比": round(short_ratio, 4),
        "≥45 字长句占比": round(long_ratio, 4),
        "口语句数": len(spoken),
        "口语句占比": round(spoken_ratio, 4),
        "学术句占比": round(1 - spoken_ratio, 4),
        "口语标记命中": sp_hits,
        "口语标记密度（每千字）": round(sp_dens, 2),
        "第一人称次数": fp_hits,
        "AI 套话命中": ai_hits,
        "AI 套话密度（每千字）": round(ai_dens, 2),
        "句首二字熵（bits）": round(head_entropy, 3),
        "4-gram 重复率": round(repeat_rate, 4),
    }
    return result, spoken


def verdict(r):
    """把指标翻译成三条判读，避免只看一个总分。"""
    lines = []

    cv = r["句长变异系数"]
    if cv >= 0.55:
        lines.append(f"句长波动 {cv}：≥0.55，长短悬殊，符合人类写作特征。")
    elif cv >= 0.45:
        lines.append(f"句长波动 {cv}：0.45–0.55，中等，仍偏整齐。")
    else:
        lines.append(f"句长波动 {cv}：<0.45，句子过于等长，机器文本的典型特征。")

    sp = r["口语句占比"]
    if 0.25 <= sp <= 0.35:
        lines.append(f"口语化 {sp:.1%} / 学术 {1-sp:.1%}：落在 70/30 目标区间内。")
    elif sp < 0.25:
        lines.append(f"口语化 {sp:.1%}：低于目标，还需补 {(0.30-sp)*100:.1f} 个百分点。")
    else:
        lines.append(f"口语化 {sp:.1%}：高于目标，学术性偏弱，需收回 {(sp-0.30)*100:.1f} 个百分点。")

    ai = r["AI 套话密度（每千字）"]
    if ai <= 1.0:
        lines.append(f"套话密度 {ai}/千字：干净。")
    elif ai <= 3.0:
        lines.append(f"套话密度 {ai}/千字：可接受，仍有压缩空间。")
    else:
        lines.append(f"套话密度 {ai}/千字：偏高，需逐处替换。")

    h = r["句首二字熵（bits）"]
    if h >= 6.8:
        lines.append(f"句首熵 {h} bits：句式开篇分散，无明显模板。")
    else:
        lines.append(f"句首熵 {h} bits：句首过于集中，存在模板化开篇。")

    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    r, spoken = audit()
    width = max(len(k) for k in r)
    print("=" * 58)
    print("中文稿文风审计")
    print("=" * 58)
    for k, v in r.items():
        print(f"{k:<{width}} : {v}")
    print("-" * 58)
    for line in verdict(r):
        print("·", line)
    print("=" * 58)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"metrics": r, "verdict": verdict(r)}, f,
                      ensure_ascii=False, indent=1)
        print("已写出", args.json)


if __name__ == "__main__":
    main()
