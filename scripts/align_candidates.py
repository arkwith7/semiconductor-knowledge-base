#!/usr/bin/env python3
"""Week 4 — Alignment candidate generator (lexical + embedding hybrid).

Phase 1 (this script): Lexical matching using rapidfuzz.
Phase 2 (optional, with sdkb[align]): Sentence-transformer embedding cosine similarity.

Inputs:
  data/nodes.parquet          — SDKB node table (columns: id, type, canonical_name, description)
  mappings/ref_labels.csv     — Reference labels (columns: ref_id, ref_type, label, source)

Output:
  mappings/mapping_candidates.tsv — Candidate alignments with scores
"""

import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent.parent
NODES_PATH = ROOT / "data" / "nodes.parquet"
REF_PATH = ROOT / "mappings" / "ref_labels.csv"
OUT_PATH = ROOT / "mappings" / "mapping_candidates.tsv"

# Type compatibility matrix: which SDKB types can map to which reference types
TYPE_COMPAT = {
    "Process":        {"ProcessGroup", "ProcessModule", "ExperimentStep", "Process"},
    "SubProcess":     {"ProcessModule", "ProcessUnit", "ExperimentStep", "ExperimentalStep", "SubProcess"},
    "EquipmentClass": {"Equipment", "EquipmentClass", "Instrument"},
    "Equipment":      {"Equipment", "Instrument", "Tool"},
    "Material":       {"Material", "Chemical", "Substance", "CHM"},
    "FailureMode":    {"FailureMode", "Defect", "Anomaly"},
    "RootCause":      {"FailureCause", "RootCause", "Cause"},
    "Mitigation":     {"Mitigation", "CorrectiveAction", "Remedy"},
    "Skill":          {"Skill", "Competency", "Capability"},
    "Vendor":         {"Organization", "Company", "Vendor"},
    "Parameter":      {"Parameter", "Property", "Metric", "PRO"},
    "Metrology":      {"Metrology", "Characterization", "CMT"},
    "TechnologyNode": {"TechnologyNode", "Node", "Generation"},
    "Organization":   {"Organization", "Institution", "Consortium"},
}

LEXICAL_THRESHOLD = 60  # Minimum fuzzy score to keep as candidate
TOP_K = 10


def normalize_label(label: str) -> str:
    """Normalize a label for matching."""
    return label.lower().strip().replace("-", " ").replace("_", " ")


def lexical_match(sdkb_df: pd.DataFrame, ref_df: pd.DataFrame) -> list[dict]:
    """Generate candidate mappings using token-based fuzzy matching."""
    candidates = []
    ref_labels = ref_df["label"].tolist()
    ref_labels_norm = [normalize_label(l) for l in ref_labels]

    for _, row in sdkb_df.iterrows():
        sdkb_id = row["id"]
        sdkb_type = row["type"]
        sdkb_label = row["canonical_name"]
        sdkb_norm = normalize_label(sdkb_label)

        # Get compatible reference types
        compat_types = TYPE_COMPAT.get(sdkb_type, set())

        # Score against all references
        results = process.extract(
            sdkb_norm,
            ref_labels_norm,
            scorer=fuzz.token_sort_ratio,
            limit=TOP_K * 3,  # Over-fetch then filter
        )

        for match_label_norm, score, idx in results:
            if score < LEXICAL_THRESHOLD:
                continue

            ref_row = ref_df.iloc[idx]
            ref_type = ref_row.get("ref_type", "")

            # Type compatibility filter
            type_compatible = not compat_types or ref_type in compat_types or ref_type == ""

            candidates.append({
                "sdkb_id": sdkb_id,
                "sdkb_type": sdkb_type,
                "sdkb_label": sdkb_label,
                "ref_id": ref_row["ref_id"],
                "ref_type": ref_type,
                "ref_label": ref_row["label"],
                "ref_source": ref_row.get("source", ""),
                "lexical_score": round(score / 100, 3),
                "type_compatible": type_compatible,
                "method": "lexical",
                "review_status": "PENDING",
            })

    return candidates


def main():
    if not NODES_PATH.exists():
        print(f"ERROR: {NODES_PATH} not found. Run sdkb-parse first.", file=sys.stderr)
        sys.exit(1)

    sdkb_df = pd.read_parquet(NODES_PATH)

    if REF_PATH.exists():
        ref_df = pd.read_csv(REF_PATH)
    else:
        # Generate a placeholder ref_labels.csv
        print(f"⚠ {REF_PATH} not found — generating placeholder")
        REF_PATH.parent.mkdir(parents=True, exist_ok=True)
        ref_df = pd.DataFrame({
            "ref_id": ["placeholder:001"],
            "ref_type": ["Process"],
            "label": ["Placeholder — replace with real reference labels"],
            "source": ["none"],
        })
        ref_df.to_csv(REF_PATH, index=False)
        print(f"  Created {REF_PATH} — populate with real reference ontology labels")
        return

    candidates = lexical_match(sdkb_df, ref_df)

    out_df = pd.DataFrame(candidates)
    # Sort by sdkb_id, descending score
    out_df = out_df.sort_values(["sdkb_id", "lexical_score"], ascending=[True, False])
    # Keep top-K per sdkb_id
    out_df = out_df.groupby("sdkb_id").head(TOP_K).reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_PATH, sep="\t", index=False)
    print(f"✓ Mapping candidates ({len(out_df)} rows) → {OUT_PATH}")
    print(f"  Unique SDKB entities matched: {out_df['sdkb_id'].nunique()}")
    print(f"  Type-compatible matches: {out_df['type_compatible'].sum()}")


if __name__ == "__main__":
    main()
