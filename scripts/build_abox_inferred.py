#!/usr/bin/env python3
"""PLAN-005 논증층 R-Box 규칙 — 규칙을 실행해 추론 판단을 **별도 그래프**로 실체화한다.

**왜 생성기가 규칙을 실행하는가.** 이 배치에는 추론기가 없다. OWL 공리로 적으면 아무도 읽지 않고
(6-B 가 그런 공리를 지웠다), 질의가 같은 규칙을 제각각 다시 적으면 규칙이 질의마다 갈라진다.
그래서 규칙은 `queries/rules/*.rq` 의 CONSTRUCT 한 벌이고, 그 결과를 여기서 한 번 실체화한다.
규칙 개체(권위·범위·실행 질의)는 T-Box 에 있다 — `pa:Rule_EvidenceInheritance`(⑤) ·
`pakr:Rule_NoveltyImpliesInventiveness`(⑥).

**왜 별도 그래프인가.** 추론은 심사관이 적은 판단이 아니다. 판단층(claim-features)에 섞으면
정답 간선과 평가 층이 규칙의 산출을 심사관 판단으로 읽는다. 그래서 산출은 따로 쓰고, 추론
노드가 `ExaminerJudgment`·`PriorArtJudgment` 로 타이핑되면 쓰기 전에 죽는다(SHACL 도 같은 것을 건다).

입력과 산출:

  판단층  ontology/sdkb-abox-claim-features.ttl (935 MB) → ontology/sdkb-abox-inferred.ttl
          통째로 읽지 않는다 — 판단 블록만 잘라 읽는다(`slice_judgments`). 잘라 읽은 판단 수가
          생성기 리포트의 판단 수와 다르면 죽는다: 직렬화 형태가 바뀌어 블록을 놓친 것이다.
  논증층  data/sources/notice_dissection/pilot_abox.ttl → …/pilot_inferred.ttl (비공개 · gitignore)
          원천 계층이 없는 공개 트리에서는 0 이 아니라 "미적재"로 적는다.

리포트(data/reports/abox_inferred_report.json)에는 규칙별 발화와 **발화하지 않은 사유**를 적는다 —
조용히 0 이 되면 규칙이 없는 것과 같다.

CLI:
    python scripts/build_abox_inferred.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_priorart_modules import _emit  # noqa: E402
from config.namespaces import SDKB_DATA, SDKB_ONT, SDKB_PA, SDKB_PA_KR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ONT_DIR = ROOT / "ontology"
RULES_DIR = ROOT / "queries" / "rules"
CF_TTL = ONT_DIR / "sdkb-abox-claim-features.ttl"
CF_REPORT = ROOT / "data" / "reports" / "abox_claim_features_report.json"
PILOT = ROOT / "data" / "sources" / "notice_dissection" / "pilot_abox.ttl"
ARG_ABOX = ONT_DIR / "sdkb-abox-argument.ttl"   # §20.22 실물 논증층 (원천이 있을 때만 지어진다)
OUT = ONT_DIR / "sdkb-abox-inferred.ttl"
PILOT_OUT = ROOT / "data" / "sources" / "notice_dissection" / "pilot_inferred.ttl"
REPORT = ROOT / "data" / "reports" / "abox_inferred_report.json"

PA, PAKR, ONT, D = SDKB_PA, SDKB_PA_KR, SDKB_ONT, SDKB_DATA
JUDGMENT_PREFIX = f"<{D}judgment/"
#: 층 → 그 층에 거는 규칙 파일. 순서는 결과에 영향이 없다(합집합) — 정렬해 두는 것은 리포트 순서 때문이다.
LAYER_RULES = {
    "judgment": ["RA_judgment_layer.rq"],
    "argument": ["RA_argument_layer.rq", "RE_argument_layer.rq"],
}
#: 같은 규칙·같은 미발화 사유를 쓰는 층 — 실물 논증층은 파일럿과 어휘가 같다.
LAYER_RULES["argument_abox"] = LAYER_RULES["argument"]
#: 추론 노드가 가져서는 안 되는 타입 — 심사관 판단과 섞지 않는다는 계약.
FORBIDDEN_TYPES = (PA.ExaminerJudgment, ONT.PriorArtJudgment)
PREFIXES = {"pa": str(PA), "pakr": str(PAKR), "rdf": str(RDF), "xsd": str(XSD)}
HEADER = """# ═══════════════════════════════════════════════════════════════════
# {title}
#
# **생성물이다. 손으로 고치지 않는다** — scripts/build_abox_inferred.py 가 queries/rules/ 의
# 규칙을 실행해 만든다. **심사관이 적은 판단이 아니다** — 규칙이 끌어낸 것이며, 노드마다
# pa:inferredBy 가 규칙을, pa:inferredFrom 이 전제 판단을 가리킨다.
#
# 재생성: make abox-inferred
# ═══════════════════════════════════════════════════════════════════"""


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slice_judgments(path: Path) -> tuple[Graph, int]:
    """claim-features TTL 에서 판단 주어 블록만 잘라 그래프로 읽는다 → (그래프, 블록 수).

    rdflib 직렬화는 주어마다 블록 하나이고 블록 사이에 빈 줄을 둔다. 판단 블록은 줄머리가 판단 IRI 다.
    규칙은 (청구항, 문헌) 으로 조건을 걸므로 출원 쪽 `hasJudgment` 는 필요 없다.
    """
    prefixes: list[str] = []
    blocks: list[str] = []
    cur: list[str] | None = None
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("@prefix"):
                prefixes.append(line)
                continue
            if cur is None:
                if line.startswith(JUDGMENT_PREFIX):
                    cur = [line]
                continue
            if line.strip():
                cur.append(line)
            else:
                blocks.append("".join(cur))
                cur = None
    if cur:
        blocks.append("".join(cur))
    g = Graph()
    g.parse(data="".join(prefixes) + "\n" + "\n".join(blocks), format="turtle")
    return g, len(blocks)


