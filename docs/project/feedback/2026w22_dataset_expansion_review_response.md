# 데이터셋 확장 검토의견 — 대응 방안 (2026 W22)

> **CONFIDENTIAL — lab-internal.** docs/feedback/ 는 익명 스냅샷 일괄 제외.
> 성격: 외부 검토자(KIPRIS 기반 대체 데이터셋 4종 제안)에 대한 **분석·대응 방안**.
> 현 학기(2026-1) 서명·승인 산출물은 **재오픈 없음** — 본 제안은 [[project_roadmap_commercialization]]
> **Stage 2(2026-2) 확장 로드맵**으로 귀속한다.

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-05-29 |
| 검토 출처 | 외부 검토의견 — "SIRP 1,000 확장 대신 KIPRIS 최신·생태계 데이터 4종 제안" |
| 현 상태 | 지도교수 승인 完(2026-1 5대 산출물 잠금) · 결과보고서 W3(6/1-7) 최종화 중 |
| 결론 | 4종 제안 모두 **채택 가치 있음**, 단 **2026-2 Stage-2 확장**으로 편성. 현 학기 범위 불변 |
| 관련 문서 | [project_status_2026_1.md](../project_status_2026_1.md) · [prior_art_ontology_gap_and_data_plan.md](../prior_art_ontology_gap_and_data_plan.md) · [plan_amendment_v3.md](../plan_amendment_v3.md) |

---

## 0. 한 줄 입장

> 검토의견의 **방향(거절특허 단일 소스 → 최신성·생태계 관계 데이터로 확장)에 전적으로 동의**한다.
> 4종 제안의 연결점(hook)은 이미 SDKB 스키마에 다수 잠들어 있어 정합성이 높다.
> 다만 현 학기 산출물은 승인 완료·잠금 상태이므로, 본 제안은 **2026-2 Stage-2의 신규 데이터 축**으로
> 편성하고, 그중 **공수 대비 효과가 가장 좋은 P4(융합기술)와 검토자 추천 P2(공동출원/인용)를 선두**로 둔다.

---

## 1. 사실 정합 — 검토 전제의 부분 보정 (반박 아님)

검토의견의 전제 일부는 현 저장소 실측과 약간 어긋나므로, 대응의 출발점으로 정정한다.
이는 검토자 지적을 약화시키는 게 아니라, **"무엇을 더 할지"의 기준선**을 맞추기 위함이다.

| 검토 전제 | 저장소 실측 | 함의 |
|---|---|---|
| "1,000건 스냅샷" | jsonl **1,000 레코드** 확정 (카드의 "773"은 초기 코호트 스냅샷) | 규모는 이미 1,000 |
| "확장이 물리적으로 어렵다" | **거절특허 소스 자체**는 매몰 코호트가 맞음 (수집 종료 2026-05-06) | ✅ 동의 — 소스 피벗이 정답 |
| "20년 전 데이터까지 소급" | 수집 기간 2026-04~05, KIPRIS Plus 기반 비교적 최신 | 최신성 보강 여지는 *생태계 축*에서 더 큼 |
| (암묵) GT 가치 미입증 우려 | examiner 인용 본문 코퍼스 **2,926건 수집**, 실 examiner-GT 평가 **완료**([gap doc §8](../prior_art_ontology_gap_and_data_plan.md)) | **Ground Truth 가치는 이미 데이터로 입증** |

**핵심**: SIRP는 "정답(GT) 자산"으로서 역할을 이미 다했다(검토자도 인정). 다음 과제는 *같은 소스를 키우는 것*이
아니라 **최신성·기업간 관계라는 새 축을 여는 것** — 이 점에서 검토의견과 완전히 일치한다.

---

## 2. 온톨로지 hook 검증 — 제안별 "이미 있는 것 / 신규 필요"

4종 제안을 실제 TTL 스키마에 대조한 결과. **검토의견이 명시한 `sdkb:coApplicant`·`sdkb:interFirmCitation`는
현재 미존재(신규 추가 필요)**이나, 더 자연스러운 기존 hook들이 이미 있다.

