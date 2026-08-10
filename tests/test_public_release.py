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

from build_public_release import (  # noqa: E402
    PRIVATE_TOKEN, is_private_doc, scrub_abs_paths, scrub_dataset, strip_notebook,
)
from check_public_release import (  # noqa: E402
    LEGACY_SLUG_ALLOWED, build_probes, scan_boundary,
)
from config.namespaces import LEGACY_REPO_SLUG  # noqa: E402


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


def test_첫줄_토큰_문서는_비공개다():
    """**첫 줄에서만** 인정한다 — 본문에서 토큰을 언급하는 문서는 그것을 설명하는 것이지
    선언하는 것이 아니다. 실제로 그런 문서가 있다(readiness_review.md:53)."""
    assert is_private_doc(f"{PRIVATE_TOKEN}\n# 내부 문서\n".encode())
    assert is_private_doc(f"   {PRIVATE_TOKEN}   \n본문\n".encode())          # 앞뒤 공백
    assert not is_private_doc(f"# 공개 문서\n\n{PRIVATE_TOKEN}\n".encode())   # 셋째 줄
    assert not is_private_doc(f"> 첫 줄에 `{PRIVATE_TOKEN}` 를 단다\n".encode())  # 인용문
    assert not is_private_doc(b"")


def test_검사기가_트리의_토큰_문서를_잡는다(tmp_path):
    """생성기가 걸러도 **손으로 만든 트리**가 있다. 실패해야 할 입력이 실패하는가."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "internal.md").write_text(
        f"{PRIVATE_TOKEN}\nCONFIDENTIAL 가격표\n", encoding="utf-8")
    (tmp_path / "docs" / "public.md").write_text(
        f"비공개 문서는 첫 줄에 `{PRIVATE_TOKEN}` 를 단다.\n", encoding="utf-8")
    private, abs_hits, legacy = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert private == ["docs/internal.md"]     # 규약을 **설명**하는 문서는 통과한다
    assert abs_hits == []
    assert legacy == []


def test_검사기가_옛_리포_URL_을_잡는다(tmp_path):
    """R3 회귀 — 리포명을 바꾼 뒤 누가 옛 URL 을 다시 심으면 공개 첫날 404 가 된다.
    실패해야 할 입력이 실패하는가, 그리고 **인용 허용 파일은 통과하는가.**"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "new.md").write_text(
        f"소스: https://github.com/arkwith7/{LEGACY_REPO_SLUG}\n", encoding="utf-8")
    (tmp_path / "docs" / "clean.md").write_text(
        "소스: https://github.com/arkwith7/sdkb-dataset\n", encoding="utf-8")
    _, _, legacy = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert [h["file"] for h in legacy] == ["docs/new.md"]

    # 허용 목록의 파일은 그 슬러그를 **인용하는 것이 일**이다 — F3 의 증거다.
    allowed = tmp_path / next(iter(LEGACY_SLUG_ALLOWED))
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text(f"F3 의 증거: …/{LEGACY_REPO_SLUG}/…\n", encoding="utf-8")
    _, _, legacy2 = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert [h["file"] for h in legacy2] == ["docs/new.md"]


def test_URL_의_home_은_스크럽되지_않는다():
    """실측 회귀 — 추적 파일 둘이 URL 안에 `/home/` 을 담는다
    (irds.ieee.org/home/… · horiba.com/kr/horiba-stec/home/). 지우면 발행된 링크가 죽는다."""
    keep = b'{"url": "https://irds.ieee.org/home/how-to-download-irds"}'
    out, n = scrub_abs_paths(keep)
    assert (out, n) == (keep, 0)

    # 리터럴로 적으면 **이 테스트 파일 자신이** 검사기에 걸린다 — 조립해서 만든다.
    abs_path = "/" + "home/u/Dev/private-repo/ids.txt"
    out, n = scrub_abs_paths(f'{{"input_ids": "{abs_path}"}}'.encode())
    assert n == 1
    assert out == b'{"input_ids": "ids.txt"}'   # 경로는 지우되 **어떤 파일인지는 남긴다**


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
