#!/usr/bin/env python3
"""Ingest ExpDataSet's curated 100-expert profile pool (KR + EN).

Inputs:
  data/experts/curated_profiles_kr.json   — 100 expert profiles (Korean)
  data/experts/curated_profiles_en.json   — 100 expert profiles (English-standardised)

Output:
  data/experts/curated_profiles.parquet   — joined KR+EN flat table
  data/experts/curated_profiles_report.json — schema + distribution stats

The curated pool is reference data from Park 2026a [ExpDataSet v3.3.5]. It serves
as the ablation reference against this term's synthetic generator (gen_experts.py).
See docs/expdataset_alignment.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_KR = ROOT / "data" / "experts" / "curated_profiles_kr.json"
IN_EN = ROOT / "data" / "experts" / "curated_profiles_en.json"
OUT = ROOT / "data" / "experts" / "curated_profiles.parquet"
OUT_REPORT = ROOT / "data" / "experts" / "curated_profiles_report.json"


def _load_records(path: Path) -> list[dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        # Common containers: 'experts', 'profiles', 'data'
        for key in ("experts", "profiles", "data", "records"):
            if key in d and isinstance(d[key], list):
                return d[key]
        raise ValueError(f"could not locate expert list in {path.name}; top keys: {list(d.keys())}")
    raise ValueError(f"unexpected JSON type in {path.name}: {type(d).__name__}")


def _flatten(rec: dict, lang: str) -> dict:
    """Compact a nested expert profile into a flat row."""
    flat = {f"{lang}_{k}": v for k, v in rec.items() if isinstance(v, (str, int, float, bool, type(None)))}
    # Special handling for common list fields → pipe-joined string for parquet friendliness
    for k, v in rec.items():
        if isinstance(v, list):
            flat[f"{lang}_{k}"] = "|".join(str(x) for x in v if x is not None)
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, (str, int, float, bool, type(None))):
                    flat[f"{lang}_{k}_{kk}"] = vv
                elif isinstance(vv, list):
                    flat[f"{lang}_{k}_{kk}"] = "|".join(str(x) for x in vv if x is not None)
    return flat


def main() -> None:
    if not IN_KR.exists() or not IN_EN.exists():
        print("ERROR: curated profile JSONs not found. Copy from ExpDataSet first.", file=sys.stderr)
        sys.exit(1)

    kr_records = _load_records(IN_KR)
    en_records = _load_records(IN_EN)
    print(f"loaded {len(kr_records)} KR profiles, {len(en_records)} EN profiles")

    kr_id_field = next((k for k in kr_records[0] if "id" in k.lower()), None) or "expert_id"
    en_id_field = next((k for k in en_records[0] if "id" in k.lower()), None) or "expert_id"
    print(f"KR id field: {kr_id_field}, EN id field: {en_id_field}")

    kr_by_id = {r.get(kr_id_field): r for r in kr_records}
    en_by_id = {r.get(en_id_field): r for r in en_records}
    common_ids = sorted(set(kr_by_id) & set(en_by_id))
    only_kr = sorted(set(kr_by_id) - set(en_by_id))
    only_en = sorted(set(en_by_id) - set(kr_by_id))

    rows: list[dict] = []
    for eid in common_ids:
        kr = _flatten(kr_by_id[eid], "kr")
        en = _flatten(en_by_id[eid], "en")
        row = {"expert_id": eid, **kr, **en, "cohort": "curated_v1"}
        rows.append(row)
    for eid in only_kr:
        rows.append({"expert_id": eid, **_flatten(kr_by_id[eid], "kr"), "cohort": "curated_v1_kr_only"})
    for eid in only_en:
        rows.append({"expert_id": eid, **_flatten(en_by_id[eid], "en"), "cohort": "curated_v1_en_only"})

    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)

    # Try to pull out interesting distributions if columns are recognisable
    candidate_categorical = [
        c for c in df.columns
        if any(t in c.lower() for t in ("category", "specialization", "domain",
                                        "industry", "level", "tier", "type",
                                        "region", "country"))
    ]
    distros = {}
    for c in candidate_categorical[:8]:
        try:
            vc = df[c].dropna().astype(str).value_counts()
            distros[c] = {k: int(v) for k, v in vc.head(20).items()}
        except Exception:  # pragma: no cover
            continue

    report = {
        "source_kr": str(IN_KR.relative_to(ROOT)),
        "source_en": str(IN_EN.relative_to(ROOT)),
        "n_kr": len(kr_records),
        "n_en": len(en_records),
        "n_common": len(common_ids),
        "n_only_kr": len(only_kr),
        "n_only_en": len(only_en),
        "n_columns": int(df.shape[1]),
        "sample_columns": list(df.columns[:30]),
        "categorical_distributions": distros,
        "output": str(OUT.relative_to(ROOT)),
        "citation": "Park 2026a — ExpDataSet v3.3.5 (kukkukpool)",
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ Curated experts ({len(df)} rows, {df.shape[1]} cols) → {OUT.relative_to(ROOT)}")
    print(f"  common KR∩EN: {len(common_ids)}, KR-only: {len(only_kr)}, EN-only: {len(only_en)}")


if __name__ == "__main__":
    main()
