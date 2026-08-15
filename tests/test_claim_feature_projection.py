"""CR-017 — 청구항 한정요소 투영이 지켜야 할 계약.

TTL 은 899 MB 라 벤더할 수 없다. 그래서 하류가 실제로 쓰는 것은 이 투영 2종이고,
**투영이 깨지는 방식은 넷**이다 — 넷 다 하류에서 조용한 오류가 된다.

1. **원문이 샌다.** `feature_text` 가 한 열이라도 들어가면 KIPRIS 비재배포 위반이고,
   CR-015 가 세운 공개 경계가 이 파일 하나로 뚫린다.
2. **grain 이 무너진다.** 행이 ClaimFeature 하나가 아니게 되면(개념 explode 등)
   하류가 조인할 때 feature 를 중복 계수한다.
3. **계수가 겹세기를 한다.** 같은 feature IRI 가 두 행이 되면 그 순간 D-41 이 재발한다
   (발행된 `ClaimFeature` 계수가 228 부풀려져 반년 인용된 사건).
4. **결정성이 깨진다.** 두 번 돌려 sha256 이 다르면 하류가 어느 판을 썼는지 말할 수 없다.

**이 테스트는 산출물을 읽기만 한다** — 빌드는 25분이 걸리므로 여기서 돌리지 않는다.
산출물이 없으면 skip 하고, 있으면 계약을 검사한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_abox_claim_features import OUT_PARQUET, OUT_PROJ_META  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (OUT_PARQUET.exists() and OUT_PROJ_META.exists()),
    reason="투영 산출물 없음 — scripts/build_abox_claim_features.py 실행 후",
)

# 원문 계열 열 이름. 하나라도 나오면 실패다(§비목표 ⓐ).
FORBIDDEN = {"feature_text", "text", "claim_text", "abstract", "claims"}


@pytest.fixture(scope="module")
def proj():
    import pandas as pd

    return pd.read_parquet(OUT_PARQUET)


@pytest.fixture(scope="module")
def meta():
    return json.loads(OUT_PROJ_META.read_text(encoding="utf-8"))


def test_no_full_text_column(proj) -> None:
    """원문은 한 열도 싣지 않는다 — 공개 경계가 이 파일에서 뚫리면 안 된다."""
    leaked = FORBIDDEN & set(proj.columns)
    assert not leaked, f"원문 계열 열이 실렸다: {leaked}"


def test_row_is_one_claim_feature(proj) -> None:
    """행 = ClaimFeature 하나. 중복이 있으면 D-41 이 재발한 것이다."""
    key = ["claim_id", "feature_seq"]
    assert not proj.duplicated(key).any(), "같은 feature 가 두 행이다 — 겹세기(D-41)"


def test_counts_match_meta(proj, meta) -> None:
    """메타의 계수가 실제 행에서 나온 값이어야 한다 — 손으로 적은 숫자를 금지한다."""
    c = meta["counts"]
    assert c["rows_features"] == len(proj)
    assert c["patents"] == proj["publication_id"].nunique()
    assert c["claims"] == proj["claim_id"].nunique()
    assert c["features_with_concept"] == int((proj["feature_concept"].str.len() > 0).sum())
    assert c["concept_links"] == int(proj["feature_concept"].str.len().sum())


def test_rows_and_lists_are_sorted(proj) -> None:
    """결정성의 근거 — 정렬이 깨지면 두 번 돌린 sha256 이 갈린다."""
    key = ["publication_id", "claim_number", "feature_seq"]
    assert proj[key].equals(proj[key].sort_values(key, kind="mergesort").reset_index(drop=True))
    unsorted = [c for c in proj["feature_concept"] if list(c) != sorted(c)]
    assert not unsorted, f"개념 리스트가 정렬돼 있지 않다 ({len(unsorted)}행)"


def test_meta_has_no_timestamp(meta) -> None:
    """시각이 들어가면 두 번 돌린 sha256 이 반드시 갈린다(성공기준 ①)."""
    blob = json.dumps(meta, ensure_ascii=False)
    for token in ("generated_at", "timestamp", "created_at", "build_time"):
        assert token not in blob, f"메타에 시각 필드가 있다: {token}"


def test_meta_pins_the_source(meta) -> None:
    """어느 그래프에서 나온 투영인지 말할 수 있어야 한다 — D-19 재발 차단."""
    src = meta["source"]
    assert len(src["ttl_sha256"]) == 64
    assert src["generator"] == "build_abox_claim_features.py"


def test_concept_df_denominators_are_consistent(proj, meta) -> None:
    """df 는 두 분모로 발행한다 — 하류가 어느 쪽으로 가중할지 고른다(비목표 ⓑ)."""
    assert meta["df_denominator"]["features"] == len(proj)
    assert meta["df_denominator"]["patents"] == proj["publication_id"].nunique()
    for iri, m in meta["concepts"].items():
        assert 0 < m["df_patent"] <= m["df_feature"], f"{iri}: 특허 df 가 feature df 를 넘는다"
