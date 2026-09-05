# PLAN-001 — 선행기술조사 온톨로지 재구성: T-Box · R-Box · A-Box

> **지위 갱신 2026-09-05 — 후속 논문의 조건에서 *하류 현 논문의 선행 조건*으로.** 하류 논지가
> 지식베이스의 사례·구축 방법으로 피벗했다(하류 `01.code_spec/plans/PLAN-092`). 이 계획이 채우는
> 것은 그 논문의 조건 **C-2(R-Box)** 와 **C-3(근거 있는 A-Box · 선행기술 뷰 한정)** 이며,
> **하류 투고가 이 계획의 완주에 종속된다.** 순서와 종료 조건은
> [PLAN-004](PLAN-004-kb-sufficiency-roadmap.md) 가 진다. **본문은 고치지 않았고 승인 상태도
> 그대로 대기다** — 임계경로에 올라왔다는 것이지 승인됐다는 뜻이 아니다.
>
> **C-2 의 종료 조건은 공리 개수가 아니다.** `inverseOf`·`propertyChainAxiom`·`disjointWith` 가
> 각 0 을 벗어나는 것에 더해, **각 공리가 어느 CQ 또는 어느 태스크 경로에 쓰이는지**를 밝혀야
> 한다 — 쓰이지 않는 공리는 자원 지표만 올리고 태스크에는 비가시다(하류 EP3 의 실측).
>
> **역할 구분 추가 (2026-09-05 · §1.9 신설).** 본문 §1.1–§1.8 은 그대로 두고, **각 공리가
> 판정 공리인지 후보 생성 공리인지**를 §1.9 가 구분한다. 특히 §1.3 의 `propertyChainAxiom` 넷은
> **후보 생성 공리이며 신규성·진보성 판정이 아니다** — 그 구분 없이는 "체인 4개 신설"이 적격
> 충족으로 오독된다. 근거는 [PLAN-005](PLAN-005-prior-art-tool-qualification.md) §3.
>
> **이식성 판정 추가 (2026-09-05 · 사용자 승인 · §1.10 신설).** 안 **C′-full** 이 채택되어
> **§1.2(b) 의 문서종 클래스 선언과 `owl:disjointWith` 는 §1.10(c) 로 대체된다.** 이 계획은
> 이제 *"반도체 전용 아닌가"* 와 *"한국 특허청 전용 아닌가"* 두 질문에 **설계로 답한다** —
> `pa:` 이름공간의 도메인·관할 **슬롯 두 축**, 그리고 `pa:underJurisdiction` 을 MinedAxiom
> 의 **필수 provenance** 로 두는 것이 그 답이다. 검증은 PLAN-005 §5 **V6**.

> **지위: 요구 정의 · 승인 대기 🛑.** 이 문서는 [CLAUDE.md §2](../../CLAUDE.md) 5단계의
> **1단계**이며, 승인 없이 2단계(분석)로 넘어가지 않는다. **이 파일이 저장소에 있다는 사실을
> 승인으로 읽지 않는다.** T-Box·shape·IRI 규칙을 바꾸는 항목은 §2 3단계에서 **별도로**
> 승인받는다 — §0 의 하류 소비자가 깨지기 때문이다.
>
> **출처 (2026-08-29 · 사용자 지시로 이관).** 하류 실험 저장소
> `sdkb-prior-art-paper` 의 `01.code_spec/plans/PLAN-071` **1부** 원문이다. 하류 논문의 논조가
> 확정되면서, **자원을 바꾸는 설계가 자원을 소유하지 않은 저장소에 있는 상태**를 해소한다.
> 원문은 2026-08-23 작성분이며 **한 글자도 고치지 않았다** — 아래 머리말만 새로 붙였다.
> 이관 당시 하류에 남긴 것은 **2부(검색 실험 재설계)** 와 착수 판정 기록이었고, 하류
> PLAN-071 의 1부 자리에는 이 문서를 가리키는 이관 포인터를 세웠다. **2026-08-30 갱신 —
> 2부와 부록도 [PLAN-003](PLAN-003-ontology-first-retrieval-experiment.md) 으로 이관됐고,
> 하류 PLAN-071 은 §-1(착수 판정 기록)만 남긴 이관 기록으로 아카이브에 있다**
> (`01.code_spec/archive/`). **이 문단은 그때의 기록이며 소급 수정하지 않는다 — 경로만
> 덧붙였다.**
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

