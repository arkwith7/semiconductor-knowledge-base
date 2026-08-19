"""§6.2 검색 성능 마스터표 — 전 시스템 × 전 지표 (N1·N7 · 원고 §5.1·§6.2).

동결된 run·qrel·split·family 지도만 읽어 **새 검색 없이** 표를 만든다. 산출은
`paper/tables/ir_performance_{split}.md` (수기 기입 금지 · CLAUDE.md §1-7).

비교 조건은 전 시스템 동일하다:
- F10 후보 마스크(시점유효·자기/패밀리 배제) 적용 후 **POOL_K=1000** 절단 — 재랭크팔이 보는 풀과 동일.
- family 수준(F1 주지표) fold-then-cut. 정답≥1 질의만 매크로 평균.
- 통계는 B3(최강 텍스트 기준선) 대비 질의단위 페어드 부트스트랩 10k·seed 고정.

**지표 관례(원고 §5.1 대비 정직 고지):** as-built qrel 은 전량 등급 1(심사관 인용 = 약한 양성)이라
nDCG 는 **이진 이득**이고 bpref 는 **retrieved-as-judged** 관례다(metrics.py docstring). 등급형은
§5.5 전문가 판정 확보 시 후속.

CLI: `python -m sdkb_paper.analysis.results_table [--split dev|test] [--latency] [--write]`.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .. import config
from ..retrieval import systems as S
from .metrics import (
    NDCG_K,
    SPLIT_B,
    evaluate,
    load_qrel,
    load_qrel_for_split,
    load_run,
)

# 표에 실을 시스템 (원고 §4.6 비교 시스템 표기 → 코드 라벨)
SYSTEM_LABELS: list[tuple[str, str]] = [
    ("B0_bm25", "BM25-Claim (B0)"),
    ("B2_dense", "Dense (B2 · Titan v2)"),
    ("B3_rrf", "Text Hybrid (B3 = B0⊕B2 RRF)"),
    ("B4_ipc", "CPC/IPC only (B4)"),
    ("B5_concept", "Ontology-only (B5)"),
    ("P0star", "Text+Ontology (P0★ · 사전지정 주)"),
    ("P1", "+ClaimFeature (P1)"),
]
# P1 dev 격자선택 결과(2026-07-27 · 재선택 없음 — 결과값이지 사전등록 아님)
P1_TAU, P1_ALPHA, P1_W4 = 0.7, 0.75, (0.25, 0.0, 0.25, 0.5)
KS = (50, 100, 500)


def _split_qrel(split: str, *, unseal: bool = False, reason: str = "") -> dict[str, set[str]]:
    """분할별 정답지. `test_b` 는 **봉인**이라 `unseal=True` 없이는 열리지 않는다(§13.3)."""
    import pandas as pd

    if split == SPLIT_B:
        return load_qrel_for_split(split, unseal=unseal, reason=reason)
    qrel = load_qrel()
    if split == "all":
        return qrel
    sp = pd.read_parquet(config.IR_SPLIT)
    keep = set(sp.loc[sp["split"] == split, "doc_id"])
    return {q: p for q, p in qrel.items() if q in keep}


def write_run(run: dict[str, list[str]], path: Path, tag: str) -> Path:
    """TREC run 파일로 기록 — 그림·하위집단이 재계산 없이 같은 순위를 읽게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for qid, docs in run.items():
            for rank, doc in enumerate(docs, 1):
                f.write(f"{qid} Q0 {doc} {rank} {1.0 / rank:.6f} {tag}\n")
    return path


def run_path(name: str, split: str) -> Path:
    return config.IR_RUNS_DIR / f"sys_{name}_{split}.txt"


