"""Build per-record quality profile and confidence tiers for the dataset.

Outputs:
  - data/processed/dataset_quality_profile.jsonl
  - data/processed/dataset_quality_report.json

Optional:
  - update each record's meta with P0 quality keys:
      gt_normalized_ok
      cited_resolved_ratio
      evidence_present
      confidence_tier
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.citation_norm import parse as parse_citation  # noqa: E402
from kipris_dataset.dataset_paths import CANONICAL_SEMICONDUCTOR_DATASET  # noqa: E402

DEFAULT_DATASET = CANONICAL_SEMICONDUCTOR_DATASET
DEFAULT_RAW = REPO_ROOT / "data/raw"
DEFAULT_PROFILE = REPO_ROOT / "data/processed/dataset_quality_profile.jsonl"
DEFAULT_REPORT = REPO_ROOT / "data/processed/dataset_quality_report.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _alnum_upper(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"dataset not found: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _find_cited_path(raw_root: Path, app_no: str, original_id: str) -> Tuple[Optional[Path], bool]:
    folder = raw_root / app_no / "cited"
    if not folder.exists():
        return None, False

    needle = _alnum_upper(original_id)
    for path in sorted(folder.glob("*.txt")):
        stem_norm = _alnum_upper(path.stem)
        if needle and needle in stem_norm:
            return path, "UNRESOLVED" not in stem_norm
    return None, False


def _required_target_fields_ok(target: Dict[str, Any]) -> bool:
    required = [
        _str(target.get("application_number")),
        _str(target.get("title")),
        _str(target.get("abstract")),
        _str(target.get("claim1")),
        _str(target.get("ipc")),
        _str(target.get("date")),
    ]
    return all(bool(v) for v in required)


def _tier(
    *,
    required_ok: bool,
    gt_total: int,
    gt_normalized_ok: bool,
    gt_resolved_count: int,
    evidence_present: bool,
) -> str:
    if (
        required_ok
        and gt_total > 0
        and gt_normalized_ok
        and gt_resolved_count > 0
        and evidence_present
    ):
        return "high-confidence"
    if required_ok and gt_total > 0 and gt_normalized_ok:
        return "medium-confidence"
    return "weak-evidence"


def _atomic_write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for rec in rows:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build dataset quality profile and confidence tiers")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--output-profile", type=Path, default=DEFAULT_PROFILE)
    ap.add_argument("--output-report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument(
        "--update-dataset-meta",
        action="store_true",
        help="Write quality fields into each record.meta",
    )
    args = ap.parse_args()

    rows = _load_jsonl(args.dataset)

    profile_rows: List[Dict[str, Any]] = []
    by_tier: Dict[str, int] = {
        "high-confidence": 0,
        "medium-confidence": 0,
        "weak-evidence": 0,
    }
    unresolved_bucket = {"KR": 0, "FOREIGN_OR_UNKNOWN": 0}
    gt_bucket = {"KR": 0, "FOREIGN_OR_UNKNOWN": 0}
    by_strategy: Dict[str, Dict[str, int]] = {}

    for rec in rows:
        target = rec.get("target_patent") or {}
        meta = rec.get("meta") or {}
        app_no = _str(target.get("application_number"))
        strategy = _str(meta.get("search_strategy")) or "UNKNOWN"

        gt_raw = list(rec.get("ground_truth_examiner") or [])
        gt_total = len(gt_raw)
        gt_normalized_count = 0
        gt_resolved_count = 0

        for raw_id in gt_raw:
            cit = parse_citation(raw_id)
            normalized = bool(cit.country and cit.serial)
            if normalized:
                gt_normalized_count += 1

            bucket = "KR" if cit.country == "KR" else "FOREIGN_OR_UNKNOWN"
            gt_bucket[bucket] += 1

            _, resolved = _find_cited_path(args.raw_root, app_no, raw_id)
            if resolved:
                gt_resolved_count += 1
            else:
                unresolved_bucket[bucket] += 1

        evidence_present = any(_str(x) for x in (rec.get("ground_truth_evidence") or []))
        required_ok = _required_target_fields_ok(target)
        gt_normalized_ok = (gt_total > 0) and (gt_normalized_count == gt_total)
        cited_resolved_ratio = (gt_resolved_count / gt_total) if gt_total else 0.0
        confidence_tier = _tier(
            required_ok=required_ok,
            gt_total=gt_total,
            gt_normalized_ok=gt_normalized_ok,
            gt_resolved_count=gt_resolved_count,
            evidence_present=evidence_present,
        )

        by_tier[confidence_tier] += 1
        strat_counts = by_strategy.setdefault(
            strategy,
            {
                "records": 0,
                "high-confidence": 0,
                "medium-confidence": 0,
                "weak-evidence": 0,
            },
        )
        strat_counts["records"] += 1
        strat_counts[confidence_tier] += 1

        profile = {
            "application_number": app_no,
            "search_strategy": strategy,
            "gt_total": gt_total,
            "gt_normalized_count": gt_normalized_count,
            "gt_normalized_ok": gt_normalized_ok,
            "gt_resolved_count": gt_resolved_count,
            "cited_resolved_ratio": round(cited_resolved_ratio, 6),
            "evidence_present": evidence_present,
            "required_target_fields_ok": required_ok,
            "confidence_tier": confidence_tier,
        }
        profile_rows.append(profile)

        if args.update_dataset_meta:
            rec_meta = rec.setdefault("meta", {})
            rec_meta["gt_normalized_ok"] = gt_normalized_ok
            rec_meta["cited_resolved_ratio"] = round(cited_resolved_ratio, 6)
            rec_meta["evidence_present"] = evidence_present
            rec_meta["confidence_tier"] = confidence_tier

    args.output_profile.parent.mkdir(parents=True, exist_ok=True)
    with args.output_profile.open("w", encoding="utf-8") as fh:
        for p in profile_rows:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    total_gt = gt_bucket["KR"] + gt_bucket["FOREIGN_OR_UNKNOWN"]
    total_unresolved = unresolved_bucket["KR"] + unresolved_bucket["FOREIGN_OR_UNKNOWN"]
    report = {
        "generated_at": _utc_now(),
        "dataset_path": str(args.dataset),
        "records": len(rows),
        "tiers": by_tier,
        "gt_totals": {
            "all": total_gt,
            "KR": gt_bucket["KR"],
            "FOREIGN_OR_UNKNOWN": gt_bucket["FOREIGN_OR_UNKNOWN"],
        },
        "gt_unresolved": {
            "all": total_unresolved,
            "KR": unresolved_bucket["KR"],
            "FOREIGN_OR_UNKNOWN": unresolved_bucket["FOREIGN_OR_UNKNOWN"],
        },
        "gt_unresolved_rate": {
            "all": round((total_unresolved / total_gt), 6) if total_gt else 0.0,
            "KR": round((unresolved_bucket["KR"] / gt_bucket["KR"]), 6) if gt_bucket["KR"] else 0.0,
            "FOREIGN_OR_UNKNOWN": round(
                (unresolved_bucket["FOREIGN_OR_UNKNOWN"] / gt_bucket["FOREIGN_OR_UNKNOWN"]),
                6,
            ) if gt_bucket["FOREIGN_OR_UNKNOWN"] else 0.0,
        },
        "by_strategy": by_strategy,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.update_dataset_meta:
        _atomic_write_jsonl(args.dataset, rows)

    print(
        f"quality profile written: {args.output_profile} (records={len(profile_rows)})\n"
        f"quality report written: {args.output_report}\n"
        f"tiers={by_tier}, unresolved(all/KR/foreign)="
        f"{total_unresolved}/{unresolved_bucket['KR']}/{unresolved_bucket['FOREIGN_OR_UNKNOWN']}"
    )


if __name__ == "__main__":
    main()
