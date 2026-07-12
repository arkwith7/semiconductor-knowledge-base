# 거절특허 데이터셋 → 선행기술조사용 온톨로지 기여: 갭 분석 및 추가 데이터 수집 가이드

> **문서 버전**: v1.0 (2026-05-16)
> **작성자**: SDKB 프로젝트 팀
> **상태**: 활성 — 실측 기반 갭 분석/실행 가이드
> **관련 문서**:
> - [`dataset_rejected_patents_card.md`](../dataset_rejected_patents_card.md) — SIRP 데이터셋 카드(출처·구성·한계)
> - CPC/IPC/F-term 정렬 — 별도 계획 문서는 제거됨 (절차는 `mappings/` SDKB-centric 패턴으로 흡수)
> - 초록 기반 NER/RE 온톨로지 보강 — 별도 계획 문서는 제거됨
> - 산출물: [`notebooks/07_sparql_prior_art_ontology.ipynb`](../../notebooks/07_sparql_prior_art_ontology.ipynb) (온톨로지 선행기술 검색), [`notebooks/04_prior_art_baseline.ipynb`](../../notebooks/04_prior_art_baseline.ipynb) (TF-IDF floor), [`scripts/build_abox_patents.py`](../../scripts/build_abox_patents.py), [`scripts/sdkb_nb.py`](../../scripts/sdkb_nb.py)

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
| 구조화 분류 ~~미사용~~ → **활용 완료** | 메타 `process_family`/`value_chain`를 결정적 브리지로 사용(§6). 링크 90.8%, orphan 71로 ↓ | 가장 값싼 신호 — 적용됨 |
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
| **P0** | B1 인용 외부특허 본문 | 중(수집 파이프라인) | 평가 가능성 자체를 확보 — *결정적* · **미착수(다음 최우선)** | examiner cited in-corpus ≥0.7 |
| ~~P0~~ | A1 구조화필드 브리지 | 소 | ✅ **완료(§6)**: 링크 90.8%, orphan 71(scope_out 48/text_miss 23) | orphan<100 달성 |
| **P1** | A2 소자/제품 계층 + B4 어휘 | 중 | 스코프 천장 상향(scope_out 48건이 직접 대상) | 스코프 커버리지 +0.2 |
| ~~P1~~ | A6 가중/제약 랭킹 | 소~중 | ✅ **완료(§6)**: IDF 가중, MRR 0.29→0.32 부분회복(floor 미달) | 동일 GT 개선폭 |
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

## 6. P0/A1 구조화 필드 브리지 — **구현 완료 + 측정 결과 (2026-05-16)**

`scripts/build_abox_patents.py`에 `process_family` 결정적 매핑(`PROCESS_FAMILY_MAP`)과 `value_chain` 스코프 분리를 구현했다(텍스트 추출과 UNION):

```
process_family → ontology  (구현된 PROCESS_FAMILY_MAP)
  etch                            → process:etch
  deposition/metallization/
    interconnect/gate_dielectric  → process:deposition
  oxidation_diffusion/oxidation/
    thermal                       → process:diffusion
  photo                           → process:lithography
  implant                         → process:implant
  memory*/packaging/mems/
    components/image_sensor/
    3d_integration                → SCOPE_OUT (노드 없음 — A2 대상)
```

**결과 (정직):**

| 지표 | 텍스트만 | **+구조화 브리지** |
|---|---|---|
| 링크 특허 | 616/773 | **702/773 (90.8%)** |
| orphan | 157 | **71** → scope_out 48 / **text_miss 23** |
| 노드/특허 mean | 2.25 | **2.66** |
| §3 평가 커버리지 n | 50 | **60 (전수)** |

- ✅ **커버리지·진단은 성공**: orphan을 *데이터로* scope_out(48, 소자계층 부재 — A2 필요, 버그 아님) vs text_miss(23, 실제 수정가능: general 19·materials 3·equipment 1)로 분리. §5-(3) 스코프 커버리지가 정직하게 산출됨.
- ❌ **랭킹은 후퇴**(IPC-4 프록시, 노트북 07 §3): MRR 0.3649→**0.2914**. 거친 Process 노드(`process:etch` 등)가 ~584건에 부여되어 비가중 overlap 변별력이 떨어지는 *예견된* 트레이드오프 → **A6 동기를 데이터로 입증**.

### A6 (개념 IDF 가중) — 구현 완료 + 결과

비가중 `COUNT DISTINCT` 대신 corpus IDF(`log(N/df)`)로 공유 개념을 가중(`rank_ontology_idf`, 노트북 07 §3):

