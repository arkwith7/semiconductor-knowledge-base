# SDKB Ontology Guide — read it, query it, extend it to your own domain

> **Who this is for.** You are interested in a semiconductor-domain ontology and want to know
> (a) what SDKB actually models, (b) whether its modelling decisions are ones you would repeat,
> and (c) how to reuse or extend it for *your* process, *your* equipment, *your* jurisdiction.
>
> **What this is not.** Not a dataset card (that is [`datasheet.md`](datasheet.md) for the whole
> knowledge base and [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md) for
> the patent layer), and not a collection runbook (that is
> [`dataset_full_collection_runbook.md`](dataset_full_collection_runbook.md)).
>
> **Every number below is produced by running the code in this repository.** Where a number can
> drift, the command that regenerates it is given next to it.

---

## 1. The one idea that explains the whole design

**Nothing in the graph is allowed to exist without saying where it came from and how literally
it was taken.**

Every curated node and edge carries a provenance record, and one field in that record is the
honesty dial:

| `ont:interpretationType` | Meaning | Count in the built core graph |
|---|---|---|
| `verbatim` | Copied from the source as-is | 718 |
| `mapped` | The source said something equivalent; we translated it into SDKB vocabulary | 158 |
| `author-defined` | The source did not say this. A curator asserted it. | 95 |

```bash
grep -ho 'interpretationType "[a-z-]*"' ontology/*.ttl | sort | uniq -c
```

If you take one thing from SDKB into your own ontology, take this. A domain KG built from
literature, standards, and vendor datasheets *will* contain author assertions; the question is
only whether a downstream consumer can tell them apart from quoted facts. Here they can, at
triple level, and SHACL refuses to release a curated node that omits the dial (§6).

The same principle produces the second design decision, in §3: **external ontologies are
referenced, not imported.**

---

## 2. Module map — what exists, and how big it is

SDKB is a small, hand-authored **T-Box** (the vocabulary) plus generated **A-Box** layers
(the instances). The T-Box is what you would reuse; the A-Box is what you would replace.

### 2.1 T-Box modules

| File | Purpose | Named classes | Object props | Datatype props | Triples |
|---|---|---|---|---|---|
| `ontology/sdkb-core.ttl` | Process · SubProcess · Equipment · Material · Metrology · FMEA (FailureMode → RootCause → Mitigation) · Skill · Expert · Device | 43 | 45 | 45 | 718 |
| `ontology/sdkb-patent.ttl` | Patent · Claim · ClaimFeature · IPC/CPC/F-term · RejectionReason · PriorArtJudgment | 16 | 32 | 26 | 447 |
| `ontology/sdkb-rbv.ttl` | Firm · Resource · Capability · ResourceCombination (resource-based view) | 9 | 6 | 3 | 77 |
| `ontology/sdkb-foresight.ttl` | Scenario · STEEPVE · Signal · RealOption | 6 | 6 | 4 | 99 |
| `ontology/sdkb-commercialization.ttl` | TRL · License · Spinoff · IPTransaction | 7 | 6 | 4 | 95 |
| `ontology/sdkb-governance.ttl` | Jurisdiction-neutral export-control hooks | 0 | 2 | 1 | 40 |
| `ontology/sdkb-governance-kr.ttl` | Korea Industrial Technology Protection Act — National Core Technology | 3 | 2 | 2 | 58 |
| **Total** | | **84** | **93** | **85** | **1,534** |

Counts are `owl:Class` / `owl:ObjectProperty` / `owl:DatatypeProperty` subjects that are named
IRIs. Blank nodes (OWL restrictions) are excluded — `sdkb-core.ttl` has 13 and
`sdkb-patent.ttl` has 6, which is why a naive `grep -c "owl:Class"` over those two files reports
56 and 22 instead of 43 and 16.

Regenerate the table:

```bash
.venv/bin/python - <<'PY'
from rdflib import Graph, RDF, OWL, URIRef
import pathlib
for f in sorted(pathlib.Path("ontology").glob("sdkb-*.ttl")):
    if any(k in f.name for k in ("abox", "-data", "instances")):
        continue
    g = Graph(); g.parse(f)
    n = lambda t: len([s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)])
    print(f"{f.name:32s} C={n(OWL.Class):3d} OP={n(OWL.ObjectProperty):3d} "
          f"DP={n(OWL.DatatypeProperty):3d} triples={len(g)}")
PY
```

### 2.2 Documentation coverage — read this before you trust a predicate

Not every module is equally documented. `rdfs:comment` coverage, measured:

