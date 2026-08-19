"""PathSim 사망 진단 D1/D3 (PLAN-018 §7.6 · 탐색적 · 상류 불변 · test 봉인).

M4 에서 PathSim(w_h)·FeatureCoverage(w_f)가 dev 에서 기여 0. **왜**인지 병목을 분리한다.

- **D1 밀도 vs 깊이:** 질의를 개념 태깅 밀도(질의 개념 수) 사분위로 나눠, PathSim-only(w_h=1) 재랭크와
  P0★ 의 dev family R@100 을 subgroup 별 비교. 고밀도서 PathSim 이 살면 병목=커버리지(ABox 확충),
  안 살면 병목=계층 평면(T-Box 심화 후보).
- **D3 P1 이 PathSim 자리 메우나:** 질의를 "정확 개념겹침이 약한"(near-miss) 정도로 나눠, FeatureCoverage
  포함 P1 이 그 집단에서 B3 대비 이득을 주는지. PathSim 이 노린 near-miss 회수를 임베딩이 대체하는지.

- **경계:** 탐색적 분석(확증 아님·§0.1). qrel 읽음(analysis)·순위는 systems/onto_eval 가 만든다·dev 로만.
CLI: `python -m sdkb_paper.analysis.pathsim_diag [--d1] [--d3]`.
"""
from __future__ import annotations

import argparse

from .. import config
from ..retrieval import systems as S
from ..retrieval.candidate import CandidateMask
from ..retrieval.hybrid import RUN_B3
from ..retrieval.ontology_rerank import OntologyFeatures, _query_features
from .bootstrap import per_query_recall
from .metrics import load_qrel, load_run
from .ontology_eval import component_cache, rerank_from_cache


def _dev_setup(split="dev"):
    import pandas as pd

    from ..collect.bq_family_ir import load_family_map
    fam = load_family_map()
    qrel = load_qrel()
    sp = pd.read_parquet(config.IR_SPLIT)
    keep = set(sp.loc[sp["split"] == split, "doc_id"])
    qrel = {q: p for q, p in qrel.items() if q in keep}
    qids = [q for q, p in qrel.items() if p]
    return fam, qrel, qids


def _quartile_labels(values: dict[str, float]) -> dict[str, str]:
    """질의→값 을 사분위 라벨(Q1..Q4)로. 동값 경계는 numpy 분위수."""
    import numpy as np
    v = np.array(list(values.values()))
    qs = np.quantile(v, [0.25, 0.5, 0.75])
    out = {}
    for q, x in values.items():
        if x <= qs[0]:
            out[q] = "Q1(최저)"
        elif x <= qs[1]:
            out[q] = "Q2"
        elif x <= qs[2]:
            out[q] = "Q3"
        else:
            out[q] = "Q4(최고)"
    return out


def _grouped_recall(run, qrel, fam, labels, k=100):
    pq = per_query_recall(run, qrel, k=k, family=fam)
    groups: dict[str, list[float]] = {}
    for q, r in pq.items():
        groups.setdefault(labels.get(q, "?"), []).append(r)
    return {g: (len(v), sum(v) / len(v)) for g, v in sorted(groups.items())}


