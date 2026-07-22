# 거절특허 → 선행기술조사 온톨로지: 변환 프로토콜·수집 완전성·성능 (설명가능 정본)

> **문서 버전**: v1.0 (2026-07-21)
> **상태**: 활성 — 실측 기반. 모든 수치는 실행된 코드/데이터의 출력이다.
> **목적**: "특허청 거절특허가 **어떤 변환 프로토콜**을 거쳐, **어느 정도 성능을 보장하는**
> 선행기술조사 온톨로지가 되었는가"를 설명 가능하게 고정한다. 이후 T-Box·A-Box 수정의 기준선.
> **선행 문서**: [`prior_art_ontology_gap_and_data_plan.md`](prior_art_ontology_gap_and_data_plan.md)
> (갭·데이터 계획 §7·§8). 본 문서는 그 위에서 **변환 프로토콜 전모 + 수집 완전성 감사 + 실체 결함**을 더한다.

---

## 0. 한 문단 요약

거절특허 1,000건(SIRP)은 [`build_abox_patents.py`](../../scripts/build_abox_patents.py)를 거쳐
`ont:Patent` 노드로 승격되고, **구조화 필드 브리지 ∪ 국문 자유텍스트 추출**로 도메인 개념(공정·소재·
디바이스…)에 연결된다(977/1,000, 평균 2.9개/특허). 그러나 **선행기술조사의 정답인 심사관 인용 문헌은
개념 노드가 아니라 매달린 IRI(정답 라벨)로만 존재**하고, **거절이유·인용근거 계층은 T-Box에만 선언되고
A-Box 인스턴스가 0개**다. 그 결과 **그래프 자체로는 선행기술을 한 건도 검색하지 못하며**, 측정된 성능
(§8.3)은 그래프가 아니라 **별도로 수집한 인용문헌 본문 코퍼스**에서 나온다. 온톨로지가 현재 방어할 수 있는
성능 주장은 단 하나 — **외국어(JP·US) 인용에 대한 보완적 recall 향상(0.7%→6.0%, ~8배)**뿐이다.

---

## 1. 원천 자산 지도 (진실의 원천)

CLAUDE.md §1·§3: TTL은 빌드 산출물이고 진실의 원천은 `data/**`와 `scripts/`다.

| 자산 | 경로 | 규모 | 역할 |
|---|---|---|---|
| 거절특허 원천 | `data/patents/raw/semiconductor_industry_rejected_patents.jsonl` | 1,000 | target·GT·evidence 원본 |
| 거절특허 메타 | `data/patents/rejected_patents_meta.parquet` | 1,000 × 38 | A-Box 빌더 입력 |
| 선행기술 엣지 | `data/patents/prior_art_edges.parquet` | 6,692 × 12 | 인용 정답(examiner/all/evidence) |
| 인용문헌 본문 | `data/patents/fulltext_corpus.parquet` | 3,154 (본문 2,926) | 평가용 코퍼스(그래프 밖) |
| 거절결정 구조화 | `data/patents/rejection_decisions/structured/*.json` | 441 | 거절이유 GT |
| 특허 A-Box | `ontology/sdkb-abox-patents.ttl` | 33,937 트리플 | 빌드 산출물 |
| 링크 리포트 | `data/reports/abox_patents_linking_report.json` | — | 정직한 커버리지/고아 |

---

## 2. 변환 프로토콜 (거절특허 → 온톨로지) — 5단계, 실측

생성기 [`build_abox_patents.py`](../../scripts/build_abox_patents.py)가 특허 1건마다 수행한다.

**① 노드 생성.** `ont:Patent` + `ont:RejectedPatent`(register_status=='거절' 1,000/1,000).
발명의 명칭 → `skos:prefLabel@ko`(과거 `rdfs:label`을 써서 제목이 질의에 안 잡힌 결함 교정됨).

**② 서지 속성.** 출원번호·`filingDate`·`publicationDate`·IPC심볼(`hasIPC`)·출원인(`assignedTo`,
prefLabel 회사당 1개·나머지 altLabel)·초록(`abstractText` 1,000)·청구항1(`firstClaimText` 1,000).

**③ 거절근거.** 제29조 항번호 → `rejectedFor`(통제어휘 `Rejection_Novelty`/`Inventiveness`).
실측: **414/1,000만 부여**(진보성 400·신규성 14). §29③은 통제어휘 없어 리포트에만(1건).

**④ 개념 링크 — 핵심, 두 경로의 합집합.**
- (a) **구조화 브리지**(결정적·무NLP): 큐레이터의 `process_family` → Process 노드
  (`PROCESS_FAMILY_MAP`, 793건), `memory`/`packaging` 등 → Device 노드(`DEVICE_FAMILY_MAP`, 104건).
