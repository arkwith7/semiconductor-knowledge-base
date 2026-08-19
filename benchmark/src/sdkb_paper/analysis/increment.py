"""3단 증분표 — BM25 → +의미검색 → +온톨로지 (N10 · 원고 §5 서두·§6.2 해설).

"온톨로지가 정말 값을 더하는가"에 답하는 가장 짧은 형식: 같은 조건에서 **한 단계씩 얹으며**
주지표가 얼마나 움직이는지 본다.

| 단계 | 시스템 |
|---|---|
| ① 의미검색 추가 | B0(BM25) → B3(B0⊕B2 RRF) |
| ② 온톨로지 추가 | B3 → P1(온톨로지 재랭크) |
| 누적 | B0 → P1 |

**해석 규율:** ①은 **사전등록 확증 비교가 아니라 기술통계 증분**이다(시스템·설정·분할 모두 동결본,
재선택 없음). 확증 비교는 §6.2 의 P0★/P1 vs B3 뿐이다. 표에 그렇게 라벨해 보고한다.

`results_table.build_runs` 가 기록한 run 파일을 재사용한다(없으면 조립). 새 검색 없음.

CLI: `python -m sdkb_paper.analysis.increment [--split test] [--write]`.
"""
from __future__ import annotations

import argparse

from .. import config
from .bootstrap import paired_bootstrap
from .metrics import evaluate, load_run
from .results_table import build_runs, run_path

STEPS = [
    ("B0_bm25", "B0 · BM25 (nori + SDKB 사용자사전)"),
    ("B2_dense", "B2 · Dense (Titan Embed v2)"),
    ("B3_rrf", "B3 · Text Hybrid = B0 ⊕ B2 (RRF)"),
    ("P1", "P1 · B3 ⊕ 온톨로지 재랭크"),
]
PAIRS = [
    ("B3_rrf", "B0_bm25", "① 의미검색 추가 (B0→B3)"),
    ("P1", "B3_rrf", "② 온톨로지 추가 (B3→P1)"),
    ("P1", "B0_bm25", "누적 (B0→P1)"),
]


def load_or_build(split: str, *, unseal: bool = False, reason: str = ""):
    """기록된 run 을 읽고, 없으면 조립한다. 반환 (runs, qrel, fam)."""
    from ..collect.bq_family_ir import load_family_map
    from .results_table import _split_qrel

    names = [n for n, _ in STEPS]
    if all(run_path(n, split).exists() for n in names):
        return ({n: load_run(run_path(n, split)) for n in names},
                _split_qrel(split, unseal=unseal, reason=reason), load_family_map())
    runs, qrel, fam, _ = build_runs(split, unseal=unseal, reason=reason)
    return {n: runs[n] for n in names}, qrel, fam


def render(split: str, r100: dict, deltas: list[dict], n_q: int) -> str:
    lines = [
        f"# 3단 증분표 — {split} 분할 (family Recall@100)",
        "",
        f"> 자동 생성: `python -m sdkb_paper.analysis.increment --split {split} --write`.",
        f"> 정답≥1 질의 {n_q}개 · 동결 run 재평가(새 검색 없음) · 페어드 부트스트랩 10k·seed {config.SEED}.",
        "> **①은 확증 비교가 아니라 기술통계 증분이다** — 사전등록 확증은 §6.2 의 P0★/P1 vs B3.",
        "",
        "| 시스템 | family R@100 |", "|---|---:|",
    ]
    for name, label in STEPS:
        lines.append(f"| {label} | {r100[name]:.4f} |")
    lines += ["", "| 증분 | Δ R@100 | 95% CI | p (양측) | 질의 승/패/동 |",
              "|---|---:|---|---:|---|"]
    for d in deltas:
        lines.append(
            f"| {d['label']} | {d['delta']:+.4f} | [{d['lb95']:+.4f}, {d['ub95']:+.4f}] | "
            f"{d['p_two_sided']:.3f} | {d['win']}/{d['loss']}/{d['tie']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", "test_b", "all"], default="test")
    ap.add_argument("--unseal", action="store_true", help="B층 봉인 개봉(원장 기록)")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    runs, qrel, fam = load_or_build(args.split, unseal=args.unseal, reason=args.reason)
    n_q = sum(1 for q, p in qrel.items() if p)
    r100 = {n: evaluate(runs[n], qrel, ks=(100,), family=fam)["recall"][100] for n, _ in STEPS}
    deltas = []
    for a, b, label in PAIRS:
        r = paired_bootstrap(runs[a], runs[b], qrel, k=100, family=fam)
        deltas.append({"label": label, **r})

    md = render(args.split, r100, deltas, n_q)
    print(md)
    if args.write:
        import pandas as pd
        config.TABLES.mkdir(parents=True, exist_ok=True)
        out = config.TABLES / f"ir_increment_{args.split}.md"
        out.write_text(md, encoding="utf-8")
        print(f"✓ {out}")
        csv_out = config.PROCESSED / "ir" / f"ir_increment_{args.split}.csv"
        pd.DataFrame([{"step": n, "label": lb, "r100": r100[n]} for n, lb in STEPS]).to_csv(
            csv_out, index=False)
        pd.DataFrame(deltas).to_csv(
            config.PROCESSED / "ir" / f"ir_increment_delta_{args.split}.csv", index=False)
        print(f"✓ {csv_out}")


if __name__ == "__main__":
    main()
