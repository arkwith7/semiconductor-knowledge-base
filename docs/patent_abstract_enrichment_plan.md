# SDKB 특허 초록 기반 온톨로지 보강 실행 계획

> **문서 버전**: v1.0 (2026-04-13)
> **작성자**: SDKB 프로젝트 팀
> **상태**: 실행 계획 (활성). 단 본 계획은 ADR v1.1 (SemicONTO Hub) 시점에 작성됨 — 이후 방향이 SDKB-Centric으로 역전되었으므로 (2026-05-12), 본 문서의 절차/타깃은 유효하되 **결과물의 정렬은 SDKB 네임스페이스로 흡수**한다는 점을 유의할 것.
> **상위 문서**: [`docs/architecture_amendment_sdkb_centric.md`](architecture_amendment_sdkb_centric.md) §4 Phase 3.5 (기존 상위 ADR은 [`docs/archive/architecture_redesign_semiconto_hub_v1.1.md`](archive/architecture_redesign_semiconto_hub_v1.1.md)로 이관됨)

---

## 1. 목적

CPC/IPC 분류가 부여된 반도체 관련 특허의 **발명의 개요(Abstract)**를 대규모로 수집하고,
NLP/LLM 기반 엔티티·관계 추출(NER+RE)을 통해 SDKB 온톨로지를:

1. **현존하는 실제 기술**로 더 풍성하게 하고 (신규 노드·관계 발견)
2. **기존 노드**에 동의어, 파라미터 범위, CPC 코드 등 속성을 보강하고
3. **기술 트렌드**를 시계열 분석하여 신흥/쇠퇴 기술을 식별하고
4. **한국어 용어 매핑**을 확보하는 것을 목적으로 한다.

---

## 2. 데이터 소스 상세

### 2.1 Google BigQuery — Patents Public Dataset (★ 1차 소스)

| 항목 | 값 |
|------|-----|
| 테이블 | `patents-public-data.patents.publications` |
| 범위 | 120+ 특허청, 1억+ 특허 문서 |
| 비용 | 매월 1TB 쿼리 무료 (초과 시 $6.25/TB) |
| 필드 | `publication_number`, `title_localized`, `abstract_localized`, `cpc`, `filing_date`, `country_code`, `claims_localized` |
| 라이선스 | Public Domain (특허 서지 정보) |
| 설정 | Google Cloud 프로젝트 + BigQuery API 활성화 필요 |

**수집 대상 CPC 코드:**

| CPC 서브트리 | 반도체 영역 | 예상 특허 수 (US, 최근 5년) |
|-------------|-----------|--------------------------|
| H01L 21 | 제조 공정 전체 | ~30,000 |
| H01L 29 | 개별 소자 (FinFET, GAA) | ~15,000 |
| H10B | 전자 메모리 (DRAM, NAND) | ~8,000 |
| G03F 7 | 포토리소그래피 | ~3,000 |
| C23C 14/16 | PVD/CVD 코팅 | ~5,000 |
| B24B 37 | CMP 연마 | ~1,500 |
| **합계** | | **~60,000-80,000** |

**BigQuery 쿼리 예시:**

```sql
-- Step 1: 반도체 제조 특허 초록 수집
-- 예상 스캔량: ~200GB (무료 한도 이내)
CREATE OR REPLACE TABLE `your_project.sdkb.patent_abstracts_semiconductor` AS
SELECT
  pub.publication_number,
  pub.country_code,
  pub.filing_date,
  pub.grant_date,
  title.text AS title_en,
  abstract.text AS abstract_en,
  ARRAY_AGG(DISTINCT cpc.code) AS cpc_codes,
  ARRAY_AGG(DISTINCT ipc.code) AS ipc_codes
FROM
  `patents-public-data.patents.publications` AS pub,
  UNNEST(pub.title_localized) AS title,
  UNNEST(pub.abstract_localized) AS abstract,
  UNNEST(pub.cpc) AS cpc
LEFT JOIN UNNEST(pub.ipc) AS ipc ON TRUE
WHERE
  (   cpc.code LIKE 'H01L21%'
   OR cpc.code LIKE 'H01L29%'
   OR cpc.code LIKE 'H10B%'
   OR cpc.code LIKE 'G03F7%'
   OR cpc.code LIKE 'C23C14%'
   OR cpc.code LIKE 'C23C16%'
   OR cpc.code LIKE 'B24B37%'
  )
  AND title.language = 'en'
  AND abstract.language = 'en'
  AND pub.filing_date >= 20200101
  AND LENGTH(abstract.text) > 100
GROUP BY
  pub.publication_number, pub.country_code,
  pub.filing_date, pub.grant_date,
  title_en, abstract_en
```