def build_runs(split: str, write: bool = True, *, unseal: bool = False,
               reason: str = "", runs_only: bool = False) -> tuple[dict, dict, dict, list[str]]:
    """전 시스템 run 을 같은 조건으로 조립. 반환 (runs, qrel, family_map, qids).

    **B층(`test_b`)에서는 qid 를 분할 표에서 뽑고 qrel 을 읽지 않는다**(PLAN-047 §13.1) —
    그래야 "run 을 먼저 만들고 봉인을 연다"(G7)가 성립한다. `unseal=False` 면 qrel 은
    빈 사전으로 두고 run 만 만든다. 그 밖의 분할은 **현행 그대로**(qrel 기반)다.
    """
    from ..collect.bq_family_ir import load_family_map
    from ..retrieval import layers
    from ..retrieval.bm25 import RUN_B0
    from ..retrieval.candidate import CandidateMask
    from ..retrieval.dense import RUN_B2
    from ..retrieval.feature_coverage import FeatureCoverageIndex
    from ..retrieval.hybrid import RUN_B3
    from ..retrieval.ontology_rerank import OntologyFeatures
    from .ontology_eval import (
        SELECTED_ALPHA,
        SELECTED_W,
        TAUS,
        component_cache_p1,
        rerank_from_cache,
        rerank_p1,
    )

    fam = load_family_map()
    if split == SPLIT_B:
        # qid 원천 = 분할 표(봉인 미열람). qrel 은 개봉이 허가된 경우에만 적재한다.
        qids = layers.split_qids(split)
        # 개봉 없이 **평가**하려는 시도는 여기서 막힌다 — `_split_qrel` 이 봉인 통로를 타고
        # 거부한다. run 만 만드는 경로(`runs_only`)에서만 정답지 없이 통과한다.
        qrel = {} if runs_only else _split_qrel(split, unseal=unseal, reason=reason)
        layer = layers.LAYER_B
    else:
        qrel = _split_qrel(split)
        qids = [q for q, p in qrel.items() if p]
        layer = layers.LAYER_A
    RUN_B0 = layers.run_path_for_layer(RUN_B0, layer)
    RUN_B2 = layers.run_path_for_layer(RUN_B2, layer)
    RUN_B3 = layers.run_path_for_layer(RUN_B3, layer)
    mask = CandidateMask()

    def masked(path: Path) -> dict[str, list[str]]:
        r = load_run(path)
        return {q: [d for d in r.get(q, []) if mask.is_allowed(q, d)][: S.POOL_K] for q in qids}

    runs: dict[str, dict[str, list[str]]] = {
        "B0_bm25": masked(RUN_B0),
        "B2_dense": masked(RUN_B2),
        "B3_rrf": masked(RUN_B3),
    }

    feats = OntologyFeatures()
    runs["B4_ipc"] = S.build_b4(feats, mask, qids=qids)
    runs["B5_concept"] = S.build_b5(feats, mask, qids=qids)

    b3_raw = load_run(RUN_B3)
    pool_docs = set(qids)
    for q in qids:
        pool_docs.update(runs["B3_rrf"][q])
    fc = FeatureCoverageIndex(restrict_docs=pool_docs)
    cache = component_cache_p1(feats, mask, b3_raw, qids, fc)
    # P0★ = FeatureCoverage 항 없이(w_f=0) 3항 가중 — cache 의 앞 5열만 쓰는 형태로 환원
    cache3 = {q: [(d, tn, c, p, ic) for d, tn, c, p, ic, _fc in rows] for q, rows in cache.items()}
    runs["P0star"] = rerank_from_cache(cache3, SELECTED_ALPHA, SELECTED_W)
    runs["P1"] = rerank_p1(cache, list(TAUS).index(P1_TAU), P1_ALPHA, P1_W4)

    if write:
        for name, run in runs.items():
            write_run(run, run_path(name, split), f"{name}_{split}")
    return runs, qrel, fam, qids


def metric_row(run: dict, qrel: dict, fam: dict) -> dict:
    r = evaluate(run, qrel, ks=KS, family=fam)
    return {
        "R@50": r["recall"][50], "R@100": r["recall"][100], "R@500": r["recall"][500],
        "S@100": r["success"][100], "MRR": r["mrr"],
        f"nDCG@{NDCG_K}": r[f"ndcg@{NDCG_K}"], "bpref": r["bpref"],
    }


