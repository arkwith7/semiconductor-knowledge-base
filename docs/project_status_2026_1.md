# Hyeonup-Project 2026-1 — Internal Status

> **Audience.** Lab-internal (advisor / graders / project owner).
> This document tracks SDKB v1.0 against the signed 2026-1 plan and its amendments.
> Public-facing usage of SDKB lives in [../README.md](../README.md) (English) / [../README.ko.md](../README.ko.md) (한국어).

- **Plan owner.** Park HyoungSik (Ph.D. 19기)
- **Advisor.** Prof. Juneseuk Shin — Quantitative Technology Management Lab, SKKU GSMOT
- **Amendment trail.** [v1](plan_amendment_v1.md) → [v2](plan_amendment_v2.md) → v3 (lab-internal) · architecture: [active ADR](architecture_amendment_sdkb_centric.md)
- **Last verified release.** baseline 198 nodes / 268 edges · SIRP 773 patents · 46/46 tests + SHACL pass

## 1. 메인 트랙 — 계획서 채점 항목

| # | 산출물 | 수량 요건 | 상태 | 경로 |
|---|---|---|---|---|
| ① | SDKB 온톨로지 | ≥198 노드 / ≥264 간선, 14 타입 | ✅ Baseline 충족 | [../data/semiconductor_v0_3.json](../data/semiconductor_v0_3.json) |
| ② | 합성 전문가 프로필 | 100명, 비식별, 도메인 자문 | ✅ **Dual track**: 합성 100 + 큐레이션 110 | `../data/expert_profiles.parquet` (합성) + `../data/experts/curated_profiles.parquet` (큐레이션) |
| ③ | 기술 문제 + 규제 시나리오 | 50 + 25 (적대적 포함, 다중 관할) | ✅ | 거절특허 50 + 거절사유 패턴 25 → `../data/problems.parquet`, `../data/regulatory_scenarios.parquet` |
| ④ | 정답 평가체계 | 7,500 ratings | ✅ **Dual GT**: examiner 7,500 + 합성 3-rater 7,800 | `../data/patents/prior_art_pairs.parquet` (examiner) + `../data/experts/curated_ratings.parquet` (3-rater κ/ICC). MRR/NDCG@5/Recall@K + κ=0.258, ICC=0.552 |
| ⑤ | 기술사업화 전략 v1 | 시장·고객·BM·경쟁 + 자원·가치·규제 + IP-R&D | ⏳ Skeleton | [commercialization_strategy_v1.md](commercialization_strategy_v1.md) |

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
