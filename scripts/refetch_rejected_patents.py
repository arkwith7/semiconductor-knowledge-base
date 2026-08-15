#!/usr/bin/env python3
"""공개본 거절특허 데이터셋에 KIPRIS 원문을 다시 채운다 (CR-015 출력 (2) · CR-016 §2 (2)).

공개본은 `abstract`·`claim1`·`claims_full[].text` 를 **빈 문자열**로 담는다 — KIPRIS 학술이용
조건이 원문 재배포를 허용하지 않기 때문이다. 스키마·식별자·IPC·날짜·정답 인용 라벨은 그대로
있으므로, 본인 키만 있으면 이 스크립트가 같은 파일을 되돌려 놓는다.

**추출 규칙을 새로 쓰지 않는다.** 원본 데이터셋을 만든 수집기의 함수를 그대로 호출한다 —
`expand_dataset_via_api._abstract_from_biblio` · `._claim1_from_biblio` ·
`enrich_targets_b3_b5._extract_claims_full`. 규칙을 다시 쓰면 복원본이 정본과 달라지고,
그 순간 아래 sha256 대조가 무의미해진다.

**정직한 한계 하나.** 원본의 `abstract` 는 검색 응답의 `astrtCont` 를 **먼저** 쓰고 서지
응답을 폴백으로 썼다(`expand_dataset_via_api.py:2442`). 이 스크립트는 출원번호로 서지만
조회하므로 두 값이 다른 건에서는 복원본이 원본과 달라질 수 있다. **그래서 성공 판정을
"돌았다"가 아니라 sha256 대조로 둔다** — 어긋나면 어긋난 건수를 리포트에 적는다.

CLI:
    python scripts/refetch_rejected_patents.py                 # 빈 필드만 채운다
    python scripts/refetch_rejected_patents.py --dry-run       # 무엇이 비었는지만 센다
    python scripts/refetch_rejected_patents.py --limit 5       # 스모크
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from expand_dataset_via_api import (  # noqa: E402
    CallBudget,
    _abstract_from_biblio,
    _claim1_from_biblio,
    get_biblio,
)
from enrich_targets_b3_b5 import _extract_claims_full  # noqa: E402
from kipris_dataset.kipris import KiprisClient  # noqa: E402

DATASET = ROOT / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
# 복원본이 가는 곳. **추적되지 않는다**(.gitignore) — 위 파일은 원문이 비어 있는 공개본이고,
# 그것을 제자리에서 채우면 `git commit -a` 한 번에 KIPRIS 원문이 공개된다.
FULLTEXT_NAME = "semiconductor_industry_rejected_patents.fulltext.jsonl"
CACHE = ROOT / "data" / "interim" / "refetch_biblio_cache.jsonl"
REPORT = ROOT / "data" / "reports" / "refetch_rejected_patents.json"

# 복원 성공의 판정선. 값을 비우기 전 정본의 서명이다 — 공개본을 만든 커밋에서 측정했다.
# 이 값을 결과를 보고 고치면 대조 자체가 사라진다.
CANONICAL_SHA256 = "fc142f515b3f3e5b235efba2f4bc075e583275ae0f090813928563de176b24e9"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.open(encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
            out[rec["application_number"]] = rec["biblio"]
    return out


def append_cache(app_no: str, biblio: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"application_number": app_no, "biblio": biblio},
                            ensure_ascii=False) + "\n")


def missing_fields(tp: dict) -> list[str]:
    out = []
    if not (tp.get("abstract") or "").strip():
        out.append("abstract")
    if not (tp.get("claim1") or "").strip():
        out.append("claim1")
    claims = tp.get("claims_full") or []
    if claims and not any((c.get("text") or "").strip() for c in claims):
        out.append("claims_full")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--in-place", action="store_true",
                    help="추적 파일을 제자리에서 갱신한다(비공개 개발 리포 전용).")
    ap.add_argument("--limit", type=int, default=None, help="앞의 N 건만 (스모크)")
    ap.add_argument("--dry-run", action="store_true", help="비어 있는 것만 세고 끝낸다")
    ap.add_argument("--max-calls", type=int, default=5000)
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.dataset.open(encoding="utf-8") if line.strip()]
    todo = [(i, r) for i, r in enumerate(rows) if missing_fields(r.get("target_patent") or {})]
    print(f"[refetch] {len(rows)}행 중 채울 것 {len(todo)}행")
    if args.dry_run:
        from collections import Counter
        c = Counter(f for _, r in todo for f in missing_fields(r["target_patent"]))
        for k, v in sorted(c.items()):
            print(f"      {k}: {v}")
        return 0
    if not todo:
        digest = sha256_of(args.dataset)
        print(f"[refetch] 채울 것이 없다. sha256 {digest}")
        print("[refetch] 정본 일치" if digest == CANONICAL_SHA256 else
              f"[refetch] ⚠ 정본과 불일치 (기대 {CANONICAL_SHA256})")
        return 0

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("KIPRIS_API_KEY")
    if not api_key:
        raise SystemExit(
            "ERROR: KIPRIS_API_KEY 가 없다. .env 에 넣거나 환경변수로 준다.\n"
            "       키는 https://plus.kipris.or.kr 에서 발급한다 — 우리가 줄 수 있는 것은 절차다."
        )

    client = KiprisClient(api_key=api_key)
    budget = CallBudget(args.max_calls)
    cache = load_cache()
    if args.limit:
        todo = todo[: args.limit]

    filled = {"abstract": 0, "claim1": 0, "claims_full": 0}
    failed: list[str] = []
    for n, (idx, row) in enumerate(todo, 1):
        tp = row["target_patent"]
        app_no = str(tp.get("application_number") or "")
        bib = cache.get(app_no)
        if bib is None:
            bib = get_biblio(client, budget, app_no)
            if bib is None:
                failed.append(app_no)
                continue
            append_cache(app_no, bib)
        want = missing_fields(tp)
        if "abstract" in want:
            v = _abstract_from_biblio(bib)
            if v:
                tp["abstract"] = v
                filled["abstract"] += 1
        if "claim1" in want:
            v = _claim1_from_biblio(bib)
            if v:
                tp["claim1"] = v
                filled["claim1"] += 1
        if "claims_full" in want:
            got = _extract_claims_full(bib)
            if got:
                by_no = {c["claim_no"]: c["text"] for c in got}
                hit = 0
                for c in tp["claims_full"]:
                    t = by_no.get(c.get("claim_no"))
                    if t:
                        c["text"] = t
                        hit += 1
                if hit:
                    filled["claims_full"] += 1
        if n % 50 == 0:
            print(f"      {n}/{len(todo)} · 호출 {budget.used}")

    # **복원본은 추적 파일을 덮지 않는다(2026-08-15).** 예전에는 args.dataset 을 제자리에서
    # 갈아치웠는데, 그 파일은 git 추적 대상이라 재인출 직후 `git status` 가 원문 1,000행을
    # 변경으로 잡는다 — `git commit -a` 한 번이면 KIPRIS 원문이 공개 리포에 올라간다.
    # 실제로 깨끗한 클론에서 재현했다(2026-08-15 · 1,000 insertions).
    # 그래서 기본 출력은 **gitignore 된 옆 파일**이고, 소비자(ingest)가 그것을 먼저 읽는다.
    # 제자리 갱신이 필요하면 --in-place 로 명시한다 — 비공개 개발 리포의 용법이다.
    out = args.dataset if args.in_place else args.dataset.with_name(FULLTEXT_NAME)
    tmp = out.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(out)
    args.dataset = out
    if not args.in_place:
        print(f"[refetch] 원문은 추적되지 않는 옆 파일에 쓴다 → {out.name}")

    digest = sha256_of(args.dataset)
    match = digest == CANONICAL_SHA256
    still = sum(1 for r in rows if missing_fields(r.get("target_patent") or {}))
    print(f"\n[refetch] 채움 {filled} · 실패 {len(failed)} · 여전히 빈 행 {still}")
    print(f"[refetch] sha256 {digest}")
    print("[refetch] ✅ 정본과 바이트 동일" if match else
          f"[refetch] ⚠ 정본과 불일치 — 기대 {CANONICAL_SHA256}\n"
          "          원인 후보: 초록 원천 차이(astrtCont ↔ 서지 폴백 · 모듈 docstring) · "
          "미해소 문헌 · KIPRIS 응답 변화. 어긋난 채로 쓰지 말고 이 값을 보고한다.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "rows_needing_fill": len(todo),
        "filled": filled,
        "failed_application_numbers": failed,
        "rows_still_empty": still,
        "sha256": digest,
        "canonical_sha256": CANONICAL_SHA256,
        "byte_identical": match,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[refetch] 리포트 → {REPORT.relative_to(ROOT)}")
    return 0 if match or still == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
