# `semiconductor_industry_rejected_patents.jsonl` 정식 스키마

> **English summary.** The canonical field-by-field schema of
> `semiconductor_industry_rejected_patents.jsonl`, the merged SIRP dataset (**1,000 records** as
> of 2026-05-16). The file merges three collection lineages: `semiconductor_commercial` (KIPRIS
> refusal-decision REST seed + KIPRIS Plus bibliographic detail), `semiconductor_ontology`
> (41 strategic coverage plans spanning FEOL → packaging → materials → equipment → design), and
> `legacy_etch_web_poc_import` (an earlier etch-only PoC file promoted into this schema).
> Each record nests `target_patent` (the refused application, including full claims, INPADOC/PCT
> family and legal-status events), `meta.rejection_decision` (OCR plus structured parse of the
> refusal decision), and `meta.ground_truth_evidence_v2` (which refusal ground maps to which
> cited document). **Field names, types and coverage ratios are language-independent facts** and
> the tables below carry English column headers alongside the Korean ones.

이 문서는 canonical merged dataset인
`data/processed/semiconductor_industry_rejected_patents.jsonl`의 실제 필드 구조를
정리한 정식 스키마입니다.

이 파일은 두 수집 계열을 하나로 합친 결과물입니다.

- `semiconductor_commercial`
  - KIPRIS 거절결정서 REST seed + KIPRIS Plus API biblio detail 기반 수집
- `semiconductor_ontology` (**2026-05-08 신설**)
  - 반도체 전산업(FEOL~패키징~소재~장비~설계) 41개 전략 온톨로지 플랜
- `legacy_etch_web_poc_import`
  - 기존 `etching_reject_web_poc_dataset.jsonl`을 새 스키마로 승격한 legacy import

2026-05-16 기준 canonical file은 **1000건** 입니다. 이 시점에 [`dataset_full_collection_runbook.md`](dataset_full_collection_runbook.md) Phase A/C 적용으로 다음 신규 필드가 추가되었습니다.

- `target_patent.claims_full` — 전체 청구항 (B3)
- `target_patent.family` — INPADOC/PCT 패밀리 (B5)
- `target_patent.legal_status` — 법적상태 이벤트 (B5)
- `meta.rejection_decision` — 거절결정서 OCR + 구조화 결과 (B2)
- `meta.ground_truth_evidence_v2` — 거절근거 → 인용발명 ID 매핑 (B2)

수집 직후 실측 보유율:

| 필드 · Field | 보유 · Present | 비율 · Coverage |
|---|---|---|
| `claims_full` | 1000/1000 | 100% |
| `family` (`publication_numbers` 비공란) | 534/1000 | 53.4% |
| `legal_status.events` | 1000/1000 | 100% |
| `rejection_decision` | 441/1000 | 44.1% |
| `ground_truth_evidence_v2` | 270/1000 | 27.0% (656 매핑) |

## 1. 레코드 구조

