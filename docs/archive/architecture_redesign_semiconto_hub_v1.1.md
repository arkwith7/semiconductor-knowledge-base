# SDKB 아키텍처 재설계: SemicONTO 중심 다중 소스 통합 전략

> **문서 버전**: v1.1 (2026-04-13)
> **작성자**: SDKB 프로젝트 팀
> **상태**: ⚠️ **SUPERSEDED (2026-05-12)** by [architecture_amendment_sdkb_centric.md](architecture_amendment_sdkb_centric.md) — 방향 역전 (SDKB가 trunk, SemicONTO는 정렬 소스). 본 문서는 변경 이력 추적용으로 보존.

---

## 1. 제안 개요

**현재 아키텍처** (Bottom-up):
```
semiconductor_v0_3.json (198노드) → SDKB Core OWL (자체 스키마)
  + SemicONTO alignment (TBD)
  + CPC/IPC/F-term (계획)
```

**제안 아키텍처** (SemicONTO Core + Hub-and-Spoke):
```
SemicONTO (상위 온톨로지, CC BY 4.0)
  ├── SDKB Manufacturing Extension (새 모듈: Process, FMEA, Governance)
  │     └── semiconductor_v0_3.json → 인스턴스 데이터로 변환·병합
  ├── CPC/IPC/F-term (참조 택소노미, SKOS 매핑)
  ├── Patent Abstract NLP (특허 초록 기반 엔티티·관계 자동 추출)
  ├── MatKG (재료 지식, CC BY 4.0)
  ├── BIS CCL (수출통제, Public Domain)
  ├── SemiKong (공정 택소노미, Apache 2.0)
  ├── tibonto/dr (공급망, Apache 2.0)
  ├── JEDEC (신뢰성 실패 모드)
  ├── Wikidata (엔티티 링킹, CC0)
  └── SEMI E10 (장비 상태 모델)
```

---

## 2. SemicONTO 상세 분석

### 2.1 SemicONTO v0.1 (2023-03-21)

| 항목 | 값 |
|------|-----|
| URI | `http://w3id.org/SemicONTO/` (w3id 영구 식별자) |
| 라이선스 | CC BY 4.0 |
| 포맷 | OWL/Turtle |
| 제작자 | Huanyu Li (Linköping University) |
| 논문 | CEUR-WS Vol-3760 |

**클래스 (21개):**
```
Matter
└── ChemicalEntity
│   ├── ChemicalSubstance
│   └── MolecularEntity
└── Material ─────────────── (prov:Entity)
    └── Semiconductor
        ├── IntrinsicSemiconductor
        └── ExtrinsicSemiconductor
            ├── N-TypeSemiconductor
            └── P-TypeSemiconductor

Experiment ──────────────── (prov:Activity)
└── SemiconductorExperiment

ExperimentalStep ─────────── (prov:Activity)

Equipment ────────────────── (prov:Agent)

InformationObject
├── ExperimentInfoObj
└── StepInfoObj

Dopant = Acceptor ∪ Donor
DopingRelation
```

**Object Properties (10개):**
- `experimentsFor`, `experimentsOn` (⊂ prov:used)
- `hasAcceptor`, `hasDonor`
- `hasEquipment` (Step → Equipment)
- `hasExperimentalStep` (Experiment → Step)
- `hasNextStep`, `hasSubStep` (Step → Step, transitive)
- `hasStructure` (Material → mdo:Structure)
- `isDescribedBy` (→ InformationObject)

**재사용 온톨로지:** PROV-O, MDO (Materials Design Ontology), EMMO (참조)

### 2.2 SemicONTO v0.2 (2025-06-24) — 추가 요소

v0.2에서 새로 도입된 개념들:

**신규 클래스 (14개 추가, 총 ~35개):**

| 추가 클래스 | 분류 |
|------------|------|
| `ExperimentalMethod` | 실험 방법론 상위 클래스 |
| `ElectronBeamLithography` | 실험 방법 |
| `ThermalEvaporation` | 실험 방법 |
| `HallEffectMeasurement` | 측정 방법 |
| `FieldEffectMeasurement` | 측정 방법 |
| `PhotoelectronSpectroscopy` | 측정 방법 |
| `SpectralResponseMeasurement` | 측정 방법 |
| `MaterialProperty` | 소재 물성 (⊂ qudt:Quantity) |
| `CMTExperiment` | 전하 이동도 테스트 |
| `EQETExperiment` | 외부양자효율 테스트 |
| `HMTExperiment` | 홀 이동도 테스트 |
| `PESExperiment` | 광전자 분광 실험 |
| `PPCExperiment` | 파라미터 특성화 실험 |
| `SEDFabrication` | 단전자 소자 제작 |

