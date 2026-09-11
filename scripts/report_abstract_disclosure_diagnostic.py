#!/usr/bin/env python3
"""PLAN-005 단계 7-B′ — 초록 개시 진단 (판정 밖 · 읽기 전용 · 그래프를 바꾸지 않는다).

**왜 판정 밖인가.** 7-B(인용문헌 Disclosure 를 초록으로 보강)는 2단계 실측에서 성립하지 않았다 —
대조 문헌 g1·g2 36,516건에는 초록이 저장소에 없다. R∀ 는 개시집합이 클수록 후보에 들기 쉬우므로
인용문헌만 두껍게 하면 **목표 쪽만 유리한 평가 편향**이 생긴다(계획서 §17 · 사용자 결정 A).
그래서 이 스크립트는 V2·τ 판정에 쓰지 않고, 하나의 진단 질문만 답한다:

    "적중 상한(R∀ ∞ 적중 0.60)은 인용문헌 개시집합이 청구항만이라 얇아서인가?"

방법 — 초록이 있는 문헌만의 **제한 코퍼스** D_r 안에서, 같은 질의·같은 문헌에 대해
  (a) 청구항 유래 개시집합           Disc_claims(d)
  (b) 청구항 ∪ 초록 유래 개시집합     Disc_claims(d) ∪ Disc_abstract(d)
를 페어드로 비교한다(적중∞ · 후보 중앙값 · 커버율). 코퍼스가 작아 절대값은 단계 7 과 비교할 수 없고,
비교할 수 있는 것은 (a)→(b) 의 **차이**뿐이다. 그 밖에 Disclosure 없는 인용문헌 804 중 초록 접지가
비지 않는 수를 접두어별로 센다.

초록 원천 셋(전부 저장소 안): data/patents/fulltext_corpus.parquet(초록만 · KR 한국어 · JP/US 영어) ·
data/patents/cited_enriched/kipris.jsonl(KR 인용) · data/patents/rejected_patents_meta.parquet(rej).
링커는 A-Box 생성기와 같은 `sdkb_nb.make_bridge(morph=True, profile="patent-text")` 이고 개념은 바인딩
개념으로 거른다(ClaimProfile 과 같은 규칙).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sdkb_nb as S  # noqa: E402
import report_stage7_remeasure as s7  # noqa: E402
from build_abox_claim_features import CONCEPT_TYPES  # noqa: E402

OUT = ROOT / "data" / "reports" / "priorart_abstract_diagnostic.json"
FULLTEXT = ROOT / "data" / "patents" / "fulltext_corpus.parquet"
KIPRIS = ROOT / "data" / "patents" / "cited_enriched" / "kipris.jsonl"
REJ_META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
B_POP = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"


def _norm_key(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(s)).upper()


def doc_key_map() -> dict[str, str]:
    """cited_doc_id(KR-P-…)·정규형(patent:kr_…) 양쪽 표기 → publication_id."""
    ed = pd.read_parquet(EDGES)
    canon = ed[ed.cited_id.astype(str).str.startswith("patent:")]
    m = {}
    for doc, cid in zip(canon.cited_doc_id, canon.cited_id):
        if isinstance(doc, str):
            m[_norm_key(doc)] = cid.split(":", 1)[1]
    if B_POP.exists():
        b = pd.read_parquet(B_POP)
        for doc, cid, npl in zip(b.cited_doc_id, b.cited_id, b.is_npl):
            if not npl and isinstance(doc, str):
                m.setdefault(_norm_key(doc), str(cid).split(":", 1)[1])
    return m


def load_abstracts() -> tuple[dict[str, str], Counter]:
    """publication_id → 초록. 같은 문헌이 여러 원천에 있으면 긴 쪽을 쓴다(결정적)."""
    keymap = doc_key_map()
    out: dict[str, str] = {}
    stat: Counter = Counter()

    def put(pid: str, text, src: str) -> None:
        t = str(text or "").strip()
        if not t:
            return
        stat[f"source__{src}"] += 1
        if len(t) > len(out.get(pid, "")):
            out[pid] = t

    ft = pd.read_parquet(FULLTEXT, columns=["doc_id", "abstract"])
    for doc, ab in zip(ft.doc_id, ft.abstract):
        pid = keymap.get(_norm_key(doc))
        if pid:
            put(pid, ab, "fulltext_corpus")
        else:
            stat["fulltext_unmapped_doc"] += 1
    if KIPRIS.exists():
        for line in KIPRIS.open(encoding="utf-8"):
            r = json.loads(line)
            pid = keymap.get(_norm_key(r.get("cited_doc_id", "")))
            if pid:
                put(pid, r.get("abstract"), "kipris_jsonl")
    m = pd.read_parquet(REJ_META, columns=["patent_id", "abstract"])
    for pid, ab in zip(m.patent_id, m.abstract):
        put(str(pid).split(":", 1)[1], ab, "rejected_meta")
    return out, stat


def link_abstracts(abstracts: dict[str, str], bound: set[str]) -> dict[str, frozenset[str]]:
    br = S.make_bridge(ROOT, morph=True, profile="patent-text")
    out = {}
    for pid in sorted(abstracts):
        cs = set()
        for _term, hits in br.extract_from_text(abstracts[pid]).items():
            for nid, typ in hits:
                if typ in CONCEPT_TYPES and nid in bound:
                    cs.add(nid)
        out[pid] = frozenset(cs)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    gt, lb = s7.load_gt()
    L, identity = s7.layers_current(expand=True)
    abstracts, src_stat = load_abstracts()
    abs_concepts = link_abstracts(abstracts, L.bound)
    nonempty = {d for d, cs in abs_concepts.items() if cs}

    # ── 진단 1: 제한 코퍼스 페어드 비교 ──────────────────────────────────
    D_r = sorted(set(L.disc) & nonempty)
    disc_a = {d: L.disc[d] for d in D_r}
    disc_b = {d: frozenset(L.disc[d] | abs_concepts[d]) for d in D_r}
    La = s7.Layer("claims_only", L.profiles, disc_a, L.expansion)
    Lb = s7.Layer("claims_plus_abstract", L.profiles, disc_b, L.expansion)
    ra, rb = s7.per_query(La, gt), s7.per_query(Lb, gt)
    common = sorted(set(ra) & set(rb))
    hit_a = [int(ra[q]["all"]["hit"]) for q in common]
    hit_b = [int(rb[q]["all"]["hit"]) for q in common]
    sa, sb = s7.summarize(ra), s7.summarize(rb)
    cov_a, cov_b = s7.v3_summary(s7.v3_rows(La, gt, lb)), s7.v3_summary(s7.v3_rows(Lb, gt, lb))
    paired = {
        "queries": len(common),
        "hit_inf_claims_only": (sum(hit_a) / len(hit_a)) if hit_a else None,
        "hit_inf_claims_plus_abstract": (sum(hit_b) / len(hit_b)) if hit_b else None,
        "hit_inf_delta_bootstrap": s7.paired_bootstrap(hit_a, hit_b, s7.FROZEN["bootstrap_B"],
                                                       s7.FROZEN["seed"], s7.FROZEN["ci"]),
        "reach_all_median": [sa["all"]["reach_median"], sb["all"]["reach_median"]],
        "SPR_all@50": [sa["all"]["SPR@50"], sb["all"]["SPR@50"]],
        "SPR_all@1000": [sa["all"]["SPR@1000"], sb["all"]["SPR@1000"]],
        "best_single_coverage_median": [cov_a.get("best_single_coverage", {}).get("median"),
                                        cov_b.get("best_single_coverage", {}).get("median")],
        "disc_size_median": [st.median(len(v) for v in disc_a.values()) if disc_a else None,
                             st.median(len(v) for v in disc_b.values()) if disc_b else None],
    }

    # ── 진단 2: Disclosure 없는 인용문헌 중 초록 접지가 비지 않는 수 ───────
    cited = {c for s in gt.values() for c in s}
    no_disc = sorted(cited - set(L.disc))
    gain = [c for c in no_disc if c in nonempty]
    by_prefix = lambda xs: dict(Counter(c.split("_", 1)[0] for c in xs))  # noqa: E731
    rep = {
        "plan": "PLAN-005 단계 7-B′ · 초록 개시 진단 (판정 밖)",
        "generator": "scripts/report_abstract_disclosure_diagnostic.py",
        "generated": str(date.today()),
        "read_only": True,
        "verdict_use": False,
        "why_not_verdict": "대조 문헌 g1·g2 에 초록이 없어 인용문헌만 보강하면 목표 쪽만 유리하다 — "
                           "제한 코퍼스 안의 페어드 차이만 해석한다(계획서 §17).",
        "inputs": {
            "mappings/claim_features.parquet": hashlib.sha256((ROOT / "mappings/claim_features.parquet").read_bytes()).hexdigest(),
            "data/patents/fulltext_corpus.parquet": hashlib.sha256(FULLTEXT.read_bytes()).hexdigest(),
        },
        "identity_check_vs_abox_report": {k: v for k, v in identity.items() if k != "cited_without_disclosure_by_prefix"},
        "abstracts": {"documents_with_abstract": len(abstracts), "abstract_grounded_nonempty": len(nonempty),
                      "sources": dict(src_stat),
                      "concepts_per_abstract_median": st.median(len(v) for v in abs_concepts.values()) if abs_concepts else None},
        "restricted_corpus": {"documents": len(D_r), "share_of_disclosures": round(len(D_r) / len(L.disc), 4) if L.disc else None},
        "paired_comparison": paired,
        "cited_without_disclosure": {"total": len(no_disc), "by_prefix": by_prefix(no_disc),
                                     "gain_nonempty_abstract_set": len(gain), "gain_by_prefix": by_prefix(gain)},
        "limitations": [
            "제한 코퍼스는 초록이 있는 문헌뿐이라 N 이 작다 — 후보 수·SPR 절대값은 단계 7 사다리와 비교 불가.",
            "JP·US 초록은 영어라 한글 표면형은 닿지 않고 영문 canonical·synonym 만 걸린다.",
            "초록 접지가 비지 않는 인용문헌이 목표 노드가 되려면 대조군도 같은 원천을 가져야 한다(별도 1단계).",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p = paired
    print(f"제한 코퍼스 {len(D_r):,} 문헌 · 질의 {p['queries']} · 적중∞ {p['hit_inf_claims_only']:.4f} → "
          f"{p['hit_inf_claims_plus_abstract']:.4f} (CI {p['hit_inf_delta_bootstrap']['ci']}) · "
          f"후보 중앙 {p['reach_all_median']} · 개시집합 중앙 {p['disc_size_median']}")
    print(f"Disclosure 없는 인용문헌 {len(no_disc)} 중 초록 접지 비지 않음 {len(gain)} {by_prefix(gain)}")
    print(f"→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
