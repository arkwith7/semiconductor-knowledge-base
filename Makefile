.PHONY: all install parse owl convert align validate test clean

PYTHON ?= python3

# ═══════════════════════════════════════════════════════════════════
# SDKB v1.0 — Build Pipeline
# ═══════════════════════════════════════════════════════════════════

all: parse owl convert

# ── Install dependencies ──────────────────────────────────────────
install:
	$(PYTHON) -m pip install -e ".[dev]"

# ── Week 1: Baseline parsing → schema report + Parquet ────────────
parse:
	$(PYTHON) scripts/parse_baseline.py

# ── Week 2: OWL metamodel → ontology/sdkb-core.ttl ───────────────
owl:
	$(PYTHON) scripts/build_owl.py

# ── Week 3: JSON → RDF/JSON-LD conversion ────────────────────────
convert:
	$(PYTHON) scripts/convert_rdf.py

# ── Week 4: Alignment candidate generation ───────────────────────
align:
	$(PYTHON) scripts/align_candidates.py

# ── SHACL validation (release gate) ──────────────────────────────
validate:
	$(PYTHON) scripts/validate_shacl.py

# ── Run all tests ─────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# ── Full pipeline (parse → owl → convert → validate → test) ──────
pipeline: parse owl convert validate test

# ── Clean generated artifacts ─────────────────────────────────────
clean:
	rm -f data/schema_report.json data/nodes.parquet data/edges.parquet
	rm -f ontology/sdkb-core.ttl ontology/sdkb-core-data.ttl ontology/sdkb-core-data.jsonld
	rm -f mappings/mapping_candidates.tsv
