"""B3 + B5 타겟 보강: 전체 청구항 + family + legal status.

근거: `docs/dataset_full_collection_runbook.md` Phase A.

호출 한도 운영
==============
- KIPRIS Plus `getBibliographyDetailInfoSearch` 1 call/특허 (이미 expand_dataset_via_api 가 1회는 호출했으나, 캐시되어 있지 않으므로 재호출)
- 응답에서 `claimInfoArray`(B3), `legalStatusInfoArray`(B5), `familyInfoArray`(B5) 를 추출
- EPO OPS INPADOC family 는 KIPRIS family 가 비어 있을 때만 폴백 (`--epo-fallback`)

기존 JSONL 의 모든 필드는 보존하고, `target_patent` 에 다음 3 필드만 추가:
- `claims_full: list[{claim_no, depends_on, text}]`
- `family: {publication_numbers: [...], source}`
- `legal_status: {events: [{date, code}], current}`

사용
====
    .venv/bin/python scripts/enrich_targets_b3_b5.py --dry-run --limit 5
    .venv/bin/python scripts/enrich_targets_b3_b5.py --profile paid --max-api-calls 1100
    .venv/bin/python scripts/enrich_targets_b3_b5.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import xmltodict
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.kipris import (  # noqa: E402
    KiprisClient,
    KiprisQuotaExceeded,
    KiprisServiceKeyError,
    OP_BIBLIO_DETAIL,
)

DEFAULT_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
DEFAULT_CACHE = REPO_ROOT / "data/processed/enrich_targets_b3_b5_cache.json"
PROFILE_PRESETS: Dict[str, Dict[str, float | int]] = {
    "free": {"interval": 0.6, "max_api_calls": 150},
    "paid": {"interval": 0.4, "max_api_calls": 1200},
}
DEFAULT_PROFILE = "free"
EPO_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_FAMILY_URL = "https://ops.epo.org/3.2/rest-services/family/publication/docdb"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _s(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _to_list(v: Any) -> List[Dict[str, Any]]:
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [i for i in v if isinstance(i, dict)]
    return []


def _load_cache(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"entries": {}}
    return {"entries": {}}


def _save_cache(path: Path, cache: Dict[str, Any]) -> None:
    cache["generated_at"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _save_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


# ── biblio detail 파싱 ──────────────────────────────────────────────────────


def _biblio_item(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    item = body.get("item")
    if isinstance(item, list):
        return item[0] if item else None
    return item if isinstance(item, dict) else None


_CLAIM_NO_RX = re.compile(r"^\s*(\d+)\s*[.)]\s*")
_DEPEND_RX = re.compile(r"제\s*(\d+)\s*항")


def _parse_claim_no(text: str) -> int:
    m = _CLAIM_NO_RX.match(text or "")
    return int(m.group(1)) if m else 0


def _parse_depends_on(text: str) -> List[int]:
    return [int(x) for x in _DEPEND_RX.findall(text or "")]


def _extract_claims_full(bib_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    arr = bib_item.get("claimInfoArray") or {}
    claims = _to_list(arr.get("claimInfo"))
    out: List[Dict[str, Any]] = []
    for c in claims:
        text = _s(c.get("claim") or c.get("claimText") or "")
        if not text:
            continue
        no = _parse_claim_no(text)
        depends = _parse_depends_on(text)
        out.append({"claim_no": no, "depends_on": depends, "text": text})
    return out


def _extract_legal_status(bib_item: Dict[str, Any]) -> Dict[str, Any]:
    arr = (
        bib_item.get("legalStatusInfoArray")
        or bib_item.get("legalStatusArray")
        or {}
    )
    events_raw = _to_list(arr.get("legalStatusInfo") or arr.get("legalStatus"))
    events = []
    for ev in events_raw:
        date = _s(
            ev.get("receiptDate")
            or ev.get("documentDate")
            or ev.get("date")
            or ev.get("eventDate")
        )
        code = _s(
            ev.get("documentName")
            or ev.get("commonCodeName")
            or ev.get("name")
            or ev.get("eventCode")
        )
        receipt_no = _s(ev.get("receiptNumber") or ev.get("documentNumber"))
        if date or code:
            events.append({"date": date, "code": code, "receipt_number": receipt_no})

    summary = bib_item.get("biblioSummaryInfoArray") or {}
    summary_info = summary.get("biblioSummaryInfo")
    if isinstance(summary_info, list):
        summary_info = summary_info[0] if summary_info else {}
    current = _s((summary_info or {}).get("finalDisposal") or (summary_info or {}).get("registerStatus"))
    return {"events": events, "current": current}


def _extract_family_kipris(bib_item: Dict[str, Any]) -> Dict[str, Any]:
    pub_nos: List[str] = []
    # 1) familyInfoArray.familyInfo (해외 패밀리)
    fam_arr = bib_item.get("familyInfoArray") or {}
    for m in _to_list(fam_arr.get("familyInfo")):
        n = _s(
            m.get("familyApplicationNumber")
            or m.get("publicationNumber")
            or m.get("documentNumber")
            or m.get("applicationNumber")
        )
        if n:
            pub_nos.append(n)
    # 2) internationalInfoArray.internationalInfo (국제출원/PCT)
    intl = bib_item.get("internationalInfoArray") or {}
    for m in _to_list(intl.get("internationalInfo")):
        n = _s(
            m.get("internationalApplicationNumber")
            or m.get("internationalPublicationNumber")
            or m.get("applicationNumber")
            or m.get("publicationNumber")
        )
        if n:
            pub_nos.append(n)
    # 3) priorityInfoArray.priorityInfo (우선권 주장 기반 패밀리 단서)
    pri = bib_item.get("priorityInfoArray") or {}
    for m in _to_list(pri.get("priorityInfo")):
        n = _s(m.get("priorityApplicationNumber") or m.get("applicationNumber"))
        if n:
            pub_nos.append(n)
    # dedupe
    pub_nos = list(dict.fromkeys(pub_nos))
    return {"publication_numbers": pub_nos, "source": "kipris_plus_api"}


# ── EPO OPS 폴백 ────────────────────────────────────────────────────────────


def _epo_token(session: requests.Session, key: str, secret: str) -> Optional[str]:
    try:
        resp = session.post(
            EPO_AUTH_URL,
            data={"grant_type": "client_credentials"},
            auth=(key, secret),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        print(f"[epo] auth failed: {exc}")
        return None


def _epo_family(session: requests.Session, token: str, app_no: str) -> List[str]:
    # KR 출원번호를 EPO docdb 형식으로 변환: KR.<applno>.A or .B
    # 간단화: KR + applno 로 시도. 실패 시 빈 리스트.
    epo_id = f"KR.{app_no}.A"
    try:
        resp = session.get(
            f"{EPO_FAMILY_URL}/{epo_id}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/xml"},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        parsed = xmltodict.parse(resp.text)
        # ops:world-patent-data -> ops:patent-family -> ops:family-member
        body = (
            parsed.get("ops:world-patent-data") or parsed.get("world-patent-data") or {}
        )
        family = (
            body.get("ops:patent-family") or body.get("patent-family") or {}
        )
        members = (
            family.get("ops:family-member") or family.get("family-member") or []
        )
        if isinstance(members, dict):
            members = [members]
        out: List[str] = []
        for mem in members:
            pubref = (
                mem.get("publication-reference") or mem.get("ops:publication-reference") or {}
            )
            doc_ids = pubref.get("document-id") or pubref.get("ops:document-id") or []
            if isinstance(doc_ids, dict):
                doc_ids = [doc_ids]
            for did in doc_ids:
                fmt = (did.get("@document-id-type") or "").lower()
                if "docdb" in fmt or fmt == "epodoc":
                    parts = []
                    for k in ("country", "doc-number", "kind"):
                        v = did.get(k) or did.get(f"ops:{k}")
                        if isinstance(v, dict):
                            v = v.get("#text") or v.get("$")
                        if v:
                            parts.append(_s(v))
                    if parts:
                        out.append("".join(parts))
                        break
        return out
    except Exception as exc:
        print(f"[epo] family error for {app_no}: {exc}")
        return []


# ── 메인 흐름 ────────────────────────────────────────────────────────────────


def fetch_one(client: KiprisClient, app_no: str) -> Optional[Dict[str, Any]]:
    try:
        header, body = client.call(OP_BIBLIO_DETAIL, {"applicationNumber": app_no})
    except KiprisQuotaExceeded:
        raise
    except KiprisServiceKeyError:
        raise
    except Exception as exc:
        return {"error": str(exc)}

    item = _biblio_item(body)
    if not item:
        return None

    return {
        "claims_full": _extract_claims_full(item),
        "legal_status": _extract_legal_status(item),
        "family": _extract_family_kipris(item),
    }


def fetch_phase(args: argparse.Namespace) -> None:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("KIPRIS_API_KEY")
    if not api_key:
        raise SystemExit("KIPRIS_API_KEY missing in .env")

    epo_key = os.getenv("EPO_OPS_KEY")
    epo_secret = os.getenv("EPO_OPS_SECRET")

    records = _load_jsonl(args.dataset)
    if args.limit:
        records = records[: args.limit]
    cache = _load_cache(args.cache)
    entries: Dict[str, Any] = cache.setdefault("entries", {})

    client = KiprisClient(api_key, min_request_interval=args.interval)
    session = requests.Session()
    session.headers["User-Agent"] = "paper-data-runbook/0.1"
    epo_token: Optional[str] = None

    used = 0
    used_epo = 0
    quota_hit = False
    for i, r in enumerate(records):
        app_no = _s((r.get("target_patent") or {}).get("application_number"))
        if not app_no:
            continue
        if app_no in entries and not args.refresh:
            tag = "cached"
        else:
            if used >= args.max_api_calls:
                print(f"[fetch] budget reached ({used}/{args.max_api_calls})")
                break
            try:
                data = fetch_one(client, app_no)
            except KiprisQuotaExceeded as exc:
                quota_hit = True
                print(f"[fetch] quota exceeded: {exc}")
                break
            except KiprisServiceKeyError as exc:
                print(f"[fetch] auth error: {exc}")
                raise SystemExit(2)
            used += 1
            if not data or "error" in (data or {}):
                entries[app_no] = {"status": "error", "detail": (data or {}).get("error", "no_item")}
                tag = "error"
            else:
                # EPO family fallback when KIPRIS family empty
                fam = data["family"]
                if (not fam["publication_numbers"]) and args.epo_fallback and epo_key and epo_secret:
                    if not epo_token:
                        epo_token = _epo_token(session, epo_key, epo_secret)
                    if epo_token:
                        epo_pubs = _epo_family(session, epo_token, app_no)
                        if epo_pubs:
                            data["family"] = {"publication_numbers": epo_pubs, "source": "epo_ops_inpadoc"}
                        used_epo += 1
                        time.sleep(args.epo_interval)
                data["status"] = "resolved"
                data["fetched_at"] = _utc_now()
                entries[app_no] = data
                tag = "resolved"
            if (i + 1) % 25 == 0:
                _save_cache(args.cache, cache)
        if (i + 1) % 50 == 0 or i == len(records) - 1:
            print(f"  [{i + 1}/{len(records)}] {app_no} {tag} used={used} used_epo={used_epo}")

    _save_cache(args.cache, cache)
    print(f"[fetch] done. used_kipris={used} used_epo={used_epo} quota_hit={quota_hit} cache={args.cache}")


def apply_phase(args: argparse.Namespace) -> None:
    records = _load_jsonl(args.dataset)
    cache = _load_cache(args.cache)
    entries: Dict[str, Any] = cache.get("entries") or {}
    if not entries:
        raise SystemExit("cache empty; run fetch phase first")

    counts = {
        "total": 0,
        "patched_claims": 0,
        "patched_family": 0,
        "patched_legal": 0,
        "no_cache": 0,
        "error": 0,
    }
    for r in records:
        counts["total"] += 1
        t = r.setdefault("target_patent", {})
        app_no = _s(t.get("application_number"))
        ent = entries.get(app_no)
        if not ent:
            counts["no_cache"] += 1
            continue
        if ent.get("status") == "error":
            counts["error"] += 1
            continue
        if ent.get("claims_full"):
            t["claims_full"] = ent["claims_full"]
            counts["patched_claims"] += 1
        if ent.get("family"):
            t["family"] = ent["family"]
            if ent["family"].get("publication_numbers"):
                counts["patched_family"] += 1
        if ent.get("legal_status"):
            t["legal_status"] = ent["legal_status"]
            counts["patched_legal"] += 1

    if args.dry_run:
        print(f"[apply] dry-run: {counts}")
        return

    backup = args.dataset.with_suffix(args.dataset.suffix + f".bak.{int(time.time())}")
    args.dataset.replace(backup)
    try:
        _save_jsonl(args.dataset, records)
    except Exception:
        # restore on failure
        backup.replace(args.dataset)
        raise
    print(f"[apply] wrote {args.dataset} ({counts}); backup={backup.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="B3+B5 타겟 보강 (전체 청구항 + family + legal status)")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--profile", choices=sorted(PROFILE_PRESETS.keys()), default=DEFAULT_PROFILE)
    ap.add_argument("--interval", type=float, default=None)
    ap.add_argument("--max-api-calls", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0, help="처리할 레코드 상한 (smoke test 용)")
    ap.add_argument("--refresh", action="store_true", help="캐시된 entry 도 다시 조회")
    ap.add_argument("--epo-fallback", action="store_true", help="KIPRIS family 비어 있을 때 EPO OPS 폴백")
    ap.add_argument("--epo-interval", type=float, default=1.5)
    ap.add_argument("--apply", action="store_true", help="캐시를 dataset 에 적용")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    preset = PROFILE_PRESETS[args.profile]
    if args.interval is None:
        args.interval = float(preset["interval"])
    if args.max_api_calls is None:
        args.max_api_calls = int(preset["max_api_calls"])

    if args.apply:
        apply_phase(args)
        return
    if args.dry_run:
        # dry-run 만 단독은 cache 정보 출력
        cache = _load_cache(args.cache)
        entries = cache.get("entries") or {}
        print(f"[dry-run] cache entries: {len(entries)}, dataset: {args.dataset}")
        return

    fetch_phase(args)


if __name__ == "__main__":
    main()
