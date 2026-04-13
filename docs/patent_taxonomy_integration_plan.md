# SDKB × 특허 기술분류 택소노미 통합 계획

> **문서 버전**: v1.0 (2026-04-13)
> **작성자**: SDKB 프로젝트 팀
> **상태**: 계획 수립 단계 (Planning)

---

## 1. 배경 및 목적

### 1.1 현황 분석

SDKB v0.3 베이스라인(198개 노드, 264개 엣지)은 반도체 제조 도메인 전문가의 지식을
기반으로 구축되었으나, 다음 한계가 존재한다:

| 한계 | 설명 |
|------|------|
| 분류 체계 부재 | 노드가 14개 유형으로만 구분되며, 국제 표준 기술분류와 연결 없음 |
| 계층 깊이 부족 | Process→SubProcess 2단계만 존재, 기술 세분화 한계 |
| 외부 상호운용성 제한 | 타 지식베이스(SemiKong, MatKG)와의 정합을 위한 중재 체계 없음 |
| 기술 범위 검증 불가 | 현재 온톨로지가 반도체 기술 전체를 얼마나 커버하는지 정량화 불가 |

### 1.2 목적

국제 특허 기술분류 체계(CPC, IPC, F-term)를 **참조 택소노미(Reference Taxonomy)**로
도입하여:

1. SDKB 노드에 국제 표준 분류 코드를 매핑하여 **상호운용성** 확보
2. 분류 체계의 계층 구조를 활용한 **택소노미 깊이 확장**
3. 특허 분류의 포괄 범위 대비 SDKB 커버리지를 측정하여 **갭 분석** 수행
4. F-term 패싯 구조를 참조한 **다면적 분류 축** 도입

---

## 2. 특허 기술분류 체계 분석

### 2.1 CPC (Cooperative Patent Classification)

- **관리**: USPTO + EPO 공동 운영
- **구조**: 계층적 (Section → Class → Subclass → Main Group → Subgroup)
- **규모**: ~260,000 심볼, IPC 대비 약 3.5배 세분화
- **갱신**: 월 1회 정기 개정
- **공개 형태**: XML/TSV bulk download (USPTO PatentsView)

**반도체 관련 핵심 CPC 서브트리:**

```
H01L — 반도체 소자 (Semiconductor Devices)
├── H01L 21    제조 공정 (Manufacturing Processes)
│   ├── 21/02  재료·기판
│   ├── 21/027 리소그래피 (포토, EUV)
│   ├── 21/28  박막 성막 (PVD, CVD, ALD)
│   ├── 21/30  식각 (건식, 습식)
│   ├── 21/321 CMP (화학기계연마)
│   ├── 21/44  이온주입
│   ├── 21/66  측정·검사
│   └── 21/67  장비·설비 (핸들링, 척, 챔버)
├── H01L 23    패키징·접속 구조
├── H01L 25    다수 소자 조립체
├── H01L 27    집적회로 (DRAM, SRAM, Logic)
├── H01L 29    개별 반도체 소자 (FinFET, GAA, MOSFET)
└── H01L 33    LED (광소자)

H10B — 전자 메모리 소자 (2023년 이관)
├── H10B 41    NAND Flash
├── H10B 43    NOR Flash
├── H10B 12    DRAM
└── H10B 63    MRAM, ReRAM, PCRAM

G03F — 포토리소그래피 (마스크, 노광 시스템)
├── G03F 7     포토레지스트 공정
└── G03F 9     얼라인먼트·오버레이

C23C — 코팅·박막 (재료 관점)
├── C23C 14    PVD 코팅
├── C23C 16    CVD 코팅
└── C23C 18    무전해 도금

B24B — 연마 (CMP 장비 관점)
└── B24B 37    CMP 연마 장치
```

### 2.2 IPC (International Patent Classification)

- **관리**: WIPO
- **구조**: CPC의 상위 호환 (CPC가 IPC를 세분화한 것)
- **규모**: ~75,000 심볼
- **용도**: 국제 정합성 — 한국(KIPO), 중국(CNIPA), 일본(JPO) 모두 IPC 기반
- **SDKB 활용**: CPC 매핑의 상위 레벨 브릿지로 사용

**IPC-CPC 관계:**
```
IPC  H01L 21/3065  (플라즈마 식각 - 일반)
 └── CPC  H01L 21/30655  (플라즈마 식각 - 다층 레지스트)
      └── CPC  H01L 21/30658  (반응성 이온 식각 - 고종횡비)
```

### 2.3 F-term (일본 FI/F-term 분류)

- **관리**: JPO (일본 특허청)
- **핵심 특성**: **패싯(Facet) 기반 다면적 분류**
- **구조**: 테마코드 → 관점(Viewpoint) → 항목 번호
- **강점**: 하나의 기술을 목적·재료·구조·공정조건 등 여러 축으로 동시 분류

**반도체 관련 핵심 테마:**

| 테마코드 | 명칭 | SDKB 매핑 대상 |
|----------|------|----------------|
| 5F004 | 반도체 소자 일반 | Process, SubProcess |
| 5F033 | 반도체 결정성장 | Material, Deposition |
| 5F045 | 기억장치 제조 | TechnologyNode, DRAM/NAND |
| 5F058 | 반도체 식각 | Etch SubProcess, Parameter |
| 5F140 | 배선 형성 방법 | Deposition, Material |
| 5F146 | CMP | CMP SubProcess, Parameter |
| 5F063 | 레지스트 감광 | Lithography, Material |

