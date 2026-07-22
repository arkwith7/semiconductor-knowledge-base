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


def _load_enriched() -> pd.DataFrame:
    frames = []
    kj = ENR / "kipris.jsonl"
    if kj.exists():
        frames.append(pd.DataFrame([json.loads(l) for l in kj.open()]))
    for pq in ("bigquery.parquet", "bigquery_us.parquet"):
        if (ENR / pq).exists():
            frames.append(pd.read_parquet(ENR / pq))
    df = pd.concat(frames, ignore_index=True)
    return df[df["resolved"] == True].drop_duplicates("cited_doc_id")  # noqa: E712


def main() -> int:
    if not ENR.exists():
        print(f"ERROR: {ENR} 없음 — 수집 먼저", file=sys.stderr)
        return 1
    try:
        br = S.make_bridge(ROOT, morph=True)
    except SystemExit:
        br = S.make_bridge(ROOT)

    edges = pd.read_parquet(EDGES)
    canon = edges[edges["cited_id"].astype(str).str.startswith("patent:")]
    cited_map = dict(zip(canon["cited_doc_id"], canon["cited_id"]))

    df = _load_enriched()
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
        for term, hits in br.extract_from_text(text).items():
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
    print(f"✓ ({len(g):,} 트리플) → {OUT_TTL.name}")
    print(f"  nodes={stat['nodes']} filing={stat['filing']} claims={stat['claims']} "
          f"개념링크={stat['with_concept']} 미해결IRI={stat['unresolved_iri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