**신규 Object Properties:**
- `hasExperimentalMethod` (Experiment → ExperimentalMethod)
- `hasMeasuredProperty` (Experiment → MaterialProperty)
- `hasProperty` (Material → MaterialProperty)

**신규 재사용 온톨로지:** QUDT (Quantity, Unit, QuantityValue)

### 2.3 SemicONTO 강점·약점 평가

| 관점 | 강점 | 약점 |
|------|------|------|
| **학술적 근거** | CEUR-WS 발표, w3id 영구 URI | 커뮤니티 작음 (Star 2, Fork 0) |
| **라이선스** | CC BY 4.0 — 자유 확장 가능 | — |
| **설계 품질** | OWL DL 준수, PROV-O 재사용, 정식 axiom | 매우 작은 규모 |
| **재료 모델링** | MDO+EMMO 연결, v0.2에서 QUDT 추가 | 반도체 재료 인스턴스 없음 |
| **공정 모델링** | hasStep/hasSubStep/hasNextStep 의미론 | **제조 공정 클래스 부재** — Experiment 기반 |
| **장비 모델링** | Equipment as prov:Agent | Equipment 하위 분류 없음 |
| **실패 모드** | — | **완전 부재** |
| **공급망/벤더** | — | **완전 부재** |
| **규제/거버넌스** | — | **완전 부재** |
| **기술 노드** | — | **완전 부재** |

---

## 3. 통합 적합성 분석

### 3.1 SemicONTO ↔ SDKB v0.3 개념 매핑

| SDKB 노드 유형 (198개) | SemicONTO 대응 | 매핑 전략 |
|------------------------|---------------|----------|
| **Process** (8개) | `Experiment` (유사) | SemicONTO의 Experiment를 확장하되, ManufacturingProcess 서브클래스 신설 |
| **SubProcess** (12개) | `ExperimentalStep` (유사) | ManufacturingStep ⊂ ExperimentalStep |
| **Equipment** (42개) | `Equipment` (**직접 대응**) | SemicONTO Equipment 그대로 사용, 하위 분류 추가 |
| **EquipmentClass** (13개) | — (부재) | EquipmentClass 신설, Equipment의 상위 분류로 |
| **Material** (20개) | `Material` (**직접 대응**) | SemicONTO Material 그대로 사용 |
| **Vendor** (18개) | — (부재) | Vendor ⊂ prov:Agent (SemicONTO의 Agent 체계 활용) |
| **Organization** (2개) | — (부재) | Organization ⊂ prov:Agent |
| **Parameter** (5개) | `MaterialProperty` (부분) | ProcessParameter 신설, QUDT 활용 |
| **Metrology** (3개) | SpectralResponseMeasurement 등 (부분) | Metrology ⊂ ExperimentalMethod |
| **TechnologyNode** (3개) | — (부재) | TechnologyNode 신설 |
| **FailureMode** (25개) | — (**완전 부재**) | FMEA 모듈 신설 필요 |
| **RootCause** (20개) | — (**완전 부재**) | FMEA 모듈 |
| **Mitigation** (20개) | — (**완전 부재**) | FMEA 모듈 |
| **Skill** (12개) | — (부재) | Skill 신설 |

**직접 재사용 가능**: Equipment, Material (+ Matter, ChemicalEntity 계층)
**확장 필요**: Experiment→ManufacturingProcess, ExperimentalStep→ManufacturingStep
**신규 모듈 필요**: FMEA, Vendor/Organization, TechnologyNode, Skill, Governance

### 3.2 아키텍처 패턴: Import + Extend