**F-term 패싯 구조 예시 (5F058 반도체 식각):**
```
테마: 5F058  반도체 식각
├── 관점A: 공정 종류     → {AA, AB, AC...} (건식, 습식, RIE, ICP...)
├── 관점B: 피식각 재료   → {BA, BB, BC...} (Si, SiO2, Metal, PR...)
├── 관점C: 식각 가스     → {CA, CB, CC...} (CF4, SF6, Cl2, BCl3...)
├── 관점D: 공정 조건     → {DA, DB, DC...} (온도, 압력, RF파워...)
├── 관점E: 목적·효과     → {EA, EB, EC...} (선택비, 균일성, CD제어...)
└── 관점F: 소자 구조     → {FA, FB, FC...} (트렌치, 비아, 게이트...)
```

이 패싯 구조는 SDKB의 `Process → Parameter`, `Process → Material` 관계를 풍부하게 보강하는 데 직접 활용 가능하다.

---

## 3. 통합 설계

### 3.1 아키텍처 개요

```
┌─────────────────────────────────────────────────────┐
│                    SDKB Core Ontology                │
│  (Process, Equipment, Material, FailureMode, ...)    │
└────────────┬───────────────────────┬────────────────┘
             │ skos:exactMatch       │ skos:closeMatch
             │ skos:broadMatch       │ skos:narrowMatch
             ▼                       ▼
┌────────────────────┐   ┌─────────────────────┐
│  CPC/IPC Taxonomy  │   │  F-term Facet Index  │
│  (SKOS Concept     │   │  (Multi-dimensional  │
│   Scheme, 계층적)   │   │   faceted scheme)    │
└────────────────────┘   └─────────────────────┘
```

### 3.2 네임스페이스 설계

| Prefix | URI | 용도 |
|--------|-----|------|
| `cpc:` | `https://worldwide.espacenet.com/classification/cpc/` | CPC 심볼 |
| `ipc:` | `https://www.wipo.int/ipc/itos4ipc/ITSupport_and_download_area/` | IPC 심볼 |
| `fterm:` | `https://www.j-platpat.inpit.go.jp/fterm/` | F-term 테마·패싯 |
| `skos:` | `http://www.w3.org/2004/02/skos/core#` | 매핑 관계 어휘 |

### 3.3 SKOS 매핑 속성 사용 기준

| SKOS 속성 | 사용 조건 | 예시 |
|-----------|----------|------|
| `skos:exactMatch` | SDKB 개념과 CPC 심볼이 1:1 대응 | `sdkb:Lithography ↔ H01L 21/027` |
| `skos:closeMatch` | 의미적으로 거의 동일하나 범위 미세 차이 | `sdkb:PVD ↔ C23C 14` |
| `skos:broadMatch` | CPC가 SDKB 개념보다 넓은 범위 | `sdkb:PlasmaEtch ← H01L 21/3065` |
| `skos:narrowMatch` | F-term 패싯이 SDKB보다 세분화 | `sdkb:Etch → 5F058-관점A` |
| `skos:relatedMatch` | 관련은 있으나 직접 대응 아님 | `sdkb:FailureMode ~ G01N (검사)` |

### 3.4 데이터 모델 (Turtle 예시)

```turtle
@prefix sdkb-data: <https://w3id.org/sdkb/data/> .
@prefix sdkb-ont:  <https://w3id.org/sdkb/ont/> .
@prefix cpc:       <https://worldwide.espacenet.com/classification/cpc/> .
@prefix fterm:     <https://www.j-platpat.inpit.go.jp/fterm/> .
@prefix skos:      <http://www.w3.org/2004/02/skos/core#> .

# ── SDKB 노드 → CPC 매핑 ──
sdkb-data:process/lithography
    skos:exactMatch  cpc:H01L21-027 ;
    skos:relatedMatch cpc:G03F7 ;
    sdkb-ont:cpcPrimary "H01L 21/027" .

sdkb-data:subprocess/plasma_etch
    skos:exactMatch  cpc:H01L21-3065 ;
    skos:closeMatch  cpc:H01L21-30655 ;
    sdkb-ont:cpcPrimary "H01L 21/3065" .

# ── SDKB 노드 → F-term 패싯 매핑 ──
sdkb-data:subprocess/plasma_etch
    skos:narrowMatch fterm:5F058-AA ;   # 공정 종류: 건식 식각
    skos:narrowMatch fterm:5F058-CA01 . # 식각 가스: CF4

# ── CPC 개념 자체 (SKOS ConceptScheme) ──
cpc:H01L21-027 a skos:Concept ;
    skos:prefLabel "Lithography processes"@en ;
    skos:prefLabel "리소그래피 공정"@ko ;
    skos:broader cpc:H01L21 ;
    skos:inScheme <https://worldwide.espacenet.com/classification/cpc/scheme> .
```

---

## 4. 실행 계획

### Phase 1: 데이터 수집 및 SKOS 변환 (2주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| **1.1** CPC 스키마 다운로드 | USPTO bulk data에서 H01L, H10B, G03F, C23C, B24B 서브트리 XML 추출 | `data/external/cpc_h01l_raw.xml` |
| **1.2** CPC→SKOS 변환 스크립트 | XML 파싱, `skos:Concept`, `skos:broader/narrower` 트리플 생성 | `scripts/ingest_cpc.py` → `ontology/cpc-semiconductor.ttl` |
| **1.3** IPC 상위 매핑 추출 | WIPO IPC XML에서 H01L 서브트리, CPC↔IPC 대응표 생성 | `mappings/ipc_cpc_bridge.ttl` |
| **1.4** F-term 테마 수집 | J-PlatPat에서 5F004, 5F033, 5F045, 5F058, 5F140, 5F146, 5F063 테마 수집 | `data/external/fterm_themes.json` |
| **1.5** F-term→SKOS 변환 | 패싯 구조를 `skos:Collection` + `skos:Concept`으로 모델링 | `ontology/fterm-semiconductor.ttl` |

