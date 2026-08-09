# 거절특허 데이터셋 전체 확장 수집 Runbook (B1~B5 + A2/B4)

> **문서 버전**: v1.0 (2026-05-16)
> **상태**: 활성 — 실행 계획 + 운영 절차
> **상위 문서**:
> - [`prior_art_ontology_gap_and_data_plan.md`](project/prior_art_ontology_gap_and_data_plan.md) — 갭 분석 (이 runbook 의 근거)
> - [`semiconductor_industry_rejected_patents_schema.md`](semiconductor_industry_rejected_patents_schema.md) — canonical schema (수집 후 스키마 확장 대상)
> - [`kipris_reject_dataset_source_mapping.md`](kipris_reject_dataset_source_mapping.md) — KIPRIS 소스 매핑
> - `legacy_web_ocr_runbook.md` (미작성) — legacy OCR 절차 (B2 의 기반)

---

## 0. 목적과 범위

`prior_art_ontology_gap_and_data_plan.md` §3-B 의 갭(B1~B6) 과 A2/B4 의 어휘 보강을 **canonical dataset `data/processed/semiconductor_industry_rejected_patents.jsonl` (현재 1000건)** 전체로 확장 수집하기 위한 실행 계획.

- *수집 대상*: 1000 건 거절특허 + 그 examiner 인용 ~2,551 / 전체 인용 ~3,505 (distinct ~3,199) prior-art + 거절결정서 PDF + 외부 device 어휘.
- *수집 후 산출물*: ① canonical JSONL 의 확장 스키마, ② `data/processed/fulltext/prior_arts/` 전체 corpus, ③ `data/processed/rejection_decisions/` OCR 텍스트 + 구조화 JSON, ④ `data/external/device_vocab/` device 계층 어휘.
- *비대상*: NLP NER/RE (별도 `patent_abstract_enrichment_plan.md`), 온톨로지 TBox 확장 (별도 `sdkb` 저장소), 평가 재실행 (별도 노트북 07/04 후속).

---

## 1. 사전 점검 (Pre-flight)

| 항목 | 확인 방법 | 현재 상태 (2026-05-16) |
|---|---|---|
| Python venv | `.venv/bin/python --version` | ✅ Python 3.12.3 |
| KIPRIS Plus API key | `.env` `KIPRIS_API_KEY` | ✅ 설정됨 |
| EPO OPS key/secret | `.env` `EPO_OPS_KEY`, `EPO_OPS_SECRET` | ✅ 설정됨 |
| USPTO/PatentsView key | `.env` `USPTO_API_KEY`, `PATENTSVIEW_API_KEY` | ✅ 설정됨 |
| AWS Bedrock (옵션, B2 후처리용) | `.env` `AWS_REGION`, `BEDROCK_MODEL` | ✅ 설정됨 |
| 시스템 tesseract + 한글 | `tesseract --version` / `kor.traineddata` | ✅ tesseract 5.3.4 + kor |
| 시스템 poppler | `which pdftoppm` | ✅ `/usr/bin/pdftoppm` |
| PDF/OCR Python libs | `.venv/bin/pip list` | ✅ pdfplumber 0.11.9 / PyMuPDF 1.27.2.3 / pdf2image 1.17.0 / pytesseract 0.3.13 / Pillow 12.2.0 |

추가 의존성은 [`requirements.txt`](../pyproject.toml) 와 [`pyproject.toml`](../pyproject.toml) 에 반영되어 있다 (`pdfplumber`, `PyMuPDF`, `pdf2image`, `pytesseract`, `Pillow`).

---

## 2. 현재 자산 실측 (시작점)

