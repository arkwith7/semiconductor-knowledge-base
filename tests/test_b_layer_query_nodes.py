"""CR-012 — B층 확증분할 질의 200건이 지켜야 할 계약.

이 CR 이 깨질 수 있는 방식은 다섯이고, 다섯 다 **조용하다** — 빌드는 성공하고 수치만 거짓이 된다.

1. **인용 간선이 새어 들어간다.** 상류에 질의→정답 간선이 하나라도 생기면 하류의 봉인
   qrel(`127a138f…`)이 그 순간 무의미해진다. 확증분할은 한 번뿐이라 되돌릴 수 없다
   (CR-012 §5 비목표 ⓐ · 검증기준 ④).
2. **IRI 규칙이 A층과 갈라진다.** `patent/kr_{출원번호}` 가 아니면 하류가 같은 노드를 두 번
   세거나(중복) 아예 못 찾는다(CR-012 §4ⓐ). 청구항 사이드카의 `rej:` 해소도 함께 깨진다.
3. **층이 섞인다.** ⓑ 의 층 구분은 **파일**이므로, B층 노드가 A층 파일에 들어가거나 A층
   노드가 이 파일에 들어오면 두 확증 분할이 뭉친다(검증기준 ⑥).
4. **T-Box 가 조용히 자란다.** 이 CR 의 델타 유형은 ②(개념층)여야 한다. ABox 가 새 술어·새
   클래스를 인라인 선언하면 유형 ①이 되고 하류의 변인이 하나 늘어난다(상류 §1.2 · CR-012 §4ⓑ-3).
5. **거절근거가 함께 실린다.** 비목표 ⓔ. 하위집단 층화 재료는 이번 범위가 아니다.

1·3·4·5 는 산출물에서, 2 는 산출물과 코드 양쪽에서 고정한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

TTL = ROOT / "ontology" / "sdkb-abox-b-layer-queries.ttl"
REPORT = ROOT / "data" / "reports" / "abox_b_layer_queries_report.json"
COLLECT_REPORT = ROOT / "data" / "reports" / "b_layer_query_collection.json"
RAW = ROOT / "data" / "patents" / "b_layer_queries_raw.jsonl"
BUILDER = ROOT / "scripts" / "build_abox_b_layer_queries.py"
COLLECTOR = ROOT / "scripts" / "collect_b_layer_queries.py"
A_LAYER_TTL = ROOT / "ontology" / "sdkb-abox-patents.ttl"

IDS_FILE = Path(
    "/home/arkwith/Dev/SKKU/sdkb-prior-art-paper/upstream/handoff/CR-012-b-query-ids.txt"
)
EXPECTED_N = 200

pytestmark = pytest.mark.skipif(not TTL.exists(), reason="B층 질의 A-Box 미빌드")


def _ttl() -> str:
    return TTL.read_text(encoding="utf-8")


# rdflib 은 접두를 선언해도 전체 IRI 로 직렬화한다. 둘 다 받는다 —
# 직렬화 형태가 바뀌었다고 계약 검사가 조용히 통과하면 안 된다.
_KR_IRI = re.compile(r"(?:data:|https://w3id\.org/sdkb/data/)patent/kr_(\d{13})")


def _query_ids(text: str) -> set[str]:
    return set(_KR_IRI.findall(text))


# ── 1. 인용 간선 0 (검증기준 ④ · 비목표 ⓐ) ──────────────────────────
@pytest.mark.parametrize("pred", ["hasPriorArtExaminer", "hasPriorArt", "overPriorArt"])
def test_no_citation_edges(pred):
    """봉인이 무의미해지는 유일한 경로. 산출물에서 직접 센다."""
    assert f"ont:{pred}" not in _ttl(), (
        f"{pred} 가 B층 파일에 있다 — 하류 봉인 qrel 이 무의미해진다(CR-012 비목표 ⓐ)")


def test_builder_fails_closed_on_citation_edges():
    """산출물 검사만으로는 '이번 입력에는 안 나왔다'까지만 보증된다.

    생성기가 스스로 세고 **0 이 아니면 중단**하는지를 코드에서 고정한다.
    """
    src = BUILDER.read_text(encoding="utf-8")
    assert "FORBIDDEN_PREDICATES" in src and "return 1" in src, (
        "생성기에 인용 간선 자체 확인·중단 경로가 없다")


# ── 2. IRI 규칙이 A층과 같다 (CR-012 §4ⓐ) ───────────────────────────
def test_iri_rule_matches_a_layer():
    iris = _query_ids(_ttl())
    assert len(iris) == EXPECTED_N, f"질의 IRI 가 {len(iris)}건 — 200 이어야 한다"
    assert "/patent/KR" not in _ttl(), "관할 접두가 대문자다 — A층 규칙과 갈라졌다"


@pytest.mark.skipif(not IDS_FILE.exists(), reason="하류 이관 파일 없음")
def test_iris_are_exactly_the_handoff_ids():
    """이관 파일의 200 과 **정확히** 같아야 한다. 더도 덜도 안 된다."""
    want = {ln.strip() for ln in IDS_FILE.read_text().splitlines() if ln.strip()}
    got = _query_ids(_ttl())
    assert got == want, (
        f"이관 목록과 불일치 — 빠짐 {len(want - got)}건 · 초과 {len(got - want)}건")


def test_collector_pins_the_handoff_signature():
    """이관 파일이 조용히 바뀌면 확증분할 200 이 거짓이 된다 — 경고가 아니라 중단이어야 한다."""
    src = COLLECTOR.read_text(encoding="utf-8")
    assert "EXPECTED_SHA256" in src and "SystemExit" in src, (
        "수집기가 이관 파일 sha256 을 대조·중단하지 않는다")


# ── 3. 층이 섞이지 않는다 (검증기준 ⑥ · 요구 ⓑ) ─────────────────────
def test_all_nodes_are_typed_as_query():
    """이 파일의 특허 노드는 **전부** RejectedPatent 다 — 후보 문서가 섞이면 층이 뭉친다."""
    rep = json.loads(REPORT.read_text())
    assert rep["typed_RejectedPatent"] == EXPECTED_N
    assert rep["rows_in"] == EXPECTED_N


@pytest.mark.skipif(not A_LAYER_TTL.exists(), reason="A층 A-Box 미빌드")
def test_no_overlap_with_a_layer_queries():
    """A층 질의 1,000 과 교집합 0. 겹치면 하류 질의밀도의 분모가 거짓이 된다."""
    a = _query_ids(A_LAYER_TTL.read_text(encoding="utf-8"))
    b = _query_ids(_ttl())
    assert not (a & b), f"A층과 {len(a & b)}건 겹친다 — 두 확증 분할이 뭉친다"


# ── 4. T-Box 가 자라지 않는다 (델타 유형 ② 유지) ────────────────────
@pytest.mark.parametrize("decl", ["owl:ObjectProperty", "owl:DatatypeProperty", "owl:Class",
                                  "rdfs:subClassOf", "rdfs:domain", "rdfs:range"])
def test_no_inline_vocabulary_declaration(decl):
    """ABox 가 어휘를 선언하면 TBox 만 읽는 소비자에게 없는 술어가 된다(상류 §1.2)."""
    assert decl not in _ttl(), f"{decl} 가 ABox 에 인라인 선언됐다 — T-Box 델타가 된다"


def test_uses_only_existing_patent_predicates():
    """이 파일이 쓰는 ont: 술어는 A층 특허 A-Box 가 이미 쓰던 것뿐이어야 한다."""
    used = set(re.findall(r"ont:([A-Za-z][A-Za-z0-9_]*)", _ttl()))
    allowed = {
        "Patent", "RejectedPatent", "IPCSymbol",          # 클래스 (참조만 · 선언 아님)
        "applicationNumber", "patentOffice", "filingDate", "hasIPC",
        "abstractText", "firstClaimText", "examinationStatus",
        "publicationNumber", "publicationDate",          # CR-014 — A층이 이미 쓰던 칸
    }
    routing = _routing_predicates()          # 개념 링크 술어는 A층 라우팅표에서 가져온다
    unexpected = used - allowed - routing
    assert not unexpected, f"예상 밖 술어: {sorted(unexpected)}"


def _routing_predicates() -> set[str]:
    from build_abox_patents import PATENT_ROUTING

    return set(PATENT_ROUTING.values())


# ── 4b. 면제는 이름을 가진 예외이지 느슨함이 아니다 ─────────────────
def test_citation_exemption_is_provenance_scoped():
    """shape 이 minCount 를 낮추지 않고 **출처로만** 면제하는지 고정한다.

    minCount 0 으로 내리면 A층 1,000 에 걸려 있던 계약까지 함께 풀린다 — 앞으로 인용 없는
    거절특허가 조용히 들어와도 게이트가 잡지 못한다. 그건 §1.6 이 금지하는 형태다.
    """
    shapes = (ROOT / "validation" / "shapes_patent.ttl").read_text(encoding="utf-8")
    # Shape_RejectedPatent 블록만 본다 — 파일 전체를 훑으면 다른 shape 의 정당한
    # `sh:minCount 0` 에 걸려 이 검사가 늘 실패한다(그러면 검사가 아니라 소음이다).
    block = shapes.split("ont:Shape_RejectedPatent", 1)[1].split("\n\n#", 1)[0]
    assert "hasPriorArtExaminer" in block and "sh:minCount 1" in block, (
        "인용 요구가 minCount 1 로 남아 있지 않다 — 계약이 통째로 풀렸다")
    assert "b_layer_query_ingest" in block, "면제가 출처(prov)에 묶여 있지 않다"


def test_negative_control_still_fails(tmp_path):
    """**실패해야 할 입력이 실패하는가**(상류 §2.5b).

    출처 표시가 없는 무인용 거절특허는 여전히 거부되어야 한다. 이것이 통과하면 면제가
    B층을 넘어 새어 나간 것이고, shape 는 더 이상 게이트가 아니다.
    """
    pyshacl = pytest.importorskip("pyshacl")
    from rdflib import Graph

    neg = tmp_path / "neg.ttl"
    neg.write_text("""
