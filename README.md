---
language:
  - en
  - ko
license: cdla-permissive-2.0
tags:
  - semiconductor
  - ontology
  - knowledge-graph
  - technology-management
  - patent-analytics
  - expert-matching
  - FMEA
  - provenance
task_categories:
  - graph-ml
size_categories:
  - 1K<n<10K
---

# SDKB v1.0 — Semiconductor Domain Knowledge Base

> **A reproducible semantic-graph substrate for quantitative technology management research in the semiconductor industry.**
> Maintained by the [Quantitative Technology Management Lab](#lab-context) at Sungkyunkwan University's Graduate School of Management of Technology (PI: Prof. Juneseuk Shin).
>
> 🇰🇷 한국어 버전: [README.ko.md](README.ko.md)
> 🔗 **Live demo (GitHub Pages):** [`arkwith7.github.io/semiconductor-knowledge-base`](https://arkwith7.github.io/semiconductor-knowledge-base/) — interactive 3-view explorer (baseline 198 nodes · SIRP top-50 + prior art · 4-pillar class skeleton)

## One-line positioning

SDKB unifies semiconductor **process / equipment / defect / skill** knowledge, **patent taxonomies** (CPC / IPC / F-term), **firm resources** (RBV), **multi-jurisdictional regulation** (US BIS · NIST · ECHA + Korea ITPA), and **standards** (SEMI / JEDEC) under a single PROV-O-tracked ontology. It is built as the shared substrate for the lab's four research lines — *tech foresight, opportunity discovery, SME innovation analysis, and interactive tech / business visualization* — and as the seed dataset for an upcoming dissertation on a **compliance-aware semantic collaboration platform**.

**First application — AFCP-EM** (*Agent-First Compliance Platform for Expert / PriorArt Matching*): two matching markets — Korean semiconductor SME ↔ expert, and patent application ↔ prior art — implemented on a single compliance-first architecture rather than as a post-hoc filter.

## Lab context

Prof. Shin's Quantitative Technology Management Lab combines patent / market / industry data with semantic modeling to support R&D planning, technology commercialization, and SME innovation. SDKB is the semiconductor-domain data substrate for that agenda:

| Lab research line | SDKB contribution | Entry point |
|---|---|---|
| Patent-/market-/industry-driven **tech foresight** | `sdkb-patent.ttl` + SIRP-773 + Topic / Novelty nodes | [Use case 1](#use-cases) |
| Promising-technology **opportunity discovery** | Novelty-focused patent mapping, emerging-memory topic clusters | [Use case 1](#use-cases), 🚧 [notebook 02](notebooks/02_patent_opportunity_demo.ipynb) |
| **SME innovation analysis / expert matching** | AFCP-EM Expert + synthetic-100 + curated-110 expert pool + multi-jurisdiction compliance gate | [Use case 2](#use-cases), 🚧 [notebook 01](notebooks/01_matching_baseline_afcp.ipynb), ✅ [notebook 05](notebooks/05_synthetic_vs_curated_comparison.ipynb) |
| **Interactive tech / business visualization** | Pyvis 3-view explorer with automatic GitHub Pages deploy | [Live demo](https://arkwith7.github.io/semiconductor-knowledge-base/), [docs/visualization_plan.md](docs/visualization_plan.md) |
| Organizational R&D / innovation design (secondary) | RBV core-resource combinations + TRL / real-option seed nodes | [Use case 4](#use-cases), 🚧 [notebook 03](notebooks/03_rbv_resource_combo_demo.ipynb) |

## Why / For / How

- **Why** — to make quantitative decisions in semiconductor technology (opportunity discovery, expert matching, core-resource combinations, technology valuation, multi-jurisdiction regulatory fit) **reproducible on a single semantic graph**.
- **For** — MOT researchers and graduate students worldwide; planning / IP / R&D staff at semiconductor materials-parts-equipment SMEs; patent attorneys and IP-R&D consultants; technology policy analysts.
- **How** — process / equipment / defect / skill knowledge + patents (CPC / IPC / F-term) + firm resources (RBV) + regulation (BIS / NIST / ECHA + Korea ITPA) + standards (SEMI / JEDEC) tied together with PROV-O provenance, then instantiated by application notebooks aligned to each lab research line.

## Use cases

Each use case instantiates a lab research line on SDKB's shared graph.

> **Notebook status legend** — ✅ shipped & runnable · 🚧 skeleton stub (data loads work; algorithm cells raise `NotImplementedError`, scheduled for 2026-1) · _(…)_ later-term placeholder.

| # | Use case | Lab line | Modules | Notebook | Reference |
|---|---|---|---|---|---|
| 1 | **Novelty-focused patent mapping** — semiconductor technology-opportunity clusters | Opportunity discovery / foresight | core + patent + SIRP | 🚧 [02](notebooks/02_patent_opportunity_demo.ipynb) | Lee/Kang/Shin (TFSC 2015), Shin et al. (TFSC 2017) |
| 2 | **AFCP-EM (Expert)** — Korean semiconductor SME ↔ expert semantic matching with multi-jurisdiction leakage gating | SME innovation / expert matching | core + governance + governance-kr | ✅ [01](notebooks/01_matching_baseline_afcp.ipynb) (matching) · ✅ [05](notebooks/05_synthetic_vs_curated_comparison.ipynb) (GT validity) | — |
| 3 | **AFCP-EM (PriorArt)** — patent application ↔ prior art using examiner-cited ground truth | IP-R&D consulting / prior-art analysis | core + patent + SIRP | ✅ [04](notebooks/04_prior_art_baseline.ipynb) | PatentMatch, CLEF-IP family |
| 4 | **Key resource combinations** — semiconductor fabless market-entry analysis | Organizational R&D / core-resource analysis | core + rbv | 🚧 [03](notebooks/03_rbv_resource_combo_demo.ipynb) (data pending — alignment track) | Cho/Shin (PLoS ONE 2025), Bae/Shin (IEEE Access 2022) |
| 5 | **Compound real options** — EUV vs. High-NA roadmap valuation | Technology valuation (later term) | core + foresight + commercialization | _(2026-2 planned)_ | Lab real-options line |
| 6 | **Interactive KG explorer** — 3-view (baseline / SIRP / 4-pillar) GitHub Pages deploy | Interactive visualization | core + patent + rbv + foresight + commercialization | ✅ [Live](https://arkwith7.github.io/semiconductor-knowledge-base/) · `scripts/build_viz.py` | Lab visualization track |

Detailed 4-pillar mapping: [docs/research_alignment.md](docs/research_alignment.md).

## Architecture

| Layer | Module | License |
|---|---|---|
| **Core (Open)** | 14-type process KG, FMEA | CDLA-Permissive-2.0 |
| **Governance (Open)** | US BIS / NIST / ECHA + Korea ITPA | CDLA-Permissive-2.0 |
| **Alignment (Open)** | patent / rbv / commercialization / foresight | CDLA-Permissive-2.0 |
| **Link-Only** | SEMI E10 / E30 / E40 / E116 (identifiers only) | N/A (metadata) |

```
ontology/
  sdkb-core.ttl                     # 14 core classes
  sdkb-governance.ttl               # BIS / NIST / ECHA
  sdkb-governance-kr.ttl            # Korea ITPA
  sdkb-patent.ttl                   # patent taxonomy (CPC / IPC / F-term / Topic / Novelty)
  sdkb-rbv.ttl                      # firm / resource / capability
  sdkb-commercialization.ttl        # TRL / license / spinoff
  sdkb-foresight.ttl                # scenario / STEEPVE / real option
data/
  semiconductor_v0_3.json           # baseline 198 nodes / 268 edges
  expert_profiles.parquet           # 100 synthetic profiles
  experts/curated_profiles.parquet  # 110 curated profiles
  problems.parquet                  # 50 technology problems
  regulatory_scenarios.parquet      # 25 adversarial scenarios
  patents/raw/                      # SIRP-773 raw JSONL + parquet
  patents/prior_art_pairs.parquet   # 7,500 examiner-grounded pairs
  compliance/                       # KR + US governance masters
docs/
  research_alignment.md             # 4-pillar mapping
  afcp_em_architecture.md           # system overview
  leakage_protocol.md               # leakage definition and measurement
  datasheet.md                      # data sheet (Gebru et al.)
  commercialization_strategy_v1.md
  visualization_plan.md
  project_status_2026_1.md          # lab-internal status — 2026-1 deliverables
validation/shapes.ttl               # SHACL
provenance/prov.ttl                 # PROV-O chain
examples/sparql/                    # example queries
notebooks/
  01_matching_baseline_afcp.ipynb    # ✅ Use Case 2 (AFCP-EM Expert floor baseline)
  02_patent_opportunity_demo.ipynb   # 🚧 Use Case 1 (novelty-focused mapping)
  03_rbv_resource_combo_demo.ipynb   # 🚧 Use Case 4 (RBV — data pending)
  04_prior_art_baseline.ipynb        # ✅ Use Case 3 (AFCP-EM PriorArt baseline)
  05_synthetic_vs_curated_comparison.ipynb  # ✅ GT validity diagnostics for UC2
CITATION.cff                        # advisor explicit
```

## Provenance and auditability

AFCP-EM's *architectural* regulatory compliance (not a post-hoc filter) and full auditability are carried by:

- `dcterms:source` / `dcterms:license` / `dcterms:bibliographicCitation` — source tracking
- `sdkb:interpretationType` — `verbatim` | `mapped` | `author-defined`
- `sdkb:validationRequired` — expert-verification flag
- PROV-O — `prov:wasGeneratedBy` / `prov:wasDerivedFrom` / `prov:wasAttributedTo`
- SHACL — every release must pass `shapes.ttl`
- Leakage protocol — [docs/leakage_protocol.md](docs/leakage_protocol.md)

## Curation sources

| Source | License | Integration |
|---|---|---|
| SemiKong (arXiv:2411.13802) | Apache 2.0 | Process hierarchy L1 → L3 |
| SemicONTO (CEUR-WS Vol-3760) | CC BY 4.0 | Material / equipment OWL alignment |
| MatKG (Scientific Data 2024) | CC BY 4.0 | Material entity expansion |
| USPTO / EPO / KIPO | Public | CPC / IPC classification (metadata only) |
| BIS CCL / EAR | Public | Equipment ECCN |
| NIST CSF 2.0 / IR 8546 | Public | Cyber governance |
| ECHA SCIP | Public | SVHC material compliance |
| Korea Industrial Technology Protection Act | Public | National core technology designation |
| Wikidata | CC0 | Entity linking |
| SEMI E10 / E30 / E40 / E116 | Proprietary | Link-Only (identifiers) |

## Usage

### Setup (once)
```bash
make venv                           # Python 3.11 venv + dependencies
source .venv/bin/activate           # or: PATH=.venv/bin:$PATH
```

### Full pipeline
```bash
make pipeline-with-expdataset       # baseline + SIRP + experts + curated ExpDataSet (everything)
make pipeline-full                  # baseline + SIRP + experts (without ExpDataSet)
```

### Individual targets
```bash
make parse           # baseline parsing
make owl             # OWL metamodel (sdkb-core.ttl)
make convert         # JSON → RDF / JSON-LD
make align           # alignment candidates
make validate        # SHACL validation
make test            # pytest (baseline + patents)
make ingest-sirp     # SIRP JSONL → parquet
make sirp-pairs      # 7,500 prior-art pairs
make sirp-problems   # 50 problems + 25 scenarios
make experts         # 100 synthetic experts
make compliance      # KR + US governance instances (205 triples)
make curated-experts # 110-profile curated pool
make curated-ratings # 7,800 3-rater ratings + κ / ICC report
make expdataset      # compliance + curated-experts + curated-ratings
make help            # list all targets
```

### Interactive visualization (GitHub Pages)
```bash
make viz       # build baseline / SIRP / 4-pillar HTML into site/
make viz-open  # build + open site/index.html in the default browser
```
- `site/` is gitignored and rebuilt by [.github/workflows/viz-deploy.yml](.github/workflows/viz-deploy.yml) on every push to `main`
- One-time setup: repository **Settings → Pages → Source: GitHub Actions**
- Details: [docs/visualization_plan.md](docs/visualization_plan.md)

### Verified release figures
- Baseline **198 nodes / 268 edges** (v0.3)
- SIRP 773 patents · 3,118 IPC links · 4,696 prior-art edges
- 7,500 examiner-grounded pairs (positive 2,723 + hard-negative 2,723 + easy-negative 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts (dual-track pool)
- 7,500 examiner-grounded + 7,800 3-rater synthetic ratings (dual-track GT; Fleiss κ = 0.258, ICC(2,1) = 0.552)
- KR + US governance: 20 controls / 205 RDF triples
- 46 / 46 tests pass · SHACL VALIDATION PASSED

## Limitations and bias

- Built on public documents and regulatory thresholds — fab-private process data is out of scope.
- FMEA causal links are literature-derived and require domain-expert validation.
- English-centric with Korean synonym augmentation; other languages are not yet supported.
- Regulatory data reflects retrieval-time snapshots; a monthly refresh pipeline is recommended.
- Synthetic expert profiles and ratings are de-identified synthetic data with no relationship to real persons or firms.

## Citation and acknowledgement

SDKB is a semiconductor-domain output of the **Quantitative Technology Management Lab** (PI: Prof. Juneseuk Shin) at SKKU's Graduate School of Management of Technology, contributing to its research agenda — tech foresight, opportunity discovery, SME innovation analysis, and interactive tech / business visualization. The forthcoming dissertation "Compliance-aware Semantic Collaboration Platform" and related journal papers will cite this dataset as an empirical artifact; the BibTeX below will be updated at that point.

```bibtex
@dataset{sdkb_v1_2026,
  title       = {SDKB v1.0: Semiconductor Domain Knowledge Base —
                 a data trunk for the Quantitative Technology Management
                 Lab's foresight, opportunity-discovery, SME-matching,
                 and interactive-visualization research agenda},
  author      = {Park, HyoungSik},
  advisor     = {Shin, Juneseuk},
  institution = {Sungkyunkwan University, Graduate School of
                 Management of Technology,
                 Quantitative Technology Management Lab},
  year        = {2026},
  version     = {1.0},
  url         = {https://github.com/arkwith7/semiconductor-knowledge-base},
  license     = {CDLA-Permissive-2.0},
  note        = {Hyeonup-Project 2026-1 deliverable; seed dataset for
                 the forthcoming compliance-aware semantic collaboration
                 platform dissertation.}
}
```

## License

CDLA-Permissive-2.0 (Open Core). The Link-Only layer is not redistributed.
See [LICENSE.txt](LICENSE.txt).

---

*Hyeonup-Project 2026-1 lab-internal status — deliverables, alignment-track ontologies, ExpDataSet integration, and amendment trail: [docs/project_status_2026_1.md](docs/project_status_2026_1.md).*
