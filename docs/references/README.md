# References

Bibliographic references for SDKB-related work, collected as the seed
for an eventual **dataset paper** on SDKB v1.0 and AFCP-EM.

## Single source of truth

[`references.bib`](references.bib) is the canonical BibTeX file —
every cited work (current and future) gets one entry there.
Per-paper Markdown notes live next to the (optional) PDF in the
relevant subdirectory.

## Policy on PDFs

This is a **public** repository, so we commit PDFs only when the
license permits redistribution.

- ✅ **Commit OK**: arXiv preprints, CC-BY journals (PLoS ONE, IEEE Access OA, Scientific Data), CEUR-WS proceedings, author-accepted manuscripts (after publisher policy check)
- ⚠️ **Link only**: closed-access journals (Elsevier TFSC, ACM, Springer); store DOI / URL and read via institutional Zotero / Mendeley
- Each `.md` note declares `oa: true|false` and `local_pdf: <name>|none`

**Default safety net** — the repo-root [`.gitignore`](../../.gitignore) blanket-ignores `*.pdf`,
so no PDF lands in a commit by accident. To commit an explicitly OA PDF, use:

```bash
git add -f docs/references/<subdir>/<bibkey>.pdf
```

## Layout

| Subdirectory | Scope |
|---|---|
| [`lab-shin/`](lab-shin/) | Prof. Juneseuk Shin and collaborators — anchor references for the lab agenda |
| [`kg-ontology/`](kg-ontology/) | Semiconductor / materials knowledge graphs and ontologies (SemiKong, SemicONTO, MatKG, …) |
| [`prior-art-matching/`](prior-art-matching/) | Patent ↔ prior-art retrieval (PatentMatch, CLEF-IP, BERT-PLI, …) |
| [`expert-matching/`](expert-matching/) | SME ↔ expert / talent / reviewer matching literature |
| [`methodology/`](methodology/) | PROV-O, SHACL, Gebru datasheet, FAIR principles, OWL design |
| [`compliance/`](compliance/) | BIS EAR / NIST IR 8546 / ECHA SCIP / 한국 산업기술보호법 — primary regulatory sources |

Subdirectories are seeded with a `README.md` describing scope and any
already-collected entries.

## BibTeX key convention

`{firstauthor}_{year}_{venue}` (lowercase, underscores). Examples:

- `shin_2015_tfsc`
- `cho_shin_2025_plosone` _(first + senior author, when helpful)_
- `semikong_2024_arxiv`

Multi-author conference papers may use a short project / dataset name
as the key (`semikong_2024_arxiv`, `matkg_2024_scidata`).

## Adding a reference

1. Append a BibTeX entry to [`references.bib`](references.bib) using the key convention
2. Copy [`_template.md`](_template.md) → `{subdir}/{bibkey}.md` and fill in
3. If OA: download PDF, save as `{subdir}/{bibkey}.pdf`, commit with `git add -f`
4. If non-OA: keep `local_pdf: none`, store your copy in Zotero locally
5. Update the parent [README.md](../../README.md) if the citation appears in a user-facing section

## Status

Seed entries (referenced in the top-level [README.md](../../README.md))
have been scaffolded with `TODO_VERIFY` markers where bibliographic
details still need confirmation against the actual papers.
