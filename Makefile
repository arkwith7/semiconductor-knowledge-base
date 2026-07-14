.PHONY: all install venv parse owl convert align validate test clean \
        ingest-sirp sirp-pairs sirp-problems sirp experts \
        compliance curated-experts curated-ratings expdataset abox abox-patents \
        semiconto-fetch semiconto-analyze semiconto-align semiconto-enrich semiconto-phase0 \
        viz viz-clean viz-open \
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
	@echo "  curated-experts Ingest curated 110-expert pool"
	@echo "  curated-ratings Ingest 7,800 3-rater ratings + compute kappa/ICC"
	@echo "  expdataset      compliance + curated-experts + curated-ratings"
	@echo "  abox            convert + lift experts/problems → A-Box TTL (notebook 06)"
	@echo "  abox-patents    convert + ingest-sirp + lift patents → A-Box TTL (notebook 07)"
	@echo "  semiconto-fetch    Download SemicONTO v0.2 TTL into ontology/imports/"
	@echo "  semiconto-analyze  Parse SemicONTO TTL → data/reports/semiconto_analysis.json"
	@echo "  semiconto-align    Build SDKB↔SemicONTO SKOS alignment (mappings/)"
	@echo "  semiconto-enrich   Identify enrichment candidates (Bucket A/B)"
	@echo "  semiconto-phase0   fetch + analyze + align + enrich (SDKB-centric Phase 0)"
	@echo "  viz             Build interactive GitHub Pages site → site/"
	@echo "  viz-open        Build viz and open site/index.html in default browser"
	@echo "  viz-clean       Remove site/ build artifacts"
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

# Lift curated experts + SME problems into an RDF A-Box linked to the
# ontology node URIs emitted by `convert` (consumed by notebook 06).
abox: convert
	$(PYTHON) scripts/build_abox_experts_problems.py

# Lift the SIRP rejected-patent corpus into an RDF A-Box (consumed by
# notebook 07 — ontology-driven prior-art retrieval).
abox-patents: convert ingest-sirp
	$(PYTHON) scripts/build_abox_patents.py

# KSIA 회원사 명부 → ont:Vendor A-Box. abox-patents 뒤에 와야 한다 —
# 이미 특허 출원인(Organization)으로 존재하는 회사를 알아보고 중복 노드를 만들지 않으려면
# sdkb-abox-patents.ttl 이 먼저 있어야 한다.
abox-vendors: convert abox-patents
	$(PYTHON) scripts/build_abox_vendors_ksia.py

align:
	$(PYTHON) scripts/align_candidates.py

# core-data 만 검증하면 Expert·Problem A-Box 에 걸리는 shape 이 **한 번도 안 돈다**
# (Shape_PersonProblemLabel 이 그랬다 — 라벨 규약 위반이 게이트를 통과했다).
validate:
	$(PYTHON) scripts/validate_shacl.py --data ontology/sdkb-core-data.ttl ontology/sdkb-abox-experts-problems.ttl

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

# ── Curated ExpDataSet integration ───────────────────────────────
compliance:
	$(PYTHON) scripts/seed_compliance_governance.py

curated-experts:
	$(PYTHON) scripts/ingest_curated_experts.py

curated-ratings:
	$(PYTHON) scripts/ingest_curated_ratings.py

expdataset: compliance curated-experts curated-ratings

# ── SemicONTO Phase 0 (SDKB-centric curation) ────────────────────
SEMICONTO_TTL := ontology/imports/SemicONTO-0.2.ttl
SEMICONTO_URL := https://huanyu-li.github.io/SemicONTO/0.2/SemicONTO.ttl
SEMICONTO_SHA := 4c53544de016b2d1147d41ba68094c7849999494378cd2c68674334b0e2e8d52

semiconto-fetch:
	@mkdir -p ontology/imports
	@if [ ! -f $(SEMICONTO_TTL) ]; then \
	  echo "Fetching SemicONTO v0.2 TTL from $(SEMICONTO_URL)"; \
	  curl -sSL -A "SDKB-curation/0.1" -H "Accept: text/turtle" \
	    -o $(SEMICONTO_TTL) $(SEMICONTO_URL); \
	else \
	  echo "$(SEMICONTO_TTL) already cached — skipping fetch"; \
	fi
	@echo "$(SEMICONTO_SHA)  $(SEMICONTO_TTL)" | sha256sum -c

semiconto-analyze: semiconto-fetch
	$(PYTHON) scripts/analyze_semiconto.py

semiconto-align: semiconto-analyze
	$(PYTHON) scripts/build_semiconto_alignment.py

semiconto-enrich: semiconto-align
	$(PYTHON) scripts/identify_enrichment_candidates.py

semiconto-phase0: semiconto-fetch semiconto-analyze semiconto-align semiconto-enrich

# ── Visualization (GitHub Pages demo) ─────────────────────────────
viz:
	$(PYTHON) scripts/build_viz.py

viz-open: viz
	@if command -v xdg-open >/dev/null 2>&1; then xdg-open site/index.html; \
	elif command -v open >/dev/null 2>&1; then open site/index.html; \
	else echo "open site/index.html manually"; fi

viz-clean:
	rm -rf site/

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
	rm -rf site/
