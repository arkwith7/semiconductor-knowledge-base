"""Tests for OWL ontology structure."""

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL, RDFS

ROOT = Path(__file__).resolve().parent.parent
OWL_PATH = ROOT / "ontology" / "sdkb-core.ttl"

ONT = "https://w3id.org/sdkb/ont/"
GOV = "https://w3id.org/sdkb/gov/"


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
