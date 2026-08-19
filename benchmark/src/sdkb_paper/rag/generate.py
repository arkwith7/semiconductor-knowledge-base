"""생성 호출 — 동결 컨텍스트 → Bedrock (PLAN-038 §12 · `make rag`).

**기본은 dry-run 이다.** 유상 호출은 `--execute` 를 명시할 때만 일어난다 — 1,188 호출은
되돌릴 수 없는 과금이므로(§12.6 ≈ 33.4M 입력 토큰) 실수로 시작되지 않게 막는다.

보존 규율(§8 성공기준 4). 응답 원문·`stop_reason`·`usage`·서빙 메타데이터를 **전량** JSONL 로
남긴다 — 재채점이 가능해야 하고, 회차 간 분산을 숨기지 않아야 한다(§1-11 *"비결정성을 숨기지
않는다"*). 파일 자체는 특허 본문 파생이므로 커밋하지 않는다(§1-5) — 커밋되는 것은 해시와 집계다.

CLI:
    uv run python -m sdkb_paper.rag.generate                 # dry-run(호출 0) · 규모만 보고
    uv run python -m sdkb_paper.rag.generate --execute       # 전량 실행(과금)
    uv run python -m sdkb_paper.rag.generate --execute --limit 5 --repeats 1   # 스모크
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .. import config
from ..retrieval.candidate import CandidateMask
from . import context as ctx
from . import frozen

try:  # .env → os.environ (boto3 가 환경에서 자격증명·리전을 읽는다)
    from dotenv import load_dotenv

    load_dotenv(config.ROOT / ".env")
except ImportError:
    pass

_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import boto3

        _CLIENT = boto3.client("bedrock-runtime", region_name=frozen.CALL_REGION)
    return _CLIENT


def gen_path(arm: str, rep: int, runset: str = frozen.RUNSET,
             split: str = frozen.SPLIT) -> Path:
    return config.RAG_GEN_DIR / f"gen_{runset}_{split}_{arm}_rep{rep}.jsonl"


def call_once(qc: ctx.QueryContext) -> dict:
    """1회 호출 → 기록 dict. 스로틀·5xx 는 재시도(§12.4 "재시도로 해결되면 수정 아님")."""
    req = ctx.build_request(qc.query_claims, qc.docs_block())
    cli = _client()
    last_err = ""
    for attempt in range(6):
        try:
            r = cli.converse(**req)
            meta = r.get("ResponseMetadata", {})
            return {
                "ok": True,
                "text": r["output"]["message"]["content"][0]["text"],
                "stop_reason": r.get("stopReason", ""),
                "usage": r.get("usage", {}),
                # global 프로파일은 서빙 리전이 고정되지 않는다(§11.9-2) — 응답 메타를 남긴다.
                "response_meta": {
                    "request_id": meta.get("RequestId", ""),
                    "headers": {
                        k: v
                        for k, v in meta.get("HTTPHeaders", {}).items()
                        if k.startswith("x-amzn") or k == "date"
                    },
                },
                "attempts": attempt + 1,
            }
        except Exception as e:  # noqa: BLE001 — 실패는 결측으로 정직하게 기록한다
            last_err = f"{type(e).__name__}: {e}"
            transient = any(s in last_err for s in ("Throttl", "Timeout", "5xx", "ServiceUnavailable"))
            if transient:
                time.sleep(min(2**attempt * 0.5, 16))
                continue
            break
    return {"ok": False, "error": last_err, "attempts": 6}


def run(execute: bool, limit: int, repeats: int, *, split: str = frozen.SPLIT,
        runset: str = frozen.RUNSET, layer: str = "A", status: str = frozen.STATUS,
        unseal: bool = False, reason: str = "") -> int:
    doc_text, q_text = ctx.load_texts(layer)
    mask = CandidateMask()
    qids = ctx.test_qids(split, unseal=unseal, reason=reason)
    if limit:
        qids = qids[:limit]

    contexts = {arm: ctx.build_arm_contexts(arm, doc_text, q_text, mask, qids,
                                            split=split, runset=runset)
                for arm in frozen.ARMS}
    n_masked = {arm: sum(c.n_masked for c in contexts[arm].values()) for arm in frozen.ARMS}
    chars = {
        arm: sum(len(c.query_claims) + len(c.docs_block()) for c in contexts[arm].values())
        for arm in frozen.ARMS
    }
    n_calls = len(qids) * len(frozen.ARMS) * repeats

    manifest = frozen.frozen_manifest(runset=runset, split=split, status=status)
    print(f"[동결] {json.dumps(manifest, ensure_ascii=False)}")
    for arm in frozen.ARMS:
        print(
            f"[팔 {arm}] run sha256={ctx.run_sha256(arm, split, runset)[:16]}… · 질의 {len(qids)} · "
            f"마스크 제외 {n_masked[arm]}건 · 입력 {chars[arm]:,}자"
        )
    print(f"[규모] 호출 {n_calls}건 · 입력 합계 {sum(chars.values()) * repeats:,}자 "
          f"(실측 자/토큰 ≈ 0.99 · PLAN-038 §12.2)")

    if not execute:
        print("[dry-run] 호출하지 않았다. 실행하려면 --execute 를 준다(과금).")
        return 0

    config.RAG_GEN_DIR.mkdir(parents=True, exist_ok=True)
    n_fail = 0
    for rep in range(repeats):
        for arm in frozen.ARMS:
            out = gen_path(arm, rep, runset, split)
            with out.open("w", encoding="utf-8") as f:
                header = {"_header": True, "arm": arm, "rep": rep, "n_queries": len(qids),
                          "run_sha256": ctx.run_sha256(arm, split, runset), **manifest}
                f.write(json.dumps(header, ensure_ascii=False, sort_keys=True) + "\n")
                for qid in qids:
                    qc = contexts[arm][qid]
                    rec = call_once(qc)
                    rec.update({"qid": qid, "arm": arm, "rep": rep,
                                "context_doc_ids": list(qc.doc_ids), "n_masked": qc.n_masked})
                    if not rec["ok"]:
                        n_fail += 1
                    f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"[기록] {out.relative_to(config.ROOT)}")
    print(f"[완료] 실패 {n_fail}/{n_calls}건")
    return 1 if n_fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="C2′ 전달 실험 — 생성 호출 (PLAN-038 §12)")
    ap.add_argument("--execute", action="store_true", help="실제 호출(과금). 없으면 dry-run")
    ap.add_argument("--limit", type=int, default=0, help="스모크: 앞 N질의만")
    ap.add_argument("--repeats", type=int, default=frozen.N_REPEATS, help="반복 회차(동결값 3)")
    # 판독 B (PLAN-047 §13.5) — 계측기는 그대로, 읽는 대상만 바꾼다.
    ap.add_argument("--split", choices=[frozen.SPLIT, frozen.SPLIT_B], default=frozen.SPLIT)
    ap.add_argument("--runset", default=None, help="동결 run 세트 라벨(기본은 층에 맞춰 자동)")
    ap.add_argument("--unseal", action="store_true", help="B층 봉인 개봉(원장 기록)")
    ap.add_argument("--reason", default="", help="개봉 사유(원장에 기록)")
    a = ap.parse_args()
    is_b = a.split == frozen.SPLIT_B
    runset = a.runset or (frozen.RUNSET_B if is_b else frozen.RUNSET)
    layer = "B" if is_b else "A"
    status = frozen.STATUS_B if is_b else frozen.STATUS
    if a.repeats != frozen.N_REPEATS:
        print(f"[주의] 반복이 동결값({frozen.N_REPEATS})과 다르다 — 스모크 전용이며 "
              f"이 산출물은 §6.8 표에 싣지 않는다.")
    return run(a.execute, a.limit, a.repeats, split=a.split, runset=runset, layer=layer,
               status=status, unseal=a.unseal, reason=a.reason)


if __name__ == "__main__":
    raise SystemExit(main())
