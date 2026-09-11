"""PLAN-005 단계 7-A′ — 저-df 개념 등록 · R8 원소기호 차단 · 레버 게이트의 계약.

1. **원천** — KG 에 노드 19(StructuralElement 12 · Device 3 · Material 4 — Parameter 는 링커 축 밖이라 제외) · 한글 synonym ·
   patent-text 전용 프로파일 · provenance. 인젝터는 멱등이다.
2. **T-Box 불변** — 새 노드의 클래스는 전부 semi 가 이미 pa:TechnicalConcept 에 건 것이고 링커 축(`CONCEPT_TYPES`)
   안에 있다. 그렇지 않으면 5-B 가 겪은 "등록해도 0 효과"가 재발한다.
3. **R8** — patent-text 에서 ASCII ≤2 표면형은 blocked 다. 실물 8건 · 합성 입력(`w`) · 다른 프로파일 불변.
4. **동결 게이트** — 재측정 리포트가 7-A′ 모드이면 레버 판정이 자기 수치와 일치하고, 새 노드는 entries 이거나
   R7 로 blocked 여야 한다(그 밖의 사유로 사라지면 실패).

산출물이 없으면 skip 하고, 있으면 계약을 검사한다(선례: tests/test_stage5b_grounding.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import add_claim_concepts_7a as C7  # noqa: E402
import build_concept_mapping as BCM  # noqa: E402
from build_abox_claim_features import CONCEPT_TYPES  # noqa: E402

PA = "https://w3id.org/sdkb/pa/"
ONT = "https://w3id.org/sdkb/ont/"
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
SEMI = ROOT / "ontology" / "sdkb-priorart-semi.ttl"
MAPPING = ROOT / "mappings" / "concept_mapping.json"
REPORT = ROOT / "data" / "reports" / "priorart_stage7_remeasure.json"

TYPE_TO_CLASS = {"StructuralElement": "StructuralElement", "Device": "Device", "Material": "Material",
                 "Parameter": "Parameter"}


def _kg() -> dict:
    return json.loads(KG_PATH.read_text(encoding="utf-8"))


def _injected(kg: dict) -> bool:
    return C7.NEW_IDS <= {n["id"] for n in kg["nodes"]}


# ── 1. 원천 ─────────────────────────────────────────────────────────────
def test_node_table_is_well_formed():
    ids = [nid for nid, *_ in C7.NODES]
    assert len(ids) == 19 and len(set(ids)) == 19
    by_type = {}
    for _, typ, *_ in C7.NODES:
        by_type[typ] = by_type.get(typ, 0) + 1
    # Parameter 는 없다 — 링커 축·featureConcept range 밖이라 등록해도 접지 0 (사용자 결정 2026-09-10)
    assert by_type == {"StructuralElement": 12, "Device": 3, "Material": 4}
    assert not any(nid.startswith("parameter:") for nid in ids)
    surfaces = [ko for *_, kos, _p, _d in C7.NODES for ko in kos] + [t for _, t in C7.EXTRA_SYNONYMS]
    assert len(surfaces) == len(set(surfaces)), "표면형 중복"
    assert all(typ in CONCEPT_TYPES for _, typ, *_ in C7.NODES), "링커 축 밖의 타입 — 등록해도 접지 0"


def test_kg_has_injected_nodes_with_ko_synonyms():
    kg = _kg()
    if not _injected(kg):
        pytest.skip("7-A′ 미주입 — make claim-concepts-7a")
    nodes = {n["id"]: n for n in kg["nodes"]}
    for nid, typ, name, kos, props, _desc in C7.NODES:
        n = nodes[nid]
        assert n["type"] == typ and n["canonical_name"] == name
        assert n["props"]["lexicon_profile"] == "patent-text"
        assert n["provenance"]["source"] == "author" and n["provenance"]["validation_required"] is True
        terms = {s["term"] for s in kg["synonyms"] if s["node_id"] == nid and s.get("lang") == "ko"}
        assert set(kos) <= terms, (nid, kos, terms)
    for nid, ko in C7.EXTRA_SYNONYMS:
        assert any(s["node_id"] == nid and s["term"] == ko for s in kg["synonyms"]), (nid, ko)


def test_injector_is_idempotent(tmp_path, monkeypatch):
    src = _kg()
    kgp = tmp_path / "kg.json"
    kgp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(C7, "KG_PATH", kgp)
    assert C7.main() == 0
    once = kgp.read_text(encoding="utf-8")
    assert C7.main() == 0
    assert kgp.read_text(encoding="utf-8") == once
    kg = json.loads(once)
    assert sum(1 for n in kg["nodes"] if n["id"] in C7.NEW_IDS) == 19
    assert sum(1 for s in kg["synonyms"] if s.get("source") == C7._SOURCE) == \
        sum(len(kos) for *_, kos, _p, _d in C7.NODES) + len(C7.EXTRA_SYNONYMS)


def test_injector_refuses_surface_clash(tmp_path, monkeypatch):
    src = _kg()
    src["nodes"] = [n for n in src["nodes"] if n["id"] not in C7.NEW_IDS]
    src["synonyms"] = [s for s in src["synonyms"] if s["node_id"] not in C7.NEW_IDS and s.get("source") != C7._SOURCE]
    src["synonyms"].append({"node_id": "process:etch", "term": "플로팅 게이트", "lang": "ko", "term_type": "synonym"})
    kgp = tmp_path / "kg.json"
    kgp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(C7, "KG_PATH", kgp)
    with pytest.raises(SystemExit):
        C7.main()


# ── 2. T-Box 불변 · 바인딩 ────────────────────────────────────────────────
def test_new_node_classes_are_bound_to_technical_concept():
    g = Graph().parse(SEMI, format="turtle")
    bound = {str(s).rsplit("/", 1)[-1] for s in g.subjects(RDFS.subClassOf, URIRef(PA + "TechnicalConcept"))}
    for _, typ, *_ in C7.NODES:
        assert TYPE_TO_CLASS[typ] in bound, typ


# ── 3. R8 ────────────────────────────────────────────────────────────────
def test_r8_predicate():
    assert BCM.is_short_ascii("w") and BCM.is_short_ascii("co") and BCM.is_short_ascii("c4")
    assert not BCM.is_short_ascii("cu2") and not BCM.is_short_ascii("텅") and not BCM.is_short_ascii("tin")


def test_r8_blocks_synthetic_short_ascii_in_patent_text_only():
    kg = {"nodes": [{"id": "material:tungsten", "type": "Material", "canonical_name": "Tungsten"}],
          "synonyms": [{"node_id": "material:tungsten", "term": "W", "lang": "en", "term_type": "synonym"}]}
    ent, blk = BCM.collect(kg, {}, "patent-text", set())
    assert {b["surface"] for b in blk if b["rule_id"] == "R8-SHORT-ASCII"} == {"w"}
    assert "w" not in {e["surface"] for e in ent} and "tungsten" in {e["surface"] for e in ent}
    ent2, blk2 = BCM.collect(kg, {}, "expert-tag", set())
    assert "w" in {e["surface"] for e in ent2} and not blk2


def test_r8_blocks_the_eight_shipped_short_surfaces():
    if not MAPPING.exists():
        pytest.skip("concept_mapping.json 없음")
    m = json.loads(MAPPING.read_text(encoding="utf-8"))["profiles"]["patent-text"]
    r8 = {b["surface"] for b in m["blocked"] if b["rule_id"] == "R8-SHORT-ASCII"}
    assert {"w", "co", "al", "cu"} <= r8
    assert not any(e["surface"].isascii() and len(e["surface"]) <= 2 for e in m["entries"])
    assert "R8-SHORT-ASCII" in json.loads(MAPPING.read_text(encoding="utf-8"))["rules"]


def test_new_surfaces_are_entries_or_r7_blocked():
    """새 노드의 표면형이 사전에서 사라지는 사유는 R7(해상도 규칙)뿐이어야 한다."""
    kg = _kg()
    if not _injected(kg) or not MAPPING.exists():
        pytest.skip("7-A′ 미주입 또는 사전 없음")
    m = json.loads(MAPPING.read_text(encoding="utf-8"))["profiles"]["patent-text"]
    entries = {(e["surface"], e["concept_id"]) for e in m["entries"]}
    blocked = {(b["surface"], b["concept_id"]): b["rule_id"] for b in m["blocked"]}
    for nid, _typ, _name, kos, _p, _d in C7.NODES:
        for ko in kos:
            s = BCM.norm(ko)
            assert (s, nid) in entries or blocked.get((s, nid)) == "R7-DF-CEILING", (ko, nid, blocked.get((s, nid)))


# ── 4. 동결 게이트 ──────────────────────────────────────────────────────
@pytest.mark.skipif(not REPORT.exists(), reason="재측정 리포트 없음")
def test_lever_verdict_is_consistent_with_frozen_gate():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    if rep.get("mode") != "stage7a":
        pytest.skip("리포트가 7-A′ 모드가 아니다")
    f = rep["frozen"]["stage7a"]
    assert f["rej_unmapped_max"] == 0.20 and f["hit_drop_max"] == 0.02 and f["c_commit"] == "0a9344b"
    lv = rep["verdict"]["lever"]
    assert lv["pass"] == (lv["failed_conditions"] == [])
    assert lv["rej_unmapped"]["pass"] == (lv["rej_unmapped"]["rate"] <= f["rej_unmapped_max"])
    r = lv["reach_median_decrease"]
    assert r["pass"] == (r["bootstrap"]["ci"][1] < 0 and r["bootstrap"]["delta"] < 0)
    h = lv["hit_inf_drop"]
    assert h["pass"] == (h["drop"] <= f["hit_drop_max"])
    assert rep["verdict"]["V2"]["ii_tau"]["tau"] == 0.6708          # τ 불변
