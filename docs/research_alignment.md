# Research Alignment: 신준석 교수 4-Pillar ↔ SDKB 모듈

> 본 문서는 SDKB가 지도교수 신준석 교수(SKKU 기술경영전문대학원, 계량기술경영연구실)의 연구 방향에 어떻게 정렬되는지를 1:1로 매핑한다. `plan_amendment_v1.md` 와 함께 읽는다.

---

## 1. 4-Pillar 매핑

| Pillar | 신 교수 시그니처 방법론 | SDKB 입력 모듈 | 산출 가능한 분석 |
|---|---|---|---|
| **기술전략 (Strategy)** | RBV/TOE 기반 핵심자원 조합 분석 | `sdkb-rbv.ttl`, `data/firms.parquet`, `sdkb-core` | 반도체 fabless 시장진입 핵심자원 조합 도출 |
| **기술예측 (Foresight)** | 특허 기반 기술기회 발굴, 토픽모델 특허분석, 신생기술 5속성 | `sdkb-patent.ttl`, `data/patents.parquet` (CPC/IPC/F-term + 초록) | Novelty-focused 특허 맵, emerging memory 토픽 클러스터 |
| **기술평가 (Valuation)** | 복합실물옵션, TRL 기반 사업가치 평가 | `sdkb-commercialization.ttl`, `sdkb-foresight.ttl` (RealOption 노드) | EUV vs High-NA 로드맵 실물옵션 가치평가 |
| **기술상업화 (Commercialization)** | 시장진입 장벽 분석, BM 설계 | `sdkb-commercialization.ttl`, `docs/commercialization_strategy_v1.md`, `sdkb-governance*.ttl` | 소부장 SME 사업화 시나리오, 다중관할 규제 적합성 |

---

## 2. 대표 논문 ↔ 데이터셋 재현성

| 신 교수 대표 연구 | 본 데이터셋으로 재현 가능한 형태 | 출력 위치 |
|---|---|---|
| Lee, Kang, Shin (2015) "Novelty-focused patent mapping for technology opportunity analysis", *TFSC* | 반도체 H01L/H10B 패밀리에서 novelty score 산출 → 기회 클러스터 시각화 | `notebooks/02_patent_opportunity_demo.ipynb` |
| Shin et al. "A novel approach to forecast promising technology through patent analysis" (TFSC 2017) | 특허 초록 토픽모델로 emerging tech 5속성(novelty/diffusion 등) 추정 | (계획문서: `docs/patent_abstract_enrichment_plan.md`) |
| Cho, Shin (2025) "Expanding the identification of key resource combinations for mid- to long-term growth in EV market entry", *PLoS ONE* | Firm × Resource × Capability 조합 그래프에서 fsQCA-style 핵심자원 조합 도출 | `notebooks/03_rbv_resource_combo_demo.ipynb` |
| Bae, Shin (2022) "Identifying a Combination of Key Resources to Overcome the Entry Barriers in the Electric Vehicle Market", *IEEE Access* | EntryBarrier 노드 + Firm Resource 카드로 반도체 fabless 진입장벽 매핑 | 위 노트북 확장 셀 |
| 신 교수 신생기술 조기식별 5속성 (2025 preprint) | Patent + Topic + Novelty 노드로 5속성 정량 추정 | (후속 학기 알고리즘) |

---

## 3. AFCP-EM 위상 (Amendment v2 이후)

AFCP-EM(**Agent-First Compliance Platform — Expert/PriorArt Matching**)은 본 데이터셋의 **1차 응용 사례 두 트랙**이다. 동일한 컴플라이언스-우선 매칭 아키텍처가 (a) 전문가 매칭과 (b) 선행기술 매칭이라는 두 시장을 동시에 겨냥한다.

```
                    SDKB (코어 + 거버넌스 + 정렬 4모듈) + SIRP 거절특허 773
                             │
   ┌─────────────────────────┼─────────────────────────┐
   ▼                         ▼                         ▼
AFCP-EM (이중 응용)       특허기회 발굴            RBV 핵심자원 조합 분석
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

## 4. 인력양성 사업과의 연계 (참고)

| 항목 | 연계 가능 산출물 |
|---|---|
| 사업명 | 글로벌첨단전략산업기술경영전문인력양성 (2025.2–2030.2) |
| 교육 활용 | 본 데이터셋 + 노트북 3종을 MOT 대학원 강의 실습 교재로 |
| 연구 활용 | sdkb-patent / sdkb-rbv 모듈을 사업 산하 학위논문의 데이터 기반으로 |
| 정책 활용 | 한국 산업기술보호법 거버넌스 노드를 정부 자문 분석의 입력으로 |

---

## 5. 갱신 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-12 | v1.0 | 초안 작성 (`plan_amendment_v1.md` 와 동시 도입) |
| 2026-05-12 | v1.1 | AFCP-EM 이중 응용(Expert/PriorArt) 반영 — `plan_amendment_v2.md` 동시 도입 |
