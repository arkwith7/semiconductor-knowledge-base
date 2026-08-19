"""L2 게이트 — OWL 논리 일관성(consistency). owlready2 + HermiT.

논문 §3.3 의 3층 검증 게이트 중 L2. 병합 후 그래프가 기술논리적으로 일관되어야 한다.

HermiT 에 그래프를 그대로 먹일 수 없어서 **추론 전용 뷰**를 만든다 (원본 그래프는 불변):

1. Turtle -> RDF/XML.  owlready2 는 Turtle 을 파싱하지 못한다 (RDF/XML·NTriples 만).
2. owl:imports 제거.   owlready2 가 import IRI 를 HTTP 로 가져오려다 404 로 죽는다.
   graph_v0/vN 은 이미 TBox 모듈을 전부 병합한 그래프라 import 는 중복이며,
   제거해야 게이트가 네트워크에 의존하지 않는다 (CI 재현성).
3. xsd:date -> xsd:dateTime.  HermiT 는 OWL 2 datatype map 만 지원하는데 xsd:date 는
   거기 없다 (UnsupportedDatatypeException). SDKB 의 sdkb-patent.ttl 은 filingDate 등의
   rdfs:range 를 xsd:date 로 선언하므로 그대로는 추론이 불가능하다.
   range 선언과 리터럴을 **함께** 승격하므로 타입 불일치 탐지력은 유지된다
   (예: filingDate 가 xsd:string 이면 range 위반으로 여전히 비일관).
   원본의 xsd:date 는 그대로 두고 SHACL(L1)이 검사한다 — H2 시계열의 전제.

Java 가 필요하다 (HermiT 는 JAR). 로컬/Colab: apt-get install default-jre.

CLI:  python -m sdkb_paper.validate.reasoner_gate <graph.ttl|.owl>
      (비일관 시 exit code 1 -> CI 에서 게이트로 동작)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from rdflib import XSD, Graph, Literal, OWL


def reasoning_view(graph: Graph) -> Graph:
    """HermiT 가 먹을 수 있는 형태로 그래프를 변환한다 (모듈 docstring 의 2·3번).

    입력 그래프를 수정하지 않는다 — 사본을 반환한다.
    """
    g = Graph()
    for s, p, o in graph:
        if p == OWL.imports:
            continue
        if isinstance(o, Literal) and o.datatype == XSD.date:
            o = Literal(f"{o}T00:00:00", datatype=XSD.dateTime)
        elif isinstance(o, Literal) and o.datatype == XSD.gYear:
            # xsd:gYear("2023") 도 HermiT 의 OWL 2 datatype map 밖이다 (xsd:date 와 같은 사유).
            # 전문가 retirementYear 가 이 타입을 쓴다. 원본 그래프의 gYear 는 그대로 두고
            # (L1 SHACL 이 검사) 추론 뷰에서만 dateTime 으로 사상한다.
            o = Literal(f"{o}-01-01T00:00:00", datatype=XSD.dateTime)
        elif o == XSD.date:  # rdfs:range xsd:date 같은 TBox 선언
            o = XSD.dateTime
        elif o == XSD.gYear:  # rdfs:range xsd:gYear 같은 TBox 선언
            o = XSD.dateTime
        g.add((s, p, o))
    return g


def check_consistency(path: str | Path) -> bool:
    from owlready2 import OwlReadyInconsistentOntologyError, World, sync_reasoner

    view = reasoning_view(Graph().parse(path))
    tmp = Path(tempfile.mkdtemp(prefix="reasoner_gate_")) / "reasoning_view.owl"
    view.serialize(tmp, format="xml")

    world = World()  # 전역 owlready2 world 오염 방지 (테스트가 연달아 돌 때 중요)
    world.get_ontology(tmp.as_uri()).load()
    try:
        sync_reasoner(world)  # HermiT
        return True
    except OwlReadyInconsistentOntologyError:
        return False


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m sdkb_paper.validate.reasoner_gate <graph.ttl|.owl>")
        sys.exit(2)
    target = sys.argv[1]
    ok = check_consistency(target)
    print(f"[reasoner_gate] {target}  consistent = {ok}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
