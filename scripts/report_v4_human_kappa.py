#!/usr/bin/env python3
"""PLAN-005 §5 V4-2 — 사람 2인 코딩 집계: κ · 합의율 · LLM 대조 (읽기 전용).

채워진 코딩 시트 두 부를 받아 아래를 낸다.

  1. **사람 2인 κ 와 합의율** — 이것이 V4-2 가 요구한 수다(하류 §1-12).
     `NA` 쌍은 κ 계산에서 빼고 건수만 보고한다.
  2. **셀별 분해** — 불일치 / 둘다관련 / 둘다무관. 층마다 뜻이 다르다.
  3. **스크리너가 놓친 관련 문헌 비율(추정)** — '둘다무관' 층에서 사람이 관련이라 한 비율에
     추출 가중(표본/모집단)을 곱한다. **이 층에서 발견되는 관련 건이 곧 LLM 스크리닝의 위양성
     아닌 위음성이며, 사람을 빼면 알 수 없는 값이다.**
  4. **LLM–사람 일치율** — 사람 준거 대비 j1·j2 각각. *"LLM 1차 스크리닝이 쓸 만한가"* 의 답.

**사람 준거의 정의.** 조정(adjudication) 파일이 있으면 그 합의값을 준거로 쓴다. 없으면
**두 코더가 일치한 행만** 준거로 쓰고, 갈린 행은 제외한 뒤 그 사실과 건수를 함께 보고한다 —
한쪽 코더를 임의로 고르는 것은 준거를 만드는 것이 아니라 고르는 것이다.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "interim" / "v4_coding"
OUT = ROOT / "data" / "reports" / "v4_human_coding.json"


def norm(v):
    s = str(v).strip().upper()
    if s in ("1", "TRUE", "Y", "O"):
        return 1
    if s in ("0", "FALSE", "N", "X"):
        return 0
    return None  # NA · 공란 · 그 밖


def kappa(a: list[int], b: list[int]) -> tuple[float, float]:
    """Cohen's κ (이진). 반환 (관측일치율, κ)."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, default=DIR / "v4_coding_sheet_A.csv")
    ap.add_argument("--b", type=Path, default=DIR / "v4_coding_sheet_B.csv")
    ap.add_argument("--key", type=Path, default=DIR / "v4_coding_key.json")
    ap.add_argument("--adjudicated", type=Path, default=DIR / "v4_adjudicated.csv",
                    help="item_id,relevance 두 컬럼. 없으면 일치행만 준거로 쓴다")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    key = pd.DataFrame(json.loads(args.key.read_text(encoding="utf-8"))["items"])
    A = pd.read_csv(args.a)[["item_id", "relevance", "confidence"]].rename(
        columns={"relevance": "a", "confidence": "conf_a"})
    B = pd.read_csv(args.b)[["item_id", "relevance"]].rename(columns={"relevance": "b"})
    d = key.merge(A, on="item_id").merge(B, on="item_id")
    d["a"] = d.a.map(norm); d["b"] = d.b.map(norm)

    unfilled = int(d.a.isna().sum() + d.b.isna().sum())
    both = d.dropna(subset=["a", "b"]).copy()
    if both.empty:
        print("채워진 행이 없다 — 코딩 시트를 먼저 회수할 것."); return 1
    po, k = kappa(list(both.a.astype(int)), list(both.b.astype(int)))

    per_cell = {}
    for cell, g in both.groupby("cell"):
        if len(g) >= 2:
            p, kk = kappa(list(g.a.astype(int)), list(g.b.astype(int)))
            per_cell[cell] = {"n": len(g), "agreement": round(p, 4),
                              "kappa": (None if pd.isna(kk) else round(kk, 4)),
                              "a_relevant": round(float(g.a.mean()), 4),
                              "b_relevant": round(float(g.b.mean()), 4)}

    # 사람 준거
    if args.adjudicated.exists():
        adj = pd.read_csv(args.adjudicated)[["item_id", "relevance"]]
        adj["h"] = adj.relevance.map(norm)
        ref = both.merge(adj[["item_id", "h"]], on="item_id").dropna(subset=["h"])
        ref_src = f"조정 파일 {args.adjudicated.name}"
    else:
        ref = both[both.a == both.b].copy(); ref["h"] = ref.a
        ref_src = "두 코더 일치행만 (조정 파일 없음 — 갈린 행은 제외했다)"

    llm = {}
    for j in ("j1", "j2"):
        if len(ref):
            llm[j] = {"agreement_with_human": round(float((ref[j].astype(int) == ref.h).mean()), 4),
                      "n": int(len(ref))}

    # 스크리너 위음성 추정 — '둘다무관' 층
    miss = None
    bn = ref[ref.cell == "둘다무관"]
    if len(bn):
        pop = 489  # v4_screening.csv 의 둘다무관 모집단
        rate = float(bn.h.mean())
        miss = {"stratum_n": int(len(bn)), "population": pop,
                "human_relevant_rate": round(rate, 4),
                "estimated_missed_docs": round(rate * pop, 1),
                "note": ("LLM 둘 다 '무관'이라 한 489건 가운데 사람이 '관련'이라 볼 비율의 추정. "
                         "이 값이 곧 LLM 스크리닝의 위음성이며 사람 없이는 알 수 없다.")}

    rep = {"generated": str(date.today()), "plan": "PLAN-005 §5 V4-2 (사람 2인 코딩)",
           "coders": "같은 연구실 2인 (설계자 아님)", "scale": "1 / 0 / NA (이진 + 판단불가)",
           "items": int(len(d)), "judged_by_both": int(len(both)),
           "unfilled_or_NA_cells": unfilled,
           "human_agreement": round(po, 4),
           "cohen_kappa_human": (None if pd.isna(k) else round(k, 4)),
           "disagreements": int((both.a != both.b).sum()),
           "per_cell": per_cell, "reference_source": ref_src,
           "llm_vs_human": llm, "screener_false_negative_estimate": miss}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    # 조정 대상 목록
    dis = both[both.a != both.b][["item_id", "cell", "a", "b"]]
    if len(dis):
        p = DIR / "v4_to_adjudicate.csv"
        dis.assign(relevance="").to_csv(p, index=False)
        print(f"조정 대상 {len(dis)}행 → {p}  (합의값을 relevance 에 적고 --adjudicated 로 재실행)")

    print(f"\n사람 2인 · 판정된 {len(both)}행")
    print(f"  합의율 {po:.4f} · **κ {k:.4f}** · 불일치 {int((both.a!=both.b).sum())} · 미기입/NA {unfilled}")
    for c, v in per_cell.items():
        print(f"    {c:8} n={v['n']:3} 합의={v['agreement']:.3f} κ={v['kappa']}")
    if llm:
        print(f"  LLM–사람 일치({ref_src}): j1={llm['j1']['agreement_with_human']} · j2={llm['j2']['agreement_with_human']}")
    if miss:
        print(f"  스크리너 위음성 추정: 둘다무관 489건 중 약 {miss['estimated_missed_docs']}건이 실제 관련")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