## 1.9 아키텍처 판정 — 공리의 역할 구분 (2026-09-05 · PLAN-005 §3 편입)

> **본문 §1.1–§1.8 은 한 글자도 고치지 않았다.** 이 절은 그 위에 **역할 구분**을 덧붙인다.
> 설계는 유지되고, 각 공리가 무엇을 하는 물건인지가 명시된다. 근거와 실측은
> [PLAN-005](PLAN-005-prior-art-tool-qualification.md) §3 · [진단 보고서](../reports/PLAN-005-diagnosis.md).

### (a) 원소층과 집합층 — 이 구분이 없어서 생긴 오독

세 업무 목적(신규성·진보성·FTO)은 전부 두 층으로 분해된다.

- **원소층** — 질의 요소 하나가 문헌 개시 요소 하나로 충족되는가 (동일·상위·치환·주지관용)
- **집합층** — 그 판정을 요소 집합 전체에 정량화 (전부 포함 / 몇 % / 두 문헌 합집합이 덮는가)

> **OWL 이 잘 하는 것은 원소층이고, 못 하는 것은 집합층이다.**

### (b) §1.3 의 `propertyChainAxiom` 넷은 **판정 공리가 아니라 후보 생성 공리다**

속성 체인의 의미론은 **존재 양화**다. `sharesConceptWith` 는 **개념 하나만 겹쳐도 간선을 만들고,
스무 개가 전부 겹쳐도 같은 간선 하나**를 만든다 — 속성 체인은 셀 수 없다. 접지 개념이 122종이고
`material:sio2` 가 74k건인 현 자원에서 이 간선은 코퍼스를 거대한 동점 블록으로 묶는다.

**그러므로 §1.3 의 체인 넷은 후보 생성(recall device)으로는 타당하고 신규성·진보성 판정으로는
무효다.** 이 구분을 적지 않으면 *"체인 공리 4개 신설"* 이 적격 조건 충족으로 오독된다.

### (c) 집합층은 OWL 밖이다 — 권고 배치

신규성(집합 포함)은 질의별 클래스를 만들면 표현은 되지만 **쓸 수 없다**: 질의마다 T-Box 가 바뀌고,
불리언이라 순위를 못 내며, 개방세계라 *"신규하다"* 는 원리적으로 함의되지 않고, 규모가 성립하지
않는다. 진보성(2문헌 합집합 커버)은 쌍 위의 술어·합집합 양화·계수가 전부 OWL 문법에 없어 **여지가
없다.**

| 층 | 형식 | 역할 |
|---|---|---|
| 원소층 | **OWL 2 RL** | `coveredBy` 로 동일·상위·치환·주지관용을 닫는다 |
| 집합층 정의 | **SHACL** | "필수요소가 전부 덮였는가"의 정본 정의 — 폐쇄세계라 부정을 표현할 수 있다 |
| 집합층 계산 | **SPARQL** | 커버율·조합 커버를 등급으로 계산하고 순위를 낸다 |

**이 배치에서 §1.3 의 공리는 전부 살아남되 역할이 바뀐다.** `substitutableWith` ·
`broaderConcept` · `skos:exactMatch` 는 판정의 *결정자*가 아니라 **원소층 충족의 확장자**이며,
그 확장이 매칭을 몇 개 더 만들었는지는 **셀 수 있다**(PLAN-005 §5 V1 절제).

### (d) `coveredBy` 를 전이로 선언하지 않는다

원소층을 한 술어로 모을 때 전이를 붙이면, "SiO₂↔SiON"·"SiON↔Si₃N₄" 두 심사 판단에서 **심사관이
판단한 적 없는 "SiO₂↔Si₃N₄" 가 자동 생성**되고 §1.2(c) 의 `supportCount`/`counterCount`
provenance 를 우회한다. 대칭+전이는 개념 그래프를 연결성분 단위로 붕괴시킨다.
**확장 깊이는 의미론이 아니라 동결된 설정값으로 둔다**(`?` / `{0,1}`).

