# -*- coding: utf-8 -*-
"""公司运行诊断模型（sft17_exec）留出样本实测。

30 条留出样本（eval/data/eval_set_exec_30.jsonl）逐条调用
llamafactory-cli api（OpenAI 兼容 /v1/chat/completions），
对齐后端 AiJsonClient 口径（temperature 0.2 + response_format json_object）。

判定口径与语料验证三件套一致：
1. JSON 可解析；
2. validate_exec_mirror（DiagnosisContract.validateExec 的 Python 镜像）0 错误；
3. unverified_numbers：输出叙述里的每个数字都能在事实清单中找到出处
   （含 add_derived 的加/减/半分位百分比派生）。

叙述层指标（衡量「非模板复读」）：
- 证据引用率：verdict.evidence / findings 里引用 F 编号的比例；
- 样本内句式种类数：技能名→S、L\d→L#、数字→# 归一后统计句干种类；
- 跨样本复读率：30 条输出里出现 >=10 次的句子占比（模板复读探测器）。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dataset"))

import build_exec_data as B  # noqa: E402

EVAL_SET = ROOT / "eval" / "data" / "eval_set_exec_30.jsonl"
OUT = ROOT / "eval" / "results" / "exec_model_eval.json"

URL = "http://127.0.0.1:8000/v1/chat/completions"

SENT_SPLIT = re.compile(r"[。；;]")
F_REF = re.compile(r"F\d+")


def call_model(system: str, user: str, timeout: int = 300) -> tuple[str, float]:
    body = json.dumps({
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"], time.time() - start


def allowed_of(facts: list) -> set:
    allowed = set()
    for f in facts:
        allowed |= B.numbers_of(f["label"] + " " + f["value"])
    return B.add_derived(allowed)


def norm_sentence(sent: str) -> str:
    text = re.sub(r"F\d+", "F#", sent)
    text = re.sub(r"L[0-3]", "L#", text)
    text = re.sub(r"《[^》]*》", "《S》", text)
    text = re.sub(r"\d+(?:\.\d+)?", "#", text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    rows = [json.loads(line) for line in
            open(EVAL_SET, encoding="utf-8")][: args.limit]

    results = []
    all_norm_sents = []
    for i, row in enumerate(rows):
        raw, latency = call_model(row["system"], row["input"])
        record = {"index": i, "latency_s": round(latency, 1)}

        try:
            payload = json.loads(raw)
            record["json_ok"] = True
        except (json.JSONDecodeError, TypeError):
            record["json_ok"] = False
            record["errors"] = ["JSON_PARSE"]
            payload = None

        if payload is not None:
            errors = B.validate_exec_mirror(payload)
            record["contract_errors"] = errors
            record["unverified_numbers"] = B.unverified_numbers(
                payload, allowed_of(row["facts"]))

            # 叙述层指标
            texts = [payload.get("summary", "")]
            verdict = payload.get("verdict") or {}
            texts.append(str(verdict.get("headline", "")))
            for ev in verdict.get("evidence", []) or []:
                texts.append(str(ev))
            for fd in payload.get("findings", []) or []:
                texts += [str(fd.get("title", "")), str(fd.get("impact", "")),
                          str(fd.get("evidence", ""))]
            for act in payload.get("actions", []) or []:
                texts.append(str(act.get("text", "")))
            blob = " ".join(texts)
            record["f_ref_count"] = len(F_REF.findall(blob))
            sents = [norm_sentence(s) for s in SENT_SPLIT.split(blob)
                     if len(s.strip()) >= 8]
            record["sent_variety"] = len(set(sents))
            record["sent_total"] = len(sents)
            all_norm_sents += sents
            record["output_chars"] = len(raw)
            ref_chars = len(row["output"])
            record["ref_chars"] = ref_chars
            record["summary_len"] = len(payload.get("summary", ""))
            record["ref_summary_len"] = len(
                (json.loads(row["output"]).get("summary", "")))
        record["raw"] = raw
        results.append(record)
        ok = record.get("json_ok") and not record.get("contract_errors") \
            and not record.get("unverified_numbers")
        print(f"[{i + 1}/{len(rows)}] {'OK' if ok else 'FAIL'} "
              f"{record.get('latency_s')}s", flush=True)

    # 汇总
    n = len(results)
    passed = [r for r in results
              if r.get("json_ok") and not r.get("contract_errors")
              and not r.get("unverified_numbers")]
    lat = sorted(r["latency_s"] for r in results if r.get("latency_s"))
    counter = {}
    for s in all_norm_sents:
        counter[s] = counter.get(s, 0) + 1
    repeated = sum(c for c in counter.values() if c >= 10)
    summary = {
        "n": n,
        "json_ok": sum(1 for r in results if r.get("json_ok")),
        "contract_pass": sum(1 for r in results if not r.get("contract_errors")),
        "numbers_verified": sum(
            1 for r in results if not r.get("unverified_numbers")),
        "full_pass": len(passed),
        "latency_s": {"min": lat[0], "p50": lat[len(lat) // 2],
                      "max": lat[-1]} if lat else None,
        "f_ref_total": sum(r.get("f_ref_count", 0) for r in results),
        "sent_variety_avg": round(
            sum(r.get("sent_variety", 0) for r in results) / max(n, 1), 2),
        "cross_sample_repeated_ratio": round(
            repeated / max(len(all_norm_sents), 1), 3),
    }
    OUT.write_text(
        json.dumps({"summary": summary, "results": results},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
