#!/usr/bin/env python3
"""Inject the A2 device/product layer into the KG (plan §7.4-3, gap A2/B4).

Reads data/external/device_vocab/device_alias_table.json (31 classes,
paper_data Phase D) and adds, idempotently, into data/semiconductor_v0_3.json:

  - one `Device` node per class (id, canonical_name, category, Wikidata prov)
  - sanitized en/ko synonyms into kg["synonyms"] so the Tier-1 lexicon
    picks device terms up in free-text extraction (closes B4 partial:
    raw Wikidata ko labels are noisy, so junk labels are filtered)

Re-run `make convert` afterwards to regenerate sdkb-core-data.ttl.
This script is safe to run repeatedly (existing device nodes are replaced,
not duplicated).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
VOCAB_PATH = ROOT / "data" / "external" / "device_vocab" / "device_alias_table.json"

_CAT_DESC = {
    "logic": "Logic/transistor device architecture.",
    "memory": "Memory device architecture.",
    "power": "Power semiconductor device.",
    "sensor": "Sensor/imaging device.",
    "packaging": "Advanced packaging / interconnect architecture.",
    "discrete": "Discrete semiconductor device (rectifying or switching component).",
}


def _clean(term: str) -> str | None:
    """Drop noisy Wikidata labels (sentences, trailing-period junk)."""
    t = (term or "").strip()
    if not t or len(t) > 30 or t.endswith(".") or t.count(" ") > 4:
        return None
    if re.fullmatch(r"[\d\W_]+", t):          # pure digits/punctuation
        return None
    return t


def main() -> int:
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))
    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))

    # Drop any previously-injected device artefacts (idempotent re-run)
    kg["nodes"] = [n for n in kg["nodes"] if n.get("type") != "Device"]
    kg["synonyms"] = [
        s for s in kg.get("synonyms", [])
        if not str(s.get("node_id", "")).startswith("device:")
    ]

    n_nodes = 0
    n_syn = 0
    for dev_id, v in vocab.items():
        cats = v.get("category") or []
        cat = cats[0] if cats else "logic"
        en = [e for e in (v.get("en") or []) if e and e.strip()]
        ko = v.get("ko") or []
        qids = v.get("wikidata") or []
        canonical = en[0] if en else dev_id.split(":", 1)[1].replace("_", " ").upper()

        kg["nodes"].append({
            "id": dev_id,
            "type": "Device",
            "canonical_name": canonical,
            "description": _CAT_DESC.get(cat, "Device architecture."),
            "props": {"category": cat},
            "provenance": {
                "source": "wikidata" if qids else "author-defined",
                "source_id": ",".join(qids),
                "reference": "Wikidata device class (paper_data Phase D, 2026-05-16)",
                "license": "CC0-1.0",
                "url": (f"https://www.wikidata.org/wiki/{qids[0]}" if qids else ""),
                "modified": False,
                "interpretation": "mapped" if qids else "author-defined",
                "cross_ref": [{"source": "wikidata", "id": q} for q in qids],
            },
        })
        n_nodes += 1

        seen: set[str] = set()
        for lang, terms in (("en", en), ("ko", ko)):
            for raw in terms:
                t = _clean(raw)
                if not t or t.lower() in seen:
                    continue
                seen.add(t.lower())
                kg["synonyms"].append({
                    "node_id": dev_id, "term": t,
                    "lang": lang, "term_type": "synonym",
                })
                n_syn += 1

    KG_PATH.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ Injected {n_nodes} Device nodes + {n_syn} synonyms → "
          f"{KG_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
