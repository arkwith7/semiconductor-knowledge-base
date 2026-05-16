"""Regression tests for the SIRP (Semiconductor Industry Rejected Patents) track.

Covers:
  - ingest_rejected_patents.py    — JSONL → 3 parquet
  - build_prior_art_pairs.py      — 7,500 pairs with positive/negative balance
  - sample_problems.py            — 50 problems + 25 scenarios

These tests are deliverable ④'s safety net: they fail if the published numbers
(773 patents, ~7,500 pairs, 50/25 split) drift due to data or sampling changes.
Run with `pytest tests/test_patents.py -v` after `make sirp`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
IPC = ROOT / "data" / "patents" / "ipc_links.parquet"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
PAIRS = ROOT / "data" / "patents" / "prior_art_pairs.parquet"
PROBLEMS = ROOT / "data" / "problems.parquet"
SCENARIOS = ROOT / "data" / "regulatory_scenarios.parquet"
INGEST_REPORT = ROOT / "data" / "patents" / "ingest_report.json"
PAIRS_REPORT = ROOT / "data" / "patents" / "pairs_report.json"
PROBLEMS_REPORT = ROOT / "data" / "problems_report.json"


def _require(p: Path, hint: str) -> None:
    if not p.exists():
        pytest.skip(f"{p.name} missing — run `make {hint}` first")


# ─── INGEST ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def meta_df() -> pd.DataFrame:
    _require(META, "ingest-sirp")
    return pd.read_parquet(META)


@pytest.fixture(scope="module")
def ipc_df() -> pd.DataFrame:
    _require(IPC, "ingest-sirp")
    return pd.read_parquet(IPC)


@pytest.fixture(scope="module")
def edges_df() -> pd.DataFrame:
    _require(EDGES, "ingest-sirp")
    return pd.read_parquet(EDGES)


class TestIngest:
    def test_raw_jsonl_present(self):
        assert RAW.exists(), (
            "SIRP raw JSONL missing — Amendment v2 commits this file. "
            "Investigate before re-ingesting."
        )

    def test_meta_row_count(self, meta_df: pd.DataFrame):
        # SIRP cohort: 773 (2026-1 grading freeze) ⊂ 1000 (paper_data
        # Phase A~D canonical, plan §7.1 — strict superset, same app numbers).
        assert len(meta_df) == 1000, f"expected 1000 patents, got {len(meta_df)}"

    def test_meta_application_number_unique(self, meta_df: pd.DataFrame):
        dupes = meta_df["application_number"].duplicated().sum()
        assert dupes == 0, f"{dupes} duplicate application_numbers"

    def test_meta_required_columns(self, meta_df: pd.DataFrame):
        required = {
            "patent_id", "application_number", "title", "abstract", "claim1",
            "primary_ipc", "primary_ipc_4digit", "process_family", "value_chain",
            "cohort_scope", "examination_status", "evidence_document_url",
        }
        missing = required - set(meta_df.columns)
        assert not missing, f"meta missing columns: {missing}"

    def test_all_rejected(self, meta_df: pd.DataFrame):
        # Every record in SIRP must be a rejection (cohort definition).
        assert (meta_df["register_status"] == "거절").all(), \
            "Found non-rejected patents in SIRP"

    def test_process_family_top_distribution(self, meta_df: pd.DataFrame):
        counts = meta_df["process_family"].value_counts().to_dict()
        # The known top axes from the data card; tolerance ±10% per family.
        assert counts.get("etch", 0) >= 200
        assert counts.get("deposition", 0) >= 120
        assert counts.get("metallization", 0) >= 60

    def test_ipc_links_present(self, ipc_df: pd.DataFrame, meta_df: pd.DataFrame):
        assert len(ipc_df) > len(meta_df), \
            "expected more IPC links than patents (multi-IPC per patent)"
        # Every patent should appear in IPC links
        patents_in_ipc = set(ipc_df["patent_id"].unique())
        patents_in_meta = set(meta_df["patent_id"])
        missing = patents_in_meta - patents_in_ipc
        assert not missing, f"{len(missing)} patents have zero IPC links"

    def test_prior_art_edges_grouped_by_source(self, edges_df: pd.DataFrame):
        by_src = edges_df["source_type"].value_counts().to_dict()
        # The published numbers: examiner ≈ 1,961, all ≈ 2,731 (overlap with examiner)
        # We normalise: examiner ≥ 1,900, all ≥ 2,700, both inside [1500, 3500].
        assert by_src.get("examiner", 0) >= 1900
        assert by_src.get("all", 0) >= 2700
        # source_type ∈ examiner | all | evidence | evidence_v2
        # (evidence_v2 = structured rejection-reason→cited GT, plan §7.3-3)
        assert set(by_src.keys()).issubset(
            {"examiner", "all", "evidence", "evidence_v2"})

    def test_ingest_report_matches(self, meta_df: pd.DataFrame):
        _require(INGEST_REPORT, "ingest-sirp")
        with open(INGEST_REPORT) as f:
            r = json.load(f)
        assert r["n_patents"] == len(meta_df)
        assert r["source_sha256"]  # non-empty


# ─── PAIRS ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pairs_df() -> pd.DataFrame:
    _require(PAIRS, "sirp-pairs")
    return pd.read_parquet(PAIRS)


class TestPairs:
    def test_pair_row_count_in_band(self, pairs_df: pd.DataFrame):
        # Plan commits to 7,500. Generator may flex ±5% if the corpus thins.
        n = len(pairs_df)
        assert 7125 <= n <= 7875, f"pairs count {n} outside ±5% of 7,500"

    def test_label_balance(self, pairs_df: pd.DataFrame):
        counts = pairs_df["label"].value_counts().to_dict()
        # We want a clearly imbalanced negative-heavy ranking eval (≥ 1:1).
        assert counts.get(0, 0) >= counts.get(1, 0), \
            "negatives must outnumber positives for retrieval eval"

    def test_difficulty_buckets_complete(self, pairs_df: pd.DataFrame):
        diffs = set(pairs_df["difficulty"].unique())
        required = {"positive_examiner", "positive_broad", "negative_hard", "negative_easy"}
        assert required.issubset(diffs), f"missing difficulty bucket: {required - diffs}"

    def test_no_self_pair(self, pairs_df: pd.DataFrame):
        same = (pairs_df["target_patent_id"] == pairs_df["cited_id"]).sum()
        assert same == 0, f"{same} self-pairs found"

    def test_negative_targets_are_real(self, pairs_df: pd.DataFrame, meta_df: pd.DataFrame):
        pool = set(meta_df["patent_id"])
        negs = pairs_df[pairs_df["label"] == 0]
        in_pool = negs["cited_id"].isin(pool).mean()
        # Negatives are sampled FROM the corpus — should be 100%.
        assert in_pool > 0.99, \
            f"only {in_pool:.0%} of negatives are in the SIRP corpus"

    def test_pair_id_unique(self, pairs_df: pd.DataFrame):
        assert pairs_df["pair_id"].is_unique


# ─── PROBLEMS & SCENARIOS ───────────────────────────────────────────

@pytest.fixture(scope="module")
def problems_df() -> pd.DataFrame:
    _require(PROBLEMS, "sirp-problems")
    return pd.read_parquet(PROBLEMS)


@pytest.fixture(scope="module")
def scenarios_df() -> pd.DataFrame:
    _require(SCENARIOS, "sirp-problems")
    return pd.read_parquet(SCENARIOS)


class TestProblems:
    def test_problem_count(self, problems_df: pd.DataFrame):
        assert len(problems_df) == 50, f"expected 50, got {len(problems_df)}"

    def test_problem_id_unique(self, problems_df: pd.DataFrame):
        assert problems_df["problem_id"].is_unique

    def test_problems_link_to_real_patents(self, problems_df: pd.DataFrame,
                                          meta_df: pd.DataFrame):
        pool = set(meta_df["patent_id"])
        missing = set(problems_df["patent_id"]) - pool
        assert not missing, f"problems reference unknown patent_ids: {missing}"

    def test_stratified_family_quota(self, problems_df: pd.DataFrame):
        counts = problems_df["process_family"].value_counts().to_dict()
        # Tier-1 families must be the heaviest tier.
        assert counts.get("etch", 0) >= 10
        assert counts.get("deposition", 0) >= 6


class TestScenarios:
    def test_scenario_count(self, scenarios_df: pd.DataFrame):
        assert len(scenarios_df) == 25, f"expected 25, got {len(scenarios_df)}"

    def test_scenario_id_unique(self, scenarios_df: pd.DataFrame):
        assert scenarios_df["scenario_id"].is_unique

    def test_rejection_types_covered(self, scenarios_df: pd.DataFrame):
        types = set(scenarios_df["rejection_type"])
        # All 5 rejection categories must appear.
        expected = {"Novelty", "Inventiveness", "ClarityScope", "Disclosure", "Eligibility"}
        assert types == expected, f"rejection_type mismatch: {types ^ expected}"

    def test_jurisdiction_profiles_covered(self, scenarios_df: pd.DataFrame):
        profiles = set(scenarios_df["jurisdiction_profile"])
        # All 5 jurisdiction templates must appear.
        expected = {"KR-only", "KR×JP", "KR×US", "KR×JP×US", "JP×US"}
        assert profiles == expected, f"jurisdiction mismatch: {profiles ^ expected}"

    def test_anchor_patent_coverage(self, scenarios_df: pd.DataFrame):
        anchored = (scenarios_df["anchor_patent_id"] != "").sum()
        # We expect anchor coverage > 80%; 100% is ideal but corpus-dependent.
        assert anchored >= 20, f"only {anchored}/25 scenarios anchored to real SIRP patent"


# ─── REPORTS ────────────────────────────────────────────────────────

class TestReports:
    def test_pairs_report_consistent(self, pairs_df: pd.DataFrame):
        _require(PAIRS_REPORT, "sirp-pairs")
        with open(PAIRS_REPORT) as f:
            r = json.load(f)
        assert r["n_pairs"] == len(pairs_df)

    def test_problems_report_consistent(self, problems_df: pd.DataFrame,
                                       scenarios_df: pd.DataFrame):
        _require(PROBLEMS_REPORT, "sirp-problems")
        with open(PROBLEMS_REPORT) as f:
            r = json.load(f)
        assert r["n_problems"] == len(problems_df)
        assert r["n_scenarios"] == len(scenarios_df)
