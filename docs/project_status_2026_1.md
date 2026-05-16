# Hyeonup-Project 2026-1 — Internal Status

> **Audience.** Lab-internal (advisor / graders / project owner).
> This document tracks SDKB v1.0 against the signed 2026-1 plan and its amendments.
> Public-facing usage of SDKB lives in [../README.md](../README.md) (English) / [../README.ko.md](../README.ko.md) (한국어).

- **Plan owner.** Park HyoungSik (Ph.D. 19기)
- **Advisor.** Prof. Juneseuk Shin — Quantitative Technology Management Lab, SKKU GSMOT
- **Amendment trail.** [v1](plan_amendment_v1.md) → [v2](plan_amendment_v2.md) → [v3](plan_amendment_v3.md) · architecture: [active ADR](architecture_amendment_sdkb_centric.md)
- **Last verified release.** baseline 198 nodes / 268 edges · SIRP 773 patents · 46/46 tests + SHACL pass

## 1. 메인 트랙 — 계획서 채점 항목

| # | 산출물 | 수량 요건 | 상태 | 경로 |
|---|---|---|---|---|
| ① | SDKB 온톨로지 | ≥198 노드 / ≥264 간선, 14 타입 | ✅ Baseline 충족 | [../data/semiconductor_v0_3.json](../data/semiconductor_v0_3.json) |
| ② | 합성 전문가 프로필 | 100명, 비식별, 도메인 자문 | ✅ **Dual track**: 합성 100 + 큐레이션 110 | `../data/expert_profiles.parquet` (합성) + `../data/experts/curated_profiles.parquet` (큐레이션) |
| ③ | 기술 문제 + 규제 시나리오 | 50 + 25 (적대적 포함, 다중 관할) | ✅ | 거절특허 50 + 거절사유 패턴 25 → `../data/problems.parquet`, `../data/regulatory_scenarios.parquet` |
| ④ | 정답 평가체계 | 7,500 ratings | ✅ **Dual GT**: examiner 7,500 + 합성 3-rater 7,800 | `../data/patents/prior_art_pairs.parquet` (examiner) + `../data/experts/curated_ratings.parquet` (3-rater κ/ICC). MRR/NDCG@5/Recall@K + κ=0.258, ICC=0.552 |
| ⑤ | 기술사업화 전략 v1 | 시장·고객·BM·경쟁 + 자원·가치·규제 + IP-R&D | ⏳ Skeleton — W6 결선 (ARKWITH IPBridge 적용 가설 §10 추가, v3 §C-1) | [commercialization_strategy_v1.md](commercialization_strategy_v1.md) |

## 2. 정렬 트랙 — 신 교수 4-pillar 방향

상세 매핑: [research_alignment.md](research_alignment.md).

| 모듈 | 목적 | 상태 | 경로 |
|---|---|---|---|
| `sdkb-patent.ttl` | Patent / CPC / IPC / F-term / Topic / Novelty / RejectionReason / hasPriorArt | ⬜ Pending | `../ontology/sdkb-patent.ttl` |
| `sdkb-rbv.ttl` | Firm / Resource / Capability / EntryBarrier | ⬜ Pending | `../ontology/sdkb-rbv.ttl` |
| `sdkb-commercialization.ttl` | TRL / License / Spinoff / IPTransaction | ⬜ Pending | `../ontology/sdkb-commercialization.ttl` |
| `sdkb-foresight.ttl` | Scenario / STEEPVE / RealOption | ⬜ Pending | `../ontology/sdkb-foresight.ttl` |
| `sdkb-governance-kr.ttl` | 한국 산업기술보호법 (다중 관할 명시화) | ⬜ Pending | `../ontology/sdkb-governance-kr.ttl` |

## 3. 1차 실 데이터 — SIRP 거절특허 773건 ⭐

| 항목 | 값 |
|---|---|
| 파일 | [../data/patents/raw/semiconductor_industry_rejected_patents.jsonl](../data/patents/raw/semiconductor_industry_rejected_patents.jsonl) |
| 규모 | **773 거절특허 + 2,731 GT 인용 선행기술 + examiner-cited 1,961 (mean 2.54/특허)** |
| 출처 | KIPRIS Plus API + KIPRIS 웹 (KIPO) |
| 코호트 | `semiconductor_ontology_rejected_patents` 431 / `semiconductor_fullstack_rejected_patents` 342 |
| 데이터 카드 | [dataset_rejected_patents_card.md](dataset_rejected_patents_card.md) |
| 라이선스 | KIPRIS Plus API 약관 — 학교 자문 후 조정 |

## 4. 큐레이션 ExpDataSet 통합 (외부 자산 흡수) ⭐

정렬 회계 (net-new contributions 5종 명시) — 별도 lab-internal 문서로 관리.

