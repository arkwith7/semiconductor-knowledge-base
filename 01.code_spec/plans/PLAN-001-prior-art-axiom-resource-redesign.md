# PLAN-001 — 선행기술조사 온톨로지 재구성: T-Box · R-Box · A-Box

> **지위: 요구 정의 · 승인 대기 🛑.** 이 문서는 [CLAUDE.md §2](../../CLAUDE.md) 5단계의
> **1단계**이며, 승인 없이 2단계(분석)로 넘어가지 않는다. **이 파일이 저장소에 있다는 사실을
> 승인으로 읽지 않는다.** T-Box·shape·IRI 규칙을 바꾸는 항목은 §2 3단계에서 **별도로**
> 승인받는다 — §0 의 하류 소비자가 깨지기 때문이다.
>
> **출처 (2026-08-29 · 사용자 지시로 이관).** 하류 실험 저장소
> `sdkb-prior-art-paper` 의 `01.code_spec/plans/PLAN-071` **1부** 원문이다. 하류 논문의 논조가
> 확정되면서, **자원을 바꾸는 설계가 자원을 소유하지 않은 저장소에 있는 상태**를 해소한다.
> 원문은 2026-08-23 작성분이며 **한 글자도 고치지 않았다** — 아래 머리말만 새로 붙였다.
> 하류에 남는 것은 **2부(검색 실험 재설계)** 와 착수 판정 기록이고, 하류 PLAN-071 의 1부
> 자리에는 이 문서를 가리키는 이관 포인터가 선다.
>
> **짝이 되는 계획.** 이 설계의 원천을 실제로 캘 수 있는가는
> [PLAN-002](PLAN-002-examiner-axiom-mining-unit.md) 가 계수했고, 그 판정은 **부분**이다.
> **PLAN-002 의 착수 판정이 이 계획의 선행 조건이다** — 공리의 원천이 없으면 §1.2 의 T-Box
> 모듈은 채울 것이 없다.

## 왜 재구성이 선행되는가 — 하류가 관측한 전제

아래 표는 하류 저장소의 실측이며 이 저장소에서 새로 산출한 값이 아니다. 원 기록은 하류
`01.code_spec/plans/PLAN-071` §0 이고, 결함 등재는 하류 `upstream/DEFECT-LEDGER.md` 다.


| 항목 | 실측 | 함의 |
|---|---|---|
| ClaimFeature 개념 미매핑률 | **71.7%** (1,306,191행 중) | 한정요소 10개 중 7개가 온톨로지 밖 → 의미 경로 부재 |
| 사용 개념 종류 | **109개**, `material:sio2`(74k)·`process:etch`(45k) 등 조립 개념 집중 | 대규모 동점 블록, 분별력 없음 |
| 개념 유형 | Skill·FailureMode 등 전문가 매칭용 어휘 | 청구항 한정요소의 의미와 불일치 |
| R-Box 공리 | TransitiveProperty 1개뿐 (chain·inverse·disjoint 0) | 추론으로 간접 경로가 생성될 여지 없음 |
| 선행기술 연결 | `hasPriorArtExaminer`·`overPriorArt` 등 전부 정답 간선 | 마스킹하면 남는 의미 연결이 사실상 없음 |
| 문서 유형 분포 | 의견제출통지서 2,060행 vs 거절결정서 689행 (§29① 262 vs 15) | 대비 논리의 실질 원천은 통지서 |
| 문서 보유 구조 | 두 문서 모두 623건 / 통지서만 370건 / 라운드 최대 5차 | 심사경과(생존·철회) 신호 존재 |

현재 상태는 "정답지 + 조립 태그"이며 지식체계가 아니다. 이 상태에서 검색 실험을
하면 낮은 도달성은 검색 알고리즘이 아니라 자원 부적격의 결과이므로, 재구성(1부)이
실험(2부)에 선행한다.

---

---

# 1부. 온톨로지 재구성 — T-Box · R-Box · A-Box

## 1.1 설계 원칙: 행정문서를 '정답'이 아니라 '공리의 원천'으로

> 거절통지 문서는 (거절특허 → 인용문헌) 링크가 아니라, **심사관이 두 기술적
> 구성을 동일·상위·치환 가능·결합 용이하다고 판단한 기록**이다. 이 판단을
> A-Box 정답 간선이 아니라 **T-Box/R-Box 공리**로 흡수하면, 직접 간선 없이도
> 인용 선행기술(특허·비특허)의 주요 청구항/개시에 의미 경로로 도달할 수 있다.

두 문서의 인식론적 역할을 구분한다.