| Module | Classes | Object props | Datatype props |
|---|---|---|---|
| `sdkb-core.ttl` | 43/43 | 45/45 | 45/45 |
| `sdkb-patent.ttl` | 16/16 | 23/32 | 17/26 |
| `sdkb-rbv.ttl` | 9/9 | **1/6** | 3/3 |
| `sdkb-foresight.ttl` | **4/6** | **1/6** | 3/4 |
| `sdkb-commercialization.ttl` | **5/7** | **1/6** | 2/4 |
| `sdkb-governance-kr.ttl` | 3/3 | **1/2** | 1/2 |

**Core and patent are the mature modules; the three alignment modules are seeds.** Their classes
are documented but most of their predicates carry only `rdfs:domain` / `rdfs:range`. If you are
evaluating SDKB for reuse, judge it on core + patent, and treat rbv / foresight / commercialization
as scaffolding you would flesh out yourself.

### 2.3 A-Box layers

The A-Box is mostly **not** in the public tree, because it is built from KIPRIS patent text that
may be used academically but not redistributed. See *"What is empty, and how to fill it"* in
[`../README.md`](../README.md) for the exact per-layer table of what is missing and which
command rebuilds it.

The one A-Box that reproduces from an empty checkout with no credentials is the curation graph:

```bash
make owl convert     # data/semiconductor_v0_3.json → ontology/sdkb-core.ttl + sdkb-core-data.ttl
```

It currently yields **275 typed instances over 16 classes** and 2,884 triples
(Equipment 41 · SubProcess 38 · Device 34 · Material 31 · FailureMode 25 · RootCause 20 ·
Mitigation 20 · Vendor 16 · Process 12 · EquipmentClass 12 · Skill 12 · Parameter 5 ·
Metrology 3 · TechnologyNode 3 · Organization 2 · Semiconductor 1).

> ⚠️ The README and datasheet quote **229 nodes / 268 edges** from a verified 2026-05-17 snapshot.
> The committed source has grown since (`data/semiconductor_v0_3.json`, last changed 2026-08-01:
> 274 nodes / 312 edges). Rebuild and count rather than trusting either figure; see
> [`public_release_readiness_review.md`](public_release_readiness_review.md) F5.

---

## 3. Three modelling decisions worth arguing with

These are the choices you would either adopt or deliberately reject when building your own
domain ontology. Each is stated with its cost, because a design guide that only lists benefits
is advertising.

### 3.1 Reference external ontologies via SKOS; do not `owl:imports` them

SDKB aligns to SemicONTO, QUDT, MatKG and Wikidata through `skos:exactMatch` / `broadMatch` /
`closeMatch` back-links rather than importing their axioms. Alignment lives in
`mappings/sdkb_semiconto_alignment.ttl` and in class-level annotations, e.g.

```turtle
ont:HallEffectMeasurement a owl:Class ;
    rdfs:label "HallEffectMeasurement"@en ;
    rdfs:comment "Metrology determining carrier type, density, and mobility via the Hall effect."@en ;
    rdfs:subClassOf ont:Metrology ;
    skos:exactMatch <http://w3id.org/SemicONTO/HallEffectMeasurement> .
```

**Why.** An import binds you to the other ontology's release cadence, its axioms, and its
reasoning cost. A semiconductor KG that imports three upstream ontologies inherits three
upstream inconsistency risks and can no longer be reasoned over in a bounded time.

**Cost.** You lose automatic subsumption across the boundary. A query that wants SemicONTO
subclasses will not get them for free; you resolve mappings explicitly. SDKB accepts this — the
competency questions in `queries/cq/` are written to **not depend on inference at all** (see the
comment in `CQ01`: *"두 층위를 명시적으로 연다 — cq_runner 는 추론 없이 질의"*).

The only exception is `owl:imports <http://www.w3.org/ns/prov-o#>`, because provenance is the
one vocabulary the whole design rests on.

### 3.2 The T-Box is hand-authored; the A-Box is always generated

`ontology/*.ttl` files that hold *instances* are build artifacts. The source of truth is
`data/**` (JSON / JSONL / parquet) plus the generators in `scripts/`. Editing a generated TTL by
hand is prohibited in this repository, for a reason that generalizes: a downstream consumer that
pins your commit and vendors your TTL will silently receive ghost data on the next rebuild.

**Cost.** Fixing a single wrong triple means finding the generator that produced it. That is
slower, and it is the point.

### 3.3 Domain boundaries are drawn by *use*, not by *subject*

Governance (export control) is a separate module from core, not because export control is a
different subject, but because a consumer doing FMEA analysis should be able to load core
without inheriting a jurisdictional model that will be stale in six months. The split is
`sdkb-governance.ttl` (jurisdiction-neutral hooks: `gov:subjectToControl`, `gov:hasJurisdiction`,
`gov:controlLevel`) + `sdkb-governance-kr.ttl` (Korea-specific: `NationalCoreTechnology`,
`nctDesignationDate`, `requiresGovApproval`).