- (b) **국문 자유텍스트 추출**: 제목+초록+청구항1에 Kiwi 형태소 ∪ 부분문자열 스캔으로 2계층 렉시콘
  (Tier-1 개념 + Tier-2 별칭) 매칭(850건).

실측 개념 엣지 분포: **Process 1,292 · Skill 630 · Material 526 · SubProcess 273 · Device 181 ·
EquipmentClass 7 · FailureMode 4 · TechnologyNode 1 · RootCause 1.**
링크 977/1,000, 평균 2.9·중앙 3·최대 9. 고아 23 = scope_out 1 + text_miss 22(general 19·재료 2·장비 1).

**⑤ 선행기술 인용.** `prior_art_edges.parquet` → `hasPriorArt`(광의 3,485엣지·인용 3,197·NPL 44)와
`hasPriorArtExaminer`(정답 2,534엣지·인용 2,321·NPL 30). **인용문헌에는 rdf:type을 붙이지 않는다**
(생성기 설계). evidence/evidence_v2 673쌍은 **적재 범위 밖으로 배제.**

---

## 3. 원천 수집 완전성 감사 — "필요한 정보가 누락되었는가"

선행기술조사 온톨로지가 요구하는 정보를 기준으로, **target(거절특허)측**과 **cited(인용문헌)측**을 나눠 실측.

### 3.1 target(거절특허)측 — 대체로 완비, 승격이 문제

| 정보 | 수집 상태 | 판정 |
|---|---|---|
| 제목·초록·IPC·출원인·출원일·공개일 | 100% | ✅ |
| **`filingDate`가 진짜 출원일인가** | filing≠publication **0% 일치**(과거 부채 해소). PCT 국내진입은 출원일이 출원번호 연도보다 이르며 정상 | ✅ **정정 확인** (CLAUDE.md §8-1 노트는 낡음) |
| **전체 청구항** | `claims_full` 원천에 **종속구조(`depends_on`)까지 100% 실재**(평균 13.7항) | ⚠️ **수집은 완비, A-Box엔 claim1만 승격**(승격 갭) |
| 거절이유(법적근거) | `rejection_legal_bases` **40%** · 결정일 44.1% · 구조화결정 441/1,000 | ⚠️ **수집 미달** → ③의 414 커버리지 원인 |
| 패밀리(INPADOC) | `family_pub_numbers` **53.4%** | ⚠️ 절반 |
| **CPC** | 원천에도 **부재**(IPC만) | ❌ **미수집** |

### 3.2 cited(인용문헌)측 — 결정적 누락, 선행기술조사의 근간

| 정보 | 수집 상태 | 판정 |
|---|---|---|
| 본문 제목·초록 | 2,926/3,154 (title 93.5%·abstract 92.8%) — **단 `fulltext_corpus.parquet`, 그래프 밖** | ⚠️ 데이터로만 존재 |
| **인용문헌 청구항** | **0%** (제목+초록만) | ❌ **미수집** — 청구항 한정요소 단위 대비 불가 |
| **인용문헌 서지(출원일·IPC)** | 엣지에 office/country/kind만, **출원일·분류 부재** | ❌ **미수집** — 우선일 필터·개념 라우팅 불가 |
| in-corpus(그래프 노드화) | **0%** (전량 매달린 IRI) | ❌ **결함 A** |

> **감사 결론**: target측은 (CPC 제외) 사실상 완비돼 있고 문제는 **승격 부족**이다. 반면 **cited측은
> 청구항·서지가 원천 단계에서 미수집**이라, 결함 A(인용문헌 노드화)를 제대로 하려면 **인용문헌의 서지·
> 청구항 추가 수집**이 선행돼야 한다. 지금 가진 것(제목+초록)만으로는 개념 링크는 붙여도 **우선일 필터와
> 청구항 대비**를 세울 수 없다.

---

## 4. 실체 결함 — "이름만 있고 실체 없는" 것들 (근거 있는 사실)

**결함 A (치명) — 선행기술 인용 대상이 매달린 IRI.** `hasPriorArtExaminer` 2,534엣지가 2,321
문헌을 가리키나 **개념·타입·본문 가진 노드는 0개**. 정답이 그래프에서 도달 불가 → 개념 질의로 선행기술
검색 원리적 불가. 본문 2,926건은 별도 코퍼스에만 있고 서지·청구항은 미수집(§3.2).

**결함 B (치명) — 거절이유·인용근거 계층이 T-Box에만 존재.** `ont:RejectionReason`·
`ont:rejectionEvidence`·`ont:rejectionPassage` 선언은 있으나 **A-Box 인스턴스 0개**. "어느 청구항
한정요소가 어느 인용발명에 대해 신규성 없음"이라는 **판단의 실제 단위**가 통째로 비어 있다. 근거
673쌍(`evidence_v2`)이 데이터에 있으나 배제됨.

