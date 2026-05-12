---
language:
  - en
  - ko
license: cdla-permissive-2.0
tags:
  - semiconductor
  - ontology
  - knowledge-graph
  - technology-management
  - patent-analytics
  - expert-matching
  - FMEA
  - provenance
task_categories:
  - graph-ml
size_categories:
  - 1K<n<10K
---

# SDKB v1.0 — Semiconductor Domain Knowledge Base

> **반도체 기술경영 다축 의사결정을 위한 공개 데이터셋**
> SKKU 기술경영전문대학원 · 계량기술경영연구실 (지도: 신준석 교수)
> Hyeonup-Project 2026-1 / Park HyoungSik (Ph.D. 19기)

**1차 응용 — AFCP-EM**: *Agent-First Compliance Platform for Expert/PriorArt Matching* — 같은 컴플라이언스-우선 매칭 아키텍처 위에서 전문가 매칭과 선행기술 매칭 두 시장을 동시에 겨냥한다.

## Why / For / How

- **Why** — 반도체 기술의 정량 의사결정(전문가 매칭, 기술기회 발굴, 핵심자원 조합, 기술가치평가, 다중관할 규제 적합성)을 재현 가능하게 만들기 위함.
- **For** — MOT 연구자·대학원생, 반도체 소부장 SME 기획/IP/R&D 담당자, 정책 분석가.
- **How** — 공정·장비·결함·스킬 + 특허(CPC/IPC/F-term) + 핵심자원(RBV) + 규제(BIS/NIST/ECHA + 한국 산업기술보호법) + 표준(SEMI/JEDEC) 를 PROV-O 출처와 함께 하나의 그래프로 묶는다.

## 1. 2026-1 산출물 진척표 (계획서 5종 + 정렬 트랙 4종)

### 1-1. 메인 트랙 — 계획서 채점 항목

| # | 산출물 | 수량 요건 | 상태 | 경로 |
|---|---|---|---|---|
| ① | SDKB 온톨로지 | ≥198 노드 / ≥264 간선, 14 타입 | ✅ Baseline 충족 | [data/semiconductor_v0_3.json](data/semiconductor_v0_3.json) |
| ② | 합성 전문가 프로필 | 100명, 비식별, 도메인 자문 | ✅ **Dual track**: 합성 100 + 큐레이션 100 | `data/expert_profiles.parquet` (합성) + `data/experts/curated_profiles.parquet` (큐레이션, Park 2026a) |
| ③ | 기술 문제 + 규제 시나리오 | 50 + 25 (적대적 포함, 다중 관할) | ✅ | **거절특허 50** + **거절사유 패턴 25** → `data/problems.parquet`, `data/regulatory_scenarios.parquet` |
| ④ | 정답 평가체계 | 7,500 ratings | ✅ **Dual GT**: examiner 7,500 + 합성 3-rater 7,800 | `data/patents/prior_art_pairs.parquet` (examiner) + `data/experts/curated_ratings.parquet` (3-rater κ/ICC). MRR/NDCG@5/Recall@K + κ=0.258, ICC=0.552 |
| ⑤ | 기술사업화 전략 v1 | 시장·고객·BM·경쟁 + 자원·가치·규제 + IP-R&D | ⏳ Skeleton | `docs/commercialization_strategy_v1.md` |

### 1-2. 정렬 트랙 — 신 교수 4-pillar 방향 (`docs/research_alignment.md` 참조)

| 모듈 | 목적 | 상태 | 경로 |
|---|---|---|---|
| `sdkb-patent.ttl` | Patent / CPC / IPC / F-term / Topic / Novelty / RejectionReason / hasPriorArt | ⬜ Pending | `ontology/sdkb-patent.ttl` |
| `sdkb-rbv.ttl` | Firm / Resource / Capability / EntryBarrier | ⬜ Pending | `ontology/sdkb-rbv.ttl` |
| `sdkb-commercialization.ttl` | TRL / License / Spinoff / IPTransaction | ⬜ Pending | `ontology/sdkb-commercialization.ttl` |
| `sdkb-foresight.ttl` | Scenario / STEEPVE / RealOption | ⬜ Pending | `ontology/sdkb-foresight.ttl` |
| `sdkb-governance-kr.ttl` | 한국 산업기술보호법 (다중 관할 명시화) | ⬜ Pending | `ontology/sdkb-governance-kr.ttl` |

