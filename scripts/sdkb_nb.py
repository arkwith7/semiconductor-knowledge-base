"""Shared notebook/runtime helpers — the single source for graph loading,
the ontology bridge, and the evaluation metrics that notebooks 06/07 and the
A-Box builders all reuse.

Before this module the metric suite was copy-pasted between notebooks 01 and
06 and each notebook re-implemented graph loading + the bridge bootstrap. Now
it is defined once here. The bridge *primitives* (lexicon / alias / norm /
routing) are NOT re-implemented — they are imported from
`build_abox_experts_problems.py`, which stays their canonical definition.

Notebook usage:

    import sys; sys.path.insert(0, str(ROOT / 'scripts'))
    import sdkb_nb as S
    g  = S.load_graph(ROOT)                 # core + every A-Box that exists
    br = S.make_bridge(ROOT)                # lexicon + alias resolver
    S.calculate_mrr_with_ground_truth(...)  # the metric suite
"""

from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path
from typing import Any

from rdflib import Graph

DATA = "https://w3id.org/sdkb/data/"
ONT = "https://w3id.org/sdkb/ont/"
PFX = (f"PREFIX ont:  <{ONT}>\n"
       f"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
       f"PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n")

# A-Box TTL files load_graph will merge onto the core graph when present.
_ABOX_FILES = {
    "experts_problems": "ontology/sdkb-abox-experts-problems.ttl",
    "patents": "ontology/sdkb-abox-patents.ttl",
}
_CORE_FILE = "ontology/sdkb-core-data.ttl"


# ── project root ──────────────────────────────────────────────────────────
def find_root(start: Path | None = None) -> Path:
    """Walk up until the ontology core-data TTL (or its parent) is found."""
    p = (start or Path.cwd()).resolve()
    for cand in (p, *p.parents):
        if (cand / _CORE_FILE).exists() or (cand / "scripts" / "sdkb_nb.py").exists():
            return cand
    return p


