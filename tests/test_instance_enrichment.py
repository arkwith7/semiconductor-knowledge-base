"""Phase 1 v1.1 — Instance-level enrichment regression tests.

Verifies that:
  - sdkb_instance_enrichment.json is well-formed and reachable
  - convert_rdf.py applies refined rdf:type triples to the data graph
  - baseline JSON's legacy SemicONTO cross_refs are correct (no longer point at
    the non-existent semiconto:ExperimentStep or to None)

See docs/project/architecture_amendment_sdkb_centric.md.
"""

import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parent.parent
ENRICHMENT_JSON = ROOT / "mappings" / "sdkb_instance_enrichment.json"
DATA_TTL = ROOT / "ontology" / "sdkb-core-data.ttl"
BASELINE_JSON = ROOT / "data" / "semiconductor_v0_3.json"

ONT = "https://w3id.org/sdkb/ont/"
DATA = "https://w3id.org/sdkb/data/"


@pytest.fixture(scope="module")
def enrichment_config():
    if not ENRICHMENT_JSON.exists():
        pytest.skip("instance enrichment config not present")
    return json.loads(ENRICHMENT_JSON.read_text())


@pytest.fixture(scope="module")
def data_graph():
    if not DATA_TTL.exists():
        pytest.skip("sdkb-core-data.ttl not generated — run convert_rdf first")
    g = Graph()
    g.parse(str(DATA_TTL), format="turtle")
    return g


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE_JSON.read_text())


class TestEnrichmentConfig:
    def test_config_has_type_refinements(self, enrichment_config):
        assert "type_refinements" in enrichment_config
        assert isinstance(enrichment_config["type_refinements"], list)

    def test_refinement_entries_have_required_keys(self, enrichment_config):
        required = {"sdkb_id", "primary_type", "refined_to", "rationale"}
        for entry in enrichment_config["type_refinements"]:
            missing = required - entry.keys()
            assert not missing, f"refinement entry missing {missing}: {entry}"

    def test_refinement_uses_sdkb_prefix(self, enrichment_config):
        for entry in enrichment_config["type_refinements"]:
            assert entry["refined_to"].startswith("sdkb:"), (
                f"refined_to must use sdkb: CURIE, got {entry['refined_to']!r}"
            )


class TestInstanceTypeRefinements:
    """The data graph must carry the refined rdf:type from the enrichment config."""

    def test_polysilicon_typed_as_semiconductor(self, data_graph):
        polysi = URIRef(DATA + "material/polysilicon")
        assert (polysi, RDF.type, URIRef(ONT + "Semiconductor")) in data_graph, (
            "material:polysilicon should additionally rdf:type sdkb:Semiconductor"
        )

    def test_polysilicon_retains_primary_material_type(self, data_graph):
        polysi = URIRef(DATA + "material/polysilicon")
        assert (polysi, RDF.type, URIRef(ONT + "Material")) in data_graph, (
            "primary rdf:type sdkb:Material must be preserved alongside the refinement"
        )

    def test_all_refinements_present_in_graph(self, data_graph, enrichment_config):
        ONT_NS = ONT
        DATA_NS = DATA
        for entry in enrichment_config["type_refinements"]:
            iri_str = DATA_NS + entry["sdkb_id"].replace(":", "/")
            local = entry["refined_to"].split(":", 1)[1]
            refined = URIRef(ONT_NS + local)
            assert (URIRef(iri_str), RDF.type, refined) in data_graph, (
                f"{entry['sdkb_id']} missing rdf:type {entry['refined_to']}"
            )


class TestLegacyCrossRefCorrections:
    """Baseline JSON's provenance.cross_ref entries must be self-consistent."""

    SEMICONTO_OWN_LOCALS = {
        # mirror of data/reports/semiconto_analysis.json own classes
        "Acceptor", "CMTExperiment", "ChemicalEntity", "ChemicalSubstance",
        "Donor", "Dopant", "DopingRelation", "EQETExperiment",
        "ElectronBeamLithography", "Equipment", "Experiment",
        "ExperimentInfoObj", "ExperimentalMethod", "ExperimentalStep",
        "ExtrinsicSemiconductor", "FieldEffectMeasurement", "HMTExperiment",
        "HallEffectMeasurement", "InformationObject", "IntrinsicSemiconductor",
        "Material", "MaterialProperty", "Matter", "MolecularEntity",
        "N-TypeSemiconductor", "P-TypeSemiconductor", "PESExperiment",
        "PPCExperiment", "PhotoelectronSpectroscopy", "SEDFabrication",
        "Semiconductor", "SemiconductorExperiment", "SpectralResponseMeasurement",
        "StepInfoObj", "ThermalEvaporation",
    }

    def test_no_obsolete_experiment_step_label(self, baseline):
        """The non-existent label ExperimentStep must not appear anywhere."""
        for n in baseline["nodes"]:
            for c in (n.get("provenance") or {}).get("cross_ref", []) or []:
                if c.get("source") == "semiconto":
                    assert c.get("class") != "ExperimentStep", (
                        f"{n['id']}: still references non-existent ExperimentStep"
                    )

    def test_no_none_or_empty_class(self, baseline):
        for n in baseline["nodes"]:
            for c in (n.get("provenance") or {}).get("cross_ref", []) or []:
                if c.get("source") == "semiconto":
                    val = c.get("class")
                    assert val not in (None, "None", ""), (
                        f"{n['id']}: semiconto cross_ref has empty class"
                    )

    def test_referenced_classes_actually_exist_in_semiconto(self, baseline):
        for n in baseline["nodes"]:
            for c in (n.get("provenance") or {}).get("cross_ref", []) or []:
                if c.get("source") == "semiconto":
                    assert c["class"] in self.SEMICONTO_OWN_LOCALS, (
                        f"{n['id']}: cross_ref class {c['class']!r} not in SemicONTO v0.2"
                    )
