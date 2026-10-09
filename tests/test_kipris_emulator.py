"""PLAN-006 T4 S3 — 에뮬레이터 명세(문법·일치·필드·IPC·판 대응)의 계약. 실패해야 할 입력 포함."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kipris_emulator as K  # noqa: E402


@pytest.fixture(scope="module")
def emu(tmp_path_factory):
    conc = tmp_path_factory.mktemp("c") / "conc.csv"
    conc.write_text(
        "from_symbol,from_version,from_modification,to_symbol,to_version,to_modification,"
        "default_reclassification,revision_project,source_file\n"
        "H01L21/306,20250101,d,H10P50/20,20260101,n,Y,X,f\n", encoding="utf-8")
    df = pd.DataFrame({
        "doc_id": ["d1", "d2", "d3", "d4", "q"],
        "is_candidate": [True, True, True, True, True],
        "title": ["플라즈마 식각 장치", "Plasma etching apparatus", "sketch of wafer", "세정 방법", "질의"],
        "abstract": ["측벽 보호막을 형성한 후 식각", "high aspect ratio contact hole", "", "웨이퍼 세정", ""],
        "claims_full": ["", "a chamber", "", "", ""],
        "claims_independent": ["식각 챔버", "", "", "", ""],
        "ipc": [["H01L21/306"], ["H10P50/20"], ["C04B41-85"], ["H01J_37-32"], ["H01L21/306"]],
    })
    return K.Emulator(df, K.Concordance(conc))


@pytest.mark.parametrize("raw,norm", [
    ("H01J_37-32", "H01J37/32"), ("C04B41-85", "C04B41/85"), ("H01L21/306", "H01L21/306"),
    ("H01L21", "H01L21"), ("H01L", "H01L"), ("h10p 50/20", "H10P50/20"), ("XYZ", None), ("", None),
])
def test_norm_ipc(raw, norm):
    assert K.norm_ipc(raw) == norm


def test_precedence_and_binds_tighter_than_or(emu):
    # 식각 + (세정 * 웨이퍼) 로 읽힌다
    assert emu.run("식각+세정*웨이퍼") == ["d1", "d4"]


def test_parentheses_override(emu):
    assert emu.run("(식각+세정)*웨이퍼") == ["d4"]


def test_korean_partial_match(emu):
    assert emu.run("식") == ["d1"]           # "식각" 의 부분 — 형태소 경계를 보지 않는다
    assert emu.run("보호막") == ["d1"]


def test_ascii_word_start_prefix(emu):
    assert emu.run("etch") == ["d2"]          # etching 에 맞고 sketch 에는 안 맞는다
    assert "d3" in emu.run("sketch")


def test_phrase_and_not(emu):
    assert emu.run('"contact hole"') == ["d2"]
    assert emu.run("웨이퍼*!세정") == []
    assert emu.run("식각*!측벽") == []


def test_space_is_and(emu):
    assert emu.run("측벽 식각") == ["d1"]
    assert emu.run("측벽 세정") == []


def test_field_restriction(emu):
    assert emu.run("챔버", fields=("CL",)) == ["d1"]  # claims_full 이 비면 claims_independent
    assert emu.run("챔버", fields=("TI",)) == []


def test_ipc_concordance_expands_old_to_new(emu):
    assert emu.run("식각+etch", ipc=["H01L21/306"]) == ["d1", "d2"]
    assert emu.run("식각+etch", ipc=["H10P"]) == ["d1", "d2"]
    assert emu.run("식각+etch", ipc=["H01J"]) == []


def test_exclude_query_doc(emu):
    assert "q" not in emu.run("질의", exclude=("q",))


@pytest.mark.parametrize("bad", ["", "   ", "(식각", "식각)", "식각+", '""', "!식각", "*식각"])
def test_invalid_queries_rejected(emu, bad):
    with pytest.raises(ValueError):
        emu.run(bad)


def test_unknown_field_rejected(emu):
    with pytest.raises(ValueError):
        emu.run("식각", fields=("XX",))


def test_subgroup_is_exact_not_digit_prefix():
    assert K._ipc_prefix_match("H01L21/306", "H01L21/306")
    assert not K._ipc_prefix_match("H01L21/306", "H01L21/30")   # 숫자 접두는 계층이 아니다
    assert K._ipc_prefix_match("H01L21/306", "H01L21")
    assert not K._ipc_prefix_match("H01L210/1", "H01L21")
    assert K._ipc_prefix_match("H01L21/306", "H01L")
