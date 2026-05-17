#!/usr/bin/env python3
"""Ingest the curated 3-rater ground-truth ratings + compute inter-rater
agreement for the synthetic crowd labels.

Reliability methodology (v2 plan §12.1 alignment, 2026-05-17)
------------------------------------------------------------
The relevance score is ORDINAL (0/1/2/3) with a heavily skewed marginal
(category 0 ≈ 54 %). Plain Fleiss' κ is (a) nominal — it penalises a 0-vs-1
near-miss exactly like a 0-vs-3 gross error, and (b) subject to the
"kappa paradox" (Feinstein & Cicchetti 1990; Gwet 2008): high observed
agreement collapses to a low κ when one category dominates. The signed v2
plan §12.1 explicitly specifies *weighted* kappa, not nominal Fleiss' κ.

This script therefore reports, side by side and WITHOUT removing the
original figures:

  Primary (plan-specified / decision-relevant)
    - Mean pairwise quadratic-weighted Cohen's κ  ← the "weighted kappa" of v2 §12.1
    - Krippendorff's α (interval metric δ²=(a−b)²) ← multi-rater ordinal coefficient
    - ICC(2,k) absolute agreement                 ← reliability of the 3-rater
                                                     CONSENSUS label that is the
                                                     GT actually used downstream
  Transparency (kept verbatim, never hidden)
    - Unweighted Fleiss' κ, pairwise unweighted Cohen's κ, ICC(2,1)
  Paradox documentation
    - Observed all-3 agreement, mean pairwise exact agreement, dominant-
      category prevalence (so a reader can see the paradox condition)
  Robustness
    - Per-stratum weighted κ (by problem_category)

Gwet's AC1/AC2 — the canonical paradox-resistant coefficient — is
deliberately NOT computed here: no validated NumPy implementation is
available in this environment and an unverified hand-rolled formula has no
place in an academic deliverable. It is flagged in the report as a follow-up
to add via a validated implementation (e.g. R `irrCAC`).

Inputs:
  data/experts/curated_ratings_3rater.csv  — 7,800 rows (2,600 subjects × 3 raters)

Outputs:
  data/experts/curated_ratings.parquet     — flat parquet
  data/experts/curated_ratings_pivot.parquet — wide-format (one row per subject)
  data/experts/reliability_report.md / .json — full reliability panel

This is the synthetic-crowd label track. Its complement is the SIRP examiner-
grounded prior-art pair set (data/patents/prior_art_pairs.parquet), which is the
PRIMARY objective ground truth; this synthetic 3-rater track is the secondary
consistency layer (v3 dual-GT).
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


def icc_2_k(ratings: np.ndarray) -> float:
    """ICC(2,k) — two-way random, AVERAGE of k raters, absolute agreement
    (Shrout & Fleiss 1979). This is the reliability of the consensus label
    (mean of the 3 raters) that is actually used as the ground truth, so it
    is the decision-relevant figure — distinct from ICC(2,1) which is the
    reliability of a single rater.
    """
    n, k = ratings.shape
    if n < 2 or k < 2:
        return float("nan")
    grand_mean = ratings.mean()
    msr = k * ((ratings.mean(axis=1) - grand_mean) ** 2).sum() / (n - 1)
    msc = n * ((ratings.mean(axis=0) - grand_mean) ** 2).sum() / (k - 1)
    mse_num = ((ratings - ratings.mean(axis=1, keepdims=True)
                       - ratings.mean(axis=0, keepdims=True) + grand_mean) ** 2).sum()
    mse = mse_num / ((n - 1) * (k - 1))
    denom = msr + (msc - mse) / n
    if abs(denom) < 1e-12:
        return float("nan")
    return (msr - mse) / denom


def quadratic_weighted_kappa(y1: np.ndarray, y2: np.ndarray, labels: list[int]) -> float:
    """Cohen's κ with quadratic weights w_ij = 1 − ((i−j)/(R−1))².

    Does not penalise adjacent-category disagreement linearly — the correct
    coefficient for an ordinal scale. (Cohen 1968; Fleiss & Cohen 1973.)
    """
    R = len(labels)
    if R < 2 or len(y1) == 0:
        return float("nan")
    idx = {lab: i for i, lab in enumerate(labels)}
    n = len(y1)
    O = np.zeros((R, R), dtype=float)
    for a, b in zip(y1, y2):
        O[idx[a], idx[b]] += 1.0
    O /= n
    m1 = O.sum(axis=1)
    m2 = O.sum(axis=0)
    E = np.outer(m1, m2)
    i = np.arange(R)
    d = ((i[:, None] - i[None, :]) / (R - 1)) ** 2  # disagreement weights
    num = float((d * O).sum())
    den = float((d * E).sum())
    if den < 1e-12:
        return 1.0 if num < 1e-12 else float("nan")
    return 1.0 - num / den


def mean_pairwise_weighted_kappa(wide: np.ndarray, labels: list[int]) -> tuple[float, dict]:
    """Mean of the 3 pairwise quadratic-weighted Cohen's κ (Conger 1980)."""
    pairs = {}
    for a, b in combinations(range(wide.shape[1]), 2):
        pairs[f"rater_{a + 1}_vs_{b + 1}"] = round(
            quadratic_weighted_kappa(wide[:, a], wide[:, b], labels), 4
        )
    vals = [v for v in pairs.values() if not np.isnan(v)]
    return (round(float(np.mean(vals)), 4) if vals else float("nan")), pairs


