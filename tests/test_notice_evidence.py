"""통지서 근거 파서의 계약을 고정한다 — PLAN-005 §10 (단계 2-A) · §20.17 교정 (2026-09-30).

고정하는 것.

  ① **관청별 정규화.** 미채움 심사관 간선의 최대 원인은 콜론이 아니라 정규화 실패였다
     (콜론형 정의줄 350줄 · 간선 235건). 출력은 간선의 KIPRIS 식별자 형식이어야 한다 —
     claim-features A-Box 가 `cited_map` 을 정확 일치로 조회한다.
  ② **기존 정규화 출력 불변.** 보완 규칙은 기존 규칙 뒤에만 둔다.
  ③ **대상 청구항.** `청구항 제N항`(6,630회) · `N 내지 M`(927) · `N~M`(250) · 인용문헌 문맥 제외.
  ④ **첨부 목록은 절이 아니다.** 마지막 절이 `[첨 부]` 목록을 삼켜 §42 간선이 2 → 163 이 된
     사고를 고정한다. 라벨 참조는 문서 전체의 **유일한** 정의로만 해소한다.
  ⑤ **손실 가드.** 기존 근거가 줄거나 바뀌면 `--apply` 가 멈춘다(동결 예외 1건 제외).
  ⑥ **부착만 하는 경로(§20.18).** `--edges-only` 는 간선 말고는 아무것도 쓰지 않고, 손실이면 간선도 쓰지 않으며, 멱등이다.

전부 합성 문자열이다 — 원천 통지서에는 성명이 있어 테스트에 싣지 않는다(§1-5).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_notice_evidence import (  # noqa: E402
    CANON, LOSS_EXCEPTIONS, _gate_result, assert_additive, attach_edges_only, cited_in_section, collapse_rows, edge_delta,
    label_definitions, normalize_cited, parse_claim_refs, parse_notice, subclause_of,
)


# ── ① ② 정규화 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, want", [
    # 기존 규칙 — 출력이 바뀌면 안 된다
    ("공개특허공보 제10-2015-0109288호(2015.09.30.)", "KR-P-1020150109288"),
    ("등록특허공보 제10-1234567호(2013.01.02.)", "KR-G-1234567"),
    ("일본 공개특허공보 특개2005-123456호(2005.05.12.)", "JP-P-2005123456"),
    ("미국 특허공보 US 7118954 B2(2006.10.10.)", "US-G-7118954"),
    # 교정 보완
    ("국제공개공보 WO2017/138166(2017.08.17.)", "WO-P-2017138166"),
    ("일본 공표특허공보 특표2015-533029호(2015.11.19.)", "JP-P-2015533029"),
    ("일본 특허공보 특허 제 5102191호(2012.12.19.)", "JP-G-5102191"),
    ("중국특허공개공보 102703740(2012.10.03.)", "CN-P-102703740"),
    ("유럽 특허출원공개공보 EP2312621(2011.04.20.)", "EP-P-02312621"),
    ("공개특허 제2003-12345호(2003.02.14.)", "KR-P-1020030012345"),
    ("공개실용신안공보 제20-2015-0001688호(2015.05.01.)", "KR-G-2020150001688"),
    ("미국공개특허공보 2010/0133646호(2010.06.03.)", "US-P-20100133646"),
    ("미국특허공보 제7118954호(2006.10.10. 공개)", "US-G-07118954"),
])
def test_normalize(raw, want):
    assert normalize_cited(raw) == want


def test_normalize_rejects_prose():
    assert normalize_cited("본 발명은 반도체 장치에 관한 것이다") is None


# ── 인용 인식 ─────────────────────────────────────────────────────────────
def test_cited_forms():
    seg = ("이 출원은 특허법 제29조제2항에 따라 특허를 받을 수 없습니다.\n"
           "인용발명 1: 공개특허공보 제10-2015-0109288호(2015.09.30.)\n"
           "비교대상발명2 국제공개공보 WO2017/138166(2017.08.17.)\n"
           "일본 공표특허공보 특표2015-533029호(2015.11.19.)\n")
    f = cited_in_section(seg)
    assert f == {"KR-P-1020150109288": "colon", "WO-P-2017138166": "label",
                 "JP-P-2015533029": "unlabeled"}


def test_two_labels_on_one_line_are_split():
    seg = "인용발명1: 공개특허공보 제10-2015-0109288호, 인용발명2: 중국특허공개공보 102703740\n"
    assert set(cited_in_section(seg)) == {"KR-P-1020150109288", "CN-P-102703740"}


def test_own_application_is_excluded():
    seg = "공개특허공보 제10-2015-0109288호\n"
    assert cited_in_section(seg, app="1020150109288") == {}


# ── ③ 대상 청구항 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("seg, want", [
    ("청구항 1, 3", [1, 3]),
    ("청구항 제2항", [2]),
    ("청구항 제1항 내지 제4항", [1, 2, 3, 4]),
    ("청구항 2~5", [2, 3, 4, 5]),
    ("청구항 1 및 청구항 7", [1, 7]),
    ("청구항 1 내지 3, 6", [1, 2, 3, 6]),
    ("청구항 1은 인용발명 1의 청구항 9와 같다", [1]),     # 인용문헌의 청구항은 뺀다
    ("청구항 5 내지 2", [2, 5]),                          # 거꾸로 된 범위는 전개하지 않는다
    ("청구항 1 내지 900", [1, 900]),                      # 폭 상한(200) 초과는 전개하지 않는다
    ("해당 없음", []),
])
def test_claim_refs(seg, want):
    assert parse_claim_refs(seg) == want


def test_subclause():
    assert subclause_of("특허법 제29조제1항제2호에 해당") == "2"
    assert subclause_of("제 29 조 제 1 항 제1호 및 제29조제1항제2호") == "1|2"
    assert subclause_of("특허법 제29조제1항에 해당") == ""


# ── ④ 첨부 목록 · 라벨 해소 ───────────────────────────────────────────────
NOTICE = """머리말
[구체적인 거절이유]
1. 이 출원의 청구항 1은 특허법 제42조제4항제2호에 따라 불명확합니다.
2. 이 출원의 청구항 1은 인용발명 1에 의하여 쉽게 발명할 수 있으므로 특허법 제29조제2항에 따라 특허를 받을 수 없습니다.
3. 이 출원의 청구항 2는 표현이 불명확하여 특허법 제42조제4항제2호에 위배됩니다.
[첨 부]
인용발명 1: 일본 공표특허공보 특표2015-533029호(2015.11.19.)
중국특허공개공보 102703740(2012.10.03.)
"""


def test_attachment_list_is_not_part_of_last_section():
    secs = parse_notice(NOTICE)
    by = {s["section"]: s for s in secs}
    # 첨부 목록의 번호가 마지막(§42) 절에 붙지 않는다
    assert by[3]["legal_bases"] == ["§42"] and by[3]["cited_ids"] == []
    # 라벨 참조는 첨부 목록의 유일한 정의로 해소된다
    assert by[2]["cited_ids"] == ["JP-P-2015533029"]
    assert by[2]["cite_forms"] == {"JP-P-2015533029": "reference"}


def test_ambiguous_label_is_not_resolved():
    body = ("인용발명 1: 공개특허공보 제10-2015-0109288호\n"
            "인용발명 1: 중국특허공개공보 102703740\n"
            "인용발명 2: 국제공개공보 WO2017/138166\n")
    assert label_definitions(body) == {("인용발명", 2): "WO-P-2017138166"}


# ── 정본 행 모으기 ────────────────────────────────────────────────────────
def _row(section, claims, form, sub="", file="a.txt"):
    return {"application_number": "1", "cited_doc_id": "X", "legal_basis": "§29①",
            "section": section, "target_claims": claims, "source_file": file,
            "subclause": sub, "cite_form": form}


def test_collapse_unions_claims_and_keeps_first_section():
    df = collapse_rows([_row(1, [1], "unlabeled", "2"), _row(3, [4, 5], "colon", "1")])
    r = df.iloc[0]
    assert (r.section, r.target_claims, r.subclause, r.cite_form) == (1, "1,4,5", "1|2", "colon")


# ── ⑤ 손실 가드 ───────────────────────────────────────────────────────────
def test_edge_delta_counts():
    d = edge_delta(["", "§29②", "§29②", "§29①|§29②", ""],
                   ["§29②", "§29②", "§29①|§29②", "§29②", ""])
    assert (d["newly_filled"], d["unchanged"], d["extended"], d["lost_or_changed"]) == (1, 1, 1, 1)


def test_loss_blocks_apply():
    d = edge_delta(["§29②"], ["§29①"])
    with pytest.raises(SystemExit):
        assert_additive(d)


def test_frozen_exception_passes_guard_and_nothing_else_does():
    (app, cid), = LOSS_EXCEPTIONS
    d = edge_delta(["§42", "§42"], ["§29②", "§29②"], [(app, cid), (app, "KR-P-0")])
    assert d["changed_by_exception"] == 1 and d["lost_or_changed"] == 1
    with pytest.raises(SystemExit):
        assert_additive(d)
    assert_additive(edge_delta(["§42"], ["§29②"], [(app, cid)]))


def test_gate_reads_sheet_with_withheld_rows(tmp_path):
    # 빈 칸이 섞이면 열이 실수형이 된다 — 그래도 1/0 을 읽고, 빈 칸은 보류로 센다
    p = tmp_path / "s.csv"
    p.write_text("correct,note\n1,\n1,\n,보류\n0,문헌다름\n", encoding="utf-8-sig")
    g = _gate_result(p, "t")
    assert (g["n"], g["correct"], g["withheld"], g["status"]) == (3, 2, 1, "미달")


def test_parse_is_deterministic():
    assert parse_notice(NOTICE) == parse_notice(NOTICE)


# ── 산출물 계약 (빌드 산출물이 있을 때만) ─────────────────────────────────
@pytest.mark.skipif(not CANON.exists(), reason="정본 parquet 미생성")
def test_canonical_contract():
    c = pd.read_parquet(CANON)
    assert list(c.columns) == ["application_number", "cited_doc_id", "legal_basis", "section",
                               "target_claims", "source_file", "subclause", "cite_form"]
    assert not c.duplicated(["application_number", "cited_doc_id", "legal_basis"]).any()
    assert set(c.cite_form) <= {"colon", "label", "unlabeled", "reference"}
    assert (c.loc[c.legal_basis != "§29①", "subclause"] == "").all()
    assert set(c.subclause) <= {"", "1", "2", "1|2"}


# ── ⑥ 부착만 하는 경로 ────────────────────────────────────────────────────
def _canon_and_edges(tmp_path, prior: list[str] | None = None):
    canon = pd.DataFrame({"application_number": ["1020200000001", "1020200000001", "1020200000002"],
                          "cited_doc_id": ["KR-P-1020150000001", "KR-P-1020150000001", "US-G-07118954"],
                          "legal_basis": ["§29②", "§29①", "§29②"]})
    ed = pd.DataFrame({"target_patent_id": ["patent:kr_1020200000001", "patent:kr_1020200000002",
                                            "patent:kr_1020200000002", "patent:kr_1020200000003"],
                       "cited_doc_id": ["KR-P-1020150000001", "US-G-7118954", "US-G-7118954", "KR-P-0"],
                       "source_type": ["examiner", "examiner", "evidence_v2", "examiner"],
                       "legal_basis": ["", "", "§29②", ""]})
    if prior is not None:
        ed["legal_bases"] = prior
    cp, ep = tmp_path / "canon.parquet", tmp_path / "edges.parquet"
    canon.to_parquet(cp, index=False)
    ed.to_parquet(ep, index=False)
    return cp, ep


def test_edges_only_attaches_sets_and_writes_nothing_else(tmp_path):
    cp, ep = _canon_and_edges(tmp_path)
    canon_bytes = cp.read_bytes()
    d = attach_edges_only(cp, ep)
    got = pd.read_parquet(ep)
    # 다중근거는 집합 · 자릿수 채움 차이(US-G-07118954 대 7118954)는 흡수 · examiner 가 아닌 간선은 빈 값
    assert list(got.legal_bases) == ["§29①|§29②", "§29②", "", ""]
    assert (d["newly_filled"], d["lost_or_changed"]) == (2, 0)
    assert cp.read_bytes() == canon_bytes
    assert sorted(x.name for x in tmp_path.iterdir()) == ["canon.parquet", "edges.parquet"]


def test_edges_only_is_idempotent(tmp_path):
    cp, ep = _canon_and_edges(tmp_path)
    attach_edges_only(cp, ep)
    once = ep.read_bytes()
    d = attach_edges_only(cp, ep)
    assert ep.read_bytes() == once and d["unchanged"] == 2 and d["newly_filled"] == 0


def test_edges_only_refuses_loss_and_leaves_edges_untouched(tmp_path):
    cp, ep = _canon_and_edges(tmp_path, prior=["§42", "", "", "§29①"])     # 정본에 없는 기존 근거 2건
    before = ep.read_bytes()
    with pytest.raises(SystemExit):
        attach_edges_only(cp, ep)
    assert ep.read_bytes() == before
