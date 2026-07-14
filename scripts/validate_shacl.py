#!/usr/bin/env python3
"""SHACL Validation runner — checks RDF data against SDKB shapes.

Usage:
  python scripts/validate_shacl.py [--data ontology/sdkb-core-data.ttl]
"""

import argparse
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA   = ROOT / "ontology" / "sdkb-core-data.ttl"
DEFAULT_SHAPES = ROOT / "validation" / "shapes.ttl"
DEFAULT_OWL    = ROOT / "ontology" / "sdkb-core.ttl"


def main():
    parser = argparse.ArgumentParser(description="SDKB SHACL Validator")
    parser.add_argument("--data",   type=Path, default=DEFAULT_DATA, nargs="+",
                        help="Data graph(s) (TTL). 여러 개를 주면 병합해서 검증한다 — "
                             "A-Box 를 빼놓고 검증하면 그 A-Box 에 걸리는 shape 이 vacuous 해진다.")
    parser.add_argument("--shapes", type=Path, default=DEFAULT_SHAPES, help="SHACL shapes (TTL)")
    parser.add_argument("--owl",    type=Path, default=DEFAULT_OWL,    help="OWL ontology (TTL)")
    args = parser.parse_args()

    data_paths = args.data if isinstance(args.data, list) else [args.data]
    for path in data_paths:
        if not path.exists():
            print(f"ERROR: Data file not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Load data graph (+ ontology for class inference)
    data_graph = Graph()
    for path in data_paths:
        data_graph.parse(str(path), format="turtle")
    if args.owl.exists():
        data_graph.parse(str(args.owl), format="turtle")
    print(f"Loaded data: {len(data_graph)} triples")

    # Load shapes
    shapes_graph = Graph()
    shapes_graph.parse(str(args.shapes), format="turtle")
    print(f"Loaded shapes: {len(shapes_graph)} triples")

    # Validate
    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
    )

    print("\n" + "=" * 60)
    if conforms:
        print("✓ SHACL VALIDATION PASSED — all shapes conform.")
    else:
        print("✗ SHACL VALIDATION FAILED — violations found:")
        print(results_text)
    print("=" * 60)

    sys.exit(0 if conforms else 1)


if __name__ == "__main__":
    main()