```turtle
# sdkb-manufacturing.ttl — SDKB 확장 모듈
@prefix sdkb: <https://w3id.org/sdkb/ont/> .
@prefix semi: <http://w3id.org/SemicONTO/> .

<https://w3id.org/sdkb/ont/>
    a owl:Ontology ;
    owl:imports <http://w3id.org/SemicONTO/0.2/> ;
    rdfs:label "SDKB Manufacturing Extension" .

# ── SemicONTO Experiment를 제조공정으로 확장 ──
sdkb:ManufacturingProcess
    a owl:Class ;
    rdfs:subClassOf semi:Experiment ;
    rdfs:label "Manufacturing Process" .

sdkb:ManufacturingStep
    a owl:Class ;
    rdfs:subClassOf semi:ExperimentalStep ;
    rdfs:label "Manufacturing Step" .

# ── SemicONTO Equipment를 세분화 ──
sdkb:EquipmentClass
    a owl:Class ;
    rdfs:label "Equipment Class" .

sdkb:Equipment  # SemicONTO Equipment 그대로 사용
    rdfs:subClassOf [ a owl:Restriction ;
        owl:onProperty sdkb:isInstanceOf ;
        owl:someValuesFrom sdkb:EquipmentClass ] .

# ── FMEA 모듈 (SemicONTO에 없는 영역) ──
sdkb:FailureMode a owl:Class .
sdkb:RootCause a owl:Class .
sdkb:Mitigation a owl:Class .

# ── Vendor/Organization (prov:Agent 체계 활용) ──
sdkb:Vendor
    a owl:Class ;
    rdfs:subClassOf <http://www.w3.org/ns/prov#Agent> .

sdkb:Organization
    a owl:Class ;
    rdfs:subClassOf <http://www.w3.org/ns/prov#Agent> .
```

---

## 4. 다중 소스 통합 레이어 설계

### 4.1 통합 아키텍처 (6-Layer)

```
Layer 6: Application & Query ─────────── SPARQL, API, Visualization
Layer 5: Governance & Regulation ──────── BIS CCL, SEMI E10, Korea NCT
Layer 4: Patent-Derived Enrichment ────── 특허 초록 NLP 추출 엔티티·관계
Layer 3: Domain Instance Data ─────────── semiconductor_v0_3 + MatKG + Wikidata
Layer 2: Reference Taxonomy ───────────── CPC/IPC/F-term (SKOS ConceptScheme)
Layer 1: Core Ontology Schema ─────────── SemicONTO + SDKB Extension Module
Layer 0: Foundation Ontologies ────────── PROV-O, SKOS, QUDT, MDO, OWL
```

### 4.2 소스별 통합 계획

| 소스 | 레이어 | 통합 방식 | SDKB 기여 영역 |
|------|--------|----------|----------------|
| **SemicONTO v0.2** | L1 | `owl:imports` — 상위 스키마 | Equipment, Material, Experiment 클래스 계층 |
| **semiconductor_v0_3** | L3 | ABox 변환 — 인스턴스 데이터 | 198노드 → SemicONTO/SDKB 클래스의 인스턴스 |
| **CPC/IPC** | L2 | `skos:ConceptScheme` + `skos:exactMatch` | 공정·재료·장비 표준 분류 코드 |
| **F-term** | L2 | `skos:Collection` (패싯) + `skos:narrowMatch` | 다면적 공정조건 분류 |
| **SemiKong** | L1+L3 | ManufacturingProcess 하위 택소노미 참조 | 10 L1 + 50~100 L2/L3 공정 분류 |
| **MatKG** | L3 | `owl:sameAs` / `skos:exactMatch` 엔티티 링킹 | 70K+ 소재 엔티티, 물성, 합성법 |
| **BIS CCL** | L4 | Governance 모듈 (ECCN → EARRule) | 장비·소재 수출통제 분류 30+ ECCN |
| **tibonto/dr** | L1+L3 | `owl:imports` 부분 모듈 | 공급망, 조직, CO₂ 추적 |
| **JEDEC JEP122H** | L1+L3 | FailureMode 택소노미 참조 | EM, TDDB, HCI, NBTI 등 실패 메커니즘 |
| **Wikidata** | L3 | `owl:sameAs` Q-item 링킹 | 공정, 기업, 장비 범용 식별자 |
| **SEMI E10** | L5 | EquipmentState 모듈 | 장비 상태 모델 (Productive, Standby, Down 등) |
| **NIST CSF/IR** | L5 | Governance 모듈 | 사이버보안, 반도체 공급망 리스크 |
| **Patent Abstracts** | L4 | NLP/LLM 추출 → ABox 보강 | 특허 초록에서 소재·공정·장비·파라미터 엔티티/관계 자동 추출 |

### 4.3 네임스페이스 통합 설계

| Prefix | URI | 역할 |
|--------|-----|------|
| `semi:` | `http://w3id.org/SemicONTO/` | 상위 온톨로지 (Import) |
| `sdkb:` | `https://w3id.org/sdkb/ont/` | SDKB 확장 클래스/속성 |
| `sdkb-data:` | `https://w3id.org/sdkb/data/` | SDKB 인스턴스 데이터 |
| `sdkb-gov:` | `https://w3id.org/sdkb/gov/` | 거버넌스 규칙 |
| `cpc:` | `https://worldwide.espacenet.com/classification/cpc/` | CPC 분류 |
| `ipc:` | `https://www.wipo.int/ipc/` | IPC 분류 |
| `fterm:` | `https://www.j-platpat.inpit.go.jp/fterm/` | F-term 패싯 |
| `matkg:` | `https://zenodo.org/records/10144972/` | MatKG 엔티티 |
| `eccn:` | `https://www.ecfr.gov/eccn/` | BIS ECCN 코드 |
| `wd:` | `http://www.wikidata.org/entity/` | Wikidata Q-item |

