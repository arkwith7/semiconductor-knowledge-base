"""claim-feature sidecar 추출 (PLAN-018 §7.5 P-1 · P1/P2 입력).

`central_axis.oxstore`(SDKB claim-feature ABox·이미 빌드·sha 스탬프)에서 IR 코퍼스 특허의 청구항 피처를
뽑아 sidecar parquet 으로 굳힌다. 구조: `Patent —hasClaim→ Claim{isIndependent} —hasFeature→
ClaimFeature{featureText, featureSeq}`.

- **featureText = KIPRIS 원문 → 비커밋**(CLAUDE §1.5). sidecar 는 gitignore·재생성 가능. 집계·서명만 보고.
- **경계(CLAUDE §0.1):** 런타임은 `~/Dev/sdkb` 를 읽지 않는다 — 처리 산출물 oxstore 만. oxstore 는
  사람이 `make` 로 빌드(provenance sha 스탬프).
- **누출 안전(§7.5 P-7):** 피처는 특허 자기 청구항의 분해물 — 정답 파생 아님(FeatureCoverage 는 질의
  자기 독립항 피처만 사용).

CLI: `python -m sdkb_paper.corpus.claim_features [--extract] [--measure]`.
"""
from __future__ import annotations

import argparse

from .. import config

ONT = "https://w3id.org/sdkb/ont/"


def _local(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def extract_sidecar() -> dict:
    """oxstore → IR 코퍼스 특허의 (doc_id·is_independent·feature_seq·feature_text) parquet."""
    import pandas as pd

    from ..ontology.central_axis import open_store

    corpus = pd.read_parquet(config.IR_CORPUS, columns=["doc_id"])
    doc_ids = set(corpus["doc_id"].astype(str))

    store = open_store()
    q = f"""SELECT ?pat ?indep ?ftext ?seq WHERE {{
      ?pat <{ONT}hasClaim> ?c .
      ?c <{ONT}isIndependent> ?indep ; <{ONT}hasFeature> ?f .
      ?f <{ONT}featureText> ?ftext .
      OPTIONAL {{ ?f <{ONT}featureSeq> ?seq }}
    }}"""
    rows = []
    for r in store.query(q):
        doc = _local(r["pat"].value)
        if doc not in doc_ids:
            continue
        indep = str(r["indep"].value).lower() in ("true", "1")
        seq = int(r["seq"].value) if r["seq"] is not None else -1
        rows.append((doc, indep, seq, r["ftext"].value))
    df = pd.DataFrame(rows, columns=["doc_id", "is_independent", "feature_seq", "feature_text"])
    df = df.drop_duplicates(["doc_id", "is_independent", "feature_seq", "feature_text"])
    config.IR_FEATURE_SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.IR_FEATURE_SIDECAR, index=False)
    return {
        "rows": len(df),
        "docs_with_features": df["doc_id"].nunique(),
        "indep_features": int(df["is_independent"].sum()),
        "distinct_text": df["feature_text"].nunique(),
        "out": str(config.IR_FEATURE_SIDECAR),
    }


def load_sidecar():
    import pandas as pd

    if not config.IR_FEATURE_SIDECAR.exists():
        raise SystemExit("[claim_features] sidecar 없음 — `--extract` 먼저")
    return pd.read_parquet(config.IR_FEATURE_SIDECAR)


def query_indep_features() -> dict[str, list[str]]:
    """질의 doc_id → 독립항 featureText 리스트(FeatureCoverage 분자 대상)."""
    df = load_sidecar()
    ind = df[df["is_independent"]]
    return {d: g["feature_text"].tolist() for d, g in ind.groupby("doc_id")}


def doc_all_features() -> dict[str, list[str]]:
    """doc_id → 전체 featureText 리스트(후보 포괄 판정 대상)."""
    df = load_sidecar()
    return {d: g["feature_text"].tolist() for d, g in df.groupby("doc_id")}


def measure_embedding_volume(split: str = "dev", pool_k: int = 1000) -> dict:
    """유료 임베딩 전 물량 실측(§7.5 P-8): 질의 독립항 피처 + dev 풀 후보 전체 피처의 distinct 텍스트."""
    import pandas as pd

    from ..analysis.metrics import load_run
    from ..retrieval.candidate import CandidateMask
    from ..retrieval.hybrid import RUN_B3

    df = load_sidecar()
    sp = pd.read_parquet(config.IR_SPLIT)
    split_docs = set(sp.loc[sp["split"] == split, "doc_id"]) if split != "all" else None

    # 질의 독립항 피처 텍스트
    qmask = df["is_independent"] & (df["doc_id"].isin(split_docs) if split_docs else True)
    q_texts = set(df.loc[qmask, "feature_text"])

    # dev B3 풀 후보들의 전체 피처 텍스트
    b3 = load_run(RUN_B3)
    mask = CandidateMask()
    pool_docs: set[str] = set()
    qids = split_docs if split_docs else set(b3)
    for qid in qids:
        if qid not in b3:
            continue
        pool = [d for d in b3[qid] if mask.is_allowed(qid, d)][:pool_k]
        pool_docs.update(pool)
    cand_texts = set(df.loc[df["doc_id"].isin(pool_docs), "feature_text"])

    union = q_texts | cand_texts
    return {
        "split": split, "n_query_indep_texts": len(q_texts),
        "n_pool_docs": len(pool_docs), "n_cand_feature_texts": len(cand_texts),
        "n_distinct_total": len(union),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--split", default="dev")
    args = ap.parse_args()
    if args.extract:
        s = extract_sidecar()
        print("✓ feature sidecar →", s["out"])
        print(f"  피처행 {s['rows']:,} · 특허 {s['docs_with_features']:,} · 독립항피처 {s['indep_features']:,}"
              f" · distinct 텍스트 {s['distinct_text']:,}")
    if args.measure:
        m = measure_embedding_volume(args.split)
        print(f"[임베딩 물량 · {m['split']}]")
        print(f"  질의 독립항 피처 텍스트 {m['n_query_indep_texts']:,}")
        print(f"  풀 후보 {m['n_pool_docs']:,}개 → 후보 피처 텍스트 {m['n_cand_feature_texts']:,}")
        print(f"  ▶ distinct 총 임베딩 대상 = {m['n_distinct_total']:,}")


if __name__ == "__main__":
    main()