**If you extend to another jurisdiction, this is the seam to use** — add
`sdkb-governance-<cc>.ttl` and reuse the neutral hooks. See §5, Recipe C.

---

## 4. Naming and identity — the rules an extension must follow

From `config/namespaces.py`, which is the single source for every generator:

| Namespace | Prefix | Use |
|---|---|---|
| `https://w3id.org/sdkb/` | `sdkb:` | Ontology-level resources |
| `https://w3id.org/sdkb/ont/` | `ont:` | Classes and predicates (the T-Box) |
| `https://w3id.org/sdkb/data/` | `data:` | Instances (the A-Box) |
| `https://w3id.org/sdkb/gov/` | `gov:` | Governance classes and predicates |

**Instance ID policy:** `{type_prefix}:{slug}` — e.g. `process:lithography`,
`equipment:lam_kiyo_cx`. The slug is lowercase ASCII, words joined by underscore, no special
characters. The type prefix is the lowercase singular form of the node type, mapped in
`TYPE_PREFIX`.

**Labels** are `skos:prefLabel`, not `rdfs:label`, on instances. (`rdfs:label` is used on T-Box
terms.) Do not mix the two — the SHACL shapes and every CQ assume the split.

**If you fork SDKB for your own domain, change the base namespace.** Reusing
`https://w3id.org/sdkb/` for your own instances makes two graphs that cannot be merged and two
provenance chains that cannot be told apart.

---

## 5. Extension recipes

Three shapes of extension, in increasing order of blast radius. All three end at the same gate
(§6) — nothing merges without passing it.

### Recipe A — add domain instances (no vocabulary change)

The common case: your fab, your equipment, your failure modes.

1. **Edit the source, not the graph.** Add nodes and edges to `data/semiconductor_v0_3.json`.
   The node record is:

   ```json
   {
     "id": "subprocess:atomic_layer_etching",
     "type": "SubProcess",
     "canonical_name": "Atomic Layer Etching",
     "description": "Self-limiting cyclic etch with per-cycle removal control.",
     "props": {"priority": 2},
     "provenance": {
       "source": "semikong",
       "source_id": "L2-Etch-ALE",
       "reference": "Nguyen et al. 2024, arXiv:2411.13802, Appendix A",
       "license": "Apache-2.0",
       "url": "https://github.com/aitomatic/semikong",
       "interpretation": "mapped",
       "modified": false
     }
   }
   ```

   The edge record is `{"src", "predicate", "dst", "weight", "provenance"}` with `predicate` in
   the generator's uppercase form (`HAS_SUBPROCESS`, `USES_MATERIAL`, …).

2. **The `provenance` block is mandatory,** and `interpretation` must be one of `verbatim` /
   `mapped` / `author-defined`. If you are asserting something no source states, write
   `author-defined` — SHACL will pass either way, but the graph will lie if you do not.

3. `make owl convert && make validate && make test`.

**What you may not do:** hand-edit `ontology/sdkb-core-data.ttl`. It is regenerated from step 1.

### Recipe B — add a class or predicate to an existing module

For example, a `ont:Chamber` class between `Equipment` and `Parameter`.

1. Add it in the **generator** (`scripts/build_owl.py`), not in the TTL.
2. Give it `rdfs:label`, `rdfs:comment`, `rdfs:subClassOf`, and — if an external ontology already
   has the concept — a `skos:exactMatch` / `broadMatch` back-link (§3.1). A predicate additionally
   needs `rdfs:domain` and `rdfs:range`; core carries them on 75/90 and 89/90 of its predicates
   respectively, and new terms should not lower that.
3. If instances will use it, extend `validation/shapes.ttl` in the same change.
4. **Write at least one competency question that fails before your change and passes after.**
   That is how you demonstrate the term earns its place; see §7.
5. `make owl convert validate test`.

**Blast radius:** vocabulary changes are visible to every downstream consumer that vendored your
graph. This repository requires them to be announced in `CHANGELOG.md` with a version bump and a
graph signature (per-class instance counts, per-predicate triple counts). Adopt the same rule in
your fork — a consumer's provenance record becomes false the moment you change a published term
in place.

### Recipe C — port SDKB to a neighbouring domain

Say display manufacturing, battery cells, or pharmaceutical process chemistry. The structure that
transfers is not the semiconductor vocabulary, it is the **five-axis frame**:

| Axis | Semiconductor instantiation | What it is generically |
|---|---|---|
| Process | Process → SubProcess (`ont:hasSubStep`, `ont:hasNextStep`) | The ordered activity hierarchy |
| Resource | EquipmentClass → Equipment → EquipmentModel, Material, Parameter, Metrology | What the activity consumes and measures |
| Failure | FailureMode → RootCause → Mitigation (`ont:isDueTo`, `ont:mitigatedBy`) | The FMEA causal chain |
| Competence | Skill, Expert, ExpertCase | Who can act on the failure |
| Governance | RegulatedItem, jurisdiction hooks | What law constrains the activity |