### Phase 2: SDKB ↔ 분류체계 매핑 (2주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| **2.1** 자동 후보 생성 | 기존 `align_candidates.py`를 확장, CPC/F-term 레이블 대상 rapidfuzz + 임베딩 매칭 | `scripts/align_patent_taxonomy.py` |
| **2.2** SDKB 198노드 → CPC 매핑 | 자동 후보(Top-5) 기반 전문가 검증, 확정 매핑 생성 | `mappings/sdkb_cpc_alignment.ttl` |
| **2.3** SDKB → F-term 패싯 매핑 | Process/SubProcess/Material 노드 대상 다면적 매핑 | `mappings/sdkb_fterm_alignment.ttl` |
| **2.4** 매핑 품질 검증 | 매핑 커버리지율, 정밀도 측정 (목표: 80% 이상 노드 매핑) | `data/reports/alignment_quality.json` |

### Phase 3: 갭 분석 및 온톨로지 확장 (2주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| **3.1** 커버리지 갭 분석 | CPC 서브트리 중 SDKB에 대응 노드가 없는 영역 식별 | `data/reports/coverage_gap.json` |
| **3.2** 확장 후보 노드 제안 | 갭 분석 결과에서 우선순위 높은 기술 영역 선정 | `data/reports/expansion_candidates.json` |
| **3.3** 택소노미 계층 심화 | CPC 계층 참조하여 Process→SubProcess 아래 3단계 추가 가능성 검토 | (설계 문서) |
| **3.4** SPARQL 분석 쿼리 | 매핑/갭 분석용 SPARQL 쿼리 작성 | `examples/sparql/04_cpc_coverage.rq` |

### Phase 4: 통합 및 검증 (1주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| **4.1** 네임스페이스 등록 | `config/namespaces.py`에 CPC, IPC, F-term 네임스페이스 추가 | (코드 수정) |
| **4.2** JSON-LD 컨텍스트 갱신 | `config/context.jsonld`에 매핑 속성 추가 | (코드 수정) |
| **4.3** SHACL 검증 규칙 추가 | 매핑 필수성, CPC 코드 형식 검증 등 | `validation/shapes_taxonomy.ttl` |
| **4.4** 통합 테스트 | 파이프라인 전체 실행, 트리플 수 검증, 매핑 일관성 검사 | `tests/test_taxonomy.py` |
| **4.5** GitHub 푸시 | 전체 산출물 커밋·태그 | `v1.1-taxonomy` 태그 |

---

## 5. 데이터 소스 및 접근 방법

### 5.1 CPC Bulk Data (USPTO)

- **URL**: https://bulkdata.uspto.gov/data/patent/classification/cpc/
- **형식**: US Patent Classification Data (XML, ZIP)
- **용량**: 전체 ~2GB, 반도체 서브트리 추출 시 ~50MB
- **라이선스**: Public Domain (미국 정부 저작물)
- **갱신**: 매월

### 5.2 IPC (WIPO)

- **URL**: https://www.wipo.int/classifications/ipc/en/ITsupport/Version20240101/
- **형식**: XML
- **라이선스**: WIPO 이용 약관 준수 (비상업적 연구 가능)

### 5.3 F-term (J-PlatPat)

- **URL**: https://www.j-platpat.inpit.go.jp/
- **접근**: 웹 인터페이스 + PDF 매뉴얼
- **제약**: Bulk download 미제공 → 테마별 수동 수집 또는 스크래핑 필요
- **대안**: JPO 공개 F-term 리스트 (CSV)를 활용

---

## 6. 기대 효과

### 6.1 정량적 목표

| 지표 | 현재 (v0.3) | 목표 (v1.1) |
|------|------------|------------|
| 노드 수 | 198 | 198 + α (갭 분석 후 확장) |
| 국제 분류 매핑 비율 | 0% | ≥ 80% (CPC 기준) |
| 택소노미 계층 깊이 | 2단계 | 3~4단계 |
| CPC 커버리지 (H01L 21 대비) | 미측정 | 측정 및 리포트 |
| 외부 상호운용성 | SKOS 레이블만 | CPC/IPC/F-term SKOS 매핑 |

### 6.2 정성적 효과

1. **특허 분석 연계**: SDKB 노드로 특허 검색 시 CPC 코드 자동 매핑 가능
2. **기술 갭 시각화**: CPC 트리 위에 SDKB 커버리지를 시각화하여 빈 영역 식별
3. **다면적 탐색**: F-term 패싯으로 "이 공정에 쓰이는 재료는?" "이 가스를 쓰는 공정은?" 등 교차 질의 가능
4. **학술 기여**: 반도체 도메인 온톨로지와 특허 분류 체계의 정합성 연구로서 MOT 박사 논문 기여

---

## 7. 리스크 및 대응

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| CPC XML 스키마 변경 | 파서 오류 | 버전 고정 + 변경 감지 스크립트 |
| F-term 접근 제한 | 데이터 수집 지연 | JPO 공개 리스트 우선 활용, 필요 시 수동 입력 |
| 매핑 모호성 | 1:N 매핑 과다 | `skos:exactMatch` 1개 + `skos:relatedMatch` N개로 구분 |
| 한국어 레이블 부재 (CPC) | 자동 매칭 정확도 저하 | 영문 레이블 기반 매칭 + 한국어 동의어(synonym) 보강 |
| 데이터 용량 증가 | 저장·처리 부담 | 반도체 서브트리만 선택적 추출 |

---

## 8. 프로젝트 파일 구조 (예정)

