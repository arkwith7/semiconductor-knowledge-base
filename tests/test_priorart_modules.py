"""PLAN-005 단계 4 — 선행기술 판단층 T-Box·R-Box 의 계약 고정.

여기서 고정하는 것은 넷이고, 셋은 **실패해야 할 입력이 실패하는가**를 직접 확인한다
(CLAUDE.md §2 5단계(b): 위반 델타를 넣었을 때 거부하지 않으면 그건 게이트가 아니다).

  ① 결정성      — 같은 원천 → 같은 바이트
  ② 불변식 A    — core 에 도메인·관할 IRI 를 주입하면 **죽는가**
  ③ 불변식 B    — 태스크 질의 필수부의 행정 어휘를 **잡는가** · OPTIONAL 은 통과시키는가
  ④ 접지 계약   — 심사관 구성요소는 캡션 청구항으로만 접지된다(단계 4 승인 결정 1)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_priorart_modules import render  # noqa: E402
from scripts.check_priorart_invariants import (  # noqa: E402
    check_core, check_query, task_queries,
)

PA = "https://w3id.org/sdkb/pa/"
ONT = "https://w3id.org/sdkb/ont/"
ONT_DIR = ROOT / "ontology"
CORE = ONT_DIR / "sdkb-priorart-core.ttl"
SEMI = ONT_DIR / "sdkb-priorart-semi.ttl"
KR = ONT_DIR / "sdkb-priorart-kr.ttl"


# ── ① 결정성 ────────────────────────────────────────────────────────
def test_build_is_byte_identical_across_runs():
    """두 번 지어 다르면 하류의 sha256 핀이 매 빌드마다 깨진다(§0)."""
    assert render() == render()


def test_working_tree_matches_generator():
    """손으로 고친 TTL 을 잡는다 — 고치면 다음 빌드에 조용히 사라진다(§1-1)."""
    rendered = render()
    for fname, text in rendered.items():
        assert (ONT_DIR / fname).read_text(encoding="utf-8") == text, (
            f"{fname} 이 생성기 출력과 다르다. `make priorart` 로 재생성할 것"
        )


def test_check_flag_returns_zero_on_clean_tree():
    r = subprocess.run([sys.executable, "scripts/build_priorart_modules.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ── ② 불변식 A — core 순도 ──────────────────────────────────────────
def test_core_is_clean():
    assert check_core(CORE) == []


@pytest.mark.parametrize("iri,why", [
    (ONT + "Process", "도메인"),
    ("https://w3id.org/sdkb/gov/JurisdictionKR", "관할"),
    ("https://w3id.org/sdkb/pa/kr/Ground_29_1", "관할"),
    ("http://w3id.org/SemicONTO/Etching", "도메인(외부)"),
])
def test_core_purity_gate_rejects_injected_iri(tmp_path, iri, why):
    """**게이트가 무는가.** 물지 않으면 이식성 주장은 검증되지 않은 문장일 뿐이다."""
    bad = tmp_path / "core_bad.ttl"
    bad.write_text(CORE.read_text(encoding="utf-8")
                   + f'\n<{PA}TechnicalConcept> <{RDFS.seeAlso}> <{iri}> .\n',
                   encoding="utf-8")
    fails = check_core(bad)
    assert fails, f"{why} IRI {iri} 를 주입했는데 통과했다"
    assert iri in fails[0]


def test_core_declares_no_domain_subclasses():
    """core 는 TechnicalConcept 의 하위를 선언하지 않는다 — 그것이 슬롯의 뜻이다."""
    g = Graph(); g.parse(CORE, format="turtle")
    subs = list(g.subjects(RDFS.subClassOf, URIRef(PA + "TechnicalConcept")))
    assert subs == []
    # 하위는 도메인 바인딩이 넣는다.
    gs = Graph(); gs.parse(SEMI, format="turtle")
    assert len(list(gs.subjects(RDFS.subClassOf, URIRef(PA + "TechnicalConcept")))) >= 6


def test_covered_by_is_not_transitive():
    """전이를 붙이면 심사관이 한 적 없는 치환이 자동 생성된다(§3.3)."""
    g = Graph(); g.parse(CORE, format="turtle")
    cov = URIRef(PA + "coveredBy")
    assert (cov, RDF.type, OWL.TransitiveProperty) not in g
    # 확장자 셋은 하위 술어로 살아 있어야 한다 (역할이 바뀔 뿐 사라지지 않는다).
    subs = set(g.subjects(RDFS.subPropertyOf, cov))
    assert URIRef(PA + "broaderConcept") in subs
    assert URIRef(PA + "substitutableWith") in subs


def test_imports_flow_one_way_and_existing_files_untouched():
    """결합은 신규 → 기존 방향뿐이다. 역방향이면 하류가 핀한 sha256 이 깨진다(§0)."""
    for f in (SEMI, KR):
        g = Graph(); g.parse(f, format="turtle")
        imports = {str(o) for o in g.objects(None, OWL.imports)}
        assert "https://w3id.org/sdkb/pa" in imports
    core = Graph(); core.parse(CORE, format="turtle")
    assert list(core.objects(None, OWL.imports)) == []
    # 기존 T-Box 는 pa: 를 한 건도 언급하지 않는다 = 한 줄도 고쳐지지 않았다.
    for name in ("sdkb-core.ttl", "sdkb-patent.ttl", "sdkb-governance.ttl"):
        assert PA not in (ONT_DIR / name).read_text(encoding="utf-8"), name


# ── ③ 불변식 B — 태스크 질의의 행정 어휘 ────────────────────────────
NEUTRAL_HEADER = "# suite: pa\n# task-neutral: required\n"
PREFIXES = f"PREFIX pa: <{PA}>\nPREFIX ont: <{ONT}>\n"


def _q(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(NEUTRAL_HEADER + PREFIXES + body, encoding="utf-8")
    return p


def test_admin_vocab_in_required_part_is_rejected(tmp_path):
    q = _q(tmp_path, "bad.rq",
           "SELECT ?p WHERE { ?p a ont:Patent ; pa:essentialConcept ?c }")
    fails = check_query(q)
    assert fails and "ont/Patent" in fails[0]


def test_admin_vocab_inside_optional_is_allowed(tmp_path):
    q = _q(tmp_path, "ok.rq",
           "SELECT ?x WHERE { ?x a pa:ClaimProfile . "
           "OPTIONAL { ?j a ont:PriorArtJudgment ; ont:onGround ?g } }")
    assert check_query(q) == []


def test_admin_vocab_in_union_branch_is_rejected(tmp_path):
    """UNION 가지는 보수적으로 필수로 본다 — 한 가지만 특허를 요구해도 종속이다."""
    q = _q(tmp_path, "union.rq",
           "SELECT ?x WHERE { { ?x a pa:ClaimProfile } UNION { ?x a ont:RejectedPatent } }")
    assert check_query(q)


def test_unparseable_query_fails_rather_than_passes(tmp_path):
    q = _q(tmp_path, "broken.rq", "SELECT ?x WHERE { ?x a pa:ClaimProfile")
    assert check_query(q)


def test_shipped_task_query_is_neutral_and_discovered():
    qs = task_queries(ROOT / "queries")
    names = {p.name for p in qs}
    assert "CQ32_novelty_uncovered_essential_concepts.rq" in names
    for q in qs:
        assert check_query(q) == [], q.name


def test_task_query_expect_min_is_zero_until_stage5():
    """A-Box 가 없는 동안 0행이 정상이다. 1 로 올리는 시점은 단계 5 와 같은 커밋."""
    text = (ROOT / "queries" / "cq" /
            "CQ32_novelty_uncovered_essential_concepts.rq").read_text(encoding="utf-8")
    assert "# expect-min: 0" in text
    assert "단계 5" in text


# ── ④ 접지 계약 (단계 4 승인 결정 1) ────────────────────────────────
def test_examiner_element_grounds_on_caption_claim_only():
    g = Graph(); g.parse(CORE, format="turtle")
    concerns = URIRef(PA + "concernsClaim")
    assert (concerns, RDF.type, OWL.ObjectProperty) in g
    assert (concerns, RDFS.domain, URIRef(PA + "ExaminerElement")) in g
    # elementGroup 은 **데이터 술어**다 — 청구항을 가리킬 수 없다는 것이 구조로 보장된다.
    grp = URIRef(PA + "elementGroup")
    assert (grp, RDF.type, OWL.DatatypeProperty) in g
    assert (grp, RDF.type, OWL.ObjectProperty) not in g
    assert (grp, RDFS.range, XSD.integer) in g
    # 요소↔요소 정렬 술어는 만들지 않았다 (일치율 15.1% · 하지 않은 정렬을 한 척하지 않는다).
    locals_ = {str(s)[len(PA):] for s in g.subjects(RDF.type, OWL.ObjectProperty)
               if str(s).startswith(PA)}
    assert not {n for n in locals_ if "alignsWith" in n or "sameFeature" in n}


def _shacl(data: Graph):
    from pyshacl import validate as sh_validate
    shapes = Graph(); shapes.parse(ROOT / "validation" / "shapes_priorart.ttl", format="turtle")
    conforms, _, text = sh_validate(data, shacl_graph=shapes, inference="none")
    return conforms, text


def test_shape_rejects_mined_axiom_without_jurisdiction():
    """관할 표기 없는 채굴 공리는 위반이다 (PLAN-001 §1.10(e) · 완료기준 7)."""
    g = Graph(); g.parse(CORE, format="turtle")
    a = URIRef("https://w3id.org/sdkb/data/axiom/test1")
    g.add((a, RDF.type, URIRef(PA + "MinedAxiom")))
    g.add((a, URIRef(PA + "axiomConfidence"), Literal("confirmed")))
    conforms, text = _shacl(g)
    assert not conforms and "underJurisdiction" in text


def test_shape_rejects_examiner_element_without_claim():
    """elementGroup 만 있고 청구항 접지가 없으면 위반이다 — 결정 1 의 기계적 근거."""
    g = Graph(); g.parse(CORE, format="turtle")
    e = URIRef("https://w3id.org/sdkb/data/elem/test1")
    g.add((e, RDF.type, URIRef(PA + "ExaminerElement")))
    g.add((e, URIRef(PA + "elementGroup"), Literal(2, datatype=XSD.integer)))
    g.add((e, URIRef(PA + "elementNo"), Literal(3, datatype=XSD.integer)))
    g.add((e, URIRef(PA + "hasVerdict"), URIRef(PA + "VerdictIdentical")))
    conforms, text = _shacl(g)
    assert not conforms and "concernsClaim" in text


def test_shipped_modules_conform_to_their_own_shapes():
    g = Graph()
    for f in (CORE, SEMI, KR):
        g.parse(f, format="turtle")
    g.parse(ONT_DIR / "sdkb-governance.ttl", format="turtle")
    conforms, text = _shacl(g)
    assert conforms, text


def test_kr_module_carries_the_jurisdiction_specific_doctrine():
    """주지관용·설계변경은 KR 심사기준 어휘라 core 에 있으면 안 된다."""
    core_text = CORE.read_text(encoding="utf-8")
    kr = Graph(); kr.parse(KR, format="turtle")
    for local in ("VerdictWellKnown", "VerdictDesignChange"):
        assert local not in core_text
        assert (URIRef("https://w3id.org/sdkb/pa/kr/" + local),
                RDF.type, URIRef(PA + "ElementVerdict")) in kr


def test_admin_vocab_smuggled_through_values_is_rejected(tmp_path):
    """`VALUES` 는 삼중항이 아니다 — BGP 만 보면 통째로 새어 나간다."""
    q = _q(tmp_path, "values.rq",
           "SELECT ?x ?t WHERE { VALUES ?t { ont:Patent } ?x a ?t }")
    assert check_query(q)


def test_optional_still_passes_after_values_handling(tmp_path):
    """구멍을 막느라 OPTIONAL 허용까지 조이면 규칙이 다른 것이 된다."""
    q = _q(tmp_path, "opt2.rq",
           "SELECT ?x WHERE { ?x a pa:ClaimProfile . "
           "OPTIONAL { VALUES ?t { ont:RejectionType } ?j ont:onGround ?t } }")
    assert check_query(q) == []
