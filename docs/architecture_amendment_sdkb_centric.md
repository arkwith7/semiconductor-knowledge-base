# Architecture Amendment — SDKB-Centric Curation Direction

> **문서 상태**: Active Amendment (supersedes ADR v1.1)
> **작성일**: 2026-05-12
> **저자**: SDKB 프로젝트 팀 (Park HyoungSik)
> **연관 문서**: [architecture_redesign_semiconto_hub.md](architecture_redesign_semiconto_hub.md) (v1.1, **superseded**)
> **승인 단계**: 학생 단계 확정 → 지도교수(신준석) 검토 요청 예정

---

## 1. 배경 — ADR v1.1과 무엇이 달라지는가

2026-04-13 작성된 `architecture_redesign_semiconto_hub.md` (v1.1)는 다음을 제안:

> "SemicONTO를 상위 온톨로지로 채택하고, SDKB는 `owl:imports SemicONTO`로 가져와 확장만 한다."

이는 **SDKB v1.0에 아직 콘텐츠가 거의 없던 시점**의 계획이었다. 그 이후 진행된 작업으로 SDKB는 다음 자산을 축적했다:

| 자산 | 규모 | 정착 위치 |
|---|---|---|
| 베이스라인 그래프 (14 코어 클래스) | **198 노드 / 268 엣지** | [data/semiconductor_v0_3.json](../data/semiconductor_v0_3.json) |
| SIRP 거절특허 데이터셋 | 773 patents + 7,500 prior-art pairs | `data/patents/` |
| 큐레이션 전문가 풀 | 110 profiles + 7,800 ratings (κ=0.258) | `data/experts/` |
| 4-pillar 정렬 모듈 (지도교수 방향) | sdkb-patent / rbv / commercialization / foresight | `ontology/*.ttl` |
| 한·미 거버넌스 마스터 | 20 controls, 205 RDF triples | `ontology/sdkb-governance-{kr,us}-instances.ttl` |
| Adversarial scenarios | 50 problems + 25 scenarios | `data/problems.parquet`, `data/regulatory_scenarios.parquet` |

이 자산들은 모두 `https://w3id.org/sdkb/` URI 공간에 자리잡았다. ADR v1.1을 그대로 실행하면 198 노드 인스턴스 URI 마이그레이션, build_owl.py 재작성, 4-pillar 모듈 재설계가 발생한다. 비용 대비 학술적 이득이 불명확하다.

## 2. 새 노선 — SDKB-Centric Curation

**핵심 결정**: SDKB v1.0이 trunk(정본)이다. SemicONTO는 다른 외부 소스(MatKG, CPC/IPC, BIS CCL, Wikidata 등)와 **동등한 큐레이션·정렬 소스**이다.

| 차원 | ADR v1.1 (superseded) | **이 Amendment (active)** |
|---|---|---|
| 상위 온톨로지 | SemicONTO | **SDKB v1.0 자체** |
| `owl:imports` 관계 | SDKB → SemicONTO | **없음.** SemicONTO TTL은 reference cache |
| URI 권위 | `http://w3id.org/SemicONTO/` | **`https://w3id.org/sdkb/`** (변경 없음) |
| 198 노드 마이그레이션 | 필요 | **불필요** |
| 매핑 방향 | `sdkb:Manufacturing ⊂ semi:Experiment` | **`sdkb:Equipment skos:exactMatch semi:Equipment`** (수평) |
| 신규 SemicONTO 개념 도입 | SemicONTO 네임스페이스 그대로 사용 | **`sdkb:` 네임스페이스로 신설** + `skos:exactMatch` 역링크 |
| 라이선스 책임 | SemicONTO에 종속 | SDKB가 정본; 인용으로 CC BY 4.0 준수 |

### 2.1 SemicONTO 자산을 SDKB가 어떻게 흡수하는가

1. **SKOS 매핑 그래프** — [mappings/sdkb_semiconto_alignment.ttl](../mappings/sdkb_semiconto_alignment.ttl)
   `sdkb:Equipment skos:exactMatch semi:Equipment`, `sdkb:Material skos:exactMatch semi:Material` 등 14 코어 클래스 + 198 인스턴스에 대한 SKOS 매핑 트리플.
2. **SDKB-side 확장 클래스** — SemicONTO에만 있는 개념(Dopant, Semiconductor, MaterialProperty 등) 중 가치 있는 것은 **`sdkb:` 네임스페이스로 새 클래스를 신설**하고 `skos:exactMatch <semiconto:…>`로 역링크. 그렇게 하면 SDKB가 자체 그래프로 닫힌 채 외부 인용은 유지된다.
3. **참조 캐시** — [ontology/imports/SemicONTO-0.2.ttl](../ontology/imports/SemicONTO-0.2.ttl)에 TTL을 보관하지만 `owl:imports`하지 않는다. SHACL 검증 시 alignment 그래프가 참조하는 IRI의 존재만 확인.

