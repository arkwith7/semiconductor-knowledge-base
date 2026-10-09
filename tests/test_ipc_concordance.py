"""PLAN-006 T4 S2 — WIPO 판 대응표 생성기의 계약."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_ipc_concordance as B  # noqa: E402


@pytest.mark.parametrize("master,readable", [
    ("H01L0021306000", "H01L21/306"),
    ("H01L0021000000", "H01L21/00"),
    ("A61L0002020000", "A61L2/02"),
    ("H10D0048010000", "H10D48/01"),
])
def test_master_symbol_to_readable(master, readable):
    assert B.to_readable(master) == readable


@pytest.mark.parametrize("bad", ["", "H01L21/306", "H01L002130600", "h01L0021306000"])
def test_malformed_symbol_rejected(bad):
    with pytest.raises(ValueError):
        B.to_readable(bad)


def test_sha_mismatch_stops(tmp_path):
    m = json.loads(B.MANIFEST.read_text(encoding="utf-8"))
    m["files"][0]["sha256"] = "0" * 64
    bad = tmp_path / "MANIFEST.json"
    bad.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(SystemExit, match="sha256"):
        B.build(B.SRC_DIR, bad)


def test_build_is_deterministic_and_matches_committed_table():
    rows = B.build()
    assert rows == B.build()
    committed = list(csv.DictReader(B.OUT.open(encoding="utf-8")))
    assert committed == rows


def test_no_blanket_subclass_equivalence():
    """H01L 은 세부 분류 단위로만 옮겨진다 — 서브클래스 전체를 가리키는 행은 없다."""
    rows = B.build()
    h01l = [r for r in rows if r["from_symbol"].startswith("H01L")]
    assert h01l and all("/" in r["from_symbol"] and "/" in r["to_symbol"] for r in h01l)
    assert {r["to_symbol"][:4] for r in h01l} <= {"H01L", "H10B", "H10D", "H10F", "H10H", "H10K", "H10N", "H10P", "H10W"}
