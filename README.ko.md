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

# SDKB — Semiconductor Domain Knowledge Base

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22030395.svg)](https://doi.org/10.5281/zenodo.22030395)

> **반도체 산업의 계량기술경영 연구를 위한 재현 가능한 시맨틱 그래프 기반.**
> 운영: 성균관대학교 기술경영전문대학원 [계량기술경영 연구실](#연구실-컨텍스트) (Quantitative Technology Management Lab, PI: 신준석 교수)
>
> 🌐 English version: [README.md](README.md)
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
> 🔗 **Live demo (GitHub Pages):** [`arkwith7.github.io/sdkb-dataset`](https://arkwith7.github.io/sdkb-dataset/) — 큐레이션 그래프 · SIRP 상위 50특허 + 선행기술 · 4-pillar 클래스 골격 인터랙티브 3-뷰
<!-- sdkb:private-end -->


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
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
| **인터랙티브 기술 · 비즈니스 시각화** | Pyvis 3-뷰 익스플로러 · GitHub Pages 자동 배포 | [Live demo](https://arkwith7.github.io/sdkb-dataset/), [docs/project/visualization_plan.md](docs/project/visualization_plan.md) |
<!-- sdkb:private-end -->

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
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
| 6 | **인터랙티브 KG 익스플로러** — 3-뷰(베이스라인 / SIRP / 4-pillar) GitHub Pages 배포 | 인터랙티브 시각화 | core + patent + rbv + foresight + commercialization | ✅ [Live](https://arkwith7.github.io/sdkb-dataset/) · `scripts/build_viz.py` | 연구실 시각화 트랙 |
<!-- sdkb:private-end -->


4-pillar 상세 매핑: [docs/project/research_alignment.md](docs/project/research_alignment.md).

## 아키텍처

| 레이어 | 모듈 | 라이선스 |
|---|---|---|
| **Core (Open)** | 공정 · 장비 · 소재 · FMEA 코어 KG | CDLA-Permissive-2.0 |
| **Governance (Open)** | 미국 BIS / NIST / ECHA + **한국 산업기술보호법** | CDLA-Permissive-2.0 |
| **Alignment (Open)** | patent / rbv / commercialization / foresight | CDLA-Permissive-2.0 |
| **Link-Only** | SEMI E10 / E30 / E40 / E116 (식별자만) | N/A (메타데이터) |

```
ontology/
  sdkb-core.ttl                     # 코어 어휘 — 규모는 "릴리스 서명" 참조
  sdkb-governance.ttl               # BIS / NIST / ECHA
  sdkb-governance-kr.ttl            # 한국 산업기술보호법
  sdkb-patent.ttl                   # 특허 분류 (CPC / IPC / F-term / Topic / Novelty)
  sdkb-rbv.ttl                      # 핵심자원 (firm / resource / capability)
  sdkb-commercialization.ttl        # TRL / 라이선스 / 스핀오프
  sdkb-foresight.ttl                # 시나리오 / STEEPVE / 실물옵션
data/
  semiconductor_v0_3.json           # 손으로 큐레이션한 원천 그래프 — 규모는 "릴리스 서명" 참조
  expert_profiles.parquet           # 합성 전문가 100
  experts/curated_profiles.parquet  # 큐레이션 110
  problems.parquet                  # 기술 문제 50
  regulatory_scenarios.parquet      # 적대적 시나리오 25
  patents/raw/                      # SIRP 원본 JSONL (1,000건) + parquet
  patents/prior_art_pairs.parquet   # 7,500 examiner-grounded pairs
  compliance/                       # KR + US 거버넌스 마스터
docs/
  README.md                         # 문서 색인 — 여기서 시작
  ontology_guide.md                 # 어휘·설계 결정·확장 레시피
  glossary_ontology.md              # RDF/OWL/SHACL 용어 + 여기서 실제로 낸 사고
  glossary_semiconductor.md         # 이 온톨로지가 표현하는 반도체 도메인
  datasheet.md                      # 데이터시트 (Gebru et al.) — SDKB 전체
  dataset_rejected_patents_card.md  # SIRP 데이터셋 카드
  leakage_protocol.md               # 누수 정의 / 측정
  public_release_readiness_review.md # 이 저장소가 아직 틀린 것 (실측)
  semiconductor_ontology_provenance_research.md  # 출처 / provenance 조사
  references/                       # BibTeX 라이브러리 + 논문별 노트
  project/                          # 아키텍처·정렬·시각화 문서
validation/shapes.ttl               # SHACL
provenance/prov.ttl                 # PROV-O 체인
examples/sparql/                    # 예시 쿼리
<!-- 공개본에서 뺀다: 노트북은 공개본에 없다 -->
<!-- sdkb:private-begin -->
notebooks/
  01_matching_baseline_expert.ipynb  # ✅ Use Case 2 (SDKB-Match Expert floor baseline)
  02_patent_opportunity_demo.ipynb   # 🚧 Use Case 1 (novelty-focused mapping)
  03_rbv_resource_combo_demo.ipynb   # 🚧 Use Case 4 (RBV — 데이터 대기)
  04_prior_art_baseline.ipynb        # ✅ Use Case 3 (SDKB-Match PriorArt 베이스라인)
  05_synthetic_vs_curated_comparison.ipynb  # ✅ UC2 용 GT 타당성 진단
<!-- sdkb:private-end -->

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

## 무엇이 비어 있고 어떻게 채우는가

이 저장소가 담는 것은 **생성기이지 인스턴스가 아니다.** T-Box·어휘·SHACL shape·CQ 스위트·
빌드 스크립트는 전부 여기 있고, KIPRIS 특허 원문으로 만든 큰 A-Box 층은 **없다** — KIPRIS
이용약관이 학술 이용은 허용하되 원문 재배포는 허용하지 않기 때문이다.

**이것은 결손이 아니라 설계다.** 빈 체크아웃에 본인 KIPRIS 키만 있으면 논문이 인용한 그래프를
다시 만들 수 있다. 아래 표가 무엇이 왜 비어 있고 어느 명령이 채우는지를 그대로 적는다.

| 층 | 비어 있는 것 | 왜 | 채우는 명령 | 필요한 자격 |
|---|---|---|---|---|
| **T-Box** (`ontology/sdkb-core.ttl`) | 없음 — **파일이 커밋돼 있다**(2026-08-15) | 빌드 산출물이기도 하다: 커밋된 `data/semiconductor_v0_3.json`(392 KB)에서 **바이트 동일**하게 재생성된다 | `make owl && make convert` | 없음 |
| **SIRP 특허 A-Box** (`ontology/sdkb-abox-patents.ttl`) | 초록·청구항 텍스트 | KIPRIS 원문은 재배포 불가 | `make refetch-fulltext && make abox-patents` | KIPRIS OpenAPI 키 |
| **거절특허 데이터셋** (`data/patents/raw/…rejected_patents.jsonl`) | `abstract`·`claim1`·`claims_full[].text` 가 **빈 문자열**로 들어 있다. 스키마·식별자·IPC·날짜·정답 인용 라벨(`ground_truth_*`)은 **그대로 있다** | 같음 | `python scripts/refetch_rejected_patents.py` (복원본을 공표된 sha256 과 대조한다) | KIPRIS OpenAPI 키 |
| **인용 선행기술 A-Box** (`ontology/sdkb-abox-prior-art.ttl` · 21 MB) | 파일 전체 | 수집한 원문에서 만든다 | `make refetch-fulltext && make abox-prior-art` | KIPRIS 키 (+ 비 KR 문헌은 BigQuery) |
| **청구항 feature A-Box** (`ontology/sdkb-abox-claim-features.ttl` · 899 MB) | 파일 전체 | 청구항 텍스트의 파생물이며, 라이선스와 무관하게 배포하기엔 너무 크다 | `make abox-claim-features` | KIPRIS 키 · 수 시간 |
| **선행기술 판단층 A-Box** (`ontology/sdkb-abox-priorart.ttl` · 53 MB) | 파일 전체 | `pa:` 어휘의 ClaimProfile / Disclosure / ExaminerElement. 발행하지 않는 구성 대비표 판정의 파생을 담는다 | `make abox-priorart` | 없음 — 입력이 전부 커밋돼 있다 · 약 30초 |
| **거버넌스 인스턴스** (`ontology/sdkb-governance-*-instances.ttl`) | 없음 — **커밋돼 있다**(2026-08-15) | 커밋된 원천의 빌드 산출물이며 바이트 동일하게 재생성된다 | `make compliance` | 없음 |
| **전문가 프로필·평점** | 없음 | 커밋돼 있다 — **합성 데이터**이고 개인정보를 담지 않는다 | `make expdataset` | 없음 |

마지막 열이 "없음"인 것은 빈 체크아웃에서 그대로 재현된다. 나머지는 본인 키가 필요하다 —
**우리가 줄 수 있는 것은 절차이지 라이선스가 걸린 원문이 아니다.**

**벤더 A-Box 는 특허 A-Box 뒤에 만든다.** `build_abox_vendors_ksia.py` 는 그래프에 이미 있는
조직 노드에 KSIA 회원사를 붙이는데, 그 노드 대부분이 특허 출원인에서 온다. 먼저 돌리면 매칭이
31 → **2** 로 떨어져 IRI 가 갈린다(`organization/asendia_co_ltd` 대 `organization/asendia`).
파일은 만들어지지만 공표된 것과 달라진다. `make pipeline-full` 은 이미 순서가 맞다.

**재현 범위 실측 (2026-08-15 · 깨끗한 클론).**

| | 받은 그대로 | 본인 키로 `refetch-fulltext` 후 |
|---|---|---|
| 역량 질문 | **14/31 = 0.452** (`pa` 1/8) | **27/31 = 0.871** — `em`·`tf`·`core` 전부 1.000 |
| 특허 A-Box | 만들 수 없다 | **33,934 트리플** (논문 스냅샷 33,931 · **0.009 %**) |

0.009 % 차이는 초록을 어디서 읽느냐에서 온다 — 원 수집기는 검색 응답의 `astrtCont` 를 먼저
쓰고 복원 스크립트는 서지만 조회한다. 끝내 복구되지 않는 넷(CQ27·CQ29–31)은 전부 청구항
한정요소 층이며, 그 층의 분해 입력이 청구항 원문 그 자체라 공개할 수 없다. 재수집해도 분해가
언어모델을 쓰므로 바이트 단위로 같아지지는 않는다.

### 역량 질문(CQ)

```bash
make cq      # queries/cq/*.rq 전량 실행 → data/reports/cq_report.json
```

31개 질문은 각자 메타데이터를 갖는다(`# suite:` — `pa` 선행기술 · `em` 전문가매칭 ·
`tf` 기술예측 · `core`). 아직 짓지 않은 A-Box 에 의존하는 질의는 **0행으로 실패**하며,
리포트의 `graph_files_missing` 이 그 파일 이름을 적는다 — 실패가 "온톨로지가 깨졌다"가 아니라
**"무엇을 더 지어야 하는가"** 를 가리키게 하기 위해서다.

### 인터랙티브 시각화 (GitHub Pages)
```bash
make viz       # SDKB → site/ 에 베이스라인 · SIRP · 4-pillar 3개 HTML + index 생성
make viz-open  # 위 + 기본 브라우저로 site/index.html 자동 오픈
```
- 빌드된 `site/`는 `.gitignore` 처리되어 main 브랜치에는 커밋되지 않음
- main에 푸시되면 [.github/workflows/viz-deploy.yml](.github/workflows/viz-deploy.yml)이 자동으로 site/를 재빌드해 GitHub Pages로 배포
- 1회 설정: 레포 **Settings → Pages → Source: GitHub Actions** 선택
- 상세: [docs/project/visualization_plan.md](docs/project/visualization_plan.md)

### 릴리스 서명

`make signature` 가 생성한다 — **아래 블록을 손으로 고치지 마세요.**
원천은 [`data/reports/graph_signature.json`](data/reports/graph_signature.json) 입니다.
(큐레이션 그래프는 2026-05-17 스냅샷 229/268 이후 자랐습니다. 손으로 관리한 수치가
어긋난 것이 이 블록을 코드가 쓰게 만든 이유입니다.)

<!-- sdkb:signature:begin -->
<!-- 이 블록은 `make signature-inject` 가 씁니다. 손으로 고치지 마세요 —
     data/reports/graph_signature.json 이 원천입니다. -->

**T-Box (vocabulary).** Named classes are counted separately from restriction
blank nodes: `grep -c owl:Class` counts both and reports a larger number.

| Module | Classes (named) | (blank) | ObjectProperty | DatatypeProperty | `rdfs:comment` | Triples |
|---|---|---|---|---|---|---|
| `sdkb-core.ttl` | 44 | 13 | 45 | 45 | 134/134 | 722 |
| `sdkb-patent.ttl` | 16 | 6 | 32 | 26 | 74/74 | 467 |
| `sdkb-rbv.ttl` | 9 | 0 | 6 | 3 | 18/18 | 82 |
| `sdkb-foresight.ttl` | 6 | 0 | 6 | 4 | 16/16 | 107 |
| `sdkb-commercialization.ttl` | 7 | 0 | 6 | 4 | 17/17 | 104 |
| `sdkb-governance.ttl` | 0 | 0 | 2 | 1 | 3/3 | 40 |
| `sdkb-governance-kr.ttl` | 3 | 0 | 2 | 2 | 7/7 | 60 |
| `sdkb-priorart-core.ttl` | 13 | 0 | 24 | 9 | 46/46 | 226 |
| `sdkb-priorart-semi.ttl` | 4 | 0 | 0 | 0 | 4/4 | 65 |
| `sdkb-priorart-kr.ttl` | 0 | 0 | 0 | 0 | 0/0 | 40 |
| **Total** | **102** | 19 | **123** | **94** | **319/319** | 1,913 |

**Curation graph** (`data/semiconductor_v0_3.json` — the hand-curated source the core A-Box is generated from).

- **289 nodes / 312 edges** across **16 node types** (version `0.3`)

**A-Box layers.** `not built` is the expected state on a fresh checkout — these layers are generated, and the large ones need a KIPRIS key. See *What is empty, and how to fill it*.

| Layer | Content | Triples |
|---|---|---|
| `sdkb-core-data.ttl` | curation graph, instantiated | 3,019 |
| `sdkb-abox-patents.ttl` | SIRP rejected patents | 34,117 |
| `sdkb-abox-prior-art.ttl` | examiner-cited prior art | 67,123 |
| `sdkb-abox-claim-features.ttl` | claim features | 12,001,973 ¹ |
| `sdkb-abox-b-layer-queries.ttl` | B-layer confirmation queries | 4,631 |
| `sdkb-abox-priorart.ttl` | prior-art claim profiles, disclosures, examiner elements | 796,656 ¹ |
| `sdkb-abox-experts-problems.ttl` | experts and problems | 8,483 |
| `sdkb-abox-vendors.ttl` | equipment vendors | 2,601 |
| `sdkb-governance-kr-instances.ttl` | Korea regulatory instances | 175 |
| `sdkb-governance-us-instances.ttl` | US export-control instances | 105 |

¹ counted by the generator that emitted the layer (`data/reports/`) rather than re-parsed here — the file is too large to re-parse on every signature run. Use `--parse-large` to re-count.

<!-- sdkb:signature:end -->

위 서명이 덮지 않는, 따로 동결된 수치:
- SIRP **1,000 patents** (GT 쌍은 773-코호트 스냅샷에 고정) · 3,118 IPC 링크 · 4,696 prior-art 엣지
- 7,500 examiner-grounded pairs (positive 2,723 + hard-neg 2,723 + easy-neg 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts = **dual-track pool**
- 7,500 examiner-grounded(객관 KIPO 인용) + 7,800 알고리즘 시뮬레이션 3-rater 합성 평점 — **인간 전문가 주석 아님** (dual-track GT). 3-rater 신뢰도: weighted κ = 0.550 / ICC(2,k) = 0.787 (합의); 투명성: Fleiss κ = 0.258 / ICC(2,1) = 0.552 — [data/experts/reliability_report.md](data/experts/reliability_report.md)
- KR + US governance: 20 controls / 205 RDF triples
- SHACL 검증 통과. 테스트 집계는 `make test` 로 확인한다 (손으로 적어 둔
  "75 passed / 10 skipped · OWL 438 triples" 는 낡았다)

## Limitations & Bias

- 공개 문서·규정 임계치 기반이며, 팹별 사유 공정 데이터는 포함하지 않음
- FMEA 인과 관계는 문헌 도출 — 도메인 전문가 검증 필요
- 영어 중심 + 한국어 동의어 보강, 그 외 언어 미지원
- 규제 데이터는 인출 시점 기준 — 월간 갱신 파이프라인 권장
- 합성 전문가 프로필·평점은 비식별 합성이며 실제 인물·기업과 무관

## Citation & Acknowledgement

본 데이터셋은 성균관대학교 기술경영전문대학원 **계량기술경영 연구실 (Quantitative Technology Management Lab, PI: 신준석 교수)** 의 연구 어젠다 — 특허·시장·산업 데이터 기반 기술예측, 유망기술 기회 발굴, 중소기업 혁신 성과 분석, 인터랙티브 기술·비즈니스 데이터 시각화 — 의 반도체 도메인 하부 산출물이다. 향후 동일 연구실에서 작성될 "**컴플라이언스 인지 시맨틱 협업 플랫폼**" 학위논문 및 관련 학술지 게재 논문에서 본 데이터셋을 실증 아티팩트로 인용할 예정이며, 그 시점에 BibTeX를 갱신한다.

```bibtex
@dataset{sdkb_2026,
  title     = {SDKB: Semiconductor Domain Knowledge Base},
  author    = {Park, HyoungSik},
  year      = {2026},
  publisher = {Zenodo},
  version   = {1.1.1},
  doi       = {10.5281/zenodo.22030395},
  url       = {https://doi.org/10.5281/zenodo.22030395}
}
```

DOI 는 두 종류이며 서로 대체되지 않는다. 데이터셋 자체를 가리킬 때는 **concept DOI**
([10.5281/zenodo.22030395](https://doi.org/10.5281/zenodo.22030395))를, 어떤 결과가 산출된 정확한 상태를 가리킬 때는
그 릴리스의 **version DOI** 를 인용한다. version DOI 는 전부 concept 레코드에 열거되며 각각 자신이
잘려 나온 태그를 밝힌다. 선행기술 논문이 보고하는 판은 태그 `v1.1.1-paper` 다.
**이 파일은 version DOI 를 박아 두지 않는다** — 그 번호는 릴리스를 발행할 때 발급되므로, 태그된
트리는 언제나 **직전 번호**밖에 적을 수 없다. `v1.1-paper` 가 스스로를 `SDKB v1.0` 이라 부르고
DOI 를 하나도 담지 못한 원인이 그것이다.

## License

CDLA-Permissive-2.0 (Open Core). Link-Only 레이어는 재배포 대상이 아니다.
자세한 내용은 [LICENSE.txt](LICENSE.txt) 참조.

---

*처음이라면 [docs/README.md](docs/README.md) 부터. 온톨로지를 이해하고 확장하려면 [docs/ontology_guide.md](docs/ontology_guide.md).*