| 제안 | 이미 존재하는 hook | 신규 필요 | 정합도 |
|---|---|---|---|
| **P1 국가핵심기술·국가R&D** | `gov:NationalCoreTechnology` · `gov:NCTField` · `gov:designatedAsNCT` · `gov:requiresGovApproval` (sdkb-governance-kr.ttl) · `ont:Firm`·`ont:holdsResource` (rbv) | `ont:fundedByMinistry` · `ont:nationalRnDProjectId` 데이터속성, R&D성과물→Firm자산 엣지 | ★★★★☆ (거버넌스 모듈 직접 활성) |
| **P2 대기업↔소부장 공동출원/인용** | `ont:assignedTo`(출원인) · `ont:cites` · `ont:hasPriorArtApplicant` (sdkb-patent.ttl) | `ont:coApplicant`(또는 다중 assignedTo 규약) · `ont:interFirmCitation` (검토자 제안 그대로, **신규**) | ★★★★★ (SDKB-Match 정체성 직결) |
| **P3 심판·분쟁(무효/권리범위/정정)** | `ont:RejectionReason`·`ont:rejectedFor` · core FMEA(FailureMode/RootCause/Mitigation) | `ont:Trial`·`ont:trialType`·`ont:trialOutcome`·`ont:correctionHistory` (**신규 클래스군**) + 별도 소스(특허심판원 IPT) | ★★★☆☆ (리스크 모듈 신설 필요) |
| **P4 IPC/CPC 융합기술 공출원** | `ont:hasIPC`·`ont:hasCPC` (sdkb-patent.ttl) · `ont:Signal`·`ont:signalsFactor`·`ont:Scenario` (sdkb-foresight.ttl, 스키마만) | `ont:coClassifiedWith`(융합 엣지) · convergence Signal 인스턴스 | ★★★★☆ (foresight 모듈+노트북02 활성) |

> 결론: P1·P4는 **스키마는 있으나 인스턴스가 비어있는 dormant 모듈(governance-kr, foresight)을 깨우는**
> 고레버리지 작업이고, P2는 SDKB-Match 정체성에 가장 직결되나 신규 술어 2개가 필요하다.
> P3는 별도 데이터 소스(심판원)와 신규 클래스군이 필요해 공수가 가장 크다.

---

## 3. 제안별 대응 방안 (공수·효과·신규 부담)

### P1 — 국가핵심기술 / 국가 R&D 연계 특허
- **수집**: KIPRIS 검색에서 `정부부처명`/`국가연구개발과제번호` 필드 매칭 반도체 특허 필터(최근 3~5년).
- **공수**: 中(필드 필터는 쉬우나 과제번호↔성과물 정합·기업 disambiguation 필요).
- **온톨로지 보강**: `gov:designatedAsNCT`로 국가핵심기술 지표 연결 + R&D 성과물 노드를 `ont:Firm holdsResource`로
  연결 → 정부과제 기반 기술역량 추론. **governance-kr 모듈(현재 controls만)에 첫 NCT 인스턴스 투입.**
- **현 학기 제외 사유**: 신규 수집·신규 데이터속성 2개 → 승인된 산출물 외. **2026-2 편성.**

### P2 — 대기업 ↔ 소부장 공동출원/인용 네트워크 (검토자 1순위)
- **수집**: 출원인에 삼성전자/SK하이닉스 + 소부장 중소기업 공동출원, 또는 소부장 특허의 대기업 선행특허 인용.
- **공수**: 中(데이터 자체는 KIPRIS로 확보 가능, **관계 추출·기업 명칭 정규화**가 본체).
- **온톨로지 보강**: **신규** `ont:coApplicant`·`ont:interFirmCitation` 추가 → 공급망 협력관계 그래프.
  SDKB-Match 추천 신뢰도의 직접 입력(숨은 대안 기업·전문가 탐색).
- **전략적 위치**: 저장소 핵심 정체성(SDKB-Match)에 가장 자연스럽게 융합 → **2026-2 Stage-2의 flagship 후보.**
  단, "거절 없이 협력관계 입증"이라는 검토자 논지는 SDKB-Match의 *근거 데이터*로 가장 강력.

