#!/usr/bin/env python3
"""Seed SDKB governance modules from ExpDataSet compliance masters.

Inputs (reference data, see [Park 2026a] — kukkukpool/ExpDataSet):
  data/compliance/kr_standards_v1.json   — KR_ITPA, 12 technology controls
  data/compliance/us_standards_v1.json   — US_EAR/CCL, 8 controls + Deemed Export

Outputs:
  ontology/sdkb-governance-kr-instances.ttl  — RDF instances under sdkb-governance-kr.ttl
  ontology/sdkb-governance-us-instances.ttl  — RDF instances under sdkb-governance.ttl
  data/compliance/technology_controls.parquet — flat table for analytics
  data/compliance/seed_report.json            — verification + counts

The KR file encodes the Korean Industrial Technology Protection Act (산업기술보호법
§33/§34) controls; the US file encodes EAR/CCL with the Deemed Export rule.
This is **reference master data**, not a contribution of this term — see
docs/expdataset_alignment.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS, SKOS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.namespaces import SDKB_ONT, SDKB_GOV, SDKB_DATA, PROV, PREFIX_MAP

IN_KR = ROOT / "data" / "compliance" / "kr_standards_v1.json"
IN_US = ROOT / "data" / "compliance" / "us_standards_v1.json"
OUT_KR_TTL = ROOT / "ontology" / "sdkb-governance-kr-instances.ttl"
OUT_US_TTL = ROOT / "ontology" / "sdkb-governance-us-instances.ttl"
OUT_FLAT = ROOT / "data" / "compliance" / "technology_controls.parquet"
OUT_REPORT = ROOT / "data" / "compliance" / "seed_report.json"


def _bind_prefixes(g: Graph) -> None:
    for pfx, ns in PREFIX_MAP.items():
        g.bind(pfx, str(ns))


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("/", "_").replace(".", "_")


def seed_kr(spec: dict) -> tuple[Graph, list[dict]]:
    g = Graph()
    _bind_prefixes(g)
    rows: list[dict] = []

    # Anchor the ITPA rule by name (already declared in sdkb-governance-kr.ttl)
    itpa_rule = SDKB_GOV["Rule_KR_ITPA"]

    for tc in spec["technology_controls"]:
        ctl_uri = SDKB_DATA["gov/kr/tech_control/" + _slug(tc["tech_keyword"])]
        g.add((ctl_uri, RDF.type, SDKB_GOV["KRIndustrialTechRule"]))
        g.add((ctl_uri, SKOS.prefLabel, Literal(tc["tech_keyword"], lang="en")))
        if tc.get("nct_code"):
            g.add((ctl_uri, SKOS.notation, Literal(tc["nct_code"])))
        if tc.get("description"):
            g.add((ctl_uri, RDFS.comment, Literal(tc["description"], lang="ko")))
        if tc.get("legal_basis"):
            g.add((ctl_uri, DCTERMS.bibliographicCitation, Literal(tc["legal_basis"])))
        g.add((ctl_uri, SDKB_ONT["interpretationType"], Literal("verbatim")))
        g.add((ctl_uri, DCTERMS.license, Literal("CDLA-Permissive-2.0")))
        g.add((ctl_uri, DCTERMS.source, Literal("ExpDataSet/kr_compliance_standards_v1.json [Park 2026a]")))
        # Link to NCT designation only if nct_code is present (CRITICAL/HIGH usually are)
        if tc.get("nct_code"):
            nct_uri = SDKB_DATA["gov/kr/nct/" + _slug(tc["nct_code"])]
            g.add((nct_uri, RDF.type, SDKB_GOV["NationalCoreTechnology"]))
            g.add((nct_uri, SKOS.notation, Literal(tc["nct_code"])))
            g.add((nct_uri, SDKB_GOV["nctField"], SDKB_GOV["NCTField_Semiconductor"]))
            g.add((nct_uri, SDKB_GOV["requiresGovApproval"],
                   Literal(tc["control_level"] in ("CRITICAL", "HIGH"), datatype=XSD.boolean)))
            g.add((ctl_uri, SDKB_GOV["designatedAsNCT"], nct_uri))
        g.add((ctl_uri, RDFS.seeAlso, itpa_rule))

        rows.append({
            "jurisdiction": tc["jurisdiction"],
            "tech_keyword": tc["tech_keyword"],
            "tech_category": tc.get("tech_category", ""),
            "control_level": tc["control_level"],
            "legal_basis": tc.get("legal_basis", ""),
            "nct_or_eccn": tc.get("nct_code", ""),
            "description": tc.get("description", ""),
            "export_restriction": tc.get("export_restriction", ""),
            "penalty": tc.get("penalty_on_violation", ""),
            "source_dataset": "kr_standards_v1",
        })
    return g, rows


def seed_us(spec: dict) -> tuple[Graph, list[dict]]:
    g = Graph()
    _bind_prefixes(g)
    rows: list[dict] = []

    bis_rule = SDKB_GOV["Rule_BIS_744_23"]

    for tc in spec["technology_controls"]:
        ctl_uri = SDKB_DATA["gov/us/tech_control/" + _slug(tc["tech_keyword"])]
        g.add((ctl_uri, RDF.type, SDKB_GOV["EARRule"]))
        g.add((ctl_uri, SKOS.prefLabel, Literal(tc["tech_keyword"], lang="en")))
        g.add((ctl_uri, SKOS.notation, Literal(tc.get("eccn", tc["tech_keyword"]))))
        g.add((ctl_uri, RDFS.comment, Literal(tc["description"], lang="ko")))
        g.add((ctl_uri, DCTERMS.bibliographicCitation, Literal(tc.get("legal_basis", "EAR_CCL"))))
        g.add((ctl_uri, SDKB_ONT["interpretationType"], Literal("verbatim")))
        g.add((ctl_uri, DCTERMS.license, Literal("CDLA-Permissive-2.0")))
        g.add((ctl_uri, DCTERMS.source, Literal("ExpDataSet/us_compliance_standards_v1.json [Park 2026a]")))
        # Tag entity-list restriction as datatype property if present
        if tc.get("entity_list_restriction"):
            g.add((ctl_uri, SDKB_ONT["securityLevel"], Literal("RESTRICTED")))
        g.add((ctl_uri, RDFS.seeAlso, bis_rule))

        rows.append({
            "jurisdiction": tc["jurisdiction"],
            "tech_keyword": tc["tech_keyword"],
            "tech_category": tc.get("tech_category", ""),
            "control_level": tc["control_level"],
            "legal_basis": tc.get("legal_basis", ""),
            "nct_or_eccn": tc.get("eccn", ""),
            "description": tc.get("description", ""),
            "export_restriction": tc.get("export_restriction", ""),
            "penalty": tc.get("penalty_on_violation", ""),
            "source_dataset": "us_standards_v1",
        })
    return g, rows


def main() -> None:
    if not IN_KR.exists() or not IN_US.exists():
        print("ERROR: compliance JSONs not found. Copy from ExpDataSet first.", file=sys.stderr)
        sys.exit(1)

    kr_spec = json.loads(IN_KR.read_text(encoding="utf-8"))
    us_spec = json.loads(IN_US.read_text(encoding="utf-8"))

    kr_graph, kr_rows = seed_kr(kr_spec)
    us_graph, us_rows = seed_us(us_spec)

    OUT_KR_TTL.parent.mkdir(parents=True, exist_ok=True)
    kr_graph.serialize(str(OUT_KR_TTL), format="turtle")
    us_graph.serialize(str(OUT_US_TTL), format="turtle")

    flat = pd.DataFrame(kr_rows + us_rows)
    flat.to_parquet(OUT_FLAT, index=False)

    report = {
        "source_kr": str(IN_KR.relative_to(ROOT)),
        "source_us": str(IN_US.relative_to(ROOT)),
        "kr_version": kr_spec.get("version"),
        "us_version": us_spec.get("version"),
        "kr_technology_controls": len(kr_rows),
        "us_technology_controls": len(us_rows),
        "kr_triples": len(kr_graph),
        "us_triples": len(us_graph),
        "control_level_distribution": {k: int(v) for k, v in flat["control_level"].value_counts().items()},
        "jurisdiction_distribution": {k: int(v) for k, v in flat["jurisdiction"].value_counts().items()},
        "outputs": {
            "kr_ttl": str(OUT_KR_TTL.relative_to(ROOT)),
            "us_ttl": str(OUT_US_TTL.relative_to(ROOT)),
            "flat_parquet": str(OUT_FLAT.relative_to(ROOT)),
        },
        "citation": "Park 2026a — ExpDataSet v3.3.5 (kukkukpool); used as reference master data.",
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ KR governance instances ({len(kr_graph)} triples, {len(kr_rows)} controls) → {OUT_KR_TTL.relative_to(ROOT)}")
    print(f"✓ US governance instances ({len(us_graph)} triples, {len(us_rows)} controls) → {OUT_US_TTL.relative_to(ROOT)}")
    print(f"✓ Flat table ({len(flat)} rows) → {OUT_FLAT.relative_to(ROOT)}")
    print(f"  level distribution: {report['control_level_distribution']}")


if __name__ == "__main__":
    main()