```sql
-- Step 2: Parquet로 내보내기
EXPORT DATA OPTIONS(
  uri='gs://your_bucket/sdkb/patent_abstracts_*.parquet',
  format='PARQUET',
  overwrite=true
) AS
SELECT * FROM `your_project.sdkb.patent_abstracts_semiconductor`
```

### 2.2 USPTO PatentsView API (보조 소스)

```python
# scripts/collect_patentsview.py — 단일 CPC 서브그룹 수집 예시
import requests
import pandas as pd

API_URL = "https://api.patentsview.org/patents/query"
HEADERS = {"X-Api-Key": "<YOUR_API_KEY>"}  # 환경변수에서 로드

def fetch_patents(cpc_prefix: str, per_page: int = 1000) -> list[dict]:
    """CPC 접두사로 특허 초록 수집 (페이지네이션)."""
    results = []
    page = 1
    while True:
        params = {
            "q": f'{{"_begins":{{"cpc_subgroup_id":"{cpc_prefix}"}}}}',
            "f": '["patent_number","patent_title","patent_abstract",'
                 '"patent_date","cpc_subgroup_id"]',
            "o": f'{{"page":{page},"per_page":{per_page}}}',
        }
        resp = requests.get(API_URL, params=params, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        patents = data.get("patents", [])
        if not patents:
            break
        results.extend(patents)
        page += 1
        if data.get("count", 0) < per_page:
            break
    return results
```

### 2.3 KIPRIS API (한국어 용어 수집)

```python
# scripts/collect_kipris.py — 한국 특허 초록 수집 (한국어 동의어 확보)
import requests

KIPRIS_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"

def fetch_kipris(keyword: str, api_key: str, num_of_rows: int = 100) -> list[dict]:
    """KIPRIS에서 한국어 특허 초록 수집."""
    params = {
        "word": keyword,
        "patent": "true",
        "ServiceKey": api_key,
        "numOfRows": num_of_rows,
    }
    resp = requests.get(KIPRIS_URL, params=params)
    resp.raise_for_status()
    # XML 파싱 후 반환
    return parse_kipris_xml(resp.text)
```

---

## 3. NLP/LLM 추출 파이프라인 상세

### 3.1 아키텍처

```
                     ┌─────────────────────┐
                     │ patent_abstracts     │
                     │ .parquet (60-80K)    │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │  전처리 (Preprocess)  │
                     │  - 문장 분리          │
                     │  - 약어 정규화        │
                     │  - CPC→도메인 태그    │
                     └──────────┬──────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
    │  NER          │  │  RE           │  │  수치 추출         │
    │  (엔티티 인식) │  │  (관계 추출)   │  │  (Parameter)     │
    │              │  │              │  │                  │
    │ Material     │  │ used_for     │  │ Temp: 250-350°C  │
    │ Process      │  │ produces     │  │ Pressure: 10mT   │
    │ Equipment    │  │ improves     │  │ Power: 100W      │
    │ Parameter    │  │ replaces     │  │ Thickness: 5nm   │
    │ Structure    │  │ causes       │  │                  │
    └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
           │                 │                    │
           └─────────────────┼────────────────────┘
                             ▼
                  ┌──────────────────┐
                  │  엔티티 정규화     │
                  │  (Entity Linking)  │
                  │  - rapidfuzz 매칭  │
                  │  - 임베딩 유사도    │
                  │  - SDKB 노드 대조  │
                  └──────────┬───────┘
                             │
                   ┌─────────┴─────────┐
                   ▼                   ▼
          ┌──────────────┐    ┌──────────────┐
          │ 기존 노드 보강  │    │ 신규 후보 생성  │
          │ (Enrichment)  │    │ (Discovery)  │
          │              │    │              │
          │ + synonym     │    │ 새 Material  │
          │ + param range │    │ 새 SubProcess│
          │ + CPC code    │    │ 새 Relation  │
          │ + description │    │ + confidence │
          └──────────────┘    └──────────────┘
```

