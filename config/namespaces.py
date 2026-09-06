"""SDKB v1.0 Namespace & ID Policy Configuration.

Naming rules (ID slug policy):
  - Node ID pattern: {type_prefix}:{slug}
    e.g. process:lithography, equipment:lam_kiyo_cx
  - Slug: lowercase ASCII, words joined by underscore, no special chars
  - Type prefix: lowercase singular form of node type

Namespace URIs:
  - Base:       https://w3id.org/sdkb/
  - Ontology:   https://w3id.org/sdkb/ont/
  - Data:       https://w3id.org/sdkb/data/
  - Governance: https://w3id.org/sdkb/gov/

External namespaces used:
  - PROV-O:   http://www.w3.org/ns/prov#
  - SKOS:     http://www.w3.org/2004/02/skos/core#
  - DCTERMS:  http://purl.org/dc/terms/
  - SHACL:    http://www.w3.org/ns/shacl#
  - OWL:      http://www.w3.org/2002/07/owl#
  - RDFS:     http://www.w3.org/2000/01/rdf-schema#
  - XSD:      http://www.w3.org/2001/XMLSchema#
"""

from rdflib import Namespace

# ── SDKB namespaces ──────────────────────────────────────────────
SDKB_BASE = "https://w3id.org/sdkb/"
SDKB      = Namespace(SDKB_BASE)
SDKB_ONT  = Namespace(SDKB_BASE + "ont/")
SDKB_DATA = Namespace(SDKB_BASE + "data/")
SDKB_GOV  = Namespace(SDKB_BASE + "gov/")

# ── 선행기술 판단층 (PLAN-005 단계 4) ────────────────────────────
# `pa:` 는 도메인·관할 중립 core 의 이름공간이다. 바인딩은 두 곳으로만 갈린다:
#   · 도메인(반도체) → 기존 `ont:` 를 쓴다. **`semi:` 를 새로 만들지 않는다** —
#     scripts/build_owl.py 의 `SEMI` 가 이미 SemicONTO 라 접두어가 두 뜻을 갖는다(§1-3).
#   · 관할(KR)      → `pakr:`. US 이식은 이 자리에 대응 모듈만 새로 쓴다.
SDKB_PA    = Namespace(SDKB_BASE + "pa/")
SDKB_PA_KR = Namespace(SDKB_BASE + "pa/kr/")

# ── Public release identity ─────────────────────────────────────
# 리포 이름은 발행되는 그래프(rdfs:seeAlso)와 인용 메타데이터(CITATION.cff)에 박힌다.
# 12곳에 흩어져 있던 것이 공개 첫날 404 의 원인이었으므로 한 곳에서만 정한다.
REPO_OWNER = "arkwith7"
REPO_SLUG = "sdkb-dataset"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_SLUG}"
REPO_BLOB = f"{REPO_URL}/blob/main/"
PAGES_URL = f"https://{REPO_OWNER}.github.io/{REPO_SLUG}/"

# 옛 리포 슬러그. 지우지 않는다 — 공개 트리 검사기가 이 문자열의 재유입을 잡는다.
LEGACY_REPO_SLUG = "semiconductor-knowledge-base"

# ── External namespaces ─────────────────────────────────────────
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

# ── Prefix map for rdflib Graph.bind() ──────────────────────────
PREFIX_MAP: dict[str, Namespace | str] = {
    "sdkb":    SDKB,
    "ont":     SDKB_ONT,
    "data":    SDKB_DATA,
    "gov":     SDKB_GOV,
    "pa":      SDKB_PA,
    "pakr":    SDKB_PA_KR,
    "prov":    PROV,
    "skos":    SKOS,
    "dcterms": "http://purl.org/dc/terms/",
    "sh":      "http://www.w3.org/ns/shacl#",
}

# ── Node type → ID prefix mapping ───────────────────────────────
TYPE_PREFIX = {
    "Process":        "process",
    "SubProcess":     "subprocess",
    "EquipmentClass": "equipclass",
    "Equipment":      "equipment",
    "Vendor":         "vendor",
    "Organization":   "organization",
    "Parameter":      "parameter",
    "Metrology":      "metrology",
    "Material":       "material",
    "TechnologyNode": "technode",
    "FailureMode":    "failuremode",
    "RootCause":      "rootcause",
    "Mitigation":     "mitigation",
    "Skill":          "skill",
    # Governance layer extensions
    "EARRule":        "gov/earrule",
    "RegulatedItem":  "gov/eccn",
    "NISTFunction":   "gov/nist",
    "SCIPRule":       "gov/scip",
    "EquipmentState": "gov/eqstate",
}


def node_uri(node_id: str) -> str:
    """Convert a baseline node ID (e.g. 'process:lithography') to a full URI."""
    return SDKB_DATA + node_id.replace(":", "/")
