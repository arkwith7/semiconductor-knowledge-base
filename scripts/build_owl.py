#!/usr/bin/env python3
"""Week 2 — OWL metamodel: generate sdkb-core.owl (Turtle) from namespace policy.

Defines the 14 Core class hierarchy, Governance extension classes,
object/datatype properties, and annotation properties for SDKB v1.0.
"""

from pathlib import Path
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS, SKOS

# Add parent to path for config import
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.namespaces import SDKB_ONT, SDKB_GOV, SDKB_BASE, PROV, PREFIX_MAP

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ontology" / "sdkb-core.ttl"

# ─── Permissive domain/range overrides ─────────────────────────────────
# A handful of curation predicates are used with multiple subject/object
# class shapes in the baseline data. Emit owl:unionOf rather than a single
# class so RDFS reasoning does not mis-type nodes (e.g. RootCause being
# coerced into FailureMode through ont:mitigatedBy's domain).
PERMISSIVE_DOMAIN: dict[str, list[str]] = {
    "mitigatedBy":      ["FailureMode", "RootCause"],
    "requiresSkill":    ["SubProcess", "Mitigation"],
    "madeBy":           ["Material", "EquipmentClass"],
    "incompatibleWith": ["SubProcess", "EquipmentClass", "Material"],
}
PERMISSIVE_RANGE: dict[str, list[str]] = {
    "notAllowedWith":   ["Material", "Parameter", "SubProcess"],
}


