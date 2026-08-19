#!/usr/bin/env python3
"""공개 트리의 무결성 기록을 **발행 자산 전량**으로 발행한다 (P0 · 하류 재현성).

**왜 이 생성기가 있는가.** `provenance/PROVENANCE.json` 은 자산을 **1건**만 등재하고 있었다.
하류 논문은 *"파일별 sha256 은 PROVENANCE.json 에 있다"* 를 재현 근거로 인용하는데, 심사자가
그 파일을 열면 대조할 수 있는 것이 하나뿐이었다. 이 생성기가 그 간극을 닫는다.

**해시는 공개 트리의 바이트로 잰다 — 비공개 원본이 아니다.** `build_public_release.py` 는
복사하면서 변형한다(사설 블록 제거·죽은 링크 평문화·원문 스크럽·절대경로 세척). 그러므로
비공개 원본의 해시를 실으면 **심사자가 공개 파일에서 계산한 값과 영원히 어긋난다.** 이 생성기는
빌드된 트리 위에서 돌고, 결과를 그 트리 안에 쓴다.

**두 파일의 역할이 다르다.** 저장소의 `provenance/PROVENANCE.json` 은 사람이 유지하는
**큐레이션 씨앗**(generator·inputs·change_request)이고, 공개 트리의 같은 경로는 이 생성기가
낸 **전량 등재본**이다. 씨앗의 필드는 병합되며 소실되지 않는다.

**결정성.** 생성 시각을 싣지 않는다 — 두 번 돌려 바이트가 달라지면 무결성 기록이 아니라 소음이다.
키는 정렬하고, 커밋은 인자로 받거나 HEAD 에서 읽는다.

CLI:
    python scripts/build_provenance.py --tree build/public
    python scripts/build_provenance.py --tree build/public --check   # 불일치면 rc=1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SELF_REL = "provenance/PROVENANCE.json"
SEED = Path("provenance/PROVENANCE.json")

README = (
    "릴리스 자산의 무결성 기록. 하류는 이 해시로 자기 스냅샷을 검증한다. "
    "해시는 이 공개 트리의 파일 바이트에서 계산되었다(비공개 원본이 아니다). "
    "생성기: scripts/build_provenance.py — 손으로 고치지 않는다."
)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def head_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return ""


def load_seed() -> dict:
    """큐레이션 필드(generator·inputs·change_request)만 꺼낸다."""
    if not SEED.exists():
        return {}
    doc = json.loads(SEED.read_text(encoding="utf-8"))
    out = {}
    for rel, meta in (doc.get("assets") or {}).items():
        keep = {k: v for k, v in meta.items() if k in ("generator", "inputs", "change_request")}
        if keep:
            out[rel] = keep
    return out


def build(tree: Path, commit: str) -> dict:
    seed = load_seed()
    assets: dict[str, dict] = {}
    for p in sorted(tree.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(tree).as_posix()
        if rel == SELF_REL:          # 자기 자신은 등재하지 않는다 (해시가 자기를 포함할 수 없다)
            continue
        entry = {"sha256": sha256(p), "bytes": p.stat().st_size}
        entry.update(seed.get(rel, {}))
        assets[rel] = entry
    return {
        "_README": README,
        "schema_version": 2,
        "release": {"upstream_commit": commit, "assets_count": len(assets)},
        "assets": dict(sorted(assets.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, default=Path("build/public"))
    ap.add_argument("--commit", default=None, help="기본: HEAD")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 대조만 한다")
    a = ap.parse_args()

    if not a.tree.is_dir():
        print(f"ERROR: 공개 트리가 없다: {a.tree} — 먼저 make public-release", file=sys.stderr)
        return 2

    doc = build(a.tree, a.commit or head_commit())
    dst = a.tree / SELF_REL

    if a.check:
        if not dst.exists():
            print(f"FAIL: {dst} 가 없다", file=sys.stderr)
            return 1
        cur = json.loads(dst.read_text(encoding="utf-8"))
        drift = []
        for rel, meta in doc["assets"].items():
            old = (cur.get("assets") or {}).get(rel)
            if old is None:
                drift.append(f"미등재 {rel}")
            elif old.get("sha256") != meta["sha256"]:
                drift.append(f"해시 불일치 {rel}")
        for rel in (cur.get("assets") or {}):
            if rel not in doc["assets"]:
                drift.append(f"트리에 없음 {rel}")
        if drift:
            for d in drift[:20]:
                print(f"FAIL: {d}", file=sys.stderr)
            print(f"FAIL: 총 {len(drift)}건", file=sys.stderr)
            return 1
        print(f"[provenance] 대조 통과 · 자산 {len(doc['assets'])}건")
        return 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                   encoding="utf-8")
    print(f"[provenance] {dst} · 자산 {len(doc['assets'])}건 · commit {doc['release']['upstream_commit'][:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
