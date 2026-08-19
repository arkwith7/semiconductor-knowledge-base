"""IR 평가 지표 (PLAN-018 §6 · 원고 §5.1).

run(순위) × qrel(정답) → Recall@K·Success@K·MRR@K·nDCG@K·bpref.
- **문서수준**(family 집계 이전): `evaluate()`.
- **family 수준(F1 주지표)**: `evaluate(..., family=<doc_id→family_id>)` — run·qrel 을 family 로
  접어 계산한다. 같은 발명의 국내외 중복 공개를 한 패밀리로 세어 회수를 정직하게 잰다(원고 §4.5·5.1).
  family 지도는 `collect/bq_family_ir`(DOCDB, 미조인은 자기자신 fallback). 주 결론은 family 수준.

- **경계(PLAN-018 §2):** analysis 는 순위를 만들지 않는다 — run 파일을 읽어 평가만 한다. qrel 열람 허용.
- 매크로 평균: 정답 ≥1 인 질의에 대해서만 평균(질의밀도 반영). 분모를 명시 보고한다(혼용 금지).

CLI: `python -m sdkb_paper.analysis.metrics [--run PATH] [--k 50 100 500] [--family]`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .. import config


def load_run(path: Path) -> dict[str, list[str]]:
    """TREC run → {qid: [doc_id, ...]} (rank 순)."""
    run: dict[str, list[str]] = {}
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            qid, _, docid, rank = parts[0], parts[1], parts[2], int(parts[3])
            run.setdefault(qid, []).append((rank, docid))
    return {q: [d for _, d in sorted(v)] for q, v in run.items()}


def load_qrel(path: Path | None = None) -> dict[str, set[str]]:
    """qrel parquet(query_id·doc_id·relevance) → {qid: {positive doc_id}} (relevance>0)."""
    import pandas as pd

    q = pd.read_parquet(path or config.QREL_EXAMINER)
    qrel: dict[str, set[str]] = {}
    for r in q.itertuples(index=False):
        if getattr(r, "relevance", 1) > 0:
            qrel.setdefault(r.query_id, set()).add(r.doc_id)
    return qrel


# --- 분할별 정답지 (PLAN-047 §13.3) -------------------------------------------
SPLIT_B = "test_b"


def qrel_path_for_split(split: str) -> Path:
    """분할 → qrel 경로. `test_b` 만 **B층 봉인**을 가리킨다."""
    return Path(config.B_QREL_SEALED) if split == SPLIT_B else Path(config.QREL_EXAMINER)


def load_qrel_for_split(split: str, *, unseal: bool = False, reason: str = "") -> dict[str, set[str]]:
    """분할에 맞는 qrel 을 적재한다. **봉인 분할은 `unseal=True` 없이는 열리지 않는다.**

    봉인 경로가 소비자에게 도달하는 통로는 이 함수 하나이며, 그 안에서 반드시
    `validate.seal_audit.open_sealed()` 를 지난다(PLAN-047 §13.3 · G7).
    """
    path = qrel_path_for_split(split)
    if split == SPLIT_B:
        from ..corpus import qrel_b
        from ..validate.seal_audit import open_sealed

        path = open_sealed(path, reason=reason or f"판독 B 평가(split={split})", allow=unseal)
        # B층 봉인은 **수집 형식**이라 그대로 못 읽는다(D-34). 변환은 파일을 만들지 않고
        # 메모리에서만 한다 — 파생본을 디스크에 남기면 봉인과 어긋날 자리가 생긴다.
        qrel = qrel_b.load_as_dict(path)
    else:
        qrel = load_qrel(path)
    if split in ("all", None):
        return qrel
    import pandas as pd

    sp = pd.read_parquet(config.IR_SPLIT, columns=["doc_id", "split"])
    keep = set(sp.loc[sp["split"] == split, "doc_id"].astype(str))
    return {q: pos for q, pos in qrel.items() if q in keep}


def _fold(ranked: list[str], fam: dict[str, str]) -> list[str]:
    """문서 순위 → family 순위. 각 family 의 **첫 등장**만 남긴다(fold-then-cut).

    family 지도에 없는 doc 은 자기 자신이 1개 family(fallback 과 동일). 이로써 top-K 는
    'K 개 서로 다른 발명을 검토'라는 뜻이 된다 — 같은 발명의 중복 공개가 K 를 낭비하지 않는다.
    """
    seen: set[str] = set()
    out: list[str] = []
    for d in ranked:
        f = fam.get(d, d)
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


NDCG_K = 20     # 원고 §5.1 보조지표 nDCG@20 (동결)


def ndcg_at_k(ranked: list[str], pos: set[str], k: int = NDCG_K) -> float:
    """nDCG@k — **이진 이득**(gain=1).

    원고 §5.1 은 "등급형 qrel 이 있는 부분집합"의 nDCG 를 예고했으나 as-built qrel 은 전량 등급 1
    (심사관 인용 = 약한 양성 · 2,416행 모두 relevance=1)이라 **등급 자원이 없다**. 등급을 지어내지
    않고 이진 이득으로 계산하며, 표에는 그렇게 라벨한다(등급형 nDCG 는 §5.5 전문가 판정 확보 시 후속).
    """
    import math

    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(ranked[:k], start=1) if d in pos)
    ideal = min(len(pos), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal + 1))
    return dcg / idcg if idcg > 0 else 0.0


def bpref(ranked: list[str], pos: set[str]) -> float:
    """bpref (Buckley & Voorhees 2004) — **retrieved-as-judged 관례**.

    고전 bpref 는 "판정된 비적합 문서"만 세지만 본 qrel 은 **양성 전용**이라(§2.2 약한 정답)
    판정 비적합 집합이 공집합 → 고전 정의로는 항상 1.0 인 공허한 지표가 된다. 그래서 **회수된
    비양성 문서를 비적합으로 간주**하는 관례를 쓴다: 상위에 미인용 후보가 많이 끼어들수록 감점.
    이는 관례이지 등급 자원이 아니며, 표·본문에 관례를 명시해 보고한다.

    bpref = (1/R) Σ_{r∈회수된 양성} (1 − min(|r 위의 비양성|, R) / R)
    """
    r = len(pos)
    if r == 0:
        return 0.0
    n_above = 0
    total = 0.0
    for d in ranked:
        if d in pos:
            total += 1.0 - min(n_above, r) / r
        else:
            n_above += 1
    return total / r


def evaluate(
    run: dict[str, list[str]],
    qrel: dict[str, set[str]],
    ks: tuple[int, ...] = (50, 100, 500),
    family: dict[str, str] | None = None,
) -> dict:
    """Recall@K·Success@K·MRR@K·nDCG@20·bpref (매크로, 정답≥1 질의만).

    `family` 를 주면 run·qrel 을 family 로 접어 **family 수준**(F1 주지표)으로 잰다. fold-then-cut:
    순위를 family 로 중복 제거한 뒤 top-K family 를 취한다. 주면 안 주면 문서수준.
    """
    if family is not None:
        qrel = {q: {family.get(d, d) for d in pos} for q, pos in qrel.items()}
    eval_qids = [q for q, pos in qrel.items() if pos]   # 정답 보유 질의만
    n = len(eval_qids)
    out: dict = {
        "n_queries_evaluated": n,
        "n_queries_in_run": len(run),
        "level": "family" if family is not None else "document",
    }
    recall = {k: 0.0 for k in ks}
    success = {k: 0 for k in ks}
    mrr = 0.0
    ndcg_sum = 0.0
    bpref_sum = 0.0
    for qid in eval_qids:
        pos = qrel[qid]
        ranked = _fold(run.get(qid, []), family) if family is not None else run.get(qid, [])
        ndcg_sum += ndcg_at_k(ranked, pos, NDCG_K)
        bpref_sum += bpref(ranked, pos)
        # MRR: 첫 정답의 역수 순위 (상한 max(ks) 내)
        for i, d in enumerate(ranked[: max(ks)], start=1):
            if d in pos:
                mrr += 1.0 / i
                break
        for k in ks:
            topk = set(ranked[:k])
            hit = len(topk & pos)
            recall[k] += hit / len(pos)
            if hit > 0:
                success[k] += 1
    out["recall"] = {k: (recall[k] / n if n else 0.0) for k in ks}
    out["success"] = {k: (success[k] / n if n else 0.0) for k in ks}
    out["mrr"] = mrr / n if n else 0.0
    out[f"ndcg@{NDCG_K}"] = ndcg_sum / n if n else 0.0
    out["bpref"] = bpref_sum / n if n else 0.0
    return out


def _fmt(res: dict) -> str:
    lines = [
        f"[{res.get('level','document')} 수준]  "
        f"평가 질의(정답≥1): {res['n_queries_evaluated']}  ·  run 질의: {res['n_queries_in_run']}",
        "─" * 48,
    ]
    for k in sorted(res["recall"]):
        lines.append(
            f"  Recall@{k:<4} {res['recall'][k]:.4f}   "
            f"Success@{k:<4} {res['success'][k]:.4f}"
        )
    lines.append(f"  MRR         {res['mrr']:.4f}")
    lines.append(f"  nDCG@{NDCG_K}(이진이득) {res[f'ndcg@{NDCG_K}']:.4f}   "
                 f"bpref(retrieved-as-judged) {res['bpref']:.4f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=None, help="TREC run 파일(기본 B0)")
    ap.add_argument("--qrel", type=Path, default=None, help="qrel parquet(기본 examiner)")
    ap.add_argument("--k", type=int, nargs="+", default=[50, 100, 500])
    ap.add_argument("--family", action="store_true",
                    help="family 수준(F1 주지표)으로 평가 — ir_family_map 필요")
    ap.add_argument("--split", choices=["train", "dev", "test", SPLIT_B, "all"], default="all",
                    help="평가할 시점 분할(F9). 기본 all. test 는 최종 비교 전 봉인 — 명시해야 열림. "
                         "test_b 는 B층 확증분할이며 --unseal 없이는 열리지 않는다")
    ap.add_argument("--unseal", action="store_true",
                    help="B층 봉인 개봉(PLAN-047 동결 커밋 이후 1회) — 원장에 기록된다")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    args = ap.parse_args()

    from ..retrieval.bm25 import RUN_B0

    run = load_run(args.run or RUN_B0)
    if args.qrel is not None:
        qrel = load_qrel(args.qrel)
        if args.split != "all":
            import pandas as pd
            sp = pd.read_parquet(config.IR_SPLIT)
            keep = set(sp.loc[sp["split"] == args.split, "doc_id"])
            qrel = {q: pos for q, pos in qrel.items() if q in keep}
    else:
        qrel = load_qrel_for_split(args.split, unseal=args.unseal, reason=args.reason)
    if args.split == "test":
        print("⚠️  test 분할 평가 — 봉인 해제(최종 비교 전이면 사전등록 위반)")
    fam = None
    if args.family:
        from ..collect.bq_family_ir import load_family_map
        fam = load_family_map()
    res = evaluate(run, qrel, tuple(sorted(args.k)), family=fam)
    print(f"[split={args.split}]")
    print(_fmt(res))


if __name__ == "__main__":
    main()
