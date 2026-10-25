# -*- coding: utf-8 -*-
"""把核订后的参考文献写回三份原稿（原地替换文献段落，正文/图表/版式零改动）。

只做一件事：定位以 "[n] " 开头的文献段落，保留编号与段落格式，
用 content 源里的最新条目替换其文字。改前自动备份。
"""
from __future__ import annotations

import os
import shutil
import sys

from docx import Document

HERE = r"E:/Intrel-Train Industrial/deliverables/ICAICE2026"
sys.path.insert(0, HERE)

import content            # 英文 25 条
import content_zh         # 中文 25 条
import content_conf       # 会议 13 条

JOBS = [
    ("main_IEEE.docx", content.REFS),
    ("中文稿_变电运维个性化Agent.docx", content_zh.REFS_ZH),
    ("投稿版_中文EI会议_规则增强.docx", content_conf.REFS),
]

BACKUP = os.path.join(HERE, "_备份_写回前_20261020")


def ref_paragraphs(doc):
    """按出现顺序返回形如 [3] 的文献段落"""
    out = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if len(t) > 3 and t.startswith("[") and "]" in t[:5]:
            head = t[1:t.index("]")]
            if head.isdigit():
                out.append((int(head), p))
    return out


def replace_entry(p, num, text):
    """保留段落格式，用单一 run 写入 [num] + text。"""
    body = text.strip()
    if not body.endswith("."):
        body += "."
    label = "[%d] " % num
    runs = p.runs
    if not runs:
        return False
    base = runs[0]
    # 保留首个 run 的字体属性，其余全部删除
    for r in runs[1:]:
        r._element.getparent().remove(r._element)
    base.text = label + body
    return True


def main():
    os.makedirs(BACKUP, exist_ok=True)
    for name, refs in JOBS:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print("！缺少文件", name)
            continue
        shutil.copy2(path, os.path.join(BACKUP, name))
        doc = Document(path)
        found = ref_paragraphs(doc)
        # 只取连续块：从第一个开始，编号必须 1..len(refs) 连续
        by_num = dict(found)
        missing = [i for i in range(1, len(refs) + 1) if i not in by_num]
        extra = [n for n in by_num if n > len(refs)]
        if missing or extra:
            print(f"！{name} 文献段落编号异常 missing={missing} extra={extra}，跳过")
            continue
        for i, r in enumerate(refs, 1):
            replace_entry(by_num[i], i, r)
        doc.save(path)
        print(f"已写回 {name}：{len(refs)} 条")

        # 复核
        doc2 = Document(path)
        check = dict(ref_paragraphs(doc2))
        bad = []
        for i, r in enumerate(refs, 1):
            want = "[%d] " % i + (r.strip() if r.strip().endswith(".") else r.strip() + ".")
            got = check[i].text
            if " ".join(got.split()) != " ".join(want.split()):
                bad.append(i)
        print("   逐条比对：", "全部一致" if not bad else f"不一致 {bad}")


if __name__ == "__main__":
    main()