## 3. Phase 0 실행 결과 (2026-05-12 완료분)

### 3.1 SemicONTO v0.2 인벤토리 ([data/reports/semiconto_analysis.json](../data/reports/semiconto_analysis.json))

| 항목 | 수치 |
|---|---|
| 총 트리플 | 329 |
| 자체(own) 클래스 | 35 |
| 재사용 클래스 (PROV-O 3 / MDO 2 / QUDT 3) | 8 |
| ObjectProperty | 17 (own 13) |
| DatatypeProperty | 9 (own 5) |
| AnnotationProperty | 11 |
| TransitiveProperty | 1 (`hasSubStep`) |

### 3.2 SDKB ↔ SemicONTO 정렬 결과 ([mappings/sdkb_semiconto_alignment.ttl](../mappings/sdkb_semiconto_alignment.ttl))

**클래스-레벨 매핑 (14 SDKB 타입)**

| SDKB 타입 | SemicONTO 타겟 | 관계 | conf |
|---|---|---|---|
| Process | `semi:Experiment` | `skos:broadMatch` | 0.60 |
| SubProcess | `semi:ExperimentalStep` | `skos:closeMatch` | 0.85 |
| Equipment | `semi:Equipment` | **`skos:exactMatch`** | 1.00 |
| Material | `semi:Material` | **`skos:exactMatch`** | 1.00 |
| Vendor | `prov:Agent` | `skos:broadMatch` | 0.70 |
| Organization | `prov:Agent` | `skos:broadMatch` | 0.70 |
| Parameter | `semi:MaterialProperty` | `skos:closeMatch` | 0.70 |
| Metrology | `semi:ExperimentalMethod` | `skos:broadMatch` | 0.70 |
| EquipmentClass | — | none (enrichment) | 0.00 |
| TechnologyNode | — | none (enrichment) | 0.00 |
| FailureMode | — | none (enrichment) | 0.00 |
| RootCause | — | none (enrichment) | 0.00 |
| Mitigation | — | none (enrichment) | 0.00 |
| Skill | — | none (enrichment) | 0.00 |

**인스턴스-레벨 매핑 (198 노드)**

| 메트릭 | 값 |
|---|---|
| 매핑된 인스턴스 | 107 / 198 (54%) |
| `exactMatch` (Equipment + Material) | 61 |
| `closeMatch` (SubProcess + Parameter) | 17 |
| `broadMatch` (Process + Vendor + Org + Metrology) | 29 |
| Bucket B (SemicONTO 부재) | 91 / 198 (46%) — FailureMode 25 + Mitigation 20 + RootCause 20 + Skill 12 + EquipmentClass 11 + TechnologyNode 3 |
| TTL 트리플 | 122 (메타 7 + 클래스 14 + 인스턴스 101) |

**레거시 cross_ref 교정**

이전 baseline JSON의 `provenance.cross_ref[source=semiconto]` 13건이 잘못되어 있었음 (`semiconto:ExperimentStep`은 존재하지 않음 — 실제 명칭은 `ExperimentalStep`이며, Process는 `Experiment`에 매핑되는 게 정확). 이번 alignment에서 모두 교정됨.

| Sdkb id (예) | 잘못된 매핑 | 교정 |
|---|---|---|
| `process:lithography` | `semiconto:ExperimentStep` | `semi:Experiment` (broadMatch) |
| `parameter:pressure` | `semiconto:None` | `semi:MaterialProperty` (closeMatch) |

(전체 13건 → [data/reports/sdkb_semiconto_alignment_report.json](../data/reports/sdkb_semiconto_alignment_report.json) `legacy_corrections`)

### 3.3 보강 후보 분석 ([data/reports/semiconto_enrichment_candidates.json](../data/reports/semiconto_enrichment_candidates.json))

#### Bucket A — SemicONTO 개념 중 SDKB 보강 후보 (29 클래스 + 13 obj props)

**우선순위 HIGH (6 클래스)** — SDKB v1.1로 즉시 흡수 가치 있음

| SemicONTO 클래스 | SDKB 보강 안 |
|---|---|
| `Dopant`, `Acceptor`, `Donor` | `sdkb:Dopant ⊂ sdkb:Material` + Acceptor/Donor 서브클래스. 이온 임플란트·확산 공정 모델링에 필수 |
| `Semiconductor`, `Intrinsic`, `Extrinsic` | `sdkb:Semiconductor ⊂ sdkb:Material` + 진성/외인성 분기. 반도체 도메인의 1차 소재 분류 |

**우선순위 MEDIUM (9 클래스)**

