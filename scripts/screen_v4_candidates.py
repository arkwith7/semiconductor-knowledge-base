#!/usr/bin/env python3
"""PLAN-005 §5 V4-2 — 연구노트 프록시 후보의 LLM 독립 2인 판정 (사람 판정의 전처리).

**이 스크립트는 정답을 만들지 않는다.** 사람 2인 코딩을 **대체하지 않고 줄인다** —
두 모델이 **독립적으로** 판정하고, **불일치분 + 층화 표본만** 사람에게 올린다.
LLM 만으로 판정을 닫으면 PLAN-004 §4-1(정답은 온톨로지 밖에서) · PLAN-005 §7-5(순환 금지)
위반이다.

동결된 설계 (2026-09-05 · 사용자 승인):

  판정자 1  로컬 ollama `gemma3:27b` — egress 없음, 파이프라인과 무관한 모델 계열
  판정자 2  Bedrock `global.anthropic.claude-sonnet-5`
            **하이쿠를 쓰지 않는 이유**: Haiku 4.5 는 코퍼스 청구항 LLM 분해에 이미 쓰였다
            (claim_features 의 llm 분해 203,207행). 판정자로 쓰면 자기 결과를 채점한다.
  후보      IDF 가중 개념 중첩 top-K. 존재 양화 도달은 코퍼스의 40%라 순위 없이는 못 넘긴다.

  **후보 풀은 텍스트를 읽을 수 있는 문헌으로 한정된다 — 접지 코퍼스 31,808건 중 2,926건
  (9.2%)뿐이다.** 읽을 수 없는 문헌은 판정할 수 없다. 이 한정은 V4-2 의 범위이며 리포트에
  명기한다(진단 §2.3 의 또 다른 발현이다).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    if (ROOT / ".env").exists():
        load_dotenv(ROOT / ".env")
except ImportError:
    pass

OLLAMA = "http://localhost:11434/api/chat"
J1 = os.getenv("V4_JUDGE1", "gemma3:27b")
J2 = os.getenv("V4_JUDGE2", "global.anthropic.claude-sonnet-5")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
CACHE = ROOT / "data" / "interim" / "v4_screen_cache.sqlite"
OUT = ROOT / "data" / "reports" / "v4_screening.json"

SYSTEM = (
    "당신은 반도체 분야 선행기술조사 보조자다. 연구 아이디어 하나와 후보 문헌 하나를 받는다. "
    "후보 문헌이 그 연구 아이디어의 **선행기술 검토 대상으로 볼 만한가**를 판정한다. "
    "판정 기준은 '같은 기술 문제 또는 같은 기술 수단을 다루는가'이며, 동일 발명일 필요는 없다. "
    'JSON 한 줄만 출력한다: {"relevant": true|false, "reason": "한 문장"}'
)


def _conn():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(CACHE, timeout=60)
    c.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, verdict TEXT)")
    return c


def _parse(s: str) -> dict | None:
    m = re.search(r"\{.*?\}", str(s), re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return {"relevant": bool(d.get("relevant")), "reason": str(d.get("reason", ""))[:300]}
    except Exception:  # noqa: BLE001
        return None


def ask_ollama(prompt: str) -> dict | None:
    r = requests.post(OLLAMA, json={
        "model": J1, "stream": False,
        "options": {"temperature": 0, "seed": 0, "num_ctx": 8192},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}]}, timeout=300)
    r.raise_for_status()
    return _parse(r.json()["message"]["content"])


_BR = None


def ask_bedrock(prompt: str) -> dict | None:
    global _BR
    if _BR is None:
        import boto3
        _BR = boto3.client("bedrock-runtime", region_name=REGION)
    for attempt in range(6):
        try:
            r = _BR.converse(
                modelId=J2, system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                # Sonnet 5 는 `temperature` 를 폐기했다 — 보내면 ValidationException 이 난다.
                # 결정성은 호출 파라미터가 아니라 **캐시된 산출물**로 확보한다(V4-1 과 같은 규율).
                inferenceConfig={"maxTokens": 1024})
            return _parse("".join(b.get("text", "") for b in r["output"]["message"]["content"]))
        except Exception as e:  # noqa: BLE001
            if "Throttl" in type(e).__name__ or "Throttl" in str(e):
                time.sleep(min(2 ** attempt * 0.5, 16)); continue
            raise
    return None


def load_texts():
    """후보 문헌의 읽을 수 있는 텍스트. 없는 문헌은 후보가 될 수 없다."""
    meta = pd.read_parquet(ROOT / "data" / "patents" / "rejected_patents_meta.parquet",
                           columns=["patent_id", "title", "abstract", "claim1"])
    meta["pid"] = meta.patent_id.str.replace("^patent:", "", regex=True)
    txt = {}
    for r in meta.itertuples():
        if isinstance(r.claim1, str) and len(r.claim1) > 20:
            txt[r.pid] = {"title": str(r.title or "")[:200], "body": r.claim1[:1200]}
    ft = pd.read_parquet(ROOT / "data" / "patents" / "fulltext_corpus.parquet")
    ed = pd.read_parquet(ROOT / "data" / "patents" / "prior_art_edges.parquet")
    mp = dict(zip(ed.cited_id.str.replace("^patent:", "", regex=True), ed.cited_doc_id))
    fmap = {r.doc_id: r for r in ft[ft.has_content].itertuples()}
    for cid, did in mp.items():
        if cid in txt or did not in fmap:
            continue
        r = fmap[did]
        body = (str(r.abstract or "") + " " + str(r.claims or "")).strip()
        if len(body) > 20:
            txt[cid] = {"title": str(r.title or "")[:200], "body": body[:1200]}
    return txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--limit-notes", type=int, default=0)
    ap.add_argument("--judges", default="both", choices=["both", "ollama", "bedrock"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    from report_v4_robustness import build_linker, link
    from report_priorart_baseline import load_concepts
    doc, _q, _gt = load_concepts()
    texts = load_texts()
    pool = {d: cs for d, cs in doc.items() if d in texts}
    cm = json.loads((ROOT / "mappings" / "concept_mapping.json").read_text(encoding="utf-8"))
    cmeta = cm["profiles"]["patent-text"]["concept_meta"]
    N = cmeta["df_denominator"]
    dfm = {k: v.get("df_abox", 0) for k, v in cmeta["concepts"].items()}
    idf = lambda c: math.log((N + 1) / (dfm.get(c, 0) + 1))  # noqa: E731

    inv = {}
    for d, cs in pool.items():
        for c in cs:
            inv.setdefault(c, set()).add(d)

    notes = json.loads((ROOT / "data" / "sources" / "arxiv" / "notes_cohort.json")
                       .read_text(encoding="utf-8"))["items"]
    if a.limit_notes:
        notes = notes[:a.limit_notes]

    ent = build_linker()
    pairs = []
    for nt in notes:
        E = link(nt["title"] + " " + nt["abstract"], ent)
        sc = {}
        for c in E:
            w = idf(c)
            for d in inv.get(c, ()):
                sc[d] = sc.get(d, 0) + w
        top = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))[:a.topk]
        for rank, (d, s) in enumerate(top, 1):
            pairs.append({"arxiv_id": nt["arxiv_id"], "topic": nt["topic"], "doc": d,
                          "rank": rank, "score": round(s, 4),
                          "note_text": (nt["title"] + ". " + nt["abstract"])[:1500]})
    print(f"후보 풀 {len(pool)}건(텍스트 보유) · 노트 {len(notes)} × top{a.topk} = 판정쌍 {len(pairs)}")

    con = _conn()
    judges = ([("ollama", J1, ask_ollama)] if a.judges in ("both", "ollama") else []) + \
             ([("bedrock", J2, ask_bedrock)] if a.judges in ("both", "bedrock") else [])

    for tag, model, fn in judges:
        todo = []
        for p in pairs:
            k = f"{model}|{p['arxiv_id']}|{p['doc']}"
            if not con.execute("SELECT 1 FROM cache WHERE key=?", (k,)).fetchone():
                todo.append((k, p))
        print(f"\n[{tag}] {model} · 신규 {len(todo)}/{len(pairs)}")
        if not todo:
            continue
        t0 = time.time()
        w = 2 if tag == "ollama" else a.workers
        def job(item):
            k, p = item
            t = texts[p["doc"]]
            prompt = (f"[연구 아이디어]\n{p['note_text']}\n\n"
                      f"[후보 문헌]\n제목: {t['title']}\n본문: {t['body']}")
            return k, fn(prompt)
        with ThreadPoolExecutor(max_workers=w) as ex:
            for i, f in enumerate(as_completed([ex.submit(job, it) for it in todo]), 1):
                try:
                    k, v = f.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  실패 {type(e).__name__} {str(e)[:100]}"); continue
                if v is not None:
                    con.execute("INSERT OR REPLACE INTO cache VALUES (?,?)",
                                (k, json.dumps(v, ensure_ascii=False)))
                if i % 20 == 0:
                    con.commit()
                    print(f"  {i}/{len(todo)}  {(time.time()-t0)/i:.1f}s/건")
        con.commit()

    rows = []
    for p in pairs:
        r = dict(p); r.pop("note_text")
        for tag, model in (("j1", J1), ("j2", J2)):
            g = con.execute("SELECT verdict FROM cache WHERE key=?",
                            (f"{model}|{p['arxiv_id']}|{p['doc']}",)).fetchone()
            v = json.loads(g[0]) if g else None
            r[tag] = None if v is None else v["relevant"]
            r[tag + "_reason"] = "" if v is None else v["reason"]
        rows.append(r)
    df = pd.DataFrame(rows)
    both = df[df.j1.notna() & df.j2.notna()]
    agree = (both.j1 == both.j2)
    po = float(agree.mean()) if len(both) else None
    # Cohen κ (두 LLM 사이 — 사람 κ 가 아니다)
    kappa = None
    if len(both):
        p1, p2 = both.j1.mean(), both.j2.mean()
        pe = p1 * p2 + (1 - p1) * (1 - p2)
        kappa = (po - pe) / (1 - pe) if pe < 1 else None

    rep = {
        "generated": str(date.today()), "plan": "PLAN-005 §5 V4-2 (LLM 1차 스크리닝)",
        "judges": {"j1": J1, "j2": J2},
        "candidate_pool": {"grounded_corpus": len(doc), "with_text": len(pool),
                           "coverage": round(len(pool) / len(doc), 4),
                           "note": ("읽을 수 없는 문헌은 판정할 수 없다. V4-2 는 텍스트 보유 "
                                    "문헌으로 한정된 범위의 측정이다(진단 §2.3).")},
        "pairs": len(df), "judged_by_both": len(both),
        "j1_relevant_rate": round(float(both.j1.mean()), 4) if len(both) else None,
        "j2_relevant_rate": round(float(both.j2.mean()), 4) if len(both) else None,
        "observed_agreement": round(po, 4) if po is not None else None,
        "cohen_kappa_llm_llm": round(kappa, 4) if kappa is not None else None,
        "disagreements": int((~agree).sum()) if len(both) else None,
        "human_queue": {
            "note": ("사람 2인 코딩 대상 — 이 스크립트는 정답을 만들지 않는다. "
                     "불일치 전량 + 일치분 층화 표본을 사람이 판정하고 κ 는 **사람 2인 사이**에서 낸다."),
            "disagreement_rows": int((~agree).sum()) if len(both) else None,
        },
        "by_topic": (both.groupby("topic")
                     .agg(pairs=("doc", "size"), j1=("j1", "mean"), j2=("j2", "mean"),
                          agree=("j1", lambda s: float((s == both.loc[s.index, "j2"]).mean())))
                     .round(4).to_dict("index") if len(both) else {}),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    csv = a.out.with_suffix(".csv")
    df.to_csv(csv, index=False)
    print(f"\n판정쌍 {len(df)} · 양쪽 판정 {len(both)}")
    if len(both):
        print(f"  관련 판정률  j1={rep['j1_relevant_rate']}  j2={rep['j2_relevant_rate']}")
        print(f"  일치율 {rep['observed_agreement']} · κ(LLM-LLM) {rep['cohen_kappa_llm_llm']} "
              f"· 불일치 {rep['disagreements']}")
    print(f"→ {a.out}\n→ {csv} (사람 코딩 시트)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