### (e) 태스크 질의에서 행정 어휘를 금지한다 — 기계 검사

> 태스크 질의의 `WHERE` 필수 부분에 `ont:Patent` · `ont:RejectedPatent` · `ont:RejectionType` ·
> `ont:PriorArtJudgment` · `ont:overPriorArt` 가 등장하면 **실패**. 이들은 `OPTIONAL { }` 증거
> 블록에서만 허용한다.

이 검사가 §1.7 의 *"연구개발요약 질의"* 를 실제로 가능하게 한다. 지금 불가능한 이유는 정확히
`queries/cq/CQ10_prior_art_candidates_by_concept.rq` 가 `?prior a ont:Patent` 로 시작하기 때문이다.

**그리고 §1.7 의 한계 서술 하나가 갱신된다.** §1.7 은 *"요약 질의는 제품 확장으로 분리"* 라고
적었으나, PLAN-005 의 목표는 **도구 자체**이므로 요약·연구노트 질의는 **분리 대상이 아니라 1급
검증 대상**이다(PLAN-005 §5 V4). §1.7 의 질의 시점 파이프라인은 그대로 쓴다.

### (f) §1.8 O-5 의 진입 조건 보정 — 목표 노드와 특이도

- **목표 노드**: O-5 가 전제하는 `ont:Disclosure` 는 현재 **클래스 선언도 인스턴스도 0건**이므로
  **오늘은 이 지표를 정의된 형태로 잴 수 없다.** 기준선은 인용문헌 노드(퇴화형)로 재고 그 사실을
  함께 적으며, 정본 수준은 O-3 이후에 잰다.
- **특이도**: `≥60%` 단일 임계에는 퇴화 최적해가 있다 — 흔한 개념 하나를 모든 문헌에 붙이면
  도달률이 1.0 에 접근한다. 진입 조건을 셋으로 한다: (i) 기준선 대비 유의 상승 (ii) 절대 하한
  통과 (iii) **`|Reach(q)|` 중앙값이 기준선 대비 증가하지 않음.**

---

## 1.10 이식성 판정 — 도메인 슬롯과 관할 슬롯 (2026-09-05 · 사용자 승인 · 안 C′-full)

> **§1.2(b) 는 이 절로 대체된다.** §1.1–§1.8 은 이관 원문이므로 **한 글자도 고치지 않는다**(머리말
> 규율). 그러나 §1.2(b) 의 문서종 클래스 선언은 아래 (c) 가 **명시적으로 대체**하며, 구현은 이
> 절을 따른다. §1.9 가 *역할*을 구분했다면 이 절은 *경계*를 긋는다.
>
> **발단.** 하류 논문이 반복해서 받는 질문 둘 — *"반도체 전용 아닌가(바이오로 가면?)"* 와
> *"한국 특허청 전용 아닌가(US·EP 로 가면?)"* — 에 대해 **이 계획은 답할 근거를 갖고 있지
> 않았다.** 이식성은 PLAN-001~005 어디에도 목표로도 비목표로도 적혀 있지 않았다.
> 사용자 결정으로 **목표에 넣는다**(2026-09-05).

### (a) 실패 지점은 두 곳이고, 형태가 같다

| 축 | 실패 지점 | 실측 |
|---|---|---|
| **도메인** | `ont:featureConcept` 의 range 가 **반도체 클래스 합집합**으로 못박혀 있다 | `ontology/sdkb-patent.ttl:587-589` — `Process ⊔ SubProcess ⊔ Device ⊔ Material ⊔ Skill ⊔ FailureMode ⊔ EquipmentClass`. 뒤 셋은 FMEA·전문가매칭 계열 |
| **관할** | `ont:noticeType`(`xsd:string`, *"의견제출통지서/거절결정서"*) · `ont:examinationStatus` · `ont:groundClause`(*"조-항-호"*) 가 **KR 절차·법조문을 리터럴로 고정** | `sdkb-patent.ttl:431-451` |

