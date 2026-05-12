# Changelog

All notable changes to SDKB will be documented in this file.

## [Unreleased] — v1.0.0-dev

### Added
- Amendment v1 / v2 ([docs/plan_amendment_v1.md](docs/plan_amendment_v1.md), [v2](docs/plan_amendment_v2.md))
- SIRP integration: 773 examiner-grounded rejected patents → 7,500 prior-art pairs, 50 problems, 25 adversarial scenarios
- Patent module ontology: `ontology/sdkb-patent.ttl` + SHACL `validation/shapes_patent.ttl` + Korean industrial-tech-protection module `sdkb-governance-kr.ttl`
- Alignment-track ontologies: `sdkb-rbv.ttl`, `sdkb-commercialization.ttl`, `sdkb-foresight.ttl`
- Scripts: `ingest_rejected_patents.py`, `build_prior_art_pairs.py`, `sample_problems.py`, `gen_experts.py`
- Tests: `tests/test_patents.py` (26 SIRP regression tests)
- Docs: AFCP-EM architecture, leakage protocol, expert validation log, datasheet, commercialization strategy v1
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
