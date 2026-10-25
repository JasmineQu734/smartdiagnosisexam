# -*- coding: utf-8 -*-
"""
构建公司运行诊断 Agent 的 SFT 语料 my_data17.json（默认 1000 条，UTF-8 无 BOM）。

与 build_my_data16.py 同一套硬规矩，但按用户要求**不混用 my_data16**，独立成集：
1) 提示词逐字复刻后端 ExecDiagnosisService.systemPrompt()（11 条）与 userPrompt()（【事实清单】+【输出模板】），
   换行用 CRLF（后端 DiagnosisPipeline.line() 是 System.lineSeparator()）。
2) 事实清单与 ExecDiagnosisService.facts() 的 8 组来源与顺序完全一致：
   position 关键岗位 → employee_skill 逐技能 → exam_history（合计 + 最多 5 条未通过）→ task_report →
   task 缺报 → certificate → safety_record → cost_record 逐类型（按 cost_type 码点序，同 MySQL ORDER BY）。
3) 输出为 DiagnosisContract.validateExec 的 6 键契约
   （summary/confidence/verdict/findings/actions/cost_summary），并满足两条系统级要求：
   - verdict.evidence 同时引用「岗位编制缺口」与「在岗技能未达标」两类事实（系统提示词第 7 条）；
   - 一票否决时安全必须最高优先级（系统提示词第 6 条）。
4) 叙述字段（summary / verdict / findings）里的每个数字都必须能通过后端
   DiagnosisContract.numbersOf + addDerived 的对账（本脚本内置 Python 镜像自查，逐条断言）；
   数字一律取事实原文数字，或 X*100/Y 四舍五入的整数百分比（同 Java Math.round 半分位向上）。
5) 真实性锚点：人数、金额、比例的数量级取自 tools/dataset/exec_benchmarks.json 的公开来源
   （国家统计局 2024 行业工资、财税〔2018〕51号 8% 培训经费上限、中电联人才报告、
   国网江苏外包人工成本 11.7 万/人年、四川电力外包费用 5% 核定口径等）。

产物
----
alpaca + system 列：{"system": <systemPrompt>, "instruction": "", "input": <userPrompt>, "output": <JSON>}
另产出：
  - tmp/agent/verify17.json          供 VerifyExecDataset.java 用真实 DiagnosisContract 复核
  - eval/data/eval_set_exec_30.jsonl 留出 30 条（不参与训练），供训练后离线实测
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import os
from datetime import date, timedelta

DEFAULT_OUT = r"D:/anaconda/LlamaFactory-main/LlamaFactory-main/data/my_data17.json"
VERIFY_OUT = r"E:/Intrel-Train Industrial/tmp/agent/verify17.json"
EVAL_OUT = r"E:/Intrel-Train Industrial/eval/data/eval_set_exec_30.jsonl"
BENCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exec_benchmarks.json")

SEP = "\r\n"

# ---------------------------------------------------------------------------
# 一、与后端逐字对齐的两段原文（ExecDiagnosisService，逐字复制，禁止改写）
# ---------------------------------------------------------------------------

SYSTEM_LINES = [
    "你是变电运维中心的「公司运行诊断专家」，面向老总出报告。",
    "你只能依据用户提供的【事实清单】写结论；事实清单之外的数据、数字、人名、时间一律不得出现。",
    "硬性要求：",
    "1. 只输出一个 JSON 对象，不要输出解释文字，不要用 markdown 代码块。",
    "2. 字段名、层级、枚举取值必须与【输出模板】完全一致，不得增删或改名。",
    "3. verdict.cause 只能取 MIXED/TALENT_GAP/SKILL_GAP：MIXED=人才缺失与技能不足并存，TALENT_GAP=以缺人为主，SKILL_GAP=以在岗技能不足为主。",
    "4. priority 只能取 HIGH/MEDIUM/LOW。",
    "5. 所有数字必须来自【事实清单】，禁止编造人数、分数、金额、比例；每条 evidence 末尾标注事实编号（如 F7），便于追溯。",
    "6. 安全记录里出现一票否决时，安全必须是最高优先级，结论里要点名；不得被成本或效率理由盖过。",
    "7. 判断人才缺失还是技能不足时，必须同时引用「岗位编制缺口」与「在岗技能未达标」两类事实。",
    "8. findings 写 3-4 项，每项都要能在事实清单里找到依据；actions 写 3-4 条，写清责任方、成本影响与预期效果。",
    "9. cost_summary 的当前成本、优化后测算、预计节省三个数字都必须能在事实清单里找到出处。",
    "10. summary 先交代当前运行基本面（编制、在岗、证书、培训、成本里已达标或正常的部分），再讲卡点、成因与优先动作；只讲问题、不提基本面视为不合格。",
    "11. findings 的 impact 要写清对哪项业务动作或成本的影响，evidence 要给出可核对的事实编号。",
]
SYSTEM_PROMPT = SEP.join(SYSTEM_LINES)

TEMPLATE_LINES = [
    "【事实清单】（结论里出现的每个数字都必须在这里找到出处）",
    "@FACTS",
    "【输出模板】",
    "{",
    '  "summary": "3-5 句总述：现在卡在哪、是缺人还是缺技能、先做什么、能省多少钱",',
    '  "confidence": 0.0 到 1.0 之间的小数,',
    '  "verdict": {"cause": "MIXED", "label": "主因表述", "headline": "一句话结论", "evidence": ["证据1", "证据2", "证据3"]},',
    '  "findings": [{"title": "问题标题", "impact": "影响", "evidence": "依据"}],',
    '  "actions": [{"priority": "HIGH", "owner": "责任方", "action": "措施", "cost_impact": "成本影响", "expected": "预期效果"}],',
    '  "cost_summary": {"current_total": 0, "optimized_total": 0, "saving": 0, "note": "口径说明"}',
    "}",
    "只输出上面这个 JSON，字段名照抄，取值按事实清单填写。",
]

# ---------------------------------------------------------------------------
# 二、Python 镜像：DiagnosisContract 的数字对账（逐条对齐 Java 实现）
# ---------------------------------------------------------------------------

IGNORED = re.compile(r"F[0-9]+|L[1-5]|第[0-9]+步|[0-9]{4}-[0-9]{2}-[0-9]{2}")
NUMBER = re.compile(r"[0-9]+(?:[.][0-9]+)?")


def _normalize(number: str) -> str:
    try:
        value = float(number)
        if value == math.floor(value) and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    except ValueError:
        return number


def numbers_of(text: str) -> set:
    if not text:
        return set()
    cleaned = IGNORED.sub(" ", text)
    return {_normalize(m.group()) for m in NUMBER.finditer(cleaned)}


def _java_round(value: float) -> int:
    """Java Math.round：半分位向上（正数域）。"""
    return int(math.floor(value + 0.5))


def add_derived(allowed: set) -> set:
    base = []
    for value in allowed:
        try:
            parsed = float(value)
            if abs(parsed) <= 100000:
                base.append(parsed)
        except ValueError:
            pass
    if len(base) < 2 or len(base) > 80:
        return allowed
    derived = set()
    for left in base:
        for right in base:
            derived.add(_normalize(str(left + right)))
            derived.add(_normalize(str(abs(left - right))))
            if right != 0:
                derived.add(_normalize(str(_java_round(left * 100 / right))))
                derived.add(_normalize(repr(left / right)))
    return allowed | derived


def unverified_numbers(payload: dict, allowed: set) -> list:
    # 后端 NARRATIVE 参与核对的路径（exec 相关部分）
    texts = []
    texts.append(str(payload.get("summary", "")))
    verdict = payload.get("verdict") or {}
    texts.append(str(verdict.get("headline", "")))
    texts.append(str(verdict.get("label", "")))
    for item in verdict.get("evidence", []) or []:
        texts.append(str(item))
    for finding in payload.get("findings", []) or []:
        texts.append(str(finding.get("title", "")))
        texts.append(str(finding.get("impact", "")))
        texts.append(str(finding.get("evidence", "")))
    unverified = []
    seen = set()
    for text in texts:
        for m in NUMBER.finditer(IGNORED.sub(" ", text)):
            number = _normalize(m.group())
            if number in allowed or number in seen:
                continue
            seen.add(number)
            unverified.append(number)
    return unverified


def validate_exec_mirror(payload: dict) -> list:
    """validateExec 的 Python 镜像（硬校验部分），用于生成期快速反馈。"""
    errors = []
    if not payload:
        return ["结论为空"]
    if not str(payload.get("summary", "")).strip():
        errors.append("summary 缺失")
    conf = payload.get("confidence")
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        errors.append("confidence 越界")
    verdict = payload.get("verdict")
    if not isinstance(verdict, dict):
        errors.append("verdict 必须是对象")
    else:
        if verdict.get("cause") not in ("MIXED", "TALENT_GAP", "SKILL_GAP"):
            errors.append("verdict.cause 越界")
        for key in ("label", "headline"):
            if not str(verdict.get(key, "")).strip():
                errors.append(f"verdict.{key} 缺失")
        ev = verdict.get("evidence")
        if not isinstance(ev, list) or not ev or any(not str(x).strip() for x in ev):
            errors.append("verdict.evidence 必须是非空数组")
    findings = payload.get("findings")
    if not isinstance(findings, list) or not findings:
        errors.append("findings 必须是非空数组")
    else:
        titles = set()
        for i, f in enumerate(findings):
            for key in ("title", "impact", "evidence"):
                if not str(f.get(key, "")).strip():
                    errors.append(f"findings[{i}].{key} 缺失")
            if str(f.get("title")) in titles:
                errors.append("findings.title 重复")
            titles.add(str(f.get("title")))
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("actions 必须是非空数组")
    else:
        for i, a in enumerate(actions):
            if a.get("priority") not in ("HIGH", "MEDIUM", "LOW"):
                errors.append(f"actions[{i}].priority 越界")
            for key in ("owner", "action", "cost_impact", "expected"):
                if not str(a.get(key, "")).strip():
                    errors.append(f"actions[{i}].{key} 缺失")
    cost = payload.get("cost_summary")
    if not isinstance(cost, dict):
        errors.append("cost_summary 必须是对象")
    else:
        for key in ("current_total", "optimized_total", "saving"):
            if not isinstance(cost.get(key), (int, float)):
                errors.append(f"cost_summary.{key} 必须是数字")
        if not str(cost.get("note", "")).strip():
            errors.append("cost_summary.note 缺失")
    return errors


# ---------------------------------------------------------------------------
# 三、档案采样（因子设计，数量级取 exec_benchmarks.json 的真实锚点）
# ---------------------------------------------------------------------------

TEAM_POOL = ["变电运维一班", "变电运维二班", "变电运维三班", "继电保护班", "电气试验班",
             "综合检修班", "自动化班", "带电作业班", "安全监察班"]
SKILL_POOL = ["继电保护", "高压试验", "倒闸操作", "故障录波", "安全规程", "直流运维", "二次安措"]
POST_POOL = [
    ("继电保护主值班员", "继电保护班", "继电保护 L3"),
    ("高压试验负责人", "电气试验班", "高压试验 L3"),
    ("定值整定校核", "继电保护班", "继电保护 L3 + 故障录波 L2"),
    ("故障录波分析", "自动化班", "故障录波 L2"),
    ("安全监护", "安全监察班", "安全规程 L3"),
    ("直流运维负责人", "自动化班", "直流运维 L2"),
    ("二次安措专责", "变电运维二班", "二次安措 L2"),
]
NAME_POOL = ["张伟", "王芳", "李娜", "刘洋", "陈静", "杨帆", "赵敏", "黄涛", "周强", "吴倩",
             "徐磊", "孙丽", "马超", "朱婷", "胡军", "郭鑫", "何平", "高翔", "林悦", "罗凯"]
EXAM_POOL = ["继电保护理论考试", "安全规程年度考试", "高压试验基础理论", "倒闸操作规程考试",
             "故障录波分析笔试", "电力安全工作规程考试", "二次安措专项考试"]
EXAM_DATE_BASE = date(2026, 9, 20)
COST_TYPES = ["培训", "加班", "招聘", "外委"]

# 数量级锚点（exec_benchmarks.json）：
#   人均培训 3000-8000 元/年（8% 上限 × 行业工资 150285 元 ≈ 1.2 万，实际执行取其中）
#   招聘全口径 0.8-3 万/人（SHRM/国内猎头参考）
#   外委人均年成本 9-19 万（国网江苏 11.7 万/人年）
#   人均加班 800-3000 元/年
ARCHETYPES = [
    ("mixed", 0.40),      # 人才缺失 + 技能不足并存
    ("talent", 0.18),     # 以缺人为主
    ("skill", 0.22),      # 以在岗技能不足为主
    ("veto", 0.12),       # 带一票否决（安全最高优先级）
    ("healthy", 0.08),    # 基本健康，问题轻微
]


def pick_archetype(rng: random.Random) -> str:
    roll = rng.random()
    acc = 0.0
    for name, weight in ARCHETYPES:
        acc += weight
        if roll < acc:
            return name
    return "mixed"


def sample_profile(index: int) -> dict:
    rng = random.Random(17000 + index)
    kind = pick_archetype(rng)

    teams = rng.sample(TEAM_POOL, rng.randint(5, 8))
    posts = []
    post_count = rng.randint(3, 5)
    chosen = rng.sample(POST_POOL, post_count)
    for name, org, req in chosen:
        if kind in ("talent", "mixed", "veto"):
            backup = rng.choice([0, 0, 1, 1, 2, 2, 3])
        elif kind == "skill":
            backup = rng.choice([1, 2, 2, 3, 4])
        else:
            backup = rng.choice([2, 2, 3, 3, 4, 8])
        headcount = rng.randint(4, 30)
        posts.append({
            "name": name,
            "org": org if org in teams else rng.choice(teams),
            "required_level": req,
            "headcount": headcount,
            "backup_count": min(backup, headcount),
            "risk": "HIGH" if backup == 0 else ("MEDIUM" if backup == 1 else "LOW"),
        })

    skills = []
    skill_names = rng.sample(SKILL_POOL, rng.randint(5, 6))
    for skill in skill_names:
        total = rng.randint(10, 40)
        if kind in ("skill", "mixed", "veto"):
            rate = rng.uniform(0.55, 0.80)
        elif kind == "talent":
            rate = rng.uniform(0.70, 0.92)
        else:
            rate = rng.uniform(0.80, 1.0)
        ok = max(1, min(total, _java_round(total * rate)))
        skills.append({"skill": skill, "total": total, "ok": ok})

    exam_total = rng.randint(40, 260)
    if kind in ("skill", "mixed", "veto"):
        below = max(1, _java_round(exam_total * rng.uniform(0.06, 0.22)))
    elif kind == "talent":
        below = _java_round(exam_total * rng.uniform(0.02, 0.10))
    else:
        below = _java_round(exam_total * rng.uniform(0.0, 0.05))
    exam_failed = []
    for _ in range(min(3, below)):
        exam_failed.append({
            "username": rng.choice(NAME_POOL),
            "exam_name": rng.choice(EXAM_POOL),
            "score": rng.randint(52, 79),
            "pass_score": rng.choice([60, 80, 85]),
            "submitted_at": (EXAM_DATE_BASE - timedelta(days=rng.randint(1, 45))).isoformat()
                             + " " + f"{rng.randint(8, 17):02d}:{rng.randint(10, 55):02d}",
        })
    exam_failed.sort(key=lambda e: e["submitted_at"], reverse=True)

    reports = rng.randint(20, 120)
    if kind in ("skill", "mixed", "veto"):
        abnormal = max(1, _java_round(reports * rng.uniform(0.15, 0.35)))
    else:
        abnormal = _java_round(reports * rng.uniform(0.02, 0.14))
    missing = rng.randint(0, 2) if kind == "healthy" else rng.randint(0, 6)
    certs = int(90 * rng.uniform(1.3, 1.9))
    cert_expiring = rng.randint(0, 2) if kind == "healthy" else rng.randint(1, 9)
    safety = rng.randint(10, 60)
    veto = rng.randint(1, 2) if kind == "veto" else 0

    headcount_est = sum(s["total"] for s in skills) // 2
    costs = {"培训": headcount_est * rng.randint(3000, 8000)}
    costs["加班"] = headcount_est * rng.randint(800, 3000)
    if kind != "healthy" or rng.random() < 0.5:
        hires = rng.randint(1, 5)
        costs["招聘"] = hires * rng.randint(8000, 30000)
    out_persons = rng.randint(1, 4) if kind != "healthy" else rng.randint(0, 2)
    if out_persons > 0:
        costs["外委"] = out_persons * rng.randint(90000, 190000)

    return {
        "kind": kind, "teams": teams, "posts": posts, "skills": skills,
        "exam_total": exam_total, "exam_below": below, "exam_failed": exam_failed,
        "reports": reports, "abnormal": abnormal, "missing": missing,
        "certs": certs, "cert_expiring": cert_expiring,
        "safety": safety, "veto": veto, "costs": costs,
    }


# ---------------------------------------------------------------------------
# 四、事实清单（与 ExecDiagnosisService.facts() 同序同形）
# ---------------------------------------------------------------------------

def build_facts(p: dict) -> list:
    facts = []

    def add(source, label, value):
        facts.append({"id": f"F{len(facts) + 1}", "source": source, "label": label, "value": value})

    for post in p["posts"]:
        add("position",
            f"关键岗位《{post['name']}》（{post['org']}）要求 {post['required_level']}",
            f"编制 {post['headcount']} 人，现有备份 {post['backup_count']} 人，风险 {post['risk']}")
    for s in sorted(p["skills"], key=lambda x: x["skill"]):
        add("employee_skill",
            f"技能 {s['skill']}：在岗 {s['total']} 人",
            f"达到岗位要求 {s['ok']} 人，未达标 {s['total'] - s['ok']} 人")
    add("exam_history", f"全公司考试记录 {p['exam_total']} 条", f"未达合格线 {p['exam_below']} 条")
    for e in p["exam_failed"]:
        add("exam_history",
            f"未通过：{e['username']}《{e['exam_name']}》{e['score']} 分（合格线 {e['pass_score']}）",
            f"考试时间 {e['submitted_at']}")
    add("task_report", f"系统内实操检测报告 {p['reports']} 份", f"判定超限 {p['abnormal']} 份")
    add("task", f"实操任务缺报 {p['missing']} 项", "缺报会让诊断输入不完整")
    add("certificate", f"证书合计 {p['certs']} 本", f"90 天内到期或已过期 {p['cert_expiring']} 本")
    if p["veto"] > 0:
        add("safety_record", f"安全记录合计 {p['safety']} 条",
            f"其中一票否决 {p['veto']} 条（安全不合格优先级最高）")
    else:
        add("safety_record", f"安全记录合计 {p['safety']} 条", "无一票否决记录")
    for ctype in sorted(p["costs"].keys()):
        add("cost_record", f"成本台账：{ctype}", f"合计 {p['costs'][ctype]} 元")
    return facts


# ---------------------------------------------------------------------------
# 五、诊断推理引擎：从档案推导 metrics → findings / actions / verdict / summary
# ---------------------------------------------------------------------------

def pc(part: float, whole: float) -> int:
    return _java_round(part * 100.0 / whole)


def round_to_hundred(value: float) -> int:
    return _java_round(value / 100.0) * 100


def diagnose(p: dict, facts: list, rng: random.Random) -> dict:
    fid = {}  # source 维度 → 事实编号，便于叙述引用
    for f in facts:
        fid.setdefault(f["source"] + "|" + f["label"], f["id"])

    def ref(label_prefix):
        for f in facts:
            if f["label"].startswith(label_prefix):
                return f
        return None

    # ---- 指标 ----
    skills_sorted = sorted(p["skills"], key=lambda s: pc(s["ok"], s["total"]))
    weakest = skills_sorted[0]
    strongest = skills_sorted[-1]
    rate = {s["skill"]: pc(s["ok"], s["total"]) for s in p["skills"]}
    exam_fail_rate = pc(p["exam_below"], p["exam_total"])
    abnormal_rate = pc(p["abnormal"], p["reports"]) if p["reports"] else 0
    single_point = [q for q in p["posts"] if q["backup_count"] < 2]
    zero_backup = [q for q in p["posts"] if q["backup_count"] == 0]
    cost_types = sorted(p["costs"].keys())
    total_cost = sum(p["costs"].values())
    outsourcing = p["costs"].get("外委", 0)
    overtime = p["costs"].get("加班", 0)
    hiring = p["costs"].get("招聘", 0)

    skill_severe = rate[weakest["skill"]] < 65 or (rate[weakest["skill"]] < 75 and (weakest["total"] - weakest["ok"]) >= 8)
    talent_severe = bool(zero_backup) or len(single_point) >= 2
    if talent_severe and skill_severe:
        cause = "MIXED"
    elif talent_severe:
        cause = "TALENT_GAP"
    elif skill_severe:
        cause = "SKILL_GAP"
    else:
        cause = "MIXED" if len(single_point) >= 1 and rate[weakest["skill"]] < 80 else (
            "TALENT_GAP" if len(single_point) >= 1 else "SKILL_GAP")

    # ---- 事实编号定位 ----
    f_post = {q["name"]: ref("关键岗位《" + q["name"] + "》") for q in p["posts"]}
    f_skill = {s["skill"]: ref("技能 " + s["skill"]) for s in p["skills"]}
    f_exam_total = ref("全公司考试记录")
    f_exam_failed = {e["username"] + e["exam_name"]: None for e in p["exam_failed"]}
    failed_refs = [f["id"] for f in facts if f["source"] == "exam_history" and f["label"].startswith("未通过：")]
    f_report = ref("系统内实操检测报告")
    f_missing = ref("实操任务缺报")
    f_cert = ref("证书合计")
    f_safety = ref("安全记录合计")
    f_cost = {t: ref("成本台账：" + t) for t in cost_types}

    # ---- findings（按严重度挑 3-4 项，安全永远第一）----
    findings = []

    def add_finding(kind_key, title, impact, evidence):
        findings.append({"_kind": kind_key, "title": title, "impact": impact, "evidence": evidence})

    if p["veto"] > 0:
        add_finding("safety",
            rng.choice([f"安全记录出现 {p['veto']} 条一票否决，处置优先级最高",
                        f"{p['veto']} 条安全记录触发一票否决",
                        f"一票否决记录 {p['veto']} 条，须先于一切业务安排处置"]),
            rng.choice(["被否决人员在解除前不得单独承担现场作业，相关工作票许可与操作安排都要另设监护，排班弹性被压到最低",
                        "一票否决直接限制现场开工面，涉事人员参与的检修与操作任务都要重新指派，产出损失随时间放大",
                        "安全不合格人员继续顶岗会放大人身与设备风险，且在人才决策中一票否决高于任何成本考虑"]),
            f"{f_safety['id']}：安全记录合计 {p['safety']} 条，其中一票否决 {p['veto']} 条")

    for q in single_point[:2]:
        sev = "HIGH" if q["backup_count"] == 0 else "MEDIUM"
        add_finding("backup",
            rng.choice([f"关键岗位《{q['name']}》备份不足",
                        f"《{q['name']}》仅有 {q['backup_count']} 人可顶岗",
                        f"关键岗位断档风险：《{q['name']}》"]),
            rng.choice([f"该岗位编制 {q['headcount']} 人，现有备份 {q['backup_count']} 人，骨干一人请假即需停工或外聘支援，定值与试验类工作排不开",
                        f"一旦现岗人员休假或调动，{q['org']} 对应业务只能降级运行，专项工作排队等人在岗",
                        f"备份薄弱使 {q['org']} 的关键作业依赖少数几人，任务高峰期只能靠加班或外委消化"]),
            f"{f_post[q['name']]['id']}：要求 {q['required_level']}，编制 {q['headcount']} 人，现有备份 {q['backup_count']} 人，风险 {q['risk']}")

    for s in skills_sorted[:2]:
        if rate[s["skill"]] >= 82:
            continue
        unmet = s["total"] - s["ok"]
        add_finding("skill",
            rng.choice([f"{s['skill']} 达标率仅 {rate[s['skill']]}%",
                        f"在岗技能不足集中在{s['skill']}",
                        f"{s['skill']}未达标 {unmet} 人"]),
            rng.choice([f"{s['skill']}是现场作业的主项，{unmet} 人未达标意味着这部分工作要靠少数达标人员顶替，任务吞吐受限且质量波动大",
                        f"未达标人员独立作业需双人复核或师傅陪同，同等工作量要投入更多工时，且是考试与实操两处证据的共同短板",
                        f"该项缺口直接压低班组的可排班人数，涉及 {s['skill']} 的检修与验收只能错峰安排"]),
            f"{f_skill[s['skill']]['id']}：在岗 {s['total']} 人，达到岗位要求 {s['ok']} 人，未达标 {unmet} 人")

    if p["exam_below"] > 0:
        add_finding("exam",
            rng.choice([f"考试未达合格线 {p['exam_below']} 条",
                        f"考试记录里 {p['exam_below']} 条未过线",
                        f"考试未过线 {p['exam_below']} 条，理论短板仍在"]),
            rng.choice([f"未过线人员按规程不能独立顶岗，与在岗技能未达标相互印证，是技能缺口的人员侧来源",
                        f"理论不过线会卡住取证与等级晋升，长期拖累梯队补位速度",
                        f"这部分人员复训补考前只能做辅助工作，直接占用带教师傅的工时"]),
            f"{f_exam_total['id']}：全公司考试记录 {p['exam_total']} 条，未达合格线 {p['exam_below']} 条"
            + (f"；{failed_refs[0]} 为最近一条未通过记录" if failed_refs else ""))

    if abnormal_rate >= 15:
        add_finding("report",
            rng.choice([f"实操报告超限率 {abnormal_rate}%",
                        f"检测报告判定超限集中在 {abnormal_rate}% 的高位",
                        f"超限判定占比 {abnormal_rate}%，过程管控偏松"]),
            rng.choice([f"超限集中在定值准备与气体检测等环节，返工与复测占用工时，也抬高安全风险等级",
                        f"超限率高说明作业过程与 SOP 的偏差未被前置拦截，质量成本随报告量线性放大",
                        f"报告超限会触发复测与原因分析流程，挤占本已紧张的骨干人力"]),
            f"{f_report['id']}：实操检测报告 {p['reports']} 份，判定超限 {p['abnormal']} 份")

    if p["missing"] >= 3:
        add_finding("missing",
            rng.choice([f"实操任务缺报 {p['missing']} 项",
                        f"缺报 {p['missing']} 项，诊断输入不完整",
                        f"{p['missing']} 项任务未交报告"]),
            rng.choice([f"缺报让诊断与归因只能基于不完整证据，超限与技能短板可能被低估",
                        f"报告缺失会拖延问题暴露时间，等下一次检测才发现偏差，纠错成本更高",
                        f"缺报纳入不了看板统计，班组之间的横向比较会失真"]),
            f"{f_missing['id']}：实操任务缺报 {p['missing']} 项")

    if p["cert_expiring"] >= 3:
        add_finding("cert",
            rng.choice([f"证书 90 天内到期或已过期 {p['cert_expiring']} 本",
                        f"{p['cert_expiring']} 本证书临期或过期",
                        f"证书复审窗口集中：{p['cert_expiring']} 本"]),
            rng.choice([f"持证人员到期未复审会失去作业资格，等于变相减员，且复审窗口错过就要重新考证",
                        f"证书失效直接影响工作票许可与特种作业安排，是刚性的合规约束",
                        f"临期证书集中到期会在同一时段制造资格空档，排班需要提前错开"]),
            f"{f_cert['id']}：证书合计 {p['certs']} 本，90 天内到期或已过期 {p['cert_expiring']} 本")

    if outsourcing > 0 and outsourcing >= max(p["costs"].values()):
        add_finding("outsourcing",
            rng.choice([f"外委支出 {outsourcing} 元居四类成本之首",
                        f"外委依赖度偏高：年支出 {outsourcing} 元",
                        f"外委成本 {outsourcing} 元，是成本结构里最大的可压缩项"]),
            rng.choice([f"外委单价逐年上行且受制于外部队伍档期，高峰期不一定排得上，价格与进度双重不可控",
                        f"外委做的是本可以由自有骨干承接的工作，等于把钱花在别人的培训成果上",
                        f"外委支出居高会挤占自有培训预算，形成「越外包越缺人」的循环"]),
            f"{f_cost['外委']['id']}：成本台账外委合计 {outsourcing} 元"
            + (f"，高于其他各类型支出" if outsourcing >= max(p["costs"].values()) else ""))

    order = {"safety": 0, "backup": 1, "skill": 2, "exam": 3, "report": 4, "missing": 5, "cert": 6, "outsourcing": 7}
    findings.sort(key=lambda f: order[f["_kind"]])
    keep = 4 if (len(findings) >= 4 and p["kind"] != "healthy") else 3
    findings = findings[:keep]
    while len(findings) < 3:
        # 兜底：健康档案也可能凑不满 3 项，用温和项补齐
        if all(f["_kind"] != "cert" for f in findings):
            add_finding("cert",
                f"证书 90 天内到期或已过期 {p['cert_expiring']} 本",
                "临期证书需在到期前完成复审，否则对应人员会暂时失去作业资格",
                f"{f_cert['id']}：证书合计 {p['certs']} 本，90 天内到期或已过期 {p['cert_expiring']} 本")
        elif all(f["_kind"] != "skill" for f in findings):
            s = weakest
            add_finding("skill",
                f"{s['skill']} 达标率 {rate[s['skill']]}%，仍有提升空间",
                f"未达标人员作业需监护或复核，轻度影响排班弹性",
                f"{f_skill[s['skill']]['id']}：在岗 {s['total']} 人，达到岗位要求 {s['ok']} 人，未达标 {s['total'] - s['ok']} 人")
        else:
            add_finding("missing",
                f"实操任务缺报 {p['missing']} 项",
                "缺报使过程证据不完整，问题暴露滞后",
                f"{f_missing['id']}：实操任务缺报 {p['missing']} 项")

    # ---- actions（与 findings 一一对应，安全优先）----
    # 文案池是 dict 字面量，所有分支都会被急切求值，因此 q / s 必须安全取值（只有匹配 kind 的分支才真正被选用）
    def post_name():
        return q["name"] if q else "关键岗位"

    def skill_name():
        return s["skill"] if s else "相关技能"

    def cost_impact_of(kind_key):
        pool = {
            "safety": ["复训与考核约 ¥0.8-1.5 万，停工机会成本另计", "约 +¥1 万（复训、考核与监护工时）", "复训成本可控，约 +¥0.8 万"],
            "backup": [f"内部转岗为主、招聘补缺为辅，约 +¥2-16 万（招聘全口径约 0.8-3 万/人）",
                       "继任者培养约 +¥1.5 万，若外部补缺另计 0.8-3 万/人",
                       "内部转岗 2 人基本零现金成本，外部招聘每人均 0.8-3 万"],
            "skill": ["专项培训 + 模拟考约 +¥1-3 万（培训预算内列支）", "微课与仿真演练约 +¥1.5 万", "师带教工时折算约 +¥1.2 万，无新增现金支出"],
            "exam": ["错题复盘与补考约 +¥0.5 万", "利用现有题库组织复盘，现金支出近 0", "补考组织成本约 +¥0.3 万"],
            "report": ["SOP 交底与报告复核约 +¥0.4 万", "增加一次专项交底，成本近 0", "复核工时约 +¥0.5 万"],
            "missing": ["纳入班组考核，现金成本 0", "无直接成本，管理动作即可", "补交与台账整理约 +¥0.2 万"],
            "cert": ["复审报名与差旅约 +¥0.3-0.8 万", "集中组织复审约 +¥0.5 万", "按人次约 600-1200 元复审费"],
            "outsourcing": [f"外委转内培后，按 5% 核定口径测算外委支出可压缩 {round_to_hundred(outsourcing * 0.10)} 元/年",
                            "外委名额转内部培养，培训投入增加但外委支出下降",
                            "压缩外委规模后年支出可降约 8%-12%"],
        }[kind_key]
        return rng.choice(pool)

    def expected_of(kind_key, q=None, s=None):
        pool = {
            "safety": ["2 周内完成复训与复核，全部解除否决并恢复排班", "涉事人员复训合格率 100%，否决清零", "整改验收通过，否决记录闭环归档"],
            "backup": [f"一个季度内《{post_name()}》备份补到 2 人", "2027Q1 前关键岗位备份全部达标", "继任者到岗并完成独立作业考核"],
            "skill": [f"{skill_name()}达标率提升到 85% 以上", "下一考核周期未达标人数减半", "L2 及以上人员增加，减少双人复核占用"],
            "exam": ["未过线人员补考通过率 90% 以上", "本季度内完成补考并清零积压", "理论过线率回到 95% 以上"],
            "report": ["超限率降到 10% 以下", "报告一次通过率明显回升", "超限集中在 2 类以下且均有对策"],
            "missing": ["报告上传率恢复 100%", "缺报清零，看板数据完整", "3 日内补齐并纳入月度考核"],
            "cert": ["到期前全部完成复审，无资格空档", "复审完成率 100%", "证书台账与复审提醒闭环"],
            "outsourcing": ["外委人次下降 30%，骨干可承接相应工单", "自有人员承接外委原有工作量的一半以上", "外委支出占比回到核定口径以内"],
        }[kind_key]
        return rng.choice(pool)

    def owner_of(kind_key):
        return {
            "safety": rng.choice(["安全监察班 + 分管老总", "安全总监", "安监部门"]),
            "backup": rng.choice(["人资 + 变电运维中心", "人力资源部 + 中心分管领导", "人资部"]),
            "skill": rng.choice(["培训中心", "培训中心 + 各班组长", "教育培训专责"]),
            "exam": rng.choice(["班组长 + 培训中心", "培训中心", "各班组长"]),
            "report": rng.choice(["班组长", "班组长 + 安监", "运维专责"]),
            "missing": rng.choice(["班组长", "各班组长", "运维专责 + 班组长"]),
            "cert": rng.choice(["班组长 + 人资", "人资部", "安监 + 人资"]),
            "outsourcing": rng.choice(["分管老总", "中心分管领导 + 人资", "分管老总 + 培训中心"]),
        }[kind_key]

    def action_text_of(kind_key, q=None, s=None):
        pool = {
            "safety": ["对一票否决涉及人员立即停止单独作业，安排复训、复核与整改验收，验收通过前不得恢复原岗",
                       "启动安全整改专项：否决人员停岗复训，同步复核相关作业票与监护安排",
                       "先停后训：涉事人员暂停独立作业资格，完成复训与再考核后按程序解除否决"],
            "backup": [f"为《{post_name()}》确定 2 名继任者并纳入带教计划，缺口先内部转岗、不足再招聘",
                       f"对《{post_name()}》开展内部转岗摸底，锁定 2 名培养对象并排定取证时间表",
                       f"把《{post_name()}》继任者培养列入季度重点：先补 L2 形成第二梯队，再冲目标等级"],
            "skill": [f"对{skill_name()}未达标人员开展专项培训 + 模拟考，达标前安排双人复核",
                      f"组织{skill_name()}微课、仿真演练与师带教，按月考核达标进度",
                      f"以错题与超限报告为教材做{skill_name()}专项复盘，达标一人恢复一人独立作业"],
            "exam": ["未过线人员统一错题复盘，两周内组织补考，成绩纳入班组考核",
                     "按知识点聚类分析未过试卷，针对性补训后补考",
                     "为未过线人员各排一次带教与一次模拟考，再进正式补考"],
            "report": ["对超限集中的环节做 SOP 交底与首件复核，超限报告逐份归因",
                       "推行报告双人复核，超限前 3 类原因纳入月度案例会",
                       "把超限环节纳入实操抽考，与班组绩效挂钩"],
            "missing": ["缺报任务 3 日内补交，逾期纳入班组月度考核",
                        "建立缺报日提醒与周通报，责任到组长",
                        "补齐缺报并在看板公示完成率"],
            "cert": ["临期证书本月内完成复审报名，复审提醒推送到班组长",
                     "集中组织复审，与排班错峰安排避免资格空档",
                     "建立证书到期前 90 天三级提醒台账"],
            "outsourcing": ["外委名额分步转内部培养：先易后难，同步压缩外委预算",
                            "把外委工单改为「骨干带学员」模式，培养期结束后收回自干",
                            "按核定口径重审外委范围，可内做的项目一律转内"],
        }[kind_key]
        return rng.choice(pool)

    actions = []
    for f in findings:
        kind_key = f["_kind"]
        q = next((x for x in p["posts"] if x["name"] in f["title"]), None)
        s = next((x for x in p["skills"] if x["skill"] in f["title"]), None)
        if kind_key == "safety":
            priority = "HIGH"
        elif kind_key == "backup":
            priority = "HIGH" if q and q["backup_count"] == 0 else "MEDIUM"
        elif kind_key == "skill":
            priority = "HIGH" if rate[s["skill"]] < 65 else "MEDIUM"
        elif kind_key == "exam":
            priority = "MEDIUM"
        elif kind_key == "report":
            priority = "MEDIUM" if abnormal_rate >= 20 else "LOW"
        elif kind_key == "missing":
            priority = "MEDIUM" if p["missing"] >= 5 else "LOW"
        elif kind_key == "cert":
            priority = "MEDIUM" if p["cert_expiring"] >= 6 else "LOW"
        else:
            priority = "MEDIUM"
        actions.append({
            "priority": priority,
            "owner": owner_of(kind_key),
            "action": action_text_of(kind_key, q, s),
            "cost_impact": cost_impact_of(kind_key),
            "expected": expected_of(kind_key, q, s),
        })
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    actions.sort(key=lambda a: rank[a["priority"]])

    # ---- cost_summary ----
    saving = 0
    levers = []
    if outsourcing > 0:
        lever = round_to_hundred(outsourcing * rng.uniform(0.06, 0.15))
        saving += lever
        levers.append(f"外委转内培约省 {lever} 元/年（外委台账 {outsourcing} 元的 6%-15%）")
    if overtime > 0 and (skill_severe or talent_severe):
        lever = round_to_hundred(overtime * rng.uniform(0.10, 0.22))
        saving += lever
        levers.append(f"可独立作业人数增加后加班回落约 {lever} 元/年（加班台账 {overtime} 元的 10%-22%）")
    if saving == 0 and hiring > 0:
        lever = round_to_hundred(hiring * 0.2)
        saving += lever
        levers.append(f"内部转岗替代部分社招，招聘费约省 {lever} 元/年")
    if saving == 0:
        saving = round_to_hundred(total_cost * 0.02)
        levers.append(f"过程返工与超时工时回收约 {saving} 元/年")
    saving = min(saving, round_to_hundred(total_cost * 0.2))
    note_variants = [
        "口径：当前成本取成本台账四类支出合计；预计节省按「" + levers[0] + "」测算，属管理测算值、不进会计科目。",
        "口径：current_total 为台账四类成本之和；优化测算以 " + levers[0] + " 为依据，其余动作的收益未重复计入，避免虚高。",
        "口径：台账口径（" + "、".join(cost_types) + "）合计为当前成本；节省只计 " + levers[0] + " 这一条最稳的来源。",
        "口径：四类台账支出合计即当前成本；预计节省来自 " + levers[0] + "，其余举措见效后另行测算。",
    ]
    cost_summary = {
        "current_total": total_cost,
        "optimized_total": total_cost - saving,
        "saving": saving,
        "note": rng.choice(note_variants),
    }

    # ---- verdict ----
    main_post = single_point[0] if single_point else p["posts"][0]
    ev1 = (f"{f_post[main_post['name']]['id']}：关键岗位《{main_post['name']}》要求 {main_post['required_level']}，"
           f"编制 {main_post['headcount']} 人、现有备份 {main_post['backup_count']} 人"
           f" → 岗位编制缺口" + ("明确，属人才缺失" if single_point else "暂不明显，梯队处于可控状态"))
    unmet_main = weakest["total"] - weakest["ok"]
    ev2 = (f"{f_skill[weakest['skill']]['id']}：技能 {weakest['skill']} 在岗 {weakest['total']} 人、"
           f"达到岗位要求 {weakest['ok']} 人、未达标 {unmet_main} 人，达标率 {rate[weakest['skill']]}%"
           f" → 在岗技能不足集中在{weakest['skill']}")
    if p["veto"] > 0:
        ev3 = f"{f_safety['id']}：安全记录 {p['veto']} 条一票否决 → 安全问题优先级最高，先于人才与技能事项处置"
    elif p["exam_below"] > 0:
        ev3 = (f"{f_exam_total['id']}：考试记录 {p['exam_total']} 条、未达合格线 {p['exam_below']} 条"
               f"（未过线率 {exam_fail_rate}%） → 理论短板与在岗技能未达标相互印证")
    else:
        ev3 = f"{f_report['id']}：实操报告 {p['reports']} 份、判定超限 {p['abnormal']} 份 → 过程质量与技能状态佐证"

    label_variants = {
        "MIXED": ["人才缺失与技能不足并存，当前以" + ("在岗技能不足" if skill_severe else "人才缺失") + "为主因",
                  "人才与技能两条缺口叠加，需先补在岗能力、再补人数",
                  "结构性缺员与在岗能力不足同时存在"],
        "TALENT_GAP": ["以人才缺失为主：关键岗位备份不足是第一约束",
                       "主要矛盾在缺人，技能缺口是缺人的下游结果",
                       "关键岗位断档风险高于技能缺口"],
        "SKILL_GAP": ["以在岗技能不足为主：现有人员能力与岗位要求存在系统性差距",
                      "主要矛盾在技能而非人数，先用好存量再谈补员",
                      "在岗达标率不足是当前最大约束"],
    }[cause]
    headline_variants = {
        "MIXED": [f"{weakest['skill']}达标率 {rate[weakest['skill']]}% 与《{main_post['name']}》备份 {main_post['backup_count']} 人并存，先技能后人数",
                  f"人才与技能缺口叠加：{weakest['skill']}未达标 {unmet_main} 人、关键岗位备份 {main_post['backup_count']} 人",
                  f"先补{weakest['skill']}在岗能力，再补《{main_post['name']}》梯队"],
        "TALENT_GAP": [f"《{main_post['name']}》备份仅 {main_post['backup_count']} 人，补人优先于补课",
                       f"关键岗位备份不足是第一约束：{main_post['name']}现有备份 {main_post['backup_count']} 人",
                       f"梯队断档风险大于技能缺口，先落实继任者"],
        "SKILL_GAP": [f"在岗技能不足为主：{weakest['skill']}达标率仅 {rate[weakest['skill']]}%",
                      f"{weakest['skill']}未达标 {unmet_main} 人是当前最大卡点，优先内培",
                      f"先提达标率再谈补人：{weakest['skill']}是第一短板"],
    }[cause]

    verdict = {
        "cause": cause,
        "label": rng.choice(label_variants),
        "headline": rng.choice(headline_variants),
        "evidence": [ev1, ev2, ev3],
    }

    # ---- summary（先基本面、再卡点、成因、优先动作）----
    strongest_ok = strongest["ok"] == strongest["total"]
    if strongest_ok:
        s1 = (f"{f_skill[strongest['skill']]['id']}显示{strongest['skill']}在岗 {strongest['total']} 人全部达标，"
              f"{f_cert['id']}处证书合计 {p['certs']} 本、90 天内到期 {p['cert_expiring']} 本，"
              f"安全记录 {p['safety']} 条" + ("、无一票否决" if p["veto"] == 0 else "、其中一票否决须优先处置") + "，基本面总体可控。")
    else:
        s1 = (f"{f_skill[strongest['skill']]['id']}显示{strongest['skill']}达标率 {rate[strongest['skill']]}% 为各项技能中最高，"
              f"证书合计 {p['certs']} 本、90 天内到期 {p['cert_expiring']} 本（{f_cert['id']}），"
              + ("安全记录无一票否决，" if p["veto"] == 0 else "") + "运行基本面总体平稳。")
    s2 = (f"卡点有二：{weakest['skill']}在岗 {weakest['total']} 人中未达标 {unmet_main} 人、达标率 {rate[weakest['skill']]}%（{f_skill[weakest['skill']]['id']}）；"
          f"《{main_post['name']}》编制 {main_post['headcount']} 人、备份 {main_post['backup_count']} 人（{f_post[main_post['name']]['id']}）。"
          if cause == "MIXED" else
          (f"最大卡点在人：《{main_post['name']}》编制 {main_post['headcount']} 人、备份仅 {main_post['backup_count']} 人（{f_post[main_post['name']]['id']}），"
           f"{weakest['skill']}达标率 {rate[weakest['skill']]}% 亦偏低（{f_skill[weakest['skill']]['id']}）。"
           if cause == "TALENT_GAP" else
           f"最大卡点在技能：{weakest['skill']}在岗 {weakest['total']} 人、未达标 {unmet_main} 人、达标率 {rate[weakest['skill']]}%（{f_skill[weakest['skill']]['id']}），"
           f"《{main_post['name']}》备份 {main_post['backup_count']} 人（{f_post[main_post['name']]['id']}）暂可维持。"))
    if p["exam_below"] > 0 and p["veto"] == 0:
        s3 = (f"成因上，考试未达合格线 {p['exam_below']} 条（{f_exam_total['id']}）与实操报告超限 {p['abnormal']} 份（{f_report['id']}）"
              f"互为印证：理论短板经现场作业放大为过程偏差。")
    elif p["veto"] > 0:
        s3 = f"成因上，{p['veto']} 条一票否决（{f_safety['id']}）是当前最高优先级，技能与人才事项都要在安全整改之后安排。"
    else:
        s3 = f"成因上，实操报告超限 {p['abnormal']} 份（{f_report['id']}）说明过程管控偏差主要来自在岗能力的差距，而非人数不足。"
    top_action = actions[0]
    s4 = f"建议先由{top_action['owner']}落实「{top_action['action'][:28]}…」，随后按优先级推进其余整改。"
    if outsourcing > 0:
        s5 = f"成本上外委台账 {outsourcing} 元（{f_cost['外委']['id']}）是最可压缩的一项，按外委转内培测算的全年节省单独列在成本小结里。"
    else:
        s5 = "成本上以培训增量换加班回落，测算口径与预计节省金额单独列在成本小结里。"
    n_sentences = rng.randint(4, 5)
    summary = "".join([s1, s2, s3, s4][:n_sentences - 1] + ([s5] if n_sentences == 5 else []))

    confidence = rng.choice([0.78, 0.8, 0.82, 0.84, 0.86])

    return {
        "summary": summary,
        "confidence": confidence,
        "verdict": verdict,
        "findings": [{k: f[k] for k in ("title", "impact", "evidence")} for f in findings],
        "actions": actions,
        "cost_summary": cost_summary,
    }


# ---------------------------------------------------------------------------
# 六、装配与自查
# ---------------------------------------------------------------------------

def render_user_prompt(facts: list) -> str:
    facts_text = SEP.join(f"{f['id']} [{f['source']}] {f['label']}；{f['value']}" for f in facts)
    return SEP.join(TEMPLATE_LINES).replace("@FACTS", facts_text)


def build_one(index: int) -> dict:
    p = sample_profile(index)
    rng = random.Random(91000 + index)
    facts = build_facts(p)
    payload = diagnose(p, facts, rng)
    return {"facts": facts, "payload": payload, "profile": p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--verify-out", default=VERIFY_OUT)
    ap.add_argument("--eval-out", default=EVAL_OUT)
    ap.add_argument("--eval-holdout", type=int, default=30)
    args = ap.parse_args()

    entries, verify_cases, violations, too_long = [], [], [], []
    train_count = args.count - args.eval_holdout
    for i in range(args.count):
        case = build_one(i)
        payload = case["payload"]
        facts = case["facts"]

        errors = validate_exec_mirror(payload)
        allowed = set()
        for f in facts:
            allowed |= numbers_of(f["label"] + " " + f["value"])
        allowed = add_derived(allowed)
        unverified = unverified_numbers(payload, allowed)
        if errors or unverified:
            violations.append({
                "index": i,
                "errors": errors,
                "unverified": unverified[:10],
                "summary": payload["summary"][:80],
            })
            continue

        output = json.dumps(payload, ensure_ascii=False)
        user_prompt = render_user_prompt(facts)
        total_chars = len(SYSTEM_PROMPT) + len(user_prompt) + len(output)
        if total_chars > 7000:
            too_long.append((i, total_chars))

        entry = {"system": SYSTEM_PROMPT, "instruction": "", "input": user_prompt, "output": output}
        if i < train_count:
            entries.append(entry)
            verify_cases.append({"facts": facts, "payload": payload})
        else:
            # 留出样本：保存完整上下文供离线实测
            os.makedirs(os.path.dirname(args.eval_out), exist_ok=True)
            with open(args.eval_out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "system": SYSTEM_PROMPT, "input": user_prompt, "output": output,
                    "facts": facts, "payload": payload,
                }, ensure_ascii=False) + "\n")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=1)
    with open(args.verify_out, "w", encoding="utf-8") as fh:
        json.dump(verify_cases, fh, ensure_ascii=False)

    lengths = sorted(len(e["system"]) + len(e["input"]) + len(e["output"]) for e in entries)
    out_lengths = sorted(len(e["output"]) for e in entries)
    print(f"训练条数: {len(entries)}（另有留出 {args.count - len(entries)} 条 → {args.eval_out}）")
    print(f"总字符: min/med/max = {lengths[0]}/{lengths[len(lengths)//2]}/{lengths[-1]}（上限 7000）")
    print(f"输出字符: min/med/max = {out_lengths[0]}/{out_lengths[len(out_lengths)//2]}/{out_lengths[-1]}")
    print(f"自查不合格被剔除: {len(violations)} 条")
    for v in violations[:8]:
        print("  违例", v["index"], "errors=", v["errors"][:3], "unverified=", v["unverified"][:6])
        print("    ", v["summary"])
    print(f"超长(>7000字符): {len(too_long)} 条", too_long[:5])
    print("产物:", args.out)
    print("复核:", args.verify_out)


if __name__ == "__main__":
    main()