| (IPC-4 프록시, n=60) | MRR | NDCG@5 | Recall@50 |
|---|---|---|---|
| 04 floor (TF-IDF) | 0.5377 | 0.2172 | 0.1708 |
| 07 ontology (비가중) | 0.2914 | 0.2361 | 0.1139 |
| **07 ontology+IDF (A6)** | **0.3152** | 0.2112 | **0.1250** |

- A6는 **부분·혼합 회복**: MRR/Recall@50 소폭 ↑, NDCG@5 소폭 ↓. 이론대로 거친 개념을 눌러 일부 회복하나 **floor(0.54)도, 구조화 이전(0.3649)도 회복 못 함**.
- 결론: 구조화 브리지+A6는 **커버리지·진단·설명가능성의 향상**이지 *어휘 floor 추월*이 아니다. 잔여 격차(MRR/Recall)는 §5-(1)(진짜 인용 GT)·§5-(2)(보완성) 없이는 닫히지 않음 — 다음 우선순위는 여전히 **P0/B1(인용 외부특허 본문 수집)**.

---

## 7. 관련 산출물 매핑

| 보완/수집 | 닿는 산출물 |
|---|---|
| A1·A6 | [`scripts/build_abox_patents.py`](../../scripts/build_abox_patents.py), [`scripts/sdkb_nb.py`](../../scripts/sdkb_nb.py) |
| A4 | [`mappings/abox_term_aliases.json`](../../mappings/abox_term_aliases.json) (`_KO`/`_KO2` 블록) |
| A2·A3 | `data/semiconductor_v0_3.json`(노드/엣지), `ontology/sdkb-patent.ttl` |
| A5 | CPC/IPC/F-term 정렬 (별도 계획 문서 제거됨) |
| B1·B2·B3·B5 | [`dataset_rejected_patents_card.md`](../dataset_rejected_patents_card.md)(수집 절차·한계 갱신 대상) |
| B4 | 초록 기반 NER/RE·외부 어휘 소스 (별도 계획 문서 제거됨) |
| 평가(§5) | [`notebooks/07_sparql_prior_art_ontology.ipynb`](../../notebooks/07_sparql_prior_art_ontology.ipynb), [`notebooks/04_prior_art_baseline.ipynb`](../../notebooks/04_prior_art_baseline.ipynb) |

---

### 한 줄 요약

> 거절특허 데이터셋이 선행기술 온톨로지에 기여하려면, **(P0) 인용 외부특허 본문을 수집해 평가 자체를 가능케 하고, 이미 보유한 `process_family`/`value_chain` 구조화 분류를 결정적으로 브리지**하는 것이 최우선이다. 그다음 소자/제품 계층·거절사유 계층을 보강하고, 성능은 *단독 우위*가 아니라 *보완성·스코프 커버리지·설명 정밀도*의 4축으로 판정한다.

---

## 7. P0/B1 + B2/B3/B5 + A2/B4 — **수집 완료 + sdkb 내부 정합 검증 (2026-05-16)**

`paper_data` 저장소(`/home/arkwith/Dev/paper_data`)의 `dataset_full_collection_runbook.md` Phase A~D 실행으로 §3-B / §4 P0~P2 다수가 데이터로 충족되었고, 본 절은 그 산출물을 **sdkb 저장소로 인입한 뒤 1000건 데이터에서 직접 재집계 검증**한 결과를 기록한다(문서 주장 신뢰가 아닌 독립 검증).

### 7.1 인입 자산 (sdkb in-repo)

| 자산 | sdkb 경로 | 규모 | git |
|---|---|---|---|
| canonical 데이터셋 | `data/patents/raw/semiconductor_industry_rejected_patents.jsonl` | 1000건 (기존 773 ⊂ 1000, 동일 출원번호 순상위집합) | commit (Amendment v2 정책) |
| 인용 외부특허 본문 | `data/patents/fulltext/{prior_arts,etching_prior_arts}/*.txt` | 3,155 + 192 | gitignore (bulk) |
| 인용 해소 캐시 | `data/patents/citation_resolution_full_cache.json` | 3,154 entries | gitignore (derived) |
| 거절결정 구조화 GT | `data/patents/rejection_decisions/{structured,_index.jsonl}` | 441 structured | commit (GT) |
| device 어휘 | `data/external/device_vocab/` | 31 classes | commit |
| 인용 정규화 모듈 | `scripts/citation_norm.py` (vendored) | — | commit |

### 7.2 독립 검증 결과 (citation_norm 정규화 후 1000건 실측)

