# Changelog

All notable changes to SDKB will be documented in this file.

## [Unreleased] — v1.0.0-dev

### Fixed / Documented (2026-07-20 — 인력·문제 축 프로비넌스 정본화 + 전문가 이름 충돌 해소)
- **`docs/deidentification_protocol.md` 신설.** 인력·문제 축이 실 원천을 그대로 쓸 수 없는
  데이터임을, 그리고 무엇을 어떻게 변조했는지를 기록한다. Expert 110 = **변조 파생 5**
  (EXP_001–005, 실 경력기술서 근거 · "1.기본정보"·"4.주요 경력 사항" 식별불가 처리 · 가명 ·
  수치는 생성값) **+ 결정적 생성 105**. Problem 226 = 최초 큐레이션 61 + 수출통제 시나리오 15 +
  온톨로지 추론 시나리오 10 + 공개사례 파생 18(WM-811K 8·블로그 5·TEMAZ 3·문헌 2) +
  구조 파생 생성 122. **원본 문서는 저장소·릴리스·하류 vendor 산출물 어디에도 반입된 적이 없다.**
- **왜 지금.** `docs/datasheet.md` 는 전문가 프로필을 일괄 "synthetic … not personally
  identifiable" 로 단언했는데, 이는 생성 105건에만 정밀하고 변조 파생 5건에는 부정확했다.
  하류 논문이 이 축의 출처를 인용해야 하는데 **참조할 문서 자체가 없었다.** datasheet 3개 항목과
  `build_abox_experts_problems.py` 의 "KR 파일이 실명" 주석(사실과 다름)을 함께 정정했다.
- **전문가 이름 충돌 해소** (`scripts/reassign_expert_names.py`, 신규 · 결정적 · 멱등).
  이름 풀이 좁아 **56개 이름이 110명에 배분**돼 있었다. 완전 중복 레코드는 **0건**이고(38필드
  정규화 해시), IRI 충돌도 0이며, 겹치는 것은 `skos:prefLabel` 문자열뿐이었다 — 그런데 라벨만
  프로젝션하는 CQ11 이 텍스트상 동일한 행 11건을 내 **데이터 중복처럼 보였다.** 삭제는 서로 다른
  프로필 54개를 없애므로 채택하지 않고, 이름이 이미 가명이므로 **성 보존 + 이름 교체**로 재부여했다
  (EN 자리표시자 `"Kang, [Given Name]"` 가 그대로 유효해진다). 고유 이름 **56 → 110**.
- **프로비넌스 위생** (`scripts/sanitize_expert_provenance.py`, 신규 · 멱등): `upgrade_log.resume_matched`
  의 `pdf` 필드가 담고 있던 **저장소 밖 비공개 경로 5건**을 KR·EN 양쪽에서 제거했다. 재현에 쓸 수
  없으면서 내부 디렉터리 구조만 배포물에 남겼기 때문이다. `text_sha256` 은 남긴다 — 파생 사실을
  고정하는 앵커는 해시이지 파일 위치가 아니다.
- 그래프: `sdkb-abox-experts-problems.ttl` **3,653 트리플 불변** · Expert 110 · Problem 226 불변.
  변경 트리플은 `skos:prefLabel` 54 + `skos:altLabel` 7 뿐. `make validate` SHACL 통과(양 그래프).
- **하류 통보 — `sdkb-foresight-paper`.** 트리플 수는 안 움직이지만 **TTL 내용이 바뀌어 sha256 이
  바뀐다.** 재vendor 후 G₀ 를 재동결해야 하며, **트리플 44,202 는 그대로**다. 특허↔공정 엣지를
  건드리지 않으므로 **H1·H2 결론은 불변**이다. CQ11 은 66행 유지에 distinct 가 55 → 66 으로 올라
  라벨 프로젝션의 겉보기 중복이 사라진다.

