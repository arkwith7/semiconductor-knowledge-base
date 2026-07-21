"""전문가 상세 경력 A-Box 적재의 회귀 테스트 (2026-07-21).

curated_profiles_kr.json 의 상세 경력·큐레이션 정렬·사례가 그래프에 실체화됐음을 고정한다.

- 새 술어는 **전부 TBox 소유**여야 한다 (인라인 선언 0 · CLAUDE.md §1.2).
- 링크는 큐레이션 ontology_alignment ID(필드별 prefix remap + 정규화 폴백)로 생성한다.
- case_experience 는 ExpertCase 로 reify 되고, 개별 링크의 range 가 옳아야 한다.
- 값은 전부 비식별 변조/생성값이다 (docs/deidentification_protocol.md §1.5).

이 축은 하류 H1/H2/RQ3 검정에 관여하지 않는다(특허↔공정 엣지 불변). 이 테스트는
그래프 구조 계약을 지키고, 삭제·평탄화로의 퇴행을 막는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, SKOS

ROOT = Path(__file__).resolve().parent.parent
ONT = Namespace("https://w3id.org/sdkb/ont/")
ABOX = ROOT / "ontology" / "sdkb-abox-experts-problems.ttl"
CORE = ROOT / "ontology" / "sdkb-core.ttl"
COREDATA = ROOT / "ontology" / "sdkb-core-data.ttl"

# 신규 어휘 — TBox 가 소유해야 한다.
NEW_CLASSES = ("EquipmentModel", "ExpertCase")
NEW_OBJ = ("hasCaseExperience", "caseProcess", "caseFailureMode",
           "caseRootCause", "caseMitigation", "caseParameter")
NEW_DT = ("age", "education", "currentStatus", "formerEmployer", "yearsExperience",
          "retirementYear", "patentCount", "publicationCount", "hasCertification",
          "language", "toeicScore", "securityClearance", "consultingAvailability",
          "specialization", "profileSummary", "majorProject", "hasNCT",
          "preferredProjectType", "hourlyRateRange", "nationality",
          "workHistoryCountry", "lastActivity", "caseSource")


@pytest.fixture(scope="module")
def abox() -> Graph:
    if not ABOX.exists():
        pytest.skip("A-Box 미빌드 — make abox")
    return Graph().parse(ABOX, format="turtle")


@pytest.fixture(scope="module")
def tbox() -> Graph:
    if not CORE.exists():
        pytest.skip("TBox 미빌드 — make owl")
    return Graph().parse(CORE, format="turtle")


def test_new_vocabulary_is_tbox_owned(tbox: Graph) -> None:
    """새 클래스·술어는 전부 TBox 에 선언돼 있어야 한다 (A-Box 인라인 금지)."""
    for c in NEW_CLASSES:
        assert (ONT[c], RDF.type, OWL.Class) in tbox, f"클래스 미선언: {c}"
    for p in NEW_OBJ:
        assert (ONT[p], RDF.type, OWL.ObjectProperty) in tbox, f"object 미선언: {p}"
    for p in NEW_DT:
        assert (ONT[p], RDF.type, OWL.DatatypeProperty) in tbox, f"datatype 미선언: {p}"


def test_all_experts_carry_core_career_fields(abox: Graph) -> None:
    """110명 전원이 핵심 경력 필드를 갖는다 (적재 누락 방지)."""
    experts = list(abox.subjects(RDF.type, ONT.Expert))
    assert len(experts) == 110, f"Expert {len(experts)} != 110"
    for field in ("education", "patentCount", "age", "yearsExperience",
                  "currentStatus", "hourlyRateRange", "nationality"):
        n = sum(1 for e in experts if (e, ONT[field], None) in abox)
        assert n == 110, f"{field}: {n}/110 만 실렸다"


def test_equipment_models_and_cases_materialized(abox: Graph) -> None:
    """장비 모델·사례가 노드로 실체화됐다 (평탄화·삭제 방지)."""
    models = list(abox.subjects(RDF.type, ONT.EquipmentModel))
    cases = list(abox.subjects(RDF.type, ONT.ExpertCase))
    assert len(models) == 29, f"EquipmentModel {len(models)} != 29"
    assert len(cases) == 163, f"ExpertCase {len(cases)} != 163"
    # 모든 모델·사례는 이름이 있다 (skos:prefLabel — 라벨 규약).
    for n in models + cases:
        assert any(True for _ in abox.objects(n, SKOS.prefLabel)), f"라벨 없음: {n}"
    # 모든 사례는 출처를 밝힌다 (정직한 프로비넌스).
    for c in cases:
        assert (c, ONT.caseSource, None) in abox, f"caseSource 없음: {c}"


def test_case_links_have_valid_range(abox: Graph) -> None:
    """case reification 의 링크는 올바른 클래스를 가리킨다 (KG 노드 타입으로 검증)."""
    kg = Graph().parse(COREDATA, format="turtle")

    def has_type(node: URIRef, cls: URIRef) -> bool:
        return (node, RDF.type, cls) in kg

    checks = [
        (ONT.caseFailureMode, ONT.FailureMode),
        (ONT.caseRootCause, ONT.RootCause),
        (ONT.caseMitigation, ONT.Mitigation),
        (ONT.caseParameter, ONT.Parameter),
    ]
    for prop, cls in checks:
        for _, o in abox.subject_objects(prop):
            assert has_type(o, cls), f"{prop} → {o} 는 {cls} 인스턴스가 아니다"


def test_hourly_rate_is_present_but_flagged_synthetic() -> None:
    """시급대는 그래프에 실리되(사용자 결정), 비식별 프로토콜이 synthetic 으로 못박는다."""
    protocol = (ROOT / "docs" / "deidentification_protocol.md").read_text()
    assert "hourlyRateRange" in protocol, "프로토콜이 hourlyRateRange 를 다루지 않는다"
    assert "생성값" in protocol or "synthetic" in protocol.lower()
