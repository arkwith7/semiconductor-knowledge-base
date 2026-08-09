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
| Total instances | **Verified snapshot 2026-05-17**: curation graph **229 nodes / 268 edges** (`data/semiconductor_v0_3.json`; baseline origin was 198/264, expanded by curation incl. Device) + **1,000** SIRP rejected patents (`data/patents/raw/semiconductor_industry_rejected_patents.jsonl`; the "773" in older docs was an initial cohort snapshot) + ancillary tables (expert profiles 100 EN + 110 KR — 105 generated + 5 de-identified derivatives, see [`deidentification_protocol.md`](deidentification_protocol.md); problems 226; scenarios; prior-art pairs). ⚠️ The committed source has grown since this snapshot; rebuild and count rather than quoting these figures — see [`public_release_readiness_review.md`](public_release_readiness_review.md) F5. |
| Splits | Baseline graph has no train/test split (it's a curation graph). Prior-art pairs split is documented in `data/patents/pairs_report.json`. |
| Confidential or sensitive content? | Patent abstracts and first claims are sourced from KIPRIS — subject to KIPRIS Plus terms. License resolution is in-progress; see [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md) §6. Expert profiles are not personally identifiable: 105 of 110 are programmatically generated, and the remaining 5 (EXP_001–005) are **de-identified, perturbed derivatives** of real practitioner career records — pseudonymous names, rewritten employment/experience values, no contact or birth data, and the original documents were never ingested into this repository. Procedure: [`deidentification_protocol.md`](deidentification_protocol.md). |

## 3. Collection process

| Q | A |
|---|---|
| How was data acquired? | (Domain core) Manual curation from public literature & standards. (Patent layer) KIPRIS Plus API + KIPRIS web for 773 records. (Expert profiles) 105 generated programmatically with `scripts/gen_experts.py` using rejection-rate–calibrated archetypes; 5 (EXP_001–005) de-identified and perturbed from real practitioner career records — originals not ingested. (Problem profiles) 61 initial curation + 15 export-control and 10 ontology-reasoning scenarios + 18 rewritten from public cases (WM-811K, TEMAZ, technical blogs, literature) + 122 structure-derived generated. Both procedures: [`deidentification_protocol.md`](deidentification_protocol.md). |
| Sampling strategy | (Domain) Comprehensive but explicitly biased toward etch/depo/lithography/CMP/oxidation/implant/packaging — the same axes as SemicONTO. (SIRP) Two cohorts: `semiconductor_ontology_rejected_patents` (431) + `semiconductor_fullstack_rejected_patents` (342). |
| Time frame | Baseline: curated 2026-04. SIRP: collected 2026-04 → 2026-05-06, covering patents filed 1997-12-31 → 2026-04-30. |
| Did the collection process involve crowdworkers, contractors, or third parties? | Patent data via KIPO/KIPRIS, regulatory data via BIS/NIST/ECHA public sources. **No human annotators.** Two GT tracks must not be conflated: (a) **primary** = `prior_art_pairs.parquet` 7,500 pairs, **examiner-grounded** (objective KIPO examiner citations), not crowd, not expert annotation; (b) **secondary** = `curated_ratings_3rater.csv` 7,800, **algorithmically simulated 3-rater synthetic labels** (NOT human experts). Domain experts advised on profile *design* only — they did **not** produce the 7,500/7,800 ratings. Any paper using this data MUST NOT describe either track as "expert annotation". |

## 4. Preprocessing / cleaning / labeling

- Baseline JSON → Parquet via `scripts/parse_baseline.py`
- JSONL SIRP → Parquet via `scripts/ingest_rejected_patents.py`
- Stratified problem sampling via `scripts/sample_problems.py`
- Prior-art pair generation (positive + hard-neg + easy-neg) via `scripts/build_prior_art_pairs.py`
- Date normalization (mixed KIPRIS formats → ISO)
- IPC parsing (pipe-separated → 4-digit & section)

## 5. Uses

### Intended uses
- SDKB-Match (Expert + PriorArt) evaluation and ablations
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

## 8. Publication-integrity notes (paper-submission grade)

Mandatory before any paper using this dataset is submitted. (The full lab-internal risk
review is not part of the public tree — see
[`public_release_readiness_review.md`](public_release_readiness_review.md) §1 for why.)

- **#2 Synthetic ≠ expert.** The 7,500 GT is examiner-grounded (objective KIPO
  citations); the 7,800 3-rater set is algorithmically simulated. Neither is
  human-expert annotation. Misrepresenting this is a fabrication risk.
- **#3 Figure consistency.** Use only the verified 2026-05-17 snapshot figures
  (229/268 nodes·edges, SIRP 1,000, weighted κ 0.550 / ICC(2,k) 0.787 /
  transparency Fleiss κ 0.258 · ICC(2,1) 0.552). Resolve the `test_owl`
  regression (`make build-owl`) before quoting any test count.
- **#7 Leakage scope.** `leakage_protocol.md` is a v0.1 *design* only — no
  quantitative leakage results were produced this term (2026-2 algorithm
  phase). Papers must not claim measured leakage figures.
- **#1 Licensing.** SIRP patent body text (abstract/claim1) is under
  unresolved KIPRIS Plus terms — see [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md)
  §6. A dataset-resource paper is blocked until §6(B) is confirmed by counsel.
