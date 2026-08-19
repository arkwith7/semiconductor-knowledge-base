"""가족 인용 병합 정답지 (PLAN-057 · §5.3 규칙 R1–R9 동결).

**무엇을 하는가.** 질의 특허가 속한 DOCDB 가족의 **타 관할 공보에 달린 심사관 인용**을 가져와
기존 심사관 인용 정답지에 더한다. 목적은 성능 향상이 아니라 **정답 불완전성이 짝지은 비교를
좌우하는지**를 보는 것이다(PLAN-055 전복 문턱 n\\*(LB₉₅)=4 의 후속).

**왜 이 라벨을 쓸 수 있는가.** 전문가 판정이 만족시키는 핵심 조건은 *"사람이 읽었다"* 가 아니라
**우리 시스템과 무관하게 먼저 생성된 관련성 라벨**이다. 타 관할 심사관 인용은 그 조건을 그대로
만족하며 비용이 사람 시간이 아니라 조회다.

**동결 규칙(PLAN-057 §5.3).**
- **R1** `citation.type` 에 **X 또는 Y** 가 포함된 인용만 — `A`·`I` 단독은 기술 배경이므로 제외.
- **R2** DOCDB 가족(`docdb-app`·`docdb-pub`)으로만 질의에 붙인다 — `fallback-self` 제외.
- **R3** 문서 대조는 기존 `normalize_pub` 키를 그대로 쓴다 — 새 정규화 규칙을 만들지 않는다.
- **R4** 필터는 **`CandidateMask`(F10) 를 그대로 호출**한다 — 기존 정답과 동일해야 비교가 성립한다.
- **R5** 기존 qrel 과 중복되는 쌍은 더하지 않고 `relevance` 는 1 — **등급을 만들지 않는다.**
- **R6** 산출은 **신규 파일**이며 `qrel_examiner.parquet` 는 읽기만 한다.
- **R7** 평가 병합은 **test 만** — `test_b` 는 증분 1쌍이라 병합하지 않는다(봉인 파생본 회피).

**경계:** 이 모듈은 run 을 만들지 않고 순위를 바꾸지 않는다. 정답지만 만든다.

CLI: `python -m sdkb_paper.corpus.qrel_family_merge [--fetch] [--build] [--compare]`
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .. import config
from ..collect.bq_family_ir import normalize_pub

#: BigQuery 원본 캐시 — 재조회 없이 재현하기 위해 디스크에 남긴다(raw · 커밋하지 않는다).
CITATIONS = config.RAW_BQ / "family_citations.parquet"
#: 병합 정답지 (신규 파일 · 기존 qrel 은 건드리지 않는다 · R6)
QREL_MERGED = config.IR_DIR / "qrel_family_merged.parquet"

#: R1 — 거절 근거 범주. 문자열에 X 나 Y 가 들어 있으면 채택한다.
XY_RE = re.compile(r"[XY]")
_PUB_RE = re.compile(r"^([A-Z]{2})-([0-9]+)-")

SQL = """
SELECT
  p.family_id            AS family_id,
  p.country_code         AS cc,
  c.publication_number   AS cited_pub,
  c.type                 AS ctype
FROM `patents-public-data.patents.publications` p, UNNEST(p.citation) c
WHERE p.family_id IN UNNEST(@fams)
  AND c.publication_number IS NOT NULL AND c.publication_number != ''
