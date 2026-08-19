"""M4 온톨로지팔 평가·격자선택 (PLAN-018 §7.3 M4-5/M4-9 · 원고 §5).

- **F18 격자선택(M4-5):** P0★ 가중치 (α, w_c, w_h, w_i) 를 **dev family Recall@100 로만** 선택한다.
  단체(simplex) 해상도 0.25 · 동률은 (낮은 α, 사전순 w) 로 결정적. test qrel 미열람.
- **마스터표:** B0·B2·B3(텍스트) + B4·B5(온톨로지 독립팔) + P0(concept+path)·P0★(결합) 을
  같은 분할·family 수준(F1)에서 비교. C2 헤드라인 = P0★ vs B3(H3).

효율: B3 풀의 원시 항(text_norm·concept·path·ipc)을 **질의당 1회** 계산해 캐시하고, 75개 가중치
구성은 캐시 위 가중합으로 재랭크 — 재계산 없음.

- **경계:** 이 모듈은 qrel 을 읽는다(analysis 허용) · 순위생성은 retrieval 에 위임 · **dev 로만 선택**.
CLI: `python -m sdkb_paper.analysis.ontology_eval [--split dev] [--select]`.
"""
from __future__ import annotations

import argparse

from .. import config
from ..retrieval import systems as S
from ..retrieval.candidate import CandidateMask
from ..retrieval.hybrid import RUN_B3
from ..retrieval.ontology_rerank import OntologyFeatures, _query_features
from .metrics import evaluate, load_qrel, load_run

GRID_RES = 0.25


def simplex_grid(res: float = GRID_RES) -> list[tuple[float, float, float]]:
    """a+b+c=1, 각 ∈{0,res,..,1} 인 (w_c,w_h,w_i) 격자(사전순 결정적)."""
    steps = [round(i * res, 2) for i in range(int(round(1 / res)) + 1)]
    out = []
    for a in steps:
        for b in steps:
            c = round(1.0 - a - b, 2)
            if c in steps and c >= 0:
                out.append((a, b, c))
    return out


def grid_configs() -> list[tuple[float, tuple[float, float, float]]]:
    """(α, (w_c,w_h,w_i)) 전량. α=0 은 텍스트 전용이라 가중치 무관 → 1개로 접음."""
    alphas = [0.0, 0.25, 0.5, 0.75, 1.0]
    simplex = simplex_grid()
    out: list[tuple[float, tuple[float, float, float]]] = []
    for al in alphas:
        if al == 0.0:
            out.append((0.0, (1.0, 0.0, 0.0)))   # 텍스트 전용(대표 1개)
        else:
            for w in simplex:
                out.append((al, w))
    return out


def component_cache(
    feats: OntologyFeatures, mask: CandidateMask, base_run: dict[str, list[str]],
    qids: list[str], pool_k: int = S.POOL_K,
    keep_axes=S.ALL_AXES, use_path: bool = True, use_ipc: bool = True,
) -> dict[str, list[tuple]]:
    """질의별 B3 풀 → [(doc, text_norm, concept, path, ipc)] (원시 항, 가중치 무관)."""
    qrows = _query_features(feats)
    cache: dict[str, list[tuple]] = {}
    for qid in qids:
        qrow = qrows.get(qid)
        pool = [d for d in base_run.get(qid, []) if mask.is_allowed(qid, d)][:pool_k]
        m = len(pool)
        rows = []
        for rank0, d in enumerate(pool):
            drow = feats.row.get(d)
            tn = 1.0 - (rank0 / (m - 1)) if m > 1 else 1.0
            if qrow is None or drow is None:
                rows.append((d, tn, 0.0, 0.0, 0.0))
                continue
            qc = S._filter_concepts(feats, feats.concepts[qrow], keep_axes)
            dc = S._filter_concepts(feats, feats.concepts[drow], keep_axes)
            c = feats.concept_overlap(qc, dc)
            p = feats.path_sim(qc, dc) if use_path else 0.0
            ic = feats.ipc_sim(feats.ipc[qrow], feats.ipc[drow]) if use_ipc else 0.0
            rows.append((d, tn, c, p, ic))
        cache[qid] = rows
    return cache


