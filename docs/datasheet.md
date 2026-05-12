# SDKB Datasheet

> Gebru-style datasheet for the **whole SDKB** dataset (not just SIRP — the SIRP card is at [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md)).

## 1. Motivation

| Q | A |
|---|---|
| For what purpose was the dataset created? | To enable provenance-grounded, multi-axis decision-making in semiconductor technology management — expert matching, prior-art retrieval, novelty mapping, key-resource analysis, and foresight scenarios. |
| Who created it and on whose behalf? | Park HyoungSik (SKKU MOT 박사 19기), under the supervision of Prof. Shin Juneseuk (Quantitative MOT Lab). |
| Funding sources | SKKU Graduate School of MOT 현업프로젝트1 (2026-1). Aligned with the *글로벌첨단전략산업기술경영전문인력양성* program (2025-2030). |

## 2. Composition

| Q | A |
|---|---|
| What do instances represent? | Nodes in a curation knowledge graph — Process, SubProcess, EquipmentClass, Equipment, Vendor, Organization, Parameter, Metrology, Material, TechnologyNode, FailureMode, RootCause, Mitigation, Skill, plus alignment-track classes (Patent, IPCSymbol, Firm, Resource, Capability, RealOption, Scenario, …). |
| Total instances | 198 baseline nodes / 264 baseline edges (`data/semiconductor_v0_3.json`) + 773 rejected patents (SIRP, `data/patents/rejected_patents_meta.parquet`) + ancillary tables (experts, problems, scenarios, prior-art pairs). |
| Splits | Baseline graph has no train/test split (it's a curation graph). Prior-art pairs split is documented in `data/patents/pairs_report.json`. |
| Confidential or sensitive content? | Patent abstracts and first claims are sourced from KIPRIS — subject to KIPRIS Plus terms. License resolution is in-progress; see [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md) §6. Synthetic expert profiles are not personally identifiable. |

## 3. Collection process

| Q | A |
|---|---|
| How was data acquired? | (Domain core) Manual curation from public literature & standards. (Patent layer) KIPRIS Plus API + KIPRIS web for 773 records. (Synthetic profiles) Generated programmatically with `scripts/gen_experts.py` (to be added) using rejection-rate–calibrated archetypes. |
| Sampling strategy | (Domain) Comprehensive but explicitly biased toward etch/depo/lithography/CMP/oxidation/implant/packaging — the same axes as SemicONTO. (SIRP) Two cohorts: `semiconductor_ontology_rejected_patents` (431) + `semiconductor_fullstack_rejected_patents` (342). |
| Time frame | Baseline: curated 2026-04. SIRP: collected 2026-04 → 2026-05-06, covering patents filed 1997-12-31 → 2026-04-30. |
| Did the collection process involve crowdworkers, contractors, or third parties? | Patent data via KIPO/KIPRIS, regulatory data via BIS/NIST/ECHA public sources. No paid annotators this term; 7,500 labels come from KIPO examiner records, not crowd. |

## 4. Preprocessing / cleaning / labeling

- Baseline JSON → Parquet via `scripts/parse_baseline.py`
- JSONL SIRP → Parquet via `scripts/ingest_rejected_patents.py`
- Stratified problem sampling via `scripts/sample_problems.py`
- Prior-art pair generation (positive + hard-neg + easy-neg) via `scripts/build_prior_art_pairs.py`
- Date normalization (mixed KIPRIS formats → ISO)
- IPC parsing (pipe-separated → 4-digit & section)

## 5. Uses

### Intended uses
- AFCP-EM (Expert + PriorArt) evaluation and ablations
- Patent-analytics replication of Prof. Shin's TFSC family (novelty mapping, topic-based forecasting)
- RBV / fsQCA-style key-resource-combination analyses
- Multi-jurisdiction compliance teaching cases

### Out-of-scope / prohibited
- Re-identification of any individual or specific firm beyond what appears in public patent records.
- Commercial product training without an explicit KIPRIS license decision.

## 6. Distribution

| Q | A |
|---|---|
| Will the dataset be distributed publicly? | Yes — Open Core layer under CDLA-Permissive-2.0. SIRP layer pending KIPRIS license resolution. |
| When? | After amendment v2 sign-off + license resolution. Target: end of 2026-1 term. |
| DOI / mirror | Zenodo DOI to be minted at release. Optional HuggingFace Datasets mirror under the same license. |

## 7. Maintenance

| Q | A |
|---|---|
| Who is supporting / hosting / maintaining the dataset? | Park HyoungSik with advisor Shin Juneseuk. |
| Will the dataset be updated? | Yes — monthly regulatory refresh planned. SIRP cohort frozen for 2026-1 grading; expanded in 2026-2. |
| Erratum policy | Tracked in `CHANGELOG.md`. SHACL release-gate failures block any release. |
