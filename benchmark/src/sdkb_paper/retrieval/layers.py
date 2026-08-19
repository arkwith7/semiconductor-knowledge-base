"""층 표지 소비 헬퍼 (PLAN-045 D1·D2).

검색 모듈 셋이 같은 두 가지를 물어본다 — "이 행이 후보인가" · "이 질의가 내 층인가".
같은 답을 세 곳에 복사하면 한 곳만 고쳐지는 사고가 난다(§2′.3 이 그 유형이다).

**구 코퍼스(층 컬럼 이전)와도 호환된다** — 컬럼이 없으면 질의 전량이 A층이던 시절이므로
`is_candidate` 는 전부 참, `query_layer` 필터는 무작동으로 둔다.
"""
from __future__ import annotations

from .. import config

LAYER_A = "A"
LAYER_B = "B"


def corpus_columns() -> set[str]:
    import pyarrow.parquet as pq

    return set(pq.ParquetFile(config.IR_CORPUS).schema.names)


def with_layer_cols(cols: list[str]) -> list[str]:
    """읽을 컬럼 목록에 층 컬럼이 있으면 더한다(중복 제거)."""
    have = corpus_columns()
    extra = [c for c in ("is_candidate", "query_layer") if c in have and c not in cols]
    return list(dict.fromkeys(cols + extra))


def candidates(df):
    """후보 자격 있는 행만. 없는 코퍼스면 전량."""
    return df[df["is_candidate"]] if "is_candidate" in df.columns else df


def queries_of(df, layer: str = LAYER_A):
    """지정한 층의 질의만. 층 컬럼이 없으면 `is_query` 전량(구 코퍼스)."""
    if "query_layer" in df.columns:
        return df[df["query_layer"] == layer]
    return df[df["is_query"]]


# --- 판독 B 배관 (PLAN-047 §13.1·§13.2) --------------------------------------
SPLIT_B = "test_b"


def split_qids(split: str) -> list[str]:
    """분할 표에서 질의 id 를 **사전순**으로 돌려준다. **qrel 을 읽지 않는다.**

    왜 이 함수가 필요한가(PLAN-047 §12.0-1): 기존 `build_runs` 는 평가할 질의를 qrel 에서
    뽑았다. 그대로 B층에 쓰면 **run 을 만들기 위해 봉인을 먼저 열어야 하고**, 그 순간
    "run 을 먼저 만들고 봉인을 연다"는 순서가 원리적으로 불가능해진다.

    판정식은 이 변경에 영향받지 않는다 — 정답 ≥1 질의만 매크로 평균하는 필터는
    `analysis.metrics.evaluate()` 안에 그대로 있다.
    """
    import pandas as pd

    from .. import config

    sp = pd.read_parquet(config.IR_SPLIT, columns=["doc_id", "split"])
    return sorted(sp.loc[sp["split"] == split, "doc_id"].astype(str))


def run_path_for_layer(base, layer: str = LAYER_A):
    """A층은 기존 경로 그대로, B층은 `_B` 접미. **A층 파일은 바이트 불변이어야 한다.**"""
    from pathlib import Path

    base = Path(base)
    if layer == LAYER_A:
        return base
    return base.with_name(f"{base.stem}_{layer}{base.suffix}")


def guard_run_target(path, layer: str, protected) -> None:
    """B층 검색이 A층 상수 경로를 목적지로 받으면 **거부한다**(PLAN-047 §13.2 쓰기 가드).

    "조심하겠다"로 두지 않는 이유는 하나다 — A층 동결 run 을 덮어쓰면 되돌릴 수 없고,
    그것이 원고 §6 의 재현 팔이다(메모리 `disk-resource-is-oprime-manuscript-is-o-arm`).
    """
    from pathlib import Path

    if layer == LAYER_A:
        return
    if Path(path).resolve() == Path(protected).resolve():
        raise ValueError(
            f"[layers] layer={layer} 인데 목적지가 A층 run 경로다: {path} — "
            "A층 동결 run 덮어쓰기 차단(PLAN-047 §13.2)"
        )