- 측정 방법군: `PhotoelectronSpectroscopy`, `HallEffectMeasurement`, `FieldEffectMeasurement` — SDKB Metrology(3개)에 비해 풍부, SubProcess의 측정 단계를 보강
- 공정 방법군: `ElectronBeamLithography`, `ThermalEvaporation` — SDKB SubProcess의 세분화 후보
- 디바이스 분류: `N-TypeSemiconductor`, `P-TypeSemiconductor` — Dopant 도입 후 자연스러운 확장
- 실험 분류: `SemiconductorExperiment`, `DopingRelation`

**SemicONTO Object Properties — HIGH 우선순위 도입 후보**

| Property | SDKB 의미 |
|---|---|
| `hasNextStep` (Step → Step) | SDKB는 `hasSubprocess`만 있음. **공정 순서 의미론 부재** — 거의 필수 |
| `hasSubStep` (Step → Step, **transitive**) | 다단계 하위공정 트랜지티브 추론 가능. SDKB는 평탄한 hasSubprocess만 보유 |
| `hasAcceptor` / `hasDonor` (ExtrinsicSemi → Material) | Dopant 도입 시 동반 필요 |
| `hasMeasuredProperty` (Experiment → MaterialProperty) | SDKB Parameter에 측정 행위 연결이 없음 |
| `hasStructure` (Material → mdo:Structure) | MDO 정렬을 통한 결정 구조 모델링 (Phase 4 MatKG 정렬의 사전 단계) |

**SemicONTO Datatype Properties — 도입 검토**

`hasExperimentAim`, `hasExperimentName`, `hasExperimentalStepAim`, `hasExperimentalStepDescription`, `hasExperimentalStepID` — SDKB는 이미 `description`/`canonical_name` 등 동등 속성을 인스턴스 JSON에 보유. **재정의 불필요**, 매핑만 충분.

#### Bucket B — SDKB 고유 기여 (SemicONTO 부재, 6 타입)

| SDKB 타입 | 다른 외부 소스 |
|---|---|
| **FailureMode** (25 인스턴스) | JEDEC JEP122H (EM/TDDB/HCI/NBTI) |
| **RootCause** (20) | FMEA 프레임워크 |
| **Mitigation** (20) | FMEA + 공정 표준 |
| **EquipmentClass** (11) | SEMI E10 + IRDS |
| **Skill** (12) | 자체 큐레이션 (이미 110 expert pool로 보완 중) |
| **TechnologyNode** (3) | IRDS roadmap |

Bucket B는 ADR v1.1이 "SemicONTO 모듈로 확장"하라 했던 영역이지만, SemicONTO 자체에 부재하므로 **이미 SDKB가 채운 부분이 곧 학술적 net contribution**으로 정당화된다.

## 4. 후속 Phase의 재조정

ADR v1.1의 Phase 1~5는 SDKB-Centric 전환에 맞춰 다음과 같이 재조정한다:

| ADR v1.1 Phase | 원래 의도 | **SDKB-Centric으로 재조정** |
|---|---|---|
| Phase 1 (코어 재구성) | SemicONTO import + 모듈 분해 | **모듈 분해는 유지** (manufacturing/fmea/supply-chain TTL 분리). SemicONTO import는 **삭제**. 4-pillar 모듈을 모듈 분해의 일부로 포함 |
| Phase 2 (인스턴스 변환) | SemicONTO 클래스로 ABox 변환 | **불필요** — 198 노드는 `sdkb:` URI 유지. SKOS alignment(Phase 0.3 산출물)로 SemicONTO 링크는 이미 확보 |
| Phase 3 (CPC/IPC/F-term) | SemicONTO Hub의 한 spoke | **그대로 진행**. 단 sdkb-patent.ttl(이미 존재)을 정본으로 두고 CPC/IPC는 `skos:ConceptScheme`으로 alignment |
| Phase 3.5 (특허 초록 NLP) | 동일 | **그대로 진행**. SIRP raw JSONL 활용 |
| Phase 4 (외부 소스 링킹) | MatKG/BIS CCL/Wikidata/SemiKong/tibonto/dr | **그대로 진행**. 모든 외부 소스를 SemicONTO와 동등하게 alignment 그래프로 처리 |
| Phase 5 (통합 검증) | SHACL + 커버리지 | **그대로 진행**. 추가로 alignment 그래프 dangling-IRI 검증 추가 |

Phase 1.1 ~ 1.6 중 `sdkb-manufacturing.ttl` (SemicONTO 기반 확장)은 **사라지고**, 대신 Phase 0.4 Bucket A의 HIGH 우선순위 6 클래스를 `sdkb-core.ttl`에 직접 추가하는 작업이 들어선다.

## 5. 결정 기록

