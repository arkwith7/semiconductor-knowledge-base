"""IR 코퍼스의 **DOCDB 패밀리 ID** 를 BigQuery 에서 가져온다 (PLAN-018 B2 · F1 주지표).

**왜 필요한가.** 주 지표는 **family-level Recall@100**(원고 §5.1·§4.5)이다. 같은 발명이 여러 나라·
공보로 중복 공개되면 한 패밀리로 묶어야 회수를 정직하게 센다. 그런데 조립된 IR 코퍼스에는
family_id 열이 없다 — qrel 정답 2,211건(심사관 인용 선행기술)은 **공개번호**로 식별되고
출원번호가 없어 시계열용 `bq_family.py`(KR 출원번호 키)의 지도로는 한 건도 조인되지 않는다.

**두 조인 경로.** (시계열 `bq_family.py` 는 건드리지 않는다 — 관심사 분리)
- **공개번호 조인:** g0_cited(선행기술 3,034 · doc_id 가 `cn_CN102403077A` 처럼 국가+번호+kind).
  BQ `publications.publication_number`(`CN-102403077-A`)와 정규화 매칭.
- **출원번호 조인:** family 미보유 KR 문서(주로 G₂ 소부장). doc_id 는 출원번호를 갖지 않으나
  코퍼스 `application_number`(13자리)로 KR `publications` 를 조인 — `bq_family.py` 와 같은 키.

**정규화 규칙(양쪽 동일).** `country_code || 앞0제거(숫자부)`. kind code(A·B1…)는 같은 출원의
서로 다른 공보라 **같은 family_id** 를 가리키므로 무시한다. 공개번호 조인의 결과가 하나의
정규화 키에 여러 family_id 를 주면(드묾) 사전순 최소를 택해 결정적으로 만든다.

**미조인 = fallback.** family_id 를 못 받은 문서는 **자기 자신**(`self:<doc_id>`)을 1개 패밀리로
둔다(원고 §4.5 "대체 규칙"). 비율을 프로파일에 보고한다 — 조용히 넘어가면 dedup 이 무효과가
되어 '수행했다'는 거짓 보고가 된다.

산출: `data/raw/bigquery/ir_family_map.parquet`(doc_id·family_id·method) — raw, 커밋하지 않는다.

CLI:  python -m sdkb_paper.collect.bq_family_ir [--dry-run]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from sdkb_paper.config import IR_CORPUS, IR_FAMILY_MAP, get_secret

# 공개번호 조인 대상 국가 (g0_cited 분포 실측 · 그 외는 fallback).
PUB_COUNTRIES = ("KR", "JP", "US", "WO", "CN", "EP", "GB")

_CC_RE = re.compile(r"^([A-Z]{2})(.+)$")
_KIND_RE = re.compile(r"^(.*?)([A-Z]\d?)$")


def normalize_pub(doc_id: str) -> tuple[str, list[str]] | None:
    """doc_id(`cn_CN102403077A`) → (country, [정규화 후보 키…]) 또는 None.

    정규화 키 = `CC`+앞0제거 숫자부. kind code(끝의 A·B1…)는 떼고 숫자부만 남긴다.
    **KR 특례:** KIPRIS 공개/등록번호는 특허=`10`·실용=`20` 타입 접두가 붙어(`KR100146263B1`
    = `10`+`0146263`) BQ(`KR-0146263-B1`)와 어긋난다 — `bq_family.py` 가 출원번호에서 다룬 그
    접두 문제다. 그래서 KR 은 접두 제거 변형을 후보에 추가한다(BQ 쪽은 접두가 없다).
    """
    if "_" not in doc_id:
        return None
    _, rest = doc_id.split("_", 1)
    m = _CC_RE.match(rest)
    if not m:
        return None
    cc, tail = m.group(1), m.group(2)
    km = _KIND_RE.match(tail)
    num = km.group(1) if km else tail
    digits = re.sub(r"\D", "", num)
    if not digits.lstrip("0"):
        return None
    keys = [f"{cc}{digits.lstrip('0')}"]
    if cc == "KR" and digits[:2] in ("10", "20") and len(digits) > 2:
        stripped = digits[2:].lstrip("0")
        if stripped:
            keys.append(f"{cc}{stripped}")
    return cc, keys


def _client():
    from google.cloud import bigquery

    get_secret("GOOGLE_APPLICATION_CREDENTIALS")  # 경로는 시크릿 (CLAUDE §1.9)
    return bigquery.Client()


# 정규화 키(country||앞0제거 숫자부)로 공개번호 조인. 결과셋은 @keys 로 좁혀 egress 를 최소화한다.
PUB_SQL = """
SELECT DISTINCT
  CONCAT(country_code,
         REGEXP_REPLACE(REGEXP_EXTRACT(publication_number, r'^[A-Z]{2}-([0-9]+)'), r'^0+', '')
  ) AS pubkey,
  family_id
FROM `patents-public-data.patents.publications`
WHERE country_code IN UNNEST(@ccs)
  AND family_id IS NOT NULL AND family_id != '-1'
  AND CONCAT(country_code,
         REGEXP_REPLACE(REGEXP_EXTRACT(publication_number, r'^[A-Z]{2}-([0-9]+)'), r'^0+', '')
      ) IN UNNEST(@keys)
"""

# 출원번호(KR 13자리 → 앞 '10' 제거한 11자리)로 조인. bq_family.py 와 동일 키.
APP_SQL = """
SELECT DISTINCT
  REGEXP_EXTRACT(application_number, r'KR-(\\d+)-') AS bq_app,
  family_id
