"""Ablation A1–A8 (PLAN-018 §7.3 M4-8 · 원고 §5.4).

선택된 P0★(결합 제안)에서 온톨로지 계층을 하나씩 제거해 **ΔRecall@100(family)** 을 잰다. 각 제거의
페어드 부트스트랩 CI + **Holm 다중비교 보정**(F6). 원고 §5.4 표:

| A | 제거 | 이번 세션 |
|---|---|---|
| A1 | CPC/IPC (use_ipc=False) | ✅ |
| A2 | 공정·소자 (Process·SubProcess·Device 축) | ✅ |
| A3 | 재료·장비·고장 (Material·Equipment·FailureMode 축) | ✅ |
| A4 | ClaimFeature | ⏸ P1/P2 후속(입력 부재) |
| A5 | 거절근거·판단 | ⏸ P1/P2 후속 |
| A6 | 계층 경로(use_path=False, 개념겹침만) | ✅ |
| A7 | 전체 온톨로지 (α=0 → 텍스트전용=B3) | ✅ |
| A8 | 전문가계층(Skill 축) — 음성대조군(H5) | ✅ |

- **H4(계층기여):** A4/A5 손실 > A1 — **A4/A5 미가용 → 후속**.
- **H5(특이성):** A8 의 ΔR@100 이 유의하지 않아야(음성대조군). 유의 악화 시 "태스크 결합" 발견으로 전환(부록 F).

- **경계:** qrel 읽음(analysis) · 순위는 systems 가 만든다 · dev 로만.
"""
from __future__ import annotations

import argparse

from .. import config
from ..retrieval import systems as S
from ..retrieval.candidate import CandidateMask
from ..retrieval.hybrid import RUN_B3
from ..retrieval.ontology_rerank import OntologyFeatures
from .bootstrap import paired_bootstrap
from .metrics import SPLIT_B, evaluate, load_qrel, load_qrel_for_split, load_run
from .ontology_eval import component_cache, rerank_from_cache

# (id, 설명, ablation 인자) — component_cache 를 각 구성으로 재계산(6종만)
ABLATIONS = [
    ("A1", "−CPC/IPC", dict(use_ipc=False)),
    ("A2", "−공정·소자", dict(keep_axes=S.ALL_AXES - S.AXES_PROCESS_DEVICE)),
    ("A3", "−재료·장비·고장", dict(keep_axes=S.ALL_AXES - S.AXES_MATERIAL_EQUIP_FAILURE)),
    ("A6", "−계층경로(개념겹침만)", dict(use_path=False)),
    ("A7", "−전체온톨로지(=텍스트전용)", "TEXT_ONLY"),
    ("A8", "−전문가계층(Skill·음성대조군)", dict(keep_axes=S.ALL_AXES - S.AXES_EXPERT)),
]


def holm(pairs: list[tuple[str, float]], alpha: float = 0.05) -> dict[str, bool]:
    """Holm-Bonferroni: (label, p) → label→reject. 오름차순 p 에 α/(m−i) 임계."""
    m = len(pairs)
    ordered = sorted(pairs, key=lambda x: x[1])
    out, prev_reject = {}, True
    for i, (lab, p) in enumerate(ordered):
        thresh = alpha / (m - i)
        rej = prev_reject and (p < thresh)
        out[lab] = rej
        prev_reject = rej
    return out


def _qrel_qids_run(split: str, *, unseal: bool, reason: str):
    """분할별 (qrel, qids, B3 run 경로). B층은 봉인이라 `unseal` 이 필요하다(PLAN-047 §13)."""
    import pandas as pd

    from ..retrieval import layers

    if split == SPLIT_B:
        qrel = load_qrel_for_split(split, unseal=unseal, reason=reason)
        qids = [q for q in layers.split_qids(split) if qrel.get(q)]
        return qrel, qids, layers.run_path_for_layer(RUN_B3, layers.LAYER_B)
    qrel = load_qrel()
    if split != "all":
        sp = pd.read_parquet(config.IR_SPLIT)
        keep = set(sp.loc[sp["split"] == split, "doc_id"])
        qrel = {q: pos for q, pos in qrel.items() if q in keep}
    return qrel, [q for q, pos in qrel.items() if pos], RUN_B3


