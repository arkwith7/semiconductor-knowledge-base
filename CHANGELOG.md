# Changelog

All notable changes to SDKB will be documented in this file.

## [Unreleased] — v1.0.0-dev

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
