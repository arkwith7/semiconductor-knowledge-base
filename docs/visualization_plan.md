# SDKB Interactive Visualization — Plan & Operations

> **Status (2026-05-12):** Phase 1 (baseline 3-view) shipped this semester.
> **Lab agenda anchor:** Quantitative Technology Management Lab — research area ④ *Interactive technology & business data visualization*.
> **Live URL:** [https://arkwith7.github.io/semiconductor-knowledge-base/](https://arkwith7.github.io/semiconductor-knowledge-base/)

This document describes how the SDKB interactive visualization site is built, deployed, and extended. It serves as the operational reference for `scripts/build_viz.py` + `.github/workflows/viz-deploy.yml`.

---

## 1. Why this exists

The project plan deliverables (① ontology, ② experts, ③ problems/scenarios, ④ ratings, ⑤ commercialization) are evaluated as data assets and tables. Without a visual surface, the *graph nature* of the SDKB — and the four-pillar alignment with the lab's research agenda — is invisible to readers who do not run notebooks. A static, browser-accessible demo closes that gap and, more importantly, instantiates the lab's research-area ④ on top of areas ①–③.

## 2. What is published (Phase 1, this semester)

| # | View | Source | Output | Counts |
|---|---|---|---|---|
| ① | Baseline core ontology | `data/semiconductor_v0_3.json` | `site/baseline.html` | 198 nodes · 268 edges · 14 types |
| ② | SIRP patent ↔ examiner-cited prior art (top-50 by citation count) | `data/patents/rejected_patents_meta.parquet` + `prior_art_edges.parquet` | `site/sirp.html` | 50 patents · ~290 prior-art edges · KR/US/JP/EP breakdown |
| ③ | 4-pillar class skeletons (patent / rbv / commercialization / foresight) | `ontology/sdkb-{patent,rbv,commercialization,foresight}.ttl` | `site/pillars.html` | ~34 owl:Class total · subClassOf edges |
| ⓘ | Landing page with lab-agenda context | (composed in `build_viz.py`) | `site/index.html` | dark theme, links to ①②③ |

Stack: **Pyvis** (vis.js wrapper) + **rdflib** (TTL parsing) + **pandas** (parquet ingest). No server, no database — purely static HTML.

## 3. Build pipeline

```bash
make viz        # → site/{index,baseline,sirp,pillars}.html  + site/.nojekyll
make viz-open   # build + open in default browser
make viz-clean  # rm -rf site/
```

The script `scripts/build_viz.py` is also exposed as a console entry point: `sdkb-build-viz`.

Implementation notes:
- Output goes to `site/` at repo root. This path is `.gitignore`d — main never contains build artifacts.
- A `site/.nojekyll` file is written so GitHub Pages serves the HTML files without Jekyll processing.
- Color palette is centralised in `TYPE_COLORS` for visual consistency across the three views.
- Each view uses Pyvis `force_atlas_2based` layout + `show_buttons(filter_=["physics"])` so the reader can toggle physics simulation interactively.
- A pinned legend (top-left, `physics=False`) shows the node-type colour key on every view.

## 4. Deployment — GitHub Pages via Actions

Workflow file: `.github/workflows/viz-deploy.yml`.

**Trigger:** push to `main` touching any of —
- `data/semiconductor_v0_3.json`
- `data/patents/raw/**`
- `ontology/sdkb-*.ttl`
- `scripts/build_viz.py`
- `pyproject.toml`
- the workflow file itself

Also `workflow_dispatch` for manual rebuilds.

**Job graph:**
1. **build** — checkout → setup-python 3.11 → `pip install -e ".[viz]"` → `make parse && make ingest-sirp && make sirp-pairs` (regenerate parquet from source) → `make viz` → `actions/upload-pages-artifact@v3` with `path: site/`.
2. **deploy** — `actions/deploy-pages@v4` publishes the artifact to GitHub Pages.

Permissions: `contents: read`, `pages: write`, `id-token: write`. Concurrency group `pages` with no cancel-in-progress so deploys queue safely.

### 4.1 One-time repo setup

GitHub Pages must be enabled with **GitHub Actions** as the source (not "Deploy from a branch"):

1. Repo → **Settings** → **Pages**
2. **Source:** *GitHub Actions*
3. Save. On the next push to `main`, the `Build & Deploy Visualization Site` workflow will run and publish to `https://arkwith7.github.io/semiconductor-knowledge-base/`.

No `gh-pages` branch is needed — the modern `deploy-pages` action ships artifacts directly to the Pages CDN, keeping the repository free of build clutter.

### 4.2 Where to find the deployed URL

After the first successful run, GitHub Settings → Pages will show the live URL. The workflow's `deploy` job also exposes it as `${{ steps.deployment.outputs.page_url }}` so subsequent runs report the URL in the Actions UI.

## 5. Data sensitivity policy

Only **already-public** content is exported into the static site:
- Baseline ontology (CDLA-Permissive-2.0)
- SIRP patent metadata (publicly accessible via KIPRIS — see `docs/dataset_rejected_patents_card.md`)
- Four-pillar ontology classes (CDLA-Permissive-2.0)

Excluded from the static site **by construction**:
- KR/US governance instance triples (linked-only in §5 of README)
- Curated expert profiles and ratings (kept inside parquet, never node-tooltipped)
- Compliance scenarios with adversarial content

If a future view introduces governance or expert nodes, gate them through a whitelist in `build_viz.py` and re-review this section.

## 6. Phase 2 extension plan (2026-2)

Each Phase-2 view maps to a specific lab research area. Phase 1 stays as-is; Phase 2 additions live in the same `site/` output via new `build_<view>()` functions.

| Lab area | Phase-2 view | Adds | Notes |
|---|---|---|---|
| ① Tech foresight | `novelty_map.html` — Novelty-focused patent landscape (Lee/Kang/Shin 2015) | Plotly scatter + Pyvis subgraph drill-down | needs patent abstract enrichment (`docs/patent_abstract_enrichment_plan.md`) |
| ② Opportunity discovery | `emerging_topics.html` — Topic-model emerging-tech clusters | Plotly + LDA outputs | needs `make topics` target |
| ③ SME-expert matching | `matching_explorer.html` — query → ranked experts + SHACL gate trace | Streamlit (external host on HF Spaces) | linked-from, not embedded |
| ② / ③ | `governance_gate.html` — SHACL conformance trace per matching | Pyvis + SHACL `sh:resultMessage` | requires compliance allowlist review |
| ④/RBV | `resource_combo.html` — fsQCA resource bundles for fabless market entry | Plotly parallel-categories | needs `firms.parquet` populated |
| ④/valuation | `real_option_tree.html` — EUV vs High-NA decision tree | Plotly/D3 | optional, depends on foresight instances |

Phase 2 is scoped to additive views only — Phase 1 views remain stable so the URL set in README/CITATION continues to resolve.

## 7. Maintenance checklist

When updating the baseline ontology, SIRP parquet, or 4-pillar TTLs:

1. Confirm `make viz` runs clean locally (no Python errors, all three HTML files written).
2. Eyeball each view in a browser (`make viz-open`). Watch for orphaned legend nodes or unstyled types — both indicate a new node type that needs a colour entry in `TYPE_COLORS`.
3. Push to `main`. The workflow fires automatically; check the Actions tab for green.
4. Open the deployed URL and verify the three cards on `index.html` show the correct counts.

When the structure changes (new view, new tooltip field, etc.), update §2 of this document and the cards in `LANDING_TEMPLATE`.
