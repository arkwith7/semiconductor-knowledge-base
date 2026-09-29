#!/usr/bin/env python3
"""PLAN-005 R1-스키마 — 논증층 파일럿 A-Box 생성기 (비공개 · 결정적).

**무엇을 만드는가.** R1 정답 해부 카드(`cards_v1.jsonl`) 중 채택 결손 15종에 걸린 54장을
구조화한 레코드(`pilot_v1.jsonl`)를 `sdkb-priorart-argument.ttl` 어휘로 옮긴다. 산출은
`data/sources/notice_dissection/pilot_abox.ttl` — 공개 경로(DENY)에 실리지 않는다.

**왜 파일럿인가.** 새 shape 가 실물에 한 번도 걸리지 않으면 장식이다(CLAUDE.md §4). 공개
그래프의 A-Box 재생성은 정본 파서 교정이 선행이라 이번 범위 밖이다(§20.15(l) · 사용자 결정).

**동결.** 구조화는 LLM 이 했으므로 재현이 보장되지 않는다 — 그래서 R1 카드와 같이 **생성기가
아니라 산출물을 동결**한다: 두 입력의 sha256 이 아래 상수와 다르면 죽는다. 레코드를 고치면
상수도 같은 커밋에서 고친다(§2 5단계 · 양쪽을 함께).

**검사(어기면 SystemExit).** 카드 존재 · (card_id, part) 중복 없음 · 청구항 ⊆ 카드 청구항 ·
문헌 색인이 카드 cited_docs 범위 안 · base ∈ 그 묶음의 문헌 · 빈 묶음은 상식 근거 · 참조
대상이 파일럿 안에 있음 · 논거·좌표·구간관계 이름이 T-Box 개체 · 채택 결손에 걸린 카드는
전부 레코드를 가짐(그 밖의 카드는 없음).

CLI:
    python scripts/build_abox_argument_pilot.py
    python scripts/build_abox_argument_pilot.py --sample          # 사람 확인 표본 10건
    python scripts/build_abox_argument_pilot.py --mark-verified 2026-09-30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD, DCTERMS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config.namespaces import SDKB_DATA, SDKB_PA, SDKB_PA_KR  # noqa: E402
from build_priorart_modules import _emit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources" / "notice_dissection"
CARDS = SRC / "cards_v1.jsonl"
PILOT = SRC / "pilot_v1.jsonl"
VERIFY = SRC / "pilot_v1_verification.json"
OUT = SRC / "pilot_abox.ttl"
ARG_TTL = ROOT / "ontology" / "sdkb-priorart-argument.ttl"

CARDS_SHA = "8e9f29246cdb63e9e96c38eb0ab1a8bf2a5b93d77d60a0c456d8977907412b2e"
PILOT_SHA = "406b3a8ce6d8821e73ea92970a4d63feaeb42e83a50b18b1f97146282280391f"
SAMPLE_SEED = 20260929
SAMPLE_N = 10

#: 2단계에서 결과 전에 동결한 규칙이 뽑은 15종(§2 1–2단계 사용자 승인 2026-09-29).
SELECTED = frozenset({
    "combination-of-documents", "judgment-cross-reference", "dependent-added-limitation",
    "alternative-grounds", "ground-without-document",
    "in-document-locator", "element-to-document-link-missing", "terminology-mapping",
    "numeric-range-overlap", "numeric-threshold-comparison",
    "design-choice-rationale", "effect-predictability", "combination-motivation",
    "obviousness-rationale", "substitution-or-transfer",
})

PA, PAKR, D = SDKB_PA, SDKB_PA_KR, SDKB_DATA
GROUND = {"§29①": PAKR.Ground_29_1, "§29①제1호": PAKR.Ground_29_1, "§29②": PAKR.Ground_29_2}
CURIE = {"pa:": str(PA), "pakr:": str(PAKR)}
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"
SOURCE = "scripts/build_abox_argument_pilot.py -> data/sources/notice_dissection/pilot_v1.jsonl"
PREFIXES = {"pa": str(PA), "pakr": str(PAKR), "xsd": str(XSD), "dcterms": str(DCTERMS),
            "rdf": str(RDF)}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", s).strip("_")


def _curie(c: str) -> URIRef:
    for pfx, ns in CURIE.items():
        if c.startswith(pfx):
            return URIRef(ns + c[len(pfx):])
    raise SystemExit(f"알 수 없는 CURIE: {c}")


def _vocab_individuals() -> dict[str, set[str]]:
    """논거·좌표·구간관계 개체 이름을 T-Box 에서 읽는다 — 하드코딩하면 어휘와 갈라진다."""
    g = Graph().parse(ARG_TTL)
    out = {}
    for cls, key in [(PA.Rationale, "Rationale"), (PA.LocatorType, "Loc"), (PA.IntervalRelation, "Interval")]:
        out[key] = {str(s)[len(str(PA)) + len(key):] for s in g.subjects(RDF.type, cls)}
    return out


def load(check_sha: bool = True) -> tuple[dict, list[dict]]:
    if check_sha:
        for p, want in [(CARDS, CARDS_SHA), (PILOT, PILOT_SHA)]:
            if _sha(p) != want:
                raise SystemExit(f"동결 입력이 바뀌었다: {p.name} sha {_sha(p)[:12]} ≠ {want[:12]}")
    cards = {c["card_id"]: c for c in map(json.loads, CARDS.open(encoding="utf-8"))}
    recs = [json.loads(l) for l in PILOT.open(encoding="utf-8")]
    return cards, recs


def _jkey(r: dict) -> str:
    return r["card_id"] + (f"#{r['part']}" if r.get("part") else "")


def check(cards: dict, recs: list[dict], vocab: dict[str, set[str]]) -> None:
    keys = [_jkey(r) for r in recs]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        raise SystemExit(f"판단 키 중복: {sorted(dup)}")
    in_scope = {cid for cid, c in cards.items() if set(c["deficiency"]) & SELECTED}
    have = {r["card_id"] for r in recs}
    if in_scope - have:
        raise SystemExit(f"채택 결손 카드에 레코드가 없다: {sorted(in_scope - have)}")
    if have - in_scope:
        raise SystemExit(f"범위 밖 카드에 레코드가 있다: {sorted(have - in_scope)}")
    keyset = set(keys)
    for r in recs:
        k, c = _jkey(r), cards.get(r["card_id"])
        if c is None:
            raise SystemExit(f"{k}: 카드가 없다")
        if c["legal_ground"] not in GROUND:
            raise SystemExit(f"{k}: 근거 {c['legal_ground']} 를 LegalGround 로 옮길 수 없다")
        cclaims = {int(x) for x in c["target_claims"]}
        if r.get("claims") is not None and not set(r["claims"]) <= cclaims:
            raise SystemExit(f"{k}: 청구항 {r['claims']} 이 카드 청구항 {sorted(cclaims)} 밖이다")
        nd = len(c["cited_docs"])
        if not r["sets"]:
            raise SystemExit(f"{k}: 근거 묶음이 없다")
        for s in r["sets"]:
            if any(not 0 <= i < nd for i in s["d"]):
                raise SystemExit(f"{k}: 문헌 색인 {s['d']} 이 카드 문헌 {nd}건 밖이다")
            if s["base"] is not None and s["base"] not in s["d"]:
                raise SystemExit(f"{k}: base {s['base']} 가 묶음 문헌 {s['d']} 에 없다")
            if not s["d"] and not s["ck"]:
                raise SystemExit(f"{k}: 문헌도 상식도 없는 빈 묶음")
            bad = set(s["rat"]) - vocab["Rationale"]
            if bad:
                raise SystemExit(f"{k}: 논거 유형이 T-Box 에 없다: {sorted(bad)}")
        for ref in r["refers_to"]:
            if ref not in keyset:
                raise SystemExit(f"{k}: 참조 대상 {ref} 가 파일럿에 없다")
        for ln in r["links"]:
            if ln["d"] is not None and not 0 <= ln["d"] < nd:
                raise SystemExit(f"{k}: 링크 문헌 색인 {ln['d']} 이 범위 밖이다")
            for t, v in ln["loc"]:
                if t not in vocab["Loc"] or not v:
                    raise SystemExit(f"{k}: 좌표 ({t}, {v!r}) 가 올바르지 않다")
            if ln.get("rel") and ln["rel"] not in vocab["Interval"]:
                raise SystemExit(f"{k}: 구간 관계 {ln['rel']} 가 T-Box 에 없다")
            for side in ("cl", "di"):
                iv = ln.get(side)
                if iv is not None and "lo" not in iv and "hi" not in iv:
                    raise SystemExit(f"{k}: 경계 없는 구간")


def _doc_iri(card: dict, i: int) -> URIRef:
    doc = card["cited_docs"][i]
    if doc.startswith("("):                        # 「첨부로만 제시」 등 번호 없는 문헌 — 출원 안에서만 식별
        return D[f"pilot/doc/{card['application']}_unnumbered{i}"]
    return D[f"pilot/doc/{_slug(doc)}"]


def _jiri(key: str) -> URIRef:
    return D["pilot/judgment/" + key.replace("#", "_p")]


def _interval(g: Graph, node: URIRef, iv: dict) -> None:
    g.add((node, RDF.type, PA.NumericInterval))
    if "q" in iv:
        g.add((node, PA.quantityLabel, Literal(iv["q"], datatype=XSD.string)))
    if "lo" in iv:
        g.add((node, PA.lowerBound, Literal(iv["lo"], datatype=XSD.decimal)))
        g.add((node, PA.lowerInclusive, Literal(bool(iv["li"]))))
    if "hi" in iv:
        g.add((node, PA.upperBound, Literal(iv["hi"], datatype=XSD.decimal)))
        g.add((node, PA.upperInclusive, Literal(bool(iv["ui"]))))
    if "unit" in iv:
        g.add((node, PA.unitText, Literal(iv["unit"], datatype=XSD.string)))


def build(cards: dict, recs: list[dict]) -> Graph:
    g = Graph()
    for r in recs:
        c, key = cards[r["card_id"]], _jkey(r)
        j = _jiri(key)
        stem = c["source_file"].removesuffix(".txt")
        exdoc = D[f"examdoc/{stem}"]
        g.add((exdoc, RDF.type, PA.ExaminationDocument))
        g.add((j, RDF.type, PA.ExaminerJudgment))
        g.add((j, PA.assertedIn, exdoc))
        g.add((j, PA.onGround, GROUND[c["legal_ground"]]))
        g.add((j, DCTERMS.source, Literal(SOURCE, datatype=XSD.string)))
        g.add((j, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
        claims = r["claims"] if r.get("claims") is not None else [int(x) for x in c["target_claims"]]
        for n in claims:
            g.add((j, PA.judgesClaim, D[f"claim/rej_{c['application']}_c{n}"]))
        g.add((j, PA.judgmentScope, PA.ScopeAddedLimitation if r["scope"] == "added" else PA.ScopeWholeClaim))
        if r.get("concludes"):
            g.add((j, PA.concludes, _curie(r["concludes"])))
        for ref in r["refers_to"]:
            g.add((j, PA.refersToJudgment, _jiri(ref)))
        for si, s in enumerate(r["sets"], 1):
            sn = URIRef(f"{j}_s{si}")
            g.add((sn, RDF.type, PA.EvidenceSet))
            g.add((j, PA.supportedBy, sn))
            for i in s["d"]:
                g.add((sn, PA.includesDocument, _doc_iri(c, i)))
            if s["base"] is not None:
                g.add((sn, PA.baseDocument, _doc_iri(c, s["base"])))
            if s["ck"]:
                g.add((sn, PA.reliesOnCommonKnowledge, Literal(True)))
            for rat in s["rat"]:
                g.add((sn, PA.hasRationale, PA["Rationale" + rat]))
        for li, ln in enumerate(r["links"], 1):
            lnode = URIRef(f"{j}_l{li}")
            g.add((lnode, RDF.type, PA.EvidenceLink))
            g.add((lnode, PA.partOfJudgment, j))
            if ln["d"] is not None:
                g.add((lnode, PA.inDocument, _doc_iri(c, ln["d"])))
            if ln.get("el"):
                g.add((lnode, PA.forElement, D[f"examiner_element/{stem}_{ln['el']}"]))
            if ln.get("ct"):
                g.add((lnode, PA.claimTerm, Literal(ln["ct"], datatype=XSD.string)))
            if ln.get("dt"):
                g.add((lnode, PA.documentTerm, Literal(ln["dt"], datatype=XSD.string)))
            for ti, (t, v) in enumerate(ln["loc"], 1):
                loc = URIRef(f"{lnode}_loc{ti}")
                g.add((loc, RDF.type, PA.DocumentLocator))
                g.add((lnode, PA.locator, loc))
                g.add((loc, PA.locatorType, PA["Loc" + t]))
                g.add((loc, PA.locatorValue, Literal(v, datatype=XSD.string)))
            if ln.get("cl"):
                _interval(g, URIRef(f"{lnode}_claimed"), ln["cl"])
                g.add((lnode, PA.claimedInterval, URIRef(f"{lnode}_claimed")))
            if ln.get("di"):
                _interval(g, URIRef(f"{lnode}_disclosed"), ln["di"])
                g.add((lnode, PA.disclosedInterval, URIRef(f"{lnode}_disclosed")))
            if ln.get("rel"):
                g.add((lnode, PA.intervalRelation, PA["Interval" + ln["rel"]]))
    return g


HEADER = """# ═══════════════════════════════════════════════════════════════════
# SDKB Prior-Art Argument — 파일럿 A-Box (R1 해부 카드 54장 · 비공개)
#
# **생성물이다. 손으로 고치지 않는다** — scripts/build_abox_argument_pilot.py 가 만든다.
# 원천: data/sources/notice_dissection/pilot_v1.jsonl (sha 동결). 공개 파생 경로에 싣지 않는다.
# ═══════════════════════════════════════════════════════════════════"""


