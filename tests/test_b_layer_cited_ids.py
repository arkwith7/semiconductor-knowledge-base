"""CR-008 — B층 식별자 정규화의 회귀 테스트.

이 CR 의 전체 설계가 **하나의 실측**에 걸려 있다: 이관 파일의 표기가 엣지표의
`cited_raw` 와 같으므로, 정규 IRI 를 조회 없이 문자열 변환으로 얻을 수 있다는 것.
그 전제가 조용히 깨지면 B층 노드가 A층과 **다른 IRI 공간**에 서게 되고, 그때는
누구도 알아채지 못한다 — 두 집합이 서로 겹치지 않으므로 충돌조차 나지 않기 때문이다.

그래서 왕복 일치를 A층 전량에 대해 고정한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_b_layer_cited_ids import (  # noqa: E402
    DEFAULT_IDS,
    EXPECTED_SHA256,
    NO_A_LAYER_PRECEDENT,
    build,
    normalize,
    verify_sha256,
)

EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"

# 2026-08-09(CR-016 성공기준 ①): 이 파일들은 **논문 평가자산**이라 공개본에 없다
# (원고 §10.3 — 하네스 비공개). 그런데 테스트는 그 사실을 몰랐고, 개인 컴퓨터에
# 논문 저장소가 있어서 **우연히** 통과하고 있었다. 빈 체크아웃에서 처음 드러났다.
# 없으면 **건너뛴다** — 검증을 느슨하게 하는 것이 아니라, 입력이 없으면 이 질문을
# 물을 수 없다는 사실을 말하는 것이다. 있으면 예전 그대로 전부 돈다.
_missing = [p.name for p in (DEFAULT_IDS, EDGES) if not p.exists()]
pytestmark = pytest.mark.skipif(
    bool(_missing),
    reason=f"논문 평가자산 미비 — {_missing}. 목록은 --ids 로 주거나 논문 저장소에서 가져온다.",
)


# ── 단위: 정규화 ────────────────────────────────────────────────────
# `cited_doc_id` 기대값은 손으로 지은 것이 아니라 **A층 실물에서 확인한 규약**이다.
# 특히 KR 등록번호는 문서종별 접두 '10' 과 선행 0 이 떨어진다(A층 264 건).
@pytest.mark.parametrize("raw,cid,doc", [
    ("KR1020090041506 A", "patent:kr_KR1020090041506A", "KR-P-1020090041506"),
    ("US20190348292 A1", "patent:us_US20190348292A1", "US-P-20190348292"),
    ("JP2001358218 A", "patent:jp_JP2001358218A", "JP-P-2001358218"),
    ("JP01033055 A", "patent:jp_JP01033055A", "JP-P-01033055"),       # 연호형 8자리
    ("KR101036572 B1", "patent:kr_KR101036572B1", "KR-G-1036572"),    # '10' 탈락
    ("KR100916931 B1", "patent:kr_KR100916931B1", "KR-G-916931"),     # '10' + 선행 0 탈락
    ("KR200287084 Y1", "patent:kr_KR200287084Y1", "KR-G-200287084"),  # A층 전례 없음
    ("CN201842886 U", "patent:cn_CN201842886U", "CN-G-201842886"),
])
def test_normalize_roundtrip(raw, cid, doc):
    c = normalize(raw)
    assert c is not None
    assert c.cited_id == cid
    assert c.cited_doc_id == doc


def test_normalize_preserves_leading_zeros():
    """선행 0 을 지우면 JP 연호형이 다른 문헌을 가리킨다."""
    assert normalize("JP01033055 A").serial == "01033055"


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "B. R. Yang et. al. An anisotropic etching effect, Advanced Materials. 2010.",
    "HIRAM E. GRANT. 지그와 고정구. 서울: 성안당. 1990.01.05., 12판 1부.",
    "Journal of The Korean Physical Soc, Vol. 45, No. 6, 2004, pp. 1639-1643",
])
def test_normalize_rejects_non_patent(raw):
    """NPL 은 특허로 오분류되지 않는다 — 형식에 맞는 것만 특허로 본다."""
    assert normalize(raw) is None


def test_every_patent_row_resolves_to_a_doc_id():
    """정본 정규화기가 514 행 전량을 읽는다 — 'UNKNOWN::' 이 하나도 없어야 한다.

    조용히 넘기면 그 문서만 수집에서 빠지고 분모 503 은 그대로여서 눈에 띄지 않는다.
    """
    df = build(DEFAULT_IDS, out=None)
    pat = df[~df["is_npl"]]
    assert not pat["cited_doc_id"].str.startswith("UNKNOWN::").any()
    assert pat["cited_kind"].isin(["publication", "grant"]).all()


# ── 단위: 무결성 ────────────────────────────────────────────────────
def test_sha256_mismatch_aborts(tmp_path):
    f = tmp_path / "ids.txt"
    f.write_text("KR1020090041506 A\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        verify_sha256(f, EXPECTED_SHA256)


def test_handoff_file_signature_frozen():
    """동결 분모 503 은 이 파일에 걸려 있다."""
    assert verify_sha256(DEFAULT_IDS) == EXPECTED_SHA256


# ── 통합: 동결된 모집단 구성 ────────────────────────────────────────
def test_population_composition_frozen():
    """CR-008 이 동결한 분모와 관할 구성. 바뀌면 CR 을 다시 받아야 한다."""
    df = build(DEFAULT_IDS, out=None)
    pat = df[~df["is_npl"]]
    assert len(df) == 514
    assert len(pat) == 503                      # 동결 분모 (2026-08-03)
    assert int(df["is_npl"].sum()) == 11
    assert pat["cited_country"].value_counts().to_dict() == {
        "KR": 235, "JP": 186, "US": 51, "WO": 24, "CN": 6, "EP": 1}


def test_no_duplicate_ids():
    df = build(DEFAULT_IDS, out=None)
    pat = df[~df["is_npl"]]
    assert not pat["cited_id"].duplicated().any()


def test_deterministic():
    """두 번 돌려 같은 표 — 정렬이 흔들리면 parquet 바이트가 달라진다."""
    a = build(DEFAULT_IDS, out=None)
    b = build(DEFAULT_IDS, out=None)
    pd.testing.assert_frame_equal(a, b)


def test_kind_codes_without_a_layer_precedent_are_exactly_five():
    """설계 D3 — 개별 검증 대상 5 건. 늘어나면 설계 결정을 다시 받아야 한다."""
    df = build(DEFAULT_IDS, out=None)
    odd = df[(~df["is_npl"]) & (df["kind_code"].isin(NO_A_LAYER_PRECEDENT))]
    assert sorted(odd["cited_raw"]) == [
        "JP2605509 Y2", "JP60244476 X2",
        "KR200287084 Y1", "KR200415562 Y1", "KR200440005 Y1"]


# ── 통합: A층 전량 왕복 (이 CR 설계의 전제) ─────────────────────────
def _a_layer_patent_docs() -> pd.DataFrame:
    """A층 특허 문헌(정규 표기). NPL(`patent:other_…`)은 이 CR 의 대상이 아니다."""
    edges = pd.read_parquet(EDGES)
    canon = edges[edges["cited_id"].astype(str).str.startswith("patent:")]
    canon = canon[~canon["cited_id"].astype(str).str.startswith("patent:other_")]
    return canon.drop_duplicates("cited_id")


@pytest.mark.skipif(not EDGES.exists(), reason="prior_art_edges.parquet 없음")
def test_cited_id_rule_matches_a_layer_for_canonical_notation():
    """정규 표기 A층 특허 문헌 전량에서 `cited_id` 규칙이 성립한다.

    A층에는 비정규 표기 14 건(`US2015/0093880`·`JP-H08-255787`·`KR2001-29136` …)이
    섞여 있고 이 모듈은 그것을 다루지 않는다 — **이관 파일 514 행에는 그런 표기가
    한 건도 없기 때문**이다(`test_population_composition_frozen` 이 이를 고정한다).
    새 표기가 들어오면 `build()` 가 중단한다.
    """
    canon = _a_layer_patent_docs()
    sub = canon[canon["cited_raw"].str.match(r"^[A-Z]{2}\d+\s*[A-Z]?\d?$", na=False)]
    assert len(sub) >= 3135, f"정규 표기 표본이 {len(sub)}건으로 줄었다"

    mismatched = []
    for _, r in sub.iterrows():
        c = normalize(str(r["cited_raw"]))
        if c is None or c.cited_id != r["cited_id"]:
            mismatched.append((r["cited_raw"], r["cited_id"], c.cited_id if c else None))
    assert not mismatched, f"왕복 불일치 {len(mismatched)}건: {mismatched[:5]}"


@pytest.mark.skipif(not EDGES.exists(), reason="prior_art_edges.parquet 없음")
def test_cited_doc_id_matches_a_layer():
    """`cited_doc_id` 가 A층 규약과 일치한다 — 갈라지면 KIPRIS 캐시 키가 어긋난다.

    A층 자체가 `cited_doc_id` 를 비워 둔 결손행 4 건은 제외한다(그쪽이 결함이다).
    """
    canon = _a_layer_patent_docs()
    canon = canon[canon["cited_doc_id"].astype(str).str.len() > 0]

    bad = []
    for _, r in canon.iterrows():
        c = normalize(str(r["cited_raw"]))
        if c and c.cited_doc_id != r["cited_doc_id"]:
            bad.append((r["cited_raw"], r["cited_doc_id"], c.cited_doc_id))
    assert not bad, f"cited_doc_id 불일치 {len(bad)}건: {bad[:5]}"


@pytest.mark.skipif(not EDGES.exists(), reason="prior_art_edges.parquet 없음")
def test_b_layer_ids_do_not_collide_with_a_layer_nodes():
    """B층 503 건 중 A층에 이미 있는 것은 3 건뿐 — 나머지가 새 노드가 된다.

    겹치는 3 건은 **같은 `cited_id`** 를 가져야 한다(그래야 노드가 하나로 합쳐진다).
    """
    canon = set(_a_layer_patent_docs()["cited_id"])
    df = build(DEFAULT_IDS, out=None)
    overlap = set(df.loc[~df["is_npl"], "cited_id"]) & canon
    assert len(overlap) == 3, f"A층 중복이 {len(overlap)}건 — 2단계 실측(3)과 다르다"
