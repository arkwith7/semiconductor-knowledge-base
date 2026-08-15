"""CR-019 — ClaimFeature 발행 계수 무결성 (하류 D-41).

**왜 이 파일이 있는가.** rdflib 는 같은 트리플을 합친다. 그래서 `g.add()` 호출 횟수를 세는
계수기는 **그래프를 기술하지 않는다.** 실제로 두 계열이 갈려 있었고 — 계수기는 방출을,
투영은 고유를 셌다 — 그 차(228)가 발행돼 하류가 자기 계수를 의심하는 오판을 낳았다.

여기서 고정하는 계약은 둘이다.
1. 계수는 **그래프가 세는 것과 같은 것**을 센다 (고유 기준).
2. 버려지는 방출은 **지우지 않고 따로 계상한다** — 조용히 합치면 다음 진단이 막힌다(D-25).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_abox_claim_features import (  # noqa: E402
    OUT_REPORT,
    _assert_count_integrity,
    _duplicate_key_stats,
)


# --- T1 · 중복 키를 세는 계약 -------------------------------------------

def test_duplicate_keys_are_counted_not_dropped():
    """같은 (patent, claim_no) 가 두 번 오면 키 1 · 초과 행 1 로 센다."""
    rows = [
        {"patent": "cited:kr_a", "claim_no": 1},
        {"patent": "cited:kr_a", "claim_no": 1},      # 중복
        {"patent": "cited:kr_a", "claim_no": 2},
        {"patent": "rej:kr_b", "claim_no": 1},
    ]
    s = _duplicate_key_stats(rows)
    assert s["input_duplicate_keys"] == 1
    assert s["input_duplicate_rows"] == 1
    assert s["duplicate_keys_by_side"] == {"cited": 1}


def test_duplicate_key_stats_splits_by_side():
    """측별 분해가 있어야 '어느 쪽 원천이 겹쳤나'를 리포트만 보고 알 수 있다."""
    rows = [
        {"patent": "cited:x", "claim_no": 1}, {"patent": "cited:x", "claim_no": 1},
        {"patent": "rej:y", "claim_no": 1}, {"patent": "rej:y", "claim_no": 1},
        {"patent": "rej:y", "claim_no": 1},                      # 3회 = 초과 2
    ]
    s = _duplicate_key_stats(rows)
    assert s["duplicate_keys_by_side"] == {"cited": 1, "rej": 1}
    assert s["input_duplicate_rows"] == 3
    assert s["input_duplicate_keys"] == 2                        # 키는 둘


def test_no_duplicates_reports_zero_not_absent():
    """중복이 없을 때 필드가 사라지면 '재지 않았다'와 '0 이었다'가 구분되지 않는다."""
    s = _duplicate_key_stats([{"patent": "rej:a", "claim_no": 1}])
    assert s["input_duplicate_keys"] == 0 and s["input_duplicate_rows"] == 0
    assert s["duplicate_keys_by_side"] == {}


def test_duplicate_key_stats_is_deterministic():
    rows = [{"patent": "cited:x", "claim_no": n % 3} for n in range(50)]
    assert _duplicate_key_stats(rows) == _duplicate_key_stats(rows)


# --- T5 · 실패해야 할 입력이 실패하는가 ---------------------------------
#
# 게이트는 초록불이 쉬우면 안 된다. 어긋난 리포트를 넣었을 때 죽지 않으면 그것은 게이트가 아니다.

def _report(features: int, rows_features: int, by_type: dict, concept_links: int) -> dict:
    return {"counts": {"features": features},
            "feature_concept_by_type": by_type,
            "projection_cr017": {"rows_features": rows_features,
                                 "concept_links": concept_links}}


def test_integrity_gate_rejects_inflated_feature_count():
    """D-41 그 자체 — 계수가 투영보다 많으면 리포트를 쓰지 않는다."""
    with pytest.raises(SystemExit) as e:
        _assert_count_integrity(_report(1_306_419, 1_306_191, {"Process": 10}, 10))
    assert "counts.features" in str(e.value)


def test_integrity_gate_rejects_inflated_concept_count():
    """표면형 겹세기 — 한 feature 가 같은 개념을 두 번 맞춰도 그래프 트리플은 하나다."""
    with pytest.raises(SystemExit) as e:
        _assert_count_integrity(_report(10, 10, {"Process": 592_779}, 529_151))
    assert "feature_concept_by_type" in str(e.value)


def test_integrity_gate_reports_both_problems_at_once():
    """하나만 알려 주면 고치고 다시 돌린 뒤에야 나머지를 안다 — 둘 다 한 번에 낸다."""
    with pytest.raises(SystemExit) as e:
        _assert_count_integrity(_report(11, 10, {"Process": 5}, 4))
    msg = str(e.value)
    assert "counts.features" in msg and "feature_concept_by_type" in msg


def test_integrity_gate_passes_when_counts_agree():
    """거짓 경보도 결함이다 — 맞는 리포트는 통과해야 한다."""
    _assert_count_integrity(_report(1_306_191, 1_306_191,
                                    {"Process": 300_000, "Material": 229_151}, 529_151))


# --- T6·T7 · 실물 통합 --------------------------------------------------

@pytest.mark.skipif(not OUT_REPORT.exists(),
                    reason="리포트 없음 — scripts/build_abox_claim_features.py 실행 후")
def test_published_report_counts_match_the_projection():
    """성공기준 ①⑥ — 발행된 리포트가 자기 투영과 같은 수를 말하는가."""
    rep = json.loads(OUT_REPORT.read_text(encoding="utf-8"))
    proj = rep["projection_cr017"]
    assert rep["counts"]["features"] == proj["rows_features"]
    assert sum(rep["feature_concept_by_type"].values()) == proj["concept_links"]


@pytest.mark.skipif(not OUT_REPORT.exists(), reason="리포트 없음")
def test_published_report_keeps_the_discarded_emissions_visible():
    """버린 것을 지우지 않았는가 — 재방출 계수가 리포트에 남아 있어야 한다."""
    rep = json.loads(OUT_REPORT.read_text(encoding="utf-8"))
    c = rep["counts"]
    for key in ("features_duplicate_emissions", "input_duplicate_keys",
                "input_duplicate_rows", "concept_hits_raw"):
        assert key in c, f"{key} 가 리포트에서 사라졌다 — 조용히 합치면 다음 진단이 막힌다"
    assert "duplicate_keys_by_side" in rep