```jsonc
{
  "target_patent": {
    "application_number": "1020227033671",
    "title": "EUV 패터닝의 결함 감소를 위한 다층 하드마스크 (multi-layer hardmask)",
    "abstract": "...",
    "ipc": "H10P 50/28|H10P 76/40|...",
    "date": "2022.11.04",
    "claim1": "...",
    "registration": {
      "register_status": "거절",
      "register_number": "",
      "register_date": ""
    },
    "biblio": {
      "examination_status": "거절결정(일반)",
      "unex_pub_number": "10-2022-0148249",
      "unex_pub_date": "2022.11.04",
      "source": "kipris_plus_api"
    },
    // ── 2026-05-16 신설 (Phase A) ─────────────────────────────────────
    "claims_full": [
      {"claim_no": 1, "depends_on": [], "text": "1. 기판을 프로세싱하는 ..."},
      {"claim_no": 2, "depends_on": [1], "text": "2. 제 1 항에 있어서, ..."}
      // 평균 13.7개 / 최대 69개
    ],
    "family": {
      "publication_numbers": ["PCT/US2021/019245", "62/982,956"],
      "source": "kipris_plus_api"   // or "epo_ops_inpadoc" when KIPRIS empty
    },
    "legal_status": {
      "events": [
        {"date": "2022.09.27", "code": "[특허출원]특허법 제203조에 따른 서면", "receipt_number": "1-1-2022-1018254-21"},
        {"date": "2024.05.10", "code": "거절결정서", "receipt_number": "..."}
      ],
      "current": "거절결정(일반)"
    }
  },
  "ground_truth_examiner": ["KR1020190085654 A", "US20190348292 A1"],
  "ground_truth_all": ["KR1020190085654 A", "US20190348292 A1", "JP2001358218 A"],
  "ground_truth_evidence": [],
  "meta": {
    "source": "kipris_plus_api",
    "collection_plan": "semiconductor_commercial",
    "collection_stage": "etch_core",
    "search_strategy": "plasma_H01J37",
    "search_query": "플라즈마 식각",
    "validated_web_query": "(플라즈마 식각+\"plasma etch\"+RIE)*(반도체+웨이퍼)",
    "cohort_scope": "semiconductor_fullstack_rejected_patents",
    "process_family": "etch",
    "value_chain": ["process", "equipment"],
    "strategy_validation_status": "validated",
    "collection_ts": "2026-05-06T12:50:23.710028Z",
    "evidence_document_type": "거절결정서",
    "evidence_document_url": "http://plus.kipris.or.kr/openapi/fileToss.jsp?...",
    "admin_documents": [
      {"type": "거절결정서", "url": "..."}
    ],
    "notes": "ground_truth_evidence is empty: KIPRIS Plus API does not expose OCR'd citation phrases.",
    // ── 2026-05-16 신설 (Phase C) ─────────────────────────────────────
    "rejection_decision": {
      "pdf_path": "data/processed/rejection_decisions/pdf/1020227033671.pdf",
      "txt_path": "data/processed/rejection_decisions/txt/1020227033671.txt",
      "structured_path": "data/processed/rejection_decisions/structured/1020227033671.json",
      "ocr_method": "pdfplumber",   // "pdfplumber" | "pymupdf" | "tesseract" | "legacy_raw"
      "legal_bases": [{"paragraph": "2", "count": 2}],   // §29② 진보성
      "decision_date": "2026-02-26"
    },
    "ground_truth_evidence_v2": [
      {
        "cited_id": "KR-P-1020190085654",
        "evidence_phrase_no": "1",   // "인용발명1"
        "target_claims": ["17", "18", "6"],
        "legal_basis": "§29②"
      },
      {
        "cited_id": "US-P-20190348292",
        "evidence_phrase_no": "2",
        "target_claims": ["17", "18", "6"],
        "legal_basis": "§29②"
      }
    ]
  }
}
```

legacy import 레코드는 같은 구조를 따르되 다음과 같은 차이가 있을 수 있습니다.

- `meta.collection_plan = "legacy_etch_web_poc_import"`
- `meta.source`는 `kipris_web_advanced_search` 또는 `kipris_plus_api`일 수 있음
- `meta.evidence_document_type`는 `의견제출통지서`, `거절결정서`, 또는 빈 문자열일 수 있음
- web+OCR origin row는 `ground_truth_evidence`가 비어 있지 않을 수 있음
- `meta.notes`에 legacy import 설명이 포함됨

## 2. 필드별 의미와 보장 수준