```
sdkb/
├── data/
│   ├── external/                 # ★ 신규
│   │   ├── cpc_h01l_raw.xml     # CPC 원본 (H01L 서브트리)
│   │   ├── cpc_h10b_raw.xml     # CPC 원본 (H10B 서브트리)
│   │   ├── ipc_h01l_raw.xml     # IPC 원본
│   │   └── fterm_themes.json    # F-term 테마 데이터
│   ├── reports/                  # ★ 신규
│   │   ├── alignment_quality.json
│   │   └── coverage_gap.json
│   └── semiconductor_v0_3.json
├── ontology/
│   ├── sdkb-core.ttl
│   ├── cpc-semiconductor.ttl    # ★ 신규: CPC SKOS 서브트리
│   └── fterm-semiconductor.ttl  # ★ 신규: F-term SKOS 패싯
├── mappings/
│   ├── sdkb_cpc_alignment.ttl   # ★ 신규: SDKB↔CPC 매핑
│   ├── sdkb_fterm_alignment.ttl # ★ 신규: SDKB↔F-term 매핑
│   └── ipc_cpc_bridge.ttl       # ★ 신규: IPC↔CPC 브릿지
├── scripts/
│   ├── ingest_cpc.py            # ★ 신규: CPC XML→SKOS 변환
│   ├── ingest_fterm.py          # ★ 신규: F-term→SKOS 변환
│   └── align_patent_taxonomy.py # ★ 신규: SDKB↔CPC/F-term 정합
├── validation/
│   └── shapes_taxonomy.ttl      # ★ 신규: 매핑 검증 SHACL
├── examples/sparql/
│   └── 04_cpc_coverage.rq       # ★ 신규: 커버리지 분석 쿼리
└── tests/
    └── test_taxonomy.py         # ★ 신규: 매핑 테스트
```

---

## 부록 A. 참고 자료

1. **CPC Scheme**: https://www.cooperativepatentclassification.org/cpcSchemeAndDefinitions
2. **USPTO Bulk Data**: https://bulkdata.uspto.gov/data/patent/classification/cpc/
3. **WIPO IPC**: https://www.wipo.int/classifications/ipc/en/
4. **J-PlatPat F-term**: https://www.j-platpat.inpit.go.jp/
5. **SKOS Reference**: https://www.w3.org/TR/skos-reference/
6. **SKOS Mapping Properties**: https://www.w3.org/TR/skos-reference/#mapping

## 부록 B. CPC-SDKB 예비 매핑 표 (상위 레벨)

| SDKB 노드 유형 | 대표 CPC 코드 | 매핑 관계 |
|----------------|---------------|----------|
| Process: Lithography | H01L 21/027, G03F 7 | exactMatch |
| Process: Etch | H01L 21/3065, H01L 21/311 | exactMatch |
| Process: Deposition | H01L 21/285, H01L 21/316 | closeMatch |
| Process: CMP | H01L 21/321, B24B 37 | exactMatch |
| Process: Implant | H01L 21/265 | exactMatch |
| Process: Diffusion | H01L 21/22 | exactMatch |
| Process: Metrology | H01L 21/66 | closeMatch |
| Process: Clean | H01L 21/02 (partial) | broadMatch |
| SubProcess: EUV Lithography | H01L 21/027 + G03F 7/20 | narrowMatch |
| SubProcess: ALD | C23C 16/455 | exactMatch |
| SubProcess: CVD | C23C 16/00 | exactMatch |
| SubProcess: PVD | C23C 14/00 | exactMatch |
| Equipment (general) | H01L 21/67 | broadMatch |
| Material (general) | H01L 21/02 (partial) | broadMatch |
| TechnologyNode: 3nm/5nm/7nm | H01L 29 (device structure) | relatedMatch |
| FailureMode | (직접 대응 없음) | — |

---

*이 문서는 Phase 1 착수 전 팀 리뷰를 거쳐 확정할 것.*
# SDKB × 특허 기술분류 택소노미 통합 계획

**문서 버전**: v1.0  
**작성일**: 2026-04-12  
**상태**: 계획 수립 (Planning)

---

## 1. 배경 및 목적

### 1.1 현황

SDKB v0.3 베이스라인은 198개 노드(14개 유형)와 264개 엣지로 구성되어 있으나,
분류 체계가 프로젝트 내부에서 자체 정의된 상태이다.
국제적으로 통용되는 표준 분류와의 연결이 없어 다음과 같은 한계가 존재한다:

- 외부 지식베이스(특허 DB, 학술 DB)와의 연계 어려움
- 분류의 완전성(completeness) 검증 기준 부재
- 기술 동향 분석(특허 통계)과의 연동 불가

### 1.2 목적

국제 특허 기술분류 체계(IPC, CPC, F-term)를 SDKB 온톨로지의 **표준 분류 백본**으로
통합하여 다음을 달성한다:

1. SDKB 노드에 국제 표준 분류 코드 부여 (SKOS 매핑)
2. 분류 계층을 활용한 택소노미 완전성 검증
3. 특허 데이터 기반 기술 동향 분석 연동 기반 확보
4. F-term 패싯 분류를 활용한 공정 파라미터 세분화

---

## 2. 특허 기술분류 체계 분석

### 2.1 IPC (International Patent Classification)

| 항목 | 내용 |
|------|------|
| 관리기관 | WIPO (세계지식재산기구) |
| 구조 | Section → Class → Subclass → Group → Subgroup (5단계) |
| 규모 | ~75,000개 심볼 |
| 갱신 주기 | 연 1회 |
| 데이터 형식 | XML, PDF (WIPO IPCPUB에서 무료 제공) |
| 라이선스 | 공개 (Public Domain) |

**반도체 관련 주요 코드:**
- `H01L` — 반도체 소자 (핵심)
- `H10B` — 전자 메모리 소자 (2023년 분리)
- `G03F` — 포토리소그래피
- `C23C` — 코팅/표면처리 (CVD/PVD)
- `B24B` — 연삭/연마 (CMP)
- `G01N` — 재료 분석/검사
- `H05K` — 인쇄 회로 (패키징)

