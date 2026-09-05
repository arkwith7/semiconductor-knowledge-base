#!/usr/bin/env python3
"""PLAN-005 단계 1 — T-Box 용어의 이식성 4분류 (읽기 전용).

PLAN-001 §1.10 이 `pa:` core 에 요구하는 것은 **도메인 어휘 0 · 관할 어휘 0** 이다.
그 불변식을 세우려면 먼저 **현 어휘가 어느 축에 묶여 있는지**를 세어야 한다.

동결된 축 넷 (2026-09-05 · 1차 스크린의 실패에서 나왔다):

  관할  jurisdiction — 의미가 특정 관할의 법조문·심사 절차에 묶인다. KR→US 이식에서 **바뀐다**.
        예: `Rejection_Novelty`(skos:notation "KIPO-29-1") · `groundClause`("조-항-호") · `noticeType`
  도메인 domain — 의미가 반도체 기술에 묶인다. 반도체→바이오 이식에서 **바뀐다**.
        예: `Dopant` · `EquipmentClass` · `realizesProcess`
  원천  provenance — **의미는 중립이고 출처만 특정 API 다.** 이식에서 **바뀌지 않는다.**
        예: `abstractText`(주석에 KIPRIS) — 초록은 관할·도메인과 무관하다.
        **1차 스크린이 이것을 관할로 오분류했다. 축을 가르는 이유가 그것이다.**
  중립  neutral — 두 이식 모두에서 그대로. `pa:` core 후보.

판정은 **레이블 문자열이 아니라 구조를 먼저 본다**(1차 스크린의 두 번째 실패):
  ① `skos:notation` 이 관할 코드(`KIPO-`·`USPTO-`·`EPO-`)면 관할.
  ② 술어는 `rdfs:domain`/`rdfs:range` 가 도메인 클래스를 가리키면 도메인.
     **같은 규칙을 관할 축에도 대칭으로 적용한다** — 관할로 판정된 클래스를 domain/range 로
     갖는 술어는 관할이다. 비대칭이면 도메인만 구조로 잡히고 관할은 텍스트에만 걸린다.
  ③ 클래스는 `rdfs:subClassOf` 상향 폐포에 도메인 뿌리가 있으면 도메인.
  ④ 그 다음에만 텍스트를 본다. **단어 경계로 맞춘다** — 1차 스크린은 "EAR"를 *appear*
     안에서 맞혀 `patent` 를 관할로 보냈다.

**자동 판정이 닿지 않는 것은 `판단필요` 로 남긴다.** 표를 채우려고 추측하지 않는다(§7 보고 방식).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
ONT = "https://w3id.org/sdkb/ont/"
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
OUT = ROOT / "data" / "reports" / "term_portability.json"

TBOX = ["sdkb-core.ttl", "sdkb-patent.ttl", "sdkb-commercialization.ttl",
        "sdkb-foresight.ttl", "sdkb-rbv.ttl", "sdkb-governance.ttl", "sdkb-governance-kr.ttl"]

# 반도체 기술에 묶인 뿌리 클래스 — featureConcept range 합집합과 그 이웃
DOMAIN_ROOTS = {"Process", "SubProcess", "Device", "Material", "Equipment", "EquipmentClass",
                "EquipmentModel", "Metrology", "Parameter", "Dopant", "Acceptor", "Donor",
                "FailureMode", "RootCause", "Mitigation", "Skill", "TechnologyNode",
                "ExtrinsicSemiconductor", "DopingRelation", "EquipmentState"}

JUR_TEXT = [r"제\s?\d+조", r"특허법", r"의견제출통지서", r"거절결정서", r"조-항-호",
            r"\bKIPO\b", r"\bUSPTO\b", r"\bEPO\b", r"특허청", r"산업기술보호법",
            r"국가핵심기술", r"수출통제", r"\bEAR\b", r"\bECCN\b", r"\bBIS\b", r"심사관"]
PROV_TEXT = [r"\bKIPRIS\b", r"\bSIRP\b", r"\bKSIA\b", r"SemicONTO", r"\bNIST\b", r"\bSCIP\b"]
DOM_TEXT = [r"반도체", r"semiconductor", r"웨이퍼", r"wafer", r"식각", r"\betch\w*",
            r"플라즈마", r"plasma", r"노광", r"litho\w*", r"증착", r"deposition",
            r"\bCMP\b", r"\bEUV\b", r"도핑", r"dopant", r"박막", r"게이트", r"\bgate\b",
            r"장비", r"equipment", r"공정", r"소자", r"불량", r"계측", r"metrology",
            r"전공정", r"후공정", r"실리콘", r"silicon"]


def hit(text: str, pats: list[str]) -> list[str]:
    return [p for p in pats if re.search(p, text, re.IGNORECASE)]


def build():
    g = Graph()
    per_file = {}
    for f in TBOX:
        sub = Graph(); sub.parse(ROOT / "ontology" / f, format="turtle")
        for t in sub:
            g.add(t)
        per_file[f] = {str(s)[len(ONT):] for s in set(sub.subjects())
                       if isinstance(s, URIRef) and str(s).startswith(ONT)}
    return g, per_file


def closure(g: Graph, s: URIRef, pred) -> set[str]:
    seen, stack = set(), [s]
    while stack:
        cur = stack.pop()
        for o in g.objects(cur, pred):
            if isinstance(o, URIRef) and str(o).startswith(ONT):
                n = str(o)[len(ONT):]
                if n not in seen:
                    seen.add(n); stack.append(o)
    return seen


def texts(g: Graph, s: URIRef) -> str:
    out = []
    for p in (RDFS.label, RDFS.comment, SKOS.prefLabel, SKOS.altLabel,
              SKOS.scopeNote, SKOS.definition, SKOS.notation):
        out += [str(o) for o in g.objects(s, p)]
    return " | ".join(out)


def range_domain_terms(g: Graph, s: URIRef) -> set[str]:
    """rdfs:domain/range 가 가리키는 클래스명 — owl:unionOf 안까지 편다."""
    out = set()
    for p in (RDFS.domain, RDFS.range):
        for o in g.objects(s, p):
            if isinstance(o, URIRef) and str(o).startswith(ONT):
                out.add(str(o)[len(ONT):])
            else:
                for u in g.objects(o, OWL.unionOf):
                    node = u
                    while node and node != RDF.nil:
                        for it in g.objects(node, RDF.first):
                            if isinstance(it, URIRef) and str(it).startswith(ONT):
                                out.add(str(it)[len(ONT):])
                        node = next(g.objects(node, RDF.rest), None)
    return out


def classify(g, s, name):
    ev = {}
    txt = texts(g, s)

    # ① 구조 — 관할 코드
    for n in g.objects(s, SKOS.notation):
        if re.match(r"^(KIPO|USPTO|EPO|KR|US|EU)-", str(n)):
            ev["notation"] = str(n)
            return "관할", ev
    # ② 구조 — domain/range 가 도메인 클래스
    rd = range_domain_terms(g, s) & DOMAIN_ROOTS
    if rd:
        ev["domain_range"] = sorted(rd)
        return "도메인", ev
    # ③ 구조 — 클래스 상향 폐포
    up = closure(g, s, RDFS.subClassOf) & DOMAIN_ROOTS
    if up:
        ev["subClassOf*"] = sorted(up)
        return "도메인", ev
    if name in DOMAIN_ROOTS:
        ev["root"] = name
        return "도메인", ev
    # ④ 텍스트 — 단어 경계
    j, d, pv = hit(txt, JUR_TEXT), hit(txt, DOM_TEXT), hit(txt, PROV_TEXT)
    if j:
        ev["text_jur"] = j
        return "관할", ev
    if d:
        ev["text_dom"] = d
        return "도메인", ev
    if pv:
        ev["text_prov"] = pv
        return "원천", ev
    return "판단필요", ev


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    g, per_file = build()
    terms = sorted({str(s)[len(ONT):] for s in set(g.subjects())
                    if isinstance(s, URIRef) and str(s).startswith(ONT)})
    rows = []
    for n in terms:
        s = URIRef(ONT + n)
        kinds = sorted({str(o).split("#")[-1] for o in g.objects(s, RDF.type)})
        cls, ev = classify(g, s, n)
        rows.append({"term": n, "rdf_type": kinds, "axis": cls, "evidence": ev,
                     "files": sorted(f for f, ts in per_file.items() if n in ts)})
    # 2차 — 관할 축의 구조 전파 (①③ 과 같은 규칙의 대칭 적용)
    jur_roots = {r["term"] for r in rows
                 if r["axis"] == "관할" and "owl:Class" in " ".join(r["rdf_type"])}
    jur_roots |= {r["term"] for r in rows if r["axis"] == "관할"
                  and any(k.endswith("Class") for k in r["rdf_type"])}
    for r in rows:
        if r["axis"] != "판단필요":
            continue
        s_ = URIRef(ONT + r["term"])
        touched = range_domain_terms(g, s_) & jur_roots
        up = closure(g, s_, RDFS.subClassOf) & jur_roots
        if touched or up:
            r["axis"] = "관할"
            r["evidence"]["jur_structure"] = sorted(touched | up)

    tally = Counter(r["axis"] for r in rows)
    by_file = {f: Counter(r["axis"] for r in rows if f in r["files"]) for f in TBOX}
    rep = {"generated": str(date.today()), "plan": "PLAN-005 단계 1 (이식성 4분류)",
           "read_only": True, "terms_total": len(rows), "axes": dict(tally),
           "by_file": {f: dict(c) for f, c in by_file.items()}, "detail": rows}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SDKB 자체 T-Box 용어 {len(rows)}건 — 이식성 4분류\n")
    for k in ("중립", "판단필요", "원천", "도메인", "관할"):
        if tally.get(k):
            print(f"  {k:6} {tally[k]:4}")
    print(f"\n{'파일':34}{'관할':>6}{'도메인':>7}{'원천':>6}{'판단필요':>9}")
    for f in TBOX:
        c = by_file[f]
        print(f"{f:34}{c['관할']:6}{c['도메인']:7}{c['원천']:6}{c['판단필요']:9}")
    print(f"\n→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
