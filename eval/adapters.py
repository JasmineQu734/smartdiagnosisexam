# -*- coding: utf-8 -*-
"""
事实适配层（fact adapter）。

论文与项目文档都要求「同一个 scene 只允许一个事实来源」。本文件把
my_data15.json 里的 150 条真实个人档案文本，按**确定性、只读输入**的方式
解析成三个场景的 facts，供 RuleEngine 回放：

  PERSONAL_GAP   -> 证书等级 / 关键任务授权门槛 / 职业目标等级 / 安全负例 / 岗位匹配度
  EXAM_RESULT    -> 考试分 / 合格线 / 错题知识点
  REPORT_ANALYSIS-> 实操超时比 / 技能缺失 / 是否按 SOP 准备

适配层不读取、也不依赖任何模型输出，保证「归因输入不含上一轮结论」。
"""
from __future__ import annotations

import re
from decimal import Decimal

# L1..L5 与职业技能等级（国家职业技能标准）的对应，来自 docs/diagnosis_schema.json 的 level_mapping 口径
LEVEL_STD = {1: "五级/初级工", 2: "四级/中级工", 3: "三级/高级工", 4: "二级/技师", 5: "一级/高级技师"}

# 安全记录枚举 -> 风险档位。授权类违规（越权 / 无票 / 未监护）判最高档。
SAFETY_ENUM = {
    "无扣分记录": 0,
    "安全扣分": 1,
    "未遂事件": 1,
    "越权操作": 2,
    "无票作业": 2,
    "未监护": 2,
}
SAFETY_AUTH_VIOLATIONS = {"越权操作", "无票作业", "未监护"}


def _one(pat: str, t: str, default=None):
    m = re.search(pat, t)
    return m.group(1).strip() if m else default


def _level(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"L([1-5])", s)
    return int(m.group(1)) if m else None


def parse_profile(text: str) -> dict:
    """把一段档案文本解析成结构化的原始字段（不做任何业务判断）。"""
    p = {}
    p["name"] = _one(r"姓名：([^｜]+)", text)
    p["position"] = _one(r"岗位：([^｜]+)", text)
    p["team"] = _one(r"部门/班组：([^｜]+)", text)
    p["years"] = _one(r"工龄：(\d+)", text)
    p["years"] = int(p["years"]) if p["years"] else None
    p["cert_level"] = _level(_one(r"证书：([^｜]+)", text))
    p["cert_expire"] = _one(r"预计到期日(\d{4}-\d{2}-\d{2})", text)
    p["safety_pass_date"] = _one(r"安全规程年度合格日期：(\d{4}-\d{2}-\d{2})", text)
    p["goal_level"] = _level(_one(r"目标等级：(L[1-5])", text))
    p["goal_years"] = _one(r"计划年限：(\d+)", text)
    p["key_task"] = _one(r"关键任务：([^，；]+)", text)
    p["key_task_level"] = _level(p["key_task"] or "")
    p["mentor"] = _one(r"带教师傅：([^｜]+)", text)
    p["mentor_review"] = _one(r"师傅评价｜带教师傅：[^｜]+｜评价：([^｜]+)", text)
    p["mentor_advice"] = _one(r"建议：([^｜]+)", text)
    p["team_score"] = _one(r"班组协作分：(\d+)", text)
    p["safety_score"] = _one(r"安全意识分：(\d+)", text)
    p["duty_score"] = _one(r"责任心分：(\d+)", text)
    p["post_match"] = _one(r"当前岗位匹配度：(\d+)", text)
    p["post_match"] = int(p["post_match"]) if p["post_match"] else None
    p["compound_match"] = _one(r"复合型方向匹配度：(\d+)", text)
    p["scene"] = _one(r"场景：([^｜]+)", text)
    p["blind_spot"] = _one(r"技能树盲区：([^｜]+)", text)
    p["soft_gap"] = _one(r"软技能短板：([^｜]+)", text)
    p["behaviour_baseline"] = _one(r"可观察行为基线：([^｜]+)", text)
    p["exam_name"] = _one(r"考试与错题：([^，]+?)考试(\d+)分", text)
    p["exam_score"] = _one(r"考试(\d+)分", text)
    p["exam_score"] = int(p["exam_score"]) if p["exam_score"] else None
    p["pass_score"] = _one(r"合格线(\d+)分", text)
    p["pass_score"] = int(p["pass_score"]) if p["pass_score"] else None
    p["knowledge_points"] = re.findall(r"知识点：([^；｜]+)", text)
    p["task_name"] = _one(r"实操任务：([^计]+)计划", text)
    p["planned_hours"] = _one(r"计划([\d.]+)小时", text)
    p["planned_hours"] = Decimal(p["planned_hours"]) if p["planned_hours"] else None
    p["actual_hours"] = _one(r"实际([\d.]+)小时", text)
    p["actual_hours"] = Decimal(p["actual_hours"]) if p["actual_hours"] else None
    p["safety_text"] = _one(r"安全记录：([^｜]+)", text)
    p["safety_type"] = None
    for k in SAFETY_ENUM:
        if p["safety_text"] and k in p["safety_text"]:
            p["safety_type"] = k
            break
    if p["safety_type"] is None and p["safety_text"]:
        p["safety_type"] = "无扣分记录" if "无扣分" in p["safety_text"] else "其他"
    p["safety_risk"] = SAFETY_ENUM.get(p["safety_type"], 0)
    p["mentor_review_count"] = _one(r"复核(\d+)次", text)
    p["mentor_review_count"] = int(p["mentor_review_count"]) if p["mentor_review_count"] else 0
    return p


