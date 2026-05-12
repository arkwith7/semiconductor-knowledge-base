# ExpDataSet Alignment — Prior Self-Work Integration

> 본 문서는 박형식의 **사전 작업물 `kukkukpool/ExpDataSet` v3.3.5**(이하 *Park 2026a*)와 본 SDKB 프로젝트의 관계를 명시하고, 어떤 자산을 어떤 형태로 본 레포에 통합했으며 본 학기(2026-1) 작업의 차별점이 무엇인지 정의한다. 학기 채점과 학술 인용 모두에 정합한 회계 문서다.

| 항목 | 내용 |
|---|---|
| 본인 사전 작업 | `kukkukpool/ExpDataSet` v3.3.5 (2026-03-01) — AFCP-EM Paper V3.3.5 + 데이터셋 8종 + 실험 결과 |
| 통합 시나리오 | **B (중도)** — Amendment v3에서 명시 |
| 작성일 | 2026-05-12 |
| 저자권 | 박형식 본인 작업물 (사용자 확인). 본 SDKB v1.0의 CDLA-Permissive-2.0 우산 아래로 가져옴 |

---

## 1. Park 2026a — 자산 인벤토리

| 자산 | 원경로 (ExpDataSet) | 본 SDKB 통합 경로 | 통합 형태 |
|---|---|---|---|
| AFCP-EM Paper V3.3.5 | `AFCP_EM_Paper_V3_3_5.pdf` | (미복제, 사전 작업물로 인용) | 인용 [Park 2026a] |
| SDKB 온톨로지 v0.2 | `data/ontology/semiconductor_v0.2.json` | 본 SDKB v0.3 = v0.2의 후속 (이번 학기 dedup + vendor:semes + OBSERVED_IN 4건 + owl:unionOf) | 후속 발전 |
| 합성 전문가 100 (KR) | `expert_profiles_dataset.json` | `data/experts/curated_profiles_kr.json` + `curated_profiles.parquet` | 본 학기 `gen_experts.py` 합성과 **병렬 보존** |
| 합성 전문가 100 (EN) | `expert_profiles_dataset_en.json` | `data/experts/curated_profiles_en.json` | 같음 |
| 7,500+ 3-rater ratings | `ground_truth_ratings.csv` | `data/experts/curated_ratings_3rater.csv` + `curated_ratings.parquet` + `curated_ratings_pivot.parquet` | **κ/ICC 계산 + 본 학기 SIRP examiner-GT와 병렬 비교** |
| 컴플라이언스 시나리오 S1~S6 | `compliance_scenarios_v1.json` | `data/compliance/scenarios_v1.json` | reference |
| 한국 거버넌스 마스터 12건 | `kr_compliance_standards_v1.json` | `data/compliance/kr_standards_v1.json` → `ontology/sdkb-governance-kr-instances.ttl` (132 triples) | sdkb-governance-kr.ttl 인스턴스 시딩 |
| 미국 거버넌스 마스터 8건 | `us_compliance_standards_v1.json` | `data/compliance/us_standards_v1.json` → `ontology/sdkb-governance-us-instances.ttl` (73 triples) | sdkb-governance.ttl 인스턴스 시딩 |
| Leakage 사고 L1~L4 | `leakage_incident_reports_v1.json` | `data/compliance/leakage_incidents_v1.json` | leakage_protocol.md 보강 자산 |
| SME 문제 201 | `sme_problems_dataset.json` | `data/problems_external/sme_problems_v1.json` | Stage 2(2026-2) 알고리즘 평가용 외부 보강 |
| 컴플라이언스 문제 30 | `compliance_test_problems_v1.json` | `data/problems_external/compliance_problems_v1.json` | reference |
| Adversarial 문제 30 | `compliance_adversarial_problems_v1.json` | `data/problems_external/adversarial_problems_v1.json` | reference |
| KGE 학습 산출물 | `results/kge/` (3,314 triples, TransE/RotatE) | (미복제, 사전 결과로 인용) | Stage 2 algoritm 평가의 baseline |
| Formal verification | `results/formal_verification_report.json` (completeness=1.0, soundness=0.711) | (미복제, 사전 결과로 인용) | Theorem 1 검증의 baseline |

---

## 2. 본 학기(2026-1) net-new contributions

다음 다섯 가지는 Park 2026a에 **없는** 본 학기의 새 기여다. 학기 채점과 학위논문 chapter 모두에서 본 학기의 독립적 성과로 청구 가능.

