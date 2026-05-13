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

    _add_legend(net, sorted(types_seen))
    out = OUT_DIR / "baseline.html"
    net.write_html(str(out), open_browser=False, notebook=False)
    _inject_toolbar(out)
    return {
        "view": "baseline",
        "path": str(out.relative_to(REPO)),
        "n_nodes": len(graph["nodes"]),
        "n_edges": len(graph["edges"]),
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
        backbone_id = PROCESS_FAMILY_MAP.get(proc_family, "process:general")
        backbone_counter[backbone_id] += 1
        body = (
            f"IPC: {ipc} · process_family: {proc_family_raw or '—'}<br/>"
            f"backbone: <code>{escape(backbone_id)}</code><br/>"
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

    _add_legend(net, ["Process", "Patent", "PriorArt"])
    out = OUT_DIR / "sirp.html"
    net.write_html(str(out), open_browser=False, notebook=False)
    _inject_toolbar(out)
    return {
        "view": "sirp",
        "path": str(out.relative_to(REPO)),
        "n_patents": len(top_patents),
        "n_prior_art_edges": len(sub_edges),
        "n_backbone_anchors": len(backbone_added),
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
      <li><strong>중소기업 혁신 / 전문가 매칭</strong> ↔ AFCP-EM Expert (notebook 01)</li>
      <li><strong>인터랙티브 기술·비즈니스 데이터 시각화</strong> ↔ <em>본 페이지</em></li>
    </ul>
  </section>

  <section>
    <h2>인터랙티브 뷰</h2>
    <div class="grid">
      <a class="card" href="baseline.html">
        <h3>① Baseline Core Ontology</h3>
        <p>공정·장비·재료·결함·계측 등 <strong>14 코어 타입 · 198 노드 / 268 엣지</strong>의 SDKB 베이스라인. 노드 타입별 컬러 + 호버 툴팁 + 물리 시뮬레이션 ON/OFF.</p>
        <div class="meta">{baseline_meta}</div>
      </a>
      <a class="card" href="sirp.html">
        <h3>② SIRP Patent ↔ Prior Art</h3>
        <p>SIRP 773 거절특허 중 <strong>상위 50건과 examiner-cited 선행기술</strong> 서브그래프. <strong>온톨로지 Process 백본</strong>(Lithography / Etch / Deposition …)을 따라 특허와 선행기술이 연결되어 다국 office(KR/US/JP/EP) 비율을 한 화면에서 확인.</p>
        <div class="meta">{sirp_meta}</div>
      </a>
      <a class="card" href="pillars.html">
        <h3>③ 4-Pillar Class Skeletons</h3>
        <p>신준석 교수님 연구라인에 정렬된 네 모듈 — <strong>patent / rbv / commercialization / foresight</strong> — 의 owl:Class · subClassOf 골격. 모듈 간 상대 규모를 한 눈에.</p>
        <div class="meta">{pillars_meta}</div>
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


def build_index(baseline_info: dict, sirp_info: dict, pillars_info: dict) -> Path:
    baseline_meta = f"{baseline_info['n_nodes']} nodes · {baseline_info['n_edges']} edges · {len(baseline_info['node_types'])} types"
    sirp_meta = (
        f"{sirp_info['n_patents']} patents · {sirp_info['n_backbone_anchors']} process anchors · "
        f"{sirp_info['n_prior_art_edges']} prior-art edges · "
        + " / ".join(f"{k}:{v}" for k, v in sorted(sirp_info["office_breakdown"].items()))
    )
    pillar_pieces = [
        f"{p}:{c['classes']}cls/{c['object_properties']}op"
        for p, c in pillars_info["pillar_counts"].items()
    ]
    pillars_meta = " · ".join(pillar_pieces)
    html = LANDING_TEMPLATE.format(
        baseline_meta=baseline_meta,
        sirp_meta=sirp_meta,
        pillars_meta=pillars_meta,
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

    build_index(baseline_info, sirp_info, pillars_info)
    print(f"[viz] ✓ index.html written")
    print(f"[viz] open: file://{OUT_DIR}/index.html")


if __name__ == "__main__":
    main()
