"""B층 봉인 qrel 을 IR 형식으로 옮긴다 (D-34 · PLAN-047 §15.2).

**왜 필요한가.** 수집기는 봉인을 `application_number` × `examiner_citations`(수집 형식 · 538행)로
남기고(`collect/b_layer/driver.py:394`), 평가기는 `query_id`·`doc_id`·`relevance`(IR 형식)를
읽는다(`analysis/metrics.py`). 식별자 공간도 다르다 — 수집 형식은 KIPRIS 출원번호와 인용
공개번호이고, 코퍼스는 `kr_1020180000414` 꼴 doc_id 다. 개봉하고 나서야 드러났다.

**이 모듈은 규칙을 새로 만들지 않는다.** 새로 고르는 순간 그것은 결과를 본 뒤 분모를 고르는
일이 되기 때문이다(§1-2). 쓰는 것은 이미 있는 둘이다 —

- **식별자 정규화**: PLAN-047 §5 G1 재측정에 쓴 규칙 그대로. `doc_id` 의 관할 접두를 떼고
  영숫자만 남겨 `publication_number`·`application_number` 와 대조한다. 그 규칙으로 B층 정답
  도달성 482/503 이 재현됐다.
- **코퍼스 밖 정답 제외**: `corpus/assemble.py` `_filter_qrel_to_corpus` 와 같은 규율.
  어떤 검색기로도 회수 불가하므로 제외하되 **원엣지·탈락 건수를 함께 보고**한다.

**봉인 파일은 읽기만 한다 — 쓰지 않는다.** 파생 qrel 을 디스크에 남기지도 않는다. 남기면
봉인과 파생본이 어긋날 자리가 생기고, 그 어긋남은 조용하다.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import config

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")


def norm_key(s: object) -> str:
    """식별자 → 대조 키. 영숫자만 남기고 대문자로. (§5 G1 재측정과 동일 규칙)"""
    return _NON_ALNUM.sub("", str(s or "")).upper()


def corpus_key_index() -> dict[str, str]:
    """대조 키 → 코퍼스 doc_id. doc_id·공개번호·출원번호 셋을 모두 키로 둔다."""
    import pandas as pd

    df = pd.read_parquet(
        config.IR_CORPUS, columns=["doc_id", "publication_number", "application_number"]
    )
    index: dict[str, str] = {}
    for d in df["doc_id"].astype(str):
        # doc_id 는 `kr_1020180000414` 꼴 — 관할 접두를 떼고 대조한다.
        index.setdefault(norm_key(d.split("_", 1)[-1]), d)
    for col in ("publication_number", "application_number"):
        for d, v in zip(df["doc_id"].astype(str), df[col]):
            k = norm_key(v)
            if k:
                index.setdefault(k, d)
    return index


def _resolve(key: str, index: dict[str, str]) -> str | None:
    """키 → doc_id. 국가코드가 붙은 형태와 벗은 형태를 둘 다 시도한다."""
    if not key:
        return None
    hit = index.get(key)
    if hit is None and len(key) > 2 and key[:2].isalpha():
        hit = index.get(key[2:])
    return hit


def to_ir_qrel(path: Path | None = None, *, verbose: bool = True):
    """수집 형식 봉인 → IR 형식 DataFrame(`query_id`·`doc_id`·`relevance`).

    반환은 **코퍼스한정** qrel 이다. 탈락분은 보고만 하고 되살리지 않는다 — 코퍼스에 없는
    문헌은 어떤 시스템도 회수할 수 없으므로 분모에 두면 전 시스템을 같은 크기로 깎을 뿐이다.
    """
    import pandas as pd

    raw = pd.read_parquet(path or config.B_QREL_SEALED)
    index = corpus_key_index()

    rows: list[tuple[str, str]] = []
    q_unmatched: set[str] = set()
    d_unmatched = 0
    for app, cit in zip(raw["application_number"], raw["examiner_citations"]):
        qid = _resolve(norm_key(app), index)
        did = _resolve(norm_key(cit), index)
        if qid is None:
            q_unmatched.add(str(app))
            continue
        if did is None:
            d_unmatched += 1
            continue
        rows.append((qid, did))

    out = pd.DataFrame(sorted(set(rows)), columns=["query_id", "doc_id"])
    out["relevance"] = 1
    if verbose:
        print(
            f"      qrel_b: 원엣지 {len(raw):,} → 코퍼스한정 {len(out):,} "
            f"(질의 {out.query_id.nunique()} · 정답노드 {out.doc_id.nunique()} · "
            f"탈락: 질의 미매칭 {len(q_unmatched)} · 정답 코퍼스부재 {d_unmatched})",
            flush=True,
        )
    return out


def load_as_dict(path: Path | None = None, *, verbose: bool = True) -> dict[str, set[str]]:
    """`{qid: {정답 doc_id}}` — `analysis.metrics.load_qrel` 과 같은 반환 형태."""
    df = to_ir_qrel(path, verbose=verbose)
    qrel: dict[str, set[str]] = {}
    for r in df.itertuples(index=False):
        qrel.setdefault(r.query_id, set()).add(r.doc_id)
    return qrel