1. **SDKB v1.0이 trunk이다.** SemicONTO를 `owl:imports`하지 않는다. SDKB URI는 변경되지 않는다.
2. **모든 외부 소스(SemicONTO, MatKG, CPC, IPC, BIS CCL, Wikidata, SemiKong, tibonto/dr, JEDEC, SEMI E10)는 동등한 alignment source로 취급한다.** alignment 그래프는 `mappings/sdkb_<source>_alignment.ttl` 패턴으로 분리한다.
3. **SemicONTO에서 가치 있는 6+9 클래스, 5 ObjectProperty는 SDKB v1.1 enrichment로 흡수한다.** 새 클래스/속성은 `sdkb:` 네임스페이스에 두고 `skos:exactMatch`로 SemicONTO를 역링크한다.
4. **레거시 baseline의 잘못된 cross_ref 13건은 교정되었다.** baseline JSON 자체를 수정할지(원본 클린업) vs alignment 그래프가 정본이 되는지는 후속 결정.
5. **ADR v1.1은 superseded로 마크하되 삭제하지 않는다.** 변경 이력 추적용으로 보존.

## 6. 산출물 (Phase 0)

| 경로 | 종류 | 상태 |
|---|---|---|
| [ontology/imports/SemicONTO-0.2.ttl](../ontology/imports/SemicONTO-0.2.ttl) | TTL cache (12 KB, SHA256 `4c53544d…`) | ✅ |
| [ontology/imports/README.md](../ontology/imports/README.md) | retrieval metadata | ✅ |
| [scripts/analyze_semiconto.py](../scripts/analyze_semiconto.py) | rdflib parser | ✅ |
| [scripts/build_semiconto_alignment.py](../scripts/build_semiconto_alignment.py) | alignment builder | ✅ |
| [scripts/identify_enrichment_candidates.py](../scripts/identify_enrichment_candidates.py) | bucket A/B 분석 | ✅ |
| [data/reports/semiconto_analysis.json](../data/reports/semiconto_analysis.json) | 클래스/속성 인벤토리 | ✅ |
| [mappings/sdkb_semiconto_alignment.csv](../mappings/sdkb_semiconto_alignment.csv) | 198 인스턴스 매핑 행 | ✅ |
| [mappings/sdkb_semiconto_alignment.ttl](../mappings/sdkb_semiconto_alignment.ttl) | SKOS 트리플 (122개) | ✅ |
| [data/reports/sdkb_semiconto_alignment_report.json](../data/reports/sdkb_semiconto_alignment_report.json) | 매핑 통계 + 레거시 교정 13건 | ✅ |
| [data/reports/semiconto_enrichment_candidates.json](../data/reports/semiconto_enrichment_candidates.json) | Bucket A 29 클래스·13 obj props + Bucket B 6 SDKB-unique | ✅ |
| [docs/architecture_amendment_sdkb_centric.md](architecture_amendment_sdkb_centric.md) | 본 문서 | ✅ |

## 7. 권장 다음 단계 (Phase 1, 새 노선)

1. **Bucket A HIGH 6 클래스를 `sdkb-core.ttl`에 추가** — Dopant/Acceptor/Donor + Semiconductor/Intrinsic/Extrinsic. `skos:exactMatch`로 SemicONTO 역링크.
2. **HIGH ObjectProperty 2개 도입** — `sdkb:hasNextStep`(공정 순서), `sdkb:hasSubStep`(transitive). 기존 `hasSubprocess`와의 의미 차이 명시.
3. **모듈 분해** — `sdkb-fmea.ttl`(FailureMode/RootCause/Mitigation), `sdkb-supply-chain.ttl`(Vendor/Organization)을 분리. `sdkb-core.ttl`은 imports 체인으로 유지.
4. **CPC/IPC SKOS 통합** (ADR v1.1 Phase 3) — sdkb-patent.ttl을 정본으로 두고 CPC를 alignment로 연결.

## 8. 부록 — Phase 0 재현 절차

```bash
# 1) SemicONTO TTL fetch (network)
curl -sSL -A "SDKB-curation/0.1" -H "Accept: text/turtle" \
  -o ontology/imports/SemicONTO-0.2.ttl \
  https://huanyu-li.github.io/SemicONTO/0.2/SemicONTO.ttl

# 2) verify checksum
echo "4c53544de016b2d1147d41ba68094c7849999494378cd2c68674334b0e2e8d52  ontology/imports/SemicONTO-0.2.ttl" | sha256sum -c

# 3) analyze + align + enrichment
PATH=.venv/bin:$PATH python scripts/analyze_semiconto.py
PATH=.venv/bin:$PATH python scripts/build_semiconto_alignment.py
PATH=.venv/bin:$PATH python scripts/identify_enrichment_candidates.py
```

추후 Makefile 타깃 `make semiconto-phase0` 추가 권장.
