from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_ETCH_WEB_POC_DATASET = REPO_ROOT / "data/processed/etching_reject_web_poc_dataset.jsonl"
CANONICAL_SEMICONDUCTOR_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
