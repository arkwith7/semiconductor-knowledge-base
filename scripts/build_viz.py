"""Build interactive HTML visualizations for SDKB.

Generates three Pyvis network views plus a landing page under ``site/``.
The output directory is published to GitHub Pages by the
``viz-deploy`` GitHub Actions workflow.

Views
-----
1. ``baseline.html``  — 198-node / 268-edge core ontology graph
2. ``sirp.html``      — Top-50 SIRP patents and their examiner-cited prior art
3. ``pillars.html``   — Class skeletons of the four pillar modules
                        (patent / rbv / commercialization / foresight)

The landing page (``index.html``) contextualises each view inside the
Quantitative Technology Management Lab research agenda and links to the
underlying source files in the repository.
"""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Iterable

import pandas as pd
import rdflib
from pyvis.network import Network

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "site"

# ── Visual palette ────────────────────────────────────────────────
TYPE_COLORS: dict[str, str] = {
    # Baseline 14 types
    "Process":         "#3B82F6",
    "SubProcess":      "#60A5FA",
    "Equipment":       "#10B981",
    "EquipmentClass":  "#34D399",
    "Material":        "#F59E0B",
    "FailureMode":     "#EF4444",
    "RootCause":       "#F87171",
    "Mitigation":      "#FB923C",
    "Metrology":       "#6B7280",
    "Parameter":       "#9CA3AF",
    "Organization":    "#8B5CF6",
    "Vendor":          "#A78BFA",
    "Skill":           "#EC4899",
    "TechnologyNode":  "#06B6D4",
    "Device":          "#14B8A6",   # A2 device/product layer (plan §7.4-3)
    "DeviceCategory":  "#0D9488",
    # SIRP additions
    "Patent":          "#0EA5E9",
    "PriorArt":        "#FACC15",
    # 4-pillar
    "patent":          "#0EA5E9",
    "rbv":             "#F97316",
    "commercialization": "#22C55E",
    "foresight":       "#A855F7",
}
DEFAULT_COLOR = "#9CA3AF"

PILLAR_TTLS = {
    "patent":            "ontology/sdkb-patent.ttl",
    "rbv":               "ontology/sdkb-rbv.ttl",
    "commercialization": "ontology/sdkb-commercialization.ttl",
    "foresight":         "ontology/sdkb-foresight.ttl",
}

# ── SIRP backbone: process_family → ontology Process anchor ───────
# Baseline Processes (semiconductor_v0_3.json) are reused where possible;
# the four ``process:*`` anchors at the bottom are synthetic domain hubs
# for patent scopes that the baseline does not yet cover.
PROCESS_FAMILY_MAP: dict[str, str] = {
    "etch":                "process:etch",
    "deposition":          "process:deposition",
    "metallization":       "process:deposition",
    "interconnect":        "process:deposition",
    "gate_dielectric":     "process:deposition",
    "photo":               "process:lithography",
    "oxidation_diffusion": "process:diffusion",
    "oxidation":           "process:diffusion",
    "thermal":             "process:diffusion",
    "implant":             "process:implant",
    "3d_integration":      "process:packaging",
    "packaging":           "process:packaging",
    "backend_packaging":   "process:packaging",
    "memory":              "process:device",
    "memory_cell":         "process:device",
    "memory_dram":         "process:device",
    "image_sensor":        "process:device",
    "mems":                "process:device",
    "components":          "process:device",
    "equipment":           "process:equipment",
    "materials":           "process:materials",
    "general":             "process:general",
}
SYNTHETIC_BACKBONE: dict[str, tuple[str, str]] = {
    "process:packaging": (
        "Packaging / 3D",
        "Backend packaging and 3D integration domain hub (non-baseline anchor).",
    ),
    "process:device": (
        "Device / Memory / Sensor",
        "Memory cell, image sensor, MEMS and device-level scope (non-baseline anchor).",
    ),
    "process:equipment": (
        "Equipment",
        "Equipment-level patent scope (non-baseline anchor).",
    ),
    "process:materials": (
        "Materials",
        "Materials-level patent scope (non-baseline anchor).",
    ),
    "process:general": (
        "General",
        "Cross-cutting / general scope (non-baseline anchor).",
    ),
}

# A2 device/product layer — MUST mirror build_abox_patents.DEVICE_FAMILY_MAP.
# In the SIRP view a device-family patent is anchored to the REAL device:*
# ontology node (not the synthetic process:device blob), so the graph shows
# the new ont:concernsDevice linkage (plan §7.4-3).
DEVICE_FAMILY_MAP: dict[str, str] = {
    "memory": "device:dram", "memory_cell": "device:dram",
    "memory_dram": "device:dram", "backend_packaging": "device:bga",
    "packaging": "device:bga", "mems": "device:mems",
    "image_sensor": "device:cmos_image_sensor", "3d_integration": "device:tsv",
}


