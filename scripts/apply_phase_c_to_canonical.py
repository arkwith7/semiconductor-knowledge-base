"""Phase C 결과(거절결정서 OCR + 구조화)를 canonical JSONL 에 통합.

근거: `docs/dataset_full_collection_runbook.md` Phase C / §5 스키마 확장.

추가 필드 (target_patent.meta 하위):
- `rejection_decision`: {pdf_path, txt_path, structured_path, ocr_method, legal_bases, decision_date}
- `ground_truth_evidence_v2`: list of {cited_id, evidence_phrase_no, target_claims, legal_basis}

기존 `ground_truth_evidence` (legacy) 는 보존.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
STRUCT_DIR = REPO_ROOT / "data/processed/rejection_decisions/structured"
PDF_DIR = REPO_ROOT / "data/processed/rejection_decisions/pdf"
TXT_DIR = REPO_ROOT / "data/processed/rejection_decisions/txt"


def _load_struct(app_no: str) -> Dict[str, Any] | None:
    p = STRUCT_DIR / f"{app_no}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_evidence_v2(struct: Dict[str, Any]) -> List[Dict[str, Any]]:
    """structured.cited_evidence_map → ground_truth_evidence_v2."""
    out: List[Dict[str, Any]] = []
    legal_bases = struct.get("legal_bases") or []
    primary_basis = legal_bases[0]["paragraph"] if legal_bases else ""
    target_claims = struct.get("target_claims") or []
    for phrase_no, cited_id in (struct.get("cited_evidence_map") or {}).items():
        out.append({
            "cited_id": cited_id,
            "evidence_phrase_no": phrase_no,
            "target_claims": target_claims,
            "legal_basis": f"§29{['','①','②','③','④'][int(primary_basis)] if primary_basis.isdigit() and 1<=int(primary_basis)<=4 else ''}",
        })
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def main() -> None:
    recs = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    patched = 0
    evidence_v2_total = 0
    for r in recs:
        app = (r.get("target_patent") or {}).get("application_number", "")
        if not app:
            continue
        s = _load_struct(app)
        if not s:
            continue
        meta = r.setdefault("meta", {})
        pdf = PDF_DIR / f"{app}.pdf"
        txt = TXT_DIR / f"{app}.txt"
        meta["rejection_decision"] = {
            "pdf_path": _rel(pdf) if pdf.exists() else "",
            "txt_path": _rel(txt) if txt.exists() else "",
            "structured_path": _rel(STRUCT_DIR / f"{app}.json"),
            "ocr_method": s.get("ocr_method", ""),
            "legal_bases": s.get("legal_bases", []),
            "decision_date": s.get("decision_date", ""),
        }
        ev = _build_evidence_v2(s)
        if ev:
            meta["ground_truth_evidence_v2"] = ev
            evidence_v2_total += len(ev)
        patched += 1

    # atomic write
    tmp = DATASET.with_suffix(DATASET.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(DATASET)
    print(f"[apply] patched={patched} evidence_v2_total={evidence_v2_total}")


if __name__ == "__main__":
    main()
