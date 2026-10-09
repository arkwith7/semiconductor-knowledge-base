#!/usr/bin/env python3
"""PLAN-006 T4 S2 — WIPO IPC Revision Concordance List → 판 대응표 (결정적 · 그래프를 바꾸지 않는다).

왜: 코퍼스에서 국내 문서는 신판(H10B/D/P/W…), 외국 인용문헌은 구판(H01L)으로 섞여 있어 IPC 한정이
정답을 판 차이만으로 잃는다(2단계 리포트 §2 · 236/408쌍). H01L 전체 ↔ H10 전체를 같은 것으로 보면
과잉 확장이 되므로 **WIPO 가 적은 세부 분류 단위의 이동만** 옮긴다.

원천: data/sources/ipc_concordance/ipc_concordancelist_<판>.zip (WIPO ITSupport_and_download_area ·
MANIFEST.json 에 URL·sha256). 출력: mappings/ipc_concordance.csv — 한 행 = (구 기호 → 신 기호) 한 간선.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data" / "sources" / "ipc_concordance"
MANIFEST = SRC_DIR / "MANIFEST.json"
OUT = ROOT / "mappings" / "ipc_concordance.csv"
NS = {"w": "http://www.wipo.int/classifications/ipc/masterfiles"}
COLUMNS = [
    "from_symbol", "from_version", "from_modification", "to_symbol", "to_version", "to_modification",
    "default_reclassification", "revision_project", "source_file",
]
_MASTER = re.compile(r"^([A-H]\d\d[A-Z])(\d{4})(\d{6})$")


def to_readable(master: str) -> str:
    """WIPO 마스터 기호 `H01L0021306000` → `H01L21/306`.

    서브그룹 6자리는 뒤쪽 0 을 지우되 최소 2자리를 남긴다(`000000`→`00`, `020000`→`02`).
    """
    m = _MASTER.match(master)
    if not m:
        raise ValueError(f"WIPO 마스터 기호 꼴이 아니다: {master!r}")
    sub, grp, sg = m.groups()
    sg = sg.rstrip("0")
    return f"{sub}{int(grp)}/{sg.ljust(2, '0')}"


def sha256_of(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(zip_path: Path) -> list[dict]:
    z = zipfile.ZipFile(zip_path)
    names = [n for n in z.namelist() if n.endswith(".xml")]
    if len(names) != 1:
        raise SystemExit(f"ERROR: {zip_path.name} 에 XML 이 하나가 아니다: {names}")
    root = ET.fromstring(z.read(names[0]))
    fv, tv = root.get("from-version"), root.get("to-version")
    rows = []
    for c in root.findall("w:concordance", NS):
        for t in c.findall("w:concordance-to", NS):
            rows.append({
                "from_symbol": to_readable(c.get("from-symbol")), "from_version": fv,
                "from_modification": c.get("modification") or "",
                "to_symbol": to_readable(t.get("to-symbol")), "to_version": tv,
                "to_modification": t.get("modification") or "",
                "default_reclassification": t.get("default-reclassification") or "",
                "revision_project": c.get("revision-project") or "",
                "source_file": zip_path.name,
            })
    return rows


def build(src_dir: Path = SRC_DIR, manifest_path: Path = MANIFEST) -> list[dict]:
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows: list[dict] = []
    for f in m["files"]:
        p = Path(src_dir) / f["file"]
        got = sha256_of(p)
        if got != f["sha256"]:
            raise SystemExit(f"ERROR: {p.name} sha256 이 매니페스트와 다르다\n  매니페스트 {f['sha256']}\n  실측 {got}")
        rows.extend(parse(p))
    rows.sort(key=lambda r: (r["from_version"], r["from_symbol"], r["to_symbol"]))
    return rows


def main() -> int:
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"OK {OUT.relative_to(ROOT)} rows={len(rows)} sha256={sha256_of(OUT)[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
