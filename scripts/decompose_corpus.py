#!/usr/bin/env python3
"""전 코퍼스 청구항 → feature 분해 (규칙 + flag 시 LLM). 중심축 데이터셋의 1단계.

소스:
  rejected  거절특허 1,000       — raw/…rejected_patents.jsonl 의 claims_full (구조화)
  cited     인용 선행기술 KR+US   — cited_enriched/{kipris.jsonl,bigquery_us.parquet} (청구항 블록)
  g2        소부장 G2 12,339      — graph_v2.ttl 의 ont:claimText (청구항 블록)

거절특허·인용(Tier 2)·g2(Tier 3) 전부 독립·종속항을 분해한다 — 종속항의 added-feature 가
§29② 진보성 판단의 초점이고 all-elements 대비의 완전 한정요소집합을 이룬다.
규칙이 flag 한 청구항만 LLM(Bedrock Haiku) 재분해.
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

# 2026-08-09(CR-016 §4): 여기 있던 절대경로 둘(SDKB·PD)을 리포 상대로 바꿨다. 인용 보강분을
# 옆 저장소에서 읽고 있었는데, 흡수된 collect_cited_biblio_claims.py 는 이 저장소의
# data/patents/cited_enriched/ 로 쓴다 — 원천이 둘이면 다시 갈라진다. 교체 전에 대조했다:
# 읽는 5파일(kipris.jsonl · bigquery{,_us,_b_layer,_us_b_layer}.parquet)이 **바이트 동일**이라
# 산출은 바뀌지 않는다.
SDKB = Path(__file__).resolve().parents[1]
ENRICHED = SDKB / "data" / "patents" / "cited_enriched"
FEATURES = SDKB / "data" / "interim" / "claim_features.jsonl"


def src_rejected():
    f = SDKB / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
    for line in f.open():
        d = json.loads(line)
        tp = d["target_patent"]
        pid = "rej:" + str(tp["application_number"])
        for c in (tp.get("claims_full") or []):   # 독립·종속 전부
            dep = [int(x) for x in (c.get("depends_on") or [])]
            yield pid, int(c["claim_no"]), c["text"], dep


def src_cited():
    kr = [json.loads(line) for line in (ENRICHED / "kipris.jsonl").open()]
    for r in kr:
        if (r.get("n_claims") or 0) > 0:
            for no, txt in split_claims(str(r["claims"])):   # 독립·종속 전부(Tier 2)
                dep = [] if is_independent(txt) else _parents(txt)
                yield "cited:" + r["cited_doc_id"], no, txt, dep
    import pandas as pd
    # B층(CR-008) parquet 을 함께 읽는다 — CR-011. KR B층 235건은 위 kipris.jsonl 에 이미 섞여
    # 들어오지만 US B층은 별도 파일이라 원천 목록에 없으면 도달하지 못한다.
    # bigquery_b_layer(JP·WO·CN·EP)는 현재 n_claims>0 이 0건이라 산출이 없다 — D-05 가 해소되면
    # 자동으로 흐르도록 통로만 열어 둔다(고치는 것이 아니라 통로다 · CR-011 비목표 ⓐ 와 무충돌).
    for pq in ("bigquery_us.parquet", "bigquery_b_layer.parquet", "bigquery_us_b_layer.parquet"):
        df = pd.read_parquet(ENRICHED / pq)
        for _, r in df[df.n_claims.fillna(0) > 0].iterrows():
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
        for no, txt in split_claims(str(sol["c"].value)):   # 독립·종속 전부(Tier 3)
            dep = [] if is_independent(txt) else _parents(txt)
            yield pid, no, txt, dep


def src_g1():
    """주 대비 코퍼스 G1(삼성·SK하이닉스) 청구항 → feature (§G1 Phase C+D).

    G2 와 완전 대칭 — 독립·종속 전부. 종속 added-feature 는 §29② 진보성 판단의 초점이며,
    판단(Tier 1)·인용(Tier 2)·코퍼스(Tier 3) 세 축과 주 대비축의 커버리지 비대칭을 해소한다(플랜 §G1 D).
    """
    from pyoxigraph import RdfFormat, Store
    store = Store()
    store.bulk_load(path=str(SDKB.parent / "SKKU/sdkb-foresight-paper/data/processed/graph_v1.ttl"),
                    format=RdfFormat.TURTLE)
    q = ("PREFIX ont: <https://w3id.org/sdkb/ont/> "
         "SELECT ?p ?c WHERE { ?p ont:claimText ?c }")
    for sol in store.query(q):
        pid = "g1:" + str(sol["p"].value).rsplit("/", 1)[-1]
        for no, txt in split_claims(str(sol["c"].value)):
            dep = [] if is_independent(txt) else _parents(txt)   # 종속 포함(Phase D·Tier 4)
            yield pid, no, txt, dep


def src_b_queries():
    """CR-012 — B층 확증분할 질의 200건의 청구항.

    pid 접두를 A층 질의와 **같은 `rej:`** 로 둔다. `build_abox_claim_features.py::_patent_iri()`
    가 이미 `rej:{출원번호}` → `data:patent/kr_{출원번호}` 를 해소하므로, 접두를 새로 만들면
    해소 코드를 고쳐야 하고 그 순간 A층/B층이 다른 경로를 타게 된다.

    청구항 덩어리를 `split_claims` 로 다시 가르는 것은 인용 축(`src_cited`)과 같다 —
    KIPRIS 는 구조화 depends_on 을 주지 않으므로 A층 SIRP(`claims_full`)처럼 읽을 수 없고,
    참조는 본문에서 뽑는다. 이 비대칭은 리포트에 남긴다.
    """
    f = SDKB / "data" / "patents" / "b_layer_queries_raw.jsonl"
    for line in f.open():
        if not line.strip():
            continue
        d = json.loads(line)
        blob = str(d.get("claims") or "")
        if not blob:
            continue
        pid = "rej:" + str(d["application_number"])
        for no, txt in split_claims(blob):     # 독립·종속 전부
            dep = [] if is_independent(txt) else _parents(txt)
            yield pid, no, txt, dep


SOURCES = {"rejected": src_rejected, "cited": src_cited, "g2": src_g2, "g1": src_g1,
           "b_queries": src_b_queries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=[*SOURCES, "all"])
    ap.add_argument("--no-llm", action="store_true", help="규칙만 (LLM 생략)")
    args = ap.parse_args()

    FEATURES.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple] = set()
    if FEATURES.exists():
        for line in FEATURES.open():
            r = json.loads(line)
            done.add((r["source"], r["patent"], r["claim_no"]))
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
                method = "llm"
                n_llm += 1
        if not feats:                      # 분해 결과 0요소 — 빈 청구항은 만들지 않는다(정직 계상)
            n_skip += 1
            continue
        fh.write(json.dumps({"source": r["source"], "patent": r["patent"], "claim_no": r["claim_no"],
                             "depends_on": r["depends_on"], "method": method, "flag": r["flag"],
                             "n_features": len(feats), "features": feats}, ensure_ascii=False) + "\n")
        n_claim += 1
        n_feat += len(feats)
    fh.close()
    cache.close()
    print(f"✓ {n_claim}청구항 → {n_feat}feature (LLM {n_llm}·{BACKEND}, 0요소 스킵 {n_skip}) "
          f"→ {FEATURES.name} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
