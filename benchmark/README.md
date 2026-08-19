# SDKB Evaluation Harness (`benchmark/`)

This directory holds the **evaluation harness** for the SDKB prior-art paper: the retrieval
systems, the release-gate conditions, the scoring and statistics, and the frozen evaluation
assets. It exists so that the code paths named in the paper's evaluation-design section are
**real files you can open**, not claims.

> **Two doors.** If you want the *dataset* — the shared T-Box, SHACL shapes, competency
> questions, mappings — you never need this directory. Start at the repository README and run
> `uv sync`. If you want to *reproduce the paper's evaluation*, you are in the right place;
> run `uv sync --extra benchmark`.

## Layout

| Path | What it is |
|---|---|
| `src/sdkb_paper/` | The harness itself — 74 files, **byte-identical** to the audited source |
| `assets/` | Frozen evaluation assets: qrel and split identifiers, thresholds, gate reports, fault-injection matrices, run sets, result tables, `verdicts.yaml` |
| `figures/data/` | Frozen values behind the paper's conceptual figures |
| `supplementary/` | S1–S6 — appendices, fault-injection detail, unexecuted design, full-length version, preregistration crosswalk |
| `MANIFEST.json` | Per-file sha256, byte size, and source path in the producing repository |
| `EXCLUDED.md` | What was **not** shipped, and why |
| `CROSSWALK.md` | The paper's system table ↔ these code entry points |

The package directory is named `sdkb_paper` because 44 of its files import it absolutely.
Renaming it would mean editing them, and then this tree would no longer be the code that was
audited. **The rule for this directory is: copy, never edit.** It is produced by a generator in
the paper repository (`scripts/export_benchmark.py`); `MANIFEST.json` lets anyone check that the
copy still matches its source.

## What you can and cannot reproduce

Three limits are stated here rather than discovered later.

1. **Patent full text is not redistributable.** KIPRIS terms allow academic use but not
   redistribution, so abstracts and claims are absent. Identifiers and the refetch procedure are
   provided instead; the repository README documents how to refill the A-Box with an API key.
2. **The published concept dictionary is a later generation than the paper's numbers.** After the
   paper's measurements, an upstream change re-targeted expert-matching aliases in the patent
   profile. Applying the published dictionary therefore yields links that differ from the ones
   behind the reported figures. This is a generation difference, not a missing asset.
3. **Hybrid fusion outputs are not byte-reproducible.** Record order varies across processes, so
   file hashes differ while the rankings do not. Verify these by content equivalence.

## About the sealed test qrel

The answer key is published, including the split that was sealed during the confirmatory
evaluation. This does not weaken the preregistration, for two reasons.

**Sealing was a procedural discipline, not secrecy.** The relevance labels are examiner citations,
which are printed in the published patent record; anyone holding the query identifiers could
always look them up. What the seal guaranteed was that *we* did not consult them while choosing
thresholds and configurations, and the evidence for that is the access ledger in
`assets/seal_access.jsonl`, not the unavailability of a file.

**Future confirmatory splits do not depend on hiding this one.** The paper's second confirmatory
split was built by collecting a new query cohort, not by withholding the first answer key. The
same route remains open.

Note also that `qrel_test_sealed.csv` is exactly `qrel_examiner.csv` restricted to the test rows of
`split.csv`; it is shipped for convenience, not as an additional disclosure.

## Licensing

Code in this directory is released under **Apache-2.0** (`LICENSE-CODE.txt` at the repository
root). The dataset layers outside this directory remain under **CDLA-Permissive-2.0**
(`LICENSE.txt`). Documentation is CC-BY-4.0.
