"""Tests for OWL ontology structure."""

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL, RDFS, SKOS, DCTERMS

ROOT = Path(__file__).resolve().parent.parent
OWL_PATH = ROOT / "ontology" / "sdkb-core.ttl"

ONT = "https://w3id.org/sdkb/ont/"
GOV = "https://w3id.org/sdkb/gov/"
SEMI = "http://w3id.org/SemicONTO/"
QUDT = "http://qudt.org/schema/qudt/"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"


@pytest.fixture(scope="module")
def owl_graph():
    if not OWL_PATH.exists():
        pytest.skip("sdkb-core.ttl not generated yet — run build_owl.py first")
    g = Graph()
    g.parse(str(OWL_PATH), format="turtle")
    return g


class TestOWLClasses:
    CORE_CLASSES = [
        "Process", "SubProcess", "EquipmentClass", "Equipment",
        "Vendor", "Organization", "Parameter", "Metrology",
        "Material", "TechnologyNode", "FailureMode", "RootCause",
        "Mitigation", "Skill",
    ]

    GOV_CLASSES = [
        "EARRule", "RegulatedItem", "NISTFunction", "NISTOutcome",
        "SCIPRule", "StandardReference", "EquipmentState",
    ]

    def test_14_core_classes_exist(self, owl_graph):
        for cls_name in self.CORE_CLASSES:
            cls = URIRef(ONT + cls_name)
            assert (cls, RDF.type, OWL.Class) in owl_graph, f"Missing core class: {cls_name}"

    def test_governance_classes_exist(self, owl_graph):
        for cls_name in self.GOV_CLASSES:
            cls = URIRef(GOV + cls_name)
            assert (cls, RDF.type, OWL.Class) in owl_graph, f"Missing gov class: {cls_name}"

    def test_subprocess_subclass_of_process(self, owl_graph):
        assert (URIRef(ONT + "SubProcess"), RDFS.subClassOf, URIRef(ONT + "Process")) in owl_graph


class TestOWLProperties:
    OBJECT_PROPS = [
        "hasSubprocess", "usesMaterial", "isDueTo", "mitigatedBy",
        "occursAtProcessStep", "isInstanceOf", "providedBy",
        "requiresSkill", "hasECCN", "controlledBy", "affectsMetric",
    ]

    DATATYPE_PROPS = [
        "confidence", "probability", "interpretationType",
        "validationRequired", "tppValue", "securityLevel",
    ]

    def test_object_properties_exist(self, owl_graph):
        for prop_name in self.OBJECT_PROPS:
            prop = URIRef(ONT + prop_name)
            assert (prop, RDF.type, OWL.ObjectProperty) in owl_graph, f"Missing object prop: {prop_name}"

    def test_datatype_properties_exist(self, owl_graph):
        for prop_name in self.DATATYPE_PROPS:
            prop = URIRef(ONT + prop_name)
            assert (prop, RDF.type, OWL.DatatypeProperty) in owl_graph, f"Missing datatype prop: {prop_name}"


