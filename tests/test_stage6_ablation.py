"""PLAN-005 단계 6-A — V1 절제 계측기의 계약 고정.

단계 1 계측기의 맹점 셋(`ont:` 주어만 · priorart 3모듈 미적재 · ② 만 구현)이 다시 생기지
않게 하고, 절제 리포트가 **현재 파일을 기술하는지**(신선도)를 잡는다. 실물 리포트가 없으면
그 부분은 skip 한다 — `make v1-ablation` 이 66분이라 매 pytest 에 돌리지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import report_v1_ablation as v1  # noqa: E402
from scripts import build_abox_priorart as gen  # noqa: E402
from scripts.check_priorart_invariants import check_query  # noqa: E402

PA = "https://w3id.org/sdkb/pa/"
DATA = "https://w3id.org/sdkb/data/"
REPORT = ROOT / "data" / "reports" / "priorart_v1_ablation.json"
TABLE = ROOT / "01.code_spec" / "reports" / "PLAN-005-stage6-axiom-consumers.md"

needs_report = pytest.mark.skipif(not REPORT.exists(), reason="절제 리포트 없음 — make v1-ablation")


@pytest.fixture(scope="module")
def modules() -> dict[str, Graph]:
    return {f: Graph().parse(ROOT / "ontology" / f, format="turtle") for f in v1.MODULES}


# ── ① 열거 — 동결 목록과 정확히 같다 ──────────────────────────────────
def test_enumeration_matches_frozen_table(modules):
    """공리가 늘거나 줄면 예측표를 **먼저** 고쳐야 한다 — 결과를 본 뒤 표를 늘리는 것을 막는다."""
    ids = [ax.id for ax in v1.enumerate_axioms(modules)]
    assert len(ids) == len(set(ids)), "중복 id"
    assert set(ids) == set(v1.FROZEN), {
        "열거만": sorted(set(ids) - set(v1.FROZEN)), "표만": sorted(set(v1.FROZEN) - set(ids))}
    assert len(ids) == 37


def test_enumeration_sees_pa_and_skos_subjects_and_legacy_eight(modules):
    """단계 1 의 맹점 — `ont:` 주어만 세면 core 6 · semi 9 · kr 3 이 보이지 않는다."""
    by_mod = {}
    for ax in v1.enumerate_axioms(modules):
        by_mod.setdefault(ax.module, []).append(ax)
    assert len([a for a in by_mod["legacy:core"] + by_mod["legacy:patent"]]) == 8
    assert sum(1 for a in by_mod["core"] if a.role == "rbox") == 6
    assert any(a.subject == "skos:exactMatch" for a in by_mod["core"])
    assert {a.role for a in by_mod["semi"]} == {"rbox", "binding-property", "binding-class"}
    assert sum(1 for a in by_mod["semi"] if a.role == "binding-class") == 11
    assert {a.kind for a in by_mod["kr"]} == {"differentFrom", "exactMatch"}


# ── ② ③ 검출기 — 게이트가 문다 ────────────────────────────────────────
def _core_data() -> tuple[Graph, set[str]]:
    a, b, c = (URIRef(DATA + f"material/{x}") for x in "abc")
    g = Graph()
    g.add((a, SKOS.broader, b)); g.add((b, SKOS.broader, c))
    for x in (a, b, c):
        g.add((x, RDF.type, URIRef("https://w3id.org/sdkb/ont/Material")))
    return g, {"material:a", "material:b", "material:c"}


def test_removing_covered_by_axiom_zeroes_materialization():
    core = Graph()
    core.add((URIRef(PA + "broaderConcept"), RDFS.subPropertyOf, URIRef(PA + "coveredBy")))
    semi = Graph()
    semi.add((URIRef("https://w3id.org/sdkb/ont/Material"), RDFS.subClassOf, URIRef(PA + "TechnicalConcept")))
    cd, _ = _core_data()
    before = v1.materialization(core, semi, cd)
    assert before["covered_by_total"] == 2 and before["bound_concepts"] == 3
    core.remove((URIRef(PA + "broaderConcept"), RDFS.subPropertyOf, URIRef(PA + "coveredBy")))
    after = v1.materialization(core, semi, cd)
    assert after["covered_by_total"] == 0 and after["bound_concepts"] == 3
    semi.remove((URIRef("https://w3id.org/sdkb/ont/Material"), RDFS.subClassOf, URIRef(PA + "TechnicalConcept")))
    assert v1.materialization(core, semi, cd)["bound_concepts"] == 0


def test_task_count_counts_one_hop_only_coverage():
    """u 가 필수개념 · d 가 u 의 상위 f 만 개시 → 1 · d 가 u 자체도 개시하면 0."""
    a, b = URIRef(DATA + "material/a"), URIRef(DATA + "material/b")
    p, d = URIRef(DATA + "profile/p"), URIRef(DATA + "disclosure/d")
    g = Graph()
    g.add((p, gen.PA.essentialConcept, a)); g.add((d, gen.PA.discloses, b)); g.add((a, gen.PA.coveredBy, b))
    t = v1.TaskSets(g)
    assert t.count({(a, b)}) == (1, 1)
    assert t.count(set()) == (0, 0)
    g.add((d, gen.PA.discloses, a))
    assert v1.TaskSets(g).count({(a, b)}) == (0, 0)


def test_blank_node_object_is_removed_by_subject_predicate():
    """단계 1 의 결함 — Dopant equivalentClass 의 공백노드 목적어가 절제되지 않았다."""
    g = Graph().parse(ROOT / "ontology" / "sdkb-core.ttl", format="turtle")
    ax = next(a for a in v1.enumerate_axioms({"sdkb-core.ttl": g}) if a.kind == "equivalentClass")
    removed = v1._remove(g, ax.triples)
    assert removed and (ax.triples[0][0], OWL.equivalentClass, None) not in g
    v1._restore(g, removed)


def test_path_column_is_structural():
    core = Graph()
    core.add((URIRef(PA + "substitutableWith"), RDFS.subPropertyOf, URIRef(PA + "coveredBy")))
    sub = v1.Axiom("x", "core", "subPropertyOf", "pa:substitutableWith", "pa:coveredBy", "rbox",
                   [(URIRef(PA + "substitutableWith"), RDFS.subPropertyOf, URIRef(PA + "coveredBy"))])
    sym = v1.Axiom("y", "core", "SymmetricProperty", "pa:substitutableWith", None, "rbox",
                   [(URIRef(PA + "substitutableWith"), RDF.type, OWL.SymmetricProperty)])
    inv = v1.Axiom("z", "core", "inverseOf", "pa:conceptOfFeature", "pa:featureConcept", "rbox",
                   [(URIRef(PA + "conceptOfFeature"), OWL.inverseOf, URIRef(PA + "featureConcept"))])
    assert v1.has_reader(sub, core) and v1.has_reader(sym, core) and not v1.has_reader(inv, core)


def test_task_measure_is_task_neutral(tmp_path):
    """④ 의 정의를 SPARQL 로 적어 불변식 B 에 통과시킨다 — 계측기 자신이 행정 어휘에 기대지 않는다."""
    q = tmp_path / "task.rq"
    q.write_text("PREFIX pa: <https://w3id.org/sdkb/pa/>\nSELECT ?p ?u WHERE { ?p pa:essentialConcept ?u . "
                 "?u pa:coveredBy ?f . ?d pa:discloses ?f . FILTER NOT EXISTS { ?d pa:discloses ?u } }",
                 encoding="utf-8")
    assert check_query(q) == []


# ── ④ 실물 리포트 — 신선도와 예측 대조 ───────────────────────────────
@needs_report
def test_report_describes_current_files():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    for rel, sha in rep["inputs"].items():
        if rel.endswith("*.rq"):
            assert sha == v1._dir_digest(v1.CQ_DIR, "*.rq"), rel
        else:
            assert sha == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), f"{rel} 가 리포트 이후 바뀌었다"
    assert rep["baseline"]["abox_covered_by_matches_tbox_driven"] is True
    assert TABLE.exists() and rep["summary"]["axioms_total"] == 37


@needs_report
def test_report_matches_frozen_prediction():
    """예측과 다르면 삭제하지 않고 멈춘다(계획) — 이 테스트가 그 정지선이다."""
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["summary"]["not_in_frozen_table"] == []
    assert rep["summary"]["prediction_mismatches"] == []
    consumed = {r["id"] for r in rep["detail"] if r["consumed"]}
    assert "core:subPropertyOf:pa:broaderConcept→pa:coveredBy" in consumed
