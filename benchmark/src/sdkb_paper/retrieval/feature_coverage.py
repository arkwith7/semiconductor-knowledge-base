"""FeatureCoverage (PLAN-018 §7.5 P-2 · P1 · 원고 §4.7).

질의 **독립항** ClaimFeature 중 후보가 의미상 포괄하는 비율:
`FC(q,d) = |{f∈F_q : max_{g∈F_d} cos(emb(f),emb(g)) ≥ τ}| / |F_q|`
featureText 를 Titan v2 로 임베딩(교차언어 — 정답 en 39%)·정규화 → 내적=코사인. τ 는 dev 격자 동결(P-3).

- **누출 안전(P-7):** 질의 자기 독립항 피처만 분자로 — 정답 파생 아님. qrel 미열람.
- **비용(P-8):** 임베딩은 유료 → 전량 사전 임베딩 후 캐시(`IR_FEATURE_EMB_CACHE`) 재사용.
- **경계:** 순위 재랭크 신호만 — run 은 systems 가 만든다.

CLI: `python -m sdkb_paper.retrieval.feature_coverage --embed`(전량 임베딩·유료).
"""
from __future__ import annotations

import argparse

import numpy as np

from .. import config
from . import dense
from ..corpus.claim_features import load_sidecar


def embed_all_features(workers: int = 16, commit_every: int = 2000) -> dict:
    """sidecar 의 distinct featureText 전량을 Titan 임베딩 → IR_FEATURE_EMB_CACHE 캐시.

    **메모리 바운드(캐시 전용):** 반환 벡터를 누적하지 않는다(과거 버그: out 리스트가 1.02M×1024
    float 를 파이썬 객체로 들고 ~30GB → WSL OOM). 기존 키만 로드(블롭 제외)해 미완료분만 임베딩하고
    벡터는 즉시 sqlite 에 쓰고 버린다. 멱등 — 중단 후 재실행하면 완료분 스킵.
    """
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor

    if not dense.MODEL:
        raise SystemExit("[feature emb] BEDROCK_EMBED_MODEL 미설정 — .env 확인")
    df = load_sidecar()
    texts = df["feature_text"].drop_duplicates().tolist()
    del df

    config.IR_FEATURE_EMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.IR_FEATURE_EMB_CACHE)
    conn.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB)")
    have = {k for (k,) in conn.execute("SELECT k FROM e")}   # 키만(블롭 제외 = 저메모리)

    todo = [(dense._key(t), t) for t in texts if dense._key(t) not in have]
    del texts, have
    print(f"[feature emb] 미완료 {len(todo):,} 임베딩(캐시 {config.IR_FEATURE_EMB_CACHE.name}·메모리바운드) …")

    def work(item):
        k, t = item
        return k, dense._invoke(t)      # 벡터는 즉시 캐시 후 폐기(누적 없음)

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for k, vec in ex.map(work, todo):
            conn.execute("INSERT OR REPLACE INTO e (k, v) VALUES (?, ?)", (k, dense._pack(vec)))
            done += 1
            if done % commit_every == 0:
                conn.commit()
                print(f"  임베딩 {done:,}/{len(todo):,} …", flush=True)
    conn.commit()
    conn.close()
    return {"n_todo": len(todo), "n_done": done}


class FeatureCoverageIndex:
    """sidecar + 캐시 임베딩을 적재해 FeatureCoverage(q,d) 를 제공한다.

    restrict_docs 를 주면 그 문서들의 피처만 적재(메모리 절약 — 전량은 ~4GB). None 이면 전량.
    """

    def __init__(self, restrict_docs: set[str] | None = None) -> None:
        import sqlite3

        df = load_sidecar()
        if restrict_docs is not None:
            df = df[df["doc_id"].isin(restrict_docs)]
        # 캐시(text_key→vec) 일괄 로드
        cache = sqlite3.connect(config.IR_FEATURE_EMB_CACHE)
        rows = {k: v for k, v in cache.execute("SELECT k, v FROM e")}
        cache.close()
        self._n_cached = len(rows)

        # distinct 텍스트 → 벡터 행렬 · 텍스트→행 인덱스
        texts = df["feature_text"].drop_duplicates().tolist()
        vecs, tindex, missing = [], {}, 0
        for t in texts:
            k = dense._key(t)
            blob = rows.get(k)
            if blob is None:
                missing += 1
                continue
            tindex[t] = len(vecs)
            vecs.append(dense._unpack(blob))
        self.n_missing = missing
        self.mat = np.asarray(vecs, dtype="float32") if vecs else np.zeros((0, config.IR_DENSE_DIM), "float32")
        self.tindex = tindex

        # doc_id → 독립항 피처 행 리스트 / 전체 피처 행 리스트
        self.indep_rows: dict[str, list[int]] = {}
        self.all_rows: dict[str, list[int]] = {}
        for doc, indep, txt in zip(df["doc_id"], df["is_independent"], df["feature_text"]):
            r = self.tindex.get(txt)
            if r is None:
                continue
            self.all_rows.setdefault(doc, []).append(r)
            if indep:
                self.indep_rows.setdefault(doc, []).append(r)

    def best_sims(self, qid: str, did: str) -> np.ndarray:
        """질의 독립항 피처별 최대 코사인 배열(후보 피처 대비). τ 무관 — 여러 τ 스레숄딩용."""
        qr = self.indep_rows.get(qid)
        dr = self.all_rows.get(did)
        if not qr or not dr:
            return np.zeros(0, dtype="float32")
        Fq = self.mat[qr]           # [nq, dim] 정규화됨
        Fd = self.mat[dr]           # [nd, dim]
        return (Fq @ Fd.T).max(axis=1)   # 각 질의 피처의 최대 유사도

    def coverage(self, qid: str, did: str, tau: float) -> float:
        """FC(q,d): 질의 독립항 피처 중 후보 피처에 cos≥τ 매칭이 있는 비율."""
        best = self.best_sims(qid, did)
        return float((best >= tau).mean()) if best.size else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true", help="전량 featureText 임베딩(유료)")
    args = ap.parse_args()
    if args.embed:
        s = embed_all_features()
        print(f"✓ feature 임베딩 완료 · 이번 실행 {s['n_done']:,}/{s['n_todo']:,} → {config.IR_FEATURE_EMB_CACHE}")


if __name__ == "__main__":
    main()