**둘은 같은 실패다** — 슬롯이어야 할 자리를 **열거로 굳힌 것**이다. 그러므로 **메커니즘 하나로
둘 다 푼다.**

**§1.2 는 이 시험을 통과하지 못한다.** §1.2(a) 는 새 태스크층을 *"기존 Process/SubProcess 재사용 ·
기존 Material 재사용"* 으로 **다시 반도체 클래스에 묶고**, §1.2(b) 는 KR 문서종 둘을 **T-Box 클래스로
굳히고 `owl:disjointWith` 까지 건다.** 계획대로 지으면 재구성을 완료해도 바이오·US 이식은 여전히
T-Box 수정을 요구한다. **이것은 지금만 고칠 수 있다** — TTL 이 발행되고 하류가 vendor 한 뒤에는
IRI 변경이 §0 계약 위반이다.

### (b) 저장소 안에 선례가 있다 — 발명하지 않는다

`ontology/sdkb-governance.ttl:15-18` 이 이미 적어 두었다 — *"The Korean Industrial Technology
Protection Act is in a separate module (`sdkb-governance-kr.ttl`) to keep jurisdictions
decomposable."* `gov:JurisdictionUS`·`gov:JurisdictionEU`·`gov:JurisdictionKR` 가 `skos:Concept`
로 있고 모듈이 관할별로 갈려 있다. **선행기술 축에 같은 패턴을 적용한다.**

**그리고 `RejectionType` 은 이미 개체 패턴이다** — `ont:Rejection_Novelty a ont:RejectionType ;
skos:notation "KIPO-29-1"`(`sdkb-patent.ttl:109-113`). 관할이 클래스가 아니라 **개체 속성**에
들어 있으므로, 이 부분에 한해서는 *"인스턴스만 추가"* 가 이미 성립한다. §1.2(b) 가 되돌리려는
것이 바로 그 성질이다.

### (c) 모듈 배치 — core 는 도메인 어휘 0 · 관할 어휘 0

```turtle
# ① sdkb-priorart-core.ttl  ·  https://w3id.org/sdkb/pa/   ← 신설 이름공간
pa:TechnicalConcept     a owl:Class .        # 도메인 슬롯 — 하위를 여기서 선언하지 않는다
pa:LegalGround          a owl:Class .        # 관할 슬롯 — ont:RejectionType 의 중립화
pa:ExaminationDocument  a owl:Class .
pa:ExaminationDocumentType a owl:Class .
pa:documentRole   → { pa:FirstAction, pa:SubsequentAction, pa:FinalAction }   # 절차 역할은 중립
pa:citationStatus → { pa:Provisional, pa:Maintained, pa:Withdrawn }           # 이미 중립(아래 (d))
pa:featureConcept rdfs:range pa:TechnicalConcept .    # ← union 이 아니다. 도메인 축의 답
pa:onGround       rdfs:range pa:LegalGround .         # ← 관할 축의 답
pa:ClaimProfile · pa:Disclosure · pa:coveredBy · pa:uncoveredConcept

# ② sdkb-priorart-semi.ttl — 도메인 바인딩 (기존 파일은 한 줄도 고치지 않는다)
semi:StructuralElement rdfs:subClassOf pa:TechnicalConcept .
ont:Process            rdfs:subClassOf pa:TechnicalConcept .   # 기존 클래스를 여기서 끌어온다

# ③ sdkb-priorart-kr.ttl — 관할 바인딩
kr:Ground_29_1     a pa:LegalGround ; skos:notation "KIPO-29-1" .
kr:NoticeOfReasons a pa:ExaminationDocumentType ; pa:documentRole pa:FirstAction .
kr:FinalRejection  a pa:ExaminationDocumentType ; pa:documentRole pa:FinalAction .
kr:NoticeOfReasons owl:differentFrom kr:FinalRejection .   # §1.2(b) 의 disjointWith 가 내려온 자리

# → 바이오는 ②만, US 는 ③만 새로 쓴다. ① 은 두 경우 모두 **0줄**.
```