def measure_latency(split: str, n_queries: int = 30) -> dict:
    """질의당 지연 — **단계별**로 잰다(원고 §5.1). 측정 못한 단계는 표에 '미측정'으로 남긴다.

    - `bm25`: Pyserini LuceneSearcher 1질의 검색(JVM warm-up 제외). JAVA_HOME 필요.
    - `rerank`: 온톨로지 특징 계산 + 가중합 재정렬(B3 상위 1,000). 제안법이 **추가하는** 비용.
    엔드투엔드 서비스 지연이 아니라 단계 비용이다 — 그렇게 라벨해 보고한다.
    """
    import numpy as np

    from ..retrieval.candidate import CandidateMask
    from ..retrieval.hybrid import RUN_B3
    from ..retrieval.ontology_rerank import OntologyFeatures

    qrel = _split_qrel(split)
    qids = sorted(q for q, p in qrel.items() if p)[:n_queries]
    out: dict[str, dict] = {}

    # --- 재랭크 단계 ---
    from .ontology_eval import component_cache, rerank_from_cache

    feats, mask = OntologyFeatures(), CandidateMask()
    b3 = load_run(RUN_B3)
    ts = []
    for q in qids:
        t0 = time.perf_counter()
        c = component_cache(feats, mask, b3, [q])
        rerank_from_cache(c, 0.75, (0.5, 0.0, 0.5))
        ts.append((time.perf_counter() - t0) * 1000)
    out["rerank"] = {"n": len(ts), "p50": float(np.percentile(ts, 50)),
                     "p95": float(np.percentile(ts, 95))}

    # --- BM25 검색 단계 ---
    try:
        config.java_home()          # JVM 부팅 전 JAVA_HOME 확정 (PLAN-018 E1 · 함정)
        import pandas as pd
        from pyserini.pyclass import autoclass
        from pyserini.search.lucene import LuceneSearcher

        from ..retrieval.bm25 import BM25_B, BM25_INDEX_DIR, BM25_K1, _tokenizers
        from ..retrieval.tokenize import pretokenize

        searcher = LuceneSearcher(str(BM25_INDEX_DIR))
        searcher.set_analyzer(autoclass("org.apache.lucene.analysis.core.WhitespaceAnalyzer")())
        searcher.set_bm25(BM25_K1, BM25_B)
        ko, en = _tokenizers()
        df = pd.read_parquet(config.IR_CORPUS,
                             columns=["doc_id", "lang", "claims_independent", "text_main"])
        df = df[df["doc_id"].astype(str).isin(set(qids))]
        ts = []
        for r in df.itertuples(index=False):
            text = str(r.claims_independent or r.text_main or "")
            if not text.strip():
                continue
            qstr = pretokenize(text, ko, en, str(r.lang or "und"))   # 토큰화 비용 포함
            t0 = time.perf_counter()
            searcher.search(qstr, 1000)
            ts.append((time.perf_counter() - t0) * 1000)
        if len(ts) > 2:
            ts = ts[1:]        # JVM warm-up 1회 제외
            out["bm25_search"] = {"n": len(ts), "p50": float(np.percentile(ts, 50)),
                                  "p95": float(np.percentile(ts, 95))}
    except Exception as e:      # JVM 부재·색인 부재 — 실패는 실패로 보고한다
        out["bm25_search"] = {"error": f"{type(e).__name__}: {e}"}
    return out


def _arm_line() -> str:
    """표가 **어느 자원 팔**에서 나왔는지 한 줄로 밝힌다 (PLAN-036 §12).

    표에 팔이 적혀 있지 않으면, `make vendor` 뒤 아무 생각 없이 `make tables` 를 돌렸을 때
    원고 §6.2 의 수치가 **말없이 다른 팔의 것으로 바뀐다.** 실제로 탐색 패널에서 그 일이
    한 번 일어났다. 서명을 표에 박아 두면 표를 보는 것만으로 팔을 알 수 있다.
    """
    from ..validate.runset import arm_label, pipeline_signature

    pipe = pipeline_signature()
    arm = arm_label(pipe["sig"])
    return f"{arm or '미등록(동결 runset 과 불일치)'} · pipeline_sig `{pipe['short']}`"


