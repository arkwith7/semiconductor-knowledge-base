#!/usr/bin/env python3
"""인용 선행기술 문헌의 **청구항 + 서지(출원일·IPC·CPC)** 수집 — 결함 A-2.

기존 `collect_cited_fulltext_full.py` 는 제목+초록만 받았다(fulltext_corpus). 선행기술
노드를 제대로 세우려면 우선일(filing_date)·분류(IPC/CPC)·청구항이 필요하다. 소스 라우팅:

  KR   → KIPRIS Plus biblio_detail   (청구항·서지·IPC/CPC 네이티브)
  US   → PatentsView Search API      (응용공개 자릿수 문제로 BigQuery 미스 → USPTO 정본)
  그외 외국(JP/WO/CN/EP/GB) → BigQuery Google Patents (claims+biblio 일괄 1쿼리)
  잔여  → EPO OPS                      (서지+초록만, 청구항 없음 — 폴백)

입력 : sdkb/data/patents/prior_art_edges.parquet 의 distinct cited (특허, is_npl=False)
출력 : data/patents/cited_enriched/<source>.parquet  (소스별 캐시, 재실행 시 재사용)

결정적·재개 가능. 같은 입력이면 같은 출력.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# 원래 경로(`sdkb-foresight-paper/.env`)는 그 저장소가 zip 으로 내려가면서 **사라졌다**.
# load_dotenv 는 없는 파일에 조용히 성공하므로, 그대로 두면 키가 비어 있는 채로
# API 가 전부 not_found 를 내고 그것이 "자원 부재"로 오독된다. 이 저장소의 .env 를 쓴다.
# 2026-08-09(F7): 2순위였던 하류 저장소 경로를 지웠다 — 남의 컴퓨터에 없다.
_env = Path(__file__).resolve().parents[1] / ".env"
if _env.exists():
    load_dotenv(_env)

EDGES = Path(__file__).resolve().parents[1] / "data" / "patents" / "prior_art_edges.parquet"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "patents" / "cited_enriched"
FOREIGN_BQ = {"JP", "WO", "CN", "EP", "GB"}   # US 는 PatentsView 로 뺀다

# 통일 출력 스키마 (소스 무관)
COLUMNS = [
    "cited_doc_id", "country", "kind", "source",
    "title", "abstract", "claims", "n_claims",
    "filing_date", "ipc", "cpc", "applicants", "resolved", "note",
]


def cited_population() -> pd.DataFrame:
    """distinct 인용 특허 (all ⊇ examiner). 노드로 세울 전체 대상."""
    pa = pd.read_parquet(EDGES)
    al = pa[(pa["source_type"] == "all") & (~pa["is_npl"])].drop_duplicates("cited_id")
    return al[["cited_doc_id", "cited_country", "cited_kind", "cited_raw"]].reset_index(drop=True)


def population_from_file(path: Path) -> pd.DataFrame:
    """CR-008 — 식별자 목록에서 만든 모집단 표를 그대로 쓴다 (B층).

    A층은 `prior_art_edges.parquet` 에서 모집단을 읽지만, B층 문헌은 그 표에 **없고
    넣을 수도 없다** — 질의–인용 대응은 이관되지 않았다(CR-008 비목표 ⓒ). 대신
    `sdkb/scripts/build_b_layer_cited_ids.py` 가 같은 컬럼의 표를 만든다.

    라우팅·수집 로직은 이 함수 아래로 **한 줄도 달라지지 않는다** — 바뀌는 것은 모집단뿐이다.
    """
    df = pd.read_parquet(path)
    df = df[~df["is_npl"]].drop_duplicates("cited_id")
    return df[["cited_doc_id", "cited_country", "cited_kind", "cited_raw"]].reset_index(drop=True)


def _doc_key(doc_id: str) -> tuple[str, str] | None:
    """'US-P-20190348292' → ('US', '20190348292')  (선행 0 유지)."""
    m = re.match(r"([A-Z]{2})-[A-Z]-([0-9A-Z]+)", str(doc_id))
    return (m.group(1), m.group(2)) if m else None


# ── BigQuery (JP/WO/CN/EP/GB) ─────────────────────────────────────────
def collect_bigquery(pop: pd.DataFrame) -> pd.DataFrame:
    from google.cloud import bigquery

    proj = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    client = bigquery.Client(project=proj)
    sub = pop[pop["cited_country"].isin(FOREIGN_BQ)].copy()
    sub["key"] = sub["cited_doc_id"].apply(
        lambda d: (lambda k: f"{k[0]}-{k[1].lstrip('0')}" if k else None)(_doc_key(d))
    )
    keys = sorted(k for k in sub["key"].dropna().unique())
    print(f"[bq] 대상 {len(sub)} · 매칭키 {len(keys)}")

    # 한 쿼리로 전량. claims_localized(거대 컬럼) 스캔이 비용 대부분 — 반드시 1회.
    q = """
    WITH tgt AS (
      SELECT k, SPLIT(k,'-')[OFFSET(0)] cc, SPLIT(k,'-')[OFFSET(1)] num
      FROM UNNEST(@keys) k
    )
    SELECT
      t.k AS key,
      ANY_VALUE(p.country_code) country,
      ANY_VALUE(p.filing_date) filing_date,
      ANY_VALUE((SELECT text FROM UNNEST(p.title_localized)    ORDER BY (language='en') DESC LIMIT 1)) title,
      ANY_VALUE((SELECT text FROM UNNEST(p.abstract_localized) ORDER BY (language='en') DESC LIMIT 1)) abstract,
      ANY_VALUE((SELECT text FROM UNNEST(p.claims_localized)   ORDER BY (language='en') DESC LIMIT 1)) claims,
      ANY_VALUE((SELECT STRING_AGG(DISTINCT code,'|') FROM UNNEST(p.ipc)) ) ipc,
      ANY_VALUE((SELECT STRING_AGG(DISTINCT code,'|') FROM UNNEST(p.cpc)) ) cpc
    FROM `patents-public-data.patents.publications` p
    JOIN tgt t
      ON p.country_code = t.cc
     AND LTRIM(REGEXP_EXTRACT(p.publication_number, r'-([0-9]+)-'),'0') = t.num
    GROUP BY t.k
    """
    jc = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("keys", "STRING", keys)],
        use_query_cache=False,
    )
    job = client.query(q, job_config=jc)
    res = pd.DataFrame([dict(r) for r in job.result()])
    print(f"[bq] 스캔 {job.total_bytes_processed/1e9:.1f}GB "
          f"(~${job.total_bytes_processed/1e12*5:.2f}) · 매칭 {len(res)}/{len(keys)}")

    key2doc = dict(zip(sub["key"], sub["cited_doc_id"]))
    kind = dict(zip(sub["cited_doc_id"], sub["cited_kind"]))
    rows = []
    matched = set(res["key"]) if len(res) else set()
    for _, r in res.iterrows():
        doc = key2doc.get(r["key"])
        claims = r.get("claims") or ""
        rows.append({
            "cited_doc_id": doc, "country": r.get("country"), "kind": kind.get(doc),
            "source": "bigquery", "title": r.get("title"), "abstract": r.get("abstract"),
            "claims": claims, "n_claims": _count_claims(claims),
            "filing_date": _fmt_date(r.get("filing_date")), "ipc": r.get("ipc"),
            "cpc": r.get("cpc"), "applicants": None, "resolved": bool(claims or r.get("abstract")),
            "note": "",
        })
    # 미매칭도 기록(정직) — 나중에 EPO 폴백 대상
    for _, r in sub[~sub["key"].isin(matched)].iterrows():
        rows.append(_miss_row(r["cited_doc_id"], r["cited_country"], r["cited_kind"],
                              "bigquery", "no_match"))
    return pd.DataFrame(rows, columns=COLUMNS)


def _count_claims(text) -> int:
    if not isinstance(text, str) or not text.strip():
        return 0
    return len(re.findall(r"(?m)^\s*\d+\s*[\.\)]", text)) or 1


def _fmt_date(v) -> str | None:
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) == 8 and s != "00000000":
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def _miss_row(doc, country, kind, source, note) -> dict:
    return {c: None for c in COLUMNS} | {
        "cited_doc_id": doc, "country": country, "kind": kind,
        "source": source, "resolved": False, "note": note,
    }


# ── KIPRIS (KR) ───────────────────────────────────────────────────────
def _kr_fmt_date(v) -> str | None:
    s = re.sub(r"\D", "", str(v or ""))
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 and s != "00000000" else None


def collect_kipris(pop: pd.DataFrame) -> pd.DataFrame:
    import json as _json
    import enrich_unresolved as eu
    from kipris_dataset.citation_norm import parse as parse_citation
    from kipris_dataset.kipris import KiprisClient

    client = KiprisClient(api_key=os.getenv("KIPRIS_API_KEY"))
    sub = pop[pop["cited_country"] == "KR"].reset_index(drop=True)
    cache = OUT_DIR / "kipris.jsonl"          # 재개: 이미 처리한 doc 은 건너뛴다
    done: dict[str, dict] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            r = _json.loads(line); done[r["cited_doc_id"]] = r
    print(f"[kipris] 대상 {len(sub)} · 캐시 {len(done)}")

    def resolve_app(raw: str) -> str:
        cit = parse_citation(raw)
        if cit.kind == "grant":
            for cand in eu._kr_register_candidates(cit.serial):
                it = eu._search_one(client, {"registerNumber": cand})
                if it and it.get("applicationNumber"):
                    return eu._s(it["applicationNumber"])
            return ""
        open_no = cit.serial if len(cit.serial) == 13 else cit.serial.zfill(13)
        it = eu._search_one(client, {"openNumber": open_no})
        return eu._s(it.get("applicationNumber")) if it else ""

    fh = cache.open("a")
    for i, r in sub.iterrows():
        doc = r["cited_doc_id"]
        if doc in done:
            continue
        raw = r["cited_raw"]  # 권위 있는 인용 문자열 (kind 판별 정확)
        try:
            app = resolve_app(raw)
            row = _miss_row(doc, "KR", r["cited_kind"], "kipris", "not_found")
            if app:
                bib = eu._biblio(client, app)
                if bib:
                    claims = [eu._s(c.get("claim") or c.get("claimText"))
                              for c in eu._to_list((bib.get("claimInfoArray") or {}).get("claimInfo"))]
                    claims = [c for c in claims if c]
                    summ = (bib.get("biblioSummaryInfoArray") or {}).get("biblioSummaryInfo")
                    summ = summ[0] if isinstance(summ, list) else (summ or {})
                    abstract = eu._extract_abstract(bib)
                    row = {c: None for c in COLUMNS} | {
                        "cited_doc_id": doc, "country": "KR", "kind": r["cited_kind"],
                        "source": "kipris", "title": eu._extract_title(bib), "abstract": abstract,
                        "claims": "\n".join(claims), "n_claims": len(claims),
                        "filing_date": _kr_fmt_date(summ.get("applicationDate")),
                        "ipc": eu._extract_ipc(bib), "cpc": None, "applicants": None,
                        "resolved": bool(claims or abstract),
                        "note": "" if claims else "no_claims",
                    }
        except Exception as e:  # noqa: BLE001 — 개별 실패가 배치를 멈추지 않게
            row = _miss_row(doc, "KR", r["cited_kind"], "kipris", f"error:{type(e).__name__}")
        fh.write(_json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
        done[doc] = row
        if (i + 1) % 100 == 0:
            print(f"  [kipris] {i+1}/{len(sub)} 처리")
    fh.close()
    return pd.DataFrame(list(done.values()), columns=COLUMNS)


# ── BigQuery (US) — 청구항 보유. Google 은 US 응용공개를 연도+시리얼6자리로 저장 ──
def _us_bq_key(doc_id: str, kind: str) -> str | None:
    k = _doc_key(doc_id)
    if not k:
        return None
    _, digits = k
    if kind == "grant":
        return f"US-{digits.lstrip('0')}"            # US-10224240
    # 응용공개: 'YYYY'+7자리 시리얼 → Google 은 'YYYY'+시리얼 뒤 6자리
    if len(digits) >= 11:
        return f"US-{digits[:4]}{digits[4:][-6:]}"   # 20190348292 → US-2019348292
    return f"US-{digits.lstrip('0')}"


def collect_bigquery_us(pop: pd.DataFrame) -> pd.DataFrame:
    from google.cloud import bigquery

    client = bigquery.Client(project=os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT"))
    sub = pop[pop["cited_country"] == "US"].copy()
    sub["key"] = [_us_bq_key(d, k) for d, k in zip(sub["cited_doc_id"], sub["cited_kind"])]
    keys = sorted(k for k in sub["key"].dropna().unique())
    print(f"[bq-us] 대상 {len(sub)} · 매칭키 {len(keys)}")

    q = """
    WITH tgt AS (SELECT k, SPLIT(k,'-')[OFFSET(1)] num FROM UNNEST(@keys) k)
    SELECT t.k AS key,
      ANY_VALUE(p.filing_date) filing_date,
      ANY_VALUE((SELECT text FROM UNNEST(p.title_localized)    LIMIT 1)) title,
      ANY_VALUE((SELECT text FROM UNNEST(p.abstract_localized) LIMIT 1)) abstract,
      ANY_VALUE((SELECT text FROM UNNEST(p.claims_localized)   LIMIT 1)) claims,
      ANY_VALUE((SELECT STRING_AGG(DISTINCT code,'|') FROM UNNEST(p.ipc))) ipc,
      ANY_VALUE((SELECT STRING_AGG(DISTINCT code,'|') FROM UNNEST(p.cpc))) cpc
    FROM `patents-public-data.patents.publications` p
    JOIN tgt t ON p.country_code='US'
      AND LTRIM(REGEXP_EXTRACT(p.publication_number, r'-([0-9]+)-'),'0') = t.num
    GROUP BY t.k
    """
    jc = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("keys", "STRING", keys)],
        use_query_cache=False)
    job = client.query(q, job_config=jc)
    res = pd.DataFrame([dict(r) for r in job.result()])
    print(f"[bq-us] 스캔 {job.total_bytes_processed/1e9:.1f}GB "
          f"(~${job.total_bytes_processed/1e12*5:.2f}) · 매칭 {len(res)}/{len(keys)}")
    key2doc = dict(zip(sub["key"], sub["cited_doc_id"]))
    kind = dict(zip(sub["cited_doc_id"], sub["cited_kind"]))
    matched = set(res["key"]) if len(res) else set()
    rows = []
    for _, r in res.iterrows():
        doc = key2doc.get(r["key"])
        claims = r.get("claims") if isinstance(r.get("claims"), str) else ""
        abstract = r.get("abstract") if isinstance(r.get("abstract"), str) else ""
        rows.append({
            "cited_doc_id": doc, "country": "US", "kind": kind.get(doc), "source": "bigquery",
            "title": r.get("title"), "abstract": abstract, "claims": claims,
            "n_claims": _count_claims(claims), "filing_date": _fmt_date(r.get("filing_date")),
            "ipc": r.get("ipc"), "cpc": r.get("cpc"), "applicants": None,
            "resolved": bool(claims or abstract), "note": "" if claims else "no_claims"})
    for _, r in sub[~sub["key"].isin(matched)].iterrows():
        rows.append(_miss_row(r["cited_doc_id"], "US", r["cited_kind"], "bigquery", "no_match"))
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    choices=["bigquery", "bigquery_us", "patentsview", "kipris", "epo"])
    # CR-008 — 주면 그 표를 모집단으로 쓴다. 없으면 기존 동작 그대로(A층).
    ap.add_argument("--population", type=Path, default=None,
                    help="식별자 목록에서 만든 모집단 parquet (B층)")
    # 산출 파일명 꼬리표. `--population` 을 주면서 이것을 비우면 A층 캐시를 덮어쓴다 —
    # bigquery.parquet 은 append 가 아니라 **전량 재작성**이기 때문이다. 그래서 강제한다.
    ap.add_argument("--tag", default=None, help="산출 파일명 접미사 (예: b_layer)")
    args = ap.parse_args()
    if args.population is not None and not args.tag:
        print("ERROR: --population 을 주면 --tag 도 줘야 한다 — "
              "없으면 A층 캐시(bigquery.parquet 등)를 덮어쓴다", file=sys.stderr)
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pop = (population_from_file(args.population) if args.population is not None
           else cited_population())

    if args.source == "bigquery":
        df = collect_bigquery(pop)
    elif args.source == "bigquery_us":
        df = collect_bigquery_us(pop)
    elif args.source == "kipris":
        df = collect_kipris(pop)
    else:
        print(f"[{args.source}] 아직 미구현 — 다음 단계"); return 1

    out = OUT_DIR / (f"{args.source}_{args.tag}.parquet" if args.tag else f"{args.source}.parquet")
    df.to_parquet(out, index=False)
    ok = int(df["resolved"].sum())
    cl = int((df["n_claims"].fillna(0) > 0).sum())
    print(f"✓ {args.source}: {len(df)}행 → {out}")
    print(f"  resolved={ok}  청구항보유={cl}  "
          f"filing_date={int(df['filing_date'].notna().sum())}  "
          f"cpc={int(df['cpc'].notna().sum())}  ipc={int(df['ipc'].notna().sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