class TestEnrichmentLayer:
    """Phase 1 v1.1 — SemicONTO-derived Bucket A HIGH classes & properties.

    See docs/architecture_amendment_sdkb_centric.md.
    """

    ENRICHMENT_CLASSES = {
        # local_name: (parent_local, semiconto_local)
        "Semiconductor":          ("Material",       "Semiconductor"),
        "IntrinsicSemiconductor": ("Semiconductor",  "IntrinsicSemiconductor"),
        "ExtrinsicSemiconductor": ("Semiconductor",  "ExtrinsicSemiconductor"),
        "Dopant":                 ("Material",       "Dopant"),
        "Acceptor":               ("Dopant",         "Acceptor"),
        "Donor":                  ("Dopant",         "Donor"),
    }

    ENRICHMENT_OBJ_PROPS = {
        # name: (domain_local, range_local, transitive, semiconto_local)
        "hasNextStep":  ("SubProcess",            "SubProcess", False, "hasNextStep"),
        "hasSubStep":   ("SubProcess",            "SubProcess", True,  "hasSubStep"),
        "hasAcceptor":  ("ExtrinsicSemiconductor", "Material",  False, "hasAcceptor"),
        "hasDonor":     ("ExtrinsicSemiconductor", "Material",  False, "hasDonor"),
    }

    def test_enrichment_classes_declared(self, owl_graph):
        for name in self.ENRICHMENT_CLASSES:
            cls = URIRef(ONT + name)
            assert (cls, RDF.type, OWL.Class) in owl_graph, (
                f"Missing enrichment class: {name}"
            )

    def test_enrichment_class_hierarchy(self, owl_graph):
        for name, (parent_local, _semi) in self.ENRICHMENT_CLASSES.items():
            cls = URIRef(ONT + name)
            parent = URIRef(ONT + parent_local)
            assert (cls, RDFS.subClassOf, parent) in owl_graph, (
                f"{name} should be rdfs:subClassOf {parent_local}"
            )

    def test_enrichment_class_skos_backlinks(self, owl_graph):
        for name, (_parent, semi_local) in self.ENRICHMENT_CLASSES.items():
            cls = URIRef(ONT + name)
            semi_target = URIRef(SEMI + semi_local)
            assert (cls, SKOS.exactMatch, semi_target) in owl_graph, (
                f"{name} should skos:exactMatch <{SEMI}{semi_local}>"
            )

    def test_dopant_equivalent_to_acceptor_or_donor(self, owl_graph):
        """Dopant ≡ Acceptor ∪ Donor (mirrors SemicONTO axiom)."""
        dopant = URIRef(ONT + "Dopant")
        equivs = list(owl_graph.objects(dopant, OWL.equivalentClass))
        assert equivs, "Dopant should have an owl:equivalentClass union axiom"
        union_node = equivs[0]
        union_lists = list(owl_graph.objects(union_node, OWL.unionOf))
        assert union_lists, "equivalentClass should reference an owl:unionOf list"
        # Walk the RDF list
        members: list[URIRef] = []
        node = union_lists[0]
        while node and str(node) != str(RDF.nil):
            first = next(iter(owl_graph.objects(node, RDF.first)), None)
            if isinstance(first, URIRef):
                members.append(first)
            node = next(iter(owl_graph.objects(node, RDF.rest)), None)
        assert set(members) == {URIRef(ONT + "Acceptor"), URIRef(ONT + "Donor")}

    def test_enrichment_obj_props_declared(self, owl_graph):
        for name in self.ENRICHMENT_OBJ_PROPS:
            prop = URIRef(ONT + name)
            assert (prop, RDF.type, OWL.ObjectProperty) in owl_graph, (
                f"Missing enrichment obj prop: {name}"
            )

    def test_enrichment_obj_prop_domain_range(self, owl_graph):
        for name, (dom, rng, _trans, _semi) in self.ENRICHMENT_OBJ_PROPS.items():
            prop = URIRef(ONT + name)
            assert (prop, RDFS.domain, URIRef(ONT + dom)) in owl_graph, (
                f"{name}: expected rdfs:domain {dom}"
            )
            assert (prop, RDFS.range, URIRef(ONT + rng)) in owl_graph, (
                f"{name}: expected rdfs:range {rng}"
            )

    def test_has_sub_step_is_transitive(self, owl_graph):
        prop = URIRef(ONT + "hasSubStep")
        assert (prop, RDF.type, OWL.TransitiveProperty) in owl_graph, (
            "hasSubStep must be owl:TransitiveProperty"
        )

    def test_enrichment_obj_prop_skos_backlinks(self, owl_graph):
        for name, (_d, _r, _t, semi_local) in self.ENRICHMENT_OBJ_PROPS.items():
            prop = URIRef(ONT + name)
            semi_target = URIRef(SEMI + semi_local)
            assert (prop, SKOS.exactMatch, semi_target) in owl_graph, (
                f"{name} should skos:exactMatch <{SEMI}{semi_local}>"
            )


