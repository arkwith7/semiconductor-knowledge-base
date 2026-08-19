"""Hybrid 검색 (PLAN-018 B3 · Reciprocal Rank Fusion).

BM25(B0)와 Dense(B2) run 을 **RRF** 로 융합한다 — 가장 강한 텍스트 기준선(원고 §4.6). 점수 스케일이
다른 두 순위를 순위(rank)만으로 결합해 정규화 문제를 피한다. c=60 은 표준 기본값(Cormack et al. 2009).

`RRF(d) = Σ_i 1 / (c + rank_i(d))`  — 각 시스템에서의 순위 역수 합. 문서가 한 시스템에만 있어도 가산.

- **경계(PLAN-018 §2):** run(순위)만 만든다 — qrel 미열람. 평가는 analysis/metrics.

CLI: `python -m sdkb_paper.retrieval.hybrid`(B0·B2 run → B3 run).
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..analysis.metrics import load_run

RUN_B3 = config.IR_RUNS_DIR / "hybrid_b3_rrf.txt"
RRF_C = 60


def rrf(runs: list[dict[str, list[str]]], k: int = 1000, c: int = RRF_C) -> dict[str, list[str]]:
    """여러 run(qid→rank순 doc 리스트)을 RRF 융합 → qid→상위 k doc 리스트."""
    qids: set[str] = set()
    for r in runs:
        qids |= set(r)
    fused: dict[str, list[str]] = {}
    for qid in qids:
        score: dict[str, float] = {}
        for r in runs:
            for rank, doc in enumerate(r.get(qid, []), start=1):
                score[doc] = score.get(doc, 0.0) + 1.0 / (c + rank)
        # 동점은 doc_id 사전순으로 깨서 결정적(F16).
        ranked = sorted(score, key=lambda d: (-score[d], d))
        fused[qid] = ranked[:k]
    return fused


def write_run(fused: dict[str, list[str]], run_path: Path, tag: str = "hybrid_b3") -> Path:
    run_path.parent.mkdir(parents=True, exist_ok=True)
    with run_path.open("w", encoding="utf-8") as f:
        for qid, docs in fused.items():
            for rank, doc in enumerate(docs, start=1):
                score = 1.0 / rank    # RRF 절대점수 대신 순위기반 표기(평가는 순위만 사용)
                f.write(f"{qid} Q0 {doc} {rank} {score:.6f} {tag}\n")
    return run_path


def main() -> None:
    import argparse

    from . import layers
    from .bm25 import RUN_B0
    from .dense import RUN_B2

    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=[layers.LAYER_A, layers.LAYER_B], default=layers.LAYER_A,
                    help="질의 층. B 는 판독 B 전용 · run 은 `_B` 접미")
    args = ap.parse_args()

    b0 = layers.run_path_for_layer(RUN_B0, args.layer)
    b2 = layers.run_path_for_layer(RUN_B2, args.layer)
    out = layers.run_path_for_layer(RUN_B3, args.layer)
    layers.guard_run_target(out, args.layer, RUN_B3)
    for p in (b0, b2):
        if not Path(p).exists():
            raise SystemExit(f"[hybrid] 입력 run 없음: {p} — 먼저 B0·B2 생성(layer={args.layer})")
    runs = [load_run(b0), load_run(b2)]
    fused = rrf(runs, k=1000)
    write_run(fused, out)
    print(f"✓ Hybrid B3(RRF c={RRF_C}) run → {out}  ({len(fused)} 질의)")


if __name__ == "__main__":
    main()
