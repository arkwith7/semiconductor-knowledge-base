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

> **반도체 산업의 계량기술경영 연구를 위한 재현 가능한 시맨틱 그래프 기반.**
> 운영: 성균관대학교 기술경영전문대학원 [계량기술경영 연구실](#연구실-컨텍스트) (Quantitative Technology Management Lab, PI: 신준석 교수)
>
> 🌐 English version: [README.md](README.md)
> 🔗 **Live demo (GitHub Pages):** [`arkwith7.github.io/semiconductor-knowledge-base`](https://arkwith7.github.io/semiconductor-knowledge-base/) — 큐레이션 그래프 229노드 · SIRP 상위 50특허 + 선행기술 · 4-pillar 클래스 골격 인터랙티브 3-뷰

## 한 줄 포지셔닝

SDKB는 반도체 **공정 · 장비 · 결함 · 스킬** 지식, **특허 분류**(CPC / IPC / F-term), **기업 자원**(RBV), **다중관할 규제**(미국 BIS · NIST · ECHA + 한국 산업기술보호법), **표준**(SEMI / JEDEC) 을 단일 PROV-O 출처 추적 온톨로지 위에 통합한다. 본 레포는 계량기술경영 연구실의 네 가지 연구 라인 — *기술예측, 유망기술 기회 발굴, 중소기업 혁신 성과 분석, 인터랙티브 기술 · 비즈니스 데이터 시각화* — 의 공통 데이터 기반이며, 후속 학위논문 "컴플라이언스 인지 시맨틱 협업 플랫폼"의 시드 데이터셋이다.

**1차 응용 — SDKB-Match** (*SDKB Matching Layer — 반도체 소부장 SME ↔ 전문가, 특허출원 ↔ 선행기술 매칭*): 두 매칭 시장을 컴플라이언스-우선 아키텍처(사후 필터가 아닌 아키텍처 수준) 위에서 동시에 구현한다.

## 약어 · 핵심 용어 (Glossary)

처음 등장하는 약어의 풀네임과 의미를 한곳에 모은다.

| 약어 | 풀네임 / 의미 |
|---|---|
| **SDKB** | Semiconductor Domain Knowledge Base — 본 데이터셋·온톨로지 트렁크 |
| **SDKB-Match** | SDKB Matching Layer — SDKB 위에 구현된 매칭 응용 계층. 반도체 소부장 SME ↔ 전문가 매칭과 특허출원 ↔ 선행기술 매칭을 컴플라이언스-우선 아키텍처(사후 필터가 아님) 위에서 동시 구현. 하위 트랙: **SDKB-Match Expert** / **SDKB-Match PriorArt** |
| **SIRP** | Semiconductor Industry Rejected Patents — 반도체 거절특허 **1,000건** 데이터셋 (초기 코호트 스냅샷 773건; GT 쌍은 773-스냅샷에 고정) |
| **소부장 SME** | 소재·부품·장비(materials·parts·equipment) 중소기업 |
| **RBV** | Resource-Based View — 기업 핵심자원 기반 관점 |
| **FMEA** | Failure Mode and Effects Analysis — 고장모드영향분석 |
| **IPC / CPC / F-term** | International / Cooperative Patent Classification / File-forming term — 특허 분류 체계 |
| **GT** | Ground Truth — 정답 라벨(examiner-grounded = 특허청 심사관 인용 기반) |
| **MRR / NDCG@K / Recall@K** | Mean Reciprocal Rank / Normalized Discounted Cumulative Gain@K / Recall@K — 검색 성능 지표 |
| **κ / ICC** | Weighted Cohen's κ / Intraclass Correlation Coefficient — 라벨 신뢰도 지표 |
| **IP-R&D** | Intellectual-Property-driven R&D — 특허 연계 연구개발·컨설팅 |
| **SHACL** | Shapes Constraint Language — RDF 그래프 제약 검증 언어 |
| **PROV-O** | W3C Provenance Ontology — 출처 추적 온톨로지 |
| **KG / OWL / RDFS / TTL** | Knowledge Graph / Web Ontology Language / RDF Schema / Turtle 직렬화 |
| **BIS / NIST / ECHA / ITPA** | US Bureau of Industry and Security / US National Institute of Standards and Technology / European Chemicals Agency / 한국 산업기술보호법(Industrial Technology Protection Act) — 다중관할 규제 소스 |
| **SEMI / JEDEC** | 반도체 표준화 기구(SEMI International Standards / JEDEC Solid State Technology Association) |
| **KIPRIS** | Korea Intellectual Property Rights Information Service — 한국특허정보넷 |
| **TFSC** | *Technological Forecasting & Social Change* — 학술지 |
| **CLEF-IP / PatentMatch** | 선행기술 검색 평가 벤치마크(평가 프로토콜 참조) |
| **MOT** | Management of Technology — 기술경영 |
| **A2 / A6** | prior-art 온톨로지 갭 플랜의 작업 항목 ID (A2 = 소자/제품 device 계층 신설, A6 = IDF 가중 개념 랭킹) |

## 연구실 컨텍스트

신준석 교수님의 계량기술경영 연구실은 정량 데이터(특허·시장·산업)와 시맨틱 모델링을 결합해 R&D 기획·기술사업화·중소기업 혁신을 지원한다. SDKB는 그 어젠다의 반도체 도메인 데이터 기반이다:

| 연구실 연구 라인 | SDKB의 기여 | 진입점 |
|---|---|---|
| 특허·시장·산업 데이터 기반 **기술예측** | `sdkb-patent.ttl` + SIRP + Topic / Novelty 노드 | [활용 사례 1](#활용-사례) |
| **유망기술 기회 발굴** | Novelty-focused patent mapping, emerging-memory 토픽 클러스터 | [활용 사례 1](#활용-사례), 🚧 [notebook 02](notebooks/02_patent_opportunity_demo.ipynb) |
| **중소기업 혁신 성과 분석 / 전문가 매칭** | SDKB-Match Expert + 합성 100 + 큐레이션 110 전문가 풀 + 다중관할 컴플라이언스 게이트 | [활용 사례 2](#활용-사례), 🚧 [notebook 01](notebooks/01_matching_baseline_expert.ipynb), ✅ [notebook 05](notebooks/05_synthetic_vs_curated_comparison.ipynb) |
| **인터랙티브 기술 · 비즈니스 시각화** | Pyvis 3-뷰 익스플로러 · GitHub Pages 자동 배포 | [Live demo](https://arkwith7.github.io/semiconductor-knowledge-base/), [docs/project/visualization_plan.md](docs/project/visualization_plan.md) |
| 조직적 R&D 관리 / 혁신 디자인 (보조축) | RBV 핵심자원 조합 + TRL / 실물옵션 시드 노드 | [활용 사례 4](#활용-사례), 🚧 [notebook 03](notebooks/03_rbv_resource_combo_demo.ipynb) |

## Why / For / How

- **Why** — 반도체 기술의 정량 의사결정(기술기회 발굴, 전문가 매칭, 핵심자원 조합, 기술가치평가, 다중관할 규제 적합성)을 **단일 시맨틱 그래프 위에서 재현 가능하게** 만들기 위함.
- **For** — 전세계 MOT 연구자·대학원생, 반도체 소부장 SME 기획/IP/R&D 담당자, 변리사·IP-R&D 컨설팅, 기술정책 분석가.
- **How** — 공정·장비·결함·스킬 지식 + 특허(CPC / IPC / F-term) + 핵심자원(RBV) + 규제(BIS / NIST / ECHA + 한국 산업기술보호법) + 표준(SEMI / JEDEC) 을 PROV-O 출처와 함께 하나의 그래프로 묶고, 그 위에 연구실의 네 가지 연구 라인을 응용 노트북으로 인스턴스화한다.

## 활용 사례

각 사례는 연구실 연구 라인을 SDKB의 동일 그래프 위에서 인스턴스화한다.

> **노트북 상태 범례** — ✅ 출시 완료(실행 가능) · 🚧 스켈레톤 stub (데이터 로딩은 동작, 알고리즘 셀은 `NotImplementedError` — 2026-1 중 구현 예정) · _(…)_ 후속 학기 자리표시자.

| # | 사용 사례 | 연구실 라인 | 모듈 | 노트북 | 학술 참조 |
|---|---|---|---|---|---|
| 1 | **Novelty-focused patent mapping** — 반도체 기술기회 클러스터 | 기회 발굴 / 기술예측 | core + patent + SIRP | 🚧 [02](notebooks/02_patent_opportunity_demo.ipynb) | Lee/Kang/Shin (TFSC 2015), Shin et al. (TFSC 2017) |
| 2 | **SDKB-Match (Expert)** — 반도체 소부장 SME ↔ 전문가 시맨틱 매칭 + 다중관할 누수 차단 | 중소기업 혁신 / 전문가 매칭 | core + governance + governance-kr | ✅ [01](notebooks/01_matching_baseline_expert.ipynb) (매칭) · ✅ [05](notebooks/05_synthetic_vs_curated_comparison.ipynb) (GT 타당성) | — |
| 3 | **SDKB-Match (PriorArt)** — 특허출원 ↔ 선행기술 매칭 (examiner GT 기반) | IP-R&D 컨설팅 / 선행기술 분석 | core + patent + SIRP | ✅ [04](notebooks/04_prior_art_baseline.ipynb) | PatentMatch, CLEF-IP 패밀리 |
| 4 | **Key resource combinations** — 반도체 fabless 시장진입 분석 | 조직적 R&D / 핵심자원 분석 | core + rbv | 🚧 [03](notebooks/03_rbv_resource_combo_demo.ipynb) (데이터 대기 — 정렬 트랙) | Cho/Shin (PLoS ONE 2025), Bae/Shin (IEEE Access 2022) |
| 5 | **복합실물옵션** — EUV vs High-NA 로드맵 가치평가 | 기술가치평가 (후속 학기) | core + foresight + commercialization | _(2026-2 예정)_ | 연구실 실물옵션 라인 |
| 6 | **인터랙티브 KG 익스플로러** — 3-뷰(베이스라인 / SIRP / 4-pillar) GitHub Pages 배포 | 인터랙티브 시각화 | core + patent + rbv + foresight + commercialization | ✅ [Live](https://arkwith7.github.io/semiconductor-knowledge-base/) · `scripts/build_viz.py` | 연구실 시각화 트랙 |

4-pillar 상세 매핑: [docs/project/research_alignment.md](docs/project/research_alignment.md).

## 아키텍처

| 레이어 | 모듈 | 라이선스 |
|---|---|---|
| **Core (Open)** | 공정 14 타입 KG, FMEA | CDLA-Permissive-2.0 |
| **Governance (Open)** | 미국 BIS / NIST / ECHA + **한국 산업기술보호법** | CDLA-Permissive-2.0 |
| **Alignment (Open)** | patent / rbv / commercialization / foresight | CDLA-Permissive-2.0 |
| **Link-Only** | SEMI E10 / E30 / E40 / E116 (식별자만) | N/A (메타데이터) |

```
ontology/
  sdkb-core.ttl                     # 14 코어 클래스
  sdkb-governance.ttl               # BIS / NIST / ECHA
  sdkb-governance-kr.ttl            # 한국 산업기술보호법
  sdkb-patent.ttl                   # 특허 분류 (CPC / IPC / F-term / Topic / Novelty)
  sdkb-rbv.ttl                      # 핵심자원 (firm / resource / capability)
  sdkb-commercialization.ttl        # TRL / 라이선스 / 스핀오프
  sdkb-foresight.ttl                # 시나리오 / STEEPVE / 실물옵션
data/
  semiconductor_v0_3.json           # 큐레이션 그래프 229노드 / 268엣지 (베이스라인 원본 198/264)
  expert_profiles.parquet           # 합성 전문가 100
  experts/curated_profiles.parquet  # 큐레이션 110
  problems.parquet                  # 기술 문제 50
  regulatory_scenarios.parquet      # 적대적 시나리오 25
  patents/raw/                      # SIRP 원본 JSONL (1,000건) + parquet
  patents/prior_art_pairs.parquet   # 7,500 examiner-grounded pairs
  compliance/                       # KR + US 거버넌스 마스터
docs/
  datasheet.md                      # 데이터시트 (Gebru et al.) — SDKB 전체
  dataset_rejected_patents_card.md  # SIRP 데이터셋 카드
  leakage_protocol.md               # 누수 정의 / 측정
  expert_validation_log.md          # 전문가 자문 audit trail
  semiconductor_ontology_provenance_research.md  # 출처 / provenance 조사
  references/                       # BibTeX 라이브러리 + 논문별 노트
  project/                          # 현업프로젝트1 거버넌스: 계획서 변경보고·
                                    #   진척표·사업화·ADR·매칭 아키텍처·
                                    #   시각화 계획·피드백
validation/shapes.ttl               # SHACL
provenance/prov.ttl                 # PROV-O 체인
examples/sparql/                    # 예시 쿼리
notebooks/
  01_matching_baseline_expert.ipynb  # ✅ Use Case 2 (SDKB-Match Expert floor baseline)
  02_patent_opportunity_demo.ipynb   # 🚧 Use Case 1 (novelty-focused mapping)
  03_rbv_resource_combo_demo.ipynb   # 🚧 Use Case 4 (RBV — 데이터 대기)
  04_prior_art_baseline.ipynb        # ✅ Use Case 3 (SDKB-Match PriorArt 베이스라인)
  05_synthetic_vs_curated_comparison.ipynb  # ✅ UC2 용 GT 타당성 진단
CITATION.cff                        # advisor 명시
```

## Provenance & Auditability

SDKB-Match의 **아키텍처 수준 규제 준수**(사후 필터가 아님)와 **감사가능성**은 다음 메타데이터로 보장된다.

- `dcterms:source` / `dcterms:license` / `dcterms:bibliographicCitation` — 출처 추적
- `sdkb:interpretationType` — `verbatim` | `mapped` | `author-defined`
- `sdkb:validationRequired` — 전문가 검증 필요 플래그
- PROV-O — `prov:wasGeneratedBy` / `prov:wasDerivedFrom` / `prov:wasAttributedTo`
- SHACL — 모든 릴리스는 `shapes.ttl` 통과 필요
- 누수(leakage) 프로토콜 — [docs/leakage_protocol.md](docs/leakage_protocol.md)

## 큐레이션 소스

| 소스 | 라이선스 | 통합 형태 |
|---|---|---|
| SemiKong (arXiv:2411.13802) | Apache 2.0 | 공정 계층 L1 → L3 |
| SemicONTO (CEUR-WS Vol-3760) | CC BY 4.0 | 재료 / 장비 OWL 정렬 |
| MatKG (Scientific Data 2024) | CC BY 4.0 | 재료 엔터티 확장 |
| USPTO / EPO / KIPO | Public | CPC / IPC 분류 (메타만) |
| BIS CCL / EAR | Public | 장비 ECCN |
| NIST CSF 2.0 / IR 8546 | Public | 사이버 거버넌스 |
| ECHA SCIP | Public | SVHC 재료 컴플라이언스 |
| 한국 산업기술보호법 | Public | 국가핵심기술 지정 |
| Wikidata | CC0 | 엔터티 링킹 |
| SEMI E10 / E30 / E40 / E116 | Proprietary | Link-Only (식별자) |

## Usage

### Setup (한 번만)
```bash
make venv                           # Python 3.11 가상환경 + 의존성 설치
source .venv/bin/activate           # 또는 PATH=.venv/bin:$PATH 프리픽스
```

### 전체 파이프라인
```bash
make pipeline-with-expdataset       # baseline + SIRP + experts + 큐레이션 ExpDataSet (전체)
make pipeline-full                  # baseline + SIRP + experts (ExpDataSet 제외)
```

### 개별 타깃
```bash
make parse           # baseline parsing
make owl             # OWL metamodel (sdkb-core.ttl)
make convert         # JSON → RDF / JSON-LD
make align           # alignment candidates
make validate        # SHACL validation
make test            # pytest (baseline + patents)
make ingest-sirp     # SIRP JSONL → parquet
make sirp-pairs      # 7,500 prior-art pairs
make sirp-problems   # 50 problems + 25 scenarios
make experts         # 100 synthetic experts
make compliance      # KR + US governance instances (205 triples)
make curated-experts # 110-profile curated pool
make curated-ratings # 7,800 3-rater ratings + κ / ICC report
make expdataset      # compliance + curated-experts + curated-ratings
make help            # 모든 타깃 목록
```

### 인터랙티브 시각화 (GitHub Pages)
```bash
make viz       # SDKB → site/ 에 베이스라인 · SIRP · 4-pillar 3개 HTML + index 생성
make viz-open  # 위 + 기본 브라우저로 site/index.html 자동 오픈
```
- 빌드된 `site/`는 `.gitignore` 처리되어 main 브랜치에는 커밋되지 않음
- main에 푸시되면 [.github/workflows/viz-deploy.yml](.github/workflows/viz-deploy.yml)이 자동으로 site/를 재빌드해 GitHub Pages로 배포
- 1회 설정: 레포 **Settings → Pages → Source: GitHub Actions** 선택
- 상세: [docs/project/visualization_plan.md](docs/project/visualization_plan.md)

### 검증된 산출물 수치
- 큐레이션 그래프 **229 노드 / 268 엣지** (v0.3; 베이스라인 원본 198/264, 큐레이션으로 확장·Device 포함)
- SIRP **1,000 patents** (GT 쌍은 773-코호트 스냅샷에 고정) · 3,118 IPC 링크 · 4,696 prior-art 엣지
- 7,500 examiner-grounded pairs (positive 2,723 + hard-neg 2,723 + easy-neg 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts = **dual-track pool**
- 7,500 examiner-grounded(객관 KIPO 인용) + 7,800 알고리즘 시뮬레이션 3-rater 합성 평점 — **인간 전문가 주석 아님** (dual-track GT). 3-rater 신뢰도: weighted κ = 0.550 / ICC(2,k) = 0.787 (합의); 투명성: Fleiss κ = 0.258 / ICC(2,1) = 0.552 — [data/experts/reliability_report.md](data/experts/reliability_report.md)
- KR + US governance: 20 controls / 205 RDF triples
- **75 passed / 10 skipped (85 collected) · OWL 438 triples · SHACL VALIDATION PASSED**

## Limitations & Bias

- 공개 문서·규정 임계치 기반이며, 팹별 사유 공정 데이터는 포함하지 않음
- FMEA 인과 관계는 문헌 도출 — 도메인 전문가 검증 필요
- 영어 중심 + 한국어 동의어 보강, 그 외 언어 미지원
- 규제 데이터는 인출 시점 기준 — 월간 갱신 파이프라인 권장
- 합성 전문가 프로필·평점은 비식별 합성이며 실제 인물·기업과 무관

## Citation & Acknowledgement

본 데이터셋은 성균관대학교 기술경영전문대학원 **계량기술경영 연구실 (Quantitative Technology Management Lab, PI: 신준석 교수)** 의 연구 어젠다 — 특허·시장·산업 데이터 기반 기술예측, 유망기술 기회 발굴, 중소기업 혁신 성과 분석, 인터랙티브 기술·비즈니스 데이터 시각화 — 의 반도체 도메인 하부 산출물이다. 향후 동일 연구실에서 작성될 "**컴플라이언스 인지 시맨틱 협업 플랫폼**" 학위논문 및 관련 학술지 게재 논문에서 본 데이터셋을 실증 아티팩트로 인용할 예정이며, 그 시점에 BibTeX를 갱신한다.

```bibtex
@dataset{sdkb_v1_2026,
  title       = {SDKB v1.0: Semiconductor Domain Knowledge Base —
                 a data trunk for the Quantitative Technology Management
                 Lab's foresight, opportunity-discovery, SME-matching,
                 and interactive-visualization research agenda},
  author      = {Park, HyoungSik},
  advisor     = {Shin, Juneseuk},
  institution = {Sungkyunkwan University, Graduate School of
                 Management of Technology,
                 Quantitative Technology Management Lab},
  year        = {2026},
  version     = {1.0},
  url         = {https://github.com/arkwith7/semiconductor-knowledge-base},
  license     = {CDLA-Permissive-2.0},
  note        = {Hyeonup-Project 2026-1 deliverable; seed dataset for
                 the forthcoming compliance-aware semantic collaboration
                 platform dissertation.}
}
```

## License

CDLA-Permissive-2.0 (Open Core). Link-Only 레이어는 재배포 대상이 아니다.
자세한 내용은 [LICENSE.txt](LICENSE.txt) 참조.

---

*현업프로젝트 2026-1 연구실 내부 진척표 — 산출물 5종, 정렬 트랙 4-pillar, ExpDataSet 통합, amendment trail: [docs/project/project_status_2026_1.md](docs/project/project_status_2026_1.md).*