def _device_index() -> dict[str, dict]:
    """{device:id -> node dict} from the KG (canonical_name, category)."""
    g = json.loads((REPO / "data/semiconductor_v0_3.json").read_text(encoding="utf-8"))
    return {n["id"]: n for n in g["nodes"] if n.get("type") == "Device"}


# ── Floating toolbar (Home / Zoom + / Zoom − / Fit) ───────────────
TOOLBAR_HTML = """
<div class="sdkb-toolbar">
  <a href="index.html" class="sdkb-btn sdkb-home" title="메인 데모 페이지로 이동">← Demo Home</a>
  <button type="button" class="sdkb-btn" onclick="sdkbZoom(1.25)" title="확대">＋</button>
  <button type="button" class="sdkb-btn" onclick="sdkbZoom(0.8)" title="축소">−</button>
  <button type="button" class="sdkb-btn" onclick="sdkbFit()" title="전체 맞춤">⤢ Fit</button>
</div>
<style>
.sdkb-toolbar {
  position: fixed; top: 14px; right: 14px; z-index: 9999;
  display: flex; gap: 6px;
  background: rgba(15, 23, 42, 0.92);
  padding: 8px 10px;
  border: 1px solid #334155;
  border-radius: 8px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", sans-serif;
  box-shadow: 0 4px 16px rgba(0,0,0,0.35);
}
.sdkb-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 34px; height: 32px; padding: 0 10px;
  background: #1E293B; color: #E2E8F0; border: 1px solid #334155;
  border-radius: 6px; font-size: 14px; font-weight: 600;
  cursor: pointer; text-decoration: none; line-height: 1;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.sdkb-btn:hover { border-color: #38BDF8; background: #0F172A; color: #38BDF8; }
.sdkb-home { font-weight: 600; }
</style>
<script>
function sdkbZoom(factor) {
  try {
    if (typeof network !== 'undefined' && network) {
      var s = network.getScale();
      network.moveTo({ scale: s * factor, animation: { duration: 220, easingFunction: 'easeInOutQuad' } });
    }
  } catch (e) { console.warn('sdkbZoom failed', e); }
}
function sdkbFit() {
  try {
    if (typeof network !== 'undefined' && network) {
      network.fit({ animation: { duration: 320, easingFunction: 'easeInOutQuad' } });
    }
  } catch (e) { console.warn('sdkbFit failed', e); }
}
</script>
"""


def _inject_toolbar(out_path: Path) -> None:
    """Inject the floating Home/Zoom toolbar into a Pyvis HTML file."""
    html = out_path.read_text(encoding="utf-8")
    if "sdkb-toolbar" in html:
        return
    marker = "<body>"
    if marker not in html:
        return
    html = html.replace(marker, marker + "\n" + TOOLBAR_HTML, 1)
    out_path.write_text(html, encoding="utf-8")


# ── Pyvis helpers ─────────────────────────────────────────────────
def _new_network(height: str = "780px") -> Network:
    net = Network(
        height=height,
        width="100%",
        bgcolor="#0F172A",
        font_color="#E2E8F0",
        notebook=False,
        cdn_resources="remote",
        directed=True,
    )
    net.force_atlas_2based(
        gravity=-55,
        central_gravity=0.015,
        spring_length=130,
        spring_strength=0.04,
        damping=0.6,
    )
    net.show_buttons(filter_=["physics"])
    return net


def _node_title(label: str, ntype: str, nid: str, description: str = "") -> str:
    desc = escape(description[:240])
    return (
        f"<b>{escape(label)}</b><br/>"
        f"<i>type:</i> {escape(ntype)}<br/>"
        f"<i>id:</i> <code>{escape(nid)}</code><br/>"
        f"{desc}"
    )


def _add_legend(net: Network, types_in_use: Iterable[str]) -> None:
    """Add invisible legend nodes pinned at the top-left corner."""
    seen = []
    for t in types_in_use:
        if t in seen:
            continue
        seen.append(t)
    for i, t in enumerate(seen):
        net.add_node(
            f"__legend__{t}",
            label=t,
            shape="box",
            color=TYPE_COLORS.get(t, DEFAULT_COLOR),
            font={"color": "#0F172A", "size": 14, "face": "monospace"},
            x=-900,
            y=-450 + i * 35,
            fixed=True,
            physics=False,
        )


