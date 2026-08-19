"""입력 토큰 실측 — `bedrock:CountTokens` 로 §12.6 비용을 무과금 확정 (PLAN-038 §12.5·§12.6).

**생성 호출을 하지 않는다.** `CountTokens` 는 과금되지 않으므로, 1,188 유상 호출을 승인하기
전에 입력 규모를 **추정이 아니라 실측**으로 못박는 것이 이 모듈의 유일한 목적이다.

계수 ID 는 베이스 ID(`frozen.COUNT_TOKENS_MODEL_ID`)다 — `global.` 추론 프로파일은 CountTokens
를 받지 않는다(§12.5 해소 기록). 같은 모델 스냅샷(20251001)이라 §1-11 "모델 버전 고정"은 유지된다.

**세는 것은 실제 실험 입력 그대로다.** `context.build_request()` 가 만든 system·messages 를
그대로 넘긴다 — 여기서 프롬프트를 다시 조립하면 계수와 호출이 갈린다.

CLI:
    uv run python -m sdkb_paper.rag.count            # 두 팔 198질의 = 396 계수 호출(무과금)
    uv run python -m sdkb_paper.rag.count --limit 5  # 표본 확인
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from .. import config
from ..retrieval.candidate import CandidateMask
from . import context as ctx
from . import frozen

try:
    from dotenv import load_dotenv

    load_dotenv(config.ROOT / ".env")
except ImportError:
    pass

OUT_PATH = config.RAG_DIR / f"count_tokens_{frozen.RUNSET}_{frozen.SPLIT}_k{frozen.K}.json"

# 1P 참고 단가(자릿수 감각용 · Bedrock 요율 아님 — §12.6 의 단서를 그대로 유지한다).
PRICE_IN_PER_MTOK = 1.0
PRICE_OUT_PER_MTOK = 5.0
OUTPUT_TOKENS_ASSUMED = 500  # §12.6 가정. 실측이 아니므로 라벨을 붙여 보고한다.

# 컨텍스트 예산(§12.2 동결 규칙) — 창 200,000 토큰의 25 %.
CONTEXT_WINDOW = 200_000
BUDGET = 50_000


def _count_one(client, qc: ctx.QueryContext) -> int:
    req = ctx.build_request(qc.query_claims, qc.docs_block())
    last_err = ""
    for attempt in range(6):
        try:
            r = client.count_tokens(
                modelId=frozen.COUNT_TOKENS_MODEL_ID,
                input={"converse": {"system": req["system"], "messages": req["messages"]}},
            )
            return int(r["inputTokens"])
        except Exception as e:  # noqa: BLE001 — 스로틀만 재시도, 나머지는 즉시 드러낸다
            last_err = f"{type(e).__name__}: {e}"
            if "Throttl" in last_err or "Timeout" in last_err:
                time.sleep(min(2**attempt * 0.5, 16))
                continue
            raise
    raise RuntimeError(f"CountTokens 재시도 소진: {last_err}")


def run(limit: int, workers: int) -> int:
    import boto3

    doc_text, q_text = ctx.load_texts()
    mask = CandidateMask()
    qids = ctx.test_qids()
    if limit:
        qids = qids[:limit]
    contexts = {arm: ctx.build_arm_contexts(arm, doc_text, q_text, mask, qids) for arm in frozen.ARMS}

    client = boto3.client("bedrock-runtime", region_name=frozen.CALL_REGION)
    per_arm: dict[str, dict[str, int]] = {}
    for arm in frozen.ARMS:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            toks = list(ex.map(lambda q: _count_one(client, contexts[arm][q]), qids))
        per_arm[arm] = dict(zip(qids, toks))

    report = {
        "plan": "PLAN-038 §12.6",
        "count_tokens_model_id": frozen.COUNT_TOKENS_MODEL_ID,
        "call_model_id": frozen.MODEL_ID,
        "k": frozen.K,
        "runset": frozen.RUNSET,
        "split": frozen.SPLIT,
        "n_queries": len(qids),
        "n_repeats": frozen.N_REPEATS,
        "arms": {},
    }
    total_in = 0
    for arm in frozen.ARMS:
        toks = [per_arm[arm][q] for q in qids]
        chars = [len(contexts[arm][q].query_claims) + len(contexts[arm][q].docs_block()) for q in qids]
        p95 = statistics.quantiles(toks, n=20, method="inclusive")[18] if len(toks) > 1 else toks[0]
        report["arms"][arm] = {
            "run_sha256": ctx.run_sha256(arm),
            "n_masked": sum(contexts[arm][q].n_masked for q in qids),
            "tokens_sum": sum(toks),
            "tokens_median": statistics.median(toks),
            "tokens_p95": p95,
            "tokens_max": max(toks),
            "chars_sum": sum(chars),
            "chars_per_token": round(sum(chars) / sum(toks), 4),
            "p95_budget_pct": round(100 * p95 / BUDGET, 1),
            "p95_window_pct": round(100 * p95 / CONTEXT_WINDOW, 1),
        }
        total_in += sum(toks)
    total_in *= frozen.N_REPEATS
    n_calls = len(qids) * len(frozen.ARMS) * frozen.N_REPEATS
    out_tok = n_calls * OUTPUT_TOKENS_ASSUMED
    report["totals"] = {
        "n_calls": n_calls,
        "input_tokens_measured": total_in,
        "output_tokens_assumed": out_tok,
        "usd_1p_reference": round(
            total_in / 1e6 * PRICE_IN_PER_MTOK + out_tok / 1e6 * PRICE_OUT_PER_MTOK, 2
        ),
        "note": "1P 참고 단가 환산이며 Bedrock 요율이 아니다. 출력 토큰은 가정(500/호출)이다.",
    }

    for arm, a in report["arms"].items():
        print(
            f"[팔 {arm}] 입력 합 {a['tokens_sum']:,}tok · 중앙 {a['tokens_median']:,.0f} · "
            f"p95 {a['tokens_p95']:,.0f}tok(예산의 {a['p95_budget_pct']}% · 창의 {a['p95_window_pct']}%) · "
            f"최대 {a['tokens_max']:,} · 자/토큰 {a['chars_per_token']} · 마스크 {a['n_masked']}건"
        )
    t = report["totals"]
    print(
        f"[규모] 호출 {t['n_calls']:,}건 · 입력 실측 {t['input_tokens_measured']:,}tok "
        f"({t['input_tokens_measured'] / 1e6:.2f}M) · 출력 가정 {t['output_tokens_assumed']:,}tok"
    )
    print(f"[비용] 1P 환산 ≈ ${t['usd_1p_reference']} — {t['note']}")
    if limit:
        print("[주의] --limit 표본이므로 이 합계는 §12.6 의 전량 수치가 아니다.")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
    print(f"[기록] {OUT_PATH.relative_to(config.ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="C2′ 입력 토큰 실측 (무과금 · PLAN-038 §12.6)")
    ap.add_argument("--limit", type=int, default=0, help="표본: 앞 N질의만(전량 수치 아님)")
    ap.add_argument("--workers", type=int, default=8, help="동시 계수 호출 수")
    a = ap.parse_args()
    return run(a.limit, a.workers)


if __name__ == "__main__":
    raise SystemExit(main())
