#!/usr/bin/env python3
"""중간서류 PDF 수집 — `pdfInfoV2` 직접 조회 경로 (거절결정서 · 의견제출통지서 공통).

왜 이 스크립트가 따로 있는가 (2026-07-30 실측)
================================================
기존 `backfill_admin_docs.py` 는 **검색 오퍼레이션** `advancedSearchInfo` 를 쓴다.
그런데 이 저장소의 반도체 거절특허 1,000건에 대해 그 오퍼레이션은 **대부분 0건을 반환한다** —
2026-05 실행에서 475건이 `matched_count=0` 이었고, 그것이 "서류가 존재하지 않는다"로
잘못 해석되어 하류(sdkb → 논문)에서 **거절근거 무라벨 600건**이라는 자원 결손으로 굳어졌다.

실제로는 **문서가 전부 있었다.** 같은 출원번호를 **출원번호 직접 조회**(`pdfInfoV2`)로
부르면 `filePath` 가 정상 반환된다. 두 서비스 모두 같은 증상이다.

    거절결정서      IntermediateDocumentREService   advancedSearchInfo → 0건 / pdfInfoV2 → 정상
    의견제출통지서  IntermediateDocumentOPService   advancedSearchInfo → 0건 / pdfInfoV2 → 정상

실측 결과: 거절결정서 538/539 · 의견제출통지서 998/1,000 확보. PDF 에 텍스트층이 있어
**OCR 이 필요 없다**(pdfplumber). 의견제출통지서 본문은 평균 ~7,000자로 거절결정서(~900자)보다
정보량이 훨씬 크며, **조항(제29조 제1·2항)·청구항 번호·인용문헌이 모두 여기에 있다** —
거절결정서는 다수가 "앞선 거절이유를 번복할 사항 없음"으로 조항을 재기술하지 않는다.

사용
====
    # 의견제출통지서 (기본)
    .venv/bin/python scripts/backfill_pdfinfo_v2.py --service op --max-api-calls 300

    # 거절결정서
    .venv/bin/python scripts/backfill_pdfinfo_v2.py --service re

산출
====
    data/processed/{opinion_notices|rejection_pdfinfo}/pdf/<출원번호>_<발송번호>.pdf
    data/processed/{...}/txt/<출원번호>_<발송번호>.txt
    data/processed/{...}/_index.json     — 출원번호별 처리 결과(재실행 시 skip)

캐시가 있으므로 중단해도 이어서 실행된다. 호출 예산은 `--max-api-calls` 로 제한한다.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.dataset_paths import CANONICAL_SEMICONDUCTOR_DATASET  # noqa: E402
from kipris_dataset.rejection_decision import RejectionDecisionClient  # noqa: E402

SERVICES = {
    # 의견제출통지서 — 조항·청구항·인용문헌의 주 원천
    "op": ("http://plus.kipris.or.kr/openapi/rest/IntermediateDocumentOPService", "opinion_notices"),
    # 거절결정서 — 다수가 앞선 거절이유를 참조만 한다
    "re": ("http://plus.kipris.or.kr/openapi/rest/IntermediateDocumentREService", "rejection_pdfinfo"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_text(pdf_bytes: bytes) -> str:
    """텍스트층 추출. 중간서류 PDF 는 텍스트층이 있어 OCR 이 불필요하다(실측)."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages).strip()


def _pdf_infos(client: RejectionDecisionClient, application_number: str) -> List[Dict[str, Any]]:
    """`pdfInfoV2` 응답을 항상 리스트로 정규화한다(문서가 복수일 수 있다 — 최초·최후 통지)."""
    data = client.get("pdfInfoV2", {"applicationNumber": application_number})
    items = ((data.get("response") or {}).get("body") or {}).get("items")
    info = (items or {}).get("pdfInfoV2") if isinstance(items, dict) else None
    if isinstance(info, list):
        return [x for x in info if isinstance(x, dict)]
    return [info] if isinstance(info, dict) else []


def main() -> None:
    ap = argparse.ArgumentParser(description="중간서류 PDF 수집 (pdfInfoV2 직접 조회)")
    ap.add_argument("--service", choices=sorted(SERVICES), default="op")
    ap.add_argument("--dataset", type=Path, default=CANONICAL_SEMICONDUCTOR_DATASET)
    ap.add_argument("--interval", type=float, default=0.4, help="호출 간격(초)")
    ap.add_argument("--max-api-calls", type=int, default=0, help="0 = 무제한")
    ap.add_argument("--refresh", action="store_true", help="캐시 무시하고 재조회")
    args = ap.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    base_url, out_name = SERVICES[args.service]
    out = REPO_ROOT / "data/processed" / out_name
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    (out / "txt").mkdir(exist_ok=True)
    index_path = out / "_index.json"

    import os

    key = os.environ.get("KIPRIS_REST_ACCESS_KEY") or os.environ["KIPRIS_API_KEY"]
    client = RejectionDecisionClient(api_key=key, base_url=base_url)

    apps = [
        str(json.loads(line)["target_patent"]["application_number"])
        for line in args.dataset.open(encoding="utf-8")
    ]
    index: Dict[str, Any] = {}
    if index_path.exists() and not args.refresh:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    remaining = [a for a in apps if a not in index]
    todo = remaining[: args.max_api_calls] if args.max_api_calls else remaining
    # 캐시로 건너뛴 것과 호출예산으로 미룬 것을 구분해 보고한다(둘을 합치면 오해를 부른다).
    print(
        f"[{args.service}] 대상 {len(apps)} · 캐시 skip {len(apps) - len(remaining)} · "
        f"이번 호출 {len(todo)} · 예산으로 보류 {len(remaining) - len(todo)}",
        flush=True,
    )

    got = missing = failed = 0
    for i, app in enumerate(todo, 1):
        record: Dict[str, Any] = {"application_number": app, "fetched_at": _now(), "docs": []}
        try:
            infos = _pdf_infos(client, app)
            record["n_docs"] = len(infos)
            for k, info in enumerate(infos):
                url = info.get("filePath") or info.get("path")
                if not url:
                    continue
                body = requests.get(url, timeout=40).content
                if body[:4] != b"%PDF":
                    record["docs"].append({"send": info.get("sendNumber"), "error": "not_pdf"})
                    continue
                name = f"{app}_{info.get('sendNumber') or k}"
                (out / "pdf" / f"{name}.pdf").write_bytes(body)
                text = _extract_text(body)
                (out / "txt" / f"{name}.txt").write_text(text, encoding="utf-8")
                record["docs"].append(
                    {"send": info.get("sendNumber"), "file": name, "bytes": len(body), "chars": len(text)}
                )
            got += 1 if record["docs"] else 0
            missing += 0 if infos else 1
        except Exception as exc:  # noqa: BLE001 — 한 건 실패가 전체를 멈추지 않게 한다
            record["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            failed += 1
        index[app] = record
        if i % 25 == 0 or i == len(todo):
            # 중단되어도 진행분이 남도록 주기적으로 기록한다
            index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            print(f"  {i}/{len(todo)} · 확보 {got} · 문서없음 {missing} · 오류 {failed}", flush=True)
        time.sleep(args.interval)

    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"[{args.service}] 완료 — 확보 {got} · 문서없음 {missing} · 오류 {failed} · index {index_path}")


if __name__ == "__main__":
    main()
