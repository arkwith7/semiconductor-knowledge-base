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

# ─── External alignment targets (SDKB-centric: not imported, referenced) ───
# SemicONTO terms used as skos:exactMatch back-links from SDKB enrichment
# classes. See docs/project/architecture_amendment_sdkb_centric.md.
SEMI = "http://w3id.org/SemicONTO/"
QUDT = "http://qudt.org/schema/qudt/"

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
    g.add((ont, RDFS.label, Literal(
        "SDKB v1.1 — Semiconductor Domain Knowledge Base Ontology", lang="en"
    )))
    g.add((ont, RDFS.comment, Literal(
        "Provenance-grounded curation ontology for semiconductor "
        "manufacturing, covering process, equipment, materials, FMEA, and "
        "regulatory governance layers. SDKB-centric architecture: external "
        "ontologies (SemicONTO, QUDT, etc.) are REFERENCED via SKOS mappings "
        "and class-level skos:exactMatch back-links, NOT imported. See "
        "docs/project/architecture_amendment_sdkb_centric.md.",
        lang="en"
    )))
    g.add((ont, OWL.versionInfo, Literal("1.1.0-dev")))
    g.add((ont, DCTERMS.modified, Literal("2026-05-12", datatype=XSD.date)))
    g.add((ont, DCTERMS.license, URIRef("https://spdx.org/licenses/CDLA-Permissive-2.0.html")))
    g.add((ont, DCTERMS.creator, Literal("Park HyoungSik — SKKU MOT")))

    # ── External dependencies ──
    # Hard import: PROV-O (used directly for prov:Entity / prov:Activity /
    # prov:Agent typing in governance and equipment layers).
    g.add((ont, OWL.imports, URIRef("http://www.w3.org/ns/prov-o#")))

    # Referenced but NOT imported (SDKB-centric policy): SemicONTO terms appear
    # as skos:exactMatch targets from sdkb: classes/properties, and the
    # alignment graph at mappings/sdkb_semiconto_alignment.ttl carries SKOS
    # mappings for 198 instances. QUDT URIs are similarly used as
    # skos:exactMatch / skos:closeMatch targets from the Quantity layer.
    g.add((ont, DCTERMS.references, URIRef("http://w3id.org/SemicONTO/0.2/")))
    g.add((ont, DCTERMS.references, URIRef("http://qudt.org/schema/qudt/")))

    # Companion documents (architecture decisions and alignment artifacts)
    g.add((ont, RDFS.seeAlso, URIRef(
        "https://github.com/arkwith7/semiconductor-knowledge-base/blob/main/"
        "docs/project/architecture_amendment_sdkb_centric.md"
    )))
    g.add((ont, RDFS.seeAlso, URIRef(
        "https://w3id.org/sdkb/alignment/semiconto"
    )))

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
        # Device 는 core-data 에 31개 인스턴스가 있는데 클래스 선언이 없었다 —
        # 선언되지 않은 클래스는 추론기·SHACL 이 검증할 수 없다 (CLAUDE.md §1.2).
        "Device":         "A device/product architecture (e.g. DRAM, BGA, CMOS image sensor).",
        # Expert·Problem 은 sdkb-abox-experts-problems.ttl 이 **A-Box 안에서 인라인
        # 선언**하고 있었다 (Expert 110 · Problem 226 인스턴스). Device 와 같은 결함이다 —
        # TBox 를 읽는 소비자에게는 존재하지 않는 클래스이고, 추론기·SHACL 이 검증할 수 없다.
        "Expert":         "A domain expert with a curated competency profile (인력 축).",
        "Problem":        "A technical problem posed by a materials/parts/equipment SME (소부장 실문제).",
    }

    for cls_name, desc in core_classes.items():
        cls = SDKB_ONT[cls_name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls_name, lang="en")))
        g.add((cls, RDFS.comment, Literal(desc, lang="en")))

    # SubProcess rdfs:subClassOf Process (hierarchy)
    g.add((SDKB_ONT.SubProcess, RDFS.subClassOf, SDKB_ONT.Process))

    # ═══════════════════════════════════════════════════════════
    # CLASSES — Enrichment Layer (SemicONTO-derived, Phase 1 v1.1)
    #
    # New SDKB classes absorbing SemicONTO v0.2 HIGH-priority concepts
    # (per docs/project/architecture_amendment_sdkb_centric.md, Bucket A).
    # URIs remain in sdkb: namespace; skos:exactMatch back-links the
    # SemicONTO term so external consumers can navigate.
    # ═══════════════════════════════════════════════════════════
    # (class_name, parent_sdkb_class_or_None, semiconto_local, description)
    enrichment_classes: list[tuple[str, str | None, str, str]] = [
        ("Semiconductor",          "Material",       "Semiconductor",
         "A material with electrical conductivity between conductor and insulator."),
        ("IntrinsicSemiconductor", "Semiconductor",  "IntrinsicSemiconductor",
         "An undoped semiconductor whose carriers come from thermal excitation."),
        ("ExtrinsicSemiconductor", "Semiconductor",  "ExtrinsicSemiconductor",
         "A doped semiconductor whose carriers come from intentional dopants."),
        ("Dopant",                 "Material",       "Dopant",
         "An impurity introduced into a semiconductor to alter conductivity."),
        ("Acceptor",               "Dopant",         "Acceptor",
         "A dopant that accepts electrons, producing a p-type semiconductor."),
        ("Donor",                  "Dopant",         "Donor",
         "A dopant that donates electrons, producing an n-type semiconductor."),
    ]
    for cls_name, parent, semi_local, desc in enrichment_classes:
        cls = SDKB_ONT[cls_name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls_name, lang="en")))
        g.add((cls, RDFS.comment, Literal(desc, lang="en")))
        if parent:
            g.add((cls, RDFS.subClassOf, SDKB_ONT[parent]))
        # Back-link to SemicONTO term (alignment, not import)
        g.add((cls, SKOS.exactMatch, URIRef(SEMI + semi_local)))

    # Dopant union axiom mirrors SemicONTO: Dopant ≡ Acceptor ∪ Donor
    dopant_union_node = BNode()
    dopant_list_root = BNode()
    g.add((SDKB_ONT.Dopant, OWL.equivalentClass, dopant_union_node))
    g.add((dopant_union_node, RDF.type, OWL.Class))
    g.add((dopant_union_node, OWL.unionOf, dopant_list_root))
    Collection(g, dopant_list_root, [SDKB_ONT.Acceptor, SDKB_ONT.Donor])

    # ── MEDIUM-priority enrichment (Bucket A MEDIUM, Phase 1 v1.1) ──
    # Selective absorption: only classes with an existing SDKB parent are
    # pulled in. SemicONTO's Experiment/InformationObject hierarchies have no
    # SDKB counterpart and are skipped per
    # docs/project/architecture_amendment_sdkb_centric.md §7.
    enrichment_medium: list[tuple[str, str, str, str]] = [
        # SubProcess specializations
        ("ElectronBeamLithography",   "SubProcess", "ElectronBeamLithography",
         "Patterning sub-process using a focused electron beam (direct-write or mask-making)."),
        ("ThermalEvaporation",        "SubProcess", "ThermalEvaporation",
         "PVD sub-process where material is vaporized by resistive or e-beam heating in vacuum."),
        # Metrology specializations
        ("HallEffectMeasurement",     "Metrology",  "HallEffectMeasurement",
         "Metrology determining carrier type, density, and mobility via the Hall effect."),
        ("FieldEffectMeasurement",    "Metrology",  "FieldEffectMeasurement",
         "Metrology determining field-effect mobility from a transistor characteristic."),
        ("PhotoelectronSpectroscopy", "Metrology",  "PhotoelectronSpectroscopy",
         "Surface/composition metrology measuring photoelectron kinetic-energy spectra (XPS/UPS)."),
        # ExtrinsicSemiconductor specializations
        ("NTypeSemiconductor",        "ExtrinsicSemiconductor", "N-TypeSemiconductor",
         "An extrinsic semiconductor whose majority carriers are electrons (donor-doped)."),
        ("PTypeSemiconductor",        "ExtrinsicSemiconductor", "P-TypeSemiconductor",
         "An extrinsic semiconductor whose majority carriers are holes (acceptor-doped)."),
    ]
    for cls_name, parent, semi_local, desc in enrichment_medium:
        cls = SDKB_ONT[cls_name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(cls_name, lang="en")))
        g.add((cls, RDFS.comment, Literal(desc, lang="en")))
        g.add((cls, RDFS.subClassOf, SDKB_ONT[parent]))
        g.add((cls, SKOS.exactMatch, URIRef(SEMI + semi_local)))

    # Standalone: DopingRelation (no SDKB parent — top-level concept)
    g.add((SDKB_ONT.DopingRelation, RDF.type, OWL.Class))
    g.add((SDKB_ONT.DopingRelation, RDFS.label, Literal("DopingRelation", lang="en")))
    g.add((SDKB_ONT.DopingRelation, RDFS.comment, Literal(
        "A relation describing how a dopant modifies a host semiconductor "
        "(host material, dopant species, concentration, profile).", lang="en"
    )))
    g.add((SDKB_ONT.DopingRelation, SKOS.exactMatch,
           URIRef(SEMI + "DopingRelation")))

    # ── Quantity / MaterialProperty layer (Phase 1 v1.1, QUDT-aligned) ──
    # SDKB-centric: QUDT URIs are referenced via skos:exactMatch, not imported.
    # Abstract sdkb:Quantity unifies the existing sdkb:Parameter (process
    # input variable) and the new sdkb:MaterialProperty (measured material
    # attribute). Both share unit/value datatype properties.
    g.add((SDKB_ONT.Quantity, RDF.type, OWL.Class))
    g.add((SDKB_ONT.Quantity, RDFS.label, Literal("Quantity", lang="en")))
    g.add((SDKB_ONT.Quantity, RDFS.comment, Literal(
        "An abstract measurable quantity with a numeric value and unit. "
        "Generalizes process Parameter and MaterialProperty.", lang="en"
    )))
    g.add((SDKB_ONT.Quantity, SKOS.exactMatch, URIRef(QUDT + "Quantity")))

    g.add((SDKB_ONT.MaterialProperty, RDF.type, OWL.Class))
    g.add((SDKB_ONT.MaterialProperty, RDFS.label, Literal("MaterialProperty", lang="en")))
    g.add((SDKB_ONT.MaterialProperty, RDFS.comment, Literal(
        "A measurable property of a material instance (e.g. bandgap, "
        "resistivity, carrier mobility, refractive index).", lang="en"
    )))
    g.add((SDKB_ONT.MaterialProperty, RDFS.subClassOf, SDKB_ONT.Quantity))
    g.add((SDKB_ONT.MaterialProperty, SKOS.exactMatch,
           URIRef(SEMI + "MaterialProperty")))
    g.add((SDKB_ONT.MaterialProperty, SKOS.closeMatch,
           URIRef(QUDT + "Quantity")))

    # Existing Parameter becomes a subclass of Quantity (closeMatch QUDT).
    g.add((SDKB_ONT.Parameter, RDFS.subClassOf, SDKB_ONT.Quantity))
    g.add((SDKB_ONT.Parameter, SKOS.closeMatch, URIRef(QUDT + "Quantity")))

    # ObjectProperty: hasProperty (Material → MaterialProperty)
    g.add((SDKB_ONT.hasProperty, RDF.type, OWL.ObjectProperty))
    g.add((SDKB_ONT.hasProperty, RDFS.label, Literal("hasProperty", lang="en")))
    g.add((SDKB_ONT.hasProperty, RDFS.comment, Literal(
        "Links a material to one of its measurable properties.", lang="en"
    )))
    g.add((SDKB_ONT.hasProperty, RDFS.domain, SDKB_ONT.Material))
    g.add((SDKB_ONT.hasProperty, RDFS.range, SDKB_ONT.MaterialProperty))
    g.add((SDKB_ONT.hasProperty, SKOS.exactMatch, URIRef(SEMI + "hasProperty")))

    # ObjectProperty: hasMeasuredProperty (SubProcess → MaterialProperty)
    # SDKB-centric reframing of SemicONTO's (Experiment → MaterialProperty):
    # in SDKB the measurement happens AT a process step, not in a standalone
    # Experiment.
    g.add((SDKB_ONT.hasMeasuredProperty, RDF.type, OWL.ObjectProperty))
    g.add((SDKB_ONT.hasMeasuredProperty, RDFS.label, Literal("hasMeasuredProperty", lang="en")))
    g.add((SDKB_ONT.hasMeasuredProperty, RDFS.comment, Literal(
        "Links a sub-process (typically Metrology) to the material property "
        "it measures.", lang="en"
    )))
    g.add((SDKB_ONT.hasMeasuredProperty, RDFS.domain, SDKB_ONT.SubProcess))
    g.add((SDKB_ONT.hasMeasuredProperty, RDFS.range, SDKB_ONT.MaterialProperty))
    g.add((SDKB_ONT.hasMeasuredProperty, SKOS.exactMatch,
           URIRef(SEMI + "hasMeasuredProperty")))

    # DatatypeProperty: hasNumericValue (Quantity → xsd:decimal)
    g.add((SDKB_ONT.hasNumericValue, RDF.type, OWL.DatatypeProperty))
    g.add((SDKB_ONT.hasNumericValue, RDFS.label, Literal("hasNumericValue", lang="en")))
    g.add((SDKB_ONT.hasNumericValue, RDFS.comment, Literal(
        "Numeric value of a Quantity. Unit is given by hasUnitSymbol.", lang="en"
    )))
    g.add((SDKB_ONT.hasNumericValue, RDFS.domain, SDKB_ONT.Quantity))
    g.add((SDKB_ONT.hasNumericValue, RDFS.range, XSD.decimal))
    g.add((SDKB_ONT.hasNumericValue, SKOS.closeMatch,
           URIRef(QUDT + "numericValue")))

    # DatatypeProperty: hasUnitSymbol (Quantity → xsd:string)
    # String symbol form (e.g. "mTorr", "W", "°C") rather than URI to qudt:Unit
    # — keeps Phase 1 minimal. Later phases can upgrade to qudt:Unit IRI.
    g.add((SDKB_ONT.hasUnitSymbol, RDF.type, OWL.DatatypeProperty))
    g.add((SDKB_ONT.hasUnitSymbol, RDFS.label, Literal("hasUnitSymbol", lang="en")))
    g.add((SDKB_ONT.hasUnitSymbol, RDFS.comment, Literal(
        "String symbol of a Quantity's unit (e.g. 'mTorr', 'W', '°C'). "
        "Pragmatic Phase 1 form; future versions may bind to qudt:Unit IRIs.", lang="en"
    )))
    g.add((SDKB_ONT.hasUnitSymbol, RDFS.domain, SDKB_ONT.Quantity))
    g.add((SDKB_ONT.hasUnitSymbol, RDFS.range, XSD.string))

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
        # ── 인력·문제 축 (experts/problems A-Box 가 인라인 선언하던 술어들) ──────
        # range 는 A-Box 가 **실제로 가리키는** 클래스의 합집합이다. 주석이 말하는
        # 이상(理想)보다 좁게 선언하면 range 위반(=거짓 함의)이 생긴다. 예컨대
        # hasEquipmentExperience 는 Vendor 265 · Metrology 40 · EquipmentClass 14 ·
        # Equipment 1 을 가리킨다 — 브릿지가 느슨하게 라우팅한 결과이고, 그 느슨함은
        # 데이터의 사실이므로 TBox 가 그대로 반영한다.
        "hasSkill":               ("Expert",     ["Skill", "Mitigation"],
                                   "Skill possessed by an expert."),
        "hasProcessExpertise":    ("Expert",     ["Process", "TechnologyNode"],
                                   "Process (or technology-node) expertise of an expert."),
        "hasMaterialExpertise":   ("Expert",     "Material",
                                   "Material expertise of an expert."),
        "hasEquipmentExperience": ("Expert",     ["Equipment", "EquipmentClass", "Vendor", "Metrology"],
                                   "Hands-on equipment experience of an expert."),
        "involvesProcess":        ("Problem",    "Process",
                                   "Process implicated by an SME problem."),
        "involvesEquipment":      ("Problem",    ["Equipment", "EquipmentClass", "Metrology"],
                                   "Equipment implicated by an SME problem."),
        "mitigationProvidesSkill": ("Mitigation", "Skill",
                                    "Skill through which a mitigation is actionable."),
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

    # ── Enrichment ObjectProperties (SemicONTO-derived, Phase 1 v1.1) ──
    # Step-order semantics + dopant relations imported from SemicONTO with
    # skos:exactMatch back-link. URIs in sdkb: namespace.
    # Schema: name -> (domain, range, transitive?, semiconto_local, description)
    enrichment_obj_props: list[tuple[str, str, str, bool, str, str]] = [
        ("hasNextStep",  "SubProcess",            "SubProcess", False, "hasNextStep",
         "Links a sub-process step to its immediately succeeding step."),
        ("hasSubStep",   "SubProcess",            "SubProcess", True,  "hasSubStep",
         "Links a sub-process step to a nested sub-step (transitive)."),
        ("hasAcceptor",  "ExtrinsicSemiconductor", "Material",  False, "hasAcceptor",
         "An extrinsic semiconductor's acceptor dopant material."),
        ("hasDonor",     "ExtrinsicSemiconductor", "Material",  False, "hasDonor",
         "An extrinsic semiconductor's donor dopant material."),
        # MEDIUM-priority: specific-Equipment binding (distinct from
        # usesEquipmentClass which binds at the EquipmentClass abstraction).
        ("hasEquipment", "SubProcess",            "Equipment",  False, "hasEquipment",
         "Links a sub-process step to a specific equipment instance "
         "(complements usesEquipmentClass at the class level)."),
    ]
    for name, domain, range_, transitive, semi_local, desc in enrichment_obj_props:
        prop = SDKB_ONT[name]
        g.add((prop, RDF.type, OWL.ObjectProperty))
        if transitive:
            g.add((prop, RDF.type, OWL.TransitiveProperty))
        g.add((prop, RDFS.label, Literal(name, lang="en")))
        g.add((prop, RDFS.comment, Literal(desc, lang="en")))
        g.add((prop, RDFS.domain, SDKB_ONT[domain]))
        g.add((prop, RDFS.range, SDKB_ONT[range_]))
        g.add((prop, SKOS.exactMatch, URIRef(SEMI + semi_local)))

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
        # ── 인력·문제 축 (experts/problems A-Box). 이 여섯은 **어디에도 선언되지 않은 채**
        # 쓰이고 있었다 — 인라인 선언조차 없었다. ObjectProperty 만 인라인 선언돼 있어서
        # 눈에 띄지 않았다. 선언되지 않은 술어는 추론기·SHACL 이 검증할 수 없다 (§1.2).
        # domain 은 Problem ∪ Vendor 다. 같은 축(밸류체인 역할)을 두 주체가 쓴다:
        # 문제를 낸 소부장 기업(Problem)과, KSIA 명부에서 올라온 공급사(Vendor).
        "companyType":           (["Problem", "Vendor"], XSD.string,
                                  "Value-chain role of a company (materials | equipment | parts | fabless | foundry …). Used both for the SME that raised a problem and for a KSIA-listed vendor."),
        "problemCategory":       ("Problem", XSD.string,
                                  "Category of the SME problem (defect_reduction | contamination | yield_improvement …)."),
        "clientCountry":         ("Problem", XSD.string,
                                  "ISO country code of the SME that raised the problem."),
        "complianceSensitivity": ("Problem", XSD.string,
                                  "Disclosure sensitivity of the problem: public | restricted | confidential."),
        "complianceFlag":        ("Expert", XSD.boolean,
                                  "Whether the expert profile is subject to compliance review."),
        "region":                (["Expert", "Problem"], XSD.string,
                                  "Geographic region of an expert or of the SME that raised a problem."),
    }

    for prop_name, (domain, range_, desc) in dt_props.items():
        prop = SDKB_ONT[prop_name]
        g.add((prop, RDF.type, OWL.DatatypeProperty))
        g.add((prop, RDFS.label, Literal(prop_name, lang="en")))
        g.add((prop, RDFS.comment, Literal(desc, lang="en")))
        g.add((prop, RDFS.range, range_))
        if domain is not None:
            _emit_class_or_union(prop, RDFS.domain, domain)

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
