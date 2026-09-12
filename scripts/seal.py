#!/usr/bin/env python3
"""PLAN-005 R0-CAL-0 — 봉인 분할 개봉 원장 (D17 · 코드 게이트로만).

봉인은 규약 문서가 아니라 **코드가** 지킨다(사용자 결정 D17 — CLAUDE.md 는 건드리지
않는다). 봉인 분할의 id 를 얻는 길은 이 함수 하나뿐이고, 그 길은 기본적으로 막혀 있다.
열려면 `allow=True` 와 사유를 **함께** 줘야 하며, 열린 사실은 추가 전용 원장에 남는다.

**CLI 에 `--unseal` 플래그를 만들지 않는다.** 에이전트도 CI 도 우연히 열 수 없어야 한다
(§20.7). `allow` 는 파이썬 호출자만 넘길 수 있고, 넘겼다는 것은 사람이 그 줄을 썼다는 뜻이다.

원장 서식은 상류 `benchmark/assets/seal_access.jsonl` 25행과 **같은 6키**다 — 서식을 새로
만들면 두 원장을 나란히 읽을 수 없다.

원장 파일이 없는 것은 결함이 아니라 **0행(아무것도 열지 않았다)** 이다. 그래서 빈 파일을
미리 커밋하지 않는다.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.splits import ROOT, SEALED, SPLIT_CSV, load_split, queries_in, sha256_of

LEDGER = ROOT / "data" / "reports" / "seal_access.jsonl"
REQUIRED_KEYS = ("opened_at", "commit", "caller", "file", "sha256", "reason")


def _head_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def ledger_rows(path: Path = LEDGER) -> list[dict]:
    """원장 행. 파일 부재는 0행이며 정상 상태다."""
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"ERROR: 봉인 원장 {ln}행이 JSON 이 아니다: {e}")
    return rows


def open_sealed(
    split: str,
    reason: str,
    *,
    allow: bool = False,
    caller: str | None = None,
    file: Path | None = None,
    ledger: Path = LEDGER,
    split_map: dict[str, str] | None = None,
) -> set[str]:
    """봉인 분할의 doc_id 를 연다. 기본은 열리지 않는다."""
    if split not in SEALED:
        raise ValueError(f"봉인 분할이 아니다: {split!r} — 열린 분할은 splits.queries_in 을 쓴다")
    if not str(reason).strip():
        raise ValueError("개봉 사유는 비울 수 없다 — 원장의 reason 이 이 교정의 증거다")
    if not allow:
        raise SystemExit(
            f"ERROR: 봉인 분할 {split!r} 을 열려면 allow=True 가 필요하다 (D17 · 코드 게이트).\n"
            "  CLI 플래그는 없다. 사람이 호출부에 그 인자를 적고, 그 사실이 원장에 남는다."
        )

    m = split_map if split_map is not None else load_split()
    ids = queries_in(split, split_map=m)
    src = Path(file) if file is not None else SPLIT_CSV
    src_abs = src if src.is_absolute() else ROOT / src
    row = {
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _head_commit(),
        "caller": caller or "unknown",
        "file": str(src_abs.relative_to(ROOT)) if src_abs.is_relative_to(ROOT) else str(src_abs),
        "sha256": sha256_of(src_abs) if src_abs.exists() else "",
        "reason": str(reason).strip(),
    }
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:  # 추가 전용 — 덮어쓰기 경로를 두지 않는다
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return ids


def ledger_is_wellformed(path: Path = LEDGER) -> tuple[bool, list[str]]:
    """전 행이 6키를 갖고 reason 이 비지 않았는가. (ok, 문제 목록)"""
    problems = []
    for i, r in enumerate(ledger_rows(path), 1):
        missing = [k for k in REQUIRED_KEYS if k not in r]
        if missing:
            problems.append(f"{i}행 키 누락 {missing}")
        if not str(r.get("reason", "")).strip():
            problems.append(f"{i}행 reason 이 비었다")
    return (not problems), problems