### 1-3. 1차 실 데이터 — 거절특허 773건 (SIRP) ⭐
| 항목 | 값 |
|---|---|
| 파일 | [data/patents/raw/semiconductor_industry_rejected_patents.jsonl](data/patents/raw/semiconductor_industry_rejected_patents.jsonl) |
| 규모 | **773 거절특허 + 2,731 GT 인용 선행기술 + examiner-cited 1,961 (mean 2.54/특허)** |
| 출처 | KIPRIS Plus API + KIPRIS 웹 (KIPO) |
| 코호트 | `semiconductor_ontology_rejected_patents` 431 / `semiconductor_fullstack_rejected_patents` 342 |
| 데이터 카드 | [docs/dataset_rejected_patents_card.md](docs/dataset_rejected_patents_card.md) |
| 라이선스 | KIPRIS Plus API 약관 — 학교 자문 후 조정 |

### 1-4. 사전 자기 작업물 통합 — Park 2026a (ExpDataSet v3.3.5) ⭐
| 자산 | 통합 위치 | 규모 |
|---|---|---|
| KR 거버넌스 마스터 (산업기술보호법 §33/§34) | `data/compliance/kr_standards_v1.json` + `ontology/sdkb-governance-kr-instances.ttl` | 12 controls, 132 triples |
| US 거버넌스 마스터 (EAR/CCL + Deemed Export) | `data/compliance/us_standards_v1.json` + `ontology/sdkb-governance-us-instances.ttl` | 8 controls, 73 triples |
| 큐레이션 전문가 풀 (KR + EN) | `data/experts/curated_profiles.parquet` | 110 profiles, 103 columns |
| 3-rater synthetic ratings | `data/experts/curated_ratings.parquet` + `curated_ratings_pivot.parquet` | 7,800 ratings · 2,600 pivot subjects · Fleiss κ=0.258, ICC(2,1)=0.552 |
| Compliance scenarios S1~S6 | `data/compliance/scenarios_v1.json` | 34 scenarios |
| Leakage incidents L1~L4 | `data/compliance/leakage_incidents_v1.json` | 4 cases |
| SME problems (external reference) | `data/problems_external/sme_problems_v1.json` | 201 problems |
| 정렬 회계 문서 | [docs/expdataset_alignment.md](docs/expdataset_alignment.md) | net-new contributions 5종 명시 |

> 변경 사유와 amendment 절차: [v1](docs/plan_amendment_v1.md) → [v2](docs/plan_amendment_v2.md) → [v3](docs/plan_amendment_v3.md)

## 2. 데이터셋 사용 사례 (Use Cases)

| 사용 사례 | 사용 모듈 | 노트북 | 학술 참조 |
|---|---|---|---|
| **AFCP-EM (Expert)** — 반도체 소부장 전문가 매칭 + 다중관할 규제 누수 차단 | core + governance + governance-kr | `notebooks/01_matching_baseline_afcp.ipynb` | 본 계획서 |
| **AFCP-EM (PriorArt)** — 특허출원 ↔ 선행기술 매칭 (IP-R&D 컨설팅) | core + patent + SIRP | `notebooks/04_prior_art_baseline.ipynb` | PatentMatch, CLEF-IP 패밀리 |
| **Novelty-focused patent mapping** — 반도체 기술기회 클러스터 | core + patent + SIRP | `notebooks/02_patent_opportunity_demo.ipynb` | Lee/Kang/Shin (TFSC 2015) |
| **Key resource combinations** — 반도체 fabless 시장진입 분석 | core + rbv | `notebooks/03_rbv_resource_combo_demo.ipynb` | Cho/Shin (PLoS ONE 2025), Bae/Shin (IEEE Access 2022) |
| 실물옵션 기술가치평가 (후속 학기) | core + foresight + commercialization | (2026-2) | 신 교수 실물옵션 라인 |

## 3. 아키텍처

