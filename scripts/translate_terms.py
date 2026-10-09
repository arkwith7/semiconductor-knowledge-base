#!/usr/bin/env python3
"""PLAN-006 T4 R2 — 공통 번역 전처리: 패싯 표현(한국어) → 영어 표현 후보 (산출물 동결 · 그래프를 바꾸지 않는다).

a′ 와 c 가 **같은 번역 파일**을 쓴다(§ train 결과 4절 · 사용자 결정 (나)). 번역에 LLM 을 쓰므로 이 파일을 쓰는
a′ 는 "LLM 번역 전처리 + 규칙 검색식 생성" 이다 — "LLM 을 전혀 쓰지 않는 비교군" 이 아니다.

재현성은 같은 설정의 재호출이 아니라 **산출물 동결**로 얻는다(§3.3′ A3). Opus 5.5 는 temperature 를 받지 않고
thinking 을 끌 수 없으므로 고정하는 것은 모델·effort·토큰 상한·프롬프트·배치 크기다. 실제로 응답한 모델
(fallback 이 돌았는지)을 행마다 기록한다.

보내는 것: train·dev 질의 청구항에서 뽑은 **명사 복합어 표현만**(공개 청구항). 통지서·결정서 원문은 보내지 않는다(§1-5).
봉인 분할(test·test_b)의 표현은 모으지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "data" / "queries" / "t4_term_translations_v1.jsonl"
MANIFEST = ROOT / "data" / "queries" / "t4_term_translations_v1.manifest.json"
MODEL = "claude-opus-5-5"
EFFORT = "low"          # 용어 번역은 단순 과업 — 고정값이며 결과를 보고 바꾸지 않는다
MAX_TOKENS = 16000
BATCH = 80
MAX_ALTS = 3
SYSTEM = (
    "You translate Korean semiconductor patent terms into English. For each term, give up to 3 English "
    "expressions that would actually appear in English-language patent documents for the same technical "
    "element, most common first. Keep each expression as specific as the Korean term; do not generalize "
    "(do not turn a specific film or structure into a broad word such as 'oxide' or 'layer' alone). "
    "If the Korean term is not a technical element (e.g. a generic word), return an empty list for it."
)
SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"ko": {"type": "string"}, "en": {"type": "array", "items": {"type": "string"}}},
        "required": ["ko", "en"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False,
}


def prompt_sha() -> str:
    return hashlib.sha256(json.dumps({"system": SYSTEM, "schema": SCHEMA, "model": MODEL, "effort": EFFORT,
                                      "max_tokens": MAX_TOKENS, "batch": BATCH}, sort_keys=True).encode()).hexdigest()


def collect_terms(splits=("train", "dev"), a_n: int = 8) -> list[str]:
    """비교군 a′(N 상한)·c1 이 고를 수 있는 패싯 표현 전부. 정렬해 돌려준다."""
    import build_search_query as Q
    import ir_corpus
    import kipris_emulator as K
    from splits import SEALED, load_split

    if set(splits) & SEALED:
        raise SystemExit("ERROR: 봉인 분할의 표현은 모으지 않는다")
    smap = load_split()
    C = ir_corpus.load(["doc_id", "is_candidate", "title", "abstract", "claims_full", "claims_independent",
                        "first_claim_original", "ipc"])
    claim = dict(zip(C["doc_id"], C["first_claim_original"]))
    emu = K.Emulator(C)
    df, lex = Q.DF(emu), Q.Lexicon()
    terms: set[str] = set()
    for q in sorted(d for d, s in smap.items() if s in splits):
        text = claim.get(q) or ""
        terms |= {f.term for f in Q.facets_keywords(text, df, a_n)}
        terms |= {f.term for f in Q.facets_elements(text, df, lex)}
    return sorted(terms)


def parse_items(text: str, asked: list[str]) -> dict[str, list[str]]:
    """응답 JSON → {ko: [en…]}. 요청하지 않은 항목은 버리고, 빠진 항목은 빈 목록으로 둔다."""
    data = json.loads(text)
    out = {t: [] for t in asked}
    for it in data.get("items", []):
        ko = it.get("ko", "").strip()
        if ko in out:
            seen, alts = set(), []
            for e in it.get("en", []):
                e = " ".join(str(e).split()).strip()
                if e and e.lower() not in seen and e.lower() != ko.lower():
                    seen.add(e.lower())
                    alts.append(e)
            out[ko] = alts[:MAX_ALTS]
    return out


def call(client, batch: list[str]):
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content": "Terms:\n" + "\n".join(batch)}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"refusal: {getattr(resp.stop_details, 'category', None)}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("max_tokens — 배치를 줄여야 한다")
    text = next(b.text for b in resp.content if b.type == "text")
    return parse_items(text, batch), resp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="표현 수만 센다(호출 없음)")
    ap.add_argument("--probe", action="store_true", help="표현 5개로 한 번 호출해 설정이 받아들여지는지 확인")
    a = ap.parse_args(argv)

    terms = collect_terms()
    print(f"표현 {len(terms)} · 배치 {BATCH} → 호출 {-(-len(terms) // BATCH)}회 · prompt_sha {prompt_sha()[:16]}…")
    if a.dry_run:
        return 0
    import anthropic

    client = anthropic.Anthropic()
    if a.probe:
        got, resp = call(client, terms[:5])
        print(json.dumps({"served_model": resp.model, "stop_reason": resp.stop_reason,
                          "usage": resp.usage.to_dict(), "sample": got}, ensure_ascii=False, indent=1))
        return 0

    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["ko"]] = r
    todo = [t for t in terms if t not in done]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    served = set()
    with OUT.open("a", encoding="utf-8") as fh:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            got, resp = call(client, batch)
            served.add(resp.model)
            for t in batch:
                fh.write(json.dumps({"ko": t, "en": got[t], "served_model": resp.model}, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{i + len(batch)}/{len(todo)} served={resp.model}", flush=True)
            time.sleep(0.5)
    rows = sorted((json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()), key=lambda r: r["ko"])
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "file": OUT.name, "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "rows": len(rows),
        "with_translation": sum(1 for r in rows if r["en"]),
        "model": MODEL, "served_models": sorted({r["served_model"] for r in rows}), "effort": EFFORT,
        "max_tokens": MAX_TOKENS, "batch": BATCH, "prompt_sha256": prompt_sha(),
        "sdk": f"anthropic=={anthropic.__version__}", "created_at": time.strftime("%Y-%m-%d"),
        "inputs": "train·dev 질의 청구항 1항에서 뽑은 명사 복합어 표현(공개 텍스트)만 · 봉인 분할 제외",
        "role": "a′·c 공통 번역 전처리 — 이 파일을 쓰는 a′ 는 'LLM 번역 전처리 + 규칙 검색식 생성' 이다",
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK {OUT.relative_to(ROOT)} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
