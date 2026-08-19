"""어휘 검증 커버리지 — CQ 집합이 온톨로지 어휘의 몇 %를 실제로 심문하는가.

CQ 응답률만 보고하는 관행은 **공허한 게이트(vacuous gate)** 를 만든다. 어휘의 10분의 1만
만지는 CQ 집합도 100% 를 기록한다 — 그 100% 는 온톨로지 전체가 아니라 그 CQ 들이 걸치는
축 하나에 대한 진술이다. 이 모듈은 그 사실을 수치로 드러낸다 (논문 §3.4.2 지표 (ii)).

**분모** = 그래프에 *실제로 쓰인* `ont:` 술어·클래스. TBox 선언 어휘가 아니다 —
인스턴스가 0인 술어까지 분모에 넣으면 온톨로지 설계 문제와 데이터 문제가 섞인다.

**분자는 두 층이다.** 어휘는 **기능(CQ)** 또는 **구조(SHACL)** 중 최소 한 층이 봐야 한다:

  · **CQ 검증** = (CQ 의 **필수** 그래프 패턴에서 참조) ∧ (그 CQ 가 ≥1 행 응답).
  · **SHACL 검증** = 어떤 shape 의 `sh:path` / `sh:targetClass` / `sh:class` 에 나타남.
  · **게이트 커버리지** = 둘의 합집합. **목표는 "아무도 안 보는 어휘 = 0"** 이지 커버리지 90% 가
    아니다 — 커버리지를 목표로 삼으면 술어를 훑는 CQ 를 지어내게 되고, 그러면 응답률 100% ·
    커버리지 90% 짜리 **더 정교한 vacuous gate** 가 된다.

서지·프로비넌스("출원번호가 있는가"·"신뢰도가 0~1 인가")는 **CQ 가 물을 질문이 아니라 제약**이다.
그것을 CQ 로 만드는 대신 SHACL 에 둔다 — 지표가 그 구분을 강제한다.

CQ 검증의 정의:
  - 단순 언급이 아니라 필수 참조다 — `OPTIONAL` 안에 술어를 넣어 커버리지를 부풀릴 수 없다.
    (`FILTER NOT EXISTS` 안의 참조는 **필수로 센다** — 질의의 답이 그 술어에 실제로 의존한다.)
  - 0 행 응답은 어휘를 검증하지 못한다 — 술어가 그래프에 없어도 0 행은 나온다.
  - 추출은 정규식이 아니라 rdflib 의 SPARQL **대수(algebra) 파싱**이다: 주석·`VALUES` 절·
    prefix 표기 차이에 흔들리지 않는다.

CLI:  python -m sdkb_paper.validate.vocab_coverage <graph.ttl> [--report] [--min-cov 0.0]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SH
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.sparql import Query
from rdflib.plugins.sparql.parserutils import CompValue

from sdkb_paper.config import ONT, QUERIES_CQ, ROOT, SHAPES_GRAPH

_ONT = str(ONT)


@dataclass(frozen=True)
class CQVocab:
    """한 CQ 가 참조하는 ont: 어휘 (필수 / OPTIONAL 로 분리)."""

    name: str
    required: frozenset[str]
    optional: frozenset[str]


@dataclass
class Coverage:
    """한 그래프에 대한 어휘 검증 커버리지 (기능 CQ · 구조 SHACL · 합집합)."""

    graph: Path
    predicates_used: dict[str, int]  # IRI -> 사용 횟수
    classes_used: dict[str, int]
    verified_predicates: set[str]    # CQ 가 검증하는 술어
    verified_classes: set[str]
    shacl_predicates: set[str]       # SHACL 이 검사하는 술어
    shacl_classes: set[str]
    per_cq: dict[str, tuple[int, frozenset[str]]]  # CQ -> (결과 행 수, 검증한 IRI)

    @property
    def gated_predicates(self) -> set[str]:
        """CQ ∪ SHACL — 어느 한 층이라도 보는 술어."""
        return (self.verified_predicates | self.shacl_predicates) & set(self.predicates_used)

    @property
    def gated_classes(self) -> set[str]:
        return (self.verified_classes | self.shacl_classes) & set(self.classes_used)

    @property
    def predicate_rate(self) -> float:
        return len(self.verified_predicates) / len(self.predicates_used) if self.predicates_used else 0.0

    @property
    def class_rate(self) -> float:
        return len(self.verified_classes) / len(self.classes_used) if self.classes_used else 0.0

    @property
    def gate_predicate_rate(self) -> float:
        return len(self.gated_predicates) / len(self.predicates_used) if self.predicates_used else 0.0

    @property
    def gate_class_rate(self) -> float:
        return len(self.gated_classes) / len(self.classes_used) if self.classes_used else 0.0

    def ungated_predicates(self) -> list[tuple[str, int]]:
        """**아무도 안 보는 술어** — CQ 도 SHACL 도 건드리지 않는다. 목표는 0 이다."""
        gated = self.gated_predicates
        return sorted(
            ((p, n) for p, n in self.predicates_used.items() if p not in gated),
            key=lambda x: (-x[1], x[0]),
        )

    def ungated_classes(self) -> list[tuple[str, int]]:
        gated = self.gated_classes
        return sorted(
            ((c, n) for c, n in self.classes_used.items() if c not in gated),
            key=lambda x: (-x[1], x[0]),
        )

    def unverified_predicates(self) -> list[tuple[str, int]]:
        return sorted(
            ((p, n) for p, n in self.predicates_used.items() if p not in self.verified_predicates),
            key=lambda x: (-x[1], x[0]),
        )

    def unverified_classes(self) -> list[tuple[str, int]]:
        return sorted(
            ((c, n) for c, n in self.classes_used.items() if c not in self.verified_classes),
            key=lambda x: (-x[1], x[0]),
        )


def _collect_iris(node: object, sink: set[str]) -> None:
    """알고리즘이 아니라 재귀 수집 — 대수 트리 어디에 있든 ont: IRI 를 줍는다."""
    if isinstance(node, URIRef):
        if str(node).startswith(_ONT):
            sink.add(str(node))
    elif isinstance(node, CompValue):
        for key, value in node.items():
            if key.startswith("_"):
                continue
            _collect_iris(value, sink)
    elif isinstance(node, (list, tuple, set)):
        for item in node:
            _collect_iris(item, sink)
    elif isinstance(node, dict):
        for value in node.values():
            _collect_iris(value, sink)


def _walk(node: object, required: set[str], optional: set[str]) -> None:
    """OPTIONAL 의 우변(LeftJoin.p2)만 optional 로 떨어뜨리고 나머지는 required 로 센다."""
    if isinstance(node, CompValue) and node.name == "LeftJoin":
        _walk(node["p1"], required, optional)
        _collect_iris(node["p2"], optional)
        _collect_iris(node.get("expr"), required)  # OPTIONAL 의 필터 조건은 필수 패턴에 걸린다
        return
    if isinstance(node, CompValue):
        for key, value in node.items():
            if key.startswith("_"):
                continue
            _walk(value, required, optional)
        return
    if isinstance(node, (list, tuple, set)):
        for item in node:
            _walk(item, required, optional)
        return
    _collect_iris(node, required)


def cq_vocabulary(rq_text: str, name: str = "") -> CQVocab:
    """SPARQL 대수를 파싱해 CQ 가 참조하는 ont: IRI 를 필수/OPTIONAL 로 나눈다."""
    query: Query = translateQuery(parseQuery(rq_text))
    required: set[str] = set()
    optional: set[str] = set()
    _walk(query.algebra, required, optional)
    return CQVocab(name=name, required=frozenset(required), optional=frozenset(optional - required))


def graph_vocabulary(g: Graph) -> tuple[dict[str, int], dict[str, int]]:
    """그래프에 **실제로 쓰인** ont: 술어와 클래스 (분모)."""
    predicates = Counter(str(p) for _, p, _ in g if str(p).startswith(_ONT))
    classes = Counter(str(o) for _, _, o in g.triples((None, RDF.type, None)) if str(o).startswith(_ONT))
    return dict(predicates), dict(classes)


def shacl_vocabulary(shapes_dir: Path) -> tuple[set[str], set[str]]:
    """SHACL shape 이 **검사하는** ont: 어휘 (술어 = sh:path · 클래스 = sh:targetClass/sh:class).

    minCount 가 없어도 검사로 센다 — 데이터타입·열거 제약은 값이 있을 때마다 실제로 걸린다.
    """
    predicates: set[str] = set()
    classes: set[str] = set()
    for ttl in sorted(shapes_dir.rglob("*.ttl")):
        g = Graph().parse(ttl)
        for _, _, o in g.triples((None, SH.path, None)):
            if isinstance(o, URIRef) and str(o).startswith(_ONT):
                predicates.add(str(o))
        for pred in (SH.targetClass, SH["class"]):
            for _, _, o in g.triples((None, pred, None)):
                if isinstance(o, URIRef) and str(o).startswith(_ONT):
                    classes.add(str(o))
    return predicates, classes


def measure(graph_path: Path, cq_dir: Path = QUERIES_CQ, shapes_dir: Path = SHAPES_GRAPH) -> Coverage:
    g = Graph().parse(graph_path)
    predicates_used, classes_used = graph_vocabulary(g)
    vocab_used = set(predicates_used) | set(classes_used)

    verified: set[str] = set()
    per_cq: dict[str, tuple[int, frozenset[str]]] = {}
    for rq in sorted(cq_dir.glob("*.rq")):
        text = rq.read_text(encoding="utf-8")
        vocab = cq_vocabulary(text, rq.stem)
        rows = len(list(g.query(text)))
        # 0 행 응답은 어휘를 검증하지 못한다 — 술어가 그래프에 없어도 0 행은 나온다.
        hit = frozenset(vocab.required & vocab_used) if rows >= 1 else frozenset()
        verified |= hit
        per_cq[rq.stem] = (rows, hit)

    shacl_preds, shacl_classes = shacl_vocabulary(shapes_dir) if shapes_dir.exists() else (set(), set())

    return Coverage(
        graph=graph_path,
        predicates_used=predicates_used,
        classes_used=classes_used,
        verified_predicates=verified & set(predicates_used),
        verified_classes=verified & set(classes_used),
        shacl_predicates=shacl_preds & set(predicates_used),
        shacl_classes=shacl_classes & set(classes_used),
        per_cq=per_cq,
    )


def _short(iri: str) -> str:
    return iri.removeprefix(_ONT)


def render(cov: Coverage) -> str:
    lines = [
        f"# 어휘 검증 커버리지 — `{cov.graph}`",
        "",
        "분모 = 그래프에 실제로 쓰인 `ont:` 어휘. 어휘는 **기능(CQ)** 또는 **구조(SHACL)** 중",
        "최소 한 층이 봐야 한다. **목표는 커버리지 90% 가 아니라 '아무도 안 보는 어휘 = 0' 이다.**",
        "",
        "| 축 | CQ 검증 | SHACL 검사 | **게이트(합집합)** | 사용됨 | **아무도 안 봄** |",
        "|---|---:|---:|---:|---:|---:|",
        f"| 술어 | {len(cov.verified_predicates)} ({cov.predicate_rate:.1%}) | {len(cov.shacl_predicates)} "
        f"| **{len(cov.gated_predicates)} ({cov.gate_predicate_rate:.1%})** | {len(cov.predicates_used)} "
        f"| **{len(cov.ungated_predicates())}** |",
        f"| 클래스 | {len(cov.verified_classes)} ({cov.class_rate:.1%}) | {len(cov.shacl_classes)} "
        f"| **{len(cov.gated_classes)} ({cov.gate_class_rate:.1%})** | {len(cov.classes_used)} "
        f"| **{len(cov.ungated_classes())}** |",
        "",
        "## CQ 별 검증 어휘",
        "",
        "| CQ | 결과행 | 검증한 어휘 |",
        "|---|---:|---|",
    ]
    for name, (rows, hit) in sorted(cov.per_cq.items()):
        terms = " · ".join(f"`{_short(i)}`" for i in sorted(hit, key=_short)) or "—"
        lines.append(f"| {name} | {rows} | {terms} |")

    lines += ["", "## 아무도 보지 않는 어휘 (CQ 도 SHACL 도) — **0 이어야 한다**", ""]
    gp, gc = cov.ungated_predicates(), cov.ungated_classes()
    if not gp and not gc:
        lines += ["없음. 모든 어휘가 CQ(기능) 또는 SHACL(구조) 중 최소 한 층의 검증을 받는다.", ""]
    else:
        lines += ["| 술어 | 사용 |", "|---|---:|"]
        lines += [f"| `{_short(i)}` | {n} |" for i, n in gp]
        lines += [f"| (클래스) `{_short(i)}` | {n} |" for i, n in gc]
        lines += [""]

    lines += ["## CQ 가 검증하지 않는 어휘 (SHACL 이 보는 것 포함)", "", "| 술어 | 사용 | | 클래스 | 사용 |", "|---|---:|---|---|---:|"]
    up, uc = cov.unverified_predicates(), cov.unverified_classes()
    for i in range(max(len(up), len(uc))):
        pcell = f"`{_short(up[i][0])}` | {up[i][1]}" if i < len(up) else " | "
        ccell = f"`{_short(uc[i][0])}` | {uc[i][1]}" if i < len(uc) else " | "
        lines.append(f"| {pcell} | | {ccell} |")
    return "\n".join(lines) + "\n"


def report_path(graph_path: Path) -> Path:
    return ROOT / "paper" / "figures" / f"vocab_coverage_{graph_path.stem}.md"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("graph", type=Path)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--min-cov", type=float, default=0.0,
        help="요구 술어 커버리지(0~1). 기본 0 — 이 지표는 게이트가 아니라 **측정**이다."
             " 임계값을 세우면 커버리지를 올리려고 CQ 를 지어내게 된다.",
    )
    args = ap.parse_args()

    cov = measure(args.graph)
    print(f"[vocab_coverage] graph = {args.graph}")
    print(f"[vocab_coverage] CQ    술어 {len(cov.verified_predicates)}/{len(cov.predicates_used)} = {cov.predicate_rate:.1%}"
          f"  · 클래스 {len(cov.verified_classes)}/{len(cov.classes_used)} = {cov.class_rate:.1%}")
    print(f"[vocab_coverage] 게이트(CQ ∪ SHACL) 술어 {len(cov.gated_predicates)}/{len(cov.predicates_used)}"
          f" = {cov.gate_predicate_rate:.1%}  · 클래스 {len(cov.gated_classes)}/{len(cov.classes_used)}"
          f" = {cov.gate_class_rate:.1%}")
    ungated = cov.ungated_predicates() + cov.ungated_classes()
    if ungated:
        print(f"[vocab_coverage] ⚠ 아무도 안 보는 어휘 {len(ungated)}개: "
              + " · ".join(f"{_short(i)}({n})" for i, n in ungated[:6]))
    else:
        print("[vocab_coverage] ✓ 아무도 안 보는 어휘 0 — 모든 어휘를 CQ 또는 SHACL 이 검증한다")

    if args.report:
        out = args.out or report_path(args.graph)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(cov), encoding="utf-8")
        print(f"[vocab_coverage] report -> {out}")

    sys.exit(0 if cov.predicate_rate >= args.min_cov else 1)


if __name__ == "__main__":
    main()