### 3.2 NER 모델 선택

| 방법 | 도구 | 장점 | 단점 |
|------|------|------|------|
| **규칙 기반** | spaCy + 커스텀 패턴 | 빠름, 투명, 도메인 용어 정확 | 신규 용어 발견 제한 |
| **사전학습 NER** | MatSciBERT, MaterialsBERT | 재료과학 도메인 특화, 무료 | 반도체 공정 커버리지 부족 |
| **LLM 기반** | Claude/GPT API | 문맥 이해 뛰어남, 관계 추출 동시 가능 | 비용, 재현성 |
| **하이브리드 (★ 권장)** | spaCy 규칙 + LLM 검증 | 정확도↑ + 비용↓ | 파이프라인 복잡도 |

**권장 하이브리드 파이프라인:**

```
1단계: spaCy 규칙 기반 NER (빠른 1차 추출)
   - SDKB 기존 198노드 + CPC 레이블 → 사전 (gazetteer)
   - 소재 패턴: 화학식 (SiO₂, HfO₂, ...), "-ide"/"-ane" 접미사
   - 파라미터 패턴: 숫자 + 단위 (nm, °C, mTorr, W, sccm)
   - 장비 패턴: 회사명 + 모델 (ASML NXE:3600, LAM Kiyo)
   ↓
2단계: LLM 검증 + 관계 추출 (고정밀 2차 처리)
   - 1단계에서 엔티티 5개 이상 추출된 초록만 대상 (~20%)
   - 구조화된 JSON 출력 프롬프트
   ↓
3단계: 정규화 + 중복 제거
   - rapidfuzz (threshold ≥ 85) + sentence-transformers 임베딩
   - SDKB 기존 노드와 매칭 → 기존/신규 분류
```

### 3.3 LLM 추출 프롬프트 설계

```
System: You are a semiconductor manufacturing domain expert.
Extract structured entities and relations from patent abstracts.

Return JSON:
{
  "entities": [
    {"text": "...", "type": "Material|Process|Equipment|Parameter|Structure|Application",
     "normalized": "...", "confidence": 0.0-1.0}
  ],
  "relations": [
    {"subject": "...", "predicate": "used_for|produces|improves|replaces|causes|measured_by",
     "object": "...", "confidence": 0.0-1.0}
  ],
  "parameters": [
    {"name": "...", "value": "...", "unit": "...", "range_min": null, "range_max": null}
  ]
}

Rules:
- Normalize chemical formulas (e.g., "hafnium oxide" → "HfO2")
- Include only semiconductor manufacturing-relevant entities
- Confidence 1.0 = explicitly stated, 0.7 = strongly implied, 0.5 = inferred
```

### 3.4 엔티티 정규화 전략

| 단계 | 방법 | 임계값 | 결과 |
|------|------|--------|------|
| 1. 정확 매칭 | SDKB 노드 canonical_name + synonyms | 100% | `owl:sameAs` |
| 2. 퍼지 매칭 | rapidfuzz token_sort_ratio | ≥ 85 | `skos:closeMatch` 후보 |
| 3. 임베딩 유사도 | sentence-transformers cosine | ≥ 0.85 | `skos:relatedMatch` 후보 |
| 4. 미매칭 | 위 모두 실패 | — | 신규 후보 노드 (pending) |

---

## 4. 산출물 스키마

### 4.1 추출 엔티티 스키마 (Parquet)

```
patent_entities.parquet
├── patent_id: string          # "US20230123456A1"
├── cpc_codes: list[string]    # ["H01L21/316", "C23C16/455"]
├── entity_text: string        # "hafnium oxide"
├── entity_type: string        # "Material"
├── entity_normalized: string  # "HfO2"
├── confidence: float          # 0.92
├── extraction_method: string  # "spacy_ner" | "llm_extraction"
├── sdkb_match_id: string?     # "material:hfO2" (기존 노드) or null
├── sdkb_match_score: float?   # 0.95
└── is_new_candidate: bool     # false (기존 매칭) or true (신규 후보)
```

### 4.2 추출 관계 스키마 (Parquet)

```
patent_relations.parquet
├── patent_id: string
├── subject_normalized: string  # "ALD"
├── predicate: string           # "produces"
├── object_normalized: string   # "HfO2 thin film"
├── confidence: float
├── subject_sdkb_id: string?    # "subprocess:ald"
├── object_sdkb_id: string?     # "material:hfO2"
└── is_novel_relation: bool     # true if both matched but relation is new
```