| 경로 · Path | 타입 · Type | 보장 수준 · Guarantee | 비고 · Notes |
|---|---|---|---|
| `target_patent.application_number` | string(13) | 필수 | canonical dedupe key |
| `target_patent.title` | string | 필수 | |
| `target_patent.abstract` | string | 필수 | |
| `target_patent.ipc` | string (`A|B|...`) | 필수 | 파이프 구분 다중 IPC |
| `target_patent.date` | string | 필수 | 출원일 또는 공개일 문자열 |
| `target_patent.claim1` | string | 필수 | |
| `target_patent.registration.register_status` | string | 필수 | 항상 `"거절"` |
| `target_patent.registration.register_number` | string | 대부분 공란 | legacy/API 모두 현재 거의 공란 |
| `target_patent.registration.register_date` | string | 대부분 공란 | |
| `target_patent.biblio.examination_status` | string | 필수 | `거절결정(일반)` 등 |
| `target_patent.biblio.unex_pub_number` | string | 필수 | 공개번호 |
| `target_patent.biblio.unex_pub_date` | string | 필수 | 공개일 |
| `target_patent.biblio.source` | string | 필수 | `kipris_plus_api` 또는 `kipris_web_detail` |
| `ground_truth_examiner` | string[] | 필수, ≥1 | 심사관 인용문헌 ID |
| `ground_truth_all` | string[] | 필수 | examiner 포함 전체 인용문헌 |
| `ground_truth_evidence` | string[] | 필수 | API-only 레코드는 빈 배열일 수 있음 |
| `meta.source` | string | 필수 | `kipris_plus_api` 또는 `kipris_web_advanced_search` |
| `meta.collection_plan` | string | 필수 | `semiconductor_commercial`, `semiconductor_ontology`, `legacy_etch_web_poc_import` 중 하나 |
| `meta.collection_stage` | string | 필수 | 어느 stage에서 수집됐는지 |
| `meta.search_strategy` | string | 필수 | keyword strategy ID |
| `meta.search_query` | string | 필수 | 실제 seed keyword |
| `meta.validated_web_query` | string | 선택 | legacy/import 또는 validated strategy에서 채움 |
| `meta.cohort_scope` | string | 필수 | `semiconductor_commercial` 플랜: `semiconductor_fullstack_rejected_patents`; `semiconductor_ontology` 플랜: `semiconductor_ontology_rejected_patents` |
| `meta.process_family` | string | 필수 | 공정군 분류 필드 |
| `meta.value_chain` | string[] | 필수 | process/material/equipment/device/component 등 |
| `meta.strategy_validation_status` | string | 필수 | strategy catalog 상태 |
| `meta.collection_ts` | ISO8601 UTC 또는 기존 문자열 | 필수 | 수집 시각 |
| `meta.evidence_document_type` | string | 선택적 필수 | 일부 API-only row는 빈 문자열 가능 |
| `meta.evidence_document_url` | string | 선택적 필수 | 일부 API-only row는 빈 문자열 가능 |
| `meta.admin_documents` | array | 필수 | 행정문서 목록 `{type, url}` |
| `meta.notes` | string | 필수 | API 제한 또는 legacy import 메모 |
| `target_patent.claims_full` | array | 선택 (2026-05-16~) | 전체 청구항 `{claim_no, depends_on, text}` — Phase A 신설 |
| `target_patent.family` | object | 선택 (2026-05-16~) | 패밀리 `{publication_numbers, source}` — Phase A 신설 |
| `target_patent.legal_status` | object | 선택 (2026-05-16~) | 법적상태 `{events:[{date, code, receipt_number}], current}` — Phase A 신설 |
| `meta.rejection_decision` | object | 선택 (2026-05-16~) | 거절결정서 OCR 결과 `{pdf_path, txt_path, structured_path, ocr_method, legal_bases, decision_date}` — Phase C 신설 |
| `meta.ground_truth_evidence_v2` | array | 선택 (2026-05-16~) | 거절근거→인용 매핑 `{cited_id, evidence_phrase_no, target_claims, legal_basis}` — Phase C 신설 |

## 3. 공정 구분 필드

이 dataset은 `meta` 내부 필드만으로 어느 공정 데이터인지 직접 구분할 수 있습니다.

### 3-1. 1차 구분 (`meta.collection_stage`)

`semiconductor_commercial` 플랜:

- `etch_core`
- `adjacent_frontend`
- `frontend_broadening`
- `backend_and_assets`

`semiconductor_ontology` 플랜 (2026-05-08 신설):

- `feol_etch`
- `feol_depo`
- `feol_photo`
- `feol_thermal_implant`
- `feol_cmp_clean`
- `mol_beol_interconnect`
- `device_logic`
- `device_memory`
- `device_special`
- `packaging_3d`
- `materials_assets`
- `metrology_eda`

### 3-2. 2차 구분 (`meta.process_family`)

| 값 | 대표 공정 |
|-----|----------|
| `etch` | 드라이/플라즈마/습식 식각 |
| `deposition` | CVD/ALD/PVD |
| `epitaxy` | SiGe/SiC/GaN 에피택시 |
| `photo` | 포토레지스트/리소그래피 |
| `clean_cmp` | CMP/세정 |
| `oxidation_diffusion` | 산화/확산 |
| `thermal` | 어닐링/RTP |
| `implant` | 이온주입 |
| `metallization` | 금속배선 |
| `interconnect` | Cu/Low-k 인터커넥트 |
| `logic_device` | FinFET/GAA/콘택실리사이드 |
| `memory_dram` | DRAM 셀 |
| `memory_nand` | NAND 플래시 |
| `power_device` | IGBT/SiC 전력 반도체 |
| `rf_device` | RF/HEMT |
| `image_sensor` | CMOS 이미지센서 |
| `mems` | MEMS |
| `compound_semiconductor` | GaAs/InP/III-V |
| `3d_integration` | TSV/웨이퍼본딩 |
| `advanced_packaging` | HBM/chiplet/플립칩 |
| `backend_packaging` | 인터포저/재배선 |
| `packaging` | 패키지본딩 |
| `materials` | 웨이퍼/에피/전구체/슬러리 |
| `components` | 챔버부품/정전쮙/포커스링 |
| `equipment` | 클러스터툴/진공이송 |
| `inspection_metrology` | 결함검사/CD-SEM/OCD |
| `eda_design` | OPC/DRC/레이아웃검증 |

