#!/usr/bin/env python3
"""Build deliverable ③ — 50 technical problems + 25 adversarial regulatory scenarios.

Inputs (run scripts/ingest_rejected_patents.py first):
  data/patents/rejected_patents_meta.parquet

Outputs:
  data/problems.parquet                — 50 stratified-sampled rejected patents
  data/regulatory_scenarios.parquet    — 25 adversarial scenarios derived from
                                         (a) rejection categories and
                                         (b) multi-jurisdiction cited-office combinations
  data/problems_report.json            — sampling distribution + scenario taxonomy

Stratification follows the empirical process_family distribution of SIRP:
  etch 15, deposition 9, metallization 5, general 3, oxidation_diffusion 3,
  photo 3, memory 3, implant 3, materials 2, packaging 2,
  remainder 2  (= 50)

The 25 adversarial scenarios are templated combinations of:
  rejection-type ∈ {Novelty, Inventiveness, ClarityScope, Disclosure, Eligibility}  (5)
  multi-jurisdiction overlap ∈ {KR-only, KR×JP, KR×US, KR×JP×US, JP×US}             (5)
Each (rejection × jurisdiction) pair becomes one scenario template, instantiated
with an actual SIRP patent that matches the cited-office composition.
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
OUT_PROBLEMS = ROOT / "data" / "problems.parquet"
OUT_SCENARIOS = ROOT / "data" / "regulatory_scenarios.parquet"
OUT_REPORT = ROOT / "data" / "problems_report.json"

# Stratified quota for the 50 technical problems.
# Tuned to roughly match SIRP's empirical process_family distribution.
PROBLEM_QUOTA: dict[str, int] = {
    "etch": 15,
    "deposition": 9,
    "metallization": 5,
    "general": 3,
    "oxidation_diffusion": 3,
    "photo": 3,
    "memory": 3,
    "implant": 3,
    "materials": 2,
    "backend_packaging": 2,
    "_remainder": 2,  # any leftover families
}

REJECTION_TYPES = [
    ("Novelty",       "신규성 부정",     "KIPO-29-1"),
    ("Inventiveness", "진보성 부정",     "KIPO-29-2"),
    ("ClarityScope",  "청구범위 불명확", "KIPO-42"),
    ("Disclosure",    "기재불비",        "KIPO-42-3"),
    ("Eligibility",   "발명의 정의 미충족", "KIPO-2"),
]

JURISDICTION_PROFILES = [
    ("KR-only",      ["KR"]),
    ("KR×JP",        ["KR", "JP"]),
    ("KR×US",        ["KR", "US"]),
    ("KR×JP×US",     ["KR", "JP", "US"]),
    ("JP×US",        ["JP", "US"]),
]

SEED = 20260512


def stratified_sample(df: pd.DataFrame, quota: dict[str, int], rng: random.Random) -> pd.DataFrame:
    """Sample `quota[family]` rows per process_family. '_remainder' bucket absorbs leftovers."""
    rows: list[pd.Series] = []
    used_ids: set[str] = set()
    remainder_n = quota.get("_remainder", 0)
    for fam, n in quota.items():
        if fam == "_remainder":
            continue
        pool = df[df["process_family"] == fam]
        take = min(n, len(pool))
        if take == 0:
            continue
        picks = pool.sample(n=take, random_state=rng.randint(0, 2**31 - 1))
        for _, r in picks.iterrows():
            rows.append(r)
            used_ids.add(r["patent_id"])
    # Remainder from any family not yet exhausted
    leftovers = df[~df["patent_id"].isin(used_ids)]
    if remainder_n > 0 and len(leftovers) > 0:
        picks = leftovers.sample(n=min(remainder_n, len(leftovers)),
                                 random_state=rng.randint(0, 2**31 - 1))
        for _, r in picks.iterrows():
            rows.append(r)
    out = pd.DataFrame(rows).reset_index(drop=True)
    return out


def main() -> None:
    if not IN_META.exists():
        print(f"ERROR: {IN_META} not found. Run scripts/ingest_rejected_patents.py first.", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(SEED)
    meta = pd.read_parquet(IN_META)

    # ── 50 problems via stratified sampling ────────────────────────
    problems = stratified_sample(meta, PROBLEM_QUOTA, rng)
    problems = problems.head(50).reset_index(drop=True)  # safety trim

    problems_out = problems.copy()
    problems_out["problem_id"] = [f"prob:{i:03d}" for i in range(len(problems_out))]
    problems_out["statement_ko"] = problems_out.apply(
        lambda r: f"[{r['process_family']}] {r['title']}", axis=1,
    )
    problems_out = problems_out[[
        "problem_id", "patent_id", "application_number", "process_family", "value_chain",
        "primary_ipc", "primary_ipc_4digit", "title", "abstract", "claim1",
        "examination_status", "filing_date", "statement_ko",
        "evidence_document_url",
    ]]
    problems_out.to_parquet(OUT_PROBLEMS, index=False)

    # ── 25 adversarial regulatory scenarios ────────────────────────
    # Compute per-target cited-office signature
    edges = pd.read_parquet(IN_EDGES) if IN_EDGES.exists() else pd.DataFrame()
    if len(edges):
        office_sig = (
            edges.groupby("target_patent_id")["cited_office"]
            .apply(lambda s: tuple(sorted(set(s) - {"UNK", "OTHER"})))
            .to_dict()
        )
    else:
        office_sig = {}

    scenarios: list[dict] = []
    scen_idx = 0
    for rejection_en, rejection_ko, notation in REJECTION_TYPES:
        for jur_label, jur_offices in JURISDICTION_PROFILES:
            jur_set = tuple(sorted(jur_offices))
            # Find a SIRP patent whose cited-office signature ⊇ jur_set
            candidates = [
                pid for pid, sig in office_sig.items()
                if set(jur_set).issubset(set(sig))
            ]
            patent_id = rng.choice(candidates) if candidates else None
            scen_idx += 1
            scenarios.append({
                "scenario_id": f"scen:{scen_idx:03d}",
                "rejection_type": rejection_en,
                "rejection_type_ko": rejection_ko,
                "rejection_notation": notation,
                "jurisdiction_profile": jur_label,
                "jurisdictions": "|".join(jur_offices),
                "anchor_patent_id": patent_id or "",
                "adversarial_intent": (
                    f"{rejection_ko} 사유로 거절된 {jur_label} 다중관할 인용 패턴을 가진 "
                    f"케이스에서 SDKB-Match가 어느 인용을 노출/차단하는지 평가한다. "
                    f"leakage rate 측정 단위."
                ),
            })
            if scen_idx >= 25:
                break
        if scen_idx >= 25:
            break

    scen_df = pd.DataFrame(scenarios)
    scen_df.to_parquet(OUT_SCENARIOS, index=False)

    report = {
        "seed": SEED,
        "n_problems": int(len(problems_out)),
        "problem_quota": PROBLEM_QUOTA,
        "problem_family_distribution": {
            k: int(v) for k, v in problems_out["process_family"].value_counts().items()
        },
        "n_scenarios": int(len(scen_df)),
        "scenario_rejection_distribution": {
            k: int(v) for k, v in scen_df["rejection_type"].value_counts().items()
        },
        "scenario_jurisdiction_distribution": {
            k: int(v) for k, v in scen_df["jurisdiction_profile"].value_counts().items()
        },
        "n_scenarios_with_anchor_patent": int((scen_df["anchor_patent_id"] != "").sum()),
        "outputs": {
            "problems": str(OUT_PROBLEMS.relative_to(ROOT)),
            "scenarios": str(OUT_SCENARIOS.relative_to(ROOT)),
        },
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ Problems   ({len(problems_out)} rows) → {OUT_PROBLEMS.relative_to(ROOT)}")
    print(f"✓ Scenarios  ({len(scen_df)} rows)  → {OUT_SCENARIOS.relative_to(ROOT)}")
    print(f"  problem family dist: {report['problem_family_distribution']}")
    print(f"  scenarios with anchor patent: {report['n_scenarios_with_anchor_patent']}/25")


if __name__ == "__main__":
    main()