### 2.2 CPC (Cooperative Patent Classification)

| 항목 | 내용 |
|------|------|
| 관리기관 | USPTO + EPO 공동 |
| 구조 | IPC 확장 (IPC의 상위집합) |
| 규모 | ~260,000개 심볼 (IPC의 ~3.5배) |
| 갱신 주기 | 매월 |
| 데이터 형식 | XML bulk download (USPTO), SPARQL endpoint (EPO) |
| 라이선스 | 공개 (Public Domain) |

**IPC 대비 장점:**
- 반도체 분야 세분화가 월등히 상세
- 2000-suffix를 통한 최신 기술 반영 (예: EUV, GAA-FET)
- USPC→CPC 연계 테이블 제공

**반도체 핵심 CPC 서브트리:**

```
H01L 21/       반도체 소자 제조 공정
├── 21/02      기판/재료
│   ├── 21/02104  벌크 실리콘
│   ├── 21/02107  SOI (Silicon on Insulator)
│   └── 21/02381  화합물 반도체 (III-V, SiC)
├── 21/027     리소그래피
│   ├── 21/0271   포토레지스트 도포/현상
│   ├── 21/0273   포토마스크
│   └── 21/0274   노광 기술
├── 21/3065    플라즈마 식각 (Dry Etch)
├── 21/311     습식 식각 (Wet Etch)
├── 21/285     PVD/스퍼터링
├── 21/316     CVD/ALD 성막
│   ├── 21/31604  PECVD
│   ├── 21/31616  LPCVD
│   └── 21/31683  ALD (Atomic Layer Deposition)
├── 21/321     CMP (화학적 기계적 연마)
├── 21/425     이온주입
├── 21/66      측정/검사 (계측)
│   ├── 21/67     장비/하우징
│   └── 21/68     지그/척/고정장치
└── 21/8234    다층 배선 형성

H01L 29/       개별 반도체 소자
├── 29/66      FinFET/GAA 제조
├── 29/775     FinFET 구조
└── 29/786     GAA (Gate-All-Around) 구조

H10B           전자 메모리 소자
├── 10/12      DRAM
├── 41/        NAND Flash
├── 43/        NOR Flash
├── 61/        MRAM
└── 63/        PRAM/ReRAM
```

### 2.3 F-term (일본 FI/F-term 분류)

| 항목 | 내용 |
|------|------|
| 관리기관 | JPO (일본 특허청) |
| 구조 | 테마코드 → 관점(패싯) → 분류번호 (3단계, 다면 분류) |
| 특징 | **패싯(다면) 분류** — 하나의 기술을 목적/재료/구조/공정 등 여러 축으로 동시 분류 |
| 데이터 형식 | J-PlatPat에서 개별 조회, 일부 bulk 제공 |
| 라이선스 | 정부 오픈 데이터 |

**반도체 관련 주요 테마 코드:**

| 테마 코드 | 명칭 | SDKB 매핑 대상 |
|-----------|------|---------------|
| 5F004 | 반도체장치 제조일반 | Process, SubProcess 전체 |
| 5F033 | 결정성장 | Material (기판) |
| 5F045 | 기억장치 제조 | Process (메모리 특화) |
| 5F058 | 반도체 에칭 | SubProcess (식각) |
| 5F048 | 이온주입 | SubProcess (이온주입) |
| 5F040 | 포토리소그래피 | SubProcess (리소) |
| 5F043 | 배선형성 | SubProcess (배선) |
| 5F046 | 산화/확산 | SubProcess (확산) |
| 4K029 | CVD | SubProcess (CVD/ALD) |
| 4K030 | PVD/스퍼터링 | SubProcess (PVD) |
| 3C058 | 연마장치 (CMP) | Equipment (CMP) |

**F-term 패싯 구조 예시 (5F004 반도체장치 제조일반):**

```
5F004  반도체장치의 제조일반
├── AA ── 목적/효과    → SDKB: FailureMode/Mitigation 연결
├── BA ── 공정종류     → SDKB: Process/SubProcess
├── BB ── 소자구조     → SDKB: TechnologyNode
├── CA ── 사용재료     → SDKB: Material
├── CB ── 가스종류     → SDKB: Parameter (gas_flow)
├── DA ── 장치/기구    → SDKB: Equipment
├── DB ── 처리조건     → SDKB: Parameter (temperature, pressure)
└── EA ── 측정/평가    → SDKB: Metrology
```

### 2.4 체계별 비교 요약

| 비교 항목 | IPC | CPC | F-term |
|-----------|-----|-----|--------|
| 세분화 수준 | ★★★ | ★★★★★ | ★★★★★ |
| 반도체 커버리지 | ★★★ | ★★★★★ | ★★★★★ |
| 국제 호환성 | ★★★★★ | ★★★★ | ★★ |
| 데이터 접근성 | ★★★★ | ★★★★★ | ★★★ |
| 패싯(다면) 분류 | ✗ | ✗ | ✓ |
| 파라미터 레벨 | ✗ | 일부 | ✓ |
| SDKB 활용 우선순위 | 2순위 | **1순위** | **1순위** |

---

## 3. SDKB 온톨로지 통합 설계

### 3.1 통합 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                   SDKB Core Ontology                 │
│  (Process, Equipment, Material, FailureMode, ...)    │
└────────┬───────────────┬───────────────┬────────────┘
         │               │               │
    skos:exactMatch  skos:closeMatch  skos:narrowMatch
         │               │               │
    ┌────▼────┐    ┌─────▼─────┐   ┌─────▼──────┐
    │   CPC   │    │    IPC    │   │   F-term    │
    │ Taxonomy│    │ Taxonomy  │   │   Facets    │
    │ (SKOS   │    │ (SKOS     │   │  (SKOS     │
    │ Concept │    │ Concept   │   │  Concept   │
    │ Scheme) │    │ Scheme)   │   │  Scheme)   │
    └─────────┘    └───────────┘   └────────────┘
