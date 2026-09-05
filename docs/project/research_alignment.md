# Research Alignment: 계량기술경영 연구실 어젠다 ↘ SDKB 하부 모듈

> 본 문서의 framing: SKKU 기술경영전문대학원 **계량기술경영 연구실(Quantitative Technology Management Lab, PI: 신준석 교수)**의 어젠다가 **상위 frame**이고, SDKB는 그 어젠다 중 **반도체 도메인 데이터·온톨로지 모듈**을 담당하는 **하위 산출물**이다. 본 문서는 그 위계 관계를 명시하고 1:1 매핑으로 추적가능성을 확보한다.

## 0. 연구실 어젠다 (상위 frame)

계량기술경영 연구실은 정량 데이터와 시맨틱 모델링을 결합해 다음 네 축의 연구를 추진한다.

1. **특허·시장·산업 데이터 기반 기술예측 (Tech Foresight)**
2. **유망기술 기회 발굴 (Opportunity Discovery)** — Novelty mapping, 신생기술 5속성, 토픽모델 특허분석
3. **중소기업 혁신 성과 분석 / 전문가 매칭** — SME ↔ 반도체 도메인 전문가 시맨틱 매칭 생태계
4. **인터랙티브 기술·비즈니스 데이터 시각화 (Interactive Visualization)**

보조축으로 **조직적 R&D 관리(RBV/TOE)** 와 **기술가치평가(복합실물옵션)** 가 함께 다루어진다. SDKB는 이 어젠다 전반에 데이터·온톨로지 기반을 공급하는 하부 모듈로 설계된다.

---

## 1. 4-Pillar 매핑 (연구실 어젠다 → SDKB 모듈)

| Pillar | 신 교수 시그니처 방법론 | SDKB 입력 모듈 | 산출 가능한 분석 |
|---|---|---|---|
| **기술전략 (Strategy)** | RBV/TOE 기반 핵심자원 조합 분석 | `sdkb-rbv.ttl`, `data/firms.parquet`, `sdkb-core` | 반도체 fabless 시장진입 핵심자원 조합 도출 |
| **기술예측 (Foresight)** | 특허 기반 기술기회 발굴, 토픽모델 특허분석, 신생기술 5속성 | `sdkb-patent.ttl`, `data/patents.parquet` (CPC/IPC/F-term + 초록) | Novelty-focused 특허 맵, emerging memory 토픽 클러스터 |
| **기술평가 (Valuation)** | 복합실물옵션, TRL 기반 사업가치 평가 | `sdkb-commercialization.ttl`, `sdkb-foresight.ttl` (RealOption 노드) | EUV vs High-NA 로드맵 실물옵션 가치평가 |
| **기술상업화 (Commercialization)** | 시장진입 장벽 분석, BM 설계 | `sdkb-commercialization.ttl`, `sdkb-governance*.ttl` | 소부장 SME 사업화 시나리오, 다중관할 규제 적합성 |

---

## 2. 대표 논문 ↔ 데이터셋 재현성

| 신 교수 대표 연구 | 본 데이터셋으로 재현 가능한 형태 | 출력 위치 |
|---|---|---|
| Lee, Kang, Shin (2015) "Novelty-focused patent mapping for technology opportunity analysis", *TFSC* | 반도체 H01L/H10B 패밀리에서 novelty score 산출 → 기회 클러스터 시각화 | 🚧 `notebooks/02_patent_opportunity_demo.ipynb` (스켈레톤) |
| Shin et al. "A novel approach to forecast promising technology through patent analysis" (TFSC 2017) | 특허 초록 토픽모델로 emerging tech 5속성(novelty/diffusion 등) 추정 | (특허 초록 기반 보강 트랙 — 별도 계획 문서는 제거됨) |
| Cho, Shin (2025) "Expanding the identification of key resource combinations for mid- to long-term growth in EV market entry", *PLoS ONE* | Firm × Resource × Capability 조합 그래프에서 fsQCA-style 핵심자원 조합 도출 | 🚧 `notebooks/03_rbv_resource_combo_demo.ipynb` (스켈레톤, 데이터 대기) |
| Bae, Shin (2022) "Identifying a Combination of Key Resources to Overcome the Entry Barriers in the Electric Vehicle Market", *IEEE Access* | EntryBarrier 노드 + Firm Resource 카드로 반도체 fabless 진입장벽 매핑 | 위 노트북 확장 셀 |
| 신 교수 신생기술 조기식별 5속성 (2025 preprint) | Patent + Topic + Novelty 노드로 5속성 정량 추정 | (후속 학기 알고리즘) |

