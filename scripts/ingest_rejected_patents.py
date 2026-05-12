#!/usr/bin/env python3
"""Ingest SIRP — Semiconductor Industry Rejected Patents (JSONL → Parquet).

Reads:
  data/patents/raw/semiconductor_industry_rejected_patents.jsonl

Writes:
  data/patents/rejected_patents_meta.parquet   — one row per patent (773)
  data/patents/ipc_links.parquet               — one row per (patent, IPC code)
  data/patents/prior_art_edges.parquet         — one row per (target → cited, source_type)
  data/patents/ingest_report.json              — summary stats & integrity checks

The output schema is consumed by:
  - scripts/build_prior_art_pairs.py    (deliverable ④ — 7,500 pairs)
  - scripts/sample_problems.py          (deliverable ③ — 50 problems + 25 scenarios)
  - ontology/sdkb-patent.ttl            (instance loading — future RDF conversion)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
OUT_DIR = ROOT / "data" / "patents"
OUT_META = OUT_DIR / "rejected_patents_meta.parquet"
OUT_IPC = OUT_DIR / "ipc_links.parquet"
OUT_EDGES = OUT_DIR / "prior_art_edges.parquet"
OUT_REPORT = OUT_DIR / "ingest_report.json"


_DATE_RE = re.compile(r"^(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})$")


def normalize_date(s: str | None) -> str | None:
    """KIPRIS dates arrive in mixed formats — '2022.11.04', '20260430', '2022-11-04'. Normalize to ISO."""
    if not s:
        return None
    s = s.strip()
    m = _DATE_RE.match(s)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{mo}-{d}"


def parse_ipc_codes(ipc_str: str | None) -> list[str]:
    if not ipc_str:
        return []
    return [c.strip() for c in ipc_str.split("|") if c.strip()]


def ipc_4digit(code: str) -> str:
    """Take 'H10P 50/28' → 'H10P', 'C23C 16/448' → 'C23C'."""
    head = code.split(" ")[0]
    return head[:4] if len(head) >= 4 else head


def make_patent_id(application_number: str, office: str = "KR") -> str:
    """Stable internal ID for SDKB nodes."""
    appnum = re.sub(r"[^0-9A-Za-z]", "", application_number or "")
    return f"patent:{office.lower()}_{appnum}"


def infer_office_from_gt(gt_id: str) -> str:
    """Best-effort office tag from a GT identifier like 'KR1020190085654 A'."""
    if not gt_id:
        return "UNK"
    head = gt_id.strip()[:2].upper()
    if head in {"KR", "JP", "US", "EP", "WO", "CN"}:
        return head
    return "OTHER"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not IN_PATH.exists():
        print(f"ERROR: {IN_PATH} not found", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    meta_rows: list[dict] = []
    ipc_rows: list[dict] = []
    edge_rows: list[dict] = []

    pf_counter: Counter = Counter()
    office_counter: Counter = Counter()
    drop_evidence = 0

    with open(IN_PATH, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"WARN: line {line_no} invalid JSON: {e}", file=sys.stderr)
                continue

            tp = rec.get("target_patent", {}) or {}
            meta = rec.get("meta", {}) or {}
            biblio = tp.get("biblio", {}) or {}
            registration = tp.get("registration", {}) or {}

            app_no = tp.get("application_number") or ""
            patent_id = make_patent_id(app_no, office="KR")

            ipc_codes = parse_ipc_codes(tp.get("ipc"))
            primary_section = ipc_codes[0][0] if ipc_codes else ""
            primary_4digit = ipc_4digit(ipc_codes[0]) if ipc_codes else ""

            family = meta.get("process_family") or ""
            pf_counter[family] += 1
            value_chain = meta.get("value_chain") or []
            if isinstance(value_chain, list):
                value_chain_str = "|".join(str(v) for v in value_chain)
            else:
                value_chain_str = str(value_chain)

            meta_rows.append({
                "patent_id": patent_id,
                "application_number": app_no,
                "patent_office": "KR",
                "title": tp.get("title") or "",
                "abstract": tp.get("abstract") or "",
                "claim1": tp.get("claim1") or "",
                "primary_ipc": ipc_codes[0] if ipc_codes else "",
                "primary_ipc_section": primary_section,
                "primary_ipc_4digit": primary_4digit,
                "n_ipc_codes": len(ipc_codes),
                "filing_date": normalize_date(tp.get("date")),
                "publication_number": biblio.get("unex_pub_number") or "",
                "publication_date": normalize_date(biblio.get("unex_pub_date")),
                "register_status": registration.get("register_status") or "",
                "register_number": registration.get("register_number") or "",
                "register_date": normalize_date(registration.get("register_date")),
                "examination_status": biblio.get("examination_status") or "",
                "process_family": family,
                "value_chain": value_chain_str,
                "collection_stage": meta.get("collection_stage") or "",
                "search_strategy": meta.get("search_strategy") or "",
                "cohort_scope": meta.get("cohort_scope") or "",
                "source": meta.get("source") or biblio.get("source") or "",
                "evidence_document_type": meta.get("evidence_document_type") or "",
                "evidence_document_url": meta.get("evidence_document_url") or "",
                "collection_ts": meta.get("collection_ts") or "",
            })

            for code in ipc_codes:
                ipc_rows.append({
                    "patent_id": patent_id,
                    "ipc_code": code,
                    "ipc_section": code[0] if code else "",
                    "ipc_4digit": ipc_4digit(code),
                })

            # Prior-art edges
            seen_pairs: set[tuple[str, str, str]] = set()
            for src_label, key in (("examiner", "ground_truth_examiner"),
                                   ("all",      "ground_truth_all"),
                                   ("evidence", "ground_truth_evidence")):
                for gt in (rec.get(key) or []):
                    if not gt:
                        continue
                    office = infer_office_from_gt(gt)
                    cited_id = f"patent:{office.lower()}_{re.sub(r'[^0-9A-Za-z]', '', gt)}"
                    if office in {"UNK", "OTHER"}:
                        # Likely a non-patent literature reference; tag but keep
                        if src_label == "evidence":
                            drop_evidence += 1
                    office_counter[office] += 1
                    triple = (patent_id, cited_id, src_label)
                    if triple in seen_pairs:
                        continue
                    seen_pairs.add(triple)
                    edge_rows.append({
                        "target_patent_id": patent_id,
                        "cited_id": cited_id,
                        "cited_raw": gt,
                        "cited_office": office,
                        "source_type": src_label,  # examiner | all | evidence
                    })

    meta_df = pd.DataFrame(meta_rows)
    ipc_df = pd.DataFrame(ipc_rows)
    edge_df = pd.DataFrame(edge_rows)

    # Integrity: application_number must be unique
    dup_appno = meta_df[meta_df["application_number"].duplicated(keep=False)]
    duplicate_app_numbers = sorted(set(dup_appno["application_number"].tolist()))

    # Write Parquet
    meta_df.to_parquet(OUT_META, index=False)
    ipc_df.to_parquet(OUT_IPC, index=False)
    edge_df.to_parquet(OUT_EDGES, index=False)

    # Summary report
    report = {
        "source_file": str(IN_PATH.relative_to(ROOT)),
        "source_sha256": file_sha256(IN_PATH),
        "n_patents": int(len(meta_df)),
        "n_ipc_links": int(len(ipc_df)),
        "n_prior_art_edges": int(len(edge_df)),
        "n_edges_by_source": {
            k: int(v) for k, v in edge_df["source_type"].value_counts().items()
        } if len(edge_df) else {},
        "process_family_distribution": dict(pf_counter.most_common()),
        "cited_office_distribution": dict(office_counter.most_common()),
        "duplicate_application_numbers": duplicate_app_numbers,
        "non_patent_evidence_dropped": int(drop_evidence),
        "outputs": {
            "meta": str(OUT_META.relative_to(ROOT)),
            "ipc_links": str(OUT_IPC.relative_to(ROOT)),
            "prior_art_edges": str(OUT_EDGES.relative_to(ROOT)),
        },
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ Patents meta ({len(meta_df)} rows) → {OUT_META.relative_to(ROOT)}")
    print(f"✓ IPC links   ({len(ipc_df)} rows) → {OUT_IPC.relative_to(ROOT)}")
    print(f"✓ Prior-art edges ({len(edge_df)} rows) → {OUT_EDGES.relative_to(ROOT)}")
    print(f"✓ Report → {OUT_REPORT.relative_to(ROOT)}")
    if duplicate_app_numbers:
        print(f"⚠ Duplicate application_numbers: {duplicate_app_numbers[:5]}{'...' if len(duplicate_app_numbers) > 5 else ''}")


if __name__ == "__main__":
    main()
