# SDKB-Match Architecture

> **SDKB Matching Layer — semiconductor SME ↔ expert / patent ↔ prior-art matching**
> v0.1 draft — 2026-05-12. Aligned with Amendment v2.

## 1. One-sentence statement

SDKB-Match is a matching platform whose **compliance constraints are part of the retrieval graph, not a post-hoc filter** — the same architecture serves two markets: (a) expert matching for 반도체 소부장 SMEs and (b) prior-art retrieval for IP-R&D.

## 2. The two tracks share the same skeleton

```
                    ┌─────────────────────────────────┐
                    │       SDKB Graph (RDF)          │
                    │  core + governance(US/EU/KR)    │
                    │  + patent + rbv + commercial    │
                    │  + foresight                    │
                    └────────────────┬────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                                                 ▼
   ┌────────────────────┐                          ┌────────────────────┐
   │  Expert track      │                          │  PriorArt track    │
   │ Query: tech problem│                          │ Query: patent app  │
   │ Pool: 100 experts  │                          │ Pool: SIRP+IPC     │
   │   (synthetic)      │                          │   peers (real)     │
   └─────────┬──────────┘                          └─────────┬──────────┘
             │                                               │
             ├──── shared agent loop ────────────────────────┤
             │   1. Retrieve candidates                      │
             │   2. Apply structural compliance gate         │
             │      (BIS §744.23, ECHA SCIP, KR-NCT,         │
             │       multi-jurisdiction overlap)             │
             │   3. Rank with provenance trace               │
             │   4. Emit audit record (PROV-O)               │
             └────────────────────────┬──────────────────────┘
                                      ▼
                            ┌──────────────────┐
                            │  Audit ledger    │
                            │  (prov.ttl ext)  │
                            └──────────────────┘
```

## 3. Components

| Layer | Component | Responsibility |
|---|---|---|
| Data | SDKB graph | Truth substrate. 14 core + governance + 4 alignment modules. |
| Data | SIRP dataset | 773 examiner-grounded prior-art labels. |
| Retrieval | Retriever | Hybrid lexical (BM25/TF-IDF) + dense (sentence-transformers). |
| Gate | Compliance gate | Structural query rewriter that injects compliance filters into the retrieval (not after). Outputs the *eligible* candidate set. |
| Ranker | Cross-encoder | Re-ranks the eligible candidates with a SDKB-aware feature stack. |
| Audit | PROV-O writer | Emits one `prov:Activity` per query, linking inputs, gate decisions, and ranking outputs. |
| API | FastAPI surface | Two endpoints: `/match/expert`, `/match/priorart`. Both return ranked list + audit ID. |

## 4. Compliance gate semantics (key concept)

The gate is what makes the system **compliance-first** rather than a generic matcher. It is a graph rewriter that, given a query and a candidate, expands them into their SDKB subgraphs (Process, Material, EquipmentClass, Patent, Firm) and refuses any pairing whose **union subgraph** violates a constraint.

Constraints are not opinions in code. They are SHACL shapes (`validation/shapes.ttl`) over the union subgraph. Examples:
- **BIS §744.23**: if the union subgraph contains a `RegulatedItem` with TPP ≥ 4800 and the matched candidate's `Organization` resolves to an EAR entity-list assignee → refuse.
- **KR-NCT**: if the union subgraph contains a `NationalCoreTechnology` with `gov:requiresGovApproval=true` and the candidate is in `JurisdictionUS|JP|CN` → refuse.
- **Multi-jurisdiction overlap**: if the union subgraph crosses ≥ 2 jurisdictions whose rules conflict → mark as `leakage_risk=high` and require explicit approval.

## 5. Inputs and outputs of this term (2026-1)

### Inputs (data produced this term)
- `data/semiconductor_v0_3.json` — 198/264 baseline
- `data/expert_profiles.parquet` — 100 synthetic experts
- `data/problems.parquet` — 50 stratified rejected patents (deliverable ③)
- `data/regulatory_scenarios.parquet` — 25 adversarial scenarios
- `data/patents/prior_art_pairs.parquet` — 7,500 examiner-grounded pairs (deliverable ④)

### Outputs (this term)
- `notebooks/04_prior_art_baseline.ipynb` — TF-IDF baseline running end-to-end on the above
- `validation/reliability_report.md` — MRR / NDCG@5 / Recall@K / leakage rate on the 7,500-pair evaluation
- `docs/project/commercialization_strategy_v1.md` — deliverable ⑤

### Out of scope this term (2026-2)
- Full agent loop with cross-encoder re-ranking
- Dense retrieval with sentence-transformers
- FastAPI surface
- Live KIPRIS query expansion

## 6. Open architectural questions (resolve W3-W4)

- Cohort split for the 7,500 pairs — random vs. by-IPC-section vs. by-time. *Recommendation*: by-IPC-section to estimate cross-domain generalization.
- Leakage rate definition — exact formula in [`leakage_protocol.md`](../leakage_protocol.md).
- Multi-jurisdiction conflict resolution — pure refusal vs. approval-required tier vs. risk-flag tier.
