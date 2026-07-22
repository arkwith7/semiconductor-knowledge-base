#!/usr/bin/env python3
"""전 코퍼스 청구항 → feature 분해 (규칙 + flag 시 LLM). 중심축 데이터셋의 1단계.

소스:
  rejected  거절특허 1,000       — raw/…rejected_patents.jsonl 의 claims_full (구조화)
  cited     인용 선행기술 KR+US   — cited_enriched/{kipris.jsonl,bigquery_us.parquet} (청구항 블록)
  g2        소부장 G2 12,339      — graph_v2.ttl 의 ont:claimText (청구항 블록)

독립항(신규성/진보성 대비 단위)만 분해한다. 규칙이 flag 한 청구항만 로컬 LLM 재분해.
증분 저장(features.jsonl) — 재실행 시 (source,patent,claim_no) 이미 처리분은 건너뛴다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decompose_claims import decompose, is_independent, split_claims  # noqa: E402
from llm_claim_validate import _conn, llm_decompose  # noqa: E402

SDKB = Path("/home/arkwith/Dev/sdkb")
PD = Path("/home/arkwith/Dev/paper_data")
FEATURES = SDKB / "data" / "interim" / "claim_features.jsonl"


def src_rejected():
    f = SDKB / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
    for line in f.open():
        d = json.loads(line)
        tp = d["target_patent"]; pid = "rej:" + str(tp["application_number"])
        for c in (tp.get("claims_full") or []):
            if not c.get("depends_on"):   # 독립항
                yield pid, int(c["claim_no"]), c["text"]


def src_cited():
    kr = [json.loads(l) for l in (PD / "data/patents/cited_enriched/kipris.jsonl").open()]
    for r in kr:
        if (r.get("n_claims") or 0) > 0:
            for no, txt in split_claims(str(r["claims"])):
                if is_independent(txt):
                    yield "cited:" + r["cited_doc_id"], no, txt
    import pandas as pd
    us = pd.read_parquet(PD / "data/patents/cited_enriched/bigquery_us.parquet")
    for _, r in us[us.n_claims.fillna(0) > 0].iterrows():
        for no, txt in split_claims(str(r["claims"])):
            if is_independent(txt):
                yield "cited:" + r["cited_doc_id"], no, txt


def src_g2():
    from pyoxigraph import RdfFormat, Store
    store = Store()
    store.bulk_load(path=str(SDKB.parent / "SKKU/sdkb-foresight-paper/data/processed/graph_v2.ttl"),
                    format=RdfFormat.TURTLE)
    q = ("PREFIX ont: <https://w3id.org/sdkb/ont/> "
         "SELECT ?p ?c WHERE { ?p ont:claimText ?c }")
    for sol in store.query(q):
        pid = "g2:" + str(sol["p"].value).rsplit("/", 1)[-1]
        for no, txt in split_claims(str(sol["c"].value)):
            if is_independent(txt):
                yield pid, no, txt


SOURCES = {"rejected": src_rejected, "cited": src_cited, "g2": src_g2}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=[*SOURCES, "all"])
    ap.add_argument("--no-llm", action="store_true", help="규칙만 (LLM 생략)")
    args = ap.parse_args()

    FEATURES.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple] = set()
    if FEATURES.exists():
        for line in FEATURES.open():
            r = json.loads(line); done.add((r["source"], r["patent"], r["claim_no"]))
    print(f"[decompose] 기처리 {len(done)}청구항")

    names = list(SOURCES) if args.source == "all" else [args.source]
    cache = _conn()
    fh = FEATURES.open("a")
    n_claim = n_feat = n_llm = 0
    t0 = time.time()
    for name in names:
        for pid, no, txt in SOURCES[name]():
            key = (name, pid, no)
            if key in done:
                continue
            dc = decompose(txt, no)
            method = "rule"
            feats = [{"seq": f.seq, "text": f.text, "marker": f.marker, "refs": list(f.refs)}
                     for f in dc.features]
            # 짧은 single 청구항은 진짜 1요소 — LLM 호출 낭비를 막는다.
            worth_llm = dc.flag_reason == "oversized_feature" or len(txt) > 150
            if dc.flagged and worth_llm and not args.no_llm:
                llm = llm_decompose(txt, cache=cache)
                if llm and len(llm) > len(feats):     # LLM 이 더 잘게 나눴을 때만 채택
                    feats = [{"seq": i + 1, "text": t, "marker": "", "refs": []}
                             for i, t in enumerate(llm)]
                    method = "llm"; n_llm += 1
            fh.write(json.dumps({"source": name, "patent": pid, "claim_no": no,
                                 "method": method, "flag": dc.flag_reason,
                                 "n_features": len(feats), "features": feats},
                                ensure_ascii=False) + "\n")
            fh.flush()
            done.add(key); n_claim += 1; n_feat += len(feats)
            if n_claim % 200 == 0:
                print(f"  {name}: {n_claim}청구항 · {n_feat}feature · LLM {n_llm} · {time.time()-t0:.0f}s")
    fh.close(); cache.close()
    print(f"✓ {n_claim}청구항 → {n_feat}feature (LLM {n_llm}) → {FEATURES.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