**§1.2(b) 의 `ont:NotificationOfReasons`·`ont:FinalRejectionDecision` 클래스 선언과 그 사이의
`owl:disjointWith` 는 채택하지 않는다.** US 는 non-final/final Office Action, EP 는 Art.94(3)
communication 으로 **절차 구조·개수·배타 관계가 다르다.** 클래스로 굳히면 US 이식이 클래스 신설과
공리 수정을 요구한다. 문서종은 **`pa:documentRole` 을 갖는 개체**로 두고, 배타성은 관할 모듈에서
말한다. §1.2(b) 의 나머지(`examRound`·`issuedDate`·`ClaimVersion`·`citationStatus` 확장)는
**그대로 살아 있다.**

### (d) 설계에서 이미 관할 중립인 축 하나 — 그 사실을 명시한다

`citationStatus ∈ {Provisional, Maintained, Withdrawn}` 는 **문서종의 이름이 아니라 문서 계열의
시간순에서 파생된다**(§1.2(b) · `derive_citation_status.py`). 그러므로 *"먼저 온 문서 / 나중
문서에서 생존 / 소멸"* 은 KR·US·EP 에서 그대로 성립한다. **PLAN-001 은 의도치 않게 관할 중립적인
축을 이미 갖고 있었고**, §1.2(b) 의 KR 문서종 클래스가 그것을 가리고 있었다.

### (e) `pa:underJurisdiction` — MinedAxiom 의 **필수** provenance (2026-09-05 승인)

§1.2(c) 의 provenance 블록에 한 줄을 더한다.

```turtle
ont:substitutableWith_sio2_sion a pa:MinedAxiom ;
    ont:axiomConfidence "confirmed" ; ont:supportCount 7 ; ont:counterCount 1 ;
    prov:wasDerivedFrom <reason_id...> ;
    pa:underJurisdiction gov:JurisdictionKR .   # ← 필수. 없으면 SHACL 위반
```

**왜 필수인가.** `combinableWith` 의 의미가 관할별로 다르다 — KR 의 결합 용이성과 US §103 의
KSR/TSM motivation-to-combine 은 같은 판단이 아니다. 관할 표기 없이 두 출처의 공리를 한 그래프에
넣으면 *"KR 심사관이 치환 가능하다고 본 것"* 과 *"US 심사관이 자명하다고 본 것"* 이 같은 추론
경로에 섞이며, 이는 §1-3(이름이 의미와 다른 필드 금지)이 막는 종류의 오염이다.
**관할 혼합 추론은 금지하며, 그 금지의 기계적 근거가 이 술어다.**

### (f) 무엇이 이식되고 무엇이 이식되지 않는가 — 네 층

| 층 | 바이오 이식 | US 이식 |
|---|---|---|
| **L1 판단·절차층**(`pa:`) | **0줄** | **0줄** |
| **L2 슬롯 바인딩** | 개념 스킴 교체(②) | 법조문·문서종 개체 추가(③) — **싸다** |
| **L3 채굴 공리** | 공리는 이식 불가 · **채굴기는 그대로 돈다**(KIPRIS 서식 동일) | **파서 전량 재작성**(USPTO 서식·인용 지시 문법이 다름) · 법리도 다름((e)) |
| **L4 인스턴스** | 추가 | 추가 |

**그러므로 방어하는 명제는 *"인스턴스만 추가하면 된다"* 가 아니다** — 그 명제는 마쿠쉬 구조·서열
목록·의약용도로 즉시 반례가 나온다. 방어하는 명제는 **"L1 0줄 변경 · L2 슬롯 교체 · L3 같은
생성기 재실행 · L4 인스턴스 추가"** 이며, **이식되는 것은 공리가 아니라 공리를 만드는 방법이다.**

**검증은 PLAN-005 §5 V6 이 진다** — 도메인은 실물 이식(V6a)으로 실증하고, 관할은 종이 이식(V6b)과
CI 불변식으로 설계 보증한다. **US 문헌 회수 성능은 재지 않으며 그렇게 적는다**(§1-4).
