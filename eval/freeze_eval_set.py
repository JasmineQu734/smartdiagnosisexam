# -*- coding: utf-8 -*-
"""
把模型评测用的 26 条样本（20 条留出 + 6 条训练原样）冻结成 jsonl，
并与已经发表的 model_eval.json 逐条比对 prompt 长度，证明「基线跑的是同一批题」。

为什么必须先冻结
----------------
run_model_eval.py 每次都用固定种子现场重建样本。只要生成器或档案库有任何改动，
重建出来的就是另一批题，此时拿基线与已发表的 M1 结果对比就是无效对比。
冻结之后再跑基线，样本、种子、采样参数三者才同时固定。

用法
----
    python eval/freeze_eval_set.py                     # 生成并校验
    python eval/freeze_eval_set.py --out eval/data/eval_set_26.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_model_eval as R  # noqa: E402

TRAIN_CORPUS = R.TRAIN_CORPUS
REFERENCE = os.path.join(HERE, "results", "model_eval.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", type=int, default=20)
    parser.add_argument("--train", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--out", default=os.path.join(HERE, "data", "eval_set_26.jsonl"))
    parser.add_argument("--reference", default=REFERENCE)
    args = parser.parse_args()

    with open(TRAIN_CORPUS, encoding="utf-8") as handle:
        train = json.load(handle)
    train_inputs = {item["input"] for item in train}

    heldout = R.build_heldout(args.heldout, args.seed, train_inputs)
    step = max(len(train) // max(args.train, 1), 1)
    verbatim = [train[index] for index in range(0, len(train), step)][:args.train]

    rows = []
    for group, samples in (("heldout", heldout), ("verbatim", verbatim)):
        for position, sample in enumerate(samples, start=1):
            rows.append({"group": group, "index": position,
                         "system": sample["system"], "input": sample["input"]})

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"写出 {args.out}：{len(rows)} 条（留出 {len(heldout)}，训练原样 {len(verbatim)}）")

    # ---- 校验：与已发表的评测结果逐条比对 prompt 长度 ----
    if not os.path.exists(args.reference):
        print("！找不到参照结果，跳过一致性校验：", args.reference)
        return 0

    with open(args.reference, encoding="utf-8") as handle:
        reference = json.load(handle)
    ref = {(case["group"], case["index"]): case for case in reference.get("cases", [])}
    if not ref:
        print("！参照结果里没有 cases，跳过一致性校验")
        return 0

    mismatch, missing = [], []
    for row in rows:
        key = (row["group"], row["index"])
        if key not in ref:
            missing.append(key)
            continue
        expected = ref[key].get("prompt_chars")
        actual = len(row["input"])
        if expected is not None and expected != actual:
            mismatch.append((key, expected, actual))

    print(f"参照 {len(ref)} 条；缺失 {len(missing)} 条；prompt 长度不一致 {len(mismatch)} 条")
    if missing:
        print("  缺失示例：", missing[:5])
    if mismatch:
        print("  不一致示例（键, 参照, 实际）：", mismatch[:5])

    if missing or mismatch:
        print("判定：样本不可复现，基线结果与已有结果不可直接对比。")
        print("      需先查清生成器或档案库是否被改动，再决定重新评测还是只做组内对比。")
        return 1

    print("判定：26 条样本与已发表结果逐条一致，可用于同题对照。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
