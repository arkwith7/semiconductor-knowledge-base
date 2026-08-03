#!/usr/bin/env python3
"""청구항 feature + 거절-판단 패턴 A-Box 빌드 — 중심축 데이터셋의 실체화.

입력:
  data/interim/claim_features.jsonl            (decompose_corpus.py 산출: 청구항→feature)
  data/patents/prior_art_edges.parquet         (evidence_v2: 거절-판단쌍 · cited_doc_id→cited_id)
출력:
  ontology/sdkb-abox-claim-features.ttl

각 feature 텍스트를 SDKB 개념에 정규화(featureConcept)한다 — build_abox_patents 와 **동일한**
브리지를 써서 어휘를 발명하지 않는다. 심사관 판단(evidence_v2)은 PriorArtJudgment 로 실체화한다.
결정적: 같은 입력이면 같은 그래프.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
FEATURES = ROOT / "data" / "interim" / "claim_features.jsonl"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-claim-features.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_claim_features_report.json"

ONT = S.ONT
DCTERMS = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"

# feature 정규화에 계상할 개념 축(build_abox_patents PATENT_ROUTING 과 정합).
CONCEPT_TYPES = {"Process", "SubProcess", "Device", "Material", "Skill", "FailureMode", "EquipmentClass"}
# §29 항 → 기존 RejectionType 개체
GROUND = {"§29①": "Rejection_Novelty", "§29②": "Rejection_Inventiveness"}


def _u(curie_or_path: str) -> URIRef:
    return URIRef(S.DATA + curie_or_path.replace(":", "/"))


def _patent_iri(field: str, cited_map: dict[str, str]) -> URIRef | None:
    """분해 patent 필드 → 그래프 특허 IRI.

    rej:{appno} → data:patent/kr_{appno} · cited:{doc_id} → cited_id 맵 ·
    g2:{slug}·g1:{slug} → data:patent/{slug} (둘 다 patent/kr_{appno} 슬러그)
    """
    kind, _, rest = field.partition(":")
    if kind == "rej":
        return _u(f"patent/kr_{rest}")
    if kind in ("g2", "g1"):
        return _u(f"patent/{rest}")
    if kind == "cited":
        cid = cited_map.get(rest)          # 'patent:kr_KR..A'
        return _u(cid.replace("patent:", "patent/")) if cid else None
    return None


def _slug(field: str) -> str:
    """Claim/Feature IRI 용 안정 슬러그."""
    return re.sub(r"[^A-Za-z0-9]+", "_", field).strip("_")


def main() -> int:
    if not FEATURES.exists():
        print(f"ERROR: {FEATURES} 없음 — decompose_corpus.py 먼저", file=sys.stderr)
        return 1
    try:
        br = S.make_bridge(ROOT, morph=True)
    except SystemExit:
        br = S.make_bridge(ROOT)

    edges = pd.read_parquet(EDGES)
    # cited_id 는 source_type 별로 형식이 다르다 — 'all'/'examiner' 는 정규형('patent:kr_..A'),
    # evidence_v2 는 비정규형('KR-P-..'). 인용 노드(A-1)는 정규형 IRI 를 쓰므로 정규형만으로 맵을 만든다.
    canon = edges[edges["cited_id"].astype(str).str.startswith("patent:")]
    cited_map = dict(zip(canon["cited_doc_id"], canon["cited_id"]))

    g = Graph()
    for p, ns in (("ont", ONT), ("data", S.DATA), ("owl", str(OWL)), ("rdfs", str(RDFS)),
                  ("skos", str(SKOS)), ("dcterms", DCTERMS)):
        g.bind(p, ns)
    R = lambda n: URIRef(ONT + n)  # noqa: E731

    stat = Counter()
    concept_hits = Counter()
    rows = [json.loads(line) for line in FEATURES.open()]
    seen_claim: set[str] = set()
    # 실재하는 청구항 IRI 집합 — dependsOnClaim 이 매달린 부모(존재하지 않는 참조 번호)를
    # 만들지 않도록. 일부 거절특허는 청구항 재번호/OCR 로 존재하지 않는 부모항을 참조한다.
    present_claims = {f"claim/{_slug(r['patent'])}_c{r['claim_no']}" for r in rows}

    for r in rows:
        pat = _patent_iri(r["patent"], cited_map)
        if pat is None:
            stat["patent_unresolved"] += 1
            continue
        pslug = _slug(r["patent"])
        cno = r["claim_no"]
        claim = _u(f"claim/{pslug}_c{cno}")
        if str(claim) not in seen_claim:
            dep = r.get("depends_on") or []
            g.add((claim, RDF.type, R("Claim")))
            g.add((claim, R("claimNumber"), Literal(int(cno), datatype=XSD.integer)))
            g.add((claim, R("isIndependent"), Literal(not dep, datatype=XSD.boolean)))
            g.add((pat, R("hasClaim"), claim))
            # 종속항 → 부모 청구항(같은 특허, claims_full 의 depends_on). 완전 한정요소집합의 상속 축.
            # 실재하는 부모에만 연결 — 존재하지 않는 참조 번호는 매달린 IRI 를 낳으므로 버리고 계상.
            for parent_no in dep:
                pkey = f"claim/{pslug}_c{parent_no}"
                if pkey in present_claims:
                    g.add((claim, R("dependsOnClaim"), _u(pkey)))
                    stat["depends_on_claim"] += 1
                else:
                    stat["depends_on_claim_dangling"] += 1
            seen_claim.add(str(claim))
            stat["claims"] += 1
            stat["claims_dependent" if dep else "claims_independent"] += 1

        feat_iris: list[tuple[URIRef, dict]] = []
        for f in r["features"]:
            fi = _u(f"feature/{pslug}_c{cno}_f{f['seq']}")
            g.add((fi, RDF.type, R("ClaimFeature")))
            g.add((fi, R("featureSeq"), Literal(int(f["seq"]), datatype=XSD.integer)))
            g.add((fi, R("featureText"), Literal(f["text"])))
            g.add((fi, R("decompositionMethod"), Literal(r["method"])))
            g.add((fi, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
            g.add((claim, R("hasFeature"), fi))
            stat["features"] += 1
            # feature → 개념 정규화
            for term, hits in br.extract_from_text(f["text"]).items():
                for nid, typ in hits:
                    if typ in CONCEPT_TYPES:
                        g.add((fi, R("featureConcept"), _u(nid)))
                        concept_hits[typ] += 1
            feat_iris.append((fi, f))
        # dependsOnFeature — '상기 X' 참조를 같은 청구항 내 앞선 feature 에 best-effort 연결
        for idx, (fi, f) in enumerate(feat_iris):
            for ref in f.get("refs", []):
                for pj, pf in feat_iris[:idx]:
                    if ref and ref in pf["text"]:
                        g.add((fi, R("dependsOnFeature"), pj))
                        stat["depends"] += 1
                        break

    # 거절-판단 패턴 → PriorArtJudgment. 두 원천을 union 한다:
    #  evidence_v2 (656행, GT — 노이즈 포함) + OCR 재추출 (거절결정 표, authoritative).
    # 키 (target특허, cited_doc, ground) 로 병합하고 청구항 집합을 합친다.
    judg: dict[tuple, set[int]] = {}
    ev = edges[edges["source_type"] == "evidence_v2"].drop_duplicates(["target_patent_id", "cited_id", "legal_basis"])
    for _, e in ev.iterrows():
        ground = GROUND.get(str(e["legal_basis"]))
        if ground is None:
            stat["judgment_no_ground"] += 1
            continue
        key = (str(e["target_patent_id"]), str(e["cited_doc_id"]), ground)  # ground = RejectionType 개체명
        cl = {int(x) for x in str(e["target_claims"] or "").split("|") if x.strip().isdigit()}
        judg.setdefault(key, set()).update(cl)
    # OCR 재추출 (data/interim/reextracted_judgments.jsonl). ground("§29②")를 evidence_v2 와
    # 같은 RejectionType 개체명으로 매핑해야 키가 병합되고 onGround IRI 가 유효해진다.
    rxf = ROOT / "data" / "interim" / "reextracted_judgments.jsonl"
    if rxf.exists():
        for line in rxf.open():
            r = json.loads(line)
            gr = GROUND.get(r["ground"])
            if gr is None:
                continue
            key = (f"patent:kr_{r['target_patent']}", str(r["cited_doc"]), gr)
            judg.setdefault(key, set()).update(int(x) for x in r["target_claims"])
            stat["reextract_rows"] += 1

    for (tgt_id, cited_doc, ground), claims in judg.items():
        canon = cited_map.get(cited_doc)
        if not canon:
            stat["judgment_cited_unresolved"] += 1
            continue
        tgt = _u(tgt_id.replace("patent:", "patent/"))
        cited = _u(canon.replace("patent:", "patent/"))
        j = _u(f"judgment/{_slug(tgt_id + '__' + cited_doc + '__' + ground)}")
        g.add((j, RDF.type, R("PriorArtJudgment")))
        g.add((j, R("onGround"), R(ground)))
        g.add((j, R("overPriorArt"), cited))
        g.add((tgt, R("hasJudgment"), j))
        stat["judgments"] += 1
        appno = tgt_id.replace("patent:kr_", "")
        for cn in sorted(claims):
            cl = _u(f"claim/{_slug('rej:'+appno)}_c{cn}")
            if str(cl) in seen_claim:
                g.add((j, R("aboutClaim"), cl))
                stat["about_claim"] += 1

    # CR-004R: RejectionReason 실체화 — reextract_claim_judgments.py --reasons-only 산출을 읽는다.
    # 입도 = 출원 × groundClause(조-항-호 전체) × 회차. 인용문헌 불필요(§29 한정 아님) — 그 조항이
    # 그 회차에 제기됐다는 사실만 기록한다. 기존 judg 루프(PriorArtJudgment·§29 한정)와 독립.
    reasons_f = ROOT / "data" / "interim" / "rejection_reasons.jsonl"
    if reasons_f.exists():
        for line in reasons_f.open():
            r = json.loads(line)
            if "_skipped_clauses" in r:
                continue
            app = r["application"]
            patent = _u(f"patent/kr_{app}")
            rr = _u(f"rejection/kr_{app}__{r['clause']}__r{r['notice_round']}")
            g.add((rr, RDF.type, R("RejectionReason")))
            g.add((rr, R("reasonGround"), R(r["reason_ground"])))
            g.add((rr, R("groundClause"), Literal(r["clause"], datatype=XSD.string)))
            g.add((rr, R("noticeRound"), Literal(int(r["notice_round"]), datatype=XSD.integer)))
            g.add((rr, R("noticeType"), Literal(r["notice_type"], datatype=XSD.string)))
            if r.get("notice_date"):
                g.add((rr, R("noticeDate"), Literal(r["notice_date"], datatype=XSD.date)))
            g.add((patent, R("rejectionEvidence"), rr))
            stat["rejection_reasons"] += 1

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")
    report = {
        "triples": len(g), "input_claims": len(rows),
        "counts": dict(stat), "feature_concept_by_type": dict(concept_hits.most_common()),
        "note": "feature 정규화 = build_abox_patents 와 동일 브리지. 판단 = evidence_v2 실체화. "
                "RejectionReason = rejection_reasons.jsonl 실체화(CR-004R).",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"✓ ({len(g):,} 트리플) → {OUT_TTL.name}")
    print(f"  claims={stat['claims']} features={stat['features']} depends={stat['depends']}")
    print(f"  judgments={stat['judgments']} about_claim={stat['about_claim']}")
    print(f"  rejection_reasons={stat['rejection_reasons']}")
    print(f"  featureConcept by type: {dict(concept_hits.most_common(6))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
