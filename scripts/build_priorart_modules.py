#!/usr/bin/env python3
"""PLAN-005 단계 4 — 선행기술 판단층 T-Box·R-Box 생성기 (3 모듈).

**왜 생성기인가.** `ontology/sdkb-patent.ttl` 은 손으로 쓴 커밋된 T-Box 이고 그 선례가
이 저장소에 있다(writer 0건 · git 이력 9커밋 전부 수기). 그럼에도 PLAN-005 §7-7 · §8 이
신규 3종을 **전부 생성기 경유**로 못박았으므로 코드가 짓는다. 손으로 고치면 다음 빌드에
사라진다(CLAUDE.md §1-1).

**무엇을 짓는가 — 세 모듈로 갈리는 이유는 이식성이다** (PLAN-001 §1.10(c)).

    ① sdkb-priorart-core.ttl   pa:  판단·절차층. **도메인 어휘 0 · 관할 어휘 0**
    ② sdkb-priorart-semi.ttl   ont: 도메인 바인딩 — 이 저장소의 반도체 어휘를 pa: 에 건다
    ③ sdkb-priorart-kr.ttl     pakr: 관할 바인딩 — KR 법조문·문서종·법리 어휘

바이오는 ②만, US 는 ③만 새로 쓴다. ① 은 두 경우 모두 **0줄**이며, 그것을 주장이 아니라
기계 보증으로 만드는 것이 `scripts/check_priorart_invariants.py` 다(§5 V6(a)).

**`semi:` 를 새로 만들지 않는다.** PLAN-001 §1.10(c) 는 도메인 바인딩을 `semi:` 로 적었으나
`scripts/build_owl.py` 에서 `SEMI` 는 이미 **SemicONTO**(`http://w3id.org/SemicONTO/`)다.
접두어 하나가 두 뜻을 가지면 §1-3 위반이므로 ②는 기존 `ont:` 를 쓴다 — 바인딩 대상이
바로 이 저장소의 반도체 어휘이고, `sdkb-patent.ttl` 이 `ont:` 를 별도 파일에서 선언하는
선례가 있다. (2026-09-06 · 3단계 승인 시 사용자 확인)

**기존 TTL 을 한 줄도 고치지 않는다.** 결합은 신규 모듈 → 기존 모듈 방향의 `owl:imports`
뿐이다. 역방향이면 `sdkb-patent.ttl` 이 바뀌어 하류(`sdkb-prior-art-paper`)가 핀한
sha256 `0a317389…9829` 이 깨진다(§0).

**결정성.** 시각·난수를 쓰지 않고, blank node 를 하나도 만들지 않으며, 직렬화는 rdflib 가
아니라 아래 `_emit` 이 (주어, 술어, 목적어) 사전순으로 한다. 같은 원천 → 같은 바이트다
(tests/test_priorart_modules.py 가 두 번 빌드해 고정한다).

CLI:
    python scripts/build_priorart_modules.py
    python scripts/build_priorart_modules.py --check    # 워킹트리와 재생성물이 같은가
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.namespaces import SDKB_ONT, SDKB_GOV, SDKB_PA, SDKB_PA_KR, PROV  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ONT_DIR = ROOT / "ontology"

PA, ONT, GOV, PAKR = SDKB_PA, SDKB_ONT, SDKB_GOV, SDKB_PA_KR

# 발행 메타. **상수다** — `datetime.now()` 를 쓰면 빌드마다 그래프가 달라지고
# 하류의 sha256 핀이 매일 깨진다(§0).
MODIFIED = "2026-09-07"
VERSION = "0.1.0-dev"
LICENSE = URIRef("https://spdx.org/licenses/CDLA-Permissive-2.0.html")

CORE_IRI = URIRef("https://w3id.org/sdkb/pa")
SEMI_IRI = URIRef("https://w3id.org/sdkb/pa/semi")
KR_IRI = URIRef("https://w3id.org/sdkb/pa/kr")
ONT_IRI = URIRef("https://w3id.org/sdkb/ont")
PATENT_IRI = URIRef("https://w3id.org/sdkb/ont/patent")

CORE_PREFIXES = {
    "pa": str(PA), "owl": str(OWL), "rdf": str(RDF), "rdfs": str(RDFS),
    "xsd": str(XSD), "skos": str(SKOS), "dcterms": str(DCTERMS), "prov": str(PROV),
}
SEMI_PREFIXES = dict(CORE_PREFIXES, ont=str(ONT))
KR_PREFIXES = dict(CORE_PREFIXES, ont=str(ONT), gov=str(GOV), pakr=str(PAKR))


def _cls(g: Graph, iri, label_en, comment=None, parent=None) -> None:
    g.add((iri, RDF.type, OWL.Class))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    if parent is not None:
        g.add((iri, RDFS.subClassOf, parent))
    if comment:
        g.add((iri, RDFS.comment, Literal(comment, lang="ko")))


def _prop(g: Graph, iri, kind, label_en, comment=None, domain=None, range_=None) -> None:
    g.add((iri, RDF.type, kind))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    if domain is not None:
        g.add((iri, RDFS.domain, domain))
    if range_ is not None:
        g.add((iri, RDFS.range, range_))
    if comment:
        g.add((iri, RDFS.comment, Literal(comment, lang="ko")))


def _indiv(g: Graph, iri, type_, ko, en, comment=None) -> None:
    g.add((iri, RDF.type, type_))
    g.add((iri, SKOS.prefLabel, Literal(ko, lang="ko")))
    g.add((iri, SKOS.prefLabel, Literal(en, lang="en")))
    if comment:
        g.add((iri, RDFS.comment, Literal(comment, lang="ko")))


# ═══════════════════════════════════════════════════════════════════
# ① core — pa: 만 등장한다. 도메인·관할 IRI 가 한 건이라도 들어오면 CI 가 죽인다.
# ═══════════════════════════════════════════════════════════════════
def build_core() -> Graph:
    g = Graph()
    g.add((CORE_IRI, RDF.type, OWL.Ontology))
    g.add((CORE_IRI, RDFS.label, Literal("SDKB Prior-Art Core — task layer", lang="en")))
    g.add((CORE_IRI, RDFS.comment, Literal(
        "선행기술 판단·심사절차의 도메인 중립·관할 중립 core. 도메인 어휘(반도체)는 "
        "sdkb-priorart-semi.ttl, 관할 어휘(KR)는 sdkb-priorart-kr.ttl 이 슬롯에 바인딩한다. "
        "이 파일에 ont:·gov:·pakr: IRI 가 등장하면 이식성 주장이 깨지며, "
        "scripts/check_priorart_invariants.py 가 그것을 실패로 만든다.", lang="ko")))
    g.add((CORE_IRI, OWL.versionInfo, Literal(VERSION)))
    g.add((CORE_IRI, DCTERMS.modified, Literal(MODIFIED, datatype=XSD.date)))
    g.add((CORE_IRI, DCTERMS.license, LICENSE))
    # core 는 아무것도 import 하지 않는다 — import 하는 순간 도메인이 딸려 들어온다.

    # ── 판단 단위 ──
    _cls(g, PA.TechnicalConcept, "technical concept",
         "도메인 슬롯. **하위 클래스를 여기서 선언하지 않는다** — 반도체 하위는 "
         "sdkb-priorart-semi.ttl, 바이오는 그 자리를 갈아끼운다.")
    _cls(g, PA.ClaimProfile, "claim profile",
         "질의·문헌 공통의 의미 단위. 특허가 아니어도 만들 수 있다(연구노트·아이디어) — "
         "그것이 §3.4 '특허 종속 해소'의 실체다.")
    _cls(g, PA.Disclosure, "disclosure", "문헌이 실제로 개시한 것. 도달 목표 노드.")
    _cls(g, PA.LegalGround, "legal ground",
         "관할 슬롯. KR §29 · US §102/§103 · EP Art.54/56 이 각각 개체로 들어온다.")

    # ── 심사 절차층 (문서종을 클래스로 굳히지 않는다) ──
    _cls(g, PA.ExaminationDocument, "examination document",
         "심사 과정에서 발행된 문서 하나. prov:Entity 라 출처 추적이 그대로 붙는다.",
         parent=PROV.Entity)
    _cls(g, PA.ExaminationDocumentType, "examination document type",
         "문서종은 **개체**다. 클래스로 굳히면 US non-final/final · EP Art.94(3) 이식이 "
         "클래스 신설을 요구한다(PLAN-001 §1.10(c)).")
    _cls(g, PA.DocumentRole, "document role", "절차상 역할 — 관할 중립.")
    _cls(g, PA.CitationStatus, "citation status",
         "문서 계열의 시간순에서 파생된다. 문서종 이름에 기대지 않으므로 이미 관할 중립이다"
         "(PLAN-001 §1.10(d)).")
    _cls(g, PA.ClaimVersion, "claim version",
         "라운드 2+ 는 보정된 청구항을 대비한다 — 버전 없이 붙이면 오접지된다.")

    # ── 증거층 ──
    _cls(g, PA.MinedAxiom, "mined axiom",
         "심사문서에서 채굴된 공리. pa:underJurisdiction 이 **없으면 SHACL 위반**이다 "
         "(PLAN-001 §1.10(e)) — KR 결합용이성과 US §103 을 한 추론에 섞지 않기 위해서다.")
    _cls(g, PA.ExaminerElement, "examiner element",
         "심사관이 구성 대비표에서 직접 나눈 구성요소. **우리 청구항 분해(ClaimFeature)와 "
         "동일시하지 않는다** — 실측에서 요소 개수가 일치하는 청구항 단위가 53개 중 8개"
         "(15.1%)뿐이다. 접지는 청구항 단위로만 하며, 요소↔요소 정렬 술어는 만들지 않는다"
         "(PLAN-005 단계 4 · 사용자 승인 결정 1).")
    _cls(g, PA.ElementVerdict, "element verdict",
         "구성요소 대비의 판정 어휘. 법리 종속 어휘(주지관용·설계변경)는 여기 두지 않고 "
         "관할 모듈이 개체로 더한다.")
    _cls(g, PA.FeatureRole, "feature role",
         "한정요소의 역할 **슬롯**. 열거를 클래스로 굳히지 않는 이유는 §5 V6a 실패예측 1번이다 "
         "— 서열·투여용법·마쿠쉬 선택지가 갈 자리가 없으면 L1 이 오염된 것이다.")

    # ── 원소층 술어 ──
    _prop(g, PA.coveredBy, OWL.ObjectProperty, "covered by",
          "원소층 충족 — 질의 개념이 문헌 개념으로 덮인다. **전이로 선언하지 않는다**(§3.3): "
          "전이를 붙이면 'SiO2↔SiON, SiON↔Si3N4' 두 판단에서 심사관이 한 적 없는 "
          "'SiO2↔Si3N4' 가 생기고 supportCount/counterCount provenance 를 우회한다. "
          "확장 깊이는 의미론이 아니라 질의 시점의 동결된 설정값이다.",
          domain=PA.TechnicalConcept, range_=PA.TechnicalConcept)
    _prop(g, PA.broaderConcept, OWL.ObjectProperty, "broader concept",
          "상위 개념. 전이다 — 개념 계층의 확장은 판단이 아니라 어휘의 성질이다.",
          domain=PA.TechnicalConcept, range_=PA.TechnicalConcept)
    g.add((PA.broaderConcept, RDF.type, OWL.TransitiveProperty))
    g.add((PA.broaderConcept, RDFS.subPropertyOf, PA.coveredBy))
    _prop(g, PA.substitutableWith, OWL.ObjectProperty, "substitutable with",
          "치환 가능(단순 설계변경·재료 치환). 대칭이나 **전이가 아니다**.",
          domain=PA.TechnicalConcept, range_=PA.TechnicalConcept)
    g.add((PA.substitutableWith, RDF.type, OWL.SymmetricProperty))
    g.add((PA.substitutableWith, RDFS.subPropertyOf, PA.coveredBy))
    # 외부 어휘를 확장자로 끌어온다. skos: 는 도메인·관할 어휘가 아니므로 core 에 허용된다.
    g.add((SKOS.exactMatch, RDFS.subPropertyOf, PA.coveredBy))
    _prop(g, PA.discloses, OWL.ObjectProperty, "discloses",
          "문헌이 개시한 개념. 신규성의 우변 — 이것이 없으면 Disclosure 는 도달 목표 노드로 "
          "선언만 되고 질의가 닿을 수 없다.",
          domain=PA.Disclosure, range_=PA.TechnicalConcept)
    _prop(g, PA.uncoveredConcept, OWL.ObjectProperty, "uncovered concept",
          "판정의 잔여 — 덮이지 않은 질의 개념. 설명가능성의 본체다.",
          range_=PA.TechnicalConcept)

    # ── 슬롯 술어 (도메인은 바인딩 모듈이 채운다 — core 에 쓰면 도메인 오염이다) ──
    _prop(g, PA.featureConcept, OWL.ObjectProperty, "feature concept",
          "한정요소가 가리키는 개념. range 가 **합집합이 아니라 슬롯**인 것이 도메인 축의 답이다. "
          "rdfs:domain 은 여기서 선언하지 않는다 — 그것이 곧 도메인 어휘이기 때문이다.",
          range_=PA.TechnicalConcept)
    _prop(g, PA.conceptOfFeature, OWL.ObjectProperty, "concept of feature",
          "featureConcept 의 역관계. 문헌 쪽에서 질의 쪽으로 거슬러 오르는 경로에 필수다.")
    g.add((PA.conceptOfFeature, OWL.inverseOf, PA.featureConcept))
    _prop(g, PA.featureRole, OWL.ObjectProperty, "feature role",
          "한정요소의 역할. 개체는 바인딩 모듈이 넣는다.", range_=PA.FeatureRole)
    _prop(g, PA.essentialConcept, OWL.ObjectProperty, "essential concept",
          "독립항 필수구성 — 신규성 판단의 좌변.",
          domain=PA.ClaimProfile, range_=PA.TechnicalConcept)
    _prop(g, PA.optionalConcept, OWL.ObjectProperty, "optional concept",
          "종속항 부가구성.", domain=PA.ClaimProfile, range_=PA.TechnicalConcept)
    _prop(g, PA.solvesProblem, OWL.ObjectProperty, "solves problem",
          "이 프로파일이 겨냥한 해결과제. 문제 축의 도달 경로가 된다.",
          domain=PA.ClaimProfile, range_=PA.TechnicalConcept)
    _prop(g, PA.achievesEffect, OWL.ObjectProperty, "achieves effect",
          "이 프로파일이 주장하는 기술적 효과.",
          domain=PA.ClaimProfile, range_=PA.TechnicalConcept)
    # 단계 5-A (2026-09-07 · 사용자 승인) — 판단 단위를 원천에 잇는 술어 둘. 단계 4 에는
    # 없었고, 그래서 ClaimProfile·Disclosure 가 어느 청구항·문헌의 것인지 그래프가 말할 수
    # 없었다. range 는 비운다 — 특허 청구항이 아닌 연구노트도 프로파일의 원천일 수 있고
    # (§3.4), 그것을 채우는 것은 바인딩 모듈의 몫이다.
    _prop(g, PA.profileOf, OWL.ObjectProperty, "profile of",
          "이 프로파일이 요약한 원천 단위. range 는 도메인 어휘라 바인딩 모듈이 채운다 — "
          "특허 청구항이 아닌 연구노트도 올 수 있다(§3.4).",
          domain=PA.ClaimProfile)
    _prop(g, PA.disclosureOf, OWL.ObjectProperty, "disclosure of",
          "이 개시집합이 속한 문헌. range 는 바인딩 모듈이 채운다.",
          domain=PA.Disclosure)

    # ── 절차·증거 술어 ──
    _prop(g, PA.onGround, OWL.ObjectProperty, "on ground",
          "판단의 법적 근거. range 가 슬롯인 것이 관할 축의 답이다.", range_=PA.LegalGround)
    _prop(g, PA.assertedIn, OWL.ObjectProperty, "asserted in",
          "이 주장이 실린 심사문서.", range_=PA.ExaminationDocument)
    _prop(g, PA.ofDocumentType, OWL.ObjectProperty, "of document type",
          "문서가 어느 종에 속하는가. 종이 개체이므로 관할마다 개수가 달라도 어휘가 견딘다.",
          domain=PA.ExaminationDocument, range_=PA.ExaminationDocumentType)
    _prop(g, PA.documentRole, OWL.ObjectProperty, "document role",
          "문서종의 절차상 역할. KR 의견제출통지서와 US non-final Office Action 이 여기서 만난다.",
          domain=PA.ExaminationDocumentType, range_=PA.DocumentRole)
    _prop(g, PA.citationStatus, OWL.ObjectProperty, "citation status",
          "인용이 후속 문서에서 살아남았는가. 문서 계열의 시간순에서 파생하며 손으로 적지 않는다.",
          range_=PA.CitationStatus)
    _prop(g, PA.aboutClaimVersion, OWL.ObjectProperty, "about claim version",
          "판단이 겨냥한 청구항의 **그 라운드 버전**. 보정 뒤 원본에 붙이면 오접지다.",
          range_=PA.ClaimVersion)
    _prop(g, PA.versionOf, OWL.ObjectProperty, "version of",
          "어느 청구항의 버전인가. range 는 도메인 어휘라 바인딩 모듈이 채운다.",
          domain=PA.ClaimVersion)
    _prop(g, PA.amendedFrom, OWL.ObjectProperty, "amended from",
          "직전 라운드의 청구항 버전. 보정 이력의 사슬이다.",
          domain=PA.ClaimVersion, range_=PA.ClaimVersion)
    _prop(g, PA.underJurisdiction, OWL.ObjectProperty, "under jurisdiction",
          "채굴 공리·법적 근거가 선 관할. **rdfs:domain 을 선언하지 않는다** — MinedAxiom 에만 "
          "걸면 LegalGround 개체가 추론으로 MinedAxiom 이 된다. 필수 조건은 SHACL "
          "(validation/shapes_priorart.ttl)이 건다.", range_=SKOS.Concept)
    _prop(g, PA.concernsClaim, OWL.ObjectProperty, "concerns claim",
          "심사관 구성요소가 속한 청구항. **표 캡션이 말하는 청구항 번호로만 만든다** — "
          "표 안의 '구성 N-M' 앞 숫자(elementGroup)로 만들면 실측 9건이 다른 청구항에 "
          "조용히 붙고 38건은 검증 불가다(§1-3 · 부채 대장 1번과 같은 양식).",
          domain=PA.ExaminerElement)
    _prop(g, PA.hasVerdict, OWL.ObjectProperty, "has verdict",
          "심사관이 그 구성요소에 내린 판정. 중립 판정은 core, 법리 판정은 관할 모듈에 있다.",
          domain=PA.ExaminerElement, range_=PA.ElementVerdict)

    # ── 데이터 술어 ──
    for iri, lab, rng, com in [
        (PA.examRound, "exam round", XSD.integer, "심사 라운드 번호 (1 = 최초 통지)."),
        (PA.issuedDate, "issued date", XSD.date, "문서 발송일. citationStatus 파생의 정렬 키다."),
        (PA.atRound, "at round", XSD.integer, "이 청구항 버전이 속한 라운드."),
        (PA.elementGroup, "element group", XSD.integer,
         "구성 대비표 안의 **표 단위 그룹 번호**. 청구항 번호가 아니다 — 원천 구조로만 보존하며 "
         "접지 키로 쓰지 않는다."),
        (PA.elementNo, "element no", XSD.integer, "그룹 안의 구성요소 번호."),
        (PA.tableIndex, "table index", XSD.integer, "문서 안 <표 N> 의 N."),
        (PA.axiomConfidence, "axiom confidence", XSD.string, "provisional | confirmed"),
        (PA.supportCount, "support count", XSD.integer, "이 공리를 지지한 심사 사례 수."),
        (PA.counterCount, "counter count", XSD.integer, "반례 수 — 철회(Withdrawn)된 인용에서 나온다."),
    ]:
        _prop(g, iri, OWL.DatatypeProperty, lab, com, range_=rng)

    # ── 중립 개체 ──
    for iri, ko, en in [
        (PA.FirstAction, "최초 통지", "first action"),
        (PA.SubsequentAction, "후속 통지", "subsequent action"),
        (PA.FinalAction, "최종 처분", "final action"),
    ]:
        _indiv(g, iri, PA.DocumentRole, ko, en)
    for iri, ko, en, com in [
        (PA.Provisional, "잠정", "provisional", "선행 문서에만 등장."),
        (PA.Maintained, "유지", "maintained", "후속 문서까지 생존."),
        (PA.Withdrawn, "철회", "withdrawn", "후속 문서에서 소멸 — 반례의 원천."),
    ]:
        _indiv(g, iri, PA.CitationStatus, ko, en, com)
    for iri, ko, en in [
        (PA.VerdictIdentical, "실질적 동일", "substantially identical"),
        (PA.VerdictDifferent, "차이", "different"),
        (PA.VerdictCorresponding, "대응", "corresponding"),
        (PA.VerdictSimilar, "유사", "similar"),
    ]:
        _indiv(g, iri, PA.ElementVerdict, ko, en)
    return g


# ═══════════════════════════════════════════════════════════════════
# ② semi — 도메인 바인딩. 여기서 ont: 가 처음 등장한다.
# ═══════════════════════════════════════════════════════════════════
def build_semi() -> Graph:
    g = Graph()
    g.add((SEMI_IRI, RDF.type, OWL.Ontology))
    g.add((SEMI_IRI, RDFS.label, Literal("SDKB Prior-Art — semiconductor domain binding", lang="en")))
    g.add((SEMI_IRI, RDFS.comment, Literal(
        "pa: 의 도메인 슬롯에 이 저장소의 반도체 어휘를 건다. 바이오 이식에서 **교체되는 "
        "유일한 파일**이며(그리고 kr 모듈), core 는 0줄 바뀐다. 기존 파일은 한 줄도 고치지 "
        "않고 subClassOf·subPropertyOf 로만 끌어온다 — 하류가 핀한 sha256 을 지키기 "
        "위해서다(§0).", lang="ko")))
    g.add((SEMI_IRI, OWL.versionInfo, Literal(VERSION)))
    g.add((SEMI_IRI, DCTERMS.modified, Literal(MODIFIED, datatype=XSD.date)))
    g.add((SEMI_IRI, DCTERMS.license, LICENSE))
    g.add((SEMI_IRI, OWL.imports, CORE_IRI))
    g.add((SEMI_IRI, OWL.imports, PATENT_IRI))

    # ── 기존 클래스를 슬롯에 건다 (선언이 아니라 끌어오기) ──
    for c in [ONT.Process, ONT.SubProcess, ONT.Material, ONT.Device, ONT.Parameter, ONT.Problem]:
        g.add((c, RDFS.subClassOf, PA.TechnicalConcept))

    # ── 축 부재 해소 — 등재 보류된 구조요소 15개가 갈 자리 (§8.1 어휘) ──
    _cls(g, ONT.StructuralElement, "structural element",
         "층·패턴·전극·게이트·스페이서·비아 등 구조물. 이 축이 없어 "
         "data/reports/ko_concept_proposals.json 의 구조요소 15개가 '축 부재'로 "
         "등재 보류돼 있었다(§8.1).", parent=PA.TechnicalConcept)
    _cls(g, ONT.TechnicalFunction, "technical function",
         "'~을 방지하기 위한' · '~을 제어하는' 작용.", parent=PA.TechnicalConcept)
    _cls(g, ONT.TechnicalEffect, "technical effect",
         "누설전류 감소·스텝커버리지 향상 등 효과.", parent=PA.TechnicalConcept)
    _cls(g, ONT.ProcessCondition, "process condition",
         "온도·압력·가스비·두께 등 조건.", parent=PA.TechnicalConcept)

    # ── 상호배제. **신규 클래스 대 기존 클래스로만 건다** ──
    # 기존 둘(예: Process·Material) 사이에 걸면 이미 실린 인스턴스가 비일관이 될 수 있고,
    # 그것은 이 단계가 약속한 '기존 어휘 불변'을 깨는 것이다.
    for a, b in [
        (ONT.StructuralElement, ONT.Process), (ONT.StructuralElement, ONT.Material),
        (ONT.TechnicalFunction, ONT.StructuralElement),
        (ONT.TechnicalEffect, ONT.StructuralElement),
    ]:
        g.add((a, OWL.disjointWith, b))

    # ── 역관계 (R-Box) ──
    _prop(g, ONT.featureOf, OWL.ObjectProperty, "feature of",
          "hasFeature 의 역관계.", domain=ONT.ClaimFeature, range_=ONT.Claim)
    g.add((ONT.featureOf, OWL.inverseOf, ONT.hasFeature))
    _prop(g, ONT.claimOf, OWL.ObjectProperty, "claim of",
          "hasClaim 의 역관계.", domain=ONT.Claim, range_=ONT.Patent)
    g.add((ONT.claimOf, OWL.inverseOf, ONT.hasClaim))

    # ── 슬롯 채우기: core 가 비워 둔 domain/range ──
    g.add((PA.featureConcept, RDFS.domain, ONT.ClaimFeature))
    g.add((PA.featureRole, RDFS.domain, ONT.ClaimFeature))
    g.add((PA.concernsClaim, RDFS.range, ONT.Claim))
    g.add((PA.versionOf, RDFS.range, ONT.Claim))
    # 단계 5-A — 프로파일은 청구항의, 개시집합은 특허 문헌의 것이다(이 도메인에서는).
    g.add((PA.profileOf, RDFS.range, ONT.Claim))
    g.add((PA.disclosureOf, RDFS.range, ONT.Patent))
    # 기존 술어를 중립 상위로 끌어올린다. 기존 IRI·의미는 그대로다.
    g.add((ONT.featureConcept, RDFS.subPropertyOf, PA.featureConcept))
    g.add((ONT.onGround, RDFS.subPropertyOf, PA.onGround))
    g.add((ONT.aboutClaim, RDFS.subPropertyOf, PA.concernsClaim))

    # ── featureRole 개체 — core 가 아니라 여기 (§5 V6a 실패예측 1번) ──
    for local, ko, en in [
        ("Role_Means", "수단", "means"), ("Role_Structure", "구조", "structure"),
        ("Role_Step", "단계", "step"), ("Role_Material", "재료", "material"),
        ("Role_Condition", "조건", "condition"), ("Role_Function", "작용", "function"),
        ("Role_Effect", "효과", "effect"),
    ]:
        _indiv(g, ONT[local], PA.FeatureRole, ko, en)
    return g


# ═══════════════════════════════════════════════════════════════════
# ③ kr — 관할 바인딩. US 이식에서 이 파일만 새로 쓴다.
# ═══════════════════════════════════════════════════════════════════
def build_kr() -> Graph:
    g = Graph()
    g.add((KR_IRI, RDF.type, OWL.Ontology))
    g.add((KR_IRI, RDFS.label, Literal("SDKB Prior-Art — KR jurisdiction binding", lang="en")))
    g.add((KR_IRI, RDFS.comment, Literal(
        "KR 특허법 조문·문서종·법리 어휘를 pa: 슬롯에 개체로 넣는다. US 이식(단계 8)은 "
        "이 파일에 대응하는 sdkb-priorart-us.ttl 만 새로 쓰며 core 는 0줄 바뀐다. "
        "문서종을 클래스가 아니라 개체로 두는 이유가 여기서 드러난다 — US 는 "
        "non-final/final Office Action 으로 개수와 배타 관계가 다르다.", lang="ko")))
    g.add((KR_IRI, OWL.versionInfo, Literal(VERSION)))
    g.add((KR_IRI, DCTERMS.modified, Literal(MODIFIED, datatype=XSD.date)))
    g.add((KR_IRI, DCTERMS.license, LICENSE))
    g.add((KR_IRI, OWL.imports, CORE_IRI))
    g.add((KR_IRI, OWL.imports, PATENT_IRI))

    # ── 법적 근거 — 기존 RejectionType 개체에 매단다(새 해소 로직을 만들지 않는다) ──
    for local, ko, en, notation, existing in [
        ("Ground_29_1", "신규성 부정 (특허법 제29조 제1항)", "lack of novelty (KR Patent Act §29(1))",
         "KIPO-29-1", ONT.Rejection_Novelty),
        ("Ground_29_2", "진보성 부정 (특허법 제29조 제2항)", "lack of inventive step (KR Patent Act §29(2))",
         "KIPO-29-2", ONT.Rejection_Inventiveness),
    ]:
        iri = PAKR[local]
        _indiv(g, iri, PA.LegalGround, ko, en)
        g.add((iri, SKOS.notation, Literal(notation)))
        g.add((iri, PA.underJurisdiction, GOV.JurisdictionKR))
        g.add((iri, SKOS.exactMatch, existing))

    # ── 문서종 — 클래스가 아니라 개체. 배타성은 관할 모듈이 말한다 ──
    _indiv(g, PAKR.NoticeOfReasons, PA.ExaminationDocumentType,
           "의견제출통지서", "notification of reasons for rejection")
    g.add((PAKR.NoticeOfReasons, PA.documentRole, PA.FirstAction))
    g.add((PAKR.NoticeOfReasons, PA.underJurisdiction, GOV.JurisdictionKR))
    _indiv(g, PAKR.FinalRejection, PA.ExaminationDocumentType,
           "거절결정서", "final rejection decision")
    g.add((PAKR.FinalRejection, PA.documentRole, PA.FinalAction))
    g.add((PAKR.FinalRejection, PA.underJurisdiction, GOV.JurisdictionKR))
    # PLAN-001 §1.2(b) 의 owl:disjointWith 가 내려온 자리. 클래스가 아니므로 differentFrom 이다.
    g.add((PAKR.NoticeOfReasons, OWL.differentFrom, PAKR.FinalRejection))

    # ── KR 법리 판정 어휘. 중립 판정 넷은 core 에 있다 ──
    for local, ko, en, com in [
        ("VerdictWellKnown", "주지관용기술", "well-known and commonly used art",
         "KR 심사기준의 판단 어휘 — 관할 중립이 아니므로 core 에 두지 않는다."),
        ("VerdictDesignChange", "단순 설계변경", "mere design change",
         "KR 심사기준의 판단 어휘."),
    ]:
        _indiv(g, PAKR[local], PA.ElementVerdict, ko, en, com)
        g.add((PAKR[local], PA.underJurisdiction, GOV.JurisdictionKR))
    return g


# ═══════════════════════════════════════════════════════════════════
# 결정적 직렬화 — rdflib 에 맡기지 않는다
# ═══════════════════════════════════════════════════════════════════
def _term(t, prefixes: dict[str, str]) -> str:
    if isinstance(t, Literal):
        lit = '"' + str(t).replace("\\", "\\\\").replace('"', '\\"') + '"'
        if t.language:
            return f"{lit}@{t.language}"
        if t.datatype:
            return f"{lit}^^{_term(URIRef(t.datatype), prefixes)}"
        return lit
    s = str(t)
    for pfx, ns in sorted(prefixes.items(), key=lambda kv: -len(kv[1])):
        if s.startswith(ns):
            local = s[len(ns):]
            if local and "/" not in local and "#" not in local:
                return f"{pfx}:{local}"
    return f"<{s}>"


def _emit(g: Graph, prefixes: dict[str, str], header: str) -> str:
    for s, p, o in g:
        for t in (s, p, o):
            if not isinstance(t, (URIRef, Literal)):
                raise SystemExit(f"blank node 가 생겼다 — 결정적 직렬화가 깨진다: {t!r}")
    lines = [header.rstrip(), ""]
    for pfx in sorted(prefixes):
        lines.append(f"@prefix {pfx}:{' ' * (8 - len(pfx))}<{prefixes[pfx]}> .")
    lines.append("")
    by_subject: dict[str, list[tuple[str, str]]] = {}
    for s, p, o in g:
        by_subject.setdefault(_term(s, prefixes), []).append((_term(p, prefixes), _term(o, prefixes)))
    for subj in sorted(by_subject):
        lines.append(subj)
        pairs = sorted(set(by_subject[subj]))
        for i, (p, o) in enumerate(pairs):
            end = " ." if i == len(pairs) - 1 else " ;"
            lines.append(f"    {p} {o}{end}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


HEADER = """# ═══════════════════════════════════════════════════════════════════
# {title}
#
# **생성물이다. 손으로 고치지 않는다** — scripts/build_priorart_modules.py 가 만든다
# (CLAUDE.md §1-1 · PLAN-005 §7-7). 고치면 다음 빌드에 조용히 사라지고, 그 사이에
# vendor 해 간 하류는 유령 데이터를 갖는다.
#
# 재생성: make priorart
# 검사  : make validate  (scripts/check_priorart_invariants.py 가 이식성 불변식을 건다)
# ═══════════════════════════════════════════════════════════════════"""

