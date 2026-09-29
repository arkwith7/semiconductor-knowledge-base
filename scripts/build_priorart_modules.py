#!/usr/bin/env python3
"""PLAN-005 단계 4 — 선행기술 판단층 T-Box·R-Box 생성기 (3 모듈 + 단계 8 의 US 바인딩).

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

    ④ sdkb-priorart-us.ttl     paus: 관할 바인딩 — US 35 U.S.C. §102/§103 · Office Action 문서종
    ⑤ sdkb-priorart-argument.ttl  pa: 판단 논증층 — 판단 단위·근거 묶음·요소↔증거·수치 구간·논거 유형

**PLAN-005 R1-스키마(2026-09-29 · 사용자 승인) — ⑤ 논증층.** R1 정답 해부(§20.15)의 결손 58종 중
결과 전에 동결한 규칙(E2 ∧ 카드 ≥5 ∧ 바뀌는 CQ 가 있음 · 파서 계열 제외)을 통과한 15종을 담는다.
①–④ 는 바이트 하나 바뀌지 않는다 — core·semi·kr 의 sha 는 V6b 판정이 동결했고(`report_stage8_paper_port.FROZEN`),
그것을 건드리면 과거 판정이 스스로 모순된다. 그래서 ⑤ 는 자기 발행일 `MODIFIED_ARG` 를 갖고
core 만 import 하며, core 와 같은 순도 불변식 A(도메인·관할 IRI 0)를 받는다.
`ont:PriorArtJudgment` 는 (출원, 인용문헌, 근거) 3키로 IRI 가 정해지는 이분 엣지라(1,812건 전부
`overPriorArt` 1개) 조합·무문헌·선택적 근거를 담을 수 없다 — 그래서 판단 단위를 **새 클래스**로 세운다.
옛 `pa:substitutableWith`(개념↔개념 대칭)는 되살리지 않는다: 원천의 치환은 방향 있는 판단 논거다(R1 카드 5장).

**단계 8 (2026-09-11 · 사용자 승인) — V6b US 종이 이식.** ④ 는 ③ 의 대칭이며 **①②③ 은 바이트
하나 바뀌지 않는다** — 그것이 V6b 의 판정량(L1 변경 라인수 0)이고 `scripts/report_stage8_paper_port.py`
가 세 파일의 sha256 을 동결값과 대조해 센다. 그래서 ④ 는 공유 상수 `MODIFIED` 를 쓰지 않고 자기
발행일 `MODIFIED_US` 를 갖는다 — 공유 상수를 바꾸면 ① 의 sha 가 바뀌어 판정이 자기모순이 된다.
④ 가 담지 않는 것: US 판정 어휘(KSR/TSM 등 — 원천이 이 저장소에 없다 · §1-4) · KR 근거와의
`skos:exactMatch`(§29① 은 유예기간이 §102 와 다르고 §29② 는 §103 KSR 과 같은 판단이 아니며, 읽는
소비자도 없다 · §7-6) · `ont:` 도메인 어휘(관할 바인딩은 도메인을 모른다) · `sdkb-patent.ttl` import.

**`semi:` 를 새로 만들지 않는다.** PLAN-001 §1.10(c) 는 도메인 바인딩을 `semi:` 로 적었으나
`scripts/build_owl.py` 에서 `SEMI` 는 이미 **SemicONTO**(`http://w3id.org/SemicONTO/`)다.
접두어 하나가 두 뜻을 가지면 §1-3 위반이므로 ②는 기존 `ont:` 를 쓴다 — 바인딩 대상이
바로 이 저장소의 반도체 어휘이고, `sdkb-patent.ttl` 이 `ont:` 를 별도 파일에서 선언하는
선례가 있다. (2026-09-06 · 3단계 승인 시 사용자 확인)

**기존 TTL 을 한 줄도 고치지 않는다.** 결합은 신규 모듈 → 기존 모듈 방향의 `owl:imports`
뿐이다. 역방향이면 `sdkb-patent.ttl` 이 바뀌어 하류(`sdkb-prior-art-paper`)가 핀한
sha256 `0a317389…9829` 이 깨진다(§0).

**단계 6-B(2026-09-09 · 사용자 승인) — V1 절제로 소비가 확인되지 않은 공리를 뺐다.** 절제
리포트(`data/reports/priorart_v1_ablation.json` · 37건 · 예측 불일치 0)에서 미소비였던 것 중
`broaderConcept` 전이 · `skos:exactMatch ⊑ coveredBy` · 역술어 셋(`pa:conceptOfFeature` ·
`ont:featureOf` · `ont:claimOf` — 선언까지) · `pakr:NoticeOfReasons owl:differentFrom` 을 지웠다.
남긴 미소비는 둘뿐이고 사유가 코드에 있다: `substitutableWith`(경로 有 · PLAN-002 채굴 쌍 대기
· **일몰**) · `disjointWith` 4건(불변식 C 가 읽는다). `propertyChainAxiom` 넷은 넣지 않는다 —
추론기 없는 §3.3 배치에서 소비자가 성립할 수 없다. tests/test_stage6_ablation.py 가
"pa: R-Box ∖ RETAINED 중 미소비 0" 을 게이트로 건다.

**단계 7-0(2026-09-09 · 사용자 승인 D-S) — 일몰 조항을 실행했다.** 단계 7 착수 시점에
PLAN-002 3단계(`Prec` · 2인 코더)가 착수되지 않았으므로(저장소 안 흔적 0 · 머리말 "코더 배정
대기" 그대로) `pa:substitutableWith` 를 대칭·`⊑ coveredBy`·선언까지 지웠다(6-B 역술어 선례).
채굴 쌍이 들어오면 그때 pa: 소유의 하위 술어를 다시 만든다(§7-6 — 지금 만들지 않는다).
이제 core 의 R-Box 는 `broaderConcept ⊑ coveredBy` 하나이고, 남은 미소비 pa: R-Box 는
semi 의 `disjointWith` 4건(불변식 C)뿐이다.

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
from config.namespaces import SDKB_ONT, SDKB_GOV, SDKB_PA, SDKB_PA_KR, SDKB_PA_US, PROV  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ONT_DIR = ROOT / "ontology"

PA, ONT, GOV, PAKR, PAUS = SDKB_PA, SDKB_ONT, SDKB_GOV, SDKB_PA_KR, SDKB_PA_US

# 발행 메타. **상수다** — `datetime.now()` 를 쓰면 빌드마다 그래프가 달라지고
# 하류의 sha256 핀이 매일 깨진다(§0).
MODIFIED = "2026-09-09"
# 단계 8 의 US 모듈은 자기 발행일을 갖는다 — 공유 상수 `MODIFIED` 를 올리면 core·semi·kr
# 의 sha 가 함께 바뀌어 "L1 변경 0줄"(V6b) 을 이 커밋 스스로 깨뜨린다.
MODIFIED_US = "2026-09-11"
# ⑤ 논증층도 같은 이유로 자기 발행일을 갖는다.
MODIFIED_ARG = "2026-09-29"
VERSION = "0.1.0-dev"
LICENSE = URIRef("https://spdx.org/licenses/CDLA-Permissive-2.0.html")

CORE_IRI = URIRef("https://w3id.org/sdkb/pa")
SEMI_IRI = URIRef("https://w3id.org/sdkb/pa/semi")
KR_IRI = URIRef("https://w3id.org/sdkb/pa/kr")
US_IRI = URIRef("https://w3id.org/sdkb/pa/us")
ARG_IRI = URIRef("https://w3id.org/sdkb/pa/argument")
ONT_IRI = URIRef("https://w3id.org/sdkb/ont")
PATENT_IRI = URIRef("https://w3id.org/sdkb/ont/patent")

CORE_PREFIXES = {
    "pa": str(PA), "owl": str(OWL), "rdf": str(RDF), "rdfs": str(RDFS),
    "xsd": str(XSD), "skos": str(SKOS), "dcterms": str(DCTERMS), "prov": str(PROV),
}
SEMI_PREFIXES = dict(CORE_PREFIXES, ont=str(ONT))
KR_PREFIXES = dict(CORE_PREFIXES, ont=str(ONT), gov=str(GOV), pakr=str(PAKR))
# US 는 `ont:` 를 모른다 — 관할 바인딩이 도메인 접두를 갖는 순간 그 파일이 도메인을 아는 것이 된다.
US_PREFIXES = dict(CORE_PREFIXES, gov=str(GOV), paus=str(PAUS))


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
          "상위 개념. **전이로 선언하지 않는다**(6-B) — 전이면 coveredBy 가 하위 술어를 통해 "
          "사실상 전이가 되어 §3.3 의 동결 깊이 {0,1} 과 모순이고, 실측(skos:broader 18쌍 중 "
          "길이-2 사슬 0)으로도 함의 차이가 0 이다. 계층의 확장은 질의의 `?` 가 든다.",
          domain=PA.TechnicalConcept, range_=PA.TechnicalConcept)
    g.add((PA.broaderConcept, RDFS.subPropertyOf, PA.coveredBy))
    # `pa:substitutableWith`(대칭 · ⊑coveredBy)는 6-B 일몰 조항(D2)에 따라 **7-0 에서 뺐다** —
    # 단계 7 착수 시점까지 PLAN-002 3단계(Prec)가 착수되지 않았다(모듈 docstring). 치환 쌍이
    # 채굴되면 그때 술어를 다시 선언한다(§7-6 · 지금 만들지 않는다).
    # `skos:exactMatch ⊑ pa:coveredBy` 는 6-B 에서 뺐다 — 유량 0 이고, 가능한 유량은 sdkb-core 의
    # 클래스 정렬 23건과 kr 의 LegalGround↔RejectionType 2건뿐이라 오염 경로였다. 개념 동일성
    # 쌍이 채굴되면 그때 pa: 소유의 하위 술어를 새로 만든다(§7-6 · 지금 만들지 않는다).
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
    # `pa:conceptOfFeature owl:inverseOf pa:featureConcept` 는 6-B 에서 선언까지 뺐다 — 역술어를
    # 읽는 소비자가 없다(run_cq 무추론 · SHACL inference none). 거슬러 오르는 경로는 질의의 `^` 가 든다.
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
    # EquipmentClass — PLAN-005 단계 5-B(L1). 5-A 실측에서 equipment_class:* 7종(feature 45,257건)이
    # 이 슬롯에 걸리지 않아 프로파일에서 제외됐다(사용자 결정 3 · 5-B 의 레버). 기존 클래스 대
    # 기존 클래스 배제는 걸지 않는다(아래 상호배제 규칙).
    for c in [ONT.Process, ONT.SubProcess, ONT.Material, ONT.Device, ONT.Parameter, ONT.Problem,
              ONT.EquipmentClass]:
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
    # 소비자는 불변식 C(check_priorart_invariants.check_disjointness · 6-B) — 이 쌍을 여기서 읽어
    # core-data·A-Box 개체가 양쪽으로 타이핑됐는지 검사한다. 추론기가 없으므로 그것이 유일한 소비다.
    for a, b in [
        (ONT.StructuralElement, ONT.Process), (ONT.StructuralElement, ONT.Material),
        (ONT.TechnicalFunction, ONT.StructuralElement),
        (ONT.TechnicalEffect, ONT.StructuralElement),
    ]:
        g.add((a, OWL.disjointWith, b))

    # 역관계 `ont:featureOf`·`ont:claimOf`(inverseOf) 는 6-B 에서 선언까지 뺐다 — 읽는 소비자가 없다.

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
    # PLAN-001 §1.2(b) 의 owl:disjointWith 가 내려온 자리였다. 클래스가 아니라 differentFrom 으로
    # 두었으나 6-B 에서 뺐다 — 개체 상이성을 읽는 소비자가 없고(무추론), 두 문서종은 IRI 가 다르다.

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
# ④ us — 관할 바인딩의 두 번째 인스턴스 (단계 8 · V6b 종이 이식).
#    kr 과 같은 슬롯을 같은 방식으로 채운다. **core 는 손대지 않는다** — 그것이 판정이다.
# ═══════════════════════════════════════════════════════════════════
def build_us() -> Graph:
    g = Graph()
    g.add((US_IRI, RDF.type, OWL.Ontology))
    g.add((US_IRI, RDFS.label, Literal("SDKB Prior-Art — US jurisdiction binding", lang="en")))
    g.add((US_IRI, RDFS.comment, Literal(
        "US 특허법(35 U.S.C.) 조문·Office Action 문서종을 pa: 슬롯에 개체로 넣는다. "
        "PLAN-005 단계 8 (V6b 종이 이식) — 이 파일이 존재하는 동안 core·semi·kr 은 바이트 하나 "
        "바뀌지 않았다는 것을 scripts/report_stage8_paper_port.py 가 sha256 으로 센다. "
        "US 판정 어휘(KSR/TSM 등)는 원천이 이 저장소에 없어 넣지 않는다 — A-Box 없이 성립하는 "
        "설계 보증이며, US 회수 성능은 재지 않는다(PLAN-005 §7-8).", lang="ko")))
    g.add((US_IRI, OWL.versionInfo, Literal(VERSION)))
    g.add((US_IRI, DCTERMS.modified, Literal(MODIFIED_US, datatype=XSD.date)))
    g.add((US_IRI, DCTERMS.license, LICENSE))
    # core 만 import 한다. kr 이 sdkb-patent.ttl 을 import 하는 이유는 ont:Rejection_* 와의
    # exactMatch 인데, US 는 그 동치를 주장하지 않으므로 도메인 T-Box 를 끌어올 이유가 없다.
    g.add((US_IRI, OWL.imports, CORE_IRI))

    # ── 법적 근거 — shape 이 notation 과 관할을 필수로 건다 ──
    for local, ko, en, notation in [
        ("Ground_102", "신규성 부정 (35 U.S.C. §102)", "lack of novelty (35 U.S.C. §102)", "USPTO-102"),
        ("Ground_103", "비자명성 부정 (35 U.S.C. §103)", "obviousness (35 U.S.C. §103)", "USPTO-103"),
    ]:
        iri = PAUS[local]
        _indiv(g, iri, PA.LegalGround, ko, en)
        g.add((iri, SKOS.notation, Literal(notation)))
        g.add((iri, PA.underJurisdiction, GOV.JurisdictionUS))

    # ── 문서종 — 개체. KR 은 둘(통지서·거절결정서), US 도 둘이지만 이름과 절차가 다르다 ──
    _indiv(g, PAUS.NonFinalOfficeAction, PA.ExaminationDocumentType,
           "비최종 거절통지 (Non-Final Office Action)", "non-final Office Action")
    g.add((PAUS.NonFinalOfficeAction, PA.documentRole, PA.FirstAction))
    g.add((PAUS.NonFinalOfficeAction, PA.underJurisdiction, GOV.JurisdictionUS))
    _indiv(g, PAUS.FinalOfficeAction, PA.ExaminationDocumentType,
           "최종 거절통지 (Final Office Action)", "final Office Action")
    g.add((PAUS.FinalOfficeAction, PA.documentRole, PA.FinalAction))
    g.add((PAUS.FinalOfficeAction, PA.underJurisdiction, GOV.JurisdictionUS))
    return g


# ═══════════════════════════════════════════════════════════════════
# ⑤ argument — 판단 논증층. core 와 같은 순도: pa: 만 등장한다(불변식 A 가 이 파일에도 걸린다).
# ═══════════════════════════════════════════════════════════════════
def build_argument() -> Graph:
    g = Graph()
    g.add((ARG_IRI, RDF.type, OWL.Ontology))
    g.add((ARG_IRI, RDFS.label, Literal("SDKB Prior-Art Argument — examiner reasoning layer", lang="en")))
    g.add((ARG_IRI, RDFS.comment, Literal(
        "심사관 판단의 근거 구조 — 판단 단위(H1) · 요소↔증거 대응(H2) · 수치 구간(H3) · 논거 유형(H4). "
        "PLAN-005 R1 정답 해부의 결손 15종에서 도출했다(§20.15 · R1-스키마). core 와 같이 "
        "도메인·관할 어휘가 0 이며 scripts/check_priorart_invariants.py 가 그것을 검사한다.", lang="ko")))
    g.add((ARG_IRI, OWL.imports, CORE_IRI))
    g.add((ARG_IRI, OWL.versionInfo, Literal(VERSION)))
    g.add((ARG_IRI, DCTERMS.modified, Literal(MODIFIED_ARG, datatype=XSD.date)))
    g.add((ARG_IRI, DCTERMS.license, LICENSE))

    # ── H1 판단 단위 ──
    _cls(g, PA.ExaminerJudgment, "examiner judgment",
         "한 심사문서 안에서 한 근거로 청구항(또는 그 부가 한정)에 내린 판단 하나. "
         "`ont:PriorArtJudgment` 는 (출원, 인용문헌, 근거) 이분 엣지라 문헌 조합·무문헌 근거·"
         "선택적 근거를 담지 못한다 — 그래서 문헌을 키로 삼지 않는 단위를 따로 세운다.")
    _cls(g, PA.EvidenceSet, "evidence set",
         "판단을 받치는 근거 묶음 하나. **묶음 안은 결합(그리고), 묶음 사이는 선택(또는)** 이다 — "
         "「인용1 단독 또는 인용1·2 결합」은 묶음 둘이다. 문헌이 0 이면 상식 근거여야 한다(SHACL).")
    _cls(g, PA.JudgmentScope, "judgment scope",
         "판단이 청구항 전체를 대비했는가, 종속항이 **부가한 사항만** 대비했는가.")
    _prop(g, PA.judgesClaim, OWL.ObjectProperty, "judges claim",
          "판단이 겨냥한 청구항. range 는 도메인 어휘라 비운다. `pa:concernsClaim` 을 쓰지 않는 이유는 "
          "그 domain 이 ExaminerElement 라서 판단이 추론으로 요소가 되기 때문이다.",
          domain=PA.ExaminerJudgment)
    _prop(g, PA.concludes, OWL.ObjectProperty, "concludes",
          "판단의 결론. 판정 어휘는 core·관할 모듈의 ElementVerdict 개체를 그대로 쓴다. "
          "`pa:hasVerdict` 는 domain 이 ExaminerElement 라 쓰지 않는다.",
          domain=PA.ExaminerJudgment, range_=PA.ElementVerdict)
    _prop(g, PA.judgmentScope, OWL.ObjectProperty, "judgment scope",
          "청구항 전체 대비인가 부가 한정 대비인가.",
          domain=PA.ExaminerJudgment, range_=PA.JudgmentScope)
    _prop(g, PA.refersToJudgment, OWL.ObjectProperty, "refers to judgment",
          "이 판단이 근거로 재사용한 다른 판단(예: §29① 동일 판단을 §29② 의 전제로). "
          "**전이로 선언하지 않는다** — 심사관이 적은 참조만 담는다.",
          domain=PA.ExaminerJudgment, range_=PA.ExaminerJudgment)
    _prop(g, PA.supportedBy, OWL.ObjectProperty, "supported by",
          "판단의 근거 묶음. 둘 이상이면 선택적 근거다.",
          domain=PA.ExaminerJudgment, range_=PA.EvidenceSet)
    _prop(g, PA.includesDocument, OWL.ObjectProperty, "includes document",
          "묶음에 든 문헌. 둘 이상이면 결합이다. range 는 바인딩 몫이라 비운다.",
          domain=PA.EvidenceSet)
    _prop(g, PA.baseDocument, OWL.ObjectProperty, "base document",
          "결합·치환의 기준(주) 문헌 — 다른 문헌의 구성을 **이 문헌에** 옮겨 적용한다. "
          "방향이 여기 있다. 값은 includesDocument 에도 있어야 한다(생성기가 검사).",
          domain=PA.EvidenceSet)
    _prop(g, PA.reliesOnCommonKnowledge, OWL.DatatypeProperty, "relies on common knowledge",
          "문헌이 아니라 주지관용·통상 관행에 기댄 근거인가.",
          domain=PA.EvidenceSet, range_=XSD.boolean)

    # ── H4 논거 유형 ──
    _cls(g, PA.Rationale, "rationale",
         "차이를 메우는 정형 논거. 개체는 KR 통지서 30건에서 관찰된 것만 둔다 — 관할 중립적 "
         "이름이지만 US KSR 근거와 `skos:exactMatch` 를 선언하지 않는다(원천이 없다 · §7-6).")
    _prop(g, PA.hasRationale, OWL.ObjectProperty, "has rationale",
          "근거 묶음이 기댄 논거 유형.", domain=PA.EvidenceSet, range_=PA.Rationale)

    # ── H2 요소↔증거 대응 ──
    _cls(g, PA.EvidenceLink, "evidence link",
         "청구항 요소 하나를 문헌의 **어디**에 대응시켰는가. 용어 대응(claimTerm↔documentTerm)도 "
         "여기 담는다 — 두 이름이 같은 것이 된 근거가 이 링크다.")
    _cls(g, PA.DocumentLocator, "document locator",
         "문헌 안의 좌표(단락·도면·청구항·컬럼/라인·표·실시예·쪽). 값은 원문 표기 그대로 둔다.")
    _cls(g, PA.LocatorType, "locator type", "좌표의 종류.")
    _prop(g, PA.partOfJudgment, OWL.ObjectProperty, "part of judgment",
          "이 대응이 속한 판단.", domain=PA.EvidenceLink, range_=PA.ExaminerJudgment)
    _prop(g, PA.forElement, OWL.ObjectProperty, "for element",
          "대응의 좌변이 심사관 구성대비표의 요소일 때 그 요소. 표가 적재되지 않은 판단에는 없다.",
          domain=PA.EvidenceLink, range_=PA.ExaminerElement)
    _prop(g, PA.inDocument, OWL.ObjectProperty, "in document",
          "대응의 우변 문헌. range 는 바인딩 몫이라 비운다.", domain=PA.EvidenceLink)
    _prop(g, PA.locator, OWL.ObjectProperty, "locator",
          "문헌 안의 좌표.", domain=PA.EvidenceLink, range_=PA.DocumentLocator)
    _prop(g, PA.locatorType, OWL.ObjectProperty, "locator type",
          "좌표의 종류.", domain=PA.DocumentLocator, range_=PA.LocatorType)
    for iri, lab, rng, dom, com in [
        (PA.locatorValue, "locator value", XSD.string, PA.DocumentLocator,
         "원문 표기 그대로의 좌표 값(예: `[0010]~[0013]` · `도4` · `컬럼3 라인5~23`)."),
        (PA.claimTerm, "claim term", XSD.string, PA.EvidenceLink, "청구항 쪽 용어."),
        (PA.documentTerm, "document term", XSD.string, PA.EvidenceLink, "문헌 쪽 용어."),
    ]:
        _prop(g, iri, OWL.DatatypeProperty, lab, com, domain=dom, range_=rng)

    # ── H3 수치 구간 ──
    _cls(g, PA.NumericInterval, "numeric interval",
         "하한·상한·개폐·단위를 갖는 구간. 한쪽만 있으면 임계(이상·이하)다. 리터럴 한 값"
         "(`ont:hasNumericValue`)으로는 겹침·포함을 질의할 수 없어서 둔다.")
    _cls(g, PA.IntervalRelation, "interval relation",
         "심사관이 적은 두 구간의 관계. 경계값에서 다시 계산할 수 있지만 심사관의 판단을 그대로 보존한다.")
    _prop(g, PA.claimedInterval, OWL.ObjectProperty, "claimed interval",
          "청구항이 한정한 구간.", domain=PA.EvidenceLink, range_=PA.NumericInterval)
    _prop(g, PA.disclosedInterval, OWL.ObjectProperty, "disclosed interval",
          "문헌이 개시한 구간(또는 값).", domain=PA.EvidenceLink, range_=PA.NumericInterval)
    _prop(g, PA.intervalRelation, OWL.ObjectProperty, "interval relation",
          "개시 구간이 청구 구간에 대해 갖는 관계.",
          domain=PA.EvidenceLink, range_=PA.IntervalRelation)
    for iri, lab, rng, com in [
        (PA.quantityLabel, "quantity label", XSD.string, "무엇의 양인가(원문 표기)."),
        (PA.lowerBound, "lower bound", XSD.decimal, "하한."),
        (PA.upperBound, "upper bound", XSD.decimal, "상한. 하한 이상이어야 한다(SHACL)."),
        (PA.lowerInclusive, "lower inclusive", XSD.boolean, "하한 포함 여부(이상=참 · 초과=거짓)."),
        (PA.upperInclusive, "upper inclusive", XSD.boolean, "상한 포함 여부(이하=참 · 미만=거짓)."),
        (PA.unitText, "unit text", XSD.string, "단위 표기. 단위 환산은 하지 않는다 — 같은 단위끼리만 비교한다."),
    ]:
        _prop(g, iri, OWL.DatatypeProperty, lab, com, domain=PA.NumericInterval, range_=rng)

    # ── 개체 ──
    for iri, ko, en in [
        (PA.ScopeWholeClaim, "청구항 전체", "whole claim"),
        (PA.ScopeAddedLimitation, "부가한 사항", "added limitation"),
    ]:
        _indiv(g, iri, PA.JudgmentScope, ko, en)
    for iri, ko, en in [
        (PA.LocParagraph, "단락", "paragraph"),
        (PA.LocFigure, "도면", "figure"),
        (PA.LocClaim, "청구항", "claim"),
        (PA.LocColumnLine, "컬럼·라인", "column and line"),
        (PA.LocTable, "표", "table"),
        (PA.LocExample, "실시예", "example"),
        (PA.LocPage, "쪽", "page"),
    ]:
        _indiv(g, iri, PA.LocatorType, ko, en)
    for iri, ko, en, com in [
        (PA.IntervalOverlaps, "일부 겹침", "overlaps", "두 구간이 일부만 겹친다."),
        (PA.IntervalDisclosedWithinClaimed, "개시가 청구 범위 안", "disclosed within claimed",
         "개시 구간(값)이 청구 구간에 포함된다 — 신규성 부정의 전형."),
        (PA.IntervalClaimedWithinDisclosed, "청구가 개시 범위 안", "claimed within disclosed",
         "청구 구간이 개시 구간보다 좁다 — 선택·최적화 논거가 붙는 자리."),
        (PA.IntervalDisjoint, "겹치지 않음", "disjoint", "두 구간이 겹치지 않는다."),
    ]:
        _indiv(g, iri, PA.IntervalRelation, ko, en, com)
    for iri, ko, en, com in [
        (PA.RationaleDesignChoice, "설계선택·최적화", "design choice",
         "필요에 따라 적절히 선택·최적화할 수 있는 정도."),
        (PA.RationalePredictableEffect, "효과 예측 가능", "predictable effect",
         "효과가 통상 예측되는 정도이거나 결합에서 자연히 생긴다."),
        (PA.RationaleCombinationMotivation, "결합 동기", "combination motivation",
         "기술분야·목적·효과의 공통이 결합의 동기가 된다."),
        (PA.RationaleRoutinePractice, "통상 수행·자명", "routine practice",
         "통상적으로 수행하는 정도이거나 자연히 얻어지는 구성."),
        (PA.RationaleSubstitution, "치환·전용", "substitution or transfer",
         "다른 문헌의 재료·구성을 기준 문헌에 바꿔 넣거나 옮겨 적용한다. 방향은 "
         "EvidenceSet 의 baseDocument 가 든다."),
    ]:
        _indiv(g, iri, PA.Rationale, ko, en, com)
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
    ("sdkb-priorart-us.ttl", build_us, US_PREFIXES,
     "SDKB Prior-Art — US 관할 바인딩 (paus: → pa:) · 단계 8 V6b 종이 이식"),
    ("sdkb-priorart-argument.ttl", build_argument, CORE_PREFIXES,
     "SDKB Prior-Art Argument (pa:) — 판단 논증층 · 도메인 어휘 0 · 관할 어휘 0"),
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