---

## 3. SDKB-Match 위상 — 연구실 비전의 첫 구현체

SDKB-Match(**SDKB 매칭 응용 계층 — 반도체 소부장 SME↔전문가 / 특허출원↔선행기술 매칭**)은 SDKB의 1차 응용 사례인 동시에, 연구실이 추구하는 **"반도체 전문가 ↔ 중소기업(SME) 시맨틱 매칭 생태계 + 컴플라이언스 인지 시맨틱 협업 플랫폼"** 비전의 첫 구현체이다. 동일한 컴플라이언스-우선 매칭 아키텍처가 (a) 전문가 매칭과 (b) 선행기술 매칭이라는 두 시장을 동시에 겨냥하여, 연구실 어젠다의 영역 ③(SME 혁신·전문가 매칭)과 ①·②(기술예측·기회 발굴)에 동시에 기여한다.

```
                    SDKB (코어 + 거버넌스 + 정렬 4모듈) + SIRP 거절특허 773
                             │
   ┌─────────────────────────┼─────────────────────────┐
   ▼                         ▼                         ▼
SDKB-Match (이중 응용)       특허기회 발굴            RBV 핵심자원 조합 분석
├ Expert (HR/컨설팅)      (Novelty mapping)         (fabless 시장진입)
└ PriorArt (IP-R&D)
   │
   ▼
실물옵션 가치평가 (2026-2 이후)
```

| 트랙 | 쿼리 | 후보 풀 | 라벨 |
|---|---|---|---|
| Expert | 기술 문제 50건 + 규제 시나리오 25 | 합성 전문가 100명 | 합성 (LLM 라벨러) + 표본 인간검증 |
| PriorArt | 거절특허 773건 | 동일 코호트 + IPC 인접 풀 | **examiner-grounded GT (실 라벨)** |

---

## 4. 인터랙티브 시각화 트랙 — 연구실 영역 ④와의 연결

연구실의 핵심 관심 영역 중 하나인 **인터랙티브 기술·비즈니스 데이터 시각화**는 2026-1 학기에 **베이스라인 3-뷰가 GitHub Pages로 배포되며**, 후속 학기에 의미적 게이트와 매칭 익스플로러로 확장된다.

### 4.1 본 학기 배포 (2026-1, 라이브)

| 뷰 | 입력 모듈 | 산출물 |
|---|---|---|
| ① Baseline core ontology — 198노드 / 268엣지, 14타입 컬러링 | `data/semiconductor_v0_3.json` | `site/baseline.html` |
| ② SIRP patent ↔ examiner-cited prior art (상위 50특허) | `data/patents/*.parquet` | `site/sirp.html` |
| ③ 4-pillar class skeleton — patent / rbv / commercialization / foresight | `ontology/sdkb-*.ttl` | `site/pillars.html` |

