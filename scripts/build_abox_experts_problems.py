#!/usr/bin/env python3
"""Lift curated experts + SME problems into an RDF A-Box linked to the SDKB ontology.

This is the *bridge / lifting* layer that notebook 06 (SPARQL A-Box matching)
needs. The core-data graph (`make convert` -> ontology/sdkb-core-data.ttl) is
pure domain knowledge (Process / Skill / FailureMode / ...). Experts and SME
problems carry only free-text tags, so we cannot SPARQL-traverse problem ->
required tech -> expert until both endpoints are *instances* that point at the
same ontology node URIs.

The lift is deliberately deterministic and auditable (no fuzzy matching, no LLM):

  Tier-1  exact normalized lexicon match against every node's canonical_name,
          its ID local part, and all synonyms (incl. Korean) in the KG.
  Tier-2  curated alias map (mappings/abox_term_aliases.json) for the
          high-frequency domain terms Tier-1 misses.

Whatever still fails to match is reported verbatim in
data/reports/abox_linking_report.json (top_unmatched) so the residual loss is
honest and the alias file can be extended over time. Genuinely out-of-ontology
terms (DRAM, DDR5, FEOL, generic 'materials') are expected to stay unmatched.

Outputs:
  ontology/sdkb-abox-experts-problems.ttl   — Expert/Problem instances + links
  data/reports/abox_linking_report.json     — coverage / unmatched / orphans

A matched node is routed to a property by its *node type* (not by which source
field it came from), which keeps the schema small and predictable:

  Expert  Skill->hasSkill  Process/SubProcess->hasProcessExpertise
          Material->hasMaterialExpertise  Equipment/EquipmentClass/Vendor->hasEquipmentExperience
  Problem Skill->requiresSkill  Process/SubProcess->involvesProcess
          Material->involvesMaterial  Equipment/EquipmentClass/Vendor->involvesEquipment
          FailureMode->exhibitsFailureMode
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.namespaces import PREFIX_MAP, SDKB_DATA, SDKB_ONT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
EXPERTS_PATH = ROOT / "data" / "experts" / "curated_profiles_kr.json"
EXPERTS_EN_PATH = ROOT / "data" / "experts" / "curated_profiles_en.json"
PROBLEMS_PATH = ROOT / "data" / "problems_external" / "sme_problems_v1.json"
ALIASES_PATH = ROOT / "mappings" / "abox_term_aliases.json"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-experts-problems.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_linking_report.json"

# Fields whose values we try to lift, per entity kind.
EXPERT_FIELDS = (
    "expertise_areas",
    "process_specialization",
    "tech_tags",
    "equipment_experience",
)

# ── Curated ontology_alignment → expert competency links (2026-07-21) ──────
# The profile ships a pre-resolved `ontology_alignment` block, but its ids use a
# DIFFERENT prefix scheme than the KG node ids (e.g. vendor:X ↔ organization:X,
# equipment:X ↔ equipment_class:X, failure:X ↔ failuremode:X, cause:X ↔
# rootcause:X, param:X ↔ parameter:X). We remap per field to the KG prefix, then
# fall back to a normalized canonical-name/synonym lookup for near-miss locals
# (cd_uniformity↔cdu, cdsem↔cd_sem, micro_trenching↔microtrenching …). Whatever
# still fails is genuinely out-of-ontology (process:inspection, mitigation:annealing,
# P00x placeholders) and is reported verbatim — never forced.
#
# field -> (KG prefix, acceptable node types, expert property)
ALIGNMENT_ROUTING: dict[str, tuple[str, frozenset[str], str]] = {
    "process_ids":         ("process",         frozenset({"Process", "SubProcess"}),        "hasProcessExpertise"),
    "subprocess_ids":      ("subprocess",      frozenset({"SubProcess"}),                    "hasProcessExpertise"),
    "vendor_ids":          ("organization",    frozenset({"Vendor", "Organization"}),        "hasEquipmentExperience"),
    "equipment_class_ids": ("equipment_class", frozenset({"EquipmentClass"}),                "hasEquipmentExperience"),
    "mitigation_ids":      ("mitigation",      frozenset({"Mitigation"}),                    "hasSkill"),
}
# alignment failure/root_cause/parameter ids are captured via ExpertCase (grouped),
# not at expert level — see case reification below.

# case_experience fields -> (KG prefix, acceptable types, ExpertCase property)
CASE_ROUTING: list[tuple[str, str, frozenset[str], str]] = [
    ("process_id",       "process",     frozenset({"Process", "SubProcess"}), "caseProcess"),
    ("failure_mode_ids", "failuremode", frozenset({"FailureMode"}),           "caseFailureMode"),
    ("root_cause_ids",   "rootcause",   frozenset({"RootCause"}),             "caseRootCause"),
    ("mitigation_ids",   "mitigation",  frozenset({"Mitigation"}),            "caseMitigation"),
    ("parameter_ids",    "parameter",   frozenset({"Parameter"}),             "caseParameter"),
]

# Expert career datatype fields (curated_profiles_kr.json → A-Box). All values
# are de-identified altered/synthetic — no claim about a real individual
# (docs/deidentification_protocol.md §1.5). experience_years is dropped (==
# years_experience for all 110); name_korean is dropped (== name for all 110).
EXPERT_DT_SINGLE: list[tuple[str, str, str]] = [
    ("age",                     "age",                    "integer"),
    ("education",               "education",              "string"),
    ("current_status",          "currentStatus",          "string"),
    ("years_experience",        "yearsExperience",        "integer"),
    ("retirement_year",         "retirementYear",         "gYear"),
    ("patent_count",            "patentCount",            "integer"),
    ("publication_count",       "publicationCount",       "integer"),
    ("toeic_score",             "toeicScore",             "integer"),
    ("security_clearance",      "securityClearance",      "string"),
    ("consulting_availability", "consultingAvailability", "string"),
    ("specialization",          "specialization",         "string"),
    ("profile_summary",         "profileSummary",         "string"),
    ("hourly_rate_range",       "hourlyRateRange",        "string"),
    ("nationality",             "nationality",            "string"),
    ("last_activity",           "lastActivity",           "date"),
    ("has_nct",                 "hasNCT",                 "boolean"),
]
EXPERT_DT_MULTI: list[tuple[str, str]] = [
    ("certifications",         "hasCertification"),
    ("languages",              "language"),
    ("major_projects",         "majorProject"),
    ("preferred_project_type", "preferredProjectType"),
    ("work_history_countries", "workHistoryCountry"),
]
PROBLEM_FIELDS = (
    "process_area",
    "required_expertise",
    "equipment_involved",
    "symptoms",
    "industry_tags",
)

# node type -> (expert property, problem property). None = drop for that kind.
TYPE_ROUTING: dict[str, tuple[str | None, str | None]] = {
    "Skill":          ("hasSkill",              "requiresSkill"),
    "Process":        ("hasProcessExpertise",   "involvesProcess"),
    "SubProcess":     ("hasProcessExpertise",   "involvesProcess"),
    "Material":       ("hasMaterialExpertise",  "involvesMaterial"),
    "Equipment":      ("hasEquipmentExperience", "involvesEquipment"),
    "EquipmentClass": ("hasEquipmentExperience", "involvesEquipment"),
    "Vendor":         ("hasEquipmentExperience", "involvesEquipment"),
    "FailureMode":    (None,                    "exhibitsFailureMode"),
    "RootCause":      (None,                    "relatedToTopic"),
    "Mitigation":     ("hasSkill",              "relatedToTopic"),
    "Metrology":      ("hasEquipmentExperience", "involvesEquipment"),
    "TechnologyNode": ("hasProcessExpertise",   "involvesProcess"),
}

# Mitigation node -> Skill node (slug-equal pairs auto-detected; a few near
# pairs curated here) so the deep SPARQL path
#   problem exhibitsFailureMode ?fm . ?fm isDueTo ?rc . ?rc mitigatedBy ?m .
#   ?m mitigationProvidesSkill ?s
# resolves to an actionable skill.
MITIGATION_SKILL_ALIASES = {
    "mitigation:chamber_clean": "skill:chamber_conditioning",
    "mitigation:gas_chemistry_change": "skill:gas_chemistry",
    "mitigation:slurry_change": "skill:slurry_management",
    "mitigation:mask_review": "skill:mask_engineering",
    "mitigation:endpoint_tuning": "skill:endpoint_detection",
}

_WS = re.compile(r"[\s/_\-.\(\)]+")


def norm(s: object) -> str:
    """Lowercase; collapse / _ - . ( ) and whitespace into single spaces."""
    return _WS.sub(" ", str(s or "").lower()).strip()


def node_uri(node_id: str) -> URIRef:
    """Mirror scripts/convert_rdf.uri so A-Box refs resolve against core-data."""
    return URIRef(str(SDKB_DATA) + node_id.replace(":", "/"))


def iter_terms(value: object):
    """Yield individual terms; a scalar string is one term, never char-iterated."""
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for v in value:
            yield from iter_terms(v)
    else:
        s = str(value).strip()
        if s:
            yield s


def build_lexicon(kg: dict) -> tuple[dict[str, list[tuple[str, str]]], dict[str, str]]:
    """Return (tier1 lexicon: normterm -> [(node_id, type)], node_id -> type)."""
    lex: dict[str, set[tuple[str, str]]] = defaultdict(set)
    node_type: dict[str, str] = {}
    for n in kg["nodes"]:
        nid, typ = n["id"], n["type"]
        node_type[nid] = typ
        local = nid.split(":", 1)[1] if ":" in nid else nid
        for key in (n.get("canonical_name"), local, local.replace("_", " ")):
            k = norm(key)
            if k:
                lex[k].add((nid, typ))
    for s in kg.get("synonyms", []):
        nid = s["node_id"]
        k = norm(s.get("term"))
        if k and nid in node_type:
            lex[k].add((nid, node_type[nid]))
    return {k: sorted(v) for k, v in lex.items()}, node_type


def load_aliases(node_type: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    raw = json.loads(ALIASES_PATH.read_text())
    out: dict[str, list[tuple[str, str]]] = {}
    bad: list[str] = []
    for term, target in raw.items():
        if term.startswith("_"):
            continue
        ids = [target] if isinstance(target, str) else list(target)
        resolved = []
        for nid in ids:
            if nid in node_type:
                resolved.append((nid, node_type[nid]))
            else:
                bad.append(f"{term} -> {nid}")
        if resolved:
            out[norm(term)] = resolved
    if bad:
        print(f"  ! {len(bad)} alias target(s) not in KG (ignored): {bad[:5]}",
              file=sys.stderr)
    return out


_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    """Deterministic slug for an equipment-model node local part."""
    return _SLUG.sub("_", str(s).lower()).strip("_")


def resolve_alignment(fid: str, prefix: str, ok_types: frozenset[str],
                      node_type: dict[str, str],
                      lexicon: dict[str, list[tuple[str, str]]]) -> str | None:
    """Resolve a curated alignment/case id to a KG node id, deterministically.

    (1) field-driven prefix remap + exact id match, then
    (2) normalized local-name lookup in the canonical-name/synonym lexicon,
        filtered to the acceptable node types (single hit, or lexicographically
        smallest on a tie). Returns None when genuinely out of ontology.
    """
    local = fid.split(":", 1)[-1]
    kid = f"{prefix}:{local}"
    if kid in node_type and node_type[kid] in ok_types:
        return kid
    cands = sorted(nid for nid, typ in lexicon.get(norm(local), ())
                   if typ in ok_types)
    return cands[0] if cands else None


_XSD = {"integer": XSD.integer, "string": XSD.string, "boolean": XSD.boolean,
        "date": XSD.date, "gYear": XSD.gYear}


def typed_literal(value: object, xsd_kind: str) -> Literal | None:
    """Coerce a JSON scalar to a typed Literal; None if empty/uncoercible."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    dt = _XSD[xsd_kind]
    if xsd_kind == "integer":
        try:
            return Literal(int(value), datatype=dt)
        except (TypeError, ValueError):
            return None
    if xsd_kind == "boolean":
        return Literal(bool(value), datatype=dt)
    if xsd_kind == "gYear":
        # values arrive as "2024"; keep only a 4-digit year.
        m = re.search(r"\d{4}", str(value))
        return Literal(m.group(0), datatype=dt) if m else None
    return Literal(str(value).strip(), datatype=dt)


