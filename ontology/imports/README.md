# SDKB Reference Cache — External Ontologies

This directory holds **read-only caches** of external ontologies that SDKB *references* but does **not** `owl:imports`. The SDKB architecture is SDKB-centric: external ontologies are curation/alignment sources, not parent schemas. See [docs/project/architecture_amendment_sdkb_centric.md](../../docs/project/architecture_amendment_sdkb_centric.md).

## Contents

| File | Source | Version | Retrieved | SHA256 |
|------|--------|---------|-----------|--------|
| `SemicONTO-0.2.ttl` | https://huanyu-li.github.io/SemicONTO/0.2/SemicONTO.ttl (canonical: http://w3id.org/SemicONTO/0.2/) | 0.2 (2025-06-24) | 2026-05-12 | `4c53544de016b2d1147d41ba68094c7849999494378cd2c68674334b0e2e8d52` |

## Verification

```bash
sha256sum -c <<< "4c53544de016b2d1147d41ba68094c7849999494378cd2c68674334b0e2e8d52  SemicONTO-0.2.ttl"
```

## Usage notes

- `SemicONTO-0.2.ttl` is parsed by `scripts/analyze_semiconto.py` to produce `data/reports/semiconto_analysis.json`.
- Alignment to SDKB lives in `mappings/sdkb_semiconto_alignment.{csv,ttl}`.
- SDKB's `sdkb-core.ttl` does **not** import this file. To pull SemicONTO concepts into SDKB, use SKOS mappings (`skos:exactMatch`/`closeMatch`/`broadMatch`) or define equivalent classes in SDKB namespace.

## License

SemicONTO is CC BY 4.0 (Huanyu Li, Linköping University). When SDKB redistributes SKOS mappings referencing SemicONTO terms, attribute via `dcterms:source` on the alignment graph.
