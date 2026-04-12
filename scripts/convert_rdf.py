#!/usr/bin/env python3
"""Week 3 — Convert baseline JSON to RDF (Turtle) and JSON-LD.

Outputs:
  ontology/sdkb-core-data.ttl   — All nodes/edges/synonyms as RDF triples
  ontology/sdkb-core-data.jsonld — Same data in JSON-LD format
"""

import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.namespaces import (
    SDKB_ONT, SDKB_DATA, SDKB_GOV, PROV, PREFIX_MAP, SDKB_BASE,
)

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "semiconductor_v0_3.json"
OUT_TTL = ROOT / "ontology" / "sdkb-core-data.ttl"
OUT_JSONLD = ROOT / "ontology" / "sdkb-core-data.jsonld"


def uri(node_id: str) -> URIRef:
    """Convert baseline ID (e.g. 'process:lithography') to data URI."""
    return URIRef(str(SDKB_DATA) + node_id.replace(":", "/"))


# Predicate → OWL property mapping
PRED_MAP = {
    "HAS_SUBPROCESS":       SDKB_ONT.hasSubprocess,
    "USES_MATERIAL":        SDKB_ONT.usesMaterial,
    "USES_EQUIPMENT_CLASS": SDKB_ONT.usesEquipmentClass,
    "HAS_PARAMETER":        SDKB_ONT.hasParameter,
    "MEASURED_BY":          SDKB_ONT.measuredBy,
    "REQUIRES_SKILL":       SDKB_ONT.requiresSkill,
    "IS_INSTANCE_OF":       SDKB_ONT.isInstanceOf,
    "PROVIDED_BY":          SDKB_ONT.providedBy,
    "MADE_BY":              SDKB_ONT.madeBy,
    "CAUSED_BY":            SDKB_ONT.isDueTo,
    "OBSERVED_IN":          SDKB_ONT.occursAtProcessStep,
    "MITIGATED_BY":         SDKB_ONT.mitigatedBy,
    "INCOMPATIBLE_WITH":    SDKB_ONT.incompatibleWith,
    "NOT_ALLOWED_WITH":     SDKB_ONT.notAllowedWith,
}


def convert_nodes(g: Graph, nodes: list) -> None:
    for n in nodes:
        u = uri(n["id"])
        g.add((u, RDF.type, SDKB_ONT[n["type"]]))
        g.add((u, SKOS.prefLabel, Literal(n["canonical_name"], lang="en")))

        if n.get("description"):
            g.add((u, SKOS.definition, Literal(n["description"], lang="en")))

        # Provenance fields
        prov = n.get("provenance", {})
        if prov.get("source"):
            g.add((u, DCTERMS.source, Literal(prov["source"])))
        if prov.get("license"):
            g.add((u, DCTERMS.license, Literal(prov["license"])))
        if prov.get("reference"):
            g.add((u, DCTERMS.bibliographicCitation, Literal(prov["reference"])))
        if prov.get("url") and prov["url"].startswith("http"):
            g.add((u, RDFS.seeAlso, URIRef(prov["url"])))
        if prov.get("interpretation"):
            g.add((u, SDKB_ONT.interpretationType, Literal(prov["interpretation"])))
        if prov.get("validation_required") is not None:
            g.add((u, SDKB_ONT.validationRequired, Literal(prov["validation_required"], datatype=XSD.boolean)))


def convert_synonyms(g: Graph, synonyms: list) -> None:
    for s in synonyms:
        u = uri(s["node_id"])
        lang = s.get("lang", "und")
        g.add((u, SKOS.altLabel, Literal(s["term"], lang=lang)))


def convert_edges(g: Graph, edges: list) -> None:
    for e in edges:
        s = uri(e["src"])
        o = uri(e["dst"])
        pred_key = e["predicate"]
        p = PRED_MAP.get(pred_key, SDKB_ONT[pred_key])
        g.add((s, p, o))

        # Reified weight → confidence (if present)
        if e.get("weight") is not None:
            # For negative weights (constraints), we still store abs value as confidence
            # and mark constraint type
            w = e["weight"]
            if w < 0:
                g.add((s, SDKB_ONT.confidence, Literal(abs(w), datatype=XSD.decimal)))
            else:
                g.add((s, SDKB_ONT.confidence, Literal(w, datatype=XSD.decimal)))

        # Edge provenance
        ep = e.get("provenance", {})
        if ep.get("validation_required"):
            g.add((s, SDKB_ONT.validationRequired, Literal(True, datatype=XSD.boolean)))


def main():
    if not IN_PATH.exists():
        print(f"ERROR: {IN_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    g = Graph()
    for pfx, ns in PREFIX_MAP.items():
        g.bind(pfx, str(ns))
    g.bind("owl", "http://www.w3.org/2002/07/owl#")
    g.bind("rdfs", str(RDFS))
    g.bind("xsd", str(XSD))

    convert_nodes(g, data["nodes"])
    convert_synonyms(g, data.get("synonyms", []))
    convert_edges(g, data["edges"])

    # ── Serialize Turtle ──────────────────────────────────────
    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")
    print(f"✓ RDF/Turtle ({len(g)} triples) → {OUT_TTL}")

    # ── Serialize JSON-LD ─────────────────────────────────────
    g.serialize(str(OUT_JSONLD), format="json-ld")
    print(f"✓ JSON-LD → {OUT_JSONLD}")


if __name__ == "__main__":
    main()