**결함 C (부분) — 거절이유 커버리지 414/1,000.** 원천 수집(§3.1)이 40%라 구조적 상한.

**결함 D (스코프) — 개념 축이 거칠고 매핑이 손실적.** `DEVICE_FAMILY_MAP`이 **모든 `memory`→
`device:dram`**(대표값)으로 보내 3D NAND 특허가 "DRAM"이 된다. 어휘에 `3d_v_nand` 노드가 있어도
**특허를 그리로 보내는 브리지가 없어 0건**(하류 explore 도구가 3D NAND 문장에 메모리 잡음만 문 뿌리).

---

## 5. 성능 — "무엇을, 어느 정도 보장하는가"

### 5.1 두 시스템을 섞지 말 것
1. **RDF 지식그래프(G₀)** — 거절특허 1,000 + 개념. 인용 선행기술은 정답 라벨(엣지)로만.
   **그래프 순회로는 선행기술 검색 불가.**
2. **검색 평가 파이프라인**([`eval_prior_art_realgt.py`](../../scripts/eval_prior_art_realgt.py)) —
   인용문헌 본문 2,926건에서 텍스트로 개념을 추출해 TF-IDF와 겨루는 **텍스트 분석.** §8.3 수치의 출처.

### 5.2 실 심사관 GT 성능 (§8.3, 사상 첫 측정 · 그래프 아님 · content 2,926/평가대상 974)

| Ranker | MRR | NDCG@5 | R@10 | R@50 |
|---|---|---|---|---|
| tfidf (floor) | 0.275 | 0.309 | 0.276 | **0.433** |
| onto | 0.061 | 0.066 | 0.061 | 0.161 |
| onto+IDF | 0.066 | 0.072 | 0.068 | 0.168 |
| hybrid(RRF) | 0.210 | 0.245 | 0.223 | 0.423 |

**온톨로지 단독은 어휘 floor 미달**(정직하게 예견된 결과 — 단독 우위가 목표가 아님).

### 5.3 방어 가능한 본질 가치 (§8.4) — 외국어 인용 보완성

| 인용 | tfidf R@50 | hybrid R@50 | Δ | n_pos |
|---|---|---|---|---|
| KR (어휘 유사) | 0.671 | 0.627 | −0.044 | 1,376 |
| **FOREIGN (JP/US)** | **0.007** | **0.060** | **+0.053** | 952 |

한국어 질의 ↔ 외국어 인용에서 TF-IDF는 무력(0.7%)이고, 언어중립 개념이 recall을 **~8배** 올린다.
**incremental recall > 0 on lexically-dissimilar citations** = 도메인 온톨로지의 본질 가치.

> **결론**: 현재 "성능 보장"이라 말할 수 있는 것은 **외국어 인용에 대한 보완적 recall 향상**뿐이며,
> 그마저 **그래프가 아니라 텍스트 파이프라인**의 성과다. 그래프 자체는 아직 선행기술을 검색하지 못한다.

---

## 6. 수정 로드맵 (실체화 우선순위)

상류 CLAUDE.md §2: 생성기·원천·T-Box·shape 변경은 **각각 1단계 요구정의부터 🛑 승인**. G₀ 이동은
하류 `sdkb-foresight-paper`의 H1 재동결을 요구한다.

| 우선 | 결함 | 무엇을 | 선행조건 | 성공기준(게이트) |
|---|---|---|---|---|
| **P0** | A | 인용문헌 본문 2,926건을 `ont:Patent` 노드로 승격 + 동일 개념추출 | **인용문헌 서지·청구항 추가 수집**(§3.2) | 그래프에서 GT 도달률 ↑, MRR/Recall을 **그래프에서** 최초 측정 |
| P1 | B | `evidence_v2` 673쌍 → `RejectionReason`/`rejectionEvidence` 실체화 | 원천 evidence_v2 정합 | RejectionReason A-Box 0→673, 청구항↔인용↔사유 삼각형 복원 |
| P1 | D | 3D NAND 등 세부 개념 신설 + `DEVICE_FAMILY_MAP` 손실 매핑 정정 | 어휘 결정 | 3d_v_nand 특허 0→N, memory 일괄 dram 제거 |
| P2 | C | 거절이유 수집 확대(구조화결정 441→) | KIPRIS 재수집 | rejectedFor 커버리지 ↑ |
| 병행 | — | 전체 청구항(`claims_full`) A-Box 승격, CPC 수집 | — | 청구항 한정요소 단위 매칭 기반 |

**즉시 다음 작업**: P0(결함 A). 단 §3.2가 보이듯 **인용문헌의 서지·청구항이 미수집**이므로, P0는
"이미 가진 본문으로 노드 승격"과 "부족한 서지·청구항 수집"의 두 하위작업으로 나뉜다 — 1단계 요구정의에서
범위를 확정한다.
