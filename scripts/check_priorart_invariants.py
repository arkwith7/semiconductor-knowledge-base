#!/usr/bin/env python3
"""PLAN-005 §5 V6(a) — 이식성 CI 불변식 두 가지.

**왜 단계 4 와 같은 커밋인가.** PLAN-005 §6 이 못박았다 — *"8·9 의 CI 불변식은 4 와 같은
커밋에서 세운다. 나중에 붙이면 이미 오염된 core 를 통과시키게 된다."* 검사 없이 지은 core
는 다음 사람이 `ont:` 한 줄을 넣어도 통과하고, 그때는 이미 발행돼 하류가 vendor 한 뒤다.

**불변식 A — core 순도.** `sdkb-priorart-core.ttl` 에 도메인(`ont:`) 또는 관할(`gov:`·
`pakr:`) 이름공간의 IRI 가 **한 건이라도** 있으면 실패. 금지 목록이 아니라 **허용 목록**으로
검사한다 — 금지 목록은 새 이름공간이 생길 때마다 조용히 뚫린다.
이것이 통과하면 *"바이오·US 이식 시 L1 변경 0줄"* 이 주장이 아니라 기계 보증이 된다.

**불변식 B — 태스크 질의의 행정 어휘 금지 (§3.4).** 태스크 질의의 `WHERE` **필수부**에
`ont:Patent`·`ont:RejectedPatent`·`ont:RejectionType`·`ont:PriorArtJudgment`·
`ont:overPriorArt` 가 등장하면 실패. `OPTIONAL { }` 증거 블록 안에서만 허용한다.
통과하면 **연구노트로 만든 ClaimProfile 도 같은 질의로 검색된다** — 특허가 아직 없는
아이디어가 1급 질의가 되고, 그것이 "특허 종속" 지적에 대한 검증 가능한 답이다.

**정규식으로 하지 않는 이유.** `OPTIONAL { ?p a ont:Patent }` 와 `?p a ont:Patent` 는
문자열로는 같은 토큰을 갖는다. 그래서 rdflib 로 **SPARQL 대수(algebra)를 파싱해서 걷고**,
`LeftJoin` 의 오른쪽 가지로 내려갈 때만 optional 로 표시한다. `UNION` 가지는 보수적으로
필수로 본다 — 한 가지에서만 특허를 요구해도 그 가지는 특허 종속이다.

**대상은 헤더로 고른다.** `# task-neutral: required` 가 붙은 질의만 검사한다. 기존 CQ 31개
는 이번 단계의 비목표(§7-2 기존 어휘 불변)이며, 그중 **CQ10 은 설계상 이 규칙에 걸린다**
(`?prior a ont:Patent` 로 시작) — 그 교정은 단계 6·7 의 몫이다. 여기서 손대면 승인 범위
밖이고, 반대로 규칙을 느슨하게 하면 게이트가 아니라 장식이 된다(§4).

CLI:
    python scripts/check_priorart_invariants.py
    python scripts/check_priorart_invariants.py --core PATH --queries DIR
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.term import Variable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORE = ROOT / "ontology" / "sdkb-priorart-core.ttl"
DEFAULT_QUERIES = ROOT / "queries"

# core 에서 허용되는 이름공간. 여기 없는 IRI 는 전부 위반이다(허용 목록 방식).
# **하위 이름공간은 자기 자신이 아니다.** `pa/kr/…` 는 `pa/` 로 시작하므로 단순 접두어
# 비교로는 통과한다 — 실제로 통과했고 회귀 테스트가 그것을 잡았다(2026-09-06). 그래서
# pa: 아래는 **로컬명에 `/` 가 없을 때만** 자기 자신으로 인정한다.
PA_BASE = "https://w3id.org/sdkb/pa/"
CORE_ALLOWED = (
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/2004/02/skos/core#",
    "http://purl.org/dc/terms/",
    "http://www.w3.org/ns/prov#",
    "https://spdx.org/licenses/",         # dcterms:license
)
# 허용 목록 위반 중 이 둘에 걸리면 원인을 이름으로 말해 준다.
DOMAIN_HINT = ("https://w3id.org/sdkb/ont/", "http://w3id.org/SemicONTO/")
JURIS_HINT = ("https://w3id.org/sdkb/gov/", "https://w3id.org/sdkb/pa/kr/",
              "https://w3id.org/sdkb/pa/us/")

ADMIN_TERMS = {
    "https://w3id.org/sdkb/ont/Patent",
    "https://w3id.org/sdkb/ont/RejectedPatent",
    "https://w3id.org/sdkb/ont/RejectionType",
    "https://w3id.org/sdkb/ont/PriorArtJudgment",
    "https://w3id.org/sdkb/ont/overPriorArt",
}
MARKER = "task-neutral"


# ── 불변식 A ────────────────────────────────────────────────────────
def _allowed(iri: str) -> bool:
    if iri == "https://w3id.org/sdkb/pa":
        return True
    if iri.startswith(PA_BASE):
        return "/" not in iri[len(PA_BASE):]      # pa/kr/… · pa/us/… 는 관할 어휘다
    return iri.startswith(CORE_ALLOWED)


def check_core(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path} 가 없다 — `make priorart` 로 먼저 짓는다"]
    g = Graph()
    g.parse(path, format="turtle")
    bad: dict[str, int] = {}
    for triple in g:
        for t in triple:
            iris = []
            if isinstance(t, URIRef):
                iris.append(str(t))
            elif isinstance(t, Literal) and t.datatype:
                iris.append(str(t.datatype))
            for iri in iris:
                if _allowed(iri):
                    continue
                bad[iri] = bad.get(iri, 0) + 1
    out = []
    for iri, n in sorted(bad.items()):
        if iri.startswith(DOMAIN_HINT):
            why = "도메인 어휘"
        elif iri.startswith(JURIS_HINT):
            why = "관할 어휘"
        else:
            why = "허용되지 않은 이름공간"
        out.append(f"core 오염 ({why}): {iri}  ×{n}")
    return out


# ── 불변식 B ────────────────────────────────────────────────────────
def _walk(node, required: bool, hits: list[tuple[str, bool]]) -> None:
    """대수를 걷는다. LeftJoin·Minus 의 오른쪽 가지만 optional 이다."""
    if node is None:
        return
    name = getattr(node, "name", None)
    if name == "BGP":
        for s, p, o in node["triples"]:
            for t in (s, p, o):
                if isinstance(t, URIRef) and str(t) in ADMIN_TERMS:
                    hits.append((str(t), required))
        return
    if name in ("LeftJoin", "Minus"):
        _walk(node.get("p1"), required, hits)
        _walk(node.get("p2"), False, hits)
        return
    if hasattr(node, "keys"):
        for k in node.keys():
            v = node[k]
            # BGP 밖에서 들어오는 자리도 본다 — `VALUES ?p { ont:Patent }` 는 삼중항이
            # 아니라 바인딩 집합이라 BGP 만 보면 통째로 새어 나간다.
            for item in (v if isinstance(v, (list, tuple)) else [v]):
                if isinstance(item, URIRef):
                    if str(item) in ADMIN_TERMS:
                        hits.append((str(item), required))
                elif isinstance(item, (Literal, Variable, str)):
                    continue
                elif hasattr(item, "name"):
                    # CompValue 는 dict 하위다 — 아래 dict 분기보다 **먼저** 걸러야
                    # 재귀가 가로채이지 않는다(2026-09-06 회귀에서 실제로 그랬다).
                    _walk(item, required, hits)
                elif isinstance(item, dict):
                    # VALUES 의 바인딩 한 줄 — 삼중항이 아니라 {변수: 값} 이다.
                    for iv in item.values():
                        if isinstance(iv, URIRef) and str(iv) in ADMIN_TERMS:
                            hits.append((str(iv), required))
                elif hasattr(item, "keys"):
                    _walk(item, required, hits)


def check_query(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        algebra = translateQuery(parseQuery(text)).algebra
    except Exception as exc:  # 파싱 불가는 통과가 아니라 실패다
        return [f"{path.name}: SPARQL 파싱 실패 — {exc}"]
    hits: list[tuple[str, bool]] = []
    _walk(algebra, True, hits)
    return [f"{path.name}: 행정 어휘 <{iri}> 가 WHERE 필수부에 있다 "
            f"(OPTIONAL 증거 블록 안에서만 허용 · §3.4)"
            for iri, req in hits if req]


def task_queries(qdir: Path) -> list[Path]:
    out = []
    for p in sorted(qdir.rglob("*.rq")):
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:15])
        for line in head.splitlines():
            if not line.startswith("#"):
                break
            body = line.lstrip("#").strip().lower()
            if body.startswith(MARKER) and body.endswith("required"):
                out.append(p)
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=Path, default=DEFAULT_CORE)
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    args = ap.parse_args()

    fails = check_core(args.core)
    print(f"불변식 A · core 순도 ({args.core.name}): "
          f"{'FAIL' if fails else 'OK — 도메인·관할 IRI 0건'}")

    qs = task_queries(args.queries)
    qfails: list[str] = []
    for q in qs:
        qfails += check_query(q)
    print(f"불변식 B · 태스크 질의 행정 어휘 ({len(qs)}건 검사): "
          f"{'FAIL' if qfails else 'OK — 필수부 적중 0건'}")
    if not qs:
        print("  (경고: '# task-neutral: required' 가 붙은 질의가 하나도 없다 — "
              "검사 대상이 0이면 통과는 아무것도 말하지 않는다)")

    for line in fails + qfails:
        print(f"  ✗ {line}")
    return 1 if (fails or qfails) else 0


if __name__ == "__main__":
    raise SystemExit(main())
