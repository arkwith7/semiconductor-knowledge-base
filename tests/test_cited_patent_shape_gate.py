"""인용문헌 shape 이 **살아 있는 게이트**인지 고정한다 — PLAN-005 후속.

이 테스트가 있는 이유. `Shape_CitedPatent`(`validation/shapes_claim_features.ttl`)은
작성된 뒤로 **자기가 겨냥하는 그래프에 한 번도 걸리지 않았다.** 단계 2-B 가 그 shape
파일을 `make validate` 에 배선했으나 짝은 `sdkb-abox-claim-features.ttl` 하나였고,
정작 `ont:CitedPatent` 3,513 건은 `sdkb-abox-prior-art.ttl` 에 있다 — 타깃 0.
부채 대장 4번(특허 shape 미배선)과 같은 양식이고, §4 의 문장 그대로 "쓰여만 있고
돌지 않는 shape 은 게이트가 아니라 장식"이었다.

고정하는 것은 `test_judgment_shape_gate` 와 같은 두 가지다.

  ① **거부해야 할 입력이 거부되는가** — license 없음 · source 없음 ·
     filingDate/abstractText 둘 다 없음(= 매달린 IRI, 이 shape 이 애초에 막으려던 것).
  ② **Makefile 이 이 shape 을 그 A-Box 와 짝지어 실행하는가** — 배선이 끊기면
     ① 이 통과해도 릴리스 경로에서는 아무것도 검사되지 않는다.

  ③ **조건부 배선이 실패를 삼키지 않는가** — ② 를 쓰다 발견했다. `make validate` 의
     조건부 짝 셋이 전부 `test -f X && cmd || echo skip` 이었고, 그 형태는 cmd 가
     실패해도 exit 0 이다. 배선되어 있어도 **실패할 수 없는 게이트**였다는 뜻이라,
     ② 만으로는 부족하다. 셋 모두에 건다.

합성 델타로 검증한다(21 MB A-Box 를 싣지 않는다). 실물 그래프 대상 실행은
`make validate` 가 하고, 그 명령의 존재를 ② 가 지킨다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
SHAPES = ROOT / "validation" / "shapes_claim_features.ttl"
TBOX = ROOT / "ontology" / "sdkb-patent.ttl"

#: A-Box 가 실제로 쓰는 네임스페이스(`test_judgment_shape_gate` 와 같은 이유로 상수).
ONT = "https://w3id.org/sdkb/ont/"

DELTA = f"""
@prefix ont:     <{ONT}> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

# 실물(cn_CN102403077A)과 같은 형태 — filingDate 로 실체를 증명하는 정상 노드.
<https://w3id.org/sdkb/data/patent/ok_filing> a ont:CitedPatent ;
    dcterms:license "KIPRIS terms — academic use, no redistribution of full text"^^xsd:string ;
    dcterms:source "BigQuery Google Patents"^^xsd:string ;
    ont:filingDate "2011-09-06"^^xsd:date .

# 완화 조항(sh:or)의 다른 갈래 — 출원일이 없어도 초록이 있으면 통과해야 한다.
<https://w3id.org/sdkb/data/patent/ok_abstract> a ont:CitedPatent ;
    dcterms:license "KIPRIS terms — academic use, no redistribution of full text"^^xsd:string ;
    dcterms:source "KIPRIS Plus API"^^xsd:string ;
    ont:abstractText "A multilayer PTC thermistor." .

<https://w3id.org/sdkb/data/patent/no_license> a ont:CitedPatent ;
    dcterms:source "BigQuery Google Patents"^^xsd:string ;
    ont:filingDate "2011-09-06"^^xsd:date .

<https://w3id.org/sdkb/data/patent/no_source> a ont:CitedPatent ;
    dcterms:license "KIPRIS terms — academic use, no redistribution of full text"^^xsd:string ;
    ont:filingDate "2011-09-06"^^xsd:date .

# 매달린 IRI — 타입과 출처만 있고 실체가 없다. sh:or 가 잡아야 한다.
<https://w3id.org/sdkb/data/patent/dangling> a ont:CitedPatent ;
    dcterms:license "KIPRIS terms — academic use, no redistribution of full text"^^xsd:string ;
    dcterms:source "BigQuery Google Patents"^^xsd:string .
