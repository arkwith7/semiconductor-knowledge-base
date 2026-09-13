# PLAN-005 단계 8 — V6b US 종이 이식 (기계 산출)

> 생성: `scripts/report_stage8_paper_port.py` · 2026-09-11 · **손으로 고치지 않는다** — `make stage8-paper-port` 가 다시 만든다. 동결값(`FROZEN`)은 결과 전에 박았다.

## 판정 — **PASS** (①–⑤ 전부)

| 조건 | 판정 |
|---|:-:|
| l1_changed_lines_0 | ✓ |
| cross_clean | ✓ |
| shacl_conforms | ✓ |
| shacl_non_vacuous | ✓ |
| cq_identical | ✓ |

## ① L1 변경 라인수 — **0** (동결 커밋 `ead24dd`)

| 파일 | 동결 sha256 | 현 sha256 | 불변 | 변경 줄 |
|---|---|---|:-:|---:|
| `ontology/sdkb-priorart-core.ttl` | `307875eb7696` | `307875eb7696` | ✓ | 0 |
| `ontology/sdkb-priorart-semi.ttl` | `d66c93252478` | `d66c93252478` | ✓ | 0 |
| `ontology/sdkb-priorart-kr.ttl` | `4e5ed9739f64` | `4e5ed9739f64` | ✓ | 0 |

## ② US 바인딩 — `ontology/sdkb-priorart-us.ttl` · 27 트리플 · sha `1a4ad2678b76`

import: `https://w3id.org/sdkb/pa` · 클래스 선언 0 · 술어 선언 0 · exactMatch 0 · ElementVerdict 0(원천 없음 · 넣지 않았다)

| 개체 | 유형 | notation | 관할 | 역할 | 라벨 |
|---|---|---|---|---|---|
| `Ground_102` | LegalGround | USPTO-102 | JurisdictionUS | — | lack of novelty (35 U.S.C. §102) |
| `Ground_103` | LegalGround | USPTO-103 | JurisdictionUS | — | obviousness (35 U.S.C. §103) |
| `FinalOfficeAction` | ExaminationDocumentType | — | JurisdictionUS | FinalAction | final Office Action |
| `NonFinalOfficeAction` | ExaminationDocumentType | — | JurisdictionUS | FirstAction | non-final Office Action |

## ③ 교차 오염 — us→도메인 0 · us→kr 0 · kr→us 0 → clean

## ④ SHACL — conforms True · US 타깃 LegalGround 2 · DocumentType 2 · non-vacuous True

## ⑤ CQ 불변 — 33 개 · US 없이/있게 행 수 벡터 **동일**

| CQ | 행 |
|---|---:|
| CQ01_patents_per_process_step | 23 |
| CQ02_recent_patents_by_step | 441 |
| CQ03_uncovered_process_steps | 27 |
| CQ04_concept_annual_series | 371 |
| CQ05_concept_vs_ipc_series | 2339 |
| CQ06_concepts_without_recent_patents | 58 |
| CQ07_device_process_crosswalk | 67 |
| CQ08_applicant_process_portfolio | 324 |
| CQ09_rejection_prior_art | 414 |
| CQ10_prior_art_candidates_by_concept | 8 |
| CQ11_experts_for_process_skill | 66 |
| CQ12_problem_process_equipment_expert | 3134 |
| CQ13_value_chain_vendor_portfolio | 21 |
| CQ14_value_chain_role_distribution | 18 |
| CQ15_failure_causal_chain | 6 |
| CQ16_material_incompatibility | 3 |
| CQ17_material_problem_expert | 35 |
| CQ18_patents_by_skill | 4 |
| CQ19_process_control_and_metrology | 6 |
| CQ20_experts_by_equipment | 395 |
| CQ21_process_hierarchy_portfolio | 38 |
| CQ22_patent_equipment_and_technode | 204 |
| CQ23_concept_export_control | 37 |
| CQ24_national_core_technology | 12 |
| CQ25_critical_control_concepts | 7 |
| CQ26_patent_export_control_exposure | 1331 |
| CQ27_fto_claim_readiness | 0 |
| CQ28_patent_failuremode_expert | 84 |
| CQ29_claim_level_rejection_judgment | 0 |
| CQ30_independent_claim_features | 0 |
| CQ31_dependent_claim_hierarchy | 0 |
| CQ32_novelty_uncovered_essential_concepts | 200 |
| CQ33_prior_art_disclosures_by_concept | 540 |

## 한계

- 이것은 **설계 보증**이다 — US 문헌 회수 성능은 재지 않았고 재지 않는다(PLAN-005 §7-8).
- US 판정 어휘(KSR/TSM · inherency 등)는 원천이 저장소에 없어 넣지 않았다(§1-4). KR 은 `VerdictWellKnown`·`VerdictDesignChange` 를 갖는다 — 비대칭은 원천의 비대칭이다.
- KR 근거와의 `skos:exactMatch` 를 걸지 않았다 — §29① 은 유예기간이 §102 와 다르고 §29② 는 §103 KSR 과 같은 판단이 아니다. 읽는 소비자도 없다(§7-6).
