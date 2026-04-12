#!/usr/bin/env python3
"""Week 1 — Baseline parser: extract schema report, nodes/edges Parquet from semiconductor_v0_3.json.

Outputs:
  data/schema_report.json   — structure summary (types, predicates, provenance stats)
  data/nodes.parquet        — flat node table
  data/edges.parquet        — flat edge table
"""

import json
import hashlib
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "semiconductor_v0_3.json"
OUT_DIR = ROOT / "data"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def flatten_provenance(prov: dict) -> dict:
    """Flatten nested provenance dict into prefixed columns."""
    flat = {}
    for k, v in prov.items():
        if k == "cross_ref":
            flat["prov_cross_ref_count"] = len(v) if isinstance(v, list) else 0
            flat["prov_cross_ref_sources"] = (
                ";".join(cr.get("source", "") for cr in v) if isinstance(v, list) else ""
            )
        elif isinstance(v, (str, int, float, bool)):
            flat[f"prov_{k}"] = v
    return flat


def check_referential_integrity(nodes: list, edges: list) -> dict:
    """Check that all edge src/dst reference existing node IDs."""
    node_ids = {n["id"] for n in nodes}
    dangling_src = []
    dangling_dst = []
    for e in edges:
        if e["src"] not in node_ids:
            dangling_src.append(e["src"])
        if e["dst"] not in node_ids:
            dangling_dst.append(e["dst"])
    return {
        "dangling_src": dangling_src,
        "dangling_dst": dangling_dst,
        "total_dangling": len(dangling_src) + len(dangling_dst),
    }


def check_id_uniqueness(nodes: list) -> dict:
    """Check node ID uniqueness."""
    ids = [n["id"] for n in nodes]
    dupes = [nid for nid, cnt in Counter(ids).items() if cnt > 1]
    return {"duplicate_ids": dupes, "is_unique": len(dupes) == 0}


def extract_node_row(n: dict) -> dict:
    """Extract a flat dict from a node for DataFrame construction."""
    row = {
        "id": n["id"],
        "type": n["type"],
        "canonical_name": n.get("canonical_name", ""),
        "description": n.get("description", ""),
    }
    # Props
    props = n.get("props", {})
    for pk, pv in props.items():
        row[f"prop_{pk}"] = pv
    # Provenance
    prov = n.get("provenance", {})
    row.update(flatten_provenance(prov))
    return row


def extract_edge_row(e: dict) -> dict:
    """Extract a flat dict from an edge for DataFrame construction."""
    row = {
        "src": e["src"],
        "predicate": e["predicate"],
        "dst": e["dst"],
        "weight": e.get("weight"),
        "description": e.get("description", ""),
    }
    prov = e.get("provenance", {})
    row.update(flatten_provenance(prov))
    # Context modifiers (can be dict or list)
    cm = e.get("context_modifiers", {})
    if isinstance(cm, dict):
        for ck, cv in cm.items():
            row[f"ctx_{ck}"] = cv
    elif isinstance(cm, list):
        row["ctx_modifiers"] = ";".join(str(x) for x in cm)
    return row


def main():
    if not IN_PATH.exists():
        print(f"ERROR: {IN_PATH} not found", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load
    with open(IN_PATH, "r", encoding="utf-8") as f:
        g = json.load(f)

    nodes = g["nodes"]
    edges = g["edges"]

    # ── Integrity checks ──────────────────────────────────────
    id_check = check_id_uniqueness(nodes)
    ref_check = check_referential_integrity(nodes, edges)

    # ── Statistics ─────────────────────────────────────────────
    node_types = dict(Counter(n["type"] for n in nodes))
    pred_types = dict(Counter(e["predicate"] for e in edges))

    validation_required_nodes = sum(
        1 for n in nodes if n.get("provenance", {}).get("validation_required", False)
    )
    validation_required_edges = sum(
        1 for e in edges if e.get("provenance", {}).get("validation_required", False)
    )

    interp_dist = dict(
        Counter(n.get("provenance", {}).get("interpretation", "unknown") for n in nodes)
    )

    # ── Schema report ─────────────────────────────────────────
    schema_report = {
        "file": str(IN_PATH.name),
        "file_sha256": file_sha256(IN_PATH),
        "version": g.get("version"),
        "version_id": g.get("version_id"),
        "status": g.get("status"),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "synonyms": len(g.get("synonyms", [])),
            "cases": len(g.get("cases", [])),
            "provenance_sources": len(g.get("provenance_sources", {})),
        },
        "node_types": node_types,
        "predicates": pred_types,
        "validation_required": {
            "nodes": validation_required_nodes,
            "edges": validation_required_edges,
        },
        "interpretation_distribution": interp_dist,
        "integrity": {
            "id_unique": id_check,
            "referential": ref_check,
        },
        "provenance_sources": list(g.get("provenance_sources", {}).keys()),
        "provenance_statistics": g.get("provenance_statistics", {}),
    }

    out_schema = OUT_DIR / "schema_report.json"
    with open(out_schema, "w", encoding="utf-8") as f:
        json.dump(schema_report, f, ensure_ascii=False, indent=2)
    print(f"✓ Schema report → {out_schema}")

    # ── Parquet tables ────────────────────────────────────────
    node_rows = [extract_node_row(n) for n in nodes]
    edge_rows = [extract_edge_row(e) for e in edges]

    node_df = pd.DataFrame(node_rows)
    edge_df = pd.DataFrame(edge_rows)

    out_nodes = OUT_DIR / "nodes.parquet"
    out_edges = OUT_DIR / "edges.parquet"
    node_df.to_parquet(out_nodes, index=False)
    edge_df.to_parquet(out_edges, index=False)
    print(f"✓ Nodes ({len(node_df)} rows) → {out_nodes}")
    print(f"✓ Edges ({len(edge_df)} rows) → {out_edges}")

    # ── Summary ───────────────────────────────────────────────
    print(f"\n=== Baseline Summary ===")
    print(f"  Version:  {g.get('version')}")
    print(f"  Nodes:    {len(nodes)} ({len(node_types)} types)")
    print(f"  Edges:    {len(edges)} ({len(pred_types)} predicates)")
    print(f"  Synonyms: {schema_report['counts']['synonyms']}")
    print(f"  Cases:    {schema_report['counts']['cases']}")
    print(f"  Validation required: {validation_required_nodes} nodes, {validation_required_edges} edges")
    print(f"  ID unique: {id_check['is_unique']}")
    print(f"  Dangling refs: {ref_check['total_dangling']}")

    if not id_check["is_unique"]:
        print(f"  ⚠ Duplicate IDs: {id_check['duplicate_ids']}")
    if ref_check["total_dangling"] > 0:
        print(f"  ⚠ Dangling src: {ref_check['dangling_src']}")
        print(f"  ⚠ Dangling dst: {ref_check['dangling_dst']}")


if __name__ == "__main__":
    main()