# --------------------------------------------------------------- 场景 facts

def facts_personal_gap(p: dict) -> dict:
    """岗位技能差距场景：站在「证书所载技能」这条轴上取事实。"""
    return {
        "current_level": p["cert_level"],
        "required_level": p["key_task_level"],     # 岗位对该关键任务的授权门槛，取自档案原文
        "future_level": p["goal_level"],           # 职业目标等级
        "post_match": p["post_match"],
        "years": p["years"],
        "safety_risk": p["safety_risk"],
        "safety_violation": p["safety_risk"] > 0,
        "auth_violation": p["safety_type"] in SAFETY_AUTH_VIOLATIONS,
        "skill_missing": bool(p["blind_spot"]),
        "soft_skill_missing": bool(p["soft_gap"]),
    }


def facts_exam_result(p: dict) -> dict:
    return {
        "score": p["exam_score"],
        "pass_score": p["pass_score"],
        "knowledge_points": p["knowledge_points"],
    }


def facts_report_analysis(p: dict) -> dict:
    ratio = None
    if p["planned_hours"] and p["actual_hours"] and p["planned_hours"] > 0:
        ratio = (p["actual_hours"] / p["planned_hours"]).quantize(Decimal("0.0001"))
    # SOP 执行从安全记录反推：授权类违规即视为未按 SOP 准备
    sop_ok = p["safety_type"] not in SAFETY_AUTH_VIOLATIONS if p["safety_type"] else None
    return {
        "actual_hours_ratio": ratio,
        "skill_missing": bool(p["blind_spot"]),
        "sop_preparation": sop_ok,
        "safety_risk": p["safety_risk"],
    }


SCENES = {
    "PERSONAL_GAP": facts_personal_gap,
    "EXAM_RESULT": facts_exam_result,
    "REPORT_ANALYSIS": facts_report_analysis,
}


def build_facts(p: dict, scene: str) -> dict:
    return SCENES[scene](p)


# --------------------------------------------------------------- 气体场景网格

GASES = ["SF6", "H2S", "SO2", "CO", "O2"]
KEYWORD_SETS = {
    "leak": ["泄漏", "压力下降"],
    "decomp": ["异味", "分解"],
    "heat": ["过热", "温升"],
    "pd": ["放电", "异响"],
    "moisture": ["受潮", "凝露"],
    "health": ["头晕", "不适"],
    "worsening": ["持续", "加剧"],
    "none": ["运行正常"],
}


def gas_grid():
    """生成气体检测场景的参数网格，用于验证分组收敛 / 命中上限 / 严重度合并语义。"""
    cases = []
    for gas in GASES:
        for ratio in ["0.35", "0.10", "0.02", "-0.05", "-0.40"]:
            for kw_name, kws in KEYWORD_SETS.items():
                r = Decimal(ratio)
                cases.append({
                    "case_id": f"{gas}|r={ratio}|kw={kw_name}",
                    "facts": {
                        "gas": gas,
                        "over_threshold": r > 0,
                        "ratio": r,
                        "document_text": "检测到" + "、".join(kws),
                        "gas_attribution": f"{gas} 归因（来自 gas_rule 配置）",
                        "gas_actions": [f"{gas} 处置措施 A", f"{gas} 处置措施 B"],
                    },
                    "expect": {
                        "over_threshold": r > 0,
                        "ratio": r,
                        "kw": kw_name,
                    },
                })
    return cases
