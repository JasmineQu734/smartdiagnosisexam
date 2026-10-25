# -*- coding: utf-8 -*-
"""
用修正后的判据重算 model_eval.json，不重新调用模型。

背景：首版 run_model_eval.py 的 parse_prompt() 把事实编号存成字符串集合，
而 check() 用整数去比对，导致「事实编号引用」一项恒判失败。原始输出已保存在
model_eval.json 的 raw 字段里，因此只要按同样的确定性顺序重建样本、重新解析事实，
就能离线重算全部指标。

用法：
    python eval/rescore_model_eval.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from run_model_eval import TRAIN_CORPUS, build_heldout, check, parse_prompt  # noqa: E402

OUT = os.path.join(HERE, "results", "model_eval.json")
HELDOUT_N, TRAIN_N, SEED = 20, 6, 20261017


def main() -> int:
    with open(OUT, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data["cases"]

    with open(TRAIN_CORPUS, encoding="utf-8") as handle:
        train = json.load(handle)
    train_inputs = {item["input"] for item in train}
    heldout = build_heldout(HELDOUT_N, SEED, train_inputs)
    step = max(len(train) // TRAIN_N, 1)
    verbatim = [train[index] for index in range(0, len(train), step)][:TRAIN_N]
    pool = {"heldout": heldout, "verbatim": verbatim}

    score = dict.fromkeys(cases[0], None) if cases else {}
    mismatch = 0
    for case in cases:
        group, index = case["group"], case["index"]
        sample = pool[group][index - 1]
        if case.get("prompt_chars") and len(sample["input"]) != case["prompt_chars"]:
            mismatch += 1
        facts = parse_prompt(sample["input"])
        if not case.get("raw"):
            continue
        result = check(case["raw"], facts)
        for key in ("json_ok", "contract_ok", "gaps_ok", "levels_ok", "severity_ok",
                    "priority_ok", "priority_gap_ok", "plan_ok", "cite_ok", "numbers_ok",
                    "safety_ok", "violations",
                    "unverified_numbers", "gaps_count", "plan_count", "confidence"):
            if key in result:
                case[key] = result[key]
            elif key in case and key != "violations":
                case.pop(key, None)

    def rate(rows: list, key: str) -> float:
        return round(sum(1 for row in rows if row.get(key)) / len(rows), 4) if rows else 0.0

    summary = {}
    for group in ("heldout", "verbatim"):
        rows = [row for row in cases if row["group"] == group and row.get("raw")]
        if not rows:
            continue
        latencies = sorted(row["latency_s"] for row in rows if row.get("latency_s"))
        summary[group] = {
            "n": len(rows),
            "json_rate": rate(rows, "json_ok"),
            "contract_rate": rate(rows, "contract_ok"),
            "gap_set_rate": rate(rows, "gaps_ok"),
            "level_accuracy": rate(rows, "levels_ok"),
            "priority_rate": rate(rows, "priority_ok"),
            "priority_gap_rate": rate(rows, "priority_gap_ok"),
            "severity_rate": rate(rows, "severity_ok"),
            "plan_rate": rate(rows, "plan_ok"),
            "citation_rate": rate(rows, "cite_ok"),
            "number_grounded_rate": rate(rows, "numbers_ok"),
            "safety_rate": rate(rows, "safety_ok"),
            "all_pass_rate": round(sum(1 for row in rows if all(
                row.get(key) for key in ("json_ok", "contract_ok", "gaps_ok", "levels_ok",
                                         "severity_ok", "priority_ok", "plan_ok",
                                         "cite_ok", "numbers_ok", "safety_ok"))) / len(rows), 4),
            "latency_p50": statistics.median(latencies),
            "latency_mean": round(statistics.fmean(latencies), 1),
            "latency_max": max(latencies),
            "violations": {tag: sum(1 for row in rows if tag in (row.get("violations") or []))
                           for tag in sorted({tag for row in rows
                                              for tag in (row.get("violations") or [])})},
        }
    summary["config"] = data["summary"].get("config", {})
    data["summary"] = summary

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)

    for group, block in summary.items():
        if group == "config":
            continue
        print(group, json.dumps(block, ensure_ascii=False))
    if mismatch:
        print("  ！有 %d 条样本的 prompt 长度与重建结果不一致，重算可能错位" % mismatch)
    else:
        print("  样本重建与原始运行逐条对齐（prompt 长度全部一致）")
    print("已重算", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
