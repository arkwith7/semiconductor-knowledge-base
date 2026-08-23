"""CR-020 — 특허 A-Box 생성기의 프로파일 배선 (D-49).

이 테스트가 지키는 것 넷.
  ① `Bridge` 의 기본 프로파일은 `expert-tag` 다 — 뒤집으면 전문가·문제 A-Box 가
     조용히 움직인다(CR-020 비목표).
  ② 특허 계열 생성기 넷과 평가·진단 둘은 `patent-text` 를 **명시**한다.
     암묵 기본값에 기대는 것이 D-49 의 원인이었다.
  ③ A-Box 어휘가 발행 사전의 `blocked` 를 소비한다 — R4·R6·R7 이 사전 층에서만
     작동하면 두 층이 갈린다(D-48).
  ④ 그 결과 A-Box 어휘와 발행 사전이 **쌍 단위로 같다** — 이 CR 의 성립 조건이다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sdkb_nb as S  # noqa: E402

PATENT_CALLERS = (
    "build_abox_patents.py",
    "build_abox_claim_features.py",
    "build_abox_prior_art.py",
    "build_abox_b_layer_queries.py",
    "eval_prior_art_realgt.py",
    "eval_explanation_precision.py",
)


@pytest.fixture(scope="module")
def mapping() -> dict:
    return json.loads((ROOT / "mappings" / "concept_mapping.json").read_text())


def _pairs(bridge) -> set[tuple[str, str]]:
    return {(key, nid)
            for table in (bridge.lex, bridge.ali)
            for key, hits in table.items()
            for nid, _typ in hits}


def test_default_profile_is_expert_tag() -> None:
    assert S.make_bridge(ROOT).profile == "expert-tag"


@pytest.mark.parametrize("name", PATENT_CALLERS)
def test_patent_callers_declare_profile(name: str) -> None:
    src = (ROOT / "scripts" / name).read_text()
    assert 'PROFILE = "patent-text"' in src, f"{name}: 프로파일 선언이 없다"
    assert "make_bridge(ROOT)" not in src, f"{name}: 암묵 기본값 호출이 남아 있다"
    assert "profile=PROFILE" in src, f"{name}: 프로파일을 넘기지 않는다"


def test_blocked_is_consumed(mapping: dict) -> None:
    bridge = S.make_bridge(ROOT, profile="patent-text")
    blocked = {(b["surface"], b["concept_id"])
               for b in mapping["profiles"]["patent-text"]["blocked"]}
    assert blocked, "patent-text 의 blocked 가 비었다 — 이 계약은 그것을 전제한다"
    for surface, concept_id in blocked:
        key = bridge._b.norm(surface)
        hits = bridge.lex.get(key) or bridge.ali.get(key) or []
        assert concept_id not in {nid for nid, _ in hits}, \
            f"{surface} → {concept_id} 가 A-Box 어휘에 남아 있다"


@pytest.mark.parametrize("profile", ["expert-tag", "patent-text"])
def test_lexicon_matches_published_mapping(profile: str, mapping: dict) -> None:
    """A-Box 어휘 ≡ 발행 사전 (쌍 단위). CR-020 §1.3 의 실측을 계약으로 굳힌다."""
    bridge = S.make_bridge(ROOT, profile=profile)
    published = {(bridge._b.norm(e["surface"]), e["concept_id"])
                 for e in mapping["profiles"][profile]["entries"]}
    assert _pairs(bridge) == published


def test_missing_mapping_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        S._blocked_pairs(tmp_path, "patent-text")


def test_unknown_profile_fails_loudly() -> None:
    with pytest.raises(SystemExit):
        S._blocked_pairs(ROOT, "no-such-profile")
