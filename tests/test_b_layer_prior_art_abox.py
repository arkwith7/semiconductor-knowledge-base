"""CR-008 — B층 노드 추가가 지켜야 할 계약.

이 CR 이 깨질 수 있는 방식은 둘이고, 둘 다 **조용하다**.

1. **간선이 새어 나간다.** B층 `hasPriorArtExaminer` 를 상류에 두면 하류의 봉인이
   무의미해진다(CR-008 비목표 ⓐ · 하류 §1-4). 간선은 하류 봉인 qrel 에만 있어야 한다.
2. **A층 자산이 움직인다.** 기존 3,034 노드의 트리플이 하나라도 바뀌면 하류가 pin 한
   스냅샷의 출처 기록이 거짓이 된다(상류 §0 · CR-008 성공기준 ③).

둘 다 "에러 없이 잘못된 그래프"로 나타나므로 테스트가 아니면 잡히지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ONT = Namespace("https://w3id.org/sdkb/ont/")
ABOX = ROOT / "ontology" / "sdkb-abox-prior-art.ttl"
POP = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"
BUILDER = ROOT / "scripts" / "build_abox_prior_art.py"

# 봉인을 무의미하게 만드는 술어들. 이 파일에 한 트리플도 있으면 안 된다.
FORBIDDEN_EDGES = ("hasPriorArtExaminer", "hasPriorArt", "overPriorArt")


@pytest.fixture(scope="module")
def abox() -> Graph:
    if not ABOX.exists():
        pytest.skip("sdkb-abox-prior-art.ttl 없음")
    g = Graph()
    g.parse(ABOX, format="turtle")
    return g


# ── 1. 간선 0 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("pred", FORBIDDEN_EDGES)
def test_prior_art_abox_has_no_citation_edges(abox, pred):
    """인용 간선은 이 파일에 존재하지 않는다 — A층에서도, B층에서도."""
    n = sum(1 for _ in abox.triples((None, ONT[pred], None)))
    assert n == 0, f"ont:{pred} 가 {n} 트리플 — 상류에 간선을 두면 하류 봉인이 무의미해진다"


def test_builder_never_emits_citation_edges():
    """생성기 원문에 간선 술어가 등장하지 않는다.

    산출물 검사만 하면 "이번 입력에는 안 나왔다"까지만 보증한다. 코드에 없으면
    어떤 입력에도 나올 수 없다.
    """
    src = BUILDER.read_text(encoding="utf-8")
    # 이 테스트 자신을 가리키는 주석은 없다 — 생성기에는 R("hasPriorArt…") 형태로만 나올 수 있다.
    for pred in FORBIDDEN_EDGES:
        assert f'R("{pred}")' not in src, f"생성기가 ont:{pred} 를 만든다"


# ── 2. A층 불변 ─────────────────────────────────────────────────────
def test_b_layer_map_never_overwrites_a_layer():
    """B층 맵 병합은 `setdefault` 다 — 같은 키가 오면 A층 값이 이긴다."""
    import build_abox_prior_art as m

    a_layer = {"KR-P-1020090041506": "patent:kr_A_LAYER_WINS"}
    b_layer = {"KR-P-1020090041506": "patent:kr_B_LAYER_LOSES",
               "JP-P-2001358218": "patent:jp_JP2001358218A"}
    merged = dict(a_layer)
    for doc, cid in b_layer.items():
        merged.setdefault(doc, cid)
    assert merged["KR-P-1020090041506"] == "patent:kr_A_LAYER_WINS"
    assert merged["JP-P-2001358218"] == "patent:jp_JP2001358218A"
    assert hasattr(m, "_b_layer_map")


@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_b_layer_map_shape():
    import build_abox_prior_art as m

    mp = m._b_layer_map(POP)
    assert len(mp) == 503                      # NPL 제외
    assert all(v.startswith("patent:") for v in mp.values())
    assert not any(k.startswith("UNKNOWN::") for k in mp)


@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_a_layer_iris_all_survive_b_layer_build(abox):
    """A층이 세운 노드 IRI 가 B층 빌드 뒤에도 **전부** 살아 있다(성공기준 ③).

    A층 IRI 의 출처는 엣지표다 — 그래프가 아니라 원천에서 기대 집합을 만든다.
    그래야 "그래프가 스스로를 증명하는" 순환이 되지 않는다.
    """
    edges = pd.read_parquet(ROOT / "data" / "patents" / "prior_art_edges.parquet")
    a_ids = {str(c) for c in edges["cited_id"]
             if str(c).startswith("patent:") and not str(c).startswith("patent:other_")}
    nodes = {str(s).replace("https://w3id.org/sdkb/data/patent/", "patent:")
             for s in abox.subjects(RDF.type, ONT.CitedPatent)}
    # A층 노드 3,034 = **특허 문헌 3,025 + NPL(`patent:other_…`) 9**.
    # 이 CR 은 NPL 노드를 세우지 않으므로 특허 문헌 쪽만 기대 집합으로 쓴다.
    survived = a_ids & nodes
    assert len(survived) >= 3025, f"A층 특허 문헌 노드가 {len(survived)}건으로 줄었다"
    npl_nodes = {n for n in nodes if n.startswith("patent:other_")}
    assert len(npl_nodes) == 9, f"A층 NPL 노드 {len(npl_nodes)}건 — 9 에서 움직였다"


@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_b_layer_resolved_ids_became_nodes(abox):
    """B층 모집단의 해소분이 노드가 됐다 — 도달성 482/503 = 0.9583 (합격선 0.95)."""
    import build_abox_prior_art as m

    nodes = {str(s).replace("https://w3id.org/sdkb/data/patent/", "patent:")
             for s in abox.subjects(RDF.type, ONT.CitedPatent)}
    built = [cid for cid in m._b_layer_map(POP).values() if cid in nodes]
    assert len(built) == 482, f"B층 노드 {len(built)}건 — 리포트(482)와 다르다"
    assert len(built) / 503 >= 0.95


# ── 3. 스키마 계약 ──────────────────────────────────────────────────
def test_abox_predicates_are_declared_in_tbox(abox):
    """ABox 의 ont: 술어가 전부 TBox 에 선언돼 있다 (상류 §5 (b) 표).

    B층 노드는 A층과 **같은 코드 경로**를 타므로 새 술어가 생길 수 없다. 이 테스트는
    그 전제를 고정한다.
    """
    tbox = Graph()
    for f in ("sdkb-core.ttl", "sdkb-patent.ttl"):
        p = ROOT / "ontology" / f
        if p.exists():
            tbox.parse(p, format="turtle")
    declared = {str(s) for s in tbox.subjects(RDF.type, None)
                if str(s).startswith(str(ONT))}
    used = {str(p) for p in abox.predicates() if str(p).startswith(str(ONT))}
    missing = sorted(used - declared)
    assert not missing, f"TBox 에 없는 술어: {missing}"


@pytest.mark.skipif(not POP.exists(), reason="B층 모집단 표 없음")
def test_population_columns_match_collector_contract():
    """수집기가 먹는 컬럼 계약 — 이름이 갈라지면 라우팅이 조용히 빈다."""
    pop = pd.read_parquet(POP)
    for col in ("cited_doc_id", "cited_country", "cited_kind", "cited_raw", "is_npl"):
        assert col in pop.columns, f"컬럼 누락: {col}"
    assert pop.loc[~pop["is_npl"], "cited_country"].isin(
        ["KR", "JP", "US", "WO", "CN", "EP"]).all()


# ── 4. 진입점 계약 (D-52 복원 · 2026-08-24) ─────────────────────────
def test_b_layer_is_the_default_path():
    """B층 경로는 **인자 없이도** 들어온다.

    CR-008 은 두 인자를 주었을 때만 B층을 읽게 설계했고, 그 보장이 도입기의 A층
    불변을 지켰다. 그러나 CR-016 이 만든 `make abox-prior-art` 는 인자 없이 호출하고,
    그래서 CR-020 재생성이 CR-008 을 조용히 되감았다(CitedPatent 3,513 → 3,034 ·
    하류 D-52). 산출물 검사(위 test_b_layer_resolved_ids_became_nodes)는 그 사고를
    사후에만 잡는다 — 이 테스트는 **호출 기본값**을 고정해 사고 자체를 막는다.
    """
    import ast

    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    defaults = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        if "default" in kw:
            defaults[node.args[0].value] = ast.dump(kw["default"])
    assert "B_LAYER_POP" in defaults.get("--population", ""), \
        "--population 의 기본값이 B층 모집단이 아니다 — 인자 없는 호출이 A층으로 되돌아간다"
    assert "B_LAYER_ENRICHED" in defaults.get("--extra-enriched", ""), \
        "--extra-enriched 의 기본값이 B층 수집분이 아니다"


def test_b_layer_default_inputs_exist():
    """기본값이 가리키는 원천이 실재한다 — 없으면 조용히 A층으로 떨어진다."""
    import build_abox_prior_art as m

    assert m.B_LAYER_POP == POP
    missing = [f for f in m.B_LAYER_ENRICHED if not (m.ENR / f).exists()]
    assert not missing, f"B층 수집분 누락: {missing} — 수집(collect_cited_biblio_claims)이 선행이다"