# ── View 1 — Baseline ─────────────────────────────────────────────
def build_baseline() -> dict:
    src = REPO / "data/semiconductor_v0_3.json"
    graph = json.loads(src.read_text(encoding="utf-8"))

    net = _new_network()
    types_seen: set[str] = set()

    for n in graph["nodes"]:
        ntype = n.get("type", "Unknown")
        types_seen.add(ntype)
        label = n.get("canonical_name") or n["id"]
        net.add_node(
            n["id"],
            label=label[:36],
            title=_node_title(label, ntype, n["id"], n.get("description", "")),
            color=TYPE_COLORS.get(ntype, DEFAULT_COLOR),
            group=ntype,
            size=18 if ntype in ("Process", "FailureMode") else 12,
        )

    for e in graph["edges"]:
        net.add_edge(
            e["src"],
            e["dst"],
            title=e["predicate"],
            label="" if e["predicate"] in {"HAS_SUBPROCESS"} else "",
            color="#475569",
            arrows="to",
        )

    # A2 device layer (plan §7.4-3): the KG has no edges for Device nodes
    # (ont:concernsDevice lives in the patent A-Box, not the core KG), so
    # without this they render as 31 floating dots. Group them under their
    # device_vocab category so the layer reads as a coherent taxonomy.
    n_dev_edges = 0
    cat_hubs: set[str] = set()
    for n in graph["nodes"]:
        if n.get("type") != "Device":
            continue
        cat = (n.get("props") or {}).get("category") or "device"
        hub = f"devcat:{cat}"
        if hub not in cat_hubs:
            cat_hubs.add(hub)
            types_seen.add("DeviceCategory")
            net.add_node(
                hub, label=f"{cat} devices",
                title=_node_title(f"{cat} device category", "A2 DeviceCategory",
                                  hub, "device_vocab category hub (Phase D)"),
                color=TYPE_COLORS["DeviceCategory"], shape="hexagon",
                size=20, group="DeviceCategory",
            )
        net.add_edge(hub, n["id"], title="hasDevice (A2)",
                     color="#0D9488", arrows="to", dashes=True)
        n_dev_edges += 1

    _add_legend(net, sorted(types_seen))
    out = OUT_DIR / "baseline.html"
    net.write_html(str(out), open_browser=False, notebook=False)
    _inject_toolbar(out)
    return {
        "view": "baseline",
        "path": str(out.relative_to(REPO)),
        "n_nodes": len(graph["nodes"]) + len(cat_hubs),
        "n_edges": len(graph["edges"]) + n_dev_edges,
        "n_device_nodes": sum(1 for n in graph["nodes"] if n.get("type") == "Device"),
        "node_types": sorted(types_seen),
    }


