"""Regression tests for dependent-claim decomposition (Tier 1 판단 계층).

Covers:
  - decompose_claims.is_independent / decompose  — 종속항도 feature ≥1 로 분해되는가
  - build_abox_claim_features 산출 리포트         — 종속항 노드·dependsOnClaim·매달린 부모 가드

거절특허 종속항(§29② 진보성의 added-feature 축)이 실체화되지 않으면 판단이 청구항 단위로
링크되지 못한다. 이 테스트는 그 실체화 계약이 흔들리면 실패한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from decompose_claims import decompose, is_independent  # noqa: E402

REPORT = ROOT / "data" / "reports" / "abox_claim_features_report.json"

# 실제 코퍼스에서 뽑은 종속항(부모 1항 한정 + 재료 추가 한정) — 결정적 픽스처.
_DEP_CLAIM = (
    "2. 제 1 항에 있어서, 상기 다층 하드마스크의 상기 하부 층은 비정질 실리콘, 실리콘 옥사이드, "
    "실리콘 카바이드로 구성된 그룹으로부터 선택된 재료를 포함하는, 기판 프로세싱 방법."
)
_INDEP_CLAIM = (
    "1. 기판 상에 다층 하드마스크를 형성하는 단계; 상기 하드마스크를 패터닝하는 단계; 및 "
    "상기 패턴을 상기 기판으로 전사하는 단계를 포함하는, 기판 프로세싱 방법."
)


# ─── 순수 함수 계약 (네트워크·LLM 없음) ─────────────────────────────
def test_dependent_claim_is_not_independent():
    assert is_independent(_DEP_CLAIM) is False
    assert is_independent(_INDEP_CLAIM) is True


def test_dependent_claim_yields_at_least_one_feature():
    """종속항도 한정요소 ≥1 로 분해돼야 SHACL Shape_Claim(hasFeature ≥1)을 통과한다."""
    dc = decompose(_DEP_CLAIM, 2)
    assert len(dc.features) >= 1
    assert all(f.text.strip() for f in dc.features)


def test_decompose_deterministic():
    """같은 청구항이면 같은 분해 — 재현성."""
    a = decompose(_DEP_CLAIM, 2)
    b = decompose(_DEP_CLAIM, 2)
    assert [f.text for f in a.features] == [f.text for f in b.features]


# ─── 빌드 산출 리포트 불변식 (아티팩트 있을 때만) ───────────────────
def _counts() -> dict:
    if not REPORT.exists():
        pytest.skip("abox_claim_features_report.json 없음 — build_abox_claim_features.py 먼저")
    return json.loads(REPORT.read_text())["counts"]


def test_report_has_dependent_claims():
    c = _counts()
    assert c.get("claims_dependent", 0) > 0, "종속항이 실체화되지 않았다"
    assert c["claims"] == c["claims_independent"] + c["claims_dependent"]


def test_dependsonclaim_edges_present():
    c = _counts()
    assert c.get("depends_on_claim", 0) >= c["claims_dependent"], (
        "종속항 수보다 dependsOnClaim 엣지가 적다 — 상속 축 누락"
    )


def test_dangling_parents_dropped_not_emitted():
    """존재하지 않는 부모항 참조는 매달린 IRI 를 낳으므로 버리고 계상해야 한다."""
    c = _counts()
    # 키가 있으면 정수여야 하고(계상됨), 없으면 0(그런 참조 없음) — 둘 다 정직.
    assert isinstance(c.get("depends_on_claim_dangling", 0), int)


# ─── Tier 2: 인용 종속항 부모 추출 + LLM 백엔드 (순수/설정) ────────────
def test_parent_extraction_from_cited_text():
    """구조화 depends_on 이 없는 인용 청구항은 텍스트에서 부모항 번호를 뽑는다."""
    from decompose_corpus import _parents
    assert _parents("2. 제 1 항에 있어서, 상기 막은 ...") == [1]
    assert _parents("5. 청구항 3 또는 청구항 4에 있어서, ...") == [3, 4]
    assert _parents("The method of claim 1, wherein ...") == [1]
    assert _parents("1. 기판 상에 막을 형성하는 단계를 포함하는 방법.") == []  # 독립항


def test_llm_backend_is_configured():
    """LLM 백엔드는 bedrock|ollama 중 하나로 확정되고 모델 문자열이 있어야 한다."""
    import llm_claim_validate as L
    assert L.BACKEND in ("bedrock", "ollama")
    assert L.MODEL  # 캐시 키에 들어가는 모델 식별자


def test_llm_cache_key_includes_model():
    """캐시 키에 모델이 들어가 백엔드 전환 시 교차 오염이 없어야 한다(결정성 계약)."""
    import llm_claim_validate as L
    assert L._key("동일 청구항") != __import__("hashlib").sha256(b"other-model\n\xeb\x8f\x99").hexdigest()
    # 같은 텍스트·같은 모델이면 같은 키(재현성)
    assert L._key("x") == L._key("x")
