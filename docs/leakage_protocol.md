# Leakage Protocol — SDKB-Match Evaluation

> v0.1 draft — 2026-05-12. Pins the evaluation contract for deliverable ④ and the 2026-2 algorithm phase.

## 1. Problem statement

A **leakage** event occurs when SDKB-Match's matching output reveals or relies on information that a multi-jurisdiction compliance rule forbids. Leakage rate measures how often this happens across the evaluation set. The rate must be **structurally bounded by design**, not patched by a post-filter — see [`matching_architecture.md`](matching_architecture.md) §4.

## 2. Definitions

| Term | Definition |
|---|---|
| Query | A technical problem (Expert track) or a patent application (PriorArt track). |
| Candidate | An expert profile (Expert) or a prior-art document (PriorArt). |
| Sensitive attribute | An SDKB property that crosses a jurisdiction-control rule: `gov:designatedAsNCT`, `gov:hasECCN ≥ 3B001`, `gov:hasSVHC`, `gov:hasJurisdiction` mismatches, `ont:securityLevel="RESTRICTED"`. |
| Forbidden pair | A (query, candidate) pair whose union subgraph violates at least one SHACL shape in `validation/shapes.ttl` / `shapes_patent.ttl`. |
| Approved disclosure | A forbidden pair that has an explicit approval token in the query (operator override). Counted separately. |

## 3. Leakage rate (primary metric)

For an evaluation set of N queries each returning a ranked list of K candidates:

```
leakage_rate@K = (# forbidden pairs in any top-K result) / (N × K)
```

For deliverable ④ this term: N = 50 problems (Expert track placeholder) + 50 SIRP-anchored queries (PriorArt track), K = 5.

**Target**: `leakage_rate@5 ≤ 0.01` for the structural-gate variant; the without-gate baseline is reported alongside to demonstrate the architecture's contribution.

## 4. Secondary metrics

| Metric | Definition | Target |
|---|---|---|
| MRR | Mean reciprocal rank of the first relevant candidate. | ≥ 0.30 baseline |
| NDCG@5 | Normalized DCG over top-5 with graded `label`. | ≥ 0.35 baseline |
| Recall@10 | Fraction of all relevant candidates appearing in top-10. | ≥ 0.55 baseline |
| Recall@50 | Fraction of all relevant candidates appearing in top-50. | ≥ 0.80 baseline |
| Coverage | Fraction of queries with at least one eligible candidate post-gate. | ≥ 0.95 |

Numbers above are **placeholders to be calibrated** after the TF-IDF baseline lands; lock them in [`validation/reliability_report.md`](../validation/reliability_report.md) at end of term.

## 5. Slice-level reporting

Report all metrics broken down by:
- `difficulty` ∈ {positive_examiner, positive_broad, negative_hard, negative_easy}
- `process_family` (top 5 by SIRP volume)
- `jurisdiction_profile` (from `regulatory_scenarios.parquet`)

## 6. Forbidden-pair generation for evaluation

Forbidden pairs for the leakage measurement are derived from `data/regulatory_scenarios.parquet`:
- Each scenario specifies a `jurisdictions` set.
- A candidate whose SDKB subgraph carries `gov:hasJurisdiction` outside the scenario's allowed set is forbidden.
- For PriorArt track, candidates carrying `gov:designatedAsNCT` with `requiresGovApproval=true` are forbidden when the query's assignee is in a non-KR jurisdiction.

## 7. Audit obligation

Every evaluation run writes a PROV-O activity record naming the dataset hashes, the SHACL shape graph hash, and the metric outputs. Without this record, the run is not citable in `validation/reliability_report.md`.
