# -*- coding: utf-8 -*-
"""
规则引擎评测参考实现（DSL v1）。

用途：在不启动 MySQL / Spring Boot 的情况下，对 db/init/*.sql 里的**真实规则定义**
做离线回放评测，产出可写进论文的指标；同一套指标也可用 run_api_eval.py 走
POST /api/v1/rules/execute 在线复核。

本文件严格按 docs/rule-engine-design.md 的口径实现：
  - 条件算子白名单（比较 / 集合 / 文本 / 布尔存在），不使用 eval、不拼 SQL
  - 数值比较走 Decimal，不用 float 比大小
  - 匹配：enabled=1 且 scene 相符，priority 降序、rule_code 升序
  - 分组收敛：stop_on_match / max_hits 只作用于本组；未分组同属默认组 ""
  - verdict：actions / causes 去重保序，cause 取首条，severity 取最严重
  - 不可判定（算子未知 / 事实缺失 / 类型不符）→ 记 skipped_reason 并跳过，不抛异常、不算命中
  - action_json 里以 _from 结尾的字段是引用事实，输出时换成该事实当前值
"""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------- 常量表

NUMERIC_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "between"}
SET_OPS = {"in", "not_in"}
TEXT_OPS = {"contains", "not_contains", "contains_any", "starts_with", "ends_with"}
BOOL_OPS = {"is_true", "is_false", "exists", "missing"}
KNOWN_OPS = NUMERIC_OPS | SET_OPS | TEXT_OPS | BOOL_OPS

# 严重度序（低 < 中 < 高）；认不出的取值按 0 兜底
SEVERITY_RANK = {"低": 1, "中": 2, "高": 3, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


class Undecidable(Exception):
    """条件无法判定：只跳过这一条规则，不影响其他规则。"""


# ---------------------------------------------------------------- 条件求值

def _dec(v: Any) -> Decimal:
    if isinstance(v, bool):
        raise Undecidable("bool 不能参与数值比较")
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float, str)):
        try:
            return Decimal(str(v))
        except InvalidOperation as exc:
            raise Undecidable(f"无法转为数值: {v!r}") from exc
    raise Undecidable(f"类型不支持数值比较: {type(v).__name__}")


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "y", "是"}
    raise Undecidable(f"无法判定布尔: {v!r}")


