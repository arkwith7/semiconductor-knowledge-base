#!/usr/bin/env python3
"""Phase 0.4 — Identify two complementary enrichment buckets.

Bucket A (SemicONTO → SDKB): SemicONTO own classes that SDKB does NOT
currently cover. These are CANDIDATE classes to import as SDKB v1.1
extension (in `sdkb:` namespace, optionally `skos:exactMatch` linked back
to SemicONTO).

Bucket B (SDKB → external): SDKB classes that SemicONTO does NOT have.
These confirm SDKB's net contribution and inform what other external
sources (JEDEC for FMEA, SEMI for EquipmentState, etc.) need to fill.

Output: data/reports/semiconto_enrichment_candidates.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMI_REPORT = ROOT / "data" / "reports" / "semiconto_analysis.json"
ALIGN_REPORT = ROOT / "data" / "reports" / "sdkb_semiconto_alignment_report.json"
OUT_PATH = ROOT / "data" / "reports" / "semiconto_enrichment_candidates.json"


def main() -> None:
    semi = json.loads(SEMI_REPORT.read_text())
    align = json.loads(ALIGN_REPORT.read_text())

    # Set of SemicONTO IRIs already targeted by SDKB at class level
    targeted_iris = {
        info["semiconto_iri"]
        for info in align["class_alignment"].values()
        if info.get("semiconto_iri")
    }

    # ── Bucket A: SemicONTO own classes NOT targeted by SDKB ──
    bucket_a: list[dict] = []
    for c in semi["classes"]:
        if c["kind"] != "own":
            continue
        if c["iri"] in targeted_iris:
            continue
        bucket_a.append({
            "semiconto_iri": c["iri"],
            "local": c["local"],
            "label": c["label"],
            "super_classes": c["super_classes"],
            "restriction_count": c["restriction_count"],
        })

    # Sub-group bucket A by top parent for readability
    def top_parent(c: dict) -> str:
        if not c["super_classes"]:
            return "(root)"
        # Use first parent's local name
        p = c["super_classes"][0]
        return p.rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    bucket_a_grouped: dict[str, list[dict]] = {}
    for c in bucket_a:
        g = top_parent(c)
        bucket_a_grouped.setdefault(g, []).append(c)

    # ── Bucket B: SDKB types with no SemicONTO match ──
    bucket_b: list[dict] = []
    for sdkb_type, info in align["class_alignment"].items():
        if info.get("semiconto_iri") is None:
            bucket_b.append({
                "sdkb_type": sdkb_type,
                "relation": info["relation"],
                "rationale_short": "SemicONTO has no corresponding concept",
            })

    # ── Priority-ranked enrichment recommendations (Bucket A) ──
    # Heuristic: a SemicONTO class with high curation density (axioms /
    # subclasses) and conceptual generality is a higher-value import.
    PRIORITY: dict[str, dict] = {
        "MaterialProperty": {
            "priority": "HIGH",
            "rationale": (
                "QUDT-anchored quantity. SDKB Parameter has no unit/quantity "
                "system; importing MaterialProperty + qudt:Quantity gives SDKB "
                "a standards-grounded measurement layer."
            ),
            "sdkb_target": "sdkb:Parameter (narrow refinement) OR new "
                           "sdkb:MaterialProperty class",
        },
        "Dopant": {
            "priority": "HIGH",
            "rationale": (
                "Dopant = Acceptor ∪ Donor is a canonical semiconductor "
                "concept absent from SDKB Material taxonomy. Enables ion-"
                "implant / diffusion process modeling."
            ),
            "sdkb_target": "new sdkb:Dopant ⊂ sdkb:Material (with Acceptor/Donor)",
        },
        "Semiconductor": {
            "priority": "HIGH",
            "rationale": (
                "SDKB Material has no semiconductor sub-class. Importing "
                "Semiconductor + Intrinsic/Extrinsic + N/P-Type aligns with "
                "the field's primary substance categorization."
            ),
            "sdkb_target": "new sdkb:Semiconductor ⊂ sdkb:Material",
        },
        "IntrinsicSemiconductor": {"priority": "HIGH", "rationale": "with Semiconductor", "sdkb_target": ""},
        "ExtrinsicSemiconductor": {"priority": "HIGH", "rationale": "with Semiconductor", "sdkb_target": ""},
        "N-TypeSemiconductor": {"priority": "MEDIUM", "rationale": "leaf of ExtrinsicSemiconductor", "sdkb_target": ""},
        "P-TypeSemiconductor": {"priority": "MEDIUM", "rationale": "leaf of ExtrinsicSemiconductor", "sdkb_target": ""},
        "Acceptor": {"priority": "HIGH", "rationale": "with Dopant", "sdkb_target": ""},
        "Donor": {"priority": "HIGH", "rationale": "with Dopant", "sdkb_target": ""},
        "ChemicalEntity": {
            "priority": "LOW",
            "rationale": (
                "Bridge to OBO ChEBI / EMMO. Useful for compliance (REACH/SCIP) "
                "alignment but not central to current SDKB use cases."
            ),
            "sdkb_target": "optional sdkb:ChemicalEntity ⊂ sdkb:Material",
        },
        "ChemicalSubstance": {"priority": "LOW", "rationale": "with ChemicalEntity", "sdkb_target": ""},
        "MolecularEntity":   {"priority": "LOW", "rationale": "with ChemicalEntity", "sdkb_target": ""},
        "Matter":            {"priority": "LOW", "rationale": "top-level abstract — not actionable", "sdkb_target": ""},
        "DopingRelation":    {"priority": "MEDIUM", "rationale": "useful with Dopant", "sdkb_target": ""},
        "Experiment":             {"priority": "—", "rationale": "already targeted (broadMatch from Process)", "sdkb_target": "—"},
        "SemiconductorExperiment":{"priority": "MEDIUM",
            "rationale": (
                "A semiconductor-specific experiment grouping. SDKB has no "
                "explicit experiment type; could be useful for prior-art "
                "characterization linking."
            ),
            "sdkb_target": "optional sdkb:SemiconductorExperiment"},
        "CMTExperiment":  {"priority": "LOW", "rationale": "narrow experiment leaf — only if SDKB models device characterization", "sdkb_target": ""},
        "EQETExperiment": {"priority": "LOW", "rationale": "narrow experiment leaf", "sdkb_target": ""},
        "HMTExperiment":  {"priority": "LOW", "rationale": "narrow experiment leaf", "sdkb_target": ""},
        "PESExperiment":  {"priority": "LOW", "rationale": "narrow experiment leaf", "sdkb_target": ""},
        "PPCExperiment":  {"priority": "LOW", "rationale": "narrow experiment leaf", "sdkb_target": ""},
        "SEDFabrication": {"priority": "LOW", "rationale": "narrow fabrication leaf (single-electron device)", "sdkb_target": ""},
        "ElectronBeamLithography":  {"priority": "MEDIUM", "rationale": "could be sub-class of sdkb:SubProcess (e-beam patterning)", "sdkb_target": "optional sdkb:ElectronBeamLithography ⊂ sdkb:SubProcess"},
        "ThermalEvaporation":       {"priority": "MEDIUM", "rationale": "PVD variant — could refine sdkb:pvd SubProcess", "sdkb_target": "optional"},
        "PhotoelectronSpectroscopy":{"priority": "MEDIUM", "rationale": "XPS — common semiconductor metrology; SDKB Metrology layer is thin (3 nodes)", "sdkb_target": "optional sdkb:PhotoelectronSpectroscopy ⊂ sdkb:Metrology"},
        "HallEffectMeasurement":    {"priority": "MEDIUM", "rationale": "carrier-property metrology; expands SDKB Metrology", "sdkb_target": "optional"},
        "FieldEffectMeasurement":   {"priority": "MEDIUM", "rationale": "device-characterization metrology", "sdkb_target": "optional"},
        "SpectralResponseMeasurement":{"priority": "LOW", "rationale": "photovoltaic-leaning metrology", "sdkb_target": ""},
        "ExperimentalMethod":       {"priority": "—", "rationale": "already targeted (broadMatch from Metrology)", "sdkb_target": "—"},
        "ExperimentalStep":         {"priority": "—", "rationale": "already targeted (closeMatch from SubProcess)", "sdkb_target": "—"},
        "ExperimentInfoObj":        {"priority": "LOW", "rationale": "metadata wrapper class — SDKB uses parquet/provenance schema instead", "sdkb_target": ""},
        "StepInfoObj":              {"priority": "LOW", "rationale": "metadata wrapper class", "sdkb_target": ""},
        "InformationObject":        {"priority": "LOW", "rationale": "abstract wrapper", "sdkb_target": ""},
    }

    # Apply priority to bucket_a entries
    for c in bucket_a:
        p = PRIORITY.get(c["local"], {})
        c["priority"] = p.get("priority", "TBD")
        c["enrichment_rationale"] = p.get("rationale", "")
        c["proposed_sdkb_target"] = p.get("sdkb_target", "")

    # Sort: HIGH first, then MEDIUM, then LOW
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "TBD": 3, "—": 9}
    bucket_a_sorted = sorted(
        bucket_a, key=lambda c: (rank.get(c["priority"], 9), c["local"])
    )

    # Object/datatype properties unique to SemicONTO that SDKB lacks
    sdkb_known_predicate_locals = {
        "hasSubprocess", "usesMaterial", "usesEquipmentClass", "hasParameter",
        "measuredBy", "requiresSkill", "isInstanceOf", "providedBy", "madeBy",
        "occursAtProcessStep", "isDueTo", "mitigatedBy", "affectsMetric",
        "relevantForTechNode", "incompatibleWith", "notAllowedWith",
        "hasECCN", "controlledBy", "relevantOutcome", "belongsToFunction",
        "hasSVHC", "standardRef", "hasEquipmentState", "hasCommunicationProtocol",
    }
    enrichment_props_obj: list[dict] = []
    for p in semi["object_properties"]:
        if p["kind"] != "own":
            continue
        if p["local"] in sdkb_known_predicate_locals:
            continue
        enrichment_props_obj.append({
            "semiconto_iri": p["iri"],
            "local": p["local"],
            "label": p["label"],
            "domain": p["domain"],
            "range": p["range"],
            "transitive": p["transitive"],
        })

    enrichment_props_dt: list[dict] = []
    sdkb_known_dt_locals = {
        "confidence", "probability", "interpretationType", "validationRequired",
        "securityLevel", "svhcConcentration", "tppValue", "effectiveDate",
        "retrievedDate", "changeSet", "deprecatedId", "conflictNote",
        "reviewStatus", "granularity",
    }
    for p in semi["datatype_properties"]:
        if p["kind"] != "own":
            continue
        if p["local"] in sdkb_known_dt_locals:
            continue
        enrichment_props_dt.append({
            "semiconto_iri": p["iri"],
            "local": p["local"],
            "label": p["label"],
            "domain": p["domain"],
            "range": p["range"],
        })

    out = {
        "bucket_a_semiconto_into_sdkb": {
            "summary": (
                "SemicONTO own classes that SDKB does NOT cover at class level. "
                "Candidates for SDKB v1.1 enrichment under sdkb: namespace, "
                "with optional skos:exactMatch back to SemicONTO."
            ),
            "count": len(bucket_a),
            "by_top_parent": {k: len(v) for k, v in bucket_a_grouped.items()},
            "classes": bucket_a_sorted,
            "object_properties": enrichment_props_obj,
            "datatype_properties": enrichment_props_dt,
        },
        "bucket_b_sdkb_unique_to_external": {
            "summary": (
                "SDKB class-level concepts absent from SemicONTO. These confirm "
                "SDKB's net contribution; richer alignment requires other "
                "external sources (JEDEC for FMEA, SEMI for EquipmentState, "
                "tibonto/dr for Vendor)."
            ),
            "count": len(bucket_b),
            "types": bucket_b,
        },
    }

    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(
        f"✓ Enrichment candidates report:\n"
        f"  Bucket A (SemicONTO → SDKB): {len(bucket_a)} classes, "
        f"{len(enrichment_props_obj)} obj props, "
        f"{len(enrichment_props_dt)} dt props\n"
        f"  Bucket B (SDKB unique): {len(bucket_b)} types\n"
        f"  → {OUT_PATH.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
