"""검증 게이트를 통과한 델타만 SDKB 그래프에 머지한다."""
from __future__ import annotations

from pathlib import Path

from rdflib import RDF, Graph

from sdkb_paper.config import ONT, SHAPES_DELTA, SHAPES_GRAPH
from sdkb_paper.validate.shacl_gate import load_shapes, target_only, validate_graph


class GateFailure(RuntimeError):
    pass


def merge_with_gate(base_ttl: Path, delta_ttl: Path, out_ttl: Path) -> Graph:
    """델타가 엄격 게이트를, 병합 결과가 그래프 게이트를 통과할 때만 저장.

    델타에는 **엄격 shape**(개념 매핑 ≥1)를 건다 — 게이트의 의미는 "이 데이터를 그래프에
    넣어도 되는가"이기 때문이다. 병합된 그래프에는 완화 shape 를 걸어, 상류가 남긴 레거시
    특허(공정 링크 없는 디바이스 특허)를 소급 처벌하지 않는다.

    실패 시 GateFailure(리포트 포함) — 델타를 그래프에 넣지 않는다.
    """
    delta = Graph().parse(delta_ttl)
    new_patents = set(delta.subjects(RDF.type, ONT.Patent))

    g = Graph()
    g.parse(base_ttl)
    g += delta

    # 엄격 shape 를 **델타의 특허에만** 건다. 델타 단독으로는 TBox 도, 델타가 가리키는 공정
    # 인스턴스도 없어 검증이 성립하지 않고, 병합 그래프 전체에 걸면 레거시를 소급 처벌한다.
    strict = target_only(load_shapes(SHAPES_DELTA), new_patents)
    conforms, report = validate_graph(g, strict)
    if not conforms:
        raise GateFailure(f"델타가 L1(엄격)을 통과하지 못했다: {delta_ttl}\n{report}")

    conforms, report = validate_graph(g, SHAPES_GRAPH)
    if not conforms:
        raise GateFailure(f"병합 그래프가 L1 을 통과하지 못했다: {delta_ttl}\n{report}")

    g.serialize(out_ttl, format="turtle")
    return g