def main() -> int:
    if not KG_PATH.exists():
        print(f"ERROR: {KG_PATH} not found", file=sys.stderr)
        return 1

    kg = json.loads(KG_PATH.read_text())
    lexicon, node_type = build_lexicon(kg)
    aliases = load_aliases(node_type)

    experts = json.loads(EXPERTS_PATH.read_text())["experts"]
    experts_en = {e["expert_id"]: e
                  for e in json.loads(EXPERTS_EN_PATH.read_text())["experts"]} \
        if EXPERTS_EN_PATH.exists() else {}
    problems = json.loads(PROBLEMS_PATH.read_text())["problems"]

    g = Graph()
    for pfx, ns in PREFIX_MAP.items():
        g.bind(pfx, str(ns))
    g.bind("owl", str(OWL))
    g.bind("rdfs", str(RDFS))
    g.bind("skos", str(SKOS))
    g.bind("xsd", str(XSD))

    # 어휘 선언은 여기서 하지 않는다 (CLAUDE.md §1.2).
    #
    # 예전에는 이 A-Box 가 owl:Class 2개(Expert·Problem)와 owl:ObjectProperty 10개를
    # **자기 안에서 인라인 선언**했다. TBox 에는 하나도 없었다 — 그래서 TBox 만 읽는
    # 소비자에게 인력·문제 축은 아예 존재하지 않는 어휘였고, 추론기·SHACL 이 검증할 수
    # 없는 자리에 있었다. 특허 A-Box 가 겪고 고친 것과 같은 사고다 (§8-2).
    #
    # 이제 전부 TBox 소유다:
    #   - Expert · Problem · hasSkill · hasProcessExpertise · hasMaterialExpertise ·
    #     hasEquipmentExperience · involvesProcess · involvesEquipment ·
    #     mitigationProvidesSkill      → sdkb-core.ttl (scripts/build_owl.py)
    #   - involvesMaterial · exhibitsFailureMode · relatedToTopic
    #                                   → sdkb-patent.ttl (domain 을 Patent ∪ Problem 으로 넓혔다.
    #                                     Patent 로 좁혀두면 이 A-Box 의 Problem 들이
    #                                     RDFS domain 함의로 Patent 가 된다)
    #   - requiresSkill                 → sdkb-core.ttl (기존)

    # ── Mitigation -> Skill enrichment (slug-equality + curated near pairs) ──
    skill_ids = {n["id"] for n in kg["nodes"] if n["type"] == "Skill"}
    mit_skill = 0
    for n in kg["nodes"]:
        if n["type"] != "Mitigation":
            continue
        slug = n["id"].split(":", 1)[1]
        cand = f"skill:{slug}"
        target = cand if cand in skill_ids else MITIGATION_SKILL_ALIASES.get(n["id"])
        if target in skill_ids:
            g.add((node_uri(n["id"]), SDKB_ONT.mitigationProvidesSkill,
                   node_uri(target)))
            mit_skill += 1

    # ── Linking bookkeeping ────────────────────────────────────────────────
    tier_counts = Counter()
    unmatched = Counter()
    matched_terms: set[str] = set()
    all_terms: set[str] = set()

    def resolve(term: str) -> list[tuple[str, str]]:
        all_terms.add(term)
        nt = norm(term)
        if nt in lexicon:
            tier_counts["tier1_lexicon"] += 1
            matched_terms.add(nt)
            return lexicon[nt]
        if nt in aliases:
            tier_counts["tier2_alias"] += 1
            matched_terms.add(nt)
            return aliases[nt]
        tier_counts["unmatched"] += 1
        unmatched[term] += 1
        return []

    def link_entity(uri: URIRef, src: dict, fields, kind: str) -> int:
        """Add type-routed links; return count of distinct ontology nodes linked."""
        linked: set[str] = set()
        for f in fields:
            for term in iter_terms(src.get(f)):
                for nid, typ in resolve(term):
                    route = TYPE_ROUTING.get(typ)
                    if not route:
                        continue
                    prop = route[0] if kind == "expert" else route[1]
                    if prop is None:
                        continue
                    g.add((uri, SDKB_ONT[prop], node_uri(nid)))
                    linked.add(nid)
        return len(linked)

    # ── Expert competency links from curated ontology_alignment ────────────
    # The alignment block replaces the fragile text-matcher for the
    # process/equipment/vendor/skill axes. Material expertise has no alignment
    # axis, so it keeps the lexicon text-matcher (materials only) — dropping it
    # would silently regress hasMaterialExpertise.
    align_resolved = Counter()      # field -> resolved id occurrences
    align_unmatched: Counter = Counter()  # fid -> occurrences (honest residual)
    model_seen: set[str] = set()    # equipment-model slugs already declared
    model_links = 0
    case_count = 0

    def link_alignment(uri: URIRef, src: dict) -> int:
        linked: set[str] = set()
        align = src.get("ontology_alignment") or {}
        for fld, (prefix, ok_types, prop) in ALIGNMENT_ROUTING.items():
            for fid in iter_terms(align.get(fld)):
                nid = resolve_alignment(fid, prefix, ok_types, node_type, lexicon)
                if nid is None:
                    align_unmatched[fid] += 1
                    continue
                align_resolved[fld] += 1
                g.add((uri, SDKB_ONT[prop], node_uri(nid)))
                linked.add(nid)
        return len(linked)

    # 정렬(ontology_alignment)에는 **재료·스킬 축이 없다** — process/vendor/equipment_class/
    # mitigation 만 있다. 그래서 이 둘만 기존 텍스트 매칭으로 잇는다. 정렬로 전량 갈아타면
    # 전문가→Skill 링크가 사라져(hasSkill 이 Mitigation 만 가리킴) "이 공정에 필요한 스킬을
    # 가진 전문가"(CQ11)가 0행이 된다 — 어휘 검증 커버리지가 잡아낸 회귀다(§5.2).
    _TEXT_AXES = {"Material": "hasMaterialExpertise", "Skill": "hasSkill"}

    def link_text_axes(uri: URIRef, src: dict) -> int:
        """재료·스킬 — 정렬이 담지 않는 두 축만 텍스트 매칭으로 잇는다."""
        linked: set[str] = set()
        for f in EXPERT_FIELDS:
            for term in iter_terms(src.get(f)):
                for nid, typ in resolve(term):
                    prop = _TEXT_AXES.get(typ)
                    if prop:
                        g.add((uri, SDKB_ONT[prop], node_uri(nid)))
                        linked.add(nid)
        return len(linked)

    def emit_equipment_models(uri: URIRef, src: dict) -> int:
        nonlocal model_links
        n = 0
        for model in iter_terms(src.get("equipment_models")):
            slug = slugify(model)
            if not slug:
                continue
            m_uri = node_uri(f"equipment_model:{slug}")
            if slug not in model_seen:
                model_seen.add(slug)
                g.add((m_uri, RDF.type, SDKB_ONT.EquipmentModel))
                g.add((m_uri, SKOS.prefLabel, Literal(model, lang="en")))
            g.add((uri, SDKB_ONT.hasEquipmentExperience, m_uri))
            model_links += 1
            n += 1
        return n

    def emit_cases(uri: URIRef, src: dict, eid: str) -> int:
        nonlocal case_count
        n = 0
        for idx, case in enumerate(src.get("case_experience") or [], start=1):
            n += 1
            case_count += 1
            c_uri = node_uri(f"case:{eid}_{idx}")
            g.add((c_uri, RDF.type, SDKB_ONT.ExpertCase))
            g.add((c_uri, SKOS.prefLabel, Literal(f"{eid} case {idx}", lang="en")))
            g.add((uri, SDKB_ONT.hasCaseExperience, c_uri))
            src_val = case.get("source")
            if src_val:
                g.add((c_uri, SDKB_ONT.caseSource, Literal(str(src_val), datatype=XSD.string)))
            for fld, prefix, ok_types, prop in CASE_ROUTING:
                for fid in iter_terms(case.get(fld)):
                    nid = resolve_alignment(fid, prefix, ok_types, node_type, lexicon)
                    if nid is None:
                        align_unmatched[fid] += 1
                        continue
                    align_resolved[fld] += 1
                    g.add((c_uri, SDKB_ONT[prop], node_uri(nid)))
        return n

    expert_orphans: list[str] = []
    for e in experts:
        eid = e["expert_id"]
        u = node_uri(f"expert:{eid}")
        g.add((u, RDF.type, SDKB_ONT.Expert))
        # 인스턴스의 이름은 skos:prefLabel 이다 (rdfs:label 은 TBox 의 클래스·속성 이름).
        # 이 A-Box 만 rdfs:label 을 쓰고 있었고, 그래서 "이 공정에 필요한 스킬을 가진
        # 전문가는 누구인가" 라는 질의가 **IRI 만** 돌려줬다 — 답은 하는데 읽히지 않았다.
        #
        # KR 파일의 이름은 **전부 가명**이다 — 실 경력기술서 파생 5건은 비식별 변조 단계에서
        # 가명이 부여됐고 나머지는 생성값이다(docs/deidentification_protocol.md). EN 파일은
        # 자리표시자("Kim, [Given Name]")라 대표 이름으로 삼을 수 없으므로,
        # prefLabel 은 KR 가명(@ko) · EN 표기는 altLabel(@en) 이다.
        kr_name = e.get("name")
        en_name = experts_en.get(eid, {}).get("name")
        if kr_name:
            g.add((u, SKOS.prefLabel, Literal(kr_name, lang="ko")))
            if en_name:
                g.add((u, SKOS.altLabel, Literal(en_name, lang="en")))
        elif en_name:
            g.add((u, SKOS.prefLabel, Literal(en_name, lang="en")))
        else:
            g.add((u, SKOS.prefLabel, Literal(eid, lang="en")))
        if e.get("region"):
            g.add((u, SDKB_ONT.region, Literal(e["region"])))
        g.add((u, SDKB_ONT.complianceFlag,
               Literal(bool(e.get("compliance_flag")), datatype=XSD.boolean)))

        # ── de-identified career datatype fields (protocol §1.5) ──
        for fld, prop, kind in EXPERT_DT_SINGLE:
            lit = typed_literal(e.get(fld), kind)
            if lit is not None:
                g.add((u, SDKB_ONT[prop], lit))
        # formerEmployer: scalar + list, de-duplicated, deterministic order.
        employers = set(iter_terms(e.get("former_employer"))) | \
            set(iter_terms(e.get("former_employers")))
        for emp in sorted(employers):
            g.add((u, SDKB_ONT.formerEmployer, Literal(emp, datatype=XSD.string)))
        for fld, prop in EXPERT_DT_MULTI:
            for val in iter_terms(e.get(fld)):
                g.add((u, SDKB_ONT[prop], Literal(val, datatype=XSD.string)))

        # ── competency + case links ──
        n_links = link_alignment(u, e) + link_text_axes(u, e)
        emit_equipment_models(u, e)
        emit_cases(u, e, eid)
        if n_links == 0:
            expert_orphans.append(eid)

    problem_orphans: list[str] = []
    for p in problems:
        pid = p["problem_id"]
        u = node_uri(f"problem:{pid}")
        g.add((u, RDF.type, SDKB_ONT.Problem))
        # 문제 제목은 원천(sme_problems_v1.json)이 영문이다.
        g.add((u, SKOS.prefLabel, Literal(p.get("problem_title") or pid, lang="en")))
        for fld, prop in (("compliance_sensitivity", "complianceSensitivity"),
                          ("client_country", "clientCountry"),
                          ("region", "region"),
                          ("company_type", "companyType"),
                          ("problem_category", "problemCategory")):
            if p.get(fld):
                g.add((u, SDKB_ONT[prop], Literal(p[fld])))
        if link_entity(u, p, PROBLEM_FIELDS, "problem") == 0:
            problem_orphans.append(pid)

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    report = {
        "inputs": {
            "kg": str(KG_PATH.relative_to(ROOT)),
            "experts": len(experts),
            "problems": len(problems),
        },
        "triples": len(g),
        "mitigation_to_skill_links": mit_skill,
        "expert_enrichment": {
            "alignment_resolved_by_field": dict(align_resolved),
            "alignment_unmatched_occurrences": sum(align_unmatched.values()),
            "alignment_distinct_unmatched": len(align_unmatched),
            "equipment_models_declared": len(model_seen),
            "equipment_model_links": model_links,
            "expert_cases": case_count,
            "top_alignment_unmatched": [
                {"id": t, "occurrences": c}
                for t, c in align_unmatched.most_common(30)
            ],
            "note": "Alignment ids use a different prefix scheme than KG node "
                    "ids; resolved by field-driven remap + normalized "
                    "canonical-name fallback. Unmatched ids are genuinely "
                    "out-of-ontology (e.g. process:inspection, mitigation:annealing, "
                    "P00x placeholders) and are never forced.",
        },
        "term_resolution": {
            "distinct_terms_seen": len(all_terms),
            "tier1_lexicon_hits": tier_counts["tier1_lexicon"],
            "tier2_alias_hits": tier_counts["tier2_alias"],
            "unmatched_occurrences": tier_counts["unmatched"],
            "distinct_unmatched": len(unmatched),
            "distinct_matched": len(matched_terms),
        },
        "orphans": {
            "experts_with_no_ontology_link": expert_orphans,
            "problems_with_no_ontology_link": problem_orphans,
            "note": "Orphans are un-rankable by the graph query — this is the "
                    "honest residual loss of the deterministic lift.",
        },
        "top_unmatched": [
            {"term": t, "occurrences": c} for t, c in unmatched.most_common(60)
        ],
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    tr = report["term_resolution"]
    print(f"✓ A-Box ({len(g)} triples) → {OUT_TTL.relative_to(ROOT)}")
    print(f"  experts={len(experts)} (orphans {len(expert_orphans)})  "
          f"problems={len(problems)} (orphans {len(problem_orphans)})  "
          f"mit→skill={mit_skill}")
    print(f"  terms: {tr['distinct_matched']} matched / "
          f"{tr['distinct_unmatched']} unmatched distinct  "
          f"(tier1={tr['tier1_lexicon_hits']} tier2={tr['tier2_alias_hits']} "
          f"miss={tr['unmatched_occurrences']} occ)")
    ee = report["expert_enrichment"]
    print(f"  enrichment: align_resolved={sum(ee['alignment_resolved_by_field'].values())} "
          f"(unmatched {ee['alignment_unmatched_occurrences']} occ / "
          f"{ee['alignment_distinct_unmatched']} distinct)  "
          f"equip_models={ee['equipment_models_declared']} (links {ee['equipment_model_links']})  "
          f"cases={ee['expert_cases']}")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