class TestEnrichmentMedium:
    """Phase 1 v1.1 — Bucket A MEDIUM classes/properties.

    Selective absorption (see docs/architecture_amendment_sdkb_centric.md):
    SemicONTO Experiment/InformationObject hierarchies have no SDKB parent
    and are intentionally skipped.
    """

    MEDIUM_CLASSES = {
        # local_name: (parent_local_or_None, semiconto_local)
        "ElectronBeamLithography":   ("SubProcess",            "ElectronBeamLithography"),
        "ThermalEvaporation":        ("SubProcess",            "ThermalEvaporation"),
        "HallEffectMeasurement":     ("Metrology",             "HallEffectMeasurement"),
        "FieldEffectMeasurement":    ("Metrology",             "FieldEffectMeasurement"),
        "PhotoelectronSpectroscopy": ("Metrology",             "PhotoelectronSpectroscopy"),
        "NTypeSemiconductor":        ("ExtrinsicSemiconductor", "N-TypeSemiconductor"),
        "PTypeSemiconductor":        ("ExtrinsicSemiconductor", "P-TypeSemiconductor"),
        "DopingRelation":            (None,                    "DopingRelation"),
    }

    def test_medium_classes_declared(self, owl_graph):
        for name in self.MEDIUM_CLASSES:
            cls = URIRef(ONT + name)
            assert (cls, RDF.type, OWL.Class) in owl_graph, f"Missing: {name}"

    def test_medium_class_hierarchy(self, owl_graph):
        for name, (parent, _) in self.MEDIUM_CLASSES.items():
            if parent is None:
                continue
            cls = URIRef(ONT + name)
            assert (cls, RDFS.subClassOf, URIRef(ONT + parent)) in owl_graph, (
                f"{name} should be rdfs:subClassOf {parent}"
            )

    def test_medium_class_skos_backlinks(self, owl_graph):
        for name, (_p, semi_local) in self.MEDIUM_CLASSES.items():
            cls = URIRef(ONT + name)
            target = URIRef(SEMI + semi_local)
            assert (cls, SKOS.exactMatch, target) in owl_graph, (
                f"{name}: missing skos:exactMatch <{SEMI}{semi_local}>"
            )

    def test_has_equipment_property(self, owl_graph):
        prop = URIRef(ONT + "hasEquipment")
        assert (prop, RDF.type, OWL.ObjectProperty) in owl_graph
        assert (prop, RDFS.domain, URIRef(ONT + "SubProcess")) in owl_graph
        assert (prop, RDFS.range, URIRef(ONT + "Equipment")) in owl_graph
        assert (prop, SKOS.exactMatch, URIRef(SEMI + "hasEquipment")) in owl_graph


class TestQuantityLayer:
    """Phase 1 v1.1 — QUDT-aligned Quantity/MaterialProperty layer.

    SDKB does not import QUDT; qudt: URIs are referenced via skos:exactMatch
    or skos:closeMatch. See docs/architecture_amendment_sdkb_centric.md §7.
    """

    def test_quantity_class_exists(self, owl_graph):
        cls = URIRef(ONT + "Quantity")
        assert (cls, RDF.type, OWL.Class) in owl_graph
        assert (cls, SKOS.exactMatch, URIRef(QUDT + "Quantity")) in owl_graph

    def test_material_property_subclass_of_quantity(self, owl_graph):
        mp = URIRef(ONT + "MaterialProperty")
        assert (mp, RDF.type, OWL.Class) in owl_graph
        assert (mp, RDFS.subClassOf, URIRef(ONT + "Quantity")) in owl_graph
        assert (mp, SKOS.exactMatch, URIRef(SEMI + "MaterialProperty")) in owl_graph

    def test_parameter_now_subclass_of_quantity(self, owl_graph):
        param = URIRef(ONT + "Parameter")
        assert (param, RDFS.subClassOf, URIRef(ONT + "Quantity")) in owl_graph, (
            "Parameter should be reclassified as a subclass of Quantity"
        )
        assert (param, SKOS.closeMatch, URIRef(QUDT + "Quantity")) in owl_graph

    def test_has_property_object_prop(self, owl_graph):
        prop = URIRef(ONT + "hasProperty")
        assert (prop, RDF.type, OWL.ObjectProperty) in owl_graph
        assert (prop, RDFS.domain, URIRef(ONT + "Material")) in owl_graph
        assert (prop, RDFS.range, URIRef(ONT + "MaterialProperty")) in owl_graph
        assert (prop, SKOS.exactMatch, URIRef(SEMI + "hasProperty")) in owl_graph

    def test_has_measured_property_object_prop(self, owl_graph):
        prop = URIRef(ONT + "hasMeasuredProperty")
        assert (prop, RDF.type, OWL.ObjectProperty) in owl_graph
        assert (prop, RDFS.domain, URIRef(ONT + "SubProcess")) in owl_graph
        assert (prop, RDFS.range, URIRef(ONT + "MaterialProperty")) in owl_graph
        assert (prop, SKOS.exactMatch, URIRef(SEMI + "hasMeasuredProperty")) in owl_graph

    def test_has_numeric_value_datatype_prop(self, owl_graph):
        prop = URIRef(ONT + "hasNumericValue")
        assert (prop, RDF.type, OWL.DatatypeProperty) in owl_graph
        assert (prop, RDFS.domain, URIRef(ONT + "Quantity")) in owl_graph
        assert (prop, RDFS.range, URIRef(XSD_NS + "decimal")) in owl_graph
        assert (prop, SKOS.closeMatch, URIRef(QUDT + "numericValue")) in owl_graph

    def test_has_unit_symbol_datatype_prop(self, owl_graph):
        prop = URIRef(ONT + "hasUnitSymbol")
        assert (prop, RDF.type, OWL.DatatypeProperty) in owl_graph
        assert (prop, RDFS.domain, URIRef(ONT + "Quantity")) in owl_graph
        assert (prop, RDFS.range, URIRef(XSD_NS + "string")) in owl_graph