def rerank_from_cache(
    cache: dict[str, list[tuple]], alpha: float, w: tuple[float, float, float], k: int = 1000,
) -> dict[str, list[str]]:
    wc, wh, wi = w
    out: dict[str, list[str]] = {}
    for qid, rows in cache.items():
        scored = []
        for d, tn, c, p, ic in rows:
            ont = wc * c + wh * p + wi * ic
            s = (1.0 - alpha) * tn + alpha * ont
            scored.append((s, d))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out[qid] = [d for _, d in scored[:k]]
    return out


def _r100(run, qrel, fam) -> float:
    return evaluate(run, qrel, ks=(100,), family=fam)["recall"][100]


# P0★ 선택 결과(dev 격자·2026-07-27) — 재현·ablation·subgroup 재사용. 결과값이지 사전등록 아님.
SELECTED_ALPHA = 0.75
SELECTED_W = (0.5, 0.0, 0.5)

# --- P1: FeatureCoverage 확장 (PLAN-018 §7.5 P-2/P-3/P-4) --------------------
TAUS = (0.5, 0.6, 0.7, 0.8)   # P-3 τ 격자


def simplex4(res: float = GRID_RES):
    """a+b+c+d=1, 각∈{0,res,..,1} 인 (w_c,w_h,w_i,w_f) 격자."""
    steps = [round(i * res, 2) for i in range(int(round(1 / res)) + 1)]
    out = []
    for a in steps:
        for b in steps:
            for c in steps:
                d = round(1.0 - a - b - c, 2)
                if d in steps and d >= 0:
                    out.append((a, b, c, d))
    return out


def component_cache_p1(feats, mask, base_run, qids, fc_index, taus=TAUS, pool_k=S.POOL_K,
                       keep_axes=S.ALL_AXES, use_path=True, use_ipc=True):
    """질의별 B3 풀 → [(doc, text_norm, concept, path, ipc, (fc@τ...))]. fc 는 τ별 스칼라.

    keep_axes/use_path/use_ipc 로 ablation(A2/A3/A6/A8) 시 개념 항을 재계산. fc 는 τ별 재사용.
    """
    qrows = _query_features(feats)
    cache = {}
    for qid in qids:
        qrow = qrows.get(qid)
        pool = [d for d in base_run.get(qid, []) if mask.is_allowed(qid, d)][:pool_k]
        m = len(pool)
        rows = []
        for rank0, d in enumerate(pool):
            drow = feats.row.get(d)
            tn = 1.0 - (rank0 / (m - 1)) if m > 1 else 1.0
            if qrow is None or drow is None:
                rows.append((d, tn, 0.0, 0.0, 0.0, tuple(0.0 for _ in taus)))
                continue
            qc = S._filter_concepts(feats, feats.concepts[qrow], keep_axes)
            dc = S._filter_concepts(feats, feats.concepts[drow], keep_axes)
            c = feats.concept_overlap(qc, dc)
            p = feats.path_sim(qc, dc) if use_path else 0.0
            ic = feats.ipc_sim(feats.ipc[qrow], feats.ipc[drow]) if use_ipc else 0.0
            bs = fc_index.best_sims(qid, d)
            fc = tuple(float((bs >= t).mean()) if bs.size else 0.0 for t in taus)
            rows.append((d, tn, c, p, ic, fc))
        cache[qid] = rows
    return cache


def rerank_p1(cache, tau_idx: int, alpha: float, w4, k: int = 1000):
    """P1 재랭크: (1−α)text + α(w_c·c + w_h·p + w_i·ipc + w_f·fc[τ])."""
    wc, wh, wi, wf = w4
    out = {}
    for qid, rows in cache.items():
        scored = []
        for d, tn, c, p, ic, fc in rows:
            ont = wc * c + wh * p + wi * ic + wf * fc[tau_idx]
            scored.append(((1.0 - alpha) * tn + alpha * ont, d))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out[qid] = [d for _, d in scored[:k]]
    return out


