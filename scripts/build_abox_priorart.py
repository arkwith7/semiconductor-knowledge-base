"""PLAN-005 단계 5-A — 선행기술 판단층(`pa:`) A-Box 실체화.

단계 4 가 만든 어휘(pa:ClaimProfile · pa:Disclosure · pa:ExaminerElement)에 첫 인스턴스를
넣는다. 그 전까지 CQ32 는 0행이 정상이었고 SHACL priorart shape 은 타깃 0(vacuous)이었으며
V2 의 정본 목표 노드(Disclosure)는 잴 수 없었다. 이 생성기가 그 셋을 처음 성립시킨다.

입력 (전부 커밋된 파일 — 자격이 필요 없다)
  mappings/claim_features.parquet                 청구항 → feature → 개념(CURIE) 투영 (1,306,191행)
  data/patents/notice_element_judgments.parquet   심사관 구성 대비표 판정 305행 (2-C · 선택 입력)
  ontology/sdkb-core-data.ttl                     개념 개체의 rdf:type · skos:broader
  ontology/sdkb-priorart-semi.ttl                 어느 ont: 클래스가 pa:TechnicalConcept 인가
  data/sources/harvest_scope_dev_train.json       누출 통제 범위 (ExaminerElement 만 해당)

출력
  ontology/sdkb-abox-priorart.ttl                 gitignore — DENY 된 notice parquet 파생을 담는다
  data/reports/abox_priorart_report.json          미매핑률 리포트 — **5-B(접지율 개선)의 기준선**

무엇을 만드는가
  ClaimProfile   독립항마다 하나. essentialConcept = 그 항의 feature 개념, optionalConcept =
                 그 항을 루트로 갖는 종속항들의 개념(essential 제외). 개념이 0 인 독립항은
                 만들지 않고 미매핑으로 센다 — 좌변이 공집합인 프로파일은 어떤 문헌에도
                 '덮인' 것이 되어 신규성 판정을 오염시킨다.
  Disclosure     문헌마다 하나 — 신규성은 "요소 집합 ⊆ **단일 문헌** 개시 집합" 이므로
                 문헌 단위가 옳다. discloses = 그 문헌 전 청구항 개념의 합집합.
  ExaminerElement 2-C 행 중 캡션 청구항이 그래프에 실재하는 것만. 캡션이 없는 행(38)은
                 elementGroup 으로 대신하지 않는다(단계 4 결정 1 · SHACL 이 강제).
  broaderConcept core-data 의 skos:broader 중 양끝이 바인딩 타입인 것. 같은 쌍을
                 **pa:coveredBy 로도 실체화**한다 — 소비자(run_cq)는 추론기를 돌리지
                 않으므로 sub-property 함의를 단언으로 두지 않으면 확장이 0건 작동한다.
                 전이 폐쇄는 만들지 않는다(§3.3 · 확장 깊이 {0,1} 은 질의의 `?` 가 든다).

무엇을 만들지 않는가 (5-A 비목표 · 사용자 승인)
  MinedAxiom·substitutableWith(채굴 쌍 산출물이 이 저장소에 없다) · ClaimVersion ·
  citationStatus · issuedDate/examRound(원천에 없다 — 지어내지 않는다) · 비 KR/US
  인용문헌의 Disclosure(청구항 분해 0% — 결손으로 센다) · 미바인딩 타입 34 개념
  (FailureMode·Skill·EquipmentClass — semi 가 pa:TechnicalConcept 에 걸지 않았다. 넣으면
  SHACL sh:class 가 문다. 계수만 하고 5-B 의 레버로 넘긴다).

누출 규율
  ClaimProfile·Disclosure 는 청구항 텍스트의 파생이며 심사관 판단을 한 조각도 담지 않는다
  — 분할 제한이 없다. ExaminerElement 는 심사관 판단이므로 scope(dev+train 800 출원)
  밖 행이 하나라도 있으면 **빌드가 죽는다**. 인용 간선(overPriorArt 등)은 내지 않는다.

결정성
  정렬 순회 · 공백노드 0 · 시각 0. 리포트에 TTL 의 sha256 을 적고 테스트가 실물과 대조한다.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import pyarrow.parquet as pq
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS, SKOS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.namespaces import SDKB_DATA, SDKB_ONT, SDKB_PA, SDKB_PA_KR, PROV  # noqa: E402
from scripts.build_notice_element_judgments import normalize_app, scope_applications  # noqa: E402

PA, PAKR, ONT, DATA = SDKB_PA, SDKB_PA_KR, SDKB_ONT, SDKB_DATA

FEATURES = ROOT / "mappings" / "claim_features.parquet"
ELEMENTS = ROOT / "data" / "patents" / "notice_element_judgments.parquet"
CORE_DATA = ROOT / "ontology" / "sdkb-core-data.ttl"
SEMI = ROOT / "ontology" / "sdkb-priorart-semi.ttl"
SCOPE = ROOT / "data" / "sources" / "harvest_scope_dev_train.json"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-priorart.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_priorart_report.json"

#: dcterms:source 는 **생성기와 산출물**을 가리킨다. 통지서 파일명은 담지 않는다(2-B 선례 · §1-5).
SOURCE_FEATURES = "scripts/build_abox_priorart.py -> mappings/claim_features.parquet"
SOURCE_ELEMENTS = "scripts/build_abox_priorart.py -> data/patents/notice_element_judgments.parquet"
#: 원천(KIPRIS 청구항)의 조건을 그대로 계승한다 — ClaimFeature 노드와 같은 리터럴.
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"
ACTIVITY = "activity/priorart_abox_build"

#: 2-C 정규화 라벨 → 판정 개체. 중립 넷은 core, 법리 둘은 KR 관할 모듈에 있다.
#: 표에 없는 라벨은 SystemExit — 조용히 떨어뜨리면 계수가 그래프를 기술하지 못한다.
VERDICT = {
    "Identical": PA.VerdictIdentical,
    "Different": PA.VerdictDifferent,
    "Corresponding": PA.VerdictCorresponding,
    "Similar": PA.VerdictSimilar,
    "WellKnown": PAKR.VerdictWellKnown,
    "DesignChange": PAKR.VerdictDesignChange,
}

FEATURE_COLUMNS = ["publication_id", "side", "claim_id", "is_independent",
                   "feature_concept", "depends_on_claim"]


class Profile(NamedTuple):
    claim_id: str
    side: str
    essential: tuple[str, ...]
    optional: tuple[str, ...]


class Disclosure(NamedTuple):
    publication_id: str
    concepts: tuple[str, ...]


class Element(NamedTuple):
    stem: str
    table_index: int
    element_group: int
    element_no: int
    claim_id: str
    verdict: str


def _u(curie_or_path: str) -> URIRef:
    """CURIE(`process:etch`) 또는 경로(`claim/rej_…_c1`) → data IRI."""
    return URIRef(str(DATA) + curie_or_path.replace(":", "/", 1))


def _concept_curie(iri: URIRef) -> str:
    """개념 개체 IRI → parquet 의 CURIE 표기 (`data/material/sio2` → `material:sio2`)."""
    local = str(iri)[len(str(DATA)):]
    kind, _, name = local.partition("/")
    return f"{kind}:{name}"


# ── 바인딩 타입 · 개념 집합 ─────────────────────────────────────────
def technical_concept_classes(semi: Graph) -> set[URIRef]:
    """semi 가 pa:TechnicalConcept 아래에 건 ont: 클래스 — 하드코딩하지 않고 T-Box 에서 읽는다."""
    out: set[URIRef] = set()
    frontier = [PA.TechnicalConcept]
    while frontier:
        parent = frontier.pop()
        for c in semi.subjects(RDFS.subClassOf, parent):
            if c not in out:
                out.add(c)
                frontier.append(c)
    return out


def bound_concepts(core_data: Graph, classes: set[URIRef]) -> set[str]:
    """바인딩 타입의 개념 개체를 CURIE 집합으로. 미바인딩 개념은 여기 없으므로 자연히 제외된다."""
    out: set[str] = set()
    for c in classes:
        for s in core_data.subjects(RDF.type, c):
            if str(s).startswith(str(DATA)):
                out.add(_concept_curie(s))
    return out


# ── 청구항 → 개념 ────────────────────────────────────────────────────
def load_features(path: Path) -> pd.DataFrame:
    return pq.read_table(path, columns=FEATURE_COLUMNS).to_pandas()


def claim_concepts(df: pd.DataFrame, bound: set[str]) -> tuple[dict[str, frozenset[str]], Counter]:
    """claim_id → 바인딩 개념 집합. 미바인딩 개념은 계수 후 제외한다."""
    stat: Counter = Counter()
    pairs = (df[["claim_id", "feature_concept"]]
             .explode("feature_concept").dropna(subset=["feature_concept"])
             .drop_duplicates())
    stat["claim_concept_pairs_total"] = len(pairs)
    keep = pairs["feature_concept"].isin(bound)
    stat["claim_concept_pairs_unbound"] = int((~keep).sum())
    stat["distinct_concepts_in_source"] = pairs["feature_concept"].nunique()
    stat["distinct_concepts_unbound"] = pairs.loc[~keep, "feature_concept"].nunique()
    pairs = pairs[keep]
    out = {cid: frozenset(sub) for cid, sub in pairs.groupby("claim_id")["feature_concept"]}
    return out, stat


def root_independents(is_independent: dict[str, bool],
                      parents: dict[str, list[str]]) -> tuple[dict[str, frozenset[str]], Counter]:
    """종속항 → 그 항이 최종적으로 매달린 독립항 집합. 부모가 결번·순환이면 빈 집합."""
    stat: Counter = Counter()
    memo: dict[str, frozenset[str]] = {}

    def roots(cid: str, path: tuple[str, ...]) -> frozenset[str]:
        if cid in memo:
            return memo[cid]
        if is_independent.get(cid):
            memo[cid] = frozenset([cid])
            return memo[cid]
        if cid in path or cid not in is_independent:
            return frozenset()          # 순환 또는 존재하지 않는 참조 — memo 하지 않는다(경로 의존)
        acc: set[str] = set()
        for p in parents.get(cid, ()):
            acc |= roots(p, path + (cid,))
        memo[cid] = frozenset(acc)
        return memo[cid]

    out: dict[str, frozenset[str]] = {}
    for cid, indep in is_independent.items():
        if indep:
            continue
        r = roots(cid, ())
        out[cid] = r
        if not r:
            stat["dependent_without_root"] += 1
        elif len(r) > 1:
            stat["dependent_with_multiple_roots"] += 1
    return out, stat


def build_profiles(claims: pd.DataFrame, concepts: dict[str, frozenset[str]],
                   roots: dict[str, frozenset[str]]) -> tuple[list[Profile], Counter]:
    """독립항마다 프로파일. claims 는 claim_id 단위로 유일한 (claim_id, side, is_independent)."""
    stat: Counter = Counter()
    side_of = dict(zip(claims["claim_id"], claims["side"]))
    indep = claims.loc[claims["is_independent"], "claim_id"]
    optional: dict[str, set[str]] = defaultdict(set)
    for dep, rs in roots.items():
        cs = concepts.get(dep)
        if not cs:
            continue
        if not rs:
            stat["optional_dropped_no_root"] += len(cs)
            continue
        for r in rs:
            if r in concepts:
                optional[r] |= cs
            else:
                stat["optional_dropped_root_has_no_profile"] += len(cs)
    out: list[Profile] = []
    for cid in sorted(indep):
        ess = concepts.get(cid)
        stat[f"independent_total__{side_of[cid]}"] += 1
        if not ess:
            stat[f"independent_unmapped__{side_of[cid]}"] += 1
            continue
        opt = optional.get(cid, set()) - ess
        stat["optional_overlapping_essential"] += len(optional.get(cid, set()) & ess)
        out.append(Profile(cid, side_of[cid], tuple(sorted(ess)), tuple(sorted(opt))))
    return out, stat


def build_disclosures(df: pd.DataFrame,
                      concepts: dict[str, frozenset[str]]) -> tuple[list[Disclosure], Counter]:
    """문헌마다 개시집합 = 전 청구항 개념 합집합. 0 이면 결손으로 센다."""
    stat: Counter = Counter()
    docs = df[["publication_id", "side", "claim_id"]].drop_duplicates()
    by_doc: dict[str, set[str]] = defaultdict(set)
    sides_of: dict[str, set[str]] = defaultdict(set)
    for pid, side, cid in docs.itertuples(index=False):
        sides_of[pid].add(side)
        by_doc[pid] |= concepts.get(cid, frozenset())
    stat["documents_in_multiple_sides"] = sum(1 for s in sides_of.values() if len(s) > 1)
    out: list[Disclosure] = []
    for pid in sorted(by_doc):
        for side in sides_of[pid]:
            stat[f"documents_total__{side}"] += 1
        if not by_doc[pid]:
            for side in sides_of[pid]:
                stat[f"documents_without_disclosure__{side}"] += 1
            if "cited" in sides_of[pid]:
                stat[f"cited_without_disclosure__{pid.split('_', 1)[0]}"] += 1
            continue
        out.append(Disclosure(pid, tuple(sorted(by_doc[pid]))))
    return out, stat


def build_hierarchy(core_data: Graph, bound: set[str]) -> tuple[list[tuple[URIRef, URIRef]], Counter]:
    """skos:broader(a, b) 중 양끝이 바인딩 개념인 것. 전이 폐쇄는 만들지 않는다."""
    stat: Counter = Counter()
    out: list[tuple[URIRef, URIRef]] = []
    for a, b in core_data.subject_objects(SKOS.broader):
        stat["skos_broader_in_source"] += 1
        if not (str(a).startswith(str(DATA)) and str(b).startswith(str(DATA))):
            stat["excluded_non_data_iri"] += 1
            continue
        if _concept_curie(a) in bound and _concept_curie(b) in bound:
            out.append((a, b))
        else:
            stat["excluded_unbound"] += 1
    return sorted(out), stat


def build_examiner_elements(elements: pd.DataFrame | None, claim_ids: set[str],
                            scope: set[str]) -> tuple[list[Element], Counter]:
    """2-C 행 → ExaminerElement. 캡션 청구항이 그래프에 실재할 때만. scope 밖은 빌드 실패."""
    stat: Counter = Counter()
    if elements is None:
        stat["source_absent"] = 1
        return [], stat
    stat["rows"] = len(elements)
    stat["documents_in_source"] = elements["source_file"].nunique()
    out: list[Element] = []
    for r in elements.sort_values(["application_number", "source_file", "table_index",
                                   "element_group", "element_no"]).itertuples(index=False):
        app = normalize_app(r.application_number)
        if app not in scope:
            stat["dropped_out_of_scope"] += 1
            continue
        if pd.isna(r.caption_claim_no):
            stat["dropped_no_caption"] += 1
            continue
        cid = f"rej_{app}_c{int(r.caption_claim_no)}"
        if cid not in claim_ids:
            stat["dropped_caption_claim_not_in_graph"] += 1
            continue
        if r.judgment not in VERDICT:
            raise SystemExit(f"ERROR: 알 수 없는 판정 라벨 {r.judgment!r} — VERDICT 표를 고칠 것")
        stem = str(r.source_file).removesuffix(".txt")
        out.append(Element(stem, int(r.table_index), int(r.element_group),
                           int(r.element_no), cid, r.judgment))
        stat["emitted"] += 1
        stat[f"verdict__{r.judgment}"] += 1
    if stat["dropped_out_of_scope"]:
        raise SystemExit(f"ERROR: scope 밖 출원의 행 {stat['dropped_out_of_scope']}건 — "
                         f"2-C 가 보장한 성질이 깨졌다. 원천을 확인할 것(§11.4)")
    stat["documents_emitted"] = len({e.stem for e in out})
    return out, stat


# ── 그래프 ──────────────────────────────────────────────────────────
def emit_graph(profiles: list[Profile], disclosures: list[Disclosure],
               hierarchy: list[tuple[URIRef, URIRef]], elements: list[Element]) -> Graph:
    g = Graph()
    for p, ns in (("pa", PA), ("pakr", PAKR), ("ont", ONT), ("data", DATA), ("prov", PROV),
                  ("dcterms", DCTERMS), ("skos", SKOS), ("xsd", XSD), ("rdfs", RDFS)):
        g.bind(p, ns)
    act = _u(ACTIVITY)
    g.add((act, RDF.type, PROV.Activity))
    g.add((act, RDFS.label, Literal("PLAN-005 stage 5-A prior-art A-Box build", lang="en")))
    lic = Literal(LICENSE, datatype=XSD.string)
    src_f = Literal(SOURCE_FEATURES, datatype=XSD.string)
    src_e = Literal(SOURCE_ELEMENTS, datatype=XSD.string)

    def _stamp(node: URIRef, src: Literal) -> None:
        g.add((node, DCTERMS.source, src))
        g.add((node, DCTERMS.license, lic))
        g.add((node, PROV.wasGeneratedBy, act))

    for pr in sorted(profiles):
        node = _u(f"profile/{pr.claim_id}")
        g.add((node, RDF.type, PA.ClaimProfile))
        g.add((node, PA.profileOf, _u(f"claim/{pr.claim_id}")))
        for c in pr.essential:
            g.add((node, PA.essentialConcept, _u(c)))
        for c in pr.optional:
            g.add((node, PA.optionalConcept, _u(c)))
        _stamp(node, src_f)

    for d in sorted(disclosures):
        node = _u(f"disclosure/{d.publication_id}")
        g.add((node, RDF.type, PA.Disclosure))
        g.add((node, PA.disclosureOf, _u(f"patent/{d.publication_id}")))
        for c in d.concepts:
            g.add((node, PA.discloses, _u(c)))
        _stamp(node, src_f)

    for a, b in hierarchy:
        g.add((a, PA.broaderConcept, b))
        g.add((a, PA.coveredBy, b))        # sub-property 함의의 1홉 실체화 — 전이 폐쇄 아님

    docs: set[str] = set()
    for e in sorted(elements):
        node = _u(f"examiner_element/{e.stem}_t{e.table_index}_g{e.element_group}_e{e.element_no}")
        doc = _u(f"examdoc/{e.stem}")
        g.add((node, RDF.type, PA.ExaminerElement))
        g.add((node, PA.concernsClaim, _u(f"claim/{e.claim_id}")))
        g.add((node, PA.hasVerdict, VERDICT[e.verdict]))
        g.add((node, PA.tableIndex, Literal(e.table_index, datatype=XSD.integer)))
        g.add((node, PA.elementGroup, Literal(e.element_group, datatype=XSD.integer)))
        g.add((node, PA.elementNo, Literal(e.element_no, datatype=XSD.integer)))
        g.add((node, PA.assertedIn, doc))
        _stamp(node, src_e)
        if e.stem not in docs:
            docs.add(e.stem)
            g.add((doc, RDF.type, PA.ExaminationDocument))
            g.add((doc, PA.ofDocumentType, PAKR.NoticeOfReasons))
            _stamp(doc, src_e)
    return g


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _side_table(stat: Counter, total_key: str, missing_key: str, sides: list[str]) -> dict:
    out = {}
    for s in sides:
        total = stat.get(f"{total_key}__{s}", 0)
        missing = stat.get(f"{missing_key}__{s}", 0)
        out[s] = {"total": total, "emitted": total - missing, "unmapped": missing,
                  "unmapped_rate": round(missing / total, 4) if total else None}
    return out


def build_report(g: Graph, ttl_sha: str, classes: set[URIRef], bound: set[str],
                 unbound_concepts: list[str], profiles: list[Profile], p_stat: Counter,
                 disclosures: list[Disclosure], d_stat: Counter, c_stat: Counter,
                 hierarchy: list, h_stat: Counter, elements: list[Element], e_stat: Counter,
                 scope_n: int) -> dict:
    sides = sorted({s for s in ("rej", "cited", "g1", "g2")})
    feature_df: Counter = Counter()
    doc_df: Counter = Counter()
    for pr in profiles:
        for c in pr.essential + pr.optional:
            feature_df[c] += 1
    for d in disclosures:
        for c in d.concepts:
            doc_df[c] += 1
    prof_side = Counter(pr.side for pr in profiles)
    return {
        "plan": "PLAN-005 단계 5-A · 선행기술 판단층 A-Box 실체화",
        "generator": "scripts/build_abox_priorart.py",
        "triples": len(g),
        "ttl_sha256": ttl_sha,
        "inputs": {str(p.relative_to(ROOT)): _sha256(p)
                   for p in (FEATURES, ELEMENTS, CORE_DATA, SEMI, SCOPE) if p.exists()},
        "technical_concept_classes": sorted(str(c).rsplit("/", 1)[-1] for c in classes),
        "concepts": {
            "bound_in_core_data": len(bound),
            "distinct_in_source": c_stat["distinct_concepts_in_source"],
            "bound_used": len(set(feature_df) | set(doc_df)),
            "unbound": c_stat["distinct_concepts_unbound"],
            "unbound_list": unbound_concepts,
            "claim_concept_pairs_total": c_stat["claim_concept_pairs_total"],
            "claim_concept_pairs_unbound": c_stat["claim_concept_pairs_unbound"],
            "note": "미바인딩 개념은 semi 가 pa:TechnicalConcept 에 걸지 않은 타입이다. "
                    "5-A 는 제외하고 센다(사용자 결정 3) — 바인딩은 5-B 의 레버다.",
        },
        "profiles": {
            "emitted": len(profiles),
            "by_side": _side_table(p_stat, "independent_total", "independent_unmapped", sides),
            "emitted_by_side": dict(sorted(prof_side.items())),
            "essential_links": sum(len(pr.essential) for pr in profiles),
            "optional_links": sum(len(pr.optional) for pr in profiles),
            "optional_dropped_no_root": p_stat["optional_dropped_no_root"],
            "optional_dropped_root_has_no_profile": p_stat["optional_dropped_root_has_no_profile"],
            "optional_overlapping_essential_removed": p_stat["optional_overlapping_essential"],
            "dependent_without_root": p_stat["dependent_without_root"],
            "dependent_with_multiple_roots": p_stat["dependent_with_multiple_roots"],
        },
        "disclosures": {
            "emitted": len(disclosures),
            "by_side": _side_table(d_stat, "documents_total", "documents_without_disclosure", sides),
            "cited_without_disclosure_by_prefix": {
                k.split("__", 1)[1]: v for k, v in sorted(d_stat.items())
                if k.startswith("cited_without_disclosure__")},
            "documents_in_multiple_sides": d_stat["documents_in_multiple_sides"],
            "discloses_links": sum(len(d.concepts) for d in disclosures),
            "policy": "청구항이 분해되지 않은 문헌(비 KR/US 인용문헌)은 Disclosure 를 만들지 "
                      "않는다 — 지어내지 않고 결손으로 센다(§4 인용측 분해 결손 처리 방침).",
        },
        "concept_df": {
            "feature_level": dict(sorted(feature_df.items())),
            "doc_level": dict(sorted(doc_df.items())),
        },
        "hierarchy": {
            "skos_broader_in_source": h_stat["skos_broader_in_source"],
            "broader_emitted": len(hierarchy),
            "covered_by_materialized_from_broader": len(hierarchy),
            "excluded_unbound": h_stat["excluded_unbound"],
            "excluded_non_data_iri": h_stat["excluded_non_data_iri"],
            "transitive_closure": False,
        },
        "examiner_elements": {
            "source": "absent" if e_stat.get("source_absent") else str(ELEMENTS.relative_to(ROOT)),
            "rows": e_stat["rows"],
            "emitted": e_stat["emitted"],
            "dropped_no_caption": e_stat["dropped_no_caption"],
            "dropped_caption_claim_not_in_graph": e_stat["dropped_caption_claim_not_in_graph"],
            "dropped_out_of_scope": e_stat["dropped_out_of_scope"],
            "documents_in_source": e_stat["documents_in_source"],
            "documents_emitted": e_stat["documents_emitted"],
            "verdicts": {k.split("__", 1)[1]: v for k, v in sorted(e_stat.items())
                         if k.startswith("verdict__")},
        },
        "leakage": {
            "scope_file": str(SCOPE.relative_to(ROOT)),
            "applications_in_scope": scope_n,
            "statement": "ClaimProfile·Disclosure 는 청구항 텍스트의 파생이며 심사관 판단을 담지 "
                         "않으므로 분할 제한이 없다. ExaminerElement 는 심사관 판단이라 scope "
                         "밖 행이 있으면 빌드가 실패한다. 인용 간선은 이 A-Box 에 없다.",
        },
        "non_goals": ["MinedAxiom / substitutableWith / exactMatch 실체화 (채굴 쌍 산출물 없음)",
                      "ClaimVersion / amendedFrom", "citationStatus 파생",
                      "issuedDate / examRound (원천 없음)", "비 KR/US 인용문헌 Disclosure",
                      "접지율 개선 (5-B)"],
    }


def main() -> int:
    for p in (FEATURES, CORE_DATA, SEMI, SCOPE):
        if not p.exists():
            print(f"ERROR: {p.relative_to(ROOT)} 없음", file=sys.stderr)
            return 1
    core_data = Graph(); core_data.parse(CORE_DATA, format="turtle")
    semi = Graph(); semi.parse(SEMI, format="turtle")
    classes = technical_concept_classes(semi)
    bound = bound_concepts(core_data, classes)

    df = load_features(FEATURES)
    concepts, c_stat = claim_concepts(df, bound)
    all_pairs = df[["claim_id", "feature_concept"]].explode("feature_concept").dropna()
    unbound_concepts = sorted(set(all_pairs["feature_concept"]) - bound)
    claims = df[["claim_id", "side", "is_independent"]].drop_duplicates("claim_id")
    is_indep = dict(zip(claims["claim_id"], claims["is_independent"].astype(bool)))
    parents = {cid: list(dep) for cid, dep in
               df[["claim_id", "depends_on_claim"]].drop_duplicates("claim_id").itertuples(index=False)
               if len(dep)}
    roots, r_stat = root_independents(is_indep, parents)
    profiles, p_stat = build_profiles(claims, concepts, roots)
    p_stat.update(r_stat)
    disclosures, d_stat = build_disclosures(df, concepts)
    hierarchy, h_stat = build_hierarchy(core_data, bound)

    scope = scope_applications()
    elements_df = pd.read_parquet(ELEMENTS) if ELEMENTS.exists() else None
    elements, e_stat = build_examiner_elements(elements_df, set(is_indep), scope)

    g = emit_graph(profiles, disclosures, hierarchy, elements)
    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")
    report = build_report(g, _sha256(OUT_TTL), classes, bound, unbound_concepts,
                          profiles, p_stat, disclosures, d_stat, c_stat,
                          hierarchy, h_stat, elements, e_stat, len(scope))
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {OUT_TTL.relative_to(ROOT)}  {len(g):,} triples · sha256 {report['ttl_sha256'][:12]}…")
    print(f"  ClaimProfile {len(profiles):,} · Disclosure {len(disclosures):,} · "
          f"ExaminerElement {len(elements)} (of {e_stat['rows']}) · "
          f"broaderConcept={len(hierarchy)} · unbound concepts {len(unbound_concepts)}")
    print(f"→ {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
