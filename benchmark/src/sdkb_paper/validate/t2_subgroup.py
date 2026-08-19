"""T2 — 하위집단 안전성 게이트 (PLAN-018 §5.1 · PLAN-019 W3 · 원고 §4.9).

`1[max_s Drop_s < δ]`. 전체 성능이 유지·개선돼도 **국소 회귀**가 δ 이상이면 승인하지 않는다.
사전 지정 축은 세 개다(config.T2_DIMS): 정답 언어 구성(KR/외국) · 공정군 · 거절근거.

- **차단 규칙의 표본 조건:** 질의 수 n < `config.T2_MIN_N`(=20)인 집단은 **차단에 쓰지 않는다**
  (원고 §4.9 "작은 하위집단은 최소 질의 수를 충족할 때만"). 표에는 남기되 판정에서 뺀다.
- **신뢰집단이 하나도 없으면** 게이트는 회귀를 *증명하지도 반증하지도* 못한다 — 통과로 두되
  `undetermined=True` 로 표시하고 보고서에 명시한다. 조용한 초록불을 만들지 않는다.
- **새 통계가 아니다.** 집단별 R@k 와 drop 은 `analysis/subgroup.compare` 가 이미 낸다.
  이 모듈은 여러 축의 max 를 취해 **판정만** 한다.

CLI: `python -m sdkb_paper.validate.t2_subgroup --new RUN --old RUN [--split dev]`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import config

K_PRIMARY = 100


def t2_decide(max_drop: float | None, delta: float = config.T_DELTA) -> bool:
    """max drop < δ 인가. 경계값(=δ)은 불통과. max_drop=None(신뢰집단 없음)은 통과·미결."""
    if max_drop is None:
        return True
    return max_drop < delta


def t2_gate(run_new, run_old, qrel, family, labels, dims=config.T2_DIMS,
            k: int = K_PRIMARY, delta: float = config.T_DELTA,
            min_n: int = config.T2_MIN_N) -> dict:
    """축별 max drop 을 모아 T2 판정. labels 는 `analysis.subgroup.query_labels` 산출."""
    from ..analysis.subgroup import compare

    per_dim, worst, worst_where = [], None, None
    for dim in dims:
        res = compare(run_new, run_old, qrel, family, labels, dim, k)
        reliable = [r for r in res["rows"] if r["n"] >= min_n]
        dim_max = max((r["drop"] for r in reliable), default=None)
        top = max(reliable, key=lambda r: r["drop"], default=None)
        per_dim.append({"dim": dim, "max_drop": dim_max, "n_reliable": len(reliable),
                        "worst_group": top["group"] if top else None,
                        "rows": res["rows"]})
        if dim_max is not None and (worst is None or dim_max > worst):
            worst, worst_where = dim_max, (dim, top["group"] if top else None)
    return {
        "gate": "T2", "metric": f"family Recall@{k}", "delta": delta, "min_n": min_n,
        "dims": per_dim, "max_drop": worst,
        "worst": {"dim": worst_where[0], "group": worst_where[1]} if worst_where else None,
        "undetermined": worst is None,
        "pass": t2_decide(worst, delta),
    }


def format_report(r: dict) -> str:
    from ..analysis.subgroup import GROUP_LABELS

    lines = [f"[T2 하위집단 안전성] {r['metric']} · δ={r['delta']} · "
             f"차단 최소표본 n≥{r['min_n']}"]
    for d in r["dims"]:
        if d["max_drop"] is None:
            lines.append(f"  · {d['dim']:<12} 신뢰집단 없음(n<{r['min_n']}) — 판정 불가")
            continue
        g = GROUP_LABELS.get(d["worst_group"], d["worst_group"])
        lines.append(f"  · {d['dim']:<12} max drop {d['max_drop']:+.4f}"
                     f"  (최악 집단: {g} · 신뢰집단 {d['n_reliable']}개)")
    if r["undetermined"]:
        lines.append("  판정: 신뢰 하위집단 0 → 국소회귀를 검증하지 못함 (통과이되 **미결**)")
    else:
        w = r["worst"]
        lines.append(f"  판정: max drop {r['max_drop']:+.4f} "
                     f"{'<' if r['pass'] else '≥'} δ ({r['delta']})"
                     f"  [{w['dim']}/{w['group']}]  →  "
                     f"{'PASS (국소회귀 없음)' if r['pass'] else 'FAIL (국소회귀)'}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", type=Path, default=None, help="신 버전 run(기본 P1)")
    ap.add_argument("--old", type=Path, default=None, help="구 버전 run(기본 B3)")
    ap.add_argument("--split", choices=["train", "dev", "test", "all"], default="dev")
    ap.add_argument("--k", type=int, default=K_PRIMARY)
    ap.add_argument("--delta", type=float, default=config.T_DELTA)
    args = ap.parse_args()

    from ..analysis.metrics import load_run
    from ..analysis.results_table import _split_qrel, run_path
    from ..analysis.subgroup import query_labels
    from ..collect.bq_family_ir import load_family_map

    qrel = _split_qrel(args.split)
    fam = load_family_map()
    labels = query_labels(qrel)
    pnew = args.new or run_path("P1", args.split)
    pold = args.old or run_path("B3_rrf", args.split)
    r = t2_gate(load_run(pnew), load_run(pold), qrel, fam, labels, k=args.k, delta=args.delta)
    print(f"[split={args.split}]  new={pnew.name}  old={pold.name}")
    print(format_report(r))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