def run_ablation(split: str = "dev", alpha: float = 0.5,
                 w: tuple[float, float, float] = (0.5, 0.0, 0.5), k: int = 100,
                 *, unseal: bool = False, reason: str = "") -> dict:
    """선택된 P0★(alpha,w)에서 A1–A8 제거손실. 반환: full R@100 + 각 ablation Δ·CI."""
    from ..collect.bq_family_ir import load_family_map
    fam = load_family_map()
    qrel, qids, b3_path = _qrel_qids_run(split, unseal=unseal, reason=reason)

    feats = OntologyFeatures()
    mask = CandidateMask()
    b3 = load_run(b3_path)

    # full P0★ (모든 축·경로·IPC)
    cache_full = component_cache(feats, mask, b3, qids)
    run_full = rerank_from_cache(cache_full, alpha, w, k=1000)
    r_full = evaluate(run_full, qrel, ks=(k,), family=fam)["recall"][k]

    rows, pvals = [], []
    for aid, desc, arg in ABLATIONS:
        if arg == "TEXT_ONLY":
            run_ab = rerank_from_cache(cache_full, 0.0, (1.0, 0.0, 0.0), k=1000)
        else:
            cache_ab = component_cache(feats, mask, b3, qids, **arg)
            # A1(use_ipc=False): w_i 를 0 으로 두고 재랭크(항 제거)
            w_ab = (w[0], w[1], 0.0) if arg.get("use_ipc") is False else w
            a_ab = alpha
            run_ab = rerank_from_cache(cache_ab, a_ab, w_ab, k=1000)
        r_ab = evaluate(run_ab, qrel, ks=(k,), family=fam)["recall"][k]
        bs = paired_bootstrap(run_full, run_ab, qrel, k=k, family=fam)
        delta = bs["delta"]      # full − ablated = 제거손실(양수 = 계층이 기여)
        p = bs["p_two_sided"]
        rows.append({"id": aid, "desc": desc, "r_ablated": r_ab, "delta_loss": delta,
                     "lb95": bs["lb95"], "ub95": bs["ub95"], "p": p})
        pvals.append((aid, p))
    reject = holm(pvals)
    for row in rows:
        row["holm_sig"] = reject[row["id"]]
    return {"split": split, "alpha": alpha, "w": w, "r_full": r_full, "k": k, "rows": rows}


def _fmt(res: dict) -> str:
    lines = [f"[Ablation · {res['split']} · P0★ α={res['alpha']} w={res['w']} · family R@{res['k']}]",
             f"  P0★(full) R@{res['k']} = {res['r_full']:.4f}",
             "  ─" * 20,
             f"  {'A':<4}{'제거':<22}{'R@k':>8}{'제거손실Δ':>11}{'95%CI':>20}{'p':>7}{'Holm':>6}"]
    for r in res["rows"]:
        ci = f"[{r['lb95']:+.4f},{r['ub95']:+.4f}]"
        sig = "유의" if r["holm_sig"] else "n.s."
        lines.append(f"  {r['id']:<4}{r['desc']:<22}{r['r_ablated']:>8.4f}"
                     f"{r['delta_loss']:>+11.4f}{ci:>20}{r['p']:>7.3f}{sig:>6}")
    lines.append("  (제거손실Δ = full − ablated · 양수=계층 기여 · A8 은 음성대조군=n.s. 기대)")
    return "\n".join(lines)