| 레이어 | 모듈 | 라이선스 |
|---|---|---|
| **Core (Open)** | 공정 14 타입 KG, FMEA | CDLA-Permissive-2.0 |
| **Governance (Open)** | BIS/NIST/ECHA + **KR 산업기술보호법** | CDLA-Permissive-2.0 |
| **Alignment (Open)** | patent / rbv / commercialization / foresight | CDLA-Permissive-2.0 |
| **Link-Only** | SEMI E10/E30/E40/E116 (식별자만) | N/A (메타데이터) |

```
ontology/
  sdkb-core.ttl                     # 14 코어 클래스
  sdkb-governance.ttl               # BIS/NIST/ECHA
  sdkb-governance-kr.ttl            # 한국 산업기술보호법 (NEW)
  sdkb-patent.ttl                   # 신 교수 방향: 특허 분류 (NEW)
  sdkb-rbv.ttl                      # 신 교수 방향: 핵심자원 (NEW)
  sdkb-commercialization.ttl        # 신 교수 방향: 사업화 (NEW)
  sdkb-foresight.ttl                # 신 교수 방향: 시나리오/옵션 (NEW)
data/
  semiconductor_v0_3.json           # 198노드 / 264엣지 베이스라인
  expert_profiles.parquet           # 100 합성 (NEW)
  problems.parquet                  # 50 기술 문제 (NEW)
  regulatory_scenarios.parquet      # 25 적대적 시나리오 (NEW)
  ground_truth.parquet              # 7,500 ratings (NEW)
  patents.parquet                   # 정렬 트랙 인스턴스 (NEW)
  firms.parquet                     # 정렬 트랙 인스턴스 (NEW)
docs/
  plan_amendment_v1.md              # 계획서 변경 보고
  research_alignment.md             # 4-pillar 매핑
  afcp_em_architecture.md           # 시스템 개요 (NEW)
  leakage_protocol.md               # 누수 정의/측정 (NEW)
  expert_validation_log.md          # 도메인 자문 흔적 (NEW)
  datasheet.md                      # 데이터시트 (Gebru) (NEW)
  commercialization_strategy_v1.md  # 사업화 전략 v1 (NEW)
  architecture_amendment_sdkb_centric.md  # 활성 ADR — SDKB-centric 방향 (2026-05-12)
  patent_taxonomy_integration_plan.md     # 활성 계획 (CPC/IPC/F-term 통합)
  patent_abstract_enrichment_plan.md      # 활성 계획 (특허 초록 NLP 보강)
  archive/architecture_redesign_semiconto_hub_v1.1.md  # SUPERSEDED — SemicONTO Hub 원안
validation/
  shapes.ttl                        # SHACL
  reliability_report.md             # κ/ICC (NEW)
provenance/
  prov.ttl                          # PROV-O 체인
examples/sparql/
  01_regulatory_risk.rq
  02_fmea_path.rq
  03_tech_gap.rq
notebooks/
  01_matching_baseline_afcp.ipynb   # 1차 응용 (NEW)
  02_patent_opportunity_demo.ipynb  # 정렬 응용 (NEW)
  03_rbv_resource_combo_demo.ipynb  # 정렬 응용 (NEW)
CITATION.cff                        # advisor 명시 (NEW)
```

## 4. Provenance & Auditability

AFCP-EM의 **아키텍처 수준 규제 준수**(사후 필터가 아님)와 **감사가능성**은 다음 메타데이터로 보장된다.

- `dcterms:source` / `dcterms:license` / `dcterms:bibliographicCitation` — 출처 추적
- `sdkb:interpretationType` — `verbatim` | `mapped` | `author-defined`
- `sdkb:validationRequired` — 전문가 검증 필요 플래그
- PROV-O — `prov:wasGeneratedBy` / `prov:wasDerivedFrom` / `prov:wasAttributedTo`
- SHACL — 모든 릴리스는 `shapes.ttl` 통과 필요
- 누수(leakage) 프로토콜 — [docs/leakage_protocol.md](docs/leakage_protocol.md) (작성 예정)

## 5. 큐레이션 소스

