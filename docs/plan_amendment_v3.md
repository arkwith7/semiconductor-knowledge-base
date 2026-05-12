# 현업프로젝트1 계획서 변경 보고 (Plan Amendment v3)

| 항목 | 내용 |
|---|---|
| 원 계획서 | `현업프로젝트_계획서_박형식.pdf` (서명 2026-03-23) |
| 선행 amendment | [v1](plan_amendment_v1.md) — 정렬 트랙 4모듈 / [v2](plan_amendment_v2.md) — SIRP 통합 + AFCP-EM 이중 응용 |
| 신청자 | 박형식 (박사 19기, 2025730080) |
| 지도교수 | 신준석 교수 |
| 변경 분류 | **사전 자기 작업물(Park 2026a, ExpDataSet v3.3.5) 정렬·통합** |
| 작성일 | 2026-05-12 |
| 상태 | Draft — 지도교수 확인 대기 |

---

## A. 변경 사유

### A-1. 사전 자기 작업물의 발견
신청자의 사전 작업물 `kukkukpool/ExpDataSet v3.3.5` (이하 *Park 2026a*)가 본 학기 작업과 **동일 시스템(AFCP-EM)·동일 산출물 5종**을 다루는 완성형 사전 연구임이 확인되었다. V3.3.5 학술 논문, Formal Verification(completeness=1.0, soundness=0.711), Online Ablation(10 method), KGE 학습(3,314 triples, TransE/RotatE)까지 갖춰져 있다.

### A-2. 직접 재구축의 비효율
본 학기 amendment v2는 이미 SIRP examiner-grounded 7,500 pairs를 새로 만들었으므로 산출물 ④의 핵심은 확보 상태다. 합성 100 전문가, 합성 3-rater 7,500 ratings, KR/US 거버넌스 마스터를 본 학기에 다시 만드는 것은 시간 낭비이며 학술적 신규성도 없다.

### A-3. 새로운 학술 기여의 가능성
Park 2026a의 **합성 3-rater 라벨**과 본 학기의 **examiner-grounded 라벨**을 비교 분석하면, V3.3.5에서 다루지 못한 외부 타당성(external validity) 검증이 본 학기의 새 contribution이 된다. 측정된 합성-rater 일치도(Fleiss κ = 0.258, ICC(2,1) = 0.552)는 합성 라벨러의 noise floor를 정량화하는 출판 가치 있는 결과다.

---

## B. Before / After (v2 통합안 → v3 통합안)

| 항목 | v2 통합안 (Amendment v2) | v3 통합안 (현재) |
|---|---|---|
| ② 전문가 100 | 본 학기 `gen_experts.py` 합성 (1 트랙) | **2 트랙**: 본 학기 합성 + Park 2026a 큐레이션 100 (병렬 보존) |
| ④ 7,500 GT | SIRP examiner-grounded 7,500 pairs | **2 트랙**: SIRP examiner-grounded + Park 2026a 합성 3-rater (병렬 비교) |
| 거버넌스 | sdkb-governance{,-kr}.ttl 스키마만 | + KR 12 + US 8 = 20 인스턴스 (205 triples) |
| 컴플라이언스 시나리오 | 본 학기 25 adversarial | + Park 2026a S1~S6 34 시나리오 (reference) |
| Leakage 프로토콜 | `docs/leakage_protocol.md` 정의 | + Park 2026a L1~L4 실 사례 4건 |
| 학술 chapter | "examiner-grounded prior-art for AFCP-EM-PriorArt" | + **"synthetic 3-rater vs examiner-grounded: a comparative study"** (notebook 05) |
| 평가 지표 | MRR/NDCG@5/Recall@K/leakage_rate | 동일 + κ/ICC (curated 트랙 한정) |

---

## C. 변경 결과

### C-1. 채점 5개 산출물의 동시 충족
| # | 산출물 | v3 충족 |
|---|---|---|
| ① | SDKB 198/264 | v0.3 (이번 학기 dedup + vendor:semes + 4 OBSERVED_IN); v0.2 도 reference |
| ② | 전문가 100 | 합성 100 + 큐레이션 100 = 200 사용 가능 |
| ③ | 문제 50 + 시나리오 25 | SIRP 거절특허 50 + 본 학기 25 + (옵션) Park 2026a 34 |
| ④ | 7,500 ratings | examiner-grounded 7,500 + 큐레이션 합성 7,800 = 두 라벨 트랙 |
| ⑤ | 사업화 전략 v1 | `commercialization_strategy_v1.md` + V3.3.5 §5-§7 인용 |

### C-2. 추가 7가지 보강
| 보강 | 위치 |
|---|---|
| KR 거버넌스 인스턴스 12건 | `ontology/sdkb-governance-kr-instances.ttl` 132 triples |
| US 거버넌스 인스턴스 8건 | `ontology/sdkb-governance-us-instances.ttl` 73 triples |
| 거버넌스 flat 테이블 | `data/compliance/technology_controls.parquet` 20 rows |
| 큐레이션 전문가 110명 | `data/experts/curated_profiles.parquet` |
| 3-rater 합성 7,800 ratings | `data/experts/curated_ratings.parquet` |
| Reliability report (κ/ICC) | `data/experts/reliability_report.md` |
| Synthetic vs Examiner 비교 노트북 | `notebooks/05_synthetic_vs_curated_comparison.ipynb` |
| 정렬 회계 문서 | `docs/expdataset_alignment.md` |

### C-3. 학기 채점 친화적 인용 형식
모든 ExpDataSet 출처 자산에 `[Park 2026a]` 인용 부착 (`scripts/seed_compliance_governance.py:67-69` 등). 본 학기 net-new contribution 5종은 `docs/expdataset_alignment.md §2`에 명시.

---

## D. 위험·완화

| 위험 | 완화 |
|---|---|
| "본 학기 contribution이 무엇이냐"는 채점 질문 | `expdataset_alignment.md §2` 5종 + §5 책임 회계 표로 즉답 가능 |
| 큐레이션 데이터의 5명 실명 PDF 처리 (`PDF/experts/{김영수,박지현,…}_경력기술서.pdf`) | 본 SDKB에 미복제 (ExpDataSet 원본에만 잔존). 학위논문 출판 전 실명/합성 여부 확정 후 처리 |
| 라이선스 | 본인 작업물 → CDLA-Permissive-2.0 우산 아래로 가져옴 |
| 7,500 ratings 두 출처 혼동 | `curated_ratings.parquet`(synthetic), `prior_art_pairs.parquet`(examiner)로 파일명 분리. notebook 05가 이 분리를 학술적으로 정당화 |

---

## E. 지도교수 확인란

본 amendment v3의 사유·범위·결과에 동의하며 2026-1학기 산출물 평가 기준을 v3로 갱신한다. v1·v2 정렬 트랙과 SIRP 통합은 본 amendment에 승계된다.

지도교수: 신 준 석 (서명) __________________________  일자 __________________________
