"""KIPRIS Plus API / EPO OPS / Google Patents로 unresolved 인용문헌을 보강한다.

## 대상
``data/processed/fulltext/etching_prior_arts/_index.json`` 의 ``resolved=false`` 항목.
  - KR/grant  : KIPRIS getAdvancedSearch registerNumber → getBibliographyDetailInfoSearch
  - KR/pub    : KIPRIS getAdvancedSearch openNumber → getBibliographyDetailInfoSearch
  - JP        : KIPRIS Foreign best-effort (커버리지 제한적)
  - US        : Google Patents 페이지 스크래핑 (search.patentsview.org NXDOMAIN 우회)
                grant  → https://patents.google.com/patent/US{num}/en
                pub    → https://patents.google.com/patent/US{pub_num}/en
    - JP        : Google Patents 페이지 스크래핑 (--include-jp 플래그)
                JP-2007-009988 → JP2007009988, WO2019088204 A1 → WO2019088204A1
    - WO/CN/EP  : EPO OPS 서지/초록 조회 (--include-epo 플래그)

## 호출 예산
  - KIPRIS: ``--interval 0.5`` → 2 req/sec (75/sec 한도 대비 충분)
  - Google Patents (US/JP/WO/CN): ``--us-interval 1.5`` → 0.67 req/sec (scraping 예의 준수)
  - ``--max-api-calls 200`` 기본 (KR+US 합산)

## 네트워크 환경
  - 인터넷 미접속 시 PatentsView 호출은 ``network_unreachable`` 로 graceful skip.
  - 스크립트를 인터넷 접속 환경에서 재실행하면 캐시되지 않은 항목만 다시 시도.

## 후속 단계 (스크립트 완료 후 실행)
    .venv/bin/python scripts/build_etching_corpus.py --include-unresolved --fresh
    .venv/bin/python scripts/build_manifest.py

사용:
    .venv/bin/python scripts/enrich_unresolved.py --dry-run
    .venv/bin/python scripts/enrich_unresolved.py --max-api-calls 200
    .venv/bin/python scripts/enrich_unresolved.py --include-us --max-api-calls 300
    .venv/bin/python scripts/enrich_unresolved.py --include-epo --max-api-calls 100
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
from typing import Any

import requests
import xmltodict
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.citation_norm import parse as parse_citation  # noqa: E402
from kipris_dataset.kipris import (  # noqa: E402
    KiprisClient,
    KiprisQuotaExceeded,
    KiprisServiceKeyError,
    OP_ADVANCED_SEARCH,
    OP_BIBLIO_DETAIL,
)

INDEX_FILE = REPO_ROOT / "data/processed/fulltext/etching_prior_arts/_index.json"
CACHE_FILE = REPO_ROOT / "data/processed/enrich_unresolved_cache.json"
FULLTEXT_DIR = REPO_ROOT / "data/processed/fulltext/etching_prior_arts"
_EPO_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_EPO_BIBLIO_URL = "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc"


# ── utils ─────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _s(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _to_list(v: Any) -> list[dict[str, Any]]:
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [i for i in v if isinstance(i, dict)]
    return []


def _textify_xml(v: Any) -> str:
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        parts = [_textify_xml(i) for i in v]
        return " ".join(p for p in parts if p).strip()
    if isinstance(v, dict):
        parts = []
        for key in ("#text", "p", "text"):
            if key in v:
                part = _textify_xml(v.get(key))
                if part:
                    parts.append(part)
        return " ".join(parts).strip()
    return ""


def _load_cache() -> dict[str, Any]:
    if CACHE_FILE.is_file():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"generated_at": _now(), "entries": {}}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache["generated_at"] = _now()
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CACHE_FILE)


def _load_index() -> list[dict[str, Any]]:
    return json.loads(INDEX_FILE.read_text(encoding="utf-8")).get("entries", [])


DATASET_FILE = REPO_ROOT / "data/processed/etching_reject_web_poc_dataset.jsonl"


def _supplement_from_dataset(
    entries: list[dict[str, Any]],
    countries: tuple[str, ...],
) -> list[dict[str, Any]]:
    """JSONL 데이터셋에서 특정 국가 인용을 읽어 entries에 없으면 추가한다."""
    existing_ids: set[str] = {e["doc_id"] for e in entries if e.get("doc_id")}
    extras: list[dict[str, Any]] = []
    seen: set[str] = set()

    if not DATASET_FILE.exists():
        return entries

    with DATASET_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            for raw_id in rec.get("ground_truth_examiner") or []:
                cit = parse_citation(raw_id)
                if cit.country not in countries:
                    continue
                doc_id = cit.normalized_id
                if not doc_id or doc_id in existing_ids or doc_id in seen:
                    continue
                seen.add(doc_id)
                extras.append({
                    "doc_id": doc_id,
                    "original": raw_id,
                    "country": cit.country,
                    "kind": cit.kind,
                    "resolved": False,
                })

    return entries + extras


def _save_index(entries: list[dict[str, Any]]) -> None:
    idx = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    idx["entries"] = entries
    idx["generated_at"] = _now()
    tmp = INDEX_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(INDEX_FILE)


class EpoOpsAuthError(RuntimeError):
    """Raised when EPO OPS credentials are rejected."""


class EpoOpsClient:
    def __init__(
        self,
        key: str,
        secret: str,
        *,
        session: requests.Session | None = None,
        min_request_interval: float = 1.0,
        timeout: int = 20,
    ) -> None:
        self.key = key.strip()
        self.secret = secret.strip()
        self.session = session or requests.Session()
        self.min_request_interval = max(0.0, float(min_request_interval))
        self.timeout = timeout
        self._token = ""
        self._token_expires_at = 0.0
        self._last_request_at = 0.0

    def _wait_turn(self) -> None:
        if self.min_request_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

    def _issue_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self._wait_turn()
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        self._last_request_at = time.monotonic()
        return response

    def _access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token

        response = self._issue_request(
            "POST",
            _EPO_AUTH_URL,
            auth=(self.key, self.secret),
            data={"grant_type": "client_credentials"},
        )
        if response.status_code in {400, 401, 403}:
            raise EpoOpsAuthError(f"EPO OPS auth failed ({response.status_code})")
        response.raise_for_status()
        payload = response.json()
        self._token = _s(payload.get("access_token"))
        expires_in = int(_s(payload.get("expires_in") or "0") or 0)
        self._token_expires_at = now + max(0, expires_in)
        if not self._token:
            raise EpoOpsAuthError("EPO OPS auth returned no access token")
        return self._token

    def fetch_biblio(self, epodoc_id: str) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": "application/xml",
        }
        response = self._issue_request("GET", f"{_EPO_BIBLIO_URL}/{epodoc_id}/biblio", headers=headers)
        if response.status_code == 404:
            return {"error": "not_found"}
        if response.status_code in {400, 401, 403}:
            raise EpoOpsAuthError(f"EPO OPS biblio request failed ({response.status_code})")
        if response.status_code == 429:
            return {"error": "rate_limited"}
        response.raise_for_status()
        try:
            payload = xmltodict.parse(response.text)
        except Exception:
            return {"error": "invalid_xml"}

        doc = ((payload.get("ops:world-patent-data") or {}).get("exchange-documents") or {}).get("exchange-document")
        if not isinstance(doc, dict):
            return {"error": "biblio_empty"}
        return {"doc": doc}


# ── KIPRIS API helpers ─────────────────────────────────────────────────────


def _bib_field(bib: dict, *keys: str) -> str:
    """Dig nested bib fields; return first non-empty string."""
    for key in keys:
        val = bib.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            # try common sub-keys
            for sub in ("astrtCont", "inventionTitle", "claim", "claimText", "ipcNumber"):
                sub_val = _s(val.get(sub))
                if sub_val:
                    return sub_val
    return ""


def _extract_abstract(bib: dict) -> str:
    arr = bib.get("abstractInfoArray") or {}
    info = arr.get("abstractInfo")
    if isinstance(info, list):
        info = info[0] if info else {}
    if isinstance(info, dict):
        return _s(info.get("astrtCont"))
    # top-level fallback
    return _s(bib.get("astrtCont"))


def _extract_claim1(bib: dict) -> str:
    arr = bib.get("claimInfoArray") or {}
    claims = _to_list(arr.get("claimInfo"))
    for c in claims:
        txt = _s(c.get("claim") or c.get("claimText") or "")
        if txt.startswith("1.") or txt.startswith("1 "):
            return txt[:3000]
    return _s(claims[0].get("claim") if claims else "")[:3000]


def _extract_ipc(bib: dict) -> str:
    arr = bib.get("ipcInfoArray") or {}
    items = _to_list(arr.get("ipcInfo"))
    return "|".join(_s(i.get("ipcNumber")) for i in items if i.get("ipcNumber"))


def _extract_title(bib: dict) -> str:
    arr = bib.get("biblioSummaryInfoArray") or {}
    info = arr.get("biblioSummaryInfo")
    if isinstance(info, list):
        info = info[0] if info else {}
    if isinstance(info, dict):
        t = _s(info.get("inventionTitle"))
        if t:
            return t
    return _s(bib.get("inventionTitle"))


def _biblio(client: KiprisClient, app_no: str) -> dict | None:
    try:
        resp = client.get(OP_BIBLIO_DETAIL, {"applicationNumber": app_no})
    except (KiprisQuotaExceeded, KiprisServiceKeyError):
        raise
    except Exception:
        return None
    item = (resp.get("response", {}).get("body") or {}).get("item")
    if isinstance(item, list):
        return item[0] if item else None
    return item if isinstance(item, dict) else None


def _search_one(client: KiprisClient, params: dict[str, Any]) -> dict | None:
    try:
        resp = client.get(OP_ADVANCED_SEARCH, {**params, "pageNo": 1, "numOfRows": 3})
    except (KiprisQuotaExceeded, KiprisServiceKeyError):
        raise
    except Exception:
        return None
    if resp is None:
        return None
    body = (resp.get("response") or {}).get("body") or {}
    items_node = body.get("items") or {}
    if isinstance(items_node, str):
        return None
    items = _to_list(items_node.get("item"))
    return items[0] if items else None


def _kr_register_candidates(serial: str) -> list[str]:
    """KR 등록번호 → KIPRIS Plus 파라미터 형식 후보 (13자리 이하 가드 포함)."""
    s = serial.lstrip("0")
    cands = []
    if not s.startswith("10"):
        cands.append(("10" + s.zfill(7))[:13])  # 10-prefixed, zero-pad to 9 total
    cands.append(s)
    if len(s) < 7:
        cands.append(s.zfill(7))
    seen: set[str] = set()
    out = []
    for c in cands:
        if len(c) <= 13 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _prefer_lang_text(v: Any, preferred_langs: tuple[str, ...] = ("en", "ko")) -> str:
    if isinstance(v, str):
        return v.strip()
    nodes: list[Any]
    if isinstance(v, list):
        nodes = v
    else:
        nodes = [v]

    for lang in preferred_langs:
        for node in nodes:
            if isinstance(node, dict) and _s(node.get("@lang")).lower() == lang:
                text = _textify_xml(node)
                if text:
                    return text
    for node in nodes:
        text = _textify_xml(node)
        if text:
            return text
    return ""


def _extract_epo_pub_date(doc: dict[str, Any]) -> str:
    refs = _to_list(((doc.get("bibliographic-data") or {}).get("publication-reference") or {}).get("document-id"))
    for doc_type in ("epodoc", "docdb"):
        for ref in refs:
            if _s(ref.get("@document-id-type")) == doc_type:
                date = _s(ref.get("date"))
                if date:
                    return date
    return ""


def _extract_epo_ipc(doc: dict[str, Any]) -> str:
    classes = _to_list(((doc.get("bibliographic-data") or {}).get("classifications-ipcr") or {}).get("classification-ipcr"))
    seen: set[str] = set()
    out: list[str] = []
    for cls in classes:
        code = re.sub(r"\s+", " ", _textify_xml(cls.get("text") or cls)).strip()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return "|".join(out)


def _extract_epo_metadata(doc: dict[str, Any]) -> dict[str, str]:
    bib = doc.get("bibliographic-data") or {}
    return {
        "title": _prefer_lang_text(bib.get("invention-title")),
        "abstract": _prefer_lang_text(doc.get("abstract")),
        "ipc": _extract_epo_ipc(doc),
        "pub_date": _extract_epo_pub_date(doc),
    }


def _epo_epodoc_id(entry: dict[str, Any]) -> str:
    citation = parse_citation(entry.get("original", ""))
    if citation.country and citation.serial:
        return f"{citation.country}{citation.serial}"
    return re.sub(r"[^A-Za-z0-9]", "", _s(entry.get("original", "")).upper())


# ── per-country resolvers ─────────────────────────────────────────────────


def resolve_kr(client: KiprisClient, entry: dict, budget: int) -> tuple[dict, int]:
    """KR grant/publication → KIPRIS biblio. Returns (updated_entry, calls_used)."""
    citation = parse_citation(entry["original"])
    serial = citation.serial
    kind = citation.kind
    calls = 0
    app_no = ""

    if kind == "grant":
        for cand in _kr_register_candidates(serial):
            if budget - calls < 1:
                break
            item = _search_one(client, {"registerNumber": cand})
            calls += 1
            if item:
                app_no = _s(item.get("applicationNumber"))
                break
    elif kind == "publication":
        open_no = serial if len(serial) == 13 else serial.zfill(13)
        item = _search_one(client, {"openNumber": open_no})
        calls += 1
        if item:
            app_no = _s(item.get("applicationNumber"))

    if not app_no or budget - calls < 1:
        return {**entry, "resolved": False, "lookup_status": "not_found"}, calls

    bib = _biblio(client, app_no)
    calls += 1
    if not bib:
        return {**entry, "resolved": False, "lookup_status": "biblio_empty"}, calls

    title = _extract_title(bib)
    abstract = _extract_abstract(bib)
    claim1 = _extract_claim1(bib)
    ipc = _extract_ipc(bib)

    if not (title or abstract or claim1):
        return {**entry, "resolved": False, "lookup_status": "biblio_empty_fields"}, calls

    updated = {
        **entry,
        "resolved": True,
        "lookup_status": "resolved",
        "applno": app_no,
        "title": title,
        "abstract": abstract,
        "claim1": claim1,
        "ipc": ipc,
        "source": "kipris_plus_api",
        "fetched_at": _now(),
    }
    return updated, calls


def resolve_jp_via_kipris(client: KiprisClient, entry: dict, budget: int) -> tuple[dict, int]:
    """JP 공개번호로 KIPRIS Plus 외국 서지를 시도.

    KIPRIS Plus는 JP/US/EP/CN 국제공보를 일부 포함한다.  가용 여부가 제한적이므로
    best-effort 처리하며, 실패 시 ``lookup_status="foreign_not_covered"`` 로 표시.
    """
    original = entry["original"]
    # normalise: "JP-2007-009988" → "JP2007009988" for openNumber
    raw = re.sub(r"[^0-9A-Za-z]", "", original.upper())
    calls = 0

    # Try KIPRIS with the raw number (foreign openNumber field)
    if budget >= 1:
        item = _search_one(client, {"openNumber": raw, "patent": "true"})
        calls += 1
        if not item:
            # Second attempt: strip country prefix
            num_only = re.sub(r"^JP", "", raw)
            item = _search_one(client, {"openNumber": num_only, "patent": "true"})
            calls += 1

    if not item:
        return {**entry, "resolved": False, "lookup_status": "foreign_not_covered"}, calls

    app_no = _s(item.get("applicationNumber"))
    if not app_no or budget - calls < 1:
        return {**entry, "resolved": False, "lookup_status": "foreign_no_appno"}, calls

    bib = _biblio(client, app_no)
    calls += 1
    if not bib:
        return {**entry, "resolved": False, "lookup_status": "foreign_biblio_empty"}, calls

    title = _extract_title(bib) or _s(item.get("inventionTitle"))
    abstract = _extract_abstract(bib) or _s(item.get("astrtCont"))
    claim1 = _extract_claim1(bib)
    ipc = _extract_ipc(bib)

    if not (title or abstract):
        return {**entry, "resolved": False, "lookup_status": "foreign_empty_fields"}, calls

    updated = {
        **entry,
        "resolved": True,
        "lookup_status": "resolved",
        "applno": app_no,
        "title": title,
        "abstract": abstract,
        "claim1": claim1,
        "ipc": ipc,
        "source": "kipris_plus_api_foreign",
        "fetched_at": _now(),
    }
    return updated, calls


# ── US Google Patents resolver ───────────────────────────────────────────
# search.patentsview.org 는 NXDOMAIN (도메인 미존재) 이므로
# Google Patents 페이지 스크래핑으로 title/abstract/date 수집.

_GOOGLE_PATENTS_BASE = "https://patents.google.com/patent"
_GP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_us_grant(serial: str) -> str:
    """US grant 일련번호 → 선행 0·kind code 제거.

    US06490145 B1 → "6490145", US5308414 → "5308414"
    """
    s = re.sub(r"\s*[A-Z]\d?\s*$", "", serial).strip()  # strip kind code (B1, B2, A)
    return s.lstrip("0") or s  # strip leading zeros (keep at least 1 digit)


def _normalize_us_pub(serial: str) -> str:
    """US pub 일련번호 → 숫자만 추출 (11자리 표준).

    US2015/0093880 → "20150093880", US2002-0063106 → "20020063106"
    US20020088548 A1 → "20020088548"
    """
    return re.sub(r"[^0-9]", "", serial)


def _gp_fetch(
    url: str,
    session: requests.Session,
    timeout: int = 20,
) -> dict[str, Any] | None:
    """Google Patents 페이지에서 메타데이터 스크래핑.

    반환:
      - ``None``              : 네트워크 오류 (ConnectionError/Timeout)
      - ``{"error": "not_found"}`` : HTTP 404
      - ``{"title": ..., "abstract": ..., "pub_date": ...}`` : 성공
    """
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code == 404:
            return {"error": "not_found"}
        r.raise_for_status()
        html = r.text

        # DC.title: 특허 제목
        title_m = re.search(r'<meta[^>]+name="DC\.title"[^>]*content="([^"]+)"', html)
        if not title_m:
            title_m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+name="DC\.title"', html)

        # description: 초록 (일부 truncation 가능)
        desc_m = re.search(r'<meta[^>]+name="description"[^>]*content="([^"]+)"', html)
        if not desc_m:
            desc_m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+name="description"', html)

        # DC.date: 여러 값 중 마지막 (보통 등록/공개일)
        dates = re.findall(r'<meta[^>]+name="DC\.date"[^>]*content="([^"]+)"', html)

        return {
            "title": title_m.group(1).strip() if title_m else "",
            "abstract": desc_m.group(1).strip() if desc_m else "",
            "pub_date": max(dates) if dates else "",  # ISO 날짜 → max = 최신일
        }
    except requests.exceptions.ConnectionError:
        return None  # offline / network unreachable
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError:
        return None
    except Exception:
        return None


def _normalize_gp_id(original: str, country: str) -> str:
    """JP/WO/CN/US 원본 번호 → Google Patents URL용 문자열.

    반환값 예시:
      'JP-2007-009988'  → 'JP2007009988'
      'JP-H08-255787'   → 'JPH08255787'
      'JP2008227064 A'  → 'JP2008227064'
      'JP07221208 A'    → 'JPH07221208'  ← Heisei 2자리 숫자 → H prefix
      'JP10178112 A'    → 'JPH10178112'  ← Heisei 10년대 (≤H13)
      'WO2019088204 A1' → 'WO2019088204A1'
      'CN111621760 A'   → 'CN111621760A'
    """
    # 공백 제거 후 알파벳+숫자만 남기기 (하이픈·슬래시 제거)
    raw = re.sub(r"[^A-Za-z0-9]", "", original.upper())
    # 이미 국가코드로 시작하면 그대로 사용
    if not raw.startswith(country):
        raw = country + raw

    # JP: 구 번호 처리 (H prefix 없는 2자리 연도 → Heisei 추정)
    # JPH08... 형식은 이미 OK; JP07.../JP10... 등은 JPH0x/JPH1x 로 변환
    if country == "JP" and not raw.startswith("JPH") and not raw.startswith("JPS"):
        # JP 다음 숫자가 2자리로 시작하면 (ex: JP07..., JP10...)
        num_part = raw[2:]  # JP 제거
        if num_part and num_part[0].isdigit():
            # 4자리 서기연도(1994~)는 그대로, 2자리 Heisei(01~13)는 H prefix 추가
            # 2자리: 01~13 → Heisei (1989+N), 14이상은 그대로(서기2002= H14 경계)
            first_two = num_part[:2]
            if first_two.isdigit() and int(first_two) <= 13 and len(num_part) <= 10:
                raw = "JPH" + num_part

    return raw


def resolve_us_google_patents(
    entry: dict,
    session: requests.Session,
    interval: float,
) -> tuple[dict, int]:
    """US grant/publication → Google Patents 스크래핑."""
    citation = parse_citation(entry["original"])
    kind = citation.kind
    serial = citation.serial
    calls = 0

    if kind == "grant":
        patent_num = _normalize_us_grant(serial)
        url = f"{_GOOGLE_PATENTS_BASE}/US{patent_num}/en"
        source_tag = "google_patents_scrape_grant"
    else:
        pub_num = _normalize_us_pub(serial)
        url = f"{_GOOGLE_PATENTS_BASE}/US{pub_num}/en"
        source_tag = "google_patents_scrape_pub"

    time.sleep(interval)
    data = _gp_fetch(url, session)
    calls += 1
    return _gp_result(entry, data, source_tag, calls)


def resolve_google_patents(
    entry: dict,
    session: requests.Session,
    interval: float,
) -> tuple[dict, int]:
    """JP/WO/CN → Google Patents 스크래핑.

    Returns (updated_entry, api_calls_used).
    ``lookup_status`` 값:
      - ``resolved``           : 성공
      - ``not_found``          : 404 (번호 오류 혹은 미수록)
      - ``network_unreachable``: 인터넷 연결 없음 (graceful)
      - ``empty_fields``       : 페이지는 열렸으나 title/abstract 없음
    """
    country = entry.get("country", "").upper()
    gp_id = _normalize_gp_id(entry["original"], country)
    url = f"{_GOOGLE_PATENTS_BASE}/{gp_id}/en"
    source_tag = f"google_patents_scrape_{country.lower()}"

    time.sleep(interval)
    data = _gp_fetch(url, session)
    calls = 1
    return _gp_result(entry, data, source_tag, calls)


def _gp_result(
    entry: dict,
    data: dict[str, Any] | None,
    source_tag: str,
    calls: int,
) -> tuple[dict, int]:
    """_gp_fetch 결과를 entry update로 변환하는 공통 헬퍼."""
    if data is None:
        return {**entry, "resolved": False, "lookup_status": "network_unreachable"}, calls
    if data.get("error") == "not_found":
        return {**entry, "resolved": False, "lookup_status": "not_found"}, calls

    title = data.get("title", "")
    abstract = data.get("abstract", "")
    pub_date = data.get("pub_date", "")

    if not (title or abstract):
        return {**entry, "resolved": False, "lookup_status": "empty_fields"}, calls

    updated = {
        **entry,
        "resolved": True,
        "lookup_status": "resolved",
        "title": title,
        "abstract": abstract,
        "claim1": "",
        "ipc": "",
        "pub_date": pub_date,
        "source": source_tag,
        "fetched_at": _now(),
    }
    return updated, calls


def resolve_epo_ops(
    client: EpoOpsClient,
    entry: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    epodoc_id = _epo_epodoc_id(entry)
    payload = client.fetch_biblio(epodoc_id)
    calls = 1

    if payload is None:
        return {**entry, "resolved": False, "lookup_status": "network_unreachable"}, calls
    if payload.get("error"):
        return {**entry, "resolved": False, "lookup_status": _s(payload.get("error"))}, calls

    meta = _extract_epo_metadata(payload["doc"])
    if not (meta["title"] or meta["abstract"]):
        return {**entry, "resolved": False, "lookup_status": "empty_fields"}, calls

    updated = {
        **entry,
        "resolved": True,
        "lookup_status": "resolved",
        "title": meta["title"],
        "abstract": meta["abstract"],
        "claim1": "",
        "ipc": meta["ipc"],
        "pub_date": meta["pub_date"],
        "source": "epo_ops",
        "fetched_at": _now(),
    }
    return updated, calls


# ── fulltext writer ──────────────────────────────────────────────────────


def _write_fulltext(entry: dict) -> None:
    """Write or overwrite the .txt file for a resolved entry."""
    doc_id = entry["doc_id"]
    txt_path = FULLTEXT_DIR / f"{doc_id}.txt"

    lines = [
        f"Document Number: {doc_id}",
        f"Original ID: {entry.get('original', '')}",
        f"Country/Kind: {entry.get('country', '')}/{entry.get('kind', '')}",
        f"Resolved: {str(entry.get('resolved', False)).lower()}",
        f"Source: {entry.get('source', '')}",
        f"Fetched: {entry.get('fetched_at', '')}",
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

    txt_path.write_text("\n".join(lines), encoding="utf-8")


# ── main ──────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="목록만 출력, API 호출 없음")
    p.add_argument("--max-api-calls", type=int, default=200,
                   help="최대 API 호출 횟수 (기본: 200)")
    p.add_argument("--interval", type=float, default=0.5,
                   help="호출 간격 초 (기본 0.5 → 2 req/sec, 75/sec 한도 대비 충분)")
    p.add_argument("--include-jp", action="store_true",
                   help="JP 문헌을 Google Patents 스크래핑으로 보강")
    p.add_argument("--include-us", action="store_true",
                   help="US 문헌 Google Patents 스크래핑으로 보강")
    p.add_argument("--include-epo", action="store_true",
                   help="WO/CN/EP 문헌을 EPO OPS로 보강")
    p.add_argument("--us-interval", type=float, default=1.5,
                   help="Google Patents 호출 간격 초 (기본 1.5 → 0.67 req/sec)")
    args = p.parse_args(argv)

    entries = _load_index()
    cache = _load_cache()
    cached: dict[str, Any] = cache.get("entries", {})

    # 비-KR 문헌은 build_etching_corpus.py가 skip하여 _index.json에 없을 수 있으므로
    # 필요 플래그별로 JSONL 데이터셋에서 직접 보충한다.
    if args.include_jp:
        entries = _supplement_from_dataset(entries, ("JP",))
    if args.include_epo:
        entries = _supplement_from_dataset(entries, ("WO", "CN", "EP"))

    # --include-jp 시 이전 KIPRIS best-effort 실패(foreign_not_covered) 캐시는 무시한다.
    # Google Patents 로 재시도해야 하기 때문.
    _gp_retry_statuses = {"foreign_not_covered", "foreign_no_appno", "foreign_biblio_empty",
                          "foreign_empty_fields", "not_found"}  # not_found: 번호 재정규화 후 재시도
    if args.include_jp:
        cached = {
            k: v for k, v in cached.items()
            if v.get("lookup_status") not in _gp_retry_statuses
        }
    if args.include_epo:
        cached = {
            k: v for k, v in cached.items()
            if not (
                any(k.startswith(prefix) for prefix in ("WO-", "CN-", "EP-"))
                and v.get("lookup_status") != "resolved"
            )
        }

    # 대상 필터링
    todo = [
        e for e in entries
        if not e.get("resolved")
        and e.get("doc_id")
        and (
            e.get("country") == "KR"
            or (args.include_jp and e.get("country") == "JP")
            or (args.include_us and e.get("country") == "US")
            or (args.include_epo and e.get("country") in ("WO", "CN", "EP"))
        )
        and e["doc_id"] not in cached
    ]

    kr_count = sum(1 for e in todo if e.get("country") == "KR")
    jp_count = sum(1 for e in todo if e.get("country") == "JP")
    wo_count = sum(1 for e in todo if e.get("country") == "WO")
    cn_count = sum(1 for e in todo if e.get("country") == "CN")
    ep_count = sum(1 for e in todo if e.get("country") == "EP")
    us_count = sum(1 for e in todo if e.get("country") == "US")
    print(f"[enrich] unresolved targets: KR={kr_count} JP={jp_count} WO={wo_count} CN={cn_count} EP={ep_count} US={us_count}  "
          f"budget={args.max_api_calls}  interval={args.interval}s  dry_run={args.dry_run}")

    if args.dry_run:
        for e in todo:
            print(f"  {e['doc_id']:35s} country={e.get('country')} kind={e.get('kind')} "
                  f"original={e.get('original')}")
        return 0

    client: KiprisClient | None = None
    if kr_count:
        api_key = os.getenv("KIPRIS_API_KEY", "").strip()
        if not api_key:
            print("[enrich] ERROR: KIPRIS_API_KEY not set in environment / .env", file=sys.stderr)
            return 2
        client = KiprisClient(
            api_key,
            min_request_interval=args.interval,
            stop_on_quota=True,
            max_retries=2,
        )

    epo_client: EpoOpsClient | None = None
    if wo_count or cn_count or ep_count:
        epo_key = os.getenv("EPO_OPS_KEY", "").strip()
        epo_secret = os.getenv("EPO_OPS_SECRET", "").strip()
        if not (epo_key and epo_secret):
            print("[enrich] ERROR: EPO_OPS_KEY / EPO_OPS_SECRET not set in environment / .env", file=sys.stderr)
            return 2
        epo_client = EpoOpsClient(epo_key, epo_secret, min_request_interval=args.interval)

    # Google Patents session (US 처리용 — API 키 불필요)
    gp_session = requests.Session()
    gp_session.headers.update(_GP_HEADERS)

    used = 0
    resolved_count = 0
    failed_count = 0
    network_skip_count = 0
    updated_entries = {e["doc_id"]: e for e in entries}  # mutable copy

    for i, entry in enumerate(todo, 1):
        if used >= args.max_api_calls:
            print(f"[enrich] budget reached ({used}/{args.max_api_calls}), stopping.")
            break

        country = entry.get("country", "")
        doc_id = entry["doc_id"]
        remaining = args.max_api_calls - used

        try:
            if country == "KR":
                assert client is not None
                new_entry, calls = resolve_kr(client, entry, remaining)
            elif country in ("WO", "CN", "EP") and args.include_epo:
                assert epo_client is not None
                new_entry, calls = resolve_epo_ops(epo_client, entry)
            elif country in ("JP", "WO", "CN") and args.include_jp:
                new_entry, calls = resolve_google_patents(entry, gp_session, args.us_interval)
            elif country == "US" and args.include_us:
                new_entry, calls = resolve_us_google_patents(entry, gp_session, args.us_interval)
            else:
                continue
        except KiprisQuotaExceeded as exc:
            print(f"[enrich] Quota exceeded: {exc}  used={used}")
            break
        except KiprisServiceKeyError as exc:
            print(f"[enrich] Auth error: {exc}")
            return 2
        except EpoOpsAuthError as exc:
            print(f"[enrich] EPO auth error: {exc}")
            return 2

        used += calls
        status = new_entry.get("lookup_status", "?")

        if new_entry.get("resolved"):
            resolved_count += 1
            updated_entries[doc_id] = new_entry
            _write_fulltext(new_entry)
            tag = "✓ resolved"
        elif status == "network_unreachable":
            network_skip_count += 1
            tag = "⚡ network_unreachable (skip)"
            # Do NOT update index — retry when online
        else:
            failed_count += 1
            updated_entries[doc_id] = new_entry
            tag = f"✗ {status}"

        # Cache after every record so partial progress is preserved
        # network_unreachable 는 캐시 저장하지 않음 → 재실행 시 재시도
        if status != "network_unreachable":
            cached[doc_id] = new_entry
            cache["entries"] = cached
            _save_cache(cache)

        print(f"  [{i}/{len(todo)}] {doc_id}  {tag}  "
              f"calls={calls}  total={used}/{args.max_api_calls}")

    # Persist updated index
    _save_index(list(updated_entries.values()))

    print(f"\n[enrich] done. resolved={resolved_count}  failed={failed_count}  "
          f"network_skip={network_skip_count}  api_calls_used={used}")
    if network_skip_count:
        print(f"  ⚡ {network_skip_count}건 네트워크 미연결로 skip됨 — 인터넷 환경에서 재실행하면 자동 재시도됩니다.")
    print("  Next steps:")
    print("    .venv/bin/python scripts/build_etching_corpus.py --include-unresolved --fresh")
    print("    .venv/bin/python scripts/build_manifest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
