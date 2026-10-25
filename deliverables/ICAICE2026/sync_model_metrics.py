# -*- coding: utf-8 -*-
"""
把 eval/results/model_eval.json 的实测结果写进 content_zh.py 的表 14 与表 15，
避免手抄数字。只改 T_MODEL / T_ABLATION 里带 __ 占位符的单元格，其余文本不动。

用法：
    python sync_model_metrics.py            # 写入
    python sync_model_metrics.py --check    # 只报告还差哪些占位符
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
METRICS = os.path.join(ROOT, "eval", "results", "model_eval.json")
CONTENT = os.path.join(HERE, "content_zh.py")


def pct(value) -> str:
    return "%.0f%%" % (round(float(value) * 100))


def latency(row: dict) -> str:
    if not row or row.get("latency_p50") is None:
        return "—"
    return "%.0f / %.0f / %.0f s" % (row["latency_p50"], row["latency_mean"], row["latency_max"])


def build_map(data: dict) -> dict:
    held = data["summary"].get("heldout") or {}
    verb = data["summary"].get("verbatim") or {}
    keys = {
        "JSON": "json_rate", "CONTRACT": "contract_rate", "GAPS": "gap_set_rate",
        "LEVELS": "level_accuracy", "PRIORITY": "priority_rate", "PLAN": "plan_rate",
        "CITE": "citation_rate", "NUM": "number_grounded_rate", "SAFETY": "safety_rate",
        "ALL": "all_pass_rate", "SEVERITY": "severity_rate", "PGAP": "priority_gap_rate",
    }
    mapping = {}
    for token, field in keys.items():
        mapping["__H_%s__" % token] = pct(held.get(field, 0))
        mapping["__V_%s__" % token] = pct(verb.get(field, 0))
    mapping["__H_LAT__"] = latency(held)
    mapping["__V_LAT__"] = latency(verb)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(METRICS):
        print("缺少实测结果：", METRICS, file=sys.stderr)
        return 2
    with open(METRICS, encoding="utf-8") as handle:
        data = json.load(handle)
    mapping = build_map(data)

    with open(CONTENT, encoding="utf-8") as handle:
        text = handle.read()

    left = sorted(set(re.findall(r"__[A-Z0-9_]+__", text)))
    if args.check:
        print("剩余占位符：", left or "无")
        return 0

    for token, value in mapping.items():
        text = text.replace(token, value)
    with open(CONTENT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    left = sorted(set(re.findall(r"__[A-Z0-9_]+__", text)))
    held = data["summary"].get("heldout", {})
    verb = data["summary"].get("verbatim", {})
    print("已写入", CONTENT)
    print("  留出 n=%s 六项全通 %s｜契约 %s｜等级 %s｜排期 %s｜溯源 %s｜安全 %s"
          % (held.get("n"), pct(held.get("all_pass_rate", 0)), pct(held.get("contract_rate", 0)),
             pct(held.get("level_accuracy", 0)), pct(held.get("plan_rate", 0)),
             pct(held.get("number_grounded_rate", 0)), pct(held.get("safety_rate", 0))))
    print("  对照 n=%s 六项全通 %s｜契约 %s｜等级 %s｜排期 %s｜溯源 %s｜安全 %s"
          % (verb.get("n"), pct(verb.get("all_pass_rate", 0)), pct(verb.get("contract_rate", 0)),
             pct(verb.get("level_accuracy", 0)), pct(verb.get("plan_rate", 0)),
             pct(verb.get("number_grounded_rate", 0)), pct(verb.get("safety_rate", 0))))
    print("  剩余占位符（需手写正文）：", left or "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