| 소스 | 라이선스 | 통합 형태 |
|---|---|---|
| SemiKong (arXiv:2411.13802) | Apache 2.0 | 공정 계층 L1→L3 |
| SemicONTO (CEUR-WS Vol-3760) | CC BY 4.0 | 재료/장비 OWL 정렬 |
| MatKG (Scientific Data 2024) | CC BY 4.0 | 재료 엔터티 확장 |
| USPTO / EPO / KIPO | Public | CPC/IPC 분류 (메타만) |
| BIS CCL/EAR | Public | 장비 ECCN |
| NIST CSF 2.0 / IR 8546 | Public | 사이버 거버넌스 |
| ECHA SCIP | Public | SVHC 재료 컴플라이언스 |
| 한국 산업기술보호법 | Public | 국가핵심기술 지정 |
| Wikidata | CC0 | 엔터티 링킹 |
| SEMI E10/E30/E40/E116 | Proprietary | Link-Only (식별자) |

## 6. Usage

### 6-1. Setup (한 번만)
```bash
make venv                           # Python 3.11 가상환경 + 의존성 설치
source .venv/bin/activate           # 또는 PATH=.venv/bin:$PATH 프리픽스
```

### 6-2. 전체 파이프라인
```bash
make pipeline-with-expdataset       # baseline + SIRP + experts + Park 2026a 통합 (전체)
make pipeline-full                  # baseline + SIRP + experts (Park 2026a 제외)
```

### 6-3. 개별 타깃
```bash
make parse       # baseline parsing
make owl         # OWL metamodel (sdkb-core.ttl)
make convert     # JSON → RDF/JSON-LD
make align       # alignment candidates (mappings/)
make validate    # SHACL validation
make test        # pytest (baseline + patents)
make ingest-sirp # SIRP JSONL → 3 parquet
make sirp-pairs  # 7,500 prior-art pairs (deliverable ④)
make sirp-problems  # 50 problems + 25 scenarios (deliverable ③)
make experts     # 100 synthetic experts (deliverable ②)
make compliance  # KR+US governance instances (Park 2026a, 205 triples)
make curated-experts  # ingest curated 110-expert pool (Park 2026a)
make curated-ratings  # ingest 7,800 3-rater ratings + κ/ICC report
make expdataset  # compliance + curated-experts + curated-ratings
make help        # 모든 타깃 목록
```

### 6-4. 검증된 산출물 수치
- 베이스라인 **198 노드 / 268 엣지** (deliverable ①, v0.3)
- SIRP 773 patents · 3,118 IPC 링크 · 4,696 prior-art 엣지
- 7,500 examiner-grounded pairs (positive 2,723 + hard-neg 2,723 + easy-neg 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts = **dual-track pool**
- 7,500 examiner + 7,800 3-rater synthetic = **dual-track GT** (κ=0.258, ICC=0.552)
- KR+US governance: 20 controls, 205 RDF triples
- **46/46 tests pass + ✓ SHACL VALIDATION PASSED**

## 7. Limitations & Bias

- 공개 문서·규정 임계치 기반이며, 팹별 사유 공정 데이터는 포함하지 않음
- FMEA 인과 관계는 문헌 도출 — 도메인 전문가 검증 필요
- 영어 중심 + 한국어 동의어 보강, 그 외 언어 미지원
- 규제 데이터는 인출 시점 기준 — 월간 갱신 파이프라인 권장
- 합성 전문가 프로필·평점은 비식별 합성이며 실제 인물·기업과 무관

## 8. Citation

```bibtex
@dataset{sdkb_v1_2026,
  title       = {SDKB v1.0: Semiconductor Domain Knowledge Base},
  author      = {Park, HyoungSik},
  advisor     = {Shin, Juneseuk},
  institution = {Sungkyunkwan University, Graduate School of
                 Management of Technology, Quantitative MOT Lab},
  year        = {2026},
  version     = {1.0},
  url         = {https://github.com/arkwith7/semiconductor-knowledge-base},
  license     = {CDLA-Permissive-2.0}
}
```

## 9. License

CDLA-Permissive-2.0 (Open Core). Link-Only 레이어는 재배포 대상이 아니다.
자세한 내용은 [LICENSE.txt](LICENSE.txt) 참조.
