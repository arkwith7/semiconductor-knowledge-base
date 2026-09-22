"""R1 통지서 스크럽의 계약을 고정한다 — PLAN-005 §20 R1 재정향.

고정하는 것.

  ① **심은 성명이 반드시 지워지는가.** 규칙마다 합성 성명을 넣고 산출에 남지 않음을 확인한다.
  ② **가리는 규칙이 놓친 형태를 잔여 검출기가 무는가.** 검출기가 치환 규칙과 같은 패턴이면
     검사가 되지 않는다 — 치환이 못 잡는 형태를 넣어 파일이 **제외**되는지 본다.
  ③ 표지가 없으면 추측하지 않고 제외하는가 · 줄번호가 원문 좌표와 같은가 · 결정적인가.
  ④ **train 밖 출원이 산출에 없는가** · 원천 sha 가 다르면 죽는가.

성명은 전부 지어낸 합성값이다. 실물 통지서를 픽스처로 쓰지 않는다(§1-5).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scrub_notice_excerpts as sn  # noqa: E402

FAKE = "홍길동"


def doc(body: str) -> str:
    """실물 통지서의 골격(표지 순서)만 따른 합성 문서."""
    return (
        "발송번호: 9-5-2020-000000000 수신 :\n"
        f"출 원 인 {FAKE}\n"
        "[심사결과]\n"
        "[구체적인 거절이유]\n"
        f"{body}\n"
        "[첨 부]\n"
        f"특허청 반도체심사과 심사관 {FAKE}\n"
    )


def scrubbed_text(body: str) -> tuple[str, str | None]:
    rows, _, reason = sn.scrub_document(doc(body))
    return ("\n".join(t for _, t in rows) if rows else ""), reason


# ── ① 심은 성명이 지워진다 ──
@pytest.mark.parametrize("body", [
    f"1. 이 출원은 대리인 {FAKE} 가 제출한 의견서에도 불구하고",
    f"대리인 변리사 {FAKE} 의 주장은 받아들일 수 없다.",
    f"담당자: {FAKE}",
    f"문의: test.user@example.com 042-481-0000",
    "의견서 제출인(특허고객번호: 123456789012)의 주장",   # 줄머리형은 R2 가 줄째 지운다 — 문장 속 형태로 R4 를 건다
    "인용발명 3 (Kim, H. et al., J. Appl. Phys.)",
    "Smith et al. 은 이를 개시한다.",
])
def test_planted_pii_is_removed(body):
    out, reason = scrubbed_text(body)
    assert reason is None, reason
    for leaked in (FAKE, "test.user", "@", "042-481-0000", "123456789012", "Kim, H.", "Smith et al"):
        assert leaked not in out


def test_header_label_line_is_dropped_whole():
    rows, counts, reason = sn.scrub_document(doc("특허고객번호: 123456789012\n본문"))
    assert reason is None and [t for _, t in rows] == ["본문"]
    assert counts["R2_header_label"] == 1


def test_signature_and_page_furniture_lines_are_dropped():
    body = f"본문 첫 줄이다.\n- 2 -\n10-2020-0001234\n반도체심사과 심사관 {FAKE}\n본문 둘째 줄이다."
    rows, counts, reason = sn.scrub_document(doc(body))
    assert reason is None
    assert [t for _, t in rows] == ["본문 첫 줄이다.", "본문 둘째 줄이다."]
    assert counts["R2_page_marker"] == 1 and counts["R2_app_number_line"] == 1
    assert counts["R2_signature"] == 1


def test_window_excludes_header_and_footer_names():
    out, reason = scrubbed_text("거절이유 본문")
    assert reason is None and FAKE not in out and out == "거절이유 본문"


# ── ② 잔여 검출기가 문다 ──
@pytest.mark.parametrize("body", [
    f"심사관({FAKE})의 판단에 따르면",          # 괄호형 — R3 는 공백/콜론만 본다
    f"담당{FAKE}",                               # 붙여 쓴 줄끝형
    f"성명 {FAKE} 의 발명",                      # 이름표형
])
def test_residual_detector_excludes_what_masking_missed(body):
    rows, counts, reason = sn.scrub_document(doc(body))
    assert rows is None
    assert reason is not None and reason.startswith("residual:")
    assert any(k.startswith("residual_") for k in counts)


def test_residual_detector_is_not_the_masking_rule():
    # 같은 패턴이면 ②가 성립하지 않는다 — 가린 뒤 깨끗한 줄에서는 조용해야 한다.
    clean, _ = sn.scrub_line(f"대리인 {FAKE} 의 의견서")
    assert sn.residual_hits(clean) == []


# ── ③ 창 · 좌표 · 결정성 ──
def test_missing_markers_are_excluded_not_guessed():
    assert sn.scrub_document("본문만 있다\n[첨 부]\n")[2] == "no_window"
    assert sn.scrub_document("[구체적인 거절이유]\n본문\n")[2] == "no_window"


def test_line_numbers_are_source_coordinates():
    raw = doc("첫째\n\n셋째")
    rows, _, _ = sn.scrub_document(raw)
    lines = raw.split("\n")
    for n, t in rows:
        assert lines[n - 1].strip() == t


def test_deterministic_bytes():
    raw = doc(f"대리인 {FAKE} 가 Kim, H. 를 인용")
    a = sn.render(sn.scrub_document(raw)[0])
    b = sn.render(sn.scrub_document(raw)[0])
    assert a == b


# ── ④ 범위와 무결성 ──
def _fixture_tree(tmp_path: Path, bodies: dict[str, tuple[str, str]], tamper: str | None = None):
    """bodies: doc_id → (split, 통지서 본문)."""
    txt = tmp_path / "txt"
    txt.mkdir()
    index, files = {}, {}
    for doc_id, (_, body) in bodies.items():
        app = doc_id[len("kr_"):]
        stem = f"{app}_952000000000001"
        raw = doc(body).encode("utf-8")
        (txt / f"{stem}.txt").write_bytes(raw)
        index[app] = {"docs": [{"file": stem}]}
        sha = hashlib.sha256(raw).hexdigest()
        files[f"{stem}.txt"] = {"sha256": ("0" * 64 if doc_id == tamper else sha)}
    split_csv = tmp_path / "split.csv"
    with split_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "split"])
        for doc_id, (s, _) in bodies.items():
            w.writerow([doc_id, s])
    (tmp_path / "_index.json").write_text(json.dumps(index), encoding="utf-8")
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps({"dirs": {"opinion_notices/txt": {"files": files}}}), encoding="utf-8")
    return dict(split_path=split_csv, index_path=tmp_path / "_index.json",
                txt_dir=txt, manifest_path=tmp_path / "MANIFEST.json", verify_split=False)


def test_only_train_applications_are_produced(tmp_path):
    kw = _fixture_tree(tmp_path, {
        "kr_1000000000001": ("train", "훈련 본문"),
        "kr_1000000000002": ("dev", "개발 본문"),
        "kr_1000000000003": ("test", "봉인 본문"),
        "kr_1000000000004": ("test_b", "봉인 본문"),
    })
    m = sn.run(tmp_path / "out", **kw)
    assert m["documents_in_scope"] == 1 and m["produced"] == 1
    assert {e["application"] for e in m["files"]} == {"1000000000001"}
    assert sorted(p.name for p in (tmp_path / "out").glob("*.txt")) == ["1000000000001_952000000000001.txt"]


def test_index_listing_same_file_twice_is_counted_once():
    split_map = {"kr_1000000000001": "train"}
    index = {"1000000000001": {"docs": [{"file": "1000000000001_9"}, {"file": "1000000000001_9"}]}}
    assert sn.scope_documents(split_map, index) == [("1000000000001", "1000000000001_9")]


def test_source_sha_mismatch_aborts(tmp_path):
    kw = _fixture_tree(tmp_path, {"kr_1000000000001": ("train", "본문")}, tamper="kr_1000000000001")
    with pytest.raises(SystemExit):
        sn.run(tmp_path / "out", **kw)


def test_two_runs_are_byte_identical(tmp_path):
    kw = _fixture_tree(tmp_path, {
        "kr_1000000000001": ("train", f"대리인 {FAKE} 가 제출"),
        "kr_1000000000002": ("train", "Smith et al. 개시"),
    })
    sn.run(tmp_path / "a", **kw)
    sn.run(tmp_path / "b", **kw)
    for p in sorted((tmp_path / "a").iterdir()):
        assert p.read_bytes() == (tmp_path / "b" / p.name).read_bytes()


def test_manifest_carries_no_source_text(tmp_path):
    kw = _fixture_tree(tmp_path, {"kr_1000000000001": ("train", f"대리인 {FAKE} 고유본문문장")})
    sn.run(tmp_path / "out", **kw)
    m = (tmp_path / "out" / "_manifest.json").read_text(encoding="utf-8")
    assert FAKE not in m and "고유본문문장" not in m