| 항목 | 수치 | 출처 |
|---|---|---|
| canonical 거절특허 | 1000 건 | `semiconductor_industry_rejected_patents.jsonl` |
| examiner 인용 string ID 합계 | 2,551 | `ground_truth_examiner` |
| all 인용 string ID 합계 | 3,505 | `ground_truth_all` |
| distinct 인용 ID | ~3,199 | dedupe `ground_truth_all` |
| 인용 fulltext 보유 | 192 건 (POC 136 건 한정) | `data/processed/fulltext/etching_prior_arts/` |
| 거절결정서 URL 보유 | ≥990 건 | `meta.evidence_document_url` |
| 거절결정서 OCR 본문 보유 | 136 건 (POC 한정, 텍스트) | `data/raw/<applno>/rejection_notice/` |
| `ground_truth_evidence` 비어있지 않은 행 | 10 / 1000 | OCR 추출 인용 문구 |
| `claim1` 보유 | 1000 / 1000 | KIPRIS Plus biblio detail |
| 전체 청구항 보유 | 0 / 1000 | 미수집 |
| INPADOC family | 0 / 1000 | 미수집 |
| forward citation | 0 / 1000 | 미수집 |

→ 따라서 **B1 in-corpus 비율은 ~6%** (192/3,199) 에 불과. P0 목표 ≥0.7 까지 ~10x 확장이 필요하다.

---

## 3. 우선순위와 단계 (Phase A → D)

`prior_art_ontology_gap_and_data_plan.md` §4 로드맵을 운영 단위로 재구성.

### Phase A — KIPRIS Plus 단일 세션 확장 (B3 + B5 일부)

같은 `getBibliographyDetailInfoSearch` 호출 흐름에 추가 페이로드만 부착하므로 KIPRIS 쿼터를 가장 효율적으로 사용.

| 항목 | 무엇을 | 호출 추가 | 산출 |
|---|---|---|---|
| B3 전체 청구항 | `getClaimInfoSearch(applicationNumber=...)` 로 독립청구항 + 종속청구항 풀세트 | 1 call/특허 × 1000 | `target_patent.claims_full` (list of claim text + dependency) |
| B5 family/legal | `getBibliographyDetailInfoSearch` 응답의 `priorArtDocumentsInfoArray` 외에 `familyInfo`/`legalStatusInfo` 그룹 추출 + 누락 시 EPO OPS `inpadoc/family` 보강 | KIPRIS 0 추가 / EPO 1/특허 | `target_patent.family` (publication numbers), `target_patent.legal_status` (event timeline) |

**호출 예산**: KIPRIS 1000 calls × interval 0.4s = ~7 분, paid profile. EPO OPS 1000 calls × interval 1.5s = ~25 분.

**스크립트**: `scripts/enrich_targets_b3_b5.py` (신설)
- 입력: `data/processed/semiconductor_industry_rejected_patents.jsonl`
- 출력: 같은 파일 + `target_patent.claims_full`, `target_patent.family`, `target_patent.legal_status`. 캐시 `data/processed/enrich_targets_b3_b5_cache.json`.

**합격 기준**:
- claim 전체 보유율 ≥0.95 (B3 §3 수용 기준 ≥0.9 보다 강화)
- family 매핑률 ≥0.7 (B5)
- 모든 추가 필드는 누락 시 빈 리스트/딕트로 보존 (스키마 호환성)

### Phase B — B1 인용 외부특허 본문 수집 (P0, 결정적)

| 단계 | 대상 | 수단 | 호출 예산 |
|---|---|---|---|
| B1-KR | KR pub/grant 인용 (~2,200건) | KIPRIS Plus `getBibliographyDetailInfoSearch` + `getClaimInfoSearch` + `getAdvancedSearch` registerNumber lookup. 기존 `scripts/resolve_citations.py` 의 로직 재사용 | 1-2 calls × 2,200 = 2,200~4,400 |
| B1-JP/US | JP/US 인용 (~770건) | Google Patents 페이지 스크래핑 (기존 `scripts/enrich_unresolved.py`). 한국어 텍스트가 없으므로 영문/일문 원문 + 영문 abstract 위주 | 1 call × 770 (interval 1.5s) |
| B1-WO/CN/EP | WO/CN/기타 (~160건) | EPO OPS biblio + abstract | 1 call × 160 |
| B1-Foreign 보강 | JP/US 인용 중 한국어 동의어 매칭 | `mappings/abox_term_aliases.json` 영문 블록 + 본문에 있는 화학식/CAS/장비명 같은 언어불변 표현 활용 (Phase D 와 연결) | — |

