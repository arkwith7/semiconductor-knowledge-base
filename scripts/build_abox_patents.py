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
}


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
        "exhibitsFailureMode": "patent concerns a FailureMode",
        "relatedToTopic": "weak/uncategorized link to an ontology node",
        "applicationNumber": "patent application number",
        "patentOffice": "issuing office",
        "primaryIpc": "primary IPC code",
    }.items():
        g.add((ONT_R(p), RDF.type, OWL.ObjectProperty))
        g.add((ONT_R(p), RDFS.comment, Literal(c, lang="en")))

    type_dist = Counter()
    nodes_per: list[int] = []
    orphans: list[str] = []
    matched_terms = Counter()

    for _, r in meta.iterrows():
        pid = str(r["patent_id"])
        pu = _u(pid)
        g.add((pu, RDF.type, ONT_R("Patent")))
        g.add((pu, RDFS.label, Literal(str(r.get("title") or pid))))
        for col, prop in (("application_number", "applicationNumber"),
                          ("patent_office", "patentOffice"),
                          ("primary_ipc", "primaryIpc")):
            v = r.get(col)
            if pd.notna(v) and str(v).strip():
                g.add((pu, ONT_R(prop), Literal(str(v))))

        text = (f"{r.get('title') or ''} {r.get('abstract') or ''} "
                f"{r.get('claim1') or ''}")
        linked: set[str] = set()
        for term, hits in br.extract_from_text(text).items():
            for nid, typ in hits:
                prop = PATENT_ROUTING.get(typ)
                if not prop:
                    continue
                g.add((pu, ONT_R(prop), _u(nid)))
                linked.add(nid)
                type_dist[typ] += 1
            if hits:
                matched_terms[term] += 1
        nodes_per.append(len(linked))
        if not linked:
            orphans.append(pid)

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    n = len(meta)
    report = {
        "input": str(META.relative_to(ROOT)),
        "patents": n,
        "triples": len(g),
        "patents_with_ontology_link": n - len(orphans),
        "orphans_count": len(orphans),
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
        "bridge_mode": mode,
        "note": "Korean free-text lift via the shared 2-tier bridge "
                "(sdkb_nb / build_abox_experts_problems) over "
                "title+abstract+claim1. Orphans are graph-unrankable for "
                "prior-art and reported honestly.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    npp = report["nodes_per_patent"]
    print(f"✓ Patent A-Box ({len(g):,} triples) → {OUT_TTL.relative_to(ROOT)}")
    print(f"  patents={n}  linked={n - len(orphans)} "
          f"orphans={len(orphans)}  nodes/patent mean={npp['mean']} "
          f"median={npp['median']} zero={npp['zero']}")
    print(f"  edges by type: {dict(type_dist.most_common(6))}")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
