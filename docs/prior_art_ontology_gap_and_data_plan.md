# 거절특허 데이터셋 → 선행기술조사용 온톨로지 기여: 갭 분석 및 추가 데이터 수집 가이드

> **문서 버전**: v1.0 (2026-05-16)
> **작성자**: SDKB 프로젝트 팀
> **상태**: 활성 — 실측 기반 갭 분석/실행 가이드
> **관련 문서**:
> - [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md) — SIRP 데이터셋 카드(출처·구성·한계)
> - [`patent_taxonomy_integration_plan.md`](patent_taxonomy_integration_plan.md) — CPC/IPC/F-term 정렬 계획
> - [`patent_abstract_enrichment_plan.md`](patent_abstract_enrichment_plan.md) — 초록 기반 NER/RE 온톨로지 보강 계획
> - 산출물: [`notebooks/07_sparql_prior_art_ontology.ipynb`](../notebooks/07_sparql_prior_art_ontology.ipynb) (온톨로지 선행기술 검색), [`notebooks/04_prior_art_baseline.ipynb`](../notebooks/04_prior_art_baseline.ipynb) (TF-IDF floor), [`scripts/build_abox_patents.py`](../scripts/build_abox_patents.py), [`scripts/sdkb_nb.py`](../scripts/sdkb_nb.py)

---

## 1. 목적과 범위

본 문서는 **SIRP 거절특허 데이터셋(773건)이 "선행기술조사용 온톨로지"에 실제로 기여하려면 무엇을 보완하고 어떤 데이터를 추가 수집해야 하는지**를, 노트북 07/04 실측에 근거해 우선순위와 함께 가이드한다.

- *아닌 것*: 신규 정렬 절차(→ 택소노미 통합 계획) 또는 LLM NER/RE 보강 절차(→ 초록 보강 계획)의 재서술.
- *맞는 것*: 위 두 계획과 데이터셋 카드를 **선행기술 검색 성능 관점에서 묶는 갭·수집 가이드**. 즉 "왜 지금은 입증이 안 되는가 → 무엇을 채우면 입증 가능한가 → 어떻게 채우는가 → 어떻게 합격 판정하는가".

---

## 2. 근거 — 이번 평가에서 측정된 사실

| 사실 | 수치/출처 | 함의 |
|---|---|---|
| examiner 인용이 corpus 밖 | positive pair 0% in-corpus (`prior_art_pairs.parquet`), edges 0% in-corpus (`prior_art_edges.parquet`) | **진짜 선행기술 검색력 측정 불가** — 가장 큰 공백 |
| IPC-4 프록시는 어휘기반에 유리 | IPC는 동일 텍스트에서 부여 → TF-IDF와 신호원 동일 | 현재 비교는 온톨로지에 구조적으로 불리(과소평가) |
| 스코프 미스매치 | 제목 휴리스틱: device성 386 / process성 133 / 기타 283 (`/773`); orphan의 ~88%가 소자·제품 특허 | 온톨로지가 *단위공정·소재·장비* 중심 → 소자/제품 특허는 노드 부재로 구조적 미커버 |
| lift 커버리지(개선 후) | 링크 616/773, orphan 157, 노드/특허 mean 2.25 (`abox_patents_linking_report.json`, morph+claim1+별칭) | 공학적 개선으로 손실↓ 했으나 스코프 천장은 못 넘음 |
| 구조화 분류 미사용 | 메타에 `process_family`(etch 231·deposition 135·oxidation_diffusion 47·photo 46·implant 38…), `value_chain`(process\|equipment 230, process\|device 90…) 존재하나 브리지는 텍스트만 사용 | **가장 값싼 미활용 신호** |
| 검색 비교(IPC-4 프록시, 04 동일 코드) | TF-IDF MRR 0.5377 / NDCG@5 0.2172 ; 온톨로지 0.3649 / **0.2506** / n=50 | NDCG@5만 floor 추월. 단독 랭커로는 미입증 |

→ 결론: 데이터셋이 *지금* 온톨로지에 기여하지 못하는 1차 원인은 NLP가 아니라 **(a) 검증 불가능한 정답 구조, (b) 온톨로지 스코프-모집단 불일치, (c) 이미 가진 구조화 분류 미활용** 이다.

---

## 3. 갭 분석

### A. 온톨로지/스키마 보완 (코드·스키마 측)

