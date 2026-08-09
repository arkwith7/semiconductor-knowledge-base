from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY_DATASET = REPO_ROOT / "data/processed/etching_reject_web_poc_dataset.jsonl"
DEFAULT_BASE_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
DEFAULT_NORMALIZED_LEGACY = REPO_ROOT / "data/processed/etching_reject_web_poc_dataset.semiconductor_schema.jsonl"
DEFAULT_MERGED_OUTPUT = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"

LEGACY_STRATEGY_METADATA: Dict[str, Dict[str, Any]] = {
    "plasma_H01J37": {
        "validated_web_query": '(플라즈마 식각+"plasma etch"+RIE)*(반도체+웨이퍼)',
        "collection_stage": "etch_core",
        "process_family": "etch",
        "value_chain": ["process", "equipment"],
        "strategy_validation_status": "legacy-web-ocr-import-20260506",
    },
    "wet_solution_kw": {
        "validated_web_query": '(습식 식각+식각 용액+에칭 용액)*(반도체+질화막+산화막)',
        "collection_stage": "etch_core",
        "process_family": "etch",
        "value_chain": ["process", "material"],
        "strategy_validation_status": "legacy-web-ocr-import-20260506",
    },
    "profile_H01L21": {
        "validated_web_query": '(반도체+식각+트렌치)*(측벽+선택비+프로파일+패턴)',
        "collection_stage": "etch_core",
        "process_family": "etch",
        "value_chain": ["process", "device"],
        "strategy_validation_status": "legacy-web-ocr-import-20260506",
    },
}


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
    tmp_path.replace(path)


def _app_no(row: Dict[str, Any]) -> str:
    return str((row.get("target_patent") or {}).get("application_number") or "").strip()


def _normalize_legacy_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(record)
    meta = deepcopy(normalized.get("meta") or {})
    strategy_name = str(meta.get("search_strategy") or "").strip()
    strategy_meta = LEGACY_STRATEGY_METADATA.get(
        strategy_name,
        {
            "validated_web_query": str(meta.get("validated_web_query") or ""),
            "collection_stage": "etch_core",
            "process_family": "etch",
            "value_chain": ["process"],
            "strategy_validation_status": "legacy-web-ocr-import-20260506",
        },
    )

    note_parts = [
        "Legacy record imported from etching_reject_web_poc_dataset.jsonl.",
        "ground_truth_evidence comes from OCR'd examiner-notice text rather than KIPRIS Plus API.",
    ]
    detail_notes = str(meta.pop("detail_notes", "")).strip()
    if detail_notes:
        note_parts.append(detail_notes)

    normalized["meta"] = {
        "source": str(meta.get("source") or "kipris_web_advanced_search"),
        "collection_plan": "legacy_etch_web_poc_import",
        "collection_stage": strategy_meta["collection_stage"],
        "search_strategy": strategy_name,
        "search_query": str(meta.get("search_query") or ""),
        "validated_web_query": str(
            meta.get("validated_web_query") or strategy_meta["validated_web_query"] or ""
        ),
        "cohort_scope": "semiconductor_fullstack_rejected_patents",
        "process_family": strategy_meta["process_family"],
        "value_chain": list(strategy_meta["value_chain"]),
        "strategy_validation_status": strategy_meta["strategy_validation_status"],
        "collection_ts": str(meta.get("collection_ts") or ""),
        "evidence_document_type": str(meta.get("evidence_document_type") or ""),
        "evidence_document_url": str(meta.get("evidence_document_url") or ""),
        "admin_documents": list(meta.get("admin_documents") or []),
        "notes": " ".join(part for part in note_parts if part),
    }
    return normalized


def _dedupe_keep_first(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    skipped = 0
    for row in rows:
        app_no = _app_no(row)
        if not app_no:
            skipped += 1
            continue
        if app_no in seen:
            skipped += 1
            continue
        seen.add(app_no)
        deduped.append(row)
    return deduped, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize legacy etching_reject_web_poc_dataset rows into the semiconductor dataset schema "
            "and merge them into the canonical semiconductor industry dataset."
        )
    )
    parser.add_argument("--legacy-dataset", type=Path, default=DEFAULT_LEGACY_DATASET)
    parser.add_argument("--base-dataset", type=Path, default=DEFAULT_BASE_DATASET)
    parser.add_argument("--normalized-legacy-out", type=Path, default=DEFAULT_NORMALIZED_LEGACY)
    parser.add_argument("--merged-out", type=Path, default=DEFAULT_MERGED_OUTPUT)
    args = parser.parse_args()

    legacy_rows = _load_jsonl(args.legacy_dataset)
    base_rows = _load_jsonl(args.base_dataset)

    normalized_legacy = [_normalize_legacy_record(row) for row in legacy_rows]
    deduped_legacy, legacy_dup_skips = _dedupe_keep_first(normalized_legacy)
    _write_jsonl(args.normalized_legacy_out, deduped_legacy)

    merged_rows, merged_dup_skips = _dedupe_keep_first([*base_rows, *deduped_legacy])
    _write_jsonl(args.merged_out, merged_rows)

    base_apps = {_app_no(row) for row in base_rows if _app_no(row)}
    imported_legacy = sum(1 for row in deduped_legacy if _app_no(row) not in base_apps)

    print(
        json.dumps(
            {
                "legacy_rows": len(legacy_rows),
                "base_rows": len(base_rows),
                "normalized_legacy_rows": len(deduped_legacy),
                "legacy_duplicate_skips": legacy_dup_skips,
                "legacy_imported_into_merged": imported_legacy,
                "merged_rows": len(merged_rows),
                "merged_duplicate_skips": merged_dup_skips,
                "normalized_legacy_out": str(args.normalized_legacy_out),
                "merged_out": str(args.merged_out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()