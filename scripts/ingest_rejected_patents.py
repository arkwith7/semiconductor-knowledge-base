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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import citation_norm as CN  # noqa: E402  vendored from paper_data — plan §7.1

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


def norm_citation(raw: str) -> tuple[str, str, str, bool]:
    """Normalize a raw GT citation via the vendored citation_norm.

    Returns (doc_id, country, kind, is_npl).  doc_id is the canonical
    'KR-P-1020190085654' form that keys the fulltext corpus (plan §7.3-1).
    NPL / unparseable citations get is_npl=True and an empty doc_id so they
    can be excluded from patent-recall denominators (plan §7.3-4).
    """
    try:
        c = CN.parse(raw)
    except Exception:
        return "", "", "", True
    nid = c.normalized_id
    if not nid or nid.startswith("UNKNOWN::") or not c.country or not c.serial:
        return "", c.country or "", c.kind or "", True
    return nid, c.country, c.kind, False


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
    country_counter: Counter = Counter()
    npl_counter: Counter = Counter()
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

            # ── Expanded schema (paper_data Phase A~D — plan §7.1) ──
            claims_full = tp.get("claims_full") or []
            fam = tp.get("family") or {}
            fam_pubs = fam.get("publication_numbers") or []
            legal_status = tp.get("legal_status") or {}
            rd = meta.get("rejection_decision") or {}
            rd_bases = rd.get("legal_bases") or []
            rd_bases_str = "|".join(
                f"§{b.get('paragraph')}×{b.get('count')}" for b in rd_bases
            )
            gt_v2 = meta.get("ground_truth_evidence_v2") or []

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
                # Expanded schema (plan §7.2)
                "n_claims_full": len(claims_full),
                "has_claims_full": bool(claims_full),
                "family_pub_numbers": "|".join(str(p) for p in fam_pubs),
                "has_family": bool(fam_pubs),
                "legal_status_current": legal_status.get("current") or "",
                "has_rejection_structured": bool(rd.get("structured_path")),
                "rejection_legal_bases": rd_bases_str,
                "rejection_decision_date": rd.get("decision_date") or "",
                "n_gt_evidence_v2": len(gt_v2),
            })

            for code in ipc_codes:
                ipc_rows.append({
                    "patent_id": patent_id,
                    "ipc_code": code,
                    "ipc_section": code[0] if code else "",
                    "ipc_4digit": ipc_4digit(code),
                })

            # Prior-art edges.  Legacy raw-GT sources keep their original
            # columns/behaviour; cited_doc_id (citation_norm canonical form)
            # + is_npl + cited_country are added for real-GT eval (plan §7.3).
            seen_pairs: set[tuple[str, str, str]] = set()

            def _emit(src_label, gt_raw, cited_id, cited_doc_id, office,
                      country, kind, is_npl, legal_basis="",
                      target_claims="", evidence_phrase_no=""):
                triple = (patent_id, cited_doc_id or cited_id, src_label)
                if triple in seen_pairs:
                    return
                seen_pairs.add(triple)
                office_counter[office] += 1
                if country:
                    country_counter[country] += 1
                if is_npl:
                    npl_counter[src_label] += 1
                edge_rows.append({
                    "target_patent_id": patent_id,
                    "cited_id": cited_id,
                    "cited_doc_id": cited_doc_id,        # KR-P-… canonical (plan §7.3-1)
                    "cited_raw": gt_raw,
                    "cited_office": office,              # legacy heuristic
                    "cited_country": country,            # citation_norm country
                    "cited_kind": kind,
                    "is_npl": is_npl,                    # exclude from patent recall (§7.3-4)
                    "source_type": src_label,            # examiner|all|evidence|evidence_v2
                    "legal_basis": legal_basis,          # evidence_v2 only
                    "target_claims": target_claims,      # evidence_v2 only (pipe-joined)
                    "evidence_phrase_no": evidence_phrase_no,
                })

            for src_label, key in (("examiner", "ground_truth_examiner"),
                                   ("all",      "ground_truth_all"),
                                   ("evidence", "ground_truth_evidence")):
                for gt in (rec.get(key) or []):
                    if not gt:
                        continue
                    office = infer_office_from_gt(gt)
                    cited_id = f"patent:{office.lower()}_{re.sub(r'[^0-9A-Za-z]', '', gt)}"
                    doc_id, country, kind, is_npl = norm_citation(gt)
                    if is_npl and src_label == "evidence":
                        drop_evidence += 1   # legacy NPL counter (backward compat)
                    _emit(src_label, gt, cited_id, doc_id, office,
                          country, kind, is_npl)

            # ground_truth_evidence_v2 — structured rejection-reason → cited
            # mapping (already citation-normalized).  Drives §5(4) pilot.
            for item in gt_v2:
                cdoc = item.get("cited_id") or ""
                if not cdoc:
                    continue
                cnt = cdoc.split("-")[0] if "-" in cdoc else ""
                tclaims = "|".join(str(c) for c in (item.get("target_claims") or []))
                _emit("evidence_v2", cdoc, cdoc, cdoc,
                      cnt or "OTHER", cnt, "",
                      cdoc.startswith("UNKNOWN::"),
                      legal_basis=item.get("legal_basis") or "",
                      target_claims=tclaims,
                      evidence_phrase_no=str(item.get("evidence_phrase_no") or ""))

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
        "cited_country_distribution": dict(country_counter.most_common()),
        "npl_edges_by_source": dict(npl_counter.most_common()),
        "duplicate_application_numbers": duplicate_app_numbers,
        "non_patent_evidence_dropped": int(drop_evidence),
        # Expanded-schema coverage (plan §7.2 acceptance criteria)
        "expanded_schema": {
            "n_with_claims_full": int(meta_df["has_claims_full"].sum()),
            "n_with_family": int(meta_df["has_family"].sum()),
            "n_with_rejection_structured": int(meta_df["has_rejection_structured"].sum()),
            "n_with_gt_evidence_v2": int((meta_df["n_gt_evidence_v2"] > 0).sum()),
            "claims_full_rate": round(float(meta_df["has_claims_full"].mean()), 4),
            "family_rate": round(float(meta_df["has_family"].mean()), 4),
        },
        "examiner_gt": {
            "n_edges": int((edge_df["source_type"] == "examiner").sum()) if len(edge_df) else 0,
            "n_distinct_doc_ids": int(
                edge_df.loc[(edge_df["source_type"] == "examiner") & (~edge_df["is_npl"]),
                            "cited_doc_id"].nunique()
            ) if len(edge_df) else 0,
            "n_npl": int(npl_counter.get("examiner", 0)),
        },
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