| 항목 | 계획 목표 | 이전 | **sdkb 재검증값** | 판정 |
|---|---|---|---|---|
| **B1** examiner 인용 in-corpus (콘텐츠) | ≥0.70 | 0% | **93.5%** (2,950/3,154 distinct resolved); 레코드 단위 **993/1000 평가가능** | ✅ 대폭 초과 |
| — 외국 인용 (JP/US, §5(2) 핵심) | — | 100% 미해소 | JP 752/821(91.6%)·US 379/474(80.0%) resolved; 전 인용 본문 파일 보유 | ✅ 결정적 |
| **B3** `claims_full` | ≥0.90 | 0% | **100%** (1000/1000) | ✅ 초과 |
| legal_status | — | 0% | **100%** | ✅ |
| **B2** 거절결정 구조화 | ≥600/773 | 10 | **441 구조화 / 270 v2 레코드 / 656 매핑** | ⚠️ 미달 |
| **B5** family | ≥0.70 | 0% | **53.4%** (534/1000) | ⚠️ 미달 |
| **B4** device alias/노드 | ≥5 | 0 | 31 classes, 평균 **3.42**, 9/31만 ≥5 | ⚠️ 미달 |
| **§5(4)** 설명 GT 본문 in-corpus | — | 불가 | `evidence_v2` cited 609 distinct 중 **96.7% 본문 보유** | ✅ 파일럿 가능 |

> `citation_resolution_full_cache.json`의 2,950/3,154(93.5%)와 paper_data §7 주장이 정확히 일치. paper_data 갱신 계획서는 잔여 갭을 정직히 명시 — **과대주장 없음**.

### 7.3 통합 요구사항 — 빌더 반영 필수 (검증 중 발견된 무결성 항목)

이 항목들을 ingest/build 파이프라인에 반영하지 않으면 결과가 **거짓 0%** 등으로 잘못 나온다(실제 1차 검증에서 재현됨).

1. **식별자 정규화 필수.** GT(`ground_truth_examiner`/`_all`)는 raw 형식(`KR1020190085654 A`), fulltext·캐시·`evidence_v2.cited_id`는 정규화형(`KR-P-1020190085654`). sdkb 내부 ID(`patent:kr_*`)와도 형식이 다름 → ingest 단계에서 `scripts/citation_norm.parse().normalized_id`로 단일 정규화 후 fulltext 코퍼스(`KR-P-*` 파일명)와 매칭.
2. **파일 존재 ≠ 콘텐츠.** 미해소 204건은 `## TITLE`/`## ABSTRACT` 없는 헤더-stub. 코퍼스 편입은 파일 존재가 아니라 **본문 유무**로 필터(유효 수치 = 93.5%, not 100%).
3. **GT 필드 버전.** legacy `ground_truth_evidence`(≈빈값 10)가 아니라 `meta.ground_truth_evidence_v2`(656/270) + `rejection_decisions/structured/*.json`의 `cited_evidence_map` 사용.
4. **NPL 제외.** examiner 인용 ~1.2%는 비특허문헌(특허 doc_id 없음) — §5 patent-recall 분모에서 명시적 제외(미제외 시 recall 과소평가).
5. **1000건 재베이스라인.** §2/§6 수치(773 모집단, orphan 71 등)는 옛 773 기준 — 1000건(commercial 864 + legacy etch 136)으로 재산출, 옛 수치와 직접 비교 금지.

### 7.4 §5 4축 — 수집 후 가능 상태

1. **실 인용 검색력**: 측정 *가능* — nb 07/04를 IPC-4 프록시 → 실 examiner 코퍼스로 재측정(993/1000).
2. **보완성**: 외국(JP/US) 인용에서 incremental recall 동시 산출 — 데이터 완비.
3. **스코프 커버리지**: orphan scope_out 48을 Phase D device 31 classes(A2 노드)로 다수 커버 후 재측정.
4. **설명 정밀도**: `ground_truth_evidence_v2` 270 rec / 656 map 기반 §29①/② × 대비청구항 × 인용발명 매핑 **파일럿** 평가 가능(수집 전 평가 자체 불가였음).

> 한 줄: **P0 해소로 §5 4축 판정이 처음으로 동시 가능. 단 수집만으로 floor 단독 우위가 자동 달성되지는 않음 — 다음은 §7.3 무결성 반영 + nb 07/04 재측정 + A2 노드 신설 + IDF/제약 재튜닝.**

---

## 8. 구축 실행 결과 (2026-05-17, sdkb in-repo)

§7.3 무결성 반영 + A2 신설 + 실 GT 재측정을 sdkb 파이프라인에 구현·실행한 결과.

### 8.1 산출물