# ── bridge primitives: import the canonical builder (single source) ───────
def _load_builder(root: Path):
    spec = importlib.util.spec_from_file_location(
        "abox_builder", str(root / "scripts" / "build_abox_experts_problems.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # safe: main() is __main__-guarded
    return mod


# ── graph loading ─────────────────────────────────────────────────────────
def load_graph(root: Path | None = None, *,
               parts: tuple[str, ...] = ("experts_problems", "patents"),
               require_core: bool = True) -> Graph:
    """Merge core-data + the requested A-Box TTLs into one rdflib Graph.

    Missing A-Box files are skipped (so this works before a given builder has
    run); a missing core file raises unless require_core=False.
    """
    root = root or find_root()
    g = Graph()
    core = root / _CORE_FILE
    if core.exists():
        g.parse(str(core), format="turtle")
    elif require_core:
        raise SystemExit(f"Missing {core} — run `make convert PYTHON=.venv/bin/python`.")
    for key in parts:
        f = root / _ABOX_FILES[key]
        if f.exists():
            g.parse(str(f), format="turtle")
    return g


# ── the bridge: free-text/tag → ontology node, with provenance tier ───────
class Bridge:
    """Resolves terms to ontology nodes via Tier-1 lexicon then Tier-2 alias,
    and routes a matched node to an A-Box predicate by its node *type*."""

    def __init__(self, root: Path, morph: bool = False):
        self._b = _load_builder(root)
        import json
        kg = json.loads((root / "data" / "semiconductor_v0_3.json").read_text())
        self.lex, self.ntype = self._b.build_lexicon(kg)
        self.ali = self._b.load_aliases(self.ntype)
        self.node_label = {n["id"]: n["canonical_name"] for n in kg["nodes"]}
        # phrase keys (len≥2), longest-first, for greedy free-text scanning
        self._keys = sorted((k for k in (set(self.lex) | set(self.ali))
                             if len(k) >= 2), key=len, reverse=True)
        # Optional Korean morphological mode (deterministic given Kiwi
        # version): noun-morpheme + n-gram candidates UNIONed with the
        # substring scan. Korean ontology terms are registered as Kiwi
        # user words so domain compounds segment correctly (다층하드마스크
        # → 하드마스크, 식각하다 → 식각). Off by default — the substring
        # path stays the deterministic floor; notebook 06 is unaffected
        # (it uses tag-list resolve(), not extract_from_text()).
        self.morph = morph
        self._kiwi = None
        if morph:
            try:
                from kiwipiepy import Kiwi
            except ImportError as e:  # pragma: no cover
                raise SystemExit(
                    "Bridge(morph=True) needs kiwipiepy — "
                    "`pip install 'kiwipiepy>=0.17'` (project 'nlp' extra)."
                ) from e
            self._kiwi = Kiwi()
            for k in (set(self.lex) | set(self.ali)):
                if len(k) >= 2 and any("가" <= ch <= "힣" for ch in k):
                    self._kiwi.add_user_word(k.replace(" ", ""), "NNP", 5.0)

    # expose builder pieces so callers never re-implement them
    @property
    def norm(self):
        return self._b.norm

    @property
    def iter_terms(self):
        return self._b.iter_terms

    @property
    def TYPE_ROUTING(self):
        return self._b.TYPE_ROUTING

    @property
    def EXPERT_FIELDS(self):
        return self._b.EXPERT_FIELDS

    @property
    def PROBLEM_FIELDS(self):
        return self._b.PROBLEM_FIELDS

    def resolve(self, term: str) -> tuple[str, list[tuple[str, str]]]:
        """('Tier-1 lexicon'|'Tier-2 alias'|'—', [(node_id, node_type), ...])."""
        k = self._b.norm(term)
        if k in self.lex:
            return "Tier-1 lexicon", self.lex[k]
        if k in self.ali:
            return "Tier-2 alias", self.ali[k]
        return "—", []

    def _morph_candidates(self, text: str) -> set[str]:
        """Normalized noun-morpheme forms + their 2/3-grams (Kiwi)."""
        toks = [tk for tk in self._kiwi.tokenize(str(text)[:6000])
                if tk.tag.startswith("NN") or tk.tag == "SL"]
        forms = [self._b.norm(tk.form) for tk in toks]
        cand = {f for f in forms if f}
        for n in (2, 3):
            for i in range(len(forms) - n + 1):
                cand.add(self._b.norm(" ".join(forms[i:i + n])))
        return cand

    def extract_from_text(self, text: str) -> dict[str, list[tuple[str, str]]]:
        """Free-prose extraction (patent title/abstract/claim). Substring scan
        (ASCII = word-bounded, Hangul = substring); when morph is on, UNION
        with Kiwi noun-morpheme candidates (recovers inflected / verb-derived
        / compound forms the substring scan misses, e.g. 식각하다 → 식각)."""
        t = self._b.norm(text)
        hits: dict[str, list[tuple[str, str]]] = {}
        for k in self._keys:
            if k.isascii():
                if not re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", t):
                    continue
            elif k not in t:
                continue
            hits[k] = self.lex.get(k) or self.ali.get(k) or []
        if self._kiwi is not None:
            for c in self._morph_candidates(text):
                if c in hits:
                    continue
                v = self.lex.get(c) or self.ali.get(c)
                if v:
                    hits[c] = v
        return hits

    def bridge_table(self, entity: dict, fields, kind: str):
        """raw tag → node → A-Box predicate table (notebook 06 §1)."""
        import pandas as pd
        rows = []
        for f in fields:
            for term in self._b.iter_terms(entity.get(f)):
                tier, hits = self.resolve(term)
                if not hits:
                    rows.append({"source_field": f, "raw_tag": term, "tier": "—",
                                 "node_id": "(unmatched — out of ontology)",
                                 "node_label": "", "node_type": "",
                                 "abox_predicate": "(dropped)"})
                    continue
                for nid, typ in hits:
                    route = self._b.TYPE_ROUTING.get(typ)
                    pred = (route[0] if kind == "expert" else route[1]) if route else None
                    rows.append({"source_field": f, "raw_tag": term, "tier": tier,
                                 "node_id": nid,
                                 "node_label": self.node_label.get(nid, ""),
                                 "node_type": typ,
                                 "abox_predicate": f"ont:{pred}" if pred else "(dropped)"})
        return pd.DataFrame(rows)


def make_bridge(root: Path | None = None, *, morph: bool = False) -> Bridge:
    return Bridge(root or find_root(), morph=morph)


# ── metric suite #1 — expert ranking (verbatim from notebooks 01/06) ──────
def calculate_mrr_with_ground_truth(ranked_results: list[list],
                                     ground_truth: dict[str, list[str]]) -> float:
    rr: list[float] = []
    for row in ranked_results:
        if not row:
            continue
        pid, ranked = row[0], row[1:]
        if pid not in ground_truth:
            continue
        relevant = set(ground_truth[pid])
        for pos, eid in enumerate(ranked, start=1):
            if eid in relevant:
                rr.append(1.0 / pos)
                break
        else:
            rr.append(0.0)
    return sum(rr) / len(rr) if rr else 0.0


def calculate_precision_at_k(ranked: list[str], relevant: set[str], k: int = 5) -> float:
    if not ranked or k <= 0:
        return 0.0
    top = ranked[:k]
    return sum(1 for e in top if e in relevant) / min(k, len(top))


def calculate_recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant or not ranked or k <= 0:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def calculate_ndcg_at_k(ranked: list[str], rel_scores: dict[str, float],
                         k: int = 5) -> float:
    if not ranked or k <= 0:
        return 0.0
    dcg = sum((2 ** rel_scores.get(eid, 0.0) - 1) / math.log2(i + 1)
              for i, eid in enumerate(ranked[:k], start=1))
    ideal = sorted(rel_scores.values(), reverse=True)
    idcg = sum((2 ** rel - 1) / math.log2(i + 1)
               for i, rel in enumerate(ideal[:k], start=1))
    return dcg / idcg if idcg > 0 else 0.0


# ── metric suite #2 — prior-art retrieval (verbatim from notebook 04) ─────
def pa_dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def pa_ndcg_at_k(positives_ranked: list[int], k: int = 5) -> float:
    """Binary-relevance NDCG@k over the ranks of the positive citations —
    identical to notebook 04's `ndcg_at_k` so floor vs ontology is one code path."""
    rels = [1 if r <= k else 0 for r in positives_ranked]
    if not any(rels):
        return 0.0
    ideal = sorted(rels, reverse=True)
    denom = pa_dcg(ideal)
    return pa_dcg(rels) / denom if denom > 0 else 0.0


def pa_metrics(pos_ranks: list[int]) -> dict[str, float]:
    """MRR + NDCG@5 + Recall@{5,10,50} for one target's positive ranks
    (exactly notebook 04's per-target block)."""
    return {
        "mrr": 1.0 / min(pos_ranks),
        "ndcg_at_5": pa_ndcg_at_k(pos_ranks, k=5),
        "recall_at_5": sum(1 for r in pos_ranks if r <= 5) / len(pos_ranks),
        "recall_at_10": sum(1 for r in pos_ranks if r <= 10) / len(pos_ranks),
        "recall_at_50": sum(1 for r in pos_ranks if r <= 50) / len(pos_ranks),
    }
