"""논증층 A-Box(§20.22 · sdkb-abox-argument.ttl)의 계약.

고정하는 것.

  ① 블록 분할 — 머리줄 형식(표지+청구항 · 표지+제N항 · 무표지+여는 말 · 표 머리)마다 열리는가,
     결론 문장(`따라서 청구항 …`)은 열지 않는가, 본문 없는 머리줄은 다음 블록과 합쳐지는가.
  ② 청구항 · 문헌 · 좌표 · 참조 해석의 경계 — 괄호 속 인용항 · 끊긴 라벨 · 번호 없는 라벨 · 본원 좌표 ·
     모호한 참조 대상.
  ③ **실패해야 할 입력이 실패하는가** — 생성기 검사기와 shape(합성 그래프).
  ④ 실물: shape 통과 · 쓰는 술어가 전부 T-Box 에 정의 · 리포트와 그래프 일치 · 결정적 · 파일럿 동결 문턱.
     원천 계층이 없는 공개 트리에서는 ④ 만 건너뛴다.

합성 픽스처에는 실물 통지서 문구를 넣지 않는다(§1-5).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

# 공개 트리에는 정본 파서가 기대는 거절결정서 생성기가 없다(DENY) — 원천과 함께 빠지므로 모듈째 건너뛴다.
try:
    import build_abox_argument as baa  # noqa: E402
except ModuleNotFoundError as e:  # pragma: no cover — 공개 트리
    pytest.skip(f"원천 계층 생성기 없음 — 공개 트리 ({e.name})", allow_module_level=True)
import build_priorart_modules as bpm  # noqa: E402

ONT = ROOT / "ontology"
SHAPES = ROOT / "validation" / "shapes_priorart_argument.ttl"
PA = Namespace("https://w3id.org/sdkb/pa/")
PAKR = Namespace("https://w3id.org/sdkb/pa/kr/")
D = Namespace("https://w3id.org/sdkb/data/")

HAS_SOURCE = baa.TXT_DIR.exists() and baa.EDGES.exists()
needs_source = pytest.mark.skipif(not HAS_SOURCE, reason="원천 계층 없음 — 공개 트리")
needs_out = pytest.mark.skipif(not baa.OUT.exists(), reason="논증층 A-Box 미빌드 (make abox-argument)")


# ── ① 블록 분할 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("head,claims", [
    ("가. 청구항 1에 대하여,", [1]),
    ("(2) 청구항 2 발명", [2]),
    ("2-1. 청구항 제3항(제1항의 종속항)", [3]),
    ("1-1. 제10항은 제1항의 구성을 더 한정한다", [10]),
    ("청구항 4(청구항 1 내지 3 인용)의 추가적인 특징은", [4]),
    ("청구항 5의 부가적인 기술적 특징은", [5]),
    ("청구항 6 비고", [6]),
    ("① 청구항 7 내지 9", [7, 8, 9]),
    ("1.2 종속항 제2-7항", [2, 3, 4, 5, 6, 7]),
    ("1.3 독립항 제8항", [8]),
])
def test_heading_forms_open_a_block(head, claims):
    seg = f"서두 문장입니다.\n{head}\n인용발명 1 에 개시되어 있습니다.\n"
    blocks = baa.split_blocks(seg)
    assert len(blocks) == 1
    assert baa.own_claims(blocks[0]["head"]) == claims


@pytest.mark.parametrize("line", [
    "따라서 청구항 1 발명은 쉽게 발명할 수 있습니다.",
    "위 표에서 보듯 청구항 1 은 동일합니다.",
])
def test_conclusion_lines_do_not_open_a_block(line):
    assert baa.split_blocks(f"서두\n{line}\n") == []


def test_head_without_body_merges_into_next_block():
    seg = "서두\n가. 청구항 1 발명\n청구항 1 발명은 A 에 있어서 인용발명 1 과 같습니다.\n나. 청구항 2 에 대하여\n본문\n"
    blocks = baa.split_blocks(seg)
    assert [b["mark"] for b in blocks] == ["가", "나"]
    assert "인용발명 1" in blocks[0]["text"] and baa._block_claims(blocks[0]) == [1]


def test_paren_dependency_is_not_own_claim():
    assert baa.own_claims("2-2. 청구항 4(청구항 1 또는 2 인용)") == [4]
    assert baa.own_claims("청구항 제5항(제1항의 종속항)") == [5]


# ── ② 문헌 · 좌표 · 참조 ─────────────────────────────────────────────
DEFS = {("인용발명", 1): "KR-P-1020000000001", ("인용발명", 2): "US-G-9000002"}


def test_wrapped_label_resolves_and_bare_label_needs_single_section_document():
    st = Counter()
    got = baa.docs_in("인용 발명 1 과 인용발명2 를 결합", "X", DEFS, set(DEFS.values()), st)
    assert set(got) == set(DEFS.values())
    one = {"KR-P-1020000000001"}
    assert set(baa.docs_in("인용발명에 개시", "X", {}, one, st)) == one
    st2 = Counter()
    assert baa.docs_in("인용발명에 개시", "X", {}, set(DEFS.values()), st2) == {}
    assert st2["label_unresolved__bare"] == 1


def test_locator_attribution_near_label_single_doc_and_applicant_side():
    st = Counter()
    text = "인용발명 2 의 식별번호 [0034] 및 도 5 참조. 한편 본원 식별번호 [0012] 와 다르다."
    labels = baa.docs_in(text, "X", DEFS, set(DEFS.values()))
    locs = baa._locators(text, labels, None, st)
    assert locs == {"US-G-9000002": {("Paragraph", "[0034]"), ("Figure", "도5")}}
    assert st["locator_applicant_side"] == 1
    st = Counter()
    assert baa._locators("단락 [0100] 에 개시", {}, "KR-P-1020000000001", st) == \
        {"KR-P-1020000000001": {("Paragraph", "[0100]")}}
    st = Counter()
    assert baa._locators("단락 [0100] 에 개시", {}, None, st) == {} and st["locator_unattributed"] == 1


def _rec(key, section, block, claims, mark="", text="", sid=None, repeated=False):
    return {"key": key, "section": section, "sid": sid or str(section), "section_repeated": repeated,
            "block": block, "claims": claims, "mark": mark, "text": text}


def test_label_reference_category_variant_and_ambiguity():
    recs = [
        _rec("n_s1_b1", 1, 1, [1], "1-1"),
        _rec("n_s1_b2", 1, 2, [2], "1-2"),
        _rec("n_s2_b1", 2, 1, [3], "2-1", "구성들은 [거절이유 1-1]에서 검토한 바와 같이 개시됩니다."),
        _rec("n_s2_b2", 2, 2, [7], "2-2", "청구항 7은 청구항 3을 카테고리를 달리하여 청구한 발명입니다."),
        _rec("n_s2_b3", 2, 3, [8], "2-3", "구성은 [거절이유 1]에서 검토한 바와 같습니다."),
    ]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[2]["refers"] == {"n_s1_b1"}
    assert recs[3]["refers"] == recs[3]["variant_of"] == {"n_s2_b1"}
    assert recs[4]["refers"] == set() and st["ref_label_unresolved__ambiguous"] == 1


def test_claim_reference_with_two_candidates_is_not_resolved():
    recs = [_rec("a", 1, 1, [1]), _rec("b", 2, 1, [1]), _rec("c", 3, 1, [5], text="청구항 5는 청구항 1의 거절이유와 동일합니다.")]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[2]["refers"] == set() and st["ref_claim_unresolved__ambiguous"] == 1


# ── ②′ 3단계 복귀 F1–F5 (1차 사람 대조 FAIL 의 원인마다 하나) ─────────────
@pytest.mark.parametrize("text,want", [
    ("인용발명 1, 2 의 결합", {1, 2}),
    ("인용발명 1 내지 3 으로부터", {1, 2, 3}),
    ("인용발명1~3 및 5 에 의하여", {1, 2, 3, 5}),
    ("인용발명 1과 2를 결합", {1, 2}),
])
def test_f1_label_list_resolves_every_member(text, want):
    defs = {("인용발명", n): f"KR-P-10200000000{n:02d}" for n in range(1, 8)}
    got = baa.docs_in(text, "X", defs, set(defs.values()))
    assert got.keys() == {defs[("인용발명", n)] for n in want}
    assert all(v == [] for v in got.values())  # 나열 뒤 좌표는 어느 문헌 것인지 말하지 않는다


def test_f2_relation_subject_must_be_a_block_claim():
    recs = [
        _rec("n_s1_b1", 1, 1, [1], "1-1"),
        _rec("n_s1_b2", 1, 2, [9], "1-2", "청구항 9는 단순 선택입니다. 청구항 10은 청구항 1을 카테고리를 달리하여 청구한 발명입니다."),
        _rec("n_s1_b3", 1, 3, [11], "1-3", "청구항 11은 청구항 1을 카테고리를 달리하여 청구한 발명입니다."),
    ]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[1]["refers"] == set() and st["ref_variant_subject_outside_block"] == 1
    assert recs[2]["variant_of"] == {"n_s1_b1"}


def test_f3_target_is_the_narrowest_judgment():
    recs = [_rec("wide", 3, 1, [1, 2, 3, 4]), _rec("narrow", 3, 3, [3]),
            _rec("r", 3, 9, [13], text="청구항 13은 청구항 3의 거절이유와 동일합니다.")]
    baa.resolve_references(recs, Counter())
    assert recs[2]["refers"] == {"narrow"}


def test_f4_consecutive_blocks_with_same_claims_merge():
    seg = "서두\n가. 청구항 6(독립항) 및 인용발명 3\n청구항 6 비고\n표 내용 인용발명 3 과 동일합니다.\n나. 청구항 7 에 대하여\n본문\n"
    blocks = baa.split_blocks(seg)
    assert [baa._block_claims(b) for b in blocks] == [[6], [7]]
    assert "표 내용" in blocks[0]["text"]


def test_f5_unmarked_head_opens_after_mark_line_or_as_table_head():
    seg = "서두\n1.2 종속항 제2-3항\n청구항 2의 기술적 특징은 인용발명 1 에 있습니다.\n구성 인용발명 1\n청구항 3 비고\n표\n"
    heads = [m.group(0).strip() for m in baa.HEAD_RX.finditer(seg) if m.group("mark") or baa._after_sentence_end(seg, m.start())]
    assert any(h.startswith("청구항 2") for h in heads) and any(h.startswith("청구항 3") for h in heads)


def test_f5_unmarked_head_after_unfinished_sentence_does_not_open():
    seg = "서두\n가. 청구항 2 에 대하여\n주지사항이 기재되어 있고,\n청구항 3에 부가된 구성도 개시되어 있습니다.\n"
    blocks = baa.split_blocks(seg)
    assert len(blocks) == 1 and "청구항 3에 부가된" in blocks[0]["text"]


# ── ②″ 3단계 재복귀 G1–G6 (2차 사람 대조 FAIL 의 원인마다 하나) ──────────
def test_g1_foreign_subject_sentence_opens_its_own_block_and_conclusion_widens():
    seg = ("서두\n가. 청구항 9 에 대하여\n인용발명 1 과 같습니다. 청구항 10 은 단순 선택에 불과합니다. "
           "청구항 1 의 구성 A 는 다릅니다.\n나. 청구항 2 에 대하여\n제2항과 제3항의 특징은 인용발명 1 에 있습니다. "
           "따라서 제2항 및 제3항은 쉽게 발명할 수 있습니다.\n")
    blocks = baa.split_blocks(seg)
    assert [baa._block_claims(b) for b in blocks] == [[9], [10], [2, 3]]
    assert "단순 선택" not in blocks[0]["text"] and "청구항 1 의 구성" in blocks[1]["text"]


def test_g2_block_with_undefined_numbered_label_is_not_emitted():
    rec = _full_rec("k_s1_b1", [1], {"KR-P-1": [3]})
    rec["missing_labels"] = 1
    g, st = _graph([rec])
    assert not set(g.subjects(RDF.type, PA.ExaminerJudgment))
    assert st["judgment_dropped__label_definition_missing"] == 1


def test_g3_block_ends_at_next_subheading():
    seg = "서두\n가. 청구항 8 에 대하여\n인용발명 1 과 같습니다.\n나. 종속항\n다. 청구항 9 에 대하여\n본문\n"
    blocks = baa.split_blocks(seg)
    assert "종속항" not in blocks[0]["text"]


def test_g4_common_knowledge_phrase():
    assert baa.CK_RX.search("통상의 기술자에게 널리 알려져 있는 기술")


def test_g5_bracket_locator_line_is_not_a_head():
    seg = "서두\n가. 청구항 1 에 대하여\n인용발명 1 에 개시되어 있습니다.\n(청구항 2~5, 도 1 참조)\n이어지는 설명입니다.\n"
    assert [baa._block_claims(b) for b in baa.split_blocks(seg)] == [[1]]


def test_g6_relation_with_an_unresolved_target_is_dropped_whole():
    recs = [_rec("a", 1, 1, [1]), _rec("b", 1, 2, [2]),
            _rec("r", 1, 3, [9, 10, 11], text="청구항 9 내지 11은 각각 청구항 1 내지 3의 거절이유와 동일합니다.")]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[2]["refers"] == set() and st["ref_claim_partial_dropped"] == 1
    recs = [_rec("a", 1, 1, [2]), _rec("p", 1, 2, [14]),
            _rec("r", 1, 3, [5], text="청구항 5(청구항 14 인용)는 청구항 2의 거절이유와 동일합니다.")]
    baa.resolve_references(recs, Counter())
    assert recs[2]["refers"] == {"a"}


def test_g6_emission_drops_relation_when_a_target_is_not_emitted():
    a = _full_rec("k_s1_b1", [1], {"KR-P-1": [3]})
    b = _full_rec("k_s1_b2", [2], {})                       # 문헌·상식 없음 → 적재되지 않음
    r = _full_rec("k_s1_b3", [3], {"KR-P-1": [3]}, refers={"k_s1_b1", "k_s1_b2"})
    g, st = _graph([a, b, r])
    assert not list(g.triples((None, PA.refersToJudgment, None)))
    assert st["ref_dropped__target_not_emitted"] == 1


# ── ②‴ 4차 H1–H6 (3차 오답 원인마다 · 보존해야 할 정상 사례와 짝) ─────────
def test_h1_parent_in_dependency_description_is_not_judged():
    assert baa.judged_claims("따라서 청구항 제11항(청구항 제1항의 종속항의 형식을 취하나)은", first_only=False) == [11]
    assert baa.own_claims("청구항 4(청구항 1 내지 3 인용)의 추가적인 특징은") == [4]
    assert baa.judged_claims("청구항 2는 청구항 1에 있어서", first_only=False) == [2]
    # 보존: 종속관계가 아닌 나열은 그대로
    assert baa.judged_claims("따라서 제2항 및 제3항은", first_only=False) == [2, 3]


def test_h2_deeper_sub_head_under_title_takes_its_own_range():
    seg = "서두\n3-1. 청구항 1 내지 13 발명\n(1) 청구항 1~6, 8~11\n인용발명 1 에 개시되어 있습니다.\n"
    assert [baa._block_claims(b) for b in baa.split_blocks(seg)] == [[1, 2, 3, 4, 5, 6, 8, 9, 10, 11]]
    # 보존: 같은 계층이거나 부분집합이 아니면 제목 범위를 쓴다
    seg2 = "서두\n가. 청구항 1 발명\n청구항 1 발명은 A 에 있어서 인용발명 1 과 같습니다.\n"
    assert [baa._block_claims(b) for b in baa.split_blocks(seg2)] == [[1]]


def test_h3_hyphen_claim_range():
    assert baa.own_claims("(1) 청구항 1-4,6,8 발명은 신규성이 없고") == [1, 2, 3, 4, 6, 8]
    assert baa.own_claims("1.2 종속항 제2-7항") == [2, 3, 4, 5, 6, 7]


def test_h4_numbered_label_never_falls_back_to_single_section_document():
    one = {"KR-P-1020000000001"}
    miss: list = []
    assert baa.docs_in("인용발명2 에 개시", "X", {}, one, None, miss) == {}
    assert miss == [("인용발명", 2)]
    assert set(baa.docs_in("인용발명에 개시", "X", {}, one)) == one       # 보존: 번호 없는 라벨 · 문헌 하나
    miss = []
    # §20.23 c — 단독 `인용발명 1` 도 정의 없이는 잇지 않는다(그 문헌이 `[인용발명 2]` 로 선언된 경우가 있었다).
    assert baa.docs_in("인용발명 1 에 개시", "X", {}, one, None, miss) == {} and miss == [("인용발명", 1)]
    miss = []
    assert baa.docs_in("인용발명 1, 2 에 개시", "X", {}, one, None, miss) == {} and len(miss) == 2  # 나열이면 확정 안 됨
    miss = []
    baa.docs_in("인용발명에서는", "X", {}, {"A", "B"}, None, miss)
    assert miss == [("인용발명", None)]                                      # 문헌 여럿이면 미해결
    assert baa.docs_in("인용발명들은 모두", "X", {}, {"A", "B"}) == {}      # 복수형은 특정 문헌이 아니다


@pytest.mark.parametrize("text,kind,want", [
    ("청구항 9는 청구항 1을 단순하게 카테고리를 달리하여 청구한 발명입니다.", "variant", [1]),
    ("청구항 26, 27 은 청구항 3, 4 발명과 기술적 사상이 동일하고 카테고리만 달리할 뿐입니다.", "variant", [3, 4]),
    ("청구항 13 은 청구항 1 발명의 구성 3, 9, 10에 대한 거절이유가 동일하게 적용됩니다.", "claim", [1]),
    ("청구항 15는 청구항 1~13의 조성물을 포함하며 청구항 14의 거절이유와 동일합니다.", "claim", [14]),
])
def test_h5_target_is_the_list_grammatically_attached(text, kind, want):
    rx = baa.CAT_RX if kind == "variant" else baa.REF_CLAIM_RX
    assert baa.attached_targets(text, rx.search(text), kind) == want


def test_h5_unattached_reference_is_not_linked():
    text = "청구항 5는 청구항 1과 실질적으로 동일한 기술적 특징을 청구하며, 이에 대하여는 앞서 본 거절이유가 동일하게 적용됩니다."
    assert baa.attached_targets(text, baa.REF_CLAIM_RX.search(text), "claim") is None


def test_h6_intra_block_target_is_not_linked_elsewhere():
    recs = [_rec("other", 2, 1, [1, 13, 24]),
            _rec("self", 1, 0, [1, 13], text="청구항 13은 청구항 1의 거절이유와 동일합니다.")]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[1]["refers"] == set() and st["ref_claim_intra_block_targets"] == 1


def test_label_reference_without_brackets():
    recs = [_rec("a", 2, 2, [5], "2-2"),
            _rec("r", 2, 4, [7], "2-4", "상기 2-2.의 거절이유에서 지적한 바와 동일한 취지입니다.")]
    baa.resolve_references(recs, Counter())
    assert recs[1]["refers"] == {"a"}


# ── ②⁗ 회귀 v1 에서 찾은 결함 (사용자 재판정 10-05) ──────────────────────
def test_locator_ranges_are_kept_as_one_range():
    st = Counter()
    text = "인용발명 1 의 단락 [0010]~[0013] 및 도 6 ~ 10 참조, 식별번호 0034-0049 참조"
    labels = baa.docs_in(text, "X", {("인용발명", 1): "KR-P-1"}, {"KR-P-1"})
    assert baa._locators(text, labels, None, st) == {
        "KR-P-1": {("Paragraph", "[0010]~[0013]"), ("Figure", "도6~10"), ("Paragraph", "[0034]~[0049]")}}
    assert all(baa.LOC_VALUE_RX.match(v) for _, v in {("P", "[0010]~[0013]"), ("F", "도6~10")})


def test_law_article_is_not_a_claim():
    assert baa.judged_claims("특허법 제29조제2항에 따라 특허를 받을 수 없습니다", first_only=False) == []
    assert baa.judged_claims("청구항 2는 특허법 제29조 제2항의 거절이유", first_only=False) == [2]


def test_table_head_with_document_label_keeps_its_claim():
    assert baa.own_claims("청구항 제1항 인용발명 1 비고") == [1]                # `인용` 발명은 종속관계가 아니다


@pytest.mark.parametrize("text,kind,want", [
    ("청구항 8·9에 대하여는 청구항 3·4와 동일한 거절이유가 적용됩니다.", "claim", [3, 4]),
    ("청구항 11은 청구항 2+4의 거절이유가 그대로 적용됩니다.", "claim", [2, 4]),
    ("청구항 6은 청구항 1~5 중 어느 한 항과 기술적 특징이 같고 카테고리를 달리합니다.", "variant", [1, 2, 3, 4, 5]),
    ("청구항 2 는 상기 청구항 1 발명에 대한 특허법 제29조제2항의 거절이유가 동일하게 적용됩니다.", "claim", [1]),
    ("청구항 16 발명은 청구항 9 발명의 ‘메모리 장치의 제조 방법’의 발명과 그 구성이 동일한 카테고리만 다른 발명입니다.", "variant", [9]),
])
def test_regression_v1_reference_forms(text, kind, want):
    rx = baa.CAT_RX if kind == "variant" else baa.REF_CLAIM_RX
    assert baa.attached_targets(text, rx.search(text), kind) == want


def test_subject_skips_title_line_but_not_a_sentence_starting_line():
    titled = "1-5. 청구항 11, 12 발명\n청구항 11 발명(청구항 10 인용)의 한정사항은 청구항 2의 거절이유가 동일하게 적용됩니다."
    assert baa.sentence_subject(titled, titled.index("거절")) == [11]
    flowing = "청구항 16 발명은 ‘메모리 장치’에 관한 발명으로,\n청구항 9 발명과 카테고리만 다른 발명입니다."
    assert baa.sentence_subject(flowing, flowing.index("카테고리")) == [16]


@pytest.mark.parametrize("text,want", [
    ("청구항 15 발명(청구항 1,2,3 중 어느 한 항 인용)의 한정사항에 대하여는 그 내용상 청구항 3 발명의 구성O에 대한 거절이유가 동일하게 적용됩니다.", [3]),
    ("(6)청구항 제13항 및 제17항에서의 한정사항은,\n청구항 제2항 및 제8항에서의 한정사항과 같으므로 청구항 제2항 및 제8항과 동일한 취지의 거절이유가 적용됩니다.", [2, 8]),
])
def test_regression_v2_reference_forms(text, want):
    m = baa.REF_CLAIM_RX.search(text)
    assert baa.attached_targets(text, m, "claim") == want
    assert baa.sentence_subject(text, m.start()) not in ([], want)


def test_summary_conclusion_is_cut_from_block_text():
    seg = ("서두\n(4) 청구항 6 내지 8\n청구항 6 은 인용발명 1 과 같습니다. 청구항 7 은 설계변경입니다. 청구항 8 은 주지입니다. "
           "따라서 청구항 3 내지 8 은 쉽게 발명할 수 있습니다.\n")
    b = baa.split_blocks(seg)[0]
    assert "청구항 3 내지 8" not in b["text"] and baa._block_claims(b) == [6, 7, 8]
    assert "청구항 3 내지 8" in b["summary"]          # 블록 청구항을 모두 덮으므로 별도 표시 · 문헌 근거로 남긴다


def test_own_limitation_mention_counts_as_discussed():
    seg = ("서두\n(1) 청구항 1-4 발명\n청구항 1-4 발명은 인용발명 1 로부터 도출할 수 있습니다. 청구항 9 발명의 한정 구성은 단순 선택입니다. "
           "따라서 청구항 1-4,9 발명은 쉽게 발명할 수 있습니다.\n")
    b = baa.split_blocks(seg)[0]
    assert baa._block_claims(b) == [1, 2, 3, 4, 9] and not b["summary"]


def test_covering_summary_supplies_documents_for_reference_only_block():
    seg = ("서두\n- 청구항 9 내지 12는 각각 청구항 1 및 3 내지 5를 단순히 카테고리를 달리하여 청구한 발명입니다.\n"
           "따라서 청구항 7 내지 12 발명은 인용발명 1 의 조합으로부터 쉽게 발명할 수 있습니다.\n")
    b = baa.split_blocks(seg)[0]
    assert "인용발명 1" in b["summary"] and "인용발명 1" not in b["text"]


def test_summary_conclusion_does_not_widen_block_or_make_intra_relation():
    seg = ("서두\n(3) 청구항 9 내지 11\n청구항 9 내지 11은 청구항 1의 구성과 같습니다. "
           "따라서 청구항 1 내지 11은 쉽게 발명할 수 있습니다.\n")
    blocks = baa.split_blocks(seg)
    assert baa._block_claims(blocks[0]) == [9, 10, 11]


# ── ③ 검사기 · shape: 실패해야 할 입력 ────────────────────────────────
class _Resolver:
    def __call__(self, nid, stat):
        return D[f"patent/{nid}"]


def _full_rec(key, claims, labels, ck=False, refers=(), variant=()):
    return {"key": key, "stem": "1020000000000_9", "app": "1020000000000", "section": 1, "sid": "1",
            "section_repeated": False, "block": 1,
            "mark": "", "grounds": ["§29②"], "claims": claims, "scope": "whole", "labels": labels,
            "ck": ck, "rat": ["DesignChoice"], "text": "인용발명 1 의 단락 [0010] 참조",
            "refers": set(refers), "variant_of": set(variant),
            "groups": [("variant" if variant else "claim", sorted(refers))] if refers else []}


def _graph(recs):
    ok = {f"rej_1020000000000_c{n}" for n in range(1, 10)}
    st = Counter()
    return baa.build(recs, _Resolver(), ok, st), st


def test_build_drops_block_without_document_or_common_knowledge():
    g, st = _graph([_full_rec("k_s1_b1", [1], {}), _full_rec("k_s1_b2", [2], {}, ck=True)])
    assert len(set(g.subjects(RDF.type, PA.ExaminerJudgment))) == 1
    assert st["judgment_dropped__no_document_no_common_knowledge"] == 1


def test_build_emits_variant_with_super_property_and_passes_check():
    g, _ = _graph([_full_rec("k_s1_b1", [1], {"KR-P-1": [3]}),
                   _full_rec("k_s1_b2", [2], {"KR-P-1": [3]}, refers={"k_s1_b1"}, variant={"k_s1_b1"})])
    a, b = baa._jiri("k_s1_b2"), baa._jiri("k_s1_b1")
    assert (a, PA.categoryVariantOf, b) in g and (a, PA.refersToJudgment, b) in g
    baa.check(g)


@pytest.mark.parametrize("name,mutate", [
    ("자기 참조", lambda g, a, b: g.add((a, PA.refersToJudgment, a))),
    ("없는 대상 참조", lambda g, a, b: g.add((a, PA.refersToJudgment, D["argument/judgment/none"]))),
    ("상위 술어 없는 범주 변형", lambda g, a, b: g.add((b, PA.categoryVariantOf, a))),
    ("형식 밖 좌표 값", lambda g, a, b: g.add((URIRef(f"{a}_l1_loc1"), PA.locatorValue, Literal("원문 문장이 새는 값")))),
    ("청구항 용어 적재", lambda g, a, b: g.add((URIRef(f"{a}_l1"), PA.claimTerm, Literal("x")))),
    ("근거 없는 판단", lambda g, a, b: g.remove((a, PA.onGround, None))),
    ("T-Box 밖 논거", lambda g, a, b: g.add((URIRef(f"{a}_s1"), PA.hasRationale, PA.RationaleNope))),
])
def test_check_rejects(name, mutate):
    g, _ = _graph([_full_rec("k_s1_b1", [1], {"KR-P-1": [3]}), _full_rec("k_s1_b2", [2], {"KR-P-1": [3]})])
    mutate(g, baa._jiri("k_s1_b1"), baa._jiri("k_s1_b2"))
    with pytest.raises(SystemExit):
        baa.check(g)


def _tbox() -> Graph:
    g = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-argument.ttl"):
        g.parse(ONT / f)
    return g


def _conforms(g: Graph) -> bool:
    ok, _, _ = validate(_tbox() + g, shacl_graph=Graph().parse(SHAPES), inference="none")
    return ok


def test_shape_accepts_generated_synthetic_graph():
    g, _ = _graph([_full_rec("k_s1_b1", [1], {"KR-P-1": [3]})])
    assert _conforms(g)


@pytest.mark.parametrize("name,mutate", [
    ("청구항 없는 판단", lambda g, j: g.remove((j, PA.judgesClaim, None))),
    ("심사문서 둘", lambda g, j: g.add((j, PA.assertedIn, D["examdoc/other"]))),
    ("빈 근거 묶음", lambda g, j: g.remove((URIRef(f"{j}_s1"), PA.includesDocument, None))),
    ("종류 없는 좌표", lambda g, j: g.remove((None, PA.locatorType, None))),
])
def test_shape_rejects_mutations_of_generated_graph(name, mutate):
    g, _ = _graph([_full_rec("k_s1_b1", [1], {"KR-P-1": [3]})])
    mutate(g, baa._jiri("k_s1_b1"))
    assert not _conforms(g)


def test_category_variant_is_declared_under_refers_to_judgment():
    g = Graph().parse(ONT / "sdkb-priorart-argument.ttl")
    assert (PA.categoryVariantOf, RDF.type, OWL.ObjectProperty) in g
    assert (PA.categoryVariantOf, RDFS.subPropertyOf, PA.refersToJudgment) in g


# ── ④ 실물 ───────────────────────────────────────────────────────────
def _defined_predicates() -> set:
    tb = Graph()
    for f in ("sdkb-patent.ttl",) + tuple(m[0] for m in bpm.MODULES):
        tb.parse(ONT / f)
    return {s for t in (OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property)
            for s in tb.subjects(RDF.type, t)} | {RDF.type}


@needs_out
def test_real_graph_uses_only_tbox_predicates_and_matches_report():
    g = Graph().parse(baa.OUT)
    preds = {p for _, p, _ in g}
    assert preds - {URIRef("http://purl.org/dc/terms/source"), URIRef("http://purl.org/dc/terms/license")} \
        <= _defined_predicates()
    assert PA.claimTerm not in preds and PA.documentTerm not in preds
    rep = json.loads(baa.REPORT.read_text(encoding="utf-8"))
    assert rep["triples"] == len(g)
    assert rep["counts"] == baa.counts(g)
    assert sum(rep["judgments_by_split"].values()) == rep["counts"]["ExaminerJudgment"] > 0


@needs_out
def test_real_graph_conforms_to_argument_shapes():
    g = Graph().parse(baa.OUT) + Graph().parse(ONT / "sdkb-abox-priorart.ttl") \
        if (ONT / "sdkb-abox-priorart.ttl").exists() else Graph().parse(baa.OUT)
    assert _conforms(g)


@needs_source
def test_real_build_is_deterministic_and_passes_frozen_pilot_thresholds():
    t1, g, _, flat = baa.render()
    t2, *_ = baa.render()
    assert t1 == t2
    ev = baa.eval_pilot(flat)
    assert ev["claim_coverage"] >= baa.PILOT_CLAIM_COVERAGE_MIN
    assert ev["document_match"] >= baa.PILOT_DOC_MATCH_MIN
    assert ev["pass"]


def test_repeated_section_number_label_reference_is_not_linked():
    """§20.23 c — 인쇄된 절 번호가 되풀이되면 `[거절이유 1-1]` 은 어느 절인지 말하지 않는다. 잇지 않고 센다."""
    recs = [_rec("n_s1_b1", 1, 1, [1], mark="1-1", sid="1", repeated=True),
            _rec("n_s1r2_b1", 1, 1, [2], mark="1-1", sid="1r2", repeated=True),
            _rec("n_s2_b1", 2, 1, [3], text="청구항 3 은 [거절이유 1-1]에서 지적한 바와 같다.")]
    st = Counter()
    baa.resolve_references(recs, st)
    assert recs[2]["refers"] == set() and st["ref_label_unresolved__repeated_section"] == 1


def test_same_section_preference_uses_section_identity_not_printed_number():
    """같은 번호의 두 절은 다른 절이다 — F3 의 '같은 절 우선' 은 절 식별자로 판단한다."""
    recs = [_rec("n_s1_b1", 1, 1, [1], sid="1", repeated=True),
            _rec("n_s1r2_b1", 1, 1, [1], sid="1r2", repeated=True),
            _rec("n_s1r2_b2", 1, 2, [2], sid="1r2", repeated=True,
                 text="청구항 2 는 청구항 1 의 거절이유와 동일합니다.")]
    baa.resolve_references(recs, Counter())
    assert recs[2]["refers"] == {"n_s1r2_b1"}


# ── §20.23 c 선택적 적재 — 보류는 의존관계를 따라 전파된다 ─────────────
def _held(r, block=(), locators=(), rationale=None):
    r["holds"] = {"block": list(block), "locators": list(locators), "rationale": rationale or {}}
    return r


def test_held_block_drops_judgment_and_relations_that_touch_it():
    g, st = _graph([_held(_full_rec("k_s1_b1", [1], {"KR-P-1": [3]}), block=["C1_foreign_subject"]),
                    _held(_full_rec("k_s1_b2", [2], {"KR-P-1": [3]}, refers={"k_s1_b1"})),
                    _held(_full_rec("k_s1_b3", [3], {"KR-P-1": [3]}, refers={"k_s1_b2"}), block=["C5_conclusion"])])
    js = {str(j).rsplit("/", 1)[1] for j in g.subjects(RDF.type, PA.ExaminerJudgment)}
    assert js == {"k_s1_b2"} and (None, PA.refersToJudgment, None) not in g
    assert st["sel_judgment__candidate"] == 3 and st["sel_judgment__held"] == 2
    assert st["hold__C8_target_held"] == 1 and st["hold__C8_source_held"] == 1
    assert st["sel_relation__candidate"] == 2 and st["sel_relation__held"] == 2
    baa.check(g)


def test_held_locators_and_one_rationale_kind_only():
    r = _full_rec("k_s1_b1", [1], {"KR-P-1": [3]})
    r["rat"] = ["DesignChoice", "PredictableEffect"]
    g, st = _graph([_held(r, locators=["C6_locators"], rationale={"PredictableEffect": ["C7_scope_partial"]})])
    j = baa._jiri("k_s1_b1")
    assert (j, PA.judgesClaim, None) in g                                   # 판단은 싣는다
    assert (None, PA.locator, None) not in g and st["sel_locator_set__held"] == 1
    rats = set(g.objects(None, PA.hasRationale))
    assert rats == {PA.RationaleDesignChoice} and st["sel_rationale_PredictableEffect__held"] == 1


@pytest.mark.parametrize("text,want", [
    ("단락 [0071] 내지 [0073] 및 도 4A,B 참조", ["[0071]~[0073]", "도4A", "도4B"]),
    ("[0036-0039]", ["[0036]~[0039]"]),
    ("단락[0026]-[0029],[0045]-[0050] 등", ["[0026]~[0029]", "[0045]~[0050]"]),
    ("[0013, 0014, 0029] 참조", ["[0013]", "[0014]", "[0029]"]),
    ("도 3a, 3b 참조", ["도3a", "도3b"]),
    ("도 5A-5B", ["도5A"]),                                       # 하이픈은 읽지 않는다(범위인지 복합 번호인지 모름)
    ("도 10A 내지 10C 참조", ["도10A~10C"]),
    ("도면 1(B))", ["도1B"]),
    ("도 1a,2-4,6 참조", ["도1a", "도2"]),
    ("도 8에서", ["도8"]),
    ("도면 2·4·8·10", ["도2", "도4", "도8", "도10"]),
    ("온도 300℃ 정도 1 이상 · 정도 3", []),                       # 낱말 속 `도` · 단위는 좌표가 아니다
])
def test_k1_locator_ranges_lists_and_suffixes(text, want):
    """K1 (§20.23 c) — 원문이 적은 범위·나열·접미를 그대로 읽는다. 이미 읽은 괄호를 다시 세지 않는다."""
    got = [v for _, items in baa.locator_items(text) for _, v in items]
    assert got == want and all(baa.LOC_VALUE_RX.match(v) for v in got)


def test_k2_summary_bundle_attributes_only_this_blocks_combination():
    """K2 — 한 결론에 묶음별 결합이 다르면 현재 블록 묶음의 절만 문헌 근거다."""
    s = "따라서 청구항 2, 3, 5 발명은 인용발명 1, 2의 결합으로, 제7-10항 발명은 인용발명 1, 3의 결합으로 쉽게 발명할 수 있습니다."
    part, amb = baa.summary_for_block(s, {8, 9, 10})
    assert not amb and "인용발명 1, 3" in part and "인용발명 1, 2" not in part


def test_k2_adjective_eun_is_not_a_bundle_subject():
    """`같은 이유로` 의 `-은` 은 주어 조사가 아니다 — 가짜 묶음이 절을 자르면 라벨을 잃는다(4차 57행)."""
    s = "따라서 청구항 14,15 발명은 각각 위 청구항 2,3에 대한 거절이유와 같은 이유로 인용발명1과 실질적으로 동일합니다."
    bundles = [sorted(c) for _, _, sps in baa.conclusion_bundles(s) for c, _, _ in sps]
    assert bundles == [[14, 15]]
    part, _ = baa.summary_for_block(s, {14, 15})
    assert "인용발명1" in part


def test_k2_split_piece_and_ambiguous_bundles():
    s = "따라서 출원발명의 청구항 9 및 16 발명은 인용발명 1 및 3으로부터 쉽게 발명할 수 있습니다."
    assert "인용발명 1 및 3" in baa.summary_for_block(s, {16})[0]          # 분할 조각(16)도 자기 묶음 절을 받는다
    amb = "따라서 청구항 1, 2 발명은 인용발명 1로, 청구항 3 발명은 인용발명 2로 쉽게 발명할 수 있습니다."
    assert baa.summary_for_block(amb, {2, 3}) == ("", True)                  # 블록이 두 묶음에 걸친다 — 보류


def test_k2_broad_conclusion_does_not_add_claims():
    """넓힌 결론 읽기는 종합 결론을 떼는 데만 쓴다 — 블록 청구항을 늘리지 않는다(§20.23 c 금지 목록)."""
    b = {"mark": "1", "head": "1-11. 청구항 14, 15", "text": "1-11. 청구항 14, 15\n청구항 14, 15 발명은 청구항 2, 3 을 카테고리를 달리한 것이다.\n"
         "그러므로 청구항 2, 3, 14, 15 발명은 인용발명 1로부터 쉽게 발명할 수 있습니다."}
    out = baa.split_by_subject(b)
    assert baa._block_claims(out[0]) == [14, 15]


def test_gate5_zero_judged_is_undecidable_not_pass(tmp_path, monkeypatch):
    """§20.23 e — 판정 0 건은 판정 불가(통과 아님) · 평가자 보류 20% 초과도 판정 불가 · 문턱 0.90."""
    import csv
    p = tmp_path / "s.csv"
    rows = ([{"kind": "block", "correct": "1"}] * 9 + [{"kind": "block", "correct": "0"}]
            + [{"kind": "DesignChoice", "correct": ""}] * 3 + [{"kind": "DesignChoice", "correct": "1"}] * 7
            + [{"kind": "held_block", "correct": "1"}])
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "correct"]); w.writeheader(); w.writerows(rows)
    monkeypatch.setattr(baa, "ROOT", tmp_path)
    out = baa.gate5(p)
    assert out["by_kind"]["block"]["pass"] is True and out["by_kind"]["block"]["rate"] == 0.9
    assert out["by_kind"]["DesignChoice"]["decidable"] is False                 # 보류 3/10 > 20%
    assert out["by_kind"]["locator"]["decidable"] is False and out["by_kind"]["locator"]["pass"] is False   # 0 건
    assert out["over_hold"]["held_block"] == {"rows": 1, "actually_correct": 1} and out["pass"] is False


def test_e5_definition_contract_and_uniqueness():
    """E5 (§20.24) — `A ⏎(…, 이하 '인용발명1'이라 함), B ⏎(…, 이하 '인용발명2'라 함)` 에서 1 = A · 2 = B.
    한 문헌이 번호 여럿에 잡히면 유일하지 않으므로 쓰지 않는다."""
    t = ("선행기술로 공개특허공보 제10-2011-0020951호\n(2011.03.03. 공개, 이하 '인용발명1'이라 함), 공개특허공보 "
         "제10-2015-0123128호\n(2015.11.03. 공개, 이하 '인용발명2'라 함)가 있습니다.")
    d = baa.e5_definitions(t, "1020170000000")
    assert d[("인용발명", 1)][0][1] == "KR-P-1020110020951" and d[("인용발명", 2)][0][1] == "KR-P-1020150123128"
    same = "공개특허공보 제10-2011-0020951호 (가, 이하 '인용발명1'이라 함), 미확인 문헌 (나, 이하 '인용발명2'라 함)"
    assert baa.e5_definitions(same, "1020170000000") == {}
    assert not baa.K6_FWD_RX.search("(2011.03.03. 공개, 이하 '인용발명1'이라 함), 공개특허공보 제10-2015-0123128호")


# ── §20.24 보정 E1–E9 ─────────────────────────────────────────────────
def test_e3_e4_mention_level_parents_and_head_continuation():
    """E3 — 부모는 그 언급만 뺀다 · E4 — 괄호로 끊긴 머리줄 나열을 이어 읽는다(5단계 누락 10번 · 4차 71행)."""
    assert baa.own_claims("2-2. 제2항(제1항의 종속항), 제6항 내지 제7항(제2항의 종속항) 및 제10항(제1항의 종속항)") == [2, 6, 7, 10]
    assert baa.own_claims("2-2. 청구항 제2항 발명(제1항 인용), 제3항 발명(제2항 인용)의 한정 구성은") == [2, 3]
    assert baa.own_claims("청구항 4(청구항 1 내지 3 인용)") == [4]
    assert baa.own_claims("1-1. 청구항 1 발명은 청구항 2 와 비교하면") == [1]          # 나열이 아니다


def test_e1_table_head_joins_only_a_sentence_intro():
    """E1 — 표 머리 줄은 앞 머리줄이 비교를 예고하는 **문장**이고 판단 서술이 아직 없을 때만 그 판단에 붙는다."""
    intro = "1-1. 청구항 1 발명과 인용발명 1을 비교해 보면 아래 표 1과 같습니다.\n청구항 1 발명 비고\n구성 A 동일\n양 발명은 동일합니다.\n"
    assert [baa._block_claims(b) for b in baa.split_blocks(intro)] == [[1]]
    title = "2-1. 청구항 1 내지 4 발명\n청구항 1 발명 인용발명 비고\n구성 A 동일하다.\n"
    assert [1, 2, 3, 4] not in [baa._block_claims(b) for b in baa.split_blocks(title)]   # 제목에 붙여 범위를 남기지 않는다


def test_e2_patent_claim_heading_form():
    assert baa.HEAD_K3_RX.match("2-1. 본원의 특허청구 제1항은 반도체 기판에")
    assert baa.own_claims("2-2. 본원의 특허청구 제2~4항은 제1 폴리") == [2, 3, 4]


def test_e9_paren_number_is_deeper_than_dot_letter():
    assert baa._mark_level("1", "1)") > baa._mark_level("나", "나.")
    assert baa._mark_level("1", "1.") < baa._mark_level("나", "나.")


def test_e6_common_knowledge_across_page_break():
    import re as _re
    t = "통상의 기술자에게는 통 - 2 - 10-2008-0030254 상적인 기술범주에 속하는 것입니다."
    assert baa.CK_RX.search(_re.sub(r"\s*" + baa.PAGE_MARK_RX.pattern + r"\s*", "", t))
    assert baa.CK_RX.search("통상의 기술자에게 잘 알려진 사항입니다")


def test_e8_two_digit_paragraph_only_with_keyword():
    got = [v for _, items in baa.locator_items("도시되어 있고[단락 84, 도면 8], 이 사건") for _, v in items]
    assert got == ["[84]", "도8"] and all(baa.LOC_VALUE_RX.match(v) for v in got)
    assert [v for _, items in baa.locator_items("단락 5 를 참고하면") for _, v in items] == []


def test_e7_section_final_conclusion_reaches_covered_blocks():
    """E7 — 절 끝 결론 `청구항 1 내지 3 은 인용발명 1, 2 의 결합` 은 블록 청구항 전체를 덮는 묶음이 하나뿐이므로 앞 블록들에도
    문헌 근거가 된다. 묶음이 블록을 다 덮지 못하면 주지 않는다(사용자 조건 10-05)."""
    text = ("[구체적인 거절이유]\n1. 이 출원은 특허법 제29조제2항에 따라 특허를 받을 수 없습니다.\n"
            "인용발명 1 : 공개특허공보 제10-2010-0012345호\n인용발명 2 : 공개특허공보 제10-2011-0054321호\n"
            "1-1. 청구항 1 발명은 인용발명 1과 대비하면 차이가 있으나 쉽게 발명할 수 있습니다.\n"
            "1-2. 청구항 2 발명은 인용발명 1에 개시되어 있어 쉽게 발명할 수 있습니다.\n"
            "1-3. 청구항 3 발명은 인용발명 2에 개시되어 있습니다. 따라서 청구항 1 내지 3 발명은 인용발명 1, 2의 결합으로부터 "
            "쉽게 발명할 수 있습니다.\n")
    recs, _ = baa.extract_notice("1020200000000_9", text)
    by = {tuple(r["claims"]): r for r in recs}
    assert set(by[(2,)]["labels"]) == {"KR-P-1020100012345", "KR-P-1020110054321"} and by[(2,)]["e7"]
    narrow = text.replace("따라서 청구항 1 내지 3 발명은", "따라서 청구항 2, 3 발명은")
    recs, _ = baa.extract_notice("1020200000000_9", narrow)
    by = {tuple(r["claims"]): r for r in recs}
    assert not by[(1,)]["e7"]                                    # 1 은 묶음에 들지 않는다


def test_e7_alternative_conclusion_is_not_a_common_document_set():
    """대안 결합 결론(`인용발명1, 또는 인용발명1,2의 결합`)은 합집합으로 귀속하지 않는다(재판정 10-05).
    블록이 자기 결론을 가지면 그 문헌 그대로, 없으면 보류한다."""
    base = ("[구체적인 거절이유]\n1. 이 출원은 특허법 제29조제2항에 따라 특허를 받을 수 없습니다.\n"
            "인용발명 1 : 공개특허공보 제10-2010-0012345호\n인용발명 2 : 공개특허공보 제10-2011-0054321호\n"
            "1-1. 청구항 1 발명은 인용발명 1과 대비하면 차이가 있으나 쉽게 발명할 수 있습니다.\n"
            "1-2. 청구항 2 발명은 {body}\n"
            "1-3. 청구항 3 발명은 인용발명 1, 2의 결합으로부터 쉽게 발명할 수 있습니다. 따라서 제1항 내지 제3항 발명은 당업자가 "
            "인용발명1, 또는 인용발명1,2의 결합에 의해 쉽게 발명할 수 있습니다.\n")
    own = base.format(body="인용발명 1의 단순한 설계변경에 불과하여 쉽게 발명할 수 있습니다.")
    r = {tuple(x["claims"]): x for x in baa.extract_notice("1020200000000_9", own)[0]}[(2,)]
    assert set(r["labels"]) == {"KR-P-1020100012345"} and not r["e7"] and not r["e7_ambiguous"]
    bare = base.format(body="인용발명 1의 라인부 구성에 대응합니다.")
    r = {tuple(x["claims"]): x for x in baa.extract_notice("1020200000000_9", bare)[0]}[(2,)]
    assert not r["e7"] and r["e7_ambiguous"]


def test_gate6_relations_are_undecidable_and_never_whole_pass(tmp_path, monkeypatch):
    """§20.24 — 새 독립 관계 표본이 없으므로 관계는 판정 불가 · '논증층 전체 통과' 는 내지 않는다."""
    import csv
    p = tmp_path / "s.csv"
    rows = ([{"kind": k, "correct": "1"} for k in ("block", "DesignChoice", "PredictableEffect", "locator") for _ in range(10)]
            + [{"kind": "categoryVariantOf", "correct": "1"}])
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "correct"]); w.writeheader(); w.writerows(rows)
    monkeypatch.setattr(baa, "ROOT", tmp_path)
    out = baa.gate5(p, relation_undecidable=True, seed=baa.SAMPLE6_SEED)
    assert out["by_kind"]["categoryVariantOf"]["decidable"] is False and out["by_kind"]["refersToJudgment"]["decidable"] is False
    assert out["pass_judged_kinds"] is True and out["pass"] is False


def test_bundle_guard_is_one_contract_for_k2_and_e7():
    """K2 · E7 공통 계약 — 대안 결합 결론은 공통 문헌 집합이 아니다(재판정 10-05 · K2 누락 사고 10-06).
    두 경로가 같은 함수를 쓰므로, 한쪽에만 규칙을 넣는 누락이 다시 생기지 않는다."""
    alt = "청구항 1 내지 3 발명은 인용발명1, 또는 인용발명1,2의 결합에 의해 쉽게 발명할 수 있습니다."
    assert baa.bundle_guard(alt, "인용발명 1의 단순한 설계변경으로 쉽게 발명할 수 있다.") == ("", False)   # 자기 결론 → 귀속 없음
    assert baa.bundle_guard(alt, "인용발명 1의 라인부에 대응한다.") == ("", True)                       # 자기 결론 없음 → 보류
    plain = "청구항 1 내지 3 발명은 인용발명 1, 2의 결합으로 쉽게 발명할 수 있습니다."
    assert baa.bundle_guard(plain, "x") == (plain, False)


def test_k2_in_block_alternative_conclusion_is_guarded():
    """K2 경로(블록 안 종합 결론)에도 같은 계약이 걸린다 — 누락 시트 r6 8번 12~15항 블록."""
    b = {"mark": "1", "head": "1-12. 청구항 12 내지 15",
         "text": "1-12. 청구항 12 내지 15\n청구항 12 내지 15 발명은 앞의 판단과 같이 인용발명 1의 구성에 대응합니다.\n"
                 "따라서 청구항 1 내지 15 발명은 당업자가 인용발명1, 또는 인용발명1,2의 결합에 의해 쉽게 발명할 수 있습니다."}
    out = baa.split_by_subject(b)
    assert out[0]["summary_docs"] == "" and out[0]["k2_ambiguous"] is True