def select_p1(cache, qrel, fam, taus=TAUS, k: int = 100) -> dict:
    """dev family R@k 최대 (τ, α, w4) 선택. 동률: 낮은 α → 사전순. P-3/P-4."""
    alphas = [0.25, 0.5, 0.75, 1.0]
    simplex = simplex4()
    results = []
    for ti, _tau in enumerate(taus):
        for al in alphas:
            for w in simplex:
                run = rerank_p1(cache, ti, al, w, k=k)
                results.append((_r100(run, qrel, fam), taus[ti], al, w))
    results.sort(key=lambda x: (-x[0], x[2], x[3]))
    r, tau, al, w = results[0]
    return {"best": {"r100": r, "tau": tau, "alpha": al, "w4": w}, "n_configs": len(results),
            "all": results}


def master_table(split: str, sel_alpha: float = SELECTED_ALPHA,
                 sel_w: tuple = SELECTED_W, k: int = 100, write_runs: bool = False) -> dict:
    """B3(F10-masked)·B4·B5·P0(concept)·P0★ 를 같은 분할·family 수준서 비교 + 페어드 부트스트랩."""
    import pandas as pd

    from ..collect.bq_family_ir import load_family_map
    from ..retrieval import systems as SS
    from .bootstrap import paired_bootstrap

    fam = load_family_map()
    qrel = load_qrel()
    if split != "all":
        sp = pd.read_parquet(config.IR_SPLIT)
        keep = set(sp.loc[sp["split"] == split, "doc_id"])
        qrel = {q: p for q, p in qrel.items() if q in keep}
    qids = [q for q, p in qrel.items() if p]

    feats = OntologyFeatures()
    mask = CandidateMask()
    b3 = load_run(RUN_B3)
    cache = component_cache(feats, mask, b3, qids)

    runs = {
        "B3_masked": rerank_from_cache(cache, 0.0, (1.0, 0.0, 0.0)),
        "B4_ipc": SS.build_b4(feats, mask, qids=qids),
        "B5_concept": SS.build_b5(feats, mask, qids=qids),
        "P0_concept": rerank_from_cache(cache, 0.5, (1.0, 0.0, 0.0)),
        "P0star": rerank_from_cache(cache, sel_alpha, sel_w),
    }
    if write_runs:
        from ..analysis.metrics import load_run as _lr  # noqa: F401
        config.IR_RUNS_DIR.mkdir(parents=True, exist_ok=True)
        for name, run in runs.items():
            p = config.IR_RUNS_DIR / f"onto_{name}_{split}.txt"
            with p.open("w", encoding="utf-8") as f:
                for qid, docs in run.items():
                    for rank, doc in enumerate(docs, 1):
                        f.write(f"{qid} Q0 {doc} {rank} {1.0/rank:.6f} onto_{name}\n")

    rows = {}
    for name, run in runs.items():
        r = evaluate(run, qrel, ks=(k, 500), family=fam)
        rows[name] = {"r100": r["recall"][k], "r500": r["recall"][500], "s100": r["success"][k]}
    boot = {}
    for name in ("P0star", "P0_concept", "B4_ipc", "B5_concept"):
        boot[name] = paired_bootstrap(runs[name], runs["B3_masked"], qrel, k=k, family=fam)
    return {"split": split, "k": k, "rows": rows, "boot": boot, "n_queries": len(qids)}