@prefix ont: <https://w3id.org/sdkb/ont/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<https://w3id.org/sdkb/data/patent/kr_9999999999999> a ont:Patent, ont:RejectedPatent ;
    skos:prefLabel "음성 대조군"@ko ;
    ont:applicationNumber "9999999999999" ;
    ont:patentOffice "KR" ;
    ont:examinationStatus "거절결정(일반)"^^xsd:string ;
    dcterms:source "test"^^xsd:string ;
    dcterms:license "test"^^xsd:string .
""", encoding="utf-8")

    data = Graph()
    data.parse(str(neg), format="turtle")
    data.parse(str(ROOT / "ontology" / "sdkb-patent.ttl"), format="turtle")
    shapes = Graph()
    shapes.parse(str(ROOT / "validation" / "shapes_patent.ttl"), format="turtle")

    conforms, _, text = pyshacl.validate(data, shacl_graph=shapes, inference="rdfs",
                                         abort_on_first=False)
    assert not conforms, "무인용·무출처 거절특허가 통과했다 — 면제가 B층 밖으로 샜다"
    assert "kr_9999999999999" in text, "거부됐지만 대상 노드가 음성 대조군이 아니다"


# ── 4c. CR-014 — 서지 두 칸은 채우고, 없는 두 칸은 채우지 않는다 ────
# 이 CR 이 깨지는 방식도 조용하다. ① 공개번호 자리에 **공고번호**를 넣으면(KIPRIS 응답의
# publicationNumber) 거절특허는 그 값이 전부 null 이라 칸이 비고, 값이 있는 날에는 A층과
# 다른 것을 담는다(§1.3). ② 없는 두 칸을 추정으로 채우면 하류 T2 의 공정군 축이 A/B 서로
# 다른 규칙으로 만든 층을 비교하게 된다 — 빌드는 성공하고 하위집단 분석만 거짓이 된다.
def test_publication_fields_are_filled():
    rep = json.loads(REPORT.read_text())
    bib = rep["cr014_bibliographic"]
    assert bib["publicationNumber"] == EXPECTED_N, (
        f"공개번호 {bib['publicationNumber']}/{EXPECTED_N} — 그만큼 하류 SHACL 위반이 남는다")
    assert bib["publicationDate"] == EXPECTED_N
    assert _ttl().count("ont:publicationNumber") == EXPECTED_N


def test_publication_number_is_the_open_number():
    """값이 이름대로인가(§1.3) — 공개번호는 `10-YYYY-NNNNNNN` 이고 출원번호와 다르다."""
    nums = re.findall(r'ont:publicationNumber\s+"([^"]+)"', _ttl())
    assert len(nums) == EXPECTED_N
    bad = [v for v in nums if not re.fullmatch(r"10-\d{4}-\d{7}", v)]
    assert not bad, f"A층 공개번호 형식이 아닌 값 {len(bad)}건 — 예: {bad[:3]}"
    # 공개일 ≥ 출원일. 두 날짜가 뒤집히면 시점 필터가 조용히 반대로 돈다.
    from rdflib import Graph, Namespace

    g = Graph()
    g.parse(str(TTL), format="turtle")
    ont = Namespace("https://w3id.org/sdkb/ont/")
    pairs = [(str(g.value(s, ont.filingDate)), str(o))
             for s, o in g.subject_objects(ont.publicationDate)]
    assert len(pairs) == EXPECTED_N
    inverted = [p for p in pairs if p[0] and p[1] and p[1] < p[0]]
    assert not inverted, f"공개일 < 출원일 인 건 {len(inverted)}건 — 예: {inverted[:3]}"


def test_process_family_is_not_invented():
    """없는 값을 만들지 않았는가. **비어 있는 것이 이 CR 의 결론**이다.

    A층의 processFamily·valueChainStage 는 특허의 속성이 아니라 SIRP 코호트의 수집 출처다.
    B층에 IPC·개념링크로 추정해 채우면 같은 이름의 다른 것이 된다(§1.3).
    """
    assert "ont:processFamily" not in _ttl(), "추정으로 채워졌다 — CR-014 회신과 어긋난다"
    assert "ont:valueChainStage" not in _ttl(), "추정으로 채워졌다 — CR-014 회신과 어긋난다"
    bib = json.loads(REPORT.read_text())["cr014_bibliographic"]
    assert bib["processFamily"] == 0 and bib["valueChainStage"] == 0
    assert bib["unfilled_reason"], "못 채운 이유가 산출물에 남지 않으면 하류가 결손을 오독한다"


# ── 5. 거절근거가 실리지 않는다 (비목표 ⓔ) ──────────────────────────
def test_no_rejection_basis():
    assert "ont:rejectedFor" not in _ttl(), "거절근거가 실렸다 — CR-012 비목표 ⓔ"
    assert "Rejection_" not in _ttl(), "RejectionType 통제어휘가 실렸다 — 비목표 ⓔ"


# ── 수집 품질 (성공기준 ② 의 상류 측) ───────────────────────────────
@pytest.mark.skipif(not COLLECT_REPORT.exists(), reason="수집 리포트 없음")
def test_collection_is_complete():
    rep = json.loads(COLLECT_REPORT.read_text())
    assert rep["collected"] == rep["requested"] == EXPECTED_N
    assert rep["with_claims"] == EXPECTED_N, (
        f"청구항 미확보 {EXPECTED_N - rep['with_claims']}건 — 성공기준 ② 가 위태롭다")
    # CR-014 — 수집 단계에서 이미 200/200 이어야 한다. 여기서 모자라면 그래프는 손댈 수 없다.
    assert rep["with_publication_number"] == EXPECTED_N
    assert rep["with_publication_date"] == EXPECTED_N


@pytest.mark.skipif(not REPORT.exists(), reason="빌드 리포트 없음")
def test_report_records_the_ab_asymmetry():
    """비대칭을 숨기면 하류가 개념링크 차이를 온톨로지 결함으로 오독한다."""
    rep = json.loads(REPORT.read_text())
    assert rep["concept_links"]["asymmetry_note"]
    assert rep["topical_composition"]["b_layer_ipc4_top"]
    assert rep["topical_composition"]["a_layer_ipc4_top"], (
        "비교 대상인 A층 분포가 비어 있다 — B층 수치만으로는 해석할 수 없다")
