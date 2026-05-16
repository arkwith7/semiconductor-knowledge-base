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
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-patents.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_patents_linking_report.json"

ONT = S.ONT

# node type → patent A-Box predicate (local name under ont:)
PATENT_ROUTING = {
    "Skill": "concernsSkill",
    "Process": "concernsProcess",
    "SubProcess": "concernsProcess",
    "Material": "concernsMaterial",
    "Equipment": "concernsEquipment",
    "EquipmentClass": "concernsEquipment",
    "Vendor": "concernsEquipment",
    "Metrology": "concernsEquipment",
    "TechnologyNode": "concernsProcess",
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

    ONT_R = lambda local: URIRef(ONT + local)  # noqa: E731

    # self-describing schema (core ontology untouched)
    g.add((ONT_R("Patent"), RDF.type, OWL.Class))
    g.add((ONT_R("Patent"), RDFS.label, Literal("Rejected patent (SIRP corpus)", lang="en")))
    for p, c in {
        "concernsProcess": "patent concerns a Process/SubProcess",
        "concernsMaterial": "patent concerns a Material",
        "concernsEquipment": "patent concerns Equipment/Vendor/Class",
        "concernsSkill": "patent concerns a Skill",
        "concernsDevice": "patent concerns a Device/product architecture (A2)",
        "exhibitsFailureMode": "patent concerns a FailureMode",
        "relatedToTopic": "weak/uncategorized link to an ontology node",
        "applicationNumber": "patent application number",
        "patentOffice": "issuing office",
        "primaryIpc": "primary IPC code",
        "processFamily": "curator-assigned process family (structured field)",
        "valueChain": "curator-assigned value-chain position (structured)",
    }.items():
        g.add((ONT_R(p), RDF.type, OWL.ObjectProperty))
        g.add((ONT_R(p), RDFS.comment, Literal(c, lang="en")))

    type_dist = Counter()
    nodes_per: list[int] = []
    orphans: list[str] = []
    matched_terms = Counter()
    n_structured = 0          # patents that got >=1 structured Process link
    n_device = 0              # patents that got >=1 structured Device link (A2)
    n_text = 0                # patents that got >=1 free-text link
    orphan_scope_out: list[str] = []   # device/packaging/component — no node
    orphan_text_miss: list[str] = []   # in-domain yet still unlinked (fixable)
    fam_unmapped = Counter()  # in-domain families with no structured node

    for _, r in meta.iterrows():
        pid = str(r["patent_id"])
        pu = _u(pid)
        g.add((pu, RDF.type, ONT_R("Patent")))
        g.add((pu, RDFS.label, Literal(str(r.get("title") or pid))))
        for col, prop in (("application_number", "applicationNumber"),
                          ("patent_office", "patentOffice"),
                          ("primary_ipc", "primaryIpc"),
                          ("process_family", "processFamily"),
                          ("value_chain", "valueChain")):
            v = r.get(col)
            if pd.notna(v) and str(v).strip():
                g.add((pu, ONT_R(prop), Literal(str(v))))

        # 1) deterministic structured-field bridge (high precision, no NLP)
        fam = str(r.get("process_family") or "").strip().lower()
        linked: set[str] = set()
        if fam in PROCESS_FAMILY_MAP:
            nid = PROCESS_FAMILY_MAP[fam]
            g.add((pu, ONT_R("concernsProcess"), _u(nid)))
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

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    n = len(meta)
    report = {
        "input": str(META.relative_to(ROOT)),
        "patents": n,
        "triples": len(g),
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
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