빌더 = `scripts/build_viz.py` · 배포 = `.github/workflows/viz-deploy.yml`. URL = [https://arkwith7.github.io/sdkb-dataset/](https://arkwith7.github.io/sdkb-dataset/). 운영 가이드: [docs/project/visualization_plan.md](visualization_plan.md).

### 4.2 후속 학기 확장 (2026-2)

| 시각화 산출 | 도구 후보 | SDKB 입력 |
|---|---|---|
| Novelty-focused patent map 인터랙션 (zoom·필터) | Plotly Dash 또는 Streamlit | patent + Topic/Novelty (특허 초록 enrichment 후) |
| SME ↔ 전문가 매칭 결과 익스플로러 + SHACL 게이트 통과/누수 표시 | Streamlit | core + governance + curated experts |
| RBV 핵심자원 조합 fsQCA 결과 시각화 | NetworkX/Plotly | rbv + firms |
| 실물옵션 의사결정 트리 (EUV vs High-NA) | Plotly/D3 | foresight + commercialization |

이로써 연구실 어젠다 ①–④ 전 영역이 SDKB 트렁크 위에서 인터랙티브하게 노출되는 길이 열렸다.

---

## 5. 인력양성 사업과의 연계 (참고)

| 항목 | 연계 가능 산출물 |
|---|---|
| 사업명 | 글로벌첨단전략산업기술경영전문인력양성 (2025.2–2030.2) |
| 교육 활용 | 본 데이터셋 + 노트북 3종을 MOT 대학원 강의 실습 교재로 |
| 연구 활용 | sdkb-patent / sdkb-rbv 모듈을 사업 산하 학위논문의 데이터 기반으로 |
| 정책 활용 | 한국 산업기술보호법 거버넌스 노드를 정부 자문 분석의 입력으로 |

---

## 6. 갱신 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-12 | v1.0 | 초안 작성 |
| 2026-05-12 | v1.1 | SDKB-Match 이중 응용(Expert/PriorArt) 반영 |
| 2026-05-12 | v1.2 | Framing 반전 — "연구실 어젠다 상위 frame ↘ SDKB 하부 모듈" 위계 명시, 영역 ④ 인터랙티브 시각화 트랙 추가 |
| 2026-05-13 | v1.3 | 노트북 02/03을 스켈레톤 stub으로 명시 (📋 dead-link → 🚧 skeleton), 노트북 03은 정렬 트랙 데이터 의존성 표기 |
| 2026-09-05 | v1.4 | **§7 신설** — 지도교수 공개 프로파일(대학원 교수소개 페이지)을 전거로 확보하고, §2 의 미확인 인용 셋을 표시. 현 작업(PLAN-005)과 직접 맞물리는 연구선 셋을 추가 |

---

## 7. 지도교수 연구 프로파일 — 전거와 접점 (2026-09-05 추가)

> **전거.** 성균관대학교 기술경영전문대학원 **교수소개 > 전임교수** 페이지(공개). 이 절의
> 논문·경력 목록은 그 페이지에서 옮긴 것이며, 이 저장소가 새로 산출한 사실이 아니다.
> **이 문서는 공개 발행 대상이 아니다** — `build_public_release.py` 의 허용목록(`ALLOW_DOCS`)에
> 없으므로 `sdkb-dataset` 에 나가지 않는다(확인: `is_allowed("docs/project/...") == False`).

| | |
|---|---|
| 성명 · 소속 | **신준석** 교수 · 성균관대학교 기술경영전문대학원 (기술경영 MOT) |
| 연락 | jsshin@skku.edu · 제2공학관(27동) 4층 27418B |
| 학력 | 서울대학교 산업공학과 (B.S. · M.S. · Ph.D.) |
| 관심분야 | Corporate foresight · Technology strategy · Business model · Portfolio management · Innovation design & management · Organizational management of R&D · **Interactive visualization of technology & business data** |
| 주요 경력 | Visiting Professor, FIT Chair, EDHEC(France, 2023) · 현대자동차 IFAT 기술전략 자문(2020–2022) · CJ제일제당 기술기획 자문(2022) · 삼성전자 DMC연구소 기술경영 자문(2013–2015) · 삼성경제연구소 기술산업실 연구원(2007–2008) |

### 7.1 먼저 정정할 것 — §2 의 인용 셋이 전거로 확인되지 않는다

**§2 표에 적힌 아래 셋은 위 공개 목록에 없다.** 다른 출처가 있을 수 있으나 **이 저장소는 확인
전까지 확정 사실로 쓰지 않는다**(CLAUDE.md §1-4).

| §2 의 표기 | 상태 |
|---|---|
| Lee, Kang, Shin (2015) *"Novelty-focused patent mapping…"*, TFSC | **전거 미확인** |
| Shin et al. *"A novel approach to forecast promising technology through patent analysis"* (TFSC 2017) | **전거 미확인** — 공개 목록의 2017 TFSC 논문은 *"Technology opportunity discovery to R&D planning: Key technological performance analysis"* 다 |
| 신생기술 조기식별 5속성 (2025 preprint) | **전거 미확인** |

§2 의 나머지 둘(PLOS ONE 2025 자원조합 · IEEE Access 2022 진입장벽)은 공개 목록과 정합한다
(PLOS ONE 2025 는 *"Expanding the identification of key resource combinations for mid- to
long-term growth in electric vehicle market entry"*). **§2 본문은 고치지 않고 이 표로 표시만
한다** — 확인 경로가 나오면 그때 갱신한다.

### 7.2 현 작업(PLAN-005)과 직접 맞물리는 연구선 셋 — §1 4-Pillar 가 놓친 것

§1 은 어젠다를 네 기둥으로 갈랐으나, **지금 진행 중인 선행기술 온톨로지 재구성과 가장 가까운
것은 그 표에 없는 셋이다.**

| # | 지도교수 연구 | 이 저장소의 대응물 | 왜 지금 중요한가 |
|---|---|---|---|
| **①** | **(2021) 공진화 분석기반 기술 인텔리전스: 반도체 패키지공정 사례**, 기술혁신연구 28(4) | `data/patents/**` · `mappings/concept_mapping.json` | **같은 도메인(반도체)·같은 원천(특허)** 의 선례다. SDKB 가 *"반도체 도메인 기술 인텔리전스"* 라는 연구선의 데이터 기반이라는 위계(§0)를 문헌으로 뒷받침하는 유일한 항목 |
| **②** | **(2018) Mapping extended technological trajectories: main path, derivative paths, technology junctures**, SCIENTOMETRICS 116(3) · **(2019) Extending technological trajectories to latest technological changes by overcoming time lags**, TFSC 143 | `data/patents/prior_art_edges.parquet` (6,692 엣지 · 심사관 2,534) · PLAN-003 E1 `SemanticPathRecall` | **둘 다 특허 인용 네트워크 위의 경로 분석**이다. PLAN-005 §5 V2 가 재는 것도 *"의미 경로가 목표에 도달하는가"* 이며, main-path 계열과 **문제 형식이 같다**. 현 실측(도달 92.9%인데 `\|Reach\|` 중앙 11,348)은 *경로가 없어서*가 아니라 *경로가 무차별해서* 실패한다는 뜻이고, 이는 main-path 문헌이 다루는 전형적 문제다 |
| **③** | **(2020) 잠재적 후보기술 경로 탐색방법: 바이오 연료 사례**, 기술혁신연구 28(3) | **PLAN-005 §5 V6a**(바이오 소코호트 실물 이식) | **경로 탐색 방법을 반도체가 아닌 도메인(바이오)에 적용한 선례**다. V6a 가 주장하려는 *"방법은 도메인을 넘어간다"* 와 같은 형태의 주장을 지도교수 연구선이 이미 한 번 했다는 뜻이고, **V6a 의 설계 근거로 인용할 수 있다** |

**②가 특히 실무적이다.** 현 V2 결과의 병목은 *분별력*이며, main-path 분석이 쓰는 장치(엣지
가중·경로 특이도·계층 절단)가 PLAN-001 §1.3 의 경로 가중·§1.4-6 의 개념 IDF 와 같은 자리를
겨냥한다. **PLAN-001 3단계 설계에서 참고할 문헌선이다.**

### 7.3 관심분야 ↔ 저장소 모듈 대조 (전거의 7개 항목 전부)

| 관심분야 | 저장소 대응물 | 상태 |
|---|---|---|
| Corporate foresight | `ontology/sdkb-foresight.ttl` (STEEPVE 7축 · 실물옵션 5종) | 어휘만 · 태스크 인스턴스 0 (PLAN-004 C-3) |
| Technology strategy | `ontology/sdkb-rbv.ttl` (`Firm`·`Resource`·`Capability`·`ResourceCombination`·`EntryBarrier`·`vrioValue`) | 어휘 존재 |
| Business model / 상업화 | `ontology/sdkb-commercialization.ttl` (TRL 1–9) | 어휘 존재 |
| Portfolio management | `queries/cq/CQ08_applicant_process_portfolio.rq` · `CQ21_process_hierarchy_portfolio.rq` | 질의 존재 |
| Innovation design & management | — | 대응물 없음 |
| Organizational management of R&D | `ont:Expert`·`ExpertCase` 계열 (전문가 매칭 뷰) | **A-Box 합성** (PLAN-004 C-3 · 1/3) |
| **Interactive visualization** | `scripts/build_viz.py` · `site/` | §4 트랙에 이미 있음 |

**대응물이 없는 것과 A-Box 가 비어 있는 것을 함께 적는다** — 표를 채우는 것이 목적이 아니라
**무엇이 아직 없는지**가 다음 작업의 입력이기 때문이다.
