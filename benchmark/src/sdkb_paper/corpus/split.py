"""시점 분할 (B8 · F9 사전등록) — 질의를 train/dev/test 로 family-disjoint 하게 나눈다.

**무엇을 나누나.** 질의(거절특허 1,000)만 나눈다. 후보 코퍼스는 나누지 않는다 — 후보는 질의별로
F10 시점컷(공개일<출원일)으로 마스킹한다(`retrieval/candidate`). train/dev 는 가중치 학습(F18)·
민감도(F11)에, **test 는 최종 비교까지 봉인**(F9·CLAUDE 규칙 #3).

**규칙(F9 동결 · config).** filingDate 순 60/20/20, 단 **family 단위** 배정(family-disjoint):
같은 발명의 여러 질의가 분할 경계를 넘지 않는다. family 대표일 = 그 family 질의들의 최소 출원일.
경계일(`F9_BOUNDARY_*`)은 데이터 감사로 확정해 **동결**했다 — 이 코드는 그 상수를 계약으로 쓴다
(재계산이 아니라). family_id 는 `collect/bq_family_ir`(DOCDB, fallback 자기자신).

산출: `IR_SPLIT`(doc_id·split·family_id·filing_date) + `IR_QREL_TEST_SEALED`(test 질의 qrel 분리).

CLI:  python -m sdkb_paper.corpus.split
"""
from __future__ import annotations

import pandas as pd

from .. import config
from ..collect.bq_family_ir import load_family_map


def build_split(
    corpus: pd.DataFrame | None = None, family: dict[str, str] | None = None
) -> pd.DataFrame:
    """질의 → DataFrame[doc_id, split, family_id, filing_date]. family-disjoint·결정적."""
    if corpus is None:
        corpus = pd.read_parquet(
            config.IR_CORPUS, columns=["doc_id", "is_query", "query_layer", "filing_date"]
        )
    if family is None:
        family = load_family_map()

    # **A층만 나눈다**(PLAN-045 D3). B층 200 을 함께 넣으면 누적 분위수가 이동해
    # 동결 경계가 2016-11-21·2021-07-21 → 2018-01-19·2020-11-27 로 표류한다(실측 §2′.4).
    # 원인은 B층 출원일이 2018-01-02 ~ 2018-02-16 한 자리에 뭉쳐 있는 것이다.
    # **아래 체크섬은 그 표류를 잡는 방어선이므로 느슨하게 만들지 않는다** — 대신 입력을 A층으로 좁힌다.
    if "query_layer" in corpus.columns:
        q = corpus[corpus["query_layer"] == "A"].copy()
    else:  # 구 코퍼스(층 컬럼 이전) — 질의가 전량 A층이던 시절
        q = corpus[corpus["is_query"]].copy()
    q["family_id"] = q["doc_id"].map(lambda d: family.get(d, d))
    q["fdate"] = pd.to_datetime(q["filing_date"], errors="coerce")
    if q["fdate"].isna().any():
        raise SystemExit(f"[split] 출원일 결측 {q['fdate'].isna().sum()}건 — 시점분할 불가")

    # family 대표일 = 최소 출원일. family 를 (대표일, family_id) 로 정렬(결정적).
    fam = (
        q.groupby("family_id")
        .agg(fdate_min=("fdate", "min"), nq=("doc_id", "size"))
        .reset_index()
        .sort_values(["fdate_min", "family_id"])
        .reset_index(drop=True)
    )
    # 누적 질의수로 60%/80% 지점에서 절단(F9_SPLIT_FRACTIONS). family 단위 → family-disjoint 보장.
    n = int(fam["nq"].sum())
    fam["cum"] = fam["nq"].cumsum()
    f_train, f_dev, _ = config.F9_SPLIT_FRACTIONS
    i60 = int((fam["cum"] >= f_train * n).idxmax())
    i80 = int((fam["cum"] >= (f_train + f_dev) * n).idxmax())
    fam["split"] = "test"
    fam.loc[: i80, "split"] = "dev"
    fam.loc[: i60, "split"] = "train"

    # 동결 경계일 체크섬: 절단 결과가 config 의 동결값과 어긋나면 즉시 실패(사전등록 표류 방지).
    got_b1 = str(fam.loc[i60 + 1, "fdate_min"].date())
    got_b2 = str(fam.loc[i80 + 1, "fdate_min"].date())
    if (got_b1, got_b2) != (config.F9_BOUNDARY_TRAIN_DEV, config.F9_BOUNDARY_DEV_TEST):
        raise SystemExit(
            f"[split] F9 경계 표류: 절단 결과 ({got_b1}, {got_b2}) ≠ 동결 "
            f"({config.F9_BOUNDARY_TRAIN_DEV}, {config.F9_BOUNDARY_DEV_TEST}). "
            f"코퍼스/family 지도가 바뀌었다 — 사전등록 재검토 없이 진행 금지."
        )

    fam_block = dict(zip(fam["family_id"], fam["split"], strict=True))
    q["split"] = q["family_id"].map(fam_block)
    out = q[["doc_id", "split", "family_id", "filing_date"]].sort_values("doc_id").reset_index(drop=True)
    return out


