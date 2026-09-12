"""PLAN-005 R0-CAL-0 — 분할 진입점의 계약.

(a) 동결 sha 둘이 실물과 일치한다 — 결과를 본 뒤 분할을 갈아끼우면 여기서 걸린다.
(b) 구조 계약 (1,200행 · 4분할 · 중복 0 · 봉인 집합).
(c) **실패해야 할 입력이 실패한다** — sha 가 다른 분할표, 봉인 문서가 섞인 채굴 범위.
(d) normalize_doc_id 는 매핑이 아니라 검사기다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import splits as S  # noqa: E402


# ── (a) 동결 sha ────────────────────────────────────────────────────────
def test_frozen_split_csv_sha_matches_file():
    assert S.sha256_of(S.SPLIT_CSV) == S.SPLIT_CSV_SHA256


def test_frozen_upstream_parquet_sha_matches_scope_file():
    scope = json.loads(S.HARVEST_SCOPE.read_text(encoding="utf-8"))
    assert scope["_source"]["sha256"] == S.UPSTREAM_PARQUET_SHA256


# ── (b) 구조 계약 ───────────────────────────────────────────────────────
def test_sealed_splits_are_test_and_test_b():
    # 사용자 승인 2026-09-12. test 만 봉인하면 test_b 가 조용히 열린다.
    assert S.SEALED == frozenset({"test", "test_b"})
    assert S.OPEN == frozenset({"dev", "train"})
    assert not (S.SEALED & S.OPEN)


def test_load_split_shape():
    m = S.load_split()
    assert len(m) == S.EXPECTED_ROWS == 1200
    assert S.split_composition(m, split_map=m) == {
        "dev": 200, "test": 200, "test_b": 200, "train": 600,
    }


def test_queries_in_open_is_800_and_disjoint_from_sealed():
    m = S.load_split()
    open_ids = S.queries_in(S.OPEN, split_map=m)
    sealed_ids = S.queries_in(S.SEALED, split_map=m)
    assert len(open_ids) == 800
    assert len(sealed_ids) == 400
    assert not (open_ids & sealed_ids)


def test_queries_in_rejects_unknown_split():
    with pytest.raises(ValueError):
        S.queries_in("holdout", split_map=S.load_split())


def test_split_composition_does_not_silently_drop_unknown_ids():
    m = S.load_split()
    out = S.split_composition(["kr_9999999999999"], split_map=m)
    assert out == {"_unknown": 1}


def test_scope_agreement_holds_today():
    facts = S.assert_scope_agreement()
    assert facts["open_queries"] == 800
    assert facts["sealed_splits"] == ["test", "test_b"]
    assert facts["counts"] == {"dev": 200, "train": 600}


# ── (c) 실패해야 할 입력이 실패한다 ─────────────────────────────────────
def test_tampered_split_csv_dies(tmp_path):
    bad = tmp_path / "split.csv"
    bad.write_text(S.SPLIT_CSV.read_text(encoding="utf-8") + "kr_1099999999999,dev,999,2020-01-01\n",
                   encoding="utf-8")
    with pytest.raises(SystemExit):
        S.load_split(bad)


def test_duplicate_doc_id_dies(tmp_path):
    bad = tmp_path / "dup.csv"
    bad.write_text("doc_id,split\nkr_1020200000001,dev\nkr_1020200000001,train\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        S.load_split(bad, verify=False)


def test_unknown_split_value_dies(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("doc_id,split\nkr_1020200000001,holdout\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        S.load_split(bad, verify=False)


def test_scope_with_one_sealed_doc_dies(tmp_path):
    """채굴 범위에 봉인 문서가 한 건 섞이면 죽는가 — E-3 이 조용히 지나간 바로 그 자리."""
    m = S.load_split()
    scope = json.loads(S.HARVEST_SCOPE.read_text(encoding="utf-8"))
    sealed_one = sorted(S.queries_in(S.SEALED, split_map=m))[0]
    scope["doc_ids"] = sorted(set(scope["doc_ids"]) | {sealed_one})
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit):
        S.assert_scope_agreement(p, split_map=m)


def test_scope_with_stale_upstream_sha_dies(tmp_path):
    m = S.load_split()
    scope = json.loads(S.HARVEST_SCOPE.read_text(encoding="utf-8"))
    scope["_source"]["sha256"] = "0" * 64
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit):
        S.assert_scope_agreement(p, split_map=m)


def test_scope_with_only_test_excluded_dies(tmp_path):
    m = S.load_split()
    scope = json.loads(S.HARVEST_SCOPE.read_text(encoding="utf-8"))
    scope["excluded_splits"] = ["test"]
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit):
        S.assert_scope_agreement(p, split_map=m)


# ── (d) normalize_doc_id 는 검사기다 ────────────────────────────────────
def test_normalize_strips_patent_prefix_only():
    assert S.normalize_doc_id("patent:kr_1019970082313") == "kr_1019970082313"
    assert S.normalize_doc_id("kr_1019970082313") == "kr_1019970082313"


def test_normalize_rejects_foreign_shapes():
    for bad in ("10-2021-0184131", "KR1020190085654", "", "patent:", "kr-1019970082313"):
        with pytest.raises(ValueError):
            S.normalize_doc_id(bad)


def test_rej_query_space_equals_split_space():
    """두 id 공간이 같다는 실측을 명제로 고정한다 — 갈리면 normalize 가 매핑이 되어야 한다."""
    pd = pytest.importorskip("pandas")
    f = ROOT / "mappings" / "claim_features.parquet"
    if not f.exists():
        pytest.skip("claim_features.parquet 없음")
    cf = pd.read_parquet(f, columns=["publication_id", "side"])
    rej = set(cf[cf.side == "rej"].publication_id.unique())
    assert rej == set(S.load_split())