### 4.4 특허 초록 기반 온톨로지 보강 (Patent Abstract Enrichment)

특허의 발명 초록(Abstract)은 가장 밀도 높은 기술 기술(description) 원천이다.
CPC/IPC 분류와 결합하면 SDKB 온톨로지를 **현존하는 실제 기술**로 풍성하게 할 수 있다.

#### 4.4.1 공개 특허 데이터 소스

| 소스 | 데이터 범위 | 접근 방식 | 비용 | 주요 필드 |
|------|-----------|----------|------|----------|
| **Google Patents (BigQuery)** | 120+ 특허청, 1억+ 특허 | SQL 쿼리 | 무료 (1TB/월) | CPC, IPC, 제목, 초록, 청구항, 출원일 |
| **USPTO PatentsView API** | 미국 특허 전체 | REST API (키 필요) | 무료 | 초록, CPC, 발명자, 출원일 |
| **EPO Open Patent Services** | 전 세계 특허 | OAuth2 REST | 무료 (4GB/주) | 초록, CPC/IPC, 패밀리 |
| **KIPRIS** | 한국 특허 | REST API | 무료 | 한국어 초록, IPC, 출원인 |
| **Lens.org** | 전 세계 특허+논문 | 웹+API | 비상업적 무료 | 통합 검색, 인용 네트워크 |

**핵심 소스**: Google BigQuery `patents-public-data.patents.publications` 테이블
— H01L/H10B/G03F/C23C/B24B CPC 코드 필터로 반도체 특허 5만~8만건 추출 가능

#### 4.4.2 NLP 추출 파이프라인

```
Patent Bulk Data (BigQuery/API)
    │  CPC코드 + 초록 + 제목
    ▼
CPC 필터링 ──── H01L, H10B, G03F, C23C, B24B만 추출
    │
    ▼
NLP/LLM 엔티티·관계 추출 (NER + RE)
    │  소재명, 공정명, 장비명, 파라미터, 구조, 응용
    │  관계: "used_for", "improves", "replaces", "produces"
    ▼
엔티티 정규화 (Entity Linking)
    │  추출 개념 → SDKB 기존 노드 매칭 (rapidfuzz + 임베딩)
    │  기존 매칭: owl:sameAs / 신규 발견: 후보 노드 생성
    ▼
온톨로지 보강 (Enrichment)
    │  신규 SubProcess, Material, Parameter 후보 추가
    │  기존 노드에 동의어·설명·CPC코드 보강
    │  기술 트렌드 (연도별 특허 수)
    ▼
전문가 검증 (Expert Review)
    confidence score 기반 우선순위
```

#### 4.4.3 보강 유형 및 예시

| 보강 유형 | 예시 | 방법 |
|-----------|------|------|
| 신규 SubProcess 발견 | Selective ALD, Area-Selective Deposition | 초록 클러스터링으로 기존 분류에 없는 공정 발견 |
| 소재-공정 관계 보강 | "EUV photoresist uses metal oxide nanoparticles" | NER로 소재-공정 쌍 추출 |
| 파라미터 범위 추가 | "plasma etch at 10-50mTorr" | 수치 추출 → ProcessParameter 값 범위 |
| 장비-공정 연결 | "ASML NXE:3600 EUV scanner" | 특허에서 장비 모델명 추출 |
| 기술 트렌드 | 연도별 CPC 코드 특허 수 → 신흥 기술 식별 | 통계 분석 |
| 동의어 확보 | "chemical mechanical polishing" = "CMP" = "planarization" | 초록 내 동의어 패턴 추출 |
| 한국어 용어 매핑 | KIPRIS 초록에서 한국어 공정명 수집 | 한-영 용어 쌍 |

#### 4.4.4 초록 추출 예시

