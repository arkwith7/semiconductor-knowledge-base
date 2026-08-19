"""§6.2f 교차언어 진단 — 정답 언어별 회수·자원 커버리지·후보 풀 편향 (PLAN-019 W1).

동결된 run·qrel·코퍼스만 읽어 **새 검색 없이** 세 진단표를 만든다. 산출은
`paper/tables/ir_crosslingual_{split}.md`(수기 기입 금지 · CLAUDE.md §1-7).

왜 이 표가 필요한가 — 원고 §6.4 는 "정답에 외국어 포함" 질의에서 제안법의 이득이 유의하지 않다고만
보고한다(Δ+0.0140, p=0.518). 그 원인이 (a) 온톨로지의 언어 중립성 부족인지 (b) 질의·문서 번역 부재인지
(c) 자원 자체의 결손인지 구분되지 않는다. 이 모듈은 **질의 단위가 아니라 정답 문서 단위**로 회수를 세어
세 원인을 분리한다.

세 표:
1. **언어별 정답 회수** — 정답 문서를 언어로 나눠 회수율을 잰다. 두 해상도를 함께 보고한다:
   `recall_doc`(그 정답 문서 자체가 top-K 안) · `recall_fam`(그 정답의 **패밀리**가 top-K family 안 —
   같은 발명의 한국어 형제 공개로 회수된 경우를 포함). 주지표 F1 이 family 수준이므로 두 값의 차이가
   "번역 없이 패밀리로 구제된 몫"을 뜻한다.
2. **언어별 자원 커버리지** — 개념링크·IPC·텍스트 보유율. 언어중립 개념층 주장의 사실 확인.
3. **후보 풀 편향** — 언어별 (문서 수, 그중 정답 수, 정답 비율). 외국어 하위풀의 방해문서 희소성은
   교차언어 이득을 과대평가시키므로 **사전에 공개**한다(정직 보고).

- **경계:** analysis 는 순위를 만들지 않는다 — run 파일을 읽어 집계만 한다(PLAN-018 §2).
- **사전등록 지위:** 동결 run·동결 설정의 **기술통계 진단**이며 확증 검정이 아니다. test 분할은 이미
  개봉됐으므로(2026-07-27 확증 1회) 재선택·재최적화는 하지 않는다.

CLI: `python -m sdkb_paper.analysis.lang_recall [--split dev|test|all] [--write]`.
"""
from __future__ import annotations

import argparse

from .. import config
from .metrics import _fold, load_qrel, load_run
from .results_table import SYSTEM_LABELS, run_path

K = 100                       # 주지표와 같은 검토 깊이(F1)
LANG_ORDER = ("ko", "en", "ja", "und")
LANG_LABELS = {"ko": "한국어", "en": "영어", "ja": "일본어", "und": "미상"}



def _candidates(df):
    """후보 문서 집합. `~is_query` 가 아니라 **`is_candidate`** 로 센다(PLAN-045 D5).

    둘은 다르다 — A층 질의 1,000 은 후보 코퍼스에도 문서로 들어 있고, B층 신규 192건은
    질의도 후보도 아니다. `~is_query` 로 세면 후자가 후보로 잘못 잡힌다.
    """
    if "is_candidate" in df.columns:
        return df[df["is_candidate"].astype(bool) & ~df["is_query"].astype(bool)]
    return df[~df["is_query"].astype(bool)]


def doc_lang_map() -> dict[str, str]:
    """doc_id → lang(ko/en/ja). 코퍼스 `lang` 은 스크립트 감지(corpus/text.detect_lang)."""
    import pandas as pd

    df = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "lang"])
    return dict(zip(df["doc_id"].astype(str), df["lang"].astype(str)))


def split_qrel(split: str) -> dict[str, set[str]]:
    import pandas as pd

    qrel = load_qrel()
    if split == "all":
        return qrel
    sp = pd.read_parquet(config.IR_SPLIT)
    keep = set(sp.loc[sp["split"] == split, "doc_id"].astype(str))
    return {q: p for q, p in qrel.items() if q in keep}