def render() -> str:
    cards, recs = load()
    check(cards, recs, _vocab_individuals())
    return _emit(build(cards, recs), PREFIXES, HEADER)


def sample_keys(recs: list[dict]) -> list[str]:
    keys = sorted(_jkey(r) for r in recs)
    return sorted(random.Random(SAMPLE_SEED).sample(keys, SAMPLE_N))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="사람 확인 표본(결정적)을 인쇄")
    ap.add_argument("--mark-verified", metavar="DATE", help="표본 확인을 마쳤음을 기록")
    args = ap.parse_args()

    cards, recs = load()
    if args.sample or args.mark_verified:
        keys = sample_keys(recs)
        if args.mark_verified:
            VERIFY.write_text(json.dumps({"pilot_sha256": PILOT_SHA, "seed": SAMPLE_SEED,
                                          "sample": keys, "verified": args.mark_verified},
                                         ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"기록: {VERIFY.relative_to(ROOT)}")
        for k in keys:
            print(k)
        return 0

    text = render()
    OUT.write_text(text, encoding="utf-8")
    g = Graph().parse(OUT, format="turtle")
    n = {cls.split("/")[-1]: len(set(g.subjects(RDF.type, cls))) for cls in
         (PA.ExaminerJudgment, PA.EvidenceSet, PA.EvidenceLink, PA.DocumentLocator, PA.NumericInterval)}
    print(f"  {OUT.relative_to(ROOT)}  {len(g)} triples  " + " · ".join(f"{k} {v}" for k, v in n.items()))
    ver = json.loads(VERIFY.read_text()) if VERIFY.exists() else None
    if not ver or ver.get("pilot_sha256") != PILOT_SHA:
        print("  사람 확인: 미완 — `--sample` 표본 10건을 카드와 대조한 뒤 `--mark-verified DATE`")
    else:
        print(f"  사람 확인: {ver['verified']} (표본 {len(ver['sample'])}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
