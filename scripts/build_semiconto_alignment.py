#!/usr/bin/env python3
"""Phase 0.3 — Build SDKB → SemicONTO alignment.

Direction (SDKB-centric, per docs/project/architecture_amendment_sdkb_centric.md):
  SDKB v1.0 is the trunk. SemicONTO is referenced as an external curation
  source via SKOS mappings — NOT imported as upper ontology.

Inputs
  - data/semiconductor_v0_3.json  (198 SDKB instance nodes)
  - data/reports/semiconto_analysis.json  (Phase 0.2 inventory)

Outputs
  - mappings/sdkb_semiconto_alignment.csv  (per-instance row)
  - mappings/sdkb_semiconto_alignment.ttl  (SKOS mapping triples + class-level
    owl:equivalentClass for exact matches)
  - data/reports/sdkb_semiconto_alignment_report.json  (summary stats)

Curation philosophy
  - Class-level mapping is the high-confidence skeleton (14 SDKB types).
  - Instance-level mapping inherits its type's class-level relation by default,
    unless an explicit `INSTANCE_OVERRIDE` entry refines it.
  - Existing baseline `provenance.cross_ref[source=semiconto]` entries are
    **corrected** here (Process→ExperimentStep is wrong; the SemicONTO class is
    ExperimentalStep, and Process should map to Experiment, not the step).
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, SKOS

ROOT = Path(__file__).resolve().parent.parent
BASELINE_JSON = ROOT / "data" / "semiconductor_v0_3.json"
SEMICONTO_REPORT = ROOT / "data" / "reports" / "semiconto_analysis.json"
OUT_CSV = ROOT / "mappings" / "sdkb_semiconto_alignment.csv"
OUT_TTL = ROOT / "mappings" / "sdkb_semiconto_alignment.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "sdkb_semiconto_alignment_report.json"

# ─── Namespaces ────────────────────────────────────────────────────
SDKB_DATA = Namespace("https://w3id.org/sdkb/data/")
SDKB_ONT = Namespace("https://w3id.org/sdkb/ont/")
SEMI = Namespace("http://w3id.org/SemicONTO/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# ─── Class-level curated alignment (14 SDKB types) ─────────────────
# Each entry: (target_iri, relation, confidence, rationale)
# relation ∈ {exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch, none}
# `none` means SemicONTO has no corresponding concept → enrichment candidate.
CLASS_ALIGNMENT: dict[str, tuple[str | None, str, float, str]] = {
    "Process": (
        str(SEMI.Experiment),
        "broadMatch",
        0.6,
        "SemicONTO Experiment is methodology-flavored; SDKB Process groups "
        "manufacturing steps. SDKB Process is narrower in scope but the "
        "closest SemicONTO ancestor.",
    ),
    "SubProcess": (
        str(SEMI.ExperimentalStep),
        "closeMatch",
        0.85,
        "Both denote a single step in a workflow. SDKB SubProcess is "
        "manufacturing-specific; SemicONTO ExperimentalStep is generic but the "
        "alignment is strong (prov:Activity in both).",
    ),
    "EquipmentClass": (
        None,
        "none",
        0.0,
        "SemicONTO has no class-of-equipment notion (only Equipment as "
        "prov:Agent). EquipmentClass is an SDKB-only abstraction layer over "
        "Equipment instances — enrichment candidate.",
    ),
    "Equipment": (
        str(SEMI.Equipment),
        "exactMatch",
        1.0,
        "Direct 1:1. Both are prov:Agent subclasses for physical tools.",
    ),
    "Vendor": (
        str(PROV.Agent),
        "broadMatch",
        0.7,
        "SemicONTO does not model vendor/supplier; the only available "
        "ancestor is prov:Agent (via reused PROV-O).",
    ),
    "Organization": (
        str(PROV.Agent),
        "broadMatch",
        0.7,
        "Same as Vendor — prov:Agent via PROV-O reuse.",
    ),
    "Parameter": (
        str(SEMI.MaterialProperty),
        "closeMatch",
        0.7,
        "SemicONTO MaterialProperty ⊂ qudt:Quantity covers measurable "
        "properties. SDKB Parameter is process-side (temp, pressure, RF "
        "power) but the quantity semantics align; QUDT bridge available.",
    ),
    "Metrology": (
        str(SEMI.ExperimentalMethod),
        "broadMatch",
        0.7,
        "SemicONTO ExperimentalMethod is a parent over Hall/PES/Spectral/etc. "
        "SDKB Metrology (CD-SEM, overlay, ellipsometry) fits as a "
        "narrower kind under it.",
    ),
    "Material": (
        str(SEMI.Material),
        "exactMatch",
        1.0,
        "Direct 1:1. Both denote a physical substance used in fabrication.",
    ),
    "TechnologyNode": (
        None,
        "none",
        0.0,
        "Absent in SemicONTO — enrichment candidate.",
    ),
    "FailureMode": (
        None,
        "none",
        0.0,
        "Absent in SemicONTO (no FMEA layer) — enrichment candidate.",
    ),
    "RootCause": (
        None,
        "none",
        0.0,
        "Absent in SemicONTO — enrichment candidate.",
    ),
    "Mitigation": (
        None,
        "none",
        0.0,
        "Absent in SemicONTO — enrichment candidate.",
    ),
    "Skill": (
        None,
        "none",
        0.0,
        "Absent in SemicONTO — enrichment candidate.",
    ),
}

# ─── Instance-level overrides (rare) ───────────────────────────────
# Used only when an instance maps to a more specific SemicONTO concept than
# its type-level default. Most instances inherit; overrides are exception.
# Format: sdkb_id -> (target_iri, relation, confidence, rationale)
INSTANCE_OVERRIDE: dict[str, tuple[str, str, float, str]] = {
    # (none for v1 — all 198 nodes inherit class-level mapping)
    # Future: e.g., material:polysilicon -> semiconto:Semiconductor (narrowMatch)
    # once curator confirms intrinsic/doped status per instance.
}

# ─── DatatypeProperty alignment ─────────────────────────────────────
# SemicONTO datatype properties for experiment/step labeling/description/ID.
# SDKB does NOT define dedicated datatype properties for these roles —
# instead, the W3C-standard SKOS/DCTERMS conventions cover them. Recording
# the mapping here makes the convention auditable and lets SPARQL queries
# bridge SemicONTO instances if encountered.
#
# Format: semiconto_local -> (sdkb_side_property_iri, relation, rationale)
DTPROP_ALIGNMENT: dict[str, tuple[str, str, str]] = {
    "hasExperimentName": (
        "http://www.w3.org/2004/02/skos/core#prefLabel",
        "closeMatch",
        "SemicONTO's experiment-name string is the canonical label of the "
        "experiment instance; SDKB uses skos:prefLabel for canonical names.",
    ),
    "hasExperimentAim": (
        "http://www.w3.org/2004/02/skos/core#definition",
        "closeMatch",
        "The aim/purpose of an experiment is its definitional statement; "
        "SDKB uses skos:definition for free-text definitions.",
    ),
    "hasExperimentalStepAim": (
        "http://www.w3.org/2004/02/skos/core#definition",
        "closeMatch",
        "Same convention as hasExperimentAim, applied to a step's purpose.",
    ),
    "hasExperimentalStepDescription": (
        "http://www.w3.org/2004/02/skos/core#definition",
        "closeMatch",
        "Step description maps to the same skos:definition role used by "
        "SDKB for free-text descriptions.",
    ),
    "hasExperimentalStepID": (
        "http://purl.org/dc/terms/identifier",
        "closeMatch",
        "Stable identifier role; SDKB uses dcterms:identifier (also "
        "encoded in the node URI fragment).",
    ),
}


def relation_to_skos(rel: str) -> URIRef | None:
    return {
        "exactMatch":   SKOS.exactMatch,
        "closeMatch":   SKOS.closeMatch,
        "broadMatch":   SKOS.broadMatch,
        "narrowMatch":  SKOS.narrowMatch,
        "relatedMatch": SKOS.relatedMatch,
    }.get(rel)


def sdkb_node_uri(node_id: str) -> URIRef:
    """SDKB instance URI from baseline ID (e.g. 'process:lithography')."""
    return URIRef(str(SDKB_DATA) + node_id.replace(":", "/"))


def sdkb_class_uri(node_type: str) -> URIRef:
    return URIRef(str(SDKB_ONT) + node_type)


def legacy_cross_ref_for(node: dict) -> str | None:
    crs = (node.get("provenance") or {}).get("cross_ref") or []
    for c in crs:
        if c.get("source") == "semiconto":
            cls = c.get("class")
            return cls if cls and cls != "None" else "(empty)"
    return None


def main() -> None:
    if not BASELINE_JSON.exists():
        raise SystemExit(f"missing {BASELINE_JSON}")
    if not SEMICONTO_REPORT.exists():
        raise SystemExit(
            f"missing {SEMICONTO_REPORT} — run scripts/analyze_semiconto.py first"
        )

    baseline = json.loads(BASELINE_JSON.read_text())
    semireport = json.loads(SEMICONTO_REPORT.read_text())
    semi_known = {c["iri"] for c in semireport["classes"]} | {
        str(PROV.Agent)
    }

    # ── Sanity check: every curated target IRI exists in the report ──
    for sdkb_type, (target, rel, *_rest) in CLASS_ALIGNMENT.items():
        if target is None:
            continue
        if target not in semi_known:
            raise SystemExit(
                f"target IRI for SDKB:{sdkb_type} not present in SemicONTO "
                f"inventory: {target}"
            )

    # ── Build CSV rows ──
    rows: list[dict] = []
    rel_counter: Counter[str] = Counter()
    type_with_target_counter: Counter[str] = Counter()
    legacy_corrections: list[dict] = []

    for n in baseline["nodes"]:
        nid = n["id"]
        ntype = n["type"]
        cls_target, cls_rel, cls_conf, cls_note = CLASS_ALIGNMENT[ntype]
        if nid in INSTANCE_OVERRIDE:
            tgt, rel, conf, note = INSTANCE_OVERRIDE[nid]
            source_kind = "instance_override"
        else:
            tgt, rel, conf, note = cls_target, cls_rel, cls_conf, cls_note
            source_kind = "class_inherit"

        legacy = legacy_cross_ref_for(n)
        # Flag legacy that disagrees with curation
        if legacy and tgt:
            # Compare local names (e.g. ExperimentStep vs ExperimentalStep)
            tgt_local = tgt.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if legacy != tgt_local:
                legacy_corrections.append({
                    "sdkb_id": nid,
                    "legacy_class": legacy,
                    "corrected_iri": tgt,
                    "relation": rel,
                })

        rows.append({
            "sdkb_id": nid,
            "sdkb_type": ntype,
            "sdkb_uri": str(sdkb_node_uri(nid)),
            "sdkb_label": n["canonical_name"],
            "semiconto_iri": tgt or "",
            "semiconto_local": (
                tgt.rsplit("/", 1)[-1].rsplit("#", 1)[-1] if tgt else ""
            ),
            "relation": rel,
            "confidence": conf,
            "source": source_kind,
            "legacy_cross_ref_class": legacy or "",
            "rationale": note,
        })
        rel_counter[rel] += 1
        if tgt:
            type_with_target_counter[ntype] += 1

    # ── Write CSV ──
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── Build TTL ──
    g = Graph()
    g.bind("sdkb", SDKB_ONT)
    g.bind("sdkb-data", SDKB_DATA)
    g.bind("semiconto", SEMI)
    g.bind("prov", PROV)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("dcterms", DCTERMS)

    align_graph = URIRef("https://w3id.org/sdkb/alignment/semiconto")
    g.add((align_graph, RDF.type, OWL.Ontology))
    g.add((align_graph, RDFS.label, Literal(
        "SDKB ↔ SemicONTO Alignment (SDKB-centric, SKOS mappings)", lang="en"
    )))
    g.add((align_graph, RDFS.comment, Literal(
        "SKOS mappings from SDKB v1.0 (trunk) to SemicONTO v0.2 "
        "(external curation source). SDKB does not owl:imports SemicONTO; "
        "SemicONTO terms are referenced by IRI only.", lang="en"
    )))
    g.add((align_graph, DCTERMS.source, URIRef("http://w3id.org/SemicONTO/0.2/")))
    g.add((align_graph, OWL.versionInfo, Literal("0.3-phase0")))

    # Class-level alignment (14 entries)
    for sdkb_type, (target, rel, conf, _note) in CLASS_ALIGNMENT.items():
        if target is None:
            continue
        sdkb_cls = sdkb_class_uri(sdkb_type)
        skos_pred = relation_to_skos(rel)
        if skos_pred is None:
            continue
        g.add((sdkb_cls, skos_pred, URIRef(target)))
        # For exactMatch, also assert owl:equivalentClass (interpretation: same set)
        if rel == "exactMatch":
            g.add((sdkb_cls, OWL.equivalentClass, URIRef(target)))

    # Instance-level alignment (198 entries) — only emit when target present
    for row in rows:
        tgt = row["semiconto_iri"]
        rel = row["relation"]
        if not tgt:
            continue
        skos_pred = relation_to_skos(rel)
        if skos_pred is None:
            continue
        sdkb_uri = URIRef(row["sdkb_uri"])
        g.add((sdkb_uri, skos_pred, URIRef(tgt)))

    # ── DatatypeProperty alignment (5 entries) ──
    # Direction: <sdkb-side W3C property> skos:closeMatch <semi:datatype_prop>
    # The rationale is stored as an rdfs:comment on the SemicONTO predicate.
    for semi_local, (sdkb_prop_iri, relation, rationale) in DTPROP_ALIGNMENT.items():
        semi_iri = URIRef(str(SEMI) + semi_local)
        sdkb_prop = URIRef(sdkb_prop_iri)
        skos_pred = relation_to_skos(relation)
        if skos_pred is not None:
            g.add((sdkb_prop, skos_pred, semi_iri))
        g.add((semi_iri, RDFS.comment, Literal(rationale, lang="en")))

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    # ── Write summary report ──
    summary = {
        "inputs": {
            "baseline_nodes": len(baseline["nodes"]),
            "semiconto_classes_own": semireport["counts"]["classes_own"],
        },
        "class_alignment": {
            sdkb_type: {
                "semiconto_iri": tgt,
                "relation": rel,
                "confidence": conf,
            }
            for sdkb_type, (tgt, rel, conf, _) in CLASS_ALIGNMENT.items()
        },
        "datatype_property_alignment": {
            semi_local: {
                "semi_iri": str(SEMI) + semi_local,
                "sdkb_side_property": sdkb_prop_iri,
                "relation": relation,
            }
            for semi_local, (sdkb_prop_iri, relation, _) in DTPROP_ALIGNMENT.items()
        },
        "instance_counts": {
            "total": len(rows),
            "with_target": sum(1 for r in rows if r["semiconto_iri"]),
            "without_target_enrichment_candidates": sum(
                1 for r in rows if not r["semiconto_iri"]
            ),
            "by_relation": dict(rel_counter),
            "with_target_by_type": dict(type_with_target_counter),
        },
        "legacy_corrections": {
            "count": len(legacy_corrections),
            "details": legacy_corrections,
        },
        "outputs": {
            "csv": str(OUT_CSV.relative_to(ROOT)),
            "ttl": str(OUT_TTL.relative_to(ROOT)),
            "triples_in_ttl": len(g),
        },
    }
    OUT_REPORT.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(
        f"✓ Alignment built: {len(rows)} instance rows "
        f"({summary['instance_counts']['with_target']} aligned, "
        f"{summary['instance_counts']['without_target_enrichment_candidates']} "
        f"unmapped/enrichment) — {len(g)} TTL triples"
    )
    print(f"  → {OUT_CSV.relative_to(ROOT)}")
    print(f"  → {OUT_TTL.relative_to(ROOT)}")
    print(f"  → {OUT_REPORT.relative_to(ROOT)}")
    print(f"  ⚠ legacy cross_ref corrections: {len(legacy_corrections)}")


if __name__ == "__main__":
    main()
