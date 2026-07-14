"""회사 하나 = IRI 하나 — 정체성 통합의 회귀 테스트.

SDKB 는 같은 회사에 역할에 따라 다른 id 를 줬다(`org:` 큐레이션 / `vendor:` 공급사 /
`organization:` 특허 출원인). 역할이 IRI 에 인코딩되면서 정체성이 갈라졌고, 그 결과
"이 회사가 공급하는 장비와 이 회사의 특허 포트폴리오"라는 IP-R&D 의 핵심 질의가
**에러 없이 0행**을 냈다 — `vendor/lam_research` 는 장비를 공급하고
`organization/lam_research` 는 특허 19건을 갖는, 서로 다른 노드였기 때문이다.

이 테스트는 그 상태로 되돌아가는 것을 막는다. 병합 근거는
mappings/org_identity_crosswalk.csv 에 한 행씩 있다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

ROOT = Path(__file__).resolve().parent.parent
ONT = Namespace("https://w3id.org/sdkb/ont/")
DATA = "https://w3id.org/sdkb/data/"
CROSSWALK = ROOT / "mappings" / "org_identity_crosswalk.csv"
ABOX = [
    ROOT / "ontology" / "sdkb-core-data.ttl",
    ROOT / "ontology" / "sdkb-abox-patents.ttl",
    ROOT / "ontology" / "sdkb-abox-vendors.ttl",
]

# 실재 회사가 아니라 "미상 공급사" 자리표시자다. 실재하지 않는 것에 정체성을 주지 않으므로
# organization/ 스킴 밖에 남는 유일한 예외다 (canonical_name = "Generic Equipment").
PLACEHOLDER = URIRef(DATA + "vendor/generic")


@pytest.fixture(scope="module")
def g() -> Graph:
    if not all(p.exists() for p in ABOX):
        pytest.skip("A-Box 미빌드 — make convert abox-patents abox-vendors")
    graph = Graph()
    for p in ABOX:
        graph.parse(p, format="turtle")
    return graph


def _companies(g: Graph) -> set[URIRef]:
    return set(g.subjects(RDF.type, ONT.Organization)) | set(g.subjects(RDF.type, ONT.Vendor))


def test_every_company_lives_under_one_scheme(g: Graph) -> None:
    """회사는 data:organization/ 한 스킴에만 산다. 역할은 rdf:type 이 말한다."""
    strays = {s for s in _companies(g) if not str(s).startswith(DATA + "organization/")}
    assert strays == {PLACEHOLDER}, f"organization/ 밖의 회사 노드: {sorted(map(str, strays))}"


def test_crosswalk_sources_are_gone(g: Graph) -> None:
    """병합 전 IRI 는 그래프에 남아 있으면 안 된다 — 남으면 정체성이 다시 갈라진다."""
    xw = pd.read_csv(CROSSWALK)
    subjects = set(g.subjects())
    dead = [
        old for old in xw["from_id"]
        if URIRef(DATA + old.replace(":", "/")) in subjects
    ]
    assert not dead, f"병합 전 IRI 가 아직 그래프에 있다: {dead}"


def test_merged_companies_carry_both_roles(g: Graph) -> None:
    """병합의 요점 — 공급 역할과 특허 포트폴리오가 **같은 노드**에 붙는다.

    kind=merge 행은 G₀ 에 특허 출원인으로 이미 있던 회사다. 병합 뒤 그 노드는
    ont:Vendor(공급) 와 ont:Organization(출원인) 을 함께 가져야 한다.
    """
    xw = pd.read_csv(CROSSWALK)
    for target in xw.loc[xw["kind"] == "merge", "to_id"]:
        iri = URIRef(DATA + target.replace(":", "/"))
        types = set(g.objects(iri, RDF.type))
        assert ONT.Vendor in types, f"{target}: 공급 역할(ont:Vendor)이 없다"
        assert ONT.Organization in types, f"{target}: 출원인 역할(ont:Organization)이 없다"


def test_no_company_has_two_preflabels_per_language(g: Graph) -> None:
    """언어당 prefLabel 은 하나다.

    CQ08(출원인 포트폴리오)은 prefLabel 문자열로 GROUP BY 한다. 병합된 노드가
    큐레이션 표제어("Samsung Electronics")와 KIPRIS verbatim 출원인명
    ("SAMSUNG ELECTRONICS CO., LTD.")을 **둘 다 prefLabel 로** 달면, 같은 회사가
    두 그룹으로 쪼개져 정체성 통합이 라벨 수준에서 되돌아간다.
    verbatim 출원인명은 altLabel 이어야 한다 (build_abox_patents._curated_orgs).
    """
    offenders = {}
    for c in _companies(g):
        langs: dict[str | None, int] = {}
        for lbl in g.objects(c, SKOS.prefLabel):
            langs[lbl.language] = langs.get(lbl.language, 0) + 1
        dup = {lang: n for lang, n in langs.items() if n > 1}
        if dup:
            offenders[str(c)] = dup
    assert not offenders, f"prefLabel 이 언어당 2개 이상인 회사: {offenders}"