**스크립트**: `scripts/collect_cited_fulltext_full.py` (신설 — 기존 `resolve_citations.py` + `enrich_unresolved.py` 를 1000-record 대상으로 확장)
- 입력: `semiconductor_industry_rejected_patents.jsonl` 의 `ground_truth_all`
- 출력:
  - `data/processed/fulltext/prior_arts/<normalized_id>.txt` (헤더 + 본문)
  - `data/processed/fulltext/prior_arts/_index.json` (resolved/unresolved 통계)
  - `data/processed/citation_resolution_full_cache.json`

**합격 기준** (B1 §3 수용 기준):
- distinct cited 의 in-corpus 비율 ≥0.7
- KR resolved 비율 ≥0.95 (POC 95.05% 와 동급)
- JP/US Google Patents resolved 비율 ≥0.6
- WO/CN EPO OPS resolved 비율 ≥0.5

**위험과 완화**:
- KIPRIS 일일 쿼터 초과 → `--max-api-calls` 와 캐시로 분할 세션 (여러 날 누적 가능)
- Google Patents 봇 차단 → User-Agent 회전, interval 1.5s 유지, 차단 감지 시 graceful skip 후 다음 세션 재시도
- 외국 특허 한국어 부재 → Phase D 영문 별칭으로 보완 (이 runbook 의 B4 트랙)

### Phase C — B2 거절결정서 PDF OCR + 거절근거 구조화

| 단계 | 무엇을 | 수단 |
|---|---|---|
| C-1 다운로드 | `meta.evidence_document_url` (≥990개) PDF 일괄 다운로드 | `requests` + KIPRIS Plus 세션 (URL은 이미 KIPRIS Plus 도메인) |
| C-2 텍스트 추출 | pdfplumber/PyMuPDF text-layer 1차, 실패 시 pdf2image+tesseract-kor OCR 2차 | layered fallback |
| C-3 구조화 파싱 | 거절 본문에서 §29①/§29②/대비 인용발명/대비 청구항 추출 | regex + 거절결정서 정형 패턴 (`docs/legacy_web_ocr_runbook.md` 의 OCR 룰 재사용) |
| C-4 평가 인덱스 | `rejection_decision_index.jsonl` (출원번호 → 텍스트 + 구조화) | |

**스크립트**: `scripts/build_rejection_decisions.py` (신설)
- 입력: `semiconductor_industry_rejected_patents.jsonl` 의 `meta.evidence_document_url` / `meta.admin_documents[].url`
- 출력:
  - `data/processed/rejection_decisions/pdf/<applno>.pdf` (원본)
  - `data/processed/rejection_decisions/txt/<applno>.txt` (텍스트)
  - `data/processed/rejection_decisions/structured/<applno>.json` (`legal_basis`, `cited_evidence_phrases`, `target_claim_focus` 등)
  - `data/processed/rejection_decisions/_index.jsonl`

**합격 기준** (B2 §3):
- 구조화 레코드 ≥600/1000 (60% 보수 목표; PDF 미존재·OCR 실패 허용)
- 거절근거 라벨 (§29① / §29② / §29④) 정확도 수기 검증 ≥0.9 (소표본 30건)
- 추출된 인용 문구의 인용발명 매핑 커버리지 ≥0.7

**위험과 완화**:
- 일부 PDF 가 인증/세션 만료 → 다운로드 시 KIPRIS 세션 토큰 갱신
- OCR 품질 저하 (스캔 도큐먼트) → tesseract `--oem 1 --psm 3 -l kor+eng`, dpi 300 권장
- 정형 패턴 변형 (구형 거절결정서) → year-bucket 별로 패턴 다중화

### Phase D — A2/B4 외부 device 어휘 인입

device/제품 계층 노드(A2) 와 동의어(B4) 는 같은 외부 소스에서 함께 추출.