def _text(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    raise Undecidable(f"文本算子收到非文本: {type(v).__name__}")


def eval_condition(cond: Any, facts: dict) -> tuple[bool, list[str]]:
    """返回 (是否命中, 命中依据的可读描述)。不可判定抛 Undecidable。"""
    if not isinstance(cond, dict):
        raise Undecidable(f"条件不是对象: {type(cond).__name__}")

    if "all" in cond:
        sub = cond["all"]
        if not isinstance(sub, list) or not sub:
            raise Undecidable("all 需要非空数组")
        trace: list[str] = []
        for c in sub:
            ok, t = eval_condition(c, facts)
            trace.extend(t)
            if not ok:
                return False, trace
        return True, trace

    if "any" in cond:
        sub = cond["any"]
        if not isinstance(sub, list) or not sub:
            raise Undecidable("any 需要非空数组")
        trace = []
        for c in sub:
            ok, t = eval_condition(c, facts)
            if ok:
                return True, trace + t
        return False, trace

    if "not" in cond:
        ok, t = eval_condition(cond["not"], facts)
        return (not ok), t

    fact = cond.get("fact")
    op = cond.get("op")
    if fact is None or op is None:
        raise Undecidable("叶子条件缺少 fact / op")
    if op not in KNOWN_OPS:
        raise Undecidable(f"未知算子 {op!r}")
    if fact not in facts:
        raise Undecidable(f"facts 缺少 {fact}")

    left = facts[fact]

    if op in BOOL_OPS:
        if op == "exists":
            return True, f"{fact} 存在"
        if op == "missing":
            return False, f"{fact} 存在"
        want = op == "is_true"
        got = _as_bool(left)
        return got is want, f"{fact}({got}) {op}"

    if "other_fact" in cond:
        other = cond["other_fact"]
        if other not in facts:
            raise Undecidable(f"facts 缺少 {other}（被 {fact} 引用）")
        right = facts[other]
        rhs_name = f"{other}({right})"
    elif "value" in cond:
        right = cond["value"]
        rhs_name = f"{right!r}"
    else:
        raise Undecidable("叶子条件既没有 value 也没有 other_fact")

    if op in NUMERIC_OPS:
        if op == "between":
            if not isinstance(right, (list, tuple)) or len(right) != 2:
                raise Undecidable("between 需要 [下界, 上界]")
            lo, hi = _dec(right[0]), _dec(right[1])
            l = _dec(left)
            hit = lo <= l <= hi
            return hit, f"{fact}({left}) between [{lo},{hi}]"
        l, r = _dec(left), _dec(right)
        hit = {
            "eq": l == r, "ne": l != r, "gt": l > r,
            "gte": l >= r, "lt": l < r, "lte": l <= r,
        }[op]
        return hit, f"{fact}({left}) {op} {rhs_name}"

    if op in SET_OPS:
        if not isinstance(right, (list, tuple, set)):
            raise Undecidable(f"{op} 需要数组")
        hit = (left in right) if op == "in" else (left not in right)
        return hit, f"{fact}({left}) {op} {list(right)}"

    # 文本算子
    lt, rt = _text(left), right
    if op == "contains_any":
        if not isinstance(rt, (list, tuple)):
            raise Undecidable("contains_any 需要关键词数组")
        hit = any(_text(k) in lt for k in rt)
        return hit, f"{fact} contains_any 命中" if hit else f"{fact} contains_any 未命中"
    rt = _text(rt)
    hit = {
        "contains": lt.__contains__(rt),
        "not_contains": not lt.__contains__(rt),
        "starts_with": lt.startswith(rt),
        "ends_with": lt.endswith(rt),
    }[op]
    return hit, f"{fact} {op} {rt!r}"


# ---------------------------------------------------------------- action_json

def resolve_action(action: dict, facts: dict) -> tuple[dict, list[str]]:
    """处理 _from 引用事实；取不到时保留键名并记说明（不静默丢字段）。"""
    out: dict[str, Any] = {}
    notes: list[str] = []
    for k, v in action.items():
        if k.endswith("_from") and isinstance(v, str):
            target = k[:-5]
            if target in action:          # 显式值优先
                continue
            if v in facts and facts[v] is not None:
                out[target] = facts[v]
            else:
                out[k] = v
                notes.append(f"{k} 引用的事实 {v!r} 未提供，字段原样保留")
        else:
            out[k] = v
    return out, notes


# ---------------------------------------------------------------- 引擎

class RuleEngine:
    def __init__(self, rules: list[dict]):
        self.rules = rules

    def candidates(self, scene: str) -> list[dict]:
        rows = [r for r in self.rules if r.get("scene") == scene and int(r.get("enabled", 1)) == 1]
        # priority 降序；同优先级按 rule_code 升序，保证结果稳定可复现
        rows.sort(key=lambda r: (-int(r.get("priority", 0)), str(r.get("rule_code", ""))))
        return rows

    def execute(self, scene: str, facts: dict, persist: bool = False) -> dict:
        hits: list[dict] = []
        skipped: list[dict] = []
        closed_groups: set[str] = set()
        group_hits: dict[str, int] = {}

        for r in self.candidates(scene):
            grp = r.get("rule_group") or ""
            if grp in closed_groups:
                skipped.append({"rule_code": r["rule_code"], "skipped_reason": f"分组 {grp or '(默认)'} 已收敛"})
                continue
            cap = int(r.get("max_hits", 0) or 0)
            if cap and group_hits.get(grp, 0) >= cap:
                closed_groups.add(grp)
                skipped.append({"rule_code": r["rule_code"], "skipped_reason": f"分组 {grp} 已达 max_hits={cap}"})
                continue
            try:
                ok, trace = eval_condition(json.loads(r["condition_json"]), facts)
            except Undecidable as exc:
                skipped.append({"rule_code": r["rule_code"], "skipped_reason": str(exc)})
                continue
            except json.JSONDecodeError as exc:
                skipped.append({"rule_code": r["rule_code"], "skipped_reason": f"condition_json 非法: {exc}"})
                continue
            if not ok:
                continue

            try:
                action = json.loads(r["action_json"])
            except json.JSONDecodeError:
                skipped.append({"rule_code": r["rule_code"], "skipped_reason": "action_json 非法"})
                continue
            resolved, notes = resolve_action(action, facts)
            hits.append({
                "rule_code": r["rule_code"],
                "rule_name": r.get("rule_name"),
                "rule_group": grp,
                "priority": int(r.get("priority", 0)),
                "condition_hit": trace,
                "actions": resolved.get("actions", []),
                "cause": resolved.get("cause"),
                "cause_from_pending": resolved.get("cause_from"),
                "severity": resolved.get("severity"),
                "output": resolved,
                "notes": notes,
                "explanation": f"命中 {r['rule_code']}：{'；'.join(trace)}" + (f"（{'；'.join(notes)}）" if notes else ""),
            })
            group_hits[grp] = group_hits.get(grp, 0) + 1
            if int(r.get("stop_on_match", 1)) == 1:
                closed_groups.add(grp)

        verdict = self._merge(hits)
        matched = bool(hits)
        return {
            "scene": scene,
            "matched": matched,
            "hits": hits,
            "skipped": skipped,
            "verdict": verdict,
            "unmatched_reason": None if matched else self._why_not(scene, facts, skipped),
            "source": "rule",
            "need_human_confirm": True,
        }

    def _why_not(self, scene: str, facts: dict, skipped: list[dict]) -> str:
        if not [r for r in self.rules if r.get("scene") == scene and int(r.get("enabled", 1)) == 1]:
            return f"场景 {scene} 没有 enabled=1 的规则"
        if skipped and len(skipped) == len(self.candidates(scene)):
            return f"场景 {scene} 全部规则不可判定：{skipped[0]['skipped_reason']}"
        return f"场景 {scene} 有规则但条件均未满足"

    @staticmethod
    def _merge(hits: list[dict]) -> dict:
        actions: list[Any] = []
        causes: list[Any] = []
        severity = None
        best = -1
        for h in hits:
            for a in h.get("actions") or []:
                if a not in actions:
                    actions.append(a)
            c = h.get("cause")
            if c is not None and c not in causes:
                causes.append(c)
            s = h.get("severity")
            if s is not None:
                rank = SEVERITY_RANK.get(str(s).upper() if str(s).isascii() else str(s), 0)
                if rank > best:
                    best, severity = rank, s
        return {
            "actions": actions,
            "causes": causes,
            "cause": causes[0] if causes else None,
            "severity": severity,
            "rule_refs": [h["rule_code"] for h in hits],
            "confidence": 0.9 if hits else 0.0,
        }


# ---------------------------------------------------------------- 从 SQL 抽规则

def _strip_sql_comments(sql: str) -> str:
    out = []
    for ln in sql.splitlines():
        s = ln.strip()
        if s.startswith("--") or s.startswith("#"):
            continue
        # 去掉行尾注释（规则文本里不会出现 --）
        i = ln.find("--")
        out.append(ln if i < 0 else ln[:i])
    return "\n".join(out)


def _split_top_level(text: str) -> list[str]:
    """按顶层逗号切分，忽略单引号内与括号内的逗号。"""
    parts, buf, depth, inq = [], [], 0, False
    i = 0
    while i < len(text):
        ch = text[i]
        if inq:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    buf.append("''");  i += 2; continue
                inq = False
            buf.append(ch)
        else:
            if ch == "'":
                inq = True; buf.append(ch)
            elif ch == "(":
                depth += 1; buf.append(ch)
            elif ch == ")":
                depth -= 1; buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf)); buf = []
            else:
                buf.append(ch)
        i += 1
    if "".join(buf).strip():
        parts.append("".join(buf))
    return parts