| 문서 | 역할 | 온톨로지에서의 지위 |
|---|---|---|
| **의견제출통지서** | 대비 논리의 원천 — 어느 인용발명의 어느 개시가 어느 한정요소에 대응·치환·결합되는가 | **후보 공리**(confidence=provisional)의 추출 재료 |
| **거절결정서** | 출원인 반박·보정을 거치고 생존한 판단의 확정 | 후보 공리의 **확정 승격**(confidence=confirmed) |
| 통지서에 있었으나 소멸한 인용 (Withdrawn) | 성립하지 않은 대응·치환의 기록 | **부정 증거** — 비치환 공리 후보, 공리 반례 카운트 |

이로써 통지서→결정서→철회가 "공리의 생성→확정→반증"이라는 지식 생애주기가 되고,
같은 구분이 그대로 qrel 등급과 평가 하위집단으로 이어진다.

## 1.2 T-Box — 두 개의 신규 모듈

기존 `sdkb-patent.ttl`은 유지하고 `sdkb-claim-semantics.ttl`을 추가한다
(`owl:imports` 결합).

### (a) 청구항 의미층 — 심사관의 독법(구성·작용·효과·조건)을 따름

```turtle
ont:TechnicalConcept          # skos:Concept 하위, 모든 청구항 개념의 공통 상위
  ├ ont:StructuralElement     # 층·패턴·전극·게이트·스페이서·비아 등 구조물
  ├ ont:ProcessStep           # 기존 Process/SubProcess 재사용 + 단계 세분
  ├ ont:Material              # 기존 재사용, 조성·도핑 하위 확장
  ├ ont:ProcessCondition      # 온도·압력·가스비·두께 (Parameter + 값 구간)
  ├ ont:Function              # "~을 방지하기 위한", "~을 제어하는" 작용
  ├ ont:TechnicalEffect       # 누설전류 감소, 스텝커버리지 향상
  └ ont:TechnicalProblem      # 해결과제 (기존 Problem 재사용)

ont:ClaimFeature
  ont:featureRole    → {Means, Structure, Step, Material, Condition, Function, Effect}
  ont:featureConcept → ont:TechnicalConcept    # 기존 union 범위를 교체
  ont:qualifies      → ont:ClaimFeature        # '상기 X' 수식 (기존 dependsOnFeature)

ont:ClaimProfile     # 독립항 1건의 의미 요약 — 질의·문헌 양쪽 공통 단위
  ont:solvesProblem    → TechnicalProblem
  ont:achievesEffect   → TechnicalEffect
  ont:essentialConcept → TechnicalConcept      # 독립항 필수구성
  ont:optionalConcept  → TechnicalConcept      # 종속항 부가구성
```

### (b) 심사경과층 — 문서·라운드·보정을 1급 객체로

```turtle
ont:ExaminationDocument  rdfs:subClassOf prov:Entity .
ont:NotificationOfReasons   rdfs:subClassOf ont:ExaminationDocument .  # 의견제출통지서
ont:FinalRejectionDecision  rdfs:subClassOf ont:ExaminationDocument .  # 거절결정서
ont:NotificationOfReasons owl:disjointWith ont:FinalRejectionDecision .
ont:examRound / ont:issuedDate / ont:concernsPatent

ont:ClaimVersion         # 라운드 2+ 는 보정된 청구항을 대비 — 버전 없이는 오접지
  ont:versionOf → ont:Claim ;  ont:atRound → xsd:integer ;
  ont:amendedFrom → ont:ClaimVersion .

# PriorArtJudgment 확장
ont:assertedIn        → ont:ExaminationDocument
ont:aboutClaimVersion → ont:ClaimVersion
ont:citationStatus    → { ont:Provisional    # 통지서에만 등장
                          ont:Maintained     # 거절결정서까지 생존/직접 등장
                          ont:Withdrawn }    # 후속 문서에서 소멸
```

`citationStatus`는 문서 계열을 시간순 정렬해 **파생 계산**하는 값이다
(`derive_citation_status.py`, 규칙 사전등록, `prov:wasGeneratedBy` 표시).

### (c) 통지서에서 추출해 T-Box에 넣는 공리 (A-Box가 아님)

| 통지서 표현 | 추출 공리 | OWL 표현 |
|---|---|---|
| "인용발명의 하드마스크 패턴은 본원의 식각 마스크에 대응" | 개념 동치/상하위 | `skos:exactMatch` / `rdfs:subClassOf` |
| "주지관용기술에 불과" | 개념 속성 | `ont:isCommonKnowledge true` + 적용 기술군 |
| "단순 설계변경 / 재료의 치환" | 치환 가능 집합 | `ont:substitutableWith` (Symmetric) |
| "인용발명 1·2 결합에 곤란성 없음" | 결합 용이 쌍 | `ont:combinableWith` (Symmetric, 기술군 한정) |
| "수치한정에 임계적 의의 없음" | 조건 구간 포섭 | `ProcessCondition` 구간 포함 규칙 |

모든 채굴 공리는 다음 provenance를 필수로 갖는다.

