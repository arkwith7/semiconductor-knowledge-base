#!/usr/bin/env python3
"""PLAN-005 §5 V4-1 — 표현 강건성 측정 (읽기 전용).

**질문.** 같은 발명을 청구항이 아닌 문체로 서술해도 같은 선행기술에 도달하는가.
정답지(심사관 인용)는 변하지 않으므로 새 정답 없이 잴 수 있다.

동결된 조작적 정의 (V2 와 같은 눈금 위에 세운다):

  링커  표면형 사전(`mappings/concept_mapping.json` 의 `patent-text` 프로파일)으로
        질의 텍스트에서 개념을 뽑는다. **결정적이며 LLM 이 아니다** — 그래서 의역
        생성 모델과의 자기일관성 경로가 없다.
  E(q)  질의 텍스트에 걸린 개념 집합
  Reach(q) = { d ≠ q : C(d) ∩ E(q) ≠ ∅ }        ← V2 와 동일 (개념 공유, 깊이 1)
  Target(q) = 코퍼스에 실재하는 심사관 인용문헌   ← V2 와 동일 (퇴화형 목표 노드)

  **변형 `claim` 이 이 측정의 기준선이다** — V2 의 기준선(claim_features 유래)과는
  링커가 다르므로 값이 다를 수 있고, **변형 간 비교만 이 리포트의 판정 대상이다.**

  층화: 원문 대비 자카드 유사도로 4분위. 문체가 멀어질수록 회수가 어떻게 변하는가.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import seal, splits  # noqa: E402

OUT = ROOT / "data" / "reports" / "v4_robustness.json"
QUERIES = ROOT / "data" / "queries" / "v4" / "v4_paraphrase_queries.parquet"


def build_linker() -> list[tuple[str, str]]:
    m = json.loads((ROOT / "mappings" / "concept_mapping.json").read_text(encoding="utf-8"))
    prof = m["profiles"]["patent-text"]
    blocked = {b if isinstance(b, str) else b.get("surface") for b in prof.get("blocked", [])}
    ent = [(e["surface"].lower(), e["concept_id"]) for e in prof["entries"]
           if e["surface"].lower() not in blocked]
    # 긴 표면형 우선 — 짧은 것이 긴 것 안에서 잘못 걸리는 것을 줄인다
    return sorted(set(ent), key=lambda x: -len(x[0]))


def link(text: str, entries) -> set[str]:
    t = str(text).lower()
    return {cid for surf, cid in entries if surf in t}


def tok(s: str) -> set[str]:
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", str(s)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--queries", type=Path, default=QUERIES)
    ap.add_argument("--with-conj-disclosure", action="store_true",
                    help="단계 7 — R∀(개념 전부 개시) · Disclosure 목표 키를 **추가**한다(기존 키 불변)")
    ap.add_argument("--split", default="all",
                    help="판정 범위 (CAL-3). 질의 파일은 바꾸지 않고 **읽을 때 거른다** — "
                         "질의 세트 sha 동결은 불변이다. all 이 아니면 산출물 경로가 갈린다")
    a = ap.parse_args()

    # CAL-3 — all 산출물을 분할 실행이 덮어쓰지 못하게 막는다 (τ·공표 수치의 출처를 지킨다)
    if a.split != "all":
        if a.split in splits.SEALED and not seal.ledger_rows():
            raise SystemExit(f"ERROR: 봉인 분할 '{a.split}' — 봉인 원장에 행이 없다(D17)")
        if a.out == OUT:
            a.out = OUT.with_name(f"v4_robustness.{a.split}.json")
        elif a.out.resolve() == OUT.resolve():
            raise SystemExit("ERROR: 분할 실행이 전량 산출물(v4_robustness.json)을 덮어쓸 수 없다 (CAL-3)")

    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from report_priorart_baseline import load_concepts
    doc, _qry, gt = load_concepts()
    inv: dict[str, set] = {}
    for d, cs in doc.items():
        for c in cs:
            inv.setdefault(c, set()).add(d)
    conj = None
    if a.with_conj_disclosure:
        # 단계 7 주 정의 R∀ 를 같은 질의 세트 위에서 함께 잰다. 텍스트 링커가 뽑은 개념 중
        # pa: 경로(바인딩 개념)에 없는 것은 ClaimProfile 이 그러듯 거른다 — 정의는 remeasure 스크립트.
        from report_stage7_remeasure import layers_current, conj_reach
        conj, _ = layers_current(expand=True)

    entries = build_linker()
    df = pd.read_parquet(a.queries)
    queries_sha = splits.sha256_of(a.queries)
    if a.split != "all":                                   # 질의 파일은 그대로 두고 읽을 때 거른다
        keep = splits.queries_in(a.split)
        df = df[df.publication_id.isin(keep)].reset_index(drop=True)
    base = df[df.variant == "claim"].set_index("publication_id").text.to_dict()

    per_variant, per_query = {}, []
    for variant, sub in df.groupby("variant"):
        sizes, hits, ecount, jac = [], [], [], []
        csizes, chits, czero = [], [], 0
        for pid, text in zip(sub.publication_id, sub.text):
            T = gt.get(pid, set()) & doc.keys()
            if not T:
                continue
            E = link(text, entries)
            R = set()
            for c in E:
                R |= inv.get(c, set())
            R.discard(pid)
            sizes.append(len(R)); hits.append(bool(T & R)); ecount.append(len(E))
            j = (len(tok(base[pid]) & tok(text)) / len(tok(base[pid]) | tok(text))
                 if pid in base else None)
            jac.append(j)
            rec = {"publication_id": pid, "variant": variant, "n_concepts": len(E),
                   "reach": len(R), "hit": bool(T & R), "jaccard": j}
            if conj is not None:
                Tc = (gt.get(pid, set()) & conj.disc.keys()) - {pid}
                Eb = frozenset(E) & conj.bound
                Rc = conj_reach(conj, Eb, pid)
                czero += int(not Eb)
                csizes.append(len(Rc)); chits.append(bool(Tc and (Tc & Rc)))
                rec.update({"hit_conj": bool(Tc and (Tc & Rc)), "reach_conj": len(Rc),
                            "n_bound_concepts": len(Eb), "has_disclosure_target": bool(Tc)})
            per_query.append(rec)
        if not sizes:
            continue
        n = len(sizes)
        if conj is not None:
            per_variant.setdefault(variant, {})["conj_disclosure"] = {
                "queries": n, "queries_with_disclosure_target": sum(
                    1 for r in per_query if r["variant"] == variant and r["has_disclosure_target"]),
                "zero_bound_concept_queries": czero,
                "reach_median": st.median(csizes),
                "hit_rate": round(sum(chits) / n, 4),
                **{f"SemanticPathRecall@{S}": round(
                    sum(1 for h, r in zip(chits, csizes) if h and r <= S) / n, 4) for S in (50, 100, 1000)},
            }
        per_variant.setdefault(variant, {})
        per_variant[variant] = {**per_variant[variant], **{
            "queries": n,
            "concepts_per_query_median": st.median(ecount),
            "zero_concept_queries": sum(1 for e in ecount if e == 0),
            "reach_median": st.median(sizes),
            "hit_rate": round(sum(hits) / n, 4),
            "SemanticPathRecall@100": round(
                sum(1 for h, r in zip(hits, sizes) if h and r <= 100) / n, 4),
            "SemanticPathRecall@1000": round(
                sum(1 for h, r in zip(hits, sizes) if h and r <= 1000) / n, 4),
            "jaccard_to_claim_median": (round(st.median([j for j in jac if j is not None]), 4)
                                        if any(j is not None for j in jac) else None),
        }}

    pq = pd.DataFrame(per_query)
    strat = {}
    llm = pq[pq.variant.isin(["L1", "L2", "L3"]) & pq.jaccard.notna()]
    if len(llm):
        llm = llm.assign(q=pd.qcut(llm.jaccard, 4, labels=["Q1_먼", "Q2", "Q3", "Q4_가까운"],
                                   duplicates="drop"))
        strat = {str(k): {"n": int(len(g)), "jaccard_median": round(float(g.jaccard.median()), 4),
                          "hit_rate": round(float(g.hit.mean()), 4),
                          "concepts_median": float(g.n_concepts.median()),
                          "reach_median": float(g.reach.median()),
                          **({"hit_rate_conj": round(float(g.hit_conj.mean()), 4),
                              "reach_conj_median": float(g.reach_conj.median())} if conj is not None else {})}
                 for k, g in llm.groupby("q", observed=True)}

    rep = {"generated": str(date.today()), "plan": "PLAN-005 §5 V4-1 (표현 강건성)",
           "read_only": True,
           # ── CAL-3 선언 (check_leakage K-4·K-5) ─────────────────────────
           "instrument_version": "R0-CAL-3",
           "split": a.split,
           "split_sha256": splits.sha256_of(splits.SPLIT_CSV),
           "seal_ledger_rows": len(seal.ledger_rows()),
           "queries_file": str(Path(a.queries).relative_to(ROOT)),
           "queries_sha256": queries_sha,
           "queries_after_split_filter": int(df.publication_id.nunique()),
           "linker": "표면형 사전 patent-text (결정적, LLM 아님)",
           "surface_forms": len(entries),
           "note": ("변형 claim 이 이 리포트의 기준선이다. V2 기준선과는 링커가 달라 값이 다를 수 "
                    "있으므로, 판정 대상은 **변형 간 비교**다."),
           "conj_disclosure": ("단계 7 — 각 변형의 `conj_disclosure` 는 R∀(바인딩 개념 전부 개시) · "
                               "Disclosure 목표 · coveredBy 확장 on(L_C) 이다. 정의는 report_stage7_remeasure.py"
                               if conj is not None else None),
           "by_variant": per_variant, "llm_jaccard_quartiles": strat}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"표면형 {len(entries)}종 · 질의 변형 {len(per_variant)}종\n")
    hdr = f"{'변형':10}{'질의':>6}{'개념중앙':>9}{'개념0':>7}{'도달중앙':>10}{'회수율':>8}{'@100':>8}{'자카드':>8}"
    print(hdr); print("-" * len(hdr))
    for v in ("claim", "L1", "abstract", "L2", "L3"):
        if v in per_variant:
            s = per_variant[v]
            print(f"{v:10}{s['queries']:6}{s['concepts_per_query_median']:9}"
                  f"{s['zero_concept_queries']:7}{s['reach_median']:10}"
                  f"{s['hit_rate']:8}{s['SemanticPathRecall@100']:8}"
                  f"{s['jaccard_to_claim_median'] or 1.0:8}")
    if strat:
        print("\nLLM 의역 자카드 4분위:")
        for k, s in strat.items():
            print(f"  {k:10} n={s['n']:5} 자카드={s['jaccard_median']:.3f} "
                  f"회수율={s['hit_rate']:.4f} 개념중앙={s['concepts_median']}")
    print(f"\n→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