### Added (2026-07-15 — 청구항 전문 어휘: IP-R&D FTO 자기완결성)
- **`ont:claimText`**(반복 가능 · 청구항당 1트리플, 선두 번호 보존) · **`ont:claimCount`**(정수) 신설.
  TBox `ontology/sdkb-patent.ttl`, 기존 `firstClaimText`/`abstractText` 패턴 그대로(domain `ont:Patent`,
  range string/integer). **파급**: 순수 가산 — 기존 인스턴스·엣지·shape 불변, 하류 G₀ 는 TBox 선언
  2개만 늘고 ABox 0 변화(재vendor 후 재동결 시 H1 불변을 하류에서 실증).
- **왜.** KIPRIS 로 수집한 특허는 제목+링크만 있어 IP-R&D 세부 태스크(FTO·회피설계)를 그래프만으로
  실행할 수 없었다 — 태스크 시점에 청구항을 다시 긁어야 해 **온톨로지의 문제해결 자기완결성**이
  깨졌다. `firstClaimText`(청구항1)만으로는 독립·종속 청구항 전체를 못 담는다. `getBibliographyDetailInfoSearch`
  가 청구항 전문을 주므로(claimCount 포함) 이를 실체화한다. 소스 라이선스 종속 — KIPRIS 원문은
  로컬 그래프 전용(비커밋·비재배포).

### Added (2026-07-12 — SemiKong 공정 분류 복원 + 소자 어휘 보강)
- **SDKB 는 출처 분류의 3개 그룹을 통째로 빠뜨리고 있었다.** `Process` 노드의 `provenance.source_id`
  (`L1-Planarization` 등)가 보여주듯 SDKB 의 공정은 SemiKong Appendix A **Table 7 의 L1 Process Group**
  인데, Table 7 은 그룹이 **10개**이고 SDKB 는 7개만 담았다. 누락: **1. Substrate Preparation ·
  9. Advanced Modules · 10. Back-End Processes**. 즉 다이싱·패키징·금속화·웨이퍼 테스트를
  **표현할 어휘 자체가 없었다.** 있는 그룹들도 L2 모듈 대부분이 빠져 있었다(예: Film Formation 에
  Oxidation·Epitaxy 없음, Thermal Processing 에 Annealing 없음).
- `scripts/add_semikong_process_nodes.py` (신규, 멱등): Table 7 의 Group·Module 열을 **전량 복원**한다.
  **Process 8 → 11** (+3 그룹), **SubProcess 12 → 38** (+26 모듈). 기존 20개 IRI 는 **하나도 건드리지
  않는다** — 하류(특허 ABox 링크, foresight-paper 의 G₀)가 그것을 가리키기 때문이다.
  Table 7 자체의 중복(1.3 Cleaning ≡ 6. Cleaning, 7.2 Thermal Oxidation ≡ 2.1 Oxidation)은 하나로 합쳤고,
  그 판단을 노드 `provenance.note` 에 남겼다.
- **Device 31 → 34**: `EPROM`(Q378210) · `FeRAM`(Q703656) · `Diode`(Q11656) 추가.
  EPROM 누락이 특히 컸다 — IPC `H10B 69/00`(EPROM 잔여군)과 구 `H01L 21/8247`(EPROM 제조)에 걸리는
  특허가 SIRP 1,000건 중 다수인데 대응 개념이 없었다. Wikidata 상 EEPROM(Q205908)은 EPROM 의
  `P279 subclass of` 하위이므로 **별개 소자**임을 확인하고 추가했다.
  `add_device_nodes.py` 에 `discrete` 카테고리 추가(다이오드는 logic/memory/power/sensor/packaging 중
  어디에도 정직하게 들어가지 않는다).
- 그래프: core-data **2,743 트리플**. `make validate` SHACL 통과, `pytest` 75 passed / 10 skipped.
- **하류 통보**: `sdkb-foresight-paper` 의 G₀ 가 26,676 → **26,973 트리플**로 움직인다. 이 논문은 아직
  G₀ 를 동결하기 전이므로 의도된 변경이며, baseline 재조립 후 표 3·H1 관측 단위를 갱신한다.