MODULES = [
    ("sdkb-priorart-core.ttl", build_core, CORE_PREFIXES,
     "SDKB Prior-Art Core (pa:) — 도메인 어휘 0 · 관할 어휘 0"),
    ("sdkb-priorart-semi.ttl", build_semi, SEMI_PREFIXES,
     "SDKB Prior-Art — 반도체 도메인 바인딩 (ont: → pa:)"),
    ("sdkb-priorart-kr.ttl", build_kr, KR_PREFIXES,
     "SDKB Prior-Art — KR 관할 바인딩 (pakr: → pa:)"),
]


def render() -> dict[str, str]:
    out = {}
    for fname, builder, prefixes, title in MODULES:
        text = _emit(builder(), prefixes, HEADER.format(title=title))
        Graph().parse(data=text, format="turtle")  # 스스로 파싱되지 않는 것은 내지 않는다
        out[fname] = text
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="워킹트리 파일이 재생성물과 같은가 (CI·게이트용)")
    args = ap.parse_args()

    rendered = render()
    if args.check:
        stale = [f for f, t in rendered.items()
                 if not (ONT_DIR / f).exists() or (ONT_DIR / f).read_text(encoding="utf-8") != t]
        if stale:
            print("FAIL: 재생성물과 다르다 (손으로 고쳤거나 생성기가 바뀌었다): " + ", ".join(stale))
            return 1
        print(f"OK: {len(rendered)} 모듈이 생성기와 일치한다")
        return 0

    for fname, text in rendered.items():
        (ONT_DIR / fname).write_text(text, encoding="utf-8")
        g = Graph(); g.parse(ONT_DIR / fname, format="turtle")
        print(f"  {fname:32s} {len(g):4d} triples")
    print(f"→ {ONT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