### 4.3 보강 후보 스키마 (JSON)

```json
{
  "enrichment_candidates": {
    "new_nodes": [
      {
        "proposed_id": "material:tdmah_precursor",
        "type": "Material",
        "canonical_name": "Tetrakis(dimethylamido)hafnium",
        "synonyms": ["TDMAH", "Hf(NMe2)4"],
        "evidence_patents": ["US20230123456A1", "US20240234567A1"],
        "evidence_count": 47,
        "confidence": 0.92,
        "proposed_cpc": "C23C 16/455",
        "proposed_relations": [
          {"predicate": "usedInProcess", "object": "subprocess:ald"}
        ]
      }
    ],
    "node_enrichments": [
      {
        "existing_id": "subprocess:ald",
        "enrichments": {
          "new_synonyms": ["atomic layer deposition", "ALD process"],
          "parameter_ranges": {
            "temperature": {"min": 150, "max": 400, "unit": "°C", "typical": 300},
            "pressure": {"min": 0.1, "max": 10, "unit": "Torr"}
          },
          "cpc_mapping": "C23C 16/455",
          "patent_count": 3240,
          "trend": {"2020": 580, "2021": 612, "2022": 650, "2023": 690, "2024": 708}
        }
      }
    ],
    "new_relations": [
      {
        "subject": "subprocess:ald",
        "predicate": "usedForApplication",
        "object": "Gate Dielectric",
        "evidence_count": 892,
        "confidence": 0.95
      }
    ]
  },
  "statistics": {
    "total_patents_processed": 62000,
    "total_entities_extracted": 185000,
    "unique_entities": 4200,
    "matched_to_sdkb": 890,
    "new_candidates": 3310,
    "total_relations_extracted": 92000,
    "novel_relations": 15600
  }
}
```

### 4.4 SDKB 온톨로지 반영 형태 (Turtle)

```turtle
@prefix sdkb-data: <https://w3id.org/sdkb/data/> .
@prefix sdkb-ont:  <https://w3id.org/sdkb/ont/> .
@prefix semi:      <http://w3id.org/SemicONTO/> .
@prefix skos:      <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:      <http://www.w3.org/ns/prov#> .
@prefix xsd:       <http://www.w3.org/2001/XMLSchema#> .

# ── 기존 노드 보강 예시 ──
sdkb-data:subprocess/ald
    skos:altLabel "atomic layer deposition"@en ,
                  "ALD process"@en ,
                  "원자층 증착"@ko ;          # KIPRIS에서 수집
    sdkb-ont:cpcPrimary "C23C 16/455" ;
    sdkb-ont:typicalTempRange [ sdkb-ont:minValue 150 ;
                                sdkb-ont:maxValue 400 ;
                                sdkb-ont:unit "°C" ] ;
    sdkb-ont:patentCount 3240 ;
    sdkb-ont:enrichedBy sdkb-data:activity/patent_nlp_2026q2 .

# ── 신규 노드 (검증 후 추가) ──
sdkb-data:material/tdmah_precursor
    a semi:Material ;
    skos:prefLabel "Tetrakis(dimethylamido)hafnium"@en ;
    skos:altLabel "TDMAH"@en , "Hf(NMe2)4"@en ;
    sdkb-ont:usedInProcess sdkb-data:subprocess/ald ;
    sdkb-ont:cpcSource "C23C 16/455" ;
    sdkb-ont:confidence 0.92 ;
    sdkb-ont:validationStatus "approved" ;  # expert review 후
    sdkb-ont:evidencePatentCount 47 ;
    prov:wasDerivedFrom sdkb-data:activity/patent_nlp_2026q2 .

# ── 출처 기록 (PROV-O) ──
sdkb-data:activity/patent_nlp_2026q2
    a prov:Activity ;
    rdfs:label "Patent abstract NLP extraction (2026 Q2)" ;
    prov:startedAtTime "2026-05-01T00:00:00"^^xsd:dateTime ;
    prov:wasAssociatedWith sdkb-data:agent/sdkb_pipeline ;
    prov:used sdkb-data:source/google_patents_bigquery .

sdkb-data:source/google_patents_bigquery
    a prov:Entity ;
    rdfs:label "Google Patents Public Dataset (BigQuery)" ;
    rdfs:seeAlso <https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data> .
```

