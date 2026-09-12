#!/usr/bin/env python3
"""PLAN-005 단계 8 — V6b US 종이 이식(paper port) 리포트. **기계가 센다.**

V6b 가 답하는 것은 *"관할 슬롯이 실제로 작동하는가"* 이지 *"US 에서 성능이 나오는가"* 가 아니다
(PLAN-005 §5 V6(c) · §7-8). 그래서 A-Box 없이 성립하며, 판정량은 넷이다.

  ① L1 변경 라인수 — core·semi·kr 세 파일의 sha256 이 **동결값(FROZEN · 단계 8 착수 시점
     커밋 ead24dd)** 과 같은가. 다르면 `git diff --numstat` 로 줄 수를 세어 **그 값을 적는다**
     (0 이 아니면 어디가 관할 종속이었는지가 결과다 · §5 V6(b) 표).
  ② US 바인딩 프로파일 — 트리플 수 · 개체(LegalGround·ExaminationDocumentType) · import.
  ③ 교차 오염 — us 가 `ont:`·`pa/kr/`·SemicONTO 를 모르고, kr 이 `pa/us/` 를 모르는가.
     관할 바인딩이 도메인이나 타관할을 알면 슬롯이 아니라 열거다.
  ④ SHACL — shapes_priorart × (core + us + governance) 위반 0 · LegalGround·DocumentType 타깃이
     비어 있지 않은가(vacuous 통과를 통과라 부르지 않는다 · 부채 대장 4번).
  ⑤ CQ 불변 — 같은 그래프에서 US 없이 / 있게 CQ 스위트를 두 번 돌려 행 수 벡터가 같은가.
     기준선을 커밋된 cq_report.json 에서 읽지 않는 이유: 그 파일은 6-B 시점(7738d97)이라
     7-A′ 이후의 A-Box 와 맞지 않는다. `--skip-cq` 면 ⑤ 를 건너뛰고 그 사실을 적는다.

결정성: 시각·난수 없음(`GENERATED` 는 상수) · 실행 시간은 기록하지 않는다 · 두 번 렌더가 바이트 동일.

CLI:
    python scripts/report_stage8_paper_port.py [--skip-cq] [--markdown PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.namespaces import SDKB_PA, SDKB_PA_US, SDKB_GOV  # noqa: E402

PA, PAUS, GOV = SDKB_PA, SDKB_PA_US, SDKB_GOV
ONT_DIR = ROOT / "ontology"
US = ONT_DIR / "sdkb-priorart-us.ttl"
KR = ONT_DIR / "sdkb-priorart-kr.ttl"
CORE = ONT_DIR / "sdkb-priorart-core.ttl"
GOVERNANCE = ONT_DIR / "sdkb-governance.ttl"
SHAPES = ROOT / "validation" / "shapes_priorart.ttl"
OUT = ROOT / "data" / "reports" / "priorart_stage8_paper_port.json"

GENERATED = "2026-09-11"          # 상수 — datetime.now() 는 리포트를 매일 다르게 만든다

#: **동결값(결과 전).** 단계 8 착수 시점(main ead24dd · 7-0 이후) 의 세 파일 sha256.
#: 이 표를 고치는 커밋은 L1 을 바꾼 커밋이며, 그 줄 수를 CHANGELOG 에 적어야 한다(§9-8).
FROZEN_COMMIT = "ead24dd"
FROZEN = {
    "ontology/sdkb-priorart-core.ttl": "307875eb7696154d4c2b38b742d89efdc7e332bcf9c70591b1168d1667036d70",
    "ontology/sdkb-priorart-semi.ttl": "d66c932524789269e7bd1a0f936b7987dc020c26abae0aaa2d3487f5c768e6ef",
    "ontology/sdkb-priorart-kr.ttl":   "4e5ed9739f648cf6bc0ba4f91079459895bb56695d6b089389b90784ea56bcf2",
}

# 교차 오염 검사의 표지. 관할 바인딩 파일 텍스트에 이 문자열이 있으면 그 파일은 그것을 "안다".
DOMAIN_MARKS = ("https://w3id.org/sdkb/ont/", "http://w3id.org/SemicONTO/")
KR_MARK = "https://w3id.org/sdkb/pa/kr/"
US_MARK = "https://w3id.org/sdkb/pa/us/"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    p = p.resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


# ── ① L1 ─────────────────────────────────────────────────────────────
def l1_check() -> dict:
    rows, total = [], 0
    for rel, frozen in FROZEN.items():
        now = _sha(ROOT / rel)
        same = now == frozen
        changed = 0
        if not same:
            # 다르면 줄 수를 센다 — 0 이 아닌 값이 곧 결과다(§5 V6(b)).
            r = subprocess.run(["git", "diff", "--numstat", FROZEN_COMMIT, "--", rel],
                               cwd=ROOT, capture_output=True, text=True)
            for line in r.stdout.splitlines():
                a, d, *_ = line.split("\t")
                changed += (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
            changed = changed or -1     # git 이 못 세면 -1 — "0" 으로 읽히지 않게
        rows.append({"file": rel, "frozen_sha256": frozen, "sha256": now,
                     "unchanged": same, "changed_lines": changed})
        total += max(changed, 0)
    return {"frozen_commit": FROZEN_COMMIT, "files": rows,
            "changed_lines_total": total, "all_unchanged": all(r["unchanged"] for r in rows)}


# ── ② US 프로파일 ──────────────────────────────────────────────────
def us_profile(path: Path = US) -> dict:
    g = Graph(); g.parse(path, format="turtle")
    ind = []
    for cls in (PA.LegalGround, PA.ExaminationDocumentType, PA.ElementVerdict):
        for s in sorted(g.subjects(RDF.type, cls)):
            ind.append({
                "iri": str(s), "type": str(cls)[len(str(PA)):],
                "notation": [str(o) for o in g.objects(s, SKOS.notation)],
                "jurisdiction": [str(o) for o in g.objects(s, PA.underJurisdiction)],
                "document_role": [str(o)[len(str(PA)):] for o in g.objects(s, PA.documentRole)],
                "label_en": [str(o) for o in g.objects(s, SKOS.prefLabel) if o.language == "en"],
            })
    counts = {k: sum(1 for i in ind if i["type"] == k)
              for k in ("LegalGround", "ExaminationDocumentType", "ElementVerdict")}
    return {"file": _rel(path), "sha256": _sha(path), "triples": len(g),
            "imports": sorted(str(o) for o in g.objects(None, OWL.imports)),
            "individuals": ind, "counts": counts,
            # 선언하지 않은 것 — 없는 것이 설계다(§1-4 · §7-6).
            "declares_classes": len(list(g.subjects(RDF.type, OWL.Class))),
            "declares_properties": len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
                                   + len(list(g.subjects(RDF.type, OWL.DatatypeProperty))),
            "exact_match": len(list(g.triples((None, SKOS.exactMatch, None))))}


# ── ③ 교차 오염 ─────────────────────────────────────────────────────
def cross_contamination(us: Path = US, kr: Path = KR) -> dict:
    ut, kt = us.read_text(encoding="utf-8"), kr.read_text(encoding="utf-8")
    hits = {
        "us_knows_domain": sum(ut.count(m) for m in DOMAIN_MARKS),
        "us_knows_kr": ut.count(KR_MARK),
        "kr_knows_us": kt.count(US_MARK),
    }
    return {**hits, "clean": all(v == 0 for v in hits.values())}


# ── ④ SHACL ─────────────────────────────────────────────────────────
def shacl_check() -> dict:
    from pyshacl import validate
    data = Graph()
    for p in (CORE, US, GOVERNANCE):
        data.parse(p, format="turtle")
    shapes = Graph(); shapes.parse(SHAPES, format="turtle")
    conforms, _, text = validate(data, shacl_graph=shapes, inference="none")
    targets = {
        "LegalGround": sum(1 for s in data.subjects(RDF.type, PA.LegalGround) if str(s).startswith(str(PAUS))),
        "ExaminationDocumentType": sum(1 for s in data.subjects(RDF.type, PA.ExaminationDocumentType)
                                       if str(s).startswith(str(PAUS))),
    }
    return {"data": [_rel(CORE), _rel(US), _rel(GOVERNANCE)], "shapes": _rel(SHAPES),
            "conforms": bool(conforms), "us_targets": targets,
            "non_vacuous": all(v > 0 for v in targets.values()),
            "report": None if conforms else text}


# ── ⑤ CQ 불변 ──────────────────────────────────────────────────────
def cq_invariance() -> dict:
    from scripts.run_cq import DEFAULT_DATA, CQ_DIR, parse_cq, load_graph, run
    without = [p for p in DEFAULT_DATA if p != US]
    g, loaded, missing = load_graph(without)
    cqs = sorted((parse_cq(p) for p in CQ_DIR.glob("*.rq")), key=lambda c: c.name)
    before = {r.name: r.rows for r in run(g, cqs)}
    g.parse(US, format="turtle")                      # 같은 그래프에 US 만 더한다
    after = {r.name: r.rows for r in run(g, cqs)}
    diff = {k: (before[k], after[k]) for k in before if before[k] != after.get(k)}
    return {"skipped": False, "graph_files_loaded": loaded, "graph_files_missing": missing,
            "n_cq": len(cqs), "rows_without_us": before, "rows_with_us": after,
            "identical": not diff, "diff": diff}


def build_report(skip_cq: bool = False) -> dict:
    rep = {"plan": "PLAN-005 단계 8 · V6b US 종이 이식", "generated": GENERATED,
           "l1": l1_check(), "us": us_profile(), "cross": cross_contamination(),
           "shacl": shacl_check(),
           "cq": {"skipped": True} if skip_cq else cq_invariance()}
    conds = {
        "l1_changed_lines_0": rep["l1"]["changed_lines_total"] == 0 and rep["l1"]["all_unchanged"],
        "cross_clean": rep["cross"]["clean"],
        "shacl_conforms": rep["shacl"]["conforms"],
        "shacl_non_vacuous": rep["shacl"]["non_vacuous"],
        "cq_identical": None if skip_cq else rep["cq"]["identical"],
    }
    decided = [v for v in conds.values() if v is not None]
    rep["conditions"] = conds
    rep["verdict"] = "PASS" if all(decided) else "FAIL"
    rep["verdict_note"] = ("CQ 불변(⑤)은 건너뛰었다 — 판정은 ①–④ 만으로" if skip_cq
                           else "①–⑤ 전부")
    return rep


def render_markdown(rep: dict) -> str:
    L = []
    L.append("# PLAN-005 단계 8 — V6b US 종이 이식 (기계 산출)\n")
    L.append(f"> 생성: `scripts/report_stage8_paper_port.py` · {rep['generated']} · "
             "**손으로 고치지 않는다** — `make stage8-paper-port` 가 다시 만든다. "
             "동결값(`FROZEN`)은 결과 전에 박았다.\n")
    L.append(f"## 판정 — **{rep['verdict']}** ({rep['verdict_note']})\n")
    L.append("| 조건 | 판정 |\n|---|:-:|")
    for k, v in rep["conditions"].items():
        L.append(f"| {k} | {'—' if v is None else ('✓' if v else '✗')} |")
    L.append("")
    l1 = rep["l1"]
    L.append(f"## ① L1 변경 라인수 — **{l1['changed_lines_total']}** (동결 커밋 `{l1['frozen_commit']}`)\n")
    L.append("| 파일 | 동결 sha256 | 현 sha256 | 불변 | 변경 줄 |\n|---|---|---|:-:|---:|")
    for r in l1["files"]:
        L.append(f"| `{r['file']}` | `{r['frozen_sha256'][:12]}` | `{r['sha256'][:12]}` | "
                 f"{'✓' if r['unchanged'] else '✗'} | {r['changed_lines']} |")
    L.append("")
    us = rep["us"]
    L.append(f"## ② US 바인딩 — `{us['file']}` · {us['triples']} 트리플 · sha `{us['sha256'][:12]}`\n")
    L.append(f"import: {', '.join('`'+i+'`' for i in us['imports'])} · 클래스 선언 {us['declares_classes']} · "
             f"술어 선언 {us['declares_properties']} · exactMatch {us['exact_match']} · "
             f"ElementVerdict {us['counts']['ElementVerdict']}(원천 없음 · 넣지 않았다)\n")
    L.append("| 개체 | 유형 | notation | 관할 | 역할 | 라벨 |\n|---|---|---|---|---|---|")
    for i in us["individuals"]:
        L.append(f"| `{i['iri'].split('/')[-1]}` | {i['type']} | {', '.join(i['notation']) or '—'} | "
                 f"{', '.join(j.split('/')[-1] for j in i['jurisdiction'])} | "
                 f"{', '.join(i['document_role']) or '—'} | {', '.join(i['label_en'])} |")
    L.append("")
    c = rep["cross"]
    L.append(f"## ③ 교차 오염 — us→도메인 {c['us_knows_domain']} · us→kr {c['us_knows_kr']} · "
             f"kr→us {c['kr_knows_us']} → {'clean' if c['clean'] else '**오염**'}\n")
    s = rep["shacl"]
    L.append(f"## ④ SHACL — conforms {s['conforms']} · US 타깃 LegalGround {s['us_targets']['LegalGround']} · "
             f"DocumentType {s['us_targets']['ExaminationDocumentType']} · non-vacuous {s['non_vacuous']}\n")
    if s["report"]:
        L.append("```\n" + s["report"] + "\n```\n")
    q = rep["cq"]
    if q.get("skipped"):
        L.append("## ⑤ CQ 불변 — 건너뜀 (`--skip-cq`)\n")
    else:
        L.append(f"## ⑤ CQ 불변 — {q['n_cq']} 개 · US 없이/있게 행 수 벡터 "
                 f"{'**동일**' if q['identical'] else '**상이**'}\n")
        if q["diff"]:
            L.append("| CQ | 없이 | 있게 |\n|---|---:|---:|")
            for k, (a, b) in sorted(q["diff"].items()):
                L.append(f"| {k} | {a} | {b} |")
        else:
            L.append("| CQ | 행 |\n|---|---:|")
            for k, v in sorted(q["rows_with_us"].items()):
                L.append(f"| {k} | {v} |")
        L.append("")
    L.append("## 한계\n")
    L.append("- 이것은 **설계 보증**이다 — US 문헌 회수 성능은 재지 않았고 재지 않는다(PLAN-005 §7-8).")
    L.append("- US 판정 어휘(KSR/TSM · inherency 등)는 원천이 저장소에 없어 넣지 않았다(§1-4). "
             "KR 은 `VerdictWellKnown`·`VerdictDesignChange` 를 갖는다 — 비대칭은 원천의 비대칭이다.")
    L.append("- KR 근거와의 `skos:exactMatch` 를 걸지 않았다 — §29① 은 유예기간이 §102 와 다르고 "
             "§29② 는 §103 KSR 과 같은 판단이 아니다. 읽는 소비자도 없다(§7-6).")
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-cq", action="store_true", help="⑤ CQ 2회 실행을 건너뛴다(≈6분)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--markdown", type=Path, default=None)
    args = ap.parse_args()
    rep = build_report(skip_cq=args.skip_cq)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"→ {_rel(args.out)}")
    if args.markdown:
        args.markdown.write_text(render_markdown(rep), encoding="utf-8")
        print(f"→ {_rel(args.markdown)}")
    print(f"판정 {rep['verdict']} · L1 변경 {rep['l1']['changed_lines_total']} 줄 · "
          f"SHACL {rep['shacl']['conforms']} · 교차 오염 {'0' if rep['cross']['clean'] else '있음'}"
          + ("" if args.skip_cq else f" · CQ 동일 {rep['cq']['identical']}"))
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
