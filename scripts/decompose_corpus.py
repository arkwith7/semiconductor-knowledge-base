#!/usr/bin/env python3
"""전 코퍼스 청구항 → feature 분해 (규칙 + flag 시 LLM). 중심축 데이터셋의 1단계.

소스:
  rejected  거절특허 1,000       — raw/…rejected_patents.jsonl 의 claims_full (구조화)
  cited     인용 선행기술 KR+US   — cited_enriched/{kipris.jsonl,bigquery_us.parquet} (청구항 블록)
  g2        소부장 G2 12,339      — graph_v2.ttl 의 ont:claimText (청구항 블록)

거절특허는 독립·종속항 전부 분해한다(종속항의 added-feature 가 §29② 진보성 판단의 초점).
cited·g2 는 독립항만(대비 단위). 규칙이 flag 한 청구항만 로컬 LLM 재분해.
증분 저장(features.jsonl) — 재실행 시 (source,patent,claim_no) 이미 처리분은 건너뛴다.
소스는 (patent, claim_no, text, depends_on) 4-튜플을 낸다(독립항 depends_on=[]).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decompose_claims import decompose, is_independent, split_claims  # noqa: E402
from llm_claim_validate import BACKEND, _conn, llm_decompose_batch  # noqa: E402

# 종속항이 참조하는 부모 청구항 번호 추출(인용·G2 는 구조화 depends_on 이 없어 텍스트에서 뽑는다).
_PARENT = re.compile(r"제\s*(\d+)\s*항|청구항\s*(\d+)|claims?\s+(\d+)", re.I)


def _parents(txt: str) -> list[int]:
    head = re.sub(r"^\s*\d+\s*[.)]\s*", "", txt.strip())[:120]  # 참조는 청구항 앞머리에 온다
    return sorted({int(g) for m in _PARENT.finditer(head) for g in m.groups() if g})

SDKB = Path("/home/arkwith/Dev/sdkb")
PD = Path("/home/arkwith/Dev/paper_data")
FEATURES = SDKB / "data" / "interim" / "claim_features.jsonl"


def src_rejected():
    f = SDKB / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
    for line in f.open():
        d = json.loads(line)
        tp = d["target_patent"]; pid = "rej:" + str(tp["application_number"])
        for c in (tp.get("claims_full") or []):   # 독립·종속 전부
            dep = [int(x) for x in (c.get("depends_on") or [])]
            yield pid, int(c["claim_no"]), c["text"], dep


def src_cited():
    kr = [json.loads(l) for l in (PD / "data/patents/cited_enriched/kipris.jsonl").open()]
    for r in kr:
        if (r.get("n_claims") or 0) > 0:
            for no, txt in split_claims(str(r["claims"])):   # 독립·종속 전부(Tier 2)
                dep = [] if is_independent(txt) else _parents(txt)
                yield "cited:" + r["cited_doc_id"], no, txt, dep
    import pandas as pd
    us = pd.read_parquet(PD / "data/patents/cited_enriched/bigquery_us.parquet")
    for _, r in us[us.n_claims.fillna(0) > 0].iterrows():
        for no, txt in split_claims(str(r["claims"])):
            dep = [] if is_independent(txt) else _parents(txt)
            yield "cited:" + r["cited_doc_id"], no, txt, dep


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
                yield pid, no, txt, []


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
    workers = int(os.getenv("LLM_WORKERS", "12"))
    cache = _conn()
    t0 = time.time()

    # 1단계: 규칙 분해(빠름·순차). LLM 대상 청구항의 텍스트를 모은다.
    pending: list[dict] = []
    llm_texts: list[str] = []
    for name in names:
        for pid, no, txt, dep in SOURCES[name]():
            if (name, pid, no) in done:
                continue
            dc = decompose(txt, no)
            feats = [{"seq": f.seq, "text": f.text, "marker": f.marker, "refs": list(f.refs)}
                     for f in dc.features]
            # 짧은 single 청구항은 진짜 1요소 — LLM 호출 낭비를 막는다.
            worth_llm = dc.flag_reason == "oversized_feature" or len(txt) > 150
            need_llm = dc.flagged and worth_llm and not args.no_llm
            pending.append({"source": name, "patent": pid, "claim_no": no, "depends_on": dep,
                            "txt": txt, "flag": dc.flag_reason, "feats": feats, "need_llm": need_llm})
            if need_llm:
                llm_texts.append(txt)
    print(f"[decompose] 규칙분해 {len(pending)}청구항 · LLM 대상 {len(llm_texts)} ({time.time()-t0:.0f}s)")

    # 2단계: LLM 재분해(병렬·캐시). 백엔드=bedrock 이면 동시 네트워크 호출로 시간 단축.
    llm_map = llm_decompose_batch(llm_texts, cache=cache, max_workers=workers) if llm_texts else {}

    # 3단계: 조립·기록. LLM 이 더 잘게 나눴으면 채택. feature 0 인 청구항은 SHACL 상 빈 청구항이라 스킵.
    fh = FEATURES.open("a")
    n_claim = n_feat = n_llm = n_skip = 0
    for r in pending:
        feats, method = r["feats"], "rule"
        if r["need_llm"]:
            llm = llm_map.get(r["txt"])
            if llm and len(llm) > len(feats):
                feats = [{"seq": i + 1, "text": t, "marker": "", "refs": []} for i, t in enumerate(llm)]
                method = "llm"; n_llm += 1
        if not feats:                      # 분해 결과 0요소 — 빈 청구항은 만들지 않는다(정직 계상)
            n_skip += 1
            continue
        fh.write(json.dumps({"source": r["source"], "patent": r["patent"], "claim_no": r["claim_no"],
                             "depends_on": r["depends_on"], "method": method, "flag": r["flag"],
                             "n_features": len(feats), "features": feats}, ensure_ascii=False) + "\n")
        n_claim += 1; n_feat += len(feats)
    fh.close(); cache.close()
    print(f"✓ {n_claim}청구항 → {n_feat}feature (LLM {n_llm}·{BACKEND}, 0요소 스킵 {n_skip}) "
          f"→ {FEATURES.name} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