FROM `patents-public-data.patents.publications`
WHERE country_code = 'KR'
  AND family_id IS NOT NULL AND family_id != '-1'
  AND REGEXP_EXTRACT(application_number, r'KR-(\\d+)-') IN UNNEST(@apps)
"""


def _dry_run(client, sql, params) -> int:
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=params
    )
    return client.query(sql, job_config=cfg).total_bytes_processed


def _run(client, sql, params) -> pd.DataFrame:
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(query_parameters=params)
    return client.query(sql, job_config=cfg).to_dataframe()


def build_family_map(
    corpus: Path = IR_CORPUS, out: Path = IR_FAMILY_MAP, dry_run: bool = False
) -> pd.DataFrame:
    from google.cloud import bigquery

    c = pd.read_parquet(corpus, columns=["doc_id", "source", "application_number"])
    c["application_number"] = c["application_number"].astype("string")

    # 공개번호 조인 대상: doc_id 에서 정규화 키를 뽑을 수 있고 국가가 대상에 든 문서.
    # 문서당 후보 키가 여럿일 수 있다(KR 접두 변형) — 전부 질의하고 조인 시 먼저 맞는 것을 쓴다.
    norm = c["doc_id"].map(normalize_pub)
    c["cc"] = [n[0] if n else None for n in norm]
    c["pubkeys"] = [n[1] if (n and n[0] in PUB_COUNTRIES) else None for n in norm]
    pubkeys = sorted({k for ks in c["pubkeys"].dropna() for k in ks})

    # 출원번호 조인 대상: 13자리 KR 출원번호 보유 문서 (공개번호로 이미 잡히는 것과 별개 축).
    app_targets = c[c["application_number"].str.len() == 13]
    apps = sorted(app_targets["application_number"].dropna().unique().tolist())
    bq_apps = [a[2:] for a in apps]  # 앞 '10' 제거

    ccs = list(PUB_COUNTRIES)
    pub_params = [
        bigquery.ArrayQueryParameter("ccs", "STRING", ccs),
        bigquery.ArrayQueryParameter("keys", "STRING", pubkeys),
    ]
    app_params = [bigquery.ArrayQueryParameter("apps", "STRING", bq_apps)]

    client = _client()
    if dry_run:
        pb = _dry_run(client, PUB_SQL, pub_params)
        ab = _dry_run(client, APP_SQL, app_params)
        tot = pb + ab
        print(f"[dry-run] 공개번호 조인 대상 {len(pubkeys):,}키 · 스캔 {pb/1e9:.2f} GB")
        print(f"[dry-run] 출원번호 조인 대상 {len(bq_apps):,}건 · 스캔 {ab/1e9:.2f} GB")
        print(f"[dry-run] 합계 {tot/1e9:.2f} GB · 추정비용 ${tot/1e12*6.25:.4f} (무료 1TB/월)")
        return pd.DataFrame()

    # --- 실행 -----------------------------------------------------------
    pub_df = _run(client, PUB_SQL, pub_params)            # pubkey · family_id
    app_df = _run(client, APP_SQL, app_params)            # bq_app · family_id
    # 정규화 키당 family_id 다중 시 사전순 최소 (결정성).
    pub_map = (
        pub_df.dropna().astype(str).sort_values("family_id")
        .drop_duplicates("pubkey").set_index("pubkey")["family_id"].to_dict()
    )
    app_map = (
        app_df.dropna().astype(str).sort_values("family_id")
        .drop_duplicates("bq_app").set_index("bq_app")["family_id"].to_dict()
    )

    # doc_id 단위로 병합: 공개번호 조인 우선(정답 문서 축), 없으면 출원번호 조인.
    rows = []
    for r in c.itertuples(index=False):
        fam, method = None, None
        pub_hit = next((pub_map[k] for k in (r.pubkeys or []) if k in pub_map), None)
        if pub_hit is not None:
            fam, method = pub_hit, "docdb-pub"
        elif isinstance(r.application_number, str) and len(r.application_number) == 13 \
                and r.application_number[2:] in app_map:
            fam, method = app_map[r.application_number[2:]], "docdb-app"
        else:
            fam, method = f"self:{r.doc_id}", "fallback-self"
        rows.append((r.doc_id, fam, method))

    fam_df = pd.DataFrame(rows, columns=["doc_id", "family_id", "method"])
    out.parent.mkdir(parents=True, exist_ok=True)
    fam_df.to_parquet(out, index=False)
    return fam_df


def load_family_map(path: Path = IR_FAMILY_MAP) -> dict[str, str]:
    """{doc_id: family_id}. fallback 포함(자기자신). 파일 없으면 예외 — 조용한 무효과 방지."""
    df = pd.read_parquet(path)
    return dict(zip(df["doc_id"], df["family_id"].astype(str), strict=True))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="스캔 바이트만 추정하고 종료")
    args = ap.parse_args()

    df = build_family_map(dry_run=args.dry_run)
    if args.dry_run:
        return 0
    n = len(df)
    by = df["method"].value_counts().to_dict()
    docdb = by.get("docdb-pub", 0) + by.get("docdb-app", 0)
    print(f"✓ ir_family_map {n:,}행 → {IR_FAMILY_MAP}")
    print(f"  DOCDB 조인 {docdb:,} ({docdb/n:.1%}) · fallback-self {by.get('fallback-self',0):,} "
          f"({by.get('fallback-self',0)/n:.1%})")
    print(f"  method 분해: {by}")
    print(f"  고유 family {df['family_id'].nunique():,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
