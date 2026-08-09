"""API 출처 레코드의 `meta.admin_documents` / `meta.evidence_document_url` 보강.

⚠ **경고 (2026-07-30 실측) — 이 스크립트의 검색 경로는 대부분 0건을 반환한다.**
   여기서 쓰는 ``advancedSearchInfo``(검색)는 이 저장소의 반도체 거절특허 1,000건 중
   **539건에 대해 matched_count=0** 을 돌려준다. 그런데 **문서는 존재한다** — 같은 출원번호를
   ``pdfInfoV2``(출원번호 직접 조회)로 부르면 filePath 가 정상 반환된다(538/539 확보).
   2026-05 실행의 0건이 "서류 없음"으로 잘못 해석되어 하류에서 거절근거 무라벨 600건이라는
   자원 결손으로 굳어졌다. **새 수집은 ``scripts/backfill_pdfinfo_v2.py`` 를 쓸 것.**
   이 스크립트는 ``--apply``(캐시 → JSONL 반영) 경로 때문에 유지한다.

대상:
- ``meta.source == "kipris_plus_api"`` 이면서 ``meta.admin_documents`` 가 비어 있는 레코드.

방식:
- 각 레코드의 ``application_number`` 로 거절결정서 REST(``IntermediateDocumentREService/advancedSearchInfo``)
  를 1회 호출.
- 응답의 ``filePath`` 들을 ``admin_documents[*].url`` 로, 첫 번째 PDF를
  ``evidence_document_url`` 로 채운다.
- ``evidence_document_type`` 은 ``"거절결정서"`` (REST는 거절결정서 PDF만 노출).

호출 예산:
- 레코드 1건당 1 call. 89건이면 ≈89 calls.
- ``--max-api-calls`` 로 일일 한도 안에서 부분 실행 가능.
- 처리한 application_number는 ``--cache`` 파일에 저장해 재실행 시 skip.

원자적 쓰기:
- 캐시 파일은 한 건 처리할 때마다 갱신(중단되어도 진행분 보존).
- JSONL은 캐시 적용 단계에서 일괄 재작성(``apply`` 모드).

사용:
    # 1) API 호출 → 캐시 파일 채우기
    .venv/bin/python scripts/backfill_admin_docs.py --max-api-calls 95

    # 2) 캐시를 JSONL에 적용
    .venv/bin/python scripts/backfill_admin_docs.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.kipris import KiprisQuotaExceeded, KiprisServiceKeyError  # noqa: E402
from kipris_dataset.dataset_paths import CANONICAL_SEMICONDUCTOR_DATASET  # noqa: E402
from kipris_dataset.rejection_decision import (  # noqa: E402
    BASE_URL as REJ_BASE_URL,
    RejectionDecisionClient,
)

DEFAULT_DATASET = CANONICAL_SEMICONDUCTOR_DATASET
DEFAULT_CACHE = REPO_ROOT / "data/processed/admin_docs_backfill_cache.json"
DEFAULT_INTERVAL = 0.6
DEFAULT_MAX_CALLS = 100


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"dataset not found: {path}")
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _atomic_write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _load_cache(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"generated_at": _utc_now(), "entries": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_cache(path: Path, cache: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache["generated_at"] = _utc_now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _eligible_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in records:
        meta = r.get("meta") or {}
        if meta.get("source") != "kipris_plus_api":
            continue
        if meta.get("admin_documents"):
            continue
        if not (r.get("target_patent") or {}).get("application_number"):
            continue
        out.append(r)
    return out


def fetch_admin_docs(
    client: RejectionDecisionClient,
    app_no: str,
) -> Dict[str, Any]:
    """REST 1회 호출 결과를 캐시 entry 형태로 반환."""
    items = client.search(application_number=app_no, docs_count=10)
    docs: List[Dict[str, Any]] = []
    for it in items or []:
        url = _str(it.get("filePath") or it.get("path") or "")
        if not url:
            continue
        docs.append(
            {
                "type": "거절결정서",
                "url": url,
                "send_number": _str(it.get("sendNumber")),
                "send_date": _str(it.get("sendDate")),
            }
        )
    return {
        "application_number": app_no,
        "fetched_at": _utc_now(),
        "matched_count": len(docs),
        "admin_documents": docs,
    }


def fetch_phase(args: argparse.Namespace) -> None:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "env")
    api_key = (
        os.getenv("KIPRIS_REJECTION_DECISION_API_KEY", "").strip()
        or os.getenv("KIPRIS_API_KEY", "").strip()
    )
    if not api_key:
        raise SystemExit("KIPRIS_REJECTION_DECISION_API_KEY or KIPRIS_API_KEY missing")
    base = os.getenv("KIPRIS_REJECTION_DECISION_BASE_URL", REJ_BASE_URL).strip() or REJ_BASE_URL

    client = RejectionDecisionClient(api_key, base_url=base, min_request_interval=args.interval)

    records = _load_jsonl(args.dataset)
    cache = _load_cache(args.cache)
    cache_entries: Dict[str, Any] = cache.get("entries") or {}

    eligible = _eligible_records(records)
    todo = [r for r in eligible if (r["target_patent"]["application_number"]) not in cache_entries]
    print(f"[fetch] eligible={len(eligible)} cached={len(cache_entries)} todo={len(todo)}")
    if not todo:
        print("[fetch] nothing to do")
        return

    used = 0
    quota_hit = False
    try:
        for i, r in enumerate(todo):
            if used >= args.max_api_calls:
                print(f"[fetch] budget reached ({used}/{args.max_api_calls})")
                break
            app_no = _str(r["target_patent"]["application_number"])
            try:
                entry = fetch_admin_docs(client, app_no)
            except KiprisQuotaExceeded as exc:
                quota_hit = True
                print(f"[fetch] quota exceeded: {exc}")
                break
            except KiprisServiceKeyError as exc:
                print(f"[fetch] auth error: {exc}")
                raise SystemExit(2)
            used += 1
            cache_entries[app_no] = entry
            cache["entries"] = cache_entries
            _save_cache(args.cache, cache)
            print(
                f"  [{i + 1}/{len(todo)}] {app_no} matched={entry['matched_count']} "
                f"used={used}/{args.max_api_calls}"
            )
    except KeyboardInterrupt:
        print("\n[fetch] interrupted; cache preserved")

    print(f"[fetch] done. used={used}, quota_hit={quota_hit}, cache={args.cache}")


def apply_phase(args: argparse.Namespace) -> None:
    records = _load_jsonl(args.dataset)
    cache = _load_cache(args.cache)
    entries: Dict[str, Any] = cache.get("entries") or {}
    if not entries:
        raise SystemExit("cache is empty; run fetch phase first")

    updated = 0
    skipped_already = 0
    no_match = 0
    for r in records:
        meta = r.get("meta") or {}
        if meta.get("source") != "kipris_plus_api":
            continue
        if meta.get("admin_documents"):
            skipped_already += 1
            continue
        app_no = _str((r.get("target_patent") or {}).get("application_number"))
        if not app_no or app_no not in entries:
            continue
        entry = entries[app_no]
        docs = entry.get("admin_documents") or []
        if not docs:
            # 캐시는 있지만 매칭 0건 — 빈 리스트 대신 이를 명시
            meta["admin_documents"] = []
            meta["evidence_document_url"] = ""
            meta["evidence_document_type"] = ""
            meta.setdefault("notes", "")
            if "no admin docs returned" not in (meta.get("notes") or ""):
                meta["notes"] = (
                    (meta.get("notes") or "")
                    + " | 거절결정서 REST 0 matches"
                ).strip(" |")
            no_match += 1
            r["meta"] = meta
            continue
        meta["admin_documents"] = [
            {"type": d["type"], "url": d["url"]} for d in docs if d.get("url")
        ]
        meta["evidence_document_url"] = docs[0].get("url", "")
        meta["evidence_document_type"] = docs[0].get("type", "거절결정서")
        meta.setdefault("notes", "")
        if "ground_truth_evidence" in (meta.get("notes") or ""):
            # 기존 notes 유지, 행정문서 보강 사실 추가 표기
            pass
        r["meta"] = meta
        updated += 1

    _atomic_write_jsonl(args.dataset, records)
    print(
        f"[apply] updated={updated}  no_match={no_match}  already_filled_skipped={skipped_already}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="API 출처 레코드의 admin_documents 백필")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    ap.add_argument("--max-api-calls", type=int, default=DEFAULT_MAX_CALLS)
    ap.add_argument("--apply", action="store_true",
                    help="API 호출 없이 캐시를 JSONL에 적용")
    args = ap.parse_args()

    if args.apply:
        apply_phase(args)
    else:
        fetch_phase(args)


if __name__ == "__main__":
    main()
