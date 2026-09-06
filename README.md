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

# SDKB — Semiconductor Domain Knowledge Base

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22030395.svg)](https://doi.org/10.5281/zenodo.22030395)

> **A reproducible semantic-graph substrate for quantitative technology management research in the semiconductor industry.**
> Maintained by the [Quantitative Technology Management Lab](#lab-context) at Sungkyunkwan University's Graduate School of Management of Technology (PI: Prof. Juneseuk Shin).
>
> 🇰🇷 한국어 버전: [README.ko.md](README.ko.md)
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
> 🔗 **Live demo (GitHub Pages):** [`arkwith7.github.io/sdkb-dataset`](https://arkwith7.github.io/sdkb-dataset/) — interactive 3-view explorer (curation graph · SIRP top-50 + prior art · 4-pillar class skeleton)
<!-- sdkb:private-end -->


> **Two doors.**
> **Using the dataset** — T-Box, SHACL shapes, competency questions, mappings: run `uv sync` and
> start below. Nothing in `benchmark/` is needed.
> **Reproducing the paper's evaluation** — retrieval systems, release-gate conditions, frozen
> evaluation assets: see [`benchmark/README.md`](benchmark/README.md) and run
> `uv sync --extra benchmark`.

## One-line positioning

SDKB unifies semiconductor **process / equipment / defect / skill** knowledge, **patent taxonomies** (CPC / IPC / F-term), **firm resources** (RBV), **multi-jurisdictional regulation** (US BIS · NIST · ECHA + Korea ITPA), and **standards** (SEMI / JEDEC) under a single PROV-O-tracked ontology. It is built as the shared substrate for the lab's four research lines — *tech foresight, opportunity discovery, SME innovation analysis, and interactive tech / business visualization* — and as the seed dataset for an upcoming dissertation on a **compliance-aware semantic collaboration platform**.

**First application — SDKB-Match** (*SDKB Matching Layer — Korean semiconductor SME ↔ expert and patent application ↔ prior-art matching*): two matching markets implemented on a single compliance-first architecture rather than as a post-hoc filter.

## Glossary

Full names and meanings of acronyms used throughout this repository.

| Acronym | Full name / meaning |
|---|---|
| **SDKB** | Semiconductor Domain Knowledge Base — this dataset / ontology trunk |
| **SDKB-Match** | SDKB Matching Layer — the matching application built on SDKB: Korean semiconductor SME ↔ expert matching and patent ↔ prior-art matching on a single compliance-first architecture (not a post-hoc filter). Sub-tracks: **SDKB-Match Expert** / **SDKB-Match PriorArt** |
| **SIRP** | Semiconductor Industry Rejected Patents — 1,000-patent rejected-patent dataset (initial cohort snapshot was 773; GT pairs frozen at the 773-snapshot) |
| **SME (소부장)** | Small/medium enterprise; here semiconductor materials-parts-equipment firms |
| **RBV** | Resource-Based View of the firm |
| **FMEA** | Failure Mode and Effects Analysis |
| **IPC / CPC / F-term** | International / Cooperative Patent Classification / File-forming term |
| **GT** | Ground Truth (examiner-grounded = patent-office examiner citations) |
| **MRR / NDCG@K / Recall@K** | Mean Reciprocal Rank / Normalized Discounted Cumulative Gain@K / Recall@K — retrieval metrics |
| **κ / ICC** | Weighted Cohen's κ / Intraclass Correlation Coefficient — label-reliability metrics |
| **IP-R&D** | Intellectual-Property-driven R&D / consulting |
| **SHACL** | Shapes Constraint Language — RDF graph constraint validation |
| **PROV-O** | W3C Provenance Ontology |
| **KG / OWL / RDFS / TTL** | Knowledge Graph / Web Ontology Language / RDF Schema / Turtle serialization |
| **BIS / NIST / ECHA / ITPA** | US Bureau of Industry and Security / US National Institute of Standards and Technology / European Chemicals Agency / Korea Industrial Technology Protection Act — multi-jurisdiction regulatory sources |
| **SEMI / JEDEC** | Semiconductor standards bodies (SEMI International Standards / JEDEC Solid State Technology Association) |
| **KIPRIS** | Korea Intellectual Property Rights Information Service |
| **TFSC** | *Technological Forecasting & Social Change* (journal) |
| **CLEF-IP / PatentMatch** | Prior-art retrieval evaluation benchmarks (protocol references) |
| **MOT** | Management of Technology |
| **A2 / A6** | Prior-art ontology-gap plan task IDs (A2 = new device/product layer; A6 = IDF-weighted concept ranking) |

## Lab context

Prof. Shin's Quantitative Technology Management Lab combines patent / market / industry data with semantic modeling to support R&D planning, technology commercialization, and SME innovation. SDKB is the semiconductor-domain data substrate for that agenda:

| Lab research line | SDKB contribution | Entry point |
|---|---|---|
| Patent-/market-/industry-driven **tech foresight** | `sdkb-patent.ttl` + SIRP + Topic / Novelty nodes | [Use case 1](#use-cases) |
| Promising-technology **opportunity discovery** | Novelty-focused patent mapping, emerging-memory topic clusters | [Use case 1](#use-cases), 🚧 [notebook 02](notebooks/02_patent_opportunity_demo.ipynb) |
| **SME innovation analysis / expert matching** | SDKB-Match Expert + synthetic-100 + curated-110 expert pool + multi-jurisdiction compliance gate | [Use case 2](#use-cases), 🚧 [notebook 01](notebooks/01_matching_baseline_expert.ipynb), ✅ [notebook 05](notebooks/05_synthetic_vs_curated_comparison.ipynb) |
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
| **Interactive tech / business visualization** | Pyvis 3-view explorer with automatic GitHub Pages deploy | [Live demo](https://arkwith7.github.io/sdkb-dataset/), [docs/project/visualization_plan.md](docs/project/visualization_plan.md) |
<!-- sdkb:private-end -->

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
| 2 | **SDKB-Match (Expert)** — Korean semiconductor SME ↔ expert semantic matching with multi-jurisdiction leakage gating | SME innovation / expert matching | core + governance + governance-kr | ✅ [01](notebooks/01_matching_baseline_expert.ipynb) (matching) · ✅ [05](notebooks/05_synthetic_vs_curated_comparison.ipynb) (GT validity) | — |
| 3 | **SDKB-Match (PriorArt)** — patent application ↔ prior art using examiner-cited ground truth | IP-R&D consulting / prior-art analysis | core + patent + SIRP | ✅ [04](notebooks/04_prior_art_baseline.ipynb) | PatentMatch, CLEF-IP family |
| 4 | **Key resource combinations** — semiconductor fabless market-entry analysis | Organizational R&D / core-resource analysis | core + rbv | 🚧 [03](notebooks/03_rbv_resource_combo_demo.ipynb) (data pending — alignment track) | Cho/Shin (PLoS ONE 2025), Bae/Shin (IEEE Access 2022) |
| 5 | **Compound real options** — EUV vs. High-NA roadmap valuation | Technology valuation (later term) | core + foresight + commercialization | _(2026-2 planned)_ | Lab real-options line |
<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
| 6 | **Interactive KG explorer** — 3-view (baseline / SIRP / 4-pillar) GitHub Pages deploy | Interactive visualization | core + patent + rbv + foresight + commercialization | ✅ [Live](https://arkwith7.github.io/sdkb-dataset/) · `scripts/build_viz.py` | Lab visualization track |
<!-- sdkb:private-end -->


Detailed 4-pillar mapping: [docs/project/research_alignment.md](docs/project/research_alignment.md).

## Architecture

| Layer | Module | License |
|---|---|---|
| **Core (Open)** | process / equipment / material / FMEA core KG | CDLA-Permissive-2.0 |
| **Governance (Open)** | US BIS / NIST / ECHA + Korea ITPA | CDLA-Permissive-2.0 |
| **Alignment (Open)** | patent / rbv / commercialization / foresight | CDLA-Permissive-2.0 |
| **Link-Only** | SEMI E10 / E30 / E40 / E116 (identifiers only) | N/A (metadata) |

```
ontology/
  sdkb-core.ttl                     # core vocabulary — counts under "Release signature"
  sdkb-governance.ttl               # BIS / NIST / ECHA
  sdkb-governance-kr.ttl            # Korea ITPA
  sdkb-patent.ttl                   # patent taxonomy (CPC / IPC / F-term / Topic / Novelty)
  sdkb-rbv.ttl                      # firm / resource / capability
  sdkb-commercialization.ttl        # TRL / license / spinoff
  sdkb-foresight.ttl                # scenario / STEEPVE / real option
data/
  semiconductor_v0_3.json           # hand-curated source graph — counts under "Release signature"
  expert_profiles.parquet           # 100 synthetic profiles
  experts/curated_profiles.parquet  # 110 curated profiles
  problems.parquet                  # 50 technology problems
  regulatory_scenarios.parquet      # 25 adversarial scenarios
  patents/raw/                      # SIRP raw JSONL (1,000 records) + parquet
  patents/prior_art_pairs.parquet   # 7,500 examiner-grounded pairs
  compliance/                       # KR + US governance masters
docs/
  README.md                         # documentation index — start here
  ontology_guide.md                 # vocabulary, modelling decisions, extension recipes
  glossary_ontology.md              # RDF/OWL/SHACL terms, with the defects they caused here
  glossary_semiconductor.md         # the semiconductor domain this ontology models
  datasheet.md                      # data sheet (Gebru et al.) — whole SDKB
  dataset_rejected_patents_card.md  # SIRP dataset card
  leakage_protocol.md               # leakage definition and measurement
  public_release_readiness_review.md # what this repo still gets wrong (measured)
  semiconductor_ontology_provenance_research.md  # source / provenance landscape
  references/                       # BibTeX library + per-paper notes
  project/                          # architecture, alignment and visualization docs
validation/shapes.ttl               # SHACL
provenance/prov.ttl                 # PROV-O chain
examples/sparql/                    # example queries
<!-- 공개본에서 뺀다: 노트북은 공개본에 없다 -->
<!-- sdkb:private-begin -->
notebooks/
  01_matching_baseline_expert.ipynb  # ✅ Use Case 2 (SDKB-Match Expert floor baseline)
  02_patent_opportunity_demo.ipynb   # 🚧 Use Case 1 (novelty-focused mapping)
  03_rbv_resource_combo_demo.ipynb   # 🚧 Use Case 4 (RBV — data pending)
  04_prior_art_baseline.ipynb        # ✅ Use Case 3 (SDKB-Match PriorArt baseline)
  05_synthetic_vs_curated_comparison.ipynb  # ✅ GT validity diagnostics for UC2
<!-- sdkb:private-end -->

CITATION.cff                        # advisor explicit
```

## Provenance and auditability

SDKB-Match's *architectural* regulatory compliance (not a post-hoc filter) and full auditability are carried by:

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

## What is empty, and how to fill it

This repository ships **generators, not instances**. The T-Box, the vocabularies, the SHACL
shapes, the competency-question suite and every build script are here; the large A-Box layers
built from KIPRIS patent text are **not**, because KIPRIS terms permit academic use but not
redistribution of full text.

**This is the design, not a gap.** A public checkout plus your own KIPRIS key reconstructs the
graph the paper cites. What follows says exactly what is missing, why, and which command fills it.

| Layer | What is empty | Why | Command to fill | Credentials needed |
|---|---|---|---|---|
| **T-Box** (`ontology/sdkb-core.ttl`) | nothing — **the file is committed** (2026-08-15) | it is also a build artifact: `data/semiconductor_v0_3.json` (392 KB) regenerates it **byte-identically** | `make owl && make convert` | none |
| **SIRP patent A-Box** (`ontology/sdkb-abox-patents.ttl`) | abstracts and claim text | KIPRIS full text is not redistributable | `make refetch-fulltext && make abox-patents` | KIPRIS OpenAPI key |
| **Rejected-patent dataset** (`data/patents/raw/…rejected_patents.jsonl`) | `abstract`, `claim1`, `claims_full[].text` are present as **empty strings** — the schema, the identifiers, the IPC/date metadata and the `ground_truth_*` citation labels are all intact | same | `python scripts/refetch_rejected_patents.py` (verifies the restored file against a published sha256) | KIPRIS OpenAPI key |
| **Cited prior-art A-Box** (`ontology/sdkb-abox-prior-art.ttl`, 21 MB) | the whole file | built from collected full text | `make refetch-fulltext && make abox-prior-art` | KIPRIS key (+ BigQuery for non-KR documents) |
| **Claim-feature A-Box** (`ontology/sdkb-abox-claim-features.ttl`, 899 MB) | the whole file | derived from claim text; too large to distribute regardless of licence | `make abox-claim-features` | KIPRIS key; several hours |
| **Governance instances** (`ontology/sdkb-governance-*-instances.ttl`) | nothing — **committed** (2026-08-15) | build artifacts of committed sources; regenerate byte-identically | `make compliance` | none |
| **Expert profiles and ratings** | nothing | committed — they are **synthetic**, generated for method evaluation, and contain no personal data | `make expdataset` | none |

Everything with "none" in the last column reproduces from an empty checkout. Everything else
needs your own key: we can give you the procedure, not the licensed text.

**Build the patent A-Box before the vendor A-Box.** `build_abox_vendors_ksia.py` matches KSIA
members against organisation nodes that already exist in the graph, and most of those nodes come
from patent applicants. Run it first and 31 matches drop to 2, producing different IRI slugs
(`organization/asendia_co_ltd` instead of `organization/asendia`) — the file still builds, it just
will not match the published one. `make pipeline-full` already orders this correctly.

**Measured reproduction (2026-08-15).** From a clean clone of this repository:

| | Out of the box | After `refetch-fulltext` with your own key |
|---|---|---|
| Competency questions | **14/31 = 0.452** (`pa` 1/8) | **27/31 = 0.871** — `em`, `tf`, `core` all 1.000 |
| Patent A-Box | not buildable | **33,934 triples** vs 33,931 in the paper's snapshot (**0.009 %**) |

The 0.009 % gap comes from where the abstract is read: the original collector preferred the search
response's `astrtCont` and the restore script queries bibliographic data only. The four questions
that never recover (CQ27, CQ29–31) all need the claim-feature layer, whose decomposition input is
the claim text itself — that layer cannot be published, and re-collecting it does not reproduce
byte-for-byte because the decomposition uses a language model.

### Competency questions

```bash
make cq      # run queries/cq/*.rq → data/reports/cq_report.json
```

The 31 questions carry their own metadata (`# suite:` — `pa` prior-art, `em` expert matching,
`tf` technology foresight, `core`). Suites that depend on an unbuilt A-Box report **0 rows and
fail**; the report's `graph_files_missing` names the files, so a failure tells you what to build
rather than that the ontology is broken.

<!-- 공개본에서 뺀다: 시각화·Pages 는 공개본에 없다 -->
<!-- sdkb:private-begin -->
### Interactive visualization (GitHub Pages)
```bash
make viz       # build baseline / SIRP / 4-pillar HTML into site/
make viz-open  # build + open site/index.html in the default browser
```
- `site/` is gitignored and rebuilt by [.github/workflows/viz-deploy.yml](.github/workflows/viz-deploy.yml) on every push to `main`
- One-time setup: repository **Settings → Pages → Source: GitHub Actions**
- Details: [docs/project/visualization_plan.md](docs/project/visualization_plan.md)
<!-- sdkb:private-end -->


### Release signature

Generated by `make signature` — **do not edit the block below by hand.**
The source of truth is [`data/reports/graph_signature.json`](data/reports/graph_signature.json).
(The curation graph grew past the 2026-05-17 snapshot of 229/268; hand-maintained
figures drifted, which is why this block is generated.)

<!-- sdkb:signature:begin -->
<!-- 이 블록은 `make signature-inject` 가 씁니다. 손으로 고치지 마세요 —
     data/reports/graph_signature.json 이 원천입니다. -->

**T-Box (vocabulary).** Named classes are counted separately from restriction
blank nodes: `grep -c owl:Class` counts both and reports a larger number.

| Module | Classes (named) | (blank) | ObjectProperty | DatatypeProperty | `rdfs:comment` | Triples |
|---|---|---|---|---|---|---|
| `sdkb-core.ttl` | 43 | 13 | 45 | 45 | 133/133 | 719 |
| `sdkb-patent.ttl` | 16 | 6 | 32 | 26 | 74/74 | 465 |
| `sdkb-rbv.ttl` | 9 | 0 | 6 | 3 | 18/18 | 82 |
| `sdkb-foresight.ttl` | 6 | 0 | 6 | 4 | 16/16 | 107 |
| `sdkb-commercialization.ttl` | 7 | 0 | 6 | 4 | 17/17 | 104 |
| `sdkb-governance.ttl` | 0 | 0 | 2 | 1 | 3/3 | 40 |
| `sdkb-governance-kr.ttl` | 3 | 0 | 2 | 2 | 7/7 | 60 |
| **Total** | **84** | 19 | **99** | **85** | **268/268** | 1,577 |

**Curation graph** (`data/semiconductor_v0_3.json` — the hand-curated source the core A-Box is generated from).

- **274 nodes / 312 edges** across **15 node types** (version `0.3`)

**A-Box layers.** `not built` is the expected state on a fresh checkout — these layers are generated, and the large ones need a KIPRIS key. See *What is empty, and how to fill it*.

| Layer | Content | Triples |
|---|---|---|
| `sdkb-core-data.ttl` | curation graph, instantiated | 2,884 |
| `sdkb-abox-patents.ttl` | SIRP rejected patents | 34,117 |
| `sdkb-abox-prior-art.ttl` | examiner-cited prior art | 67,123 |
| `sdkb-abox-claim-features.ttl` | claim features | 11,871,397 ¹ |
| `sdkb-abox-b-layer-queries.ttl` | B-layer confirmation queries | 4,631 |
| `sdkb-abox-experts-problems.ttl` | experts and problems | 8,483 |
| `sdkb-abox-vendors.ttl` | equipment vendors | 2,601 |
| `sdkb-governance-kr-instances.ttl` | Korea regulatory instances | 175 |
| `sdkb-governance-us-instances.ttl` | US export-control instances | 105 |

¹ counted by the generator that emitted the layer (`data/reports/`) rather than re-parsed here — the file is too large to re-parse on every signature run. Use `--parse-large` to re-count.

<!-- sdkb:signature:end -->

Other frozen counts (not covered by the signature above):
- SIRP **1,000 patents** (GT pairs frozen at the 773-cohort snapshot) · 3,118 IPC links · 4,696 prior-art edges
- 7,500 examiner-grounded pairs (positive 2,723 + hard-negative 2,723 + easy-negative 2,054)
- 50 stratified problems · 25 adversarial scenarios (all anchored)
- 100 synthetic experts + 110 curated experts (dual-track pool)
- 7,500 examiner-grounded (objective KIPO citations) + 7,800 algorithmically-simulated 3-rater synthetic ratings — **not human-expert annotation** (dual-track GT). 3-rater reliability: weighted κ = 0.550 / ICC(2,k) = 0.787 (consensus); transparency: Fleiss κ = 0.258 / ICC(2,1) = 0.552 — see [data/experts/reliability_report.md](data/experts/reliability_report.md)
- KR + US governance: 20 controls / 205 RDF triples
- SHACL validation passes; run `make test` for the current test tally (the previously
  hand-written "75 passed / 10 skipped · OWL 438 triples" had gone stale)

## Limitations and bias

- Built on public documents and regulatory thresholds — fab-private process data is out of scope.
- FMEA causal links are literature-derived and require domain-expert validation.
- English-centric with Korean synonym augmentation; other languages are not yet supported.
- Regulatory data reflects retrieval-time snapshots; a monthly refresh pipeline is recommended.
- Synthetic expert profiles and ratings are de-identified synthetic data with no relationship to real persons or firms.

## Citation and acknowledgement

SDKB is a semiconductor-domain output of the **Quantitative Technology Management Lab** (PI: Prof. Juneseuk Shin) at SKKU's Graduate School of Management of Technology, contributing to its research agenda — tech foresight, opportunity discovery, SME innovation analysis, and interactive tech / business visualization. The forthcoming dissertation "Compliance-aware Semantic Collaboration Platform" and related journal papers will cite this dataset as an empirical artifact; the BibTeX below will be updated at that point.

```bibtex
@dataset{sdkb_2026,
  title     = {SDKB: Semiconductor Domain Knowledge Base},
  author    = {Park, HyoungSik},
  year      = {2026},
  publisher = {Zenodo},
  version   = {1.1.1},
  doi       = {10.5281/zenodo.22030395},
  url       = {https://doi.org/10.5281/zenodo.22030395},
  note      = {Concept DOI — resolves to the latest version.
               The release reported in the prior-art paper is
               tag v1.1.1-paper; its version DOI is listed on
               the concept record.}
}
```

Two kinds of DOI are minted, and they are not interchangeable. Cite the **concept DOI**
([10.5281/zenodo.22030395](https://doi.org/10.5281/zenodo.22030395)) when you mean the dataset; cite the
**version DOI** of a specific release when you need the exact state some result was computed on.
Every version DOI is listed on the concept record, and each one names the tag it was cut from.
This file does not hardcode a version DOI: the number is minted when the release is published, so a
tagged tree can only ever state the *previous* one — which is exactly how `v1.1-paper` came to call
itself `SDKB v1.0` and carry no DOI at all.

## License

This repository carries two licenses, because it carries two kinds of thing.

| Path | License | File |
|---|---|---|
| `ontology/` `data/` `mappings/` `validation/` `queries/` `provenance/` | CDLA-Permissive-2.0 | [LICENSE.txt](LICENSE.txt) |
| `scripts/` `config/` `benchmark/src/` `Makefile` `pyproject.toml` | Apache-2.0 | [LICENSE-CODE.txt](LICENSE-CODE.txt) |
| `docs/` `README*` | CC-BY-4.0 | — |

CDLA is a data licence, so it never covered the generators; stating the code licence separately
removes an ambiguity that predates the harness. The Link-Only layer is not redistributed.

---

*New here? Start at [docs/README.md](docs/README.md). To understand or extend the ontology itself: [docs/ontology_guide.md](docs/ontology_guide.md).*
