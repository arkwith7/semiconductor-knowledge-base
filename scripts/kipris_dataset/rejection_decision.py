"""KIPRIS Plus 거절결정서 REST 프로토타입 유틸리티.

현재 목적:
- applicationNumber 기준으로 거절결정서 REST(`advancedSearchInfo`)를 조회
- 기존 거절특허 레코드에 보조 정보로 붙일 수 있는 최소 구조를 제공

서비스 설명 페이지:
- https://plus.kipris.or.kr/portal/popup/service/DBII_000000000000243/view.do
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import requests
import xmltodict

from .kipris import KiprisQuotaExceeded, KiprisServiceKeyError

BASE_URL = "http://plus.kipris.or.kr/openapi/rest/IntermediateDocumentREService"
OP_ADVANCED_SEARCH = "advancedSearchInfo"


def _str(value: Any) -> str:
    return str(value).strip() if value else ""


def _to_list(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _looks_like_service_key_error(message: Optional[str]) -> bool:
    if not message:
        return False
    text = str(message).lower()
    return any(
        token in text
        for token in [
            "서비스 이용 권한",
            "서비스키",
            "servicekey",
            "service key",
            "accesskey",
            "access key",
            "만료",
            "잘못",
            "인증",
        ]
    )


def _looks_like_quota_error(message: Optional[str]) -> bool:
    if not message:
        return False
    text = str(message).lower()
    return any(
        token in text
        for token in ["트래픽", "제한", "초과", "quota", "limit", "rate", "too many", "429", "denied"]
    )


class RejectionDecisionClient:
    """KIPRIS Plus 거절결정서 REST GET 래퍼."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        min_request_interval: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._min_interval = float(min_request_interval)
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

    def get(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/{operation.lstrip('/')}"
        req_params = {**params, "accessKey": self._api_key}

        for attempt in range(self._max_retries):
            try:
                self._throttle()
                response = requests.get(url, params=req_params, timeout=30)
                if response.status_code in {401, 403, 429}:
                    message = f"HTTP {response.status_code}"
                    if response.status_code == 429:
                        raise KiprisQuotaExceeded(message)
                    raise KiprisServiceKeyError(message)

                response.raise_for_status()
                parsed = xmltodict.parse(response.text)

                header = (parsed.get("response") or {}).get("header") or {}
                result_code = _str(header.get("resultCode"))
                result_msg = _str(header.get("resultMsg") or header.get("resultmsg"))
                error_message = result_msg or result_code

                if _looks_like_service_key_error(error_message):
                    raise KiprisServiceKeyError(error_message)
                if _looks_like_quota_error(error_message):
                    raise KiprisQuotaExceeded(error_message)
                if result_code or result_msg:
                    raise RuntimeError(
                        f"KIPRIS rejection decision API error: code={result_code or '?'} msg={result_msg or '?'}"
                    )

                return parsed
            except (KiprisServiceKeyError, KiprisQuotaExceeded):
                raise
            except Exception:
                if attempt < self._max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))

        return {}

    def search(
        self,
        *,
        application_number: Optional[str] = None,
        word: Optional[str] = None,
        rejection_content: Optional[str] = None,
        send_number: Optional[str] = None,
        send_date: Optional[str] = None,
        patent: bool = True,
        utility: bool = True,
        design: bool = False,
        trade_mark: bool = False,
        docs_start: int = 1,
        docs_count: int = 10,
        desc_sort: bool = True,
        sort_spec: str = "AD",
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "patent": str(patent).lower(),
            "utility": str(utility).lower(),
            "design": str(design).lower(),
            "tradeMark": str(trade_mark).lower(),
            "docsStart": docs_start,
            "docsCount": docs_count,
            "descSort": str(desc_sort).lower(),
            "sortSpec": sort_spec,
        }
        if application_number:
            params["applicationNumber"] = application_number
        if word:
            params["word"] = word
        if rejection_content:
            params["rejectionContent"] = rejection_content
        if send_number:
            params["sendNumber"] = send_number
        if send_date:
            params["sendDate"] = send_date

        parsed = self.get(OP_ADVANCED_SEARCH, params)
        body = (parsed.get("response") or {}).get("body") or {}
        items_wrapper = body.get("items") or {}
        items_raw = items_wrapper.get("advancedSearchInfo") or body.get("advancedSearchInfo") or []
        return _to_list(items_raw)


def normalize_rejection_decision_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """응답 item을 후속 조인에 쓰기 쉬운 형태로 정리."""
    return {
        "application_number": _str(item.get("applicationNumber")),
        "send_number": _str(item.get("sendNumber")),
        "send_date": _str(item.get("sendDate")),
        "title": _str(item.get("title") or item.get("inventionTitle")),
        "file_path": _str(item.get("filePath")),
        "raw": item,
    }


def build_rejection_decision_attachment(
    application_number: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """기존 레코드에 붙일 보조 구조를 생성."""
    normalized = [normalize_rejection_decision_item(item) for item in items]
    return {
        "query": {
            "application_number": _str(application_number),
            "matched_count": len(normalized),
            "service": "IntermediateDocumentREService/advancedSearchInfo",
        },
        "items": normalized,
    }
