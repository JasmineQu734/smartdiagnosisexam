# -*- coding: utf-8 -*-
"""
对 model_eval.json 里保存的原始输出做二次统计，不重新调用模型。

重点是「事实编号引用」这一项：run_model_eval.py 的硬判据是「≥3 条 reasons 带有效 F 编号」，
但只报通过率会丢失信息。这里补三个细粒度指标：
  · 至少一处有效引用的输出占比
  · reasons 中带引用的条数占全部 reasons 的比例
  · 「等级差写对但没标出处」的输出占比（内容对、出处缺）
"""
from __future__ import annotations

import json
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "results", "model_eval.json")
OUT = os.path.join(HERE, "results", "model_eval_cite.json")


def analyse(cases: list) -> dict:
    rows = []
    for case in cases:
        raw = case.get("raw")
        if not raw:
            continue
        text = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
        try:
            payload = json.loads(text)
        except Exception:
            continue
        reasons = [str(item) for item in (payload.get("verdict") or {}).get("reasons", [])]
        cited = [item for item in reasons if re.search(r"F\d+", item)]
        factors = {int(code) for item in reasons for code in re.findall(r"F(\d+)", item)}
        rows.append({
            "group": case["group"],
            "reasons": len(reasons),
            "cited": len(cited),
            "any_cite": bool(cited),
            "three_plus": len(cited) >= 3,
            "codes": sorted(factors),
        })

    def agg(subset: list) -> dict:
        if not subset:
            return {}
        total_reasons = sum(row["reasons"] for row in subset)
        total_cited = sum(row["cited"] for row in subset)
        return {
            "n": len(subset),
            "any_cite_rate": round(sum(1 for row in subset if row["any_cite"]) / len(subset), 4),
            "three_plus_rate": round(sum(1 for row in subset if row["three_plus"]) / len(subset), 4),
            "cited_share_of_reasons": round(total_cited / total_reasons, 4) if total_reasons else 0.0,
            "mean_factors_cited": round(statistics.fmean(len(row["codes"]) for row in subset), 2),
        }

    return {
        "overall": agg(rows),
        "heldout": agg([row for row in rows if row["group"] == "heldout"]),
        "verbatim": agg([row for row in rows if row["group"] == "verbatim"]),
    }


def main() -> int:
    with open(SRC, encoding="utf-8") as handle:
        data = json.load(handle)
    result = analyse(data["cases"])
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    print("写出", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