def render(split: str, rows: dict, boot: dict, n_q: int, n_qrel: int,
           latency: dict | None = None) -> str:
    hdr = ["시스템", "R@50", "R@100", "R@500", "Success@100", "MRR@500",
           f"nDCG@{NDCG_K}", "bpref"]
    lines = [
        f"# §6.2 검색 성능 결과표 — {split} 분할",
        "",
        f"> 자동 생성: `python -m sdkb_paper.analysis.results_table --split {split} --write`. "
        "수기 기입 금지(CLAUDE.md §1-7).",
        f"> 조건: family 수준(F1 주지표) · F10 마스크 후 POOL_K=1000 절단 · 정답≥1 질의 **{n_q}**개 · "
        f"qrel(문서수준) **{n_qrel}**건 · 페어드 부트스트랩 10k·seed {config.SEED}.",
        f"> **nDCG@{NDCG_K} 는 이진 이득**(qrel 전량 등급 1 — 등급 자원 없음), "
        "**bpref 는 retrieved-as-judged 관례**(양성 전용 qrel). 원고 §5.1 대비 관례 차이를 명시한다.",
        f"> **자원 팔: {_arm_line()}** — 이 표는 재랭크를 현재 디스크의 온톨로지 자원으로 다시 "
        "계산한다. 팔이 다르면 수치도 다르다(PLAN-036 §12).",
        "",
        "| " + " | ".join(hdr) + " |",
        "|" + "---|" * len(hdr),
    ]
    for name, label in SYSTEM_LABELS:
        m = rows[name]
        lines.append(
            f"| {label} | {m['R@50']:.4f} | {m['R@100']:.4f} | {m['R@500']:.4f} | "
            f"{m['S@100']:.4f} | {m['MRR']:.4f} | {m[f'nDCG@{NDCG_K}']:.4f} | {m['bpref']:.4f} |"
        )
    lines += [
        "",
        "## 주지표(family Recall@100) — B3 텍스트 기준선 대비",
        "",
        "| 시스템 | Δ R@100 | 95% CI | p (양측) | 질의 승/패/동 |",
        "|---|---:|---|---:|---|",
    ]
    for name, label in SYSTEM_LABELS:
        if name == "B3_rrf" or name not in boot:
            continue
        b = boot[name]["recall"]
        lines.append(
            f"| {label} | {b['delta']:+.4f} | [{b['lb95']:+.4f}, {b['ub95']:+.4f}] | "
            f"{b['p_two_sided']:.3f} | {b['win']}/{b['loss']}/{b['tie']} |"
        )
    lines += [
        "",
        f"## 보조지표 — B3 대비 (H3 사전등록 기준은 R@100 **및** nDCG@{NDCG_K} 개선을 요구한다)",
        "",
        f"| 시스템 | Δ nDCG@{NDCG_K} | 95% CI | p | Δ MRR@500 | 95% CI | p | Δ bpref | p |",
        "|---|---:|---|---:|---:|---|---:|---:|---:|",
    ]
    for name, label in SYSTEM_LABELS:
        if name == "B3_rrf" or name not in boot:
            continue
        nd, mr, bp = boot[name]["ndcg"], boot[name]["mrr"], boot[name]["bpref"]
        lines.append(
            f"| {label} | {nd['delta']:+.4f} | [{nd['lb95']:+.4f}, {nd['ub95']:+.4f}] | "
            f"{nd['p_two_sided']:.3f} | {mr['delta']:+.4f} | "
            f"[{mr['lb95']:+.4f}, {mr['ub95']:+.4f}] | {mr['p_two_sided']:.3f} | "
            f"{bp['delta']:+.4f} | {bp['p_two_sided']:.3f} |"
        )
    if latency:
        lines += ["", "## 질의당 지연 (단계별 · 엔드투엔드 아님)", "",
                  "| 단계 | n | p50 (ms) | p95 (ms) |", "|---|---:|---:|---:|"]
        for stage, v in latency.items():
            if "error" in v:
                lines.append(f"| {stage} | — | 미측정 | 미측정 ({v['error']}) |")
            else:
                lines.append(f"| {stage} | {v['n']} | {v['p50']:.1f} | {v['p95']:.1f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", SPLIT_B, "all"], default="dev")
    ap.add_argument("--latency", action="store_true", help="단계별 지연 측정(JVM 필요)")
    ap.add_argument("--write", action="store_true", help="paper/tables/ 에 표 기록")
    ap.add_argument("--runs-only", action="store_true",
                    help="run 만 만들고 평가하지 않는다(판독 B 의 개봉 전 단계 · G7)")
    ap.add_argument("--unseal", action="store_true",
                    help="B층 봉인 개봉(PLAN-047 동결 커밋 이후 1회) — 원장에 기록된다")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    args = ap.parse_args()
    if args.split == "test":
        print("⚠️  test 분할 — 봉인 개봉(최종 비교 후 재평가만 허용 · 재선택 금지)")

    from .bootstrap import paired_bootstrap

    if args.runs_only:
        # 개봉 전 단계: run 만 만든다. 봉인은 열지 않는다(§8 (2) · G7 증거).
        runs, _qrel, _fam, qids = build_runs(args.split, unseal=False, runs_only=True)
        for name, _ in SYSTEM_LABELS:
            print(f"  {name:<12} {len(runs[name])} 질의 → {run_path(name, args.split)}")
        print(f"✓ run 산출 완료 (질의 {len(qids)}건) — 평가하지 않았다(봉인 미열람)")
        return

    runs, qrel, fam, qids = build_runs(args.split, unseal=args.unseal, reason=args.reason)
    rows = {name: metric_row(runs[name], qrel, fam) for name, _ in SYSTEM_LABELS}
    boot = {
        name: {m: paired_bootstrap(runs[name], runs["B3_rrf"], qrel, k=100, family=fam, metric=m)
               for m in ("recall", "ndcg", "mrr", "bpref")}
        for name, _ in SYSTEM_LABELS if name != "B3_rrf"
    }
    # 표에 적는 질의 수는 **정답 ≥1 질의**다(주지표 정의 · PLAN-031 §4). A층은 qid 원천이
    # qrel 이라 둘이 같았지만, B층은 qid 가 분할에서 오므로 정답 0인 질의가 섞인다
    # (실측 200 중 2건). `evaluate()` 는 이미 정답 보유 질의만 평균하므로 **판정은 그대로**이고,
    # 바뀌는 것은 표에 적히는 분모의 정직함뿐이다.
    eval_qids = [q for q in qids if qrel.get(q)]
    n_qrel = sum(len(qrel[q]) for q in eval_qids)
    lat = measure_latency(args.split) if args.latency else None

    md = render(args.split, rows, boot, len(eval_qids), n_qrel, lat)
    print(md)
    if args.write:
        config.TABLES.mkdir(parents=True, exist_ok=True)
        out = config.TABLES / f"ir_performance_{args.split}.md"
        out.write_text(md, encoding="utf-8")
        print(f"✓ {out}")
        # viz 는 계산하지 않는다(CLAUDE.md §3) — 그림 입력을 CSV 로 배출한다.
        import pandas as pd
        recs = []
        for name, label in SYSTEM_LABELS:
            rec = {"system": name, "label": label, **rows[name]}
            if name in boot:
                for m in ("recall", "ndcg", "mrr", "bpref"):
                    b = boot[name][m]
                    rec |= {f"d_{m}": b["delta"], f"lb_{m}": b["lb95"],
                            f"ub_{m}": b["ub95"], f"p_{m}": b["p_two_sided"]}
                rec |= {"win": boot[name]["recall"]["win"], "loss": boot[name]["recall"]["loss"],
                        "tie": boot[name]["recall"]["tie"]}
            recs.append(rec)
        csv_out = config.PROCESSED / "ir" / f"ir_performance_{args.split}.csv"
        pd.DataFrame(recs).to_csv(csv_out, index=False)
        print(f"✓ {csv_out}")


if __name__ == "__main__":
    main()
