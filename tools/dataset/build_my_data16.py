# -*- coding: utf-8 -*-
"""
构建个性化诊断 Agent 的 SFT 语料 my_data16.json（默认 500 条，UTF-8 no BOM）。

它解决 my_data15 的三处错位
---------------------------
1) 提示词不同形：my_data15 的 input 是「档案散文」（基本信息｜…；师傅评价｜…），
   而线上后端 PersonalDiagnosisService.userPrompt() 实际发出去的是
   【今天】+【事实清单】+【本次缺口清单】+【输出模板】。
   本脚本按后端源码逐字复刻那份 prompt（含事实编号 F1…、「缺口清单」「输出模板」两段）。
2) 契约不同形：my_data15 的 output 是 11 键 A 版（conclusion/evidence/root_cause/…），
   线上 DiagnosisContract.validatePersonal 要的是 6 键 B 版
   （summary/confidence/verdict/gaps/plan/compound_path），两版交集只有 gaps 且字段名不同。
   本脚本直接产出 B 版，并用 port_contract 做全套校验（含「未被 polish 改写」的不变式）。
3) 答案不完整：my_data15 单条中位 2404 token，cutoff_len=1024 会丢掉 78% 的答案，
   模型从没见过一个闭合 JSON。本脚本保证每条目标答案完整闭合，末尾报告长度分布。

产物
----
alpaca + system 列：{"system": <systemPrompt>, "instruction": "", "input": <userPrompt>, "output": <JSON>}
经过 LlamaFactory 的 AlpacaDatasetConverter（src/llamafactory/data/converter.py）后，
instruction 为空串时不会被拼进 query，于是消息序列恰好是：
    system: <systemPrompt>  /  user: <userPrompt>  /  assistant: <output>
与线上 AiJsonClient 发出的 system + user 两条消息结构一致。
注册到 dataset_info.json 时必须声明 system 列（alpaca 的默认列名里没有 system）：
    "my_data16": {"file_name": "my_data16.json", "formatting": "alpaca",
                  "columns": {"system": "system"}}

用法
----
    python build_my_data16.py                       # 500 条 -> 桌面 my_data16.json
    python build_my_data16.py --count 600 --out D:/x.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import date, timedelta

SRC = r"D:/anaconda/LlamaFactory-main/LlamaFactory-main/data/my_data15.json"
DEFAULT_OUT = r"C:/Users/admin/Desktop/my_data16.json"

# 后端 DiagnosisPipeline.line() 用的是 System.lineSeparator()，本机 Windows 下为 CRLF。
# 训练输入与推理输入保持同一套换行，避免训练/推理分布不一致。
SEP = "\r\n"

# ---------------------------------------------------------------------------
# 一、与后端逐字对齐的两段原文
# ---------------------------------------------------------------------------

# PersonalDiagnosisService.systemPrompt() 的 13 条硬性要求（第 6 条占两行），逐字复制。
SYSTEM_LINES = [
    "你是变电运维人才培训系统的「个人学习诊断专家」。",
    "你只能依据用户提供的【事实清单】写结论；事实清单之外的数据、数字、人名、时间一律不得出现。",
    "硬性要求：",
    "1. 只输出一个 JSON 对象，不要输出解释文字，不要用 markdown 代码块。",
    "2. 字段名、层级、枚举取值必须与【输出模板】完全一致，不得增删或改名。",
    "3. severity 只能取 HIGH/MEDIUM/LOW；priority 只能取 P1/P2/P3；kind 只能取 课程/带教/模拟考。",
    "4. 所有数字必须来自【事实清单】，禁止编造分数、人数、金额、日期、时长。",
    "5. 每条 reasons 都要能对应到事实清单里的具体一条，并在句末标注事实编号（如 F7）；"
    "其中至少一条写已达标或已持证的基础项（优势），其余写缺口项，不要只列缺口。",
    "6. 事实不足以判断时写「现有数据不足以判断」，不要猜测 —— 但这条只管叙述字段（summary / reasons / impact）。",
    "   plan 的 due_at 是「计划日期」、不是事实数据，照【今天】往后排期即可，必须写成 YYYY-MM-DD。",
    "7. gaps 只写事实清单中明确未达岗位要求的技能；plan 写 3-4 步；compound_path 写 3-4 个阶段。",
    "8. summary 先交代岗位与已达标/已持证的基础项（优势），再说最大缺口与方向；只谈缺口、不提已有基础视为不合格。",
    "9. impact 写清缺口导致的业务后果（现在哪个动作做不了或必须依赖他人），action 写清下一步可执行的动作，不要写成空泛口号。",
    "10. verdict.reasons 各条之间不得互相复读，每条必须给出不同的事实依据；plan 各步的 reason 也必须各不相同，并说清这一步在整条路径里的位置。",
    "11. summary 里提到的每一个缺口技能，都要能在 gaps 里找到同名条目；不要在 summary 里提一个 gaps 里没有的技能。",
    "12. compound_path 的 why 回答「为什么把这几项合在一起学」，benefit 回答「学完之后能做什么」，两者不得互相摘抄或复述。",
    "13. plan 的 due_at 必须晚于【今天】并随 step 递增，不要几步挤在同一天。",
]
SYSTEM_PROMPT = SEP.join(SYSTEM_LINES)

# userPrompt() 里的【输出模板】段，逐字复制（含缩进与结尾那一句）。
TEMPLATE_LINES = [
    "【输出模板】",
    "{",
    '  "summary": "2-3 句总述：属于能力空白还是在岗技能不足，最大缺口是什么",',
    '  "confidence": 0.0 到 1.0 之间的小数,',
    '  "verdict": {"headline": "一句话结论", "reasons": ["依据1", "依据2", "依据3", "依据4"]},',
    '  "gaps": [{"skill": "技能名", "current": 1, "required": 3, "future": 3,',
    '            "severity": "HIGH", "priority": "P1", "impact": "业务影响", "action": "怎么做"}],',
    '  "plan": [{"step": 1, "kind": "课程", "title": "动作标题", "target_skill": "技能名",',
    '            "to_level": "L2", "due_at": "2026-10-01", "reason": "为什么先做这一步"}],',
    '  "compound_path": {"title": "复合型路线标题", "why": "为什么走这条路",',
    '     "stages": [{"phase": "第 1 阶段 · 0-2 个月", "focus": "聚焦点", "skills": "学什么", "milestone": "达标标志"}],',
    '     "benefit": "收益"}',
    "}",
    "照【输出模板】的字段名填写，只输出一个 JSON 对象，不要输出任何解释文字。",
]

SEVERITIES = ["HIGH", "MEDIUM", "LOW"]
KINDS = ["课程", "带教", "模拟考"]

# 岗位技能要求里的制度依据。全部取自 train_system.position_skill_requirement 的真实取值，
# 术语与线上一致（basis_role 三种、standard_no 七种）。
BASIS_POOL = [
    ("主依据", "GB/T 14285-2023"),
    ("主依据", "GB/T 16927.1-2011"),
    ("主依据", "GB/T 22390.6-2026"),
    ("主依据", "GB/T 40584-2021"),
    ("未来需求依据", "GB/T 45906.8-2025"),
    ("未来需求依据", "GB/T 45906.5-2025"),
]
SAFETY_BASIS = ("作业依据", "GB 26860-2011")

# 安全规程是「合格/合格」的特殊技能：不进 gaps，只作已达标优势项。
SAFETY_SKILL = "安全规程"
CN_NUM = {1: "一", 2: "两", 3: "三", 4: "四"}
TODAYS = ["2026-09-08", "2026-09-21", "2026-10-16", "2026-10-27", "2026-11-05",
          "2026-11-18", "2026-12-02", "2026-12-15", "2027-01-06", "2027-02-10"]


def stable_hash(text: str) -> int:
    """进程无关的稳定散列：Python 内置 hash() 每个进程都变，会让语料无法复现。"""
    return sum((index + 1) * ord(char) for index, char in enumerate(text))


def narrative_safe(text: str) -> str:
    """叙述字段里除事实数字外不得出现任何数字；场景名偶带数字时先剔掉。"""
    return re.sub(r"[0-9]", "", text or "")


def number(text: str):
    """'2.6' -> 2.6；'2.0' -> 2（与后端拼字符串的口径一致，整数不带小数点）。"""
    value = float(text)
    return int(value) if value == int(value) else value


def fmt(value) -> str:
    """2.6 -> '2.6'；2 -> '2'。"""
    if value is None:
        return ""
    return str(int(value)) if float(value) == int(value) else str(value)


# ---------------------------------------------------------------------------
# 二、解析 my_data15 的档案原文
# ---------------------------------------------------------------------------

def seg(text: str, key: str, end: str = r"｜") -> str:
    """取「key：」之后、到 end 之前的一段。end 用正则片段，便于处理值里自带「；」的字段。"""
    match = re.search(re.escape(key) + r"：(.+?)(?:" + end + r"|$)", text)
    return match.group(1).strip() if match else ""


def parse_persona(text: str) -> dict:
    """档案散文 -> 结构化 persona。字段缺失一律给空串，不抛异常。"""
    task_raw = seg(text, "关键任务", r"；")
    task_skill = re.split(r"达到", task_raw)[0].strip() if task_raw else ""

    cert_raw = seg(text, "证书", r"｜")
    level_match = re.search(r"(L[1-5])资格", cert_raw)
    expire_match = re.search(r"预计到期日([0-9-]{10})", cert_raw)

    exam_raw = seg(text, "考试与错题", r"｜")
    exam_name, exam_score, exam_pass = "", None, None
    name_match = re.search(r"^(.*?)考试([0-9.]+)分，合格线([0-9.]+)分", exam_raw)
    if name_match:
        exam_name = name_match.group(1).strip()
        exam_score = number(name_match.group(2))
        exam_pass = number(name_match.group(3))
    wrong_points = []
    for match in re.finditer(r"知识点：([^；;]+)", exam_raw):
        point = match.group(1).strip()
        if point and point not in wrong_points:
            wrong_points.append(point)

    practice_raw = seg(text, "实操任务", r"｜")
    practice_skill, planned_hours, actual_hours = "", None, None
    hour_match = re.search(r"^(.*?)计划([0-9.]+)小时，实际([0-9.]+)小时", practice_raw)
    if hour_match:
        practice_skill = hour_match.group(1).strip()
        planned_hours = number(hour_match.group(2))
        actual_hours = number(hour_match.group(3))

    safety_raw = seg(text, "安全记录", r"｜")

    tenure_match = re.search(r"([0-9]+)", seg(text, "工龄", r"｜"))
    match_match = re.search(r"([0-9]+)", seg(text, "当前岗位匹配度", r"｜"))
    coop = re.search(r"班组协作分：([0-9]+)", text)
    safety_score = re.search(r"安全意识分：([0-9]+)", text)
    duty = re.search(r"责任心分：([0-9]+)", text)

    return {
        "position": seg(text, "岗位", r"｜"),
        "team": seg(text, "部门/班组", r"｜"),
        "tenure": int(tenure_match.group(1)) if tenure_match else 0,
        "entry_at": seg(text, "入职时间", r"｜"),
        "education": seg(text, "学历", r"｜"),
        "cert_name": re.split(r"L[1-5]资格", cert_raw)[0].strip() if cert_raw else "",
        "cert_level": level_match.group(1) if level_match else "",
        "cert_expire": expire_match.group(1) if expire_match else "",
        "safe_pass_at": seg(text, "安全规程年度合格日期", r"；"),
        "goal_level": seg(text, "目标等级", r"｜"),
        "task_skill": task_skill,
        "mentor": seg(text, "带教师傅", r"｜"),
        "mentor_comment": seg(text, "评价", r"｜建议"),
        "mentor_advice": seg(text, "建议", r"；"),
        "team_comment": seg(text, "班组评语", r"；"),
        "match_rate": int(match_match.group(1)) if match_match else 60,
        "coop_score": int(coop.group(1)) if coop else 78,
        "safety_score": int(safety_score.group(1)) if safety_score else 80,
        "duty_score": int(duty.group(1)) if duty else 78,
        "scene": seg(text, "场景", r"｜"),
        "blind": seg(text, "技能树盲区", r"｜"),
        "soft_gap": seg(text, "软技能短板", r"｜"),
        "behavior": seg(text, "可观察行为基线", r"｜"),
        "exam_name": exam_name, "exam_score": exam_score, "exam_pass": exam_pass,
        "wrong_points": wrong_points,
        "practice_skill": practice_skill,
        "planned_hours": planned_hours, "actual_hours": actual_hours,
        "safety": safety_raw,
        "safety_head": safety_raw.split("；")[0].strip(),
    }


# ---------------------------------------------------------------------------
# 三、构造事实清单（严格照后端 facts() 的 10 组顺序与渲染格式）
# ---------------------------------------------------------------------------

def build_facts(persona: dict, variant: dict) -> tuple:
    """返回 (facts, index)。每条 fact 形如 {"id","source","label","value"}。"""
    facts: list = []
    index = {"skill": {}, "source": {}}

    def add(source: str, label: str, value: str) -> dict:
        fact = {"id": "F" + str(len(facts) + 1), "source": source, "label": label, "value": value}
        facts.append(fact)
        index["source"].setdefault(source, []).append(fact)
        return fact

    position = persona["position"]

    # 1. 岗位技能要求（与线上一致的「要求 / 未来需求 / 依据」三段式）
    for skill, required, future, basis in variant["requirements"]:
        add("position_skill_requirement", "岗位《" + position + "》要求技能 " + skill,
            "要求 " + required + "，未来需求 " + future + "；依据 " + basis[0] + " / " + basis[1])

    # 2. 技能雷达现状（未达标在前、已达标在后；与后端 unmet/met 的分类口径一致）
    unmet_summary, met_summary = [], []
    for row in variant["radar"]:
        fact = add("employee_skill",
                   "技能 " + row["skill"] + "：当前 " + row["level"] + "，岗位要求 " + row["required"]
                   + "，未来需求 " + row["future"] + "（" + row["state"] + "）",
                   "证据：" + row["evidence"] + "；雷达评语：" + row["note"])
        item = ("（当前 " + row["level"] + "，岗位要求 " + row["required"] + "，未来需求 "
                + row["future"] + "，" + row["state"] + "，雷达优先级 " + row["severity"] + "）")
        (met_summary if "达标" in row["state"] else unmet_summary).append(row["skill"] + item)
        index["skill"][row["skill"]] = {"row": row, "fact_id": fact["id"]}

    # 3. 考试成绩与错题
    exam_fact = None
    if persona["exam_name"] and persona["exam_score"] is not None:
        wrong = "、".join(persona["wrong_points"]) if persona["wrong_points"] else ""
        exam_fact = add("exam_history",
                        "考试《" + persona["exam_name"] + "》" + fmt(persona["exam_score"]) + " 分（合格线 "
                        + fmt(persona["exam_pass"]) + "，" + ("已通过" if variant["exam_passed"] else "未通过")
                        + "，" + variant["exam_date"] + "）",
                        "无错题记录" if not wrong else "错题知识点：" + wrong)
        index["source"]["exam"] = exam_fact

    # 4. 能力记忆库（必须排掉 source_label = 本 Agent 的旧结论，否则模型会引用自己过去的输出）
    for row in variant["memory"]:
        add("memory_item", row["occurred_at"] + " " + row["type_label"] + "：" + row["title"],
            row["detail"] + "（来源：" + row["source_label"] + "）")

    # 5. 学习计划执行情况
    for row in variant["plans"]:
        add("learning_plan",
            "学习计划《" + row["course"] + "》：目标 " + row["skill"] + " → L" + str(row["target_level"])
            + "，进度 " + str(row["progress"]) + "%",
            "截止 " + row["due_at"])

    # 6. 练习正确率
    for row in variant["practice"]:
        add("practice_stat", "练习统计：" + row["skill"],
            "答对 " + str(row["correct"]) + " / " + str(row["answered"]) + " 题")

    # 7. 证书与复审
    if persona["cert_name"] and persona["cert_level"]:
        add("certificate", "证书《" + persona["cert_name"] + "》" + persona["cert_level"],
            "有效期至 " + persona["cert_expire"] + "，状态 有效")

    # 8. 安全记录（安全不合格在人才决策里优先级最高，必须显式给出）
    record = variant["safety"]
    safety_fact = add("safety_record", "安全记录 " + record["type"] + "（" + record["severity"] + "）",
                      "一票否决=" + ("是" if record["veto"] else "否") + "；" + record["description"])
    index["source"]["safety"] = safety_fact

    # 9. 本人相关的实操检测报告
    add("task_report", "本人相关实操检测报告 " + str(variant["report_total"]) + " 份",
        "其中判定超限 " + str(variant["report_abnormal"]) + " 份")

    # 10. 技能雷达差距汇总：刻意放最后，保证前面 9 组事实的编号（F1…）不变
    gap_fact = add("skill_gap_summary",
                   "技能雷达差距汇总：未达岗位要求的技能共 " + str(len(unmet_summary)) + " 项",
                   "未达标技能：" + "；".join(unmet_summary) + "。已达标技能："
                   + ("；".join(met_summary) if met_summary else "无"))
    index["source"]["gap_summary"] = gap_fact
    return facts, index


def render_facts(facts: list) -> str:
    """DiagnosisPipeline.renderFacts 的逐字复刻：每行 `F1 [source] label；value` + 行分隔符。"""
    return "".join(fact["id"] + " [" + fact["source"] + "] " + fact["label"] + "；" + fact["value"] + SEP
                   for fact in facts)


def render_prompt(facts: list, index: dict, today: str) -> str:
    """PersonalDiagnosisService.userPrompt 的逐字复刻（含 line() 在事实块后多出的一个空行）。"""
    due_example = (date.fromisoformat(today) + timedelta(days=14)).isoformat()
    parts = [
        "【今天】" + today + "（plan.due_at 是计划日期，从今天往后排，例如 " + due_example
        + "；它不参与事实核对）" + SEP,
        "【事实清单】（结论里出现的每个数字都必须在这里找到出处）" + SEP,
        render_facts(facts) + SEP,  # render_facts 每行已带 SEP，这里再加一个 => 事实块后留空行
    ]
    summary_fact = index["source"]["gap_summary"]
    parts += [
        "【本次缺口清单】（来自技能雷达，是 gaps 的唯一来源，不要另找技能）" + SEP,
        "  " + summary_fact["id"] + "：" + summary_fact["value"] + SEP,
        "  gaps 必须正好覆盖「未达标技能」，一项不多、一项不少，顺序照清单排；" + SEP,
        "  「已达标技能」必须写进 summary，并至少出现在一条 reasons 里作为优势项；" + SEP,
        "  写等级差距、考试分数这类句子时，句末标出对应的事实编号。" + SEP,
    ]
    parts += [line + SEP for line in TEMPLATE_LINES]
    return "".join(parts)


# ---------------------------------------------------------------------------
# 四、撰写结论（线上 6 键 B 版）
# ---------------------------------------------------------------------------

def author_output(persona: dict, index: dict, variant: dict, today: str) -> tuple:
    """返回 (payload, meta)。meta 记录 summary/reasons 实际用到的技能，供自查避免子串误判。"""
    base = date.fromisoformat(today)
    scene = narrative_safe(persona["scene"])
    gap_meta = [index["skill"][name] for name in variant["gap_order"]]
    met_meta = [index["skill"][name] for name in variant["met_order"]]
    primary, secondary = gap_meta[0], (gap_meta[1] if len(gap_meta) > 1 else None)
    primary_skill = primary["row"]["skill"]
    secondary_skill = secondary["row"]["skill"] if secondary else ""
    met_names = "、".join(meta["row"]["skill"] for meta in met_meta)
    seed = variant["seed"]

    # ---- gaps：技能/等级/severity/priority 完全来自技能雷达，模型只转述 ----
    gaps = []
    for order, meta in enumerate(gap_meta):
        row = meta["row"]
        gaps.append({
            "skill": row["skill"],
            "current": int(row["level"][1]),
            "required": int(row["required"][1]),
            "future": int(row["future"][1]),
            "severity": row["severity"],
            "priority": "P" + str(min(order + 1, 3)),
            "impact": gap_impact(row, persona, scene, meta),
            "action": gap_action(row, persona, scene, meta, seed),
        })

    # ---- verdict.reasons：每条句末带事实编号；至少一条写优势项；条数收在模板量级（<=5） ----
    gap_reasons = []
    for meta in gap_meta:
        row = meta["row"]
        diff = int(row["required"][1]) - int(row["level"][1])
        gap_reasons.append(row["skill"] + "当前 " + row["level"] + "、岗位要求 " + row["required"]
                           + "，差" + CN_NUM.get(diff, str(diff)) + "级（" + meta["fact_id"] + "）")
    exam_reasons = []
    if "exam" in index["source"]:
        exam = index["source"]["exam"]
        exam_reasons.append("考试《" + persona["exam_name"] + "》" + fmt(persona["exam_score"]) + " 分、合格线 "
                            + fmt(persona["exam_pass"]) + " 分，"
                            + ("已通过" if variant["exam_passed"] else "未通过")
                            + "（" + exam["id"] + "）")
    met_reasons = []
    for meta in met_meta:
        row = meta["row"]
        if row["level"] == "合格":
            met_reasons.append(row["skill"] + "已通过年度资格确认，是本人现有的能力基础（" + meta["fact_id"] + "）")
        else:
            met_reasons.append(row["skill"] + "已达标 " + row["level"] + "，是本人现有的能力基础（"
                               + meta["fact_id"] + "）")
    safety = index["source"]["safety"]
    record = variant["safety"]
    if record["type"] == "无扣分记录":
        safety_reasons = ["安全记录：近 12 个月无扣分、无未遂事件（" + safety["id"] + "）"]
    elif record["veto"]:
        safety_reasons = ["安全记录：近 12 个月存在" + record["type"] + "，属一票否决项，本轮不纳入授权推进（"
                          + safety["id"] + "）"]
    else:
        safety_reasons = ["安全记录：近 12 个月有" + record["type"] + "台账记录，需按班组要求闭环（"
                          + safety["id"] + "）"]
    # 缺口与考试优先保留；优势项与安全至少各留一个位置，条数在 4-6 之间浮动（贴真实模型的输出习惯）
    core = gap_reasons + exam_reasons
    extra = met_reasons + safety_reasons
    target = 4 + (variant["seed"] % 3)
    reasons = core[:max(1, target - 1)] + extra
    reasons = reasons[:target]

    # ---- summary：先交代岗位与优势，再说最大缺口；提到的缺口技能必须都在 gaps 里 ----
    kind = "能力空白" if persona["tenure"] <= 2 else "在岗技能不足"
    flavour = seed % 3
    if flavour == 0:
        summary = (persona["position"] + "目前在" + met_names + "上已具备基础，整体属于" + kind
                   + "：最大缺口是" + primary_skill + "（当前 " + primary["row"]["level"] + "、岗位要求 "
                   + primary["row"]["required"] + "）")
        if secondary:
            summary += "，其次是" + secondary_skill
        summary += "。先补齐" + primary_skill + "再谈向 " + persona["goal_level"] + " 推进。"
    elif flavour == 1:
        summary = ("从岗位要求看，" + persona["position"] + "的" + met_names + "已达到岗位要求，整体属于" + kind
                   + "；最需要补的是" + primary_skill + "（当前 " + primary["row"]["level"] + "、岗位要求 "
                   + primary["row"]["required"] + "）")
        summary += ("，" + secondary_skill + "紧随其后。建议先把" + primary_skill + "的规则知识与现场验证补齐。"
                    if secondary else "。建议先把" + primary_skill + "的规则知识与现场验证补齐。")
    else:
        summary = (persona["position"] + "的能力结构属于" + kind + "：" + met_names + "是已达标的基础项，"
                   + primary_skill + "（当前 " + primary["row"]["level"] + "、岗位要求 " + primary["row"]["required"]
                   + "）是最大缺口")
        summary += ("，" + secondary_skill + "次之。下一步应以" + primary_skill + "为主线推进。"
                    if secondary else "。下一步应以" + primary_skill + "为主线推进。")

    headlines = [
        primary_skill + "是最大缺口，先补" + primary_skill + "的规则知识再进现场验证。",
        "以" + primary_skill + "为主线补齐差距，" + met_meta[0]["row"]["skill"] + "的基础可支撑后续带教。",
        primary_skill + "的等级差距最影响独立作业，先补" + primary_skill + "再谈向 "
        + persona["goal_level"] + " 申请评定。",
    ]

    return {
        "summary": summary,
        "confidence": variant["confidence"],
        "verdict": {"headline": headlines[seed % len(headlines)], "reasons": reasons},
        "gaps": gaps,
        "plan": build_plan(persona, primary, secondary, base, variant, scene),
        "compound_path": build_compound(persona, primary, secondary, variant),
    }, {"summary_skills": [primary_skill, secondary_skill] + [m["row"]["skill"] for m in met_meta],
        "gap_skills": [m["row"]["skill"] for m in gap_meta],
        "met_skills": [m["row"]["skill"] for m in met_meta]}


def gap_impact(row: dict, persona: dict, scene: str, meta: dict) -> str:
    """impact 只写业务后果，数字只用中文（避免出现事实清单之外的可疑数字）。"""
    diff = int(row["required"][1]) - int(row["level"][1])
    templates = [
        row["skill"] + "当前 " + row["level"] + "、岗位要求 " + row["required"] + "，差"
        + CN_NUM.get(diff, str(diff)) + "级，本人还不能独立承担相关作业，关键步骤必须由师傅复核后才可执行。",
        row["skill"] + "未达岗位要求（当前 " + row["level"] + "），在" + (scene or "现场作业")
        + "中需要他人全程监护，无法计入可授权范围。",
        "由于" + row["skill"] + "只到 " + row["level"] + "，" + (scene or "现场作业")
        + "中的判定结论仍需师傅二次确认，影响闭环时效。",
    ]
    return templates[stable_hash(persona["position"] + row["skill"] + str(meta["fact_id"])) % len(templates)]


def gap_action(row: dict, persona: dict, scene: str, meta: dict, seed: int) -> str:
    """action 写下一步可执行动作，不含数字。"""
    templates = [
        "围绕" + row["skill"] + "的错题逐题归因，补齐规则知识后由师傅在" + (scene or "现场作业")
        + "中带教验证，经复核通过再申请等级评定。",
        "先完成" + row["skill"] + "的知识点梳理与口述，再在" + (scene or "现场作业")
        + "中完成受监护实操，形成带签字的验证记录。",
        "按技能雷达要求补齐" + row["skill"] + "的课程学习与带教任务，通过模拟考后由班组长复核确认。",
    ]
    return templates[(stable_hash(row["skill"] + persona["position"] + str(meta["fact_id"])) + seed) % len(templates)]


def build_plan(persona: dict, primary: dict, secondary, base: date, variant: dict, scene: str) -> list:
    """3 步（单缺口）或 4 步（多缺口）；due_at 晚于今天且严格递增，各步 reason 互不复读。"""
    row = primary["row"]
    skill = row["skill"]
    high = int(row["required"][1])
    mid = min(high, int(row["level"][1]) + 1)
    gap = variant["plan_gap"]
    steps = [
        {"step": 1, "kind": "课程", "title": skill + "错题归因与规则知识补齐", "target_skill": skill,
         "to_level": "L" + str(mid), "due_at": (base + timedelta(days=gap)).isoformat(),
         "reason": "错题暴露的是" + skill + "的判定规则没有形成稳定检查点，先把知识补齐，后面的带教才有可验证的对象。"},
        {"step": 2, "kind": "带教", "title": skill + "现场跟做与要点确认", "target_skill": skill,
         "to_level": "L" + str(high), "due_at": (base + timedelta(days=gap * 2)).isoformat(),
         "reason": "课堂知识必须在真实作业里验证，由师傅在" + (scene or "现场作业") + "中带教完整流程，确认动作没有走形。"},
        {"step": 3, "kind": "模拟考", "title": skill + "理论考试与授权边界口述", "target_skill": skill,
         "to_level": "L" + str(high), "due_at": (base + timedelta(days=gap * 3)).isoformat(),
         "reason": "用模拟考确认缺口是否真的补上，验证通过后才具备申请等级评定的证据。"},
    ]
    if secondary is not None:
        second = secondary["row"]
        steps.append({
            "step": 4, "kind": "课程", "title": second["skill"] + "基础补齐", "target_skill": second["skill"],
            "to_level": "L" + str(int(second["required"][1])),
            "due_at": (base + timedelta(days=gap * 4)).isoformat(),
            "reason": second["skill"] + "的差距比主线小，安排在主线收口之后再集中补齐，避免两门课程互相挤占时间。",
        })
    return steps


def build_compound(persona: dict, primary: dict, secondary, variant: dict) -> dict:
    """3 个阶段（单缺口）或 4 个阶段（多缺口）；why 与 benefit 不得互相摘抄。"""
    row = primary["row"]
    skill = row["skill"]
    mid = min(int(row["required"][1]), int(row["level"][1]) + 1)
    second_skill = secondary["row"]["skill"] if secondary else ""
    title = (skill + "与" + second_skill + "复合提升路线") if secondary else (skill + "专项提升路线")
    if secondary:
        why = ("两项缺口都落在现场作业的同一段流程上，共用同一套安规与判据底子，"
               "合并推进能省下一次重复的安全交底与复训。")
    else:
        why = skill + "是当前岗位要求里唯一的缺口项，集中一条线推进，避免被其他任务切碎注意力。"
    stages = [
        {"phase": "第 1 阶段 · 0-2 个月", "focus": skill + " 从 " + row["level"] + " 到 L" + str(mid),
         "skills": "判定规则、错题归因、作业前条件确认",
         "milestone": skill + " 规则知识达到 L" + str(mid) + "（课程结业）"},
        {"phase": "第 2 阶段 · 2-4 个月", "focus": skill + " 在真实作业中的受监护验证",
         "skills": "现场跟做、要点口述、记录留痕",
         "milestone": skill + " 现场作业达到 " + row["required"]},
    ]
    if secondary:
        second = secondary["row"]
        stages.append({"phase": "第 3 阶段 · 4-6 个月", "focus": second["skill"] + " 追赶岗位要求",
                       "skills": second["skill"] + " 课程与带教验证",
                       "milestone": second["skill"] + " 达到 " + second["required"]})
    stages.append({"phase": "第 " + str(len(stages) + 1) + " 阶段 · 收口", "focus": "缺口项合并验收",
                   "skills": "综合模拟考、过程留痕复核", "milestone": "班组长复核通过并进入等级评定"})
    benefit = ("路线走完后，本人可以在" + (persona["scene"] or "现场作业") + "中独立完成" + skill
               + "的判断与处置，不再依赖师傅逐项复核，也具备向 " + persona["goal_level"] + " 申请评定的材料。")
    return {"title": title, "why": why, "stages": stages, "benefit": benefit}


# ---------------------------------------------------------------------------
# 五、契约校验（DiagnosisContract / DiagnosisPipeline 的 Python 移植）
# ---------------------------------------------------------------------------

IGNORED = re.compile(r"F[0-9]+|L[1-5]|第[0-9]+步|[0-9]{4}-[0-9]{2}-[0-9]{2}")
NUMBER = re.compile(r"[0-9]+(?:[.][0-9]+)?")
NARRATIVE = [["summary"], ["verdict", "headline"], ["verdict", "label"], ["verdict", "reasons"],
             ["verdict", "evidence"], ["gaps", "impact"], ["plan", "reason"], ["findings", "title"],
             ["findings", "impact"], ["findings", "evidence"], ["compound_path", "why"]]


def jnum(value: float) -> str:
    """Java：整数走 String.valueOf(long)，小数走 Double.toString（最短往返表示）。"""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def normalize(value: str) -> str:
    try:
        return jnum(float(value))
    except ValueError:
        return value


def numbers_of(text: str) -> set:
    return {normalize(match.group(0)) for match in NUMBER.finditer(IGNORED.sub(" ", text or ""))}


def add_derived(allowed: set) -> set:
    """与 DiagnosisContract.addDerived 同口径：允许「由事实算出来的」和/差/商/占比。"""
    base = []
    for value in allowed:
        try:
            parsed = float(value)
            if abs(parsed) <= 100000:
                base.append(parsed)
        except ValueError:
            continue
    if len(base) < 2 or len(base) > 80:
        return allowed
    for left in base:
        for right in base:
            allowed.add(normalize(jnum(left + right)))
            allowed.add(normalize(jnum(abs(left - right))))
            if right != 0:
                allowed.add(normalize(jnum(round(left * 100 / right))))
                allowed.add(normalize(jnum(left / right)))
    return allowed


def collect(node, path, texts):
    if node is None:
        return
    if not path:
        if isinstance(node, list):
            texts.extend(str(item) for item in node if item is not None)
        else:
            texts.append(str(node))
        return
    if isinstance(node, dict):
        collect(node.get(path[0]), path[1:], texts)
    elif isinstance(node, list):
        for item in node:
            collect(item, path, texts)


def contract_errors(payload) -> list:
    """validatePersonal 的移植：字段缺失、类型、枚举、范围、去重。"""
    errors = []
    if not isinstance(payload, dict):
        return ["结论为空"]

    def blank(value):
        return value is None or (isinstance(value, str) and not value.strip())

    def need_text(container, field, where):
        if field not in container or blank(container[field]):
            errors.append(where + "." + field + " 缺失或为空")

    need_text(payload, "summary", "根")
    conf = payload.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
        errors.append("根.confidence 必须是 0-1 之间的小数")

    verdict = payload.get("verdict")
    if not isinstance(verdict, dict):
        errors.append("根.verdict 必须是对象")
    else:
        need_text(verdict, "headline", "verdict")
        reasons = verdict.get("reasons")
        if not isinstance(reasons, list) or not reasons:
            errors.append("verdict.reasons 必须是非空数组")
        elif any(blank(item) for item in reasons):
            errors.append("verdict.reasons 存在空条目")

    gaps = payload.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        errors.append("根.gaps 必须是非空数组")
    else:
        seen = set()
        for pos, gap in enumerate(gaps):
            where = "gaps[" + str(pos) + "]"
            if not isinstance(gap, dict):
                errors.append(where + " 数组元素必须是对象")
                continue
            for field in ("skill", "impact", "action"):
                need_text(gap, field, where)
            for field in ("current", "required", "future"):
                value = gap.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                    errors.append(where + "." + field + " 必须是 1-5 的整数")
            if gap.get("severity") not in SEVERITIES:
                errors.append(where + ".severity 枚举越界")
            if gap.get("priority") not in ("P1", "P2", "P3"):
                errors.append(where + ".priority 枚举越界")
            if gap.get("skill") in seen:
                errors.append(where + ".skill 重复出现")
            seen.add(gap.get("skill"))

    plan = payload.get("plan")
    if not isinstance(plan, list) or not plan:
        errors.append("根.plan 必须是非空数组")
    else:
        for pos, step in enumerate(plan):
            where = "plan[" + str(pos) + "]"
            if not isinstance(step, dict):
                errors.append(where + " 数组元素必须是对象")
                continue
            if not isinstance(step.get("step"), int) or isinstance(step.get("step"), bool) or step["step"] < 1:
                errors.append(where + ".step 必须是正整数")
            if step.get("kind") not in KINDS:
                errors.append(where + ".kind 枚举越界")
            for field in ("title", "target_skill", "reason"):
                need_text(step, field, where)
            if not re.fullmatch(r"L[1-5]", str(step.get("to_level", ""))):
                errors.append(where + ".to_level 格式不合法")
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", str(step.get("due_at", ""))):
                errors.append(where + ".due_at 格式不合法")

    compound = payload.get("compound_path")
    if not isinstance(compound, dict):
        errors.append("根.compound_path 必须是对象")
    else:
        for field in ("title", "why", "benefit"):
            need_text(compound, field, "compound_path")
        stages = compound.get("stages")
        if not isinstance(stages, list) or not stages:
            errors.append("compound_path.stages 必须是非空数组")
        else:
            for pos, stage in enumerate(stages):
                where = "compound_path.stages[" + str(pos) + "]"
                if not isinstance(stage, dict):
                    errors.append(where + " 数组元素必须是对象")
                    continue
                for field in ("phase", "focus", "skills", "milestone"):
                    need_text(stage, field, where)
    return errors


def unverified(payload: dict, facts: list) -> list:
    """unverifiedNumbers 的移植：叙述字段里出现、但事实清单里查不到的数字。"""
    allowed = set()
    for fact in facts:
        allowed |= numbers_of(fact["label"] + " " + fact["value"])
    add_derived(allowed)
    texts = []
    for path in NARRATIVE:
        collect(payload, path, texts)
    out, seen = [], set()
    for text in texts:
        for match in NUMBER.finditer(IGNORED.sub(" ", text)):
            value = normalize(match.group(0))
            if value in allowed or value in seen:
                continue
            seen.add(value)
            out.append(value + " ← " + text[:24])
            if len(out) >= 20:
                return out
    return out


def overlap(left: str, right: str) -> float:
    """最长公共子串占比，与 DiagnosisPipeline.overlap 同口径。"""
    if not left or not right:
        return 0.0
    previous = [0] * (len(right) + 1)
    longest = 0
    for i in range(1, len(left) + 1):
        current = [0] * (len(right) + 1)
        for j in range(1, len(right) + 1):
            if left[i - 1] == right[j - 1]:
                current[j] = previous[j - 1] + 1
                longest = max(longest, current[j])
        previous = current
    return longest / min(len(left), len(right))


def prefix_len(left: str, right: str) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def polish_errors(payload: dict, today: str) -> list:
    """polishPersonal 的不变式：样本必须「不需要被改写」，否则线上结论会被后端再改一遍。"""
    errors = []
    base = date.fromisoformat(today)
    previous = None
    for pos, step in enumerate(payload["plan"]):
        due = date.fromisoformat(step["due_at"])
        if not due > base:
            errors.append("plan[" + str(pos) + "].due_at 不晚于今天（会被 polish 重排）")
        if previous is not None and not due > previous:
            errors.append("plan[" + str(pos) + "].due_at 未严格递增（会被 polish 重排）")
        previous = due
    seen = []
    for pos, step in enumerate(payload["plan"]):
        reason = step["reason"]
        for old in seen:
            if overlap(old, reason) >= 0.8 or prefix_len(old, reason) >= 24:
                errors.append("plan[" + str(pos) + "].reason 与前面某步复读（会被 polish 改写）")
                break
        seen.append(reason)
    compound = payload["compound_path"]
    if overlap(compound["why"], compound["benefit"]) >= 0.5:
        errors.append("compound_path.benefit 与 why 互相摘抄（会被 polish 改写）")
    return errors


def rule_errors(payload: dict, meta: dict) -> list:
    """提示词里那几条「模型最容易违反」的软规则，用 authoring meta 精确自查（避免子串误判）。"""
    errors = []
    for reason in payload["verdict"]["reasons"]:
        if not re.search(r"F[0-9]+", reason):
            errors.append("reasons 未标注事实编号：" + reason[:20])
    reasons_text = " ".join(payload["verdict"]["reasons"])
    if not any(skill in reasons_text for skill in meta["met_skills"]):
        errors.append("reasons 里没有写已达标/已持证的优势项")
    for skill in meta["met_skills"]:
        if skill not in payload["summary"]:
            errors.append("summary 未交代优势项：" + skill)
    gap_set = set(meta["gap_skills"])
    for skill in meta["summary_skills"]:
        if not skill:
            continue
        if skill not in gap_set and skill not in meta["met_skills"]:
            errors.append("summary 引用了既不在 gaps 也不在优势项的技能：" + skill)
    # 提示词 rule 11 是单向约束（summary 提到的缺口必须在 gaps 里），并不要求 summary 覆盖全部缺口；
    # 只要求最大缺口（gaps 第 1 条）必须出现在 summary，这是 rule 8「最大缺口是什么」的硬要求。
    if meta["gap_skills"] and meta["gap_skills"][0] not in payload["summary"]:
        errors.append("summary 未提到最大缺口：" + meta["gap_skills"][0])
    for gap in payload["gaps"]:
        if gap["severity"] not in SEVERITIES:
            continue
    order = [SEVERITIES.index(gap["severity"]) for gap in payload["gaps"]]
    if order != sorted(order):
        errors.append("gaps 未按 severity 从高到低排列（会被 applyRadarPriority 重排）")
    for pos, gap in enumerate(payload["gaps"]):
        if gap["priority"] != "P" + str(min(pos + 1, 3)):
            errors.append("gaps[" + str(pos) + "].priority 与排序后编号不一致")
    if len(payload["plan"]) not in (3, 4):
        errors.append("plan 步数不是 3-4")
    if len(payload["compound_path"]["stages"]) not in (3, 4):
        errors.append("stages 个数不是 3-4")
    return errors


# ---------------------------------------------------------------------------
# 六、变体与主流程
# ---------------------------------------------------------------------------

SAFETY_POOL = [
    {"type": "无扣分记录", "severity": "LOW", "veto": False,
     "description": "近12个月无安全扣分和未遂事件，现场安措执行记录完整。"},
    {"type": "安全扣分", "severity": "MEDIUM", "veto": False,
     "description": "近12个月因漏填一项风险预控措施扣2分，未造成设备或人身后果。"},
    {"type": "未遂事件", "severity": "HIGH", "veto": False,
     "description": "近12个月曾在夜间巡视中靠近异常发热点，因同伴提醒及时退回，形成1起未遂事件。"},
    {"type": "越权操作", "severity": "HIGH", "veto": True,
     "description": "近12个月曾在师傅未到场时尝试修改监控告警屏蔽条件，被及时制止，未改变运行状态。"},
    {"type": "无票作业", "severity": "HIGH", "veto": True,
     "description": "近12个月曾参与一次无票拆接二次端子排的违章作业，未造成保护误动，已完成班组通报。"},
    {"type": "未监护", "severity": "MEDIUM", "veto": False,
     "description": "近12个月曾在带教任务中未等监护人到位就开始仪器接线，被班组长叫停。"},
]

# 已达标优势项技能池：不含安全规程（它单独处理），并保证与盲区不冲突。
MET_POOL = ["倒闸操作", "设备巡视", "工器具管理", "两票执行", "设备台账核对"]


def make_variant(persona: dict, rng: random.Random) -> dict:
    """给一份档案抽一组「事实组合」：缺口数量、等级、考试结果、安全记录、日期、措辞种子。"""
    blind = persona["blind"] or rng.choice(MET_POOL)
    task_skill = persona["task_skill"]
    pool = [s for s in (task_skill,) + tuple(MET_POOL) if s and s != blind]

    gap_count = rng.choice([1, 2, 2, 3])
    gap_skills = [blind]
    for candidate in pool:
        if candidate not in gap_skills:
            gap_skills.append(candidate)
        if len(gap_skills) >= gap_count:
            break
    gap_skills = gap_skills[:gap_count]

    # 雷达：缺口行（未达标，未达标在前） + 优势行（已达标，在后）
    radar = []
    for order, skill in enumerate(gap_skills):
        if order == 0:
            required, future = rng.choice([("L3", "L3"), ("L2", "L3"), ("L3", "L4")])
            level = rng.choice(["L1", "L1", "L2"])
            severity = "HIGH"
        elif order == 1:
            required, future = rng.choice([("L2", "L3"), ("L3", "L3")])
            level, severity = "L1", "MEDIUM"
        else:
            required, future = "L2", "L2"
            level, severity = "L1", "LOW"
        radar.append({
            "skill": skill, "level": level, "required": required, "future": future, "state": "",
            "severity": severity,
            "evidence": (persona["scene"] or "现场作业") + "中的实操与考试成绩" if order == 0
            else "近 6 个月带教记录与练习统计",
            "note": (persona["mentor_comment"] or "基础动作已具备，判定规则仍不稳定") if order == 0
            else "现场跟做次数不足，尚无独立作业记录",
        })
    for row in radar:
        row["state"] = "差 " + str(int(row["required"][1]) - int(row["level"][1])) + " 级"

    # 优势项：必须至少 1 条（summary 要交代优势，reasons 要有一条优势依据）
    met_order = []
    met_candidates = [s for s in MET_POOL if s not in gap_skills and s != SAFETY_SKILL]
    rng.shuffle(met_candidates)
    for name in met_candidates:
        if name in met_order:
            continue
        met_order.append(name)
        if len(met_order) >= rng.choice([1, 1, 2]):
            break
    met_order.append(SAFETY_SKILL)
    for name in met_order:
        if name == SAFETY_SKILL:
            radar.append({"skill": name, "level": "合格", "required": "合格", "future": "合格",
                          "state": "已达标", "severity": "LOW",
                          "evidence": persona["safe_pass_at"] or "年度资格确认记录",
                          "note": "年度合格，未出现超期或扣分记录"})
        else:
            radar.append({"skill": name, "level": "L3", "required": "L3", "future": "L3",
                          "state": "已达标", "severity": "LOW",
                          "evidence": "已持证并在有效期内", "note": "岗位要求已满足，可承担授权作业"})

    # 岗位技能要求：缺口技能各一条 + 安全规程（合格/合格），与线上表结构一致
    requirements = []
    for row in radar[:len(gap_skills)]:
        requirements.append((row["skill"], row["required"], row["future"],
                             rng.choice(BASIS_POOL)))
    requirements.append((SAFETY_SKILL, "合格", "合格", SAFETY_BASIS))

    today = rng.choice(TODAYS)
    # 考试结论必须与分数自洽（线上由 result 字段决定，这里按分数与合格线推导，避免「58 分已通过」这种自相矛盾）
    exam_passed = (persona["exam_score"] is not None and persona["exam_pass"] is not None
                   and persona["exam_score"] >= persona["exam_pass"])
    exam_day = date.fromisoformat(today) - timedelta(days=rng.choice([12, 26, 41]))
    exam_date = exam_day.isoformat() + " " + "%02d:%02d" % (rng.randint(9, 17), rng.choice([0, 20, 35, 40, 55]))
    safety = dict(rng.choice(SAFETY_POOL))

    # 能力记忆库：用真实表里的 type_label / source_label 口径；绝不写「个人学习 Agent」来源
    memory = [
        {"occurred_at": (date.fromisoformat(today) - timedelta(days=9)).isoformat(),
         "type_label": "带教记忆", "source_label": "师傅评价",
         "title": persona["mentor_comment"] or "现场带教后基础动作已具备",
         "detail": persona["mentor_advice"] or "先完成错题归因和授权边界口述，再安排带教验证"},
        {"occurred_at": (date.fromisoformat(today) - timedelta(days=16)).isoformat(),
         "type_label": "实操记忆", "source_label": "班组长评分",
         "title": persona["team_comment"] or "可以承担常规任务，复杂场景需提前报告",
         "detail": "班组协作分 " + str(persona["coop_score"]) + "，安全意识分 " + str(persona["safety_score"])},
    ]
    if persona["exam_name"] and persona["exam_score"] is not None:
        memory.append({
            "occurred_at": (date.fromisoformat(today) - timedelta(days=23)).isoformat(),
            "type_label": "考试记忆", "source_label": "考试中心",
            "title": persona["exam_name"] + " " + fmt(persona["exam_score"]) + " 分（合格线 "
                     + fmt(persona["exam_pass"]) + "）",
            "detail": "错题已归档，等待错题复盘" if persona["wrong_points"] else "无错题记录"})
    if persona["practice_skill"]:
        memory.append({
            "occurred_at": (date.fromisoformat(today) - timedelta(days=31)).isoformat(),
            "type_label": "实操记忆", "source_label": "任务台账",
            "title": persona["practice_skill"] + "任务完成记录",
            "detail": "计划 " + fmt(persona["planned_hours"]) + "小时，实际 " + fmt(persona["actual_hours"]) + "小时"})
    memory.append({
        "occurred_at": (date.fromisoformat(today) - timedelta(days=38)).isoformat(),
        "type_label": "学习记忆", "source_label": "学习总版",
        "title": persona["behavior"] or "完成事实-风险-请求汇报",
        "detail": "由带教师傅按行为规范逐项确认，已计入带教台账"})
    if safety["veto"] or safety["severity"] == "HIGH":
        memory.append({
            "occurred_at": (date.fromisoformat(today) - timedelta(days=53)).isoformat(),
            "type_label": "错误记忆", "source_label": "安全稽查",
            "title": "安全记录：" + safety["type"], "detail": safety["description"]})
    memory = memory[:6]

    plans = []
    for order in range(rng.choice([0, 1, 2])):
        plans.append({
            "course": gap_skills[order % len(gap_skills)] + "专项课程",
            "skill": gap_skills[order % len(gap_skills)],
            "target_level": rng.choice([2, 3]),
            "progress": rng.choice([20, 40, 60, 80]),
            "due_at": (date.fromisoformat(today) + timedelta(days=rng.choice([30, 45, 60]))).isoformat()})

    practice = []
    if persona["exam_name"]:
        answered = rng.choice([20, 24, 30, 40])
        practice.append({"skill": persona["exam_name"], "answered": answered,
                         "correct": max(6, answered - rng.choice([4, 7, 9, 12]))})

    return {
        "radar": radar, "requirements": requirements, "gap_order": gap_skills, "met_order": met_order,
        "exam_passed": exam_passed, "exam_date": exam_date,
        "memory": memory, "plans": plans, "practice": practice, "safety": safety,
        "confidence": round(rng.uniform(0.72, 0.93), 2),
        "report_total": rng.choice([2, 3, 4, 5]), "report_abnormal": rng.choice([0, 0, 1, 1, 2]),
        "plan_gap": rng.choice([12, 14, 21]), "seed": rng.randint(0, 99999), "today": today,
    }


def build_sample(persona: dict, rng: random.Random) -> tuple:
    variant = make_variant(persona, rng)
    facts, index = build_facts(persona, variant)
    prompt = render_prompt(facts, index, variant["today"])
    payload, meta = author_output(persona, index, variant, variant["today"])

    errors = []
    errors += ["契约:" + item for item in contract_errors(payload)]
    errors += ["数字:" + item for item in unverified(payload, facts)]
    errors += ["规范:" + item for item in polish_errors(payload, variant["today"])]
    errors += ["规则:" + item for item in rule_errors(payload, meta)]
    if errors:
        return None, errors, facts, variant["today"]

    sample = {
        "system": SYSTEM_PROMPT,
        "instruction": "",
        "input": prompt,
        "output": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }
    return sample, [], facts, variant["today"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--src", default=SRC)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--dump-verify", default="",
                        help="把每条的事实清单与 output 另存一份，供后端 DiagnosisContract 逐条核验")
    args = parser.parse_args()

    with open(args.src, encoding="utf-8") as handle:
        source = json.load(handle)
    personas = [parse_persona(item["input"]) for item in source]
    broken = [i for i, p in enumerate(personas) if not p["position"] or not p["blind"]]
    if broken:
        print("警告：以下档案解析不完整", broken[:10], file=sys.stderr)

    rng = random.Random(args.seed)
    samples, rejected, verify_cases = [], [], []
    attempt = 0
    while len(samples) < args.count and attempt < args.count * 15:
        persona = personas[attempt % len(personas)]
        attempt += 1
        sample, errors, facts, today = build_sample(persona, rng)
        if sample is None:
            rejected.append((attempt, errors[:3]))
            continue
        samples.append(sample)
        if args.dump_verify:
            verify_cases.append({
                "today": today,
                "facts": [{"label": fact["label"], "value": fact["value"]} for fact in facts],
                "payload": json.loads(sample["output"]),
            })

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(samples, handle, ensure_ascii=False, indent=1)
    if args.dump_verify:
        with open(args.dump_verify, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(verify_cases, handle, ensure_ascii=False, indent=1)
        print("  核验用例      :", args.dump_verify)

    payloads = [json.loads(item["output"]) for item in samples]
    inputs = sorted(len(item["input"]) for item in samples)
    print("生成完成：", args.out)
    print("  样本数        :", len(samples))
    print("  尝试次数      :", attempt, " 被拒:", len(rejected))
    print("  input 字符数  : 中位", inputs[len(inputs) // 2], " 最小", inputs[0], " 最大", inputs[-1])
    print("  唯一 prompt 数:", len({item["input"] for item in samples}))
    print("  唯一档案数    :", len({item["input"][:120] for item in samples}))
    print("  gaps 条数分布 :", {n: sum(1 for p in payloads if len(p["gaps"]) == n) for n in (1, 2, 3)})
    print("  plan 步数分布 :", {n: sum(1 for p in payloads if len(p["plan"]) == n) for n in (3, 4)})
    print("  stages 分布   :", {n: sum(1 for p in payloads if len(p["compound_path"]["stages"]) == n) for n in (3, 4)})
    for item in rejected[:5]:
        print("  被拒样例:", item)

    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            "E:/models/models/Qwen--Qwen2.5-7B-Instruct/snapshots/master", trust_remote_code=True)
        lengths = sorted(len(tokenizer.encode(item["system"] + item["input"] + item["output"])) for item in samples)
        print("  单条 token 数 : 中位", lengths[len(lengths) // 2], " 最大", lengths[-1],
              "（cutoff_len 建议 >= 4096）")
    except Exception as error:  # noqa: BLE001
        print("  （跳过 token 统计：", type(error).__name__, str(error)[:60], "）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