```turtle
ont:substitutableWith_sio2_sion  a ont:MinedAxiom ;
    ont:axiomConfidence "confirmed" ;         # provisional | confirmed
    ont:supportCount 7 ; ont:counterCount 1 ; # 지지 / 반례(Withdrawn 유래) 건수
    prov:wasDerivedFrom <reason_id...> ;      # 전부 dev 분할 문서
    ont:sourceDocType ont:NotificationOfReasons .
```

## 1.3 R-Box — 간접 경로가 '추론으로 생기도록'

OWL 2 RL 범위 안에서 다음을 선언한다. 경로 유형과 가중치가 검색 코드가 아니라
**온톨로지 자원 번들의 일부**가 되므로 O→O′ 교체 시 변경이 TTL diff로 드러난다.

```turtle
# 역관계 — 문헌 쪽에서 질의 쪽으로 거슬러 오르는 경로 필수
ont:featureOf         owl:inverseOf ont:hasFeature .
ont:claimOf           owl:inverseOf ont:hasClaim .
ont:conceptOfFeature  owl:inverseOf ont:featureConcept .

# 전이 — 계층 확장
ont:broaderConcept a owl:TransitiveProperty .
ont:hasSubStep     a owl:TransitiveProperty .

# 속성 체인 — 정답 간선 없이 문헌끼리 연결되는 파생 관계
ont:sharesConceptWith owl:propertyChainAxiom
  ( ont:hasFeature ont:featureConcept ont:conceptOfFeature ont:featureOf ) .
ont:sharesSubstitutableConceptWith owl:propertyChainAxiom
  ( ont:hasFeature ont:featureConcept ont:substitutableWith
    ont:conceptOfFeature ont:featureOf ) .
ont:sharesProblemWith owl:propertyChainAxiom
  ( ont:solvesProblem ont:problemOf ) .
ont:sharesBroaderConceptWith owl:propertyChainAxiom          # 상위 개념 1단계만
  ( ont:hasFeature ont:featureConcept ont:broaderConcept
    ont:conceptOfFeature ont:featureOf ) .

# 상호배제 — 동점 블록 억제 + SHACL 오류 검출
ont:StructuralElement owl:disjointWith ont:ProcessStep , ont:Material .
ont:Function          owl:disjointWith ont:StructuralElement .
```

경로 가중치는 공리 confidence 차등(confirmed > provisional)을 포함해 자원
번들 설정으로 선언한다.

## 1.4 A-Box — 양쪽 문헌을 같은 해상도로, 목표 노드를 명시

1. **인용 선행기술의 대상 개시 실체화**: `PriorArtJudgment`에
   `ont:overDisclosure → ont:Disclosure`(인용특허의 청구항 또는 명세서 단락,
   통지서의 "인용발명 1의 청구항 3 / 단락 [0025]")를 추가. 이 노드가 도달성
   측정의 **목표 노드**다. 간선 자체는 정답 유래이므로 검색 시 마스킹하되,
   평가 목표를 "문헌 도달"에서 "주요 청구항/개시 도달"로 올린다.
2. **인용특허 측에도 동일 파이프라인으로 ClaimProfile 생성** (규칙+LLM 분해 →
   featureRole → TechnicalConcept). 거절특허 측과 개념 해상도 동일 보장.
3. **비특허문헌(NPL)**: `ont:NonPatentLiterature` 클래스 + 핵심 개시 단위의
   동일 Profile 구조. `overPriorArt`에 range가 없는 이유를 노드 타입으로 해소.
4. **ClaimProfile은 ClaimVersion 단위**로 생성 — 라운드 2+ 보정 반영, 대비된
   버전에 접지.
5. **개념 커버리지 목표**: 미매핑 71.7% → **20% 이하**. (a) CPC 서브그룹
   정의문에서 TechnicalConcept 후보 추출, (b) 거절·인용특허 청구항 명사구
   클러스터링 후 큐레이션, (c) 기존 v0.3 274노드는 `broaderConcept` 상위로
   유지. 109개 → 최소 수백~천 단위 개념 필요.
6. **개념 특이도(IDF)**: 개념별 df를 기록해 `material:sio2` 류가 경로 점수를
   지배하지 않게 함 (concept_mapping.json CR-009 방침과 정합).

## 1.5 qrel 등급 재정의 (기존 2점/1점/unknown 체계와 정합)

| 등급 | 정의 | 근거 |
|---|---|---|
| **2 (강)** | citationStatus=Maintained | 출원인 반박을 거친 확정 판단 |
| **1 (약)** | Provisional (통지서만, §29①/② 근거) | 심사관 1차 판단 — 여전히 양성 |
| **별도 트랙** | Withdrawn | qrel 제외, **hard-negative 후보 풀**로 보관 (비관련 확정 아님 — 절차적 소멸 가능성) |

