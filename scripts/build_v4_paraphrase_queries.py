#!/usr/bin/env python3
"""PLAN-005 §5 V4-1 — 표현 강건성 질의 세트 생성 (LLM 의역).

**무엇을 재려는가.** 같은 발명을 청구항이 아닌 문체로 서술했을 때도 같은 선행기술이
회수되는가. 정답지(심사관 인용)는 그대로이므로 **새 정답 없이** 잴 수 있다.

동결된 설계 (2026-09-05 · 사용자 승인 · §2 3단계):

  질의 집합  V2·V3 와 같은 759 질의. 질의 텍스트는 `claim1`(첫 독립항 원문).
  생성 모델  Bedrock 추론 프로파일 `global.anthropic.claude-opus-5`
             (베어 모델 ID 는 on-demand 미지원이라 ValidationException 이 난다)
             — **분해·링킹 경로와 다른 모델이어야 한다.** 같으면 재는 것이 표현
               강건성이 아니라 그 모델의 자기일관성이다. 기존 분해기는 Haiku 4.5
               (`AWS_BEDROCK_MODEL_HAIKU`)이고 링커는 표면형 사전(결정적)이라
               자기일관성 경로가 없다.
  의역 강도  3수준 — L1 청구항 문체 유지 / L2 산문 재서술 / L3 연구노트 메모
  결정성     Opus 5 는 `temperature` 를 받지 않는다(400). 그러므로 재현을 보장하는 것은
             호출 파라미터가 아니라 **동결된 산출물**이다 — 질의 세트를 sha256 과 함께
             커밋하고, 재실행은 sqlite 캐시로 무호출 재현한다.
  개인정보   청구항·초록에는 성명이 없다(§1-5). 통지서·결정서는 이 스크립트가 열지 않는다.
  egress     청구항 전문이 AWS 로 나간다 — 사용자 명시 승인분이다(2026-09-05).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    if (ROOT / ".env").exists():
        load_dotenv(ROOT / ".env")
except ImportError:
    pass

MODEL = os.getenv("V4_GEN_MODEL", "global.anthropic.claude-opus-5")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
CACHE = ROOT / "data" / "interim" / "v4_paraphrase_cache.sqlite"
OUT = ROOT / "data" / "processed" / "v4_paraphrase_queries.parquet"

LEVELS = {
    "L1": ("청구항 문체를 유지하되 표현만 바꾼다. 구성요소와 단계는 하나도 빠뜨리지 않는다. "
           "동의어·어순·조사 표현을 바꾸되 청구항 특유의 형식은 남긴다."),
    "L2": ("청구항 형식을 버리고 **평이한 기술 산문**으로 다시 쓴다. '~하는 단계', '상기', "
           "'~을 특징으로 하는' 같은 청구항 관용구를 쓰지 않는다. 기술 내용은 모두 보존한다."),
    "L3": ("연구자가 **연구노트에 적은 아이디어 메모**처럼 3~5문장으로 쓴다. 해결하려는 문제와 "
           "핵심 수단 위주로 서술하고, 청구항 구조(전제부·구성요소 나열)를 완전히 해체한다. "
           "기술요소의 이름은 보존한다."),
}
SYSTEM = (
    "당신은 반도체 분야 특허 문서를 다른 문체로 다시 쓰는 도구다. "
    "기술적 내용을 더하거나 빼지 않는다 — 새로운 기술요소를 발명하지 말고, 있는 것을 지우지도 마라. "
    "설명·머리말·마크다운 없이 다시 쓴 본문만 출력한다."
)


def _conn() -> sqlite3.Connection:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(CACHE, timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, text TEXT)")
    return c


def _key(pid: str, level: str, text: str) -> str:
    return hashlib.sha256(f"{MODEL}\n{level}\n{pid}\n{text}".encode()).hexdigest()


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import boto3
        _CLIENT = boto3.client("bedrock-runtime", region_name=REGION)
    return _CLIENT


def _generate(text: str, level: str) -> tuple[str, dict]:
    """Bedrock Converse. Opus 5 는 temperature 를 받지 않으므로 보내지 않는다."""
    cli = _client()
    for attempt in range(6):
        try:
            r = cli.converse(
                modelId=MODEL,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [
                    {"text": f"{LEVELS[level]}\n\n--- 원문(청구항) ---\n{text}"}]}],
                inferenceConfig={"maxTokens": 2048},
            )
            out = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
            return out.strip(), r.get("usage", {})
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            if "Throttl" in name or "Throttl" in str(e) or "ServiceUnavailable" in name:
                time.sleep(min(2 ** attempt * 0.5, 16))
                continue
            raise
    raise RuntimeError("throttled out")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="파일럿 질의 수 (0=전량)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true", help="호출 없이 대상 수만 센다")
    a = ap.parse_args()

    # 질의 집합 — V2 와 동일하게 재구성한다(심사관 인용이 코퍼스에 실재하는 거절특허).
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from report_priorart_baseline import load_concepts
    doc, qry, gt = load_concepts()
    qids = sorted(q for q, tg in gt.items() if q in qry and qry[q] and (tg & doc.keys()))

    meta = pd.read_parquet(ROOT / "data" / "patents" / "rejected_patents_meta.parquet",
                           columns=["patent_id", "claim1", "abstract"])
    meta["pid"] = meta.patent_id.str.replace("^patent:", "", regex=True)
    text = meta.set_index("pid")[["claim1", "abstract"]].to_dict("index")
    qids = [q for q in qids if q in text and text[q]["claim1"]]
    if a.limit:
        qids = qids[:a.limit]

    jobs = [(q, lv) for q in qids for lv in LEVELS]
    print(f"질의 {len(qids)} × 강도 {len(LEVELS)} = 호출 대상 {len(jobs)} · 모델 {MODEL} · {REGION}")
    if a.dry_run:
        return 0

    con = _conn()
    have = {r[0] for r in con.execute("SELECT key FROM cache")}
    todo = [(q, lv) for q, lv in jobs if _key(q, lv, text[q]["claim1"]) not in have]
    print(f"캐시 적중 {len(jobs) - len(todo)} · 신규 호출 {len(todo)}")

    tin = tout = 0
    if todo:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(_generate, text[q]["claim1"], lv): (q, lv) for q, lv in todo}
            for i, f in enumerate(as_completed(futs), 1):
                q, lv = futs[f]
                try:
                    out, usage = f.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  실패 {q}/{lv}: {type(e).__name__} {str(e)[:120]}")
                    continue
                tin += usage.get("inputTokens", 0); tout += usage.get("outputTokens", 0)
                con.execute("INSERT OR REPLACE INTO cache VALUES (?,?)",
                            (_key(q, lv, text[q]["claim1"]), out))
                if i % 25 == 0:
                    con.commit(); print(f"  {i}/{len(todo)}  in={tin} out={tout}")
        con.commit()

    rows = []
    for q in qids:
        rows.append({"publication_id": q, "variant": "claim", "text": text[q]["claim1"]})
        if text[q]["abstract"]:
            rows.append({"publication_id": q, "variant": "abstract", "text": text[q]["abstract"]})
        for lv in LEVELS:
            r = con.execute("SELECT text FROM cache WHERE key=?",
                            (_key(q, lv, text[q]["claim1"]),)).fetchone()
            if r and r[0]:
                rows.append({"publication_id": q, "variant": lv, "text": r[0]})
    df = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    sha = hashlib.sha256(a.out.read_bytes()).hexdigest()
    (a.out.with_suffix(".sha256")).write_text(f"{sha}  {a.out.name}\n", encoding="utf-8")

    print(f"\n질의 세트 {len(df)}행 · 변형별:")
    print(df.variant.value_counts().to_string())
    print(f"\n토큰  in={tin}  out={tout}")
    print(f"sha256 {sha}\n→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
