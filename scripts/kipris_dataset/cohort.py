from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

# Etching-focused IPC/CPC hard filter set from ipr-d scope docs.
# Comparison is prefix-based after normalization.
ETCHING_CODE_PREFIXES: Tuple[str, ...] = (
    "H01L21/3065",  # dry etching
    "H01L21/311",   # chemical etching
    "C23F1/",       # chemical etching family
    "C23F4/",       # ion-beam/plasma etching
    "H01J37/32",    # plasma processing apparatus
    "B81C1/",       # MEMS micromachining (incl. etching)
)


def normalize_code(code: str) -> str:
    s = str(code or "").strip().upper()
    return s.replace(" ", "")


def split_codes(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [x.strip() for x in raw.replace(",", "|").split("|")]
        return [v for v in values if v]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def code_matches_etching(code: str) -> bool:
    c = normalize_code(code)
    if not c:
        return False
    return any(c.startswith(prefix) for prefix in ETCHING_CODE_PREFIXES)


def extract_target_codes(record: Dict[str, Any]) -> List[str]:
    tp = (record.get("target_patent") or {}) if isinstance(record, dict) else {}
    biblio = (tp.get("biblio") or {}) if isinstance(tp, dict) else {}
    cls = (biblio.get("classification") or {}) if isinstance(biblio, dict) else {}

    codes: List[str] = []
    codes.extend(split_codes(tp.get("ipc")))
    codes.extend(split_codes(cls.get("ipc")))
    codes.extend(split_codes(cls.get("cpc")))

    out: List[str] = []
    seen = set()
    for c in codes:
        n = normalize_code(c)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def matched_etching_codes(record: Dict[str, Any]) -> List[str]:
    return [c for c in extract_target_codes(record) if code_matches_etching(c)]


def is_etching_target_record(record: Dict[str, Any]) -> bool:
    return bool(matched_etching_codes(record))


def filter_etching_cohort(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if is_etching_target_record(r)]


def annotate_etching_meta(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    meta = dict((out.get("meta") or {}))
    matched = matched_etching_codes(out)
    meta["cohort_scope"] = "etching_hard_filter"
    meta["etching_filter_matched_codes"] = matched
    out["meta"] = meta
    return out