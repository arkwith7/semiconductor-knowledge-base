"""F11 어휘 중첩 집단 — low/high overlap 동결 (원고 §5.3 · §6.4 · H3 조건부 절).

원고 §5.3 은 "낮은 어휘 중첩"을 **결과를 본 뒤 정하지 않는다**고 사전등록했다. 그 규율을 코드로
집행한다:

1. 질의 텍스트 = 독립항(`claims_independent` · F8 질의표현)과 그 질의의 **qrel 정답 문헌**
   텍스트(`text_main` = 초록+청구항전체)의 **문자 n-gram Jaccard** 를 잰다.
2. 질의 점수 = 정답들에 대한 **평균**(집계 방식 민감도로 max 도 함께 보고).
3. **dev 분포의 하위 사분위(Q1)를 임계로 동결**하고 그 값을 `overlap_threshold.json` 에 기록한다.
   test 는 이 동결값을 그대로 적용한다 — test 분포로 임계를 다시 잡지 않는다.
4. 민감도: n=3/4 · 집계 mean/max · 형태소(nori) 토큰 Jaccard.

**누출 아님:** 이 점수는 순위 함수에 들어가지 않는다. 질의를 사후 층화하는 **분석용 라벨**이며
(원고 §5.2 하위집단), 시스템은 이 값을 볼 수 없다.

CLI: `python -m sdkb_paper.analysis.overlap [--freeze] [--sensitivity]`.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata

from .. import config

NGRAM_N = 3                 # 동결 기본값 (민감도 n=4 별도 보고)
AGG = "mean"                # 동결 기본 집계 (민감도 max 별도 보고)
THRESHOLD_FILE = config.IR_OVERLAP_THRESHOLD

# 불용어 — 한국어 특허 상투어 + 영어 기능어. 문자 n-gram 이라 최소한만 제거한다(§5.3 "불용어 제거").
STOP_PATTERNS = [
    "특허청구범위", "청구항", "발명의", "상기", "것을 특징으로 하는", "구성되는", "포함하는",
    "및", "또는", "wherein", "comprising", "claim", "according to", "said", "the ", " a ", " an ",
]


def normalize(text: str) -> str:
    """NFKC 정규화 → 소문자 → 불용어 제거 → 한글/영숫자만 남기고 공백 축약."""
    t = unicodedata.normalize("NFKC", str(text or "")).lower()
    for s in STOP_PATTERNS:
        t = t.replace(s.lower(), " ")
    t = re.sub(r"[^0-9a-z가-힣]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def char_ngrams(text: str, n: int = NGRAM_N) -> set[str]:
    t = normalize(text).replace(" ", "")
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()


def morph_tokens(text: str) -> set[str]:
    """형태소(nori · SDKB 사용자사전) 토큰 집합 — 민감도 분석용."""
    return set(_nori()(normalize(text)))


_NORI = None


def _nori():
    """nori 토큰화기 1회 부팅 캐시 (JVM 부팅 비용)."""
    global _NORI
    if _NORI is None:
        from ..retrieval.tokenize import NoriTokenizer
        _NORI = NoriTokenizer(mode="NONE", userdict=config.IR_USERDICT)
    return _NORI


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def compute(split: str | None = None, n: int = NGRAM_N, agg: str = AGG,
            morph: bool = False, qrel: dict[str, set[str]] | None = None) -> dict[str, float]:
    """질의 → 정답들과의 어휘 중첩 점수. split=None 이면 전체.

    `qrel` 을 주면 그것을 쓴다 — B층(`test_b`)은 정답지가 다른 파일이고, 기본 examiner qrel 로는
    이 분할의 질의가 한 건도 잡히지 않는다(D-34). **임계는 여전히 dev 에서 동결한 값을 쓴다** —
    바뀌는 것은 점수를 매길 대상이지 합격선이 아니다.
    """
    import pandas as pd

    from .metrics import load_qrel

    qrel = load_qrel() if qrel is None else dict(qrel)
    if split:
        sp = pd.read_parquet(config.IR_SPLIT)
        keep = set(sp.loc[sp["split"] == split, "doc_id"])
        qrel = {q: p for q, p in qrel.items() if q in keep}
    qids = [q for q, p in qrel.items() if p]
    need = set(qids) | {d for q in qids for d in qrel[q]}

    df = pd.read_parquet(config.IR_CORPUS,
                         columns=["doc_id", "claims_independent", "text_main"])
    df = df[df["doc_id"].astype(str).isin(need)]
    qtext = dict(zip(df["doc_id"].astype(str), df["claims_independent"].astype(str)))
    dtext = dict(zip(df["doc_id"].astype(str), df["text_main"].astype(str)))

    feat = morph_tokens if morph else (lambda t: char_ngrams(t, n))
    cache: dict[str, set] = {}

    def gram(doc_id: str, text: str) -> set:
        if doc_id not in cache:
            cache[doc_id] = feat(text)
        return cache[doc_id]

    out: dict[str, float] = {}
    for qid in qids:
        qg = gram(qid, qtext.get(qid, "") or dtext.get(qid, ""))
        sims = [jaccard(qg, gram(d, dtext.get(d, ""))) for d in sorted(qrel[qid]) if d in dtext]
        if not sims:
            continue                      # 정답 텍스트 부재 → 층화 불가(표에 명기)
        out[qid] = sum(sims) / len(sims) if agg == "mean" else max(sims)
    return out


def freeze_threshold(force: bool = False) -> dict:
    """dev 분포의 Q1 을 low-overlap 임계로 **동결**하고 파일에 기록한다.

    이미 동결돼 있으면 재계산하지 않는다 — 임계가 결과를 본 뒤 움직이지 않게 하는 것이 요점이다
    (CLAUDE.md §1-3). 재동결은 `--force` 로만, 그 사실을 출력한다.
    """
    import numpy as np

    if THRESHOLD_FILE.exists() and not force:
        return json.loads(THRESHOLD_FILE.read_text(encoding="utf-8"))
    dev = compute("dev")
    vals = np.array(sorted(dev.values()))
    rec = {
        "metric": f"char_{NGRAM_N}gram_jaccard", "agg": AGG, "source_split": "dev",
        "n_queries": int(vals.size), "q1_threshold": float(np.percentile(vals, 25)),
        "median": float(np.percentile(vals, 50)), "q3": float(np.percentile(vals, 75)),
        "mean": float(vals.mean()), "min": float(vals.min()), "max": float(vals.max()),
        "note": "low-overlap = 점수 ≤ q1_threshold. dev 에서만 산출하고 test 에 그대로 적용한다.",
    }
    THRESHOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    THRESHOLD_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    return rec


def labels(split: str, qrel: dict[str, set[str]] | None = None) -> dict[str, str]:
    """질의 → 'low_overlap' | 'high_overlap' (동결 임계 적용)."""
    thr = freeze_threshold()["q1_threshold"]
    return {q: ("low_overlap" if v <= thr else "high_overlap")
            for q, v in compute(split, qrel=qrel).items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true", help="dev Q1 임계 동결(최초 1회)")
    ap.add_argument("--force", action="store_true", help="동결 임계 재산출(사유 보고 필수)")
    ap.add_argument("--sensitivity", action="store_true", help="n·집계·토큰화 민감도")
    args = ap.parse_args()

    rec = freeze_threshold(force=args.force)
    print(f"[F11 동결 임계] {rec['metric']} · agg={rec['agg']} · dev {rec['n_queries']}질의")
    print(f"  Q1(low-overlap 임계) = {rec['q1_threshold']:.4f}  "
          f"median {rec['median']:.4f}  Q3 {rec['q3']:.4f}  "
          f"range [{rec['min']:.4f}, {rec['max']:.4f}]")
    print(f"  → {THRESHOLD_FILE}")

    for sp in ("dev", "test"):
        lab = labels(sp)
        n_low = sum(1 for v in lab.values() if v == "low_overlap")
        print(f"  {sp}: low {n_low} · high {len(lab) - n_low} (총 {len(lab)})")

    if args.sensitivity:
        import numpy as np
        print("\n[민감도 — 임계 정의가 집단 구성을 얼마나 바꾸는가]")
        base = labels("test")
        for name, kw in [("n=4", {"n": 4}), ("agg=max", {"agg": "max"}),
                         ("형태소(nori)", {"morph": True})]:
            alt = compute("test", **kw)
            thr = float(np.percentile(list(compute("dev", **kw).values()), 25))
            altlab = {q: ("low_overlap" if v <= thr else "high_overlap") for q, v in alt.items()}
            common = set(base) & set(altlab)
            agree = sum(1 for q in common if base[q] == altlab[q])
            print(f"  {name:<12} dev Q1={thr:.4f} · test 집단 일치율 {agree}/{len(common)} "
                  f"({agree / len(common):.1%})")


if __name__ == "__main__":
    main()
