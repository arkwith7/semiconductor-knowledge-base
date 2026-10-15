#!/usr/bin/env python3
"""PLAN-006 T4 — 평가 후보 코퍼스의 단일 진입점 (읽기 전용).

코퍼스는 git 밖에 산다(170MB · 원문 포함). 그래서 "파일이 있다" 는 사실만으로는 같은 코퍼스라는
보증이 없다 — 값을 MANIFEST 에 핀하고, 없거나 어긋나면 조용히 진행하지 않고 SystemExit 한다
(`splits.load_split` 과 같은 규율). 평가가 다른 코퍼스를 읽고 같은 이름의 리포트를 내는 것이
여기서 막으려는 실패다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "sources" / "ir_corpus"
MANIFEST = CORPUS_DIR / "MANIFEST.json"


def manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_path(m: dict | None = None, *, base: Path = CORPUS_DIR) -> Path:
    m = m or manifest()
    return Path(base) / m["file"]


def verify(path: Path | None = None, m: dict | None = None) -> Path:
    """없거나 sha 가 다르면 SystemExit. 통과하면 경로를 돌려준다."""
    m = m or manifest()
    path = Path(path) if path else corpus_path(m)
    if not path.exists():
        raise SystemExit(
            f"ERROR: 평가 코퍼스가 없다: {path}\n"
            f"  내려받기: python scripts/ir_corpus.py fetch --release  (또는 --from <로컬 사본>)"
        )
    got = sha256_of(path)
    if got != m["sha256"]:
        raise SystemExit(
            f"ERROR: 평가 코퍼스 sha256 이 매니페스트와 다르다: {path}\n"
            f"  매니페스트 {m['sha256']}\n  실측       {got}"
        )
    return path


def load(columns: list[str] | None = None, *, path: Path | None = None, m: dict | None = None):
    """검증을 통과한 코퍼스만 읽는다. 행 수도 매니페스트와 대조한다."""
    import pandas as pd

    m = m or manifest()
    p = verify(path, m)
    df = pd.read_parquet(p, columns=columns)
    if len(df) != m["rows"]:
        raise SystemExit(f"ERROR: 코퍼스 행 수가 매니페스트({m['rows']})와 다르다: {len(df)}")
    return df


def fetch(*, src: Path | None, release: bool, m: dict | None = None, base: Path = CORPUS_DIR) -> Path:
    m = m or manifest()
    dst = corpus_path(m, base=base)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src is not None:
        shutil.copyfile(src, dst)
    elif release:
        # 보관 저장소 이름은 비공개 원천 계층(MANIFEST)에만 둔다 — 코드에 박으면 공개 트리로 새어 나간다
        st = m["storage"]
        if not st.get("release_repo") or not st.get("release_tag"):
            raise SystemExit("ERROR: MANIFEST storage 에 release_repo·release_tag 가 없다")
        subprocess.run(
            ["gh", "release", "download", st["release_tag"], "--repo", st["release_repo"],
             "--pattern", m["file"], "--dir", str(dst.parent), "--clobber"],
            check=True,
        )
    else:
        raise SystemExit("ERROR: --from 또는 --release 중 하나를 준다")
    try:
        return verify(dst, m)
    except SystemExit:
        dst.unlink(missing_ok=True)  # 어긋난 파일을 남기면 다음 실행이 그것을 다시 검증하게 된다
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--from", dest="src", type=Path)
    g.add_argument("--release", action="store_true")
    sub.add_parser("verify")
    a = ap.parse_args(argv)
    p = fetch(src=a.src, release=a.release) if a.cmd == "fetch" else verify()
    print(f"OK {p} sha256={manifest()['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
