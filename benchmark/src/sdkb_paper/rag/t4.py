"""T4 판정 — 하류 생성 층 비열등 (PLAN-047 §4.2 동결식 · §18.2 설계 · `make t4`).

**판정식과 마진은 이 파일이 정하지 않는다.** ε_T4=0.02 · η=0.01 은 결과를 보기 전에 PLAN-047 §4
에서 동결됐고(커밋 `67568c8`), 여기서는 **적용만** 한다. 임계를 인자로 받지 않는 것이 그 집행
장치다 — 호출자가 마진을 바꿀 수 있으면 동결이 아니다.

    T4 = ( LB₉₅(Δ 인용 정확도(전체)) > −ε_T4 )  ∧  ( UB₉₅(Δ 환각률) < +η )
    Δ = P1 − B3_rrf · 질의단위 paired bootstrap 10,000 · 양측 · seed 고정

**비율의 재계산이다**(§18.2-3). 인용 정확도·환각률은 질의당 평균이 아니라 **인용 식별자 전량을
분모로 하는 비율**이므로(§11.4 동결), 리샘플에서도 `Σ분자 / Σ분모` 를 다시 구한다. 질의당 비율의
평균으로 바꾸면 그것은 CI 가 아니라 **다른 지표**다.

CLI: `uv run python -m sdkb_paper.rag.t4 --split test_b --unseal --reason "…" [--write]`
"""
from __future__ import annotations

import argparse
import hashlib
import json

from .. import config
from . import frozen
from . import score as sc

# ── PLAN-047 §4.2 동결 마진 — 이 파일에서 바꿀 수 없다 ──────────────────────────
EPS_T4 = 0.02   # 인용 정확도 비열등 마진 (T1 의 ε 승계 · 같은 [0,1] 비율 척도)
ETA = 0.01      # 환각률 상승 허용 (ε/2 · 손해가 비대칭)
N_BOOT = 10000

BASELINE_ARM = "B3_rrf"
NEW_ARM = "P1"

# (지표, 분자, 분모) — `aggregate()` 의 정의와 문자 그대로 같아야 한다.
RATIOS = {
    "citation_precision": ("n_cited_correct", "n_cited", None),
    "hallucination_rate": ("n_cited_out_of_context", "n_cited", None),
    "citation_precision_cond": ("n_cited_correct", "n_cited", "cond"),
    "quote_grounded_rate": ("n_quotes_grounded", "n_quotes", None),
}
DECISION_KEYS = ("citation_precision", "hallucination_rate")


def per_query_counts(split: str, *, unseal: bool = False, reason: str = "") -> dict[str, dict]:
    """팔 → qid → 질의별 계수(회차 3회 **평균**). §18.2-2.

    회차 평균을 점추정으로 쓰는 것은 §4.2 의 요구다. 회차 간 분산은 `score.py` 가 따로 낸다
    (§1-11 "비결정성을 숨기지 않는다") — 여기서 뭉개는 것이 아니라 **다른 곳에서 보고**된다.
    """
    import pandas as pd

    from ..analysis.metrics import load_qrel, load_qrel_for_split

    if split == frozen.SPLIT_B:
        qrel = load_qrel_for_split(split, unseal=unseal, reason=reason or "C2′ T4 판정")
    else:
        qrel = load_qrel(config.IR_QREL_TEST_SEALED)
    corpus = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "text_main"])
    doc_text = {str(d): ("" if t is None else str(t))
                for d, t in zip(corpus["doc_id"], corpus["text_main"])}

    fields = ("n_cited", "n_cited_correct", "n_cited_out_of_context",
              "n_quotes", "n_quotes_grounded", "n_pos_in_context")
    out: dict[str, dict] = {}
    inputs: dict[str, str] = {}
    for arm in frozen.ARMS:
        acc: dict[str, list[dict]] = {}
        for path in sorted(config.RAG_GEN_DIR.glob(f"gen_*_{split}_{arm}_rep*.jsonl")):
            _, recs = sc.load_jsonl(path)
            inputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            for rec in recs:
                qid = rec.get("qid", "")
                acc.setdefault(qid, []).append(
                    sc.score_one(rec, qrel.get(qid, set()), doc_text))
        out[arm] = {
            qid: {f: sum(s[f] for s in ss) / len(ss) for f in fields}
            for qid, ss in acc.items()
        }
    out["_inputs"] = inputs
    return out


