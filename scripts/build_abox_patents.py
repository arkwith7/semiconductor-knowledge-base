#!/usr/bin/env python3
"""Lift the SIRP rejected-patent corpus into an RDF A-Box linked to the SDKB
ontology — the patent-side analogue of `build_abox_experts_problems.py`.

Notebook 07 needs patents to be ontology instances so a SPARQL query can go
`patent-idea text → ontology concepts → other patents that share them` and
return prior-art patent numbers. Patent titles/abstracts are Korean prose, so
extraction is free-text (longest-key-first, Hangul substring / ASCII word
boundary) using the *same* Tier-1 lexicon + Tier-2 alias bridge as the
experts/problems lift — single source via `sdkb_nb`.

Inputs:
  data/patents/rejected_patents_meta.parquet   (`make ingest-sirp`)
Outputs:
  ontology/sdkb-abox-patents.ttl
  data/reports/abox_patents_linking_report.json   (honest coverage / orphans)
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
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
PRIOR_ART = ROOT / "data" / "patents" / "prior_art_edges.parquet"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-patents.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_patents_linking_report.json"

# KIPO 거절 근거(특허법 제29조) 항 번호 → TBox 의 RejectionType 통제어휘.
# rejected_patents_meta 의 rejection_legal_bases 는 "§2×3|§1×1" 형태다 (항×횟수).
# 제29조 제3항 등 나머지 항은 TBox 통제어휘에 대응 개념이 없어 싣지 않고 리포트에 남긴다.
REJECTION_PARAGRAPH_TO_TYPE = {
    "1": "Rejection_Novelty",         # 제29조 제1항 — 신규성
    "2": "Rejection_Inventiveness",   # 제29조 제2항 — 진보성
}

ONT = S.ONT
DCTERMS = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

# 이 A-Box 가 나온 출처. shapes_patent.ttl 이 특허마다 요구한다.
INGEST_ACTIVITY = "activity/sirp_ingest"
KIPRIS_SOURCE = "KIPRIS Plus API (getBibliographyDetailInfoSearch)"
PATENT_LICENSE = "KIPRIS terms — academic use, no redistribution of full text"

# node type → patent A-Box predicate (local name under ont:)
#
# 모두 sdkb-patent.ttl TBox 가 정의한 술어다. 예전 생성기는 여기서 concernsProcess /
# concernsMaterial / primaryIpc 를 **ABox 안에서 새로 선언**해 썼는데, TBox 를 읽는
# 소비자에게는 존재하지 않는 술어였고 SHACL·추론기가 검증할 수 없었다 (CLAUDE.md §8-2).
PATENT_ROUTING = {
    "Skill": "concernsSkill",
    "Process": "realizesProcess",        # TBox: domain Patent, range Process
    "SubProcess": "realizesProcess",     # SubProcess ⊑ Process 이므로 range 만족
    "Material": "involvesMaterial",      # TBox: range Material
    "Equipment": "concernsEquipment",
    "EquipmentClass": "realizesEquipmentClass",   # TBox: range EquipmentClass
    "Vendor": "concernsEquipment",
    "Metrology": "concernsEquipment",
    "TechnologyNode": "concernsTechnologyNode",   # realizesProcess 로 보내면 range 위반
    "FailureMode": "exhibitsFailureMode",
    "RootCause": "relatedToTopic",
    "Mitigation": "relatedToTopic",
    "Device": "concernsDevice",   # A2 device/product layer (plan §7.4-3)
}

# Deterministic bridge from the curator-assigned `process_family` field
# (rejected_patents_meta.parquet) to an ontology Process node. This is a
# structured-field link — high precision, no NLP — added IN ADDITION to the
# free-text extraction. Only families that map cleanly to a unit-process
# node are listed; device/product/packaging families are intentionally
# absent (see SCOPE_OUT_FAMILIES) so orphans split honestly into
# "text-miss" (fixable) vs "out-of-ontology-scope" (needs a device layer).
PROCESS_FAMILY_MAP = {
    "etch": "process:etch",
    "deposition": "process:deposition",
    "metallization": "process:deposition",   # metal-layer deposition
    "interconnect": "process:deposition",     # damascene metal fill
    "gate_dielectric": "process:deposition",  # modern high-k = ALD/depo
    "oxidation_diffusion": "process:diffusion",
    "oxidation": "process:diffusion",
    "thermal": "process:diffusion",           # anneal / thermal step
    "photo": "process:lithography",
    "lithography": "process:lithography",      # was text_miss — clearly in-scope
    "implant": "process:implant",
}
# A2 device/product layer (plan §7.4-3): families that have no UNIT-PROCESS
# home but DO map cleanly to a Device-architecture node now that the 31
# device classes are in the KG. Deterministic, no NLP — routed via
# ont:concernsDevice. Representative-device choice is documented per family.
DEVICE_FAMILY_MAP = {
    "memory": "device:dram",            # DRAM = representative memory cell
    "memory_cell": "device:dram",
    "memory_dram": "device:dram",
    "backend_packaging": "device:bga",  # BGA = representative package
    "packaging": "device:bga",
    "mems": "device:mems",
    "image_sensor": "device:cmos_image_sensor",
    "3d_integration": "device:tsv",     # 3D integration = TSV stacking
}
# After the device layer, the only family with NO ontology home is the
# genuinely generic 'components' (13 patents) — kept scope-out, honestly.
SCOPE_OUT_FAMILIES = {
    "components",
}


def _value_chain_tokens(v) -> set[str]:
    return {t.strip() for t in str(v or "").split("|") if t.strip()}


def _u(curie_or_id: str) -> URIRef:
    """`patent:kr_..` / `skill:..` → data URI (mirrors convert_rdf.uri)."""
    return URIRef(S.DATA + curie_or_id.replace(":", "/"))


def _org_slug(name: str) -> str:
    """출원인 명칭 → 안정적인 IRI 슬러그.

    표기 변형(대소문자·구두점·법인격 접미어)을 흡수한다. 완벽한 기업 식별자 해소(entity
    resolution)는 아니다 — 남는 변형은 프로파일이 드러내고, 그 한계는 논문 §5.3 에 적는다.
    """
    s = name.lower()
    for suffix in (
        "co., ltd.", "co.,ltd.", "co. ltd", "corporation", "incorporated",
        "kabushiki kaisha", "inc.", "inc", "ltd.", "ltd", "llc", "gmbh", "corp.", "corp",
    ):
        s = s.replace(suffix, " ")
    s = re.sub(r"[^a-z0-9가-힣]+", "_", s).strip("_")
    return s or "unknown"


def _applicants(row) -> list[tuple[str, str, str]]:
    """(슬러그, 영문명, 한글명) 목록. 영문명이 있으면 그것을 표준 표기로 삼는다."""
    en = [a.strip() for a in str(row.get("applicant_en") or "").split("|") if a.strip()]
    ko = [a.strip() for a in str(row.get("applicant_ko") or "").split("|") if a.strip()]

    out, seen = [], set()
    for i, name in enumerate(en or ko):
        slug = _org_slug(name)
        if slug in seen:
            continue
        seen.add(slug)
        out.append((slug, name if en else "", ko[i] if i < len(ko) else ""))
    return out


def _ipc_codes(row) -> list[str]:
    """특허 1건의 IPC 코드. KIPRIS 서지의 ipc_codes('A|B') 우선, 없으면 primary_ipc."""
    raw = row.get("ipc_codes")
    if pd.notna(raw) and str(raw).strip():
        codes = [c.strip() for c in str(raw).split("|") if c.strip()]
    else:
        p = row.get("primary_ipc")
        codes = [str(p).strip()] if pd.notna(p) and str(p).strip() else []
    return list(dict.fromkeys(codes))   # 순서 보존 dedup


def _rejection_paragraphs(v) -> list[str]:
    """'§2×3|§1×1' → ['2', '1'].  항 번호만 뽑는다 (×N 은 인용 횟수라 무시)."""
    if not v or pd.isna(v) or not str(v).strip():
        return []
    return [m.group(1) for m in re.finditer(r"§(\d+)", str(v))]


def _emit_prior_art(g: Graph, ont_r, known: set[str]) -> dict:
    """심사관·광의 선행기술 인용을 그래프에 싣는다.

    prior_art_edges.parquet 의 source_type 은 겹친다: examiner ⊂ all.
    - ont:hasPriorArt         ← 'all'      (광의 정답. 출처는 심사관 또는 출원인)
    - ont:hasPriorArtExaminer ← 'examiner' ('all' 의 부분집합. 심사관 인용 = 검색 평가의 정답)
    evidence/evidence_v2 (673쌍) 는 거절결정서 본문에서 구절 단위로 추출한 것이라
    ont:rejectionEvidence(range RejectionReason) 모델링이 필요하다 — 이 적재의 범위 밖이다.

    인용문헌에는 rdf:type 을 붙이지 않는다. 우리는 그 문헌의 서지(출원번호·출원일)를
    갖고 있지 않고, 30건은 비특허문헌(논문·표준)이라 ont:Patent 가 아니다. TBox 의
    hasPriorArt 가 range 를 두지 않는 이유다.
    """
    if not PRIOR_ART.exists():
        return {"loaded": False, "reason": f"{PRIOR_ART.name} not found"}

    edges = pd.read_parquet(PRIOR_ART)
    stats: dict = {"loaded": True}
    for source_type, prop in (("all", "hasPriorArt"), ("examiner", "hasPriorArtExaminer")):
        sub = edges[edges["source_type"] == source_type].drop_duplicates(
            ["target_patent_id", "cited_id"]
        )
        n_edge = n_skip = 0
        for tgt, cited in zip(sub["target_patent_id"], sub["cited_id"]):
            if str(tgt) not in known:   # 우리 코퍼스 밖의 특허는 domain 위반이다
                n_skip += 1
                continue
            g.add((_u(str(tgt)), ont_r(prop), _u(str(cited))))
            n_edge += 1
        stats[prop] = {
            "edges": n_edge,
            "skipped_unknown_target": n_skip,
            "distinct_cited": int(sub["cited_id"].nunique()),
            "npl_cited": int(sub["is_npl"].sum()),
        }
    stats["excluded_evidence_pairs"] = int(
        edges[edges["source_type"].isin(["evidence", "evidence_v2"])]
        .drop_duplicates(["target_patent_id", "cited_id"]).shape[0]
    )
    return stats


def main() -> int:
    if not META.exists():
        print(f"ERROR: {META} not found — run "
              f"`make ingest-sirp PYTHON=.venv/bin/python` first.", file=sys.stderr)
        return 1

    meta = pd.read_parquet(META)
    # Korean morphological mode: Kiwi (user-dict for domain compounds) UNIONed
    # with the deterministic substring scan; falls back to substring-only if
    # kiwipiepy is absent so the pipeline still runs.
    try:
        br = S.make_bridge(ROOT, morph=True)
        mode = "morph(Kiwi)+substring, title+abstract+claim1"
    except SystemExit:
        br = S.make_bridge(ROOT)
        mode = "substring-only (kiwipiepy missing), title+abstract+claim1"
    print(f"  bridge mode: {mode}")

    g = Graph()
    g.bind("ont", ONT)
    g.bind("data", S.DATA)
    g.bind("owl", str(OWL))
    g.bind("rdfs", str(RDFS))
    g.bind("dcterms", DCTERMS)
    g.bind("prov", PROV)
    g.bind("skos", SKOS)

    ONT_R = lambda local: URIRef(ONT + local)  # noqa: E731

    # 어휘 선언은 여기서 하지 않는다 — 클래스·술어는 전부 TBox(ontology/sdkb-patent.ttl,
    # sdkb-core.ttl)가 정의한다. ABox 가 어휘를 인라인 선언하면 TBox 만 읽는 소비자에게
    # 그 술어는 존재하지 않게 되고, 추론기·SHACL 이 검증할 수 없다 (CLAUDE.md §1.2).

    # 이 A-Box 를 만든 적재 활동 (shapes_patent.ttl 의 prov:wasGeneratedBy 요구)
    activity = _u(INGEST_ACTIVITY)
    g.add((activity, RDF.type, PROV.Activity))
    g.add((activity, RDFS.label, Literal("SIRP rejected-patent ingest", lang="en")))

    type_dist = Counter()
    nodes_per: list[int] = []
    orphans: list[str] = []
    matched_terms = Counter()
    n_structured = 0          # patents that got >=1 structured Process link
    n_device = 0              # patents that got >=1 structured Device link (A2)
    n_text = 0                # patents that got >=1 free-text link
    n_org_links = 0           # patent -> Organization (assignedTo) 트리플 수
    orphan_scope_out: list[str] = []   # device/packaging/component — no node
    orphan_text_miss: list[str] = []   # in-domain yet still unlinked (fixable)
    fam_unmapped = Counter()  # in-domain families with no structured node
    n_rejected = 0             # rdf:type ont:RejectedPatent 를 받은 특허
    rejected_for = Counter()   # RejectionType 별 rejectedFor 트리플
    unmapped_paragraphs = Counter()  # TBox 통제어휘에 없는 제29조 항
    text_props = Counter()     # abstractText / firstClaimText

    for _, r in meta.iterrows():
        pid = str(r["patent_id"])
        pu = _u(pid)
        g.add((pu, RDF.type, ONT_R("Patent")))
        g.add((pu, RDFS.label, Literal(str(r.get("title") or pid))))

        # 문자열 속성 — 전부 TBox 가 정의한 DatatypeProperty
        for col, prop in (("application_number", "applicationNumber"),
                          ("patent_office", "patentOffice"),
                          ("publication_number", "publicationNumber"),
                          ("examination_status", "examinationStatus"),
                          ("process_family", "processFamily"),
                          ("value_chain", "valueChainStage")):
            v = r.get(col)
            if pd.notna(v) and str(v).strip():
                # 평문 리터럴로 둔다 (RDF 1.1 에서 곧 xsd:string). ^^xsd:string 을 명시하면
                # shapes 의 sh:in ( "KR" … ) 평문 리터럴과 term 이 달라져 위반이 난다.
                g.add((pu, ONT_R(prop), Literal(str(v))))

        # 날짜 — xsd:date. filingDate 는 KIPRIS 권위 원천에서 온 **진짜 출원일**이다
        # (raw JSONL 의 date 는 공개일이었다 — CLAUDE.md §8-1). 시계열 연구의 전제.
        for col, prop in (("filing_date", "filingDate"),
                          ("publication_date", "publicationDate")):
            v = r.get(col)
            if pd.notna(v) and str(v).strip():
                g.add((pu, ONT_R(prop), Literal(str(v), datatype=XSD.date)))

        # IPC — TBox 의 hasIPC 는 range 가 ont:IPCSymbol 인 ObjectProperty 다.
        # 리터럴(primaryIpc)로 흘리던 것을 심볼 노드로 승격한다 (skos:notation 은
        # shapes_patent.ttl 의 Shape_IPCSymbol 요구).
        for code in _ipc_codes(r):
            sym = _u(f"ipc/{code.replace(' ', '_').replace('/', '-')}")
            g.add((sym, RDF.type, ONT_R("IPCSymbol")))
            g.add((sym, SKOS.notation, Literal(code, datatype=XSD.string)))
            g.add((pu, ONT_R("hasIPC"), sym))

        # 출원인 — TBox 의 ont:assignedTo (domain Patent, range Organization).
        # 출원인 없는 특허 지식베이스는 기업별 포트폴리오·경쟁 분석을 지원할 수 없다.
        for slug, en, ko in _applicants(r):
            org = _u(f"organization/{slug}")
            g.add((org, RDF.type, ONT_R("Organization")))
            if en:
                g.add((org, SKOS.prefLabel, Literal(en, lang="en")))
            if ko:
                g.add((org, SKOS.altLabel, Literal(ko, lang="ko")))
            # Shape_CoreNode 는 모든 Organization 에 dcterms:license 와 interpretationType 을
            # 요구한다. 출원인 보강 때 이 둘을 빠뜨려 위반 702건이 났었다 (PLAN-013 D3).
            # 출원인 이름은 KIPRIS 서지의 값을 그대로 옮긴 것이므로 verbatim 이다.
            g.add((org, DCTERMS.source, Literal(KIPRIS_SOURCE, datatype=XSD.string)))
            g.add((org, DCTERMS.license, Literal(PATENT_LICENSE, datatype=XSD.string)))
            g.add((org, ONT_R("interpretationType"), Literal("verbatim")))
            g.add((pu, ONT_R("assignedTo"), org))
            n_org_links += 1

        # SIRP 는 거절특허 코퍼스다 — register_status 가 1,000건 전부 '거절'이다.
        # TBox 의 RejectedPatent ⊑ Patent 이므로 위의 rdf:type Patent 와 모순되지 않는다.
        if str(r.get("register_status") or "").strip() == "거절":
            g.add((pu, RDF.type, ONT_R("RejectedPatent")))
            n_rejected += 1

        # 거절 근거 — rejectedFor 의 range 는 ont:RejectionType (통제어휘 개체)다.
        for para in _rejection_paragraphs(r.get("rejection_legal_bases")):
            rtype = REJECTION_PARAGRAPH_TO_TYPE.get(para)
            if rtype is None:
                unmapped_paragraphs[para] += 1
                continue
            g.add((pu, ONT_R("rejectedFor"), ONT_R(rtype)))
            rejected_for[rtype] += 1

        # 초록·청구항 1 — TBox 의 abstractText / firstClaimText.
        # 이 텍스트는 KIPRIS 학술이용 조건 아래 있다 (아래 dcterms:license 가 명시한다).
        for col, prop in (("abstract", "abstractText"), ("claim1", "firstClaimText")):
            v = r.get(col)
            if pd.notna(v) and str(v).strip():
                g.add((pu, ONT_R(prop), Literal(str(v))))
                text_props[prop] += 1

        # 출처·라이선스·생성 활동 — shapes_patent.ttl 이 특허마다 요구한다
        g.add((pu, DCTERMS.source, Literal(KIPRIS_SOURCE, datatype=XSD.string)))
        g.add((pu, DCTERMS.license, Literal(PATENT_LICENSE, datatype=XSD.string)))
        g.add((pu, PROV.wasGeneratedBy, activity))

        # 1) deterministic structured-field bridge (high precision, no NLP)
        fam = str(r.get("process_family") or "").strip().lower()
        linked: set[str] = set()
        if fam in PROCESS_FAMILY_MAP:
            nid = PROCESS_FAMILY_MAP[fam]
            g.add((pu, ONT_R("realizesProcess"), _u(nid)))   # TBox 술어 (구 concernsProcess)
            linked.add(nid)
            type_dist["Process"] += 1
            n_structured += 1
        # A2: deterministic device-family bridge (plan §7.4-3)
        if fam in DEVICE_FAMILY_MAP:
            dnid = DEVICE_FAMILY_MAP[fam]
            g.add((pu, ONT_R("concernsDevice"), _u(dnid)))
            linked.add(dnid)
            type_dist["Device"] += 1
            n_device += 1

        # 2) free-text extraction (UNION with the structured link)
        text = (f"{r.get('title') or ''} {r.get('abstract') or ''} "
                f"{r.get('claim1') or ''}")
        had_text = False
        for term, hits in br.extract_from_text(text).items():
            for nid, typ in hits:
                prop = PATENT_ROUTING.get(typ)
                if not prop:
                    continue
                if nid not in linked:
                    g.add((pu, ONT_R(prop), _u(nid)))
                    type_dist[typ] += 1
                linked.add(nid)
                had_text = True
            if hits:
                matched_terms[term] += 1
        if had_text:
            n_text += 1

        nodes_per.append(len(linked))
        if not linked:
            orphans.append(pid)
            vc = _value_chain_tokens(r.get("value_chain"))
            if fam in SCOPE_OUT_FAMILIES or {"device", "component"} & vc:
                orphan_scope_out.append(pid)   # needs a device layer (A2)
            else:
                orphan_text_miss.append(pid)   # genuinely fixable residue
                if fam and fam not in PROCESS_FAMILY_MAP:
                    fam_unmapped[fam] += 1

    # 선행기술 인용 — 특허 루프 밖에서, 우리가 아는 특허만 대상으로
    prior_art = _emit_prior_art(g, ONT_R, set(meta["patent_id"].astype(str)))

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    n = len(meta)
    report = {
        "input": str(META.relative_to(ROOT)),
        "patents": n,
        "triples": len(g),
        "rejection": {
            "typed_RejectedPatent": n_rejected,
            "rejectedFor": dict(rejected_for),
            "unmapped_paragraphs": dict(unmapped_paragraphs),
        },
        "text": dict(text_props),
        "prior_art": prior_art,
        "patents_with_ontology_link": n - len(orphans),
        "link_provenance": {
            "structured_process_family": n_structured,
            "structured_device_family": n_device,   # A2 (plan §7.4-3)
            "free_text": n_text,
            "process_family_map": PROCESS_FAMILY_MAP,
            "device_family_map": DEVICE_FAMILY_MAP,
        },
        "orphans_count": len(orphans),
        "orphans_split": {
            "scope_out": len(orphan_scope_out),
            "text_miss": len(orphan_text_miss),
            "note": "scope_out = device/packaging/component family or "
                    "value_chain device|component — no ontology node exists "
                    "(needs the A2 device layer; NOT a lift bug). text_miss = "
                    "in-domain yet unlinked — the genuinely fixable residue.",
            "text_miss_families": dict(fam_unmapped.most_common()),
            "scope_out_sample": orphan_scope_out[:10],
            "text_miss_sample": orphan_text_miss[:10],
        },
        "orphans_sample": orphans[:15],
        "nodes_per_patent": {
            "mean": round(sum(nodes_per) / n, 3) if n else 0,
            "median": int(sorted(nodes_per)[n // 2]) if n else 0,
            "max": max(nodes_per) if nodes_per else 0,
            "zero": sum(1 for x in nodes_per if x == 0),
        },
        "concern_edges_by_node_type": dict(type_dist.most_common()),
        "top_matched_terms": [
            {"term": t, "patents": c} for t, c in matched_terms.most_common(40)
        ],
        "bridge_mode": mode + " + structured(process_family)",
        "note": "Lift = deterministic process_family->Process bridge UNION "
                "Korean free-text (sdkb_nb 2-tier, title+abstract+claim1). "
                "Orphans split into scope_out (no ontology node — device "
                "layer gap) vs text_miss (fixable) so the residual loss is "
                "diagnosed, not just counted.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    npp = report["nodes_per_patent"]
    print(f"✓ Patent A-Box ({len(g):,} triples) → {OUT_TTL.relative_to(ROOT)}")
    print(f"  patents={n}  linked={n - len(orphans)} "
          f"(structured={n_structured}, text={n_text})  "
          f"nodes/patent mean={npp['mean']} median={npp['median']}")
    print(f"  orphans={len(orphans)}  -> scope_out={len(orphan_scope_out)} "
          f"(device layer gap) / text_miss={len(orphan_text_miss)} (fixable)")
    print(f"  edges by type: {dict(type_dist.most_common(6))}")
    print(f"  RejectedPatent={n_rejected}  rejectedFor={sum(rejected_for.values())} "
          f"{dict(rejected_for)}  text={dict(text_props)}")
    if prior_art.get("loaded"):
        pa = prior_art["hasPriorArt"]
        px = prior_art["hasPriorArtExaminer"]
        print(f"  priorArt: hasPriorArt={pa['edges']} (cited {pa['distinct_cited']}) "
              f"examiner={px['edges']} (cited {px['distinct_cited']}, npl {px['npl_cited']})"
              f"  excluded_evidence_pairs={prior_art['excluded_evidence_pairs']}")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