# ── View 2 — SIRP (Top-50 patents + examiner-cited prior art) ─────
def build_sirp(top_n: int = 50) -> dict:
    """Patent ↔ Process backbone ↔ examiner-cited prior-art subgraph.

    Each rejected patent is anchored to an ontology ``Process`` (or a
    synthetic domain hub if the baseline does not cover it), so the
    backbone reads as ``Process → Patent → PriorArt``.  The patent
    cluster aligns visually with the SDKB Process spine, instead of
    showing only direct patent ↔ prior-art links.
    """
    patents_path = REPO / "data/patents/rejected_patents_meta.parquet"
    edges_path = REPO / "data/patents/prior_art_edges.parquet"
    baseline_path = REPO / "data/semiconductor_v0_3.json"

    patents = pd.read_parquet(patents_path)
    edges = pd.read_parquet(edges_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_proc = {
        n["id"]: n for n in baseline["nodes"]
        if n.get("type") in ("Process", "SubProcess")
    }
    dev_idx = _device_index()  # A2 device:* nodes (plan §7.4-3)

    examiner_edges = edges[edges["source_type"] == "examiner"].copy()
    citation_counts = (
        examiner_edges.groupby("target_patent_id").size().reset_index(name="n_cited")
    )
    top_patents = (
        citation_counts.sort_values("n_cited", ascending=False).head(top_n)["target_patent_id"].tolist()
    )

    sub_edges = examiner_edges[examiner_edges["target_patent_id"].isin(top_patents)]
    patent_meta = patents.set_index("patent_id")

    net = _new_network()

    backbone_added: set[str] = set()
    backbone_counter: Counter = Counter()

    def _add_backbone(pid: str) -> None:
        if pid in backbone_added:
            return
        backbone_added.add(pid)
        if pid in baseline_proc:
            node = baseline_proc[pid]
            label = node.get("canonical_name") or pid
            desc = node.get("description") or ""
            badge = f"ontology Process ({node.get('type','Process')})"
        else:
            label, desc = SYNTHETIC_BACKBONE.get(pid, (pid, ""))
            badge = "domain anchor (non-baseline)"
        net.add_node(
            pid,
            label=label,
            title=_node_title(label, badge, pid, desc),
            color=TYPE_COLORS["Process"],
            shape="hexagon",
            size=32,
            font={"size": 18, "color": "#E0F2FE", "face": "monospace"},
            group="Process",
        )

    def _add_device_anchor(dev_id: str) -> None:
        if dev_id in backbone_added:
            return
        backbone_added.add(dev_id)
        n = dev_idx.get(dev_id, {})
        label = n.get("canonical_name") or dev_id
        cat = (n.get("props") or {}).get("category") or ""
        net.add_node(
            dev_id,
            label=label,
            title=_node_title(label, f"A2 Device ({cat})", dev_id,
                              n.get("description") or "device/product layer"),
            color=TYPE_COLORS["Device"], shape="box", size=30,
            font={"size": 17, "color": "#042F2E", "face": "monospace"},
            group="Device",
        )

    n_a2_edges = 0
    cited_office_counter: Counter = Counter()
    for pid in top_patents:
        if pid not in patent_meta.index:
            continue
        row = patent_meta.loc[pid]
        title = str(row.get("title", "")) or pid
        ipc = str(row.get("primary_ipc", "") or "—")
        cohort = str(row.get("cohort_scope", "") or "")
        proc_family_raw = str(row.get("process_family", "") or "").strip()
        proc_family = proc_family_raw.lower()
        dev_id = DEVICE_FAMILY_MAP.get(proc_family)  # A2: real device:* node
        backbone_id = dev_id or PROCESS_FAMILY_MAP.get(proc_family, "process:general")
        backbone_counter[backbone_id] += 1
        anchor_kind = "concernsDevice (A2)" if dev_id else "addresses_process"
        body = (
            f"IPC: {ipc} · process_family: {proc_family_raw or '—'}<br/>"
            f"anchor: <code>{escape(backbone_id)}</code> ({anchor_kind})<br/>"
            f"cohort: {cohort}"
        )
        net.add_node(
            pid,
            label=title[:34] + ("…" if len(title) > 34 else ""),
            title=_node_title(title, "Patent (rejected)", pid, body),
            color=TYPE_COLORS["Patent"],
            shape="diamond",
            size=20,
            group="Patent",
        )
        if dev_id:
            _add_device_anchor(dev_id)
            net.add_edge(pid, dev_id, title="ont:concernsDevice (A2)",
                         color="#14B8A6", arrows="to")
            n_a2_edges += 1
        else:
            _add_backbone(backbone_id)
            net.add_edge(
                backbone_id, pid,
                title="addresses_process",
                color="#94A3B8",
                arrows="to",
                dashes=True,
            )

    for _, e in sub_edges.iterrows():
        target = e["target_patent_id"]
        cited = e["cited_id"]
        office = e.get("cited_office") or "?"
        cited_office_counter[office] += 1
        if cited not in net.get_nodes():
            net.add_node(
                cited,
                label=cited.split(":")[-1][:24],
                title=_node_title(cited, f"PriorArt ({office})", cited),
                color=TYPE_COLORS["PriorArt"],
                shape="dot",
                size=8,
                group="PriorArt",
            )
        net.add_edge(target, cited, title="hasPriorArt (examiner)", color="#64748B", arrows="to")

    _add_legend(net, ["Process", "Device", "Patent", "PriorArt"])
    out = OUT_DIR / "sirp.html"
    net.write_html(str(out), open_browser=False, notebook=False)
    _inject_toolbar(out)
    return {
        "view": "sirp",
        "path": str(out.relative_to(REPO)),
        "n_patents": len(top_patents),
        "n_prior_art_edges": len(sub_edges),
        "n_backbone_anchors": len(backbone_added),
        "n_a2_device_edges": n_a2_edges,
        "backbone_breakdown": dict(backbone_counter),
        "office_breakdown": dict(cited_office_counter),
    }


# ── View 3 — 4-pillar class skeletons ─────────────────────────────
def build_pillars() -> dict:
    net = _new_network(height="820px")
    OWL = rdflib.OWL
    RDFS = rdflib.RDFS
    RDF = rdflib.namespace.RDF

    counts: dict[str, dict[str, int]] = {}
    for pillar, ttl_rel in PILLAR_TTLS.items():
        g = rdflib.Graph()
        g.parse(REPO / ttl_rel, format="turtle")
        classes = list(g.subjects(predicate=RDF.type, object=OWL.Class))
        obj_props = list(g.subjects(predicate=RDF.type, object=OWL.ObjectProperty))

        # Pillar anchor node
        anchor_id = f"pillar:{pillar}"
        net.add_node(
            anchor_id,
            label=pillar,
            color=TYPE_COLORS[pillar],
            shape="hexagon",
            size=34,
            font={"size": 22, "color": "#0F172A", "face": "monospace"},
            group=f"pillar_{pillar}",
        )

        local_names = []
        for c in classes:
            cname = str(c).rsplit("/", 1)[-1] or str(c)
            local_names.append(cname)
            label = g.value(c, RDFS.label)
            desc = str(g.value(c, RDFS.comment) or "")
            net.add_node(
                f"{pillar}:{cname}",
                label=cname,
                title=_node_title(str(label or cname), f"owl:Class ({pillar})", str(c), desc),
                color=TYPE_COLORS[pillar],
                shape="dot",
                size=14,
                group=f"pillar_{pillar}",
            )
            net.add_edge(anchor_id, f"{pillar}:{cname}", color="#475569", arrows="to")

        # subClassOf within the pillar
        for sub, _, sup in g.triples((None, RDFS.subClassOf, None)):
            sub_name = str(sub).rsplit("/", 1)[-1]
            sup_name = str(sup).rsplit("/", 1)[-1]
            sub_key = f"{pillar}:{sub_name}"
            sup_key = f"{pillar}:{sup_name}"
            if sub_key in net.get_nodes() and sup_key in net.get_nodes():
                net.add_edge(sub_key, sup_key, title="rdfs:subClassOf", color="#94A3B8", dashes=True, arrows="to")

        counts[pillar] = {
            "classes": len(classes),
            "object_properties": len(obj_props),
        }

    # Visual legend (pillar names)
    _add_legend(net, list(PILLAR_TTLS.keys()))
    out = OUT_DIR / "pillars.html"
    net.write_html(str(out), open_browser=False, notebook=False)
    _inject_toolbar(out)
    return {
        "view": "pillars",
        "path": str(out.relative_to(REPO)),
        "pillar_counts": counts,
    }


# ── View 4 — §5 measured-results dashboard ────────────────────────
def _load_report(name: str) -> dict | None:
    p = REPO / "data" / "reports" / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_metrics() -> dict:
    """Static dashboard of the measured Phase 1–4 results (plan §8).

    Reads the committed data/reports/*.json. Defensive: any missing report
    degrades to an 'N/A' note so CI (which does not run the eval scripts)
    never breaks.
    """
    rg = _load_report("prior_art_realgt_report.json")
    ep = _load_report("explanation_precision_report.json")
    ab = _load_report("abox_patents_linking_report.json")
    ft = _load_report("fulltext_corpus_report.json")

    def cell(x):
        return "—" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))

    if rg and rg.get("ranker_summary"):
        rs = rg["ranker_summary"]
        rows = "".join(
            f"<tr><td><code>{m}</code></td><td>{cell(rs[m]['MRR'])}</td>"
            f"<td>{cell(rs[m]['NDCG@5'])}</td><td>{cell(rs[m]['Recall@10'])}</td>"
            f"<td>{cell(rs[m]['Recall@50'])}</td></tr>"
            for m in ("tfidf", "onto", "onto_idf", "hybrid") if m in rs
        )
        s51 = (f"<p class='note'>corpus(content)={cell(rg.get('corpus_content_docs'))} · "
               f"evaluable targets={cell(rg.get('evaluable_targets'))} · "
               f"real examiner GT (IPC-4 프록시 아님)</p>"
               "<table><thead><tr><th>ranker</th><th>MRR</th><th>NDCG@5</th>"
               "<th>R@10</th><th>R@50</th></tr></thead><tbody>"
               f"{rows}</tbody></table>")
    else:
        s51 = "<p class='na'>N/A — run <code>scripts/eval_prior_art_realgt.py</code></p>"

    if rg and rg.get("incremental_recall_sec5_2"):
        ir = rg["incremental_recall_sec5_2"]
        tf, hy = ir["Recall@50_tfidf"], ir["Recall@50_hybrid"]
        dl, npos = ir["delta_hybrid_minus_tfidf"], ir["gt_positives_in_corpus"]
        s52 = ("<table><thead><tr><th>인용</th><th>tfidf R@50</th>"
               "<th>hybrid R@50</th><th>Δ (hybrid−tfidf)</th><th>n_pos</th></tr>"
               "</thead><tbody>"
               + "".join(
                   f"<tr><td>{b}</td><td>{cell(tf[b])}</td><td>{cell(hy[b])}</td>"
                   f"<td class='{'pos' if dl[b]>=0 else 'neg'}'>{dl[b]:+.4f}</td>"
                   f"<td>{cell(npos[b])}</td></tr>" for b in ("KR", "FOREIGN"))
               + "</tbody></table>"
               "<p class='note'>FOREIGN(JP/US…) = 어휘 비유사 — 도메인 온톨로지 본질 가치 축. "
               "외국 인용에서 Δ&gt;0 = §5(2) 보완성 입증.</p>")
    else:
        s52 = "<p class='na'>N/A</p>"

    if ep:
        lb = ep.get("coverage_by_legal_basis", {})
        lbrows = "".join(
            f"<tr><td>{k}</td><td>{v['explained']}/{v['total']}</td>"
            f"<td>{cell(v['rate'])}</td></tr>" for k, v in lb.items())
        s54 = (f"<p class='note'>pilot {cell(ep.get('evidence_v2_mappings_total'))} map / "
               f"{cell(ep.get('evidence_v2_records_total'))} rec · "
               f"corpus 내 {cell(ep.get('pairs_with_cited_in_content_corpus'))} pair</p>"
               f"<p>explanation coverage = <strong>{cell(ep.get('explanation_coverage'))}</strong> "
               f"(권고 {cell(ep.get('explanation_threshold'))} → "
               f"{'충족' if ep.get('meets_threshold') else '미달'})</p>"
               "<table><thead><tr><th>legal_basis</th><th>explained</th>"
               f"<th>rate</th></tr></thead><tbody>{lbrows}</tbody></table>")
    else:
        s54 = "<p class='na'>N/A — run <code>scripts/eval_explanation_precision.py</code></p>"

    if ab:
        osp = ab.get("orphans_split", {})
        lp = ab.get("link_provenance", {})
        s_a2 = (f"<ul><li>patents linked: <strong>{cell(ab.get('patents_with_ontology_link'))}"
                f"/{cell(ab.get('patents'))}</strong></li>"
                f"<li>orphan scope_out: <strong>{cell(osp.get('scope_out'))}</strong> "
                f"· text_miss: {cell(osp.get('text_miss'))}</li>"
                f"<li>A2 structured device bridge: <strong>{cell(lp.get('structured_device_family'))}</strong> patents</li>"
                f"<li>nodes/patent mean: {cell((ab.get('nodes_per_patent') or {}).get('mean'))}</li></ul>")
    else:
        s_a2 = "<p class='na'>N/A — run <code>make abox-patents</code></p>"
    if ft:
        s_ft = (f"<p>fulltext corpus: <strong>{cell(ft.get('n_with_content'))}</strong> content "
                f"/ {cell(ft.get('n_stub'))} stub ({cell(ft.get('content_rate'))}) "
                f"— stub 필터 적용(§7.3-2)</p>")
    else:
        s_ft = ""

    page = (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<title>SDKB — §5 측정 결과</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>"
        "body{margin:0;background:#0F172A;color:#E2E8F0;"
        "font-family:-apple-system,'Segoe UI','Noto Sans KR',sans-serif;line-height:1.55}"
        "main{max-width:1000px;margin:0 auto;padding:32px}"
        "h1{font-size:26px;margin:0 0 4px}h2{color:#38BDF8;font-size:14px;"
        "letter-spacing:.08em;text-transform:uppercase;margin:32px 0 10px}"
        "table{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px}"
        "th,td{border:1px solid #334155;padding:7px 10px;text-align:right}"
        "th{background:#1E293B;color:#94A3B8}td:first-child,th:first-child{text-align:left}"
        ".note{color:#94A3B8;font-size:13px}.na{color:#F59E0B;font-size:13px}"
        ".pos{color:#34D399}.neg{color:#F87171}code{background:#0B1220;padding:1px 6px;"
        "border-radius:3px}a{color:#38BDF8}.sub{color:#94A3B8;font-size:13px}"
        "</style></head><body><main>"
        "<a href='index.html'>← Demo Home</a>"
        "<h1>§5 4축 측정 결과 — 실 examiner-GT (Phase 1–4)</h1>"
        "<p class='sub'>plan §8 / 2026-05-17. IPC-4 프록시가 아닌 실제 인용 코퍼스 기반 첫 측정.</p>"
        f"<h2>§5(1) 검색력 (실 examiner GT)</h2>{s51}"
        f"<h2>§5(2) 보완성 — incremental recall (핵심)</h2>{s52}"
        f"<h2>§5(3) A2 스코프 커버리지</h2>{s_a2}{s_ft}"
        f"<h2>§5(4) 설명 정밀도 (파일럿)</h2>{s54}"
        "<p class='note'>온톨로지 단독은 floor 미추월(계획이 예견한 정직한 결과). "
        "핵심 성과 = §5(2) 외국 인용 보완성 입증 + 4축이 처음으로 동시 측정 가능.</p>"
        "</main></body></html>"
    )
    out = OUT_DIR / "metrics.html"
    out.write_text(page, encoding="utf-8")
    have = [n for n, r in (("realgt", rg), ("explanation", ep),
                           ("abox", ab), ("fulltext", ft)) if r]
    return {"view": "metrics", "path": str(out.relative_to(REPO)),
            "reports_present": have}


