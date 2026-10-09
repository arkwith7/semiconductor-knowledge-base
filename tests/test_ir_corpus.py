"""PLAN-006 T4 S1 — 코퍼스 진입점이 없는 파일·어긋난 파일을 거부하는가 (실패해야 할 입력)."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ir_corpus as IC  # noqa: E402


def _fixture(tmp_path: Path):
    p = tmp_path / "c.parquet"
    pd.DataFrame({"doc_id": ["kr_1", "us_2"], "is_candidate": [True, True]}).to_parquet(p)
    m = {"file": "c.parquet", "sha256": IC.sha256_of(p), "rows": 2}
    return p, m


def test_tracked_manifest_pins_sha_and_rows():
    m = IC.manifest()
    assert len(m["sha256"]) == 64 and m["rows"] == 41223 and m["storage"]["in_git"] is False


def test_verify_passes_on_matching_file(tmp_path):
    p, m = _fixture(tmp_path)
    assert IC.verify(p, m) == p
    assert len(IC.load(path=p, m=m)) == 2


def test_missing_file_stops(tmp_path):
    _, m = _fixture(tmp_path)
    with pytest.raises(SystemExit, match="없다"):
        IC.verify(tmp_path / "nope.parquet", m)


def test_sha_mismatch_stops(tmp_path):
    p, m = _fixture(tmp_path)
    with pytest.raises(SystemExit, match="sha256"):
        IC.verify(p, {**m, "sha256": "0" * 64})


def test_row_count_mismatch_stops(tmp_path):
    p, m = _fixture(tmp_path)
    with pytest.raises(SystemExit, match="행 수"):
        IC.load(path=p, m={**m, "rows": 3})


def test_fetch_from_copy_removes_bad_file(tmp_path):
    p, m = _fixture(tmp_path)
    base = tmp_path / "dst"
    assert IC.fetch(src=p, release=False, m=m, base=base).exists()
    bad = {**m, "sha256": "f" * 64}
    (base / m["file"]).unlink()
    with pytest.raises(SystemExit):
        IC.fetch(src=p, release=False, m=bad, base=base)
    assert not (base / m["file"]).exists()
