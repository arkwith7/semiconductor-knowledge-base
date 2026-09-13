"""PLAN-005 R0-CAL-2 — V7 순위 계측기의 계약.

(a) 동결 정의에 문턱이 없고, V2 의 FROZEN 은 한 자리도 바뀌지 않았다.
(b) 점수·순위 키·동점 띠의 의미 — 각 순위 키가 실제로 동점을 가른다.
(c) **실패해야 할 입력이 실패한다** — E 합집합 cov 는 항등 검사에 걸리고, NPL 은 코퍼스에 있어도 빠진다.
(d) 추출한 순수 함수가 리팩터 전 인라인 동작과 같다 (산출 JSON 바이트 동일은 5단계 cmp 가 잡는다).
(e) 실물 리포트 — τ 재현 · 봉인 id 0 · 판정 없음. 리포트가 없으면 skip.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import check_leakage as CL  # noqa: E402
from scripts import eval_prior_art_realgt as rg  # noqa: E402
from scripts import report_stage7_remeasure as s7  # noqa: E402
from scripts import report_v7_coverage_rank as v7  # noqa: E402
from scripts import splits  # noqa: E402

REPORT = ROOT / "data" / "reports" / "v7_coverage_rank.json"
S7_REPORT = ROOT / "data" / "reports" / "priorart_stage7_remeasure.json"
needs_report = pytest.mark.skipif(not REPORT.exists(), reason="V7 리포트 없음 — make v7-rank")

#: CAL-2 착수 시점(main 02746c3)의 report_stage7_remeasure.FROZEN — V2 정의·τ·판정은 건드리지 않는다.
S7_FROZEN_SHA256 = "65b7d6394e2e90cad1ef0a0f3fcb77bd20b3168a5b91093211e3577bdc8d0888"


# ── (a) 동결 ──────────────────────────────────────────────────────────────
def test_v2_frozen_is_byte_unchanged():
    blob = json.dumps(s7.FROZEN, sort_keys=True, ensure_ascii=False).encode()
    assert hashlib.sha256(blob).hexdigest() == S7_FROZEN_SHA256
    assert s7.FROZEN["tau"] == 0.6708


def test_frozen_v7_defines_but_has_no_threshold():
    f = v7.FROZEN_V7
    assert f["k"] == 50 and f["verdict"] is None
    assert f["order_key"] == ["score 내림", "|∩| 내림", "|Disc*(d)| 오름 (특이도)", "id 사전순"]
    assert set(f["pools"]) == {"P_corpus", "P_disc", "P_common"} and "주" in f["pools"]["P_common"]
    numeric = {k for k, v in f.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    assert numeric == {"k"}, f"문턱처럼 보이는 수치 키: {numeric - {'k'}}"


def test_scopes_exclude_sealed_splits():
    assert not set(v7.SCOPES) & splits.SEALED and v7.PRIMARY_SPLIT == "dev"


# ── (b) 점수 · 순위 · 동점 띠 ─────────────────────────────────────────────
def _layer():
    fs = frozenset
    profiles = {"q": [fs({"a", "b"}), fs({"c"})]}
    disc = {"d1": fs({"a"}), "d2": fs({"c"}), "d3": fs({"a", "b"}), "d4": fs({"a", "b", "x", "y"}),
            "d5": fs({"z"}), "q": fs({"a", "b", "c"})}
    return s7.Layer("T", profiles, disc, None)


def test_coverage_score_is_profile_max_and_excludes_self_and_zero():
    sc = v7.coverage_scores(_layer(), "q")
    assert sc == {"d1": (0.5, 1), "d2": (1.0, 1), "d3": (1.0, 2), "d4": (1.0, 2)}


def test_coverage_score_respects_pool():
    assert set(v7.coverage_scores(_layer(), "q", pool={"d1", "d3"})) == {"d1", "d3"}


def test_each_order_key_breaks_ties():
    L = _layer()
    sc = v7.coverage_scores(L, "q")
    order = [d for d, _ in sorted(sc.items(), key=lambda it: v7.coverage_sort_key(L)(*it))]
    # d3·d4 는 score·|∩| 동률 → |Disc*| 가 작은 d3 먼저 · d2 는 |∩| 1 이라 뒤 · d1 은 score 0.5 로 끝
    assert order == ["d3", "d4", "d2", "d1"]
    fs = frozenset
    L2 = s7.Layer("T", {"q": [fs({"a"})]}, {"b1": fs({"a"}), "a1": fs({"a"})}, None)
    sc2 = v7.coverage_scores(L2, "q")
    assert [d for d, _ in sorted(sc2.items(), key=lambda it: v7.coverage_sort_key(L2)(*it))] == ["a1", "b1"]


def test_rank_with_ties_groups_are_contiguous_and_id_is_not_part_of_tie():
    fs = frozenset
    L = s7.Layer("T", {"q": [fs({"a"})]}, {"b1": fs({"a"}), "a1": fs({"a"}), "c1": fs({"a", "z"})}, None)
    placed = v7.rank_with_ties(v7.coverage_scores(L, "q"), v7.coverage_sort_key(L), v7.coverage_tie_key(L))
    assert placed == {"a1": (0, 0, 2), "b1": (1, 0, 2), "c1": (2, 2, 1)}


@pytest.mark.parametrize("placed,k,want", [
    (None, 50, {"hit": 0, "exp": 0.0, "best": 0, "worst": 0}),
    ((10, 5, 45), 50, {"hit": 1, "exp": 1.0, "best": 1, "worst": 1}),       # m+g = 50 → 경계 안
    ((55, 50, 10), 50, {"hit": 0, "exp": 0.0, "best": 0, "worst": 0}),      # m = 50 → 경계 밖
    ((48, 45, 10), 50, {"hit": 1, "exp": 0.5, "best": 1, "worst": 0}),      # 경계에 걸침
    ((52, 45, 10), 50, {"hit": 0, "exp": 0.5, "best": 1, "worst": 0}),      # 같은 그룹 · 사전순 운에 밀림
])
def test_tie_band(placed, k, want):
    assert v7.tie_band(placed, k) == want


def test_micro_counts_citations_macro_counts_queries():
    pairs = [{"q": "A", "bucket": "KR", "hit": 1, "exp": 1.0, "best": 1, "worst": 1},
             {"q": "A", "bucket": "KR", "hit": 0, "exp": 0.0, "best": 0, "worst": 0},
             {"q": "B", "bucket": "KR", "hit": 1, "exp": 1.0, "best": 1, "worst": 1},
             {"q": "B", "bucket": "FOREIGN", "hit": 0, "exp": 0.5, "best": 1, "worst": 0}]
    agg = v7.aggregate(pairs)
    assert agg["micro"]["KR"]["hit"] == pytest.approx(2 / 3) and agg["micro"]["KR"]["pairs"] == 3
    assert agg["macro"]["KR"]["hit"] == pytest.approx(0.75) and agg["macro"]["KR"]["queries"] == 2
    assert agg["micro"]["FOREIGN"] == {"pairs": 1, "queries": 1, "hit": 0.0, "exp": 0.5, "best": 1.0, "worst": 0.0}
    assert v7.aggregate([])["micro"]["KR"]["hit"] is None
    assert rg.micro_recall_at_k([(1, "KR"), (60, "KR"), (3, "FOREIGN")]) == {"KR": [1, 2], "FOREIGN": [1, 1]}


def test_tfidf_rank_is_order_of_tfidf_scores_and_pool_restriction_keeps_relative_order():
    texts = ["alpha beta gamma", "beta gamma", "alpha alpha delta", "gamma", "alpha beta"]
    inv, idf, norms = rg.tfidf_index(texts)
    sims = rg.tfidf_scores("alpha beta", inv, idf, norms)
    ranks = rg.tfidf_rank("alpha beta", inv, idf, norms, len(texts))
    placed = v7.rank_with_ties(sims, v7.tfidf_sort_key, v7.tfidf_tie_key)
    assert {di: p[0] + 1 for di, p in placed.items()} == ranks
    pool = {0, 2, 4}
    sub = v7.rank_with_ties({d: s for d, s in sims.items() if d in pool}, v7.tfidf_sort_key, v7.tfidf_tie_key)
    assert sorted(sub, key=lambda d: sub[d][0]) == [d for d in sorted(ranks, key=ranks.get) if d in pool]


# ── (c) 실패해야 할 입력 ──────────────────────────────────────────────────
def test_identity_holds_for_profile_max():
    assert v7.assert_identity(_layer(), {"q"}) == {"queries_checked": 1, "mismatch": 0}


def test_identity_rejects_union_coverage():
    """v3_rows 의 E 합집합 cov 로 바꾸면 d2(프로파일 {c} 충족 · R∀ 소속)가 1/3 이 되어 죽어야 한다."""
    def union_cov(layer, q):
        E = layer.E(q)
        return {d: (len(E & cs) / len(E), len(E & cs)) for d, cs in layer.disc_star.items() if d != q and E & cs}
    with pytest.raises(SystemExit):
        v7.assert_identity(_layer(), {"q"}, score_fn=union_cov)


def _edges():
    return pd.DataFrame({
        "target_patent_id": ["patent:kr_1", "patent:kr_1", "patent:kr_1", "patent:kr_2"],
        "cited_doc_id": ["KR-P-A", "KR-P-NPL", "KR-P-B", "KR-P-A"],
        "source_type": ["examiner", "examiner", "all", "examiner"],
        "is_npl": [False, True, False, False],
    })


def test_npl_is_excluded_even_when_in_corpus():
    edges, cidx = _edges(), {"KR-P-A": 0, "KR-P-NPL": 1, "KR-P-B": 2}
    assert rg.load_examiner_gt(edges, cidx) == {"patent:kr_1": ["KR-P-A"], "patent:kr_2": ["KR-P-A"]}
    # 픽스처가 판별력이 있다 — 필터가 없으면 NPL 이 들어온다
    unfiltered = edges[edges.source_type == "examiner"]
    assert "KR-P-NPL" in set(unfiltered.cited_doc_id)


def test_crosswalk_uses_patent_form_and_dies_when_ambiguous():
    edges = pd.DataFrame({"cited_doc_id": ["KR-P-1", "KR-P-1", "US-P-2"],
                          "cited_id": ["patent:kr_KR1A", "KR-P-1", "patent:us_US2A"]})
    assert v7.corpus_crosswalk(edges, ["KR-P-1", "US-P-2"]) == {"KR-P-1": "kr_KR1A", "US-P-2": "us_US2A"}
    bad = pd.concat([edges, pd.DataFrame({"cited_doc_id": ["US-P-2"], "cited_id": ["patent:us_US2B"]})])
    with pytest.raises(SystemExit):
        v7.corpus_crosswalk(bad, ["KR-P-1", "US-P-2"])
    with pytest.raises(SystemExit):
        v7.corpus_crosswalk(edges, ["JP-P-9"])


# ── (d) 추출 함수 == 리팩터 전 인라인 ─────────────────────────────────────
def test_extracted_gt_loader_matches_pre_refactor_inline():
    edges, cidx = _edges(), {"KR-P-A": 0, "KR-P-NPL": 1, "KR-P-B": 2}
    ex = edges[(edges["source_type"] == "examiner") & (~edges["is_npl"])]      # main 02746c3 의 인라인 그대로
    legacy: dict[str, list[str]] = defaultdict(list)
    for tp, cd in zip(ex["target_patent_id"], ex["cited_doc_id"]):
        if cd in cidx:
            legacy[tp].append(cd)
    got = rg.load_examiner_gt(edges, cidx)
    assert got == dict(legacy) and list(got) == list(legacy)


def test_extracted_micro_recall_matches_pre_refactor_inline():
    ranks = [(1, "KR"), (50, "KR"), (51, "FOREIGN"), (2926, "KR"), (7, "FOREIGN")]
    legacy = {"KR": [0, 0], "FOREIGN": [0, 0]}
    for r, b in ranks:                                                            # main 02746c3 의 인라인 그대로
        legacy[b][1] += 1
        if r <= 50:
            legacy[b][0] += 1
    assert rg.micro_recall_at_k(ranks, k=50) == legacy


# ── (e) 실물 ─────────────────────────────────────────────────────────────
def test_leakage_checker_watches_v7_report():
    assert REPORT in CL.EVAL_REPORTS


@needs_report
def test_report_declares_scope_and_no_verdict():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["instrument_version"] == "R0-CAL-2" and rep["split"] == "dev" and rep["verdict"] is None
    assert rep["split_sha256"] == splits.SPLIT_CSV_SHA256
    assert rep["frozen_v7"] == json.loads(json.dumps(v7.FROZEN_V7, ensure_ascii=False))


@needs_report
def test_report_reproduces_tau_and_identity():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    ic = rep["instrument_checks"]
    assert ic["score_eq1_is_R_all"]["mismatch"] == 0
    assert ic["tau_reproduction"]["tau_reproduced"] == s7.FROZEN["tau"]
    assert ic["tau_reproduction"]["pairs"] == ic["tau_reproduction"]["committed_realgt"]["gt_positives_in_corpus"]


@needs_report
def test_report_has_no_sealed_query_ids():
    sealed = splits.queries_in(sorted(splits.SEALED))
    txt = REPORT.read_text(encoding="utf-8")
    assert not set(CL.DOC_ID_RX.findall(txt)) & sealed


@needs_report
def test_ladder_changes_one_condition_per_rung():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    lad = rep["tau_ladder"]
    assert [r["rung"] for r in lad] == [0, 1, 2, 3]
    n = [r["tfidf"]["micro"]["ALL"]["pairs"] for r in lad]
    assert n[0] >= n[1] >= n[2] and n[2] == n[3]                       # 3칸은 GT 가 아니라 풀만 바꾼다
    assert lad[2]["coverage_rank"]["micro"]["ALL"]["pairs"] == lad[3]["coverage_rank"]["micro"]["ALL"]["pairs"] == n[3]
    assert rep["by_scope_at_P_common"]["all"]["tfidf"] == lad[3]["tfidf"]


@pytest.mark.skipif(not S7_REPORT.exists(), reason="단계 7 리포트 없음")
def test_stage7_limitation_keeps_old_sentence_and_points_to_cal2():
    lim = json.loads(S7_REPORT.read_text(encoding="utf-8"))["limitations"][0]
    assert "비대칭은 τ 를 유리하게 하지 않는다" in lim and "CAL-2 가 이 진술을 코드로 대체했다" in lim