def _literal(tok: str) -> Any:
    tok = tok.strip()
    if tok.upper() == "NULL":
        return None
    if tok.startswith("'") and tok.endswith("'") and len(tok) >= 2:
        return tok[1:-1].replace("''", "'")
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return tok


def extract_rules_from_sql(sql_dir: str) -> tuple[list[dict], dict]:
    """
    按文件编号顺序解析 db/init/*.sql 中所有 `INSERT INTO rule (...)` 语句，
    后出现的同 rule_code 覆盖先出现的（与建库脚本按序执行的语义一致）。
    """
    rules: dict[str, dict] = {}
    meta = {"files": [], "statements": 0, "rows": 0}

    comment_re = re.compile(r"--[^\n]*")
    ins_re = re.compile(
        r"INSERT\s+INTO\s+rule\s*\((.*?)\)\s*VALUES\s*(.*?)(?=ON\s+DUPLICATE|;\s*(?:\n|$)|$)",
        re.I | re.S,
    )
    for name in sorted(os.listdir(sql_dir)):
        if not name.lower().endswith(".sql"):
            continue
        path = os.path.join(sql_dir, name)
        raw = open(path, encoding="utf-8").read()
        sql = comment_re.sub("", raw)
        found = 0
        for m in ins_re.finditer(sql):
            cols = [c.strip().strip("`").lower() for c in m.group(1).split(",")]
            meta["statements"] += 1
            body = m.group(2).strip().rstrip(";")
            for row_txt in _split_top_level(body):
                row_txt = row_txt.strip()
                if not row_txt.startswith("(") or not row_txt.endswith(")"):
                    continue
                vals = [_literal(v) for v in _split_top_level(row_txt[1:-1])]
                if len(vals) != len(cols):
                    continue
                row = dict(zip(cols, vals))
                code = row.get("rule_code")
                if not code:
                    continue
                row.setdefault("rule_name", None)
                row.setdefault("rule_group", "")
                row.setdefault("stop_on_match", 1)
                row.setdefault("max_hits", 0)
                row.setdefault("enabled", 1)
                row.setdefault("priority", 0)
                row["_from_file"] = name
                rules[code] = row
                found += 1
                meta["rows"] += 1
        if found:
            meta["files"].append(f"{name}: {found} 行")
    return list(rules.values()), meta


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "db", "init")
    rs, mt = extract_rules_from_sql(d)
    print(f"抽取规则 {len(rs)} 条；{mt}")
    for r in sorted(rs, key=lambda x: (x["scene"], -int(x["priority"]))):
        print(f"  [{r['scene']:<15}] {r['rule_code']:<28} p={r['priority']:<4} "
              f"grp={r['rule_group'] or '(默认)':<8} stop={r['stop_on_match']} max={r['max_hits']} <- {r['_from_file']}")
