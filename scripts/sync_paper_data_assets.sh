#!/usr/bin/env bash
# Re-copy gitignored prior-art bulk assets from the paper_data collection repo.
# Provenance & rationale: docs/project/prior_art_ontology_gap_and_data_plan.md §7.1.
# Committed assets (canonical jsonl, rejection_decisions/structured, device_vocab,
# citation_norm.py) are tracked in git and NOT re-copied here.
set -euo pipefail

SRC="${1:-/home/arkwith/Dev/paper_data}"
DST="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$SRC/data/processed" ] || { echo "ERR: paper_data not found at $SRC" >&2; exit 1; }

mkdir -p "$DST/data/patents/fulltext"
cp -r "$SRC/data/processed/fulltext/prior_arts"          "$DST/data/patents/fulltext/"
cp -r "$SRC/data/processed/fulltext/etching_prior_arts"  "$DST/data/patents/fulltext/"
cp    "$SRC/data/processed/citation_resolution_full_cache.json" \
      "$DST/data/patents/citation_resolution_full_cache.json"

echo "synced fulltext: $(ls "$DST/data/patents/fulltext/prior_arts" | wc -l) + \
$(ls "$DST/data/patents/fulltext/etching_prior_arts" | wc -l) docs; \
cache $(wc -c < "$DST/data/patents/citation_resolution_full_cache.json") bytes"