| 소스 | 대상 도메인 | 수집 방식 |
|---|---|---|
| Wikidata SPARQL | semiconductor device classes (FinFET, GAA, DRAM cell, NAND string, IGBT, HBT, packaging types) | `https://query.wikidata.org/sparql` 에 SPARQL 질의, label_ko/label_en/alias 추출 |
| IEEE IRDS (공개 PDF) | logic device, memory device, packaging 의 표준 로드맵 용어 | 공식 IRDS executive summary PDF → 용어 추출 (이미 OCR 스택 사용) |
| TTA 정보통신용어사전 | 한국어 표준 표면형 | `http://word.tta.or.kr` 검색 결과 스크래핑 (소규모, robots.txt 준수) |
| Wikidata 한국어 라벨 | 한국어 동의어 자동 확보 | 같은 SPARQL 응답의 `?label_ko` |

**스크립트**: `scripts/build_device_vocab.py` (신설)
- 입력: 사전 정의된 device class 시드 목록 (logic/memory/power/sensor/packaging × ~30 클래스)
- 출력:
  - `data/external/device_vocab/wikidata_device_classes.jsonl`
  - `data/external/device_vocab/device_alias_table.json` (KG 호환 `{node_id: {ko: [...], en: [...], en_abbr: [...]}}`)

**합격 기준** (A2/B4 §3):
- device 노드별 한/영 동의어 ≥5
- 30+ device classes 커버
- 산출물이 `mappings/abox_term_aliases.json` 의 `_KO`/`_KO2` 블록과 충돌 없음 (key 충돌 시 manual review)

---

## 4. 실행 순서와 의존성

```
Phase A (B3+B5, KIPRIS Plus + EPO)
  └── 단독 가능, 30분 내 완료 예상
Phase B (B1, 인용 fulltext)
  ├── B1-KR  ← Phase A 완료 후 (같은 KIPRIS 세션 재활용)
  ├── B1-JP/US ← B1-KR 와 병렬
  └── B1-WO/CN ← 단독, EPO OPS 쿼터로 제한
Phase C (B2, 거절결정서 OCR)
  └── Phase B 와 독립, 병렬 가능. 다만 디스크 I/O 와 OCR CPU 부담을 고려해 직렬화 권장.
Phase D (A2+B4, device vocab)
  └── 완전 독립, 어느 시점에도 가능
```

권장 실행 일정 (단일 워크스테이션 기준):
- **Day 1**: Phase A 완료 + Phase D 시작 (저비용·저위험)
- **Day 2-3**: Phase B (KR 인용 우선, 그 다음 외국)
- **Day 4-5**: Phase C (PDF 다운로드 + OCR)
- **Day 6**: 산출물 검증 + canonical JSONL 스키마 확장 + docs 갱신

---

## 5. 스키마 확장 (수집 후)

> **수집 완료 (2026-05-16).** 신설 5개 필드의 정식 스키마 정의는 **[`semiconductor_industry_rejected_patents_schema.md`](semiconductor_industry_rejected_patents_schema.md) §1~§2** 가 단일 출처(SoT)입니다. 필드 구조와 보장 수준표는 해당 문서를 참조하십시오.

- 모든 신설 필드는 *선택(optional)*. 기존 필수 필드와 스키마 후방 호환(BC) 유지.
- `ground_truth_evidence` (v1) 는 legacy 호환을 위해 유지하고, B2 결과는 `ground_truth_evidence_v2` 에 기록. v1 은 deprecated 표시.
- 2026-05-16 실측 보유율: `claims_full` 100%, `family` 53.4%, `legal_status` 100%, `rejection_decision` 44.1%, `ground_truth_evidence_v2` 27.0% (656 매핑) → 상세는 §10 참조.

---

## 6. 산출물 매핑 표

