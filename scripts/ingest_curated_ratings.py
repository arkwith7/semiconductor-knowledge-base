#!/usr/bin/env python3
"""Ingest the curated 7,500 3-rater ground-truth ratings + compute inter-rater
agreement (weighted κ, ICC) for the synthetic crowd labels.

Inputs:
  data/experts/curated_ratings_3rater.csv  — 7,500 rows (50 problems × 50 experts × 3 raters)

Outputs:
  data/experts/curated_ratings.parquet     — flat parquet
  data/experts/curated_ratings_pivot.parquet — wide-format (one row per (problem, expert) with rater1/rater2/rater3 columns)
  data/experts/reliability_report.md       — κ/ICC + agreement matrices

This is the synthetic-crowd label track. Its complement is the SIRP examiner-
grounded prior-art pair set (data/patents/prior_art_pairs.parquet). The two are
compared in notebooks/05_synthetic_vs_curated_comparison.ipynb.
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_CSV = ROOT / "data" / "experts" / "curated_ratings_3rater.csv"
OUT_LONG = ROOT / "data" / "experts" / "curated_ratings.parquet"
OUT_PIVOT = ROOT / "data" / "experts" / "curated_ratings_pivot.parquet"
OUT_REPORT_MD = ROOT / "data" / "experts" / "reliability_report.md"
OUT_REPORT_JSON = ROOT / "data" / "experts" / "reliability_report.json"


def cohen_kappa(y1: np.ndarray, y2: np.ndarray, labels: list[int] | None = None) -> float:
    """Compute Cohen's κ for binary/ordinal labels."""
    if labels is None:
        labels = sorted(set(np.concatenate([y1, y2])))
    n = len(y1)
    if n == 0:
        return float("nan")
    obs = float(np.mean(y1 == y2))
    # Marginal probabilities
    p1 = np.array([np.mean(y1 == c) for c in labels])
    p2 = np.array([np.mean(y2 == c) for c in labels])
    exp = float(np.sum(p1 * p2))
    if abs(1.0 - exp) < 1e-12:
        return 1.0 if obs == 1.0 else 0.0
    return (obs - exp) / (1.0 - exp)


def icc_2_1(ratings: np.ndarray) -> float:
    """Compute ICC(2,1) — two-way random, single rater, absolute agreement.

    `ratings` shape: (n_subjects, k_raters).
    """
    n, k = ratings.shape
    if n < 2 or k < 2:
        return float("nan")
    grand_mean = ratings.mean()
    msr = k * ((ratings.mean(axis=1) - grand_mean) ** 2).sum() / (n - 1)  # subject MS
    msc = n * ((ratings.mean(axis=0) - grand_mean) ** 2).sum() / (k - 1)  # rater MS
    mse_num = ((ratings - ratings.mean(axis=1, keepdims=True)
                       - ratings.mean(axis=0, keepdims=True) + grand_mean) ** 2).sum()
    mse = mse_num / ((n - 1) * (k - 1))
    denom = msr + (k - 1) * mse + (k / n) * (msc - mse)
    if abs(denom) < 1e-12:
        return float("nan")
    return (msr - mse) / denom


def fleiss_kappa(matrix: np.ndarray) -> float:
    """Fleiss' κ for `matrix` shape (n_subjects, k_categories) of counts per category."""
    n, k = matrix.shape
    n_per_subject = matrix.sum(axis=1)[0]
    if not np.all(matrix.sum(axis=1) == n_per_subject):
        return float("nan")
    p_j = matrix.sum(axis=0) / (n * n_per_subject)
    p_i = (matrix ** 2).sum(axis=1) - n_per_subject
    p_i = p_i / (n_per_subject * (n_per_subject - 1))
    p_bar = float(p_i.mean())
    pe_bar = float((p_j ** 2).sum())
    if abs(1.0 - pe_bar) < 1e-12:
        return float("nan")
    return (p_bar - pe_bar) / (1.0 - pe_bar)