| # | 보완 항목 | 무엇을 / 왜 | 검증(수용 기준) |
|---|---|---|---|
| A1 | **구조화 필드 브리지** | `process_family`/`value_chain`를 결정적으로 온톨로지 노드에 매핑(텍스트 NLP 불필요). etch→`process:etch`, deposition→`process:deposition`, oxidation_diffusion→`process:diffusion`, photo→`process:lithography`, implant→`process:implant` 등 ~6패밀리로 ~500건 고정밀 링크. metallization은 노드 결정 필요, memory/general은 스코프 외로 라벨링 | orphan ↓(목표 <100), 노드/특허 mean ↑, 링크 정밀도 수기표본 ≥0.95 |
| A2 | **소자/제품 계층 노드 추가** | 현재 노드 타입엔 Device/Product/Architecture 부재. memory cell·transistor(FinFET/GAA)·display·LED·packaging 등 상위 클래스 + `device:* HAS_PROCESS process:*` 엣지 신설. orphan의 ~88%가 여기 해당 | 스코프 커버리지(아래 §5) +0.2 이상, device성 386건 중 링크율 측정 |
| A3 | **거절사유/청구항 계층** | 선행기술조사 핵심은 "왜 거절(신규성/진보성)되었나". `rejection_reason`·독립청구항 한정요소를 노드/속성화하여 `patent NOT_NOVEL_OVER cited`, `claim HAS_FEATURE concept` 표현 | 거절사유 보유 특허에서 사유→개념 매핑 커버리지 ≥0.7 |
| A4 | **동의어/한국어 표면형 확장** | KG 동의어 86개 → 부족. `mappings/abox_term_aliases.json` 한국어 블록을 `top_unmatched` 빈도순으로 지속 확장; 약어·영문 병기(괄호 안 영문)·복합어 분해 규칙 강화 | 동일 corpus에서 신규 매칭 distinct term 증가, orphan ↓ |
| A5 | **IPC/CPC 앵커 노드** | IPC-4(47클래스)·CPC를 1급 노드로 두고 `patent HAS_IPC ipc:*`, `ipc:* MAPS_TO process:*` 정렬(택소노미 통합 계획과 접속) → 스코프 라우팅·프록시 GT 품질 동시 개선 | IPC↔Process 정렬 표 작성, 프록시를 IPC-4→CPC-subgroup으로 정밀화 |
| A6 | **가중·제약 신호 활용** | 현재 overlap은 비가중 정수. 개념 IDF(희소 개념 가중)·엣지 `ont:confidence`·`INCOMPATIBLE_WITH`/`NOT_ALLOWED_WITH` 제약을 랭킹에 반영 | 동일 GT에서 MRR/NDCG 개선 폭(앞 비가중 대비) 보고 |

### B. 추가 데이터 수집 (데이터 측)

| # | 수집 항목 | 무엇을 / 왜 | 검증(수용 기준) |
|---|---|---|---|
| B1 | **인용 외부특허 본문 (최우선·P0)** | examiner가 인용한 JP/US/KR 외부특허의 제목·초록·대표청구항 수집 → cited 특허를 corpus에 편입. 이게 있어야 **진짜 선행기술 정답(MRR/Recall) 측정** 가능. 현재 0% in-corpus가 모든 평가를 막는 단일 병목 | examiner cited의 corpus 편입률 ≥0.7, 그 위에서 07/04를 *실 인용 GT*로 재측정 가능 |
| B2 | **거절사유 텍스트/구조화** | 의견제출통지서·거절결정의 거절근거(신규성 §29①, 진보성 §29②)·대비 인용발명·대비 청구항. A3의 입력 | 거절사유 구조화 레코드 ≥600/773 |
| B3 | **전체 청구항 + 독립항 한정요소** | 현재 `claim1`만 보유(평균 300자). 독립청구항 전체·종속 구조 → 한정요소 단위 매칭(선행기술 판단의 실제 단위) | claim 전체 보유율 ≥0.9, 한정요소 파싱 파일럿 |
| B4 | **소자/제품 도메인 어휘 소스** | A2 신설 노드의 동의어·계층을 채울 외부 소스(IEEE/IRDS device 용어, JEDEC, 위키데이터 device class, 한국어 표준용어) | device 노드별 한/영 동의어 ≥5, A2 링크율 실측 |
| B5 | **특허패밀리·법적상태·인용 네트워크** | INPADOC family, 등록/거절 확정, forward/backward citation. 동일 발명 다국적 패밀리로 B1 in-corpus율↑, 인용망은 그래프 확장(`CITES`) 신호 | family 매핑률, citation 엣지 수, 인용망 추가 후 incremental recall |
| B6 | **어휘 미스 로그 피드백 루프** | 빌더가 `top_unmatched`(빈도순)와 orphan 사유를 리포트 → 주기적으로 A4/A2에 환류하는 운영 절차 | 리포트 기반 분기별 별칭/노드 추가가 orphan을 단조 감소시키는지 |

---

## 4. 우선순위 로드맵

| 우선 | 항목 | 노력 | 기대 효과 | 1차 지표 |
|---|---|---|---|---|
| **P0** | B1 인용 외부특허 본문 | 중(수집 파이프라인) | 평가 가능성 자체를 확보 — *결정적* | examiner cited in-corpus ≥0.7 |
| **P0** | A1 구조화필드 브리지 | 소(결정적 매핑) | orphan↓, 정밀도↑, 즉시 적용 가능 | orphan <100, 정밀도≥0.95 |
| **P1** | A2 소자/제품 계층 + B4 어휘 | 중 | 스코프 천장 상향(모집단의 절반) | 스코프 커버리지 +0.2 |
| **P1** | A6 가중/제약 랭킹 | 소~중 | MRR/NDCG 개선(인프라 기존) | 동일 GT 개선폭 |
| **P1** | A5 IPC/CPC 앵커 + 프록시 정밀화 | 중 | 평가 편향 완화 | IPC-4→CPC subgroup 프록시 |
| **P2** | A3 거절사유/청구항 + B2/B3 | 대 | 진짜 선행기술 판단 단위 | 사유→개념 커버리지≥0.7 |
| **P2** | B5 패밀리/인용망, B6 피드백루프 | 중 | recall 확장·운영 지속성 | incremental recall, orphan 추세 |