def run_ablation_p1(split: str, tau: float, alpha: float, w4: tuple, k: int = 100,
                    *, unseal: bool = False, reason: str = "") -> dict:
    """P1(FeatureCoverage 포함) 기저에서 A1–A8 완비(A4=−FC·A5=−GroundCompat) + Holm. H4 검정.

    w4=(w_c,w_h,w_i,w_f). A5(GroundCompat)는 oracle-free 주모드서 항이 0 → 구조적 Δ=0(P-5).
    """
    from ..collect.bq_family_ir import load_family_map
    from ..retrieval.candidate import CandidateMask
    from ..retrieval.feature_coverage import FeatureCoverageIndex
    from ..retrieval.ontology_rerank import OntologyFeatures
    from .ontology_eval import TAUS, component_cache_p1, rerank_p1
    fam = load_family_map()
    qrel, qids, b3_path = _qrel_qids_run(split, unseal=unseal, reason=reason)
    ti = list(TAUS).index(tau)

    feats = OntologyFeatures()
    mask = CandidateMask()
    b3 = load_run(b3_path)
    # FC 인덱스: 풀 후보 + 질의만 적재(메모리 절약)
    pool_docs = set(qids)
    for qid in qids:
        pool_docs.update([d for d in b3.get(qid, []) if mask.is_allowed(qid, d)][:S.POOL_K])
    fc = FeatureCoverageIndex(restrict_docs=pool_docs)

    cache_full = component_cache_p1(feats, mask, b3, qids, fc)
    run_full = rerank_p1(cache_full, ti, alpha, w4, k=1000)
    r_full = evaluate(run_full, qrel, ks=(k,), family=fam)["recall"][k]

    wc, wh, wi, wf = w4
    specs = [
        ("A1", "−CPC/IPC", "reweight", (wc, wh, 0.0, wf), {}),
        ("A2", "−공정·소자", "recache", w4, dict(keep_axes=S.ALL_AXES - S.AXES_PROCESS_DEVICE)),
        ("A3", "−재료·장비·고장", "recache", w4, dict(keep_axes=S.ALL_AXES - S.AXES_MATERIAL_EQUIP_FAILURE)),
        ("A4", "−ClaimFeature(FC)", "reweight", (wc, wh, wi, 0.0), {}),
        ("A5", "−거절근거(GroundCompat)", "ground0", w4, {}),
        ("A6", "−계층경로", "recache", w4, dict(use_path=False)),
        ("A7", "−전체온톨로지(=텍스트)", "textonly", (0.0, 0.0, 0.0, 0.0), {}),
        ("A8", "−전문가계층(Skill)", "recache", w4, dict(keep_axes=S.ALL_AXES - S.AXES_EXPERT)),
    ]
    rows, pvals = [], []
    for aid, desc, kind, w_ab, ckw in specs:
        if kind == "ground0":
            # oracle-free 에서 GroundCompat 항 부재 → 제거해도 동일 = Δ0 (구조적·P-5)
            run_ab = run_full
        elif kind == "textonly":
            run_ab = rerank_p1(cache_full, ti, 0.0, (0.0, 0.0, 0.0, 0.0), k=1000)
        elif kind == "reweight":
            run_ab = rerank_p1(cache_full, ti, alpha, w_ab, k=1000)
        else:  # recache (axis/path 재계산)
            cache_ab = component_cache_p1(feats, mask, b3, qids, fc, **ckw)
            run_ab = rerank_p1(cache_ab, ti, alpha, w_ab, k=1000)
        r_ab = evaluate(run_ab, qrel, ks=(k,), family=fam)["recall"][k]
        bs = paired_bootstrap(run_full, run_ab, qrel, k=k, family=fam)
        rows.append({"id": aid, "desc": desc, "r_ablated": r_ab, "delta_loss": bs["delta"],
                     "lb95": bs["lb95"], "ub95": bs["ub95"], "p": bs["p_two_sided"]})
        pvals.append((aid, bs["p_two_sided"]))
    reject = holm(pvals)
    for row in rows:
        row["holm_sig"] = reject[row["id"]]
    return {"split": split, "alpha": alpha, "w": w4, "tau": tau, "r_full": r_full, "k": k, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", SPLIT_B, "all"], default="dev")
    ap.add_argument("--p1", action="store_true", help="P1(FeatureCoverage) 기저 A1–A8(H4)")
    ap.add_argument("--tau", type=float, help="P1 선택 τ")
    ap.add_argument("--alpha", type=float, required=True, help="선택된 α")
    ap.add_argument("--w", type=float, nargs="+", required=True,
                    metavar="W", help="P0★=Wc Wh Wi · P1=Wc Wh Wi Wf")
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--write", action="store_true", help="§6.4 ablation 표·그림 입력 CSV 기록")
    ap.add_argument("--unseal", action="store_true", help="B층 봉인 개봉(원장 기록)")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    args = ap.parse_args()
    if args.split == "test":
        print("⚠️  test 개봉 — 사전등록 위반 가능(F9)")
    if args.p1:
        res = run_ablation_p1(args.split, args.tau, args.alpha, tuple(args.w), args.k,
                              unseal=args.unseal, reason=args.reason)
    else:
        res = run_ablation(args.split, args.alpha, tuple(args.w), args.k,
                           unseal=args.unseal, reason=args.reason)
    print(_fmt(res))
    if args.write:
        import pandas as pd
        df = pd.DataFrame(res["rows"])
        df["r_full"] = res["r_full"]
        out = config.PROCESSED / "ir" / f"ir_ablation_{args.split}.csv"
        df.to_csv(out, index=False)
        print(f"✓ {out}")


if __name__ == "__main__":
    main()
