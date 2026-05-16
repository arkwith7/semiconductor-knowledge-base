#!/usr/bin/env python3
"""Strip raw KIPRIS 거절결정서 OCR text from the committed GT (license).

The public repo's KIPRIS redistribution status is unresolved
(docs/dataset_rejected_patents_card.md §6). The §5(4) ground truth only
needs the structured MAPPING (cited_evidence_map · legal_bases ·
target_claims); the raw `excerpt` OCR of the official rejection-decision
document is the license-sensitive part and is removed here.

Idempotent: drops the `excerpt` key from every
data/patents/rejection_decisions/structured/*.json. `text_length` is kept
(a length integer, not content) for provenance. The raw text remains only
in the private paper_data collection repo.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRUCT_DIR = ROOT / "data" / "patents" / "rejection_decisions" / "structured"
DROP_KEYS = ("excerpt",)  # raw KIPRIS document OCR text


def main() -> int:
    files = sorted(STRUCT_DIR.glob("*.json"))
    scrubbed = 0
    for f in files:
        obj = json.loads(f.read_text(encoding="utf-8"))
        if any(k in obj for k in DROP_KEYS):
            for k in DROP_KEYS:
                obj.pop(k, None)
            obj["_excerpt_removed"] = True  # transparency marker
            f.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                         encoding="utf-8")
            scrubbed += 1
    print(f"✓ Scrubbed {scrubbed}/{len(files)} structured GT files "
          f"(dropped {DROP_KEYS}; mapping/legal_bases/target_claims kept)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
