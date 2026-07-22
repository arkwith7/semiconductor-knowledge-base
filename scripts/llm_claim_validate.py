#!/usr/bin/env python3
"""청구항 feature 분해 — LLM 검증 계층 (로컬 Ollama qwen3-coder | AWS Bedrock Haiku).

규칙 분해가 flag 한 청구항(요소 1개·과대 요소 등 ~15%)만 LLM 으로 재분해한다.
temperature=0 + sqlite 캐시로 결정적 — 같은 청구항이면 같은 분해가 재실행 시 무호출로 재현된다.
캐시 키에 MODEL 이 들어가므로 백엔드를 바꿔도 서로 다른 캐시 슬롯을 쓴다(교차 오염 없음).

백엔드는 LLM_BACKEND 로 고른다: bedrock(기본, AWS_BEDROCK_MODEL_HAIKU 있을 때) | ollama.
Bedrock 경로는 청구항 전문을 외부(AWS)로 보낸다 — 사용자가 명시 승인한 경우에만 쓴다(egress).
규칙이 신뢰 가능한 85%는 LLM 을 부르지 않는다. LLM 응답이 파싱 실패거나 비면 규칙 출력을 유지한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# .env(paper 저장소)에서 AWS 자격증명·모델 ID 를 읽는다. 이미 설정된 환경변수는 덮지 않는다.
try:
    from dotenv import load_dotenv
    for _p in ("/home/arkwith/Dev/SKKU/sdkb-foresight-paper/.env",
               str(Path(__file__).resolve().parents[2] / "SKKU/sdkb-foresight-paper/.env")):
        if Path(_p).exists():
            load_dotenv(_p)
            break
except ImportError:
    pass

OLLAMA_URL = "http://localhost:11434/api/chat"
_OLLAMA_MODEL = "qwen3-coder:30b"
_BEDROCK_MODEL = os.getenv("AWS_BEDROCK_MODEL_HAIKU", "")
BACKEND = os.getenv("LLM_BACKEND") or ("bedrock" if _BEDROCK_MODEL else "ollama")
MODEL = _BEDROCK_MODEL if BACKEND == "bedrock" else _OLLAMA_MODEL
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


def _call_ollama(text: str, timeout: int = 240) -> list[str]:
    resp = requests.post(OLLAMA_URL, timeout=timeout, json={
        "model": MODEL, "stream": False, "options": {"temperature": 0, "seed": 0},
        "messages": [{"role": "system", "content": _SYSTEM},
                     {"role": "user", "content": f"청구항: {text}"}],
    })
    resp.raise_for_status()
    return _parse(resp.json().get("message", {}).get("content", "")) or []


_BEDROCK = None


def _bedrock():
    """리전당 클라이언트 1개(호출은 스레드 안전). 지연 생성."""
    global _BEDROCK
    if _BEDROCK is None:
        import boto3
        _BEDROCK = boto3.client("bedrock-runtime",
                                region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _BEDROCK


def _call_bedrock(text: str, timeout: int = 60) -> list[str]:
    """Bedrock Haiku converse. 스로틀은 지수 백오프로 재시도."""
    cli = _bedrock()
    for attempt in range(6):
        try:
            r = cli.converse(
                modelId=MODEL, system=[{"text": _SYSTEM}],
                messages=[{"role": "user", "content": [{"text": f"청구항: {text}"}]}],
                inferenceConfig={"temperature": 0, "maxTokens": 1024})
            return _parse(r["output"]["message"]["content"][0]["text"]) or []
        except Exception as e:  # noqa: BLE001 — 스로틀/일시 오류만 백오프, 그 외는 규칙 유지
            if "Throttl" in type(e).__name__ or "Throttl" in str(e):
                time.sleep(min(2 ** attempt * 0.5, 16))
                continue
            return []
    return []


def _call_llm(text: str) -> list[str]:
    try:
        return _call_bedrock(text) if BACKEND == "bedrock" else _call_ollama(text)
    except (requests.RequestException, ValueError, KeyError):
        return []


def llm_decompose(claim_text: str, *, cache: sqlite3.Connection | None = None) -> list[str] | None:
    """청구항 1건 → 요소 문자열 목록. 캐시 우선, 실패 시 None(규칙 출력 유지)."""
    own = cache is None
    cache = cache or _conn()
    k = _key(claim_text)
    row = cache.execute("SELECT features FROM cache WHERE key=?", (k,)).fetchone()
    if row is not None:
        return json.loads(row[0]) or None
    feats = _call_llm(claim_text)
    cache.execute("INSERT OR REPLACE INTO cache (key, features) VALUES (?,?)",
                  (k, json.dumps(feats, ensure_ascii=False)))
    cache.commit()
    if own:
        cache.close()
    return feats or None


def llm_decompose_batch(texts: list[str], *, cache: sqlite3.Connection,
                        max_workers: int = 12) -> dict[str, list[str]]:
    """여러 청구항을 동시 재분해 → {text: features}. 캐시 미스분만 병렬 네트워크 호출.

    네트워크(Bedrock)는 워커 스레드에서, sqlite 읽기/쓰기는 메인 스레드에서만 한다
    (단일 커넥션 스레드 안전 확보). 같은 입력이면 캐시로 재현 — 결정적.
    """
    uniq = list(dict.fromkeys(texts))
    result: dict[str, list[str]] = {}
    todo: list[str] = []
    for t in uniq:
        row = cache.execute("SELECT features FROM cache WHERE key=?", (_key(t),)).fetchone()
        if row is not None:
            result[t] = json.loads(row[0])
        else:
            todo.append(t)
    if todo:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_call_llm, t): t for t in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                t = futs[fut]
                try:
                    feats = fut.result()
                except Exception:  # noqa: BLE001
                    feats = []
                result[t] = feats
                cache.execute("INSERT OR REPLACE INTO cache (key, features) VALUES (?,?)",
                              (_key(t), json.dumps(feats, ensure_ascii=False)))
                if i % 500 == 0:
                    cache.commit()
                    print(f"  [llm] {i}/{len(todo)} 재분해 ({BACKEND})")
        cache.commit()
    return result
