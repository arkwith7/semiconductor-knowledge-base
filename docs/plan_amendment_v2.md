# 현업프로젝트1 계획서 변경 보고 (Plan Amendment v2)

| 항목 | 내용 |
|---|---|
| 원 계획서 | `현업프로젝트_계획서_박형식.pdf` (서명 2026-03-23) |
| 선행 amendment | [plan_amendment_v1.md](plan_amendment_v1.md) (정렬 트랙 4모듈 추가) |
| 신청자 | 박형식 (박사 19기, 학번 2025730080) |
| 지도교수 | 신준석 교수 |
| 변경 분류 | **합성 데이터 → 실제 검증 데이터 부분 교체** + AFCP-EM 응용 확장 |
| 작성일 | 2026-05-12 |
| 상태 | Draft — 지도교수 확인 대기 |

---

## A. 변경 사유

### A-1. 실제 검증 데이터의 확보
별도 수집된 **반도체 도메인 거절 특허 773건**(`semiconductor_industry_rejected_patents.jsonl`)이 본 프로젝트 직전에 가용해졌다. 이 데이터는 IP-R&D 실습용 AI Agent 개발·평가를 위해 KIPRIS Plus API 등으로 수집된 것으로, 다음 두 특성이 본 프로젝트의 산출물 ③·④의 성격을 근본적으로 강화한다.

1. **수집 코호트 명칭 자체가 `semiconductor_ontology_rejected_patents` (431건)** — 처음부터 SDKB 통합을 염두에 둔 코호트가 절반 이상을 차지한다.
2. **각 레코드에 심사관 인용 선행기술(`ground_truth_examiner`)이 평균 2.54건, `ground_truth_all` 평균 3.53건 부착** — 합성 라벨이 아닌, 특허청 심사관(공인 도메인 전문가)이 실제로 부여한 정답이다.

학술적 위상이 합성 데이터 대비 한 단계 높다(PatentMatch, CLEF-IP와 동급의 ground-truthed prior-art benchmark).

### A-2. AFCP-EM 응용 확장의 자연적 정합
원 계획의 AFCP-EM은 "전문가 매칭" 단일 응용으로 정의되었다. 본 데이터는 **선행기술 매칭(prior-art retrieval)** 응용을 동일 아키텍처(컴플라이언스 우선) 위에서 가능케 한다. 매칭의 본질이 동일하므로(쿼리 × 후보 풀 × 다중관할 컴플라이언스 필터), AFCP-EM 알고리즘 한 세트가 두 시장을 동시에 겨냥할 수 있다 — HR/컨설팅 + IP-R&D 컨설팅.

### A-3. 평가 지표의 자연 연속화
계획서 산출물 ④의 평가가 합성 라벨 기반 weighted κ / ICC였다면, 본 데이터를 도입하면 평가 지표가 **MRR, NDCG@5, Recall@K, leakage rate** 로 자연스럽게 전환된다. 이는 계획서의 **2026-2학기 AFCP-EM 평가지표와 정확히 일치**하여 학기간 연속성을 확보한다.

---

## B. Before / After (v1 정렬안 → v2 통합안)

| 항목 | v1 정렬안 | v2 통합안 |
|---|---|---|
| 데이터 출처 | 합성 (LLM 라벨러) | **실제 거절특허 773건 + 보조 합성** |
| ② 전문가 100 | 합성 | 합성 (유지) |
| ③ 문제 50 | 합성 LLM 생성 | **거절특허 50건 층화추출** (process_family 비율 기반) |
| ③ 시나리오 25 | 합성 적대적 | **거절사유 패턴 25건** (진보성·신규성·청구범위·다중관할 충돌) |
| ④ 7,500 ratings | 합성 7,500 + 600 인간검증 | **examiner-grounded 7,500 pairs** (positive ≈3,000 + hard-negative ≈4,500) |
| 평가 지표 | weighted κ / ICC | **MRR, NDCG@5, Recall@K, leakage rate** |
| AFCP-EM 응용 | Expert 단일 | **Expert + PriorArt 이중 응용** (Agent-First Compliance Platform — Expert/PriorArt Matching) |
| sdkb-patent.ttl | 스키마 + 소규모 합성 인스턴스 | **773 실 인스턴스 + IPC/거절사유 분류 포함** |
| 사업화 전략 v1 | 7축 | 7축 + **IP-R&D 컨설팅 시장 사례** 추가 |

---

## C. 변경 결과

### C-1. 채점 핵심 5개 산출물의 충족
| # | 산출물 | v2 충족 방식 |
|---|---|---|
| ① | SDKB 198/264 | 동일, 추가로 `sdkb-patent.ttl` 노드 추가 |
| ② | 전문가 100 | 합성 유지 |
| ③ | 문제 50 + 시나리오 25 | **거절특허 50 + 거절사유 패턴 25** (실 데이터) |
| ④ | 7,500 ratings | **examiner-grounded pairs 7,500** (실 라벨) |
| ⑤ | 사업화 전략 v1 | 7축 + IP-R&D 시장 |

### C-2. AFCP-EM 리브랜드
"Agent-First Compliance Platform — Expert/PriorArt Matching" — 약칭 AFCP-EM 유지, 의미 확장.

### C-3. 데이터셋의 학술 인용성
**examiner-grounded prior-art pairs**라는 학술 표준 라벨링 — IP&M·TFSC 외에 *Scientometrics*, *World Patent Information*, *JOI* 등 IP/특허분석 저널까지 투고 후보 확대.

---

## D. 위험 및 완화

| 위험 | 완화 |
|---|---|
| KIPRIS Plus API 본문 재배포 라이선스 제약 가능 | **현 상태**: 데이터를 레포에 포함, **학기 중 학교(산학협력단/도서관) 자문 후 조정**. fallback: 본문은 `data/patents/raw/`로 격리 후 `.gitattributes`로 별도 관리, 공개 레이어는 메타+식별자+거절결정서 URL만 유지 (`sdkb-patent-linkonly.ttl`) |
| `ground_truth_evidence` 결손 756/773 | 거절결정서 PDF 재인출 + OCR/LLM 추출은 **2026-2학기 작업으로 분리** |
| 외국 특허 비율 KR 57% / JP 24% / US 14% | 다국가 메타데이터는 EPO OPS / USPTO PEDS로 후속 학기 보강 |
| 날짜 포맷 이상치 (예: `20260430` 8자리) | ingest 단계 정규화 (`2026.04.30`) |
| 거절특허 50건 추출 시 process_family 편향 | 층화추출 + 가중 균형 (etch 15 / depo 9 / metal 5 / general 3 / oxide 3 / photo 3 / memory 3 / implant 3 / materials 2 / packaging 2 / 기타 2) |

---

## E. 지도교수 확인란

본 amendment v2의 사유·범위·결과에 동의하며 2026-1학기 산출물 평가 기준을 v2로 최종 갱신한다. v1 정렬 트랙은 본 amendment에 포함·승계된다.

지도교수: 신 준 석 (서명) __________________________  일자 __________________________