def run_rules(g: Graph, rule_files: list[Path]) -> Graph:
    out = Graph()
    for rf in sorted(rule_files):
        for t in g.query(rf.read_text(encoding="utf-8")):
            out.add(t)
    return out


def check_inferred(inferred: Graph, source: Graph) -> None:
    """쓰기 전에 죽는다 — 추론이 심사관 판단으로 타이핑되거나 없는 전제를 가리키면."""
    for t in FORBIDDEN_TYPES:
        bad = sorted(set(inferred.subjects(RDF.type, t)))
        if bad:
            raise SystemExit(f"ERROR: 추론 노드가 {t} 로 타이핑됐다 — 심사관 판단과 섞인다: {bad[:3]}")
    for node, prem in inferred.subject_objects(PA.inferredFrom):
        if (prem, None, None) not in source:
            raise SystemExit(f"ERROR: {node} 의 전제 {prem} 가 입력 그래프에 없다")


def _rule_stats(inferred: Graph) -> dict:
    stats: dict[str, dict] = {}
    for node, rule in sorted(inferred.subject_objects(PA.inferredBy)):
        key = str(rule).replace(str(PAKR), "pakr:").replace(str(PA), "pa:")
        s = stats.setdefault(key, {"nodes": 0, "claims": 0, "inherited_support": 0})
        s["nodes"] += 1
        s["claims"] += len(set(inferred.objects(node, PA.inferredClaim)))
        s["inherited_support"] += len(set(inferred.objects(node, PA.inheritedSupport)))
    return stats


_ASK_COUNT = "SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {body} }}"
#: 발화하지 않은 사유. 규칙의 조건이 아니라 **입력이 모자라서** 걸리지 않은 것을 센다.
SKIPS = {
    "judgment": {
        "novelty_judgment_without_claim": """
            ?x a <{ont}PriorArtJudgment> ; <{ont}onGround> <{ont}Rejection_Novelty> .
            FILTER NOT EXISTS {{ ?x <{ont}aboutClaim> ?c }}""",
        "novelty_claim_already_inventive": """
            ?j a <{ont}PriorArtJudgment> ; <{ont}onGround> <{ont}Rejection_Novelty> ;
               <{ont}overPriorArt> ?d ; <{ont}aboutClaim> ?c .
            ?j2 a <{ont}PriorArtJudgment> ; <{ont}onGround> <{ont}Rejection_Inventiveness> ;
                <{ont}overPriorArt> ?d ; <{ont}aboutClaim> ?c .
            BIND(CONCAT(STR(?j), " ", STR(?c)) AS ?x)""",
    },
    "argument": {
        "novelty_judgment_without_document": """
            ?x a <{pa}ExaminerJudgment> ; <{pa}onGround> <{pakr}Ground_29_1> .
            FILTER NOT EXISTS {{ ?x <{pa}supportedBy>/<{pa}includesDocument> ?d }}""",
        "reference_target_not_a_judgment": """
            ?r <{pa}refersToJudgment> ?x . FILTER NOT EXISTS {{ ?x a <{pa}ExaminerJudgment> }}""",
        "self_reference": """
            ?x <{pa}refersToJudgment> ?x .""",
    },
}


SKIPS["argument_abox"] = SKIPS["argument"]