def gold_lang_recall(run: dict[str, list[str]], qrel: dict[str, set[str]],
                     doc_lang: dict[str, str], fam: dict[str, str] | None = None,
                     k: int = K) -> dict[str, dict]:
    """정답 문서 단위 회수 — 언어별 {n, hit_doc, hit_fam, recall_doc, recall_fam}.

    질의 단위 매크로 평균이 아니라 **정답 단위 마이크로 집계**다. 질의 평균은 한국어 정답이 다수라
    교차언어 신호를 희석한다(test 정답 ko 340 vs en 128).
    """
    fam = fam or {}
    out: dict[str, dict] = {}
    for qid, pos in qrel.items():
        if not pos:
            continue
        ranked = run.get(qid, [])
        top_docs = set(ranked[:k])
        top_fams = set(_fold(ranked, fam)[:k]) if fam else set()
        for d in pos:
            lg = doc_lang.get(d, "und")
            rec = out.setdefault(lg, {"n": 0, "hit_doc": 0, "hit_fam": 0})
            rec["n"] += 1
            rec["hit_doc"] += int(d in top_docs)
            rec["hit_fam"] += int(fam.get(d, d) in top_fams) if fam else 0
    for rec in out.values():
        rec["recall_doc"] = rec["hit_doc"] / rec["n"] if rec["n"] else 0.0
        rec["recall_fam"] = rec["hit_fam"] / rec["n"] if rec["n"] else 0.0
    return out


def resource_coverage() -> list[dict]:
    """언어별 자원 커버리지 — 후보 문서 전체 / 심사관 정답 노드 각각."""
    import pandas as pd

    df = pd.read_parquet(
        config.IR_CORPUS,
        columns=["doc_id", "lang", "is_query", "is_examiner_positive",
                 "concepts", "ipc", "text_main"],
    )
    df["n_concept"] = df["concepts"].apply(lambda x: 0 if x is None else len(x))
    df["n_ipc"] = df["ipc"].apply(lambda x: 0 if x is None else len(x))
    df["len_text"] = df["text_main"].fillna("").astype(str).str.len()

    rows: list[dict] = []
    for scope, sub in (("후보 문서(질의 제외)", _candidates(df)),
                       ("심사관 정답 노드", df[df["is_examiner_positive"].astype(bool)])):
        for lg, g in sub.groupby("lang"):
            rows.append({
                "scope": scope, "lang": str(lg), "n": int(len(g)),
                "concept_cov": float((g["n_concept"] > 0).mean()),
                "concept_mean": float(g["n_concept"].mean()),
                "ipc_cov": float((g["n_ipc"] > 0).mean()),
                "text_cov": float((g["len_text"] > 50).mean()),
                "text_median": float(g["len_text"].median()),
            })
    return rows


def pool_bias() -> list[dict]:
    """언어별 (후보 문서 수 · 그중 정답 수 · 정답 비율). 외국어 풀의 방해문서 희소성 공개."""
    import pandas as pd

    df = pd.read_parquet(config.IR_CORPUS,
                         columns=["doc_id", "lang", "is_query", "is_examiner_positive"])
    cand = _candidates(df)
    rows = []
    for lg, g in cand.groupby("lang"):
        n_pos = int(g["is_examiner_positive"].astype(bool).sum())
        rows.append({"lang": str(lg), "n_docs": int(len(g)), "n_positive": n_pos,
                     "positive_share": n_pos / len(g) if len(g) else 0.0})
    return rows


def _langs(recalls: dict[str, dict[str, dict]]) -> list[str]:
    seen = {lg for r in recalls.values() for lg in r}
    return [lg for lg in LANG_ORDER if lg in seen] + sorted(seen - set(LANG_ORDER))


