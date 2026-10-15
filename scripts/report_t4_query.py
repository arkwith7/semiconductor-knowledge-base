#!/usr/bin/env python3
"""PLAN-006 T4 S6 — 비교군별 구조화 검색식의 회수·검토량 리포트 (읽기 전용 · 그래프를 바꾸지 않는다).

분할 규율 (PLAN-006 §3.1′ 조건 5·6)
  train  매개변수(m_min · a′ 의 N)를 정하는 자리. 격자 결과를 그대로 싣는다.
  dev    **동결 매개변수 파일이 커밋된 뒤에만** 돈다(`--params`). 개발 단계 효과 확인.
  test · test_b  이 스크립트로는 열 수 없다(봉인).

지표 (§3.3′ A4) — 예산 B 마다 같은 정책을 다시 실행한다
  macro_recall   질의별 회수율 평균 (주 지표 · 실패 질의 = 0)
  micro_recall   쌍 기준 (보조)
  success_rate   예산 안 집합을 얻은 질의 비율
  size_median    성공 질의의 최종 집합 크기
  macro_recall_success_only  성공 질의만의 회수율 평균
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_search_query as Q  # noqa: E402
import ir_corpus  # noqa: E402
import kipris_emulator as K  # noqa: E402
from splits import SEALED, load_split  # noqa: E402

QREL = ROOT / "benchmark" / "assets" / "qrel_examiner.csv"
ARMS = ("a_prime", "c1")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bundle(params: dict) -> dict:
    """하류가 이 결과를 쓰려면 함께 받아야 하는 버전 묶음 (§3.3′)."""
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "scripts"], capture_output=True, text=True).stdout.strip())
    return {
        "corpus_sha256": ir_corpus.manifest()["sha256"],
        "concordance_sha256": sha(K.CONCORDANCE),
        "generator_commit": head, "generator_scripts_dirty": dirty,
        "params_sha256": hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest(),
        "params": params,
    }


def verify_freeze(spec: dict) -> None:
    """동결 명세의 자원 해시와 실제 파일이 같은지 확인한다 — 다르면 dev 를 돌리지 않는다."""
    import build_search_query as Qm
    checks = {
        "corpus": ir_corpus.manifest()["sha256"],
        "split": sha(ROOT / "benchmark" / "assets" / "split.csv"),
        "qrel": sha(QREL),
        "concordance": sha(K.CONCORDANCE),
        "translations": sha(Qm.TRANSLATIONS),
        "c3_weights": sha(ROOT / spec["resources"]["c3_weights"]["path"]),
        "concept_mapping": sha(ROOT / "mappings" / "concept_mapping.json"),
        "aliases": sha(ROOT / "mappings" / "abox_term_aliases.json"),
    }
    bad = {k: (spec["resources"][k]["sha256"], v) for k, v in checks.items() if spec["resources"][k]["sha256"] != v}
    if bad:
        raise SystemExit(f"ERROR: 동결 명세와 다른 자원: {bad}")


def load_gt(split: str, smap: dict[str, str]) -> dict[str, set[str]]:
    gt: dict[str, set[str]] = {}
    with QREL.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if smap.get(r["query_id"]) == split:
                gt.setdefault(r["query_id"], set()).add(r["doc_id"])
    return gt


def facets_for(arm: str, claim: str, df, lex, a_n: int):
    if arm == "a_prime":
        F = Q.facets_keywords(claim, df, a_n)
    elif arm in ("c1", "c2", "c3"):   # c2·c3 는 c1 과 같은 패싯 — 계획(planner) 단계만 다르다
        F = Q.facets_elements(claim, df, lex)
    elif arm == "c1_nosyn":   # 요소 패싯 · 온톨로지 동의어 없음 — 동의어의 추가 효과를 따로 재기 위한 셀
        F = Q.facets_elements(claim, df, None)
    else:
        raise SystemExit(f"ERROR: 아직 구현하지 않은 비교군: {arm}")
    return sorted(F, key=lambda f: (-f.df, f.seq))


def evaluate(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["success"]]
    gt_total = sum(r["gt"] for r in rows)
    return {
        "queries": len(rows),
        "macro_recall": round(sum(r["hit"] / r["gt"] for r in rows) / len(rows), 4),
        "micro_recall": round(sum(r["hit"] for r in rows) / gt_total, 4),
        "success_rate": round(len(ok) / len(rows), 4),
        "size_median": median([r["size"] for r in ok]) if ok else None,
        "macro_recall_success_only": round(sum(r["hit"] / r["gt"] for r in ok) / len(ok), 4) if ok else None,
        "no_facet_queries": sum(1 for r in rows if r["no_facet"]),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["train", "dev"])
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--budgets", default="100,200,500")
    ap.add_argument("--m-min", default="10", help="쉼표로 여러 값 = train 격자")
    ap.add_argument("--a-n", default="6", help="a′ 키워드 수 · 쉼표로 여러 값 = train 격자")
    ap.add_argument("--params", type=Path, help="dev 실행에 필요한 동결 매개변수 JSON")
    ap.add_argument("--strategy", default="single", help="single · multi(R1) · 쉼표로 둘 다")
    ap.add_argument("--lang", default="ko", help="ko(번역 없음) · tr(R2 공통 번역) · 쉼표로 둘 다")
    ap.add_argument("--df-max", default=str(Q.DF_MAX_FRAC), help="패싯 df 상한 비율 — a′·c 공통 · 쉼표로 여러 값 = train 격자")
    ap.add_argument("--subset", default="all", choices=["all", "learn", "check"],
                    help="train 안 패밀리 단위 구간 — c3 가중은 learn 에서만 배우고 비교는 check 에서 한다")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows-out", type=Path)
    a = ap.parse_args(argv)

    if a.split in SEALED:
        raise SystemExit("ERROR: 봉인 분할은 열 수 없다")
    if a.split == "dev":
        if not a.params or not a.params.exists():
            raise SystemExit("ERROR: dev 는 train 에서 정한 동결 매개변수(--params) 없이 돌지 않는다")
        spec = json.loads(a.params.read_text(encoding="utf-8"))
        verify_freeze(spec)
        m_mins, a_ns = [spec["rule"]["m_min"]], [spec["rule"]["a_n"]]
        a.df_max = str(spec["rule"]["df_max"])
    else:
        m_mins = [int(x) for x in a.m_min.split(",")]
        a_ns = [int(x) for x in a.a_n.split(",")]
    arms = a.arms.split(",")
    budgets = [int(x) for x in a.budgets.split(",")]

    smap = load_split()
    gt = load_gt(a.split, smap)
    C = ir_corpus.load(["doc_id", "is_candidate", "title", "abstract", "claims_full", "claims_independent",
                        "first_claim_original", "ipc", "concepts"])
    claim = dict(zip(C["doc_id"], C["first_claim_original"]))
    emu = K.Emulator(C)
    df, lex = Q.DF(emu), Q.Lexicon()
    fam = {r["doc_id"]: r["family_id"] for r in csv.DictReader(open(ROOT / "benchmark" / "assets" / "split.csv", encoding="utf-8"))}
    learn = {q for q, s in smap.items() if s == "train" and Q.family_bucket(fam[q]) < Q.C3_LEARN_FRAC}
    if a.split == "train" and a.subset != "all":
        gt = {q: v for q, v in gt.items() if (q in learn) == (a.subset == "learn")}
    queries = sorted(gt)[: a.limit or None]
    sel = jw = None
    if {"c2", "c3"} & set(arms):
        sel = Q.IpcSelector(C, exclude_docs={q for q, s in smap.items() if s != "train"})
    if "c3" in arms:
        train_gt = load_gt("train", smap)
        if a.split == "train":
            learn_gt = {q: v for q, v in train_gt.items() if q in learn}
            jw = Q.JudgmentWeights(learn_gt, {d: set(v) for d, v in zip(C["doc_id"], C["concepts"]) if v is not None})
        else:   # dev: train 전체로 배워 동결한 가중 파일만 읽는다
            w = spec["resources"]["c3_weights"]
            jw = Q.load_weights(ROOT / w["path"], w["sha256"])

    results, rows_all = [], []
    t0 = time.time()
    strategies = a.strategy.split(",")
    langs = a.lang.split(",")
    tr = Q.Translations() if "tr" in langs else None
    df_maxes = [float(x) for x in a.df_max.split(",")]
    cells = [(dm, lang, st, arm, a_n, m_min)
             for dm in df_maxes for lang in langs for st in strategies for arm in arms
             for a_n in (a_ns if arm == "a_prime" else [None])
             for m_min in (m_mins if st == "single" else [None])]
    for df_max, lang, strategy, arm, a_n, m_min in cells:
        Q.DF_MAX_FRAC = df_max   # 패싯·번역 후보 선택이 이 상한을 읽는다 — a′·c 공통
        for B in budgets:
            rows = []
            for q in queries:
                F = facets_for(arm, claim.get(q) or "", df, lex, a_n or 0)
                if lang == "tr":
                    F = tr.apply(F, df)
                if not F:
                    rows.append({"q": q, "hit": 0, "gt": len(gt[q]), "success": False, "size": None, "no_facet": True, "runs": 0})
                    continue
                if strategy == "single":
                    hist, best, S = Q.adjust(F, emu, budget=B, m_min=m_min, ipc_codes=None, exclude=(q,))
                    rows.append({"q": q, "hit": len(set(S) & gt[q]), "gt": len(gt[q]), "success": best is not None,
                                 "hit_ids": "|".join(sorted(set(S) & gt[q])),
                                 "size": best.size if best else None, "no_facet": False, "runs": len(hist),
                                 "facets": len(F), "k_final": best.k if best else None})
                else:
                    planner = Q.plan_multi_adaptive if strategy == "adaptive" else Q.plan_multi
                    ipc_narrow = sel.choose([Q.concept_local(f.concept) for f in F]) if arm in ("c2", "c3") else None
                    splitter = (lambda fs: Q.core_split_weighted(fs, jw)) if arm == "c3" else None
                    subs, S = planner(F, emu, budget=B, exclude=(q,), ipc_narrow=ipc_narrow or None, splitter=splitter)
                    rows.append({"q": q, "hit": len(set(S) & gt[q]), "gt": len(gt[q]), "success": bool(S),
                                 "hit_ids": "|".join(sorted(set(S) & gt[q])),
                                 "size": len(S) if S else None, "no_facet": False, "runs": len(subs),
                                 "facets": len(F), "accepted": sum(x.accepted for x in subs),
                                 "accepted_roles": "|".join(x.role for x in subs if x.accepted)})
            cfg = {"df_max": df_max, "lang": lang, "strategy": strategy, "arm": arm, "budget": B, "m_min": m_min, "a_n": a_n}
            results.append({**cfg, **evaluate(rows)})
            rows_all += [{**cfg, **r} for r in rows]
            print(json.dumps(results[-1], ensure_ascii=False), f"t={time.time() - t0:.0f}s", flush=True)

    params = {"df_max": df_maxes, "ADAPT_TRIES": Q.ADAPT_TRIES, "lang": langs, "translations_sha256": tr.sha if tr else None, "strategy": strategies, "MULTI_MAX_RUNS": Q.MULTI_MAX_RUNS, "PAIR_MAX": Q.PAIR_MAX, "m_min": m_mins, "a_n": a_ns, "MAX_RUNS": Q.MAX_RUNS, "DF_MIN": Q.DF_MIN, "DF_MAX_FRAC": Q.DF_MAX_FRAC,
              "MAX_FACETS": Q.MAX_FACETS, "SYN_MAX": Q.SYN_MAX,
              "IPC_MIN_DOCS": Q.IPC_MIN_DOCS, "IPC_TOP": Q.IPC_TOP, "C3_LEARN_FRAC": Q.C3_LEARN_FRAC, "C3_PRIOR": Q.C3_PRIOR}
    out = {"plan": "PLAN-006 T4", "split": a.split, "subset": a.subset, "queries": len(queries),
           "c3_learn_queries": len(learn) if a.split == "train" else "train 전체",
           "denominator": "코퍼스 안 심사관 인용(qrel_examiner) — 질의별 회수율의 분모",
           "bundle": bundle(params), "results": results}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.rows_out:
        a.rows_out.parent.mkdir(parents=True, exist_ok=True)
        with a.rows_out.open("w", encoding="utf-8", newline="") as fh:
            keys = sorted({k for r in rows_all for k in r})
            w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
            w.writeheader(); w.writerows(rows_all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
