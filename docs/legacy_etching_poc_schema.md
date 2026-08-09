# `etching_reject_web_poc_dataset.jsonl` 정식 스키마 (legacy archive)

이 문서는 `data/processed/etching_reject_web_poc_dataset.jsonl`에 실제로 들어 있는 필드를
관측 기준으로 정리한 정식 스키마입니다.

현재 운영 기본 스키마는 `semiconductor_industry_rejected_patents.jsonl`이며, 본 문서는 legacy web+OCR / early API row의 provenance를 해석할 때 사용합니다.

수집 경로는 KIPRIS 웹 상세보기 + 의견제출통지서 OCR이며, 이 점에서
[docs/kipris_reject_dataset_source_mapping.md](kipris_reject_dataset_source_mapping.md)의
KIPRIS Plus API 매핑과 1:1로 일치하지 않습니다 (점검 결과:
[docs/README.md](README.md)).

## 1. 레코드 구조

```jsonc
{
  "target_patent": {
    "application_number": "1020200128163",       // 13자리 KIPRIS 출원번호
    "title": "반도체 식각장치의 플라즈마 포커스 링",
    "abstract": "...",                             // 발명의 요약
    "ipc": "H01J37/32|H10P72/00",                  // 파이프 구분 IPC 코드 문자열
    "date": "2020-10-05",                          // 출원일 또는 공개일 (YYYY-MM-DD)
    "claim1": "...",                               // 청구항 1 원문
    "registration": {                              // 거절특허이므로 register_* 필드는 항상 공란
      "register_status": "거절",
      "register_number": "",
      "register_date": ""
    },
    "biblio": {
      "examination_status": "거절결정(일반)",
      "unex_pub_number": "1020220045439",
      "unex_pub_date": "2022-04-12",
      "source": "kipris_web_detail"
    }
  },
  "ground_truth_examiner": ["10-1998202", "JP-2007-009988", "10-2010-0095284"],
  "ground_truth_all": ["10-1998202", "JP-2007-009988", "10-2010-0095284"],
  "ground_truth_evidence": [                       // 의견제출통지서 OCR에서 추출한 인용 문구
    "등록특허공보 제 10-1998202 호 (2019.07.10.)",
    "일본 공개특허공보 특개 2007-009988 호 (2007.01.18.)",
    "공개특허공보 제 10-2010-0095284 호 (2010.08.30.)"
  ],
  "meta": {
    "source": "kipris_web_advanced_search",
    "search_strategy": "plasma_H01J37",            // active set: plasma_H01J37 | wet_solution_kw | profile_H01L21
    "search_query": "(플라즈마 식각+\"plasma etch\"+RIE)*(반도체+웨이퍼)",
    "validated_web_query": "...",                  // (선택) 웹 UI 최종 검증식
    "cohort_scope": "semiconductor_etching_rejected_patents",
    "collection_ts": "2026-05-03T06:58:00Z",
    "evidence_document_type": "의견제출통지서",
    "evidence_document_url": "https://www.kipris.or.kr/khome/detail/document.do?...",
    "detail_notes": "(선택) 사람 검토 메모",
    "admin_documents": [                            // 의견제출통지서·최후의견제출통지서·거절결정서 등
      {"type": "의견제출통지서", "url": "..."},
      {"type": "거절결정서",      "url": "..."}
    ]
  }
}
```

## 2. 필드별 의미와 보장 수준

| 경로 | 타입 | 보장 수준 | 비고 |
|---|---|---|---|
| `target_patent.application_number` | string(13) | 필수 | KIPRIS 출원번호. 모든 평가의 1차 키 |
| `target_patent.title` | string | 필수 | |
| `target_patent.abstract` | string | 필수 | KIPRIS DOM의 “Abstract” 섹션 |
| `target_patent.ipc` | string (`A|B|...`) | 필수 | 파이프 구분 다중 IPC. 분할은 `split("|")` |
| `target_patent.date` | string `YYYY-MM-DD` | 필수 | 현재는 출원일 우선 사용 |
| `target_patent.claim1` | string | 필수 | DOM의 청구항 1 원문 |
| `target_patent.registration.register_status` | string | 필수 | 항상 `"거절"` (코호트 정의) |
| `target_patent.registration.register_number` | string | 항상 공란 | 거절이므로 등록번호 없음. **스키마에서 제거 권장** |
| `target_patent.registration.register_date` | string | 항상 공란 | 동상 |
| `target_patent.biblio.examination_status` | string | 필수 | KIPO 행정상태 표기 (`거절결정(일반)` 등) |
| `target_patent.biblio.unex_pub_number` | string | 필수 | 공개번호 |
| `target_patent.biblio.unex_pub_date` | string | 필수 | 공개일 |
| `target_patent.biblio.source` | string | 필수 | `"kipris_web_detail"` 고정 |
| `ground_truth_examiner` | string[] | 필수, ≥1 | 심사관 인용문헌 ID. **표기 정규화 규칙은 §3 참조** |
| `ground_truth_all` | string[] | 필수 | 현재 PoC에서는 examiner와 동일 |
| `ground_truth_evidence` | string[] | 필수 | OCR에서 추출한 인용 표기 문구 |
| `meta.source` | string | 필수 | `"kipris_web_advanced_search"` 고정 |
| `meta.search_strategy` | string | 필수 | active set 3종 |
| `meta.search_query` | string | 필수 | API 키워드 표현 |
| `meta.validated_web_query` | string | 선택 | 웹 UI에서 최종 검증된 표현 |
| `meta.cohort_scope` | string | 필수 | `"semiconductor_etching_rejected_patents"` 고정 |
| `meta.collection_ts` | ISO8601 UTC | 필수 | |
| `meta.evidence_document_type` | string | 필수 | 현재 전건 `"의견제출통지서"` |
| `meta.evidence_document_url` | URL | 필수 | KIPRIS 행정문서 PDF 직링크 |
| `meta.detail_notes` | string | 선택 | 사람 검토 메모 |
| `meta.admin_documents` | array | 필수 | 모든 행정문서(의견제출통지서/최후의견제출통지서/거절결정서)의 `{type,url}` |