"""


def _query_families() -> list[str]:
    """질의 특허가 속한 DOCDB 가족 (R2 · `fallback-self` 제외)."""
    fm = pd.read_parquet(config.IR_FAMILY_MAP)
    c = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "is_query"])
    qs = set(c.loc[c["is_query"], "doc_id"].astype(str))
    m = fm[fm["doc_id"].astype(str).isin(qs) & fm["method"].isin(["docdb-app", "docdb-pub"])]
    return sorted(m["family_id"].astype(str).unique().tolist())


def fetch(dry_run: bool = True) -> Path | None:
    """BigQuery 에서 가족 인용을 받아 캐시한다. 기본은 dry-run(스캔량 보고)."""
    from google.cloud import bigquery

    config.get_secret("GOOGLE_APPLICATION_CREDENTIALS")
    client = bigquery.Client()
    fams = _query_families()
    params = [bigquery.ArrayQueryParameter("fams", "STRING", fams)]
    if dry_run:
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                      query_parameters=params)
        b = client.query(SQL, job_config=cfg).total_bytes_processed
        print(f"[dry-run] 가족 {len(fams):,} · 스캔 {b/1e9:.1f} GB · "
              f"추정 ${b/1e12*6.25:.2f} (무료 1TB/월)")
        return None
    df = client.query(SQL, job_config=bigquery.QueryJobConfig(query_parameters=params)
                      ).to_dataframe()
    CITATIONS.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CITATIONS, index=False)
    print(f"✓ 인용 {len(df):,}행 → {CITATIONS}")
    return CITATIONS


def _corpus_keys() -> dict[str, str]:
    """후보 코퍼스의 정규화 키 → doc_id (R3). 키를 못 만드는 문서는 대조 대상이 아니다."""
    c = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "is_candidate"])
    out: dict[str, str] = {}
    for d in c.loc[c["is_candidate"], "doc_id"].astype(str):
        n = normalize_pub(d)
        if n:
            for k in n[1]:
                out.setdefault(k, d)
    return out


def _bq_key(pub: object) -> str | None:
    """`US-1234567-A` → `US1234567` (앞 0 제거) — `normalize_pub` 과 같은 규칙."""
    m = _PUB_RE.match(str(pub or ""))
    return f"{m.group(1)}{m.group(2).lstrip('0')}" if m else None


def build(write: bool = True) -> pd.DataFrame:
    """병합 정답지를 만든다. 반환은 **신규 쌍만** (기존 qrel 은 포함하지 않는다)."""
    from ..retrieval.candidate import CandidateMask

    cit = pd.read_parquet(CITATIONS)
    fm = pd.read_parquet(config.IR_FAMILY_MAP)
    c = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "is_query"])
    qrel = pd.read_parquet(config.QREL_EXAMINER)

    xy = cit[cit["ctype"].fillna("").str.contains(XY_RE, na=False)].copy()      # R1
    keys = _corpus_keys()
    xy["cand"] = xy["cited_pub"].map(lambda p: keys.get(_bq_key(p)))            # R3
    xy = xy[xy["cand"].notna()]

    qs = set(c.loc[c["is_query"], "doc_id"].astype(str))
    qf = fm[fm["doc_id"].astype(str).isin(qs) & fm["method"].isin(["docdb-app", "docdb-pub"])]
    fam2q = qf.groupby(qf["family_id"].astype(str))["doc_id"].apply(list).to_dict()   # R2

    pairs = {(q, d) for f_, d in zip(xy["family_id"].astype(str), xy["cand"], strict=True)
             for q in fam2q.get(f_, [])}
    existing = set(zip(qrel["query_id"].astype(str), qrel["doc_id"].astype(str), strict=True))
    fresh = sorted(p for p in pairs if p not in existing)                        # R5
    mask = CandidateMask()
    kept = [(q, d) for q, d in fresh if mask.is_allowed(q, d)]                   # R4

    out = pd.DataFrame(kept, columns=["query_id", "doc_id"])
    out["relevance"] = 1                                                         # R5
    print(f"  도달 쌍 {len(pairs):,} · 기존 중복 {len(pairs)-len(fresh):,} "
          f"({(len(pairs)-len(fresh))/len(pairs):.1%} 독립 교차 확인) · 신규 {len(fresh):,} "
          f"· F10 통과 {len(kept):,}")
    if write:
        out.to_parquet(QREL_MERGED, index=False)                                 # R6
        print(f"✓ {QREL_MERGED}")
    return out


def merged_qrel(split: str) -> dict[str, set[str]]:
    """기존 qrel + 병합분. **`test_b` 는 병합하지 않는다**(R7)."""
    from ..analysis.metrics import load_qrel_for_split

    base = load_qrel_for_split(split)
    if split == "test_b":
        return base
    add = pd.read_parquet(QREL_MERGED)
    out = {q: set(v) for q, v in base.items()}
    for q, d in zip(add["query_id"].astype(str), add["doc_id"].astype(str), strict=True):
        if q in out:
            out[q].add(d)
    return out


def compare(split: str = "test") -> dict:
    """병합 전후의 짝지은 차이를 대조한다 (R8 · 동결 run 위에서 채점만 다시 한다)."""
    from ..analysis.bootstrap import paired_bootstrap
    from ..analysis.metrics import load_qrel_for_split, load_run
    from ..collect.bq_family_ir import load_family_map

    fam = load_family_map()
    runs_dir = Path(config.IR_DIR) / "runsets" / "O_pre_linker"
    sp = pd.read_parquet(config.IR_SPLIT, columns=["doc_id", "split"])
    keep = set(sp.loc[sp["split"] == split, "doc_id"].astype(str))
    out: dict = {"split": split}
    for label, qrel in (("기존", load_qrel_for_split(split)), ("병합", merged_qrel(split))):
        q = {k: v for k, v in qrel.items() if k in keep and v}
        for a, b in (("P1", "B3_rrf"), ("P0star", "B3_rrf")):
            r = paired_bootstrap(load_run(runs_dir / f"sys_{a}_{split}.txt"),
                                 load_run(runs_dir / f"sys_{b}_{split}.txt"),
                                 q, k=100, family=fam)
            out[f"{label}·{a}"] = {k: round(r[k], 4) for k in
                                   ("mean_a", "mean_b", "delta", "lb95", "ub95", "p_two_sided")}
            print(f"  [{label}] {a:7s} − B3  {r['mean_a']:.4f} vs {r['mean_b']:.4f}  "
                  f"Δ {r['delta']:+.4f}  CI [{r['lb95']:+.4f}, {r['ub95']:+.4f}]  "
                  f"p={r['p_two_sided']:.4f}  (정답 보유 질의 {len(q)})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="BigQuery 조회(기본 dry-run)")
    ap.add_argument("--execute", action="store_true", help="--fetch 를 실제로 실행한다")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if args.fetch:
        fetch(dry_run=not args.execute)
    if args.build:
        build()
    if args.compare:
        compare("test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