---

## 5. 기술 트렌드 분석 모듈

### 5.1 CPC별 특허 수 시계열

```python
# scripts/analyze_patent_trends.py
def compute_cpc_trends(df: pd.DataFrame) -> pd.DataFrame:
    """CPC 서브그룹별 연도별 특허 수 집계."""
    df["year"] = df["filing_date"].str[:4].astype(int)
    # CPC를 Main Group 레벨 (H01L 21/30) 로 집계
    df["cpc_main"] = df["cpc_codes"].apply(
        lambda codes: [c[:10].strip() for c in codes]
    )
    exploded = df.explode("cpc_main")
    trends = exploded.groupby(["cpc_main", "year"]).size().reset_index(name="count")
    return trends.pivot(index="cpc_main", columns="year", values="count").fillna(0)
```

### 5.2 분석 활용

| 분석 유형 | 방법 | SDKB 활용 |
|-----------|------|----------|
| **신흥 기술 식별** | 최근 3년 CAGR > 20% CPC 코드 | 갭 분석 우선순위 (이 기술이 SDKB에 있는가?) |
| **쇠퇴 기술 식별** | 최근 3년 연속 감소 | 기존 노드 `deprecated` 후보 |
| **기술 융합 탐지** | 동일 특허에 공존하는 CPC 쌍 빈도 | 새로운 `relatedTo` 엣지 후보 |
| **지역별 강점** | 국가별 CPC 분포 | 한국 기업 기술 포트폴리오 분석 |

---

## 6. 실행 계획 상세

### Step 1: 환경 준비 (2일)

| 태스크 | 상세 |
|--------|------|
| 1.1 | Google Cloud 프로젝트 생성 + BigQuery API 활성화 |
| 1.2 | PatentsView API 키 발급 |
| 1.3 | KIPRIS API 키 발급 (공공데이터포털) |
| 1.4 | Python 의존성 추가: `google-cloud-bigquery`, `sentence-transformers`, `spacy` |
| 1.5 | spaCy 모델 다운로드: `en_core_web_trf` |

```toml
# pyproject.toml 추가 의존성
[project.optional-dependencies]
patent = [
    "google-cloud-bigquery>=3.0",
    "db-dtypes",
    "sentence-transformers>=2.0",
    "spacy>=3.7",
    "tqdm",
]
```

### Step 2: 특허 데이터 수집 (3일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 2.1 | BigQuery SQL 실행 — 6개 CPC 서브트리 초록 수집 | GCS → 로컬 Parquet |
| 2.2 | PatentsView API — 보조 데이터 수집 (청구항 등) | `data/external/patentsview_*.parquet` |
| 2.3 | KIPRIS API — 한국 반도체 특허 초록 1만건 수집 | `data/external/kipris_abstracts.parquet` |
| 2.4 | 데이터 품질 검사 — 중복 제거, 빈 초록 필터링 | `data/external/patent_abstracts.parquet` (정제본) |

```
산출물 크기 예상:
├── patent_abstracts.parquet       ~150MB (60K건, 영문)
├── patentsview_claims.parquet     ~50MB (보조)
└── kipris_abstracts.parquet       ~30MB (10K건, 한국어)
```

### Step 3: 전처리 (2일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 3.1 | 문장 분리 (spaCy sentencizer) | 초록 → 문장 단위 |
| 3.2 | 약어 사전 구축 (ALD, CVD, CMP, EUV...) | `config/abbreviations.json` |
| 3.3 | CPC 코드 → 도메인 태그 매핑 | 초록에 도메인 컨텍스트 부여 |
| 3.4 | SDKB 기존 노드 gazetteer 생성 | `config/sdkb_gazetteer.jsonl` |

### Step 4: NER + RE 추출 (5일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 4.1 | spaCy 규칙 기반 NER 파이프라인 구현 | `scripts/extract_patent_entities.py` |
| 4.2 | 화학식 패턴 매처 (regex) | SiO₂, HfO₂, TaN 등 |
| 4.3 | 파라미터 수치 추출기 (regex + 단위 인식) | 온도, 압력, 전력, 유량, 두께 |
| 4.4 | LLM 기반 관계 추출 (고부가가치 초록 대상) | `scripts/extract_patent_relations_llm.py` |
| 4.5 | 배치 처리 실행 (60K건 × spaCy + 12K건 × LLM) | `data/patent_entities.parquet`, `data/patent_relations.parquet` |