## 3. 정답 ID 정규화 규칙 (제안)

평가에서 GT와 검색 결과를 비교하려면 표기 차이를 제거해야 한다. 다음 규칙을
정식 채택 후 코드에 반영한다.

### 3-1. 정규형 정의

`(country, kind, normalized_id)` 3-튜플로 변환한다.

| 원문 표기 | country | kind | normalized_id | 매칭 키 권고 |
|---|---|---|---|---|
| `10-1998202` | KR | grant | `KR1998202` | KIPO 등록번호 |
| `10-2017-0126049` | KR | publication | `KR1020170126049` | KIPRIS 공개번호 |
| `KR2001-29136` | KR | publication | `KR1020010029136` | 약식 → 13자리 변환 |
| `KR2005-10679` | KR | publication | `KR1020050010679` | |
| `JP-2007-009988` | JP | publication | `JP2007009988` | |
| `JP-H08-255787` | JP | publication | `JPH08255787` | 헤이세이 연호 유지 |
| `US2002-0063106` | US | publication | `US20020063106` | |
| `US2010/0213162` | US | publication | `US20100213162` | |
| `US5308414` | US | grant | `US5308414` | |

### 3-2. 약식 KR 공개번호 → 13자리 변환

`KR<YY>-<NNNNN>` 또는 `<YY>-<NNNNN>` 형식은 다음과 같이 13자리화한다.

```
KR<YY>-<NNNNN>  →  KR1020<YY>0<NNNNN>   (YY가 두 자리일 때 1900/2000년대 휴리스틱은 KIPO 정책에 따라 결정)
```

이 변환 규칙은 코드에서 `kipris_dataset/citation_norm.py`(가칭)로 모듈화하고,
변환 실패는 `unresolved` 표시를 유지한 채 보존한다.

### 3-3. 매칭 절차

평가 시 다음 순서로 매칭한다.

1. GT를 §3-1 정규형으로 변환.
2. 후보 검색 결과(KIPRIS Plus `getAdvancedSearch` 등)를 동일 정규형으로 변환.
3. 1차: `country + normalized_id`로 정확 매칭.
4. 2차: KR 공개번호 → 출원번호 룩업이 실패하면 `KR<grant_no>` 등록번호로 보조 매칭.
5. 외국문헌은 `country + kind + normalized_id`까지 일치해야 매칭 성공으로 인정.

### 3-4. 현재 데이터의 정규화 가능성 점검

- KR(공개): 6건, 모두 13자리 변환 가능
- KR(등록): 1건 (`10-1998202`)
- JP: 2건, 1건은 헤이세이 표기 필요
- US: 4건, slash/dash 혼재

## 4. 원문 아카이브와의 연결

`data/raw/<application_number>/`는 동일 출원번호 단위로 다음을 보장한다.

```
target/target_patent_<application_number>.txt          # KIPRIS 웹 상세 텍스트
rejection_notice/rejection_notice_<application_number>.txt  # 의견제출통지서 OCR 텍스트
cited/<NN>_<citation_id>[_unresolved].txt              # 인용문헌 원문 또는 placeholder
README.txt                                              # cited 목록과 resolved 여부
```

향후 보완으로 다음 보강을 권고한다.

- `manifest.json`(레코드 단위): JSONL의 GT 표기 → 정규형 → `cited/*.txt` 경로의 매핑.
- `meta.admin_documents[*]`에 `sha256`, `downloaded_at`, `ocr_engine` 키 추가.
- `data/raw/`는 `.gitignore` 대상이므로, 제3자 재현을 위해 archive 다운로드 스크립트가 별도로 필요.

## 5. 향후 변경 절차

이 스키마는 PoC v1로 동결한다. 변경이 필요하면 다음 절차를 따른다.

1. 변경 의도와 대상은 [docs/README.md](README.md) 및 canonical 문서 체계에 맞춰 기록.
2. 새 `etching_reject_web_poc_dataset.v2.jsonl` 산출과 동시에 v1을 보존.
3. 평가 스크립트는 schema 버전을 명시적으로 인식해 분기.
