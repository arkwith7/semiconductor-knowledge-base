#!/usr/bin/env python3
"""Build the cited-prior-art full-text corpus index (plan §7.3-2).

Parses data/patents/fulltext/{prior_arts,etching_prior_arts}/*.txt — the
examiner-cited external patents collected by paper_data Phase B — into a
single parquet keyed by the citation_norm canonical doc_id (KR-P-…).

CRITICAL: file existence ≠ content.  Unresolved citations are written as
header-only stubs (no ## TITLE / ## ABSTRACT).  `has_content` flags the
~93.5 % that actually carry retrievable text; downstream evaluation must
filter on has_content, not on file presence (plan §7.3-2).

Output:
  data/patents/fulltext_corpus.parquet
  data/reports/fulltext_corpus_report.json
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FT_DIRS = [
    ROOT / "data" / "patents" / "fulltext" / "prior_arts",
    ROOT / "data" / "patents" / "fulltext" / "etching_prior_arts",
]
OUT_PARQUET = ROOT / "data" / "patents" / "fulltext_corpus.parquet"
OUT_REPORT = ROOT / "data" / "reports" / "fulltext_corpus_report.json"

_SECT = re.compile(r"^##\s+(TITLE|ABSTRACT|CLAIM[S]?)\s*$", re.M)


def parse_doc(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    doc_id = path.stem
    header, _, body = txt.partition("=" * 40)
    hdr = dict(
        (m.group(1).strip().lower(), m.group(2).strip())
        for m in re.finditer(r"^([A-Za-z/ ]+):\s*(.*)$", header, re.M)
    )
    country = (hdr.get("country/kind", "/").split("/")[0] or "").strip()
    kind = (hdr.get("country/kind", "/").split("/")[-1] or "").strip()
    # Split body into ## SECTION blocks
    sections: dict[str, str] = {}
    parts = _SECT.split(body)
    # parts = [pre, NAME, content, NAME, content, ...]
    for i in range(1, len(parts) - 1, 2):
        sections.setdefault(parts[i].strip().upper(), parts[i + 1].strip())
    title = sections.get("TITLE", "").strip()
    abstract = sections.get("ABSTRACT", "").strip()
    claims = next((v for k, v in sections.items() if k.startswith("CLAIM")), "").strip()
    has_content = bool(title) and len(title) >= 2 and bool(abstract) and len(abstract) >= 20
    return {
        "doc_id": doc_id,
        "country": country or (doc_id.split("-")[0] if "-" in doc_id else ""),
        "kind": kind,
        "title": title,
        "abstract": abstract,
        "claims": claims,
        "n_chars": len(title) + len(abstract),
        "has_content": has_content,
        "source_dir": path.parent.name,
    }


def main() -> int:
    rows: list[dict] = []
    seen: set[str] = set()
    for d in FT_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.txt")):
            r = parse_doc(p)
            if r["doc_id"] in seen:        # prior_arts wins over etching dup
                continue
            seen.add(r["doc_id"])
            rows.append(r)

    df = pd.DataFrame(rows)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    by_c = Counter(df["country"])
    by_c_content = Counter(df.loc[df["has_content"], "country"])
    report = {
        "n_files": int(len(df)),
        "n_with_content": int(df["has_content"].sum()),
        "n_stub": int((~df["has_content"]).sum()),
        "content_rate": round(float(df["has_content"].mean()), 4),
        "by_country": {
            c: {"total": int(by_c[c]), "with_content": int(by_c_content.get(c, 0))}
            for c in sorted(by_c)
        },
        "output": str(OUT_PARQUET.relative_to(ROOT)),
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ Fulltext corpus: {len(df)} docs "
          f"({report['n_with_content']} content / {report['n_stub']} stub, "
          f"{report['content_rate']:.1%}) → {OUT_PARQUET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
