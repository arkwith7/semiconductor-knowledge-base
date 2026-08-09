"""B1 인용 외부특허 본문 수집 (1000-record 캐노니컬 전체 대상).

근거: `docs/dataset_full_collection_runbook.md` Phase B.

오케스트레이션:
- canonical JSONL 의 `ground_truth_all` 에서 distinct cited ID 수집
- 국가별 라우팅:
    KR/pub | KR/grant → KIPRIS Plus (scripts/enrich_unresolved.resolve_kr 재사용)
    JP/pub | JP/grant → Google Patents 스크래핑 (resolve_google_patents)
    US/pub | US/grant → Google Patents 스크래핑
    WO/CN/EP/...     → EPO OPS (resolve_epo_ops)
- fulltext 출력: `data/processed/fulltext/prior_arts/<normalized_id>.txt`
- 인덱스: `data/processed/fulltext/prior_arts/_index.json`

사용
====
    .venv/bin/python scripts/collect_cited_fulltext_full.py --plan      # 호출 예산 추정
    .venv/bin/python scripts/collect_cited_fulltext_full.py --kr-only --max-kr-calls 200
    .venv/bin/python scripts/collect_cited_fulltext_full.py --include-jp --include-us --include-epo
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.citation_norm import parse as parse_citation  # noqa: E402
from kipris_dataset.kipris import (  # noqa: E402
    KiprisClient,
    KiprisQuotaExceeded,
    KiprisServiceKeyError,
)

# 기존 enrich_unresolved.py 의 헬퍼 그대로 재사용 (검증 코드, 재구현 회피)
import enrich_unresolved as eu  # noqa: E402


DEFAULT_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
OUT_DIR = REPO_ROOT / "data/processed/fulltext/prior_arts"
INDEX_FILE = OUT_DIR / "_index.json"
CACHE_FILE = REPO_ROOT / "data/processed/citation_resolution_full_cache.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_cache(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": {}}


def _save_cache(path: Path, cache: Dict[str, Any]) -> None:
    cache["generated_at"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)


def _build_entry(original: str) -> Optional[Dict[str, Any]]:
    cit = parse_citation(original)
    if not cit.country or not cit.serial:
        return None
    return {
        "doc_id": cit.normalized_id,
        "original": original,
        "country": cit.country,
        "kind": cit.kind,
        "serial": cit.serial,
        "resolved": False,
    }


def _collect_distinct_citations(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """distinct doc_id 기준으로 1회만 처리. 각 doc_id 의 첫 등장 original 사용."""
    seen: Dict[str, Dict[str, Any]] = {}
    for r in records:
        for cid in (r.get("ground_truth_all") or []):
            if not isinstance(cid, str):
                continue
            ent = _build_entry(cid)
            if not ent:
                continue
            if ent["doc_id"] not in seen:
                seen[ent["doc_id"]] = ent
    return list(seen.values())


def _classify(entry: Dict[str, Any]) -> str:
    c = entry["country"].upper()
    if c == "KR":
        return "kr"
    if c == "JP":
        return "jp"
    if c == "US":
        return "us"
    if c in {"WO", "CN", "EP", "DE", "FR", "GB"}:
        return "epo"
    return "other"


def _ensure_out_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # FULLTEXT_DIR 와 정합: enrich_unresolved 의 _write_fulltext 가 etching_prior_arts/ 로 쓰므로
    # 여기는 자체 writer 를 둔다 (아래 _write_fulltext).


def _write_fulltext(entry: Dict[str, Any]) -> None:
    doc_id = entry["doc_id"]
    path = OUT_DIR / f"{_safe_filename(doc_id)}.txt"
    lines = [
        f"Document Number: {doc_id}",
        f"Original ID: {entry.get('original','')}",
        f"Country/Kind: {entry.get('country','')}/{entry.get('kind','')}",
        f"Resolved: {str(entry.get('resolved', False)).lower()}",
        f"Source: {entry.get('source','')}",
        f"Fetched: {entry.get('fetched_at','')}",
        "=" * 80,
        "",
    ]
    if entry.get("title"):
        lines += ["## TITLE", "", entry["title"], ""]
    if entry.get("abstract"):
        lines += ["## ABSTRACT", "", entry["abstract"], ""]
    if entry.get("claim1"):
        lines += ["## CLAIM 1", "", entry["claim1"], ""]
    if entry.get("ipc"):
        lines += ["## IPC", "", entry["ipc"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_unresolved_placeholder(entry: Dict[str, Any]) -> None:
    doc_id = entry["doc_id"]
    path = OUT_DIR / f"{_safe_filename(doc_id)}.txt"
    lines = [
        f"Document Number: {doc_id}",
        f"Original ID: {entry.get('original','')}",
        f"Country/Kind: {entry.get('country','')}/{entry.get('kind','')}",
        f"Resolved: false",
        f"Lookup status: {entry.get('lookup_status','')}",
        f"Fetched: {entry.get('fetched_at','')}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plan(distinct: List[Dict[str, Any]]) -> Dict[str, int]:
    cnt = Counter(_classify(e) for e in distinct)
    return dict(cnt)


def _existing_resolved_ids() -> set:
    if not INDEX_FILE.exists():
        return set()
    try:
        idx = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {e["doc_id"] for e in idx.get("entries", []) if e.get("resolved")}


def _save_index(entries: List[Dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resolved = sum(1 for e in entries if e.get("resolved"))
    payload = {
        "schema_version": "prior_arts_corpus/v2_canonical",
        "generated_at": _utc_now(),
        "source_dataset": str(DEFAULT_DATASET.relative_to(REPO_ROOT)),
        "counts": {
            "total": len(entries),
            "resolved": resolved,
            "unresolved": len(entries) - resolved,
        },
        "by_country": dict(Counter(e["country"] for e in entries)),
        "entries": entries,
    }
    INDEX_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ── 처리 본 루프 ───────────────────────────────────────────────────────────


def process(args: argparse.Namespace) -> None:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("KIPRIS_API_KEY")
    epo_key = os.getenv("EPO_OPS_KEY")
    epo_secret = os.getenv("EPO_OPS_SECRET")

    records = _load_jsonl(args.dataset)
    distinct = _collect_distinct_citations(records)
    print(f"[input] dataset records={len(records)} distinct_citations={len(distinct)}")

    plan = _plan(distinct)
    print(f"[plan] by country bucket: {plan}")
    if args.plan:
        return

    _ensure_out_dir()
    cache = _load_cache(args.cache)
    cache_entries: Dict[str, Any] = cache.setdefault("entries", {})

    # KR client / EPO client / requests session (Google Patents)
    kr_client = KiprisClient(api_key, min_request_interval=args.interval) if api_key else None
    epo_client = None
    if args.include_epo and epo_key and epo_secret:
        epo_client = eu.EpoOpsClient(
            epo_key, epo_secret, min_request_interval=args.epo_interval
        )
    gp_session = requests.Session()
    gp_session.headers.update(eu._GP_HEADERS)

    used = {"kr": 0, "jp": 0, "us": 0, "epo": 0}
    budget = {
        "kr": args.max_kr_calls,
        "jp": args.max_jp_calls,
        "us": args.max_us_calls,
        "epo": args.max_epo_calls,
    }
    counts = Counter()
    quota_hit = False

    for i, entry in enumerate(distinct):
        doc_id = entry["doc_id"]
        bucket = _classify(entry)
        if doc_id in cache_entries and not args.refresh:
            cached = cache_entries[doc_id]
            counts[("cached", cached.get("lookup_status", "unknown"))] += 1
            continue

        # 라우팅
        if bucket == "kr":
            if not args.include_kr:
                counts[("skipped", "kr_disabled")] += 1
                continue
            if used["kr"] >= budget["kr"]:
                counts[("skipped", "kr_budget")] += 1
                continue
            try:
                updated, calls = eu.resolve_kr(kr_client, entry, budget["kr"] - used["kr"])
            except KiprisQuotaExceeded as exc:
                print(f"[fetch] KIPRIS quota exceeded: {exc}")
                quota_hit = True
                break
            except KiprisServiceKeyError as exc:
                print(f"[fetch] KIPRIS auth error: {exc}")
                raise SystemExit(2)
            used["kr"] += calls
        elif bucket == "jp":
            if not args.include_jp:
                counts[("skipped", "jp_disabled")] += 1
                continue
            if used["jp"] >= budget["jp"]:
                counts[("skipped", "jp_budget")] += 1
                continue
            updated, calls = eu.resolve_google_patents(entry, gp_session, args.gp_interval)
            used["jp"] += calls
        elif bucket == "us":
            if not args.include_us:
                counts[("skipped", "us_disabled")] += 1
                continue
            if used["us"] >= budget["us"]:
                counts[("skipped", "us_budget")] += 1
                continue
            updated, calls = eu.resolve_google_patents(entry, gp_session, args.gp_interval)
            used["us"] += calls
        elif bucket == "epo":
            if not args.include_epo:
                counts[("skipped", "epo_disabled")] += 1
                continue
            if not epo_client:
                counts[("skipped", "epo_no_client")] += 1
                continue
            if used["epo"] >= budget["epo"]:
                counts[("skipped", "epo_budget")] += 1
                continue
            try:
                updated, calls = eu.resolve_epo_ops(epo_client, entry)
            except Exception as exc:
                print(f"[fetch] EPO error for {doc_id}: {exc}")
                updated = {**entry, "resolved": False, "lookup_status": "epo_error"}
                calls = 1
            used["epo"] += calls
        else:
            counts[("skipped", "other_country")] += 1
            continue

        updated["fetched_at"] = _utc_now()
        cache_entries[doc_id] = updated
        if updated.get("resolved"):
            _write_fulltext(updated)
            counts[(bucket, "resolved")] += 1
        else:
            _write_unresolved_placeholder(updated)
            counts[(bucket, updated.get("lookup_status", "unresolved"))] += 1

        # 주기적 캐시 flush
        if (i + 1) % 50 == 0:
            _save_cache(args.cache, cache)
            print(
                f"  [{i + 1}/{len(distinct)}] used={used} | "
                + ", ".join(f"{k}={v}" for k, v in counts.most_common(8))
            )

    _save_cache(args.cache, cache)

    # 인덱스 구성
    index_entries: List[Dict[str, Any]] = []
    for e in distinct:
        cached = cache_entries.get(e["doc_id"])
        if cached:
            index_entries.append(
                {
                    "doc_id": cached["doc_id"],
                    "original": cached.get("original", e.get("original", "")),
                    "country": cached.get("country", e.get("country", "")),
                    "kind": cached.get("kind", e.get("kind", "")),
                    "resolved": bool(cached.get("resolved")),
                    "lookup_status": cached.get("lookup_status", ""),
                    "source": cached.get("source", ""),
                    "fetched_at": cached.get("fetched_at", ""),
                }
            )
        else:
            index_entries.append({**e, "lookup_status": "unprocessed"})
    _save_index(index_entries)

    print(f"\n[done] used={used} quota_hit={quota_hit}")
    print(f"[summary] counts={dict(counts.most_common())}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="B1 인용 외부특허 본문 수집 (KR+JP+US+WO/CN/EP)"
    )
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--cache", type=Path, default=CACHE_FILE)
    ap.add_argument("--plan", action="store_true", help="국가별 예산 추정만 출력")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument(
        "--include-kr", action="store_true", default=True, help="KR 인용 (기본 ON)"
    )
    ap.add_argument("--no-kr", dest="include_kr", action="store_false")
    ap.add_argument("--include-jp", action="store_true", default=False)
    ap.add_argument("--include-us", action="store_true", default=False)
    ap.add_argument("--include-epo", action="store_true", default=False)
    ap.add_argument(
        "--kr-only",
        action="store_true",
        help="KR만 처리. JP/US/EPO 비활성화 (smoke test 등)",
    )
    ap.add_argument("--max-kr-calls", type=int, default=5000)
    ap.add_argument("--max-jp-calls", type=int, default=600)
    ap.add_argument("--max-us-calls", type=int, default=500)
    ap.add_argument("--max-epo-calls", type=int, default=300)
    ap.add_argument(
        "--interval", type=float, default=0.4, help="KIPRIS 호출 간격 초"
    )
    ap.add_argument(
        "--gp-interval", type=float, default=1.5, help="Google Patents 호출 간격 초"
    )
    ap.add_argument("--epo-interval", type=float, default=1.0)
    args = ap.parse_args()

    if args.kr_only:
        args.include_jp = False
        args.include_us = False
        args.include_epo = False

    process(args)


if __name__ == "__main__":
    main()
