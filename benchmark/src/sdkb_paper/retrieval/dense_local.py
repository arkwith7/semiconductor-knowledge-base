"""다국어 밀집 검색 — 로컬 인코더 (PLAN-054 B6·B8 · 사전등록 §3.1·§6).

`dense.py`(B2 · Titan v2)의 **배선을 그대로 두고 인코딩 호출부만 교체**한다. 문서 텍스트·질의
텍스트·색인(FAISS IndexFlatIP)·정규화·동점 처리는 B2 와 동일하며, **바뀌는 것은 인코더 하나**다.
그래야 관측된 차이를 인코더에 귀속시킬 수 있다.

**절단은 어댑터가 한다(사전등록 D2).** 컨텍스트를 넘는 입력에 대해 `bge-m3` 는 값을 돌려주고
`snowflake-arctic-embed2` 는 400 으로 실패한다 — 서버에 맡기면 구성 간 차이가 인코더가 아니라
서버 동작에 귀속된다. 따라서 HF 토크나이저로 `ctx` 토큰에서 **결정적으로 선절단**하고 매 호출에
`num_ctx` 를 명시한다. 명시하지 않으면 두 모델 모두 4096 으로 적재된다(OBS3·OBS5.2).

**모델 버전은 다이제스트로 고정한다(CLAUDE.md §1-11 · 사전등록 §6.1).** `latest` 는 움직이는
태그이므로 실행 시점의 매니페스트 다이제스트를 원장 값과 대조하고, 다르면 **실행하지 않는다** —
다이제스트가 바뀐 모델은 재측정 대상이 아니라 새 실험이다.

**직렬 실행이다.** 워커는 1이고 두 모델을 동시에 상주시키지 않는다(사전등록 §3.3). 이 장비에서
병렬 적재로 VRAM 이 넘쳐 정지한 이력이 근거다. 캐시 키에 다이제스트를 넣어 두 모델의 벡터가
같은 키를 공유하지 않게 한다.

- **경계:** 이 모듈은 qrel 을 읽지 않는다 — run(순위)만 만든다.

CLI: `python -m sdkb_paper.retrieval.dense_local --model bge-m3 [--layer A]`
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config
from . import layers

OLLAMA_URL = "http://localhost:11434"
DIM = config.IR_DENSE_DIM          # 1024 — B2 와 동일
CACHE = config.IR_DIR / "dense_local_cache.sqlite"
LOG_DIR = config.ROOT / "data" / "logs"    # /tmp 에 두면 재부팅이 지운다(2026-08-17 사고)

#: 요청 간 최소 간격(초). 2026-08-17 에 지속 8.3 req/s 로 6분 돌린 뒤 호스트 GPU 가
#: `UCodeReset TDR` 로 넘어갔고 장비가 정지했다. 서비스 시간이 약 0.09 s 이므로 0.22 s 간격은
#: 약 4.5 req/s 로 부하를 절반 아래로 낮춘다. **순위에는 영향이 없다** — 같은 입력, 같은 벡터다.
MIN_INTERVAL_S = float(os.getenv("DENSE_LOCAL_MIN_INTERVAL", "0.22"))
REQUEST_TIMEOUT_S = 120
COMMIT_EVERY = 100                 # 재개 지점을 여미기 위해 500 → 100 (2026-08-17)


@dataclass(frozen=True)
class LocalEncoder:
    """로컬 인코더의 동결 명세. 값은 PLAN-054 §6.1 원장에서 옮겨 적지 않고 여기서 대조한다."""
    key: str
    tag: str
    digest: str          # 매니페스트 sha256 (실행 시 재확인 · E7)
    hf_tokenizer: str    # 선절단용 — 서버측 절단에 의존하지 않는다
    ctx: int             # 매 호출에 명시하는 num_ctx
    system: str          # 구성 이름 (B6 · B8)


ENCODERS = {
    "bge-m3": LocalEncoder(
        key="bge-m3", tag="bge-m3:latest",
        digest="7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab",
        hf_tokenizer="BAAI/bge-m3", ctx=8192, system="B6",
    ),
    "arctic": LocalEncoder(
        key="arctic", tag="snowflake-arctic-embed2:latest",
        digest="5de93a84837d0ff00da872e90830df5d973f616cbf1e5c198731ab19dd7b776b",
        hf_tokenizer="Snowflake/snowflake-arctic-embed-l-v2.0", ctx=8192, system="B8",
    ),
}

#: run 파일명 — 기존 run 과 겹치지 않는 새 이름만 쓴다(적격심사 E3).
RUN_PATHS = {"bge-m3": config.IR_RUNS_DIR / "dense_b6_claim.txt",
             "arctic": config.IR_RUNS_DIR / "dense_b8_claim.txt"}

_TOKENIZERS: dict[str, object] = {}


# --- 모델 버전·토크나이저 -----------------------------------------------------

def verify_digest(enc: LocalEncoder, *, url: str = OLLAMA_URL) -> str:
    """실행 시점 다이제스트가 원장과 같은지 확인한다. 다르면 **실행하지 않는다**(E7)."""
    import requests

    r = requests.get(f"{url}/api/tags", timeout=10)
    r.raise_for_status()
    found = {m["model"]: m.get("digest", "") for m in r.json().get("models", [])}
    got = found.get(enc.tag)
    if got is None:
        raise SystemExit(f"[dense_local] 모델 미적재: {enc.tag} — `ollama pull {enc.tag}`")
    if got != enc.digest:
        raise SystemExit(
            f"[dense_local] 다이제스트 불일치 — 태그가 움직였다(E7).\n"
            f"  원장 {enc.digest}\n  실행 {got}\n"
            f"  이것은 재측정이 아니라 새 실험이므로 실행하지 않는다."
        )
    return got


def _tokenizer(enc: LocalEncoder):
    if enc.key not in _TOKENIZERS:
        from transformers import AutoTokenizer
        _TOKENIZERS[enc.key] = AutoTokenizer.from_pretrained(enc.hf_tokenizer)
    return _TOKENIZERS[enc.key]


def truncate(text: str, enc: LocalEncoder) -> tuple[str, bool]:
    """`ctx` 토큰에서 결정적으로 선절단. 반환 (텍스트, 절단여부).

    특수 토큰 자리 둘을 남긴다 — 서버가 붙이는 `<s>`·`</s>` 가 상한을 다시 넘기지 않게 한다.
    """
    tok = _tokenizer(enc)
    ids = tok.encode(text, add_special_tokens=False)
    if len(ids) <= enc.ctx - 2:
        return text, False
    return tok.decode(ids[: enc.ctx - 2], skip_special_tokens=True), True


# --- 캐시 ---------------------------------------------------------------------

def _cache(path: Path | None = None) -> sqlite3.Connection:
    p = path or CACHE
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB)")
    return c


def _key(text: str, enc: LocalEncoder) -> str:
    """캐시 키에 **다이제스트**를 넣는다 — 넣지 않으면 두 모델의 벡터가 조용히 섞인다."""
    return hashlib.sha256(
        f"{enc.tag}|{enc.digest}|{DIM}|norm|ctx{enc.ctx}|{text}".encode()).hexdigest()


def _pack(v: list[float]) -> bytes:
    return struct.pack(f"<{len(v)}f", *v)


def _unpack(b: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(b) // 4}f", b))


# --- 인코딩 -------------------------------------------------------------------

class EncoderDown(SystemExit):
    """인코더가 응답하지 못하는 상태. **재시도하지 않는다** — 근거는 아래.

    2026-08-17 사고에서 호스트 GPU 가 `UCodeReset TDR` 로 넘어간 뒤, 재시도가 죽은 GPU 에
    5분 간격으로 요청을 계속 던져 ollama 가 runner 를 세 개 더 띄웠다. 그 뒤 장비가 정지했다.
    **GPU 소실은 일시 오류가 아니므로 즉시 멈추고 사람에게 알린다.**
    """


_LAST_CALL = 0.0


def _embed_one(text: str, enc: LocalEncoder, *, url: str = OLLAMA_URL) -> list[float]:
    """1건 임베딩. `num_ctx` 를 매 호출에 명시하고, 정규화는 서버 출력이 이미 L2=1 이다(OBS6).

    **속도 제한과 즉시 중단이 이 함수의 두 규칙이다**(2026-08-17). 지연은 순위를 바꾸지 않는다.
    """
    global _LAST_CALL
    import requests

    wait = MIN_INTERVAL_S - (time.monotonic() - _LAST_CALL)
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL = time.monotonic()
    try:
        r = requests.post(
            f"{url}/api/embed",
            json={"model": enc.tag, "input": text,
                  "options": {"num_ctx": enc.ctx}, "keep_alive": "10m"},
            timeout=REQUEST_TIMEOUT_S,
        )
    except Exception as e:                       # noqa: BLE001 — 통신 실패는 GPU 소실을 뜻할 수 있다
        raise EncoderDown(
            f"[dense_local] {enc.system} 요청 실패({type(e).__name__}) — 재시도하지 않는다.\n"
            f"  확인 순서: `nvidia-smi` · `journalctl -u ollama -n 30` ·\n"
            f"  `dmesg | grep dxg`(WSL 에서 GPU 채널이 끊기면 wait_for_completion 실패가 찍힌다).\n"
            f"  진행분은 캐시에 남아 있으므로 원인 해소 후 같은 명령으로 재개하면 이어 붙는다."
        ) from e
    if r.status_code == 400:
        # 선절단을 했는데도 400 이면 상한 가정이 틀린 것이다 — 조용히 자르지 않는다.
        raise EncoderDown(f"[dense_local] 400 — 선절단 가정 불성립: {r.text[:200]}")
    if r.status_code >= 500:
        raise EncoderDown(f"[dense_local] {r.status_code} — 서버측 실패, 즉시 중단: {r.text[:200]}")
    r.raise_for_status()
    return r.json()["embeddings"][0]


def embed_texts(texts: list[str], enc: LocalEncoder, *, cache_path: Path | None = None,
                label: str = "") -> tuple[list[list[float]], int]:
    """텍스트 → 임베딩(순서 보존). **직렬**이며 반환값에 절단 건수를 함께 준다."""
    cache = _cache(cache_path)
    prepared, n_trunc = [], 0
    for t in texts:
        s, cut = truncate(t, enc)
        prepared.append(s)
        n_trunc += int(cut)
    keys = [_key(t, enc) for t in prepared]
    have = {k for (k,) in cache.execute("SELECT k FROM e")}
    todo = [i for i, k in enumerate(keys) if k not in have]
    print(f"  [{enc.system}] {label} {len(texts):,}건 · 신규 {len(todo):,}"
          f" · 캐시 재사용 {len(texts) - len(todo):,} · 절단 {n_trunc:,}"
          f" · 간격 {MIN_INTERVAL_S}s", flush=True)
    t0 = time.monotonic()
    n = 0
    try:
        for n, i in enumerate(todo, 1):
            vec = _embed_one(prepared[i], enc)
            cache.execute("INSERT OR REPLACE INTO e (k, v) VALUES (?, ?)",
                          (keys[i], _pack(vec)))
            if n % COMMIT_EVERY == 0:
                cache.commit()
                el = time.monotonic() - t0
                rate = n / el if el else 0.0
                eta = (len(todo) - n) / rate / 60 if rate else 0.0
                print(f"    {n:,}/{len(todo):,} · {rate:.1f} req/s · 남은 {eta:.0f}분", flush=True)
    finally:
        # 중단이든 완주든 여기까지의 벡터는 남긴다 — 재개가 이어 붙는 근거다.
        cache.commit()
        if n and n < len(todo):
            print(f"  ⚠ 중단 — {n:,}/{len(todo):,} 까지 캐시에 커밋했다", flush=True)
    rows = dict(cache.execute("SELECT k, v FROM e"))
    return [_unpack(rows[k]) for k in keys], n_trunc


# --- 검색 ---------------------------------------------------------------------

def search(model: str, *, k: int = 1000, layer: str = layers.LAYER_A,
           run_path: Path | None = None, exclude_self: bool = True) -> Path:
    """문서·질의 임베딩 → FAISS flat 검색 → TREC run. B2 와 같은 배선이다."""
    import faiss
    import numpy as np
    import pandas as pd

    enc = ENCODERS[model]
    verify_digest(enc)                                   # E7 — 먼저 막는다
    base = run_path or RUN_PATHS[model]
    out_path = layers.run_path_for_layer(base, layer)
    layers.guard_run_target(out_path, layer, base)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cols = list(dict.fromkeys(["doc_id", "is_query", "text_main", "claims_independent"]))
    df = pd.read_parquet(config.IR_CORPUS, columns=layers.with_layer_cols(cols))
    docs = layers.candidates(df)
    doc_texts = [str(t or "") for t in docs["text_main"]]
    doc_ids = docs["doc_id"].tolist()
    keep = [i for i, t in enumerate(doc_texts) if t.strip()]

    dvecs, n_cut_doc = embed_texts([doc_texts[i] for i in keep], enc, label="문서")
    index = faiss.IndexFlatIP(DIM)                       # 정규화 → 내적 = 코사인 · 결정적
    index.add(np.asarray(dvecs, dtype="float32"))
    row_docid = [doc_ids[i] for i in keep]

    q_texts, q_ids = [], []
    for row in layers.queries_of(df, layer).itertuples(index=False):
        t = row.claims_independent or row.text_main or ""
        if str(t).strip():
            q_texts.append(str(t))
            q_ids.append(row.doc_id)
    qvecs, n_cut_q = embed_texts(q_texts, enc, label="질의")
    scores, idx = index.search(np.asarray(qvecs, dtype="float32"), k + (1 if exclude_self else 0))

    with out_path.open("w", encoding="utf-8") as f:
        for qi, qid in enumerate(q_ids):
            rank = 0
            for j, drow in enumerate(idx[qi]):
                if drow < 0:
                    continue
                did = row_docid[drow]
                if exclude_self and did == qid:
                    continue
                rank += 1
                f.write(f"{qid} Q0 {did} {rank} {scores[qi][j]:.6f} {enc.system.lower()}\n")
                if rank >= k:
                    break
    print(f"  질의 {len(q_ids):,}건 · 문서 절단 {n_cut_doc:,} · 질의 절단 {n_cut_q:,}")
    print(f"  run → {out_path}")
    return out_path


class _Tee:
    """출력을 화면과 파일에 함께 쓴다. **로그가 사라지면 사고를 사후에 못 읽는다.**

    `stream` 을 받는 이유: `EncoderDown` 의 진단 문구는 **stderr 로 나간다.** stdout 만 tee 하면
    정작 중단 사유가 로그에 남지 않는다 — 2026-08-17 재개 시도에서 실제로 그렇게 비었다.
    """

    def __init__(self, path: Path, stream=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = path.open("a", encoding="utf-8", buffering=1)
        self._out = stream if stream is not None else sys.stdout

    def write(self, s: str) -> int:
        self._out.write(s)
        self._f.write(s)
        return len(s)

    def flush(self) -> None:
        self._out.flush()
        self._f.flush()


def tee_to(path: Path) -> None:
    """stdout·stderr 를 같은 로그 파일로 함께 흘린다."""
    sys.stdout = _Tee(path, sys.stdout)      # type: ignore[assignment]
    sys.stderr = _Tee(path, sys.stderr)      # type: ignore[assignment]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(ENCODERS), required=True)
    ap.add_argument("--layer", choices=[layers.LAYER_A, layers.LAYER_B], default=layers.LAYER_A)
    ap.add_argument("--k", type=int, default=1000)
    ap.add_argument("--log", type=Path, default=None,
                    help=f"기본 {LOG_DIR}/dense_local_<model>.log — /tmp 에 두지 않는다")
    args = ap.parse_args()
    enc = ENCODERS[args.model]
    tee_to(args.log or LOG_DIR / f"dense_local_{args.model}.log")
    print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} · [{enc.system}] {enc.tag} · dim={DIM}"
          f" · num_ctx={enc.ctx} · 직렬(워커 1) · 간격 {MIN_INTERVAL_S}s · layer={args.layer} ===")
    search(args.model, k=args.k, layer=args.layer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