### Fixed / Changed (2026-05-17 — figure reconciliation, reliability re-measurement, OWL regen)
- **OWL regression fixed**: committed `ontology/sdkb-core.ttl` was a stale `1.0.0-dev` build missing the enrichment layer + `dcterms:modified`/`dcterms:references`/`rdfs:seeAlso`/`versionInfo 1.1.0-dev`, causing 24 `tests/test_owl.py` failures. Regenerated via `make owl` (`scripts/build_owl.py`) → **438 triples**, `1.1.0-dev`. Full suite now **75 passed / 10 skipped (85 collected) / 0 failed**. (Earlier "46/46" and "85/85" were pre-regression counts.)
- **Verified-figure reconciliation** (single snapshot, 2026-05-17): curation graph **229 nodes / 268 edges** (baseline origin 198/264, expanded by curation incl. `Device`); SIRP raw corpus **1,000 records** (the prior "773"/"SIRP-773" was the initial cohort snapshot; the 7,500 GT pairs remain frozen at the 773-snapshot and are unchanged). README (EN/KO), datasheet, and the SIRP card synced to these figures.
- **Synthetic-rating reliability re-measured to plan spec** (v2 §12.1 specifies *weighted* κ; code had computed unweighted Fleiss κ on an ordinal/skewed scale): `scripts/ingest_curated_ratings.py` now reports mean pairwise quadratic-weighted κ = **0.550**, Krippendorff α(interval) = 0.552, ICC(2,k) consensus = **0.787** (passes the ≥0.70 gate; this is the reliability of the 3-rater consensus label actually used as GT), with original Fleiss κ = 0.258 / ICC(2,1) = 0.552 kept verbatim and kappa-paradox evidence documented. New `data/experts/reliability_report.{md,json}`.
- **Publication-integrity docs added**: [docs/project/dataset_publication_risk_review.md](docs/project/dataset_publication_risk_review.md) (8-item dataset-dispute risk review); datasheet §8 + SIRP card §5-2/§7-1 now state explicitly that neither GT track is human-expert annotation (examiner-grounded 7,500 = objective KIPO citations; 3-rater 7,800 = algorithmically simulated).

### Added (2026-05-12 — SDKB-Centric Curation, Phase 0+1)
- Architecture amendment: [docs/project/architecture_amendment_sdkb_centric.md](docs/project/architecture_amendment_sdkb_centric.md) reverses ADR v1.1 — SDKB v1.0 is the trunk; SemicONTO becomes one of many external alignment sources via SKOS mapping, not the upper ontology (no `owl:imports`).
- SemicONTO Phase 0 curation: [ontology/imports/SemicONTO-0.2.ttl](ontology/imports/SemicONTO-0.2.ttl) cached, [data/reports/semiconto_analysis.json](data/reports/semiconto_analysis.json) inventory, [mappings/sdkb_semiconto_alignment.{csv,ttl}](mappings/) (122 SKOS triples, 107/198 nodes aligned), [data/reports/semiconto_enrichment_candidates.json](data/reports/semiconto_enrichment_candidates.json) (Bucket A 29 cls + 13 obj props / Bucket B 6 SDKB-unique types).
- SDKB v1.1 enrichment layer in [ontology/sdkb-core.ttl](ontology/sdkb-core.ttl): 6 new classes (`Semiconductor`, `Intrinsic/ExtrinsicSemiconductor`, `Dopant`, `Acceptor`, `Donor`) and 4 new ObjectProperties (`hasNextStep`, `hasSubStep` transitive, `hasAcceptor`, `hasDonor`) — all with `skos:exactMatch` back-link to SemicONTO. OWL ontology grew from 257 → 353 triples.
- Scripts: `analyze_semiconto.py`, `build_semiconto_alignment.py`, `identify_enrichment_candidates.py`. Makefile target `semiconto-phase0` (fetch + analyze + align + enrich).
- Tests: 8 new enrichment regression tests in `tests/test_owl.py::TestEnrichmentLayer` (54/54 passing).
- docs/archive/: superseded ADR v1.1 moved here; patent_*_plan.md parents rewired to the new amendment.