"""

VIOLATORS = {"no_license", "no_source", "dangling"}
CONFORMERS = {"ok_filing", "ok_abstract"}


@pytest.fixture(scope="module")
def report() -> str:
    pyshacl = pytest.importorskip("pyshacl")
    g = Graph()
    g.parse(data=DELTA, format="turtle")
    g.parse(str(TBOX), format="turtle")
    shapes = Graph()
    shapes.parse(str(SHAPES), format="turtle")
    conforms, _, text = pyshacl.validate(
        g, shacl_graph=shapes, inference="none", abort_on_first=False)
    assert not conforms, "위반 델타가 통과했다 — shape 이 타깃을 못 잡고 있다(vacuous)"
    return text


@pytest.mark.parametrize("bad", sorted(VIOLATORS))
def test_결손_인용문헌이_거부된다(report: str, bad: str) -> None:
    assert f"/patent/{bad}>" in report, f"{bad} 가 위반으로 잡히지 않았다"


@pytest.mark.parametrize("good", sorted(CONFORMERS))
def test_정상_인용문헌은_통과한다(report: str, good: str) -> None:
    assert f"/patent/{good}>" not in report, f"{good} 가 위반으로 잡혔다 — 과잉 게이트"


def _validate_block() -> str:
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    return mk.split("\nvalidate:", 1)[1].split("\ntest:", 1)[0]


def _data_lines() -> list[str]:
    """`--data` 로 실제 검증 대상을 넘기는 줄만 고른다.

    주석(`@#`)을 세면 안 된다 — 초판이 그랬고, 배선을 지워도 주석에 남은 파일명 때문에
    테스트가 통과했다(변이 검사로 잡음). 파일명이 **명령줄에** 있어야 게이트다.
    """
    return [l for l in _validate_block().splitlines()
            if "--data" in l and not l.lstrip().startswith("@#")]


def test_makefile_이_prior_art_A_Box_와_짝지어_실행한다() -> None:
    """배선 계약. 짝이 없으면 shape 은 타깃 0 으로 vacuous 하게 통과한다."""
    hits = [l for l in _data_lines() if "ontology/sdkb-abox-prior-art.ttl" in l]
    assert hits, (
        "make validate 의 어떤 --data 에도 sdkb-abox-prior-art.ttl 이 없다 — "
        "Shape_CitedPatent 이 다시 타깃 0 이 된다(부채 대장 4번과 같은 양식)")


#: `make validate` 안에서 A-Box 존재 여부로 갈리는 세 짝. 셋 다 같은 함정을 공유한다.
CONDITIONAL_ABOXES = (
    "ontology/sdkb-abox-b-layer-queries.ttl",
    "ontology/sdkb-abox-claim-features.ttl",
    "ontology/sdkb-abox-prior-art.ttl",
)


@pytest.mark.parametrize("abox", CONDITIONAL_ABOXES)
def test_조건부_배선이_실패를_삼키지_않는다(abox: str) -> None:
    """`test -f X && cmd || echo skip` 은 cmd 가 실패해도 exit 0 이다 — 즉 **실패할 수
    없는 게이트**이고, 위반이 0 인 동안은 드러나지 않아 더 위험하다.

        $ sh -c 'test -f /etc/hostname && false || echo skip'
        skip
        $ echo $?
        0

    조건부 짝은 검증기의 종료코드를 보존하는 `if/else` 여야 한다. 세 짝 모두에 건다 —
    한 곳만 고치면 다음 배선이 옛 형태를 복사해 온다(실제로 그렇게 번졌다).
    """
    block = _validate_block()
    hits = [l for l in _data_lines() if abox in l]
    assert hits, f"{abox} 를 검증하는 --data 명령이 없다"
    for line in hits:
        assert "|| echo" not in line, f"{abox} 짝의 검증 실패가 스킵 메시지에 삼켜진다"
    assert f"@if [ -f {abox} ]" in block, (
        f"{abox} 배선이 종료코드를 보존하는 if/else 형태가 아니다")
