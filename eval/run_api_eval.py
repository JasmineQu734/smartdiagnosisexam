# -*- coding: utf-8 -*-
"""
在线复核：把同一批事实通过真实后端 POST /api/v1/rules/execute 跑一遍，
用来对照 run_eval.py 的离线回放结果（论文中的「离线回放 + 在线复核」双通道）。

前置：后端已启动，且有一个管理员账号（默认 admin）。
      docker compose up -d   # 或 backend 目录下 mvn spring-boot:run

用法：
  python eval/run_api_eval.py --base http://localhost:8080 --user admin [--sample 30]

产物：
  eval/results/api_check.json —— 逐条比对离线与在线的 matched / rule_refs / severity
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import build_facts, parse_profile  # noqa: E402
from ruleeng import RuleEngine, extract_rules_from_sql  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = ["PERSONAL_GAP", "EXAM_RESULT", "REPORT_ANALYSIS"]


def post(base: str, path: str, body: dict, token: str | None = None) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--sample", type=int, default=30, help="抽样档案条数")
    ap.add_argument("--scene", action="append", default=None)
    args = ap.parse_args()

    scenes = args.scene or SCENES
    corpus = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "data", "my_data15.json"), encoding="utf-8"))
    profiles = [parse_profile(s["input"]) for s in corpus][: args.sample]
    engine = RuleEngine(extract_rules_from_sql(os.path.join(ROOT, "db", "init"))[0])

    login = post(args.base, "/api/v1/auth/login", {"username": args.user})
    token = (login.get("data") or {}).get("token")
    if not token:
        print("登录失败：", json.dumps(login, ensure_ascii=False)[:400])
        sys.exit(2)
    print(f"已登录 {args.user}")

    rows, agree = [], 0
    for i, p in enumerate(profiles):
        for scene in scenes:
            facts = build_facts(p, scene)
            off = engine.execute(scene, facts)
            try:
                api = post(args.base, "/api/v1/rules/execute",
                           {"scene": scene, "target_id": p.get("name") or f"P{i}",
                            "facts": facts, "options": {"persist": False}},
                           token)
            except urllib.error.HTTPError as exc:
                rows.append({"idx": i, "scene": scene, "http_error": exc.code,
                             "body": exc.read().decode("utf-8", "ignore")[:200]})
                continue
            d = api.get("data") or {}
            same = (bool(d.get("matched")) == bool(off["matched"])) and \
                   (sorted((d.get("verdict") or {}).get("rule_refs") or []) == sorted(off["verdict"]["rule_refs"]))
            agree += same
            rows.append({"idx": i, "scene": scene, "same": same,
                         "offline": {"matched": off["matched"], "rule_refs": off["verdict"]["rule_refs"]},
                         "online": {"matched": d.get("matched"),
                                    "rule_refs": (d.get("verdict") or {}).get("rule_refs")}})
    total = len(rows)
    out = {"base": args.base, "sample": args.sample, "scenes": scenes,
           "executions": total, "agree": agree,
           "agreement_rate": round(agree / total, 4) if total else None, "rows": rows}
    dst = os.path.join(ROOT, "eval", "results", "api_check.json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"离线 / 在线一致：{agree}/{total}"
          + (f"（{agree/total:.1%}）" if total else ""))
    print("已写出", dst)


if __name__ == "__main__":
    main()
