#!/usr/bin/env python3
"""PLAN-006 T4 — c3 요소 우선순위 가중을 **train 전체** 심사관 인용으로 배워 동결한다(dev 평가용).

train 개발 측정에서는 학습 구간(패밀리 해시 7/10)만 썼다. dev 는 train 바깥이므로 같은 방법·매개변수
(베타 사전 C3_PRIOR)로 train 전체에서 다시 배운다 — 방법은 바꾸지 않는다. dev·test 의 인용은 읽지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_search_query as Q  # noqa: E402
import ir_corpus  # noqa: E402
import report_t4_query as R  # noqa: E402
from splits import load_split  # noqa: E402

OUT = ROOT / "data" / "queries" / "t4_c3_weights_v1.json"


def main() -> int:
    gt = R.load_gt("train", load_split())
    C = ir_corpus.load(["doc_id", "concepts"])
    jw = Q.JudgmentWeights(gt, {d: set(v) for d, v in zip(C["doc_id"], C["concepts"]) if v is not None})
    sha = Q.save_weights(jw, OUT, {"learn": "train 전체 질의의 심사관 인용(qrel_examiner · 코퍼스 안)", "queries": len(gt),
                                   "corpus_sha256": ir_corpus.manifest()["sha256"]})
    print(f"OK {OUT.relative_to(ROOT)} concepts={len(jw.w)} sha256={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