Practical steps:

1. **Change the namespace base** (`config/namespaces.py`) — see §4.
2. **Keep** `sdkb-core.ttl`'s FMEA and process-hierarchy predicates; they are domain-neutral.
3. **Replace** the semiconductor-specific classes: `Semiconductor`, `Dopant`, `TechnologyNode`,
   `DopingRelation`, and the SemicONTO-aligned metrology subclasses.
4. **Reuse** `sdkb-governance.ttl` unchanged and write your own
   `sdkb-governance-<jurisdiction>.ttl` against its neutral hooks (§3.3).
5. **Re-derive your competency questions first, then build.** SDKB's 31 CQs are the spec that the
   vocabulary answers to; a port that copies the vocabulary but not the questions has no way to
   know when it is done.

The patent module (`sdkb-patent.ttl`) ports unchanged to any domain that does prior-art work —
it models patents, claims and examiner citations, not semiconductors.

---

## 6. The release gate — what "valid" means here

```bash
make owl convert          # sources → T-Box + A-Box (TTL is only ever produced here)
make abox-patents         # patent A-Box, if you have the data
make validate             # SHACL
make test                 # unit + integration
```

`validation/` holds three shape files: `shapes.ttl` (curated core), `shapes_patent.ttl`,
`shapes_claim_features.ttl`. The core shape requires, on every curated node
(`ont:Process`, `ont:SubProcess`, `ont:EquipmentClass`, …):

- `skos:prefLabel`
- `dcterms:license` — **the per-source licence, not the repository licence**; this is how a
  mixed-licence graph stays auditable
- `ont:interpretationType` — the honesty dial from §1

plus datatype constraints on the expert/problem layer (`ont:age` integer, `ont:patentCount`
integer ≥ 0, `ont:retirementYear` `xsd:gYear`, …).

Two rules this repository applies to its own gate, worth copying:

- **A shape that has never been run against the graph it targets is decoration, not validation.**
- **Check that inputs which should fail do fail.** If injecting a violating delta does not get
  rejected, you do not have a gate.

---

## 7. Competency questions — the executable spec

```bash
make cq        # runs queries/cq/*.rq → data/reports/cq_report.json
```

31 SPARQL queries, each carrying its own metadata header:

```sparql
# desc: 공정 단계별로 매핑된 특허가 몇 건인가? (커버리지 기본 질의)
# suite: core
# monotone: up
# expect-min: 1
```

| Header | Meaning |
|---|---|
| `suite:` | Which task the question belongs to — `core` (12), `pa` prior art (8), `em` expert matching (6), `tf` technology foresight (5) |
| `monotone:` | Whether the answer count should go up or down as the graph grows — turns a query into a regression check |
| `expect-min:` | The floor below which the suite fails |
| `target:` | Which graph file the query needs |

**A suite whose A-Box has not been built reports 0 rows and fails**, and the report's
`graph_files_missing` field names the file. So a failure tells you *what to build*, not that the
ontology is broken.

The four suites exist so that a change to one task's vocabulary can be checked against the other
three — if adding a patent predicate breaks `em`, you learn it here. That cross-task
non-regression check is the part of this design most worth stealing: **in a shared T-Box, no
single task's metrics are sufficient to approve a change.**

Shorter, standalone examples live in `examples/sparql/` (regulatory risk, FMEA path, technology
gap) and are a gentler entry point than the CQ suite.

---

## 8. Where to look next

| You want to | Read |
|---|---|
| Judge whether the data is fit for your purpose | [`datasheet.md`](datasheet.md) (whole KB), [`dataset_rejected_patents_card.md`](dataset_rejected_patents_card.md) (patent layer) |
| Rebuild the patent layer with your own KIPRIS key | [`dataset_full_collection_runbook.md`](dataset_full_collection_runbook.md) |
| Understand the patent field semantics | [`semiconductor_industry_rejected_patents_schema.md`](semiconductor_industry_rejected_patents_schema.md), [`kipris_reject_dataset_source_mapping.md`](kipris_reject_dataset_source_mapping.md) |
| See how upstream ontologies were surveyed and chosen | [`semiconductor_ontology_provenance_research.md`](semiconductor_ontology_provenance_research.md) |
| Understand the evaluation-leakage stance | [`leakage_protocol.md`](leakage_protocol.md) |
| Know what this repo still gets wrong | [`public_release_readiness_review.md`](public_release_readiness_review.md) |

Directory index: [`README.md`](README.md).