```
원문 (US Patent 특허 초록):
"A method for atomic layer deposition of hafnium oxide thin films
 using tetrakis(dimethylamido)hafnium precursor at temperatures
 between 250-350°C, achieving step coverage exceeding 95% in
 high aspect ratio trenches for advanced 3nm node gate dielectric."

추출 결과:
├── Process: ALD                    → subprocess:ald (기존 매칭)
├── Material: HfO2                  → material:hfO2 (기존 매칭)
├── Material: TDMAH precursor       → ★ 신규 Precursor 후보
├── Parameter: Temp = 250-350°C     → parameter:temperature 범위 추가
├── Metric: Step Coverage > 95%     → ★ 신규 품질 지표 후보
├── Structure: HAR Trench           → ★ 신규 구조 개념 후보
├── TechnologyNode: 3nm             → technode:3nm (기존 매칭)
├── Application: Gate Dielectric    → ★ 신규 Application 후보
└── 관계: ALD --produces--> HfO2 thin film
          HfO2 --used_as--> Gate Dielectric
```

#### 4.4.5 데이터 흐름 (Layer 4)

```turtle
# 특허 추출 엔티티 → SDKB 인스턴스 (자동 생성, 검증 전)
sdkb-data:material/tdmah_precursor
    a semi:Material ;
    skos:prefLabel "Tetrakis(dimethylamido)hafnium"@en ;
    skos:altLabel "TDMAH"@en ;
    sdkb:extractedFrom sdkb-data:patent/US20230123456 ;
    sdkb:confidence 0.92 ;
    sdkb:validationStatus "pending" ;
    sdkb:cpcSource cpc:C23C16-455 ;
    sdkb:usedInProcess sdkb-data:subprocess/ald .

# 특허 출처 기록 (PROV-O)
sdkb-data:patent/US20230123456
    a prov:Entity ;
    dcterms:identifier "US20230123456A1" ;
    sdkb:cpcCode "C23C 16/455" ;
    sdkb:filingDate "2023-05-15"^^xsd:date .
```

> **상세 실행 계획**은 별도 문서 `docs/patent_abstract_enrichment_plan.md`를 참조.

---

## 5. 모듈 구조 설계

### 5.1 온톨로지 모듈 분해

```
ontology/
├── imports/
│   └── SemicONTO-0.2.ttl          # SemicONTO v0.2 원본 (캐시)
│
├── sdkb-manufacturing.ttl          # 제조공정 확장 모듈
│   ├── owl:imports SemicONTO
│   ├── ManufacturingProcess ⊂ semi:Experiment
│   ├── ManufacturingStep ⊂ semi:ExperimentalStep
│   ├── EquipmentClass (신규)
│   ├── ProcessParameter ⊂ semi:MaterialProperty
│   ├── TechnologyNode (신규)
│   └── Skill (신규)
│
├── sdkb-fmea.ttl                   # FMEA 모듈
│   ├── FailureMode, RootCause, Mitigation
│   ├── isDueTo, mitigatedBy, occursAtProcessStep
│   └── JEDEC 실패 메커니즘 택소노미
│
├── sdkb-supply-chain.ttl           # 공급망 모듈
│   ├── Vendor ⊂ prov:Agent
│   ├── Organization ⊂ prov:Agent
│   ├── providedBy, manufacturedBy
│   └── (tibonto/dr 정합)
│
├── sdkb-governance.ttl             # 거버넌스/규제 모듈
│   ├── EARRule, ECCNCode, SCIPRule
│   ├── EquipmentState (SEMI E10)
│   └── NISTFunction, NISTOutcome
│
├── sdkb-taxonomy-bridge.ttl        # 분류체계 브릿지
│   ├── CPC/IPC/F-term SKOS 매핑
│   └── skos:exactMatch, broadMatch, narrowMatch
│
└── sdkb-core.ttl                   # 통합 메타 온톨로지
    ├── owl:imports sdkb-manufacturing
    ├── owl:imports sdkb-fmea
    ├── owl:imports sdkb-supply-chain
    ├── owl:imports sdkb-governance
    └── owl:imports sdkb-taxonomy-bridge
```

### 5.2 SemicONTO 클래스 확장 트리

