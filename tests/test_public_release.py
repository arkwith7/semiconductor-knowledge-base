"""공개본 생성기·검사기 회귀 테스트 (CR-015).

**왜 테스트가 필요한가.** 이 경로의 실수는 되돌릴 수 없다 — 공개된 커밋은 지워도 포크·
캐시·PR ref 로 남는다. 그래서 "비웠다"를 눈으로 확인하지 않고 기계로 고정한다.

세 가지를 고정한다:
  ① 원문 세 필드는 **값만** 비고 **키·구조는 남는다**(소비자 코드가 깨지지 않는다)
  ② 남기기로 한 서지(title·ipc·date·식별자·ground_truth_*)는 **그대로** 있다
  ③ 지문 검사기가 **누출을 실제로 잡는다** — 통과만 확인하면 항상 통과하는 검사기도 통과한다
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_public_release import scrub_dataset, strip_notebook  # noqa: E402
from check_public_release import build_probes  # noqa: E402


def _record() -> dict:
    long_ko = "반도체 기판 위에 하드마스크 층을 형성하고 극자외선 노광으로 패터닝하는 방법에 관한 것으로서 " * 3
    return {
        "target_patent": {
            "application_number": "1020227033671",
            "title": "EUV 패터닝의 결함 감소를 위한 다층 하드마스크",
            "abstract": "초록 " + long_ko,
            "ipc": "H10P 50/28|C23C 16/448",
            "date": "2022.09.27",
            "claim1": "1. 청구항 " + long_ko,
            "claims_full": [
                {"claim_no": 1, "depends_on": [], "text": "1. 청구항 " + long_ko},
                {"claim_no": 2, "depends_on": [1], "text": "2. 제1항에 있어서 " + long_ko},
            ],
            "family": {"publication_numbers": ["US11xxxxx"], "source": "kipris"},
        },
        "ground_truth_examiner": ["KR1020190085654 A"],
        "ground_truth_all": ["KR1020190085654 A", "US20190348292 A1"],
        "meta": {"source": "kipris_plus_api"},
    }


@pytest.fixture()
def scrubbed() -> tuple[dict, dict]:
    raw = (json.dumps(_record(), ensure_ascii=False) + "\n").encode("utf-8")
    out, stats = scrub_dataset(raw)
    return json.loads(out.decode("utf-8").strip()), stats


def test_원문_세_필드가_값만_빈다(scrubbed):
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert tp["abstract"] == ""
    assert tp["claim1"] == ""
    assert [c["text"] for c in tp["claims_full"]] == ["", ""]


def test_스키마와_청구항_구조는_남는다(scrubbed):
    """항을 지우면 ingest_rejected_patents 가 세는 항수·보유 플래그가 거짓이 된다."""
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert "abstract" in tp and "claim1" in tp          # 키 삭제가 아니라 값 비우기
    assert [c["claim_no"] for c in tp["claims_full"]] == [1, 2]
    assert tp["claims_full"][1]["depends_on"] == [1]


def test_서지와_정답은_그대로다(scrubbed):
    """title 은 서지이며 kipris_biblio.parquet 에 이미 커밋돼 있다 — 비우면 손실만 난다."""
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert tp["title"] == "EUV 패터닝의 결함 감소를 위한 다층 하드마스크"
    assert tp["ipc"] and tp["date"] and tp["application_number"]
    assert rec["ground_truth_examiner"] == ["KR1020190085654 A"]
    assert len(rec["ground_truth_all"]) == 2


def test_비운_건수를_센다(scrubbed):
    _, stats = scrubbed
    assert stats == {"rows": 1, "abstract": 1, "claim1": 1, "claims_full_texts": 2}


def test_노트북_출력이_제거된다():
    nb = {"cells": [{"cell_type": "code", "execution_count": 3,
                     "outputs": [{"output_type": "stream", "text": ["초록 : ..."]}],
                     "source": []}],
          "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    out, n = strip_notebook((json.dumps(nb) + "\n").encode("utf-8"))
    got = json.loads(out.decode("utf-8"))
    assert n == 1
    assert got["cells"][0]["outputs"] == []
    assert got["cells"][0]["execution_count"] is None


def test_검사기_지문이_누출을_잡는다(tmp_path):
    """통과만 확인하면 항상 통과하는 검사기도 통과한다 — 잡는 쪽을 고정한다."""
    canonical = tmp_path / "canonical.jsonl"
    canonical.write_text(json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")
    probes, _ = build_probes(canonical)
    assert probes, "지문이 하나도 안 나오면 검사기는 아무것도 못 잡는다"
    leaked = _record()["target_patent"]["abstract"]
    assert any(p in leaked for _, _, p in probes)


def test_남기는_필드와_겹치는_지문은_버린다(tmp_path):
    """초록이 제목을 되풀이하는 특허가 있다 — 그 지문은 누출과 정상 발행을 구분하지 못한다."""
    rec = _record()
    title = "가" * 200
    rec["target_patent"]["title"] = title
    rec["target_patent"]["abstract"] = title
    canonical = tmp_path / "canonical.jsonl"
    canonical.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    probes, dropped = build_probes(canonical)
    assert dropped >= 1
    assert all(field != "abstract" for _, field, _ in probes)
