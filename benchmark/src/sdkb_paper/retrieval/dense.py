"""Dense 검색 (PLAN-018 B2 · F12 Titan Embed Text v2 · FAISS flat).

Titan Embed Text v2(`amazon.titan-embed-text-v2:0`)로 문서·질의를 1024차원 정규화 임베딩하고,
**FAISS IndexFlatIP**(정규화 → 내적=코사인)로 정확·결정적 검색한다. flat 은 근사 파라미터가 0이라
ablation 을 오염시키지 않는다(F16·§8). 임베딩은 결정적(temperature 무관)이며 텍스트해시로 캐시해
재실행이 무료·재현 가능하다.

- 문서 텍스트: `text_main`(SPEC-007 주 색인 텍스트) · 질의: `claims_independent`(F8, 불완전 시 text_main).
- **경계(PLAN-018 §2):** 이 모듈은 qrel 을 읽지 않는다 — run(순위)만 만든다. 평가는 analysis/metrics.
- Titan v2 토큰 상한 8192 초과 문서(실측 2건)는 적응 절단 후 임베딩(§ 로그 보고).

CLI: `python -m sdkb_paper.retrieval.dense`(임베딩→FAISS flat→검색→run). Bedrock 자격증명 필요.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config
from . import layers

# .env → os.environ (boto3 가 환경에서 자격증명·리전을 읽는다).
try:
    from dotenv import load_dotenv
    load_dotenv(config.ROOT / ".env")
except ImportError:
    pass

MODEL = os.getenv("BEDROCK_EMBED_MODEL") or os.getenv("AWS_BEDROCK_EMBED_MODEL", "")
DIM = config.IR_DENSE_DIM

RUN_B2 = config.IR_RUNS_DIR / "dense_b2_claim.txt"

_CLIENT = None
_LOCK = threading.Lock()   # sqlite 캐시 접근 직렬화 (네트워크 호출은 락 밖)


def _client():
    global _CLIENT
    if _CLIENT is None:
        import boto3
        _CLIENT = boto3.client(
            "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
        )
    return _CLIENT


def _cache(cache_path=None) -> sqlite3.Connection:
    path = cache_path or config.IR_DENSE_CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB)")
    return c


def _key(text: str) -> str:
    return hashlib.sha256(f"{MODEL}|{DIM}|norm|{text}".encode()).hexdigest()


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _invoke(text: str) -> list[float]:
    """Titan v2 임베딩 1건. 토큰상한 초과 시 절반씩 적응 절단·스로틀/일시서버오류 백오프."""
    import time
    cli = _client()
    body_text = text
    # 일시적(재시도 가능) 서버측 오류 — 백오프 후 재시도. 대량 임베딩서 1건이라도 전체 중단 방지.
    transient = ("Throttl", "ModelError", "ServiceUnavailable", "InternalServer",
                 "InternalFailure", "500", "503")
    transient_msg = ("Try your request again", "unexpected error", "timed out", "timeout")
    for attempt in range(10):
        try:
            r = cli.invoke_model(
                modelId=MODEL,
                body=json.dumps({"inputText": body_text, "dimensions": DIM, "normalize": True}),
            )
            return json.loads(r["body"].read())["embedding"]
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            msg = str(e)
            is_transient = any(t in name or t in msg for t in transient) \
                or any(m in msg for m in transient_msg)
            if is_transient and attempt < 9:
                time.sleep(min(2 ** attempt * 0.5, 30))
                continue
            if "Validation" in name and len(body_text) > 500:
                body_text = body_text[: len(body_text) // 2]   # 토큰상한 → 적응 절단
                continue
            raise
    raise RuntimeError("Titan 임베딩 실패(재시도 소진)")


def embed_texts(texts: list[str], workers: int = 16, cache_path=None) -> list[list[float]]:
    """텍스트 리스트 → 임베딩 리스트(순서 보존). 캐시 히트는 호출 생략. cache_path 로 별도 캐시 지정."""
    if not MODEL:
        raise SystemExit("[dense] BEDROCK_EMBED_MODEL 미설정 — .env 확인")
    cache = _cache(cache_path)
    keys = [_key(t) for t in texts]
    out: list[list[float] | None] = [None] * len(texts)
    todo = []
    with _LOCK:
        rows = {k: v for k, v in cache.execute("SELECT k, v FROM e")}
    for i, k in enumerate(keys):
        if k in rows:
            out[i] = _unpack(rows[k])
        else:
            todo.append(i)

    def work(i: int) -> tuple[int, list[float]]:
        return i, _invoke(texts[i])

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, vec in ex.map(work, todo):
            out[i] = vec
            with _LOCK:
                cache.execute("INSERT OR REPLACE INTO e (k, v) VALUES (?, ?)", (keys[i], _pack(vec)))
                done += 1
                if done % 2000 == 0:
                    cache.commit()
                    print(f"  임베딩 {done}/{len(todo)} …")
    with _LOCK:
        cache.commit()
    return [v for v in out]  # type: ignore[misc]


# --- FAISS flat 색인·검색 -------------------------------------------------
def _matrix(vecs: list[list[float]]):
    import numpy as np
    return np.asarray(vecs, dtype="float32")


def search(
    query_col: str = "claims_independent",
    fallback_col: str = "text_main",
    doc_col: str = "text_main",
    k: int = 1000,
    exclude_self: bool = True,
    run_path: Path | None = None,
    tag: str = "dense_b2",
    workers: int = 16,
    layer: str = layers.LAYER_A,
) -> Path:
    """문서·질의 임베딩 → FAISS flat 검색 → TREC run(qrel 미열람)."""
    import faiss
    import pandas as pd

    run_path = run_path or layers.run_path_for_layer(RUN_B2, layer)
    layers.guard_run_target(run_path, layer, RUN_B2)
    run_path.parent.mkdir(parents=True, exist_ok=True)

    # 컬럼 중복 제거(doc_col==fallback_col 이면 pandas 가 DataFrame 을 돌려줘 반복이 깨진다).
    cols = list(dict.fromkeys(["doc_id", "is_query", doc_col, query_col, fallback_col]))
    df = pd.read_parquet(config.IR_CORPUS, columns=layers.with_layer_cols(cols))
    # 문서 = 후보 자격 있는 행만 (PLAN-045 D2). 질의 = 지정한 층만 (기본 A).
    docs = layers.candidates(df)
    doc_texts = [str(t or "") for t in docs[doc_col]]
    nonempty = [i for i, t in enumerate(doc_texts) if t.strip()]
    doc_ids = docs["doc_id"].tolist()

    print(f"① 문서 임베딩 {len(nonempty):,}건(빈 text 제외 {len(df) - len(nonempty)}) …")
    dvecs = embed_texts([doc_texts[i] for i in nonempty], workers=workers)
    xb = _matrix(dvecs)
    index = faiss.IndexFlatIP(DIM)     # 정규화 임베딩 → 내적 = 코사인 · 정확·결정적
    index.add(xb)
    row_docid = [doc_ids[i] for i in nonempty]

    queries = layers.queries_of(df, layer)
    q_texts, q_ids = [], []
    for row in queries.itertuples(index=False):
        t = getattr(row, query_col) or getattr(row, fallback_col) or ""
        if str(t).strip():
            q_texts.append(str(t))
            q_ids.append(row.doc_id)
    print(f"② 질의 임베딩 {len(q_texts):,}건 · FAISS flat 검색(k={k}) …")
    qvecs = embed_texts(q_texts, workers=workers)
    xq = _matrix(qvecs)
    kk = k + (1 if exclude_self else 0)
    scores, idx = index.search(xq, kk)

    written = 0
    with run_path.open("w", encoding="utf-8") as f:
        for qi, qid in enumerate(q_ids):
            rank = 0
            for j, docrow in enumerate(idx[qi]):
                if docrow < 0:
                    continue
                did = row_docid[docrow]
                if exclude_self and did == qid:
                    continue
                rank += 1
                f.write(f"{qid} Q0 {did} {rank} {scores[qi][j]:.6f} {tag}\n")
                if rank >= k:
                    break
            written += 1
    print(f"  질의 {written}건 · run → {run_path}")
    return run_path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=[layers.LAYER_A, layers.LAYER_B], default=layers.LAYER_A,
                    help="질의 층. B 는 판독 B 전용 · run 은 `_B` 접미")
    args = ap.parse_args()
    # 문서 임베딩은 텍스트 해시 키로 캐시에 있다 — B층 실행의 신규 유료 호출은 **질의 200건**뿐이다.
    print(f"Dense B2 · {MODEL} · dim={DIM} · layer={args.layer}")
    search(k=1000, layer=args.layer)
    print("✓ Dense B2 run 완료 — 평가는 `python -m sdkb_paper.analysis.metrics --run ...`")


if __name__ == "__main__":
    main()
