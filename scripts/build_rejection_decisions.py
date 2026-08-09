"""B2 거절결정서 PDF 다운로드 + OCR + 구조화.

근거: `docs/dataset_full_collection_runbook.md` Phase C.

흐름:
1. canonical JSONL 의 `meta.evidence_document_url` 에서 PDF 다운로드
2. pdfplumber/PyMuPDF 1차 텍스트 추출 → 실패 시 pdf2image + tesseract-kor OCR
3. 텍스트에서 §29①/§29② (신규성/진보성), 대비 인용발명, 대비 청구항 추출
4. structured JSON 저장
5. 인덱스 작성

사전 단계 (URL 누락 시):
    .venv/bin/python scripts/backfill_admin_docs.py --apply

사용
====
    .venv/bin/python scripts/build_rejection_decisions.py --plan
    .venv/bin/python scripts/build_rejection_decisions.py --download --limit 5
    .venv/bin/python scripts/build_rejection_decisions.py --ocr --limit 5
    .venv/bin/python scripts/build_rejection_decisions.py --full
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
OUT_DIR = REPO_ROOT / "data/processed/rejection_decisions"
PDF_DIR = OUT_DIR / "pdf"
TXT_DIR = OUT_DIR / "txt"
STRUCT_DIR = OUT_DIR / "structured"
INDEX_FILE = OUT_DIR / "_index.jsonl"

DOWNLOAD_TIMEOUT = 60
DEFAULT_DL_INTERVAL = 0.5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ensure_dirs() -> None:
    for d in (PDF_DIR, TXT_DIR, STRUCT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _collect_targets(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in records:
        m = r.get("meta") or {}
        url = m.get("evidence_document_url") or ""
        app_no = (r.get("target_patent") or {}).get("application_number", "")
        legacy_txt = None
        if (REPO_ROOT / "data/raw" / app_no / "rejection_notice").exists():
            files = list((REPO_ROOT / "data/raw" / app_no / "rejection_notice").glob("*.txt"))
            if files:
                legacy_txt = files[0]
        out.append({
            "application_number": app_no,
            "url": url,
            "doc_type": m.get("evidence_document_type", ""),
            "collection_plan": m.get("collection_plan", ""),
            "legacy_txt_path": str(legacy_txt) if legacy_txt else "",
        })
    return out


# ── 다운로드 ────────────────────────────────────────────────────────────────


def _pdf_path(app_no: str) -> Path:
    return PDF_DIR / f"{app_no}.pdf"


def download_phase(targets: List[Dict[str, Any]], args: argparse.Namespace) -> Dict[str, int]:
    sess = requests.Session()
    sess.headers["User-Agent"] = "paper-data-runbook/0.1"
    counts: Counter = Counter()
    used = 0
    for t in targets:
        app = t["application_number"]
        url = t["url"]
        pdf_path = _pdf_path(app)
        if pdf_path.exists() and pdf_path.stat().st_size > 1024:
            counts["already_exists"] += 1
            continue
        if not url:
            counts["no_url"] += 1
            continue
        if args.limit and used >= args.limit:
            counts["limit_hit"] += 1
            break
        try:
            r = sess.get(url, timeout=DOWNLOAD_TIMEOUT)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "").lower()
            content = r.content
            if not (b"%PDF" in content[:1024] or "pdf" in ct):
                counts["non_pdf"] += 1
                if args.verbose:
                    print(f"  [non-pdf] {app}: content-type={ct} head={content[:32]!r}")
                continue
            pdf_path.write_bytes(content)
            counts["downloaded"] += 1
            used += 1
        except Exception as exc:
            counts["error"] += 1
            if args.verbose:
                print(f"  [error] {app}: {exc}")
        time.sleep(args.dl_interval)
        if used % 25 == 0 and used > 0:
            print(f"  [download] used={used} ok={counts['downloaded']} fail={counts['error']}")
    return dict(counts)


# ── OCR ─────────────────────────────────────────────────────────────────────


def _extract_text_layered(pdf_path: Path) -> Tuple[str, str]:
    """returns (text, method)."""
    # 1) pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                parts.append(t)
            text = "\n".join(parts).strip()
            if len(text) >= 300:
                return text, "pdfplumber"
    except Exception:
        pass
    # 2) PyMuPDF
    try:
        import fitz
        doc = fitz.open(pdf_path)
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts).strip()
        if len(text) >= 300:
            return text, "pymupdf"
    except Exception:
        pass
    # 3) tesseract OCR (image-based)
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(str(pdf_path), dpi=300)
        parts = []
        for img in images:
            t = pytesseract.image_to_string(img, lang="kor+eng", config="--oem 1 --psm 3")
            parts.append(t)
        text = "\n".join(parts).strip()
        if text:
            return text, "tesseract"
    except Exception as exc:
        return "", f"ocr_failed:{exc.__class__.__name__}"
    return "", "all_failed"


# ── 구조화 파싱 ────────────────────────────────────────────────────────────


_LEGAL_BASIS_RX = re.compile(r"제\s*29\s*조\s*(?:제)?\s*([1-4])\s*항")
_CITED_RX = re.compile(r"인용발명\s*(\d+)")
_CLAIM_FOCUS_RX = re.compile(r"청구항\s*(\d+(?:\s*[,~]\s*\d+)*)")
_REJECTED_DATE_RX = re.compile(r"(\d{4})[.\-년]\s*(\d{1,2})[.\-월]\s*(\d{1,2})")

# "인용발명1: 공개특허공보 제10-2015-0109288호" 같은 라인에서 실제 ID 추출
_CITED_LINE_RX = re.compile(
    r"인용발명\s*(\d+)\s*[:：]?\s*([^\n]{0,200})",
    re.MULTILINE,
)
_KR_PUB_RX = re.compile(r"10[-\s]?(\d{4})[-\s]?(\d{6,7})")
_KR_REG_RX = re.compile(r"제\s*(\d{6,7})\s*호")
_US_PUB_RX = re.compile(r"US\s*(\d{4})\s*[/\-]\s*(\d{7})")
_US_GRANT_RX = re.compile(r"US\s*(\d{6,8})\s*[A-Z]?\d*")
_JP_RX = re.compile(r"(?:특개|특공|JP)\s*(?:평|소|H|S)?\s*(\d{2,4})\s*[-\s]?\s*(\d{4,7})")


def _normalize_cited_id(country_hint: str, raw: str) -> Optional[str]:
    """거절결정서 본문에서 발견한 표기를 normalized_id 로 매핑."""
    text = raw.strip()
    # KR pub: "제10-YYYY-NNNNNNN호" → KR-P-10YYYYNNNNNNN
    m = _KR_PUB_RX.search(text)
    if m and ("공개특허공보" in raw or "공개" in raw or country_hint == "KR"):
        return f"KR-P-10{m.group(1)}{m.group(2).zfill(7)}"
    # KR grant: "등록특허 제NNNNNNN호" → KR-G-NNNNNNN
    if "등록특허" in raw or "등록공보" in raw:
        m = _KR_REG_RX.search(text)
        if m:
            return f"KR-G-{m.group(1)}"
    # US pub: "US YYYY/NNNNNNN" → US-P-YYYYNNNNNNN
    m = _US_PUB_RX.search(text)
    if m:
        return f"US-P-{m.group(1)}{m.group(2)}"
    # US grant: bare 7~8 digit
    m = _US_GRANT_RX.search(text)
    if m and ("US" in raw.upper() or "미국" in raw) and "공개" not in raw:
        digits = m.group(1)
        if len(digits) <= 8:
            return f"US-G-{digits}"
    # JP
    m = _JP_RX.search(text)
    if m:
        year = m.group(1)
        num = m.group(2)
        return f"JP-P-{year}{num.zfill(6)}"
    return None


def parse_rejection_structure(text: str) -> Dict[str, Any]:
    """거절결정서 본문에서 핵심 구조 추출.

    추출 항목:
    - legal_bases: [{paragraph: "1"|"2"|"3"|"4", count: 출현빈도}]  → §29① 신규성 / §29② 진보성
    - cited_evidence_phrases: 인용발명 1·2·3 식별자
    - target_claims: 청구항 번호 리스트 (대비 청구항)
    - decision_date: yyyy-mm-dd
    - excerpt: 거절근거 문단의 첫 500자 (수기 검증용)
    """
    legal_basis_counts = Counter()
    for m in _LEGAL_BASIS_RX.finditer(text):
        legal_basis_counts[m.group(1)] += 1
    legal_bases = [{"paragraph": k, "count": v} for k, v in legal_basis_counts.most_common()]

    cited_ids = sorted({m.group(1) for m in _CITED_RX.finditer(text)})

    # 인용발명N 라인에서 실제 ID 매핑 시도 (KR/US/JP)
    evidence_map: Dict[str, str] = {}
    for m in _CITED_LINE_RX.finditer(text):
        n = m.group(1)
        line = m.group(2)
        # country hint from prefix tokens
        if "미국" in line or "US" in line.upper():
            country_hint = "US"
        elif "공개특허" in line or "등록" in line:
            country_hint = "KR"
        elif "JP" in line.upper() or "특개" in line or "특공" in line or "일본" in line:
            country_hint = "JP"
        else:
            country_hint = ""
        norm = _normalize_cited_id(country_hint, line)
        if norm and n not in evidence_map:
            evidence_map[n] = norm

    claim_ids: List[str] = []
    for m in _CLAIM_FOCUS_RX.finditer(text):
        seg = re.sub(r"\s+", "", m.group(1))
        claim_ids.extend(seg.split(","))
    claim_ids = sorted(set(c for c in claim_ids if c))

    decision_date = ""
    m = _REJECTED_DATE_RX.search(text)
    if m:
        decision_date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # 거절 근거 발췌 (가장 의미 있는 발췌)
    excerpt = ""
    for token in ("거절이유", "이 출원", "심사관", "대비"):
        idx = text.find(token)
        if idx != -1:
            excerpt = text[idx : idx + 500]
            break
    if not excerpt:
        excerpt = text[:500]

    return {
        "legal_bases": legal_bases,
        "cited_evidence_phrases": cited_ids,
        "cited_evidence_map": evidence_map,  # {"1": "KR-P-1020150109288", ...}
        "target_claims": claim_ids,
        "decision_date": decision_date,
        "excerpt": excerpt,
        "text_length": len(text),
    }


def ocr_phase(targets: List[Dict[str, Any]], args: argparse.Namespace) -> Dict[str, int]:
    counts: Counter = Counter()
    processed = 0
    for t in targets:
        app = t["application_number"]
        pdf_path = _pdf_path(app)
        legacy_txt = t.get("legacy_txt_path", "")

        # legacy raw text 가 있으면 그대로 사용
        if legacy_txt and Path(legacy_txt).exists():
            text = Path(legacy_txt).read_text(encoding="utf-8", errors="ignore")
            method = "legacy_raw"
        elif pdf_path.exists() and pdf_path.stat().st_size > 1024:
            txt_path = TXT_DIR / f"{app}.txt"
            if txt_path.exists() and not args.refresh:
                text = txt_path.read_text(encoding="utf-8")
                method = "cached"
            else:
                text, method = _extract_text_layered(pdf_path)
                if text:
                    txt_path.write_text(text, encoding="utf-8")
        else:
            counts["no_pdf"] += 1
            continue

        if not text or len(text.strip()) < 50:
            counts[f"empty_{method}"] += 1
            continue

        struct = parse_rejection_structure(text)
        struct["application_number"] = app
        struct["ocr_method"] = method
        struct["generated_at"] = _utc_now()
        (STRUCT_DIR / f"{app}.json").write_text(
            json.dumps(struct, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        counts[f"structured_{method}"] += 1
        processed += 1
        if args.limit and processed >= args.limit:
            break
        if processed % 25 == 0:
            print(f"  [ocr] processed={processed} | {dict(counts.most_common(6))}")
    return dict(counts)


def write_index(targets: List[Dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as f:
        for t in targets:
            app = t["application_number"]
            pdf_path = _pdf_path(app)
            txt_path = TXT_DIR / f"{app}.txt"
            struct_path = STRUCT_DIR / f"{app}.json"
            entry = {
                "application_number": app,
                "doc_type": t.get("doc_type", ""),
                "has_url": bool(t.get("url")),
                "pdf_path": str(pdf_path.relative_to(REPO_ROOT)) if pdf_path.exists() else "",
                "txt_path": str(txt_path.relative_to(REPO_ROOT)) if txt_path.exists() else "",
                "struct_path": str(struct_path.relative_to(REPO_ROOT)) if struct_path.exists() else "",
                "legacy_txt_path": t.get("legacy_txt_path", ""),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 메인 ────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description="B2 거절결정서 PDF 다운로드 + OCR + 구조화")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--full", action="store_true", help="download + ocr + index")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dl-interval", type=float, default=DEFAULT_DL_INTERVAL)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    _ensure_dirs()
    load_dotenv(REPO_ROOT / ".env")
    records = _load_jsonl(args.dataset)
    targets = _collect_targets(records)
    has_url = sum(1 for t in targets if t["url"])
    has_legacy = sum(1 for t in targets if t["legacy_txt_path"])
    print(f"[input] records={len(records)} has_url={has_url} has_legacy_raw={has_legacy}")

    if args.plan:
        # PDF 다운로드 가능 = URL 있는 것 + legacy 텍스트 (다운로드 불필요)
        print(f"[plan] downloadable_pdfs={has_url} legacy_text_only={has_legacy} total_processable={has_url + has_legacy}")
        return

    if args.full or args.download:
        print("[download] starting...")
        dl_counts = download_phase(targets, args)
        print(f"[download] {dl_counts}")
    if args.full or args.ocr:
        print("[ocr] starting...")
        ocr_counts = ocr_phase(targets, args)
        print(f"[ocr] {ocr_counts}")
    if args.full or args.index:
        write_index(targets)
        print(f"[index] written to {INDEX_FILE}")


if __name__ == "__main__":
    main()
