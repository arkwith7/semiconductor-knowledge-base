"""Phase 0+1 — Regression tests for the SDKB ↔ SemicONTO alignment graph.

Verifies that mappings/sdkb_semiconto_alignment.ttl contains:
  - Class-level SKOS mappings for the 8 SDKB types with SemicONTO targets
  - 5 DatatypeProperty alignments (semi:hasExperimentName etc.) → W3C
    conventions used by SDKB (skos:prefLabel / skos:definition / dcterms:id).

See docs/project/architecture_amendment_sdkb_centric.md §6.
"""

import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SKOS, RDFS

ROOT = Path(__file__).resolve().parent.parent
TTL_PATH = ROOT / "mappings" / "sdkb_semiconto_alignment.ttl"
REPORT_PATH = ROOT / "data" / "reports" / "sdkb_semiconto_alignment_report.json"

SDKB_ONT = "https://w3id.org/sdkb/ont/"
SEMI = "http://w3id.org/SemicONTO/"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS_NS = "http://purl.org/dc/terms/"


@pytest.fixture(scope="module")
def align_graph():
    if not TTL_PATH.exists():
        pytest.skip("alignment TTL not generated yet — run scripts/build_semiconto_alignment.py")
    g = Graph()
    g.parse(str(TTL_PATH), format="turtle")
    return g


@pytest.fixture(scope="module")
def align_report():
    if not REPORT_PATH.exists():
        pytest.skip("alignment report not generated")
    return json.loads(REPORT_PATH.read_text())


class TestClassAlignments:
    EXPECTED = {
        # SDKB class -> (SemicONTO target, relation)
        "Equipment":     ("Equipment",            SKOS.exactMatch),
        "Material":      ("Material",             SKOS.exactMatch),
        "Process":       ("Experiment",           SKOS.broadMatch),
        "SubProcess":    ("ExperimentalStep",     SKOS.closeMatch),
        "Parameter":     ("MaterialProperty",     SKOS.closeMatch),
        "Metrology":     ("ExperimentalMethod",   SKOS.broadMatch),
    }

    def test_each_class_mapping_present(self, align_graph):
        for sdkb_local, (semi_local, pred) in self.EXPECTED.items():
            sdkb_uri = URIRef(SDKB_ONT + sdkb_local)
            semi_uri = URIRef(SEMI + semi_local)
            assert (sdkb_uri, pred, semi_uri) in align_graph, (
                f"missing {sdkb_local} {pred} semi:{semi_local}"
            )


class TestDatatypePropertyAlignment:
    """5 SemicONTO datatype properties mapped to SDKB's W3C-standard convention."""

    DTPROPS = {
        "hasExperimentName":             (SKOS_NS + "prefLabel",        SKOS.closeMatch),
        "hasExperimentAim":              (SKOS_NS + "definition",       SKOS.closeMatch),
        "hasExperimentalStepAim":        (SKOS_NS + "definition",       SKOS.closeMatch),
        "hasExperimentalStepDescription":(SKOS_NS + "definition",       SKOS.closeMatch),
        "hasExperimentalStepID":         (DCTERMS_NS + "identifier",    SKOS.closeMatch),
    }

    def test_dtprop_mapping_triples_present(self, align_graph):
        for semi_local, (sdkb_side_iri, pred) in self.DTPROPS.items():
            sdkb_side = URIRef(sdkb_side_iri)
            semi_iri = URIRef(SEMI + semi_local)
            assert (sdkb_side, pred, semi_iri) in align_graph, (
                f"missing <{sdkb_side_iri}> {pred} <semi:{semi_local}>"
            )

    def test_dtprop_rationale_recorded(self, align_graph):
        """Each SemicONTO datatype prop must carry an rdfs:comment with rationale."""
        for semi_local in self.DTPROPS:
            semi_iri = URIRef(SEMI + semi_local)
            comments = list(align_graph.objects(semi_iri, RDFS.comment))
            assert comments, f"missing rdfs:comment on semi:{semi_local}"

    def test_dtprop_in_report(self, align_report):
        assert "datatype_property_alignment" in align_report
        for semi_local in self.DTPROPS:
            assert semi_local in align_report["datatype_property_alignment"], (
                f"semi:{semi_local} missing from report"
            )


class TestLegacyCorrectionsCleared:
    def test_zero_pending_legacy_corrections(self, align_report):
        assert align_report["legacy_corrections"]["count"] == 0, (
            f"baseline JSON still has legacy cross_ref errors: "
            f"{align_report['legacy_corrections']['details']}"
        )