### Fixed (2026-05-12)
- 13 legacy `provenance.cross_ref[source=semiconto]` entries in baseline JSON were wrong (`semiconto:ExperimentStep` does not exist — actual class is `ExperimentalStep`; Process was mis-mapped to step instead of `Experiment`). **Now corrected at the source**: baseline JSON updated in-place; alignment graph reports `legacy_corrections: 0`. Each corrected entry carries an updated `note` explaining the fix.

### Added (2026-05-12 — Instance-level enrichment)
- `mappings/sdkb_instance_enrichment.json` — externalized type-refinement overrides (declarative, audit-friendly). Phase 1 v1.1 ships with `material:polysilicon → sdkb:Semiconductor`. Empty enrichment classes (Dopant/Acceptor/Donor/Intrinsic/Extrinsic) are documented in the config rather than silently absent.
- `scripts/convert_rdf.py` reads the enrichment file and emits additional `rdf:type` triples (primary type preserved, refined class added — safe because refined ⊂ primary). RDF data graph: 2117 → 2118 triples.
- `tests/test_instance_enrichment.py` — 9 regression tests covering (a) config schema, (b) refined types present in data graph, (c) baseline cross_refs reference only real SemicONTO classes.

### Added (2026-05-12 — Self-description metadata + DT prop alignment)
- `sdkb-core.ttl` ontology declaration now self-describes its external dependencies: `owl:imports` is reserved for PROV-O (the only hard import); SemicONTO 0.2 and QUDT are declared via `dcterms:references` to make the SDKB-centric policy machine-readable. Added `dcterms:modified` (2026-05-12) and bumped `owl:versionInfo` to `1.1.0-dev`. `rdfs:seeAlso` links to the architecture amendment doc and the alignment graph URI. OWL ontology: 433 → 438 triples.
- 5 SemicONTO DatatypeProperty mappings encoded in [mappings/sdkb_semiconto_alignment.ttl](mappings/sdkb_semiconto_alignment.ttl): `semi:hasExperimentName` ↔ `skos:prefLabel`, three `*Aim`/`*Description` predicates ↔ `skos:definition`, `semi:hasExperimentalStepID` ↔ `dcterms:identifier`. All recorded as `skos:closeMatch` with rdfs:comment rationale; also surfaced in `data/reports/sdkb_semiconto_alignment_report.json` under `datatype_property_alignment`. Alignment graph: 122 → 132 triples.
- 11 new regression tests: `tests/test_owl.py::TestOntologyDependencyMetadata` (6) and `tests/test_alignment_graph.py` (5). Total **85/85 passing**.

### Added (2026-05-12 — MEDIUM enrichment + SHACL + QUDT)
- Bucket A MEDIUM enrichment (8 classes + 1 obj prop): `ElectronBeamLithography`/`ThermalEvaporation` ⊂ SubProcess; `HallEffectMeasurement`/`FieldEffectMeasurement`/`PhotoelectronSpectroscopy` ⊂ Metrology; `NTypeSemiconductor`/`PTypeSemiconductor` ⊂ ExtrinsicSemiconductor; `DopingRelation` standalone; `hasEquipment` (SubProcess→Equipment). All with `skos:exactMatch` to SemicONTO. Selective absorption — SemicONTO classes tied to absent parents (Experiment, InformationObject) were intentionally skipped.
- SHACL enrichment shapes (`validation/shapes.ttl` +53 triples): `Shape_ExtrinsicSemiconductor` enforces "must have hasAcceptor or hasDonor" (SemicONTO axiom); domain shapes for `hasAcceptor`/`hasDonor` (subjects must be ExtrinsicSemiconductor); range shapes for `hasNextStep`/`hasSubStep`/`hasEquipment`; `Shape_DopantInstance` enforces Dopant ≡ Acceptor ∪ Donor at instance level.
- QUDT-aligned Quantity layer: abstract `sdkb:Quantity` (`skos:exactMatch qudt:Quantity`), `sdkb:MaterialProperty ⊂ sdkb:Quantity` (`skos:exactMatch semi:MaterialProperty`), existing `sdkb:Parameter` reclassified as `⊂ sdkb:Quantity`. New properties: `sdkb:hasProperty` (Material → MaterialProperty), `sdkb:hasMeasuredProperty` (SubProcess → MaterialProperty), `sdkb:hasNumericValue` (xsd:decimal), `sdkb:hasUnitSymbol` (xsd:string). QUDT NOT imported — referenced by IRI only, consistent with SDKB-centric policy.
- OWL ontology grew 257 → 353 → 398 → **433 triples** across the three Phase 1 enrichment passes.
- 21 additional tests in `tests/test_owl.py::TestEnrichmentMedium` and `tests/test_owl.py::TestQuantityLayer`. Total **74/74 passing**.

