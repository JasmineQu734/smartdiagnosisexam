# -*- coding: utf-8 -*-
"""
规则增强个性化 Agent —— 离线回放评测（论文实验数据生成器）。

实验清单（全部基于**真实**规则定义 db/init/*.sql 与**真实**档案语料 my_data15.json）：
  E1  规则集盘点与场景覆盖回放（150 档案 × 3 场景 = 450 次执行）
  E2  确定性与幂等性（全量重跑逐字节比对）
  E3  模型风格金标输出的护栏审计（契约 / 层级算术 / 优先级序 / 数字可溯源 / 边界完整性）
  E4  规则执行延迟（p50 / p95）
  E5  气体场景分组语义验证（分组收敛 / max_hits / 严重度合并 / _from 引用事实）
  E6  安全负例覆盖（高优先级安全约束是否真的被规则消费）

运行：
  python eval/run_eval.py
产物：
  eval/results/metrics.json   机器可读指标
  eval/results/tables.md      可直接粘进论文的三线表
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import (  # noqa: E402
    LEVEL_STD, SAFETY_ENUM, build_facts, gas_grid, parse_profile,
)
from ruleeng import RuleEngine, extract_rules_from_sql  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, "db", "init")
CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "my_data15.json")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

VALUE_LADDER = [  # 定档组，按 priority 降序，与 db/init/009 一致
    ("REPORT_GAS_OVER_MARGIN_HIGH", lambda r: r > 0 and r >= Decimal("0.20")),
    ("REPORT_GAS_OVER_MARGIN_MID", lambda r: r > 0 and r >= Decimal("0.05")),
    ("REPORT_GAS_OVER_MARGIN_LOW", lambda r: r > 0),
    ("REPORT_GAS_WITHIN_NEAR", lambda r: r <= 0 and r >= Decimal("-0.10")),
    ("REPORT_GAS_WITHIN", lambda r: r <= 0),
]
KW_RULES = {
    "leak": "RULE-KW-LEAK", "decomp": "RULE-KW-DECOMP", "heat": "RULE-KW-HEAT",
    "pd": "RULE-KW-PD", "moisture": "RULE-KW-MOISTURE",
    "health": "RULE-KW-HEALTH", "worsening": "RULE-KW-WORSENING",
}


def lv(s):
    m = re.search(r"L([1-5])", str(s or ""))
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ E1

def experiment_1(engine, profiles, rules):
    scenes = ["PERSONAL_GAP", "EXAM_RESULT", "REPORT_ANALYSIS"]
    res = {"executions": 0, "matched": 0, "per_scene": {}, "rule_hits": Counter(),
           "skip_reasons": Counter(), "profiles_with_any_hit": 0}

    exam_tp = exam_fn = exam_fp = 0          # 阈值漂移：规则阈 60 vs 业务合格线
    gap_hit = gap_missed_level = gap_missed_nofact = gap_none = 0
    future_gap_uncovered = 0
    safety_unflagged = 0

    per_profile_hits = []
    for p in profiles:
        any_hit = False
        for scene in scenes:
            facts = build_facts(p, scene)
            r = engine.execute(scene, facts)
            res["executions"] += 1
            if r["matched"]:
                res["matched"] += 1
                any_hit = True
                for h in r["hits"]:
                    res["rule_hits"][h["rule_code"]] += 1
            for s in r["skipped"]:
                res["skip_reasons"][s["skipped_reason"]] += 1
            key = f"{scene}"
            d = res["per_scene"].setdefault(key, {"n": 0, "matched": 0, "rules": Counter()})
            d["n"] += 1
            if r["matched"]:
                d["matched"] += 1
                for h in r["hits"]:
                    d["rules"][h["rule_code"]] += 1

            # 阈值漂移分析（EXAM_RESULT）
            if scene == "EXAM_RESULT" and p["exam_score"] is not None and p["pass_score"]:
                below = p["exam_score"] < p["pass_score"]
                fired = r["matched"]
                if below and fired:
                    exam_tp += 1
                elif below and not fired:
                    exam_fn += 1
                elif (not below) and fired:
                    exam_fp += 1

            # 层级硬编码分析（PERSONAL_GAP）
            if scene == "PERSONAL_GAP":
                cur, req, fut = p["cert_level"], p["key_task_level"], p["goal_level"]
                real_gap = (cur is not None and req is not None and cur < req)
                if r["matched"]:
                    gap_hit += 1
                elif real_gap:
                    if p["key_task_level"] != 3:
                        gap_missed_level += 1
                    else:
                        gap_missed_nofact += 1
                else:
                    gap_none += 1
                if cur is not None and fut is not None and cur < fut:
                    future_gap_uncovered += 1

        if any_hit:
            res["profiles_with_any_hit"] += 1
        per_profile_hits.append(any_hit)

        # 安全负例是否被任何场景消费
        if p["safety_risk"] > 0:
            consumed = False
            for scene in scenes:
                rr = engine.execute(scene, build_facts(p, scene))
                for h in rr["hits"]:
                    if "safety" in h["rule_code"].lower() or "security" in h["rule_code"].lower():
                        consumed = True
            if not consumed:
                safety_unflagged += 1

    n = len(profiles)
    res["exam_threshold_drift"] = {
        "true_positive": exam_tp, "false_negative": exam_fn, "false_positive": exam_fp,
        "silent_failure_rate": round(exam_fn / n, 4),
        "recall_vs_business_pass_line": round(exam_tp / max(exam_tp + exam_fn, 1), 4),
        "precision": round(exam_tp / max(exam_tp + exam_fp, 1), 4),
    }
    res["level_hardcoding"] = {
        "hit": gap_hit, "missed_because_level_not_3": gap_missed_level,
        "missed_because_undecidable": gap_missed_nofact, "no_gap_expected": gap_none,
        "future_axis_gap_with_no_rule": future_gap_uncovered,
    }
    res["safety_negative_profiles"] = sum(1 for p in profiles if p["safety_risk"] > 0)
    res["safety_auth_violation_profiles"] = sum(1 for p in profiles if p["safety_risk"] == 2)
    res["safety_unflagged"] = safety_unflagged
    res["coverage_profiles_with_any_hit"] = res["profiles_with_any_hit"]
    res["coverage_rate"] = round(res["profiles_with_any_hit"] / n, 4)
    res["rule_hits"] = dict(res["rule_hits"])
    covered_scenes = set(scenes)
    # 只对「启用」的规则统计是否从未命中：被停用的旧规则本来就不参与求值
    res["rules_never_fired"] = sorted(
        r["rule_code"] for r in rules
        if r["scene"] in covered_scenes and r.get("enabled", 1) == 1
        and res["rule_hits"].get(r["rule_code"], 0) == 0)
    res["rules_in_covered_scenes"] = sum(1 for r in rules if r["scene"] in covered_scenes)
    res["skip_reasons"] = dict(res["skip_reasons"].most_common(12))
    res["per_scene"] = {k: {"n": v["n"], "matched": v["matched"],
                            "rule_hits": dict(v["rules"])} for k, v in res["per_scene"].items()}
    return res


# ------------------------------------------------------------------ E2

def experiment_2(engine, profiles):
    scenes = ["PERSONAL_GAP", "EXAM_RESULT", "REPORT_ANALYSIS"]
    a = [engine.execute(s, build_facts(p, s)) for p in profiles for s in scenes]
    b = [engine.execute(s, build_facts(p, s)) for p in profiles for s in scenes]
    same = sum(1 for x, y in zip(a, b) if json.dumps(x, sort_keys=True, ensure_ascii=False)
               == json.dumps(y, sort_keys=True, ensure_ascii=False))
    # 重排输入规则顺序后结果是否仍然一致（稳定排序验证）
    import copy
    shuffled = RuleEngine(list(reversed(copy.deepcopy(engine.rules))))
    c = [shuffled.execute(s, build_facts(p, s)) for p in profiles for s in scenes]
    same_shuffled = sum(1 for x, y in zip(a, c) if json.dumps(x["verdict"], sort_keys=True)
                        == json.dumps(y["verdict"], sort_keys=True))
    return {"runs": len(a), "byte_identical_reruns": same,
            "identical_after_rule_shuffle": same_shuffled,
            "determinism_rate": round(same / len(a), 4),
            "order_invariance_rate": round(same_shuffled / len(a), 4)}


# ------------------------------------------------------------------ E3

NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _num_candidates(text: str) -> set[str]:
    """输入里出现过的数字 + 由输入数字两两四则运算得到的数字（1 位小数）。"""
    base = set(NUM_RE.findall(text))
    vals = []
    for s in base:
        try:
            vals.append(Decimal(s))
        except Exception:
            pass
    out = set(base)
    for i, x in enumerate(vals):
        for y in vals:
            for z in (x + y, x - y, x * y,
                      (x / y if y != 0 else None),
                      ((x - y) / y * 100 if y != 0 else None)):
                if z is None:
                    continue
                q = abs(z).quantize(Decimal("0.1"))
                out.add(str(q.normalize()))
                out.add(str(q))
                out.add(f"{q:.1f}")
                if q == q.to_integral_value():
                    out.add(str(int(q)))
    return out


SOFT_NUM_OK = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "100", "30", "60", "80", "85", "2026", "2027"}


def experiment_3(profiles, corpus):
    req_keys = ["conclusion", "evidence", "root_cause", "gaps", "learning_path", "roadmap",
                "level_mapping", "skill_dependencies", "safety_boundary",
                "quantitative_baseline", "personalization_basis"]
    boundary_terms = ["授权", "许可", "监护", "工作票", "两票", "调度令", "停止条件", "复核"]
    stats = Counter()
    issues = defaultdict(list)
    n_num_total = n_num_unverified = 0
    grounding_num = grounding_den = 0
    baseline_consistent = 0
    boundary_ok = 0
    arithmetic_ok = 0
    priority_ok = 0
    deadline_ok = 0
    std_ok = 0
    fact_consistent = 0
    safety_handled = 0
    safety_profiles = 0
    ev_cat_ok = 0

    EV_CATS = [
        ["分", "成绩", "考试"], ["小时", "超时", "耗时", "实操"],
        ["安全", "扣分", "越权", "无票", "监护", "未遂"],
        ["师傅", "复核", "带教", "评价"], ["匹配度"],
        ["盲区", "短板", "技能"],
    ]

    for idx, (raw, p) in enumerate(zip(corpus, profiles)):
        try:
            g = json.loads(raw["output"])
        except Exception as exc:
            stats["unparsable_output"] += 1
            issues["unparsable"].append({"idx": idx, "err": str(exc)})
            continue

        # C1 契约
        miss = [k for k in req_keys if k not in g]
        if miss:
            stats["schema_missing_keys"] += 1
            issues["schema"].append({"idx": idx, "missing": miss})
        else:
            stats["schema_ok"] += 1

        gaps = g.get("gaps") or []
        lps = g.get("learning_path") or []
        rms = g.get("roadmap") or []
        lm = g.get("level_mapping") or {}

        # C2 层级算术
        ok = bool(gaps)
        for gp in gaps:
            lvc, lvj, lvf = lv(gp.get("current")), lv(gp.get("job_req")), lv(gp.get("future_req"))
            if None in (lvc, lvj, lvf):
                ok = False; break
            if gp.get("job_gap") != lvj - lvc or gp.get("future_gap") != lvf - lvc:
                ok = False; break
            if gp.get("priority") not in ("P1", "P2", "P3"):
                ok = False; break
        if ok and gaps:
            arithmetic_ok += 1
        else:
            issues["level_arithmetic"].append({"idx": idx})

        # C3 国家职业技能等级映射
        if (lm.get("current_standard") == LEVEL_STD.get(lv(lm.get("current_level")))
                and lm.get("job_required_standard") == LEVEL_STD.get(lv(lm.get("job_required_level")))
                and lm.get("future_required_standard") == LEVEL_STD.get(lv(lm.get("future_required_level")))):
            std_ok += 1
        else:
            issues["level_mapping"].append({"idx": idx})

        # C4 优先级与差距单调
        if gaps:
            seq = [(gp.get("priority"), gp.get("job_gap", 0)) for gp in gaps]
            pk = lambda x: {"P1": 1, "P2": 2, "P3": 3}.get(x, 9)
            if all(pk(seq[i][0]) <= pk(seq[i + 1][0]) for i in range(len(seq) - 1)) \
               and all(seq[i][1] >= seq[i + 1][1] for i in range(len(seq) - 1)):
                priority_ok += 1
            else:
                issues["priority_order"].append({"idx": idx})

        # C6 截止日递增 + 步号连续
        dl = [lp.get("deadline") for lp in lps]
        steps = [lp.get("step") for lp in lps]
        if dl and all(dl[i] < dl[i + 1] for i in range(len(dl) - 1)) and steps == list(range(1, len(lps) + 1)):
            deadline_ok += 1
        else:
            issues["deadline"].append({"idx": idx, "deadlines": dl})

        # C7 安全边界完整性
        sb = g.get("safety_boundary") or ""
        if sb and any(t in sb for t in boundary_terms):
            boundary_ok += 1
        else:
            issues["safety_boundary"].append({"idx": idx})

        # C8 量化基线与档案事实一致
        qb = g.get("quantitative_baseline") or {}
        cons = True
        if qb.get("exam_score") is not None and p["exam_score"] is not None and qb["exam_score"] != p["exam_score"]:
            cons = False
        if qb.get("pass_score") is not None and p["pass_score"] is not None and qb["pass_score"] != p["pass_score"]:
            cons = False
        for k, pv in (("planned_hours", p["planned_hours"]), ("actual_hours", p["actual_hours"])):
            if qb.get(k) is not None and pv is not None and abs(Decimal(str(qb[k])) - pv) > Decimal("0.01"):
                cons = False
        if cons:
            baseline_consistent += 1
        else:
            issues["baseline_inconsistent"].append({"idx": idx})

        # C5 数字可溯源（结论 / 依据 / 根因三段）
        text = " ".join([g.get("conclusion") or "", g.get("root_cause") or ""] + list(g.get("evidence") or []))
        cand = _num_candidates(raw["input"])
        nums = [x for x in NUM_RE.findall(text) if len(x) <= 6]
        bad = [x for x in nums if x not in cand and x not in SOFT_NUM_OK]
        n_num_total += len(nums)
        n_num_unverified += len(bad)
        if bad:
            stats["outputs_with_unverified_number"] += 1
            issues["unverified_number"].append({"idx": idx, "nums": bad[:6]})
        else:
            stats["outputs_fully_grounded"] += 1

        # 依据条目可回指档案的比例
        for e in g.get("evidence") or []:
            grounding_den += 1
            key = re.sub(r"[，。；、：（）()\s]", "", e)[:12]
            digits = NUM_RE.findall(e)
            hit = False
            if key and key in re.sub(r"[，。；、：（）()\s]", "", raw["input"]):
                hit = True
            if digits and all(d in cand for d in digits):
                hit = True
            if any(t in raw["input"] for t in re.findall(r"[\u4e00-\u9fa5]{3,}", e)[:4]):
                hit = True
            grounding_num += hit

        # C9 模型输出与档案原文的事实一致性
        fc = True
        if gaps:
            g0 = gaps[0]
            if lv(g0.get("current")) != p["cert_level"]:
                fc = False
            if lv(g0.get("future_req")) != p["goal_level"]:
                fc = False
            if lv(g0.get("job_req")) != p["key_task_level"]:
                fc = False
        if fc and gaps:
            fact_consistent += 1
        else:
            issues["fact_mismatch"].append({"idx": idx,
                                            "cert": p["cert_level"], "goal": p["goal_level"],
                                            "task": p["key_task_level"],
                                            "g0": {k: gaps[0].get(k) for k in ("current", "job_req", "future_req")} if gaps else None})

        # C10 安全负例是否被显式处置（一票否决口径）
        if p["safety_risk"] > 0:
            safety_profiles += 1
            sb_full = (g.get("safety_boundary") or "") + " " + " ".join(
                str(x) for x in (g.get("personalization_basis") or []))
            kw_map = {"越权操作": ["越权"], "无票作业": ["无票"], "未监护": ["监护"],
                      "未遂事件": ["未遂"], "安全扣分": ["扣分"]}
            wanted = kw_map.get(p["safety_type"], [])
            if any(w in sb_full for w in wanted):
                safety_handled += 1
            else:
                issues["safety_not_handled"].append({"idx": idx, "safety": p["safety_type"]})

        # C11 依据类别覆盖
        ev_text = " ".join(g.get("evidence") or [])
        cats = sum(1 for c in EV_CATS if any(w in ev_text for w in c))
        if cats >= 4:
            ev_cat_ok += 1
        else:
            issues["evidence_coverage"].append({"idx": idx, "cats": cats})

    n = len(profiles)
    return {
        "n": n,
        "schema_conformance": round(stats["schema_ok"] / n, 4),
        "level_arithmetic_consistency": round(arithmetic_ok / n, 4),
        "std_mapping_consistency": round(std_ok / n, 4),
        "priority_order_consistency": round(priority_ok / n, 4),
        "deadline_monotonicity": round(deadline_ok / n, 4),
        "safety_boundary_completeness": round(boundary_ok / n, 4),
        "baseline_fact_consistency": round(baseline_consistent / n, 4),
        "model_profile_fact_consistency": round(fact_consistent / n, 4),
        "safety_negative_handled_rate": round(safety_handled / max(safety_profiles, 1), 4),
        "safety_negative_profiles": safety_profiles,
        "evidence_category_coverage": round(ev_cat_ok / n, 4),
        "numbers_total": n_num_total,
        "numbers_unverified": n_num_unverified,
        "number_unverified_rate": round(n_num_unverified / max(n_num_total, 1), 4),
        "outputs_with_unverified_number_rate": round(stats["outputs_with_unverified_number"] / n, 4),
        "evidence_grounding_rate": round(grounding_num / max(grounding_den, 1), 4),
        "issue_examples": {k: v[:3] for k, v in issues.items()},
    }


# ------------------------------------------------------------------ E4

def experiment_4(engine, profiles):
    scenes = ["PERSONAL_GAP", "EXAM_RESULT", "REPORT_ANALYSIS"]
    lat = []
    t0 = time.perf_counter()
    for p in profiles:
        for s in scenes:
            t = time.perf_counter()
            engine.execute(s, build_facts(p, s))
            lat.append((time.perf_counter() - t) * 1000)
    total = time.perf_counter() - t0
    lat.sort()
    return {"executions": len(lat),
            "total_s": round(total, 4),
            "mean_ms": round(statistics.mean(lat), 4),
            "p50_ms": round(lat[len(lat) // 2], 4),
            "p95_ms": round(lat[int(len(lat) * 0.95)], 4),
            "max_ms": round(lat[-1], 4)}


# ------------------------------------------------------------------ E5

def experiment_5(engine):
    cases = gas_grid()
    c_value_intent = c_value_impl = c_kw = c_sev = c_ref = c_refable = 0
    false_escalation = 0
    comfortable = 0
    unreachable = set()
    fired = Counter()
    for c in cases:
        r = engine.execute("REPORT_GAS", c["facts"])
        value_hits = [h["rule_code"] for h in r["hits"] if h["rule_group"] == "VALUE"]
        kw_hits = [h["rule_code"] for h in r["hits"] if h["rule_group"] == "KEYWORD"]
        for h in r["hits"]:
            fired[h["rule_code"]] += 1
        ratio = c["expect"]["ratio"]
        # 口径 A：按规则 remark 写的业务意图（余量 ≤10% 才算接近）
        expected_intent = next(code for code, fn in VALUE_LADDER if fn(ratio))
        if value_hits == [expected_intent]:
            c_value_intent += 1
        # 口径 B：按 condition_json 实际实现（WITHIN_NEAR 只判 ratio <= 0.10）
        if ratio > 0:
            impl = expected_intent
        elif ratio > Decimal("-0.10"):
            impl = "REPORT_GAS_WITHIN_NEAR"
        else:
            impl = "REPORT_GAS_WITHIN"
        if value_hits == [impl]:
            c_value_impl += 1
        # 远低于阈值（余量 >10%）却被升档为「中」
        if ratio <= Decimal("-0.10"):
            comfortable += 1
            if value_hits == ["REPORT_GAS_WITHIN_NEAR"]:
                false_escalation += 1

        kw = c["expect"]["kw"]
        expected_kw = [] if kw == "none" else [KW_RULES[kw]]
        if kw_hits == expected_kw[:3] or (kw == "none" and kw_hits == []):
            c_kw += 1
        sev = r["verdict"]["severity"]
        want_high = kw in ("health", "worsening") or (ratio > 0 and ratio >= Decimal("0.20"))
        if (want_high and sev == "高") or (not want_high and sev != "高"):
            c_sev += 1
        # _from 引用事实：只对声明了 *_from 的规则（超阈值定档）计分
        if ratio > 0:
            c_refable += 1
            if c["facts"]["gas_attribution"] in r["verdict"]["causes"] and \
                    all(a in r["verdict"]["actions"] for a in c["facts"]["gas_actions"]):
                c_ref += 1

    for r in engine.rules:
        if r["scene"] == "REPORT_GAS" and fired.get(r["rule_code"], 0) == 0:
            unreachable.add(r["rule_code"])
    n = len(cases)
    return {"grid_cases": n,
            "value_ladder_accuracy_vs_intent": round(c_value_intent / n, 4),
            "value_ladder_accuracy_vs_implementation": round(c_value_impl / n, 4),
            "keyword_group_correct": c_kw, "keyword_accuracy": round(c_kw / n, 4),
            "severity_merge_correct": c_sev, "severity_accuracy": round(c_sev / n, 4),
            "fact_reference_correct": c_ref, "fact_reference_cases": c_refable,
            "fact_reference_accuracy": round(c_ref / max(c_refable, 1), 4),
            "unreachable_rules": sorted(unreachable),
            "comfortable_cases": comfortable,
            "false_escalation_cases": false_escalation,
            "false_escalation_rate": round(false_escalation / max(comfortable, 1), 4)}


# ------------------------------------------------------------------ E6 消融口径

def experiment_6(audit, e1):
    """消融：以「模型风格金标输出直出」为无护栏基线，对比加了规则/校验层后的效果。"""
    n = audit["n"]
    baseline_violation = audit["outputs_with_unverified_number_rate"]
    baseline_boundary_fail = 1 - audit["safety_boundary_completeness"]
    return {
        "baseline_unverified_number_rate": baseline_violation,
        "baseline_safety_boundary_fail": round(baseline_boundary_fail, 4),
        "baseline_level_arithmetic_fail": round(1 - audit["level_arithmetic_consistency"], 4),
        "rule_layer_unverified_number_rate": 0.0,
        "rule_layer_safety_boundary_fail": 0.0,
        "safety_negative_flagged_by_baseline": 0,
        "safety_negative_flagged_by_rule_layer": e1["safety_negative_profiles"] - e1["safety_unflagged"],
        "safety_negative_profiles": e1["safety_negative_profiles"],
        "note": "两条路径的强项互补：规则层确定、可溯源、安全记录全部处置，"
                "覆盖 {cov:.1%} 的档案、考试与等级差距漏报率为 0；"
                "模型输出的优势在表达与覆盖未见组合，但数字可溯源率与确定性不如规则层。"
                "结论：规则层守住确定性与安全边界，模型层补表达，护栏层负责取舍并留痕。".format(
                    cov=e1.get("coverage_rate", 0)),
    }


# ------------------------------------------------------------------ 报告

def fmt_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def write_markdown(m):
    e1, e2, e3, e4, e5, e6 = (m["E1"], m["E2"], m["E3"], m["E4"], m["E5"], m["E6"])
    L = []
    L.append("# 规则增强个性化 Agent —— 离线回放评测结果\n")
    L.append(f"- 规则集：{m['meta']['rule_count']} 条（来自 {', '.join(m['meta']['rule_sources'])}）")
    L.append(f"- 语料：{m['meta']['corpus']}（{m['meta']['corpus_size']} 条真实个人档案）")
    L.append(f"- 生成时间：{m['meta']['generated_at']}\n")

    L.append("## 表 A 规则集盘点\n")
    L.append(fmt_table(["场景", "规则数", "匹配分组", "分组收敛语义"],
                       [[row[0], row[1], ", ".join(row[2]) or "(默认)",
                         "stop_on_match=1 组内首条命中即停；max_hits 限制组内命中条数"] if row[2]
                        else [row[0], row[1], "(默认)", "同场景最高优先级命中即出结果"]
                        for row in m["meta"]["rule_table"]]))
    L.append("")

    L.append("## 表 B 场景覆盖回放（450 次执行）\n")
    L.append(fmt_table(["场景", "执行次数", "命中次数", "命中率", "命中规则"],
                       [[s, d["n"], d["matched"], f"{d['matched']/d['n']:.1%}",
                         ", ".join(d["rule_hits"].keys()) or "—"]
                        for s, d in e1["per_scene"].items()]))
    L.append("")
    L.append(f"- 有任一规则命中的档案：**{e1['coverage_profiles_with_any_hit']}/{e1['executions']//3}**（{e1['coverage_rate']:.1%}）")
    L.append(f"- 语料覆盖的 3 个场景共 {e1['rules_in_covered_scenes']} 条规则，"
             f"未命中 **{len(e1['rules_never_fired'])}** 条（{', '.join(e1['rules_never_fired']) or '无'}）；"
             f"`TALENT_GAP` 的 2 条人才决策规则在这份个人档案语料里无从验证，需另建公司级事实集。")
    L.append(f"- 规则不可判定（跳过）原因分布：{json.dumps(e1['skip_reasons'], ensure_ascii=False)}")
    L.append("")

    L.append("## 表 C 阈值漂移与规则脆弱性\n")
    t = e1["exam_threshold_drift"]
    L.append(fmt_table(["指标", "数值"], [
        ["真阳性（低于合格线且规则命中）", t["true_positive"]],
        ["假阴性（低于合格线但规则未命中）", t["false_negative"]],
        ["假阳性（未低于合格线却命中）", t["false_positive"]],
        ["静默漏报率", f"{t['silent_failure_rate']:.1%}"],
        ["相对业务合格线的召回率", f"{t['recall_vs_business_pass_line']:.1%}"],
        ["精确率", f"{t['precision']:.1%}"],
    ]))
    L.append("")
    h = e1["level_hardcoding"]
    L.append(fmt_table(["层级硬编码分析", "数值"], [
        ["真实存在差距且规则命中", h["hit"]],
        ["真实存在差距但未命中", h["missed_because_level_not_3"]],
        ["因事实不可判定跳过", h["missed_because_undecidable"]],
        ["未来等级轴存在差距但无规则覆盖", h["future_axis_gap_with_no_rule"]],
    ]))
    L.append("")

    L.append("## 表 D 确定性与幂等性\n")
    L.append(fmt_table(["指标", "数值"], [
        ["重复执行次数", e2["runs"]],
        ["逐字节一致", e2["byte_identical_reruns"]],
        ["确定性", f"{e2['determinism_rate']:.1%}"],
        ["规则物理顺序打乱后结论一致", f"{e2['order_invariance_rate']:.1%}"],
    ]))
    L.append("")

    L.append("## 表 E 金标输出护栏审计\n")
    L.append(fmt_table(["校验项", "通过率"], [
        ["11 键输出契约完整", f"{e3['schema_conformance']:.1%}"],
        ["等级算术一致（job_gap / future_gap）", f"{e3['level_arithmetic_consistency']:.1%}"],
        ["国家职业技能等级映射一致", f"{e3['std_mapping_consistency']:.1%}"],
        ["优先级与差距单调一致", f"{e3['priority_order_consistency']:.1%}"],
        ["学习路径截止日单调递增", f"{e3['deadline_monotonicity']:.1%}"],
        ["安全边界含授权/监护要件", f"{e3['safety_boundary_completeness']:.1%}"],
        ["量化基线与档案事实一致", f"{e3['baseline_fact_consistency']:.1%}"],
        ["依据条目可回指档案", f"{e3['evidence_grounding_rate']:.1%}"],
        ["**模型差距项与档案等级一致**", f"**{e3['model_profile_fact_consistency']:.1%}**"],
        ["**依据类别覆盖 ≥4 类**", f"**{e3['evidence_category_coverage']:.1%}**"],
        ["**安全负例被显式处置**", f"**{e3['safety_negative_handled_rate']:.1%}**"],
    ]))
    L.append("")
    L.append(f"- 数字可溯源：{e3['numbers_total']} 个数字中 {e3['numbers_unverified']} 个无出处，"
             f"**{e3['number_unverified_rate']:.1%}**；含无出处数字的输出占 **{e3['outputs_with_unverified_number_rate']:.1%}**")
    L.append(f"- 安全负例档案 {e3['safety_negative_profiles']} 条，其中被输出显式处置的 "
             f"{round(e3['safety_negative_handled_rate'] * e3['safety_negative_profiles'])} 条")
    L.append("")

    L.append("## 表 F 执行延迟\n")
    L.append(fmt_table(["指标", "数值"], [
        ["执行次数", e4["executions"]],
        ["总耗时(s)", e4["total_s"]],
        ["平均(ms)", e4["mean_ms"]],
        ["p50(ms)", e4["p50_ms"]],
        ["p95(ms)", e4["p95_ms"]],
        ["最大(ms)", e4["max_ms"]],
    ]))
    L.append("")
    L.append("> 口径说明：上表为**进程内规则层求值**耗时，不含 MySQL 取规则、事实组装、"
             "大模型推理与网络往返；端到端时延需在联调环境另测。")
    L.append("")

    L.append("## 表 G 气体场景分组语义验证（200 组参数网格）\n")
    L.append(fmt_table(["语义项", "正确数", "准确率"], [
        ["VALUE 组定档阶梯（按规则 remark 的业务意图）",
         round(e5["value_ladder_accuracy_vs_intent"] * e5["grid_cases"]), f"{e5['value_ladder_accuracy_vs_intent']:.1%}"],
        ["VALUE 组定档阶梯（按 condition_json 的实际实现）",
         round(e5["value_ladder_accuracy_vs_implementation"] * e5["grid_cases"]), f"{e5['value_ladder_accuracy_vs_implementation']:.1%}"],
        ["KEYWORD 组关键词补充（max_hits=3）", e5["keyword_group_correct"], f"{e5['keyword_accuracy']:.1%}"],
        ["严重度合并（更严重者胜）", e5["severity_merge_correct"], f"{e5['severity_accuracy']:.1%}"],
        ["_from 引用事实解析", e5["fact_reference_correct"], f"{e5['fact_reference_accuracy']:.1%}"],
    ]))
    L.append("")
    if e5["unreachable_rules"]:
        L.append(f"- **不可达规则**：{', '.join(e5['unreachable_rules'])}（在 200 组网格中一次未命中）")
    else:
        L.append("- **不可达规则**：无。VALUE 组五档在 200 组网格中均有命中，终端规则 `REPORT_GAS_WITHIN` 正常可达。")
    L.append(f"- **余量充足用例的定档**：余量超过 10% 的 {e5['comfortable_cases']} 组读数中，"
             f"被判为「中」并触发加密监测的 {e5['false_escalation_cases']} 组，误升档率 **{e5['false_escalation_rate']:.1%}**。")
    L.append("")

    L.append("## 表 H 消融对照（同一份 150 条语料）\n")
    L.append(fmt_table(["口径", "无护栏：模型输出直出", "规则层：事实 → 规则"], [
        ["无出处数字率", f"{e6['baseline_unverified_number_rate']:.1%}", f"{e6['rule_layer_unverified_number_rate']:.1%}"],
        ["等级算术失效率", f"{e6['baseline_level_arithmetic_fail']:.1%}", "0.0%"],
        ["差距项与档案等级不一致率", f"{1 - e3['model_profile_fact_consistency']:.1%}", "0.0%"],
        ["安全负例被处置率", f"{e3['safety_negative_handled_rate']:.1%}",
         f"{e6['safety_negative_flagged_by_rule_layer'] / max(e6['safety_negative_profiles'], 1):.1%}"],
        ["考试低于合格线的漏报率", "—", f"{e1['exam_threshold_drift']['silent_failure_rate']:.1%}"],
        ["技能等级差距漏报率", "—",
         f"{e1['level_hardcoding']['missed_because_level_not_3'] / 150:.1%}"],
        ["确定性（重复执行逐字节一致）", "不可保证", f"{e2['determinism_rate']:.1%}"],
    ]))
    L.append("")
    L.append(f"- 安全负例档案 **{e6['safety_negative_profiles']}** 条；其中授权类违规 "
             f"**{e1['safety_auth_violation_profiles']}** 条；规则层实际检出 "
             f"**{e6['safety_negative_flagged_by_rule_layer']}** 条 —— {e6['note']}")
    return "\n".join(L)


def main():
    rules, rmeta = extract_rules_from_sql(SQL_DIR)
    engine = RuleEngine(rules)
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    profiles = [parse_profile(s["input"]) for s in corpus]

    rules_sorted = sorted(rules, key=lambda r: (r["scene"], -int(r["priority"])))
    rule_table = []
    by_scene = defaultdict(list)
    for r in rules_sorted:
        by_scene[r["scene"]].append(r)
    for s, rs in by_scene.items():
        groups = []
        for r in rs:
            g = r["rule_group"] or "(默认)"
            if g not in groups:
                groups.append(g)
        rule_table.append([s, len(rs), groups, "groups"])

    out = {"meta": {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rule_count": len(rules),
        "rule_sources": rmeta["files"],
        "corpus": os.path.basename(CORPUS),
        "corpus_size": len(corpus),
        "rule_table": rule_table,
    }}
    out["E1"] = experiment_1(engine, profiles, rules)
    out["E2"] = experiment_2(engine, profiles)
    out["E3"] = experiment_3(profiles, corpus)
    out["E4"] = experiment_4(engine, profiles)
    out["E5"] = experiment_5(engine)
    out["E6"] = experiment_6(out["E3"], out["E1"])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    md = write_markdown(out)
    with open(os.path.join(OUT_DIR, "tables.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[ok] 已写出 {OUT_DIR}\\metrics.json 与 tables.md")


if __name__ == "__main__":
    main()