def build_ontology() -> Graph:
    g = Graph()

    # ── Bind prefixes ────────────────────────────────────────
    for pfx, ns in PREFIX_MAP.items():
        g.bind(pfx, str(ns))
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    ont = URIRef(SDKB_BASE + "ont")

    # ── Ontology declaration ─────────────────────────────────
    g.add((ont, RDF.type, OWL.Ontology))
    g.add((ont, RDFS.label, Literal("SDKB v1.0 — Semiconductor Domain Knowledge Base Ontology", lang="en")))
    g.add((ont, RDFS.comment, Literal(
        "Provenance-grounded curation ontology for semiconductor manufacturing, "
        "covering process, equipment, materials, FMEA, and regulatory governance layers.",
        lang="en"
    )))
    g.add((ont, OWL.versionInfo, Literal("1.0.0-dev")))
    g.add((ont, DCTERMS.license, URIRef("https://spdx.org/licenses/CDLA-Permissive-2.0.html")))
    g.add((ont, DCTERMS.creator, Literal("Park HyoungSik — SKKU MOT")))
    g.add((ont, OWL.imports, URIRef("http://www.w3.org/ns/prov-o#")))

    # ═══════════════════════════════════════════════════════════
    # CLASSES — Domain Layer (14 Core types)
    # ═══════════════════════════════════════════════════════════
    core_classes = {
        "Process":        "A major semiconductor manufacturing process (e.g. Lithography, Etch).",
        "SubProcess":     "A sub-step within a Process (e.g. Wet Etch, Plasma Etch).",
        "EquipmentClass": "A category of semiconductor manufacturing equipment.",
        "Equipment":      "A specific equipment instance (model/vendor).",
        "Vendor":         "A supplier or manufacturer of equipment or materials.",
        "Organization":   "An industry consortium, standards body, or institution.",
        "Parameter":      "A measurable process parameter (e.g. temperature, pressure).",
        "Metrology":      "A measurement or inspection method.",
        "Material":       "A raw material, chemical, or substance used in manufacturing.",
        "TechnologyNode": "A semiconductor technology generation (e.g. 7nm, 3nm).",
        "FailureMode":    "A defect or failure observed in manufacturing.",
        "RootCause":      "An identified root cause of a failure mode.",
        "Mitigation":     "A corrective or preventive action for a failure mode.",
        "Skill":          "A human competency required for a process or mitigation.",
    }

    for cls_name, desc in core_classes.items():
        cls = SDKB_ONT[cls_name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls_name, lang="en")))
        g.add((cls, RDFS.comment, Literal(desc, lang="en")))

    # SubProcess rdfs:subClassOf Process (hierarchy)
    g.add((SDKB_ONT.SubProcess, RDFS.subClassOf, SDKB_ONT.Process))

    # ═══════════════════════════════════════════════════════════
    # CLASSES — Governance Layer
    # ═══════════════════════════════════════════════════════════
    gov_classes = {
        "EARRule":          "A BIS Export Administration Regulation rule (e.g. §744.23).",
        "RegulatedItem":    "An item classified by ECCN (e.g. 3B001).",
        "NISTFunction":     "A NIST CSF 2.0 function (Govern/Identify/Protect/Detect/Respond/Recover).",
        "NISTOutcome":      "A desired security outcome from NIST IR 8546.",
        "SCIPRule":         "An ECHA SCIP reporting rule for SVHC substances.",
        "StandardReference":"A reference to a paywalled/restricted standard (Link-Only).",
        "EquipmentState":   "A SEMI E10 equipment state (Productive/Standby/Engineering/etc.).",
    }

    for cls_name, desc in gov_classes.items():
        cls = SDKB_GOV[cls_name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls_name, lang="en")))
        g.add((cls, RDFS.comment, Literal(desc, lang="en")))

    # EquipmentState as subclass of prov:Entity
    g.add((SDKB_GOV.EquipmentState, RDFS.subClassOf, PROV.Entity))

    # ═══════════════════════════════════════════════════════════
    # OBJECT PROPERTIES — Domain Layer
    # ═══════════════════════════════════════════════════════════
    obj_props = {
        # Process/SubProcess relations
        "hasSubprocess":       ("Process",        "SubProcess",     "Links a process to its sub-steps."),
        "usesMaterial":        ("SubProcess",     "Material",       "Material used in a sub-process."),
        "usesEquipmentClass":  ("SubProcess",     "EquipmentClass", "Equipment class used in a sub-process."),
        "hasParameter":        ("SubProcess",     "Parameter",      "A measurable parameter of a sub-process."),
        "measuredBy":          ("SubProcess",     "Metrology",      "Metrology method for a sub-process."),
        "requiresSkill":       ("SubProcess",     "Skill",          "Skill required for a sub-process or mitigation."),
        # Equipment relations
        "isInstanceOf":        ("Equipment",      "EquipmentClass", "Equipment belongs to a class."),
        "providedBy":          ("Equipment",      "Vendor",         "Equipment supplied by vendor."),
        "madeBy":              ("Material",       "Vendor",         "Material produced by vendor."),
        # FMEA relations
        "occursAtProcessStep": ("FailureMode",    "SubProcess",     "Failure observed at a process step."),
        "isDueTo":             ("FailureMode",    "RootCause",      "Causal link from failure to root cause."),
        "mitigatedBy":         ("FailureMode",    "Mitigation",     "Mitigation action for a failure mode."),
        "affectsMetric":       ("FailureMode",    "Parameter",      "Metric affected by the failure (e.g. CD, LER)."),
        # Technology node
        "relevantForTechNode": ("SubProcess",     "TechnologyNode", "Sub-process relevant for a technology node."),
        # Negative constraints
        "incompatibleWith":    ("SubProcess",     "Material",       "Material incompatible with a sub-process."),
        "notAllowedWith":      ("SubProcess",     "Material",       "Material not permitted in a sub-process."),
    }

    def _resolve(cls_name: str) -> URIRef:
        return (SDKB_GOV if cls_name in gov_classes else SDKB_ONT)[cls_name]

    def _emit_class_or_union(prop_uri: URIRef, predicate: URIRef,
                             spec) -> None:
        """spec is a class name str or a list of class names (→ owl:unionOf)."""
        if isinstance(spec, list):
            union_node = BNode()
            list_root = BNode()
            g.add((prop_uri, predicate, union_node))
            g.add((union_node, RDF.type, OWL.Class))
            g.add((union_node, OWL.unionOf, list_root))
            Collection(g, list_root, [_resolve(c) for c in spec])
        else:
            g.add((prop_uri, predicate, _resolve(spec)))

    for prop_name, (domain, range_, desc) in obj_props.items():
        prop = SDKB_ONT[prop_name]
        g.add((prop, RDF.type, OWL.ObjectProperty))
        g.add((prop, RDFS.label, Literal(prop_name, lang="en")))
        g.add((prop, RDFS.comment, Literal(desc, lang="en")))
        # Use permissive overrides where the baseline data exercises multiple shapes.
        dom_spec = PERMISSIVE_DOMAIN.get(prop_name, domain)
        rng_spec = PERMISSIVE_RANGE.get(prop_name, range_)
        _emit_class_or_union(prop, RDFS.domain, dom_spec)
        _emit_class_or_union(prop, RDFS.range, rng_spec)

    # ═══════════════════════════════════════════════════════════
    # OBJECT PROPERTIES — Governance Layer
    # ═══════════════════════════════════════════════════════════
    gov_obj_props = {
        "hasECCN":                ("EquipmentClass", "RegulatedItem",    "Links equipment class to ECCN classification."),
        "controlledBy":           ("RegulatedItem",  "EARRule",          "Regulation controlling this item."),
        "relevantOutcome":        ("Equipment",      "NISTOutcome",      "NIST security outcome relevant to equipment."),
        "belongsToFunction":      ("NISTOutcome",    "NISTFunction",     "Outcome belongs to a NIST CSF 2.0 function."),
        "hasSVHC":                ("Material",       "SCIPRule",         "Material linked to SCIP reporting rule."),
        "standardRef":            ("EquipmentClass", "StandardReference","Reference to an industry standard."),
        "hasEquipmentState":      ("Equipment",      "EquipmentState",   "Current equipment state per SEMI E10."),
        "hasCommunicationProtocol":("Equipment",     "StandardReference","Communication protocol standard (E30/EDA)."),
    }

    for prop_name, (domain, range_, desc) in gov_obj_props.items():
        prop = SDKB_ONT[prop_name]
        g.add((prop, RDF.type, OWL.ObjectProperty))
        g.add((prop, RDFS.label, Literal(prop_name, lang="en")))
        g.add((prop, RDFS.comment, Literal(desc, lang="en")))
        _emit_class_or_union(prop, RDFS.domain, domain)
        _emit_class_or_union(prop, RDFS.range, range_)

    # ═══════════════════════════════════════════════════════════
    # DATATYPE PROPERTIES
    # ═══════════════════════════════════════════════════════════
    dt_props = {
        "confidence":          (None, XSD.decimal,  "Confidence score (0.0–1.0) from expert/literature."),
        "probability":         (None, XSD.decimal,  "Conditional probability of cause→failure (optional)."),
        "interpretationType":  (None, XSD.string,   "Interpretation: verbatim | mapped | author-defined."),
        "validationRequired":  (None, XSD.boolean,  "Whether this entity needs expert validation."),
        "securityLevel":       (None, XSD.string,   "Security classification: PUBLIC | RESTRICTED."),
        "svhcConcentration":   (None, XSD.decimal,  "SVHC concentration (w/w fraction)."),
        "tppValue":            (None, XSD.decimal,  "Total Processing Performance value."),
        "effectiveDate":       (None, XSD.date,     "Regulatory effective date."),
        "retrievedDate":       (None, XSD.date,     "Date when the data was retrieved."),
        "changeSet":           (None, XSD.string,   "Release version tag for change tracking."),
        "deprecatedId":        (None, XSD.string,   "Former ID preserved after merge."),
        "conflictNote":        (None, XSD.string,   "Note on unresolved alignment conflict."),
        "reviewStatus":        (None, XSD.string,   "Review status: APPROVED | DISPUTED | PENDING."),
        "granularity":         (None, XSD.string,   "Process granularity level (group/module/unit)."),
    }

    for prop_name, (domain, range_, desc) in dt_props.items():
        prop = SDKB_ONT[prop_name]
        g.add((prop, RDF.type, OWL.DatatypeProperty))
        g.add((prop, RDFS.label, Literal(prop_name, lang="en")))
        g.add((prop, RDFS.comment, Literal(desc, lang="en")))
        g.add((prop, RDFS.range, range_))

    # ═══════════════════════════════════════════════════════════
    # CONSTRAINT TYPES (named individuals for weight semantics)
    # ═══════════════════════════════════════════════════════════
    for ctype in ("hardConstraint", "softConstraint"):
        ind = SDKB_ONT[ctype]
        g.add((ind, RDF.type, OWL.NamedIndividual))
        g.add((ind, RDF.type, SDKB_ONT.ConstraintType if ctype else OWL.Thing))
        g.add((ind, RDFS.label, Literal(ctype, lang="en")))

    # ConstraintType class
    ct = SDKB_ONT.ConstraintType
    g.add((ct, RDF.type, OWL.Class))
    g.add((ct, RDFS.label, Literal("ConstraintType", lang="en")))
    g.add((ct, RDFS.comment, Literal("Type of constraint: hard (prohibitive) or soft (advisory).", lang="en")))

    return g


def main():
    g = build_ontology()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT), format="turtle")
    print(f"✓ OWL ontology ({len(g)} triples) → {OUT}")


if __name__ == "__main__":
    main()
