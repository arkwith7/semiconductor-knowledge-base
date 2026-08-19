"""후보 마스크 D_q — F10 시점유효·family-disjoint (PLAN-018 §7.3 M4-6 · 원고 §4.4).

선행기술 검색은 **질의 출원 시점에 존재하던 문서**만 후보로 삼아야 한다(미래 누출 방지). 또한 같은
특허 패밀리(자기 확장·분할출원)는 후보에서 제외한다.

`D_q(q) = { d : d≠q ∧ pub_date(d) < filing_date(q) ∧ family(d)≠family(q) }`

- **경계(PLAN-018 §2):** 이 모듈은 qrel 을 읽지 않는다 — 코퍼스 메타(날짜·family)만 본다.
- **pub_date 결측(실측 4,492건) 처리:** 미래임을 **증명할 수 없으므로 시점유효로 포함**한다(포함이
  recall 보수적 하향 — 미래문서를 빼면 top-K 슬롯이 비어 recall 만 올라간다. 정답은 정의상 시점선행).
  이 규칙과 결측수는 프로파일에 보고한다.
- **정답 무해성:** 심사관 인용 정답은 출원 이전 공개·타 family 이므로 마스킹해도 recall 이 보존된다
  (M2/M3 정직 주석과 정합). 마스크의 효과는 **미래·자기 family 문서의 top-K 점유 제거**다.

용도: B4/B5 는 `allowed_array(qid)` 로 채점 대상을 제한하고, B0–B3 run 은 `filter_run` 으로 사후 필터.
"""
from __future__ import annotations

import numpy as np

from .. import config


def _to_int(s: object) -> int:
    """'YYYY-MM-DD' → YYYYMMDD int. 결측/파싱실패 → 0(항상 시점유효로 포함)."""
    if not s or (isinstance(s, float) and np.isnan(s)):
        return 0
    t = str(s).replace("-", "")[:8]
    return int(t) if t.isdigit() and len(t) == 8 else 0


class CandidateMask:
    """코퍼스 메타를 한 번 적재해 질의별 F10 후보 판정을 제공한다(결정적·qrel 미열람)."""

    def __init__(self) -> None:
        import pandas as pd

        from . import layers

        df = pd.read_parquet(
            config.IR_CORPUS,
            columns=layers.with_layer_cols(
                ["doc_id", "is_query", "filing_date", "publication_date"]
            ),
        )
        fam = pd.read_parquet(config.IR_FAMILY_MAP, columns=["doc_id", "family_id"])
        fmap = dict(zip(fam["doc_id"].astype(str), fam["family_id"].astype(str)))

        self.doc_ids: list[str] = df["doc_id"].astype(str).tolist()
        self.row: dict[str, int] = {d: i for i, d in enumerate(self.doc_ids)}
        # 후보 판정용 배열(코퍼스 순서 정렬)
        self.pub_int = np.array([_to_int(x) for x in df["publication_date"]], dtype=np.int64)
        # 후보 자격 배열(PLAN-045 D2). B층 질의가 새로 데려온 문서는 **공개일이 없어**
        # `pub_int = 0 < cutoff` 로 시점 조건을 항상 통과한다 — 시점 필터로는 못 막는다.
        # 그래서 자격 자체를 배열로 들고 `allowed_array` 에서 곱한다.
        self.cand_ok = (
            df["is_candidate"].to_numpy().astype(bool)
            if "is_candidate" in df.columns
            else np.ones(len(df), dtype=bool)
        )
        self.family = np.array([fmap.get(d, d) for d in self.doc_ids], dtype=object)
        self.n_pub_missing = int((self.pub_int == 0).sum())

        # 질의 컷오프(출원일)·family
        qmask = df["is_query"].to_numpy()
        self.q_filing: dict[str, int] = {}
        self.q_family: dict[str, str] = {}
        for d, isq, fdate in zip(self.doc_ids, qmask, df["filing_date"]):
            if isq:
                self.q_filing[d] = _to_int(fdate)
                self.q_family[d] = fmap.get(d, d)

    def allowed_array(self, qid: str) -> np.ndarray:
        """코퍼스 순서 bool 배열: True = D_q(q) 포함 후보. B4/B5 채점 제한용."""
        cutoff = self.q_filing.get(qid, 0)
        qfam = self.q_family.get(qid, qid)
        # cutoff=0(질의 출원일 결측·없음) → 시점조건 미적용(전부 통과)로 두되 자기·family 은 항상 제외.
        time_ok = (self.pub_int < cutoff) if cutoff else np.ones(len(self.doc_ids), dtype=bool)
        fam_ok = self.family != qfam
        self_ok = np.array([d != qid for d in self.doc_ids])
        return time_ok & fam_ok & self_ok & self.cand_ok

    def is_allowed(self, qid: str, doc_id: str) -> bool:
        if doc_id == qid:
            return False
        i = self.row.get(doc_id)
        if i is None:
            return True  # 코퍼스 밖 문서는 판정 불가 → 보수적 포함(정답 보존)
        cutoff = self.q_filing.get(qid, 0)
        if cutoff and self.pub_int[i] >= cutoff:
            return False
        return self.family[i] != self.q_family.get(qid, qid)

    def filter_run(
        self, run: dict[str, list[str]], keep: int | None = None
    ) -> dict[str, list[str]]:
        """run 의 각 순위에서 D_q 위반 문서 제거(순서 보존). keep = 상위 절단."""
        out: dict[str, list[str]] = {}
        for qid, ranked in run.items():
            f = [d for d in ranked if self.is_allowed(qid, d)]
            out[qid] = f[:keep] if keep else f
        return out
