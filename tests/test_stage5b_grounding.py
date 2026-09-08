"""PLAN-005 단계 5-B — 개념 접지율 개선의 계약 고정.

5-A 가 남긴 눈금(미매핑률)을 두 레버로 움직였다 — L1 `EquipmentClass` 를 semi 의 pa:TechnicalConcept
슬롯에 걸고, L2 등재 보류된 구조요소 15개를 `StructuralElement` 노드로 등록해 재접지했다.

여기서 고정하는 것은 넷이다.
1. **원천** — KG 에 StructuralElement 15 · 한글 synonym · patent-text 전용 프로파일 · provenance.
2. **생성기 ↔ T-Box 계약** — 링커가 방출하는 축(`CONCEPT_TYPES`)과 `ont:featureConcept` range 합집합,
   그리고 semi 가 pa:TechnicalConcept 에 건 인스턴스 보유 클래스가 서로 어긋나지 않는다.
   이 계약이 없어서 5-B 착수 시점에 *"노드를 등록해도 링커가 버려 25분 재빌드가 0 효과"* 인 구멍이
   있었다(CONCEPT_TYPES 에 StructuralElement 가 없었다).
3. **산출물** — 리포트에 equipment_class 미바인딩 0 · 사전에서 7개는 R7 차단 · 8개는 entries · shape 타깃.
4. **동결 목표** — 1단계에서 결과를 보기 전에 동결한 수치. 실패하면 목표를 고치지 않고 실패로 보고한다.

산출물이 없으면 skip 하고, 있으면 계약을 검사한다(선례: tests/test_abox_priorart.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import add_structural_elements as SE  # noqa: E402
from build_abox_claim_features import CONCEPT_TYPES  # noqa: E402

PA = "https://w3id.org/sdkb/pa/"
ONT = "https://w3id.org/sdkb/ont/"
ONT_DIR = ROOT / "ontology"
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
SEMI = ONT_DIR / "sdkb-priorart-semi.ttl"
CORE_DATA = ONT_DIR / "sdkb-core-data.ttl"
PATENT_TBOX = ONT_DIR / "sdkb-patent.ttl"
SHAPES = ROOT / "validation" / "shapes.ttl"
MAPPING = ROOT / "mappings" / "concept_mapping.json"
PRIORART_REPORT = ROOT / "data" / "reports" / "abox_priorart_report.json"
RELEASE_META = ROOT / "mappings" / "claim_feature_release_meta.json"

# 1단계 실측(R7 분모 4,513 · 문턱 0.06)에서 차단이 예상된 7개 — 실측이 다르면 CHANGELOG 에 적고 고친다.
EXPECTED_BLOCKED_KO = {"기판", "전극", "게이트", "적층", "소스", "드레인", "채널"}
KO_SURFACES = {ko for _, _, ko, _ in SE.ELEMENTS}

# 1단계 승인(2026-09-07)으로 동결한 목표. 기준선: rej 독립항 미매핑 0.2818 · feature 접지 0.331 ·
# g1 0.6212 · g2 0.6265.
TARGET_REJ_UNMAPPED_MAX = 0.25
TARGET_FEATURE_GROUNDED_MIN = 0.37
TARGET_G1_UNMAPPED_MAX = 0.6212 - 0.03
TARGET_G2_UNMAPPED_MAX = 0.6265 - 0.03


def _skip_unless(*paths: Path, hint: str):
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        pytest.skip(f"{missing} 미생성 — {hint}")


# ── 1. 원천 ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def kg() -> dict:
    return json.loads(KG_PATH.read_text(encoding="utf-8"))


def test_kg_has_fifteen_structural_elements_with_ko_synonyms(kg):
    nodes = [n for n in kg["nodes"] if n["type"] == SE.TYPE]
    assert {n["id"] for n in nodes} == SE.NEW_IDS and len(nodes) == 15
    for n in nodes:
        assert n["props"].get("lexicon_profile") == "patent-text", n["id"]
        prov = n["provenance"]
        assert prov["interpretation"] == "author-defined" and prov["license"] == "CDLA-Permissive-2.0"
        assert prov["validation_required"] is True
    ko_by_node = {}
    for s in kg["synonyms"]:
        if s["node_id"] in SE.NEW_IDS and s.get("lang") == "ko":
            ko_by_node.setdefault(s["node_id"], set()).add(s["term"])
    assert set(ko_by_node) == SE.NEW_IDS, "한글 synonym 이 없는 구조요소가 있다"
    assert set().union(*ko_by_node.values()) == KO_SURFACES


def test_injector_is_idempotent(tmp_path, monkeypatch):
    """두 번 돌려도 노드·synonym 이 늘지 않는다 — 원천 파일은 건드리지 않고 사본으로 검사한다."""
    copy = tmp_path / "kg.json"
    copy.write_text(KG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(SE, "KG_PATH", copy)
    assert SE.main() == 0
    once = json.loads(copy.read_text(encoding="utf-8"))
    assert SE.main() == 0
    twice = json.loads(copy.read_text(encoding="utf-8"))
    assert len(once["nodes"]) == len(twice["nodes"]) and len(once["synonyms"]) == len(twice["synonyms"])
    assert sum(n["type"] == SE.TYPE for n in twice["nodes"]) == 15


# ── 2. 생성기 ↔ T-Box 계약 ──────────────────────────────────────────
def _feature_concept_range(g: Graph) -> set[str]:
    prop = URIRef(ONT + "featureConcept")
    out: set[str] = set()
    for rng in g.objects(prop, RDFS.range):
        union = g.value(rng, OWL.unionOf)
        if union is None:
            out.add(str(rng).rsplit("/", 1)[-1])
            continue
        for c in Collection(g, union):
            out.add(str(c).rsplit("/", 1)[-1])
    return out


def _bound_classes(semi: Graph) -> set[URIRef]:
    out: set[URIRef] = set()
    frontier = [URIRef(PA + "TechnicalConcept")]
    while frontier:
        parent = frontier.pop()
        for c in semi.subjects(RDFS.subClassOf, parent):
            if c not in out:
                out.add(c)
                frontier.append(c)
    return out


def test_linker_axes_match_feature_concept_range_and_semi_binding():
    _skip_unless(SEMI, CORE_DATA, hint="make priorart convert")
    tbox = Graph().parse(PATENT_TBOX, format="turtle")
    rng = _feature_concept_range(tbox)
    assert rng, "featureConcept range 를 읽지 못했다"
    # (a) 링커가 방출하는 축은 전부 range 에 있다 — 없으면 A-Box 가 T-Box 를 거짓으로 만든다.
    assert CONCEPT_TYPES <= rng, f"range 밖 축: {CONCEPT_TYPES - rng}"
    # (b) semi 가 판정 어휘에 걸었고 core-data 에 인스턴스가 있고 range 에도 든 클래스는 링커가 방출해야 한다.
    semi = Graph().parse(SEMI, format="turtle")
    core = Graph().parse(CORE_DATA, format="turtle")
    bound_with_instances = {
        str(c).rsplit("/", 1)[-1] for c in _bound_classes(semi)
        if str(c).startswith(ONT) and any(True for _ in core.subjects(RDF.type, c))
    }
    silent = (bound_with_instances & rng) - CONCEPT_TYPES
    assert silent == set(), f"semi 가 걸었고 인스턴스도 있는데 링커가 버리는 축: {silent}"
    assert {"EquipmentClass", "StructuralElement"} <= bound_with_instances


# ── 3. 산출물 ────────────────────────────────────────────────────────
def test_shapes_target_structural_element():
    g = Graph().parse(SHAPES, format="turtle")
    se = URIRef(ONT + "StructuralElement")
    from rdflib import Namespace
    SH = Namespace("http://www.w3.org/ns/shacl#")
    for shape in ("Shape_CoreNode", "Shape_Provenance"):
        targets = set(g.objects(URIRef(ONT + shape), SH.targetClass))
        assert se in targets, shape


def test_priorart_report_binds_equipment_class_and_structural_element():
    _skip_unless(PRIORART_REPORT, hint="make abox-priorart")
    rep = json.loads(PRIORART_REPORT.read_text(encoding="utf-8"))
    assert "StructuralElement" in rep["technical_concept_classes"]
    assert "EquipmentClass" in rep["technical_concept_classes"]
    eq = [c for c in rep["concepts"]["unbound_list"] if c.startswith("equipment_class:")]
    assert eq == [], f"L1 뒤에도 미바인딩인 equipment_class: {eq}"


def test_mapping_blocks_seven_by_r7_and_admits_eight():
    _skip_unless(MAPPING, hint="make concept-mapping")
    pt = json.loads(MAPPING.read_text(encoding="utf-8"))["profiles"]["patent-text"]
    entries = {e["surface"] for e in pt["entries"] if e["concept_id"] in SE.NEW_IDS}
    blocked = {b["surface"]: b["rule_id"] for b in pt["blocked"] if b["concept_id"] in SE.NEW_IDS}
    assert set(blocked) & KO_SURFACES == EXPECTED_BLOCKED_KO, sorted(set(blocked) & KO_SURFACES)
    assert all(blocked[s] == "R7-DF-CEILING" for s in EXPECTED_BLOCKED_KO)
    assert entries & KO_SURFACES == KO_SURFACES - EXPECTED_BLOCKED_KO
    # 차단된 표면형은 entries 에 없다 — 둘 다에 있으면 사전이 스스로 모순이다.
    assert not (entries & EXPECTED_BLOCKED_KO)


def test_release_meta_records_linker_mode():
    """L0 사고의 재발 차단 — 어느 링커 모드·버전으로 만든 투영인지 메타가 말해야 한다."""
    _skip_unless(RELEASE_META, hint="make abox-claim-features")
    src = json.loads(RELEASE_META.read_text(encoding="utf-8"))["source"]
    assert src["linker"]["morph"] is True and src["linker"]["profile"] == "patent-text"
    assert src["linker"]["kiwipiepy"], "kiwipiepy 버전이 비어 있다"


# ── 4. 동결 목표 ─────────────────────────────────────────────────────
def test_frozen_targets_hold():
    _skip_unless(PRIORART_REPORT, RELEASE_META, hint="make abox-claim-features abox-priorart")
    rep = json.loads(PRIORART_REPORT.read_text(encoding="utf-8"))
    meta = json.loads(RELEASE_META.read_text(encoding="utf-8"))
    by = rep["profiles"]["by_side"]
    grounded = meta["counts"]["features_with_concept"] / meta["counts"]["rows_features"]
    assert meta["counts"]["rows_features"] == 1_306_191, "행 수가 움직였다 — 재접지가 아니라 재분해다"
    assert by["rej"]["unmapped_rate"] <= TARGET_REJ_UNMAPPED_MAX, by["rej"]
    assert grounded >= TARGET_FEATURE_GROUNDED_MIN, grounded
    assert by["g1"]["unmapped_rate"] <= TARGET_G1_UNMAPPED_MAX, by["g1"]
    assert by["g2"]["unmapped_rate"] <= TARGET_G2_UNMAPPED_MAX, by["g2"]
