#!/usr/bin/env python3
"""인용 선행기술 문헌 A-Box 빌드 — 결함 A 해소(매달린 IRI → 실체 노드).

심사관 인용 선행기술은 hasPriorArtExaminer/overPriorArt 의 대상이지만 그래프에 타입·서지·
개념이 없는 매달린 IRI 였다. 이 생성기가 수집분(서지·초록·청구항)을 그 IRI 에 실체화한다 —
새 IRI 를 만들지 않고 기존 엣지 대상에 본체를 붙인다.

입력  data/patents/cited_enriched/{kipris.jsonl, bigquery.parquet, bigquery_us.parquet}
      data/patents/prior_art_edges.parquet   (cited_doc_id → 정규 cited_id)
출력  ontology/sdkb-abox-prior-art.ttl

개념 링크는 build_abox_patents 와 동일 브리지(어휘 발명 없음). 청구항 단위 feature 는
build_abox_claim_features 가 별도로 실체화한다 — 여기서는 노드 본체(타입·서지·초록·claimText)만.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)

#: CR-020 — 특허 본문을 읽는 경로는 `patent-text` 어휘로 해소한다.
#: 기본값(`expert-tag`)에 기대지 않고 명시한다 — 암묵값이 D-49 의 원인이었다.
PROFILE = "patent-text"
ENR = ROOT / "data" / "patents" / "cited_enriched"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-prior-art.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_prior_art_report.json"

ONT = S.ONT
DCTERMS = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"
CONCEPT_ROUTING = {"Process": "realizesProcess", "SubProcess": "realizesProcess",
                   "Device": "concernsDevice", "Material": "involvesMaterial",
                   "EquipmentClass": "realizesEquipmentClass", "Skill": "concernsSkill",
                   "FailureMode": "exhibitsFailureMode"}
SRC_LABEL = {"kipris": "KIPRIS Plus API", "bigquery": "BigQuery Google Patents"}


def _u(path: str) -> URIRef:
    return URIRef(S.DATA + path.replace(":", "/"))


def _load_enriched(extra: tuple[str, ...] = ()) -> pd.DataFrame:
    frames = []
    kj = ENR / "kipris.jsonl"
    if kj.exists():
        frames.append(pd.DataFrame([json.loads(l) for l in kj.open()]))
    for pq in ("bigquery.parquet", "bigquery_us.parquet") + extra:
        if (ENR / pq).exists():
            frames.append(pd.read_parquet(ENR / pq))
    df = pd.concat(frames, ignore_index=True)
    return df[df["resolved"] == True].drop_duplicates("cited_doc_id")  # noqa: E712


def _b_layer_map(pop_path: Path) -> dict[str, str]:
    """CR-008 — B층 (cited_doc_id → cited_id). 엣지표 조회를 대신한다.

    B층 문헌은 `prior_art_edges.parquet` 에 **없다**(질의–인용 대응 미이관 · 비목표 ⓒ).
    IRI 규칙의 근거와 검증은 `scripts/build_b_layer_cited_ids.py` · `tests/` 에 있다.
    """
    pop = pd.read_parquet(pop_path)
    pop = pop[~pop["is_npl"]]
    return dict(zip(pop["cited_doc_id"], pop["cited_id"]))


# CR-008 성공기준 ② 의 참조선 — A층을 **관할별 분모**로 다시 잰 실측(2026-08-04).
# CR 본문의 "초록 ≥ 0.57" 은 ja **언어** 부분집합 117 건의 값이라 분모가 다르다. 둘 다 싣고
# 하류가 판단하게 한다 — 상류가 동결 기준을 고치면 사후 조정이 된다(설계 D4).
A_LAYER_REFERENCE = {
    "KR": {"n": 1720, "abstract": 0.999, "claim": 1.000},
    "JP": {"n": 721, "abstract": 0.921, "claim": 0.000},
    "US": {"n": 471, "abstract": 0.998, "claim": 0.996},
    "WO": {"n": 81, "abstract": 0.975, "claim": 0.000},
    "CN": {"n": 20, "abstract": 1.000, "claim": 0.000},
    "EP": {"n": 12, "abstract": 1.000, "claim": 0.000},
}
CR008_THRESHOLDS = {"KR_claim": 0.99, "US_claim": 0.99, "foreign_abstract": 0.57}
B_REPORT = ROOT / "data" / "reports" / "abox_prior_art_b_layer_report.json"


def b_report(pop_path: Path, enriched: pd.DataFrame, g: Graph) -> None:
    """CR-008 출력 (2) — 관할별 확보 리포트.

    **합계 행을 만들지 않는다.** 합계로 보면 얇은 문서가 채운 0.95 를 성공으로 읽게 된다
    (CR 성공기준 ②). NPL 은 어느 관할 행에도 넣지 않고 별도 행으로만 보고한다.
    """
    pop = pd.read_parquet(pop_path)
    pat, npl = pop[~pop["is_npl"]], pop[pop["is_npl"]]
    enr = enriched.set_index("cited_doc_id")

    def _has_text(s: pd.Series) -> float:
        """**빈 문자열은 없는 것이다.** BigQuery 경로는 청구항을 못 받으면 NaN 이 아니라
        `""` 를 준다 — notna() 로 세면 JP 청구항이 0.000 이 아니라 1.000 으로 보고된다."""
        if not len(s):
            return 0.0
        return float(s.fillna("").astype(str).str.strip().ne("").mean())

    by_j: dict[str, dict] = {}
    for cc, sub in pat.groupby("cited_country"):
        got = enr.reindex(sub["cited_doc_id"]).dropna(how="all")
        n = len(sub)
        node_ok = sum(1 for cid in sub["cited_id"]
                      if (_u(str(cid).replace("patent:", "patent/")), RDF.type,
                          URIRef(ONT + "CitedPatent")) in g)
        by_j[cc] = {
            "n": n,
            "resolved_nodes": node_ok,
            "reachability": round(node_ok / n, 4) if n else 0.0,
            # 분모는 **관할별 특허 문헌 수**(CR-008 성공기준 ②) — 해소된 것만이 아니다.
            "abstract": round(_has_text(got["abstract"]) * len(got) / n, 4) if n else 0.0,
            "claim": round(_has_text(got["claims"]) * len(got) / n, 4) if n else 0.0,
        }

    unresolved = [
        {"cited_raw": r["cited_raw"], "country": r["cited_country"],
         "reason": "수집 미해소" if r["cited_doc_id"] not in enr.index else "노드 미생성"}
        for _, r in pat.iterrows()
        if (_u(str(r["cited_id"]).replace("patent:", "patent/")), RDF.type,
            URIRef(ONT + "CitedPatent")) not in g
    ]
    odd = pat[pat["kind_code"].isin({"X2", "Y1", "Y2"})]

    B_REPORT.parent.mkdir(parents=True, exist_ok=True)
    B_REPORT.write_text(json.dumps({
        "ids_file": str(pop_path),
        "denominator_patent_docs": int(len(pat)),
        "npl_excluded": int(len(npl)),
        "total_ids": int(len(pop)),
        "by_jurisdiction": by_j,
        "a_layer_reference_by_jurisdiction": A_LAYER_REFERENCE,
        "cr008_thresholds": CR008_THRESHOLDS,
        "kind_codes_without_a_layer_precedent": [
            {"cited_raw": r["cited_raw"], "cited_id": r["cited_id"],
             "node_built": (_u(str(r["cited_id"]).replace("patent:", "patent/")), RDF.type,
                            URIRef(ONT + "CitedPatent")) in g}
            for _, r in odd.iterrows()],
        "npl_rows": npl["cited_raw"].tolist(),
        "unresolved": unresolved,
        "note": "합계 행 없음 — 관할별로만 본다(CR-008 성공기준 ②). "
                "분모 503 은 2026-08-03 동결이며 결과를 보고 고르지 않는다.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ B층 리포트 → {B_REPORT.name}")
    for cc, v in sorted(by_j.items(), key=lambda x: -x[1]["n"]):
        print(f"  {cc}  n={v['n']:>4}  도달성={v['reachability']:.4f}  "
              f"초록={v['abstract']:.4f}  청구항={v['claim']:.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="인용 선행기술 A-Box 빌드")
    # CR-008 — 주면 B층 모집단의 IRI 를 **기존 맵에 병합**한다(덮어쓰지 않는다 = A층 불변).
    ap.add_argument("--population", type=Path, default=None)
    ap.add_argument("--extra-enriched", nargs="*", default=[],
                    help="추가로 읽을 cited_enriched 파일명 (예: bigquery_b_layer.parquet)")
    args = ap.parse_args()

    if not ENR.exists():
        print(f"ERROR: {ENR} 없음 — 수집 먼저", file=sys.stderr)
        return 1
    try:
        br = S.make_bridge(ROOT, morph=True, profile=PROFILE)
    except SystemExit:
        br = S.make_bridge(ROOT, profile=PROFILE)

    edges = pd.read_parquet(EDGES)
    canon = edges[edges["cited_id"].astype(str).str.startswith("patent:")]
    cited_map = dict(zip(canon["cited_doc_id"], canon["cited_id"]))
    if args.population is not None:
        # 충돌 시 기존 값 우선 — A층 자산 불변(성공기준 ③)이 우연이 아니라 규칙이 된다.
        for doc, cid in _b_layer_map(args.population).items():
            cited_map.setdefault(doc, cid)

    df = _load_enriched(tuple(args.extra_enriched))
    g = Graph()
    for p, ns in (("ont", ONT), ("data", S.DATA), ("owl", str(OWL)), ("rdfs", str(RDFS)),
                  ("skos", str(SKOS)), ("dcterms", DCTERMS), ("prov", str(PROV))):
        g.bind(p, ns)
    R = lambda n: URIRef(ONT + n)  # noqa: E731

    stat = Counter()
    for _, r in df.iterrows():
        cid = cited_map.get(r["cited_doc_id"])
        if not cid:
            stat["unresolved_iri"] += 1
            continue
        node = _u(cid.replace("patent:", "patent/"))
        # CitedPatent ⊑ Patent (TBox). 명시적 ont:Patent 타입은 붙이지 않는다 — 붙이면
        # Shape_Patent(출원번호 필수)가 서지 불완전한 인용문헌을 위반 처리한다. 완화
        # Shape_CitedPatent 로 검증하고, Patent 의미는 subClassOf 추론이 준다.
        g.add((node, RDF.type, R("CitedPatent")))
        lang = "ko" if r["country"] == "KR" else "en"
        title = r.get("title")
        if isinstance(title, str) and title.strip():
            g.add((node, SKOS.prefLabel, Literal(title, lang=lang)))
        # 서지
        fd = r.get("filing_date")
        if isinstance(fd, str) and fd.strip():
            g.add((node, R("filingDate"), Literal(fd, datatype=XSD.date)))
            stat["filing"] += 1
        for scheme, col in (("IPCSymbol", "ipc"), ("CPCSymbol", "cpc")):
            codes = r.get(col)
            if isinstance(codes, str) and codes.strip():
                for code in codes.split("|"):
                    code = code.strip()
                    if not code:
                        continue
                    sym = _u(f"{'ipc' if scheme=='IPCSymbol' else 'cpc'}/{code.replace(' ','_').replace('/','-')}")
                    g.add((sym, RDF.type, R(scheme)))
                    g.add((sym, SKOS.notation, Literal(code, datatype=XSD.string)))
                    g.add((node, R("hasIPC" if scheme == "IPCSymbol" else "hasCPC"), sym))
        # 본문
        abstract = r.get("abstract")
        if isinstance(abstract, str) and abstract.strip():
            g.add((node, R("abstractText"), Literal(abstract)))
        claims = r.get("claims")
        if isinstance(claims, str) and claims.strip():
            g.add((node, R("claimText"), Literal(claims)))
            stat["claims"] += 1
        # 개념 링크(문서 단위) — feature 단위는 build_abox_claim_features 가 별도로 붙인다
        text = " ".join(str(r.get(c) or "") for c in ("title", "abstract"))
        linked = set()
        # CR-013 ⓒ — 단독 `hf` 는 원문 대소문자로만 갈린다. 원문을 넘긴다.
        for term, hits in S.resolve_hf_case(br.extract_from_text(text), text).items():
            for nid, typ in hits:
                prop = CONCEPT_ROUTING.get(typ)
                if prop and nid not in linked:
                    g.add((node, R(prop), _u(nid)))
                    linked.add(nid)
                    stat[f"concept_{typ}"] += 1
        if linked:
            stat["with_concept"] += 1
        # 출처
        src = SRC_LABEL.get(r.get("source"), str(r.get("source")))
        g.add((node, DCTERMS.source, Literal(src, datatype=XSD.string)))
        g.add((node, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
        stat["nodes"] += 1

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")
    report = {"triples": len(g), "input_resolved": len(df), "counts": dict(stat),
              "note": "인용문헌 노드 = 기존 cited IRI 에 타입·서지·초록·claimText·개념 링크 부여. "
                      "feature 는 build_abox_claim_features 가 별도 실체화."}
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.population is not None:
        b_report(args.population, df, g)
    print(f"✓ ({len(g):,} 트리플) → {OUT_TTL.name}")
    print(f"  nodes={stat['nodes']} filing={stat['filing']} claims={stat['claims']} "
          f"개념링크={stat['with_concept']} 미해결IRI={stat['unresolved_iri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
