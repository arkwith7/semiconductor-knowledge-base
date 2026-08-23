#!/usr/bin/env python3
"""§5(4) explanation-precision PILOT (plan §7.4-4).

Before the collection this axis could not be evaluated at all. Phase C gave
`ground_truth_evidence_v2`: 656 structured (target → cited, legal_basis
§29①/②, target_claims) mappings over 270 rejected patents — the examiner's
own statement of WHICH cited invention defeats WHICH claims and on what
legal ground.

This pilot asks: for examiner-confirmed citations, can the ontology produce
a non-empty, plausible *shared-concept explanation* of why the pair overlaps
technically — and at what coverage / precision proxy?

  explanation = concepts(target) ∩ concepts(cited fulltext)
  coverage    = fraction of evidence_v2 pairs with a non-empty explanation
  precision-proxy = mean |shared| and its split by legal basis
                    (§29① novelty vs §29② inventive step)

Pilot scope (270 records) per plan §7.4-4 — NOT the full 1000.
Output: data/reports/explanation_precision_report.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)

#: CR-020 — 특허 본문을 읽는 경로는 `patent-text` 어휘로 해소한다.
#: 기본값(`expert-tag`)에 기대지 않고 명시한다 — 암묵값이 D-49 의 원인이었다.
PROFILE = "patent-text"
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
CORPUS = ROOT / "data" / "patents" / "fulltext_corpus.parquet"
OUT = ROOT / "data" / "reports" / "explanation_precision_report.json"

EXPL_THRESHOLD = 0.70  # plan §5 recommended explanation-precision bar


def concepts(br, text: str):
    out = {}
    for hits in br.extract_from_text(text or "").values():
        for nid, typ in hits:
            out[nid] = typ
    return out


def main() -> int:
    meta = pd.read_parquet(META).set_index("patent_id")
    edges = pd.read_parquet(EDGES)
    corp = pd.read_parquet(CORPUS)
    corp = corp[corp["has_content"]].set_index("doc_id")

    v2 = edges[edges["source_type"] == "evidence_v2"].copy()
    n_map_total = len(v2)
    n_rec_total = v2["target_patent_id"].nunique()

    br = S.make_bridge(ROOT, morph=False, profile=PROFILE)
    ccache: dict[str, dict] = {}

    rows = []
    n_cited_in_corpus = 0
    for tp, cd, lb, tcl in zip(v2["target_patent_id"], v2["cited_doc_id"],
                               v2["legal_basis"], v2["target_claims"]):
        if tp not in meta.index or cd not in corp.index:
            continue
        n_cited_in_corpus += 1
        r = meta.loc[tp]
        qtext = f"{r.get('title') or ''} {r.get('abstract') or ''} {r.get('claim1') or ''}"
        if tp not in ccache:
            ccache[tp] = concepts(br, qtext)
        if cd not in ccache:
            cr = corp.loc[cd]
            ccache[cd] = concepts(br, f"{cr.get('title') or ''} {cr.get('abstract') or ''}")
        qc, dc = ccache[tp], ccache[cd]
        shared = set(qc) & set(dc)
        rows.append({
            "target": tp, "cited": cd,
            "legal_basis": (lb or "").strip() or "?",
            "n_target_claims": len([x for x in (tcl or "").split("|") if x]),
            "n_shared": len(shared),
            "explained": bool(shared),
            "shared_types": Counter(qc[s] for s in shared),
            "shared": sorted(shared),
        })

    n = len(rows)
    n_expl = sum(r["explained"] for r in rows)
    cov = round(n_expl / n, 4) if n else 0.0
    mean_shared = round(sum(r["n_shared"] for r in rows) / n, 3) if n else 0.0
    mean_shared_when_expl = round(
        sum(r["n_shared"] for r in rows if r["explained"]) / n_expl, 3
    ) if n_expl else 0.0

    by_lb = defaultdict(lambda: [0, 0])  # legal_basis -> [explained, total]
    for r in rows:
        by_lb[r["legal_basis"]][0] += int(r["explained"])
        by_lb[r["legal_basis"]][1] += 1
    type_dist = Counter()
    for r in rows:
        type_dist.update(r["shared_types"])

    sample = [
        {"target": r["target"], "cited": r["cited"],
         "legal_basis": r["legal_basis"], "shared": r["shared"][:6]}
        for r in sorted(rows, key=lambda x: -x["n_shared"])[:8]
    ]

    report = {
        "pilot_scope": "ground_truth_evidence_v2 (plan §7.4-4 — 270 rec / 656 map)",
        "evidence_v2_mappings_total": int(n_map_total),
        "evidence_v2_records_total": int(n_rec_total),
        "pairs_with_cited_in_content_corpus": int(n_cited_in_corpus),
        "explanation_coverage": cov,
        "explanation_threshold": EXPL_THRESHOLD,
        "meets_threshold": bool(cov >= EXPL_THRESHOLD),
        "mean_shared_concepts": mean_shared,
        "mean_shared_when_explained": mean_shared_when_expl,
        "coverage_by_legal_basis": {
            k: {"explained": v[0], "total": v[1],
                "rate": round(v[0] / v[1], 4) if v[1] else 0.0}
            for k, v in sorted(by_lb.items())
        },
        "shared_concept_type_distribution": dict(type_dist.most_common()),
        "top_explained_samples": sample,
        "notes": [
            "Explanation = ontology concepts shared by target and examiner-"
            "cited fulltext; coverage = non-empty-explanation rate.",
            "PILOT (270 rec) — not the full corpus; bridge morph=False "
            "(substring fallback, kiwipiepy absent).",
            "§29① = novelty (KR Patent Act 29(1)); §29② = inventive step.",
            "This axis was UNMEASURABLE before the Phase C collection.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"evidence_v2: {n_map_total} maps / {n_rec_total} records")
    print(f"pairs w/ cited in content corpus: {n_cited_in_corpus}")
    print(f"explanation coverage: {cov:.4f}  (threshold {EXPL_THRESHOLD}) "
          f"-> {'MEETS' if cov >= EXPL_THRESHOLD else 'BELOW'}")
    print(f"mean shared concepts: {mean_shared} "
          f"(when explained: {mean_shared_when_expl})")
    print("by legal basis:")
    for k, v in sorted(by_lb.items()):
        print(f"  {k:6} {v[0]:4}/{v[1]:4}  rate={v[0]/v[1] if v[1] else 0:.4f}")
    print(f"✓ report → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