def _ratio(rows: list[dict], num: str, den: str, cond: bool) -> float | None:
    """`aggregate()` 와 **문자 그대로 같은** 비율. 조건부는 팔마다 자기 분모를 쓴다(§11.4-①).

    조건부의 분모가 팔 사이에 다른 것은 결함이 아니라 정의다 — 컨텍스트에 정답이 있는 질의가
    팔마다 다르기 때문이다(A층 B3 83 · P1 73 · PLAN-038 §16.0-2 ⓑ). 그래서 **판정에 쓰지 않고
    보고만 한다**(§4.2).
    """
    rs = [r for r in rows if r["n_pos_in_context"] > 0] if cond else rows
    d = sum(r[den] for r in rs)
    return (sum(r[num] for r in rs) / d) if d > 0 else None


def _ratio_delta(new: list[dict], base: list[dict], num: str, den: str,
                 cond: bool = False) -> float | None:
    rn, rb = _ratio(new, num, den, cond), _ratio(base, num, den, cond)
    return None if rn is None or rb is None else rn - rb


def bootstrap_ratio_delta(new_q: dict, base_q: dict, num: str, den: str, *,
                          cond: bool = False, n_boot: int = N_BOOT,
                          seed: int = config.SEED) -> dict:
    """Δ(비율)의 점추정과 95 % CI — 질의 단위 페어드 · 비율 재계산(§18.2-3·4·5)."""
    import numpy as np

    qids = sorted(set(new_q) & set(base_q))     # 페어드 — 두 팔이 같은 질의를 본다
    new = [new_q[q] for q in qids]
    base = [base_q[q] for q in qids]
    m = len(qids)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, m, size=(n_boot, m))
    boot, n_dropped = [], 0
    for row in idx:
        d = _ratio_delta([new[i] for i in row], [base[i] for i in row], num, den, cond)
        if d is None:      # 리샘플의 분모가 0 — 버리고 센다(§18.2-4 · 숨기지 않는다)
            n_dropped += 1
            continue
        boot.append(d)
    arr = np.array(boot)
    lb, ub = (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))) if len(arr) else (None, None)
    p_two = (2.0 * min(float((arr <= 0).mean()), float((arr >= 0).mean()))) if len(arr) else None
    return {
        "n_queries": m,
        "delta": _ratio_delta(new, base, num, den, cond),
        "mean_new": _ratio(new, num, den, cond),
        "mean_base": _ratio(base, num, den, cond),
        "lb95": lb, "ub95": ub,
        "p_two_sided": min(p_two, 1.0) if p_two is not None else None,
        "n_boot": n_boot, "n_dropped": n_dropped, "seed": seed,
    }


def verdict(stats: dict) -> dict:
    """§4.2 판정식 — 두 조건의 논리곱. 마진은 모듈 상수이며 인자로 받지 않는다."""
    prec, hall = stats["citation_precision"], stats["hallucination_rate"]
    c1 = prec["lb95"] is not None and prec["lb95"] > -EPS_T4
    c2 = hall["ub95"] is not None and hall["ub95"] < ETA
    return {
        "eps_t4": EPS_T4, "eta": ETA,
        "cond_precision_noninferior": bool(c1),
        "cond_hallucination_bounded": bool(c2),
        "T4": bool(c1 and c2),
    }


def run(split: str, *, unseal: bool = False, reason: str = "") -> dict:
    counts = per_query_counts(split, unseal=unseal, reason=reason)
    inputs = counts.pop("_inputs")
    stats = {
        key: bootstrap_ratio_delta(counts[NEW_ARM], counts[BASELINE_ARM], num, den,
                                   cond=(mode == "cond"))
        for key, (num, den, mode) in RATIOS.items()
    }
    return {
        "frozen": frozen.frozen_manifest(
            runset=frozen.RUNSET_B if split == frozen.SPLIT_B else frozen.RUNSET,
            split=split,
            status=frozen.STATUS_B if split == frozen.SPLIT_B else frozen.STATUS),
        "contrast": f"{NEW_ARM} − {BASELINE_ARM}",
        "stats": stats,
        "verdict": verdict(stats),
        "inputs": inputs,
        "plan": "PLAN-047 §4.2 (판정식·마진 동결) · §18.2 (산출 설계)",
    }


