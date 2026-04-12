---
language:
  - en
  - ko
license: cdla-permissive-2.0
tags:
  - semiconductor
  - ontology
  - knowledge-graph
  - FMEA
  - foresight
  - supply-chain
  - provenance
  - curation
task_categories:
  - graph-ml
size_categories:
  - 1K<n<10K
---

# SDKB v1.0 — Semiconductor Domain Knowledge Base

**Provenance-grounded curation ontology for semiconductor manufacturing technology management.**

## Overview

SDKB (Semiconductor Domain Knowledge Base) v1.0 is a curated, open-core knowledge graph
designed for semiconductor technology management decision support. It covers:

- **14 Core node types**: Process, SubProcess, EquipmentClass, Equipment, Vendor, Organization,
  Parameter, Metrology, Material, TechnologyNode, FailureMode, RootCause, Mitigation, Skill
- **198+ nodes** and **264+ edges** with full provenance metadata
- **Governance layer**: BIS EAR/Entity List, NIST CSF 2.0/IR 8546, ECHA SCIP rules
- **Link-Only layer**: SEMI E10/E30/E40/E116 standard references (identifiers only, no paywalled content)

## Architecture

| Layer | Description | License |
|-------|-------------|---------|
| **Domain (Open Core)** | Process/equipment/material/FMEA knowledge graph | CDLA-Permissive-2.0 |
| **Governance (Open Core)** | Regulatory rules (BIS/NIST/ECHA) as structured nodes | CDLA-Permissive-2.0 |
| **Link-Only** | Paywalled standard references (SEMI/JEDEC/IRDS) — identifiers/URLs only | N/A (metadata only) |

## Dataset Structure

```
ontology/
  sdkb-core.ttl              # OWL ontology (14 Core + 7 Governance classes)
  sdkb-core-data.ttl          # All nodes/edges as RDF triples
  sdkb-core-data.jsonld       # Same data in JSON-LD format
  sdkb-governance.ttl         # BIS/NIST/ECHA governance nodes (TBD)
  sdkb-links-semi.ttl         # SEMI standard references (TBD)
data/
  nodes.parquet               # Flat node table
  edges.parquet               # Flat edge table
  schema_report.json          # Baseline structure & integrity report
  expert_profiles.parquet     # Synthetic expert profiles (100, TBD)
  problems.parquet            # Technical problems (50) + regulatory scenarios (25, TBD)
  ground_truth.parquet        # Cross-evaluation ratings (7,500, TBD)
mappings/
  semikong_alignment.tsv      # SemiKong process hierarchy mapping (TBD)
  semiconto_alignment.ttl     # SemicONTO schema alignment (TBD)
validation/
  shapes.ttl                  # SHACL shapes for release gate validation
provenance/
  prov.ttl                    # PROV-O provenance chain (agents/activities/sources)
examples/sparql/
  01_regulatory_risk.rq       # BIS ECCN → EAR rule query
  02_fmea_path.rq             # Failure → cause → mitigation path query
  03_tech_gap.rq              # Technology gap detection query
```

## Provenance & Quality

Every node and edge carries provenance metadata:
- **Source tracing**: `dcterms:source`, `dcterms:license`, `dcterms:bibliographicCitation`
- **Interpretation type**: `verbatim` (directly from source) | `mapped` (restructured) | `author-defined` (expert judgment)
- **Validation flag**: `sdkb:validationRequired` for items needing expert review
- **PROV-O chain**: `prov:wasGeneratedBy`, `prov:wasDerivedFrom`, `prov:wasAttributedTo`
- **SHACL validation**: All release artifacts must pass shapes.ttl before packaging

## Curation Sources

| Source | License | Integration |
|--------|---------|-------------|
| SemiKong (arXiv:2411.13802) | Apache 2.0 | Process hierarchy L1→L3 |
| SemicONTO (CEUR-WS Vol-3760) | CC BY 4.0 | Material/equipment OWL alignment |
| MatKG (Scientific Data 2024) | CC BY 4.0 | Material entity expansion |
| BIS CCL/EAR | Public Domain | Equipment ECCN classification |
| NIST CSF 2.0 / IR 8546 | Public Domain | Cybersecurity governance |
| ECHA SCIP | Public Access | SVHC material compliance |
| Wikidata | CC0 | Entity linking (owl:sameAs) |
| SEMI E10/E30/E40/E116 | Proprietary | Link-Only (identifiers) |

## Technology Foresight Framework

SDKB integrates the STEEPVE (Social, Technological, Economic, Environmental, Political, Values, Ethical)
framework for technology management decision support:

1. **Technology portfolio optimization**: Gap analysis between R&D capabilities and market demand
2. **Supply chain risk prediction**: Geopolitical scenario simulation via GraphRAG
3. **Expert matching**: Bilingual (KR/EN) synonym-aware search across process/material/failure domains
4. **Regulatory compliance**: Automated BIS §744.23 / ECHA SCIP rule checking

## Usage

```bash
# Install
pip install -e ".[dev]"

# Run full pipeline
make pipeline

# Individual steps
make parse      # Week 1: baseline parsing
make owl        # Week 2: OWL metamodel
make convert    # Week 3: RDF/JSON-LD conversion
make align      # Week 4: alignment candidates
make validate   # SHACL validation
make test       # Run test suite
```

## Limitations & Bias

- Based on publicly available documents and regulatory thresholds; does not include proprietary fab-specific process data
- FMEA causal relationships are literature-derived and require domain expert validation
- English-centric with Korean synonym support; other languages not covered
- Regulatory data reflects rules as of the data retrieval date; monthly update pipeline recommended

## Citation

```bibtex
@misc{sdkb2026,
  title   = {SDKB v1.0: Semiconductor Domain Knowledge Base},
  author  = {Park, HyoungSik},
  year    = {2026},
  note    = {SKKU MOT, Advisor: Prof. Shin Jun-seok},
  license = {CDLA-Permissive-2.0},
}
```

## License

CDLA-Permissive-2.0 (Open Core data). Link-Only layer excluded from redistribution.
See [LICENSE.txt](LICENSE.txt) for full terms.
