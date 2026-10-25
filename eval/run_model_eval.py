# -*- coding: utf-8 -*-
"""
真实模型实测：把留出集的 prompt 直接打到本机 llama-factory 起的 OpenAI 兼容服务
（默认 http://127.0.0.1:8000，模型名 qwen2.5-3b-lora），逐条按线上护栏的四类校验打分。

为什么要单独做这份评测
----------------------
run_eval.py 里表 E 审计的是 my_data15 的 150 份「参考输出」——那是 SFT 的训练目标，
不是模型的实际响应，不能当模型成绩。本脚本调用真正在跑的 adapter，衡量的是：
  · 输出契约合法率（6 键 JSON 能否解析、字段与枚举是否合规）
  · 事实忠实度（gaps 的技能集合与等级是否等于事实清单，reasons 的 F 编号是否存在）
  · 排期合规（due_at 晚于今天且严格递增，priority 与差距大小单调）
  · 安全处置（档案带安全负例时，输出是否给出授权/监护/复核类边界）
  · 延迟（端到端，含 tokenize + 生成 + 网络）

留出集口径
----------
用与训练同一条生成流水线（tools/dataset/build_my_data16.py）、不同的随机种子再造一批
prompt，并剔除与训练集逐字相同的样本。档案库仍是同一批 150 人，因此这里衡量的是
「未见事实组合」上的契约遵从与事实忠实度，**不是**对未见员工的泛化——论文的效度威胁一节
必须这样写。

用法
----
    python eval/run_model_eval.py                      # 20 条留出 + 6 条训练原样
    python eval/run_model_eval.py --heldout 8 --train 2
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN_DIR = os.path.join(ROOT, "tools", "dataset")
TRAIN_CORPUS = r"D:/anaconda/LlamaFactory-main/LlamaFactory-main/data/my_data16.json"

API = os.environ.get("AGENT_API", "http://127.0.0.1:8000/v1/chat/completions")
MODEL = os.environ.get("AGENT_MODEL", "qwen2.5-3b-lora")
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.2"))

KEYS = {"summary", "confidence", "verdict", "gaps", "plan", "compound_path"}
LEVELS = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
SEVERITY = {"HIGH", "MEDIUM", "LOW"}
PRIORITY = {"P1", "P2", "P3"}
KIND = {"课程", "带教", "模拟考"}
SAFETY_HINT = ("授权", "监护", "复核", "工作票", "双人", "监护", "越权", "未遂")


# --------------------------------------------------------------------------
# 一、从 prompt 里把事实解析回来（事实清单是唯一权威来源）
# --------------------------------------------------------------------------
def parse_prompt(text: str) -> dict:
    """返回 {today, fact_ids, skills:{name:{current,required,future,gap,sev}}, gaps:[...], text}"""
    today = None
    match = re.search(r"【今天】(\d{4}-\d{2}-\d{2})", text)
    if match:
        today = date.fromisoformat(match.group(1))

    fact_ids = {int(code) for code in re.findall(r"^F(\d+)\s+\[", text, re.M)}

    skills: dict[str, dict] = {}
    # F4 [employee_skill] 技能 局放检测：当前 L1，岗位要求 L2，未来需求 L3（差 1 级）
    for block in re.finditer(
            r"\[employee_skill\] 技能 ([^：]+)：当前 (L\d|合格)，岗位要求 (L\d|合格)，未来需求 (L\d|合格)（([^）]*)）",
            text):
        name, cur, req, fut, state = block.groups()
        skills[name.strip()] = {
            "current": LEVELS.get(cur), "required": LEVELS.get(req), "future": LEVELS.get(fut),
            "state": state,
        }

    # F22 [skill_gap_summary] ... 未达标技能：A（当前 L1，岗位要求 L2，未来需求 L3，差 1 级，雷达优先级 HIGH）
    gap_list = []
    seg = re.search(r"未达标技能：(.+?)。已达标技能：", text, re.S)
    if seg:
        for row in re.finditer(
                r"([^；，、]+)（当前 (L\d)，岗位要求 (L\d)，未来需求 (L\d)，差 (\d) 级，雷达优先级 (HIGH|MEDIUM|LOW)）",
                seg.group(1)):
            name, cur, req, fut, gap, sev = row.groups()
            gap_list.append({"skill": name.strip(), "current": int(cur[1]), "required": int(req[1]),
                             "future": int(fut[1]), "gap": int(gap), "severity": sev})
    for item in gap_list:
        if item["skill"] in skills:
            skills[item["skill"]]["severity"] = item["severity"]

    numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
    has_safety = bool(re.search(r"\[safety_record\][^\n]*?（(HIGH|MEDIUM)）", text)) or \
        any(word in text for word in ("未遂", "越权", "无票", "未监护", "扣分"))
    return {"today": today, "fact_ids": fact_ids, "skills": skills, "gap_list": gap_list,
            "numbers": numbers, "has_safety": has_safety, "text": text}


# --------------------------------------------------------------------------
# 二、四类校验
# --------------------------------------------------------------------------
def check(payload_text: str, facts: dict) -> dict:
    out: dict = {"json_ok": False, "contract_ok": False, "gaps_ok": False, "levels_ok": False,
                 "priority_ok": False, "plan_ok": False, "cite_ok": False, "numbers_ok": False,
                 "safety_ok": False, "violations": []}
    text = payload_text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    try:
        payload = json.loads(text)
    except Exception:
        return out
    out["json_ok"] = True

    def bad(tag: str) -> None:
        out["violations"].append(tag)

    # 契约：6 键、嵌套必填、枚举合规
    if not isinstance(payload, dict) or set(payload) != KEYS:
        bad("key_set")
        return out
    verdict = payload.get("verdict") or {}
    if not isinstance(verdict, dict) or not verdict.get("headline") or not verdict.get("reasons"):
        bad("verdict_shape")
        return out
    if not isinstance(payload.get("gaps"), list) or not payload["gaps"]:
        bad("gaps_shape")
        return out
    if not isinstance(payload.get("plan"), list) or not payload["plan"]:
        bad("plan_shape")
        return out
    compound = payload.get("compound_path") or {}
    if not isinstance(compound, dict) or not compound.get("stages"):
        bad("compound_shape")
        return out
    ok = True
    for gap in payload["gaps"]:
        if not isinstance(gap, dict) or set(gap) != {"skill", "current", "required", "future",
                                                     "severity", "priority", "impact", "action"}:
            ok = False
            bad("gap_fields")
            break
        if gap["severity"] not in SEVERITY or gap["priority"] not in PRIORITY:
            ok = False
            bad("gap_enum")
            break
    for step in payload["plan"]:
        if not isinstance(step, dict) or set(step) != {"step", "kind", "title", "target_skill",
                                                       "to_level", "due_at", "reason"}:
            ok = False
            bad("plan_fields")
            break
        if step["kind"] not in KIND:
            ok = False
            bad("plan_enum")
            break
    conf = payload.get("confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        ok = False
        bad("confidence_range")
    out["contract_ok"] = ok

    # 事实：gaps 的技能集合必须等于「未达标技能」，一项不多一项不少
    want = [item["skill"] for item in facts["gap_list"]]
    got = [gap.get("skill") for gap in payload["gaps"]]
    if set(got) == set(want):
        out["gaps_ok"] = True
    else:
        bad("gap_set")

    # 等级：current / required / future 必须等于事实清单里的等级
    ok = bool(out["gaps_ok"])
    if ok:
        for gap in payload["gaps"]:
            ref = facts["skills"].get(gap["skill"], {})
            if (gap["current"], gap["required"], gap["future"]) != (
                    ref.get("current"), ref.get("required"), ref.get("future")):
                ok = False
                bad("level_mismatch")
                break
    out["levels_ok"] = ok

    # 优先级：契约口径是 severity → P1/P2/P3（语料与前端都按这个约定）；
    # 另记一个附加口径「优先级与差距大小单调」，它并不在契约里，用于观察模型是否只是在复述约定。
    ok = True
    rank = {"P1": 1, "P2": 2, "P3": 3}
    sev_map = {"HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"}
    for gap in payload["gaps"]:
        if sev_map.get(gap["severity"]) != gap["priority"]:
            ok = False
    if not ok:
        bad("priority_severity")
    out["priority_ok"] = ok

    # severity 本身也要等于事实清单里的雷达优先级
    ok = all(facts["skills"].get(gap["skill"], {}).get("severity") in (None, gap["severity"])
             for gap in payload["gaps"])
    out["severity_ok"] = ok
    if not ok:
        bad("severity_mismatch")

    ok = True
    ordered = []
    for gap in payload["gaps"]:
        ref = facts["skills"].get(gap["skill"], {})
        if ref.get("current") is None or ref.get("required") is None:
            continue
        ordered.append((rank.get(gap["priority"], 9), ref["required"] - ref["current"]))
    if ordered:
        for left in range(len(ordered)):
            for right in range(left + 1, len(ordered)):
                if ordered[left][0] < ordered[right][0] and ordered[left][1] < ordered[right][1]:
                    ok = False
    out["priority_gap_ok"] = ok

    # 排期：due_at 晚于今天、严格递增、step 连续
    ok = True
    today = facts["today"]
    dates = []
    for index, step in enumerate(payload["plan"], start=1):
        try:
            due = date.fromisoformat(str(step["due_at"]))
        except Exception:
            ok = False
            bad("due_format")
            break
        if today and due <= today:
            ok = False
            bad("due_before_today")
        if step["step"] != index:
            ok = False
            bad("step_number")
        dates.append(due)
    if len(dates) > 1 and any(dates[i] >= dates[i + 1] for i in range(len(dates) - 1)):
        ok = False
        bad("due_not_increasing")
    out["plan_ok"] = ok

    # 引用：reasons 至少 3 条，且其中至少 3 条带存在的事实编号
    reasons = [str(item) for item in verdict.get("reasons", [])]
    cited = [int(code) for item in reasons for code in re.findall(r"F(\d+)", item)]
    valid = [code for code in cited if code in facts["fact_ids"]]
    out["cite_ok"] = len(valid) >= 3
    if not out["cite_ok"]:
        bad("citation")

    # 数字：输出里的数字必须能在事实清单里找到
    body = json.dumps(payload, ensure_ascii=False)
    # confidence 是模型自评的小数，本就允许是清单里没有的新值，不参与可溯源性判定
    body = body.replace(str(payload.get("confidence")), "")
    extra = [n for n in set(re.findall(r"\d+(?:\.\d+)?", body)) if n not in facts["numbers"]]
    # due_at 与 step 编号允许新出现（排期日期本就往后排）
    allowed_extra = {str(step["step"]) for step in payload["plan"]}
    allowed_extra |= {part for step in payload["plan"] for part in str(step["due_at"]).split("-")}
    allowed_extra |= {str(value) for value in payload["gaps"] for value in
                      (value.get("current"), value.get("required"), value.get("future"))}
    extra = [n for n in extra if n not in allowed_extra]
    out["numbers_ok"] = not extra
    if extra:
        out["unverified_numbers"] = extra[:6]
        bad("unverified_number")

    # 安全：档案带安全负例时，输出要给出授权/监护/复核类边界
    if facts["has_safety"]:
        out["safety_ok"] = any(word in body for word in SAFETY_HINT)
        if not out["safety_ok"]:
            bad("safety_missing")
    else:
        out["safety_ok"] = True

    out["gaps_count"] = len(payload["gaps"])
    out["plan_count"] = len(payload["plan"])
    out["confidence"] = conf
    out["narrative"] = narrative_metrics(payload, facts)
    return out


# --------------------------------------------------------------------------
# 二之二、叙述层代理指标（可复算，不是人工评分）
# --------------------------------------------------------------------------
def evidence_of(text: str, skill: str) -> str:
    """取某技能条目的「证据：……」。模板基线不会引用它，模型可能引用。"""
    match = re.search(r"\[employee_skill\] 技能 %s：[^\n]*?证据：([^；\n]+)" % re.escape(skill), text)
    return match.group(1).strip() if match else ""


def _skeleton(text: str, name: str) -> str:
    """把技能名、等级与数字归一，只留句式骨架，用于比较「是不是同一句话换个数字」。"""
    if name:
        text = text.replace(name, "S")
    text = re.sub(r"L\d", "L#", text)
    text = re.sub(r"\d+(?:\.\d+)?", "#", text)
    return text.strip()


def narrative_metrics(payload: dict, facts: dict) -> dict:
    """
    判定性判据（契约、gaps 集合、等级、排期、数字）由架构保证，连固定模板都能满分，
    所以模型的价值只能用叙述层指标来体现。这里给三个可复算的代理量：
      · 句干唯一率：把技能名归一后，impact / action 还剩几种写法（越低越像模板）
      · 证据引用率：action 里是否出现该技能「证据」字段的片段（模板为 0）
      · 文本长度：action 平均字数与 summary 字数
    明确标注：这是代理指标，不能替代人工评审。
    """
    gaps = payload.get("gaps") or []
    pairs = [(str(gap.get("skill", "")), str(gap.get("impact", "")), str(gap.get("action", "")))
             for gap in gaps]
    if not pairs:
        return {"action_skeleton_unique": 0.0, "impact_skeleton_unique": 0.0,
                "evidence_grounded_rate": 0.0, "action_chars_mean": 0.0, "summary_chars": 0}

    body = facts.get("text", "")
    grounded = 0
    for name, _impact, action in pairs:
        evidence = evidence_of(body, name)
        if evidence and any(evidence[start:start + 4] in action
                            for start in range(max(len(evidence) - 3, 1))):
            grounded += 1

    action_sk = {_skeleton(action, name) for name, _i, action in pairs}
    impact_sk = {_skeleton(impact, name) for name, impact, _a in pairs}
    total = len(pairs)
    return {
        "action_skeletons": len(action_sk),
        "impact_skeletons": len(impact_sk),
        "evidence_grounded_rate": round(grounded / total, 4),
        "action_chars_mean": round(statistics.fmean([len(action) for _n, _i, action in pairs]), 1),
        "summary_chars": len(str(payload.get("summary", ""))),
    }


# --------------------------------------------------------------------------
# 三、调用
# --------------------------------------------------------------------------
def ask(sample: dict, timeout: int = 600) -> tuple[str, float, dict]:
    """
    采样参数与后端 AiJsonClient 保持一致：temperature 0.2 + response_format=json_object，
    这样测到的就是线上护栏真正会收到的那一份输出。后端对 OpenAI 兼容协议不发 max_tokens，
    这里加 1800 的硬上限只为避免个别样本无限生成拖住评测。
    """
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": sample["system"]},
                     {"role": "user", "content": sample["input"]}],
        "temperature": TEMPERATURE,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    request = urllib.request.Request(
        API, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    elapsed = time.time() - start
    choice = payload["choices"][0]
    return choice["message"]["content"], elapsed, payload.get("usage", {})


def build_heldout(count: int, seed: int, exclude: set[str]) -> list[dict]:
    sys.path.insert(0, GEN_DIR)
    import build_my_data16 as gen  # noqa: PLC0415

    with open(gen.SRC, encoding="utf-8") as handle:
        source = json.load(handle)
    personas = [gen.parse_persona(item["input"]) for item in source]
    rng = random.Random(seed)
    picked, attempt = [], 0
    while len(picked) < count and attempt < count * 40:
        persona = personas[attempt % len(personas)]
        attempt += 1
        sample, errors, _facts, _today = gen.build_sample(persona, rng)
        if sample is None or sample["input"] in exclude:
            continue
        picked.append(sample)
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", type=int, default=20)
    parser.add_argument("--train", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--out", default=os.path.join(HERE, "results", "model_eval.json"))
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--eval-set", default=None,
                        help="读冻结的样本集（jsonl），不再现场生成。基线对照必须用这个参数，"
                             "否则每次重建的样本不同，与已发表结果不可比。")
    parser.add_argument("--freeze-out", default=None,
                        help="把本次实际送评的样本写成 jsonl，供后续基线复用。")
    args = parser.parse_args()

    with open(TRAIN_CORPUS, encoding="utf-8") as handle:
        train = json.load(handle)

    if args.eval_set:
        with open(args.eval_set, encoding="utf-8") as handle:
            frozen = [json.loads(line) for line in handle if line.strip()]
        heldout = [item for item in frozen if item["group"] == "heldout"]
        verbatim = [item for item in frozen if item["group"] == "verbatim"]
        print(f"读冻结样本集 {args.eval_set}：留出 {len(heldout)} 条，训练原样 {len(verbatim)} 条")
    else:
        train_inputs = {item["input"] for item in train}
        print("生成留出样本（与训练集 prompt 逐字不重合）...")
        heldout = build_heldout(args.heldout, args.seed, train_inputs)
        step = max(len(train) // max(args.train, 1), 1)
        verbatim = [train[index] for index in range(0, len(train), step)][:args.train]
        if args.freeze_out:
            os.makedirs(os.path.dirname(os.path.abspath(args.freeze_out)), exist_ok=True)
            with open(args.freeze_out, "w", encoding="utf-8", newline="\n") as handle:
                for group, samples in (("heldout", heldout), ("verbatim", verbatim)):
                    for position, sample in enumerate(samples, start=1):
                        handle.write(json.dumps({"group": group, "index": position,
                                                 "system": sample["system"],
                                                 "input": sample["input"]},
                                                ensure_ascii=False) + "\n")
            print("冻结样本集写出", args.freeze_out)

    print(f"留出 {len(heldout)} 条，训练原样 {len(verbatim)} 条，服务 {API} 模型 {MODEL}")

    cases = []
    for group, samples in (("heldout", heldout), ("verbatim", verbatim)):
        for position, sample in enumerate(samples, start=1):
            facts = parse_prompt(sample["input"])
            try:
                content, elapsed, usage = ask(sample)
                result = check(content, facts)
                result.update({"group": group, "index": position, "latency_s": round(elapsed, 1),
                               "prompt_chars": len(sample["input"]),
                               "output_chars": len(content),
                               "completion_tokens": usage.get("completion_tokens"),
                               "finish": "stop", "raw": content[:4000]})
            except Exception as error:  # noqa: BLE001
                result = {"group": group, "index": position, "error": f"{type(error).__name__}: {error}",
                          "json_ok": False, "contract_ok": False, "gaps_ok": False, "levels_ok": False,
                          "priority_ok": False, "plan_ok": False, "cite_ok": False,
                          "numbers_ok": False, "safety_ok": False, "violations": ["call_failed"]}
            cases.append(result)
            flag = "OK " if result.get("contract_ok") and result.get("gaps_ok") else "NG "
            print(f"  {flag}{group}[{position}] {result.get('latency_s', '-')}s "
                  f"contract={result.get('contract_ok')} gaps={result.get('gaps_ok')} "
                  f"levels={result.get('levels_ok')} plan={result.get('plan_ok')} "
                  f"safety={result.get('safety_ok')} {result.get('violations')}")
            time.sleep(args.sleep)

    def rate(rows: list[dict], key: str) -> float:
        return round(sum(1 for row in rows if row.get(key)) / len(rows), 4) if rows else 0.0

    summary = {}
    for group in ("heldout", "verbatim"):
        rows = [row for row in cases if row["group"] == group]
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
            "plan_rate": rate(rows, "plan_ok"),
            "citation_rate": rate(rows, "cite_ok"),
            "number_grounded_rate": rate(rows, "numbers_ok"),
            "safety_rate": rate(rows, "safety_ok"),
            "all_pass_rate": round(sum(1 for row in rows if all(
                row.get(key) for key in ("json_ok", "contract_ok", "gaps_ok", "levels_ok",
                                         "priority_ok", "plan_ok"))) / len(rows), 4),
            "latency_p50": statistics.median(latencies) if latencies else None,
            "latency_mean": round(statistics.fmean(latencies), 1) if latencies else None,
            "latency_max": max(latencies) if latencies else None,
            "violations": {tag: sum(1 for row in rows if tag in row.get("violations", []))
                           for tag in sorted({tag for row in rows for tag in row.get("violations", [])})},
        }
        print(f"== {group} ==", json.dumps(summary[group], ensure_ascii=False))

    summary["config"] = {"api": API, "model": MODEL, "heldout_seed": args.seed,
                         "temperature": TEMPERATURE, "response_format": "json_object", "max_tokens": 1800}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"summary": summary, "cases": cases}, handle, ensure_ascii=False, indent=1)
    print("写出", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