class TestOntologyDependencyMetadata:
    """SDKB-centric: external ontologies are referenced (not imported).

    The Ontology declaration must distinguish owl:imports (hard) from
    dcterms:references (soft, used only via skos:exactMatch / closeMatch).
    """

    ONT_IRI = URIRef("https://w3id.org/sdkb/ont")

    def test_prov_o_is_the_only_owl_import(self, owl_graph):
        imports = set(owl_graph.objects(self.ONT_IRI, OWL.imports))
        assert imports == {URIRef("http://www.w3.org/ns/prov-o#")}, (
            f"only PROV-O should be owl:imports; got {imports}"
        )

    def test_semiconto_is_referenced_not_imported(self, owl_graph):
        semi_iri = URIRef("http://w3id.org/SemicONTO/0.2/")
        refs = set(owl_graph.objects(self.ONT_IRI, DCTERMS.references))
        assert semi_iri in refs, (
            f"SemicONTO 0.2 must appear in dcterms:references; got {refs}"
        )
        assert (self.ONT_IRI, OWL.imports, semi_iri) not in owl_graph, (
            "SemicONTO must NOT be owl:imports (SDKB-centric policy)"
        )

    def test_qudt_is_referenced_not_imported(self, owl_graph):
        qudt_iri = URIRef("http://qudt.org/schema/qudt/")
        refs = set(owl_graph.objects(self.ONT_IRI, DCTERMS.references))
        assert qudt_iri in refs, (
            f"QUDT must appear in dcterms:references; got {refs}"
        )
        assert (self.ONT_IRI, OWL.imports, qudt_iri) not in owl_graph, (
            "QUDT must NOT be owl:imports (SDKB-centric policy)"
        )

    def test_version_info_advanced_for_enrichment(self, owl_graph):
        ver = next(iter(owl_graph.objects(self.ONT_IRI, OWL.versionInfo)), None)
        assert ver is not None
        assert str(ver).startswith("1.1"), (
            f"versionInfo should advance to 1.1.x for Phase 1 enrichment; got {ver!r}"
        )

    def test_modified_date_is_set(self, owl_graph):
        modified = list(owl_graph.objects(self.ONT_IRI, DCTERMS.modified))
        assert modified, "dcterms:modified must be set"

    def test_amendment_doc_is_seealso(self, owl_graph):
        sees = [str(o) for o in owl_graph.objects(self.ONT_IRI, RDFS.seeAlso)]
        assert any("architecture_amendment_sdkb_centric" in s for s in sees), (
            "rdfs:seeAlso should link to the SDKB-centric architecture amendment doc"
        )
