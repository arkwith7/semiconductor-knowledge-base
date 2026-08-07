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
import re
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
#
# **기준선은 HEAD 가 아니라 고정된 커밋이다.** 앞선 판은 워킹트리를 `HEAD:` 와 비교했고,
# 그래서 **CR-013 이 커밋되는 순간 스스로 무효가 됐다** — HEAD == 워킹트리가 되어 델타가
# 사라지고 아래 단정이 영구히 실패한다. 커밋 전 창에서만 통과하는 테스트는 게이트가 아니다.
#
# 고정 기준선으로 바꾸면 성질이 반대가 된다. 이 자산은 **CR 마다 한 번씩만 움직이므로**,
# "기준선 이후 일어난 변경 전부"를 아래 표에 적어 두면 그 표가 곧 **누적 변경 대장**이 된다.
# 새 CR 이 자산을 건드리면 이 테스트가 실패하고, 통과시키려면 **표에 델타를 적어야 한다** —
# 조용한 변경이 불가능하다는 원래 성질이 그대로 유지되면서 커밋 뒤에도 살아 있다.
BASELINE_COMMIT = "39855bb46c95897f401986caa18e1c423c8e63c6"  # CR-008·CR-009 판 (CR-013 직전)

# 기준선 이후 **선언된** 사전 값 변경. 새 CR 은 여기에 자기 델타를 더한다.
#   CR-013 — 단독 `hf` 제거 · `high k` 를 상위 부류로 재지정
DECLARED_REMOVED = {"patent-text": {("hf", "material:hf_acid"), ("high k", "material:hfO2")}}
DECLARED_ADDED = {"patent-text": {("high k", "material:dielectric")}}
DECLARED_NEW_RULES = {"R6-SURFACE-SUPPRESS"}

_DECLARE_HINT = (
    "\n→ 자산을 바꾼 CR 이 있다면 이 파일의 DECLARED_REMOVED/DECLARED_ADDED 에 델타를 "
    "적어라. 적지 않고 통과시키는 길은 없다(§1-6)."
)


def test_entries_changed_only_where_declared(asset):
    """`entries`·`blocked` 는 **고정 기준선 + 선언된 델타** 와 정확히 같다.

    비교 대상은 `BASELINE_COMMIT` 의 자산이다. 그 커밋이 없으면(얕은 클론) 건너뛴다.
    """
    prev = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASELINE_COMMIT}:mappings/concept_mapping.json"],
        capture_output=True, text=True)
    if prev.returncode != 0:
        pytest.skip(f"기준선 커밋 {BASELINE_COMMIT[:7]} 없음 (얕은 클론)")
    old = json.loads(prev.stdout)

    def pairs(doc, profile, key="entries"):
        return {(e["surface"], e["concept_id"]) for e in doc["profiles"][profile][key]}

    for profile in PROFILES:
        removed = pairs(old, profile) - pairs(asset, profile)
        added = pairs(asset, profile) - pairs(old, profile)
        expect_rm = DECLARED_REMOVED.get(profile, set())
        expect_add = DECLARED_ADDED.get(profile, set())
        assert removed == expect_rm, (
            f"{profile}: 선언되지 않은 제거 {removed - expect_rm} · "
            f"선언됐으나 일어나지 않은 제거 {expect_rm - removed}{_DECLARE_HINT}")
        assert added == expect_add, (
            f"{profile}: 선언되지 않은 추가 {added - expect_add} · "
            f"선언됐으나 일어나지 않은 추가 {expect_add - added}{_DECLARE_HINT}")
        # 뺀 것은 blocked 로 **옮겨져야** 한다 — 조용히 사라지면 안 된다.
        moved = pairs(asset, profile, "blocked") - pairs(old, profile, "blocked")
        assert moved == expect_rm, f"{profile}: blocked 이동 기록이 어긋난다 {moved}"

    # 규칙은 추가만 가능하다 — 기존 규칙 문구가 바뀌면 하류 해석이 달라진다.
    assert set(asset["rules"]) - set(old["rules"]) == DECLARED_NEW_RULES
    for k, v in old["rules"].items():
        assert asset["rules"][k] == v, f"{k}: 기존 규칙 문구가 바뀌었다"


def test_baseline_is_pinned_not_head():
    """**이 테스트가 커밋 뒤에도 살아 있는지**를 고정한다.

    기준선을 `HEAD:` 로 되돌리면 자산을 바꾼 CR 이 커밋되는 순간 위 테스트가 스스로
    무효가 된다(2026-08-08 에 실제로 그랬다 — CR-013 `4f3dbfb` 커밋 직후 영구 실패).
    회귀를 막는 자리는 여기뿐이다 — 위 테스트는 자기가 무효해진 것을 알 수 없다.
    """
    src = Path(__file__).read_text(encoding="utf-8")
    # 찾는 문자열을 쪼개서 만든다 — 통째로 쓰면 **이 단정문 자신이** 소스에 그 문자열을
    # 넣어 테스트가 늘 실패한다(처음에 그렇게 썼고 그래서 실패했다).
    forbidden = "HEAD" + ":mappings/concept_mapping.json"
    assert forbidden not in src, (
        "기준선이 HEAD 로 되돌아갔다 — 자산을 바꾼 CR 이 커밋되면 테스트가 자기무효화된다")
    assert re.fullmatch(r"[0-9a-f]{40}", BASELINE_COMMIT), (
        "기준선은 40자리 전체 SHA 로 고정한다 — 짧은 SHA·브랜치명·`^` 표기는 히스토리가 "
        "바뀌면 다른 것을 가리킨다")


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