```
[SemicONTO v0.2 기존 클래스]          [SDKB 확장 클래스]
─────────────────────────          ──────────────────

prov:Activity                      
├── semi:Experiment                
│   ├── semi:SemiconductorExperiment
│   │   ├── semi:CMTExperiment     
│   │   ├── semi:EQETExperiment    
│   │   └── ...                    
│   └── ★ sdkb:ManufacturingProcess    ← 제조공정 (Process)
│       ├── sdkb:Lithography       
│       ├── sdkb:Etch              
│       ├── sdkb:Deposition        
│       ├── sdkb:CMP               
│       ├── sdkb:Implant           
│       └── ...                    
└── semi:ExperimentalStep          
    └── ★ sdkb:ManufacturingStep       ← 하위공정 (SubProcess)
        ├── sdkb:EUVLithography    
        ├── sdkb:PlasmaEtch        
        ├── sdkb:ALD               
        └── ...                    

prov:Agent                         
├── semi:Equipment                 
│   └── (42개 인스턴스)             
├── ★ sdkb:Vendor                      ← 공급업체
├── ★ sdkb:Organization                ← 제조사/연구기관
└── ★ sdkb:HumanAgent                  ← 전문가

semi:Material                      
├── semi:Semiconductor             
│   ├── semi:IntrinsicSemiconductor
│   └── semi:ExtrinsicSemiconductor
├── (20개 소재 인스턴스)            
└── ★ sdkb:ProcessMaterial             ← 공정 소재 (PR, Gas, Slurry)

semi:ExperimentalMethod            
├── semi:ElectronBeamLithography   
├── semi:ThermalEvaporation        
└── ★ sdkb:Metrology                   ← 계측 방법

semi:MaterialProperty              
└── ★ sdkb:ProcessParameter            ← 공정 파라미터

★ sdkb:EquipmentClass                  ← 장비 분류 (신규 최상위)
★ sdkb:TechnologyNode                  ← 기술 노드 (신규 최상위)
★ sdkb:Skill                           ← 엔지니어 역량 (신규 최상위)
★ sdkb:FailureMode                     ← 실패 모드 (신규 최상위)
★ sdkb:RootCause                       ← 근본 원인 (신규 최상위)
★ sdkb:Mitigation                      ← 완화 조치 (신규 최상위)
```

---

## 6. 현행 대비 변경 영향 분석

### 6.1 기존 산출물 상태 및 재활용 계획

| 기존 파일 | 현재 상태 | 재설계 영향 |
|-----------|----------|------------|
| `semiconductor_v0_3.json` | ✅ 사용 중 (198노드) | **유지** — 인스턴스 데이터 소스로 계속 사용 |
| `scripts/parse_baseline.py` | ✅ 동작 (Parquet 생성) | **유지** — 파싱 로직 불변 |
| `scripts/build_owl.py` | ✅ 동작 (257 트리플) | **전면 재작성** — SemicONTO import + 확장 구조로 |
| `scripts/convert_rdf.py` | ✅ 동작 (2,106 트리플) | **수정** — 새 네임스페이스·클래스 매핑 반영 |
| `ontology/sdkb-core.ttl` | ✅ 생성됨 | **모듈화 재구성** — 5개 하위 모듈로 분리 |
| `config/namespaces.py` | ✅ 사용 중 | **확장** — SemicONTO, CPC, MatKG 등 네임스페이스 추가 |
| `config/context.jsonld` | ✅ 사용 중 | **확장** — SemicONTO 컨텍스트 추가 |
| `validation/shapes.ttl` | ✅ 작성됨 | **확장** — SemicONTO 호환성 검증 규칙 추가 |
| `provenance/prov.ttl` | ✅ 작성됨 | **확장** — 새 소스 엔티티 추가 |
| `tests/` | ✅ 18/20 통과 | **확장** — SemicONTO import 검증 테스트 추가 |
| `Makefile` | ✅ 사용 중 | **확장** — 새 타겟 추가 (ingest-semiconto, etc.) |

### 6.2 기술적 쟁점

| 쟁점 | 설명 | 권고안 |
|------|------|--------|
| **URI 체계 차이** | SemicONTO: `http://`, SDKB: `https://` | SDKB 확장 모듈은 `https://w3id.org/sdkb/`로 유지, SemicONTO는 원본 URI 그대로 import |
| **Experiment vs Process** | SemicONTO의 "실험"과 반도체 "제조공정"은 의미론적 차이 | ManufacturingProcess ⊂ Experiment로 모델링 — 실험도 공정의 일종으로 보는 넓은 해석 |
| **버전 관리** | SemicONTO v0.2가 변경되면 SDKB에 영향 | `ontology/imports/`에 v0.2 TTL 캐시, 업스트림 변경 감지 스크립트 |
| **인스턴스 ID 호환** | 기존 v0_3의 `process:lithography` 형태 | `sdkb-data:process/lithography` URI로 변환, 기존 ID는 `skos:notation` 보존 |
| **중복 정의 방지** | SemicONTO Equipment와 SDKB Equipment | SDKB는 SemicONTO의 것을 직접 사용 (`semi:Equipment`), 재정의하지 않음 |

---

## 7. 실행 계획 (개정)