### P3 — 심판·분쟁(무효/권리범위확인/정정) 데이터
- **수집**: KIPRIS + 특허심판원(IPT) — 심판 청구 리스트·결과(인용/기각)·정정공고 청구항 변동 이력. **별도 소스.**
- **공수**: 大(별도 API/크롤 소스 + 신규 클래스군 `ont:Trial` 등 + 무효사유 텍스트마이닝→FMEA 매핑).
- **온톨로지 보강**: 분쟁 빈발 특허의 무효사유 → core FMEA 결함/위험 클래스 매핑 → 출원 전 특허장벽(Clearance) 분석.
- **위치**: SIRP의 "리스크" 관점을 *시장 단계*로 확장하는 고부가 데이터이나 공수 최대 → **2026-2 후반 또는 Stage-3.**

### P4 — IPC/CPC 융합기술 공출원 (공수 대비 최고 효율)
- **수집**: H01L(반도체) + G06N/G06F(AI) 또는 H10N(양자) **동시 부여** 특허. **분류코드 매칭만으로 가능 = 최저 수집비용.**
- **공수**: 小(분류코드 교집합 질의), 검토자도 "데이터 확보 매우 쉬움" 명시.
- **온톨로지 보강**: `ont:coClassifiedWith` 융합 엣지 + `sdkb-foresight.ttl`의 `ont:Signal`/`ont:Scenario`
  인스턴스화 → 이종기술 결합 패턴 추론. **현재 stub 상태인 [notebooks/02_patent_opportunity_demo.ipynb](../../notebooks/02_patent_opportunity_demo.ipynb)
  (기술기회 발견/Foresight) 라인을 실제로 활성화.**
- **학술 정합**: 신 교수 4-pillar/STEEPVE Foresight 트랙([research_alignment.md](../research_alignment.md))의 직접 입력 →
  박사논문 seed·목표저널(IP&M/Scientometrics) 어젠다와 연결.

---

## 4. 권고 우선순위 — 검토의견과의 차이점 명시

검토자는 **P2 우선**을 권고했다. 본 대응은 **부분 동의 + 보완**한다:

| 우선 | 제안 | 근거 | 시점 |
|---|---|---|---|
| **1차(파일럿)** | **P4 융합기술** | 수집비용 최저(분류코드 매칭) + dormant foresight 모듈·노트북02 활성 + 신 교수 학술 트랙 직결 → **가장 빨리 "동작하는 확장"을 증빙** | 2026-2 초 |
| **2차(flagship)** | **P2 공동출원/인용** | SDKB-Match 정체성 직결·검토자 1순위. 단 신규 술어 2개+관계추출 필요 → 파일럿 후 본격 | 2026-2 |
| 3차 | **P1 국가핵심기술/R&D** | governance-kr NCT 모듈 활성·정책 스토리 강력, 필드 필터로 비교적 용이 | 2026-2 |
| 4차 | **P3 심판·분쟁** | 부가가치 최고이나 별도 소스+신규 클래스군으로 공수 최대 | 2026-2 후반~Stage-3 |

**차이의 이유**: 검토자의 P2 우선은 *전략적 가치* 기준으로 타당하다. 다만 P2는 신규 술어·관계추출이라는
*착수 마찰*이 있다. 따라서 **"가장 값싸고 빠른 가시적 성과(P4)로 확장 가설을 먼저 검증"**한 뒤 **P2를 flagship으로
본격화**하는 순서가, 2026-2 초반 모멘텀과 검토자 의도를 동시에 만족한다. (P2를 1차로 바로 가도 무방 — 두 안 모두 제시.)

---

## 5. 현 학기(2026-1) 가드레일

- 본 4종은 **승인 완료된 5대 산출물(온톨로지·전문가100·문제50+규제25·GT7,500·사업화v1)에 포함되지 않는다.**
- 결과보고서 W3 제출물은 **현 범위로 최종화**한다. 4종은 보고서 **5장 "한계 및 후속 연구 / 확장 로드맵"** 절에
  *2026-2 데이터 확장 축*으로 1~2단락 명시(신규 작업 부담 없음, 서술만).
