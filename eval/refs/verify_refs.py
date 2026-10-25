# -*- coding: utf-8 -*-
"""逐条核验论文参考文献是否真实存在（不联网生成任何内容，只做查证）。

数据源（复用 PaperCash 的 lib/sources 与 lib/http_client）：
  - CrossRef  https://api.crossref.org/works/{doi}
  - DataCite  https://api.datacite.org/dois/{doi}   (10.48550 = arXiv 注册号)
  - arXiv     http://export.arxiv.org/api/query?id_list=
  - Semantic Scholar  /paper/search   （标题兜底检索）

输出：eval/refs/ref_verification.json  +  ref_verification.md
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

PC = r"C:/Users/admin/.workbuddy/skills/papercash/scripts"
sys.path.insert(0, PC)

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = json.load(open(os.path.join(HERE, "refs_raw.json"), encoding="utf-8"))

S = requests.Session()
S.headers.update({
    "User-Agent": "PaperCash-RefAudit/1.0 (mailto:papercash@example.com)",
    "Accept": "application/json",
})

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"<>]+", re.I)
ARXIV_RE = re.compile(r"arXiv[:\s/]*(\d{4}\.\d{4,5})(v\d+)?", re.I)


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def guess_title(ref: str) -> str:
    """把参考文献条目切成 (标题, 其余)"""
    body = re.split(r"https?://|DOI:|\[J\]|\[C\]|\[M\]", ref)[0].strip()
    # 去掉作者段：第一个 ". " 之后到下一个句点前通常是标题
    parts = [p.strip() for p in body.split(". ") if p.strip()]
    if len(parts) >= 2:
        return parts[1].rstrip(".")
    return body


def fetch(url, timeout=25):
    for _ in range(3):
        try:
            r = S.get(url, timeout=timeout)
            if r.status_code == 429:
                time.sleep(3)
                continue
            return r
        except Exception:
            time.sleep(2)
    return None


def crossref_doi(doi: str):
    r = fetch("https://api.crossref.org/works/" + doi.replace("#", "%23"))
    if r is None or r.status_code != 200:
        return None
    try:
        return r.json()["message"]
    except Exception:
        return None


def datacite_doi(doi: str):
    r = fetch("https://api.datacite.org/dois/" + doi)
    if r is None or r.status_code != 200:
        return None
    try:
        return r.json()["data"]["attributes"]
    except Exception:
        return None


def arxiv_meta(aid: str):
    """arXiv API 要求请求间隔 >=3s，遇 503 退避重试。"""
    for attempt in range(4):
        time.sleep(3.2 if attempt == 0 else 6)
        r = fetch(f"https://export.arxiv.org/api/query?id_list={aid}", timeout=30)
        if r is None or r.status_code != 200:
            continue
        try:
            root = ET.fromstring(r.content)
        except Exception:
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        e = root.find("a:entry", ns)
        if e is None:
            return None
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        if not title or "Error" in title:
            return None
        authors = [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)]
        pub = e.findtext("a:published", "", ns) or ""
        return {"title": title, "authors": [a for a in authors if a],
                "year": pub[:4], "id": e.findtext("a:id", "", ns)}
    return None


def arxiv_title_search(title: str):
    """按标题在 arXiv 检索（用于只给了会议名、没给 arXiv 号的条目）。"""
    q = "ti:" + requests.utils.quote('"' + title.split(":")[0][:80] + '"')
    for attempt in range(3):
        time.sleep(3.2 if attempt == 0 else 6)
        r = fetch(f"https://export.arxiv.org/api/query?search_query={q}&max_results=3", timeout=30)
        if r is None or r.status_code != 200:
            continue
        try:
            root = ET.fromstring(r.content)
        except Exception:
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        out = []
        for e in root.findall("a:entry", ns):
            t = " ".join((e.findtext("a:title", "", ns) or "").split())
            if not t or "Error" in t:
                continue
            out.append({"title": t, "year": (e.findtext("a:published", "", ns) or "")[:4],
                        "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
                        "id": e.findtext("a:id", "", ns)})
        return out
    return []


def doi_resolves(doi: str) -> bool:
    r = fetch("https://doi.org/api/handles/" + doi, timeout=20)
    if r is None:
        return False
    try:
        return r.status_code == 200 and r.json().get("responseCode") == 1
    except Exception:
        return False


def s2_search(title: str, limit=5):
    r = fetch(
        "https://api.semanticscholar.org/graph/v1/paper/search?query="
        + requests.utils.quote(title)
        + f"&limit={limit}&fields=title,authors,year,externalIds,venue"
    )
    if r is None or r.status_code != 200:
        return []
    try:
        return r.json().get("data", [])
    except Exception:
        return []


def crossref_search(title: str):
    r = fetch(
        "https://api.crossref.org/works?rows=5&select=DOI,title,author,issued,container-title&query.bibliographic="
        + requests.utils.quote(title)
    )
    if r is None or r.status_code != 200:
        return []
    try:
        return r.json()["message"]["items"]
    except Exception:
        return []


def first_family(authors):
    if not authors:
        return ""
    a = authors[0]
    return a.get("family") or a.get("name") or "" if isinstance(a, dict) else str(a)


def audit(name: str, refs: list[str]):
    out = []
    for i, ref in enumerate(refs, 1):
        tid = f"{name}-{i:02d}"
        rec = {"id": tid, "ref": ref, "claim_title": guess_title(ref)}
        doi = DOI_RE.search(ref)
        arx = ARXIV_RE.search(ref)
        doi = doi.group(0).rstrip(".") if doi else None
        rec["doi"] = doi
        rec["arxiv"] = arx.group(1) if arx else None

        found = None
        via = None

        if doi and doi.lower().startswith("10.48550/arxiv."):
            aid = doi.split("arXiv.", 1)[1]
            m = arxiv_meta(aid)
            if m:
                found = {"title": m["title"], "year": m["year"], "authors": m["authors"],
                         "venue": "arXiv", "doi": doi}
                via = f"arXiv:{aid}"
            else:
                rec["status"] = "DOI_NOT_RESOLVED"
        elif doi:
            m = crossref_doi(doi)
            if m:
                titles = m.get("title") or [""]
                authors = [first_family([a]) for a in (m.get("author") or [])]
                year = ""
                for k in ("published-print", "published-online", "issued", "created"):
                    dp = (m.get(k) or {}).get("date-parts") or [[]]
                    if dp and dp[0] and dp[0][0]:
                        year = str(dp[0][0])
                        break
                found = {"title": titles[0], "year": year, "authors": authors,
                         "venue": (m.get("container-title") or [""])[0],
                         "volume": m.get("volume"), "page": m.get("page"),
                         "doi": doi}
                via = "CrossRef"
            else:
                d = datacite_doi(doi)
                if d:
                    found = {"title": (d.get("titles") or [{}])[0].get("title", ""),
                             "year": str(d.get("publicationYear") or ""),
                             "authors": [a.get("name", "") for a in (d.get("creators") or [])],
                             "venue": (d.get("publisher") or ""), "doi": doi}
                    via = "DataCite"
                elif arx:
                    m = arxiv_meta(arx.group(1))
                    if m:
                        found = {"title": m["title"], "year": m["year"], "authors": m["authors"],
                                 "venue": "arXiv", "doi": doi}
                        via = f"arXiv:{arx.group(1)}"
                    else:
                        rec["status"] = "DOI_NOT_RESOLVED"
                else:
                    rec["status"] = "DOI_NOT_RESOLVED"
        elif arx:
            m = arxiv_meta(arx.group(1))
            if m:
                found = {"title": m["title"], "year": m["year"], "authors": m["authors"],
                         "venue": "arXiv", "doi": None}
                via = f"arXiv:{arx.group(1)}"
            else:
                rec["status"] = "ARXIV_NOT_FOUND"

        if found is not None:
            rec["resolved"] = found
            rec["via"] = via
            rec["title_sim"] = round(sim(rec["claim_title"], found["title"]), 3)
            rec["doi_registered"] = doi_resolves(doi) if doi else None
            rec["status"] = "VERIFIED" if rec["title_sim"] >= 0.82 else "TITLE_MISMATCH"
        elif rec.get("status") is None:
            # 无标识符：标题兜底检索
            cands = crossref_search(rec["claim_title"]) or []
            best = None
            for c in cands:
                t = (c.get("title") or [""])[0]
                s = sim(rec["claim_title"], t)
                if best is None or s > best[1]:
                    best = (c, s)
            if best and best[1] >= 0.75:
                c, s = best
                rec["resolved"] = {"title": (c.get("title") or [""])[0],
                                   "doi": c.get("DOI"),
                                   "venue": (c.get("container-title") or [""])[0]}
                rec["via"] = "CrossRef-title"
                rec["title_sim"] = round(s, 3)
                rec["status"] = "VERIFIED_TITLE_ONLY"
            else:
                ax = arxiv_title_search(rec["claim_title"])
                hit = None
                for c in ax:
                    s = sim(rec["claim_title"], c["title"])
                    if s >= 0.85 and (hit is None or s > hit[1]):
                        hit = (c, s)
                if hit:
                    c, s = hit
                    rec["resolved"] = {"title": c["title"], "year": c["year"], "doi": c["id"]}
                    rec["via"] = "arXiv-title"
                    rec["title_sim"] = round(s, 3)
                    rec["status"] = "VERIFIED_TITLE_ONLY"
                    out.append(rec)
                    print(f"{tid:14s} {rec['status']:18s} {rec['via']:18s} {c['title'][:70]}")
                    continue
                s2 = s2_search(rec["claim_title"])
                if s2:
                    s = sim(rec["claim_title"], s2[0]["title"])
                    rec["best_s2"] = {"title": s2[0]["title"], "year": s2[0].get("year"),
                                      "ids": s2[0].get("externalIds"), "sim": round(s, 3)}
                    rec["status"] = "NEEDS_MANUAL" if s < 0.75 else "VERIFIED_TITLE_ONLY"
                    if s >= 0.75:
                        rec["title_sim"] = round(s, 3)
                        rec["via"] = "SemanticScholar"
                else:
                    rec["status"] = "NOT_FOUND"
        out.append(rec)
        print(f"{tid:14s} {rec['status']:18s} {rec.get('via','-'):18s} "
              f"{(rec.get('resolved') or {}).get('title','')[:70]}")
        time.sleep(0.35)
    return out


if __name__ == "__main__":
    res = {
        "en": audit("EN", RAW["en"]),
        "zh": audit("ZH", RAW["zh"]),
        "conf": audit("CONF", RAW["conf"]),
    }
    json.dump(res, open(os.path.join(HERE, "ref_verification.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for k, v in res.items():
        bad = [r["id"] for r in v if r["status"] not in ("VERIFIED", "VERIFIED_TITLE_ONLY")]
        print(f"\n[{k}] {len(v)} 条，异常 {len(bad)}: {bad}")