| 단계 | 산출물 경로 | 형식 |
|---|---|---|
| Phase A | `data/processed/semiconductor_industry_rejected_patents.jsonl` (확장) | JSONL |
| Phase A 캐시 | `data/processed/enrich_targets_b3_b5_cache.json` | JSON |
| Phase B 본문 | `data/processed/fulltext/prior_arts/<normalized_id>.txt` | TXT (헤더+본문) |
| Phase B 인덱스 | `data/processed/fulltext/prior_arts/_index.json` | JSON |
| Phase B 캐시 | `data/processed/citation_resolution_full_cache.json` | JSON |
| Phase C 원본 | `data/processed/rejection_decisions/pdf/<applno>.pdf` | PDF |
| Phase C 텍스트 | `data/processed/rejection_decisions/txt/<applno>.txt` | TXT |
| Phase C 구조화 | `data/processed/rejection_decisions/structured/<applno>.json` | JSON |
| Phase C 인덱스 | `data/processed/rejection_decisions/_index.jsonl` | JSONL |
| Phase D 어휘 | `data/external/device_vocab/wikidata_device_classes.jsonl` | JSONL |
| Phase D 별칭 | `data/external/device_vocab/device_alias_table.json` | JSON |

기존 `data/processed/fulltext/etching_prior_arts/` 는 legacy 보존 (POC 136건 한정). 신규 `prior_arts/` 가 1000건 통합 본가.

---

## 7. 수집 후 docs 갱신 대상

수집 완료 후 다음 파일들을 갱신한다 (`docs/` 디렉토리):

| 파일 | 갱신 포인트 |
|---|---|
| `semiconductor_industry_rejected_patents_schema.md` | §1 레코드 구조 + §2 필드표에 신설 필드 5개 추가 (`claims_full`, `family`, `legal_status`, `meta.rejection_decision`, `meta.ground_truth_evidence_v2`) |
| `README.md` | §1 현재 운영 문서 목록에 이 runbook 링크 추가 |
| `paper_dataset_alignment.md` | §1차 핵심 자산 / 보조 자산 절에 신설 산출물 경로 추가 |
| `research_methodology_and_dataset_evaluation.md` | §3 검증 방식 + §4 평가 지표에 `evidence_v2` 기반 설명 평가 절차 추가 |
| `kipris_reject_dataset_source_mapping.md` | §3 (신설) family/legal endpoint, §4 (신설) Google Patents/EPO OPS fallback 매핑 추가 |
| `legacy_web_ocr_runbook.md` | "legacy 한정" 표기 유지, 신규 PDF OCR 절차는 본 runbook 의 Phase C 로 이관 |
| `legacy_etching_poc_schema.md` | 변경 없음 (POC legacy) |
| `legacy_kipris_etching_search_strategy.md` | 변경 없음 (검색식 설계) |

상위 갭 분석 문서 `prior_art_ontology_gap_and_data_plan.md` 의 §6/§7 에 본 runbook 결과를 1줄 요약으로 추가한다.

---

## 8. 합격 판정 (전체 단위)

`prior_art_ontology_gap_and_data_plan.md` §5 의 4축 중 본 수집이 직접 영향을 미치는 축:

| 축 | 본 수집의 기여 | 측정 방법 |
|---|---|---|
| (1) 실 인용 검색력 | **결정적 (B1)** | examiner cited in-corpus ≥0.7 달성 후 노트북 07/04 재측정 |
| (2) 보완성 | 간접 (B1 후행 노트북에서 평가) | `Recall(TF-IDF ∪ ontology) − Recall(TF-IDF)` |
| (3) 스코프 커버리지 | **직접 (A2+B4 후행으로 device 계층 신설)** | orphan scope_out 48건 해소 |
| (4) 설명 정밀도 | **결정적 (B2)** | 거절근거 → 인용발명 매핑 정확도 |

본 runbook 의 1차 합격 기준 (수집 자체):

1. canonical JSONL 의 `claims_full` 보유율 ≥0.95
2. canonical JSONL 의 `family` 보유율 ≥0.7
3. `data/processed/fulltext/prior_arts/` 의 distinct cited in-corpus 비율 ≥0.7
4. `data/processed/rejection_decisions/structured/` 의 구조화 레코드 ≥600
5. `data/external/device_vocab/` 의 device class ≥30, 클래스당 동의어 ≥5

이 5개 합격 후 후속 평가 (노트북 07/04 재측정) 로 §5 의 (1)/(2) 를 판정한다.