def main() -> None:
    if not IN_CSV.exists():
        print(f"ERROR: {IN_CSV} not found", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(IN_CSV)
    print(f"loaded {len(df)} rows; columns: {list(df.columns)[:10]}")
    df.to_parquet(OUT_LONG, index=False)

    # Build a (problem_id, expert_id) → list of (evaluator_id, score) pivot
    pivot = (
        df.groupby(["problem_id", "expert_id"])["relevance_score"]
        .agg(list)
        .reset_index(name="scores")
    )
    pivot["n_raters"] = pivot["scores"].apply(len)
    pivot["mean_score"] = pivot["scores"].apply(lambda xs: float(np.mean(xs)) if xs else float("nan"))
    pivot["majority_score"] = pivot["scores"].apply(
        lambda xs: int(np.round(np.mean(xs))) if xs else None
    )
    # Wide format for the modal case (3 raters)
    has_three = pivot[pivot["n_raters"] == 3].copy()
    has_three["rater_1"] = has_three["scores"].apply(lambda xs: xs[0])
    has_three["rater_2"] = has_three["scores"].apply(lambda xs: xs[1])
    has_three["rater_3"] = has_three["scores"].apply(lambda xs: xs[2])
    pivot_out = has_three.drop(columns=["scores"])
    pivot_out.to_parquet(OUT_PIVOT, index=False)

    # Inter-rater reliability — pairwise Cohen's κ + Fleiss' κ + ICC
    pair_kappas = {}
    if len(has_three):
        for a, b in combinations([1, 2, 3], 2):
            y_a = has_three[f"rater_{a}"].to_numpy()
            y_b = has_three[f"rater_{b}"].to_numpy()
            pair_kappas[f"rater_{a}_vs_{b}"] = round(float(cohen_kappa(y_a, y_b)), 4)

    # Fleiss: build count matrix (n_subjects, k_categories)
    labels_sorted = sorted(df["relevance_score"].dropna().unique().tolist())
    label_index = {lab: i for i, lab in enumerate(labels_sorted)}
    fleiss_mat = np.zeros((len(has_three), len(labels_sorted)), dtype=int)
    for row_i, scores in enumerate(has_three["scores"]):
        for s in scores:
            fleiss_mat[row_i, label_index[s]] += 1
    fleiss_k = round(float(fleiss_kappa(fleiss_mat)), 4) if len(has_three) else float("nan")

    # ICC(2,1) on the 3-rater pivot
    icc_input = has_three[["rater_1", "rater_2", "rater_3"]].to_numpy(dtype=float)
    icc_val = round(float(icc_2_1(icc_input)), 4) if len(icc_input) >= 2 else float("nan")

    report = {
        "source": str(IN_CSV.relative_to(ROOT)),
        "n_ratings": int(len(df)),
        "n_subjects_three_raters": int(len(has_three)),
        "n_problems": int(df["problem_id"].nunique()),
        "n_experts": int(df["expert_id"].nunique()),
        "label_scale": labels_sorted,
        "pairwise_cohens_kappa": pair_kappas,
        "fleiss_kappa": fleiss_k,
        "icc_2_1": icc_val,
        "raters_named": sorted(df["evaluator_name"].dropna().unique().tolist()) if "evaluator_name" in df.columns else [],
        "outputs": {
            "long": str(OUT_LONG.relative_to(ROOT)),
            "pivot": str(OUT_PIVOT.relative_to(ROOT)),
        },
        "citation": "Curated ExpDataSet — 3-rater synthetic ratings.",
    }
    OUT_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable MD
    md_lines = [
        "# Curated Synthetic Ratings — Inter-Rater Reliability",
        "",
        "> Source: `data/experts/curated_ratings_3rater.csv` "
        "(7,500 ratings, 50 problems × 50 experts × 3 raters).",
        "> Provenance: curated ExpDataSet — 3-rater synthetic crowd labels.",
        "",
        f"- Subjects with 3 raters: **{report['n_subjects_three_raters']}** / "
        f"{int(report['n_subjects_three_raters'] * 3)} total ratings",
        f"- Label scale: {report['label_scale']}",
        f"- Raters: {', '.join(report['raters_named']) if report['raters_named'] else 'n/a'}",
        "",
        "## Pairwise Cohen's κ",
        "",
        "| pair | κ |",
        "|---|---|",
    ]
    for k, v in pair_kappas.items():
        md_lines.append(f"| {k} | {v:.4f} |")
    md_lines += [
        "",
        f"## Fleiss' κ (3 raters): **{fleiss_k:.4f}**",
        f"## ICC(2,1) — two-way random, single rater, absolute agreement: **{icc_val:.4f}**",
        "",
        "## Interpretation",
        "",
        "- κ < 0.20 — slight; 0.21–0.40 — fair; 0.41–0.60 — moderate; "
        "0.61–0.80 — substantial; > 0.80 — almost perfect (Landis & Koch 1977).",
        "- ICC < 0.50 — poor; 0.50–0.75 — moderate; 0.75–0.90 — good; > 0.90 — excellent (Koo & Li 2016).",
    ]
    OUT_REPORT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"✓ Long ratings  ({len(df)} rows)  → {OUT_LONG.relative_to(ROOT)}")
    print(f"✓ Pivot ratings ({len(pivot_out)} subjects) → {OUT_PIVOT.relative_to(ROOT)}")
    print(f"✓ Reliability report → {OUT_REPORT_MD.relative_to(ROOT)}")
    print(f"  Cohen's κ pairs: {pair_kappas}")
    print(f"  Fleiss' κ = {fleiss_k}, ICC(2,1) = {icc_val}")


if __name__ == "__main__":
    main()