| # | Contribution | 위치 |
|---|---|---|
| 1 | **SIRP — 773 KIPO examiner-grounded prior-art pairs** | `data/patents/prior_art_pairs.parquet` (7,500 pairs, real examiner labels) |
| 2 | **AFCP-EM-PriorArt 응용 트랙** (Park 2026a는 Expert 단일 트랙) | `docs/afcp_em_architecture.md` §3, `notebooks/04_prior_art_baseline.ipynb` |
| 3 | **Patent / RBV / Commercialization / Foresight 5개 모듈** (sdkb-patent + 4종) | `ontology/sdkb-{patent,rbv,commercialization,foresight,governance-kr}.ttl` |
| 4 | **다중관할 NCT-누수 SHACL SPARQL shape** (Park 2026a는 Tier-1/2/3 코드 게이트만) | `validation/shapes_patent.ttl` §Shape_NCTLeakage |
| 5 | **SDKB v0.2 → v0.3 베이스라인 보강** (dedup + vendor:semes + 4 OBSERVED_IN + owl:unionOf permissive domains) | `data/semiconductor_v0_3.json`, `scripts/build_owl.py` |

---

## 3. 학술적으로 새로운 chapter — Synthetic vs Examiner-Grounded

Park 2026a는 **합성 3-rater** 라벨만으로 §5 실험을 진행했다. 본 학기는 **examiner-grounded 라벨**을 새로 확보했으므로 두 라벨 소스의 비교가 가능해진다 — 이건 V3.3.5에서 다루지 못한 외부 타당성 검증이며, 본 학기의 학술 contribution이다.

**관측된 합성-rater 일치도** (`data/experts/reliability_report.md`):

| 지표 | 값 | 해석 (Landis & Koch 1977 / Koo & Li 2016) |
|---|---|---|
| Cohen's κ rater 1↔2 | 0.233 | fair |
| Cohen's κ rater 1↔3 | 0.306 | fair |
| Cohen's κ rater 2↔3 | 0.235 | fair |
| **Fleiss' κ** (3 raters) | **0.258** | fair |
| **ICC(2,1)** | **0.552** | moderate |

이 fair-moderate 수준은 "합성 3-rater도 인간 평가와 닮은 noise를 시뮬레이트한다"는 새로운 시사점이다.

**의미**: 두 데이터는 동일한 relevance를 측정하지 않는다.
- Examiner-grounded: 객관적·공인 (KIPO 심사관 1인 결정), 단일 권위 라벨
- Synthetic 3-rater: 주관적·집계 (3인 평균), 다인 noise 포함

→ **AFCP-EM 평가 시 두 라벨을 다른 트랙에서 사용** (`notebooks/05_synthetic_vs_curated_comparison.ipynb`).

---

## 4. 인용 형식

본 SDKB의 모든 ExpDataSet 출처 자산에는 다음 인용을 부착한다.

```bibtex
@unpublished{park2026a,
  author = {Park, HyoungSik},
  title  = {AFCP-EM: An Agent-First Compliance Platform for Semiconductor
            Expert Matching — Dataset and Experimental Evaluation (V3.3.5)},
  year   = {2026},
  note   = {Prior self-work; repository: arkwith7/kukkukpool},
  date   = {2026-03-01}
}
```

본 학기 산출물은 별도 출판 단위로 위 인용을 참조하며, 다음과 같이 등록된다.

```bibtex
@dataset{sdkb_v1_2026,
  title       = {SDKB v1.0: Semiconductor Domain Knowledge Base with
                 SIRP Examiner-Grounded Prior-Art and AFCP-EM Dual-Track},
  author      = {Park, HyoungSik},
  advisor     = {Shin, Juneseuk},
  institution = {Sungkyunkwan University, MOT},
  year        = {2026},
  version     = {1.0},
  url         = {https://github.com/arkwith7/semiconductor-knowledge-base},
  license     = {CDLA-Permissive-2.0},
  note        = {Extends prior self-work [Park 2026a].}
}
```

---

## 5. 책임의 회계

| 자산 | 본 SDKB가 청구 | Park 2026a가 출처 |
|---|---|---|
| SIRP 7,500 examiner pairs | ✓ | — |
| AFCP-EM-PriorArt track | ✓ | — |
| Patent/RBV/Comm/Foresight 모듈 | ✓ | — |
| SHACL NCT-leakage shape | ✓ | — |
| v0.2 → v0.3 baseline 개선 | ✓ | 부분 (v0.2 토대) |
| 합성 100 전문가 풀 | — | ✓ |
| 7,500 3-rater ratings | — | ✓ |
| KR/US 거버넌스 마스터 | — | ✓ |
| AFCP-EM 시스템명 + Tier 게이트 | — | ✓ |
| Compliance scenarios S1~S6 | — | ✓ |
| KGE 학습 결과 | — (참조만) | ✓ |
| Formal verification | — (참조만) | ✓ |
| Multi-Signal 가중치 (0.20/0.10/0.70) | — (참조만) | ✓ |

요약: **이번 학기의 작업은 Park 2026a의 평가 외부 타당성을 확장하고, prior-art retrieval로 시장을 넓히는 일관된 follow-on**이다.

---

## 6. 갱신 이력

| 일자 | 변경 |
|---|---|
| 2026-05-12 | 초안 작성 — Amendment v3와 동시 도입 |