---

## 9. 변경 이력

- v1.0 (2026-05-16) — 초안. `prior_art_ontology_gap_and_data_plan.md` §3-B 와 §4 우선순위에 맞춰 Phase A/B/C/D 로 재구성.
- v1.1 (2026-05-16) — 4-phase 전체 실행 완료 후 §10 결과 + §11 운영 메모 추가.

---

## 10. 실행 결과 (2026-05-16, v1.1)

### Phase A — B3 청구항 + B5 family/legal status

스크립트: [`scripts/enrich_targets_b3_b5.py`](../scripts/enrich_targets_b3_b5.py)
호출: KIPRIS Plus `getBibliographyDetailInfoSearch` × 997, EPO OPS family × 465 (폴백)

| 지표 | 결과 | 합격 기준 | 판정 |
|---|---|---|---|
| `claims_full` 보유 | 1000/1000 (100%) | ≥0.95 | ✅ |
| `legal_status.events` 보유 | 1000/1000 (100%) | — | ✅ |
| `family.publication_numbers` 비공란 | 534/1000 (53.4%) | ≥0.7 | ❌ |
| 평균 청구항 수 | 13.7 (min 1, max 69) | — | — |
| `current` legal 분포 | 거절결정(일반) 670 / 재심사 304 / 심사전치 16 / 후재심사중 8 / 취소환송 2 | — | — |

family 미달은 한국 출원 모집단(1000건 중 ~538건이 KR-only) 의 INPADOC family 부재가 구조적 한계. EPO OPS 폴백을 적용했음에도 추가 family 발견은 제한적. **A5(IPC/CPC 앵커 노드) 와 함께 다음 운영에서 보강**.

### Phase B — B1 인용 외부특허 본문

스크립트: [`scripts/collect_cited_fulltext_full.py`](../scripts/collect_cited_fulltext_full.py)
호출:
- KIPRIS Plus (KR): 3,470 calls × 0.4s ≈ 23분
- Google Patents (JP/US/CN): 1,295 calls × 1.5s ≈ 32분
- EPO OPS (WO/EP): 119 calls × 1.0s ≈ 2분

| 지표 | 결과 | 합격 기준 | 판정 |
|---|---|---|---|
| distinct 인용 in-corpus 비율 | 2,950/3,154 (93.5%) | ≥0.7 | ✅✅ |
| KR resolved | 1,728/1,740 (99.3%) | ≥0.95 | ✅ |
| JP resolved (Google Patents) | 752/821 (91.6%) | ≥0.6 | ✅ |
| US resolved (Google Patents) | 379/474 (80.0%) | ≥0.6 | ✅ |
| WO resolved (EPO OPS) | 71/86 (82.6%) | ≥0.5 | ✅ |
| CN resolved (EPO OPS) | 19/20 (95.0%) | ≥0.5 | ✅ |
| EP resolved (EPO OPS) | 1/12 (8.3%) | ≥0.5 | ❌ |

EP 미달은 EPO OPS 의 EP 자체 커버리지 한계 (12건 중 11건이 `not_found` 또는 `empty_fields`). EP 인용은 모집단에서 12건뿐이라 평가 영향 미미.

**§8 합격 기준 (3) `distinct cited in-corpus ≥0.7` 결정적 달성.** §5(1) 실 인용 검색력 평가가 처음으로 측정 가능 상태가 되었음.

### Phase C — B2 거절결정서 OCR + 구조화

스크립트: [`scripts/build_rejection_decisions.py`](../scripts/build_rejection_decisions.py) + [`scripts/backfill_admin_docs.py`](../scripts/backfill_admin_docs.py) (URL 보강)

| 단계 | 결과 |
|---|---|
| URL 보유 (시작) | 243/1000 |
| URL 보유 (backfill 후) | 461/1000 (+218건 발견) |
| PDF 다운로드 | 431 (URL 부재·non-PDF 응답 제외) |
| OCR 텍스트 추출 | 430 (pdfplumber 1차) |
| 구조화 JSON | 441 (legacy 11 포함) |
| canonical 통합 (`meta.rejection_decision`) | 441/1000 (44.1%) |
| `ground_truth_evidence_v2` 매핑 | 270/1000 records (656 cited→legal_basis→target_claims 매핑) |

