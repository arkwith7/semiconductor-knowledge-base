"""PLAN-005 R0-CAL-0 — 누설 검사기의 계약.

게이트는 물어야 게이트다. 그래서 여기서 가장 중요한 것은 통과 확인이 아니라 **주입**이다 —
봉인 문서를 채굴 산출물에 심으면 K-2 가 반드시 실패하는가, 분할을 선언한 리포트에 봉인
질의가 있으면 K-4 가 실패하는가.

그리고 K-6 은 **0 을 보고하지 않는다.** 인용문헌 family 를 잴 데이터가 없는 것과 재서 0 이
나온 것은 다른 말이고, 둘을 같게 적으면 없는 증거가 증거처럼 읽힌다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import check_leakage as CL  # noqa: E402
from scripts import splits as S  # noqa: E402


@pytest.fixture(scope="module")
def split_map():
    return S.load_split()


def _sealed_doc(split_map):
    return sorted(S.queries_in(S.SEALED, split_map=split_map))[0]


# ── 오늘의 상태 ─────────────────────────────────────────────────────────
def test_k1_k2_k3_pass_today(split_map):
    assert CL.k1_split_frozen(split_map)["status"] == "PASS"
    assert CL.k2_harvest_outputs(split_map)["status"] == "PASS"
    assert CL.k3_dictionaries()["status"] == "PASS"


def test_k4_k5_are_pending_until_cal3(split_map):
    # 사용자 결정 B — 아직 없는 산출물에 대한 검사는 거짓 FAIL 이 아니라 PENDING 이다.
    assert CL.k4_eval_reports(split_map)["status"] == "PENDING"
    assert CL.k5_seal_ledger()["status"] == "PENDING"


def test_k6_reports_unmeasurable_not_zero(split_map):
    r = CL.k6_family(split_map)
    assert r["status"] == "UNMEASURABLE"
    assert r["numbers"]["crossing"] == 0
    um = r["numbers"]["unmeasurable"]
    assert set(um) == {"cited_family", "cited_filing_date"}
    assert um["cited_family"]["matched"] == []


# ── 주입 — 실패해야 할 입력이 실패하는가 ────────────────────────────────
def test_k2_fails_when_sealed_doc_is_injected(tmp_path, split_map, monkeypatch):
    sealed = _sealed_doc(split_map)
    copies = []
    for p in CL.HARVEST_ARTIFACTS:
        q = tmp_path / p.name
        q.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        copies.append(q)
    doc = json.loads(copies[0].read_text(encoding="utf-8"))
    doc["_injected"] = {"claim_source": sealed}
    copies[0].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(CL, "HARVEST_ARTIFACTS", copies)
    r = CL.k2_harvest_outputs(split_map)
    assert r["status"] == "FAIL"
    assert r["numbers"]["sealed_hits"] == 1


def test_k2_injection_under_an_unexpected_key_is_still_caught(tmp_path, split_map, monkeypatch):
    """키 이름이 아니라 값의 모양으로 찾는 이유 — 스키마가 바뀌어도 새면 잡아야 한다."""
    sealed = _sealed_doc(split_map)
    copies = []
    for p in CL.HARVEST_ARTIFACTS:
        q = tmp_path / p.name
        q.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        copies.append(q)
    doc = json.loads(copies[1].read_text(encoding="utf-8"))
    doc["quite_unrelated_field"] = [[{"deep": f"근거 문헌 {sealed} 참조"}]]
    copies[1].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(CL, "HARVEST_ARTIFACTS", copies)
    assert CL.k2_harvest_outputs(split_map)["status"] == "FAIL"


def test_k3_fails_when_identifier_enters_a_dictionary(tmp_path, monkeypatch):
    fake = tmp_path / "abox_term_aliases.json"
    fake.write_text(json.dumps({"게이트전극": ["kr_1020210184131"]}, ensure_ascii=False),
                    encoding="utf-8")
    monkeypatch.setattr(CL, "MAPPING_ARTIFACTS", [fake])
    r = CL.k3_dictionaries()
    assert r["status"] == "FAIL"
    assert r["numbers"]["identifier_hits"] >= 1


def test_k4_fails_when_split_scoped_report_holds_sealed_queries(tmp_path, split_map, monkeypatch):
    sealed = _sealed_doc(split_map)
    fake = tmp_path / "priorart_stage7_remeasure.json"
    fake.write_text(json.dumps(
        {"split": "dev", "split_sha256": S.SPLIT_CSV_SHA256, "per_query": {sealed: {"n": 1}}},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(CL, "EVAL_REPORTS", [fake])
    r = CL.k4_eval_reports(split_map)
    assert r["status"] == "FAIL"


def test_k4_passes_when_split_scoped_report_is_clean(tmp_path, split_map, monkeypatch):
    open_doc = sorted(S.queries_in(S.OPEN, split_map=split_map))[0]
    fake = tmp_path / "priorart_stage7_remeasure.json"
    fake.write_text(json.dumps(
        {"split": "dev", "split_sha256": S.SPLIT_CSV_SHA256, "per_query": {open_doc: {"n": 1}}},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(CL, "EVAL_REPORTS", [fake])
    assert CL.k4_eval_reports(split_map)["status"] == "PASS"


def test_k5_fails_on_row_count_mismatch(tmp_path, monkeypatch):
    fake = tmp_path / "v4_robustness.json"
    fake.write_text(json.dumps({"seal_ledger_rows": 7}), encoding="utf-8")
    monkeypatch.setattr(CL, "EVAL_REPORTS", [fake])
    r = CL.k5_seal_ledger()
    assert r["status"] == "FAIL"


def test_k5_fails_on_malformed_ledger(tmp_path, monkeypatch):
    led = tmp_path / "seal_access.jsonl"
    led.write_text(json.dumps({"opened_at": "x"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(CL.seal, "LEDGER", led)
    monkeypatch.setattr(CL, "EVAL_REPORTS", [])
    assert CL.k5_seal_ledger()["status"] == "FAIL"


# ── 부수 산출 (사용자 결정 A) ───────────────────────────────────────────
def test_query_universe_is_1000_and_80pct_open(split_map):
    qu = CL.query_universe(split_map)
    gt = qu["gt_bearing"]
    assert gt["n"] == 1000
    assert gt["composition"] == {"dev": 200, "test": 200, "train": 600}
    assert gt["composition"].get("test_b", 0) == 0     # test_b 는 정답 간선이 없어 질의가 아니다
    open_n = gt["composition"]["dev"] + gt["composition"]["train"]
    assert open_n / gt["n"] == 0.8                      # §20 E-3 의 "80%"
    assert qu["reachable_target_approx"]["approximate"] is True


# ── 결정성 ─────────────────────────────────────────────────────────────
def test_report_has_no_timestamp_key():
    """generated 날짜를 넣으면 두 실행의 바이트가 갈려 재현성 검사가 못 돈다."""
    out = ROOT / "data" / "reports" / "leakage_check.json"
    if not out.exists():
        pytest.skip("리포트 없음 — make check-leakage")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "generated" not in doc and "generated_at" not in doc
