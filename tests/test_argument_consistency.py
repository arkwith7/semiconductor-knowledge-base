"""논증층 일관성 검사(scripts/argument_consistency.py)의 계약 — PLAN-005 §20.23 c.

각 검사마다 **지정한 결함을 넣으면 잡고, 깨끗한 입력은 통과시키는지**를 본다(결함 주입). 이것은 그 결함을 잡는다는
증거일 뿐 공통 맹점이 없다는 증명이 아니다 — 알려진 맹점은 `test_known_blind_spot_*` 로 그 한계를 고정한다.
본문은 합성 문장이다(실물 통지서 발췌를 쓰지 않는다).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import argument_consistency as AC  # noqa: E402

D1, D2 = "KR-P-1020100012345", "KR-P-1020110054321"
DEFS = "인용발명 1 : 대한민국 공개특허공보 제10-2010-0012345호\n인용발명 2 : 대한민국 공개특허공보 제10-2011-0054321호\n"


def rec(claims, text, labels=None, how=None, rat=(), locs=None, summary="", key="k"):
    labels = labels if labels is not None else {D1: []}
    how = how if how is not None else {D1: [("definition", "인용발명", 1)]}
    return {"key": key, "claims": claims, "text": text, "labels": labels, "how": how, "rat": list(rat),
            "locs": locs or {}, "summary": summary, "sec_span": (0, 10_000)}


# ── C1 · C2 · C5 블록 ─────────────────────────────────────────────────
def test_c1_foreign_subject_caught_and_clean_passes():
    clean = "1. 청구항 1 발명은 인용발명 1과 동일합니다.\n따라서 청구항 1 발명은 신규성이 없습니다."
    assert AC.c1_claims(rec([1], clean)) == []
    bad = clean + "\n청구항 2 및 3 발명의 한정 구성들은 인용발명 1에 개시되어 있습니다."
    assert "C1_foreign_subject" in AC.c1_claims(rec([1], bad))


def test_c1_parent_and_cited_claims_are_not_subjects():
    t = ("1-4. 청구항 4 발명(청구항 3 인용)은 인용발명 1의 청구항 3에 개시된 구성과 같습니다.\n"
         "제4항(제3항의 종속항)의 한정은 인용발명 1(청구항 2~5, 단락 [0010] 참조)에 있습니다.")
    assert AC.c1_claims(rec([4], t)) == []


def test_c1_excess_claim_injection_is_caught():
    t = "1. 청구항 1 발명은 인용발명 1과 동일합니다."
    assert AC.c1_claims(rec([1], t)) == []
    assert "C1_excess_claim" in AC.c1_claims(rec([1, 7], t))        # 본문이 다루지 않는 청구항을 블록에 더했다


def test_c2_new_judgment_line_vs_sub_items_and_reference_targets():
    head = "2-2. 청구항 2 발명은 인용발명 1과 같습니다.\n"
    assert AC.c2_new_judgment(rec([2], head + "2-3. 청구항 3 발명은 인용발명 1로부터 쉽게 발명할 수 있습니다.")) == ["C2_new_judgment"]
    assert AC.c2_new_judgment(rec([2], head + "1) 인용발명 1과의 대비\n2) 인용발명 2와의 대비")) == []
    assert AC.c2_new_judgment(rec([18], "[청구항 18]\n2-9. 제18항(제17항의 제조방법으로 제조된 소자)은 동일합니다.")) == []


def test_c5_conclusion_outside_block():
    t = "1-6. 청구항 6 발명은 인용발명 1과 같습니다.\n"
    assert AC.c5_conclusion(rec([6], t + "따라서 청구항 6 발명은 진보성이 없습니다.")) == []
    assert AC.c5_conclusion(rec([6], t + "따라서 청구항 1 내지 6 발명은 진보성이 없습니다.")) == ["C5_conclusion"]
    assert AC.c5_conclusion(rec([19], "1-19. 청구항 19 발명은 같습니다.\n따라서 청구항 18 발명은 쉽게 발명할 수 있습니다.")) == ["C5_conclusion"]


# ── C3 · C4 문헌 ─────────────────────────────────────────────────────
def test_c3_label_gap_and_chemical_subscripts():
    t = "청구항 1 발명은 인용발명 1 내지 인용발명 3의 결합으로부터 쉽게 발명할 수 있습니다."
    how = {D1: [("definition", "인용발명", 1)], D2: [("definition", "인용발명", 3)]}
    assert "C3_label_gap" in AC.c3_documents(rec([1], t, labels={D1: [], D2: []}, how=how), {})
    assert AC.label_numbers_used("인용발명 1과 2의 결합이며 Al O\n2 3 막을 쓴다") == {1, 2}
    assert AC.label_numbers_used("인용발명 1-2 및 5, 혹은 인용발명 1-3 및 5") == {1, 2, 3, 5}
    assert AC.label_numbers_used("인용발명 1,\n2, 또는 3 에 의하여") == {1, 2, 3}          # 줄바꿈 · 이중 구분자(회귀 82행)


def test_c3_wrong_document_of_same_country_is_caught_when_defined():
    """같은 국가의 다른 문헌으로 라벨을 이은 경우 — 명시적 정의가 있으면 정의와 대조해 잡는다."""
    defs = AC.definitions(DEFS, "1020200000000")
    ok = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", labels={D1: []}, how={D1: [("definition", "인용발명", 1)]})
    assert AC.c3_documents(ok, defs) == []
    bad = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", labels={D2: []}, how={D2: [("definition", "인용발명", 1)]})
    assert "C3_definition_mismatch" in AC.c3_documents(bad, defs)


def test_known_blind_spot_same_country_without_definition():
    """정의가 통지서에 없으면 같은 국가의 다른 문헌으로 이어도 C3·C4 는 모른다(BLIND_SPOTS 3)."""
    bad = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", labels={D2: []}, how={D2: [("definition", "인용발명", 1)]})
    assert AC.c3_documents(bad, {}) == [] and AC.c4_country(bad, {}) == []
    assert any("같은 국가" in b for b in AC.BLIND_SPOTS)


def test_c3_definition_conflict_and_substitution():
    text = "인용발명 1 : 대한민국 공개특허공보 제10-2010-0012345호\n" + "가" * 50 + \
           "\n인용발명 1 : 대한민국 공개특허공보 제10-2011-0054321호\n"
    defs = AC.definitions(text, "1020200000000")
    r = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", how={D1: [("definition", "인용발명", 1)]})
    r["sec_span"] = (10_000, 20_000)                    # 이 판단의 절에는 정의가 없다 — 범위가 불명확하다
    assert "C3_definition_conflict" in AC.c3_documents(r, defs)
    sub = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", how={D1: [("single_section_document", "인용발명", 1)]})
    assert "C3_substitution" in AC.c3_documents(sub, AC.definitions(DEFS.replace("인용발명 1", "인용발명 2", 1), "1"))
    assert "C3_substitution" not in AC.c3_documents(sub, AC.definitions(DEFS, "1020200000000"))   # 정의가 확인해 준다


def test_c4_foreign_document_normalized_as_kr():
    text = "인용발명 1 : 미국 공개특허 2010-33878호\n"
    nid = "KR-P-1020100033878"                          # 정본 파서가 실제로 내는 잘못된 정규화
    r = rec([1], "청구항 1 발명은 인용발명 1과 같습니다.", labels={nid: []}, how={nid: [("definition", "인용발명", 1)]})
    assert AC.c4_country(r, AC.definition_windows(text, "1020200000000")) == ["C4_country"]
    back = "미국 공개특허 2010-33878호(이하 '인용발명 1')\n"
    assert AC.c4_country(r, AC.definition_windows(back, "1020200000000")) == ["C4_country"]
    assert AC.c4_country(rec([1], "x"), AC.definition_windows(DEFS, "1020200000000")) == []


# ── C6 좌표 ─────────────────────────────────────────────────────────
LOC_TEXT = "청구항 1 발명은 인용발명 1의 단락 [0071] 내지 [0073] 및 도 4A,B 에 개시되어 있습니다."
LOC_OK = {D1: {("Paragraph", "[0071]~[0073]"), ("Figure", "도4A"), ("Figure", "도4B")}}


def test_c6_content_comparison_catches_each_injected_defect():
    assert AC.c6_locators(rec([1], LOC_TEXT, locs=LOC_OK)) == []
    dropped = {D1: LOC_OK[D1] - {("Figure", "도4B")}}
    assert AC.c6_locators(rec([1], LOC_TEXT, locs=dropped)) == ["C6_locators"]            # 좌표 하나 누락
    ends = {D1: {("Paragraph", "[0071]"), ("Paragraph", "[0073]"), ("Figure", "도4A"), ("Figure", "도4B")}}
    assert AC.c6_locators(rec([1], LOC_TEXT, locs=ends)) == ["C6_locators"]               # 범위를 양 끝으로
    other = {D2: LOC_OK[D1]}
    assert AC.c6_locators(rec([1], LOC_TEXT, labels={D1: [], D2: []}, locs=other)) == ["C6_locators"]   # 다른 문헌에 귀속
    shifted = {D1: {("Paragraph", "[0071]~[0074]"), ("Figure", "도4A"), ("Figure", "도4B")}}
    assert AC.c6_locators(rec([1], LOC_TEXT, locs=shifted)) == ["C6_locators"]            # 번호 틀림


def test_c6_applicant_side_and_non_figures_are_not_expected():
    t = "본원 청구항 1의 단락 [0010] 은 온도 300℃ 에서 형성하는 것이고, 인용발명 1의 도 2 참조."
    assert AC.c6_locators(rec([1], t, locs={D1: {("Figure", "도2")}})) == []


def test_c6_list_label_is_unattributed():
    t = "청구항 1 발명은 인용발명 1, 2의 도 3 에 개시되어 있습니다."
    r = rec([1], t, labels={D1: [], D2: []}, how={D1: [("definition", "인용발명", 1)], D2: [("definition", "인용발명", 2)]})
    assert AC.c6_locators(r) == ["C6_locators"]           # 나열 뒤 좌표는 어느 문헌 것인지 모른다 — 집합이 불완전


# ── C7 논거 (종류별) ─────────────────────────────────────────────────
def test_c7_scope_is_per_kind_and_partial_is_caught():
    t = ("청구항 1, 5, 6 발명은 인용발명 1과 같으며 이는 단순한 설계 변경에 불과합니다.\n\n"
         "청구항 5, 6 발명은 그 효과도 통상의 기술자가 예측할 수 있는 정도입니다.")
    out = AC.c7_rationale(rec([1, 5, 6], t, rat=["DesignChoice", "PredictableEffect"]))
    assert out == {"PredictableEffect": ["C7_scope_partial"]}          # 설계 변경은 전체 · 효과 예측만 일부


def test_c7_parallel_subjects_with_dependency_parentheses():
    t = ("제3, 5항(제1항의 종속항), 제4항(제3항의 종속항) 및 제8항(제6항의 종속항) 발명의 한정은 "
         "통상의 기술자가 용이하게 설계 변경할 수 있는 사항입니다.")
    assert AC.c7_rationale(rec([3, 4, 5, 8], t, rat=["DesignChoice"])) == {}
    assert AC.c7_rationale(rec([3, 4, 5], t, rat=["DesignChoice"])) == {"DesignChoice": ["C7_scope_mismatch"]}


def test_c7_heading_line_is_not_the_subject():
    t = "1-2. 청구항 2-5\n(가) 청구항 2-4의 한정 사항은 단순한 설계 변경에 불과합니다."
    assert AC.c7_rationale(rec([2, 3, 4], t, rat=["DesignChoice"])) == {}


def test_check_notice_shape():
    r = rec([1], "1. 청구항 1 발명은 인용발명 1과 동일합니다.")
    out = AC.check_notice(DEFS, "1020200000000", [r])
    assert set(out["k"]) == {"block", "locators", "rationale"} and out["k"]["block"] == []


def test_c6_figure_hyphen_is_ambiguous_and_held():
    """`도면 1-5, 1-6` 의 하이픈은 범위인지 복합 도면 번호인지 원문이 말하지 않는다 — 추출기도 검사도 읽지 않고, 검사는 보류한다.
    (둘 다 무시만 하면 둘이 같이 놓친다.)"""
    t = "청구항 1 발명은 인용발명 1의 도면 1-5, 1-6 에 개시되어 있습니다."
    assert AC.c6_locators(rec([1], t, locs={D1: {("Figure", "도1")}})) == ["C6_locators"]


def test_c1_parallel_subject_chain_catches_dropped_first_member():
    """`제2항(제1항 인용) 및 제3항(제2항 인용)의 패턴 구조는` — 2 는 3 의 부모이기도 하지만 여기서는 주어다. 블록이 3 만 담으면 잡는다."""
    t = "2. 제2항(제1항 인용) 및 제3항(제2항 인용)의 패턴 구조는 인용발명 1에 기재되어 있습니다."
    assert "C1_foreign_subject" in AC.c1_claims(rec([3], t))
    assert AC.c1_claims(rec([2, 3], t)) == []


# ── §20.24 추가 검사 ─────────────────────────────────────────────────
def test_c9_fragment_without_judgment_is_held():
    frag = "1-1. 청구항 1 발명과 인용발명 1을 비교해 보면 아래 표 1과 같습니다.\n<표 1>\n인용발명 1\n"
    assert AC.c9_judgment_statement(rec([1], frag)) == ["C9_no_judgment"]
    assert AC.c9_judgment_statement(rec([1], frag + "양 발명은 실질적으로 동일합니다.")) == []


def test_c10_distinct_openings_vs_per_document_sub_items():
    merged = "2-1. 본원의 특허청구 제1항은 A 를 포함한다.\n2-2. 본원의 특허청구 제2~4항은 B 를 더한다.\n"
    assert AC.c10_multiple_openings(rec([1, 2, 3, 4], merged)) == ["C10_multiple_openings"]
    title = "나. 청구항 2 내지 10 발명\n1) 청구항 2 발명의 합금 비중은 인용발명 2와 같다.\n"
    assert AC.c10_multiple_openings(rec(list(range(2, 11)), title)) == ["C10_title_range"]     # 제목 범위가 블록에 남음
    assert AC.c10_multiple_openings(rec([2], title)) == []                                      # 하위 항목으로 갈라졌으면 통과
    per_doc = "1. 청구항 1\n1) 인용발명 1과의 대비\n2) 인용발명 2와의 대비\n"
    assert AC.c10_multiple_openings(rec([1], per_doc)) == []
    same = "1. 청구항 1 발명\n(1) 청구항 1 발명과 인용발명 1의 대비는 동일하다.\n"
    assert AC.c10_multiple_openings(rec([1], same)) == []


def test_c1_subject_with_attached_limitation_form():
    t = "2-2. 제6항(제2항의 종속항)\n제10항 발명에 부가된 제 1, 2 소자 분리막의 두께의 구성은 인용발명 1에 개시된다."
    assert "C1_foreign_subject" in AC.c1_claims(rec([6], t))


def test_c3_position_definition_contract():
    """`A ⏎(…, 이하 '인용발명1'이라 함), B ⏎(…, 이하 '인용발명2'라 함)` — 라벨 1 은 A 다. B 에 이으면 잡는다."""
    text = ("선행기술로 공개특허공보 제10-2011-0020951호\n(2011.03.03. 공개, 이하 '인용발명1'이라 함), 공개특허공보 "
            "제10-2015-0123128호\n(2015.11.03. 공개, 이하 '인용발명2'라 함)가 있습니다.\n")
    A_, B_ = "KR-P-1020110020951", "KR-P-1020150123128"
    ok = rec([1], "x", labels={A_: []}, how={A_: [("definition", "인용발명", 1)]})
    bad = rec([1], "x", labels={B_: []}, how={B_: [("definition", "인용발명", 1)]})
    ok["sec_span"] = bad["sec_span"] = (0, len(text))
    assert AC.c3_position(ok, text) == [] and AC.c3_position(bad, text) == ["C3_definition_position"]


def test_c4_serial_with_commas():
    nid = "KR-G-5836506"
    r = rec([18], "x", labels={nid: []}, how={nid: [("definition", "인용발명", 2)]})
    assert AC.c4_serial(r, "인용발명2[미국등록특허공보 제5,836,506호 (1998)]") == ["C4_country_serial"]
    assert AC.c4_serial(r, "인용발명2[등록특허공보 제5836506호]") == []


def test_c7_inherits_only_within_same_judgment_segment():
    t = ("청구항 18 발명은 희생막을 사용하는 점에서 차이가 있다. 다만, 이는 단순한 설계변경에 불과하다.")
    assert AC.c7_rationale2(rec([7, 8, 17, 18], t, rat=["DesignChoice"])) == {"DesignChoice": ["C7_scope_partial"]}
    cited = "인용발명 1에는 희생막이 개시되어 있다. 이는 단순한 설계변경에 불과하다."
    assert AC.c7_rationale2(rec([7, 8], cited, rat=["DesignChoice"])) == {"DesignChoice": ["C7_scope_unclear"]}
    assert AC.c7_rationale2(rec([7], cited, rat=["DesignChoice"])) == {}          # 청구항 하나면 대상이 유일하다


def test_c11_common_knowledge_across_page_break():
    t = "기술분야의 통상의 기술자에게는 통 - 2 - 10-2008-0030254 상적인 기술범주에 속하는 것입니다."
    assert AC.c11_common_knowledge(rec([3], t)) == ["C11_common_knowledge"]
    r = rec([3], t); r["ck"] = True
    assert AC.c11_common_knowledge(r) == []


def test_c6_bare_label_anchor_and_two_digit_paragraph():
    t = "청구항 2 발명의 구성은 비교대상발명의 불순물 함유 구성(문단 [0088] 참조)과 같다."
    assert AC.c6_locators(rec([2], t, locs={D1: {("Paragraph", "[0088]")}})) == []      # 본원 쪽으로 오분류하지 않는다
    t2 = "청구항 4 발명은 인용발명 1에 도시되어 있고[단락 84, 도면 8] 동일하다."
    assert AC.c6_locators(rec([4], t2, locs={D1: {("Figure", "도8")}})) == ["C6_locators"]   # 두 자리 단락 누락을 잡는다


def test_c3_one_document_many_labels():
    r = rec([6], "x", labels={D1: []}, how={D1: [("definition", "인용발명", 1), ("definition", "인용발명", 2)]})
    assert AC.c3_position(r, "x") == ["C3_one_document_many_labels"]
