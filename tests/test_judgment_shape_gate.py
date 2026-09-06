"""판단 shape 이 **살아 있는 게이트**인지 고정한다 — PLAN-005 단계 2-B.

이 테스트가 있는 이유. `validation/shapes_claim_features.ttl` 은 작성된 뒤로
**어디에도 배선되어 있지 않았다**(`grep -rn shapes_claim_features Makefile scripts/ tests/`
가 2026-09-06 까지 빈 출력이었다). 부채 대장 4번(특허 shape 미배선)과 같은 양식이고,
§4 의 문장 그대로 "쓰여만 있고 돌지 않는 shape 은 게이트가 아니라 장식"이었다.

그래서 여기서 고정하는 것은 두 가지다.

  ① **거부해야 할 입력이 거부되는가** — 근거 없음 · 근거 2개 · 근거가 RejectionType 이
     아님 · 대비 선행기술 없음. 넷 다 위반으로 잡히지 않으면 그것은 게이트가 아니다.
  ② **Makefile 이 이 shape 을 실제로 실행하는가** — 배선이 끊기면 ① 이 통과해도
     릴리스 경로에서는 아무것도 검사되지 않는다. 두 계약은 **같이** 걸려야 한다.

합성 델타로 검증한다(907 MB A-Box 를 싣지 않는다). 실물 그래프 대상 실행은
`make validate` 가 하고, 그 명령의 존재를 ② 가 지킨다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
SHAPES = ROOT / "validation" / "shapes_claim_features.ttl"
TBOX = ROOT / "ontology" / "sdkb-patent.ttl"

#: A-Box 가 실제로 쓰는 네임스페이스. `ontology#` 로 착각하면 shape 이 타깃을 못 잡고
#: **위반 데이터가 통과한다** — 이 테스트를 쓰다 실제로 겪었으므로 상수로 박아 둔다.
ONT = "https://w3id.org/sdkb/ont/"

DELTA = f"""
@prefix ont: <{ONT}> .
<https://w3id.org/sdkb/data/judgment/ok> a ont:PriorArtJudgment ;
    ont:onGround ont:Rejection_Novelty ;
    ont:overPriorArt <https://w3id.org/sdkb/data/patent/kr_X> .
<https://w3id.org/sdkb/data/judgment/no_ground> a ont:PriorArtJudgment ;
    ont:overPriorArt <https://w3id.org/sdkb/data/patent/kr_X> .
<https://w3id.org/sdkb/data/judgment/two_grounds> a ont:PriorArtJudgment ;
    ont:onGround ont:Rejection_Novelty , ont:Rejection_Inventiveness ;
    ont:overPriorArt <https://w3id.org/sdkb/data/patent/kr_X> .
<https://w3id.org/sdkb/data/judgment/bad_ground> a ont:PriorArtJudgment ;
    ont:onGround <https://w3id.org/sdkb/data/patent/kr_X> ;
    ont:overPriorArt <https://w3id.org/sdkb/data/patent/kr_X> .
<https://w3id.org/sdkb/data/judgment/no_prior_art> a ont:PriorArtJudgment ;
    ont:onGround ont:Rejection_Novelty .
"""

VIOLATORS = {"no_ground", "two_grounds", "bad_ground", "no_prior_art"}


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
def test_위반_판단이_거부된다(report: str, bad: str) -> None:
    assert f"/judgment/{bad}>" in report, f"{bad} 가 위반으로 잡히지 않았다"


def test_정상_판단은_통과한다(report: str) -> None:
    assert "/judgment/ok>" not in report, "정상 판단이 위반으로 잡혔다 — 과잉 게이트"


def test_makefile_이_이_shape_을_실행한다() -> None:
    """배선 계약. ① 이 아무리 통과해도 이것이 끊기면 릴리스 경로는 무검사다."""
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    validate_block = mk.split("\nvalidate:", 1)[1].split("\ntest:", 1)[0]
    assert "shapes_claim_features.ttl" in validate_block, (
        "make validate 가 shapes_claim_features.ttl 을 실행하지 않는다 — "
        "shape 이 다시 장식이 됐다(부채 대장 4번과 같은 양식)")
    assert "sdkb-abox-claim-features.ttl" in validate_block, (
        "shape 이 겨냥하는 실물 A-Box 와 짝지어져 있지 않다")
