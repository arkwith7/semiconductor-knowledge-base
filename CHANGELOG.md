# Changelog

All notable changes to SDKB will be documented in this file.

## [Unreleased] — v1.0.0-dev

### Added
- Project scaffolding: directory structure, pyproject.toml, Makefile
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
