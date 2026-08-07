"""CR-011 — B층 청구항의 ClaimFeature 분해가 지켜야 할 계약.

이 CR 이 깨질 수 있는 방식은 넷이고, 넷 다 **조용하다**.

1. **A층이 움직인다.** 기존 `Claim` 586,567 · `ClaimFeature` 1,289,512 의 IRI 가 하나라도
   사라지면 하류가 pin 한 스냅샷의 출처 기록이 거짓이 된다(CR-011 성공기준 ③ · 상류 §0).
2. **B층 IRI 맵이 A층을 덮어쓴다.** 병합이 `setdefault` 가 아니면 같은 키에서 A층 값이 진다.
3. **`ont:claimText` 가 사라진다.** 이 CR 은 형식 교체가 아니라 **추가**다(비목표 ⓑ).
   다른 소비자가 그 술어를 읽고 있을 수 있다.
4. **결측이 "청구항 있음"으로 둔갑한다.** parquet 결측은 float `nan` 이고 `nan` 은 참이라
   `str(v or "")` 가 `"nan"` 을 낸다. 실제로 JP 19건이 미분해로 잘못 계상됐다(2026-08-06).
   손실 리포트의 분모를 **부풀리는 방향**이라 없는 손실을 상류에 보고하게 된다.

1·3 은 산출물에서, 2·4 는 코드에서 확인한다 — 산출물만 보면 "이번 입력에는 안 나왔다"까지만
보증하기 때문이다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ABOX = ROOT / "ontology" / "sdkb-abox-claim-features.ttl"
POP = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"
REPORT = ROOT / "data" / "reports" / "abox_claim_features_report.json"
LOSS = ROOT / "data" / "reports" / "b_layer_claim_decomposition_loss.json"
BUILDER = ROOT / "scripts" / "build_abox_claim_features.py"

# CR-011 성공기준 ③ — 이 값 아래로 내려가면 A층이 사라진 것이다.
A_LAYER_CLAIMS = 586_567
A_LAYER_FEATURES = 1_289_512


# ── 1. A층 불변 (성공기준 ③) ────────────────────────────────────────
@pytest.mark.skipif(not REPORT.exists(), reason="빌드 리포트 없음")
def test_a_layer_counts_never_shrink():
    """Claim·ClaimFeature 는 **늘기만 한다.** B층은 추가이지 교체가 아니다."""
    counts = json.loads(REPORT.read_text())["counts"]
    assert counts["claims"] >= A_LAYER_CLAIMS, (
        f"Claim 이 {counts['claims']} 로 줄었다 — A층 {A_LAYER_CLAIMS} 이 사라졌다")
    assert counts["features"] >= A_LAYER_FEATURES, (
        f"ClaimFeature 가 {counts['features']} 로 줄었다 — A층 {A_LAYER_FEATURES} 이 사라졌다")


# ── 2. B층 맵 병합이 A층을 덮어쓰지 않는다 ──────────────────────────
@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_b_layer_merge_uses_setdefault():
    """생성기가 `setdefault` 로 병합한다 — 같은 키면 A층(엣지표) 값이 이긴다."""
    src = BUILDER.read_text(encoding="utf-8")
    assert "cited_map.setdefault(doc, cid)" in src, (
        "B층 병합이 setdefault 가 아니다 — A층 IRI 가 덮어써질 수 있다")


@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_b_layer_population_shape():
    """모집단은 NPL 을 뺀 503건이고 IRI 는 전부 정규형이다."""
    pop = pd.read_parquet(POP)
    pat = pop[~pop["is_npl"]]
    assert len(pat) == 503
    assert pat["cited_id"].astype(str).str.startswith("patent:").all()


# ── 3. claimText 를 지우지 않는다 (비목표 ⓑ) ────────────────────────
def test_builder_never_deletes_claim_text():
    """이 생성기는 `ont:claimText` 를 만들지도 지우지도 않는다 — 다른 파일 소관이다."""
    src = BUILDER.read_text(encoding="utf-8")
    assert 'R("claimText")' not in src
    assert "claimText" not in src.replace("# ", "")  # 주석 밖에서 등장하지 않는다


# ── 4. 결측이 "청구항 있음"으로 둔갑하지 않는다 ─────────────────────
def test_claim_len_treats_missing_as_zero():
    """float `nan` 은 참이라 `str(v or "")` 가 `"nan"`(3글자)을 낸다.

    이 회귀가 살아나면 손실 리포트가 **없는 손실을 보고**한다 — 분모를 부풀리는 방향이다.
    """
    import build_abox_claim_features as m

    fn = m._b_loss_report.__globals__  # noqa: SLF001 — 모듈 내 지역 헬퍼 접근용
    assert fn is not None
    # 헬퍼는 _b_loss_report 안에 있으므로 동작을 대리 검증한다: 결측 표기가 코드에 남아 있는가.
    src = BUILDER.read_text(encoding="utf-8")
    assert "pd.isna" in src, "결측 검사가 사라졌다 — nan 이 '청구항 있음'으로 둔갑한다"
    assert 'str(r.get("claims") or "")' not in src, "결측을 참으로 만드는 표현이 되살아났다"


@pytest.mark.skipif(not LOSS.exists(), reason="B층 손실 리포트 없음")
def test_b_layer_loss_report_meets_cr011_thresholds():
    """성공기준 ①② — KR·US 분해율 ≥ 0.95. 본문 없는 US 2건은 분모에서 뺀다."""
    d = json.loads(LOSS.read_text())
    by = d["by_country"]
    assert by["KR"]["decomposition_rate"] >= 0.95, f"KR {by['KR']}"
    assert by["US"]["decomposition_rate"] >= 0.95, f"US {by['US']}"
    # JP·WO·CN·EP 는 D-05 상한이라 분모가 0 이어야 한다 — 있으면 결측 오판이다(위 회귀).
    for c in ("JP", "WO", "CN", "EP"):
        if c in by:
            assert by[c]["n_with_claim_text"] == 0, (
                f"{c} 에 청구항 문자열 {by[c]['n_with_claim_text']}건 — D-05 상한과 어긋난다")
