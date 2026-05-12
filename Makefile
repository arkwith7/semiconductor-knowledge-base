.PHONY: all install venv parse owl convert align validate test clean \
        ingest-sirp sirp-pairs sirp-problems sirp experts \
        compliance curated-experts curated-ratings expdataset \
        pipeline pipeline-sirp pipeline-full pipeline-with-expdataset help

PYTHON ?= python3

# ═══════════════════════════════════════════════════════════════════
# SDKB v1.0 — Build Pipeline
# Two tracks: (1) baseline curation, (2) SIRP patent layer.
# ═══════════════════════════════════════════════════════════════════

help:
	@echo "Targets:"
	@echo "  venv            Create .venv with Python 3.11"
	@echo "  install         Install package into the active env with dev+priorart+notebook extras"
	@echo "  parse           Baseline JSON → schema_report + parquet"
	@echo "  owl             Build sdkb-core.ttl ontology"
	@echo "  convert         JSON → RDF/JSON-LD"
	@echo "  align           Generate mapping candidates"
	@echo "  validate        SHACL validation"
	@echo "  test            Run pytest"
	@echo "  ingest-sirp     SIRP JSONL → patents/*.parquet"
	@echo "  sirp-pairs      Build 7,500 prior-art pairs"
	@echo "  sirp-problems   50 problems + 25 scenarios"
	@echo "  sirp            ingest-sirp + sirp-pairs + sirp-problems"
	@echo "  experts         Build 100 synthetic expert profiles"
	@echo "  compliance      Seed KR+US governance instances from ExpDataSet"
	@echo "  curated-experts Ingest curated 100-expert pool (Park 2026a)"
	@echo "  curated-ratings Ingest 7,800 3-rater ratings + compute kappa/ICC"
	@echo "  expdataset      compliance + curated-experts + curated-ratings"
	@echo "  pipeline        parse + owl + convert + validate + test"
	@echo "  pipeline-sirp   pipeline + sirp"
	@echo "  pipeline-full   pipeline + sirp + experts"
	@echo "  pipeline-with-expdataset   pipeline-full + expdataset"
	@echo "  clean           Remove generated artifacts"
	@echo ""
	@echo "Tip: prefix targets with PATH=.venv/bin:\$\$PATH or source .venv/bin/activate first."

all: parse owl convert

# ── Setup ─────────────────────────────────────────────────────────
venv:
	python3.11 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip setuptools wheel
	.venv/bin/python -m pip install -e ".[dev,priorart,notebook]"

install:
	$(PYTHON) -m pip install -e ".[dev,priorart,notebook]"

# ── Baseline track ────────────────────────────────────────────────
parse:
	$(PYTHON) scripts/parse_baseline.py

owl:
	$(PYTHON) scripts/build_owl.py

convert:
	$(PYTHON) scripts/convert_rdf.py

align:
	$(PYTHON) scripts/align_candidates.py

validate:
	$(PYTHON) scripts/validate_shacl.py

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# ── SIRP (patent) track ───────────────────────────────────────────
ingest-sirp:
	$(PYTHON) scripts/ingest_rejected_patents.py

sirp-pairs: ingest-sirp
	$(PYTHON) scripts/build_prior_art_pairs.py

sirp-problems: ingest-sirp
	$(PYTHON) scripts/sample_problems.py

sirp: ingest-sirp sirp-pairs sirp-problems

experts:
	$(PYTHON) scripts/gen_experts.py

# ── ExpDataSet (Park 2026a) integration ──────────────────────────
compliance:
	$(PYTHON) scripts/seed_compliance_governance.py

curated-experts:
	$(PYTHON) scripts/ingest_curated_experts.py

curated-ratings:
	$(PYTHON) scripts/ingest_curated_ratings.py

expdataset: compliance curated-experts curated-ratings

# ── Composed pipelines ────────────────────────────────────────────
pipeline: parse owl convert validate test

pipeline-sirp: pipeline sirp

pipeline-full: pipeline sirp experts

pipeline-with-expdataset: pipeline-full expdataset

# ── Clean ─────────────────────────────────────────────────────────
clean:
	rm -f data/schema_report.json data/nodes.parquet data/edges.parquet
	rm -f data/problems.parquet data/regulatory_scenarios.parquet data/problems_report.json
	rm -f data/expert_profiles.parquet data/experts_report.json
	rm -f data/patents/rejected_patents_meta.parquet
	rm -f data/patents/ipc_links.parquet
	rm -f data/patents/prior_art_edges.parquet
	rm -f data/patents/prior_art_pairs.parquet
	rm -f data/patents/ingest_report.json data/patents/pairs_report.json
	rm -f data/compliance/technology_controls.parquet data/compliance/seed_report.json
	rm -f data/experts/curated_profiles.parquet data/experts/curated_profiles_report.json
	rm -f data/experts/curated_ratings.parquet data/experts/curated_ratings_pivot.parquet
	rm -f data/experts/reliability_report.md data/experts/reliability_report.json
	rm -f ontology/sdkb-core.ttl ontology/sdkb-core-data.ttl ontology/sdkb-core-data.jsonld
	rm -f ontology/sdkb-governance-kr-instances.ttl ontology/sdkb-governance-us-instances.ttl
	rm -f mappings/mapping_candidates.tsv