def render(split: str, recalls: dict[str, dict[str, dict]], cov: list[dict],
           pool: list[dict], n_q: int, k: int = K) -> str:
    langs = _langs(recalls)
    totals = {lg: next((r[lg]["n"] for r in recalls.values() if lg in r), 0) for lg in langs}
    n_gold = sum(totals.values())
    foreign = sum(v for lg, v in totals.items() if lg != "ko")

    lines = [
        f"# §6.2f 교차언어 진단 — {split} 분할",
        "",
        f"> 자동 생성: `python -m sdkb_paper.analysis.lang_recall --split {split} --write`. "
        "수기 기입 금지(CLAUDE.md §1-7).",
        f"> 동결 run·동결 설정의 **기술통계 진단**(확증 검정 아님) · 새 검색 0건 · "
        f"정답≥1 질의 **{n_q}**개 · 정답 문서 **{n_gold}**건(비한국어 {foreign}건 = "
        f"{foreign / n_gold:.1%}).",
        "",
        f"## 1. 정답 언어별 회수 (검토 깊이 K={k} · 정답 문서 단위 마이크로 집계)",
        "",
        "`recall_doc` = 그 정답 문서 자체가 상위 K 안. `recall_fam` = 그 정답의 **패밀리**가 상위 K "
        "family 안(같은 발명의 한국어 형제 공개로 회수된 몫 포함 · 주지표 F1 과 같은 해상도).",
        "",
        "| 시스템 | " + " | ".join(
            f"{LANG_LABELS.get(lg, lg)} n={totals[lg]}" for lg in langs) + " |",
        "|---" * (len(langs) + 1) + "|",
    ]
    for name, label in SYSTEM_LABELS:
        if name not in recalls:
            continue
        cells = []
        for lg in langs:
            r = recalls[name].get(lg)
            cells.append("—" if not r else
                         f"{r['recall_doc']:.3f} / {r['recall_fam']:.3f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "값은 `recall_doc / recall_fam`.", ""]

    lines += ["## 2. 언어별 자원 커버리지 (개념링크·분류·텍스트)", "",
              "| 범위 | 언어 | 문서 수 | 개념링크 보유율 | 문서당 개념 | IPC 보유율 | 텍스트 보유율 | 텍스트 중앙길이 |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in cov:
        lines.append(
            f"| {r['scope']} | {LANG_LABELS.get(r['lang'], r['lang'])} | {r['n']:,} | "
            f"{r['concept_cov']:.1%} | {r['concept_mean']:.2f} | {r['ipc_cov']:.1%} | "
            f"{r['text_cov']:.1%} | {r['text_median']:,.0f} |")

    lines += ["", "## 3. 후보 풀 편향 (외국어 하위풀의 방해문서 희소성)", "",
              "| 언어 | 후보 문서 수 | 그중 심사관 정답 | 정답 비율 |", "|---|---:|---:|---:|"]
    for r in sorted(pool, key=lambda x: -x["n_docs"]):
        lines.append(f"| {LANG_LABELS.get(r['lang'], r['lang'])} | {r['n_docs']:,} | "
                     f"{r['n_positive']:,} | {r['positive_share']:.1%} |")
    lines += ["", "> 외국어 하위풀은 방해문서가 희소하므로 **번역·교차언어 팔의 이득은 구조적으로 "
              "과대평가**된다. 후속 실험(PLAN-019 W2)은 이 편향을 사전 보고하고 감도분석으로 통제한다.",
              ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", "all"], default="test")
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--write", action="store_true", help="paper/tables/ 에 표 기록")
    args = ap.parse_args()
    if args.split == "test":
        print("⚠️  test 분할 — 봉인 개봉 후 재집계 전용(재선택 금지)")

    from ..collect.bq_family_ir import load_family_map

    fam = load_family_map()
    qrel = split_qrel(args.split)
    qrel = {q: p for q, p in qrel.items() if p}
    doc_lang = doc_lang_map()

    recalls: dict[str, dict[str, dict]] = {}
    for name, _label in SYSTEM_LABELS:
        path = run_path(name, args.split)
        if not path.exists():
            print(f"  (건너뜀 · run 없음) {path.name}")
            continue
        recalls[name] = gold_lang_recall(load_run(path), qrel, doc_lang, fam, k=args.k)

    md = render(args.split, recalls, resource_coverage(), pool_bias(), len(qrel), args.k)
    print(md)
    if args.write:
        import pandas as pd

        config.TABLES.mkdir(parents=True, exist_ok=True)
        out = config.TABLES / f"ir_crosslingual_{args.split}.md"
        out.write_text(md, encoding="utf-8")
        print(f"✓ {out}")
        recs = [{"system": n, "lang": lg, **v} for n, r in recalls.items() for lg, v in r.items()]
        csv_out = config.PROCESSED / "ir" / f"ir_crosslingual_{args.split}.csv"
        pd.DataFrame(recs).to_csv(csv_out, index=False)
        print(f"✓ {csv_out}")


if __name__ == "__main__":
    main()