### Added
- Amendment v1 / v2 ([docs/project/plan_amendment_v1.md](docs/project/plan_amendment_v1.md), [v2](docs/project/plan_amendment_v2.md))
- SIRP integration: 773 examiner-grounded rejected patents → 7,500 prior-art pairs, 50 problems, 25 adversarial scenarios
- Patent module ontology: `ontology/sdkb-patent.ttl` + SHACL `validation/shapes_patent.ttl` + Korean industrial-tech-protection module `sdkb-governance-kr.ttl`
- Alignment-track ontologies: `sdkb-rbv.ttl`, `sdkb-commercialization.ttl`, `sdkb-foresight.ttl`
- Scripts: `ingest_rejected_patents.py`, `build_prior_art_pairs.py`, `sample_problems.py`, `gen_experts.py`
- Tests: `tests/test_patents.py` (26 SIRP regression tests)
- Docs: SDKB-Match architecture, leakage protocol, expert validation log, datasheet, commercialization strategy v1
- Notebook: `notebooks/04_prior_art_baseline.ipynb` (TF-IDF baseline with MRR/NDCG@5/Recall@K)
- Makefile targets: `venv`, `ingest-sirp`, `sirp-pairs`, `sirp-problems`, `sirp`, `experts`, `pipeline-full`
- CITATION.cff with advisor attribution

### Fixed
- **Bug 1**: deduplicated `equipment:asml_scanner` in `data/semiconductor_v0_3.json` (was 198 nodes including a duplicate, now 198 unique with `vendor:semes` added as a meaningful Korean 소부장 vendor)
- **Bug 2**: widened OWL property domains via `owl:unionOf` for `mitigatedBy`, `requiresSkill`, `madeBy`, `incompatibleWith` (and `notAllowedWith` range) in `scripts/build_owl.py` — closes RDFS inference cascade that mis-typed `RootCause` nodes as `FailureMode`
- **Bug 3**: added 4 missing `OBSERVED_IN` edges for `cdu` / `erosion` / `footing` / `particle` FailureModes — closes the remaining `Shape_FailureMode` SHACL gap
- `validation/shapes.ttl`: added missing `rdf:` / `rdfs:` prefix declarations (latent bug exposed under strict rdflib 7.x)
- All 20 baseline tests, 26 SIRP tests, and SHACL validation now pass; baseline 198 nodes / 268 edges

### Project scaffolding
- Namespace/ID policy: `config/namespaces.py`, `config/context.jsonld`
- Week 1 script: `scripts/parse_baseline.py` (schema report, Parquet extraction)
- Week 2 script: `scripts/build_owl.py` (OWL metamodel with 14 Core + 7 Governance classes)
- Week 3 script: `scripts/convert_rdf.py` (JSON→RDF/Turtle + JSON-LD)
- Week 4 script: `scripts/align_candidates.py` (lexical fuzzy matching engine)
- SHACL shapes: `validation/shapes.ttl` (release gate validation rules)
- PROV-O template: `provenance/prov.ttl` (agents, activities, source entities)
- JSON-LD context: `config/context.jsonld` (W3C JSON-LD 1.1 mapping)
- SPARQL examples: regulatory risk, FMEA path, tech gap queries
- Test suite: `tests/test_baseline.py`, `tests/test_owl.py`
- SHACL validator script: `scripts/validate_shacl.py`
