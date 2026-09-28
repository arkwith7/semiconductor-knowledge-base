#!/usr/bin/env python3
"""PLAN-005 R1 — 해부 카드를 검사하고 **표현 결손 목록**으로 집계한다 (그래프를 바꾸지 않는다).

설계: [PLAN-005 §20.15](../01.code_spec/plans/PLAN-005-prior-art-tool-qualification.md)

**어휘 인벤토리는 손으로 쓰지 않는다.** 결손 판정(E0~E3)은 *"현 어휘로 이 주장을 적을 수
있는가"* 이므로, 비교 대상인 어휘 목록이 사람의 기억이면 판정이 검증되지 않는다. 그래서 T-Box
TTL 에서 rdflib 로 선언을 긁어 목록을 만들고, 카드의 `verdict_terms` 가 그 목록의 부분집합인지
**기계로 검사한다.** 없는 용어를 적으면 죽는다.

**해부 자체는 LLM(에이전트)이 했다 — 재현이 보장되지 않는다.** 그러므로 이 집계기는 생성기가
아니라 **검사기 + 렌더러**이고, 동결되는 것은 카드 파일의 sha256 이다(§20.8 R2 선례).

검사(하나라도 어기면 SystemExit — 게이트는 무는 것이어야 한다):
  · 표본이 사람 확인을 받았는가(`human_verified`)      ← §1-5 · §20.14(g)
  · 카드의 원천이 표본에 있고 sha256 이 일치하는가
  · 좌표가 있는가(`L<숫자>`) · 인용이 50자 이하인가     ← 인용 최소화 결정
  · `verdict` 가 E0~E3 인가 · `verdict_terms ⊆ 인벤토리`
  · E0 이 아닌 카드에 결손 슬러그가 하나 이상 있는가

사용
  make report-dissection
  python3 scripts/report_r1_dissection.py --inventory
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
SAMPLE = SOURCES / "notice_dissection" / "sample_v1.json"
CARDS = SOURCES / "notice_dissection" / "cards_v1.jsonl"
SCRUB_DIR = SOURCES / "notice_excerpts_scrubbed"
ONTOLOGY = ROOT / "ontology"
REPORT = ROOT / "01.code_spec" / "reports" / "PLAN-005-r1-dissection.md"

#: T-Box 만 본다. A-Box(`sdkb-abox-*`)·인스턴스 파일은 어휘를 선언하는 자리가 아니다(§1-2).
TBOX_GLOBS = ("sdkb-core.ttl", "sdkb-patent.ttl", "sdkb-priorart-*.ttl",
              "sdkb-governance.ttl", "sdkb-governance-kr.ttl", "sdkb-governance-us.ttl",
              "sdkb-commercialization.ttl", "sdkb-foresight.ttl", "sdkb-rbv.ttl")

VERDICTS = ("E0", "E1", "E2", "E3")
VERDICT_MEANING = {
    "E0": "현 자원으로 손실 없이 표현된다",
    "E1": "A-Box 결손 — 담을 술어는 있는데 값·인스턴스가 없다",
    "E2": "T-Box 결손 — 담을 클래스·술어 자체가 없다",
    "E3": "R-Box 결손 — 담을 수는 있으나 추론·제약이 없어 질의로 꺼내지 못한다",
}

#: 결손 계열. **매핑에 없는 슬러그가 있으면 죽는다** — 새 결손을 만들면 어느 층의 문제인지
#: 반드시 말해야 한다. 분류 없는 목록은 개수만 늘고 행동으로 이어지지 않는다.
FAMILY = {
    "A 증거 위치": ("in-document-locator", "reference-numeral-anchor",
                 "figure-or-spectrum-comparison", "claim-chain-in-cited-document"),
    "B 판단 단위 구조": ("combination-of-documents", "judgment-cross-reference", "alternative-grounds",
                    "judgment-unit-boundary", "claim-category-transfer", "dependent-added-limitation",
                    "whole-invention-comparison", "comparison-axis", "property-follows-from-structure",
                    "novelty-implies-inventiveness"),
    "C 요소–문헌 대응": ("element-to-document-link-missing", "element-table-not-ingested",
                    "element-table-caption-missing", "terminology-mapping", "function-equivalence",
                    "substitution-or-transfer", "wording-vs-substance", "negative-limitation"),
    "D 수치·조건": ("numeric-range-overlap", "numeric-threshold-comparison", "measure-equivalence",
                 "conditional-limitation", "measurement-context-condition", "numeric-or-geometric-condition",
                 "relational-process-condition", "relational-geometry-comparison",
                 "derived-value-computation", "optimization-of-numeric-range"),
    "E 판단 논거": ("design-choice-rationale", "obviousness-rationale", "effect-predictability",
                 "combination-motivation", "domain-common-knowledge", "absent-disclosure-common-knowledge",
                 "inferred-disclosure", "inherent-property-rationale", "difference-and-why-trivial",
                 "ground-without-document", "required-evidence-demand"),
    "F 법조·절차": ("ground-subclause-lost", "critical-date-of-judgment", "non-prior-art-ground"),
    "G 정본 데이터(파서)": ("ground-omitted-from-canon", "cited-document-omitted", "ground-misattributed",
                      "ground-document-cross-product", "target-claims-contaminated",
                      "target-claims-incomplete", "legal-basis-target-claims-empty",
                      "cited-document-unnumbered", "citation-number-format-variant",
                      "citation-term-variant", "citation-declaration-inline",
                      "citation-numbering-discontinuity"),
}
FAMILY_OF = {s: f for f, ss in FAMILY.items() for s in ss}

COORD = re.compile(r"^L\d+$")
QUOTE_MAX = 50
REQUIRED = ("card_id", "source_file", "source_sha256", "application", "legal_ground",
            "target_claims", "cited_docs", "query_element", "disclosure", "assertion_type",
            "coords", "quote", "verdict", "verdict_terms", "verdict_reason",
            "deficiency", "parser_gap", "units", "unit_n")
#: **한 카드 = 한 판단이 아니다** (2026-09-28 사용자 결정). 한 문서 안에서 「주장유형 × 결손조합」이
#: 같은 단위를 한 카드로 묶고 덮은 단위 라벨을 `units` 에 전부 적는다. 실측 단위 수가 설계 예상의
#: 8배였고(4문서 31단위), 단위당 1행이면 같은 결손이 수십 번 복제돼 결손 목록이 흐려진다.
#: 그래서 **카드 수를 판단 수로 읽어서는 안 된다** — 판단 수는 `unit_n` 의 합이다.


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(ontology: Path = ONTOLOGY) -> tuple[dict[str, str], dict[str, str]]:
    """선언된 어휘 → 어느 TTL 에서 왔는가. 두 번째 값은 파일별 sha256(재현 핀)."""
    try:
        from rdflib import BNode, OWL, RDF, Graph, URIRef
    except ModuleNotFoundError as e:
        raise SystemExit(f"ERROR: rdflib 가 없다 ({e}). 가상환경에서 실행할 것.")
    kinds = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
             RDF.Property, URIRef("http://www.w3.org/2002/07/owl#NamedIndividual"))
    terms: dict[str, str] = {}
    shas: dict[str, str] = {}
    paths = sorted({p for g in TBOX_GLOBS for p in Path(ontology).glob(g)})
    if not paths:
        raise SystemExit(f"ERROR: T-Box TTL 이 없다 — {ontology}. `make owl convert` 가 선행이다.")
    graphs: dict[Path, Graph] = {}
    for p in paths:
        g = Graph()
        g.parse(p, format="turtle")
        graphs[p] = g
        shas[p.name] = sha256_of(p)

    def qname(g: Graph, s) -> str | None:
        if isinstance(s, BNode):            # 공백 노드는 어휘의 단위가 아니다
            return None
        q = g.namespace_manager.normalizeUri(s)
        return None if q.startswith("<") else q   # 접두어 없는 IRI 도 아니다

    classes: set = set()
    for p, g in graphs.items():
        for s, _, o in g.triples((None, RDF.type, None)):
            if o not in kinds:
                continue
            q = qname(g, s)
            if q is None:
                continue
            terms.setdefault(q, p.name)
            if o == OWL.Class:
                classes.add(s)
    # **열거형 개별자도 어휘다.** `pakr:VerdictWellKnown`(주지관용)·`pakr:Ground_*` 는 개별자로
    # 선언돼 있고, 이것들이 없으면 "주지관용" 주장을 담을 자리가 없다고 잘못 판정하게 된다.
    for p, g in graphs.items():
        for s, _, o in g.triples((None, RDF.type, None)):
            if o not in classes:
                continue
            q = qname(g, s)
            if q is not None:
                terms.setdefault(q, p.name)
    return terms, shas


#: 인용발명 표기의 변이. 해부에서 「파서가 왜 놓쳤는가」의 후보가 나왔으므로 **전수로 센다** —
#: 30건의 관찰을 688건에서 확인하는 자리다. 본문을 인쇄하지 않고 적중 건수만 센다.
NOTATION = {
    "인용발명N:": re.compile(r"인용발명\s*\d\s*[:：]"),
    "인용발명N": re.compile(r"인용발명\s*\d"),
    "비교대상발명": re.compile(r"비교대상발명"),
    "인용문헌": re.compile(r"인용문헌"),
}


def canon_gaps(scrub_dir: Path = SCRUB_DIR,
               legal_basis: Path | None = None) -> dict:
    """정본(`notice_legal_basis`)의 결손을 전수로 센다 — 해부 관찰의 규모 확인.

    두 가지를 센다.
      ① 표기 변이 × 근거행 유무 — 파서가 무엇을 필요조건으로 삼고 있는지
      ② target_claims 에 그 출원의 청구항 수를 넘는 번호가 있는가 — 오염의 **하한**
        (범위 안의 오염은 이 방법으로 잡히지 않는다)
    """
    import pandas as pd
    lb_path = legal_basis or (ROOT / "data" / "patents" / "notice_legal_basis.parquet")
    lb = pd.read_parquet(lb_path)
    has = set(lb.source_file)
    manifest = json.loads((Path(scrub_dir) / "_manifest.json").read_text(encoding="utf-8"))
    produced = [e["output"] for e in manifest["files"] if e.get("output")]

    tally = {k: {"has": 0, "none": 0} for k in NOTATION}
    n_has = n_none = 0
    for f in produced:
        text = (Path(scrub_dir) / f).read_text(encoding="utf-8")
        key = "has" if f in has else "none"
        n_has, n_none = (n_has + 1, n_none) if key == "has" else (n_has, n_none + 1)
        for name, pat in NOTATION.items():
            if pat.search(text):
                tally[name][key] += 1

    meta = pd.read_parquet(ROOT / "data" / "patents" / "rejected_patents_meta.parquet")
    n_claims = dict(zip(meta.application_number, pd.to_numeric(meta.n_claims_full, errors="coerce")))
    rows = lb[lb.target_claims.astype(str).str.strip() != ""]
    checked = over = 0
    for app, tc in zip(rows.application_number, rows.target_claims):
        limit = n_claims.get(app)
        nums = [int(x) for x in re.findall(r"\d+", str(tc))]
        if not nums or limit != limit:      # NaN 검사
            continue
        checked += 1
        if any(n > limit for n in nums):
            over += 1
    return {"produced": len(produced), "with_basis": n_has, "without_basis": n_none,
            "notation": tally, "target_claims_checked": checked, "target_claims_over": over}


def load_cards(path: Path = CARDS) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"ERROR: 카드 파일이 없다 — {path}.")
    cards = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cards.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"ERROR: 카드 {i}행이 JSON 이 아니다: {e}")
    return cards


def check(cards: list[dict], sample: dict, terms: dict[str, str]) -> None:
    """실패해야 할 입력이 실패하는 자리. 경고로 넘기지 않는다."""
    if not sample.get("human_verified"):
        raise SystemExit(
            "ERROR: 표본이 사람 확인을 받지 않았다 — 본문을 LLM 에 보낼 자격이 없다(§1-5). "
            "`sample_notice_dissection.py --mark-verified` 가 선행이다.")
    by_file = {r["source_file"]: r for r in sample["files"]}
    seen: set[str] = set()
    for c in cards:
        cid = c.get("card_id", "(무명)")
        missing = [k for k in REQUIRED if k not in c]
        if missing:
            raise SystemExit(f"ERROR: 카드 {cid} 에 필수 키가 없다: {missing}")
        if cid in seen:
            raise SystemExit(f"ERROR: card_id 중복: {cid}")
        seen.add(cid)
        rec = by_file.get(c["source_file"])
        if rec is None:
            raise SystemExit(f"ERROR: 카드 {cid} 의 원천이 표본에 없다: {c['source_file']}")
        if c["source_sha256"] != rec["sha256"]:
            raise SystemExit(f"ERROR: 카드 {cid} 의 sha256 이 표본과 다르다 — 원천이 바뀌었다")
        if not c["coords"] or not all(COORD.match(x) for x in c["coords"]):
            raise SystemExit(f"ERROR: 카드 {cid} 의 좌표가 없거나 모양이 다르다: {c['coords']}")
        if len(c["quote"]) > QUOTE_MAX:
            raise SystemExit(f"ERROR: 카드 {cid} 의 인용이 {QUOTE_MAX}자를 넘는다: {len(c['quote'])}자")
        if c["verdict"] not in VERDICTS:
            raise SystemExit(f"ERROR: 카드 {cid} 의 판정이 {VERDICTS} 가 아니다: {c['verdict']}")
        unknown = [t for t in c["verdict_terms"] if t not in terms]
        if unknown:
            raise SystemExit(
                f"ERROR: 카드 {cid} 가 인벤토리에 없는 용어를 지목한다: {unknown}. "
                "T-Box 에 없는 용어로 '표현된다'고 판정할 수 없다(§1-2).")
        if not c["units"] or c["unit_n"] != len(c["units"]):
            raise SystemExit(
                f"ERROR: 카드 {cid} 의 단위 목록이 비었거나 unit_n 과 맞지 않다: "
                f"{c['unit_n']} vs {len(c['units'])}")
        if c["verdict"] != "E0" and not c["deficiency"]:
            raise SystemExit(f"ERROR: 카드 {cid} 가 {c['verdict']} 인데 결손 슬러그가 없다")
        for sec in c.get("secondary", []):
            if sec not in VERDICTS:
                raise SystemExit(f"ERROR: 카드 {cid} 의 secondary 판정이 이상하다: {sec}")


def aggregate(cards: list[dict], sample: dict) -> dict:
    unmapped = sorted({s for c in cards for s in c["deficiency"] if s not in FAMILY_OF})
    if unmapped:
        raise SystemExit(
            f"ERROR: 계열 매핑에 없는 결손 슬러그: {unmapped}. "
            "FAMILY 에 넣어라 — 분류되지 않은 결손은 목록만 늘린다.")
    by_stratum = {r["source_file"]: r["stratum"] for r in sample["files"]}
    defs: dict[str, list[str]] = defaultdict(list)
    worst: dict[str, str] = {}
    for c in cards:
        for slug in c["deficiency"]:
            defs[slug].append(c["card_id"])
            rank = {"E0": 0, "E1": 1, "E3": 2, "E2": 3}
            if slug not in worst or rank[c["verdict"]] > rank[worst[slug]]:
                worst[slug] = c["verdict"]
    return {
        "cards": len(cards),
        "units": sum(c["unit_n"] for c in cards),
        "documents": len({c["source_file"] for c in cards}),
        "by_verdict": dict(sorted(Counter(c["verdict"] for c in cards).items())),
        "by_stratum": dict(sorted(Counter(by_stratum[c["source_file"]] for c in cards).items())),
        "by_assertion": dict(sorted(Counter(c["assertion_type"] for c in cards).items())),
        "parser_gap": sum(1 for c in cards if c["parser_gap"]),
        "deficiencies": {k: {"verdict": worst[k], "cards": sorted(v), "n": len(v),
                             "family": FAMILY_OF[k]}
                         for k, v in sorted(defs.items(), key=lambda kv: -len(kv[1]))},
        "by_family": {f: sum(len(defs[s]) for s in ss if s in defs)
                      for f, ss in FAMILY.items()},
        "slugs_by_family": {f: sorted(s for s in ss if s in defs) for f, ss in FAMILY.items()},
    }


def render(agg: dict, cards: list[dict], sample: dict, terms: dict[str, str],
           shas: dict[str, str], cards_path: Path) -> str:
    L: list[str] = []
    A = L.append
    A("# PLAN-005 R1 — train 정답 해부와 표현 결손 목록")
    A("")
    A("> **이 문서는 스크립트가 렌더한다**(`scripts/report_r1_dissection.py`) — 손으로 쓰지 않는다(§5).")
    A("> 해부는 LLM 이 수행했으므로 재현이 보장되지 않는다. 그래서 **생성기가 아니라 산출물을 동결**한다:")
    A(f"> `{cards_path.relative_to(ROOT)}` sha256 `{sha256_of(cards_path)}`.")
    A("")
    A("## 0. 무엇을 보았는가")
    A("")
    A(f"- 표본 **{len(sample['files'])}문서** (층화 · seed `{sample['seed']}` · "
      f"사람 확인 {sample['verified_on']}) → **판단 단위 {agg['units']}건**을 "
      f"해부 카드 **{agg['cards']}장**으로 (문서 {agg['documents']})")
    A("- **카드 수를 판단 수로 읽지 말 것.** 한 문서 안에서 「주장유형 × 결손조합」이 같은 "
      "단위를 한 카드로 묶었고, 덮은 단위 라벨은 카드의 `units` 에 전부 있다.")
    A(f"- 모집단 {sample['population']} · 층별 {sample['population_by_stratum']}")
    A(f"- **{sample['not_a_frequency_estimate']}**")
    A(f"- 어휘 인벤토리 **{len(terms)}개 용어** (T-Box TTL {len(shas)}개에서 rdflib 로 추출)")
    A("")
    A("## 1. 판정 분포")
    A("")
    A("| 판정 | 뜻 | 카드 |")
    A("|---|---|---|")
    for v in VERDICTS:
        A(f"| **{v}** | {VERDICT_MEANING[v]} | {agg['by_verdict'].get(v, 0)} |")
    A("")
    A(f"층별 카드 {agg['by_stratum']} · 주장 유형 {agg['by_assertion']}")
    A("")
    A(f"**`parser_gap` {agg['parser_gap']}장** — 원문에 근거가 있는데 "
      "`notice_legal_basis.parquet` 에 없는 주장이다.")
    A("")
    A("## 2. 표현 결손 목록")
    A("")
    A(f"**결손 {len(agg['deficiencies'])}종**을 일곱 계열로 묶었다. 계열별 카드 적중 "
      f"{agg['by_family']}.")
    A("")
    for fam, slugs in agg["slugs_by_family"].items():
        if not slugs:
            continue
        A(f"### {fam}")
        A("")
        A("| 결손 | 판정 | 카드 | 근거 카드 |")
        A("|---|---|---|---|")
        for slug in sorted(slugs, key=lambda s: -agg["deficiencies"][s]["n"]):
            d = agg["deficiencies"][slug]
            ids = ", ".join(f"`{c}`" for c in d["cards"][:3])
            more = f" 외 {d['n'] - 3}" if d["n"] > 3 else ""
            A(f"| `{slug}` | **{d['verdict']}** | {d['n']} | {ids}{more} |")
        A("")
    A("## 3. 정본 데이터 결함 — 전수 측정 (해부 관찰의 규모 확인)")
    A("")
    g = canon_gaps()
    A(f"스크럽 산출 **{g['produced']}건** 중 정본에 근거행이 있는 것 **{g['with_basis']}** · "
      f"없는 것 **{g['without_basis']}**.")
    A("")
    A("| 인용발명 표기 | 근거행 있음 | 근거행 없음 |")
    A("|---|---|---|")
    for name, t in g["notation"].items():
        A(f"| `{name}` | {t['has']} ({t['has'] / max(g['with_basis'], 1):.0%}) | "
          f"{t['none']} ({t['none'] / max(g['without_basis'], 1):.0%}) |")
    A("")
    A(f"`target_claims` 대조 가능 **{g['target_claims_checked']}행** 중 "
      f"**{g['target_claims_over']}행 ({g['target_claims_over'] / max(g['target_claims_checked'], 1):.1%})**"
      " 이 그 출원의 청구항 수를 넘는 번호를 담는다 — 오염의 **하한**이다(범위 안의 오염은 "
      "이 방법으로 잡히지 않는다).")
    A("")
    A("> 해석과 처리 방침은 **PLAN-005 §20.15** 에 있다. 이번 R1 은 이 결함을 **등재만 하고 "
      "고치지 않는다**(사용자 결정 2026-09-28) — 해부와 계측기 교정을 섞지 않기 위함이다.")
    A("")
    A("## 4. 어휘 인벤토리 (기계 추출 · 재현 핀)")
    A("")
    A("| TTL | sha256 | 용어 |")
    A("|---|---|---|")
    per = Counter(terms.values())
    for name, sha in sorted(shas.items()):
        A(f"| `{name}` | `{sha[:16]}…` | {per.get(name, 0)} |")
    A("")
    A("## 5. 재현")
    A("")
    A("```bash")
    A("make sample-dissection      # 표본 30건 (결정적 · seed 20260922)")
    A("make report-dissection      # 카드 검사 + 이 문서 렌더")
    A("```")
    A("")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", type=Path, default=SAMPLE)
    ap.add_argument("--cards", type=Path, default=CARDS)
    ap.add_argument("--markdown", type=Path, default=REPORT)
    ap.add_argument("--inventory", action="store_true", help="어휘 인벤토리만 인쇄한다")
    a = ap.parse_args()

    terms, shas = inventory()
    if a.inventory:
        print(f"[inventory] 용어 {len(terms)} · TTL {len(shas)}")
        for name in sorted(shas):
            own = sorted(t for t, src in terms.items() if src == name)
            print(f"\n── {name} ({len(own)})")
            print("   " + " ".join(own))
        return

    sample = json.loads(Path(a.sample).read_text(encoding="utf-8"))
    cards = load_cards(a.cards)
    check(cards, sample, terms)
    agg = aggregate(cards, sample)
    Path(a.markdown).write_text(
        render(agg, cards, sample, terms, shas, Path(a.cards)), encoding="utf-8")
    print(f"[report-dissection] 카드 {agg['cards']}장 / {agg['documents']}문서 · "
          f"판정 {agg['by_verdict']} · 결손 {len(agg['deficiencies'])}종")
    print(f"[report-dissection] parser_gap {agg['parser_gap']} · "
          f"카드 sha256 {sha256_of(Path(a.cards))[:16]}…")
    print(f"[report-dissection] → {a.markdown}")


if __name__ == "__main__":
    main()
