# Research Alignment: 계량기술경영 연구실 어젠다 ↘ SDKB 하부 모듈

> 본 문서의 framing: SKKU 기술경영전문대학원 **계량기술경영 연구실(Quantitative Technology Management Lab, PI: 신준석 교수)**의 어젠다가 **상위 frame**이고, SDKB는 그 어젠다 중 **반도체 도메인 데이터·온톨로지 모듈**을 담당하는 **하위 산출물**이다. 본 문서는 그 위계 관계를 명시하고 1:1 매핑으로 추적가능성을 확보한다. `plan_amendment_v1.md` 와 함께 읽는다.

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
| **기술상업화 (Commercialization)** | 시장진입 장벽 분석, BM 설계 | `sdkb-commercialization.ttl`, `docs/project/commercialization_strategy_v1.md`, `sdkb-governance*.ttl` | 소부장 SME 사업화 시나리오, 다중관할 규제 적합성 |

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

빌더 = `scripts/build_viz.py` · 배포 = `.github/workflows/viz-deploy.yml`. URL = [https://arkwith7.github.io/semiconductor-knowledge-base/](https://arkwith7.github.io/semiconductor-knowledge-base/). 운영 가이드: [docs/project/visualization_plan.md](visualization_plan.md).

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
| 2026-05-12 | v1.0 | 초안 작성 (`plan_amendment_v1.md` 와 동시 도입) |
| 2026-05-12 | v1.1 | SDKB-Match 이중 응용(Expert/PriorArt) 반영 — `plan_amendment_v2.md` 동시 도입 |
| 2026-05-12 | v1.2 | Framing 반전 — "연구실 어젠다 상위 frame ↘ SDKB 하부 모듈" 위계 명시, 영역 ④ 인터랙티브 시각화 트랙 추가 |
| 2026-05-13 | v1.3 | 노트북 02/03을 스켈레톤 stub으로 명시 (📋 dead-link → 🚧 skeleton), 노트북 03은 정렬 트랙 데이터 의존성 표기 |
