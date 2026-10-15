#!/usr/bin/env python3
"""PLAN-006 T4 — 동결된 실행 산출물에서 지표·대비를 계산한다 (읽기 전용 · 결정적).

산식 (동결 명세 §metrics 와 같다)
  A 주 분모   코퍼스 안 심사관 인용(qrel_examiner) — 질의별 회수율 = |회수 ∩ 정답| / |정답|, 정답 ≥1 질의 평균(macro)
  B 보조      비NPL 심사관 인용 전체(prior_art_edges · examiner · ~is_npl) — 코퍼스 밖 정답은 회수 불가로 분모에만,
              코퍼스 안 정답이 0 인 질의도 0 으로 넣어 평균
  C 보조      A 에서 검색 텍스트(초록·청구항)가 없는 정답 문서를 뺀 것 — 정답이 남지 않은 질의는 제외
  언어별      언어 L 정답이 ≥1 인 질의만, 질의별 |회수 ∩ 정답_L| / |정답_L| 평균 + 쌍 기준(micro) 병기
              (일본어는 별도 층으로 보고하되 A·B·C 전체 지표에서는 빼지 않는다)
  대비        질의 단위 paired bootstrap (A 지표) · 반복 10,000 · 시드 고정 · 95% 백분위 구간
              — 동결된 단일 실행에서 질의 표본의 불확실성만 잰다(LLM 의 실행 간 확률 변동은 포함하지 않는다)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ir_corpus  # noqa: E402
import report_t4_query as R  # noqa: E402
from splits import load_split  # noqa: E402

SEED = 20261011
N_BOOT = 10_000


def raw_counts(split: str, smap) -> dict[str, int]:
    e = pd.read_parquet(ROOT / "data" / "patents" / "prior_art_edges.parquet")
    e = e[(e["source_type"] == "examiner") & (~e["is_npl"])]
    e = e.assign(q=e["target_patent_id"].str.replace("patent:", "", regex=False))
    e = e[e["q"].map(smap) == split].drop_duplicates(["q", "cited_id"])
    return e.groupby("q").size().to_dict()


def load_hits(rule_rows: Path | None, llm: list[Path], budget: int) -> dict[str, dict[str, set[str]]]:
    arms: dict[str, dict[str, set[str]]] = {}
    sizes: dict[str, dict[str, int]] = {}
    if rule_rows:
        for r in csv.DictReader(open(rule_rows, encoding="utf-8")):
            if int(r["budget"]) != budget:
                continue
            arms.setdefault(r["arm"], {})[r["q"]] = set(x for x in (r.get("hit_ids") or "").split("|") if x)
            sizes.setdefault(r["arm"], {})[r["q"]] = int(float(r["size"])) if r.get("size") not in ("", None) else 0
    for p in llm:
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            if int(r["budget"]) != budget:
                continue
            arms.setdefault(r["arm"], {})[r["q"]] = set(r["hit_ids"])
            sizes.setdefault(r["arm"], {})[r["q"]] = len(r["union"])
    return arms, sizes


def metrics(hits: dict[str, set[str]], sizes: dict[str, int], gt, raw, textless, lang) -> dict:
    qs = sorted(gt)
    rA = {q: len(hits.get(q, set()) & gt[q]) / len(gt[q]) for q in qs}
    allq = sorted(raw)
    rB = [len(hits.get(q, set()) & gt.get(q, set())) / raw[q] for q in allq]
    rC = {}
    for q in qs:
        g = gt[q] - textless
        if g:
            rC[q] = len(hits.get(q, set()) & g) / len(g)
    out = {"queries_A": len(qs), "A_macro": round(float(np.mean(list(rA.values()))), 4),
           "A_micro": round(sum(len(hits.get(q, set()) & gt[q]) for q in qs) / sum(len(gt[q]) for q in qs), 4),
           "queries_B": len(allq), "B_macro": round(float(np.mean(rB)), 4),
           "B_micro": round(sum(len(hits.get(q, set()) & gt.get(q, set())) for q in allq) / sum(raw.values()), 4),
           "queries_C": len(rC), "C_macro": round(float(np.mean(list(rC.values()))), 4),
           "success_rate": round(float(np.mean([sizes.get(q, 0) > 0 for q in qs])), 4),
           "review_size_median": float(np.median([sizes.get(q, 0) for q in qs]))}
    for L in ("ko", "en", "ja"):
        per, h, n = [], 0, 0
        for q in qs:
            g = {d for d in gt[q] if lang.get(d) == L}
            if g:
                k = len(hits.get(q, set()) & g)
                per.append(k / len(g)); h += k; n += len(g)
        out[f"{L}_queries"] = len(per)
        out[f"{L}_macro"] = round(float(np.mean(per)), 4) if per else None
        out[f"{L}_micro"] = round(h / n, 4) if n else None
    return out, rA


def boot(x: dict, y: dict) -> list[float]:
    qs = sorted(set(x) & set(y))
    v = np.array([x[q] - y[q] for q in qs])
    m = v[np.random.default_rng(SEED).integers(0, len(v), (N_BOOT, len(v)))].mean(1)
    return [round(float(v.mean()), 4), round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4), len(qs)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["train", "dev"])
    ap.add_argument("--rule-rows", type=Path)
    ap.add_argument("--llm", type=Path, nargs="*", default=[])
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--restrict-to-run", action="store_true",
                    help="train 부분 구간 실행용 — 모든 비교군이 실행한 질의로 분모를 좁힌다. dev 에서는 쓰지 않는다")
    a = ap.parse_args(argv)
    smap = load_split()
    gt = R.load_gt(a.split, smap)
    raw = raw_counts(a.split, smap)
    C = ir_corpus.load(["doc_id", "lang", "abstract", "claims_full", "claims_independent"])
    lang = dict(zip(C["doc_id"], C["lang"]))
    has_text = (C["abstract"].fillna("").str.len() > 0) | (C["claims_full"].fillna("").str.len() > 0) | \
               (C["claims_independent"].fillna("").str.len() > 0)
    textless = set(C.loc[~has_text, "doc_id"])
    arms, sizes = load_hits(a.rule_rows, a.llm, a.budget)
    ran = set.intersection(*(set(v) for v in arms.values()))
    if a.restrict_to_run:
        if a.split == "dev":
            raise SystemExit("ERROR: dev 는 전 질의 실행이 원칙이다 — --restrict-to-run 을 쓰지 않는다")
        gt = {q: v for q, v in gt.items() if q in ran}
        raw = {q: v for q, v in raw.items() if q in ran}
    else:
        missing = {arm: len(set(gt) - set(v)) for arm, v in arms.items() if set(gt) - set(v)}
        if missing:
            raise SystemExit(f"ERROR: 실행하지 않은 질의가 있다 {missing} — 실패는 0 으로 기록된 행이어야 한다")
    res, per = {}, {}
    for arm in sorted(arms):
        res[arm], per[arm] = metrics(arms[arm], sizes[arm], gt, raw, textless, lang)
    contrasts = {}
    for name, (x, y) in {"primary d-b": ("d", "b"), "aux c3-a_prime": ("c3", "a_prime"),
                         "desc b-a_prime": ("b", "a_prime"), "desc d-c3": ("d", "c3"),
                         "desc c1-c1_nosyn": ("c1", "c1_nosyn"), "desc c2-c1": ("c2", "c1"), "desc c3-c2": ("c3", "c2")}.items():
        if x in per and y in per:
            contrasts[name] = boot(per[x], per[y])
    out = {"split": a.split, "budget": a.budget, "seed": SEED, "n_boot": N_BOOT,
           "denominators": {"A_pairs": sum(len(v) for v in gt.values()), "B_pairs": sum(raw.values()),
                            "textless_gt_pairs": sum(len(v & textless) for v in gt.values())},
           "arms": res, "contrasts": contrasts}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
