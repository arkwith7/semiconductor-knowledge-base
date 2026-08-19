"""페어드 부트스트랩 (PLAN-018 §6 · F4 · 원고 §5.2).

두 시스템의 주지표(family-level Recall@100) 차이를 **질의 단위 페어드 부트스트랩**(10,000회, 95% CI)로
검정한다. T1 비열등성(LB95(ΔR100) > −ε)과 B0–B3 성능차의 신뢰구간을 지지한다. 시드는 `config.SEED`
고정(F16) — 같은 run·qrel → 같은 CI.

- 페어드 = 같은 질의 표본에서 A·B 를 함께 평가해 질의난이도 상관을 제거한다.
- 지표는 질의별 스칼라(recall@k)로 환원해 부트스트랩 — family 접힘은 지표 계산에 이미 반영.

CLI: `python -m sdkb_paper.analysis.bootstrap --a RUN_A --b RUN_B [--k 100] [--family]`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .. import config
from .metrics import _fold, load_qrel, load_run


def per_query_recall(
    run: dict[str, list[str]],
    qrel: dict[str, set[str]],
    k: int = 100,
    family: dict[str, str] | None = None,
) -> dict[str, float]:
    """질의별 Recall@k (정답≥1 질의만). family 주면 fold-then-cut family 수준."""
    if family is not None:
        qrel = {q: {family.get(d, d) for d in pos} for q, pos in qrel.items()}
    out: dict[str, float] = {}
    for qid, pos in qrel.items():
        if not pos:
            continue
        ranked = _fold(run.get(qid, []), family) if family is not None else run.get(qid, [])
        hit = len(set(ranked[:k]) & pos)
        out[qid] = hit / len(pos)
    return out


def per_query_metric(
    run: dict[str, list[str]],
    qrel: dict[str, set[str]],
    metric: str = "recall",
    k: int = 100,
    family: dict[str, str] | None = None,
) -> dict[str, float]:
    """질의별 스칼라 지표 — recall@k · ndcg@20 · mrr@k · bpref.

    주지표(recall)와 **같은 페어드 부트스트랩 절차**를 보조지표에도 쓰기 위한 일반화다(원고 §5.1
    보조지표). 지표 정의는 metrics.py 가 정본 — 여기서 다시 정의하지 않는다.
    """
    if metric == "recall":
        return per_query_recall(run, qrel, k, family)
    from .metrics import NDCG_K, _fold, bpref, ndcg_at_k

    if family is not None:
        qrel = {q: {family.get(d, d) for d in pos} for q, pos in qrel.items()}
    out: dict[str, float] = {}
    for qid, pos in qrel.items():
        if not pos:
            continue
        ranked = _fold(run.get(qid, []), family) if family is not None else run.get(qid, [])
        if metric == "ndcg":
            out[qid] = ndcg_at_k(ranked, pos, NDCG_K)
        elif metric == "bpref":
            out[qid] = bpref(ranked, pos)
        elif metric == "mrr":
            out[qid] = next((1.0 / i for i, d in enumerate(ranked[:k], 1) if d in pos), 0.0)
        else:
            raise ValueError(f"알 수 없는 지표: {metric}")
    return out


def paired_bootstrap(
    run_a: dict[str, list[str]],
    run_b: dict[str, list[str]],
    qrel: dict[str, set[str]],
    k: int = 100,
    family: dict[str, str] | None = None,
    n: int = 10000,
    seed: int = config.SEED,
    metric: str = "recall",
) -> dict:
    """A−B 의 평균 지표 차이와 95% CI (질의 단위 페어드). 기본 지표 = 주지표 Recall@k."""
    import numpy as np

    ra = per_query_metric(run_a, qrel, metric, k, family)
    rb = per_query_metric(run_b, qrel, metric, k, family)
    qids = sorted(set(ra) & set(rb))       # 두 시스템 공통 평가질의(페어드)
    a = np.array([ra[q] for q in qids])
    b = np.array([rb[q] for q in qids])
    m = len(qids)
    diff = a - b

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, m, size=(n, m))
    boot = diff[idx].mean(axis=1)          # 각 리샘플의 평균 차이
    lb, ub = np.percentile(boot, [2.5, 97.5])
    # 양측 부트스트랩 p (H0: Δ=0): 부호 반대편 꼬리 비율 ×2. Holm 보정 입력(ablation).
    p_two = 2.0 * min(float((boot <= 0).mean()), float((boot >= 0).mean()))
    return {
        "k": k, "level": "family" if family is not None else "document", "n_queries": m,
        "mean_a": float(a.mean()), "mean_b": float(b.mean()), "delta": float(diff.mean()),
        "lb95": float(lb), "ub95": float(ub), "p_two_sided": min(p_two, 1.0),
        "n_boot": n, "seed": seed,
        "win": int((diff > 0).sum()), "loss": int((diff < 0).sum()), "tie": int((diff == 0).sum()),
    }


def _fmt(r: dict) -> str:
    return (
        f"[{r['level']} · Recall@{r['k']} · 페어드 {r['n_queries']}질의 · boot {r['n_boot']}·seed {r['seed']}]\n"
        f"  mean_A {r['mean_a']:.4f}  mean_B {r['mean_b']:.4f}  Δ(A−B) {r['delta']:+.4f}"
        f"  95%CI [{r['lb95']:+.4f}, {r['ub95']:+.4f}]\n"
        f"  질의 승/패/동 {r['win']}/{r['loss']}/{r['tie']}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True, help="시스템 A run")
    ap.add_argument("--b", type=Path, required=True, help="시스템 B run")
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--family", action="store_true", help="family 수준(F1)")
    ap.add_argument("--split", choices=["train", "dev", "test", "all"], default="dev")
    args = ap.parse_args()

    qrel = load_qrel()
    if args.split != "all":
        import pandas as pd
        sp = pd.read_parquet(config.IR_SPLIT)
        keep = set(sp.loc[sp["split"] == args.split, "doc_id"])
        qrel = {q: pos for q, pos in qrel.items() if q in keep}
        if args.split == "test":
            print("⚠️  test 개봉 — 최종 비교 전이면 사전등록 위반")
    fam = None
    if args.family:
        from ..collect.bq_family_ir import load_family_map
        fam = load_family_map()
    r = paired_bootstrap(load_run(args.a), load_run(args.b), qrel, k=args.k, family=fam)
    print(f"[split={args.split}]")
    print(_fmt(r))


if __name__ == "__main__":
    main()