| 자산 | 통합 위치 | 규모 |
|---|---|---|
| KR 거버넌스 마스터 (산업기술보호법 §33/§34) | `../data/compliance/kr_standards_v1.json` + `../ontology/sdkb-governance-kr-instances.ttl` | 12 controls, 132 triples |
| US 거버넌스 마스터 (EAR/CCL + Deemed Export) | `../data/compliance/us_standards_v1.json` + `../ontology/sdkb-governance-us-instances.ttl` | 8 controls, 73 triples |
| 큐레이션 전문가 풀 (KR + EN) | `../data/experts/curated_profiles.parquet` | 110 profiles, 103 columns |
| 3-rater synthetic ratings | `../data/experts/curated_ratings.parquet` + `curated_ratings_pivot.parquet` | 7,800 ratings · 2,600 pivot subjects · Fleiss κ=0.258, ICC(2,1)=0.552 |
| Compliance scenarios S1~S6 | `../data/compliance/scenarios_v1.json` | 34 scenarios |
| Leakage incidents L1~L4 | `../data/compliance/leakage_incidents_v1.json` | 4 cases |
| SME problems (external reference) | `../data/problems_external/sme_problems_v1.json` | 201 problems |

## 5. Plan reference

Signed plan PDF (현업프로젝트1 계획서) — see lab project memory.

## 6. Verified release figures (baseline)

- 베이스라인 **198 노드 / 268 엣지** (deliverable ①, v0.3)
- SIRP 773 patents · 3,118 IPC 링크 · 4,696 prior-art 엣지
- 7,500 examiner-grounded pairs (positive 2,723 + hard-neg 2,723 + easy-neg 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts = **dual-track pool**
- 7,500 examiner + 7,800 3-rater synthetic = **dual-track GT** (κ=0.258, ICC=0.552)
- KR+US governance: 20 controls, 205 RDF triples
- **46/46 tests pass + ✓ SHACL VALIDATION PASSED**

## 7. 현업프로젝트 결과보고서(5장) framing — v3 합의 ⭐

[Amendment v3 §C-2](plan_amendment_v3.md) 매핑 표를 그대로 인용. 참여기업·외부 참여자·기업수요는 v3 §A-2.

- **참여기업**: 주식회사 아크위드(ARKWITH) — 학생소속기업
- **외부 참여자**: Bespin Global · POSCO DX · KUKKUK 팀(김범수 FST 부사장 외)
- **기업수요 반영여부**: 기획 시 ☑ — IPBridge 사업 문제 4건(plasma sub-domain 정체 / 청구항 의미 매칭 한계 / 정성 매칭 / 사후 필터 컴플라이언스)이 SDKB 큐레이션 기획에 직접 반영

각 장의 산출물 매핑 (v3 §C-2 발췌):

| 보고서 장 | 본 프로젝트 산출물 |
|---|---|
| 1장 문제와 기업 현황 | ARKWITH 사업 개요 + IPBridge v0 측정 (B=0.324 / C=0.838) + 4가지 기업 문제 |
| 2장 기존 방법 | IPBridge v0 (BM25+LLM+도메인 팩) + 학계 부분 ontology |
| 3장 신규 방법 | SDKB v1.0 4-layer 아키텍처 + PROV-O + SHACL + SDKB-centric curation ([architecture_amendment_sdkb_centric.md](architecture_amendment_sdkb_centric.md)) |
| 4장 적용 결과 | UC1·UC2 SPARQL + IPBridge ↔ SDKB strata별 비교 + 품질지표 (SHACL 46/46 · κ · ICC) |
| 5장 성과 및 기대효과 | HuggingFace 공개 + GitHub Pages 시각화 + IPBridge 적용 가설 + 박사논문 seed |

SPARQL 시연 commitment:

- `examples/sparql/uc1_expert_compliance_match.rq` + `data/use_cases/uc1_result.tsv` + `tests/test_uc1_sparql.py`
- `examples/sparql/uc2_prior_art_retrieval.rq` + `data/use_cases/uc2_result.tsv` + `tests/test_uc2_sparql.py`

GitHub Pages 인터랙티브 증빙:

- `site/usecases/uc1_expert_matching.html`
- `site/usecases/uc2_prior_art.html`

빌더는 [`scripts/build_viz.py`](../scripts/build_viz.py)에 entry 2개 추가 ([`visualization_plan.md`](visualization_plan.md) Phase 2 일부를 학기 내로 앞당김).

## 8. 잔여 7주 실행 일정 (2026-05-15 → 2026-07-초)

[Amendment v3 §D](plan_amendment_v3.md) 그대로 인용. 주당 6~8시간 예산, 총 약 42시간.

| 주차 | 작업 | 산출물 |
|---|---|---|
| W1 (5/15-21) | 행정 정보 + UC1/UC2 시나리오 확정 + 골격 .docx | 골격 1p + 시나리오 메모 1p |
| W2 (5/22-28) | UC1·UC2 SPARQL 결선 + 회귀 테스트 | uc{1,2}.rq + result.tsv + test_*.py |
| W3 (5/29-6/4) | GitHub Pages use case view 추가 | site/usecases/*.html 2건 |
| W4 (6/5-11) | IPBridge v0 ↔ SDKB strata별 비교 + §4.2.4 본문 | 비교 표 + 그래프 + 본문 초안 |
| W5 (6/12-18) | 1~3장 본문 | 보고서 30~50% |
| W6 (6/19-25) | 4~5장 본문 + 부록 결선 + ⑤ 결선 | 보고서 95% |
| W7 (6/26-7/2) | SME 리뷰 + 수정 + 합격확인서 + 제출 | 최종 .docx + 합격확인서 |

SME 리뷰 채널: 김범수 FST 부사장 (W4 사전) / 이영주 POSCO DX PM (W7) — [`expert_validation_log.md`](expert_validation_log.md) 템플릿 적용.