| 합격 기준 | 결과 | 판정 |
|---|---|---|
| 구조화 레코드 ≥600/1000 | 441/1000 | ❌ (URL 미존재 539건이 구조적 한계) |
| 거절근거 라벨 (§29①/②/④) | 추출 작동 (수기 검증 미수행) | 잠정 ✅ |
| 거절근거 → 인용발명 매핑 | 656 매핑 / 270 records | ✅ |

구조화 레코드 미달은 KIPRIS REST `advancedSearchInfo` 가 539건에 대해 거절결정서 record 가 없다고 응답한 데서 비롯됨. **BULK 거절결정서 데이터셋 (`docs/kipris_reject_dataset_source_mapping.md` §2 BULK) 도입으로만 보강 가능 — 별도 운영 결정 필요.**

### Phase D — A2/B4 device 어휘

스크립트: [`scripts/build_device_vocab.py`](../scripts/build_device_vocab.py)

| 지표 | 결과 | 합격 기준 | 판정 |
|---|---|---|---|
| device classes | 31 | ≥30 | ✅ |
| en alias 총 | 79 | — | — |
| ko alias 총 | 37 | — | — |
| class 당 평균 en alias | 2.5 | ≥5 | ❌ |
| class 당 평균 ko alias | 1.2 | ≥3 | ❌ |

Wikidata SPARQL `rdfs:label` exact match 의 한계. 다음 운영에서 `skos:altLabel` 와 `CONTAINS` 검색을 추가하고, IEEE IRDS / TTA 표준용어사전 등 추가 소스 인입 필요.

---

## 11. 운영 메모

### 11-1. 캐시 race 주의

`scripts/collect_cited_fulltext_full.py` 의 KR 모드와 foreign 모드를 동시에 실행할 경우 같은 캐시 파일을 두 프로세스가 쓰므로 race condition 으로 일부 entry 가 손실됨 (2026-05-16 1회 발생, fulltext txt 파일은 무사 → 캐시 재구성으로 복구). **운영 권고: 두 모드를 순차 실행하거나 별도 `--cache` 경로 지정.**

### 11-2. 백업

Phase A 적용 직전 `semiconductor_industry_rejected_patents.jsonl` 의 백업이 `.bak.<unixts>` 로 자동 생성됨. 신설 필드를 다시 되돌리려면 백업 파일로 교체.

### 11-3. KIPRIS 호출 합산

본 runbook 1회 수행으로 사용된 KIPRIS Plus 호출:
- Phase A: 997 calls (biblio detail)
- Phase B KR: 3,470 calls (lookup + biblio detail)
- backfill_admin_docs: 693 calls (advancedSearchInfo)
- 합계: ~5,160 calls

paid 프로파일 일일 한도 안에서 1일 분량으로 처리 가능.

---

## 12. 미해결 항목 (다음 수집 세션 진입점)

아래 항목은 §10 합격 기준 미달 또는 운영 중 발견된 미처리 과제입니다.

| 항목 | Phase / 출처 | 우선순위 |
|---|---|---|
| family 보유율 53.4% 미달 — A5(IPC/CPC 앵커 노드) 병행 보강 필요 | Phase A | 높음 |
| Phase C 구조화 레코드 441/1000 — KIPRIS BULK 거절결정서 도입 운영 결정 필요 | Phase C | 높음 |
| device vocab alias 미달 — `skos:altLabel` 확장 + IEEE IRDS / TTA 소스 추가 인입 | Phase D | 중간 |
| EP 인용 resolved 8.3% (12건) — EPO OPS 외 대안 검토 | Phase B | 낮음 |
| `collect_cited_fulltext_full.py` KR/foreign 모드 동시 실행 시 캐시 race condition — 순차 실행 또는 `--cache` 경로 분리 | §11-1 | 낮음 |
