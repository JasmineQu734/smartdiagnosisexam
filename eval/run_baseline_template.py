# -*- coding: utf-8 -*-
"""
基线 A：规则结论 + 固定模板叙述（不调用任何模型）。

对照的意义在于隔离变量
----------------------
后端在装配事实时，规则层已经把「谁缺哪几级」算完了（事实清单第 19 号
`skill_gap_summary` 与随之给出的【本次缺口清单】）。这份基线直接把这些结论
按固定句式填成六键 JSON，一个字都不生成。于是它与「规则结论 + 微调模型叙述」
之间只差一个变量：叙述由谁写。

预期结论（跑完自己带出来，不要写死）
------------------------------------
它会在契约、gaps 集合、等级、优先级、排期、数字溯源这些「判定性」判据上接近
满分——因为这些都是架构与规则给的，不是模型给的。这正是要写进论文的事实：
把六键契约合法率当作模型能力是不成立的。模型的价值只能落在叙述层，所以本脚本
同时记录三个叙述层代理指标（句干重复、证据引用、文本长度），供 compare 脚本
与模型输出对齐比较。

用法
----
    python eval/run_baseline_template.py
    python eval/run_baseline_template.py --eval-set eval/data/eval_set_26.jsonl \
        --out eval/results/baseline_template.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_model_eval as R  # noqa: E402

PLAN_GAP_DAYS = 7          # 相邻两步的间隔天数，模板固定
KIND_ROTATION = ("课程", "带教")
SEV_TO_PRIORITY = {"HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"}


def fact_number_by_tag(text: str, tag: str) -> int | None:
    """取事实清单里某个 source 标签的编号，例如 skill_gap_summary -> 19。"""
    match = re.search(r"^F(\d+)\s+\[%s\]" % tag, text, re.M)
    return int(match.group(1)) if match else None


def reach_level(value: int | None) -> str:
    return "L%d" % value if value else "合格"


def build_output(prompt: str, facts: dict) -> dict:
    """把规则结论按固定句式填成六键 JSON。这里没有任何推理，只有字符串插值。"""
    today = facts["today"] or dt.date.today()
    gap_sum_no = fact_number_by_tag(prompt, "skill_gap_summary")
    gaps = facts["gap_list"]
    reached = [name for name, info in facts["skills"].items() if info.get("state") == "已达标"]
    ref = "F%d" % gap_sum_no if gap_sum_no else "事实清单"

    # ---- summary ----
    if gaps:
        head = gaps[0]
        summary = (
            "该员工共 %d 项技能未达岗位要求。其中缺口最大的是%s，当前 %s，岗位要求 %s，差 %d 级。"
            "已达标技能%s可承担授权作业（%s）。"
            % (len(gaps), head["skill"], reach_level(head["current"]),
               reach_level(head["required"]), head["gap"],
               "、".join(reached) if reached else "暂无", ref))
    else:
        summary = "该员工各项技能均已达到岗位要求，暂无未达标技能（%s）。" % ref

    # ---- verdict ----
    if gaps:
        headline = "在职技能不足：%d 项未达标，最大缺口为%s" % (len(gaps), gaps[0]["skill"])
    else:
        headline = "能力达标：未发现未达标技能"
    reasons = []
    for item in gaps:
        reasons.append("%s 当前 %s，岗位要求 %s，未来需求 %s，差 %d 级（%s）。"
                       % (item["skill"], reach_level(item["current"]), reach_level(item["required"]),
                          reach_level(item["future"]), item["gap"], ref))
    if reached:
        reasons.append("%s 已满足岗位要求，可作为优势项承担授权作业（%s）。"
                       % ("、".join(reached), ref))
    safety_no = fact_number_by_tag(prompt, "safety_record")
    if safety_no:
        reasons.append("安全记录存在未监护情形，须在上岗前补齐授权边界（F%d）。" % safety_no)
    exam_no = fact_number_by_tag(prompt, "exam_history")
    if exam_no:
        reasons.append("存在未通过考试记录，错题须先复盘再进入实操验证（F%d）。" % exam_no)
    if len(reasons) < 3:
        reasons.append("技能雷达与岗位要求逐项比对，差距项已全部列出（%s）。" % ref)

    # ---- gaps：句干固定，只换技能名与等级 ----
    gap_rows = []
    for item in gaps:
        gap_rows.append({
            "skill": item["skill"],
            "current": item["current"],
            "required": item["required"],
            "future": item["future"],
            "severity": item["severity"],
            "priority": SEV_TO_PRIORITY.get(item["severity"], "P3"),
            "impact": "该技能当前低于岗位要求，相关作业暂不能独立承担",
            "action": "按计划完成课程与带教，达标后验证到 %s" % reach_level(item["required"]),
        })

    # ---- plan：一项差距两步，日期依次后推 ----
    plan_rows = []
    step = 0
    for index, item in enumerate(gaps):
        for offset, kind in enumerate(KIND_ROTATION):
            step += 1
            due = today + dt.timedelta(days=PLAN_GAP_DAYS * step)
            plan_rows.append({
                "step": step,
                "kind": kind,
                "title": "%s%s" % ("补强" if kind == "课程" else "带教验证", item["skill"]),
                "target_skill": item["skill"],
                "to_level": reach_level(item["required"] if offset == 1 else
                                        min((item["current"] or 1) + 1, item["required"] or 5)),
                "due_at": due.isoformat(),
                "reason": "该技能与岗位要求差 %d 级，按优先级排入本步（%s）。" % (item["gap"], ref),
            })
    if not plan_rows:
        plan_rows.append({
            "step": 1, "kind": "课程", "title": "维持性复训",
            "target_skill": reached[0] if reached else "安全规程",
            "to_level": "L3",
            "due_at": (today + dt.timedelta(days=PLAN_GAP_DAYS)).isoformat(),
            "reason": "当前无未达标技能，安排维持性复训以防能力回落（%s）。" % ref,
        })

    # ---- compound_path ----
    stage_one = gaps[:1]
    stage_two = gaps[1:]
    stages = [{
        "phase": "第一阶段",
        "focus": "补齐最大缺口",
        "skills": "、".join(item["skill"] for item in stage_one) or "维持性复训",
        "milestone": "达到岗位要求等级并通过验证",
    }]
    if stage_two:
        stages.append({
            "phase": "第二阶段",
            "focus": "补齐其余缺口",
            "skills": "、".join(item["skill"] for item in stage_two),
            "milestone": "全部未达标技能达到岗位要求",
        })

    return {
        "summary": summary,
        "confidence": 0.5,
        "verdict": {"headline": headline, "reasons": reasons},
        "gaps": gap_rows,
        "plan": plan_rows,
        "compound_path": {
            "title": "复合型能力补齐路线" if len(gaps) > 1 else "单项能力补齐路线",
            "why": "按技能雷达给出的差距与优先级顺序安排，先补最大缺口（%s）。" % ref,
            "stages": stages,
            "benefit": "在不影响在岗作业的前提下完成等级达标，并保留过程留痕",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default=os.path.join(HERE, "data", "eval_set_26.jsonl"))
    parser.add_argument("--out", default=os.path.join(HERE, "results", "baseline_template.json"))
    args = parser.parse_args()

    with open(args.eval_set, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    print("样本集 %s：%d 条" % (args.eval_set, len(rows)))

    cases = []
    for row in rows:
        facts = R.parse_prompt(row["input"])
        payload = build_output(row["input"], facts)
        text = json.dumps(payload, ensure_ascii=False)
        result = R.check(text, facts)
        result.update({"group": row["group"], "index": row["index"], "latency_s": 0.0,
                       "prompt_chars": len(row["input"]), "output_chars": len(text),
                       "raw": text})
        cases.append(result)
        flag = "OK " if result.get("contract_ok") and result.get("gaps_ok") else "NG "
        print("  %s%s[%d] contract=%s gaps=%s levels=%s plan=%s numbers=%s safety=%s %s"
              % (flag, row["group"], row["index"], result.get("contract_ok"),
                 result.get("gaps_ok"), result.get("levels_ok"), result.get("plan_ok"),
                 result.get("numbers_ok"), result.get("safety_ok"), result.get("violations")))

    def rate(rows_: list[dict], key: str) -> float:
        return round(sum(1 for item in rows_ if item.get(key)) / len(rows_), 4) if rows_ else 0.0

    summary = {}
    for group in ("heldout", "verbatim"):
        subset = [item for item in cases if item["group"] == group]
        if not subset:
            continue
        summary[group] = {
            "n": len(subset),
            **{name: rate(subset, name) for name in
               ("json_ok", "contract_ok", "gaps_ok", "levels_ok", "priority_ok",
                "plan_ok", "cite_ok", "numbers_ok", "safety_ok")},
            "all_pass_rate": round(sum(1 for item in subset if all(
                item.get(key) for key in ("json_ok", "contract_ok", "gaps_ok", "levels_ok",
                                          "priority_ok", "plan_ok"))) / len(subset), 4),
            "violations": {tag: sum(1 for item in subset if tag in item.get("violations", []))
                           for tag in sorted({tag for item in subset
                                              for tag in item.get("violations", [])})},
            "narrative_mean": {
                name: round(statistics.fmean([item["narrative"][name] for item in subset]), 4)
                for name in ("action_skeletons", "impact_skeletons",
                             "evidence_grounded_rate", "action_chars_mean", "summary_chars")
            },
        }
        print("== %s ==" % group, json.dumps(summary[group], ensure_ascii=False))

    summary["config"] = {"baseline": "rule_conclusion + fixed_template", "model": None,
                         "eval_set": os.path.basename(args.eval_set), "n": len(cases)}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"summary": summary, "cases": cases}, handle, ensure_ascii=False, indent=1)
    print("写出", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