```

### 3.2 RDF 모델링

#### 3.2.1 분류 체계를 SKOS ConceptScheme으로 표현

```turtle
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sdkb: <https://w3id.org/sdkb/ont/> .
@prefix cpc:  <https://w3id.org/sdkb/taxonomy/cpc/> .
@prefix ipc:  <https://w3id.org/sdkb/taxonomy/ipc/> .
@prefix fterm: <https://w3id.org/sdkb/taxonomy/fterm/> .

# CPC ConceptScheme
cpc:scheme a skos:ConceptScheme ;
    skos:prefLabel "CPC - Cooperative Patent Classification"@en ;
    skos:prefLabel "CPC 특허분류"@ko ;
    dct:publisher "USPTO/EPO" ;
    dct:source <https://www.cooperativepatentclassification.org/> .

# CPC Concept 예시
cpc:H01L21 a skos:Concept ;
    skos:inScheme cpc:scheme ;
    skos:prefLabel "Processes or apparatus adapted for semiconductor devices"@en ;
    skos:prefLabel "반도체 소자 제조 공정"@ko ;
    skos:notation "H01L 21/00" ;
    skos:broader cpc:H01L .

cpc:H01L21-3065 a skos:Concept ;
    skos:inScheme cpc:scheme ;
    skos:prefLabel "Plasma etching"@en ;
    skos:prefLabel "플라즈마 식각"@ko ;
    skos:notation "H01L 21/3065" ;
    skos:broader cpc:H01L21 .
```

#### 3.2.2 SDKB 노드 ↔ 분류 코드 매핑

```turtle
# SDKB Process 노드 → CPC/IPC/F-term 매핑
sdkb-data:process/etch
    skos:exactMatch  cpc:H01L21-3065 ;     # CPC: Plasma etching
    skos:broadMatch  ipc:H01L21-3065 ;     # IPC (동일 코드, 넓은 범위)
    skos:closeMatch  fterm:5F058 ;          # F-term: 반도체 에칭
    sdkb:cpcCode     "H01L 21/3065" ;       # 리터럴 편의 속성
    sdkb:ftermTheme  "5F058" .

sdkb-data:subprocess/ald
    skos:exactMatch  cpc:H01L21-31683 ;    # CPC: ALD
    skos:closeMatch  fterm:4K029 ;          # F-term: CVD
    sdkb:cpcCode     "H01L 21/31683" .

sdkb-data:material/hfO2
    skos:narrowMatch fterm:5F004-CA ;       # F-term 재료 패싯
    sdkb:ftermFacet  "5F004/CA" .
```

#### 3.2.3 SKOS 매핑 관계 사용 기준

| 관계 | 조건 | 예시 |
|------|------|------|
| `skos:exactMatch` | SDKB 개념 = 분류 코드 범위 1:1 | etch ↔ H01L 21/3065 |
| `skos:closeMatch` | 의미적으로 거의 동일, 범위 약간 차이 | etch ↔ 5F058 |
| `skos:broadMatch` | 분류 코드가 SDKB보다 넓음 | lithography ↔ H01L 21/027 (EUV+DUV+...) |
| `skos:narrowMatch` | 분류 코드가 SDKB보다 좁음 | deposition ↔ H01L 21/31683 (ALD만) |
| `skos:relatedMatch` | 관련은 있으나 직접 대응 아님 | failuremode ↔ (특허에 직접 분류 없음) |

### 3.3 OWL 확장 — 분류 속성 추가

```turtle
# 신규 Datatype Properties
sdkb:cpcCode a owl:DatatypeProperty ;
    rdfs:label "CPC classification code"@en ;
    rdfs:domain sdkb:CoreNode ;
    rdfs:range xsd:string ;
    rdfs:comment "Cooperative Patent Classification code (e.g., H01L 21/3065)" .

sdkb:ipcCode a owl:DatatypeProperty ;
    rdfs:label "IPC classification code"@en ;
    rdfs:domain sdkb:CoreNode ;
    rdfs:range xsd:string .

sdkb:ftermTheme a owl:DatatypeProperty ;
    rdfs:label "F-term theme code"@en ;
    rdfs:domain sdkb:CoreNode ;
    rdfs:range xsd:string .

sdkb:ftermFacet a owl:DatatypeProperty ;
    rdfs:label "F-term facet code"@en ;
    rdfs:domain sdkb:CoreNode ;
    rdfs:range xsd:string .

# 신규 Object Property
sdkb:hasClassification a owl:ObjectProperty ;
    rdfs:label "has patent classification"@en ;
    rdfs:domain sdkb:CoreNode ;
    rdfs:range skos:Concept .
```

---

## 4. 데이터 소스 및 수집 방안

### 4.1 CPC 데이터

| 항목 | 내용 |
|------|------|
| 소스 | USPTO Bulk Data: `https://bulkdata.uspto.gov/data/patent/classification/cpc/` |
| 형식 | `cpc-scheme-{YYYY-MM}.xml` (전체 스키마, ~300MB) |
| 추출 범위 | H01L, H10B, G03F, C23C, B24B 서브트리 (반도체 관련만) |
| 예상 심볼 수 | ~5,000–8,000개 (반도체 서브트리) |
| 갱신 | 분기별 동기화 |

### 4.2 IPC 데이터

| 항목 | 내용 |
|------|------|
| 소스 | WIPO IPCPUB: `https://www.wipo.int/classifications/ipc/en/` |
| 형식 | XML (전체), JSON API (개별 조회) |
| 추출 범위 | CPC 추출 범위와 동일 |
| 용도 | CPC→IPC 상위 매핑 확인 |

