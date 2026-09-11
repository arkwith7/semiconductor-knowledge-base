"""PLAN-005 단계 7 — 재측정기의 계약.

(a) 동결 상수가 계획서와 같다 — 결과를 본 뒤 문턱을 만지면 여기서 걸린다.
(b) Reach 두 정의의 의미 (합성 층 · 확장 방향 · 자기 제외).
(c) **실패해야 할 입력이 실패한다** — 흔한 개념을 모든 문헌에 붙인 개시집합은 (iii) 에 걸리고,
    τ 아래 값은 (ii) 에 걸리며, CI 가 0 을 품으면 (i) 에 걸린다. V4 는 5pt 넘는 저하가 걸린다.
(d) 실물 리포트 — 단계 1 재현 · 입력 신선도 · 동일성 검사. 리포트가 없으면 skip.
(e) V4 질의 세트 sha 동결.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import report_stage7_remeasure as s7  # noqa: E402

REPORT = ROOT / "data" / "reports" / "priorart_stage7_remeasure.json"
V4_SHA = ROOT / "data" / "queries" / "v4" / "v4_paraphrase_queries.sha256"
needs_report = pytest.mark.skipif(not REPORT.exists(), reason="단계 7 리포트 없음 — make stage7-remeasure")


# ── (a) 동결 상수 ───────────────────────────────────────────────────────
def test_frozen_constants_match_plan():
    f = s7.FROZEN
    assert f["tau"] == 0.6708 and "tfidf_KR" in f["tau_source"]
    assert f["S_primary"] == 50 and f["S_all"] == [50, 100, 1000, "inf"]
    assert f["primary_reach"] == "R∀"
    assert f["bootstrap_B"] == 10000 and f["seed"] == 20260909 and f["ci"] == 0.95
    assert f["v4_drop_max"] == 0.05 and f["v4_quartile_drop_max"] == 0.10
    assert f["baseline_commit"] == "460806d" and f["baseline_parquet_sha256_prefix"] == "16f8300dbf15"
    assert "§29②" in f["v3_gate_stratum"]


# ── (b) Reach 의미 ─────────────────────────────────────────────────────
def _layer(expansion=None):
    fs = frozenset
    profiles = {"q": [fs({"a", "b"})]}
    disc = {"d1": fs({"a", "b"}), "d2": fs({"a"}), "d3": fs({"f"}), "q": fs({"a", "b"})}
    return s7.Layer("T", profiles, disc, expansion)


def test_reach_exist_is_any_shared_concept_and_excludes_self():
    L = _layer()
    assert L.reach_exist("q") == {"d1", "d2"}


def test_reach_all_requires_every_essential_concept():
    L = _layer()
    assert L.reach_all("q") == {"d1"}


def test_expansion_is_depth_one_from_disclosed_broader_to_covered():
    """d3 는 f 만 개시 · b coveredBy f 이면 Disc*(d3) ∋ b — a 는 없으므로 R∀ 에는 여전히 못 든다."""
    L = _layer(expansion={"f": {"b"}})
    assert "b" in L.disc_star["d3"] and "a" not in L.disc_star["d3"]
    assert L.reach_exist("q") == {"d1", "d2", "d3"}
    assert L.reach_all("q") == {"d1"}
    L2 = _layer(expansion={"f": {"a", "b"}})
    assert L2.reach_all("q") == {"d1", "d3"}


def test_per_query_needs_profile_and_target():
    L = _layer()
    recs = s7.per_query(L, {"q": {"d1", "zz"}, "nq": {"d1"}, "q2": {"zz"}})
    assert set(recs) == {"q"} and recs["q"]["n_target"] == 1
    assert recs["q"]["all"] == {"reach": 1, "hit": True}


# ── (c) 실패해야 할 입력 ────────────────────────────────────────────────
def _recs(n: int, hit_fit: int, reach: int, kr=True):
    return {f"q{i}": {"n_target": 1, "target_kr": kr, "target_us": False,
                      "exist": {"reach": reach, "hit": i < hit_fit},
                      "all": {"reach": reach, "hit": i < hit_fit}} for i in range(n)}


def test_v2_passes_on_synthetic_good_input():
    A = _recs(200, 20, 10)
    C = _recs(200, 160, 10)
    v = s7.v2_verdict(A, C)
    assert v["pass"] and v["failed_conditions"] == []


def test_v2_fails_specificity_when_reach_inflates():
    """흔한 개념 하나를 모든 문헌에 붙이면 도달률은 오르지만 |Reach| 중앙값이 커진다 → (iii) FAIL."""
    A = _recs(200, 20, 10)
    C = _recs(200, 160, 40)
    v = s7.v2_verdict(A, C)
    assert not v["pass"] and "iii" in v["failed_conditions"]


def test_v2_fails_tau_when_kr_layer_is_below_control():
    A = _recs(200, 20, 10)
    C = _recs(200, 100, 10)           # 0.50 < 0.6708
    v = s7.v2_verdict(A, C)
    assert "ii" in v["failed_conditions"] and not v["pass"]


def test_v2_fails_significance_when_ci_contains_zero():
    A = _recs(200, 150, 10)
    C = dict(A); C = {q: {**r, "all": {"reach": 10, "hit": (i < 152)}} for i, (q, r) in enumerate(A.items())}
    v = s7.v2_verdict(A, C)
    assert "i" in v["failed_conditions"]


def test_bootstrap_is_deterministic_and_paired():
    a, c = [0] * 50 + [1] * 50, [0] * 30 + [1] * 70
    r1 = s7.paired_bootstrap(a, c, 2000, 7, 0.95)
    r2 = s7.paired_bootstrap(a, c, 2000, 7, 0.95)
    assert r1 == r2 and abs(r1["delta"] - 0.2) < 1e-12 and r1["ci"][0] > 0


def test_mcnemar_counts_discordant_only():
    m = s7.mcnemar_exact([1, 1, 0, 0], [1, 0, 1, 1])
    assert (m["c_only"], m["a_only"]) == (2, 1) and 0 < m["p"] <= 1


def test_v3_gate_uses_inventive_step_stratum_only():
    rows = [{"q": f"q{i}", "nE": 3, "n_cited": 2, "best_single": .5, "best_pair": .5 + .2 * (i % 2),
             "delta": .2 * (i % 2), "stratum": "§29②-only"} for i in range(60)]
    rows += [{"q": "n1", "nE": 3, "n_cited": 2, "best_single": .5, "best_pair": .5, "delta": 0.0, "stratum": "§29①-only"}]
    v = s7.v3_verdict(rows, rows)
    assert v["gate_queries"] == 60 and v["pass"]
    flat = [{**r, "best_pair": r["best_single"], "delta": 0.0} for r in rows]
    assert not s7.v3_verdict(flat, flat)["pass"]


def test_v4_verdict_flags_missing_conj_and_catches_drop():
    base = {"by_variant": {"claim": {"hit_rate": .90}, "L1": {"hit_rate": .89}, "L2": {"hit_rate": .88},
                           "L3": {"hit_rate": .87}},
            "llm_jaccard_quartiles": {"Q1_먼": {"hit_rate": .86}, "Q4_가까운": {"hit_rate": .90}}}
    v = s7.v4_verdict(base)
    assert v["pass"] is None and "R∀" in v["status"]
    for var in ("claim", "L1", "L2", "L3"):
        base["by_variant"][var]["conj_disclosure"] = {"hit_rate": base["by_variant"][var]["hit_rate"]}
    assert s7.v4_verdict(base)["pass"] is True
    base["by_variant"]["L3"]["conj_disclosure"]["hit_rate"] = .80          # 10pt 저하
    assert s7.v4_verdict(base)["pass"] is False
    assert s7.v4_verdict(None)["pass"] is None


# ── (d) 실물 리포트 ─────────────────────────────────────────────────────
@needs_report
def test_report_reproduces_stage1_and_describes_current_files():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["stage1_reproduction"]["ok"] is True, rep["stage1_reproduction"]
    for rel, sha in rep["inputs"].items():
        if rel == "baseline_parquet_sha256":
            assert sha.startswith(s7.FROZEN["baseline_parquet_sha256_prefix"])
        elif rel.startswith("layer_parquet_sha256["):
            continue                                   # git 소급·추가 층의 parquet — 저장소 경로가 아니다
        elif sha is not None:
            assert sha == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), f"{rel} 가 리포트 이후 바뀌었다"
    ident = rep["identity_check_vs_abox_report"]
    for k in ("profiles", "disclosures", "essential_links", "covered_by_pairs", "bound_concepts"):
        assert ident[k][0] == ident[k][1], k
    assert rep["frozen"] == s7.FROZEN
    assert rep["descriptive"]["Q_A_and_Q_C"] == rep["descriptive"]["Q"]["L_A"]      # Q_A ⊂ Q_C (2단계 실측)


@needs_report
def test_report_verdict_is_consistent_with_its_own_numbers():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    v2 = rep["verdict"]["V2"]
    assert v2["pass"] == (v2["failed_conditions"] == [])
    assert v2["ii_tau"]["pass"] == (v2["ii_tau"]["SPR_all@50_KR_C"] >= s7.FROZEN["tau"])
    assert v2["iii_specificity"]["pass"] == (
        v2["iii_specificity"]["reach_all_median_C"] <= v2["iii_specificity"]["reach_all_median_A"])


# ── (e) V4 질의 세트 동결 ───────────────────────────────────────────────
def test_v4_query_set_is_frozen():
    expected = V4_SHA.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256((V4_SHA.parent / "v4_paraphrase_queries.parquet").read_bytes()).hexdigest()
    assert actual == expected == "cda3d6679859ec491c1971fe2ea27bed3c36e702fa0acb9a97e5e0b2344fea68"