### Phase 0: SemicONTO 수집 및 분석 (1주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 0.1 | SemicONTO v0.2 TTL 다운로드 및 로컬 캐시 | `ontology/imports/SemicONTO-0.2.ttl` |
| 0.2 | SemicONTO 클래스/속성 정밀 분석 (rdflib 파싱) | `data/reports/semiconto_analysis.json` |
| 0.3 | SemicONTO ↔ v0_3 198노드 상세 매핑 테이블 작성 | `mappings/semiconto_sdkb_mapping.csv` |
| 0.4 | 확장 포인트(Extension Point) 식별 및 확정 | (본 문서 업데이트) |

### Phase 1: 코어 온톨로지 재구성 (2주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 1.1 | `sdkb-manufacturing.ttl` 작성 (SemicONTO import + 14 확장 클래스) | `ontology/sdkb-manufacturing.ttl` |
| 1.2 | `sdkb-fmea.ttl` 작성 (FailureMode/RootCause/Mitigation) | `ontology/sdkb-fmea.ttl` |
| 1.3 | `sdkb-supply-chain.ttl` 작성 (Vendor, Organization) | `ontology/sdkb-supply-chain.ttl` |
| 1.4 | `sdkb-core.ttl` 통합 온톨로지 (imports 체인) | `ontology/sdkb-core.ttl` (재구성) |
| 1.5 | `build_owl.py` 재작성 | `scripts/build_owl.py` |
| 1.6 | 네임스페이스·컨텍스트 업데이트 | `config/namespaces.py`, `config/context.jsonld` |

### Phase 2: 인스턴스 데이터 변환 (1주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 2.1 | `convert_rdf.py` 수정 — SemicONTO 클래스 기반 RDF 생성 | `scripts/convert_rdf.py` |
| 2.2 | 198노드 → SemicONTO+SDKB 확장 클래스 인스턴스로 변환 검증 | `ontology/sdkb-core-data.ttl` |
| 2.3 | SHACL 검증 규칙 업데이트 | `validation/shapes.ttl` |

### Phase 3: 특허 분류체계 통합 (2주)

*(patent_taxonomy_integration_plan.md의 Phase 1~2와 동일)*

| 태스크 | 산출물 |
|--------|--------|
| 3.1 CPC 수집·SKOS 변환 | `ontology/cpc-semiconductor.ttl` |
| 3.2 IPC 브릿지 | `mappings/ipc_cpc_bridge.ttl` |
| 3.3 F-term 수집·SKOS 변환 | `ontology/fterm-semiconductor.ttl` |
| 3.4 SDKB ↔ CPC/F-term 매핑 | `mappings/sdkb_cpc_alignment.ttl` |

### Phase 3.5: 특허 초록 기반 온톨로지 보강 (3주)

*(patent_abstract_enrichment_plan.md 참조)*

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 3.5.1 | BigQuery/API에서 반도체 CPC별 특허 초록 수집 (5~8만건) | `data/external/patent_abstracts.parquet` |
| 3.5.2 | NER/RE 파이프라인 구축 (소재·공정·장비·파라미터 추출) | `scripts/extract_patent_entities.py` |
| 3.5.3 | 추출 엔티티 → SDKB 노드 매칭 + 신규 후보 생성 | `data/reports/patent_entity_linking.json` |
| 3.5.4 | 동의어·파라미터 범위·기술 트렌드 분석 | `data/reports/patent_enrichment_candidates.json` |
| 3.5.5 | KIPRIS 한국어 초록으로 한-영 용어 쌍 수집 | `data/external/ko_en_terms.csv` |
| 3.5.6 | 전문가 검증 후 온톨로지 반영 | 업데이트된 TTL, 확장된 노드·엣지 |

### Phase 4: 외부 소스 링킹 (2주)

| 태스크 | 상세 | 산출물 |
|--------|------|--------|
| 4.1 | MatKG 엔티티 링킹 — SDKB Material ↔ MatKG CHM | `mappings/sdkb_matkg_alignment.ttl` |
| 4.2 | BIS CCL 수집 — eCFR API 3B/3C/3D/3E ECCN | `data/external/bis_ccl.json` → `ontology/sdkb-governance.ttl` |
| 4.3 | SemiKong 택소노미 수동 추출 | `data/external/semikong_taxonomy.json` |
| 4.4 | Wikidata Q-item 링킹 | `mappings/sdkb_wikidata_alignment.ttl` |
| 4.5 | tibonto/dr 부분 정합 | `mappings/sdkb_tibonto_alignment.ttl` |