def build_split_b(
    corpus: pd.DataFrame | None = None, family: dict[str, str] | None = None
) -> pd.DataFrame:
    """B층 질의 200 → split="test_b". **A층 분할과 섞이지 않는 라벨을 쓴다.**

    B층은 제2 확증분할 전량이므로 시점 분할을 하지 않는다(PLAN-031). 여기서 하는 일은
    층을 명시적으로 적어 두는 것뿐이고, **판정·개봉은 이 함수의 일이 아니다** —
    B층 봉인 qrel(`config.B_QREL_SEALED`)은 읽지도 쓰지도 않는다(PLAN-045 §1.5 ⓐ).
    """
    if corpus is None:
        corpus = pd.read_parquet(
            config.IR_CORPUS, columns=["doc_id", "is_query", "query_layer", "filing_date"]
        )
    if family is None:
        family = load_family_map()
    if "query_layer" not in corpus.columns:
        return pd.DataFrame(columns=["doc_id", "split", "family_id", "filing_date"])
    b = corpus[corpus["query_layer"] == "B"].copy()
    if b.empty:
        return pd.DataFrame(columns=["doc_id", "split", "family_id", "filing_date"])
    b["family_id"] = b["doc_id"].map(lambda d: family.get(d, d))
    b["split"] = "test_b"
    return (b[["doc_id", "split", "family_id", "filing_date"]]
            .sort_values("doc_id").reset_index(drop=True))


def seal(split: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """test 질의의 qrel 을 분리 저장(봉인). 반환 = (봉인된 test qrel, 개발용 visible qrel)."""
    qrel = pd.read_parquet(config.QREL_EXAMINER)
    test_qids = set(split.loc[split["split"] == "test", "doc_id"])
    sealed = qrel[qrel["query_id"].isin(test_qids)]
    visible = qrel[~qrel["query_id"].isin(test_qids)]
    sealed.to_parquet(config.IR_QREL_TEST_SEALED, index=False)
    return sealed, visible


def main() -> int:
    split = build_split()
    # A층 봉인은 **A층 분할만** 보고 만든다 — `test_b` 는 `test` 가 아니므로
    # `seal()` 의 test_qids 에 들어가지 않는다(PLAN-045 D3). A층 봉인 서명 불변의 근거.
    sealed, visible = seal(split)
    split_b = build_split_b()
    if not split_b.empty:
        split = pd.concat([split, split_b], ignore_index=True)
    config.IR_SPLIT.parent.mkdir(parents=True, exist_ok=True)
    split.to_parquet(config.IR_SPLIT, index=False)
    counts = split["split"].value_counts()
    n = int(counts.reindex(["train", "dev", "test"]).fillna(0).sum())
    print(f"✓ split {n} 질의 → {config.IR_SPLIT}")
    for s in ("train", "dev", "test"):
        c = int(counts.get(s, 0))
        print(f"  {s:5} {c:4} ({c/n:.1%})")
    if not split_b.empty:
        print(f"  test_b {len(split_b):4} (B층 제2 확증분할 · A층 분모에 넣지 않는다 · 봉인 미개봉)")
    print(f"  family-disjoint: 구성상 보장 · 고유 family {split['family_id'].nunique()}")
    print(f"✓ test qrel 봉인 {len(sealed)} 엣지({sealed['query_id'].nunique()} 질의) "
          f"→ {config.IR_QREL_TEST_SEALED} · 개발용 visible {len(visible)} 엣지")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