| 신규/수정 | 역할 |
|---|---|
| `scripts/citation_norm.py` (vendored) | raw GT → 정규화 doc_id (§7.3-1) |
| `scripts/ingest_rejected_patents.py` (수정) | 정규화 doc_id·`is_npl`·`cited_doc_id`·`evidence_v2` edge·확장 스키마 컬럼 |
| `scripts/build_fulltext_corpus.py` (신규) | 인용 본문 코퍼스 인덱스 + **stub 필터** (§7.3-2) → 2,926 content / 228 stub |
| `scripts/add_device_nodes.py` (신규) | KG에 Device 31노드 + 정제 동의어 91 주입 (A2/B4) |
| `scripts/build_abox_patents.py` (수정) | `DEVICE_FAMILY_MAP`·`concernsDevice`·`lithography` 정정 |
| `scripts/eval_prior_art_realgt.py` (신규) | §5(1)+§5(2) 실 examiner-GT 평가 |
| `scripts/eval_explanation_precision.py` (신규) | §5(4) 설명 정밀도 파일럿 |

### 8.2 A2 스코프 커버리지 (§5-3)

| 지표 | 773 baseline(§6) | **1000 + A2** |
|---|---|---|
| 링크 특허 | 702/773 | **976/1000** |
| orphan scope_out | 48 | **1** (generic `components` 잔여만) |
| orphan text_miss | 23 | 23 (general 20·materials 2·equipment 1 — 예견된 generic) |
| 노드/특허 mean | 2.66 | **2.89** |
| 구조 device 브리지 | 0 | 104건 + free-text Device edge 162 |

### 8.3 실 examiner-GT 검색력 (§5-1) — IPC-4 프록시 *아님*, 사상 첫 측정

corpus = content 2,926 / evaluable targets = 974.

| Ranker | MRR | NDCG@5 | R@10 | R@50 |
|---|---|---|---|---|
| tfidf (floor) | 0.275 | 0.309 | 0.276 | **0.433** |
| onto | 0.061 | 0.066 | 0.061 | 0.161 |
| onto+IDF (A6) | 0.066 | 0.072 | 0.068 | 0.168 |
| hybrid (RRF) | 0.210 | 0.245 | 0.223 | 0.423 |

→ 온톨로지 단독은 floor 미추월(**계획대로 예견된 정직한 결과** — 단독 우위가 목표가 아님).

### 8.4 보완성 (§5-2) — 핵심 가치 축, 데이터로 입증

R@50, examiner GT positive를 인용국 기준 분리:

| 인용 | tfidf | hybrid | Δ | n_pos |
|---|---|---|---|---|
| KR (어휘 유사) | 0.671 | 0.627 | −0.044 | 1,376 |
| **FOREIGN (JP/US…, 어휘 비유사)** | **0.007** | **0.060** | **+0.053** | 952 |

→ 한국어 질의 ↔ 외국어 인용에서 TF-IDF는 사실상 무력(0.7%), 언어중립 온톨로지 개념이 외국 인용 recall을 **~8배(0.7%→6.0%)** 상향. **incremental recall > 0 on lexically-dissimilar citations** = 도메인 온톨로지 본질 가치 입증. (KR에서는 −0.044 — 균일 RRF 융합의 희석; 다음 최적화: 외국어/저신뢰 질의에서만 온톨로지 가중.)

### 8.5 설명 정밀도 (§5-4) 파일럿 — 수집 전 *측정 불가*였던 축

`ground_truth_evidence_v2` 656 map / 270 rec, content corpus 내 618 pair:

| 지표 | 값 |
|---|---|
| explanation coverage | **0.60** (권고 0.70 미달) |
| §29② (진보성, n=604) | 0.599 |
| mean shared concepts (explained 시) | 1.71 |

→ 축이 0.60 베이스라인으로 **정량화**됨(파일럿). 잔여 격차 원인 = substring 폴백(kiwipiepy 부재)·외국어 개념추출 한계 → B4 device alias 확장 + morph 활성화가 개선 경로.

### 8.6 회귀

본 작업 테스트(`test_baseline`·`test_patents` 등) 전부 통과(773→1000·Device·evidence_v2 반영해 갱신). `test_owl` 24건은 **기존 실패**(stale `sdkb-core.ttl` / `make owl` 미실행, 본 작업 무관·범위 밖).

> 한 줄: **§5 4축이 처음으로 동시 측정됨. §5-2(보완성)가 외국 인용에서 +0.053로 입증되어 도메인 온톨로지의 본질 가치가 데이터로 확인됨. 단독 검색력·설명 정밀도는 floor/0.70 미달이나 측정 가능 상태 자체가 P0 해소의 성과 — 다음은 외국어 개념추출·선택적 융합·morph/B4 확장.**