# ── Landing page ──────────────────────────────────────────────────
LANDING_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>SDKB — Interactive Graph Demo · Quantitative Technology Management Lab</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {{
    --bg: #0F172A; --panel: #1E293B; --ink: #E2E8F0; --muted: #94A3B8;
    --accent: #38BDF8; --border: #334155;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", sans-serif;
    line-height: 1.55;
  }}
  header {{
    padding: 48px 32px 32px; max-width: 1100px; margin: 0 auto;
    border-bottom: 1px solid var(--border);
  }}
  header .tag {{
    display: inline-block; padding: 4px 10px; border-radius: 4px;
    background: #1E40AF; color: #E0F2FE; font-size: 13px; font-weight: 600;
    letter-spacing: 0.04em;
  }}
  header h1 {{ font-size: 32px; margin: 12px 0 8px; line-height: 1.25; }}
  header p.sub {{ color: var(--muted); margin: 4px 0; font-size: 15px; }}
  main {{ padding: 24px 32px 48px; max-width: 1100px; margin: 0 auto; }}
  section h2 {{
    font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--accent); margin: 32px 0 12px;
  }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
  .card {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; text-decoration: none; color: inherit; transition: border-color 0.15s ease;
  }}
  .card:hover {{ border-color: var(--accent); }}
  .card h3 {{ margin: 0 0 8px; font-size: 17px; }}
  .card p {{ margin: 0; color: var(--muted); font-size: 14px; }}
  .card .meta {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; color: var(--accent); margin-top: 12px; }}
  ul.lab {{ margin: 12px 0; padding-left: 18px; color: var(--muted); }}
  ul.lab li {{ margin-bottom: 6px; }}
  footer {{ padding: 24px 32px; max-width: 1100px; margin: 0 auto; color: var(--muted); font-size: 13px; border-top: 1px solid var(--border); }}
  a {{ color: var(--accent); }}
  code {{ background: #0B1220; padding: 1px 6px; border-radius: 3px; }}
</style>
</head>
<body>
<header>
  <span class="tag">Quantitative Technology Management Lab · SKKU MOT</span>
  <h1>SDKB — Interactive Knowledge Graph Demo</h1>
  <p class="sub">계량기술경영 연구실(지도: 신준석 교수)의 어젠다 중 <strong>반도체 도메인 데이터 트렁크</strong>를 인터랙티브하게 탐색합니다.</p>
  <p class="sub">Hyeonup-Project 2026-1 / Park HyoungSik (Ph.D. 19기) · <a href="https://github.com/arkwith7/semiconductor-knowledge-base">GitHub 소스</a></p>
</header>

<main>
  <section>
    <h2>연구실 어젠다 내 본 데모의 위치</h2>
    <ul class="lab">
      <li>특허·시장·산업 데이터 기반 <strong>기술예측</strong> ↔ SIRP 773 + sdkb-patent</li>
      <li><strong>유망기술 기회 발굴</strong> ↔ Novelty-focused patent 매핑 (후속)</li>
      <li><strong>중소기업 혁신 / 전문가 매칭</strong> ↔ SDKB-Match Expert (notebook 01)</li>
      <li><strong>인터랙티브 기술·비즈니스 데이터 시각화</strong> ↔ <em>본 페이지</em></li>
    </ul>
  </section>

  <section>
    <h2>인터랙티브 뷰</h2>
    <div class="grid">
      <a class="card" href="baseline.html">
        <h3>① Baseline Core Ontology + A2 Device</h3>
        <p>공정·장비·재료·결함·계측 코어 + <strong>A2 device/product 계층 31노드</strong>(plan §7.4-3)를 device_vocab 카테고리 허브로 묶어 표시. 노드 타입별 컬러 + 호버 툴팁.</p>
        <div class="meta">{baseline_meta}</div>
      </a>
      <a class="card" href="sirp.html">
        <h3>② SIRP Patent ↔ Prior Art (+A2)</h3>
        <p>1000 거절특허 중 <strong>상위 50건과 examiner-cited 선행기술</strong> 서브그래프. Process 백본 + device-family 특허는 실 <strong><code>device:*</code> 노드에 ont:concernsDevice</strong>로 연결(합성 blob 대체). 다국 office 비율 동시 확인.</p>
        <div class="meta">{sirp_meta}</div>
      </a>
      <a class="card" href="pillars.html">
        <h3>③ 4-Pillar Class Skeletons</h3>
        <p>신준석 교수님 연구라인에 정렬된 네 모듈 — <strong>patent / rbv / commercialization / foresight</strong> — 의 owl:Class · subClassOf 골격. 모듈 간 상대 규모를 한 눈에.</p>
        <div class="meta">{pillars_meta}</div>
      </a>
      <a class="card" href="metrics.html">
        <h3>④ §5 측정 결과 대시보드</h3>
        <p>실 examiner-GT 기반 <strong>§5(1) 검색력 · §5(2) 보완성(KR vs 외국) · §5(3) A2 커버리지 · §5(4) 설명정밀도</strong>. IPC-4 프록시 아닌 실 인용 코퍼스 첫 측정 (plan §8).</p>
        <div class="meta">{metrics_meta}</div>
      </a>
    </div>
  </section>

  <section>
    <h2>주석</h2>
    <p style="color: var(--muted); font-size: 14px;">
      본 페이지는 <code>make viz</code> → <code>scripts/build_viz.py</code> 로 빌드되며, <code>main</code>에 푸시가 발생하면
      <code>.github/workflows/viz-deploy.yml</code>이 GitHub Pages로 자동 배포합니다. 시맨틱 협업 플랫폼 비전의
      후속 시각화(SHACL 게이트·매칭 익스플로러·Novelty patent map)는 2026-2 학기에 추가됩니다.
    </p>
  </section>
</main>

<footer>
  Built with <a href="https://pyvis.readthedocs.io/">Pyvis</a> · vis.js · rdflib · pandas. CDLA-Permissive-2.0.
</footer>
</body>
</html>
"""


def build_index(baseline_info: dict, sirp_info: dict, pillars_info: dict,
                 metrics_info: dict) -> Path:
    baseline_meta = (
        f"{baseline_info['n_nodes']} nodes · {baseline_info['n_edges']} edges · "
        f"{len(baseline_info['node_types'])} types · "
        f"A2 device {baseline_info.get('n_device_nodes', 0)}"
    )
    sirp_meta = (
        f"{sirp_info['n_patents']} patents · {sirp_info['n_backbone_anchors']} anchors · "
        f"A2 concernsDevice {sirp_info.get('n_a2_device_edges', 0)} · "
        f"{sirp_info['n_prior_art_edges']} prior-art edges · "
        + " / ".join(f"{k}:{v}" for k, v in sorted(sirp_info["office_breakdown"].items()))
    )
    pillar_pieces = [
        f"{p}:{c['classes']}cls/{c['object_properties']}op"
        for p, c in pillars_info["pillar_counts"].items()
    ]
    pillars_meta = " · ".join(pillar_pieces)
    rp = metrics_info.get("reports_present", [])
    metrics_meta = ("reports: " + ("/".join(rp) if rp else "none — run eval scripts"))
    html = LANDING_TEMPLATE.format(
        baseline_meta=baseline_meta,
        sirp_meta=sirp_meta,
        pillars_meta=pillars_meta,
        metrics_meta=metrics_meta,
    )
    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / ".nojekyll").write_text("")
    print(f"[viz] output → {OUT_DIR}")

    baseline_info = build_baseline()
    print(f"[viz] ✓ baseline: {baseline_info['n_nodes']} nodes / {baseline_info['n_edges']} edges")

    sirp_info = build_sirp()
    print(f"[viz] ✓ sirp: {sirp_info['n_patents']} patents / {sirp_info['n_prior_art_edges']} edges")

    pillars_info = build_pillars()
    print(f"[viz] ✓ pillars: " + ", ".join(
        f"{p} {c['classes']}cls" for p, c in pillars_info["pillar_counts"].items()
    ))

    metrics_info = build_metrics()
    print(f"[viz] ✓ metrics: reports={metrics_info['reports_present'] or 'none'}")

    build_index(baseline_info, sirp_info, pillars_info, metrics_info)
    print(f"[viz] ✓ index.html written")
    print(f"[viz] open: file://{OUT_DIR}/index.html")


if __name__ == "__main__":
    main()