### 4.3 F-term 데이터

| 항목 | 내용 |
|------|------|
| 소스 | J-PlatPat: `https://www.j-platpat.inpit.go.jp/` |
| 보조 소스 | JPO F-term 리스트 (PDF/Excel) |
| 추출 범위 | 5F004, 5F033, 5F040, 5F043, 5F045, 5F046, 5F048, 5F058, 4K029, 4K030, 3C058 |
| 특이사항 | API 미제공 — 수동 수집 또는 스크래핑 필요 |
| 대안 | Google Patents의 F-term 인덱스 파일 활용 |

---

## 5. 실행 계획

### Phase 1: CPC 택소노미 구축 (2주)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| W1 | CPC bulk XML 다운로드 및 반도체 서브트리 추출 스크립트 개발 | `scripts/extract_cpc.py` |
| W1 | CPC XML → SKOS RDF 변환 | `ontology/taxonomy/cpc-semiconductor.ttl` |
| W2 | SDKB 198개 노드 → CPC 코드 반자동 매핑 | `mappings/sdkb_cpc_alignment.ttl` |
| W2 | 매핑 품질 검증 (커버리지, 정확도) | `reports/cpc_mapping_quality.json` |

**세부 작업:**

```
W1-1. CPC 스키마 다운로드
      - USPTO bulk XML에서 최신 cpc-scheme 다운로드
      - H01L, H10B, G03F, C23C, B24B 서브트리 필터링

W1-2. CPC → SKOS 변환 스크립트
      - XML 파싱 → skos:Concept + skos:broader/narrower 생성
      - 영문 label + 한국어 label (수동 번역 목록 활용)
      - skos:notation에 CPC 코드 저장

W2-1. SDKB ↔ CPC 매핑
      - 자동 매핑: rapidfuzz로 label 유사도 매칭 (threshold ≥ 70)
      - 수동 검토: 반도체 전문가가 자동 매핑 결과 검증/수정
      - SKOS 매핑 관계 유형 결정 (exact/close/broad/narrow)

W2-2. 커버리지 분석
      - SDKB 노드 중 CPC 매핑됨 / 매핑안됨 비율
      - CPC에는 있으나 SDKB에 없는 개념 → 노드 추가 후보 도출
```

### Phase 2: IPC 크로스 매핑 (1주)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| W3 | CPC→IPC 크로스레퍼런스 테이블 활용 IPC 매핑 자동 생성 | `mappings/sdkb_ipc_alignment.ttl` |
| W3 | IPC 기준 국제 호환성 검증 | 검증 보고서 |

**세부 작업:**

```
W3-1. CPC↔IPC 매핑 테이블 활용
      - USPTO 제공 CPC-to-IPC concordance file 다운로드
      - SDKB→CPC 매핑에서 자동으로 IPC 매핑 유도
      - skos:broadMatch로 IPC 연결 (IPC가 CPC보다 항상 넓거나 같음)

W3-2. 국제 호환성 확인
      - 한국(KIPO), 중국(CNIPA) 특허 DB에서 IPC로 검색 가능 확인
      - SDKB 노드별 해당 IPC 코드의 특허 건수 통계 (기술 중요도 프록시)
```

### Phase 3: F-term 패싯 통합 (2주)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| W4 | F-term 테마코드 수집 (반도체 11개 테마) | `data/taxonomy/fterm_raw/` |
| W4 | F-term → SKOS 변환 (패싯 구조 보존) | `ontology/taxonomy/fterm-semiconductor.ttl` |
| W5 | F-term 패싯 → SDKB Property 매핑 | `mappings/sdkb_fterm_alignment.ttl` |
| W5 | F-term 기반 Parameter/Material 노드 보강 후보 도출 | 보강 후보 리스트 |

**세부 작업:**

```
W4-1. F-term 수집
      - 5F004, 5F033, 5F040, 5F043, 5F045, 5F046, 5F048, 5F058 수집
      - 4K029, 4K030, 3C058 수집
      - 각 테마의 패싯 구조(관점 코드) 정리

W4-2. F-term → SKOS 변환
      - skos:ConceptScheme (테마 단위)
      - skos:Collection (패싯/관점 단위)
      - skos:Concept (개별 분류항목)
      - 패싯 구조를 isocatap:hasFacet 또는 자체 속성으로 표현

W5-1. F-term ↔ SDKB 매핑
      - 공정 패싯(BA/BB) → Process/SubProcess 매핑
      - 재료 패싯(CA/CB) → Material/Parameter 매핑
      - 장치 패싯(DA) → Equipment/EquipmentClass 매핑
      - 목적/효과 패싯(AA) → FailureMode/Mitigation 매핑

W5-2. 노드 보강 분석
      - F-term에 있으나 SDKB에 없는 재료/공정 파라미터 식별
      - 추가 노드 후보 목록 작성 (전문가 검토 대상)
```

### Phase 4: 통합 검증 및 적용 (1주)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| W6 | OWL 스키마에 분류 속성 추가 | `ontology/sdkb-core.ttl` (갱신) |
| W6 | SHACL shapes에 분류 코드 검증 규칙 추가 | `validation/shapes.ttl` (갱신) |
| W6 | 전체 파이프라인 통합 테스트 | `tests/test_taxonomy.py` |
| W6 | SPARQL 택소노미 쿼리 예시 추가 | `examples/sparql/04_taxonomy_*.rq` |

---

## 6. 디렉토리 구조 (신규/변경)