def select_p0(cache, qrel, fam, k: int = 100) -> dict:
    """dev family R@100 최대 (α,w) 선택. 동률: 낮은 α → 사전순 w. 전 구성 표 동반."""
    results = []
    for alpha, w in grid_configs():
        run = rerank_from_cache(cache, alpha, w, k=k)
        r = _r100(run, qrel, fam)
        results.append((r, alpha, w))
    # 최대 r, 동률시 낮은 alpha, 그다음 사전순 w
    results.sort(key=lambda x: (-x[0], x[1], x[2]))
    best_r, best_a, best_w = results[0]
    return {"best": {"r100": best_r, "alpha": best_a, "w": best_w},
            "all": [{"r100": r, "alpha": a, "w": w} for r, a, w in results]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", "all"], default="dev")
    ap.add_argument("--select", action="store_true", help="dev 격자선택 실행(F18·P0★)")
    ap.add_argument("--select-p1", action="store_true", help="dev P1 격자선택(τ×4가중·H4 준비)")
    ap.add_argument("--master", action="store_true", help="마스터표(B3·B4·B5·P0·P0★)+부트스트랩")
    ap.add_argument("--write-runs", action="store_true", help="마스터 run 파일 기록")
    ap.add_argument("--k", type=int, default=100)
    args = ap.parse_args()
    if args.split == "test":
        print("⚠️  test 개봉 — 최종 비교 전이면 사전등록 위반(F9)")

    import pandas as pd

    from ..collect.bq_family_ir import load_family_map
    fam = load_family_map()
    qrel = load_qrel()
    sp = pd.read_parquet(config.IR_SPLIT)
    keep_q = set(sp.loc[sp["split"] == args.split, "doc_id"]) if args.split != "all" else None
    if keep_q is not None:
        qrel = {q: pos for q, pos in qrel.items() if q in keep_q}
    qids = [q for q, pos in qrel.items() if pos]

    feats = OntologyFeatures()
    mask = CandidateMask()
    b3 = load_run(RUN_B3)

    if args.select:
        cache = component_cache(feats, mask, b3, qids)
        sel = select_p0(cache, qrel, fam, k=args.k)
        b = sel["best"]
        print(f"[F18 격자선택 · {args.split} family R@{args.k}]  {len(sel['all'])} 구성")
        print(f"  ★ 최적: α={b['alpha']} · (w_c,w_h,w_i)={b['w']} · R@{args.k}={b['r100']:.4f}")
        top = sorted(sel["all"], key=lambda x: -x["r100"])[:5]
        for t in top:
            print(f"    α={t['alpha']} w={t['w']} → {t['r100']:.4f}")
        # α=0(텍스트 전용=B3 풀 재정렬 없음) 대조
        base = next(x for x in sel["all"] if x["alpha"] == 0.0)
        print(f"  텍스트전용(α=0) R@{args.k}={base['r100']:.4f}  ← P0★ 이 이걸 넘는가 = H3")

    if args.select_p1:
        from ..retrieval.feature_coverage import FeatureCoverageIndex
        pool_docs = set(qids)
        for qid in qids:
            pool_docs.update([d for d in b3.get(qid, []) if mask.is_allowed(qid, d)][:S.POOL_K])
        fc = FeatureCoverageIndex(restrict_docs=pool_docs)
        cache = component_cache_p1(feats, mask, b3, qids, fc)
        sel = select_p1(cache, qrel, fam, k=args.k)
        b = sel["best"]
        print(f"[P1 격자선택 · {args.split} family R@{args.k}]  {sel['n_configs']} 구성 · FC 미싱 {fc.n_missing}")
        print(f"  ★ 최적: τ={b['tau']} · α={b['alpha']} · (w_c,w_h,w_i,w_f)={b['w4']} · R@{args.k}={b['r100']:.4f}")
        for r, tau, al, w in sorted(sel["all"], key=lambda x: -x[0])[:6]:
            print(f"    τ={tau} α={al} w={w} → {r:.4f}")

    if args.master:
        res = master_table(args.split, k=args.k, write_runs=args.write_runs)
        print(f"[마스터표 · {args.split} · family R@{args.k} · {res['n_queries']}질의]")
        for name, r in res["rows"].items():
            print(f"  {name:14} R@{args.k}={r['r100']:.4f}  R@500={r['r500']:.4f}  S@{args.k}={r['s100']:.4f}")
        print("  ─ 부트스트랩 vs B3(F10-masked) ─")
        for name, b in res["boot"].items():
            print(f"  {name:14} Δ={b['delta']:+.4f} CI[{b['lb95']:+.4f},{b['ub95']:+.4f}]"
                  f" p={b['p_two_sided']:.3f} 승/패/동 {b['win']}/{b['loss']}/{b['tie']}")


if __name__ == "__main__":
    main()
