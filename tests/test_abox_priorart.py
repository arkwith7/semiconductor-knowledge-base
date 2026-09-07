"""PLAN-005 단계 5-A — 선행기술 판단층 A-Box 의 계약 고정.

합성 fixture 로 순수 함수를 검사하고, 실물 A-Box 는 빌드돼 있을 때만 검사한다(선례:
tests/test_b_layer_prior_art_abox.py). 셋은 **실패해야 할 입력이 실패하는가**를 직접
확인한다(CLAUDE.md §2 5단계(b)) — 신규 shape 둘이 위반 델타를 무는가, 미바인딩 타입이
거부되는가, scope 밖 행이 빌드를 죽이는가.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import pandas as pd
import pytest
from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_abox_priorart as m  # noqa: E402
from scripts.check_priorart_invariants import check_query  # noqa: E402
from scripts.run_cq import load_graph, parse_cq  # noqa: E402

PA = "https://w3id.org/sdkb/pa/"
ONT = "https://w3id.org/sdkb/ont/"
DATA = "https://w3id.org/sdkb/data/"
ONT_DIR = ROOT / "ontology"
ABOX = ONT_DIR / "sdkb-abox-priorart.ttl"
REPORT = ROOT / "data" / "reports" / "abox_priorart_report.json"
SHAPES = ROOT / "validation" / "shapes_priorart.ttl"
TBOX = [ONT_DIR / f for f in ("sdkb-priorart-core.ttl", "sdkb-priorart-semi.ttl",
                              "sdkb-priorart-kr.ttl", "sdkb-patent.ttl", "sdkb-governance.ttl")]

needs_abox = pytest.mark.skipif(not ABOX.exists() or not REPORT.exists(),
                                reason="priorart A-Box 미빌드 — make abox-priorart")


# ── 합성 fixture ──────────────────────────────────────────────────────
def _tiny_inputs():
    """독립항 2 · 종속항 2(한 항은 부모 결번) · 미바인딩 개념 하나 · 문헌 2."""
    df = pd.DataFrame({
        "publication_id": ["kr_A", "kr_A", "kr_A", "kr_B", "kr_B"],
        "side": ["rej", "rej", "rej", "cited", "cited"],
        "claim_id": ["rej_A_c1", "rej_A_c2", "rej_A_c9", "cited_B_c1", "cited_B_c1"],
        "is_independent": [True, False, False, True, True],
        "feature_concept": [["material:sio2", "skill:x"], ["process:etch"], ["material:hfo2"],
                            ["material:dielectric"], []],
        "depends_on_claim": [[], ["rej_A_c1"], ["rej_A_c7"], [], []],
    })
    bound = {"material:sio2", "process:etch", "material:hfo2", "material:dielectric"}
    return df, bound


def _tiny_graph():
    df, bound = _tiny_inputs()
    concepts, _ = m.claim_concepts(df, bound)
    claims = df[["claim_id", "side", "is_independent"]].drop_duplicates("claim_id")
    is_indep = dict(zip(claims["claim_id"], claims["is_independent"]))
    parents = {"rej_A_c2": ["rej_A_c1"], "rej_A_c9": ["rej_A_c7"]}
    roots, _ = m.root_independents(is_indep, parents)
    profiles, _ = m.build_profiles(claims, concepts, roots)
    disclosures, _ = m.build_disclosures(df, concepts)
    hier = [(URIRef(DATA + "material/sio2"), URIRef(DATA + "material/dielectric"))]
    return profiles, disclosures, hier


def _tbox() -> Graph:
    g = Graph()
    for p in TBOX:
        g.parse(p, format="turtle")
    return g


def _shacl(data: Graph):
    conforms, _, text = validate(data, shacl_graph=Graph().parse(SHAPES, format="turtle"),
                                 inference="none")
    return conforms, text


# ── ① 결정성 ────────────────────────────────────────────────────────
def test_emit_graph_is_byte_identical_across_shuffled_inputs():
    profiles, disclosures, hier = _tiny_graph()
    a = m.emit_graph(profiles, disclosures, hier, []).serialize(format="turtle")
    p2, d2 = list(profiles), list(disclosures)
    random.Random(7).shuffle(p2); random.Random(7).shuffle(d2)
    b = m.emit_graph(p2, d2, hier, []).serialize(format="turtle")
    assert a == b


@needs_abox
def test_report_sha256_matches_shipped_ttl():
    """손편집·부분 재생성을 잡는다 — 리포트가 기술하는 파일이 실물이어야 한다."""
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["ttl_sha256"] == hashlib.sha256(ABOX.read_bytes()).hexdigest()


# ── ② 술어·어휘 계약 ─────────────────────────────────────────────────
@pytest.fixture(scope="module")
def abox() -> Graph:
    if not ABOX.exists():
        pytest.skip("priorart A-Box 미빌드")
    g = Graph(); g.parse(ABOX, format="turtle")
    return g


@needs_abox
def test_all_pa_and_ont_terms_declared_in_tbox(abox):
    """A-Box 가 쓰는 pa:/pakr:/ont: 술어·클래스·개체가 전부 T-Box 에 선언돼 있다(§2 5단계(b))."""
    tbox = _tbox()
    declared = {str(s) for s in tbox.subjects(RDF.type, None)
                if str(s).startswith((PA, ONT))}
    used = {str(p) for p in abox.predicates() if str(p).startswith((PA, ONT))}
    used |= {str(o) for o in abox.objects(None, RDF.type) if str(o).startswith((PA, ONT))}
    used |= {str(o) for _, p, o in abox if str(p).startswith(PA) and str(o).startswith((PA, ONT))}
    missing = sorted(used - declared)
    assert not missing, f"T-Box 에 없는 어휘: {missing}"


@needs_abox
def test_abox_declares_no_vocabulary(abox):
    """ABox 안의 인라인 어휘 선언 0 (§1-2)."""
    for kind in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        assert not list(abox.subjects(RDF.type, kind))


@needs_abox
def test_no_citation_edges_in_abox(abox):
    """누출 진술의 증거 — 정답 간선은 이 층에 없다."""
    for p in ("overPriorArt", "hasPriorArt", "hasPriorArtExaminer", "hasJudgment"):
        assert (None, URIRef(ONT + p), None) not in abox


# ── ③ SHACL — 실물에 걸리고, 위반 델타를 문다 ────────────────────────
@needs_abox
def test_shipped_abox_conforms_and_targets_are_not_vacuous(abox):
    data = _tbox()
    data.parse(ONT_DIR / "sdkb-core-data.ttl", format="turtle")
    data += abox
    conforms, text = _shacl(data)
    assert conforms, text[:2000]
    for cls in ("ClaimProfile", "Disclosure", "ExaminerElement"):
        assert len(list(abox.subjects(RDF.type, URIRef(PA + cls)))) > 0, cls


def _delta_graph() -> Graph:
    g = _tbox()
    g.parse(ONT_DIR / "sdkb-core-data.ttl", format="turtle")
    return g


def test_shape_rejects_profile_without_essential_and_disclosure_without_discloses():
    g = _delta_graph()
    g.add((URIRef(DATA + "profile/x"), RDF.type, URIRef(PA + "ClaimProfile")))
    g.add((URIRef(DATA + "profile/x"), URIRef(PA + "profileOf"), URIRef(DATA + "claim/x")))
    conforms, _ = _shacl(g)
    assert not conforms
    g = _delta_graph()
    g.add((URIRef(DATA + "disclosure/y"), RDF.type, URIRef(PA + "Disclosure")))
    g.add((URIRef(DATA + "disclosure/y"), URIRef(PA + "disclosureOf"), URIRef(DATA + "patent/y")))
    conforms, _ = _shacl(g)
    assert not conforms


def test_shape_rejects_essential_concept_outside_technical_concept():
    """미바인딩 타입(ont:Skill)의 개체를 필수구성으로 넣으면 sh:class 가 문다(결정 3 의 근거)."""
    g = _delta_graph()
    skill = next(s for s in g.subjects(RDF.type, URIRef(ONT + "Skill")))
    node = URIRef(DATA + "profile/z")
    g.add((node, RDF.type, URIRef(PA + "ClaimProfile")))
    g.add((node, URIRef(PA + "profileOf"), URIRef(DATA + "claim/z")))
    g.add((node, URIRef(PA + "essentialConcept"), skill))
    conforms, _ = _shacl(g)
    assert not conforms
    # 같은 자리에 바인딩 타입(ont:Material) 개체를 넣으면 통과한다 — 게이트가 방향을 안다.
    g.remove((node, URIRef(PA + "essentialConcept"), skill))
    mat = next(s for s in g.subjects(RDF.type, URIRef(ONT + "Material")))
    g.add((node, URIRef(PA + "essentialConcept"), mat))
    conforms, text = _shacl(g)
    assert conforms, text[:1000]


# ── ④ 생성 규칙 (합성) ──────────────────────────────────────────────
def test_profiles_and_optional_concepts_follow_dependency_roots():
    profiles, disclosures, _ = _tiny_graph()
    by_id = {p.claim_id: p for p in profiles}
    assert set(by_id) == {"rej_A_c1", "cited_B_c1"}
    assert by_id["rej_A_c1"].essential == ("material:sio2",)      # skill:x 는 미바인딩 → 제외
    assert by_id["rej_A_c1"].optional == ("process:etch",)         # c9 는 부모 결번 → 버림
    assert {d.publication_id: d.concepts for d in disclosures} == {
        "kr_A": ("material:hfo2", "material:sio2", "process:etch"),
        "kr_B": ("material:dielectric",)}


def test_unbound_concepts_are_counted_not_emitted():
    df, bound = _tiny_inputs()
    _, stat = m.claim_concepts(df, bound)
    assert stat["distinct_concepts_unbound"] == 1
    assert stat["claim_concept_pairs_unbound"] == 1


def test_examiner_rows_without_caption_or_claim_are_not_emitted():
    rows = pd.DataFrame({
        "application_number": ["1020120000001"] * 3,
        "source_file": ["1020120000001_9.txt"] * 3,
        "table_index": [1, 1, 1], "element_group": [1, 1, 1], "element_no": [1, 2, 3],
        "caption_claim_no": pd.array([1, None, 7], dtype="Int64"),
        "judgment_raw": ["동일", "차이", "차이"],
        "judgment": ["Identical", "Different", "Different"],
    })
    out, stat = m.build_examiner_elements(rows, {"rej_1020120000001_c1"}, {"1020120000001"})
    assert [e.element_no for e in out] == [1]
    assert stat["dropped_no_caption"] == 1
    assert stat["dropped_caption_claim_not_in_graph"] == 1
    assert stat["emitted"] == 1 and stat["documents_emitted"] == 1


def test_examiner_element_out_of_scope_aborts():
    rows = pd.DataFrame({
        "application_number": ["1020129999999"], "source_file": ["1020129999999_1.txt"],
        "table_index": [1], "element_group": [1], "element_no": [1],
        "caption_claim_no": pd.array([1], dtype="Int64"),
        "judgment_raw": ["동일"], "judgment": ["Identical"],
    })
    with pytest.raises(SystemExit):
        m.build_examiner_elements(rows, {"rej_1020129999999_c1"}, {"1020120000001"})


def test_covered_by_is_materialized_one_hop_without_closure():
    """a→b→c 계층에서 coveredBy 는 (a,b)·(b,c) 뿐 — (a,c) 가 있으면 전이 폐쇄를 만든 것이다."""
    a, b, c = (URIRef(DATA + f"material/{x}") for x in "abc")
    g = m.emit_graph([], [], [(a, b), (b, c)], [])
    cov = set(g.subject_objects(URIRef(PA + "coveredBy")))
    assert cov == {(a, b), (b, c)}
    assert cov == set(g.subject_objects(URIRef(PA + "broaderConcept")))


# ── ⑤ 실물 계수·누출 ─────────────────────────────────────────────────
@needs_abox
def test_graph_counts_match_report(abox):
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    count = lambda cls: len(list(abox.subjects(RDF.type, URIRef(PA + cls))))  # noqa: E731
    assert count("ClaimProfile") == rep["profiles"]["emitted"]
    assert count("Disclosure") == rep["disclosures"]["emitted"]
    assert count("ExaminerElement") == rep["examiner_elements"]["emitted"]
    assert len(abox) == rep["triples"]
    e = rep["examiner_elements"]
    assert e["emitted"] + e["dropped_no_caption"] + e["dropped_caption_claim_not_in_graph"] == e["rows"]
    h = rep["hierarchy"]
    assert h["broader_emitted"] == h["covered_by_materialized_from_broader"]
    assert len(list(abox.subject_objects(URIRef(PA + "coveredBy")))) == h["broader_emitted"]


@needs_abox
def test_every_examiner_element_application_in_scope(abox):
    scope = m.scope_applications()
    for _, o in abox.subject_objects(URIRef(PA + "concernsClaim")):
        local = str(o).rsplit("/", 1)[-1]           # rej_{app}_c{n}
        assert local.startswith("rej_")
        assert local.split("_")[1] in scope, local


@needs_abox
def test_essential_and_optional_are_disjoint(abox):
    ess, opt = URIRef(PA + "essentialConcept"), URIRef(PA + "optionalConcept")
    for i, s in enumerate(abox.subjects(RDF.type, URIRef(PA + "ClaimProfile"))):
        if i >= 1000:
            break
        assert not (set(abox.objects(s, ess)) & set(abox.objects(s, opt))), s


# ── ⑥ CQ32 — 실물에서 1행 이상이고 여전히 중립이다 ────────────────────
@needs_abox
def test_cq32_returns_rows_and_stays_neutral():
    q = ROOT / "queries" / "cq" / "CQ32_novelty_uncovered_essential_concepts.rq"
    assert check_query(q) == []
    cq = parse_cq(q)
    assert cq.expect_min == 1
    g, _, _ = load_graph(TBOX[:3] + [ONT_DIR / "sdkb-core-data.ttl", ABOX])
    rows = len(list(g.query(cq.query)))
    assert rows >= 1


# ── ⑦ 배선 ──────────────────────────────────────────────────────────
def test_makefile_wires_abox_priorart_into_validate_without_backdoor():
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "abox-priorart:" in mk
    validate_block = mk.split("\nvalidate:", 1)[1].split("\ntest:", 1)[0]
    assert "ontology/sdkb-abox-priorart.ttl" in validate_block
    priorart_lines = [ln for ln in validate_block.splitlines() if "sdkb-abox-priorart" in ln]
    assert not any("|| echo" in ln for ln in priorart_lines)
    assert "abox-priorart" in mk.split("\nabox-full:", 1)[1].splitlines()[0]


def test_graph_signature_registers_layer():
    from scripts.report_graph_signature import ABOX_LAYERS
    assert any(n == "sdkb-abox-priorart" and r == "abox_priorart_report.json"
               for n, _, r in ABOX_LAYERS)


def test_gitignore_excludes_abox():
    assert "ontology/sdkb-abox-priorart.ttl" in (ROOT / ".gitignore").read_text(encoding="utf-8")