def d1_density_vs_depth(k=100):
    """개념 밀도 사분위별 PathSim-only·P0★·B3 R@k. 병목 판별."""
    feats = OntologyFeatures()
    mask = CandidateMask()
    fam, qrel, qids = _dev_setup()
    b3 = load_run(RUN_B3)
    qrows = _query_features(feats)

    # 질의 개념 밀도
    density = {q: len(feats.concepts[qrows[q]]) for q in qids if q in qrows}
    labels = _quartile_labels(density)

    cache = component_cache(feats, mask, b3, qids)
    runs = {
        "B3(text)": rerank_from_cache(cache, 0.0, (1.0, 0.0, 0.0)),
        "PathSim-only(w_h=1)": rerank_from_cache(cache, 1.0, (0.0, 1.0, 0.0)),
        "P0★(sel)": rerank_from_cache(cache, 0.75, (0.5, 0.0, 0.5)),
    }
    print(f"[D1 밀도 vs 깊이 · dev family R@{k}]  질의 개념밀도 사분위")
    import numpy as np
    print(f"  밀도 분포: 평균 {np.mean(list(density.values())):.2f} · "
          f"사분위 {np.quantile(list(density.values()), [.25,.5,.75]).round(2).tolist()}")
    for name, run in runs.items():
        g = _grouped_recall(run, qrel, fam, labels, k)
        cells = " · ".join(f"{grp}:{r:.3f}(n{n})" for grp, (n, r) in g.items())
        print(f"  {name:22} {cells}")
    print("  ▶ 판별: PathSim-only 가 Q4(고밀도)서 B3 근접·상승하면 병목=커버리지 · "
          "전 분위 낮으면 병목=계층 평면")


def d3_p1_fills_pathsim(k=100, tau=0.7):
    """정확 개념겹침이 약한(near-miss) 집단에서 P1(FC 포함)이 B3 대비 이득 주나."""
    from ..retrieval.feature_coverage import FeatureCoverageIndex
    from .ontology_eval import component_cache_p1, rerank_p1
    feats = OntologyFeatures()
    mask = CandidateMask()
    fam, qrel, qids = _dev_setup()
    b3 = load_run(RUN_B3)
    qrows = _query_features(feats)

    # near-miss 척도: 질의 정답과의 평균 정확 개념겹침(낮을수록 exact-concept 로는 안 잡힘)
    # 누출 회피: qrel 은 subgroup 라벨링에만 쓰고 순위엔 미사용(analysis 경계).
    overlap = {}
    for q in qids:
        pos = qrel[q]
        qc = feats.concepts[qrows[q]] if q in qrows else frozenset()
        best = 0.0
        for d in pos:
            dr = feats.row.get(d)
            if dr is not None:
                best = max(best, feats.concept_overlap(qc, feats.concepts[dr]))
        overlap[q] = best
    labels = _quartile_labels(overlap)   # Q1 = 개념겹침 최저 = near-miss

    pool_docs = set(qids)
    for q in qids:
        pool_docs.update([d for d in b3.get(q, []) if mask.is_allowed(q, d)][:S.POOL_K])
    fc = FeatureCoverageIndex(restrict_docs=pool_docs)

    cache_c = component_cache(feats, mask, b3, qids)
    cache_p1 = component_cache_p1(feats, mask, b3, qids, fc)
    ti = [0.5, 0.6, 0.7, 0.8].index(tau)
    runs = {
        "B3(text)": rerank_from_cache(cache_c, 0.0, (1.0, 0.0, 0.0)),
        "P0★(concept+ipc)": rerank_from_cache(cache_c, 0.75, (0.5, 0.0, 0.5)),
        "P1(+FeatureCov)": rerank_p1(cache_p1, ti, 0.75, (0.25, 0.0, 0.25, 0.5)),
    }
    print(f"[D3 P1 이 near-miss 회수 · dev family R@{k} · τ={tau}]  질의-정답 정확개념겹침 사분위")
    for name, run in runs.items():
        g = _grouped_recall(run, qrel, fam, labels, k)
        cells = " · ".join(f"{grp}:{r:.3f}(n{n})" for grp, (n, r) in g.items())
        print(f"  {name:20} {cells}")
    print("  ▶ 판별: Q1(near-miss·개념겹침 최저)서 P1 이 P0★/B3 를 넘으면 임베딩이 PathSim 자리 대체")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d1", action="store_true")
    ap.add_argument("--d3", action="store_true")
    ap.add_argument("--k", type=int, default=100)
    args = ap.parse_args()
    if args.d1:
        d1_density_vs_depth(args.k)
    if args.d3:
        d3_p1_fills_pathsim(args.k)


if __name__ == "__main__":
    main()
