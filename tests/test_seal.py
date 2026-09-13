"""PLAN-005 R0-CAL-0 — 봉인 개봉의 계약 (D17 · 코드 게이트로만).

핵심은 둘이다. **기본이 막혀 있는가**, 그리고 **막혔을 때 흔적조차 남지 않는가**.
원장에 행이 있다는 것은 누군가 봉인을 열었다는 뜻이어야 하고, 막힌 시도가 행을 남기면
그 뜻이 흐려진다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import seal  # noqa: E402
from scripts import splits as S  # noqa: E402


def test_blocked_by_default_and_leaves_no_trace(tmp_path):
    led = tmp_path / "seal_access.jsonl"
    with pytest.raises(SystemExit):
        seal.open_sealed("test", "정당한 사유", ledger=led)
    assert seal.ledger_rows(led) == []          # 막힌 시도는 원장을 더럽히지 않는다
    assert not led.exists()


def test_open_splits_are_not_this_functions_job():
    with pytest.raises(ValueError):
        seal.open_sealed("dev", "사유", allow=True)


def test_empty_reason_rejected_even_when_allowed(tmp_path):
    led = tmp_path / "seal_access.jsonl"
    with pytest.raises(ValueError):
        seal.open_sealed("test", "   ", allow=True, ledger=led)
    assert seal.ledger_rows(led) == []


def test_allowed_open_returns_ids_and_writes_one_row(tmp_path):
    led = tmp_path / "seal_access.jsonl"
    ids = seal.open_sealed("test", "CAL-0 계약 시험", allow=True, caller="tests:test_seal", ledger=led)
    assert len(ids) == 200
    rows = seal.ledger_rows(led)
    assert len(rows) == 1
    assert tuple(sorted(rows[0])) == tuple(sorted(seal.REQUIRED_KEYS))
    assert rows[0]["reason"] == "CAL-0 계약 시험"
    assert rows[0]["caller"] == "tests:test_seal"


def test_ledger_is_append_only(tmp_path):
    led = tmp_path / "seal_access.jsonl"
    seal.open_sealed("test", "첫 개봉", allow=True, ledger=led)
    seal.open_sealed("test_b", "둘째 개봉", allow=True, ledger=led)
    rows = seal.ledger_rows(led)
    assert [r["reason"] for r in rows] == ["첫 개봉", "둘째 개봉"]


def test_ledger_keys_match_upstream_ledger():
    """상류 원장과 서식이 같아야 두 원장을 나란히 읽을 수 있다."""
    up = ROOT / "benchmark" / "assets" / "seal_access.jsonl"
    if not up.exists():
        pytest.skip("상류 원장 없음")
    for line in up.read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert tuple(sorted(json.loads(line))) == tuple(sorted(seal.REQUIRED_KEYS))


def test_malformed_row_is_caught(tmp_path):
    led = tmp_path / "seal_access.jsonl"
    led.write_text(json.dumps({"opened_at": "x", "reason": ""}, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    ok, problems = seal.ledger_is_wellformed(led)
    assert not ok and problems


def test_no_unseal_cli_flag_is_declared():
    """에이전트·CI 가 우연히 열 수 있는 문을 만들지 않았는가 (§20.7).

    산문 속 언급이 아니라 **선언**을 본다 — 막아야 할 것은 CLI 표면이다.
    """
    import ast

    for p in (ROOT / "scripts" / "seal.py", ROOT / "scripts" / "check_leakage.py",
              ROOT / "scripts" / "splits.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        assert not a.value.lstrip("-").startswith("unseal"), p


def test_real_ledger_absent_means_zero_rows():
    # 파일 부재는 결함이 아니라 "아무것도 열지 않았다" 이다.
    assert isinstance(seal.ledger_rows(), list)