### 3-3. 3차 구분

- `meta.search_strategy`
  - 예: `plasma_H01J37`, `photo_resist_pattern_H01L21`, `backend_rdl_interposer_H01L23`

### 3-4. value chain 구분 (`meta.value_chain`)

`process`, `material`, `equipment`, `device`, `component`, `design` 값의 리스트.
`semiconductor_ontology` 플랜에서 `design` 값이 신규 추가되었습니다 (`eda_design` 공정군).

따라서 평가나 분석에서 다음과 같은 집계가 가능합니다.

- etch-only 서브셋
- photo-only 서브셋
- backend/material/equipment-only 서브셋
- `collection_stage × process_family` 매트릭스

## 4. provenance 차이

이 merged dataset은 provenance가 둘로 나뉩니다.

### 4-1. API-native row

- `meta.collection_plan = semiconductor_commercial`
- `meta.source = kipris_plus_api`
- `ground_truth_evidence = []`
- `meta.notes`에 KIPRIS Plus API는 OCR citation phrase를 주지 않는다는 설명이 들어감

### 4-2. legacy import row

- `meta.collection_plan = legacy_etch_web_poc_import`
- 내부적으로 두 provenance가 섞여 있음
- legacy web+OCR row
  - `meta.source = kipris_web_advanced_search`
  - `ground_truth_evidence`에 의견제출통지서 OCR 인용 문구가 있음
  - `meta.evidence_document_type = 의견제출통지서`
- legacy API row
  - `meta.source = kipris_plus_api`
  - `ground_truth_evidence = []`
  - `meta.evidence_document_type`는 `거절결정서` 또는 빈 문자열일 수 있음
- 공통적으로 `meta.notes`에 legacy import 설명이 들어감

분석 시 이 둘을 분리하려면 `meta.collection_plan` 또는 `meta.source`로 나누면 됩니다.

## 5. merge 규칙

legacy etch PoC를 canonical dataset에 합칠 때는 다음 규칙을 썼습니다.

1. `target_patent.application_number`를 dedupe key로 사용
2. 기존 canonical semiconductor row를 우선 유지
3. legacy row는 중복되지 않는 경우만 import
4. legacy row의 `meta`는 새 스키마에 맞게 승격
5. 승격 시 `detail_notes`는 `meta.notes`로 접어 넣음

실제 merge는 [scripts/merge_legacy_etch_into_semiconductor_dataset.py](../scripts/merge_legacy_etch_into_semiconductor_dataset.py)로 수행했습니다.

## 6. 생성 산출물

- canonical merged dataset
  - `data/processed/semiconductor_industry_rejected_patents.jsonl`
- normalized legacy-only copy
  - `data/processed/etching_reject_web_poc_dataset.semiconductor_schema.jsonl`

legacy 원본 `etching_reject_web_poc_dataset.jsonl`은 보존합니다.

### 6-1. 2026-05-16 전체 수집 산출물 (`dataset_full_collection_runbook.md`)

| 산출물 | 경로 | 형식 | 건수 |
|---|---|---|---|
| 인용 외부특허 본문 (B1) | `data/processed/fulltext/prior_arts/<doc_id>.txt` | TXT (헤더+본문) | 2,950/3,154 resolved (93.5%) |
| 인용 인덱스 | `data/processed/fulltext/prior_arts/_index.json` | JSON | KR 1728 / JP 752 / US 379 / WO 71 / CN 19 / EP 1 |
| 거절결정서 PDF | `data/processed/rejection_decisions/pdf/<applno>.pdf` | PDF | 431 |
| 거절결정서 OCR 텍스트 | `data/processed/rejection_decisions/txt/<applno>.txt` | TXT | 430 |
| 거절결정서 구조화 | `data/processed/rejection_decisions/structured/<applno>.json` | JSON | 441 (legacy 11 포함) |
| 거절결정서 인덱스 | `data/processed/rejection_decisions/_index.jsonl` | JSONL | 1000 |
| 외부 device 어휘 | `data/external/device_vocab/wikidata_device_classes.jsonl` | JSONL | 31 classes |
| 외부 device 별칭 | `data/external/device_vocab/device_alias_table.json` | JSON | en 79 / ko 37 라벨 |

기존 legacy `data/processed/fulltext/etching_prior_arts/` (POC 192건) 는 그대로 보존합니다. 새 `prior_arts/` 가 1000-record canonical 모집단의 통합 본가입니다.