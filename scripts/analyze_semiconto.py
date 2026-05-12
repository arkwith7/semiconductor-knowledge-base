#!/usr/bin/env python3
"""Phase 0.2 — Parse SemicONTO v0.2 TTL and emit class/property inventory.

Reads ontology/imports/SemicONTO-0.2.ttl and writes
data/reports/semiconto_analysis.json.

The report is consumed downstream by:
  - scripts/build_semiconto_alignment.py (Phase 0.3)
  - docs/architecture_amendment_sdkb_centric.md (Phase 0.4)

Inventory dimensions:
  - ontology metadata (URI, version, license, creator)
  - classes: own (SemicONTO namespace) vs reused (external IRI)
  - subclass hierarchy and equivalentClass unions
  - object/datatype/annotation properties with domain/range
  - count of OWL restrictions per class (axiom density)
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS

ROOT = Path(__file__).resolve().parent.parent
TTL_PATH = ROOT / "ontology" / "imports" / "SemicONTO-0.2.ttl"
OUT_PATH = ROOT / "data" / "reports" / "semiconto_analysis.json"
SEMICONTO_NS = "http://w3id.org/SemicONTO/"
SEMI = Namespace(SEMICONTO_NS)


def _is_own(uri: str) -> bool:
    """True if URI is in the SemicONTO namespace (own term, not reused)."""
    return uri.startswith(SEMICONTO_NS)


def _local(uri: str) -> str:
    """Last segment of URI, used as a display key."""
    if "#" in uri:
        return uri.rsplit("#", 1)[1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _label(g: Graph, s: URIRef) -> str | None:
    for o in g.objects(s, RDFS.label):
        if isinstance(o, Literal):
            return str(o)
    return None


def _comment(g: Graph, s: URIRef) -> str | None:
    for o in g.objects(s, RDFS.comment):
        if isinstance(o, Literal):
            return str(o)
    return None


def _annotation(g: Graph, s: URIRef, pred: URIRef) -> str | None:
    for o in g.objects(s, pred):
        if isinstance(o, Literal):
            return str(o)
    return None


def _class_kind(uri: str) -> str:
    if _is_own(uri):
        return "own"
    if uri.startswith("http://qudt.org/"):
        return "reused:qudt"
    if uri.startswith("https://w3id.org/mdo/"):
        return "reused:mdo"
    if uri.startswith("http://www.w3.org/ns/prov#"):
        return "reused:prov"
    return "reused:other"


def _named_resource(node) -> str | None:
    """Return URI string for IRI nodes; None for BNodes/Literals.

    Used to skip OWL Restriction blank nodes when listing
    superclasses/equivalents as user-facing class references.
    """
    return str(node) if isinstance(node, URIRef) else None


def collect_ontology_metadata(g: Graph) -> dict:
    ont = URIRef(SEMICONTO_NS)
    return {
        "iri": str(ont),
        "version_iri": _annotation(g, ont, OWL.versionIRI) or _named_resource(
            next(iter(g.objects(ont, OWL.versionIRI)), None)
        ),
        "version_info": _annotation(g, ont, OWL.versionInfo),
        "title": _annotation(g, ont, DCTERMS.title),
        "creator": _annotation(g, ont, DCTERMS.creator),
        "created": _annotation(g, ont, DCTERMS.created),
        "license": _annotation(g, ont, DCTERMS.license),
        "see_also": [str(o) for o in g.objects(ont, RDFS.seeAlso)],
    }


def collect_classes(g: Graph) -> tuple[list[dict], dict]:
    """Return (classes, summary).

    classes: list of {iri, kind, label, comment, super_classes,
                       equivalent_unions, restriction_count}
    summary: aggregates by kind
    """
    classes: dict[str, dict] = {}
    summary: dict[str, int] = defaultdict(int)

    for cls in g.subjects(RDF.type, OWL.Class):
        if isinstance(cls, BNode):
            continue
        uri = str(cls)
        kind = _class_kind(uri)
        summary[kind] += 1
        if uri in classes:
            continue
        supers_named: list[str] = []
        restriction_count = 0
        for sc in g.objects(cls, RDFS.subClassOf):
            if isinstance(sc, BNode):
                restriction_count += 1
            else:
                supers_named.append(str(sc))
        equiv_unions: list[list[str]] = []
        for eq in g.objects(cls, OWL.equivalentClass):
            if isinstance(eq, BNode):
                members: list[str] = []
                for union_list_root in g.objects(eq, OWL.unionOf):
                    # walk RDF list
                    node = union_list_root
                    while node and node != RDF.nil:
                        first = next(iter(g.objects(node, RDF.first)), None)
                        if isinstance(first, URIRef):
                            members.append(str(first))
                        rest = next(iter(g.objects(node, RDF.rest)), None)
                        node = rest
                if members:
                    equiv_unions.append(members)
        classes[uri] = {
            "iri": uri,
            "local": _local(uri),
            "kind": kind,
            "label": _label(g, cls),
            "comment": _comment(g, cls),
            "super_classes": sorted(set(supers_named)),
            "equivalent_unions": equiv_unions,
            "restriction_count": restriction_count,
        }

    return sorted(classes.values(), key=lambda c: (c["kind"], c["local"])), dict(summary)


def collect_properties(g: Graph, prop_type: URIRef) -> list[dict]:
    out: list[dict] = []
    for p in g.subjects(RDF.type, prop_type):
        if isinstance(p, BNode):
            continue
        uri = str(p)
        domains: list[str] = []
        for d in g.objects(p, RDFS.domain):
            if isinstance(d, URIRef):
                domains.append(str(d))
        ranges: list[str] = []
        for r in g.objects(p, RDFS.range):
            if isinstance(r, URIRef):
                ranges.append(str(r))
        sup_props: list[str] = []
        for sp in g.objects(p, RDFS.subPropertyOf):
            if isinstance(sp, URIRef):
                sup_props.append(str(sp))
        is_transitive = (p, RDF.type, OWL.TransitiveProperty) in g
        out.append({
            "iri": uri,
            "local": _local(uri),
            "kind": _class_kind(uri),
            "label": _label(g, p),
            "domain": sorted(set(domains)),
            "range": sorted(set(ranges)),
            "sub_property_of": sorted(set(sup_props)),
            "transitive": is_transitive,
        })
    return sorted(out, key=lambda x: (x["kind"], x["local"]))


def build_hierarchy(classes: list[dict]) -> dict[str, list[str]]:
    """parent_uri -> [child_uri]. Only own-namespace edges shown."""
    h: dict[str, list[str]] = defaultdict(list)
    for c in classes:
        for parent in c["super_classes"]:
            h[parent].append(c["iri"])
    return {k: sorted(v) for k, v in h.items()}


def main() -> None:
    if not TTL_PATH.exists():
        raise SystemExit(f"missing {TTL_PATH} — run Phase 0.1 fetch first")

    g = Graph()
    g.parse(str(TTL_PATH), format="turtle")

    meta = collect_ontology_metadata(g)
    classes, class_summary = collect_classes(g)
    obj_props = collect_properties(g, OWL.ObjectProperty)
    dt_props = collect_properties(g, OWL.DatatypeProperty)
    ann_props = collect_properties(g, OWL.AnnotationProperty)
    hierarchy = build_hierarchy(classes)

    own_classes = [c for c in classes if c["kind"] == "own"]
    report = {
        "source": {
            "file": str(TTL_PATH.relative_to(ROOT)),
            "triples": len(g),
        },
        "ontology": meta,
        "counts": {
            "classes_total": len(classes),
            "classes_own": len(own_classes),
            "classes_by_kind": class_summary,
            "object_properties": len(obj_props),
            "datatype_properties": len(dt_props),
            "annotation_properties": len(ann_props),
        },
        "classes": classes,
        "object_properties": obj_props,
        "datatype_properties": dt_props,
        "annotation_properties": ann_props,
        "subclass_hierarchy": hierarchy,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(
        f"✓ SemicONTO analysis ({len(g)} triples, "
        f"{len(own_classes)} own classes, "
        f"{len(obj_props)} obj props, "
        f"{len(dt_props)} dt props) → {OUT_PATH.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
