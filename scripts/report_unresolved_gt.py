"""Generate unresolved GT report with KR vs Foreign/Unknown split.

Output:
  data/processed/unresolved_gt_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.citation_norm import parse as parse_citation  # noqa: E402
from kipris_dataset.dataset_paths import CANONICAL_SEMICONDUCTOR_DATASET  # noqa: E402

DEFAULT_DATASET = CANONICAL_SEMICONDUCTOR_DATASET
DEFAULT_RAW = REPO_ROOT / "data/raw"
DEFAULT_OUTPUT = REPO_ROOT / "data/processed/unresolved_gt_report.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _alnum_upper(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"dataset not found: {path}")
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


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


def main() -> None:
    ap = argparse.ArgumentParser(description="Report unresolved GT with KR/Foreign split")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    rows = _load_jsonl(args.dataset)

    total_gt = 0
    total_unresolved = 0

    bucket_total = {"KR": 0, "FOREIGN_OR_UNKNOWN": 0}
    bucket_unresolved = {"KR": 0, "FOREIGN_OR_UNKNOWN": 0}

    by_country_total: Dict[str, int] = {}
    by_country_unresolved: Dict[str, int] = {}
    by_strategy: Dict[str, Dict[str, int]] = {}

    unresolved_examples: List[Dict[str, str]] = []

    for rec in rows:
        target = rec.get("target_patent") or {}
        meta = rec.get("meta") or {}
        app_no = _str(target.get("application_number"))
        strategy = _str(meta.get("search_strategy")) or "UNKNOWN"

        strat = by_strategy.setdefault(
            strategy,
            {
                "gt_total": 0,
                "gt_unresolved": 0,
                "KR_total": 0,
                "KR_unresolved": 0,
                "FOREIGN_OR_UNKNOWN_total": 0,
                "FOREIGN_OR_UNKNOWN_unresolved": 0,
            },
        )

        for raw_id in (rec.get("ground_truth_examiner") or []):
            total_gt += 1
            strat["gt_total"] += 1

            cit = parse_citation(raw_id)
            country = cit.country or "UNKNOWN"
            by_country_total[country] = by_country_total.get(country, 0) + 1

            bucket = "KR" if country == "KR" else "FOREIGN_OR_UNKNOWN"
            bucket_total[bucket] += 1
            strat[f"{bucket}_total"] += 1

            _, resolved = _find_cited_path(args.raw_root, app_no, raw_id)
            if resolved:
                continue

            total_unresolved += 1
            strat["gt_unresolved"] += 1
            bucket_unresolved[bucket] += 1
            strat[f"{bucket}_unresolved"] += 1
            by_country_unresolved[country] = by_country_unresolved.get(country, 0) + 1

            if len(unresolved_examples) < 30:
                unresolved_examples.append(
                    {
                        "application_number": app_no,
                        "search_strategy": strategy,
                        "raw_id": _str(raw_id),
                        "country": country,
                        "bucket": bucket,
                    }
                )

    report = {
        "generated_at": _utc_now(),
        "dataset_path": str(args.dataset),
        "raw_root": str(args.raw_root),
        "totals": {
            "gt_total": total_gt,
            "gt_unresolved": total_unresolved,
            "gt_unresolved_rate": round((total_unresolved / total_gt), 6) if total_gt else 0.0,
        },
        "bucket_totals": bucket_total,
        "bucket_unresolved": bucket_unresolved,
        "bucket_unresolved_rate": {
            "KR": round((bucket_unresolved["KR"] / bucket_total["KR"]), 6) if bucket_total["KR"] else 0.0,
            "FOREIGN_OR_UNKNOWN": round(
                (bucket_unresolved["FOREIGN_OR_UNKNOWN"] / bucket_total["FOREIGN_OR_UNKNOWN"]),
                6,
            ) if bucket_total["FOREIGN_OR_UNKNOWN"] else 0.0,
        },
        "by_country_total": by_country_total,
        "by_country_unresolved": by_country_unresolved,
        "by_strategy": by_strategy,
        "unresolved_examples": unresolved_examples,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"unresolved report written: {args.output} "
        f"(gt_total={total_gt}, unresolved={total_unresolved}, "
        f"KR_unresolved_rate={report['bucket_unresolved_rate']['KR']}, "
        f"foreign_unresolved_rate={report['bucket_unresolved_rate']['FOREIGN_OR_UNKNOWN']})"
    )


if __name__ == "__main__":
    main()
