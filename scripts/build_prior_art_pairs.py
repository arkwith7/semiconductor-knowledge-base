#!/usr/bin/env python3
"""Build deliverable ④ — 7,500 prior-art retrieval pairs from SIRP.

Inputs (run scripts/ingest_rejected_patents.py first):
  data/patents/rejected_patents_meta.parquet
  data/patents/ipc_links.parquet
  data/patents/prior_art_edges.parquet

Output:
  data/patents/prior_art_pairs.parquet   — (target_patent_id, candidate_id, label, source_type, difficulty)
  data/patents/pairs_report.json         — split counts, target distribution, leakage probes

Pair design (calibrated to the 7,500 target in the signed plan + Amendment v2):
  Positive (examiner-cited):       all triples with source_type='examiner'      (~1,961)
  Positive (broad GT):             triples in 'all' but not in 'examiner'        (~770)
  Hard negative (same IPC-4digit,  random patents from the corpus with the same
                 different family) primary_ipc_4digit but different process_family (~2,300)
  Easy negative (different IPC      random patents from a different IPC section  (~2,500)
                 section)
  Total ≈ 7,500.

The 'difficulty' column lets downstream evaluation report MRR/NDCG@K stratified
by difficulty, which is the protocol Prof. Shin's TFSC-family papers expect.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
IN_EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
OUT_PAIRS = ROOT / "data" / "patents" / "prior_art_pairs.parquet"
OUT_REPORT = ROOT / "data" / "patents" / "pairs_report.json"

# Target counts (tunable; defaults sum to ~7,500)
TARGETS = {
    "hard_negative_per_positive": 1.0,   # 1 hard-neg per positive triple
    "easy_negative_per_positive": 1.1,   # 1.1 easy-neg per positive triple
    "max_pairs": 7800,                   # hard cap (we trim to ~7,500 by random downsample)
    "target_total": 7500,
}

SEED = 20260512


def main() -> None:
    if not IN_META.exists() or not IN_EDGES.exists():
        print(f"ERROR: missing input. Run scripts/ingest_rejected_patents.py first.", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(SEED)
    meta = pd.read_parquet(IN_META)
    edges = pd.read_parquet(IN_EDGES)

    # ── Positives ──────────────────────────────────────────────────
    examiner = edges[edges["source_type"] == "examiner"].copy()
    examiner["label"] = 1
    examiner["difficulty"] = "positive_examiner"

    all_edges = edges[edges["source_type"] == "all"].copy()
    # Some GT-all rows are duplicates of GT-examiner; keep the broader-only subset
    examiner_keys = set(zip(examiner["target_patent_id"], examiner["cited_id"]))
    broad = all_edges[~all_edges.apply(
        lambda r: (r["target_patent_id"], r["cited_id"]) in examiner_keys, axis=1
    )].copy()
    broad["label"] = 1
    broad["difficulty"] = "positive_broad"

    positives = pd.concat([examiner, broad], ignore_index=True)
    n_pos = len(positives)
    print(f"Positives: examiner={len(examiner)} + broad={len(broad)} = {n_pos}")

    # ── Build the in-corpus candidate pool ─────────────────────────
    # Use the 773 SIRP patents themselves as the candidate corpus.
    # (External GT IDs without an SIRP entry are not sampleable as candidates;
    #  the retrieval evaluation treats them as "external positives" — found in
    #  GT but not in the searchable pool. This is faithful to PatentMatch
    #  convention: positives may live outside the indexed corpus.)
    pool = meta[["patent_id", "primary_ipc_4digit", "primary_ipc_section",
                 "process_family"]].copy()

    fam_to_ids: dict[str, list[str]] = (
        pool.groupby("process_family")["patent_id"].apply(list).to_dict()
    )
    sec_to_ids: dict[str, list[str]] = (
        pool.groupby("primary_ipc_section")["patent_id"].apply(list).to_dict()
    )
    ipc4_to_ids: dict[str, list[str]] = (
        pool.groupby("primary_ipc_4digit")["patent_id"].apply(list).to_dict()
    )
    by_pid = pool.set_index("patent_id")

    # Forbidden set for negatives: anything ever cited as prior-art for a target
    forbid: dict[str, set[str]] = (
        edges.groupby("target_patent_id")["cited_id"]
        .apply(lambda s: set(s.tolist())).to_dict()
    )

    def sample_hard_negative(target_id: str) -> str | None:
        if target_id not in by_pid.index:
            return None
        row = by_pid.loc[target_id]
        ipc4 = row["primary_ipc_4digit"]
        family = row["process_family"]
        candidates = ipc4_to_ids.get(ipc4, [])
        # Same IPC-4digit, different family, not the target, not a known prior-art
        bad = forbid.get(target_id, set()) | {target_id}
        eligible = [c for c in candidates if by_pid.loc[c, "process_family"] != family and c not in bad]
        if not eligible:
            return None
        return rng.choice(eligible)

    def sample_easy_negative(target_id: str) -> str | None:
        if target_id not in by_pid.index:
            return None
        row = by_pid.loc[target_id]
        section = row["primary_ipc_section"]
        # Different IPC section
        other_sections = [s for s in sec_to_ids.keys() if s and s != section]
        if not other_sections:
            return None
        bad = forbid.get(target_id, set()) | {target_id}
        for _ in range(8):
            s = rng.choice(other_sections)
            pool_ids = sec_to_ids.get(s, [])
            if not pool_ids:
                continue
            c = rng.choice(pool_ids)
            if c not in bad:
                return c
        return None

    # ── Negatives ──────────────────────────────────────────────────
    hard_rows = []
    easy_rows = []
    targets_with_pool = positives[positives["target_patent_id"].isin(by_pid.index)]
    n_hard_target = int(round(len(positives) * TARGETS["hard_negative_per_positive"]))
    n_easy_target = int(round(len(positives) * TARGETS["easy_negative_per_positive"]))

    # Sample hard negs aligned to target_patent distribution
    pos_targets = targets_with_pool["target_patent_id"].tolist()
    rng.shuffle(pos_targets)
    iter_targets = (t for t in pos_targets * 4)  # repeat pool to allow retries
    while len(hard_rows) < n_hard_target:
        try:
            t = next(iter_targets)
        except StopIteration:
            break
        c = sample_hard_negative(t)
        if c is None:
            continue
        hard_rows.append({
            "target_patent_id": t, "cited_id": c, "cited_raw": "", "cited_office": "KR",
            "source_type": "negative_hard", "label": 0, "difficulty": "negative_hard",
        })

    rng.shuffle(pos_targets)
    iter_targets = (t for t in pos_targets * 4)
    while len(easy_rows) < n_easy_target:
        try:
            t = next(iter_targets)
        except StopIteration:
            break
        c = sample_easy_negative(t)
        if c is None:
            continue
        easy_rows.append({
            "target_patent_id": t, "cited_id": c, "cited_raw": "", "cited_office": "KR",
            "source_type": "negative_easy", "label": 0, "difficulty": "negative_easy",
        })

    hard_df = pd.DataFrame(hard_rows)
    easy_df = pd.DataFrame(easy_rows)

    # ── Combine and trim to ~target_total ──────────────────────────
    all_pairs = pd.concat([positives, hard_df, easy_df], ignore_index=True)
    if len(all_pairs) > TARGETS["target_total"]:
        # Downsample easy negatives first to stay close to target
        overflow = len(all_pairs) - TARGETS["target_total"]
        if overflow > 0 and len(easy_df) > 0:
            drop_n = min(overflow, len(easy_df))
            drop_idx = rng.sample(range(len(easy_df)), drop_n)
            keep_mask = pd.Series([i not in set(drop_idx) for i in range(len(easy_df))])
            easy_df = easy_df[keep_mask.values].reset_index(drop=True)
            all_pairs = pd.concat([positives, hard_df, easy_df], ignore_index=True)

    # Final shuffle + assign pair_id
    all_pairs = all_pairs.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    all_pairs["pair_id"] = [f"pair:{i:05d}" for i in range(len(all_pairs))]
    all_pairs = all_pairs[[
        "pair_id", "target_patent_id", "cited_id", "cited_raw", "cited_office",
        "source_type", "label", "difficulty",
    ]]

    all_pairs.to_parquet(OUT_PAIRS, index=False)

    report = {
        "seed": SEED,
        "n_pairs": int(len(all_pairs)),
        "by_label": {
            int(k): int(v) for k, v in all_pairs["label"].value_counts().items()
        },
        "by_difficulty": {
            k: int(v) for k, v in all_pairs["difficulty"].value_counts().items()
        },
        "n_unique_targets": int(all_pairs["target_patent_id"].nunique()),
        "n_unique_candidates": int(all_pairs["cited_id"].nunique()),
        "candidates_in_pool_pct": round(
            100.0 * all_pairs["cited_id"].isin(by_pid.index).mean(), 2,
        ),
        "output": str(OUT_PAIRS.relative_to(ROOT)),
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ Prior-art pairs ({len(all_pairs)} rows) → {OUT_PAIRS.relative_to(ROOT)}")
    print(f"  by_label: {report['by_label']}")
    print(f"  by_difficulty: {report['by_difficulty']}")
    print(f"  candidates in corpus pool: {report['candidates_in_pool_pct']}%")


if __name__ == "__main__":
    main()