```
sdkb/
├── data/
│   └── taxonomy/                   # [신규] 원본 분류 데이터
│       ├── cpc_raw/                # CPC bulk XML 추출본
│       ├── ipc_raw/                # IPC XML 추출본
│       └── fterm_raw/              # F-term 수집 데이터
├── ontology/
│   ├── sdkb-core.ttl               # [변경] 분류 속성 추가
│   └── taxonomy/                   # [신규] 분류 체계 SKOS
│       ├── cpc-semiconductor.ttl   # CPC 반도체 서브트리
│       ├── ipc-semiconductor.ttl   # IPC 반도체 서브트리
│       └── fterm-semiconductor.ttl # F-term 패싯 분류
├── mappings/
│   ├── sdkb_cpc_alignment.ttl      # [신규] SDKB→CPC 매핑
│   ├── sdkb_ipc_alignment.ttl      # [신규] SDKB→IPC 매핑
│   └── sdkb_fterm_alignment.ttl    # [신규] SDKB→F-term 매핑
├── scripts/
│   ├── extract_cpc.py              # [신규] CPC XML→SKOS 변환
│   ├── extract_fterm.py            # [신규] F-term→SKOS 변환
│   └── map_taxonomy.py             # [신규] 반자동 매핑 엔진
├── reports/
│   └── cpc_mapping_quality.json    # [신규] 매핑 품질 보고서
├── validation/
│   └── shapes.ttl                  # [변경] 분류 코드 검증 추가
├── examples/sparql/
│   ├── 04_taxonomy_coverage.rq     # [신규] 분류 커버리지 쿼리
│   └── 05_taxonomy_gap.rq          # [신규] 분류 갭 분석 쿼리
└── tests/
    └── test_taxonomy.py            # [신규] 택소노미 통합 테스트
```

---

## 7. 기술적 고려사항

### 7.1 네임스페이스 정책

```python
# config/namespaces.py 에 추가
CPC_NS   = Namespace("https://w3id.org/sdkb/taxonomy/cpc/")
IPC_NS   = Namespace("https://w3id.org/sdkb/taxonomy/ipc/")
FTERM_NS = Namespace("https://w3id.org/sdkb/taxonomy/fterm/")
```

### 7.2 CPC 코드 → URI 변환 규칙

```
H01L 21/3065  →  cpc:H01L21-3065
H01L 21/02104 →  cpc:H01L21-02104
H10B 41/00    →  cpc:H10B41-00
```
- 공백 제거, "/" → "-" 변환
- 일관된 소문자/대문자 정책: 원본 그대로(대문자+소문자 혼용)

### 7.3 F-term 코드 → URI 변환 규칙

```
5F004/BA/01  →  fterm:5F004-BA-01
5F058/AA     →  fterm:5F058-AA
```

### 7.4 데이터 규모 예측

| 분류 체계 | 추출 심볼 수 | 트리플 수 (예상) |
|-----------|-------------|-----------------|
| CPC (반도체) | ~5,000–8,000 | ~30,000–50,000 |
| IPC (반도체) | ~1,500–2,500 | ~8,000–15,000 |
| F-term (11테마) | ~3,000–5,000 | ~20,000–35,000 |
| SDKB 매핑 | ~600–1,000 | ~2,000–4,000 |
| **합계** | | **~60,000–104,000** |

### 7.5 리스크 및 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| CPC XML 파싱 복잡도 높음 | 스크립트 개발 지연 | lxml 기반 스트리밍 파서 사용 |
| F-term 데이터 수동 수집 부담 | Phase 3 지연 | Google Patents F-term 인덱스 활용 검토 |
| 매핑 정확도 전문가 검토 필요 | 품질 미달 | 자동 매핑 후 신뢰도 점수 ≥80 만 자동 채택, 나머지 수동 검토 |
| 분류 체계 갱신 시 동기화 | 유지보수 부담 | 갱신 일자 기록, 분기별 diff 확인 스크립트 |

---

## 8. 성공 지표

| 지표 | 목표값 |
|------|--------|
| CPC 매핑 커버리지 | SDKB 노드의 ≥ 80% |
| IPC 매핑 커버리지 | CPC 매핑된 노드의 100% (자동 유도) |
| F-term 매핑 커버리지 | Process/SubProcess/Material/Equipment의 ≥ 70% |
| 매핑 정확도 (전문가 검증) | ≥ 90% |
| SHACL 검증 통과율 | 매핑된 노드의 100% |
| 택소노미 기반 신규 노드 후보 | ≥ 30개 식별 |

---

## 9. 향후 확장 가능성

1. **특허 통계 연동**: CPC 코드별 연간 출원 건수 → 기술 동향 시계열 분석
2. **KIPRIS 연동**: 한국 특허 DB에서 IPC 기반 검색 → SDKB 노드별 한국 특허 링크
3. **특허 기반 기업 경쟁력 분석**: CPC 코드 + 출원인 → Vendor/Organization 노드 강화
4. **NPL(비특허문헌) 연계**: 특허 인용 학술논문 → SDKB 출처(provenance) 확장
5. **SEP(표준필수특허) 분석**: CPC + ETSI DB → 표준과 특허의 교차 분석

---

## 부록 A: 참고 자료

- [CPC 공식 사이트](https://www.cooperativepatentclassification.org/)
- [USPTO CPC Bulk Data](https://bulkdata.uspto.gov/data/patent/classification/cpc/)
- [WIPO IPC Publication](https://www.wipo.int/classifications/ipc/en/)
- [JPO F-term 안내](https://www.jpo.go.jp/e/system/patent/gaiyo/bunrui/)
- [J-PlatPat 특허검색](https://www.j-platpat.inpit.go.jp/)
- [SKOS Reference (W3C)](https://www.w3.org/TR/skos-reference/)
- [SKOS Mapping Properties](https://www.w3.org/TR/skos-reference/#mapping)
