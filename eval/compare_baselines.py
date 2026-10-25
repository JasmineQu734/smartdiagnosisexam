# -*- coding: utf-8 -*-
"""
把三组结果并成一张对照表：规则+模板 / 规则+微调模型 / 规则+未微调基座。

同一把尺子
----------
三组用的是同一批 26 条冻结样本（eval/data/eval_set_26.jsonl）、同一个判据函数
（run_model_eval.check）、同样的采样参数（temperature 0.2、response_format=json_object）。
唯一变化的变量是「叙述由谁写」：固定模板、微调后的 3B、还是未微调的 3B。

为什么还要单独报叙述层指标
--------------------------
判定性判据（契约、gaps 集合、等级、排期、数字溯源）由架构与规则保证，
固定模板也能满分，因此它们区分不出模型的贡献。模型的增量只能落在叙述层，
这里用三个可复算的代理量衡量，并在输出里明确标注「代理指标，非人工评分」。

置信区间
--------
26 条样本的分辨率约 4%，所以每个通过率都附 Clopper-Pearson 精确双侧 95% 区间。
20/20 全通过时下界为 83.2%，这正是论文里不能写「100% 可靠」的原因。

用法
----
    python eval/compare_baselines.py
    python eval/compare_baselines.py --base eval/results/model_eval_base.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_model_eval as R  # noqa: E402

CHECKS = [("json_ok", "JSON 可解析"), ("contract_ok", "六键契约"), ("gaps_ok", "gaps 集合"),
          ("levels_ok", "等级一致"), ("priority_ok", "优先级规则"), ("plan_ok", "排期合规"),
          ("cite_ok", "事实编号引用"), ("numbers_ok", "数值可溯源"), ("safety_ok", "安全处置"),
          ("all_pass", "全部通过")]


def interval(success: int, total: int) -> tuple[float, float]:
    """Clopper-Pearson 精确双侧 95% 区间。"""
    if total == 0:
        return 0.0, 0.0
    if success == 0:
        return 0.0, round(1 - 0.025 ** (1 / total), 4)
    if success == total:
        return round(0.025 ** (1 / total), 4), 1.0
    try:
        from scipy.stats import beta
        return (round(float(beta.ppf(0.025, success, total - success + 1)), 4),
                round(float(beta.ppf(0.975, success + 1, total - success)), 4))
    except Exception:  # noqa: BLE001
        low = success / total - 1.96 * (success / total * (1 - success / total) / total) ** 0.5
        high = success / total + 1.96 * (success / total * (1 - success / total) / total) ** 0.5
        return round(max(low, 0.0), 4), round(min(high, 1.0), 4)


def load_prompts(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return {(row["group"], row["index"]): row["input"] for row in rows}


def summarize(path: str, prompts: dict, label: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data.get("cases", [])
    if not cases:
        return {"label": label, "path": path, "n": 0}

    # 兼容旧结果：没有 narrative 字段时从 raw 现算
    for case in cases:
        if "narrative" in case:
            continue
        prompt = prompts.get((case.get("group"), case.get("index")), "")
        try:
            payload = json.loads(R.re.sub(r"^```(?:json)?|```$", "", str(case.get("raw", "")).strip()).strip())
            case["narrative"] = R.narrative_metrics(payload, R.parse_prompt(prompt))
        except Exception:  # noqa: BLE001
            case["narrative"] = {}

    result = {"label": label, "path": os.path.basename(path), "n": len(cases), "rates": {},
              "narrative": {}, "latency": {}}
    for key, name in CHECKS:
        if key == "all_pass":
            passes = [all(case.get(flag) for flag in
                          ("json_ok", "contract_ok", "gaps_ok", "levels_ok", "priority_ok", "plan_ok"))
                      for case in cases]
        else:
            passes = [bool(case.get(key)) for case in cases]
        success = sum(1 for flag in passes if flag)
        low, high = interval(success, len(cases))
        result["rates"][name] = {"success": success, "n": len(cases),
                                 "rate": round(success / len(cases), 4), "ci95": [low, high]}

    narratives = [case["narrative"] for case in cases if case.get("narrative")]
    if narratives:
        for key in ("action_skeletons", "impact_skeletons", "evidence_grounded_rate",
                    "action_chars_mean", "summary_chars"):
            values = [item.get(key) for item in narratives if item.get(key) is not None]
            if values:
                result["narrative"][key] = round(statistics.fmean(values), 2)

    latencies = sorted(case["latency_s"] for case in cases if case.get("latency_s"))
    if latencies:
        result["latency"] = {"p50": round(statistics.median(latencies), 1),
                             "mean": round(statistics.fmean(latencies), 1),
                             "max": round(max(latencies), 1)}

    result["violations"] = {tag: sum(1 for case in cases if tag in case.get("violations", []))
                            for tag in sorted({tag for case in cases for tag in case.get("violations", [])})}
    return result


def markdown(group: list[dict]) -> str:
    alive = [item for item in group if item["n"]]
    lines = ["| 判据 | " + " | ".join(item["label"] for item in alive) + " |",
             "|---|" + "---|" * len(alive)]
    for _key, name in CHECKS:
        cells = []
        for item in alive:
            entry = item["rates"][name]
            cells.append("%d/%d（%.1f%%，%.1f–%.1f）" % (
                entry["success"], entry["n"], entry["rate"] * 100,
                entry["ci95"][0] * 100, entry["ci95"][1] * 100))
        lines.append("| %s | %s |" % (name, " | ".join(cells)))

    lines.append("| action 句式种类（均值） | " + " | ".join(
        "%.2f" % item["narrative"].get("action_skeletons", 0) if item["narrative"] else "—"
        for item in alive) + " |")
    lines.append("| 证据引用率 | " + " | ".join(
        "%.1f%%" % (item["narrative"].get("evidence_grounded_rate", 0) * 100) if item["narrative"] else "—"
        for item in alive) + " |")
    lines.append("| action 平均字数 | " + " | ".join(
        "%.1f" % item["narrative"].get("action_chars_mean", 0) if item["narrative"] else "—"
        for item in alive) + " |")
    lines.append("| 单条延迟 p50（s） | " + " | ".join(
        "%.1f" % item["latency"].get("p50", 0) if item["latency"] else "—"
        for item in alive) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default=os.path.join(HERE, "data", "eval_set_26.jsonl"))
    parser.add_argument("--template", default=os.path.join(HERE, "results", "baseline_template.json"))
    parser.add_argument("--lora", default=os.path.join(HERE, "results", "model_eval.json"),
                        help="微调后模型的评测结果")
    parser.add_argument("--base", default=os.path.join(HERE, "results", "model_eval_base.json"),
                        help="未微调基座的评测结果，不存在时会在表里留空")
    parser.add_argument("--out", default=os.path.join(HERE, "results", "baseline_compare.json"))
    args = parser.parse_args()

    prompts = load_prompts(args.eval_set)
    groups = [("规则结论 + 固定模板", args.template),
              ("规则结论 + 微调 3B", args.lora),
              ("规则结论 + 未微调 3B", args.base)]

    summary, tables = {}, []
    for label, path in groups:
        if not os.path.exists(path):
            print("！未找到 %s，跳过：%s" % (label, path))
            summary[label] = {"label": label, "path": None, "n": 0, "missing": True}
            continue
        summary[label] = summarize(path, prompts, label)
        print("== %s ==" % label)
        for _key, name in CHECKS:
            entry = summary[label]["rates"][name]
            print("  %-14s %2d/%2d  %.1f%%  95%%CI %.1f–%.1f" % (
                name, entry["success"], entry["n"], entry["rate"] * 100,
                entry["ci95"][0] * 100, entry["ci95"][1] * 100))
        print("  叙述层:", json.dumps(summary[label]["narrative"], ensure_ascii=False))
        print("  违规项:", json.dumps(summary[label]["violations"], ensure_ascii=False))

    tables.append(markdown([summary[label] for label, _p in groups]))
    text = "\n\n".join(tables)
    print("\n" + text)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"groups": summary, "markdown": text,
                   "note": "判定性判据由架构保证，模板基线亦满分；模型增量见叙述层代理指标。"
                           "叙述层为代理指标，不能替代人工评审。"},
                  handle, ensure_ascii=False, indent=1)
    print("\n写出", args.out)

    md = os.path.join(os.path.dirname(os.path.abspath(args.out)), "baseline_compare.md")
    with open(md, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")
    print("写出", md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