절차적 사유(기재요건·단일성 등)에 딸린 인용은 qrel에서 배제:
`ground ∈ {Rejection_Novelty, Rejection_Inventiveness, Rejection_ExpandedPriorFiling}`
필터를 사전등록.

진단 지표: "Withdrawn 문헌이 Maintained보다 위에 랭크되는 빈도" — 온톨로지가
심사관의 최종 판단 구조를 반영하는지의 부차 신호.

## 1.6 누출 규율 — 구축과 테스트 양쪽 사용의 조건

1. **분할 축은 특허 패밀리. 문서 유형이 아님.** "통지서로 구축, 결정서로
   테스트" 같은 문서 내부 분할은 같은 대비 논리를 양쪽에 두는 직접 누출이므로
   금지 (두 문서 동시 보유 623건).
2. dev 패밀리의 통지서·결정서 → 공리 추출 허용. **test 패밀리의 어떤
   문서에서도 공리 추출 금지.** `check_leakage.py`가 모든 MinedAxiom의
   `prov:wasDerivedFrom`을 역추적해 test reason_id 유래 0건 검증.
3. 시간 적격성: 인용문헌 공개일 < 거절특허 출원일. 보정 청구항 질의 시 대비
   문서의 `issuedDate` 기록.
4. 검색 시 마스킹 대상: `hasPriorArt{,Examiner,Applicant}` · `overPriorArt` ·
   `overDisclosure` · `overlappingFeature` · `NoveltyScore` · qrel 파생 링크 일체.

## 1.7 질의 시점 동작 — 연구개발요약/청구항의 A-Box 인스턴스화

질의 문서는 T-Box에 넣는 것이 아니라 **T-Box가 정의한 클래스의 임시 A-Box
인스턴스(ClaimProfile)로 변환**되어 기존 문헌과 같은 의미 공간에서 경로
점수로 비교된다.

```
연구개발요약 / 청구항 텍스트
  │ ① 분해 (구축과 동일한 규칙+LLM 파이프라인)
  ▼ ClaimFeature 목록 (featureRole 부여)
  │ ② 개념 링킹 (표면형 사전 + 프로파일)
  ▼ :query_001 a ont:ClaimProfile ; essentialConcept ... ; solvesProblem ...
  │ ③ 경로 구체화·점수화 (동결된 경로 유형 × 가중치)
  ▼ 후보 랭킹 + 후보별 의미 경로 근거 (설명 가능)
```

성립 조건 세 가지 = 2부 실험이 측정하는 바로 그것:
① 개념 커버리지(미매핑이면 score=0), ② 공리 밀도(표현이 다른 문서를 잇는
치환·상하위·문제공유 공리), ③ 코퍼스 범위(A-Box에 색인된 문헌만 검색).

한계 두 가지(논문·제품 서술 공통):
- 연구개발요약은 청구항보다 분해가 어려움 → 논문 질의 단위는
  (거절특허, 독립청구항) 유지, 요약 질의는 제품(IPBridge) 확장으로 분리.
  요약은 "유사 청구항 형태 정규화" 전처리 단계 추가.
- 시스템 출력은 "선행기술 판정"이 아니라 **설명 가능한 후보 + 근거 경로**.
  Recall@100이 지표인 이유: 검토 후보 100건 안에 진짜 선행기술이 들도록.

구현: `build_claim_profiles.py`는 배치(구축)·단건 질의 양 모드를 지원하는
단일 모듈로 — 재현성 보장.

## 1.8 구현 단계와 게이트

| 단계 | 산출물 | 검증 |
|---|---|---|
| O-1 | `sdkb-claim-semantics.ttl` (청구항 의미층 + 심사경과층) + SHACL | `owl:imports` 결합 일관성 통과 |
| O-1.5 | `derive_citation_status.py` — Provisional/Maintained/Withdrawn 파생 | 분포 리포트 (문서유형×근거 교차표) |
| O-2 | `mine_examiner_axioms.py` — 문서 유형 인지형: 통지서=후보, 결정서=승격, Withdrawn=부정 증거 | 사람 검토 후 승인분만 TTL화, provenance 필수, 문서유형별 공리 수율 리포트 |
| O-3 | `build_claim_profiles.py` — rej/cited/NPL 공통, ClaimVersion 단위, 배치+단건 모드 | 미매핑률·개념 수·개념별 df 리포트 |
| O-4 | `materialize_paths.py` — 체인·역관계·전이 구체화, confidence 전파 → `derived_paths.parquet` | 정답 간선 마스킹 상태 실행, `check_leakage.py` 0건 |
| O-5 | 도달성 리포트 — grade 2/1 × 경로 유형 × 공리 confidence 3축 교차표 | **진입 조건**: SemanticPathRecall(독립항 기준) 유의 수준(예: ≥60%) 미달 시 2부 착수 금지 |

---
