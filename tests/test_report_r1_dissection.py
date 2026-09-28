"""R1 해부 집계기의 계약을 고정한다 — PLAN-005 §20.15.

고정하는 것.

  ① **인벤토리가 기계 산출인가.** 실물 T-Box 에서 어휘를 긁어오고, 열거형 개별자
     (`pakr:VerdictWellKnown` 같은 주지관용 판정)까지 어휘로 잡는가. 이것이 빠지면
     「담을 자리가 없다」는 판정이 거짓이 된다.
  ② **실패해야 할 입력이 실패하는가.** 인벤토리에 없는 용어 · 좌표 없음 · 인용 초과 ·
     사람 확인 없음 · 단위 목록 불일치 · 계열 미분류 · sha 불일치.
  ③ 집계가 카드 수와 판단 수를 구분하는가(`cards` 대 `units`).

카드 픽스처는 합성이다. 실물 통지서 문구를 넣지 않는다(§1-5).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import report_r1_dissection as rd  # noqa: E402

TERMS = {"pa:coveredBy": "t.ttl", "pakr:VerdictWellKnown": "t.ttl"}


def card(**over):
    c = {
        "card_id": "c1", "source_file": "f.txt", "source_sha256": "a" * 64,
        "application": "1020000000000", "legal_ground": "§29②", "target_claims": ["1"],
        "cited_docs": ["X"], "query_element": "요소", "disclosure": "개시",
        "assertion_type": "조합", "condition": "", "coords": ["L0010"], "quote": "인용",
        "verdict": "E2", "secondary": [], "verdict_terms": ["pa:coveredBy"],
        "verdict_reason": "이유", "deficiency": ["combination-of-documents"],
        "parser_gap": True, "units": ["1-1"], "unit_n": 1,
    }
    c.update(over)
    return c


def sample(verified=True):
    return {"files": [{"source_file": "f.txt", "sha256": "a" * 64, "stratum": "mixed"}],
            "human_verified": verified, "verified_on": "2026-09-28", "seed": 1,
            "population": 1, "population_by_stratum": {"mixed": 1},
            "not_a_frequency_estimate": "…"}


def test_inventory_is_machine_extracted_and_includes_enum_individuals():
    terms, shas = rd.inventory()
    assert len(terms) > 200 and shas
    assert "pa:coveredBy" in terms and "pa:Disclosure" in terms
    # 주지관용·설계변경 판정은 개별자로 선언돼 있다 — 빠뜨리면 결손 판정이 거짓이 된다.
    assert "pakr:VerdictWellKnown" in terms and "pakr:VerdictDesignChange" in terms
    # A-Box 는 어휘 선언의 자리가 아니다(§1-2).
    assert not any(n.startswith("sdkb-abox") for n in shas)


def test_happy_path_counts_cards_and_units_separately():
    cards = [card(), card(card_id="c2", units=["2-1", "2-2"], unit_n=2,
                          deficiency=["in-document-locator"])]
    rd.check(cards, sample(), TERMS)
    agg = rd.aggregate(cards, sample())
    assert agg["cards"] == 2 and agg["units"] == 3
    assert agg["by_verdict"] == {"E2": 2} and agg["parser_gap"] == 2
    assert agg["deficiencies"]["in-document-locator"]["family"] == "A 증거 위치"


@pytest.mark.parametrize("bad,msg", [
    ({"verdict_terms": ["pa:없는술어"]}, "인벤토리에 없는 용어"),
    ({"coords": []}, "좌표가 없거나"),
    ({"quote": "가" * 51}, "인용이 50자를 넘는다"),
    ({"verdict": "E9"}, "판정이"),
    ({"unit_n": 5}, "단위 목록이 비었거나"),
    ({"deficiency": []}, "결손 슬러그가 없다"),
    ({"source_sha256": "b" * 64}, "sha256 이 표본과 다르다"),
    ({"source_file": "다른파일.txt"}, "원천이 표본에 없다"),
])
def test_injection_dies(bad, msg):
    with pytest.raises(SystemExit, match=msg):
        rd.check([card(**bad)], sample(), TERMS)


def test_unverified_sample_is_refused():
    """사람 확인 전에는 본문이 LLM 에 갈 자격이 없다 — 집계도 거부한다(§1-5)."""
    with pytest.raises(SystemExit, match="사람 확인을 받지 않았다"):
        rd.check([card()], sample(verified=False), TERMS)


def test_unmapped_deficiency_dies():
    """새 결손을 만들면 어느 층의 문제인지 말해야 한다 — 분류 없는 목록은 개수만 늘린다."""
    cards = [card(deficiency=["아직-분류하지-않은-결손"])]
    with pytest.raises(SystemExit, match="계열 매핑에 없는 결손"):
        rd.aggregate(cards, sample())


def test_duplicate_card_id_dies():
    with pytest.raises(SystemExit, match="card_id 중복"):
        rd.check([card(), card()], sample(), TERMS)


def test_committed_cards_pass_their_own_gate():
    """커밋된 카드가 이 집계기의 검사를 실제로 통과하는가 — 장식이 아닌지 확인한다."""
    s = json.loads((rd.SAMPLE).read_text(encoding="utf-8"))
    cards = rd.load_cards()
    terms, _ = rd.inventory()
    rd.check(cards, s, terms)
    agg = rd.aggregate(cards, s)
    assert agg["documents"] == len(s["files"]) == 30
    assert agg["units"] >= agg["cards"] > 0