### Phase 5: 통합 검증 및 배포 (1주)

| 태스크 | 산출물 |
|--------|--------|
| 5.1 SHACL 전체 검증 | `data/reports/validation_report.json` |
| 5.2 커버리지 분석 (CPC 대비) | `data/reports/coverage_gap.json` |
| 5.3 통합 테스트 | `tests/test_semiconto_import.py`, `tests/test_taxonomy.py`, `tests/test_patent_enrichment.py` |
| 5.4 README/CHANGELOG 업데이트 | `README.md`, `CHANGELOG.md` |
| 5.5 GitHub 푸시 및 태그 | `v1.1-semiconto-core` 태그 |

---

## 8. 기대 효과

| 지표 | 현재 (v1.0) | 목표 (v1.1) |
|------|------------|------------|
| 상위 온톨로지 | 자체 스키마 | SemicONTO v0.2 기반 |
| 외부 온톨로지 재사용 | PROV-O만 | SemicONTO, MDO, QUDT, SKOS |
| 모듈 수 | 1 (monolithic) | 5+ (Manufacturing, FMEA, SupplyChain, Governance, Taxonomy) |
| 참조 택소노미 | 없음 | CPC, IPC, F-term |
| 외부 엔티티 링킹 | 없음 | MatKG, Wikidata, BIS CCL |
| 국제 표준 매핑 비율 | 0% | ≥ 80% (CPC 기준) |
| 특허 기반 보강 | 없음 | 5~8만건 초록에서 엔티티·관계 자동 추출, 동의어·파라미터 보강 |
| 한국어 용어 매핑 | 없음 | KIPRIS 초록 기반 한-영 용어 쌍 |
| 학술 발표 가능성 | 자체 구축물 | "SemicONTO 확장" — 기존 연구 위에 기여 |

---

## 9. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| SemicONTO v0.3 출시 시 breaking change | 확장 모듈 호환성 깨짐 | Import 버전 고정 (v0.2), 업그레이드 스크립트 준비 |
| Experiment→ManufacturingProcess 모델링 논란 | 학술 리뷰어 의문 | SKOS 매핑으로 대안 제공 (SemicONTO 원저자 사전 협의 권장) |
| 다중 소스 라이선스 충돌 | 배포 제한 | 라이선스 호환 매트릭스 관리 (주로 CC BY 4.0 + Apache 2.0 + Public Domain) |
| 온톨로지 복잡도 증가 | 유지보수 부담 | 모듈화 설계로 독립적 업데이트 가능 |
| MatKG 2.8GB 데이터 처리 | 리소스 부담 | 반도체 관련 엔티티만 필터 추출 (~수천 개) |
| NLP 추출 정확도 한계 | 오류 엔티티 온톨로지 유입 | confidence score + 전문가 검증 2단계 게이트, validationStatus 속성 |
| BigQuery 대량 쿼리 비용 | 무료 한도 초과 시 과금 | 반도체 CPC 서브트리만 선별, 파티셔닝 쿼리로 1TB 이내 유지 |
| 특허 초록 다국어 처리 | 비영문 초록 NER 정확도 저하 | 1차 영문 초록만 처리, KIPRIS 한국어는 별도 파이프라인 |

---

## 10. 결론

SemicONTO를 상위 온톨로지로 채택하는 것은 다음 이유에서 합리적이다:

1. **유일한 목적 구축 반도체 OWL 온톨로지** — CC BY 4.0, w3id 영구 URI
2. **PROV-O + MDO + QUDT 재사용** — SDKB의 출처 추적, 소재 모델링, 단위 표현과 직접 정합
3. **학술 기반** — CEUR-WS 발표물 위에 확장하는 것이 독립 구축보다 학술적 기여가 명확
4. **확장 가능한 설계** — Equipment, Material, ExperimentalStep 등 핵심 클래스가 이미 존재하며, 제조공정·FMEA·공급망은 서브클래스로 자연스럽게 확장 가능

**핵심 원칙:**
- SemicONTO를 **변경하지 않고** `owl:imports`로 가져와 확장만 한다
- semiconductor_v0_3.json의 198노드는 **인스턴스 데이터**로서 완전히 보존된다
- 모든 외부 소스는 **SKOS 매핑** 또는 **owl:sameAs**로 느슨하게 연결하여 독립성을 유지한다

---

*이 문서는 Phase 0 착수 전 팀 리뷰를 거쳐 확정할 것.*
*SemicONTO 원저자(Huanyu Li)에게 확장 계획을 사전 통보하는 것을 권장함.*
