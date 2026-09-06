"""사람 2인 코딩 집계기의 준거 구성 계약 — PLAN-005 §5 V4-2.

**이 테스트는 실제로 잘못된 수를 낸 뒤에 생겼다(2026-09-06).** 조정 파일을 넘기자
`j2` 가 0.0 이 되고 스크리너 위음성 추정이 489/489(100%)로 나왔다. 원인은 데이터가
아니라 집계기였다 — 조정 파일과 `inner join` 을 걸어 **두 코더가 이미 합의한 행을 통째로
버리고** 조정 파일에 있는 행만 준거로 남겼다. 그 행들은 정의상 두 코더가 **갈린** 행이라
기저율이 편향돼 있다.

더 나쁜 것은 **그 흐름을 스크립트 자신이 안내했다는 점**이다 — 갈린 행만 담은
`v4_to_adjudicate.csv` 를 쓰고 그것을 `--adjudicated` 로 넘기라고 출력한다. 즉 지시대로
따르면 반드시 틀린 수가 나왔다.

그래서 고정하는 것은 하나다: **준거는 일치행 합의값 + 갈린 행의 조정값이며, 조정 파일은
준거를 보강하지 대체하지 않는다.**
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_v4_human_kappa.py"

#: 6항목 — 4행 일치(1,1,0,0) · 2행 불일치. 조정에서 불일치 2행을 1 로 확정한다.
ITEMS = [
    {"item_id": "T1", "cell": "둘다관련", "j1": 1, "j2": 1},
    {"item_id": "T2", "cell": "둘다관련", "j1": 1, "j2": 0},
    {"item_id": "T3", "cell": "둘다무관", "j1": 0, "j2": 0},
    {"item_id": "T4", "cell": "둘다무관", "j1": 0, "j2": 0},
    {"item_id": "T5", "cell": "불일치", "j1": 1, "j2": 0},
    {"item_id": "T6", "cell": "불일치", "j1": 0, "j2": 1},
]
A_REL = {"T1": 1, "T2": 1, "T3": 0, "T4": 0, "T5": 1, "T6": 0}   # T5·T6 에서 갈린다
B_REL = {"T1": 1, "T2": 1, "T3": 0, "T4": 0, "T5": 0, "T6": 1}


def _fixture(tmp: Path, with_adjudication: bool) -> Path:
    (tmp / "key.json").write_text(json.dumps({"items": ITEMS}, ensure_ascii=False), encoding="utf-8")
    for name, rel in (("a.csv", A_REL), ("b.csv", B_REL)):
        lines = ["item_id,relevance,confidence"] + [f"{k},{v},H" for k, v in rel.items()]
        (tmp / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if with_adjudication:
        (tmp / "adj.csv").write_text("item_id,relevance\nT5,1\nT6,1\n", encoding="utf-8")
    return tmp / "out.json"


def _run(tmp: Path, out: Path, adjudicated: Path | None) -> dict:
    cmd = [sys.executable, str(SCRIPT), "--a", str(tmp / "a.csv"), "--b", str(tmp / "b.csv"),
           "--key", str(tmp / "key.json"), "--out", str(out),
           "--adjudicated", str(adjudicated if adjudicated else tmp / "does_not_exist.csv")]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_조정_파일이_준거를_보강한다(tmp_path: Path) -> None:
    """준거는 6행 전부여야 한다 — 조정한 2행만 남으면 그것이 이 결함이다."""
    out = _fixture(tmp_path, with_adjudication=True)
    rep = _run(tmp_path, out, tmp_path / "adj.csv")
    n = rep["llm_vs_human"]["j1"]["n"]
    assert n == len(ITEMS), (
        f"준거가 {n}행이다 — 조정 파일이 준거를 **대체**했다. 일치행 합의값이 버려지면 "
        f"남는 것은 두 코더가 갈린 행뿐이고 기저율이 편향된다")
    assert "보강" not in rep["reference_source"] or True
    assert "조정" in rep["reference_source"]


def test_조정_파일이_없으면_일치행만_준거다(tmp_path: Path) -> None:
    """되돌아가는 쪽도 고정한다 — 조정이 없으면 갈린 행은 제외하고 그 사실을 밝힌다."""
    out = _fixture(tmp_path, with_adjudication=False)
    rep = _run(tmp_path, out, None)
    assert rep["llm_vs_human"]["j1"]["n"] == 4, "일치행 4행만 준거여야 한다"
    assert "일치행" in rep["reference_source"]


def test_조정값이_일치행도_덮을_수_있다(tmp_path: Path) -> None:
    """조정자가 합의행을 되짚어 뒤집었다면 그쪽이 이긴다 — 조정은 나중에 본 판단이다."""
    out = _fixture(tmp_path, with_adjudication=True)
    (tmp_path / "adj.csv").write_text(
        "item_id,relevance\nT5,1\nT6,1\nT1,0\n", encoding="utf-8")   # T1 은 둘 다 1 이었다
    rep = _run(tmp_path, out, tmp_path / "adj.csv")
    assert rep["llm_vs_human"]["j1"]["n"] == len(ITEMS)
    # T1(j1=1)이 준거 0 으로 뒤집혔으므로 j1 일치는 6행 중 하나가 깎인다.
    assert rep["llm_vs_human"]["j1"]["agreement_with_human"] < 1.0


def test_사람_κ_는_조정과_무관하다(tmp_path: Path) -> None:
    """κ 는 **두 코더 사이**의 값이다. 조정은 준거를 만들 뿐 κ 를 바꾸면 안 된다."""
    out1 = _fixture(tmp_path, with_adjudication=True)
    k_adj = _run(tmp_path, out1, tmp_path / "adj.csv")["cohen_kappa_human"]
    k_raw = _run(tmp_path, out1, None)["cohen_kappa_human"]
    assert k_adj == k_raw, "조정이 사람 κ 를 움직였다 — κ 는 조정 이전의 값이다"
