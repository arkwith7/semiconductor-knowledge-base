#!/usr/bin/env python3
"""PLAN-006 T4 R2 — 공통 번역 전처리: 패싯 표현(한국어) → 영어 표현 후보 (산출물 동결 · 그래프를 바꾸지 않는다).

a′ 와 c 가 **같은 번역 파일**을 쓴다(§ train 결과 4절 · 사용자 결정 (나)). 번역에 LLM 을 쓰므로 이 파일을 쓰는
a′ 는 "LLM 번역 전처리 + 규칙 검색식 생성" 이다 — "LLM 을 전혀 쓰지 않는 비교군" 이 아니다.

재현성은 같은 설정의 재호출이 아니라 **산출물 동결**로 얻는다(§3.3′ A3). Opus 5.5 는 temperature 를 받지 않고
thinking 을 끌 수 없으므로 고정하는 것은 모델·effort·토큰 상한·프롬프트·배치 크기다.

호출 경로 (2026-10-10 사용자 결정): **Amazon Bedrock `bedrock-runtime` · 전역 교차 리전 추론 프로파일**
(`AnthropicBedrock` · `global.anthropic.claude-opus-5-5`). 처음엔 Mantle(`AnthropicBedrockMantle`)로 정했으나
서울 Mantle 엔드포인트에서 이 계정은 모든 모델이 404 였고, bedrock-runtime 전역 프로파일은 Opus 5.5 로 응답했다
(응답 model=claude-opus-5-5 · effort 수용). AWS 자격 증명 체인(환경변수 키 → 프로파일·SSO → 역할)으로 서명하며
비밀은 코드에 없다. 이 경로에서는
- 구조화 출력을 쓰지 않는다 → JSON 은 프롬프트로 요구하고 여기서 검증한다.
- 서버측 fallback 을 지원하지 않으며 **쓰지도 않는다** — 다른 모델의 번역이 섞이면 검색 결과에 모델 차이가 섞인다.
실패 처리: 일시 오류(429·5xx·연결)는 SDK 가 같은 모델로 재시도(MAX_RETRIES) · 권한·모델 접근·요청 형식 오류는 중단 ·
거절·형식이 깨진 출력은 그 배치의 표현을 실패 목록에 적고 계속한다 · 모델을 바꿔야 하면 새 번역 버전으로 만든다.

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
MODEL = "global.anthropic.claude-opus-5-5"
MAX_RETRIES = 3
# 설정 확인용 — 데이터에서 뽑지 않은 일반 기술어(코퍼스·청구항 원문 아님)
PROBE_TERMS = ["측벽 보호막", "고종횡비 접촉홀", "플라즈마 식각 챔버", "터널 산화막", "반사방지막"]
FAILED = ROOT / "data" / "queries" / "t4_term_translations_v1.failed.jsonl"
USAGE = ROOT / "data" / "queries" / "t4_term_translations_v1.usage.jsonl"
EFFORT = "low"          # 용어 번역은 단순 과업 — 고정값이며 결과를 보고 바꾸지 않는다
MAX_TOKENS = 16000
BATCH = 80
MAX_ALTS = 3
SYSTEM = (
    "You translate Korean semiconductor patent terms into English. For each term, give up to 3 English "
    "expressions that would actually appear in English-language patent documents for the same technical "
    "element, most common first. Keep each expression as specific as the Korean term; do not generalize "
    "(do not turn a specific film or structure into a broad word such as 'oxide' or 'layer' alone). "
    "If the Korean term is not a technical element (e.g. a generic word), return an empty list for it. "
    'Answer with JSON only, no prose and no code fence, exactly in this shape: '
    '{"items": [{"ko": "<the Korean term exactly as given>", "en": ["...", "..."]}]} '
    "with one item per input term, in input order."
)


def prompt_sha() -> str:
    return hashlib.sha256(json.dumps({"system": SYSTEM, "model": MODEL, "effort": EFFORT,
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


class BadOutput(ValueError):
    """형식이 깨진 응답 — 그 배치를 실패로 기록한다."""


def parse_items(text: str, asked: list[str]) -> dict[str, list[str]]:
    """응답 JSON → {ko: [en…]}. 요청하지 않은 항목은 버린다. 요청한 표현이 응답에 없으면 BadOutput.

    구조화 출력이 없는 경로이므로 스키마를 여기서 검증한다.
    """
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    data = json.loads(t)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise BadOutput("items 배열이 없다")
    out = {t: [] for t in asked}
    present = set()
    for it in data.get("items", []):
        if not isinstance(it, dict) or not isinstance(it.get("en", []), list):
            raise BadOutput(f"항목 형식이 다르다: {it!r}"[:200])
        ko = str(it.get("ko", "")).strip()
        if ko in out:
            present.add(ko)
            seen, alts = set(), []
            for e in it.get("en", []):
                e = " ".join(str(e).split()).strip()
                if e and e.lower() not in seen and e.lower() != ko.lower():
                    seen.add(e.lower())
                    alts.append(e)
            out[ko] = alts[:MAX_ALTS]
    missing = [t for t in asked if t not in present]
    if missing:
        raise BadOutput(f"응답에 빠진 표현 {len(missing)}개")
    return out


def make_client():
    import os

    from anthropic import AnthropicBedrock
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        raise SystemExit("ERROR: AWS_REGION 이 없다 — 실행 환경에 리전을 지정한다")
    return AnthropicBedrock(aws_region=region, max_retries=MAX_RETRIES)


def call(client, batch: list[str]):
    """한 배치 호출. 거절·잘림·형식 오류는 BadOutput — 권한·요청 오류는 SDK 예외가 그대로 올라가 실행을 멈춘다."""
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": "Terms:\n" + "\n".join(batch)}],
    )
    if resp.stop_reason == "refusal":
        raise BadOutput(f"refusal: {getattr(resp.stop_details, 'category', None)}")
    if resp.stop_reason == "max_tokens":
        raise BadOutput("max_tokens — 잘린 응답")
    text = "\n".join(b.text for b in resp.content if b.type == "text")
    return parse_items(text, batch), resp


def usage_row(resp, n: int) -> dict:
    u = resp.usage
    return {"terms": n, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "served_model": resp.model, "request_id": getattr(resp, "_request_id", None)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="표현 수만 센다(호출 없음)")
    ap.add_argument("--probe", action="store_true", help="표현 5개로 한 번 호출해 설정이 받아들여지는지 확인")
    a = ap.parse_args(argv)

    if a.probe:
        terms = PROBE_TERMS
    else:
        terms = collect_terms()
    print(f"표현 {len(terms)} · 배치 {BATCH} → 호출 {-(-len(terms) // BATCH)}회 · prompt_sha {prompt_sha()[:16]}…")
    if a.dry_run:
        return 0
    import anthropic

    client = make_client()
    if a.probe:
        got, resp = call(client, PROBE_TERMS)
        print(json.dumps({"served_model": resp.model, "stop_reason": resp.stop_reason,
                          "usage": usage_row(resp, 5), "sample": got}, ensure_ascii=False, indent=1))
        return 0

    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["ko"]] = r
    todo = [t for t in terms if t not in done]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh, USAGE.open("a", encoding="utf-8") as uh, \
            FAILED.open("a", encoding="utf-8") as xh:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            try:
                got, resp = call(client, batch)
            except (BadOutput, json.JSONDecodeError) as e:
                for t in batch:
                    xh.write(json.dumps({"ko": t, "reason": str(e)[:200]}, ensure_ascii=False) + "\n")
                xh.flush()
                print(f"{i + len(batch)}/{len(todo)} 실패 배치 기록: {str(e)[:80]}", flush=True)
                continue
            uh.write(json.dumps(usage_row(resp, len(batch))) + "\n"); uh.flush()
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
        "model": MODEL, "endpoint": "Amazon Bedrock bedrock-runtime · global 교차 리전 추론 · AnthropicBedrock", "fallback": "none",
        "served_models": sorted({r["served_model"] for r in rows}), "effort": EFFORT,
        "max_tokens": MAX_TOKENS, "batch": BATCH, "prompt_sha256": prompt_sha(),
        "sdk": f"anthropic=={anthropic.__version__}", "max_retries": MAX_RETRIES,
        "failed_terms": sum(1 for _ in FAILED.open(encoding="utf-8")) if FAILED.exists() else 0, "created_at": time.strftime("%Y-%m-%d"),
        "inputs": "train·dev 질의 청구항 1항에서 뽑은 명사 복합어 표현(공개 텍스트)만 · 봉인 분할 제외",
        "role": "a′·c 공통 번역 전처리 — 이 파일을 쓰는 a′ 는 'LLM 번역 전처리 + 규칙 검색식 생성' 이다",
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK {OUT.relative_to(ROOT)} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
