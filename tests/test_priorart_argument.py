"""논증층(⑤ sdkb-priorart-argument.ttl)과 그 파일럿 A-Box 의 계약 — PLAN-005 R1-스키마.

고정하는 것.

  ① **기존 네 모듈이 한 바이트도 바뀌지 않았는가.** core·semi·kr 은 V6b 판정의 동결 sha 와,
     us 는 생성기 재생성물과 대조한다. ⑤ 를 더하면서 ①–④ 를 건드리면 과거 판정이 자기모순이 된다.
  ② ⑤ 가 core 와 같은 순도(도메인·관할 IRI 0)를 지키고, 설계에서 승인한 어휘 수와 같은가.
  ③ **실패해야 할 입력이 실패하는가** — 파일럿 검사기(합성 픽스처)와 shape(합성 그래프) 양쪽.
  ④ 실물 파일럿: 결정적 · shape 통과 · **쓰는 술어가 전부 T-Box 에 정의** · CQ 15개가
     적용 전 0행 → 적용 후 ≥1행. 원천 계층이 없는 공개 트리에서는 ④ 만 건너뛴다.

합성 픽스처에는 실물 통지서 문구를 넣지 않는다(§1-5).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_abox_argument_pilot as bap  # noqa: E402
import build_priorart_modules as bpm  # noqa: E402
from check_priorart_invariants import check_core  # noqa: E402
from report_stage8_paper_port import FROZEN  # noqa: E402
from run_cq import parse_cq  # noqa: E402

ONT = ROOT / "ontology"
ARG = ONT / "sdkb-priorart-argument.ttl"
SHAPES = ROOT / "validation" / "shapes_priorart_argument.ttl"
CQ_DIR = ROOT / "queries" / "cq_argument"
PA = Namespace("https://w3id.org/sdkb/pa/")
PAKR = Namespace("https://w3id.org/sdkb/pa/kr/")
X = Namespace("https://example.org/t/")

HAS_SOURCE = bap.PILOT.exists() and bap.CARDS.exists()


# ── ① 기존 모듈 불변 ─────────────────────────────────────────────────
def test_v6b_frozen_modules_are_byte_identical():
    for rel, want in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, rel


def test_all_modules_match_generator():
    rendered = bpm.render()
    assert "sdkb-priorart-argument.ttl" in rendered
    for fname, text in rendered.items():
        assert (ONT / fname).read_text(encoding="utf-8") == text, fname


def test_render_is_deterministic():
    assert bpm.render() == bpm.render()


# ── ② 순도와 어휘 규모 ───────────────────────────────────────────────
def test_argument_module_is_pure():
    assert check_core(ARG) == []


def test_argument_vocabulary_matches_approved_design():
    g = Graph().parse(ARG)
    n = {k: len(set(g.subjects(RDF.type, t))) for k, t in
         [("class", OWL.Class), ("op", OWL.ObjectProperty), ("dp", OWL.DatatypeProperty)]}
    # R1-스키마 9·16·10·18 + 논증층 R-Box 규칙(2026-10-04) 클래스 2 · 객체 4 · 데이터 2 · 규칙 개체 1.
    assert n == {"class": 11, "op": 20, "dp": 12}
    individuals = {s for s, o in g.subject_objects(RDF.type)
                   if o not in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology)}
    assert len(individuals) == 19
    assert set(g.objects(bpm.ARG_IRI, OWL.imports)) == {bpm.CORE_IRI}


def test_retired_substitutable_with_is_not_revived():
    # 원천의 치환은 방향 있는 판단 논거라 논거 개체(RationaleSubstitution)로 담는다 — 옛 대칭 술어가 아니다.
    for text in bpm.render().values():
        assert "substitutableWith" not in text.replace("`pa:substitutableWith`", "")


# ── ③-a 파일럿 검사기: 실패해야 할 입력이 실패하는가 (합성) ──────────────
VOCAB = {"Rationale": {"DesignChoice", "Substitution"}, "Loc": {"Paragraph"}, "Interval": {"Overlaps"}}


def _card(cid="c1-a", **over):
    c = {"card_id": cid, "application": "1020000000000", "source_file": "1020000000000_1.txt",
         "legal_ground": "§29②", "target_claims": ["1", "2"], "cited_docs": ["DOC-A", "DOC-B"],
         "deficiency": ["combination-of-documents"]}
    c.update(over)
    return c


def _rec(cid="c1-a", **over):
    r = {"card_id": cid, "part": None, "claims": None, "scope": "whole", "concludes": None,
         "refers_to": [], "sets": [{"d": [0, 1], "base": 0, "ck": False, "rat": ["DesignChoice"]}],
         "links": [{"d": 0, "ct": "a", "dt": "b", "loc": [["Paragraph", "[0001]"]],
                    "cl": {"lo": "1", "li": True, "hi": "2", "ui": True}}]}
    r.update(over)
    return r


def test_checker_accepts_well_formed_fixture():
    bap.check({"c1-a": _card()}, [_rec()], VOCAB)


@pytest.mark.parametrize("cards,recs,msg", [
    ({"c1-a": _card(), "c2-a": _card("c2-a")}, [_rec()], "레코드가 없다"),
    ({"c1-a": _card(), "c3-a": _card("c3-a", deficiency=["judgment-unit-boundary"])},
     [_rec(), _rec("c3-a")], "범위 밖"),
    ({"c1-a": _card()}, [_rec(), _rec()], "중복"),
    ({"c1-a": _card()}, [_rec(claims=[9])], "청구항"),
    ({"c1-a": _card()}, [_rec(sets=[{"d": [5], "base": None, "ck": False, "rat": []}])], "문헌 색인"),
    ({"c1-a": _card()}, [_rec(sets=[{"d": [0], "base": 1, "ck": False, "rat": []}])], "base"),
    ({"c1-a": _card()}, [_rec(sets=[{"d": [], "base": None, "ck": False, "rat": []}])], "빈 묶음"),
    ({"c1-a": _card()}, [_rec(sets=[])], "근거 묶음이 없다"),
    ({"c1-a": _card()}, [_rec(sets=[{"d": [0], "base": None, "ck": False, "rat": ["Invented"]}])], "논거"),
    ({"c1-a": _card()}, [_rec(refers_to=["ghost"])], "참조 대상"),
    ({"c1-a": _card()}, [_rec(links=[{"d": 0, "loc": [["Chapter", "1"]]}])], "좌표"),
    ({"c1-a": _card()}, [_rec(links=[{"d": 0, "loc": [], "rel": "Touches"}])], "구간 관계"),
    ({"c1-a": _card()}, [_rec(links=[{"d": 0, "loc": [], "cl": {"unit": "%"}}])], "경계 없는"),
    ({"c1-a": _card(legal_ground="§42")}, [_rec()], "LegalGround"),
])
def test_checker_rejects(cards, recs, msg):
    with pytest.raises(SystemExit, match=msg):
        bap.check(cards, recs, VOCAB)


def test_frozen_input_drift_is_fatal(tmp_path, monkeypatch):
    fake = tmp_path / "pilot.jsonl"
    fake.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(bap, "PILOT", fake)
    monkeypatch.setattr(bap, "CARDS", fake)
    with pytest.raises(SystemExit, match="동결 입력"):
        bap.load()


# ── ③-b shape: 실패해야 할 입력이 실패하는가 (합성 그래프) ─────────────
def _shape_graph(mutate=None) -> Graph:
    g = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-argument.ttl"):
        g.parse(ONT / f)
    j, s, ln, loc, iv = X.j, X.s, X.l, X.loc, X.iv
    triples = [
        (X.doc, RDF.type, PA.ExaminationDocument),
        (j, RDF.type, PA.ExaminerJudgment), (j, PA.assertedIn, X.doc), (j, PA.onGround, PAKR.Ground_29_2),
        (j, PA.judgesClaim, X.c1), (j, PA.supportedBy, s), (j, PA.judgmentScope, PA.ScopeWholeClaim),
        (s, RDF.type, PA.EvidenceSet), (s, PA.includesDocument, X.d1), (s, PA.hasRationale, PA.RationaleDesignChoice),
        (ln, RDF.type, PA.EvidenceLink), (ln, PA.partOfJudgment, j), (ln, PA.inDocument, X.d1),
        (ln, PA.locator, loc), (loc, RDF.type, PA.DocumentLocator), (loc, PA.locatorType, PA.LocParagraph),
        (loc, PA.locatorValue, Literal("[0001]", datatype=XSD.string)),
        (ln, PA.claimedInterval, iv), (iv, RDF.type, PA.NumericInterval),
        (iv, PA.lowerBound, Literal("1", datatype=XSD.decimal)), (iv, PA.upperBound, Literal("2", datatype=XSD.decimal)),
    ]
    for t in triples:
        g.add(t)
    if mutate:
        mutate(g)
    return g


def _conforms(g: Graph) -> bool:
    ok, _, _ = validate(g, shacl_graph=Graph().parse(SHAPES), inference="none")
    return ok


def test_shapes_accept_minimal_valid_graph():
    assert _conforms(_shape_graph())


@pytest.mark.parametrize("name,mutate", [
    ("근거 묶음 없는 판단", lambda g: g.remove((X.j, PA.supportedBy, X.s))),
    ("문헌도 상식도 없는 묶음", lambda g: g.remove((X.s, PA.includesDocument, X.d1))),
    ("근거 없는 판단(onGround)", lambda g: g.remove((X.j, PA.onGround, PAKR.Ground_29_2))),
    ("뒤집힌 구간", lambda g: g.set((X.iv, PA.lowerBound, Literal("3", datatype=XSD.decimal)))),
    ("경계 없는 구간", lambda g: (g.remove((X.iv, PA.lowerBound, None)), g.remove((X.iv, PA.upperBound, None)))),
    ("종류 없는 좌표", lambda g: g.remove((X.loc, PA.locatorType, PA.LocParagraph))),
    ("두 판단에 속한 링크", lambda g: (g.add((X.j2, RDF.type, PA.ExaminerJudgment)), g.add((X.l, PA.partOfJudgment, X.j2)))),
    ("판정 어휘가 아닌 결론", lambda g: g.add((X.j, PA.concludes, X.notAVerdict))),
    ("범위 밖 scope", lambda g: g.set((X.j, PA.judgmentScope, X.someScope))),
])
def test_shapes_reject(name, mutate):
    assert not _conforms(_shape_graph(mutate)), name


def test_common_knowledge_set_without_document_is_allowed():
    def ck(g):
        g.remove((X.s, PA.includesDocument, X.d1))
        g.add((X.s, PA.reliesOnCommonKnowledge, Literal(True)))
    assert _conforms(_shape_graph(ck))


# ── ④ 실물 파일럿 (원천 계층이 있을 때만) ─────────────────────────────
needs_source = pytest.mark.skipif(not HAS_SOURCE, reason="원천 계층(data/sources/) 없음 — 공개 트리")


@pytest.fixture(scope="module")
def pilot() -> Graph:
    return Graph().parse(data=bap.render(), format="turtle")


@needs_source
def test_pilot_render_is_deterministic():
    assert bap.render() == bap.render()


@needs_source
def test_pilot_uses_only_tbox_defined_predicates(pilot):
    tbox = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-argument.ttl"):
        tbox.parse(ONT / f)
    defined = set(tbox.subjects(RDF.type, OWL.ObjectProperty)) | set(tbox.subjects(RDF.type, OWL.DatatypeProperty))
    allowed_ns = (str(RDF), "http://purl.org/dc/terms/")
    used = {p for p in pilot.predicates() if not str(p).startswith(allowed_ns)}
    assert used and used <= defined, sorted(map(str, used - defined))
    classes = set(tbox.subjects(RDF.type, OWL.Class))
    assert set(pilot.objects(None, RDF.type)) <= classes


@needs_source
def test_pilot_conforms_to_shapes(pilot):
    g = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-argument.ttl"):
        g.parse(ONT / f)
    g += pilot
    # forElement 의 sh:class 는 A-Box 의 ExaminerElement 타입을 본다 — 전체 A-Box 대신 그 타입만 싣는다.
    for el in set(pilot.objects(None, PA.forElement)):
        g.add((el, RDF.type, PA.ExaminerElement))
    assert _conforms(g)


@needs_source
def test_pilot_covers_every_in_scope_card(pilot):
    cards, recs = bap.load()
    in_scope = {cid for cid, c in cards.items() if set(c["deficiency"]) & bap.SELECTED}
    assert len(in_scope) == 54 and {r["card_id"] for r in recs} == in_scope


def _cqs():
    return sorted(CQ_DIR.glob("*.rq"))


def test_one_cq_per_selected_deficiency():
    cqs = _cqs()
    assert len(cqs) == len(bap.SELECTED) == 15
    descs = " ".join(parse_cq(p).desc for p in cqs)
    for slug in bap.SELECTED:
        assert slug in descs, slug


@pytest.mark.parametrize("path", _cqs(), ids=lambda p: p.stem)
def test_cq_returns_nothing_before_schema(path):
    before = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-semi.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-us.ttl"):
        before.parse(ONT / f)
    assert len(list(before.query(parse_cq(path).query))) == 0


@needs_source
@pytest.mark.parametrize("path", _cqs(), ids=lambda p: p.stem)
def test_cq_answers_after_schema(path, pilot):
    after = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-argument.ttl"):
        after.parse(ONT / f)
    after += pilot
    cq = parse_cq(path)
    assert len(list(after.query(cq.query))) >= cq.expect_min
