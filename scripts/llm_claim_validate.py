#!/usr/bin/env python3
"""청구항 feature 분해 — LLM 검증 계층 (로컬 Ollama qwen3-coder).

규칙 분해가 flag 한 청구항(요소 1개·과대 요소 등 ~15%)만 로컬 LLM 으로 재분해한다.
로컬이라 KIPRIS 비재배포 청구항이 기기를 벗어나지 않는다(라이선스 안전). temperature=0 +
sqlite 캐시로 결정적 — 같은 청구항이면 같은 분해가 재실행 시 무호출로 재현된다.

규칙이 신뢰 가능한 85%는 LLM 을 부르지 않는다. LLM 응답이 파싱 실패거나 비면 규칙 출력을 유지한다.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3-coder:30b"
_CACHE = Path(__file__).resolve().parents[1] / "data" / "interim" / "llm_claim_cache.sqlite"

_SYSTEM = (
    "You segment ONE patent claim into its distinct limitations (features). "
    "A limitation is a single structural or step element. Preserve the original "
    "language (Korean or English). Drop leading conjunctions (및/그리고/and/or) and "
    "the '상기'/'said' back-reference prefix is fine to keep. "
    "Return ONLY a JSON array of strings — no preamble, no explanation, no markdown."
)


def _conn() -> sqlite3.Connection:
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_CACHE)
    c.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, features TEXT)")
    return c


def _key(text: str) -> str:
    return hashlib.sha256(f"{MODEL}\n{text}".encode()).hexdigest()


def _parse(content: str) -> list[str] | None:
    """LLM 출력에서 JSON 배열을 뽑는다. 코드펜스·잡텍스트에 견고하게."""
    s = content.strip()
    i, j = s.find("["), s.rfind("]")
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        arr = json.loads(s[i : j + 1])
    except json.JSONDecodeError:
        return None
    feats = [str(x).strip() for x in arr if str(x).strip()]
    return feats or None


def llm_decompose(claim_text: str, *, cache: sqlite3.Connection | None = None,
                  timeout: int = 240) -> list[str] | None:
    """청구항 1건 → 요소 문자열 목록. 캐시 우선, 실패 시 None(규칙 출력 유지)."""
    own = cache is None
    cache = cache or _conn()
    k = _key(claim_text)
    row = cache.execute("SELECT features FROM cache WHERE key=?", (k,)).fetchone()
    if row is not None:
        return json.loads(row[0]) or None
    try:
        resp = requests.post(OLLAMA_URL, timeout=timeout, json={
            "model": MODEL, "stream": False, "options": {"temperature": 0, "seed": 0},
            "messages": [{"role": "system", "content": _SYSTEM},
                         {"role": "user", "content": f"청구항: {claim_text}"}],
        })
        resp.raise_for_status()
        feats = _parse(resp.json().get("message", {}).get("content", "")) or []
    except (requests.RequestException, ValueError):
        feats = []
    cache.execute("INSERT OR REPLACE INTO cache (key, features) VALUES (?,?)",
                  (k, json.dumps(feats, ensure_ascii=False)))
    cache.commit()
    if own:
        cache.close()
    return feats or None