**처리 시간 예상:**
- spaCy NER: 60K건 × ~0.1초 = ~100분
- LLM RE: 12K건 × ~2초 = ~7시간 (배치 API 활용 시 ~2시간)

### Step 5: 엔티티 링킹 + 보강 후보 생성 (3일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 5.1 | SDKB 198노드 대비 추출 엔티티 매칭 | `data/reports/patent_entity_linking.json` |
| 5.2 | 신규 후보 노드 생성 (evidence_count ≥ 10) | 10회 이상 등장한 미매칭 엔티티만 |
| 5.3 | 기존 노드 보강 데이터 집계 (동의어, 파라미터 범위) | 노드별 통계 |
| 5.4 | 관계 후보 생성 (confidence ≥ 0.7, count ≥ 5) | 고빈도·고신뢰 관계만 |
| 5.5 | 기술 트렌드 분석 | `data/reports/patent_trends.json` |
| 5.6 | 통합 보강 리포트 생성 | `data/reports/patent_enrichment_candidates.json` |

### Step 6: 한국어 용어 매핑 (2일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 6.1 | KIPRIS 한국어 초록에서 NER (한국어 spaCy/KoNLPy) | 한국어 기술 용어 추출 |
| 6.2 | 한-영 용어 쌍 매칭 (동일 IPC 특허 패밀리 활용) | `data/external/ko_en_terms.csv` |
| 6.3 | SDKB 노드에 `skos:altLabel` (한국어) 후보 생성 | 기존 노드 한국어 라벨 보강 |

### Step 7: 전문가 검증 + 온톨로지 반영 (3일)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 7.1 | 신규 후보 노드 우선순위 정렬 (confidence × evidence_count) | 검증 시트 |
| 7.2 | 전문가 검증 (approve / reject / merge) | 검증 결과 기록 |
| 7.3 | 승인된 노드·관계를 TTL로 변환 | `ontology/sdkb-patent-enrichment.ttl` |
| 7.4 | 기존 노드 보강 (동의어, 파라미터, CPC 코드) 반영 | 기존 TTL 업데이트 |
| 7.5 | SHACL 검증 | `data/reports/enrichment_validation.json` |
| 7.6 | 테스트 | `tests/test_patent_enrichment.py` |

### Step 8: 배포 (1일)

| 태스크 | 산출물 |
|--------|--------|
| 8.1 | CHANGELOG 업데이트 | `CHANGELOG.md` |
| 8.2 | README 보강 섹션 추가 | `README.md` |
| 8.3 | GitHub 커밋·태그 | `v1.2-patent-enrichment` |

---

## 7. 프로젝트 파일 구조 (예정)

```
sdkb/
├── data/
│   ├── external/
│   │   ├── patent_abstracts.parquet       # ★ BigQuery 수집 (60-80K건)
│   │   ├── patentsview_claims.parquet     # ★ 보조 데이터
│   │   ├── kipris_abstracts.parquet       # ★ 한국어 초록
│   │   └── ko_en_terms.csv               # ★ 한-영 용어 쌍
│   ├── patent_entities.parquet            # ★ NER 추출 결과
│   ├── patent_relations.parquet           # ★ RE 추출 결과
│   └── reports/
│       ├── patent_entity_linking.json     # ★ 엔티티 링킹 결과
│       ├── patent_enrichment_candidates.json  # ★ 보강 후보 종합
│       └── patent_trends.json             # ★ 기술 트렌드 분석
├── ontology/
│   └── sdkb-patent-enrichment.ttl         # ★ 특허 기반 보강 트리플
├── config/
│   ├── abbreviations.json                 # ★ 반도체 약어 사전
│   └── sdkb_gazetteer.jsonl               # ★ NER용 사전
├── scripts/
│   ├── collect_bigquery.py                # ★ BigQuery 수집
│   ├── collect_patentsview.py             # ★ PatentsView 수집
│   ├── collect_kipris.py                  # ★ KIPRIS 수집
│   ├── extract_patent_entities.py         # ★ NER 파이프라인
│   ├── extract_patent_relations_llm.py    # ★ LLM 관계 추출
│   ├── link_patent_entities.py            # ★ 엔티티 링킹
│   ├── analyze_patent_trends.py           # ★ 트렌드 분석
│   └── generate_enrichment_ttl.py         # ★ TTL 변환
└── tests/
    └── test_patent_enrichment.py          # ★ 보강 검증 테스트
```

