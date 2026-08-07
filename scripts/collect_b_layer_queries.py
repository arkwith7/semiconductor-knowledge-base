#!/usr/bin/env python3
"""CR-012 ⓐ — B층 확증분할 질의 200건의 서지·청구항 수집 (KIPRIS Plus).

왜 새 수집기인가. 기존 `collect_cited_biblio_claims.py`(paper_data)는 **인용 문헌**
수집기다. 입력이 인용 표기(`KR1020090041506 A`)라서 출원번호를 먼저 **해소**해야 하고
(`resolve_app` — registerNumber/openNumber 검색 1회 추가), 출력 스키마가
`cited_doc_id` 중심이다. B층 질의 200 은 그 둘 다 필요 없다 —

  ① 하류 이관 파일이 **출원번호 그 자체**를 준다(13자리 · 200/200). 해소 단계가 없다.
  ② 질의는 CitedPatent 가 아니라 RejectedPatent 다. `cited_doc_id` 를 만들면 이름이
     의미와 달라진다(CLAUDE.md §1.3).

그래서 해소를 뺀 직행 경로만 새로 쓰고, **API 호출과 파싱은 전부 기존 정본을 재사용**한다
(`paper_data/scripts/enrich_unresolved.py` 의 `_biblio`·`_extract_*`). 파서를 새로 쓰면
같은 KIPRIS 응답을 두 규칙으로 읽게 되어 A층/B층이 비균질해진다.

입력 : 하류 이관 파일 `upstream/handoff/CR-012-b-query-ids.txt` (200행 · sha256 대조 강제)
출력 : data/patents/b_layer_queries_raw.jsonl  (**gitignore** — KIPRIS 비재배포 원문 + 논문 평가자산)
       data/reports/b_layer_query_collection.json  (집계만 · 커밋)

재개 가능·멱등. 이미 받은 출원번호는 건너뛴다. 같은 입력 → 같은 출력(타임스탬프 없음).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PD = Path("/home/arkwith/Dev/paper_data")

# API 호출·응답 파싱의 정본은 paper_data 에 있다. 복사하지 않고 가져다 쓴다
# (decompose_corpus.py 가 cited_enriched 를 읽는 것과 같은 방식의 의존이다).
sys.path.insert(0, str(PD / "scripts"))
sys.path.insert(0, str(PD / "src"))
import enrich_unresolved as eu  # noqa: E402
from kipris_dataset.kipris import KiprisClient, OP_BIBLIO_DETAIL  # noqa: E402

DEFAULT_IDS = Path(
    "/home/arkwith/Dev/SKKU/sdkb-prior-art-paper/upstream/handoff/CR-012-b-query-ids.txt"
)
OUT_JSONL = ROOT / "data" / "patents" / "b_layer_queries_raw.jsonl"
OUT_REPORT = ROOT / "data" / "reports" / "b_layer_query_collection.json"

# 이관 파일의 동결 서명 (CR-012 §4ⓐ · 하류 HANDOFF-QUEUE §1.13 재검증).
# 불일치는 경고가 아니라 **중단**이다 — 파일이 조용히 바뀌면 확증분할 200 이 거짓이 된다
# (CR-008 `build_b_layer_cited_ids.py` 가 세운 규율 그대로).
EXPECTED_SHA256 = "ef4ad03c2734af4212209516c05064b1550bea478f1f79bc72f3e2f14bac60e5"

# KIPRIS 는 초당 75 요청까지 받지만, 200 건짜리 배치에 그 상한을 쓸 이유가 없다.
MIN_INTERVAL = 0.5


def load_ids(path: Path) -> list[str]:
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != EXPECTED_SHA256:
        raise SystemExit(
            f"이관 파일 서명 불일치 — 중단.\n  기대 {EXPECTED_SHA256}\n  실제 {got}\n"
            f"  {path}\n하류와 동일한 200 건인지 확인하기 전에는 수집하지 않는다."
        )
    ids = [ln.strip() for ln in raw.decode().splitlines() if ln.strip()]
    if len(ids) != len(set(ids)):
        raise SystemExit("이관 파일에 중복 출원번호가 있다 — 중단.")
    bad = [i for i in ids if not (i.isdigit() and len(i) == 13)]
    if bad:
        raise SystemExit(f"13자리 숫자가 아닌 출원번호 {len(bad)}건 — 중단. 예: {bad[:3]}")
    return ids


def _claim_blob(bib: dict) -> tuple[str, int]:
    """청구항 배열 → 개행으로 이은 한 덩어리 + 건수.

    인용 문헌(CR-011)이 쓴 형태와 **같게** 둔다. 하류 분해기는 이 덩어리를
    `split_claims()` 로 다시 가르는데, 여기서 형태를 바꾸면 같은 분해기가 A층 인용과
    B층 질의를 다르게 읽는다.
    """
    arr = (bib.get("claimInfoArray") or {}).get("claimInfo")
    texts = [eu._s(c.get("claim") or c.get("claimText")) for c in eu._to_list(arr)]
    texts = [t for t in texts if t]
    return "\n".join(texts), len(texts)


def _fmt_date(v) -> str:
    """KIPRIS 'YYYYMMDD' / 'YYYY.MM.DD' → ISO. 빈 값은 빈 문자열."""
    s = "".join(ch for ch in str(v or "") if ch.isdigit())
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s != "00000000" else ""


def collect(ids: list[str], limit: int | None = None) -> list[dict]:
    done: dict[str, dict] = {}
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["application_number"]] = r

    todo = [i for i in ids if i not in done]
    if limit:
        todo = todo[:limit]
    print(f"[collect] 대상 {len(ids)} · 캐시 {len(done)} · 이번 수집 {len(todo)}")

    if todo:
        key = os.environ.get("KIPRIS_API_KEY")
        if not key:
            raise SystemExit("KIPRIS_API_KEY 없음 — .env 또는 환경변수를 확인하라.")
        client = KiprisClient(api_key=key, min_request_interval=MIN_INTERVAL)
        OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with OUT_JSONL.open("a") as fh:
            for n, an in enumerate(todo, 1):
                row = {"application_number": an, "resolved": False, "note": "not_found",
                       "invention_title": "", "abstract": "", "claims": "", "n_claims": 0,
                       "filing_date": "", "ipc_codes": "",
                       "examination_status": "", "register_status": ""}
                try:
                    bib = eu._biblio(client, an)
                    if bib:
                        summ = (bib.get("biblioSummaryInfoArray") or {}).get("biblioSummaryInfo")
                        summ = summ[0] if isinstance(summ, list) else (summ or {})
                        claims, n_claims = _claim_blob(bib)
                        abstract = eu._extract_abstract(bib)
                        row = {
                            "application_number": an,
                            "invention_title": eu._extract_title(bib),
                            "abstract": abstract,
                            "claims": claims,
                            "n_claims": n_claims,
                            "filing_date": _fmt_date(summ.get("applicationDate")),
                            "ipc_codes": eu._extract_ipc(bib),
                            # shapes_patent.ttl 은 RejectedPatent 마다 examinationStatus 를
                            # 요구한다(하류 bibliographic_shape.ttl:53 도 같다). KIPRIS 의
                            # finalDisposal 이 그 값이다 — "거절결정(재심사)" 처럼.
                            "examination_status": eu._s(summ.get("finalDisposal")),
                            # 권위 원천 대조(§1.3). 하류는 이 200 건이 거절특허라고 말했고,
                            # 상류는 그 말을 KIPRIS 에서 **독립적으로** 확인한다. 어긋나면
                            # RejectedPatent 타입 자체가 거짓이 되므로 빌드가 중단한다.
                            "register_status": eu._s(summ.get("registerStatus")),
                            "resolved": bool(claims or abstract),
                            "note": "" if claims else "no_claims",
                        }
                except Exception as e:  # noqa: BLE001 — 개별 실패가 배치를 멈추지 않게
                    row["note"] = f"error:{type(e).__name__}"
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                done[an] = row
                if n % 25 == 0:
                    print(f"  [collect] {n}/{len(todo)} …", flush=True)

    # 이관 파일 순서를 정본으로 삼는다 — 수집 순서가 산출 순서를 흔들면 안 된다.
    return [done[i] for i in ids if i in done]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    ap.add_argument("--limit", type=int, default=None, help="앞의 N 건만 (스모크)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    ids = load_ids(args.ids)
    rows = collect(ids, args.limit)

    n = len(rows)
    have_claims = sum(1 for r in rows if r["n_claims"] > 0)
    have_abs = sum(1 for r in rows if r["abstract"])
    have_date = sum(1 for r in rows if r["filing_date"])
    have_ipc = sum(1 for r in rows if r["ipc_codes"])
    have_exam = sum(1 for r in rows if r.get("examination_status"))
    reg_status = Counter(r.get("register_status") or "(빈값)" for r in rows)
    failed = [{"application_number": r["application_number"], "note": r["note"]}
              for r in rows if not r["resolved"]]

    report = {
        "cr": "CR-012",
        "input_ids": str(args.ids),
        "input_sha256": EXPECTED_SHA256,
        "requested": len(ids),
        "collected": n,
        "resolved": n - len(failed),
        "with_claims": have_claims,
        "with_abstract": have_abs,
        "with_filing_date": have_date,
        "with_ipc": have_ipc,
        "with_examination_status": have_exam,
        "register_status_distribution": dict(reg_status),
        "claims_per_patent_mean": round(sum(r["n_claims"] for r in rows) / n, 2) if n else 0,
        "unresolved": failed,
        "note": "출원번호 직행 조회(getBibliographyDetailInfoSearch). 인용 표기 해소 단계 없음 — "
                "하류 이관 파일이 출원번호 자체를 준다.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"\n✓ {n}/{len(ids)}건 → {OUT_JSONL.relative_to(ROOT)}")
    print(f"  청구항 보유 : {have_claims}/{n}   초록 {have_abs}/{n}   "
          f"출원일 {have_date}/{n}   IPC {have_ipc}/{n}   심사상태 {have_exam}/{n}")
    print(f"  등록상태(권위 원천 대조) : {dict(reg_status)}")
    print(f"  미해소      : {len(failed)}건")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
