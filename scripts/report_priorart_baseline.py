#!/usr/bin/env python3
"""PLAN-005 단계 1 — V1~V3 기준선 계수 (읽기 전용).

**이 스크립트는 자원을 바꾸지 않는다.** 재구성 전의 눈금을 박는 것이 목적이며,
PLAN-005 §5 V5 *"재구성 전에 V1–V4 를 현 자원에서 1회 산출하고 커밋한다"* 의 산출물이다.

동결된 조작적 정의 (결과를 보기 전에 정한다 · §1-2):

  V1 공리 절제 — R-Box 공리 a 를 뺀 그래프에서 CQ 스위트를 전량 재실행한다.
      a 가 "소비된다" ⟺ 응답 행 수 벡터가 변한다. 변하지 않으면 자원에 넣을 근거가 없다.

  V2 도달 — Reach(q) 는 **오늘 존재하는 유일한 의미 경로**인 개념 공유(존재 양화,
      `sharesConceptWith` 의 퇴화형, 깊이 1)로 정의한다.
        E(q)  = q 의 독립항 한정요소에 접지된 개념 집합
        C(d)  = 문헌 d 에 접지된 개념 집합
        Reach(q) = { d ≠ q : C(d) ∩ E(q) ≠ ∅ }
        Target(q) = 코퍼스에 실재하는 q 의 심사관 인용문헌  ← **퇴화형 목표 노드**
        SemanticPathRecall@S = |{ q : Target∩Reach ≠ ∅ ∧ |Reach(q)| ≤ S }| / |Q|
      **목표 노드는 퇴화형이다** — 정본인 `ont:Disclosure` 는 클래스 선언도 인스턴스도
      0건이라 오늘은 잴 수 없다(PLAN-005 §5 V2). 그 사실을 리포트에 함께 적는다.
      **마스킹은 구성으로 지켜진다** — Reach 계산에 정답 간선을 한 번도 읽지 않는다.
      특이도로 |Reach(q)| 중앙값을 **반드시 함께** 낸다. 이것이 없으면 지표에 퇴화
      최적해가 있다(흔한 개념 하나를 모든 문헌에 붙이면 도달률이 1 에 접근한다).

  V3 커버 — cov(q,d) = |E(q) ∩ C(d)| / |E(q)| (신규성 프록시: 단일 문헌 포함률)
      진보성: 심사관 인용 쌍의 합집합 커버가 단일 최대를 넘는 폭 ΔCoverage.

원천은 `data/**` 의 parquet 이다(§1-1 진실의 원천). A-Box TTL 은 이 parquet 에서
생성되므로 같은 값이며, 863 MB TTL 을 인메모리로 올리지 않기 위해 원천을 직접 읽는다.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from datetime import date
from pathlib import Path

import pandas as pd
from rdflib import RDF, RDFS, OWL, Graph, URIRef

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_cq import DEFAULT_DATA, CQ_DIR, parse_cq, load_graph, run as run_cqs  # noqa: E402

ONT = "https://w3id.org/sdkb/ont/"
OUT = ROOT / "data" / "reports" / "priorart_baseline.json"

TBOX = [
    "sdkb-core.ttl", "sdkb-patent.ttl", "sdkb-commercialization.ttl",
    "sdkb-foresight.ttl", "sdkb-rbv.ttl", "sdkb-governance.ttl", "sdkb-governance-kr.ttl",
]


# ── V1 ────────────────────────────────────────────────────────────────────────
def rbox_axioms(g: Graph) -> list[dict]:
    """SDKB 자체 이름공간의 추론 공리 전량을 (술어, 트리플) 로 열거한다."""
    out = []
    for pred, kind in (
        (RDF.type, None), (RDFS.subPropertyOf, "subPropertyOf"),
        (OWL.equivalentClass, "equivalentClass"), (OWL.inverseOf, "inverseOf"),
        (OWL.propertyChainAxiom, "propertyChainAxiom"), (OWL.disjointWith, "disjointWith"),
        (OWL.hasKey, "hasKey"),
    ):
        if kind is None:
            for cls, lab in ((OWL.TransitiveProperty, "TransitiveProperty"),
                             (OWL.SymmetricProperty, "SymmetricProperty"),
                             (OWL.FunctionalProperty, "FunctionalProperty")):
                for s in g.subjects(RDF.type, cls):
                    if str(s).startswith(ONT):
                        out.append({"kind": lab, "term": str(s)[len(ONT):],
                                    "triples": [(s, RDF.type, cls)]})
            continue
        for s, _, o in g.triples((None, pred, None)):
            if str(s).startswith(ONT):
                out.append({"kind": kind, "term": str(s)[len(ONT):],
                            "target": str(o).split("/")[-1].split("#")[-1],
                            "triples": [(s, pred, o)]})
    return out


def v1_ablation() -> dict:
    cqs = [parse_cq(p) for p in sorted(CQ_DIR.glob("*.rq"))]
    tbox = Graph()
    for f in TBOX:
        tbox.parse(ROOT / "ontology" / f, format="turtle")
    axioms = rbox_axioms(tbox)

    g, loaded, missing = load_graph(DEFAULT_DATA)
    base = {r.name: r.rows for r in run_cqs(g, cqs)}

    results = []
    for ax in axioms:
        # 공백노드 목적어(예: equivalentClass 의 owl:unionOf 표현)는 그래프마다 식별자가
        # 달라 트리플 동일성으로 잡히지 않는다. (주어, 술어)로 실제 그래프에서 되찾는다.
        removed = []
        for s_, p_, o_ in ax["triples"]:
            if (s_, p_, o_) in g:
                removed.append((s_, p_, o_))
            else:
                removed += [(s_, p_, oo) for oo in g.objects(s_, p_)]
        for t in removed:
            g.remove(t)
        after = {r.name: r.rows for r in run_cqs(g, cqs)}
        for t in removed:
            g.add(t)
        delta = {k: [base[k], after[k]] for k in base if base[k] != after[k]}
        results.append({
            "kind": ax["kind"], "term": ax["term"], "target": ax.get("target"),
            "present_in_graph": bool(removed),
            "cq_changed": sorted(delta), "consumed": bool(delta),
        })
    return {
        "axioms_total": len(axioms),
        "consumed": sum(1 for r in results if r["consumed"]),
        "unconsumed": sum(1 for r in results if not r["consumed"]),
        "cq_count": len(cqs),
        "cq_baseline_rows_total": sum(base.values()),
        "graphs_loaded": loaded, "graphs_missing": missing,
        "detail": results,
    }


# ── V2 · V3 공통 원천 ─────────────────────────────────────────────────────────
def load_concepts():
    cf = pd.read_parquet(ROOT / "mappings" / "claim_features.parquet",
                         columns=["publication_id", "side", "is_independent", "feature_concept"])
    cf["feature_concept"] = cf.feature_concept.apply(
        lambda v: [] if v is None else [str(x) for x in v])
    doc = (cf.explode("feature_concept").dropna(subset=["feature_concept"])
             .groupby("publication_id").feature_concept.apply(set).to_dict())
    ind = cf[cf.is_independent & (cf.side == "rej")]
    qry = (ind.explode("feature_concept").dropna(subset=["feature_concept"])
              .groupby("publication_id").feature_concept.apply(set).to_dict())
    ed = pd.read_parquet(ROOT / "data" / "patents" / "prior_art_edges.parquet")
    ex = ed[ed.source_type == "examiner"].copy()
    ex["tgt"] = ex.target_patent_id.str.replace("^patent:", "", regex=True)
    ex["cid"] = ex.cited_id.str.replace("^patent:", "", regex=True)
    gt = ex.groupby("tgt").cid.apply(set).to_dict()
    return doc, qry, gt


def v2_reach(doc, qry, gt) -> dict:
    inv = {}
    for d, cs in doc.items():
        for c in cs:
            inv.setdefault(c, set()).add(d)

    Q = [q for q, tg in gt.items() if q in qry and qry[q] and (tg & doc.keys())]
    reach_sizes, hits, tgt_sizes = [], [], []
    for q in Q:
        E = qry[q]
        R = set()
        for c in E:
            R |= inv.get(c, set())
        R.discard(q)
        T = gt[q] & doc.keys()
        reach_sizes.append(len(R)); tgt_sizes.append(len(T)); hits.append(bool(T & R))

    def spr(S):
        return sum(1 for h, r in zip(hits, reach_sizes) if h and r <= S) / len(Q)

    return {
        "queries": len(Q),
        "queries_dropped_no_query_concept": sum(
            1 for q, tg in gt.items() if (tg & doc.keys()) and not qry.get(q)),
        "corpus_docs_grounded": len(doc),
        "target_node": "인용문헌 노드 (퇴화형) — ont:Disclosure 는 클래스·인스턴스 0건이라 오늘 잴 수 없다",
        "masking": "구성으로 충족 — Reach 계산이 정답 간선을 읽지 않는다",
        "target_size_median": st.median(tgt_sizes),
        "reach_size_median": st.median(reach_sizes),
        "reach_size_mean": round(sum(reach_sizes) / len(reach_sizes), 1),
        "reach_size_max": max(reach_sizes),
        "reach_zero_queries": sum(1 for r in reach_sizes if r == 0),
        "hit_rate_any_S": sum(hits) / len(Q),
        "SemanticPathRecall@100": spr(100),
        "SemanticPathRecall@1000": spr(1000),
        "SemanticPathRecall@inf": spr(float("inf")),
    }


def v3_coverage(doc, qry, gt) -> dict:
    rows = []
    for q, tg in gt.items():
        E = qry.get(q) or set()
        cited = [d for d in tg if d in doc]
        if not E or not cited:
            continue
        covs = sorted(((len(E & doc[d]) / len(E)), d) for d in cited)
        best1 = covs[-1][0]
        best2 = best1
        if len(cited) > 1:
            for i in range(len(cited)):
                for j in range(i + 1, len(cited)):
                    u = doc[cited[i]] | doc[cited[j]]
                    best2 = max(best2, len(E & u) / len(E))
        rows.append({"q": q, "nE": len(E), "n_cited": len(cited),
                     "best_single": best1, "best_pair": best2, "delta": best2 - best1})
    df = pd.DataFrame(rows)
    sat = df[(df.best_single == 0) | (df.best_single == 1)]
    multi = df[df.n_cited >= 2]
    return {
        "queries": len(df),
        "essential_concepts_per_query": {
            "median": float(df.nE.median()), "mean": round(float(df.nE.mean()), 2),
            "p10": float(df.nE.quantile(.10)), "p90": float(df.nE.quantile(.90)),
        },
        "best_single_coverage": {
            "median": float(df.best_single.median()), "mean": round(float(df.best_single.mean()), 4),
            "eq0": int((df.best_single == 0).sum()), "eq1": int((df.best_single == 1).sum()),
            "saturated_frac": round(len(sat) / len(df), 4),
        },
        "pair_queries": len(multi),
        "delta_coverage": {
            "median": float(multi.delta.median()) if len(multi) else None,
            "mean": round(float(multi.delta.mean()), 4) if len(multi) else None,
            "gt0_frac": round(float((multi.delta > 0).mean()), 4) if len(multi) else None,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--skip-v1", action="store_true")
    a = ap.parse_args()

    rep = {"generated": str(date.today()), "plan": "PLAN-005 단계 1 (V1–V3 기준선)",
           "read_only": True}
    if not a.skip_v1:
        rep["V1_axiom_ablation"] = v1_ablation()
    doc, qry, gt = load_concepts()
    rep["V2_semantic_path_recall"] = v2_reach(doc, qry, gt)
    rep["V3_coverage"] = v3_coverage(doc, qry, gt)
    rep["V4_query_independence"] = {
        "status": "미산출",
        "reason": "요약·의역 질의 생성이 선행되어야 한다(PLAN-005 §5 V4-1). "
                  "실제 연구노트 소표본(V4-2)은 2인 독립 판정이 필요하므로 사람 자원에 걸린다.",
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2)[:4000])
    print(f"\n→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