def to_markdown(rep: dict) -> str:
    v = rep["verdict"]
    labels = {
        "citation_precision": "**인용 정확도 (전체)** ← T4 주지표",
        "hallucination_rate": "**환각률** ← T4 둘째 조건",
        "citation_precision_cond": "인용 정확도 (근거 존재 질의 조건부) · 보고만",
        "quote_grounded_rate": "근거 문장 일치 (결정적 하한) · 보고만",
    }
    lines = [
        "# T4 판정 — 하류 생성 층 비열등 (PLAN-047 §4.2 · RQ5 · C2′)",
        "",
        f"**판정: T4 = {'통과' if v['T4'] else '실패'}**  "
        f"(인용 정확도 비열등 {'✅' if v['cond_precision_noninferior'] else '❌'} · "
        f"환각률 상한 {'✅' if v['cond_hallucination_bounded'] else '❌'})",
        "",
        f"판정식과 마진은 **결과를 보기 전에** 동결됐다 — `ε_T4 = {v['eps_t4']}` · `η = {v['eta']}` "
        "(PLAN-047 §4 · 동결 커밋 `67568c8`).",
        f"대비 = `{rep['contrast']}` · 질의 단위 페어드 부트스트랩 "
        f"{rep['stats']['citation_precision']['n_boot']:,}회 · 양측 · seed 고정 · 회차 3회 평균.",
        "",
        "| 지표 | 기준(B3_rrf) | 새 팔(P1) | Δ | 95% CI | *p* |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for k, label in labels.items():
        s = rep["stats"][k]
        ci = "—" if s["lb95"] is None else f"[{s['lb95']:+.4f}, {s['ub95']:+.4f}]"
        lines.append(
            f"| {label} | {s['mean_base']:.4f} | {s['mean_new']:.4f} | {s['delta']:+.4f} | "
            f"{ci} | {s['p_two_sided']:.3f} |")
    dropped = sum(s["n_dropped"] for s in rep["stats"].values())
    lines += [
        "",
        f"페어드 질의 {rep['stats']['citation_precision']['n_queries']}건 · "
        f"분모 0 으로 버린 리샘플 **{dropped}건**(§18.2-4).",
        "",
        "**비열등이 우월은 아니다.** T4 통과는 *\"생성 층에서 뒷걸음치지 않았다\"* 이며, "
        "*\"RAG 답변이 좋아졌다\"* 로 쓰지 않는다(§1-11 다섯째 금지 · 원고 §7.6 결론 규칙).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="C2′ T4 판정 (PLAN-047 §4.2)")
    ap.add_argument("--split", choices=[frozen.SPLIT, frozen.SPLIT_B], default=frozen.SPLIT_B)
    ap.add_argument("--unseal", action="store_true", help="B층 봉인 개봉(원장 기록)")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    ap.add_argument("--write", action="store_true", help="JSON·표를 파일로 쓴다")
    a = ap.parse_args()
    if a.split != frozen.SPLIT_B:
        print("[차단] T4 는 B층 확증 판독에만 적용한다 — A층은 탐색적이며 마진 동결 이전이다"
              "(PLAN-047 §18.3).")
        return 2

    rep = run(a.split, unseal=a.unseal, reason=a.reason)
    if not rep["inputs"]:
        print("[없음] 생성 산출물이 없다 — 먼저 `make rag` 를 돌린다.")
        return 1
    print(to_markdown(rep))
    if a.write:
        config.RAG_SCORE_DIR.mkdir(parents=True, exist_ok=True)
        (config.RAG_SCORE_DIR / "rag_t4_verdict_test_b.json").write_text(
            json.dumps(rep, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        table = config.TABLES / "rag_t4_verdict_test_b.md"
        table.parent.mkdir(parents=True, exist_ok=True)
        table.write_text(to_markdown(rep), encoding="utf-8")
        print(f"[기록] {table.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
