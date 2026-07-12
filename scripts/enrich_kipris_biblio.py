#!/usr/bin/env python3
"""SIRP 특허의 서지정보를 KIPRIS 권위 원천에서 다시 받아온다 — 특히 **출원일**.

왜 필요한가 (CLAUDE.md §8-1):
  최초 수집(raw JSONL)의 `target_patent.date` 는 출원일이 아니라 **공개일**이다.
  biblio.unex_pub_date 와 값이 같고(99%), 출원번호가 인코딩한 출원연도와는 34% 만 일치한다.
  출원번호는 연도만 인코딩하므로 출원일을 로컬에서 복원할 수 없다 → 권위 원천에서 받는다.

  KIPRIS getBibliographyDetailInfoSearch 응답 예 (출원번호 10-2021-0184131):
      applicationDate 2021.12.21   ← 진짜 출원일
      openDate        2023.06.28   ← 지금까지 filing_date 자리에 들어가 있던 값

입력:  data/patents/rejected_patents_meta.parquet  (application_number)
출력:  data/patents/kipris_biblio.parquet          (권위 서지 — 커밋 대상, 메타데이터만)
       응답은 sqlite 에 캐시하므로 재실행해도 API 를 다시 때리지 않는다.

CLI:  python scripts/enrich_kipris_biblio.py [--limit N]
      KIPRIS_API_KEY 를 환경변수 또는 .env 에서 읽는다.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
OUT = ROOT / "data" / "patents" / "kipris_biblio.parquet"
CACHE = ROOT / "data" / "patents" / ".kipris_cache.sqlite"

ENDPOINT = (
    "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"
    "/getBibliographyDetailInfoSearch"
)
REQUEST_INTERVAL_SEC = 0.2   # 무제한 학술 자격이어도 서버 예의
MAX_RETRIES = 4


def api_key() -> str:
    key = os.environ.get("KIPRIS_API_KEY")
    if key:
        return key
    for env in (ROOT / ".env", ROOT.parent / "SKKU" / "sdkb-foresight-paper" / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("KIPRIS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("KIPRIS_API_KEY 를 환경변수나 .env 에서 찾을 수 없다.")


def _cache() -> sqlite3.Connection:
    con = sqlite3.connect(CACHE)
    con.execute(
        "CREATE TABLE IF NOT EXISTS biblio ("
        " application_number TEXT PRIMARY KEY, fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        " body TEXT)"
    )
    return con


def fetch(session: requests.Session, con: sqlite3.Connection, key: str, an: str) -> str:
    row = con.execute(
        "SELECT body FROM biblio WHERE application_number=?", (an,)
    ).fetchone()
    if row:
        return row[0]

    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(
                ENDPOINT, params={"applicationNumber": an, "ServiceKey": key}, timeout=30
            )
            r.raise_for_status()
            # 실패 응답(키 오류·조회 실패)을 캐시하면 재실행해도 에러가 되돌아온다 — 성공만 캐시한다.
            code = _result_code(r.text)
            if code != "00":
                raise RuntimeError(f"KIPRIS resultCode={code}")
            con.execute(
                "INSERT OR REPLACE INTO biblio (application_number, body) VALUES (?,?)",
                (an, r.text),
            )
            con.commit()
            time.sleep(REQUEST_INTERVAL_SEC)
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(2**attempt)
    raise RuntimeError(f"KIPRIS 요청 실패: {an}") from last


def _result_code(body: str) -> str:
    el = ET.fromstring(body).find(".//resultCode")
    return (el.text or "").strip() if el is not None and el.text else "??"


def _iso(kipris_date: str) -> str:
    """KIPRIS 는 'YYYY.MM.DD' 로 준다 → ISO 'YYYY-MM-DD'. 빈 값은 빈 문자열."""
    d = (kipris_date or "").strip().strip("()")
    return d.replace(".", "-") if len(d) == 10 else ""


def parse(body: str) -> dict:
    """응답 XML → 서지 dict. 태그명은 실제 응답에서 확인한 것이다."""
    root = ET.fromstring(body)

    def first(tag: str) -> str:
        el = root.find(f".//{tag}")
        return (el.text or "").strip() if el is not None and el.text else ""

    ipcs = [
        (e.text or "").strip()
        for e in root.iter("ipcNumber")
        if e.text and (e.text or "").strip()
    ]
    return {
        "result_code": first("resultCode"),
        "filing_date": _iso(first("applicationDate")),      # ← 진짜 출원일
        "open_date": _iso(first("openDate")),               # ← 공개일 (기존 filing_date 의 정체)
        "open_number": first("openNumber"),
        "register_date": _iso(first("registerDate")),
        "ipc_codes": "|".join(dict.fromkeys(ipcs)),         # 순서 보존 dedup
        "invention_title": first("inventionTitle"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="앞의 N 건만 (스모크 테스트용)")
    args = ap.parse_args()

    if not META.exists():
        print(f"ERROR: {META} 없음 — `make ingest-sirp` 먼저.", file=sys.stderr)
        return 1

    meta = pd.read_parquet(META, columns=["application_number"])
    ans = meta["application_number"].astype(str).str.replace("-", "", regex=False)
    ans = ans[ans.str.len() > 0].drop_duplicates().tolist()
    if args.limit:
        ans = ans[: args.limit]

    key, session, con = api_key(), requests.Session(), _cache()
    rows, failed = [], []
    for i, an in enumerate(ans, 1):
        try:
            rec = parse(fetch(session, con, key, an))
        except Exception as e:  # 네트워크·파싱 실패는 건너뛰되 끝에 정직하게 센다
            failed.append((an, str(e)[:60]))
            continue
        rec["application_number"] = an
        rows.append(rec)
        if i % 100 == 0:
            print(f"  {i}/{len(ans)} …", flush=True)

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    # --- 프로파일 (CLAUDE.md §5: 수집물에는 프로파일이 따라붙는다) ---
    ok = (df.result_code == "00").sum() if len(df) else 0
    have = (df.filing_date != "").sum() if len(df) else 0
    print(f"\n✓ {len(df):,}건 → {OUT.relative_to(ROOT)}  (실패 {len(failed)}건)")
    print(f"  resultCode==00      : {ok:,}/{len(df):,}")
    print(f"  filing_date 확보     : {have:,}/{len(df):,}  결측 {len(df)-have:,}")
    if len(df):
        d = df[(df.filing_date != "") & (df.open_date != "")]
        # 진짜 불변조건: 출원일 ≤ 공개일. (출원번호의 연도와 출원일 연도는 PCT 국내단계 진입에서
        # 정당하게 어긋나므로 — 국제출원일이 KR 출원번호 부여보다 앞선다 — 검증에 쓰지 않는다.)
        print(f"  출원일 ≤ 공개일      : {(d.filing_date <= d.open_date).mean():.1%}  (불변조건)")
        print(f"  filing_date == open_date : {(df.filing_date == df.open_date).mean():.1%}"
              f"   (기존 컬럼은 99% — 그게 결함이었다)")
        yrs = df.loc[df.filing_date != "", "filing_date"].str[:4]
        print(f"  출원연도 범위        : {yrs.min()} ~ {yrs.max()}")
        print(f"  연도별 상위          : {dict(yrs.value_counts().head(5))}")
        print(f"  ipc_codes 확보       : {(df.ipc_codes != '').sum():,}/{len(df):,}")
    for an, err in failed[:5]:
        print(f"  ! 실패 {an}: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
