#!/usr/bin/env python3
"""그래프 서명 생성기 — 클래스·술어·인스턴스 수를 **코드가 센다** (R4 · 점검 F4·F5).

왜 필요한가. CLAUDE.md §4 는 *"릴리스를 만들 때 그래프 서명(클래스별 인스턴스 수, 술어별
트리플 수)을 CHANGELOG 에 남긴다. 하류는 이 숫자로 자기 스냅샷을 검증한다"* 고 요구하는데
**그 요구를 이행하는 코드가 없었다.** 그래서 README 의 수치가 손으로 관리됐고, 원천이
2026-08-01 에 자란 뒤 넷이 어긋났다(점검 F4·F5). 손으로 고치면 다음에 또 어긋난다.

세는 방식에 대한 두 가지 결정.

**① 명명(named)과 blank node 를 분리해 센다.** `grep -c "owl:Class"` 는 restriction blank node
까지 세므로 `sdkb-patent.ttl` 을 22 로 보고한다 — 명명 클래스는 16 이다. 둘 다 맞는 숫자지만
같은 자리에 쓰면 틀린 말이 된다(§1-4).

**② 없는 것은 0 이 아니라 "미적재"로 적는다.** A-Box 의 큰 층은 KIPRIS 재인출이 선행하므로
빈 체크아웃에서는 존재하지 않는다. 0 이라고 적으면 외부인이 **자기 빌드가 실패했다**고 읽는다.

큰 A-Box(기본 50 MB 초과)는 rdflib 로 다시 파싱하지 않고 **생성기가 이미 낸 리포트**의 트리플
수를 읽는다(`triples_source: "report"`). 899 MB 를 서명 뽑을 때마다 재파싱하면 아무도 돌리지
않게 되고, 돌지 않는 절차는 절차가 아니다.

CLI:
    python scripts/report_graph_signature.py                     # → data/reports/graph_signature.json
    python scripts/report_graph_signature.py --inject            # + README 두 판의 서명 블록 갱신
    python scripts/report_graph_signature.py --check             # 블록이 최신인가 (CI·게이트용)
    python scripts/report_graph_signature.py --parse-large       # 큰 A-Box 도 직접 파싱
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph, RDF, RDFS, OWL
from rdflib.term import BNode

ROOT = Path(__file__).resolve().parents[1]
ONT = ROOT / "ontology"
REPORTS = ROOT / "data" / "reports"
CURATION_SRC = ROOT / "data" / "semiconductor_v0_3.json"
OUT_JSON = REPORTS / "graph_signature.json"
LARGE_BYTES = 50 * 1024 * 1024

MARK_BEGIN = "<!-- sdkb:signature:begin -->"
MARK_END = "<!-- sdkb:signature:end -->"

# T-Box 모듈 — 순서는 읽는 순서다(코어 → 태스크 → 정렬 → 거버넌스).
TBOX_MODULES = [
    "sdkb-core",
    "sdkb-patent",
    "sdkb-rbv",
    "sdkb-foresight",
    "sdkb-commercialization",
    "sdkb-governance",
    "sdkb-governance-kr",
    # PLAN-005 단계 4. 서명에 넣지 않으면 하류가 자기 스냅샷을 이 숫자로 검증할 수 없고,
    # README 의 어휘 규모가 조용히 낡는다(§1-4 · §4).
    "sdkb-priorart-core",
    "sdkb-priorart-semi",
    "sdkb-priorart-kr",
]

# A-Box 층 → 트리플 수를 적어 두는 생성기 리포트. 큰 파일은 이 리포트에서 읽는다.
# 라벨은 영문이다 — 이 블록은 영문 README 와 국문 README 에 **같은 문자열로** 들어간다.
# 판마다 다른 문자열을 넣으면 --check 가 두 판을 따로 관리해야 하고, 그러면 갈라진다.
ABOX_LAYERS = [
    ("sdkb-core-data", "curation graph, instantiated", None),
    ("sdkb-abox-patents", "SIRP rejected patents", "abox_patents_linking_report.json"),
    ("sdkb-abox-prior-art", "examiner-cited prior art", "abox_prior_art_report.json"),
    ("sdkb-abox-claim-features", "claim features", "abox_claim_features_report.json"),
    ("sdkb-abox-b-layer-queries", "B-layer confirmation queries", "abox_b_layer_queries_report.json"),
    ("sdkb-abox-priorart", "prior-art claim profiles, disclosures, examiner elements", "abox_priorart_report.json"),
    ("sdkb-abox-experts-problems", "experts and problems", "abox_linking_report.json"),
    ("sdkb-abox-vendors", "equipment vendors", "abox_vendors_report.json"),
    ("sdkb-governance-kr-instances", "Korea regulatory instances", None),
    ("sdkb-governance-us-instances", "US export-control instances", None),
]


def _named(g: Graph, cls) -> list:
    return [s for s in g.subjects(RDF.type, cls) if not isinstance(s, BNode)]


def tbox_signature(module: str) -> dict:
    path = ONT / f"{module}.ttl"
    if not path.exists():
        return {"module": module, "status": "not_built"}
    g = Graph()
    g.parse(path, format="turtle")
    classes, ops, dps = (_named(g, OWL.Class), _named(g, OWL.ObjectProperty),
                         _named(g, OWL.DatatypeProperty))
    blanks = sum(1 for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, BNode))
    documented = sum(1 for s in classes + ops + dps if (s, RDFS.comment, None) in g)
    return {
        "module": module, "status": "built",
        "classes_named": len(classes), "classes_blank": blanks,
        "object_properties": len(ops), "datatype_properties": len(dps),
        "terms": len(classes) + len(ops) + len(dps),
        "documented": documented,
        "triples": len(g),
    }


def abox_signature(name: str, label: str, report: str | None, parse_large: bool) -> dict:
    path = ONT / f"{name}.ttl"
    row = {"layer": name, "label": label}
    if not path.exists():
        # 비어 있는 것이 설계다 — 채우는 방법은 README 의 결손 표에 있다.
        row["status"] = "not_built"
        return row
    size = path.stat().st_size
    row.update(status="built", bytes=size)
    if size > LARGE_BYTES and not parse_large:
        rp = REPORTS / report if report else None
        if rp and rp.exists():
            row["triples"] = json.loads(rp.read_text(encoding="utf-8")).get("triples")
            row["triples_source"] = f"report:{report}"
        else:
            row["triples"] = None
            row["triples_source"] = "unavailable (리포트 없음 · --parse-large 로 직접 셀 수 있다)"
        return row
    g = Graph()
    g.parse(path, format="turtle")
    row["triples"] = len(g)
    row["triples_source"] = "parsed"
    return row


def curation_signature() -> dict:
    if not CURATION_SRC.exists():
        return {"status": "not_built"}
    d = json.loads(CURATION_SRC.read_text(encoding="utf-8"))
    types = Counter(n.get("type") for n in d["nodes"])
    return {
        "status": "built",
        "version": d.get("version"),
        "nodes": len(d["nodes"]), "edges": len(d["edges"]),
        "node_types": len(types),
        "nodes_by_type": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def build() -> dict:
    args_parse_large = getattr(build, "_parse_large", False)
    tbox = [tbox_signature(m) for m in TBOX_MODULES]
    built = [r for r in tbox if r["status"] == "built"]
    return {
        "note": ("코드가 센 값이다. 손으로 고치지 않는다 — README 의 서명 블록은 "
                 "`make signature-inject` 가 다시 쓴다."),
        "tbox_modules": tbox,
        "tbox_total": {
            "classes_named": sum(r["classes_named"] for r in built),
            "classes_blank": sum(r["classes_blank"] for r in built),
            "object_properties": sum(r["object_properties"] for r in built),
            "datatype_properties": sum(r["datatype_properties"] for r in built),
            "terms": sum(r["terms"] for r in built),
            "documented": sum(r["documented"] for r in built),
            "triples": sum(r["triples"] for r in built),
        },
        "curation_source": curation_signature(),
        "abox_layers": [abox_signature(n, lb, rp, args_parse_large) for n, lb, rp in ABOX_LAYERS],
    }


def render_block(sig: dict) -> str:
    """README 에 넣을 마크다운. **여기서 나온 문자열만이 정본이다.**"""
    t = sig["tbox_total"]
    lines = [
        MARK_BEGIN,
        "<!-- 이 블록은 `make signature-inject` 가 씁니다. 손으로 고치지 마세요 —",
        "     data/reports/graph_signature.json 이 원천입니다. -->",
        "",
        "**T-Box (vocabulary).** Named classes are counted separately from restriction",
        "blank nodes: `grep -c owl:Class` counts both and reports a larger number.",
        "",
        "| Module | Classes (named) | (blank) | ObjectProperty | DatatypeProperty | `rdfs:comment` | Triples |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sig["tbox_modules"]:
        if r["status"] != "built":
            lines.append(f"| `{r['module']}.ttl` | not built | — | — | — | — | — |")
            continue
        lines.append(
            f"| `{r['module']}.ttl` | {r['classes_named']} | {r['classes_blank']} | "
            f"{r['object_properties']} | {r['datatype_properties']} | "
            f"{r['documented']}/{r['terms']} | {r['triples']:,} |")
    if t["terms"]:
        lines.append(
            f"| **Total** | **{t['classes_named']}** | {t['classes_blank']} | "
            f"**{t['object_properties']}** | **{t['datatype_properties']}** | "
            f"**{t['documented']}/{t['terms']}** | {t['triples']:,} |")
    else:
        # 0 을 총계로 적으면 "빌드가 실패했다"로 읽힌다. 아무것도 세지 못했다고 적는다.
        lines.append("| **Total** | nothing built — run `make owl convert` | — | — | — | — | — |")

    c = sig["curation_source"]
    lines += ["", "**Curation graph** (`data/semiconductor_v0_3.json` — the hand-curated source"
              " the core A-Box is generated from)."]
    if c["status"] == "built":
        lines.append("")
        lines.append(f"- **{c['nodes']} nodes / {c['edges']} edges** across "
                     f"**{c['node_types']} node types** (version `{c['version']}`)")
    else:
        lines += ["", "- not built"]

    lines += ["", "**A-Box layers.** `not built` is the expected state on a fresh checkout —"
              " these layers are generated, and the large ones need a KIPRIS key. See"
              " *What is empty, and how to fill it*.", "",
              "| Layer | Content | Triples |", "|---|---|---|"]
    for r in sig["abox_layers"]:
        if r["status"] != "built":
            lines.append(f"| `{r['layer']}.ttl` | {r['label']} | not built |")
            continue
        n = r.get("triples")
        cell = f"{n:,}" if isinstance(n, int) else "unavailable"
        if r.get("triples_source", "").startswith("report:"):
            cell += " ¹"
        lines.append(f"| `{r['layer']}.ttl` | {r['label']} | {cell} |")
    if any(str(r.get("triples_source", "")).startswith("report:") for r in sig["abox_layers"]):
        lines += ["", "¹ counted by the generator that emitted the layer (`data/reports/`)"
                  " rather than re-parsed here — the file is too large to re-parse on every"
                  " signature run. Use `--parse-large` to re-count."]
    lines += ["", MARK_END]
    return "\n".join(lines)


def inject(readmes: list[Path], block: str, check: bool) -> int:
    pat = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.S)
    stale = 0
    for p in readmes:
        if not p.exists():
            print(f"   ! {p.name} 없음 — 건너뛴다")
            continue
        s = p.read_text(encoding="utf-8")
        if not pat.search(s):
            print(f"   ✗ {p.name}: 서명 블록 마커가 없다 ({MARK_BEGIN})")
            stale += 1
            continue
        new = pat.sub(lambda _: block, s)
        if new == s:
            print(f"   ✓ {p.name}: 최신")
        elif check:
            print(f"   ✗ {p.name}: 낡았다 — `make signature-inject` 를 돌려라")
            stale += 1
        else:
            p.write_text(new, encoding="utf-8")
            print(f"   ↻ {p.name}: 서명 블록 갱신")
    return stale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    ap.add_argument("--inject", action="store_true", help="README 두 판의 서명 블록을 다시 쓴다")
    ap.add_argument("--check", action="store_true",
                    help="블록이 최신인지만 본다 (쓰지 않는다 · 낡았으면 종료코드 1)")
    ap.add_argument("--parse-large", action="store_true",
                    help="큰 A-Box 도 rdflib 로 직접 센다 (느리다)")
    args = ap.parse_args()

    build._parse_large = args.parse_large
    sig = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sig, ensure_ascii=False, indent=2), encoding="utf-8")
    t = sig["tbox_total"]
    print(f"[signature] T-Box 명명 클래스 {t['classes_named']} · OP {t['object_properties']} · "
          f"DP {t['datatype_properties']} · 주석 {t['documented']}/{t['terms']} · "
          f"트리플 {t['triples']:,}")
    c = sig["curation_source"]
    if c["status"] == "built":
        print(f"[signature] 큐레이션 원천 {c['nodes']} 노드 / {c['edges']} 엣지 · "
              f"노드 타입 {c['node_types']}종")
    missing = [r["layer"] for r in sig["abox_layers"] if r["status"] != "built"]
    print(f"[signature] A-Box 적재 {len(sig['abox_layers']) - len(missing)}"
          f"/{len(sig['abox_layers'])}층" + (f" · 미적재: {', '.join(missing)}" if missing else ""))
    print(f"[signature] → {args.out.relative_to(ROOT)}")

    if args.inject and not sig["tbox_total"]["terms"]:
        # 빈 체크아웃에서 --inject 를 돌리면 README 가 0 으로 덮인다. 쓰기 전에 막는다.
        print("[signature] ✗ T-Box 가 하나도 빌드되지 않았다 — README 를 덮지 않는다. "
              "`make owl convert` 를 먼저 돌려라.")
        return 1

    if args.inject or args.check:
        stale = inject([ROOT / "README.md", ROOT / "README.ko.md"], render_block(sig), args.check)
        if stale:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
