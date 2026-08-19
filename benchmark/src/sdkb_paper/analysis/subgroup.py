"""하위집단 분해 T2 (PLAN-018 §7.3 M4-10 · 원고 §5.2·5.3 · T-gate T2).

두 시스템의 family Recall@100 을 하위집단별로 분해해 **국소 회귀**(max drop)를 잰다 — T2 안전성 게이트
입력. 하위집단 축:

- **정답 언어(cross-lingual):** 질의 자체는 전량 한국어이므로 **정답(positive)의 언어 구성**으로 나눈다
  (KR-only / 외국포함 / 혼합). 정답의 39% 가 영어·2% 일본어(SPEC-007) — 언어중립 개념 온톨로지팔이
  값을 증명할 무대(원고 H2b). 이 축이 T2 의 핵심 KR/외국 차원이다.
- **공정군(process group):** 질의 지배 개념 축(Process·SubProcess / Device / Material / FailureMode …).
- **거절근거(2026-07-27 배선):** 벤더 파생 `rejection_basis.csv`(config.REJECTION_BASIS)의 법조 라벨.
  **주의 — 자원의 실상:** 상류 원본 1,000건 중 진보성(제29조 제2항) 400 · 신규성(제1항) 14이며
  **신규성 단독 거절은 0건**(14건 전부 진보성과 병존) · 600건은 구조화 라벨 없음. 따라서
  "신규성 vs 진보성" 대비는 성립하지 않는다 — 집단은 `inventiveness` / `novelty+inventiveness`
  / `unlabeled` 셋이고 신규성 병존군은 MIN_N 미달(dev 4·test 3)이라 **확정 결론 금지**다.
- **어휘 중첩(F11 · 원고 §5.3):** `analysis/overlap.py` 의 dev-Q1 동결 임계로 low/high 이분.

최소 질의수(기본 20) 미달 하위집단은 확정결론 금지 · 표에 n 명기(M4-10).

- **경계:** qrel 읽음(analysis) · 순위생성 없음 · dev 로만.
CLI: `python -m sdkb_paper.analysis.subgroup --a RUN_NEW --b RUN_OLD [--split dev]`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .. import config
from .bootstrap import per_query_recall
from .metrics import SPLIT_B, load_qrel, load_qrel_for_split, load_run

MIN_N = 20   # 하위집단 최소 질의수(미달 = 확정결론 금지)
# B층 질의에는 공정군·거절근거 라벨의 **원천이 없다**(PLAN-047 §12.3). A층 공정군은 파생값이
# 아니라 SIRP 코호트의 수집 출처이고, 거절근거 CSV 도 A층 산출이다. IPC 로 추정해 채우면
# 빌드는 성공하고 하위집단 분석만 거짓이 된다 — 그래서 없는 것은 없다고 적는다.
NO_LABEL = "라벨없음"


def positive_lang_label(pos_docs: set[str], doc_lang: dict[str, str]) -> str:
    """정답 문서 언어 구성 → 'kr_only' / 'has_foreign' / 'unknown'."""
    langs = {doc_lang.get(d, "") for d in pos_docs}
    langs.discard("")
    if not langs:
        return "unknown"
    foreign = any(lg != "ko" for lg in langs)
    return "has_foreign" if foreign else "kr_only"


def rejection_labels() -> dict[str, str]:
    """doc_id → 'inventiveness' | 'novelty+inventiveness' | 'unlabeled' (벤더 파생 CSV).

    신규성 단독 집단은 자원에 존재하지 않는다(상류 실측 0건) — 없는 집단을 만들지 않는다.
    """
    import csv

    out: dict[str, str] = {}
    if not config.REJECTION_BASIS.exists():
        return out
    with config.REJECTION_BASIS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nov, inv = r["has_novelty"] == "1", r["has_inventiveness"] == "1"
            out[r["doc_id"]] = ("novelty+inventiveness" if nov and inv else
                                "novelty_only" if nov else
                                "inventiveness" if inv else "unlabeled")
    return out


def query_labels(qrel: dict[str, set[str]], split: str | None = None,
                 lex_qrel: dict[str, set[str]] | None = None) -> dict[str, dict[str, str]]:
    """질의 → {'pos_lang', 'proc_group', 'rejection', 'lex_overlap'}.

    split 을 주면 F11 어휘중첩 라벨(동결 임계)까지 붙인다 — 임계는 dev 에서만 산출된다.
    """
    import pandas as pd

    from ..ontology.concept_axis import load_axis
    axis = load_axis()
    from ..retrieval import layers

    df = pd.read_parquet(
        config.IR_CORPUS,
        columns=layers.with_layer_cols(["doc_id", "lang", "concepts", "is_query"]),
    )
    doc_lang = dict(zip(df["doc_id"].astype(str), df["lang"].astype(str)))
    # T2 하위집단은 **A층 판정 전용**이다(PLAN-045 D5). B층 질의를 섞으면 δ 판정의
    # 표본이 사전등록과 달라진다 — 그것은 재측정이 아니라 다른 검정이다.
    q_a = layers.queries_of(df, layers.LAYER_A)
    qconcepts = {str(d): (list(c) if c is not None else [])
                 for d, c in zip(q_a["doc_id"], q_a["concepts"])}
    a_layer_qids = set(qconcepts)

    def proc_group(qid: str) -> str:
        axes = [axis.get(c, "") for c in qconcepts.get(qid, [])]
        for grp, members in [("process", {"Process", "SubProcess"}),
                             ("device", {"Device"}),
                             ("failure", {"FailureMode"}),
                             ("material", {"Material"})]:
            if any(a in members for a in axes):
                return grp
        return "other"

    rej = rejection_labels()
    lex: dict[str, str] = {}
    if split:
        from .overlap import labels as overlap_labels
        # B층은 정답지가 다른 파일이라 명시적으로 넘긴다(D-34). 임계는 dev 동결값 그대로.
        lex = overlap_labels(split, qrel=lex_qrel)

    out = {}
    for qid, pos in qrel.items():
        if not pos:
            continue
        in_a = qid in a_layer_qids
        out[qid] = {"pos_lang": positive_lang_label(pos, doc_lang),
                    # A층 밖(=B층) 질의는 두 축의 라벨 원천이 없다 — "other"·"unlabeled" 로
                    # 뭉뚱그리면 없는 집단이 있는 것처럼 보인다.
                    "proc_group": proc_group(qid) if in_a else NO_LABEL,
                    "rejection": rej.get(qid, "unlabeled") if in_a else NO_LABEL,
                    "lex_overlap": lex.get(qid, "unknown")}
    return out


def by_subgroup(run, qrel, fam, labels, dim: str, k: int = 100) -> dict[str, dict]:
    """dim(pos_lang|proc_group)별 평균 R@k + n. fam 는 family 지도."""
    pq = per_query_recall(run, qrel, k=k, family=fam)
    groups: dict[str, list[float]] = {}
    for qid, r in pq.items():
        g = labels.get(qid, {}).get(dim, "unknown")
        groups.setdefault(g, []).append(r)
    return {g: {"n": len(v), "recall": sum(v) / len(v)} for g, v in groups.items()}


def compare(run_new, run_old, qrel, fam, labels, dim: str, k: int = 100) -> dict:
    """하위집단별 R@k(new,old) + drop(old−new). max drop = T2 입력."""
    a = by_subgroup(run_new, qrel, fam, labels, dim, k)
    b = by_subgroup(run_old, qrel, fam, labels, dim, k)
    rows, max_drop = [], -1.0
    for g in sorted(set(a) | set(b)):
        rn, ro = a.get(g, {}).get("recall", 0.0), b.get(g, {}).get("recall", 0.0)
        n = a.get(g, {}).get("n", b.get(g, {}).get("n", 0))
        drop = ro - rn
        rows.append({"group": g, "n": n, "r_new": rn, "r_old": ro, "drop": drop,
                     "reliable": n >= MIN_N})
        if n >= MIN_N and drop > max_drop:
            max_drop = drop
    return {"dim": dim, "rows": rows, "max_drop": max_drop}


def _fmt(res: dict, delta: float) -> str:
    lines = [f"  [{res['dim']}]  max_drop(신뢰집단만) = {res['max_drop']:+.4f}"
             f"  {'≥δ 국소회귀!' if res['max_drop'] >= delta else '(< δ 안전)'}"]
    lines.append(f"    {'집단':<14}{'n':>5}{'R_new':>9}{'R_old':>9}{'drop':>9}")
    for r in res["rows"]:
        flag = "" if r["reliable"] else "  (n<20·비확정)"
        lines.append(f"    {r['group']:<14}{r['n']:>5}{r['r_new']:>9.4f}"
                     f"{r['r_old']:>9.4f}{r['drop']:>+9.4f}{flag}")
    return "\n".join(lines)


DIM_TITLES = {
    "rejection": "거절근거 (특허법 제29조)",
    "lex_overlap": "어휘 중첩 (F11 · dev-Q1 동결 임계)",
    "pos_lang": "정답 언어 구성 (교차언어)",
    "proc_group": "공정군 (질의 지배 개념축)",
}
GROUP_LABELS = {
    "inventiveness": "진보성만(제2항)", "novelty+inventiveness": "신규성+진보성(제1·2항)",
    "novelty_only": "신규성만(제1항)", "unlabeled": "구조화 라벨 없음",
    "low_overlap": "low lexical overlap", "high_overlap": "high lexical overlap",
    "unknown": "미상(정답 텍스트 부재)",
    "kr_only": "정답 전량 한국어", "has_foreign": "정답에 외국어 포함",
}


def table_rows(run_new, run_old, qrel, fam, labels, dim: str, k: int = 100) -> list[dict]:
    """하위집단별 (n · qrel 수 · R_old · R_new · Δ · 95%CI). Δ 는 집단 내 페어드 부트스트랩."""
    from .bootstrap import paired_bootstrap

    groups: dict[str, list[str]] = {}
    for qid in (q for q, p in qrel.items() if p):
        groups.setdefault(labels.get(qid, {}).get(dim, "unknown"), []).append(qid)
    rows = []
    for g in sorted(groups, key=lambda x: -len(groups[x])):
        qids = groups[g]
        sub = {q: qrel[q] for q in qids}
        b = paired_bootstrap(run_new, run_old, sub, k=k, family=fam)
        rows.append({"group": g, "n": len(qids), "n_qrel": sum(len(qrel[q]) for q in qids),
                     "r_old": b["mean_b"], "r_new": b["mean_a"], "delta": b["delta"],
                     "lb95": b["lb95"], "ub95": b["ub95"], "p": b["p_two_sided"],
                     "reliable": len(qids) >= MIN_N})
    return rows


def render_table(split: str, dims: dict[str, list[dict]], k: int, new_label: str,
                 old_label: str) -> str:
    lines = [
        f"# §6.4 하위집단 결과표 — {split} 분할",
        "",
        f"> 자동 생성: `python -m sdkb_paper.analysis.subgroup --table --split {split}`. "
        "수기 기입 금지(CLAUDE.md §1-7).",
        f"> 비교: **{new_label}** vs **{old_label}** · family Recall@{k} · "
        f"집단 내 질의단위 페어드 부트스트랩 10k·seed {config.SEED}.",
        f"> **n < {MIN_N} 집단은 확정 결론을 내지 않는다**(표에 ⚠ 표시). Δ = 제안법 − 기준선.",
        "",
    ]
    for dim, rows in dims.items():
        lines += [f"## {DIM_TITLES.get(dim, dim)}", "",
                  f"| 집단 | 질의 수 | qrel 수 | {old_label} R@{k} | {new_label} R@{k} | Δ | 95% CI | p |",
                  "|---|---:|---:|---:|---:|---:|---|---:|"]
        for r in rows:
            name = GROUP_LABELS.get(r["group"], r["group"])
            flag = "" if r["reliable"] else f" ⚠(n<{MIN_N})"
            lines.append(
                f"| {name}{flag} | {r['n']} | {r['n_qrel']} | {r['r_old']:.4f} | "
                f"{r['r_new']:.4f} | {r['delta']:+.4f} | "
                f"[{r['lb95']:+.4f}, {r['ub95']:+.4f}] | {r['p']:.3f} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, default=None, help="새 시스템 run(기본 P1)")
    ap.add_argument("--b", type=Path, default=None, help="기준 run(기본 B3)")
    ap.add_argument("--split", choices=["train", "dev", "test", SPLIT_B, "all"], default="dev")
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--delta", type=float, default=0.05, help="T2 마진 δ(F3)")
    ap.add_argument("--table", action="store_true", help="§6.4 표 생성(paper/tables 기록)")
    ap.add_argument("--unseal", action="store_true", help="B층 봉인 개봉(원장 기록)")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    args = ap.parse_args()
    if args.split == "test":
        print("⚠️  test 개봉 — 사전등록 위반 가능(F9)")

    import pandas as pd

    from ..collect.bq_family_ir import load_family_map
    from .results_table import run_path
    fam = load_family_map()
    if args.split == SPLIT_B:
        # B층은 층화 라벨의 원천이 둘뿐이다(PLAN-047 §12.3) — 공정군·거절근거는 "라벨없음"이고
        # **δ 판정을 내지 않는다.** T2 는 A층 판정 전용이다(PLAN-045 D5).
        qrel = load_qrel_for_split(args.split, unseal=args.unseal, reason=args.reason)
    else:
        qrel = load_qrel()
        if args.split != "all":
            sp = pd.read_parquet(config.IR_SPLIT)
            keep = set(sp.loc[sp["split"] == args.split, "doc_id"])
            qrel = {q: pos for q, pos in qrel.items() if q in keep}
    labels = query_labels(qrel, split=args.split if args.table else None,
                          lex_qrel=qrel if args.split == SPLIT_B else None)
    pa = args.a or run_path("P1", args.split)
    pb = args.b or run_path("B3_rrf", args.split)
    run_a, run_b = load_run(pa), load_run(pb)

    if args.table:
        # B층은 산출 가능한 축이 둘뿐이다(§12.3). 없는 축을 빈 표로 싣지 않는다.
        dim_names = (("lex_overlap", "pos_lang") if args.split == SPLIT_B
                     else ("rejection", "lex_overlap", "pos_lang", "proc_group"))
        dims = {d: table_rows(run_a, run_b, qrel, fam, labels, d, args.k)
                for d in dim_names}
        md = render_table(args.split, dims, args.k, "P1 (제안)", "B3 (텍스트 기준선)")
        print(md)
        config.TABLES.mkdir(parents=True, exist_ok=True)
        out = config.TABLES / f"ir_subgroup_{args.split}.md"
        out.write_text(md, encoding="utf-8")
        print(f"✓ {out}")
        import pandas as pd     # viz 입력 (viz 는 계산하지 않는다 · CLAUDE.md §3)
        pd.DataFrame([{"dim": d, **r} for d, rs in dims.items() for r in rs]).to_csv(
            config.PROCESSED / "ir" / f"ir_subgroup_{args.split}.csv", index=False)
        return

    if args.split == SPLIT_B:
        # T2 δ 판정은 A층 전용이다(PLAN-045 D5 · PLAN-047 §13.4). B층에서 δ 를 적용하면
        # 사전등록이 정한 것과 다른 표본으로 같은 이름의 판정을 내게 된다.
        print(f"[B층 층화 · {args.split} · family R@{args.k} · **δ 판정 없음**] "
              f"new={pa.name} old={pb.name}")
        for dim in ("pos_lang", "lex_overlap"):
            res = compare(run_a, run_b, qrel, fam, labels, dim, args.k)
            print(_fmt(res, float("inf")).replace("(< δ 안전)", "(판정 없음)"))
        return

    print(f"[하위집단 T2 · {args.split} · family R@{args.k} · δ={args.delta}]  new={pa.name} old={pb.name}")
    for dim in ("pos_lang", "proc_group", "rejection"):
        print(_fmt(compare(run_a, run_b, qrel, fam, labels, dim, args.k), args.delta))


if __name__ == "__main__":
    main()
