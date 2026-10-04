"""추론 판단(PLAN-005 논증층 R-Box 규칙)의 계약.

고정하는 것.

  ① 규칙이 **걸려야 할 때만** 걸린다 — R-a(§29①⇒§29②) · R-e(재참조⇒근거 승계)를 합성 그래프로.
     특히 실패해야 할 입력: §29② 가 이미 있는 청구항 · §29③ · 문헌 없는 판단 · 청구항 없는 판단 ·
     자기 참조 · 순환 참조의 두 번째 단계 · 결론 승계.
  ② **추론은 심사관 판단이 아니다** — 생성기 검사와 SHACL 양쪽이 심사관 타입을 거부한다.
  ③ 규칙 개체(T-Box)와 규칙 파일이 서로를 가리킨다 — 고아 규칙 파일도, 없는 파일을 가리키는 개체도 없다.
  ④ 판단 블록 잘라 읽기가 직렬화 전체를 읽은 것과 같은 판단을 낸다.
  ⑤ 실물: 추론 그래프가 쓰는 술어가 전부 T-Box 에 정의 · 소비자 CQ 가 적용 전 규칙 행 0 → 적용 후 ≥1.

합성 그래프에는 실물 통지서 문구를 넣지 않는다(§1-5).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_abox_inferred as bai  # noqa: E402
import build_priorart_modules as bpm  # noqa: E402
from run_cq import parse_cq  # noqa: E402

ONT_DIR = ROOT / "ontology"
SHAPES = ROOT / "validation" / "shapes_priorart_inferred.ttl"
CQR = ROOT / "queries" / "cq_rules"
PA = Namespace("https://w3id.org/sdkb/pa/")
PAKR = Namespace("https://w3id.org/sdkb/pa/kr/")
ONT = Namespace("https://w3id.org/sdkb/ont/")
D = Namespace("https://w3id.org/sdkb/data/")
RA = PAKR.Rule_NoveltyImpliesInventiveness
RE = PA.Rule_EvidenceInheritance


def _tbox() -> Graph:
    g = Graph()
    for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-kr.ttl", "sdkb-priorart-argument.ttl",
              "sdkb-priorart-rules-kr.ttl"):
        g.parse(ONT_DIR / f)
    return g


def _run(layer: str, g: Graph) -> Graph:
    return bai.run_rules(g, [bai.RULES_DIR / f for f in bai.LAYER_RULES[layer]])


# ── 판단층 픽스처 ────────────────────────────────────────────────────
def _pj(g: Graph, name: str, ground: str, doc: str, claims: list[str]) -> URIRef:
    j = D[f"judgment/{name}"]
    g.add((j, RDF.type, ONT.PriorArtJudgment))
    g.add((j, ONT.onGround, ONT[ground]))
    g.add((j, ONT.overPriorArt, D[f"patent/{doc}"]))
    for c in claims:
        g.add((j, ONT.aboutClaim, D[f"claim/rej_1_{c}"]))
    return j


def _claims(inf: Graph, rule) -> set[str]:
    return {str(c).rsplit("_", 1)[1] for n in inf.subjects(PA.inferredBy, rule)
            for c in inf.objects(n, PA.inferredClaim)}


def test_ra_judgment_layer_fills_only_missing_claims():
    g = Graph()
    j = _pj(g, "n1", "Rejection_Novelty", "d1", ["c1", "c2"])
    _pj(g, "i1", "Rejection_Inventiveness", "d1", ["c1"])
    inf = _run("judgment", g)
    assert _claims(inf, RA) == {"c2"}
    node = D["inferred/RA_judgment_n1"]
    assert (node, PA.inferredFrom, j) in inf
    assert (node, PA.onGround, PAKR.Ground_29_2) in inf
    # 근거 술어는 pa:onGround 다 — ont:onGround 는 domain 때문에 노드를 심사관 판단으로 만든다.
    assert not list(inf.triples((None, ONT.onGround, None)))


def test_ra_judgment_layer_does_not_fire_when_inventive_step_already_covers():
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1"])
    _pj(g, "i1", "Rejection_Inventiveness", "d1", ["c1"])
    assert len(_run("judgment", g)) == 0


def test_ra_judgment_layer_other_document_does_not_block():
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1"])
    _pj(g, "i1", "Rejection_Inventiveness", "d2", ["c1"])
    assert _claims(_run("judgment", g), RA) == {"c1"}


def test_ra_judgment_layer_claimless_judgment_does_not_fire_and_is_counted():
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", [])
    assert len(_run("judgment", g)) == 0
    assert bai._skips(g, "judgment")["novelty_judgment_without_claim"] == 1


# ── 논증층 픽스처 ────────────────────────────────────────────────────
def _ej(g: Graph, name: str, ground, claims: list[str], docs: list[str] | None,
        refers: list[str] = (), concludes=None) -> URIRef:
    j = D[f"pilot/judgment/{name}"]
    g.add((j, RDF.type, PA.ExaminerJudgment))
    g.add((j, PA.onGround, ground))
    for c in claims:
        g.add((j, PA.judgesClaim, D[f"claim/rej_1_{c}"]))
    if docs is not None:
        s = URIRef(f"{j}_s0")
        g.add((s, RDF.type, PA.EvidenceSet))
        g.add((j, PA.supportedBy, s))
        for d in docs:
            g.add((s, PA.includesDocument, D[f"pilot/doc/{d}"]))
    for r in refers:
        g.add((j, PA.refersToJudgment, D[f"pilot/judgment/{r}"]))
    if concludes is not None:
        g.add((j, PA.concludes, concludes))
    return j


def test_ra_argument_layer_fires_for_novelty_only_claim():
    g = Graph()
    _ej(g, "a", PAKR.Ground_29_1, ["c1"], ["d1"])
    assert _claims(_run("argument", g), RA) == {"c1"}


def test_ra_argument_layer_does_not_fire_on_other_grounds():
    # §29③(확대된 선원)은 진보성의 선행기술이 될 수 없다 — 규칙 조건에 없어야 한다.
    g = Graph()
    _ej(g, "a", URIRef(str(PAKR) + "Ground_29_3"), ["c1"], ["d1"])
    _ej(g, "b", PAKR.Ground_29_2, ["c2"], ["d1"])
    assert _claims(_run("argument", g), RA) == set()


def test_ra_argument_layer_needs_a_document():
    g = Graph()
    _ej(g, "a", PAKR.Ground_29_1, ["c1"], [])
    assert _claims(_run("argument", g), RA) == set()
    assert bai._skips(g, "argument")["novelty_judgment_without_document"] == 1


def test_ra_argument_layer_respects_explicit_and_referencing_inventive_judgments():
    g = Graph()
    _ej(g, "a", PAKR.Ground_29_1, ["c1", "c2", "c3"], ["d1"])
    _ej(g, "b", PAKR.Ground_29_2, ["c1"], ["d1"])              # 같은 청구항·같은 문헌을 직접 다룸
    _ej(g, "c", PAKR.Ground_29_2, ["c2"], None, refers=["a"])  # a 를 전제로 참조하며 c2 를 다룸
    assert _claims(_run("argument", g), RA) == {"c3"}


def test_re_inherits_support_but_not_conclusion():
    g = Graph()
    _ej(g, "t", PAKR.Ground_29_1, ["c1"], ["d1"], concludes=PA.VerdictIdentical)
    r = _ej(g, "r", PAKR.Ground_29_2, ["c2"], ["d2"], refers=["t"])
    inf = _run("argument", g)
    nodes = set(inf.subjects(PA.inferredBy, RE))
    assert nodes == {D["inferred/RE_pilot_judgment_r__pilot_judgment_t"]}
    (node,) = nodes
    assert set(inf.objects(node, PA.inferredFrom)) == {r, D["pilot/judgment/t"]}
    assert set(inf.objects(node, PA.inheritedSupport)) == {URIRef(f"{D}pilot/judgment/t_s0")}
    assert not list(inf.triples((None, PA.concludes, None)))


def test_re_self_reference_does_not_fire():
    g = Graph()
    _ej(g, "r", PAKR.Ground_29_2, ["c1"], ["d1"], refers=["r"])
    assert not set(_run("argument", g).subjects(PA.inferredBy, RE))
    assert bai._skips(g, "argument")["self_reference"] == 1


def test_re_follows_one_hop_only_through_a_cycle():
    g = Graph()
    _ej(g, "r", PAKR.Ground_29_2, ["c1"], ["d1"], refers=["t"])
    _ej(g, "t", PAKR.Ground_29_2, ["c2"], ["d2"], refers=["r"])
    inf = _run("argument", g)
    for node in inf.subjects(PA.inferredBy, RE):
        prem = set(inf.objects(node, PA.inferredFrom))
        (s,) = set(inf.objects(node, PA.inheritedSupport))
        # 승계한 묶음은 **직접 참조된** 판단의 것이다 — 두 단계를 돌아 자기 묶음을 승계하지 않는다.
        owner = URIRef(str(s).rsplit("_s", 1)[0])
        (referrer,) = prem - {owner}
        assert (referrer, PA.refersToJudgment, owner) in g
    assert len(set(inf.subjects(PA.inferredBy, RE))) == 2


def test_re_unresolved_reference_is_counted():
    g = Graph()
    _ej(g, "r", PAKR.Ground_29_2, ["c1"], ["d1"], refers=["missing"])
    assert not set(_run("argument", g).subjects(PA.inferredBy, RE))
    assert bai._skips(g, "argument")["reference_target_not_a_judgment"] == 1


# ── ② 추론 ≠ 심사관 판단 ─────────────────────────────────────────────
def _one_inferred() -> tuple[Graph, Graph]:
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1"])
    return g, _run("judgment", g)


@pytest.mark.parametrize("bad_type", [PA.ExaminerJudgment, ONT.PriorArtJudgment])
def test_generator_refuses_inferred_node_typed_as_examiner_judgment(bad_type):
    src, inf = _one_inferred()
    inf.add((next(inf.subjects(RDF.type, PA.InferredJudgment)), RDF.type, bad_type))
    with pytest.raises(SystemExit):
        bai.check_inferred(inf, src)


def test_generator_refuses_premise_missing_from_input():
    src, inf = _one_inferred()
    with pytest.raises(SystemExit):
        bai.check_inferred(inf, Graph())


def _conforms(data: Graph) -> bool:
    ok, _, _ = validate(data + _tbox(), shacl_graph=Graph().parse(SHAPES), inference="none")
    return ok


def test_shape_accepts_generated_inference():
    assert _conforms(_one_inferred()[1])


@pytest.mark.parametrize("mutate", ["examiner_type", "priorart_type", "no_rule", "no_premise", "neither"])
def test_shape_rejects_broken_inference(mutate):
    _, inf = _one_inferred()
    n = next(inf.subjects(RDF.type, PA.InferredJudgment))
    if mutate == "examiner_type":
        inf.add((n, RDF.type, PA.ExaminerJudgment))
    elif mutate == "priorart_type":
        inf.add((n, RDF.type, ONT.PriorArtJudgment))
    elif mutate == "no_rule":
        inf.remove((n, PA.inferredBy, None))
    elif mutate == "no_premise":
        inf.remove((n, PA.inferredFrom, None))
    elif mutate == "neither":
        inf.remove((n, PA.onGround, None))
    assert not _conforms(inf)


# ── ③ 규칙 개체 ↔ 규칙 파일 ──────────────────────────────────────────
def test_rule_individuals_and_rule_files_point_at_each_other():
    tb = _tbox()
    rules = set(tb.subjects(RDF.type, PA.InferenceRule))
    assert rules == {RA, RE}
    named = set()
    for r in rules:
        assert list(tb.objects(r, PA.ruleAuthority)), r
        for q in tb.objects(r, PA.ruleQuery):
            assert (ROOT / str(q)).is_file(), q
            assert f"# rule: {tb.namespace_manager.normalizeUri(r)}" in (ROOT / str(q)).read_text(encoding="utf-8")
            named.add(Path(str(q)).name)
    on_disk = {p.name for p in bai.RULES_DIR.glob("*.rq")}
    assert named == on_disk == {f for fs in bai.LAYER_RULES.values() for f in fs}


def test_rules_module_imports_argument_and_kr_only():
    g = Graph().parse(ONT_DIR / "sdkb-priorart-rules-kr.ttl")
    assert set(g.objects(bpm.RULES_KR_IRI, OWL.imports)) == {bpm.ARG_IRI, bpm.KR_IRI}
    # 규칙 개체 외의 어휘를 선언하지 않는다 — 어휘는 ⑤ 에 있다.
    assert not set(g.subjects(RDF.type, OWL.Class)) and not set(g.subjects(RDF.type, OWL.ObjectProperty))


# ── ④ 판단 블록 잘라 읽기 ────────────────────────────────────────────
def test_slice_judgments_matches_full_parse(tmp_path):
    g = Graph()
    g.bind("ont", ONT)
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1", "c2"])
    _pj(g, "i1", "Rejection_Inventiveness", "d1", ["c1"])
    other = D["patent/kr_1"]
    g.add((other, ONT.hasJudgment, D["judgment/n1"]))
    g.add((other, RDFS.label, Literal("x")))
    p = tmp_path / "cf.ttl"
    g.serialize(p, format="turtle")
    sliced, n = bai.slice_judgments(p)
    assert n == 2
    want = Graph()
    for t in g:
        if str(t[0]).startswith(f"{D}judgment/"):
            want.add(t)
    assert set(sliced) == set(want)


def test_rule_output_is_deterministic():
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1", "c2", "c3"])
    a = bpm._emit(_run("judgment", g), bai.PREFIXES, "#")
    b = bpm._emit(_run("judgment", g), bai.PREFIXES, "#")
    assert a == b


# ── ⑤ 실물 ───────────────────────────────────────────────────────────
needs_inferred = pytest.mark.skipif(not bai.OUT.exists(), reason="추론 판단 미빌드 (make abox-inferred)")
needs_pilot = pytest.mark.skipif(not bai.PILOT_OUT.exists(), reason="원천 계층 없음 — 공개 트리")


def _defined_predicates() -> set:
    tb = Graph()
    for f in ("sdkb-patent.ttl",) + tuple(m[0] for m in bpm.MODULES):
        tb.parse(ONT_DIR / f)
    return {s for t in (OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property)
            for s in tb.subjects(RDF.type, t)} | {RDF.type}


@needs_inferred
def test_real_inferred_graph_uses_only_tbox_predicates_and_matches_report():
    inf = Graph().parse(bai.OUT)
    assert {p for _, p, _ in inf} <= _defined_predicates()
    rep = json.loads(bai.REPORT.read_text(encoding="utf-8"))
    assert rep["triples"] == rep["layers"]["judgment"]["triples"] == len(inf)
    assert rep["layers"]["judgment"]["rules"]["pakr:Rule_NoveltyImpliesInventiveness"]["nodes"] == \
        len(set(inf.subjects(PA.inferredBy, RA))) > 0


@needs_pilot
def test_real_pilot_inferred_graph_uses_only_tbox_predicates():
    inf = Graph().parse(bai.PILOT_OUT)
    assert {p for _, p, _ in inf} <= _defined_predicates()
    assert set(inf.subjects(PA.inferredBy, RE))


@needs_pilot
@pytest.mark.parametrize("path,col,tag", [
    (CQR / "CQR01_inventive_step_objection_by_source.rq", 2, "rule"),
    (CQR / "CQR02_support_direct_and_inherited.rq", 2, "inherited"),
])
def test_consumer_cq_rows_appear_only_after_rules(path, col, tag):
    pilot = Graph().parse(bai.PILOT)
    q = parse_cq(path).query
    before = [r for r in (_tbox() + pilot).query(q) if str(r[col]) == tag]
    after = [r for r in (_tbox() + pilot + Graph().parse(bai.PILOT_OUT)).query(q) if str(r[col]) == tag]
    assert len(before) == 0 and len(after) >= parse_cq(path).expect_min


def test_consumer_cq_on_judgment_layer_fixture():
    g = Graph()
    _pj(g, "n1", "Rejection_Novelty", "d1", ["c1"])
    q = parse_cq(CQR / "CQR01_inventive_step_objection_by_source.rq").query
    assert not [r for r in (_tbox() + g).query(q) if str(r[2]) == "rule"]
    assert [r for r in (_tbox() + g + _run("judgment", g)).query(q) if str(r[2]) == "rule"]
