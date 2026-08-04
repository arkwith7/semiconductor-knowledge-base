"""CR-009 — 개념 단위 메타(df·계층)가 지켜야 할 계약.

이 자산이 깨질 수 있는 방식은 셋이고, 셋 다 하류에서 **조용히 잘못된 가중**이 된다.

1. **개념이 빠진다.** df=0 인 개념의 키가 없으면 하류는 "없음"과 "0"을 구별할 수 없고,
   없음을 최대 특이도(idf 무한대)로 오해한다.
2. **기존 사전이 움직인다.** CR-009 는 **추가만** 한다 — `entries` 의 값이 하나라도
   바뀌면 CR-007 이 발행한 사전과 하류가 vendor 한 사전이 어긋난다.
3. **결정성이 깨진다.** 두 번 돌려 sha256 이 다르면 성공기준 ②(릴리스 간 비교)가
   원리적으로 무의미해진다.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_concept_mapping import (  # noqa: E402
    OUT_PATH,
    PROFILES,
    concept_df,
    concept_hierarchy,
    norm,
)

DF_REPORT = ROOT / "data" / "reports" / "concept_df_report.json"


@pytest.fixture(scope="module")
def asset() -> dict:
    if not OUT_PATH.exists():
        pytest.skip("concept_mapping.json 없음")
    return json.loads(OUT_PATH.read_text(encoding="utf-8"))


# ── 단위: df 계산 ───────────────────────────────────────────────────
def test_df_counts_documents_not_occurrences():
    """한 문서에 같은 개념의 표면형이 여러 번 나와도 1 이다."""
    entries = [{"surface": "etch", "concept_id": "process:etch"},
               {"surface": "etching", "concept_id": "process:etch"}]
    docs = [norm("etch etch etching"), norm("nothing here"), norm("ETCHING")]
    assert concept_df(entries, docs) == {"process:etch": 2}


def test_df_includes_zero_concepts():
    """어느 문서에도 없는 개념도 키를 갖는다 — 없음과 0 은 다르다."""
    entries = [{"surface": "unobtainium", "concept_id": "material:unobtainium"}]
    assert concept_df(entries, [norm("silicon dioxide")]) == {"material:unobtainium": 0}


def test_df_ignores_empty_surface_and_empty_docs():
    entries = [{"surface": "  ", "concept_id": "x:blank"},
               {"surface": "cmp", "concept_id": "process:cmp"}]
    assert concept_df(entries, ["", norm("CMP slurry")]) == {"process:cmp": 1}


# ── 단위: 계층 ──────────────────────────────────────────────────────
def test_hierarchy_depth_and_superordinate():
    kg = {"nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
          "edges": [{"src": "b", "predicate": "BROADER", "dst": "a"},
                    {"src": "c", "predicate": "BROADER", "dst": "b"}]}
    depth, sup = concept_hierarchy(kg)
    assert depth == {"a": 0, "b": 1, "c": 2}
    assert sup == {"a": True, "b": True, "c": False}


def test_hierarchy_rejects_cycles():
    """사이클을 조용히 자르면 깊이가 입력 순서에 의존하게 된다."""
    kg = {"nodes": [{"id": "a"}, {"id": "b"}],
          "edges": [{"src": "a", "predicate": "BROADER", "dst": "b"},
                    {"src": "b", "predicate": "BROADER", "dst": "a"}]}
    with pytest.raises(ValueError):
        concept_hierarchy(kg)


def test_hierarchy_ignores_non_broader_edges():
    kg = {"nodes": [{"id": "a"}, {"id": "b"}],
          "edges": [{"src": "b", "predicate": "USES", "dst": "a"}]}
    depth, sup = concept_hierarchy(kg)
    assert depth == {"a": 0, "b": 0}
    assert sup == {"a": False, "b": False}


# ── 통합: 자산 스키마 ───────────────────────────────────────────────
def test_schema_version_bumped(asset):
    assert asset["schema_version"] == "1.1"


@pytest.mark.parametrize("profile", PROFILES)
def test_every_concept_has_all_four_fields(profile, asset):
    """성공기준 ① — 두 프로파일 개념 전량이 넷을 갖는다."""
    prof = asset["profiles"][profile]
    meta = prof["concept_meta"]
    concepts_in_entries = {e["concept_id"] for e in prof["entries"]}
    assert set(meta["concepts"]) == concepts_in_entries, "개념 집합 불일치"
    assert isinstance(meta["df_denominator"], int) and meta["df_denominator"] > 0
    for cid, m in meta["concepts"].items():
        assert set(m) == {"df_abox", "depth", "is_superordinate"}, cid
        assert isinstance(m["df_abox"], int) and m["df_abox"] >= 0
        assert isinstance(m["depth"], int) and m["depth"] >= 0
        assert isinstance(m["is_superordinate"], bool)


@pytest.mark.parametrize("profile", PROFILES)
def test_df_never_exceeds_denominator(profile, asset):
    meta = asset["profiles"][profile]["concept_meta"]
    n = meta["df_denominator"]
    over = {c: m["df_abox"] for c, m in meta["concepts"].items() if m["df_abox"] > n}
    assert not over, f"분모를 넘는 df: {over}"


def test_profiles_publish_independent_df(asset):
    """프로파일별 발행 요구의 근거 — 두 사전의 df 가 실제로 다르다.

    같아지면 한 값으로 뭉쳐도 된다는 뜻이므로, 그때는 CR 을 다시 읽어야 한다.
    """
    a = asset["profiles"]["patent-text"]["concept_meta"]["concepts"]
    b = asset["profiles"]["expert-tag"]["concept_meta"]["concepts"]
    shared = set(a) & set(b)
    differing = [c for c in shared if a[c]["df_abox"] != b[c]["df_abox"]]
    assert differing, "두 프로파일의 df 가 전부 같다 — R4 차단이 작동하지 않는다"


def test_frozen_denominator_matches_abox(asset):
    """분모 4,513 = SIRP 1,000 + 인용 3,513. 바뀌면 df 전체가 다른 뜻이 된다.

    **CR-008 이 이 값을 바꿨다** — CR-009 최초 산출 시점의 분모는 4,034(인용 3,034)였고,
    B층 노드 479 가 추가되면서 4,513 이 됐다. 두 CR 은 파일이 겹치지 않지만 **데이터가
    겹친다**: df 의 분모는 A-Box 문서 수이고, CR-008 은 그 문서를 늘린다.
    그래서 CR-008 이 재수집될 때마다 이 자산도 다시 발행해야 한다.
    """
    for profile in PROFILES:
        assert asset["profiles"][profile]["concept_meta"]["df_denominator"] == 4513


# ── 통합: 추가만 했는가 ─────────────────────────────────────────────
def test_entries_unchanged_by_meta_addition(asset):
    """CR-009 는 추가만 한다 — `entries`·`blocked` 는 CR-007 판과 같아야 한다.

    git 에 남은 직전 판과 비교한다. 비교 대상이 없으면(신규 클론) 건너뛴다.
    """
    prev = subprocess.run(
        ["git", "-C", str(ROOT), "show", "HEAD:mappings/concept_mapping.json"],
        capture_output=True, text=True)
    if prev.returncode != 0:
        pytest.skip("직전 판 없음")
    old = json.loads(prev.stdout)
    for profile in PROFILES:
        assert asset["profiles"][profile]["entries"] == old["profiles"][profile]["entries"], \
            f"{profile}: entries 가 바뀌었다 — CR-009 는 값을 바꾸지 않는다"
        assert asset["profiles"][profile]["blocked"] == old["profiles"][profile]["blocked"], \
            f"{profile}: blocked 가 바뀌었다"
    assert asset["rules"] == old["rules"]


# ── 통합: 결정성 ────────────────────────────────────────────────────
def test_rebuild_is_byte_identical():
    """두 번 돌려 같은 바이트 — 성공기준 ① 의 뒷부분."""
    before = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_concept_mapping.py"),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, f"--check 실패: {r.stdout}{r.stderr}"
    assert hashlib.sha256(OUT_PATH.read_bytes()).hexdigest() == before


def test_no_timestamp_in_asset():
    """타임스탬프가 들어가면 재실행마다 파일이 달라져 성공기준 ②가 무의미해진다."""
    text = OUT_PATH.read_text(encoding="utf-8")
    for token in ("generated_at", "timestamp", "built_at"):
        assert token not in text


# ── 통합: 리포트 (설계 D3·D4) ───────────────────────────────────────
@pytest.mark.skipif(not DF_REPORT.exists(), reason="df 리포트 없음")
def test_report_states_depth_thinness_and_d20():
    r = json.loads(DF_REPORT.read_text(encoding="utf-8"))
    for profile in PROFILES:
        assert "depth_distribution" in r[profile]
        assert "d20_affected_note" in r[profile]
        assert len(r[profile]["top30"]) == 30
