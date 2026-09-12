#!/usr/bin/env python3
"""PLAN-005 R0-CAL-0 — 분할의 단일 진입점 (읽기 전용 · 그래프를 바꾸지 않는다).

E-3(§20.2)의 본질은 *"채굴 범위 파일과 평가 질의 집합이 서로를 모른다"* 였다. 두 쪽이
각자 분할을 해석하는 한 언젠가 갈리고, 갈린 사실을 아무도 모른다. 그래서 분할을 읽는
자리를 여기 하나로 모으고, `assert_scope_agreement()` 가 둘을 한 곳에서 묶어 갈리는
순간 죽는다.

동결 sha 는 `report_stage7_remeasure.baseline_parquet()` 의 규율을 그대로 따른다 —
값을 코드에 적고, 어긋나면 조용히 진행하지 않고 SystemExit 한다.

**sha 가 둘인 이유** (실측 2026-09-12 · §20 2단계 F-4):

    split.csv      714dafe0…   이 저장소의 정본. MANIFEST 가 핀하고 공개본에 실린다.
    split.parquet  f93c18d2…   상류(sdkb-prior-art-paper) 원본. 채굴 산출물이 이 값을 적는다.

같은 논리적 분할인데 파일이 둘이다. 한쪽만 검사하면 다른 쪽이 갈려도 통과한다.

**봉인은 {test, test_b} 다** (사용자 승인 2026-09-12). `harvest_scope_dev_train.json` 의
`excluded_splits` 와 같다. 봉인 분할의 id 를 얻는 길은 이 모듈에 없다 — `scripts/seal.py`
가 원장과 함께 연다(D17 · 코드 게이트로만).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

SPLIT_CSV = ROOT / "benchmark" / "assets" / "split.csv"
SPLIT_CSV_SHA256 = "714dafe033afabf5185b3cc6f1a39bbc7099c4d71b414f81031e2b48e2165108"
UPSTREAM_PARQUET_SHA256 = "f93c18d28857f6304f692e821928b7189c5e525e88524e95a51ff31ca8961943"
HARVEST_SCOPE = ROOT / "data" / "sources" / "harvest_scope_dev_train.json"

SEALED = frozenset({"test", "test_b"})
OPEN = frozenset({"dev", "train"})
ALL_SPLITS = SEALED | OPEN

EXPECTED_ROWS = 1200
DOC_ID_SHAPE = re.compile(r"^(kr|us|jp|wo|cn|ep)_[A-Za-z0-9]+$")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_split(path: Path = SPLIT_CSV, *, verify: bool = True) -> dict[str, str]:
    """doc_id → split. 동결 sha 와 구조 계약을 함께 검사한다.

    verify=False 는 **테스트의 주입 픽스처 전용**이다. 실사용 경로에서 끄지 않는다.
    """
    path = Path(path)
    if verify:
        got = sha256_of(path)
        if got != SPLIT_CSV_SHA256:
            raise SystemExit(
                f"ERROR: 분할 파일의 sha256 이 동결값과 다르다: {path}\n"
                f"  동결 {SPLIT_CSV_SHA256}\n  실측 {got}"
            )
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"ERROR: 분할 파일이 비었다: {path}")
    missing = {"doc_id", "split"} - set(rows[0])
    if missing:
        raise SystemExit(f"ERROR: 분할 파일에 필수 열이 없다: {sorted(missing)}")
    mapping: dict[str, str] = {}
    for r in rows:
        d, s = r["doc_id"].strip(), r["split"].strip()
        if s not in ALL_SPLITS:
            raise SystemExit(f"ERROR: 알 수 없는 분할값 {s!r} (doc_id={d})")
        if d in mapping:
            raise SystemExit(f"ERROR: doc_id 중복: {d}")
        mapping[d] = s
    if verify and len(mapping) != EXPECTED_ROWS:
        raise SystemExit(f"ERROR: 분할 행 수가 {EXPECTED_ROWS} 가 아니다: {len(mapping)}")
    return mapping


def normalize_doc_id(x: str) -> str:
    """`patent:` 접두만 벗기고 모양을 검사한다.

    **매핑하지 않는다.** rej 질의 id 공간과 split.csv 의 doc_id 공간은 표기까지 동일함이
    실측됐다(2026-09-12 · 차집합 양방향 0). 그래서 이 함수의 일은 변환이 아니라, 언젠가
    두 공간이 갈리면 조용히 통과하지 않고 여기서 죽는 것이다.
    """
    s = str(x).strip()
    if s.startswith("patent:"):
        s = s[len("patent:"):]
    if not DOC_ID_SHAPE.match(s):
        raise ValueError(f"문서 식별자 모양이 아니다: {x!r}")
    return s


def queries_in(
    splits: str | Iterable[str],
    *,
    universe: Iterable[str] | None = None,
    split_map: dict[str, str] | None = None,
) -> set[str]:
    """해당 분할의 doc_id 집합. universe 를 주면 교집합."""
    want = {splits} if isinstance(splits, str) else set(splits)
    unknown = want - ALL_SPLITS
    if unknown:
        raise ValueError(f"알 수 없는 분할: {sorted(unknown)}")
    m = split_map if split_map is not None else load_split()
    ids = {d for d, s in m.items() if s in want}
    if universe is not None:
        ids &= {normalize_doc_id(u) for u in universe}
    return ids


def split_composition(
    ids: Iterable[str], *, split_map: dict[str, str] | None = None
) -> dict[str, int]:
    """분할별 계수. 분할표에 없는 id 는 버리지 않고 `_unknown` 으로 센다."""
    m = split_map if split_map is not None else load_split()
    c = Counter(m.get(i, "_unknown") for i in ids)
    return {k: c[k] for k in sorted(c)}


def assert_scope_agreement(
    scope_path: Path = HARVEST_SCOPE, *, split_map: dict[str, str] | None = None
) -> dict:
    """채굴 범위 파일과 분할표가 같은 것을 말하는지 한 곳에서 묶는다 — 이 교정의 심장.

    넷을 본다: ① dev∪train 집합 동일 ② excluded_splits == 봉인 ③ 상류 parquet sha
    ④ counts. 하나라도 어긋나면 SystemExit — 갈린 채로 계속 가는 것이 E-3 그 자체였다.
    """
    scope_path = Path(scope_path)
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    m = split_map if split_map is not None else load_split()

    scope_ids = set(scope.get("doc_ids") or [])
    open_ids = queries_in(OPEN, split_map=m)
    if scope_ids != open_ids:
        raise SystemExit(
            "ERROR: 채굴 범위와 dev∪train 이 다르다 — "
            f"범위만 {len(scope_ids - open_ids)}건 · 분할만 {len(open_ids - scope_ids)}건"
        )

    excluded = sorted(scope.get("excluded_splits") or [])
    if excluded != sorted(SEALED):
        raise SystemExit(f"ERROR: excluded_splits 가 봉인 분할과 다르다: {excluded}")

    upstream = ((scope.get("_source") or {}).get("sha256")) or ""
    if upstream != UPSTREAM_PARQUET_SHA256:
        raise SystemExit(
            "ERROR: 채굴 범위가 적은 상류 분할 sha 가 동결값과 다르다\n"
            f"  동결 {UPSTREAM_PARQUET_SHA256}\n  실측 {upstream}"
        )

    counts = {k: int(v) for k, v in (scope.get("counts") or {}).items()}
    actual = split_composition(scope_ids, split_map=m)
    if counts != actual:
        raise SystemExit(f"ERROR: 범위 counts 가 실측과 다르다: 기록 {counts} · 실측 {actual}")

    return {
        "scope_file": str(scope_path.relative_to(ROOT)),
        "scope_sha256": sha256_of(scope_path),
        "split_csv_sha256": SPLIT_CSV_SHA256,
        "upstream_parquet_sha256": UPSTREAM_PARQUET_SHA256,
        "open_splits": sorted(OPEN),
        "sealed_splits": sorted(SEALED),
        "open_queries": len(open_ids),
        "counts": actual,
    }
