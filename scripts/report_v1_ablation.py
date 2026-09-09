#!/usr/bin/env python3
"""PLAN-005 단계 6-A — V1 공리 단위 절제 (계측 완성 · 그래프는 바꾸지 않는다).

단계 1 의 `report_priorart_baseline.py` 는 §5 V1 의 네 검출기 중 ②(CQ 행 수)만 구현했고
`ont:` 주어만 세어 단계 4 가 만든 `pa:` 공리를 보지 못했다. 그 결과 "8건 중 소비 0" 은
공리의 무의미가 아니라 **계측기의 맹점**이었다 — 추론기 없는 rdflib 에서 T-Box 공리 하나를
빼도 어떤 BGP 질의도 행 수가 변할 수 없다. 이 스크립트는 그 맹점을 닫는다.

동결된 조작적 정의 (결과를 보기 전에 · 계획 파일 2026-09-08 · 사용자 승인):

  공리 a 가 "소비된다" ⟺ 아래 중 하나가 O∖a 에서 변한다.
    ② CQ 스위트 전량의 응답 행 수 벡터                      (run_cq · 추론 없음)
    ③ 생성기 실체화의 입력 — coveredBy 쌍 수 · 바인딩 개념 수 (build_abox_priorart 가
       core 의 `⊑ pa:coveredBy` 와 semi 의 `⊑ pa:TechnicalConcept` 를 **읽는다** · 6-A)
    ④ 태스크 질의의 커버 — "u 가 프로파일 p 의 필수개념이고, u 의 coveredBy 상위 f 를
       문헌 d 가 개시하되 u 자체는 개시하지 않는" (p,u) 쌍 수 · (p,d,u) 수
  **경로(path)** 와 **유량(flow)** 을 구분한다. 경로 = 그 공리를 읽는 소비자가 존재한다.
  유량 = 실제 데이터에서 그 읽기가 결과를 바꿨다. `substitutableWith ⊑ coveredBy` 는
  경로가 있고(생성기가 읽는다) 유량이 0 이다(채굴 쌍이 없다) — 그 둘을 한 열에 뭉개면
  "삭제"와 "대기"가 갈리지 않는다.

④ 를 SPARQL 로 쓰지 않는 이유: 같은 정의의 rdflib COUNT 는 15분 넘게 끝나지 않았다
(2026-09-08 실측). 집합 계수는 1.5초다. CQ32 는 LIMIT 200 에 포화돼 있어(현 rows=200) 행 수로는
coveredBy 의 소비가 보이지 않는다 — 그 값은 기록 열로만 둔다.

이 스크립트는 자원을 바꾸지 않는다. 단계 1 파일(`priorart_baseline.json`)도 다시 쓰지 않는다 —
그것은 2026-09-05 의 기록이다. 산출은 `data/reports/priorart_v1_ablation.json` 과
`--markdown` 으로 렌더한 공리↔소비자 대조표다(§5 · 프로파일은 코드가 만든다).

    python scripts/report_v1_ablation.py --list             # 공리 열거만 (수 초)
    python scripts/report_v1_ablation.py --skip-cq          # ③④ 만 (≈1분)
    python scripts/report_v1_ablation.py --markdown PATH    # 전량 (② 가 공리당 ≈146초)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from rdflib import Graph, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.namespaces import SDKB_ONT, SDKB_PA, SDKB_PA_KR  # noqa: E402
from scripts import build_abox_priorart as gen  # noqa: E402
from scripts.run_cq import DEFAULT_DATA, CQ_DIR, parse_cq, load_graph, run as run_cqs  # noqa: E402

ONT, PA, PAKR = str(SDKB_ONT), str(SDKB_PA), str(SDKB_PA_KR)
ONT_DIR = ROOT / "ontology"
OUT = ROOT / "data" / "reports" / "priorart_v1_ablation.json"
ABOX = ONT_DIR / "sdkb-abox-priorart.ttl"
CORE_DATA = ONT_DIR / "sdkb-core-data.ttl"
CQ32 = "CQ32_novelty_uncovered_essential_concepts"

#: 단계 1 이 본 T-Box 7 + 단계 4 의 pa: 3모듈. 그룹은 열거 규칙을 가른다(아래 enumerate_axioms).
MODULES = {
    "sdkb-core.ttl": "legacy", "sdkb-patent.ttl": "legacy", "sdkb-commercialization.ttl": "legacy",
    "sdkb-foresight.ttl": "legacy", "sdkb-rbv.ttl": "legacy", "sdkb-governance.ttl": "legacy",
    "sdkb-governance-kr.ttl": "legacy",
    "sdkb-priorart-core.ttl": "core", "sdkb-priorart-semi.ttl": "semi", "sdkb-priorart-kr.ttl": "kr",
}
TYPE_KINDS = {
    OWL.TransitiveProperty: "TransitiveProperty", OWL.SymmetricProperty: "SymmetricProperty",
    OWL.FunctionalProperty: "FunctionalProperty", OWL.InverseFunctionalProperty: "InverseFunctionalProperty",
    OWL.AsymmetricProperty: "AsymmetricProperty", OWL.IrreflexiveProperty: "IrreflexiveProperty",
}
PRED_KINDS = {
    RDFS.subPropertyOf: "subPropertyOf", OWL.equivalentClass: "equivalentClass",
    OWL.equivalentProperty: "equivalentProperty", OWL.inverseOf: "inverseOf",
    OWL.propertyChainAxiom: "propertyChainAxiom", OWL.disjointWith: "disjointWith",
    OWL.differentFrom: "differentFrom", OWL.hasKey: "hasKey",
}
PREFIXES = {ONT: "ont", PA: "pa", PAKR: "pa/kr", str(SKOS): "skos"}


def curie(t) -> str:
    if isinstance(t, BNode):
        return "_:bnode"
    s = str(t)
    for ns, px in sorted(PREFIXES.items(), key=lambda kv: -len(kv[0])):
        if s.startswith(ns):
            return f"{px}:{s[len(ns):]}"
    return s


def _ns(t) -> str | None:
    s = str(t)
    for ns in (PAKR, PA, ONT):           # pa/kr 가 pa 보다 길어 먼저 본다
        if s.startswith(ns):
            return ns
    return None


@dataclass
class Axiom:
    id: str
    module: str
    kind: str
    subject: str
    object: str | None
    role: str                       # rbox | binding-property | binding-class | binding-match
    triples: list[tuple] = field(default_factory=list)


def enumerate_axioms(graphs: dict[str, Graph]) -> list[Axiom]:
    """모듈별 추론 공리·바인딩 트리플 전량. 규칙:

    legacy 모듈 — 단계 1 과 같은 규칙(`ont:` 주어의 R-Box 종류만). 그래야 8건이 재현된다.
    pa: 3모듈 — 주어가 ont:/pa:/pa/kr: 이거나 `skos:exactMatch`(C5 의 주어) 인 R-Box 종류 전부 +
      subPropertyOf(ont → pa 는 바인딩) + subClassOf(목적어 pa: 만 · 바인딩) + 개체 exactMatch(바인딩).
    """
    out: list[Axiom] = []
    for fname, g in graphs.items():
        group = MODULES[fname]
        mod = fname.removesuffix(".ttl").replace("sdkb-priorart-", "").replace("sdkb-", "legacy:")
        def _ok(s) -> bool:
            return _ns(s) == ONT if group == "legacy" else (_ns(s) is not None or s == SKOS.exactMatch)
        for cls, kind in TYPE_KINDS.items():
            for s in sorted(g.subjects(RDF.type, cls)):
                if _ok(s):
                    out.append(Axiom(f"{mod}:{kind}:{curie(s)}", mod, kind, curie(s), None, "rbox",
                                     [(s, RDF.type, cls)]))
        for pred, kind in PRED_KINDS.items():
            for s, o in sorted(g.subject_objects(pred), key=lambda so: (str(so[0]), str(so[1]))):
                if not _ok(s):
                    continue
                role = "rbox"
                if kind == "subPropertyOf" and _ns(s) == ONT and _ns(o) == PA:
                    role = "binding-property"
                out.append(Axiom(f"{mod}:{kind}:{curie(s)}→{curie(o)}", mod, kind, curie(s), curie(o), role,
                                 [(s, pred, o)]))
        if group != "legacy":
            for s, o in sorted(g.subject_objects(RDFS.subClassOf), key=lambda so: (str(so[0]), str(so[1]))):
                if _ns(o) == PA and _ns(s) is not None:
                    out.append(Axiom(f"{mod}:subClassOf:{curie(s)}→{curie(o)}", mod, "subClassOf",
                                     curie(s), curie(o), "binding-class", [(s, RDFS.subClassOf, o)]))
            for s, o in sorted(g.subject_objects(SKOS.exactMatch), key=lambda so: (str(so[0]), str(so[1]))):
                if _ns(s) is not None:
                    out.append(Axiom(f"{mod}:exactMatch:{curie(s)}→{curie(o)}", mod, "exactMatch",
                                     curie(s), curie(o), "binding-match", [(s, SKOS.exactMatch, o)]))
    return out


# ── 동결 예측 (계획 파일 2026-09-08 · 결과를 보기 전에) ────────────────────────
#: id → (예측 consumed, 제안 조치, 사유). 여기 없는 공리가 열거되면 리포트가 그것을 표시한다 —
#: 예측표를 사후에 늘리지 않기 위해서다. 조치는 6-B 의 안이며 6-A 는 아무것도 지우지 않았다.
#: 6-B(2026-09-09) 가 "삭제" 로 표시된 6건을 실제로 지웠다 — 표에는 기록으로 남긴다.
#: tests/test_stage6_ablation.py 가 열거 ⊆ 표, 표 ∖ 열거 == 6-B 삭제분 을 고정한다.
_KEEP_LEGACY = ("보존 (§7-2 · 하류 핀)", "단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀")
_SUNSET = ("보존 + 일몰 (D2)", "경로 有(생성기가 읽음) · 유량 0 — PLAN-002 채굴 쌍 없음 · 단계 7 착수까지 Prec 미착수면 삭제")
_INVERSE = ("삭제 (6-B · 술어 포함)", "역술어를 읽는 소비자 없음 — run_cq 무추론 · SHACL inference none")
_DISJOINT = ("불변식 C 신설 (D3)", "현 파이프라인에 소비자 없음 → 6-B 가 배제쌍 동시 타이핑 검사를 validate 에 배선")
_BIND_PROP = ("보존 (바인딩 재분류)", "V6b 이식용 슬롯 바인딩 — R-Box 가 아니라 subClassOf 11건과 같은 급")
_BIND_CLS = ("보존 (바인딩)", "생성기 technical_concept_classes · SHACL sh:class 가 읽음")
_BIND_CLS0 = ("보존 (바인딩 · 인스턴스 대기)", "경로 有 · core-data 인스턴스 0 이라 유량 0")
_MATCH = ("보존 (크로스워크 바인딩)", "C5 제거 후 R-Box 아님 · LegalGround↔RejectionType 해소")
FROZEN: dict[str, tuple[bool, str, str]] = {
    "legacy:core:TransitiveProperty:ont:hasSubStep": (False, *_KEEP_LEGACY),
    "legacy:core:equivalentClass:ont:Dopant→_:bnode": (False, *_KEEP_LEGACY),
    "legacy:patent:TransitiveProperty:ont:broaderClassification": (False, *_KEEP_LEGACY),
    "legacy:patent:subPropertyOf:ont:hasCPC→ont:hasClassification": (False, *_KEEP_LEGACY),
    "legacy:patent:subPropertyOf:ont:hasFTerm→ont:hasClassification": (False, *_KEEP_LEGACY),
    "legacy:patent:subPropertyOf:ont:hasIPC→ont:hasClassification": (False, *_KEEP_LEGACY),
    "legacy:patent:subPropertyOf:ont:hasPriorArtApplicant→ont:hasPriorArt": (False, *_KEEP_LEGACY),
    "legacy:patent:subPropertyOf:ont:hasPriorArtExaminer→ont:hasPriorArt": (False, *_KEEP_LEGACY),
    "core:TransitiveProperty:pa:broaderConcept": (
        False, "삭제 (6-B)", "skos:broader 18쌍 중 길이-2 사슬 0 · 전이는 동결 깊이 {0,1}(§3.3) 과 모순"),
    "core:SymmetricProperty:pa:substitutableWith": (False, *_SUNSET),
    "core:subPropertyOf:skos:exactMatch→pa:coveredBy": (
        False, "삭제 (6-B)", "유량 0 (core-data exactMatch 0) · 가능한 유량은 클래스 정렬 23 + LegalGround 2 = 오염뿐"),
    "core:subPropertyOf:pa:broaderConcept→pa:coveredBy": (
        True, "유지", "생성기가 읽어 coveredBy 16쌍 실체화 · ④ 4,306 쌍이 이 공리에 걸린다"),
    "core:subPropertyOf:pa:substitutableWith→pa:coveredBy": (False, *_SUNSET),
    "core:inverseOf:pa:conceptOfFeature→pa:featureConcept": (False, *_INVERSE),
    "semi:subPropertyOf:ont:aboutClaim→pa:concernsClaim": (False, *_BIND_PROP),
    "semi:subPropertyOf:ont:featureConcept→pa:featureConcept": (False, *_BIND_PROP),
    "semi:subPropertyOf:ont:onGround→pa:onGround": (False, *_BIND_PROP),
    "semi:inverseOf:ont:claimOf→ont:hasClaim": (False, *_INVERSE),
    "semi:inverseOf:ont:featureOf→ont:hasFeature": (False, *_INVERSE),
    "semi:disjointWith:ont:StructuralElement→ont:Material": (False, *_DISJOINT),
    "semi:disjointWith:ont:StructuralElement→ont:Process": (False, *_DISJOINT),
    "semi:disjointWith:ont:TechnicalEffect→ont:StructuralElement": (False, *_DISJOINT),
    "semi:disjointWith:ont:TechnicalFunction→ont:StructuralElement": (False, *_DISJOINT),
    "semi:subClassOf:ont:Device→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:EquipmentClass→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:Material→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:Parameter→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:Problem→pa:TechnicalConcept": (False, *_BIND_CLS0),
    "semi:subClassOf:ont:Process→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:ProcessCondition→pa:TechnicalConcept": (False, *_BIND_CLS0),
    "semi:subClassOf:ont:StructuralElement→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:SubProcess→pa:TechnicalConcept": (True, *_BIND_CLS),
    "semi:subClassOf:ont:TechnicalEffect→pa:TechnicalConcept": (False, *_BIND_CLS0),
    "semi:subClassOf:ont:TechnicalFunction→pa:TechnicalConcept": (False, *_BIND_CLS0),
    "kr:differentFrom:pa/kr:NoticeOfReasons→pa/kr:FinalRejection": (
        False, "삭제 (6-B)", "개체 상이성을 읽는 소비자 없음"),
    "kr:exactMatch:pa/kr:Ground_29_1→ont:Rejection_Novelty": (False, *_MATCH),
    "kr:exactMatch:pa/kr:Ground_29_2→ont:Rejection_Inventiveness": (False, *_MATCH),
}


def _remove(g: Graph, triples: list[tuple]) -> list[tuple]:
    """트리플을 빼고 뺀 것을 돌려준다. 공백노드 목적어는 (주어, 술어)로 되찾는다(단계 1 교정)."""
    removed = []
    for s, p, o in triples:
        if (s, p, o) in g:
            removed.append((s, p, o))
        elif isinstance(o, BNode):
            removed += [(s, p, oo) for oo in g.objects(s, p)]
    for t in removed:
        g.remove(t)
    return removed


def _restore(g: Graph, triples: list[tuple]) -> None:
    for t in triples:
        g.add(t)


# ── ③ · ④ ──────────────────────────────────────────────────────────────────────
def materialization(core: Graph, semi: Graph, core_data: Graph) -> dict:
    classes = gen.technical_concept_classes(semi)
    bound = gen.bound_concepts(core_data, classes)
    exp, _ = gen.covered_by_sources(core, core_data, bound)
    pairs = {(a, b) for ps in exp.values() for a, b in ps}
    return {"bound_concepts": len(bound), "technical_concept_classes": len(classes),
            "covered_by_by_subproperty": {gen._local(p): len(v) for p, v in sorted(exp.items())},
            "covered_by_total": len(pairs), "pairs": pairs}


class TaskSets:
    """A-Box 의 세 술어를 집합으로. ④ 는 여기서 센다(SPARQL 아님 — 모듈 docstring)."""

    def __init__(self, abox: Graph):
        self.ess: dict[URIRef, set[URIRef]] = defaultdict(set)
        for p, u in abox.subject_objects(gen.PA.essentialConcept):
            self.ess[p].add(u)
        self.by_f: dict[URIRef, set[URIRef]] = defaultdict(set)
        for d, f in abox.subject_objects(gen.PA.discloses):
            self.by_f[f].add(d)
        self.abox_covered = set(abox.subject_objects(gen.PA.coveredBy))

    def count(self, pairs: set[tuple[URIRef, URIRef]]) -> tuple[int, int]:
        cov: dict[URIRef, set[URIRef]] = defaultdict(set)
        for u, f in pairs:
            cov[u].add(f)
        n_pu = n_pdu = 0
        for us in self.ess.values():
            for u in us:
                if u not in cov:
                    continue
                ds: set[URIRef] = set()
                for f in cov[u]:
                    ds |= self.by_f.get(f, set())
                ds -= self.by_f.get(u, set())
                if ds:
                    n_pu += 1
                    n_pdu += len(ds)
        return n_pu, n_pdu


def has_reader(ax: Axiom, core: Graph) -> bool:
    """경로(path) — 이 공리를 실제로 읽는 소비자가 파이프라인에 있는가 (구조적 · 데이터 무관)."""
    s, _, o = ax.triples[0]
    if ax.kind == "subPropertyOf" and o == gen.PA.coveredBy:
        return True                                      # build_abox_priorart.covered_by_sources
    if ax.kind == "SymmetricProperty" and (s, RDFS.subPropertyOf, gen.PA.coveredBy) in core:
        return True                                      # 〃 (양방향 방출)
    if ax.kind == "subClassOf":
        return True                                      # technical_concept_classes · SHACL sh:class
    if ax.kind == "disjointWith":
        return True                                      # check_priorart_invariants.check_disjointness (6-B 불변식 C)
    return False                                         # run_cq 무추론 · SHACL inference none


def cq_mentions(cqs, term: str) -> list[str]:
    """설명 열 — 질의 본문이 그 항을 문자열로 담는가. 판정이 아니다."""
    return [c.name for c in cqs if term in c.query]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def _dir_digest(d: Path, glob: str) -> str:
    h = hashlib.sha256()
    for p in sorted(d.glob(glob)):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def ablate(cq_scope: str, log=print) -> dict:
    graphs = {f: Graph().parse(ONT_DIR / f, format="turtle") for f in MODULES}
    axioms = enumerate_axioms(graphs)
    core, semi = graphs["sdkb-priorart-core.ttl"], graphs["sdkb-priorart-semi.ttl"]
    core_data = Graph().parse(CORE_DATA, format="turtle")
    cqs = [parse_cq(p) for p in sorted(CQ_DIR.glob("*.rq"))]

    log(f"· 공리 {len(axioms)}건 열거 · A-Box 적재 중")
    abox = Graph().parse(ABOX, format="turtle")
    tasks = TaskSets(abox)
    base_m = materialization(core, semi, core_data)
    if tasks.abox_covered != base_m["pairs"]:
        raise SystemExit("ERROR: A-Box 의 coveredBy 가 T-Box 주도 실체화와 다르다 — "
                         "`make abox-priorart` 로 다시 짓고 나서 절제할 것")
    base_pu, base_pdu = tasks.count(base_m["pairs"])

    base_rows: dict[str, int] = {}
    g = None
    loaded, missing = [], []
    if cq_scope != "none":
        log("· CQ 그래프 적재 중 (DEFAULT_DATA)")
        g, loaded, missing = load_graph(DEFAULT_DATA)
        t0 = time.time()
        base_rows = {r.name: r.rows for r in run_cqs(g, cqs)}
        log(f"· CQ 기준선 {sum(base_rows.values()):,}행 · {time.time() - t0:.0f}초/회")

    detail = []
    for i, ax in enumerate(axioms, 1):
        mod_graph = graphs[next(f for f in MODULES if f.removesuffix(".ttl")
                                .replace("sdkb-priorart-", "").replace("sdkb-", "legacy:") == ax.module)]
        removed = _remove(mod_graph, ax.triples)
        m = materialization(core, semi, core_data)
        pu, pdu = tasks.count(m["pairs"])
        rec = {
            "id": ax.id, "module": ax.module, "kind": ax.kind, "role": ax.role,
            "subject": ax.subject, "object": ax.object,
            "present_in_graph": bool(removed), "triples_removed": len(removed),
            "materialization_after": {k: v for k, v in m.items() if k != "pairs"},
            "covered_by_delta": m["covered_by_total"] - base_m["covered_by_total"],
            "bound_concepts_delta": m["bound_concepts"] - base_m["bound_concepts"],
            "task_pu_after": pu, "task_pdu_after": pdu,
            "task_pu_delta": pu - base_pu,
            "cq_changed": None, "cq_skipped": True,
            "cq_mentions_subject": cq_mentions(cqs, ax.subject),
            "path": has_reader(ax, core),
        }
        run_cq_here = g is not None and (cq_scope == "all" or ax.role != "binding-class")
        if run_cq_here:
            t0 = time.time()
            removed_g = _remove(g, ax.triples)
            after = {r.name: r.rows for r in run_cqs(g, cqs)}
            _restore(g, removed_g)
            rec["cq_changed"] = sorted(k for k in base_rows if base_rows[k] != after.get(k))
            rec["cq_skipped"] = False
            rec["cq_seconds"] = round(time.time() - t0, 1)
        _restore(mod_graph, removed)
        changed_3 = rec["covered_by_delta"] != 0 or rec["bound_concepts_delta"] != 0
        changed_4 = rec["task_pu_delta"] != 0 or pdu != base_pdu
        changed_2 = bool(rec["cq_changed"])
        rec["consumed"] = changed_2 or changed_3 or changed_4
        rec["consumed_by"] = [k for k, v in (("cq", changed_2), ("materialization", changed_3),
                                             ("task", changed_4)) if v]
        rec["flow"] = rec["consumed"]
        pred = FROZEN.get(ax.id)
        rec["predicted_consumed"] = pred[0] if pred else None
        rec["prediction_ok"] = (pred[0] == rec["consumed"]) if pred else None
        rec["proposed_action"] = pred[1] if pred else "(예측표에 없음)"
        rec["reason"] = pred[2] if pred else ""
        detail.append(rec)
        log(f"  [{i:2d}/{len(axioms)}] {ax.id}  consumed={rec['consumed']}"
            f"{'' if rec['cq_skipped'] else f' · cq {rec['cq_seconds']}s'}")

    by_role: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "consumed": 0})
    for r in detail:
        by_role[r["role"]]["total"] += 1
        by_role[r["role"]]["consumed"] += int(r["consumed"])
    return {
        "plan": "PLAN-005 단계 6-A · V1 공리 단위 절제 (계측 완성)",
        "generator": "scripts/report_v1_ablation.py",
        "generated": str(date.today()),
        "read_only": True,
        "definition": {
            "consumed": "②③④ 중 하나가 O∖a 에서 변한다 (모듈 docstring)",
            "cq_scope": cq_scope,
            "task_measure": "(p,u): u∈essential(p) ∧ ∃d: d discloses coveredBy(u) ∧ ¬(d discloses u)",
            "path_vs_flow": "path = 읽는 소비자가 있다 · flow = 이 데이터에서 결과가 변했다",
        },
        "inputs": {
            **{f"ontology/{f}": _sha(ONT_DIR / f) for f in MODULES},
            "ontology/sdkb-core-data.ttl": _sha(CORE_DATA),
            "ontology/sdkb-abox-priorart.ttl": _sha(ABOX),
            "scripts/build_abox_priorart.py": _sha(ROOT / "scripts" / "build_abox_priorart.py"),
            "queries/cq/*.rq": _dir_digest(CQ_DIR, "*.rq"),
        },
        "graphs_loaded": loaded, "graphs_missing": missing,
        "baseline": {
            "cq_count": len(cqs), "cq_rows_total": sum(base_rows.values()) if base_rows else None,
            "cq32_rows": base_rows.get(CQ32),
            **{k: v for k, v in base_m.items() if k != "pairs"},
            "task_pu": base_pu, "task_pdu": base_pdu,
            "abox_covered_by_matches_tbox_driven": True,
        },
        "summary": {
            "axioms_total": len(detail),
            "consumed": sum(r["consumed"] for r in detail),
            "unconsumed": sum(not r["consumed"] for r in detail),
            "by_role": dict(by_role),
            "unconsumed_rbox_in_pa_modules": sorted(r["id"] for r in detail if r["role"] == "rbox"
                                                    and not r["consumed"] and r["module"] in ("core", "semi", "kr")),
            "prediction_mismatches": sorted(r["id"] for r in detail if r["prediction_ok"] is False),
            "not_in_frozen_table": sorted(r["id"] for r in detail if r["predicted_consumed"] is None),
        },
        "detail": detail,
        "limitations": [
            "② 는 추론기 없는 rdflib 라 구조적으로 0 이다 — §5 문면대로 실행하되 판정은 ③④ 가 진다.",
            "④ 는 프로파일·개시집합을 고정하고 coveredBy 만 바꾼다. 바인딩(subClassOf) 절제는 ③ 의 "
            "bound_concepts 로 검출하며 프로파일 재파생은 하지 않는다(생성기 재실행 30초 × 11).",
            "CQ32 는 LIMIT 200 포화라 행 수가 움직이지 않는다 — cq32_rows 는 기록용이다.",
            "legacy 8건은 §7-2·하류 핀(sdkb-patent.ttl 0a317389…)으로 삭제 대상이 아니다 — 결과와 무관하게.",
        ],
    }


def render_markdown(rep: dict) -> str:
    b, s = rep["baseline"], rep["summary"]
    head = [
        "# PLAN-005 단계 6-A — 공리↔소비자 대조표 (V1 절제 · 기계 산출)",
        "",
        f"> 생성: `{rep['generator']}` · {rep['generated']} · **손으로 고치지 않는다** — "
        f"`make v1-ablation` 이 다시 만든다. 정의는 스크립트 docstring, 예측은 `FROZEN` 표.",
        "",
        f"**결론.** 공리 {s['axioms_total']}건 중 소비 **{s['consumed']}** · 미소비 {s['unconsumed']}. "
        f"pa: 모듈의 R-Box 미소비: {len(s['unconsumed_rbox_in_pa_modules'])}건. "
        f"예측 불일치: {len(s['prediction_mismatches'])}건"
        + (f" — {', '.join(s['prediction_mismatches'])}" if s["prediction_mismatches"] else "") + ".",
        "",
        "| 기준선 | 값 |", "|---|---:|",
        f"| CQ 수 / 행 합 | {b['cq_count']} / {b['cq_rows_total']} |",
        f"| CQ32 행 (LIMIT 200) | {b['cq32_rows']} |",
        f"| coveredBy 쌍 (술어별) | {b['covered_by_total']} {b['covered_by_by_subproperty']} |",
        f"| 바인딩 개념 / 클래스 | {b['bound_concepts']} / {b['technical_concept_classes']} |",
        f"| ④ (p,u) / (p,d,u) | {b['task_pu']:,} / {b['task_pdu']:,} |",
        "",
        "| # | 공리 | 모듈 | 종류 | 역할 | ② CQ 변화 | ③ coveredBy Δ · bound Δ | ④ (p,u) Δ | 경로 | 유량 | 예측 | 제안 | 사유 |",
        "|---:|---|---|---|---|---|---|---:|:-:|:-:|:-:|---|---|",
    ]
    rows = []
    for i, r in enumerate(rep["detail"], 1):
        cq = "skip" if r["cq_skipped"] else (", ".join(r["cq_changed"]) or "—")
        pred = {True: "소비", False: "미소비", None: "?"}[r["predicted_consumed"]]
        ok = "" if r["prediction_ok"] in (True, None) else " ✗"
        rows.append(f"| {i} | `{r['id']}` | {r['module']} | {r['kind']} | {r['role']} | {cq} | "
                    f"{r['covered_by_delta']:+d} · {r['bound_concepts_delta']:+d} | {r['task_pu_delta']:+d} | "
                    f"{'✓' if r['path'] else '—'} | {'✓' if r['flow'] else '—'} | {pred}{ok} | "
                    f"{r['proposed_action']} | {r['reason']} |")
    tail = ["", "## 한계", ""] + [f"- {x}" for x in rep["limitations"]]
    return "\n".join(head + rows + tail) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--markdown", type=Path, default=None, help="대조표를 이 경로에 렌더한다")
    ap.add_argument("--list", action="store_true", help="공리 열거만 출력하고 끝낸다")
    ap.add_argument("--skip-cq", action="store_true", help="② 를 건너뛴다 (③④ 만 · ≈1분)")
    ap.add_argument("--cq-all", action="store_true", help="② 를 바인딩(subClassOf)에도 돌린다")
    args = ap.parse_args()

    if args.list:
        graphs = {f: Graph().parse(ONT_DIR / f, format="turtle") for f in MODULES}
        for ax in enumerate_axioms(graphs):
            print(f"{ax.role:17s} {ax.id}")
        return 0
    for p in (ABOX, CORE_DATA):
        if not p.exists():
            print(f"ERROR: {p.relative_to(ROOT)} 없음 — make abox-priorart", file=sys.stderr)
            return 1
    scope = "none" if args.skip_cq else ("all" if args.cq_all else "rbox")
    rep = ablate(scope)
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"→ {_rel(args.out)}")
    if args.markdown:
        args.markdown.write_text(render_markdown(rep), encoding="utf-8")
        print(f"→ {_rel(args.markdown)}")
    s = rep["summary"]
    print(f"소비 {s['consumed']} / 미소비 {s['unconsumed']} · pa: R-Box 미소비 "
          f"{len(s['unconsumed_rbox_in_pa_modules'])} · 예측 불일치 {len(s['prediction_mismatches'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
