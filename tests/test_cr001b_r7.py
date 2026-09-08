"""CR-001B — R7-DF-CEILING 과 한국어 표면형 수확기의 계약.

이 테스트가 지키는 것 셋.
  ① R7 은 **문턱 위에서만** 차단하고, 사유(rule_id)와 df 비율을 함께 남긴다.
  ② **기존 등재 표면형에는 소급하지 않는다** — 유예 목록이 그것을 강제한다.
     소급하면 자원 델타에 추가와 제거가 섞여 원인을 가를 수 없다(하류 DP4).
  ③ 수확 범위는 dev+train 뿐이다 — test·test_b 가 섞이면 봉인 분할이 자원으로 샌다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_concept_mapping import (  # noqa: E402
    ALIASES_PATH, DF_CEILING, KG_PATH, OUT_PATH, collect, norm, surface_df,
)
import harvest_ko_surfaces as H  # noqa: E402

CANDIDATES = ROOT / "data" / "reports" / "ko_surface_candidates.json"
PROPOSALS = ROOT / "data" / "reports" / "ko_concept_proposals.json"


@pytest.fixture(scope="module")
def kg() -> dict:
    return json.loads(KG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def aliases() -> dict:
    return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def asset() -> dict:
    if not OUT_PATH.exists():
        pytest.skip("concept_mapping.json 미생성 — scripts/build_concept_mapping.py")
    return json.loads(OUT_PATH.read_text(encoding="utf-8"))


# ── 단위: R7 경계 ──────────────────────────────────────────────────
def test_r7_blocks_above_ceiling_only(kg, aliases):
    """0.0599 는 통과하고 0.0601 은 차단된다 — 경계에서 판정이 뒤집힌다."""
    surface = "절연층"
    for ratio, expect_entry in ((DF_CEILING - 0.0001, True), (DF_CEILING + 0.0001, False)):
        entries, blocked = collect(kg, aliases, "patent-text", set(),
                                   df_ratio={surface: ratio})
        assert (surface in {e["surface"] for e in entries}) is expect_entry
        hit = [b for b in blocked if b["surface"] == surface]
        assert bool(hit) is (not expect_entry)
        if hit:
            assert hit[0]["rule_id"] == "R7-DF-CEILING"
            assert hit[0]["df_ratio"] == pytest.approx(ratio, abs=1e-4)


def test_r7_is_inert_without_df(kg, aliases):
    """df 를 주지 않으면 R7 은 돌지 않는다 — 조용히 다른 답을 내지 않는다."""
    entries, blocked = collect(kg, aliases, "patent-text", set())
    assert not [b for b in blocked if b["rule_id"] == "R7-DF-CEILING"]
    assert "절연층" in {e["surface"] for e in entries}


def test_r7_does_not_apply_to_expert_tag(kg, aliases):
    """R7 은 patent-text 한정이다 — 전문가매칭 프로파일의 현행 동작은 불변이다(T3)."""
    entries, blocked = collect(kg, aliases, "expert-tag", set(),
                               df_ratio={"식각": 0.9}, grandfathered=frozenset())
    assert not [b for b in blocked if b["rule_id"] == "R7-DF-CEILING"]
    assert "식각" in {e["surface"] for e in entries}


def test_grandfathered_surfaces_survive_r7(kg, aliases):
    """유예 목록의 기존 표면형은 문턱을 넘어도 남는다 — 소급 금지의 집행."""
    grand = {norm(s) for s in aliases["_r7_grandfathered"]["surfaces"]}
    assert "증착" in grand and "식각" in grand
    ratio = {s: 0.99 for s in grand}
    entries, blocked = collect(kg, aliases, "patent-text", set(),
                               df_ratio=ratio, grandfathered=frozenset(grand))
    kept = {e["surface"] for e in entries}
    assert grand <= kept
    assert not [b for b in blocked if b["rule_id"] == "R7-DF-CEILING"]


def test_grandfather_list_matches_measured_ratios(asset, aliases):
    """유예 목록은 감사 기록이다 — 발행된 표면형 df 와 어긋나면 실패시킨다."""
    meta = asset["profiles"]["patent-text"]["surface_meta"]
    denom = meta["df_denominator"]
    for surface, recorded in aliases["_r7_grandfathered"]["surfaces"].items():
        counted = meta["surfaces"].get(norm(surface))
        assert counted is not None, f"유예 목록의 {surface} 가 발행 표면형에 없다"
        assert round(counted / denom, 4) == pytest.approx(recorded, abs=1e-4)


# ── 단위: 표면형 df ────────────────────────────────────────────────
def test_surface_df_counts_documents_not_occurrences():
    docs = ["절연층 위에 절연층을 형성한다", "", "게이트 전극"]
    assert surface_df(["절연층", "게이트", "없는말"], docs) == {
        "절연층": 1, "게이트": 1, "없는말": 0}


def test_surface_df_handles_empty_input():
    assert surface_df([], ["아무 문서"]) == {}
    assert surface_df(["절연층"], []) == {"절연층": 0}


# ── 단위: 수확기 명사구 필터 ────────────────────────────────────────
@pytest.mark.parametrize("surface,keep", [
    ("절연층", True), ("반도체층", True), ("회로", True), ("온도", True),
    ("재료를", False), ("형성된", False), ("기판상에", False), ("포함하는", False),
    ("청구항", False), ("발명", False),
])
def test_noun_like_filter(surface, keep):
    assert H.is_noun_like(surface) is keep


def test_josa_filter_spares_two_char_nouns():
    """2자 명사의 끝 글자는 조사가 아니다 — 회로·온도·밀도가 죽지 않는다.

    `효과`·`구성` 처럼 법리 서술에서 오는 낱말은 이 규칙이 아니라 _LEGAL_STOP 이 거른다.
    """
    for s in ("회로", "온도", "밀도", "속도"):
        assert H.is_noun_like(s)


# ── 계약: 누출 경계 ────────────────────────────────────────────────
def test_harvest_scope_excludes_sealed_splits():
    scope = H.load_scope()
    assert set(scope["counts"]) == {"dev", "train"}
    assert scope["excluded_splits"] == ["test", "test_b"]
    assert len(scope["doc_ids"]) == sum(scope["counts"].values())


def test_reports_carry_no_source_prose():
    """제안 파일에 원문 문장을 담지 않는다 — 표면형은 6자 이하 한글 덩어리뿐이다."""
    if not CANDIDATES.exists():
        pytest.skip("리포트 미생성 — scripts/harvest_ko_surfaces.py")
    rep = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    for row in rep["candidates"]:
        assert len(row["surface"]) <= 6
        assert set(row["channels"]) <= {"claim", "table"}


def test_basic_terms_all_judged():
    """성공기준 ②′ — 기본 낱말 19 에 미판정이 없다."""
    if not CANDIDATES.exists():
        pytest.skip("리포트 미생성")
    bt = json.loads(CANDIDATES.read_text(encoding="utf-8"))["basic_terms"]
    assert len(bt["terms"]) == 19
    assert sum(bt["counts"].values()) == 19
    assert {r["disposition"] for r in bt["terms"]} <= {"entry", "blocked", "proposal"}


def test_proposals_do_not_register_new_iris():
    """출력 (2)는 제안일 뿐이다 — 신규 개념 IRI 는 이 CR 에 포함되지 않는다(㉢).

    2026-09-08(PLAN-005 5-B): `len(kg_ids) == 274` 상수를 뺐다. ㉢ 보류의 **구조요소 15개**
    (`basic_terms`)는 5-B 가 `StructuralElement` 노드로 등록했다 — 그것이 이 테스트가 지키던
    "이 CR 은 등록하지 않는다" 와 모순되지 않는 이유는, 등록 주체가 CR-001B 가 아니라 5-B 이고
    제안 목록(`proposals` 294행)은 여전히 IRI 를 갖지 않기 때문이다. 아래 단정이 그 둘을 가른다.
    """
    if not PROPOSALS.exists():
        pytest.skip("리포트 미생성")
    prop = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))
    assert prop["decision"].startswith("㉢")
    for row in prop["proposals"]:
        assert "concept_id" not in row
    # basic_terms 15 는 전부 StructuralElement 노드의 ko synonym 으로 해소됐다(5-B).
    se_ids = {n["id"] for n in kg["nodes"] if n["type"] == "StructuralElement"}
    se_terms = {s["term"] for s in kg["synonyms"] if s["node_id"] in se_ids and s.get("lang") == "ko"}
    held = {r["surface"] for r in prop["basic_terms"]}
    assert held <= se_terms, f"5-B 가 등록하지 않은 보류 표면형: {sorted(held - se_terms)}"
    # 제안 294 표면형 중 basic_terms 와 겹치는 넷(배선·비아·웨이퍼·트렌치)을 뺀 나머지는 KG 의 어떤
    # 노드 이름·synonym 도 아니다 — 5-B 가 등록한 것은 basic_terms 만이다.
    names = {n["canonical_name"].lower() for n in kg["nodes"]} | {s["term"] for s in kg["synonyms"]}
    leaked = [r["surface"] for r in prop["proposals"] if r["surface"] in names and r["surface"] not in held]
    assert leaked == [], f"제안 목록의 표면형이 KG 에 등록돼 있다(5-B 범위 밖): {leaked}"