- 본 문서는 [project_status_2026_1.md](../project_status_2026_1.md) §10(후속 정리 항목, 비채점) 및
  [[project_roadmap_commercialization]] Stage 2에 1줄 포인터로 연결.

---

## 6. 다음 액션 (승인 시)

1. (문서) 보고서 5장 "확장 로드맵" 단락에 4종 요약 반영 — *현 학기 내, 서술만.*
2. (2026-2 착수) P4 파일럿 스펙: IPC/CPC 교집합 질의 + `ont:coClassifiedWith` 스키마 추가 + 노트북02 1셀 데모.
3. (2026-2) P2 스펙: `ont:coApplicant`/`ont:interFirmCitation` 술어 설계 + 기업명 정규화 파이프라인.
4. 신 교수 §D-2 미팅 결정항목에 **"2026-2 데이터 확장 축 채택 여부"** 1건 추가 송부.

---

## 7. 보고서 5장 삽입용 초안 (붙여넣기 블록)

> 결과보고서(.docx) **5장 "성과 및 기대효과 / 한계 및 후속 연구"** 의 *데이터 확장 로드맵* 절에
> 그대로 붙여넣을 수 있는 1~2단락 초안. **현 학기 신규 작업 아님 — 후속 계획 서술.**

---

**(초안) 데이터 확장 로드맵 — 2026-2 (Stage 2)**

본 학기 1차 실데이터인 SIRP(반도체 거절특허 1,000건, examiner-grounded 7,500 pairs)는 선행기술조사의
정답(Ground Truth) 자산으로서 역할을 입증하였다. 거절특허는 *과거의 심사 실패*를 보여주는 매몰 코호트이므로,
후속 학기에는 동일 소스의 확대가 아니라 **최신성과 기업간 생태계 관계를 보강하는 4개 데이터 축**으로 확장한다.
(i) **IPC/CPC 융합기술 공출원**(H01L×G06N/H10N) — 분류코드 교집합만으로 확보 가능한 최저비용 데이터로,
`sdkb-foresight` 모듈의 신호·시나리오 노드를 활성화하여 기술기회 발견(Foresight) 라인을 구동한다.
(ii) **대기업↔소부장 공동출원·인용 네트워크** — `coApplicant`·`interFirmCitation` 관계를 신설하여
SDKB-Match의 공급망 협력관계 추론 신뢰도를 강화한다. (iii) **국가핵심기술·국가 R&D 연계 특허** —
`sdkb-governance-kr`의 국가핵심기술(NCT) 노드를 인스턴스화하여 정부과제 기반 기술역량을 추론한다.
(iv) **특허심판·분쟁(무효/권리범위/정정) 데이터** — 시장 단계의 "살아있는 리스크"를 FMEA 결함·위험 클래스에
매핑하여 출원 전 특허장벽(Clearance) 분석 기반을 마련한다. 이들은 모두 현재 스키마에 정의되었으나
인스턴스가 비어 있는 거버넌스·Foresight·RBV 모듈을 깨우는 작업이며, 2026-2 Stage 2의 알고리즘
고도화(SDKB-Match)와 병행하여 본 데이터셋의 최신성·실무 적용성을 높인다.

---

## 부록 — 검토자 표기 vs 실제 스키마 식별자

| 검토자 표기 | 실제(권고) | 상태 |
|---|---|---|
| `sdkb:coApplicant` | `ont:coApplicant` (신규) 또는 다중 `ont:assignedTo` | 미존재 → P2에서 신설 |
| `sdkb:interFirmCitation` | `ont:interFirmCitation` (신규) | 미존재 → P2에서 신설 |
| `sdkb-governance-kr.ttl` | ✅ 존재 (`gov:NationalCoreTechnology` 등) | P1 hook |
| `sdkb-rbv.ttl` | ✅ 존재 (`ont:Firm`/`ont:holdsResource`) | P1·P2 자산 연결 |
| `sdkb-foresight.ttl` | ✅ 존재 (`ont:Signal`/`ont:Scenario`, 스키마만) | P4 hook |
| `sdkb-core.ttl` FMEA | ✅ 존재 (FailureMode 등) | P3 hook |
