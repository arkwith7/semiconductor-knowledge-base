"""KIPRIS Plus API HTTP 어댑터 (공유 모듈).

notebooks/02, notebooks/03, scripts/ 에서 공통으로 사용하는 KIPRIS API 클라이언트입니다.
이전에는 각 노트북이 독립적으로 구현하던 것을 이 모듈로 통합했습니다.

사용 예시 (노트북/스크립트):
    from kipris_dataset.kipris import KiprisClient, KiprisQuotaExceeded, normalize_patent_id

    client = KiprisClient(api_key, min_request_interval=0.5)
    header, body = client.call("getAdvancedSearch", {"word": "딥러닝 반도체"})
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, Optional, Tuple

import requests
import xmltodict

BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"

OP_ADVANCED_SEARCH = "getAdvancedSearch"
OP_BIBLIO_DETAIL = "getBibliographyDetailInfoSearch"
OP_PUB_FULLTEXT = "getPubFullTextInfoSearch"
OP_ANN_FULLTEXT = "getAnnounceFullTextInfoSearch"
OP_REG_FULLTEXT = "getRegistrationFullTextInfoSearch"
OP_CLAIM = "getClaimInfoSearch"


class KiprisServiceKeyError(RuntimeError):
    """서비스키 만료 또는 권한 오류."""


class KiprisQuotaExceeded(RuntimeError):
    """일/분당 호출 한도 초과."""


_PATENT_PREFIXES = (
    "US", "KR", "JP", "CN", "EP", "WO", "DE", "FR", "GB", "TW",
    "CA", "AU", "RU", "IN", "BR", "IT", "ES",
)


def normalize_patent_id(pid: str) -> str:
    pid = re.sub(r"[\s\-]", "", str(pid).strip()).lower()
    pid = re.sub(r"[ab]\d*$", "", pid)
    return pid


def looks_like_patent_doc_number(value: str) -> bool:
    if not value:
        return False
    s = str(value).strip()
    if any(x in s for x in ["arXiv", "Vol.", "pp.", "doi", "et al", "IEEE", "ACM", "Journal", "Proceedings"]):
        return False
    if re.search(r"[가-힣]", s) and not s.upper().startswith("KR"):
        return False
    up = s.upper().replace(" ", "")
    if not any(up.startswith(p) for p in _PATENT_PREFIXES):
        return False
    digits = re.findall(r"\d+", up)
    return bool(digits) and len("".join(digits)) >= 6


def normalize_patent_number(doc_num: str) -> str:
    s = re.sub(r"[\s/\-]", "", str(doc_num).strip())
    s = re.sub(r"[^0-9A-Za-z]", "", s)
    s = re.sub(r"^KR10", "KR", s, flags=re.IGNORECASE)
    return s


def is_korean_patent(doc_num: str) -> bool:
    return str(doc_num).strip().upper().startswith("KR")


def guess_google_patents_lang(doc_num: str) -> str:
    up = str(doc_num).strip().upper()
    if up.startswith("JP"):
        return "ja"
    if up.startswith("CN"):
        return "zh-CN"
    if up.startswith("KR"):
        return "ko"
    return "en"


def _looks_like_servicekey_error(msg: Optional[str]) -> bool:
    if not msg:
        return False
    return any(x in str(msg) for x in [
        "서비스 이용 권한", "서비스키", "만료", "잘못", "SERVICEKEY", "SERVICE KEY",
    ])


def _looks_like_quota_error(msg: Optional[str]) -> bool:
    if not msg:
        return False
    m = str(msg).lower()
    # 파라미터 검증 에러("13자리를 초과할수 없습니다" 등)는 quota가 아니라 input error.
    # "초과" 단독으로는 quota를 의미하지 않으므로 더 구체적인 quota 단서가 함께 있어야 한다.
    if "자리" in m or "digits" in m or "length" in m:
        return False
    return any(k in m for k in ["트래픽", "quota", "limit", "rate", "too many", "429", "denied"]) \
        or ("호출" in m and "초과" in m) \
        or ("일" in m and "초과" in m) \
        or "제한" in m


class KiprisClient:
    """KIPRIS Plus API GET 래퍼."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        min_request_interval: float = 0.0,
        stop_on_quota: bool = True,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._min_interval = float(min_request_interval)
        self._stop_on_quota = stop_on_quota
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._last_request_ts: float = 0.0

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            wait = self._last_request_ts + self._min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    def get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/{path}"
        req_params = {**params, "ServiceKey": self._api_key}

        for attempt in range(self._max_retries):
            try:
                self._throttle()
                resp = requests.get(url, params=req_params, timeout=30)

                if resp.status_code in {401, 403, 429}:
                    msg = f"HTTP {resp.status_code}"
                    if self._stop_on_quota:
                        raise KiprisQuotaExceeded(msg)
                    resp.raise_for_status()

                resp.raise_for_status()
                parsed = xmltodict.parse(resp.text)

                response = parsed.get("response") or {}
                header = response.get("header") or {}
                result_msg = header.get("resultMsg") or header.get("resultmsg")

                if _looks_like_servicekey_error(result_msg):
                    raise KiprisServiceKeyError(str(result_msg))
                if self._stop_on_quota and _looks_like_quota_error(result_msg):
                    raise KiprisQuotaExceeded(str(result_msg))

                return parsed

            except (KiprisServiceKeyError, KiprisQuotaExceeded):
                raise
            except Exception:
                if attempt < self._max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))

        return {}

    def call(self, path: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        parsed = self.get(path, params)
        response = parsed.get("response") or {}
        header = response.get("header") or {}
        body = response.get("body") or {}
        return header, body