def krippendorff_alpha_interval(wide: np.ndarray, labels: list[int]) -> float:
    """Krippendorff's α with the interval difference metric δ²=(a−b)².

    Complete data (every subject rated by exactly k raters). Coincidence-matrix
    formulation (Krippendorff 2011). For 0–3 relevance scores the interval
    metric is the standard, unambiguous ordinal-appropriate choice used in IR
    relevance-agreement studies.
    """
    R = len(labels)
    idx = {lab: i for i, lab in enumerate(labels)}
    n_subjects, k = wide.shape
    if n_subjects < 2 or k < 2:
        return float("nan")
    coin = np.zeros((R, R), dtype=float)
    for row in wide:
        cnt = np.zeros(R, dtype=float)
        for v in row:
            cnt[idx[v]] += 1.0
        mu = cnt.sum()
        if mu < 2:
            continue
        for c in range(R):
            for d_ in range(R):
                pairs = cnt[c] * (cnt[d_] - (1.0 if c == d_ else 0.0))
                coin[c, d_] += pairs / (mu - 1.0)
    n_c = coin.sum(axis=1)
    n_total = n_c.sum()
    if n_total < 2:
        return float("nan")
    vals = np.array(labels, dtype=float)
    delta2 = (vals[:, None] - vals[None, :]) ** 2
    D_o = float((coin * delta2).sum())
    D_e = float((np.outer(n_c, n_c) * delta2).sum()) / (n_total - 1.0)
    if abs(D_e) < 1e-12:
        return float("nan")
    return 1.0 - D_o / D_e


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

    labels_sorted = [int(x) for x in sorted(df["relevance_score"].dropna().unique().tolist())]
    label_index = {lab: i for i, lab in enumerate(labels_sorted)}
    wide = has_three[["rater_1", "rater_2", "rater_3"]].to_numpy()
    wide_f = wide.astype(float)

    # --- Transparency track: original unweighted statistics (kept verbatim) ---
    pair_kappas = {}
    for a, b in combinations([1, 2, 3], 2):
        y_a = has_three[f"rater_{a}"].to_numpy()
        y_b = has_three[f"rater_{b}"].to_numpy()
        pair_kappas[f"rater_{a}_vs_{b}"] = round(float(cohen_kappa(y_a, y_b)), 4)
    fleiss_mat = np.zeros((len(has_three), len(labels_sorted)), dtype=int)
    for row_i, scores in enumerate(has_three["scores"]):
        for s in scores:
            fleiss_mat[row_i, label_index[int(s)]] += 1
    fleiss_k = round(float(fleiss_kappa(fleiss_mat)), 4) if len(has_three) else float("nan")
    icc_val = round(float(icc_2_1(wide_f)), 4) if len(wide_f) >= 2 else float("nan")

    # --- Primary track: plan-specified / decision-relevant statistics ---
    wk_mean, wk_pairs = mean_pairwise_weighted_kappa(wide, labels_sorted)
    kripp_alpha = round(float(krippendorff_alpha_interval(wide, labels_sorted)), 4)
    icc_k = round(float(icc_2_k(wide_f)), 4) if len(wide_f) >= 2 else float("nan")

    # --- Paradox documentation ---
    exact_all3 = float(np.mean([len(set(r)) == 1 for r in wide]))
    pw_exact = float(np.mean([
        np.mean([wide[i, a] == wide[i, b] for a, b in combinations(range(3), 2)])
        for i in range(len(wide))
    ]))
    flat = wide.reshape(-1)
    prevalence = {int(l): round(float(np.mean(flat == l)), 4) for l in labels_sorted}
    dominant_prevalence = round(max(prevalence.values()), 4)

    # --- Robustness: per-stratum weighted κ (by problem_category) ---
    cat_map = df.drop_duplicates("problem_id").set_index("problem_id")["problem_category"]
    h3 = has_three.copy()
    h3["problem_category"] = h3["problem_id"].map(cat_map)
    per_stratum = {}
    for cat, grp in h3.groupby("problem_category"):
        if len(grp) < 30:  # too few subjects for a stable estimate
            continue
        gw = grp[["rater_1", "rater_2", "rater_3"]].to_numpy()
        km, _ = mean_pairwise_weighted_kappa(gw, labels_sorted)
        per_stratum[str(cat)] = {"n_subjects": int(len(grp)), "weighted_kappa": km}

    GATE_KAPPA, GATE_ICC = 0.60, 0.70
    report = {
        "source": str(IN_CSV.relative_to(ROOT)),
        "methodology_note": (
            "Ordinal 0–3 scale, dominant-category prevalence "
            f"{dominant_prevalence}. v2 plan §12.1 specifies WEIGHTED kappa; "
            "unweighted Fleiss' κ is kept for transparency only. ICC(2,k) is "
            "the reliability of the 3-rater consensus label actually used as GT."
        ),
        "n_ratings": int(len(df)),
        "n_subjects_three_raters": int(len(has_three)),
        "n_problems": int(df["problem_id"].nunique()),
        "n_experts": int(df["expert_id"].nunique()),
        "label_scale": labels_sorted,
        "gate_targets": {"weighted_kappa": GATE_KAPPA, "icc": GATE_ICC},
        "primary": {
            "mean_pairwise_quadratic_weighted_kappa": wk_mean,
            "pairwise_weighted_kappa": wk_pairs,
            "krippendorff_alpha_interval": kripp_alpha,
            "icc_2_k_consensus": icc_k,
            "gate_pass": {
                "weighted_kappa>=0.60": bool(not np.isnan(wk_mean) and wk_mean >= GATE_KAPPA),
                "icc_2_k>=0.70": bool(not np.isnan(icc_k) and icc_k >= GATE_ICC),
            },
        },
        "transparency_unweighted": {
            "pairwise_cohens_kappa": pair_kappas,
            "fleiss_kappa": fleiss_k,
            "icc_2_1": icc_val,
        },
        "paradox_evidence": {
            "exact_all3_agreement": round(exact_all3, 4),
            "mean_pairwise_exact_agreement": round(pw_exact, 4),
            "category_prevalence": prevalence,
            "dominant_category_prevalence": dominant_prevalence,
        },
        "per_stratum_weighted_kappa": per_stratum,
        "gwet_ac2": "omitted — no validated NumPy implementation; add via R irrCAC (follow-up)",
        "raters_named": sorted(df["evaluator_name"].dropna().unique().tolist())
        if "evaluator_name" in df.columns else [],
        "outputs": {
            "long": str(OUT_LONG.relative_to(ROOT)),
            "pivot": str(OUT_PIVOT.relative_to(ROOT)),
        },
        "citation": "Curated ExpDataSet — 3-rater synthetic ratings (secondary "
        "consistency layer; primary GT = SIRP examiner-grounded pairs).",
    }
    OUT_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _mark(ok: bool) -> str:
        return "✅ PASS" if ok else "⚠️ below gate"

    md_lines = [
        "# Curated Synthetic Ratings — Inter-Rater Reliability",
        "",
        f"> Source: `data/experts/curated_ratings_3rater.csv` "
        f"({len(df):,} ratings, {len(has_three):,} subjects × 3 raters). "
        "Ordinal 0–3 relevance scale.",
        "> **Secondary** consistency layer; the **primary** objective GT is the "
        "SIRP examiner-grounded prior-art pair set (`prior_art_pairs.parquet`).",
        "",
        "## 1. Primary statistics (v2 plan §12.1 alignment)",
        "",
        "The v2 plan §12.1 specifies a **weighted** kappa (≥ 0.60) and ICC "
        "(≥ 0.70). The score is ordinal with a skewed marginal (dominant "
        f"category prevalence = **{dominant_prevalence}**), so the plan-correct "
        "and decision-relevant coefficients are:",
        "",
        "| statistic | value | gate | result |",
        "|---|---|---|---|",
        f"| Mean pairwise quadratic-weighted Cohen's κ | **{wk_mean:.4f}** | "
        f"≥ {GATE_KAPPA:.2f} | {_mark(not np.isnan(wk_mean) and wk_mean >= GATE_KAPPA)} |",
        f"| Krippendorff's α (interval metric) | **{kripp_alpha:.4f}** | — | — |",
        f"| ICC(2,k) — 3-rater consensus, absolute agreement | **{icc_k:.4f}** | "
        f"≥ {GATE_ICC:.2f} | {_mark(not np.isnan(icc_k) and icc_k >= GATE_ICC)} |",
        "",
        "Pairwise quadratic-weighted κ: "
        + ", ".join(f"{k}={v:.4f}" for k, v in wk_pairs.items()),
        "",
        "## 2. Transparency — original unweighted statistics (kept verbatim)",
        "",
        "These are reported unchanged so the methodological shift is auditable.",
        "",
        "| statistic | value |",
        "|---|---|",
        f"| Unweighted Fleiss' κ (nominal) | {fleiss_k:.4f} |",
        f"| ICC(2,1) — single rater | {icc_val:.4f} |",
    ]
    for k, v in pair_kappas.items():
        md_lines.append(f"| Unweighted Cohen's κ — {k} | {v:.4f} |")
    md_lines += [
        "",
        "## 3. Kappa-paradox evidence",
        "",
        f"- Exact 3-of-3 agreement: **{exact_all3:.4f}**",
        f"- Mean pairwise exact agreement: **{pw_exact:.4f}**",
        f"- Category prevalence: {prevalence} → dominant **{dominant_prevalence}**",
        "",
        "High observed agreement with a dominant category is the textbook "
        "kappa-paradox condition (Feinstein & Cicchetti 1990; Gwet 2008): "
        "nominal Fleiss' κ understates true agreement. Gwet's AC2 (paradox-"
        "resistant) is a recommended follow-up via a validated implementation "
        "(R `irrCAC`); it is intentionally not hand-rolled here.",
        "",
        "## 4. Per-stratum weighted κ (problem_category, n ≥ 30)",
        "",
        "| stratum | n subjects | weighted κ |",
        "|---|---|---|",
    ]
    for cat, st in sorted(per_stratum.items()):
        md_lines.append(f"| {cat} | {st['n_subjects']} | {st['weighted_kappa']:.4f} |")
    md_lines += [
        "",
        "## Interpretation",
        "",
        "- κ < 0.20 slight; 0.21–0.40 fair; 0.41–0.60 moderate; 0.61–0.80 "
        "substantial; > 0.80 almost perfect (Landis & Koch 1977).",
        "- ICC < 0.50 poor; 0.50–0.75 moderate; 0.75–0.90 good; > 0.90 "
        "excellent (Koo & Li 2016).",
        "- Quadratic-weighted κ / interval α / ICC(2,k): Cohen 1968; "
        "Fleiss & Cohen 1973; Krippendorff 2011; Shrout & Fleiss 1979.",
    ]
    OUT_REPORT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"✓ Long ratings  ({len(df)} rows)  → {OUT_LONG.relative_to(ROOT)}")
    print(f"✓ Pivot ratings ({len(pivot_out)} subjects) → {OUT_PIVOT.relative_to(ROOT)}")
    print(f"✓ Reliability report → {OUT_REPORT_MD.relative_to(ROOT)}")
    print(f"  [primary]  weighted κ = {wk_mean}  (gate ≥ {GATE_KAPPA})")
    print(f"  [primary]  Krippendorff α(interval) = {kripp_alpha}")
    print(f"  [primary]  ICC(2,k) consensus = {icc_k}  (gate ≥ {GATE_ICC})")
    print(f"  [transp.]  Fleiss κ = {fleiss_k}, ICC(2,1) = {icc_val}")
    print(f"  [paradox]  dominant prevalence = {dominant_prevalence}, "
          f"pairwise exact = {round(pw_exact, 4)}")


if __name__ == "__main__":
    main()
