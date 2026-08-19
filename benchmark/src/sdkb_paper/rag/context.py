"""컨텍스트 조립 — 동결 run 상위 K → 생성 요청 (PLAN-038 §12.2·§12.3).

**두 팔의 입력 차이는 검색 run 하나뿐이다**(§8 성공기준 1). 그것을 주석으로 약속하지 않고
구조로 강제한다 — 요청 payload 는 `build_request(query_claims, docs)` 한 곳에서만 만들어지고,
팔 이름은 이 함수에 **들어가지 않는다.** 팔이 바꾸는 것은 `docs` 리스트 하나다.

누출(§8 성공기준 5)은 `CandidateMask` 로 막는다 — 질의 자신·같은 패밀리·시점 위반 문서는
컨텍스트에 들어가지 않는다. 마스크가 무엇을 몇 건 걷어냈는지는 감사 기록으로 남긴다
(0 이어야 정상이지만, **0 이라고 가정하지 않는다**).

**팔 고정.** `data/processed/ir/runs/` 는 PLAN-035 실행 때 O′ 자원으로 덮여 있다. 이 모듈은
`runsets/O_pre_linker/` 만 읽는다(원고 §6 재현 팔 · effort.py 와 같은 규율).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..analysis.metrics import load_run
from . import frozen

ARM_DIR = config.IR_RUNSETS_DIR / frozen.RUNSET


def arm_dir(runset: str = frozen.RUNSET) -> Path:
    # 기본 팔은 모듈 상수를 그대로 돌려준다 — 테스트가 `ARM_DIR` 을 갈아끼워 쓰기 때문이다.
    return ARM_DIR if runset == frozen.RUNSET else config.IR_RUNSETS_DIR / runset


def run_path(arm: str, split: str = frozen.SPLIT, runset: str = frozen.RUNSET) -> Path:
    return arm_dir(runset) / f"sys_{arm}_{split}.txt"


@dataclass(frozen=True)
class QueryContext:
    """한 질의 × 한 팔의 컨텍스트. 생성에 들어가는 모든 것이 여기 있다."""

    qid: str
    query_claims: str
    doc_ids: tuple[str, ...]        # 순위 순서 · 길이 ≤ K
    doc_texts: tuple[str, ...]
    n_masked: int                   # 누출 마스크가 상위권에서 걷어낸 건수(감사용)

    def docs_block(self) -> str:
        return frozen.DOC_SEPARATOR.join(
            frozen.DOC_TEMPLATE.format(doc_id=d, text=t)
            for d, t in zip(self.doc_ids, self.doc_texts)
        )


# ── 요청 조립 — 팔을 모른다 ─────────────────────────────────────────────────────
def build_user_message(query_claims: str, docs_block: str) -> str:
    return frozen.USER_TEMPLATE.format(QUERY_CLAIMS=query_claims, DOCS=docs_block)


def build_request(query_claims: str, docs_block: str) -> dict:
    """Bedrock `converse` payload. **팔 인자를 받지 않는다** — 그것이 §8-1 의 강제다."""
    return {
        "modelId": frozen.MODEL_ID,
        "system": [{"text": frozen.SYSTEM_PROMPT}],
        "messages": [
            {"role": "user", "content": [{"text": build_user_message(query_claims, docs_block)}]}
        ],
        "inferenceConfig": {
            # top_p·top_k 는 보내지 않는다(§12.1-3c) — 변인을 하나로 둔다.
            "temperature": frozen.TEMPERATURE,
            "maxTokens": frozen.MAX_TOKENS,
        },
    }


# ── 적재 ────────────────────────────────────────────────────────────────────────
def load_texts(layer: str = "A") -> tuple[dict[str, str], dict[str, str]]:
    """(문서 본문 `text_main`, 지정 층 질의의 독립항 `claims_independent`).

    기본은 A층이다(PLAN-045 D5) — C2′ 전달 실험의 확증은 판독 B 사전등록 아래 서고,
    여기서 층을 바꾸는 것은 **계측기 교체가 아니라 다른 실험**이다.
    """
    import pandas as pd

    from ..retrieval import layers as lyr

    df = pd.read_parquet(
        config.IR_CORPUS,
        columns=lyr.with_layer_cols(
            ["doc_id", "is_query", "text_main", "claims_independent"]
        ),
    )
    doc_text = {
        str(d): ("" if t is None else str(t)) for d, t in zip(df["doc_id"], df["text_main"])
    }
    q = lyr.queries_of(df, layer)
    q_text = {
        str(d): ("" if t is None else str(t))
        for d, t in zip(q["doc_id"], q["claims_independent"])
    }
    return doc_text, q_text


def build_arm_contexts(
    arm: str,
    doc_text: dict[str, str],
    q_text: dict[str, str],
    mask,
    qids: list[str],
    k: int = frozen.K,
    split: str = frozen.SPLIT,
    runset: str = frozen.RUNSET,
) -> dict[str, QueryContext]:
    """동결 run → 질의별 상위 K 컨텍스트. 마스크 위반 문서는 제외하고 다음 순위로 채운다."""
    path = run_path(arm, split, runset)
    if not path.exists():
        raise FileNotFoundError(f"동결 팔의 run 이 없다: {path}")
    run = load_run(path)

    out: dict[str, QueryContext] = {}
    for qid in qids:
        ranked = run.get(qid, [])
        kept, masked = [], 0
        for d in ranked:
            if len(kept) >= k:
                break
            if mask.is_allowed(qid, d):
                kept.append(d)
            else:
                masked += 1
        out[qid] = QueryContext(
            qid=qid,
            query_claims=q_text.get(qid, ""),
            doc_ids=tuple(kept),
            doc_texts=tuple(doc_text.get(d, "") for d in kept),
            n_masked=masked,
        )
    return out


def run_sha256(arm: str, split: str = frozen.SPLIT, runset: str = frozen.RUNSET) -> str:
    return hashlib.sha256(run_path(arm, split, runset).read_bytes()).hexdigest()


def test_qids(split: str = frozen.SPLIT, *, unseal: bool = False, reason: str = "") -> list[str]:
    """봉인 qrel 의 정답 ≥1 질의(분모 규율 §0). 문서 단위 — family 와 섞지 않는다(§11.4-②).

    B층(`test_b`)은 **봉인 열람이므로 `unseal=True` 없이는 실패한다**(PLAN-047 §13.3).
    """
    from ..analysis.metrics import load_qrel, load_qrel_for_split

    if split == frozen.SPLIT_B:
        qrel = load_qrel_for_split(split, unseal=unseal, reason=reason or "C2′ 판독 B 채점")
    else:
        qrel = load_qrel(config.IR_QREL_TEST_SEALED)
    return sorted(q for q, pos in qrel.items() if pos)
