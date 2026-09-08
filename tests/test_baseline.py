"""Tests for Week 1 — Baseline parsing (schema report, integrity checks)."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "data" / "semiconductor_v0_3.json"
SCHEMA_REPORT = ROOT / "data" / "schema_report.json"
NODES_PARQUET = ROOT / "data" / "nodes.parquet"
EDGES_PARQUET = ROOT / "data" / "edges.parquet"


@pytest.fixture(scope="module")
def baseline():
    with open(BASELINE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema_report():
    if not SCHEMA_REPORT.exists():
        pytest.skip("schema_report.json not generated yet — run sdkb-parse first")
    with open(SCHEMA_REPORT, "r", encoding="utf-8") as f:
        return json.load(f)


class TestBaselineStructure:
    """Verify the baseline JSON has the expected top-level keys."""

    def test_has_nodes(self, baseline):
        assert "nodes" in baseline
        assert len(baseline["nodes"]) >= 198

    def test_has_edges(self, baseline):
        assert "edges" in baseline
        assert len(baseline["edges"]) >= 264

    def test_has_synonyms(self, baseline):
        assert "synonyms" in baseline

    def test_has_provenance_sources(self, baseline):
        assert "provenance_sources" in baseline

    def test_version(self, baseline):
        assert baseline.get("version") == "0.3"


class TestNodeIntegrity:
    """Verify node structure and ID uniqueness."""

    def test_node_ids_unique(self, baseline):
        ids = [n["id"] for n in baseline["nodes"]]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"

    def test_nodes_have_required_fields(self, baseline):
        for n in baseline["nodes"]:
            assert "id" in n, f"Node missing 'id': {n}"
            assert "type" in n, f"Node missing 'type': {n.get('id')}"
            assert "canonical_name" in n, f"Node missing 'canonical_name': {n.get('id')}"

    def test_node_types(self, baseline):
        types = {n["type"] for n in baseline["nodes"]}
        expected = {
            "Process", "SubProcess", "EquipmentClass", "Equipment",
            "Vendor", "Organization", "Parameter", "Metrology",
            "Material", "TechnologyNode", "FailureMode", "RootCause",
            "Mitigation", "Skill",
            "Device",  # A2 device/product layer (plan §7.4-3, gap A2/B4)
            "StructuralElement",  # PLAN-005 5-B — 등재 보류된 구조요소 15개의 축
        }
        assert types == expected, f"Unexpected types: {types - expected}, Missing: {expected - types}"


class TestEdgeIntegrity:
    """Verify edge structure and referential integrity."""

    def test_edges_have_required_fields(self, baseline):
        for e in baseline["edges"]:
            assert "src" in e, f"Edge missing 'src'"
            assert "dst" in e, f"Edge missing 'dst'"
            assert "predicate" in e, f"Edge missing 'predicate'"

    def test_referential_integrity(self, baseline):
        node_ids = {n["id"] for n in baseline["nodes"]}
        for e in baseline["edges"]:
            assert e["src"] in node_ids, f"Dangling src: {e['src']}"
            assert e["dst"] in node_ids, f"Dangling dst: {e['dst']}"


class TestProvenanceFields:
    """Verify provenance metadata is present on nodes."""

    def test_nodes_have_provenance(self, baseline):
        missing = [n["id"] for n in baseline["nodes"] if "provenance" not in n]
        assert len(missing) == 0, f"Nodes missing provenance: {missing[:5]}..."

    def test_provenance_has_source(self, baseline):
        for n in baseline["nodes"]:
            prov = n.get("provenance", {})
            assert "source" in prov, f"Node {n['id']} provenance missing 'source'"

    def test_provenance_has_interpretation(self, baseline):
        valid = {"verbatim", "mapped", "author-defined"}
        for n in baseline["nodes"]:
            interp = n.get("provenance", {}).get("interpretation")
            assert interp in valid, f"Node {n['id']} invalid interpretation: {interp}"


class TestSchemaReport:
    """Verify generated schema report correctness."""

    def test_report_counts(self, schema_report):
        assert schema_report["counts"]["nodes"] >= 198
        assert schema_report["counts"]["edges"] >= 264

    def test_report_has_integrity_checks(self, schema_report):
        assert "integrity" in schema_report
        assert schema_report["integrity"]["id_unique"]["is_unique"] is True
        assert schema_report["integrity"]["referential"]["total_dangling"] == 0