def _skips(g: Graph, layer: str) -> dict[str, int]:
    ns = {"ont": str(ONT), "pa": str(PA), "pakr": str(PAKR)}
    return {k: int(next(iter(g.query(_ASK_COUNT.format(body=b.format(**ns)))))[0])
            for k, b in SKIPS[layer].items()}


def build_layer(layer: str, source: Graph) -> tuple[Graph, dict]:
    inferred = run_rules(source, [RULES_DIR / f for f in LAYER_RULES[layer]])
    check_inferred(inferred, source)
    return inferred, {"status": "built", "input_triples": len(source),
                      "rules": _rule_stats(inferred), "not_fired": _skips(source, layer),
                      "triples": len(inferred)}


def _write(g: Graph, path: Path, title: str) -> str:
    text = _emit(g, PREFIXES, HEADER.format(title=title))
    Graph().parse(data=text, format="turtle")  # 스스로 파싱되지 않는 것은 내지 않는다
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    if not CF_TTL.exists():
        raise SystemExit(f"ERROR: {CF_TTL.name} 가 없다 — make abox-claim-features 가 먼저다.")
    jg, n_blocks = slice_judgments(CF_TTL)
    want = json.loads(CF_REPORT.read_text(encoding="utf-8"))["counts"]["judgments"]
    n_judg = len(set(jg.subjects(RDF.type, ONT.PriorArtJudgment)))
    if not (n_blocks == n_judg == want):
        raise SystemExit(f"ERROR: 잘라 읽은 판단이 리포트와 다르다 — 블록 {n_blocks} · 판단 {n_judg} · "
                         f"리포트 {want}. 직렬화 형태가 바뀌었는지 확인할 것.")

    layers: dict[str, dict] = {}
    inferred, layers["judgment"] = build_layer("judgment", jg)
    layers["judgment"].update(input=f"{CF_TTL.relative_to(ROOT)} (판단 블록 {n_blocks})", input_sha256=_sha(CF_TTL))
    # §20.22 — 실물 논증층의 추론도 같은 산출 파일에 **더한다**. 노드 IRI 가 층마다 달라(RA_judgment_… ·
    # RA_argument_…) 겹치지 않으므로 파일 트리플 수 = 두 층 트리플 수의 합이다.
    out_g = Graph()
    out_g += inferred
    if ARG_ABOX.exists():
        ag = Graph().parse(ARG_ABOX, format="turtle")
        ainf, layers["argument_abox"] = build_layer("argument_abox", ag)
        layers["argument_abox"].update(input=str(ARG_ABOX.relative_to(ROOT)), input_sha256=_sha(ARG_ABOX))
        out_g += ainf
    else:
        layers["argument_abox"] = {"status": "not_loaded",
                                   "why": "원천 계층(data/sources/opinion_notices/)이 없다 — 공개 트리. 0 이 아니라 미적재다."}
    out_sha = _write(out_g, OUT, "SDKB 추론 판단 — 판단층 · 논증층 (규칙 산출 · 별도 그래프)")
    for name in ("judgment", "argument_abox"):
        if layers[name]["status"] == "built":
            layers[name].update(output=str(OUT.relative_to(ROOT)), output_sha256=out_sha)

    if PILOT.exists():
        pg = Graph().parse(PILOT, format="turtle")
        pinf, layers["argument"] = build_layer("argument", pg)
        layers["argument"].update(
            input=str(PILOT.relative_to(ROOT)), input_sha256=_sha(PILOT),
            output=str(PILOT_OUT.relative_to(ROOT)),
            output_sha256=_write(pinf, PILOT_OUT, "SDKB 추론 판단 — 논증층 파일럿 (비공개 · 규칙 산출)"))
    else:
        layers["argument"] = {"status": "not_loaded",
                              "why": "원천 계층(data/sources/)이 없다 — 공개 트리. 0 이 아니라 미적재다."}

    report = {
        "_README": "규칙별 발화(rules)와 입력이 모자라 발화하지 않은 수(not_fired). 추론은 심사관 판단이 아니다.",
        "rule_files": {f: _sha(RULES_DIR / f) for fs in LAYER_RULES.values() for f in fs},
        "layers": layers,
        # 그래프 서명이 읽는 값 — 산출 파일(sdkb-abox-inferred.ttl)의 트리플 수다.
        "triples": len(out_g),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, lay in layers.items():
        if lay["status"] != "built":
            print(f"  {name:9s} 미적재 — {lay['why']}")
            continue
        rules = " · ".join(f"{k} 노드 {v['nodes']}" for k, v in lay["rules"].items()) or "발화 0"
        print(f"  {name:9s} {rules} · 트리플 {lay['triples']} · 미발화 {lay['not_fired']}")
    print(f"→ {OUT.relative_to(ROOT)} · {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
