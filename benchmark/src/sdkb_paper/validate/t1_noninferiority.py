"""T1 — 검색 비열등성 게이트 (PLAN-018 §5.1 · PLAN-019 W3 · 원고 §4.9).

`1[LB95(ΔR100) > −ε]`. 델타 그래프가 병합돼 순위가 바뀌었을 때, 주지표(family Recall@100)가
사전 동결된 마진 ε 이상 **떨어지지 않았음**을 요구한다. 비열등성 검정의 논리 그대로다:
H₀ = (신 − 구) ≤ −ε · H₁ = 차이 > −ε. ε 은 검정력과 독립하게 사전등록됐다(config.T_EPSILON=0.02).

- **새 통계가 아니다.** 신뢰구간은 `analysis/bootstrap.paired_bootstrap`(질의단위 페어드 10k ·
  seed 고정)이 이미 산출한다. 이 모듈은 **판정만** 한다 — 계산기를 두 벌 두지 않는다.
- **경계 규칙:** LB95 가 정확히 −ε 이면 **불통과**다(부등호는 엄격 > · 원고 §4.9 수식 그대로).
- **전제:** 누출 감사 통과(CLAUDE.md §5 T1 행). 비열등성은 정직한 순위에 대해서만 뜻이 있다.

CLI: `python -m sdkb_paper.validate.t1_noninferiority --new RUN --old RUN [--split dev]`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import config

K_PRIMARY = 100     # 주지표 검토 깊이(F1 · 동결)


def t1_decide(lb95: float, epsilon: float = config.T_EPSILON) -> bool:
    """LB95(Δ) > −ε 인가. 경계값(=−ε)은 불통과."""
    return lb95 > -epsilon


def t1_gate(run_new, run_old, qrel, family=None, k: int = K_PRIMARY,
            epsilon: float = config.T_EPSILON) -> dict:
    """T1 판정 + 근거(Δ·95%CI·표본). run 은 {qid: [doc_id]} · qrel 은 {qid: {doc_id}}."""
    from ..analysis.bootstrap import paired_bootstrap

    b = paired_bootstrap(run_new, run_old, qrel, k=k, family=family)
    return {
        "gate": "T1", "metric": f"family Recall@{k}" if family is not None else f"Recall@{k}",
        "epsilon": epsilon, "delta": b["delta"], "lb95": b["lb95"], "ub95": b["ub95"],
        "mean_new": b["mean_a"], "mean_old": b["mean_b"], "n_queries": b["n_queries"],
        "n_boot": b["n_boot"], "seed": b["seed"],
        "pass": t1_decide(b["lb95"], epsilon),
    }


def format_report(r: dict) -> str:
    verdict = "PASS (비열등)" if r["pass"] else "FAIL (열등 배제 실패)"
    return (
        f"[T1 비열등성] {r['metric']} · ε={r['epsilon']} · 페어드 {r['n_queries']}질의 "
        f"(boot {r['n_boot']}·seed {r['seed']})\n"
        f"  구 {r['mean_old']:.4f} → 신 {r['mean_new']:.4f}   Δ {r['delta']:+.4f}"
        f"  95%CI [{r['lb95']:+.4f}, {r['ub95']:+.4f}]\n"
        f"  판정: LB95 {r['lb95']:+.4f} {'>' if r['pass'] else '≤'} −ε ({-r['epsilon']:+.4f})"
        f"  →  {verdict}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", type=Path, default=None, help="신 버전 run(기본 P1)")
    ap.add_argument("--old", type=Path, default=None, help="구 버전 run(기본 B3)")
    ap.add_argument("--split", choices=["train", "dev", "test", "all"], default="dev")
    ap.add_argument("--k", type=int, default=K_PRIMARY)
    ap.add_argument("--epsilon", type=float, default=config.T_EPSILON)
    ap.add_argument("--document-level", action="store_true",
                    help="family 접기 없이 문서 수준(진단용 · 주지표 아님)")
    args = ap.parse_args()

    from ..analysis.metrics import load_run
    from ..analysis.results_table import _split_qrel, run_path

    qrel = _split_qrel(args.split)
    fam = None
    if not args.document_level:
        from ..collect.bq_family_ir import load_family_map
        fam = load_family_map()
    pnew = args.new or run_path("P1", args.split)
    pold = args.old or run_path("B3_rrf", args.split)
    r = t1_gate(load_run(pnew), load_run(pold), qrel, family=fam, k=args.k, epsilon=args.epsilon)
    print(f"[split={args.split}]  new={pnew.name}  old={pold.name}")
    print(format_report(r))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