---

## 5. "기여한다"의 합격 판정 지표

단일 MRR 수치가 아니라 **4축**으로 판정한다(노트북 07 §3·Notes와 일관):

1. **실 인용 검색력 (B1 선행)**: examiner 인용을 GT로 한 MRR/NDCG@5/Recall@{10,50}. *floor와의 절대 비교는 B1 완료 후에만 유효.*
2. **보완성(incremental recall)**: `Recall(TF-IDF ∪ 온톨로지) − Recall(TF-IDF)` > 0, 특히 *어휘적으로 비유사한* 인용에서. 도메인 온톨로지의 본질 가치 축.
3. **스코프 커버리지**: 대상 특허 모집단 중 온톨로지 스코프 내 비율 및 그 부분집합에서의 검색력. NLP·별칭과 독립한 구조적 가능성 천장.
4. **설명 정밀도/실무 유용성**: 공유 개념이 실제 기술 중첩인지 전문가 소표본 채점, 후보 선별 시간 단축. floor가 못 주는 고유 가치.

> 기여 인정 기준(권고): **(1)에서 floor 대비 비열세 + (2)>0 + (3) 공정계열에서 ≥0.8 + (4) 설명 정밀도 ≥0.7**. 단독 랭커 우위가 아니라 *보완+설명* 입증이 현실적 목표.

---

## 6. 즉시 실행 가능한 Quick Win (P0/A1, 코드 변경 소규모)

`scripts/build_abox_patents.py`는 현재 title+abstract+claim1 텍스트만 본다. 메타의 **`process_family`** 는 큐레이터가 부여한 결정적 분류이므로 텍스트 추출과 *별도로* 다음 매핑을 추가하면 즉시 고정밀 링크가 늘어난다:

```
process_family → ontology
  etch                → process:etch
  deposition          → process:deposition
  oxidation_diffusion → process:diffusion
  photo               → process:lithography
  implant             → process:implant
  metallization       → (노드 결정 필요: process:deposition 또는 신규 metallization 노드)
  memory / general    → (스코프 외 라벨 — orphan 사유로 기록, A2 대상)
```

- 적용: 빌더에 `concernsProcess`(결정적) 엣지를 `process_family` 매핑으로 추가, `value_chain`에 `device` 포함 시 `scope_out` 플래그를 리포트에 기록.
- 기대: orphan의 상당수가 "텍스트 미스"가 아니라 "스코프 외"임을 *데이터로 분리* → §5-(3) 스코프 커버리지를 정직하게 산출, 공정계열 링크 정밀도 상승.
- 검증: 재빌드 후 `abox_patents_linking_report.json`의 orphan/노드분포 + 수기표본 정밀도, 노트북 07 §3 재측정.

---

## 7. 관련 산출물 매핑

| 보완/수집 | 닿는 산출물 |
|---|---|
| A1·A6 | [`scripts/build_abox_patents.py`](../scripts/build_abox_patents.py), [`scripts/sdkb_nb.py`](../scripts/sdkb_nb.py) |
| A4 | [`mappings/abox_term_aliases.json`](../mappings/abox_term_aliases.json) (`_KO`/`_KO2` 블록) |
| A2·A3 | `data/semiconductor_v0_3.json`(노드/엣지), `ontology/sdkb-patent.ttl` |
| A5 | [`patent_taxonomy_integration_plan.md`](patent_taxonomy_integration_plan.md) |
| B1·B2·B3·B5 | [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md)(수집 절차·한계 갱신 대상) |
| B4 | [`patent_abstract_enrichment_plan.md`](patent_abstract_enrichment_plan.md)(NER/RE·외부 어휘 소스) |
| 평가(§5) | [`notebooks/07_sparql_prior_art_ontology.ipynb`](../notebooks/07_sparql_prior_art_ontology.ipynb), [`notebooks/04_prior_art_baseline.ipynb`](../notebooks/04_prior_art_baseline.ipynb) |

---

### 한 줄 요약

> 거절특허 데이터셋이 선행기술 온톨로지에 기여하려면, **(P0) 인용 외부특허 본문을 수집해 평가 자체를 가능케 하고, 이미 보유한 `process_family`/`value_chain` 구조화 분류를 결정적으로 브리지**하는 것이 최우선이다. 그다음 소자/제품 계층·거절사유 계층을 보강하고, 성능은 *단독 우위*가 아니라 *보완성·스코프 커버리지·설명 정밀도*의 4축으로 판정한다.
