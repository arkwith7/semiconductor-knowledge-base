#!/usr/bin/env python3
"""공개본 트리 생성기 — KIPRIS 원문을 뺀 릴리스 트리를 만든다 (CR-015 출력 (1)·(1-b)·(4)).

**왜 생성기인가.** 원고 §10.3 은 *"KIPRIS 원문은 재배포할 수 없다"* 고 쓰는데 이 저장소는
초록·청구항 전문 1,000건을 커밋하고 있(었)다. 두 문장이 같은 것을 가리키며 서로 반대다.
손으로 지우면 다음에 또 어긋나므로, **공개할 트리를 매번 코드가 만든다.**

만드는 것:
  1. `data/patents/raw/…rejected_patents.jsonl` — abstract · claim1 · claims_full[].text 를
     **빈 문자열로** 둔다. **키는 지우지 않는다** — 스키마·claim_no·depends_on 은 서지
     구조이고, `ingest_rejected_patents.py:216-259` 가 항수와 보유 플래그를 읽는다.
     `title` 은 남긴다(서지이며 이미 `kipris_biblio.parquet` 에 커밋돼 있다).
  2. 노트북 셀 출력 제거 — 07 의 출력 하나가 초록 발췌를 인쇄한다. 같은 정책이 이미
     노트북 08 에 적용된 전례가 있다.
  3. 나머지는 `git ls-files` 그대로 복사한다. **화이트리스트가 아니라 블랙리스트**인
     이유는, 새 파일이 생겼을 때 조용히 빠지는 쪽보다 조용히 들어오는 쪽이 검사기에
     걸리기 때문이다(`check_public_release.py`).

만들지 않는 것: 공개 리포에 푸시하지 않는다. 이 스크립트는 트리까지만 만들고, orphan
커밋과 푸시는 사람이 검사기 통과를 확인한 뒤에 한다 — **되돌릴 수 없는 단계는 자동화하지
않는다.**

CLI:
    python scripts/build_public_release.py --out /tmp/sdkb-public
    python scripts/build_public_release.py --out /tmp/sdkb-public --rev 212fe62
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_REL = "data/patents/raw/semiconductor_industry_rejected_patents.jsonl"

# 원문을 담는 필드. title 은 여기 없다 — 서지다.
TEXT_FIELDS = ("abstract", "claim1")


def tracked_files(rev: str | None) -> list[str]:
    cmd = ["git", "ls-tree", "-r", "--name-only", rev] if rev else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def read_blob(rel: str, rev: str | None) -> bytes:
    if rev:
        return subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT,
                              capture_output=True, check=True).stdout
    return (ROOT / rel).read_bytes()


def scrub_dataset(raw: bytes) -> tuple[bytes, dict]:
    """원문 세 필드를 비운다. 스키마·키·항수는 건드리지 않는다."""
    stats = {"rows": 0, "abstract": 0, "claim1": 0, "claims_full_texts": 0}
    lines = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        tp = rec.get("target_patent") or {}
        stats["rows"] += 1
        for f in TEXT_FIELDS:
            if (tp.get(f) or "").strip():
                tp[f] = ""
                stats[f] += 1
        for c in (tp.get("claims_full") or []):
            if (c.get("text") or "").strip():
                c["text"] = ""
                stats["claims_full_texts"] += 1
        # ensure_ascii=False 왕복이 원본과 바이트 동일함을 확인하고 고른 직렬화다.
        lines.append(json.dumps(rec, ensure_ascii=False))
    return ("\n".join(lines) + "\n").encode("utf-8"), stats


def strip_notebook(raw: bytes) -> tuple[bytes, int]:
    nb = json.loads(raw.decode("utf-8"))
    n = 0
    for cell in nb.get("cells", []):
        if cell.get("outputs"):
            cell["outputs"] = []
            n += 1
        if "execution_count" in cell:
            cell["execution_count"] = None
    return (json.dumps(nb, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="공개 트리를 쓸 빈 디렉터리")
    ap.add_argument("--rev", default=None,
                    help="기준 커밋(기본: 현재 워킹트리의 추적 파일)")
    ap.add_argument("--force", action="store_true", help="--out 이 비어 있지 않아도 덮어쓴다")
    args = ap.parse_args()

    out: Path = args.out
    if out.exists() and any(out.iterdir()) and not args.force:
        raise SystemExit(f"ERROR: {out} 가 비어 있지 않다. --force 를 주거나 다른 경로를 쓴다.")
    if out.exists() and args.force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    files = tracked_files(args.rev)
    scrub_stats, nb_stripped, copied = {}, {}, 0
    for rel in files:
        raw = read_blob(rel, args.rev)
        if rel == DATASET_REL:
            raw, scrub_stats = scrub_dataset(raw)
        elif rel.endswith(".ipynb"):
            raw, n = strip_notebook(raw)
            if n:
                nb_stripped[rel] = n
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
        copied += 1

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rev": args.rev or "working-tree",
        "files": copied,
        "dataset_scrub": scrub_stats,
        "notebook_outputs_stripped": nb_stripped,
    }
    (out / "data" / "reports").mkdir(parents=True, exist_ok=True)
    (out / "data" / "reports" / "public_release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[public] {copied}개 파일 → {out}")
    print(f"[public] 데이터셋 비움: {scrub_stats}")
    print(f"[public] 노트북 출력 제거: {nb_stripped or '없음'}")
    print("[public] 다음 단계는 검사기다 — 통과 전에는 푸시하지 않는다:")
    print(f"         python scripts/check_public_release.py --tree {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
