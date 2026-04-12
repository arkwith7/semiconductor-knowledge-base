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

# ── External namespaces ─────────────────────────────────────────
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

# ── Prefix map for rdflib Graph.bind() ──────────────────────────
PREFIX_MAP: dict[str, Namespace | str] = {
    "sdkb":    SDKB,
    "ont":     SDKB_ONT,
    "data":    SDKB_DATA,
    "gov":     SDKB_GOV,
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