---

## 8. 일정 요약

| 주차 | Step | 기간 | 주요 활동 |
|------|------|------|----------|
| W1 | Step 1-2 | 5일 | 환경 준비 + 데이터 수집 |
| W2 | Step 3-4 | 7일 | 전처리 + NER/RE 추출 |
| W3 | Step 5-8 | 8일 | 엔티티 링킹 + 검증 + 배포 |

**총 소요: 약 3주 (20 working days)**

---

## 9. 비용 추정

| 항목 | 예상 비용 |
|------|----------|
| Google BigQuery 쿼리 | 무료 (1TB 이내) |
| GCS 저장소 (임시) | ~$0.50 (200MB × $0.023/GB·월) |
| PatentsView API | 무료 |
| KIPRIS API | 무료 |
| LLM API (12K건 × ~500 토큰) | ~$15-30 (Claude Haiku/GPT-4o-mini) |
| sentence-transformers (로컬 GPU) | 무료 (CPU로도 가능) |
| **합계** | **~$20-35** |

---

## 10. 품질 관리

### 10.1 정확도 목표

| 지표 | 목표 |
|------|------|
| NER Precision | ≥ 85% (100건 수동 샘플 검증) |
| NER Recall | ≥ 75% |
| Entity Linking Accuracy | ≥ 90% (기존 노드 매칭 시) |
| Relation Extraction Precision | ≥ 80% |

### 10.2 검증 방법

1. **샘플 검증**: 100건 초록 수동 NER/RE → 자동 결과와 대조
2. **교차 검증**: 동일 엔티티가 다수 특허에서 일관적으로 추출되는지 확인
3. **전문가 합의**: 신규 후보 노드는 2인 이상 전문가 승인

### 10.3 재현성

- 모든 스크립트에 `--seed` 파라미터 (결정론적 실행)
- BigQuery SQL 쿼리를 `scripts/sql/` 에 버전 관리
- LLM 프롬프트를 `config/prompts/` 에 버전 관리
- 추출 결과 Parquet에 메타데이터 (모델 버전, 처리 일시) 기록

---

## 11. 리스크 및 대응

| 리스크 | 영향 | 발생 확률 | 대응 |
|--------|------|----------|------|
| BigQuery 쿼리 1TB 초과 | 과금 ($6.25/TB) | 낮음 | CPC 서브트리 분할 쿼리, `--dry-run` 으로 사전 용량 확인 |
| NER 정확도 목표 미달 | 오류 엔티티 유입 | 중간 | confidence 임계값 상향, evidence_count 필터 강화 |
| LLM API 비용 초과 | 예산 초과 | 낮음 | Haiku/Mini 모델 사용, 대상 초록 수 제한 |
| 한국어 NER 정확도 저하 | 한-영 매핑 품질 저하 | 중간 | 특허 패밀리 기반 매칭으로 보완 (같은 발명의 한·영 버전 활용) |
| 중복 엔티티 과다 | 정규화 실패 | 중간 | 2단계 정규화 (퍼지 + 임베딩), 수동 클러스터 병합 |

---

## 12. 선행 사례 (Prior Art)

| 프로젝트 | 접근 방식 | SDKB 참고 사항 |
|----------|----------|--------------|
| **MatKG** (Scientific Data 2024) | 500만 논문 초록 NER → 70K 엔티티 | 동일 패턴, SDKB는 특허 초록 대상 |
| **SciKGTeX** (ISWC 2023) | 논문에서 온톨로지 자동 추출 | NLP→온톨로지 변환 파이프라인 참조 |
| **PatCit** (EPO/WIPO) | 특허 인용 네트워크 분석 | 기술 영향력 분석 방법론 참조 |
| **DeepPatent** (ACL 2020) | 특허 분류 자동화 | CPC 예측 모델 활용 가능 |

---

*이 문서는 `architecture_redesign_semiconto_hub.md` Phase 3.5와 연동된다.*
*Step 1 착수 전 Google Cloud 프로젝트 설정 및 API 키 확보가 선행되어야 한다.*
