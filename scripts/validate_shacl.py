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
    # PLAN-005 단계 2-B — claim-features A-Box(11.87M 트리플)는 rdfs 물질화를 얹으면 이 기계에서
    # 돌지 않는다(파싱만으로 최대 RSS 15.7 GB · 가용 25 GB). 그 층의 shape 들은 targetClass 와
    # sh:class 가 A-Box·T-Box 에 **명시 타이핑**되어 있어 추론 없이도 타깃을 잡는다 —
    # 실측: inference=none 으로 186초에 완주하고 위반 0. 느슨하게 만든 것이 아니라,
    # 추론이 필요 없는 shape 에서 추론 비용만 뺀 것이다. 기본값은 rdfs 그대로 둔다.
    parser.add_argument("--inference", default="rdfs", choices=["rdfs", "owlrl", "both", "none"],
                        help="pySHACL 추론 모드 (기본 rdfs)")
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
    # 타깃 계수 — shape 이 **실물에 걸렸는지** 를 출력으로 남긴다. 0 이면 vacuous 통과이고,
    # 그것은 통과가 아니라 게이트 부재다(§4 · 부채 대장 4번이 그 사고였다).
    from rdflib.namespace import RDF as _RDF
    import rdflib as _rl
    SH = _rl.Namespace("http://www.w3.org/ns/shacl#")
    for cls in sorted({str(o) for o in shapes_graph.objects(None, SH.targetClass)}):
        n = len(set(data_graph.subjects(_RDF.type, _rl.URIRef(cls))))
        print(f"  target {cls.rsplit('/', 1)[-1].rsplit('#', 1)[-1]}: {n} 노드"
              + ("   ← ⚠ 타깃 0 (vacuous)" if n == 0 else ""))

    # Validate
    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference=args.inference,
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
