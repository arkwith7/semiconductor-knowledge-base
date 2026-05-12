# Semiconductor domain ontologies for knowledge base provenance

**Seven publicly downloadable, clearly licensed sources can ground a semiconductor domain knowledge base (SDKB) today — but no single resource covers the full manufacturing domain.** The strongest foundations are MatKG (70K+ materials entities, CC BY 4.0), the BIS Commerce Control List (machine-readable via eCFR API, public domain), and SemicONTO (OWL ontology, CC BY 4.0). A critical gap persists: no publicly available, machine-readable ontology comprehensively covers semiconductor manufacturing process steps with downloadable structured data. SemiKong describes the most complete process taxonomy but has not released it as a downloadable file. Building an SDKB will require stitching together multiple partial sources across materials, processes, equipment, failure modes, and regulatory classifications.

---

## Actually downloadable sources with clear licenses

The table below summarizes every source investigated, ranked by practical accessibility — the combination of being genuinely downloadable, having a clear license, and containing structured data.

| Source | License | Format | Entities | Domain Coverage | Downloadable? |
|--------|---------|--------|----------|-----------------|---------------|
| **MatKG** | CC BY 4.0 | CSV, RDF/N-Triples | 70K–150K entities, 3.5–5.4M triples | Materials, properties, synthesis methods | ✅ Zenodo |
| **BIS CCL (ECCN)** | Public domain | XML/JSON via API | ~30 semiconductor ECCNs, hundreds of sub-items | Equipment, materials, technology controls | ✅ eCFR API |
| **SemicONTO** | CC BY 4.0 | Turtle (.ttl), OWL | ~12 classes, ~16 properties | Semiconductor experiments, equipment, doping | ✅ GitHub |
| **Digital Reference (tibonto/dr)** | Apache 2.0 | Turtle (.ttl), OWL | Multiple sub-ontologies | Supply chain, manufacturing, CO₂, planning | ✅ GitHub |
| **Wikidata** | CC0 | RDF, JSON-LD, SPARQL | ~100+ semiconductor Q-items | Process nodes, companies, equipment types | ✅ SPARQL/dumps |
| **MDO** | CC BY 4.0 | OWL/Turtle | ~50+ classes | Materials structure, composition, properties | ✅ GitHub |
| **NIST IOF Core** | Public domain | OWL | ~20 core terms + extensions | General manufacturing, supply chains | ✅ NIST/GitHub |
| **SemiKong** | Apache 2.0 (LICENSE file) | Text in paper only | 10 L1, est. 50–100 L2/L3 categories | Full fab process taxonomy (FEOL+BEOL) | ⚠️ Not as structured file |
| **IRDS/ITRS** | © IEEE, free with attribution | PDF | ~15 chapters, dozens of parameter tables | Device scaling, lithography, metrology | ⚠️ PDF only |
| **JEDEC JEP122H** | Free with registration | PDF | ~15 failure mechanisms | Reliability failure modes, activation energies | ⚠️ PDF, requires account |
| **Korea NCTs** | Government notice | PDF/web | 11 semiconductor technologies | DRAM, NAND, foundry, CIS, packaging | ⚠️ Korean, English summaries |
| **SEMI Standards** | Proprietary | PDF | Hundreds of definitions | Equipment states, GEM, process management | ❌ Paywalled ($150–380) |
| **FMEA KGs** | Code MIT; data proprietary | Neo4j/CSV schema | Unknown | Failure mode–cause–effect triples | ❌ Data not released |

---

## SemiKong offers the best process taxonomy — but only on paper

SemiKong (arXiv:2411.13802) provides the most comprehensive semiconductor manufacturing process taxonomy identified in this research. Developed by Aitomatic in collaboration with Tokyo Electron, it defines **10 L1 categories** spanning the full fabrication flow: Substrate Preparation, Film Formation (deposition), Patterning (lithography + etching), Doping (ion implantation), Planarization (CMP), Cleaning and Surface Preparation, Thermal Processing, Metrology and Inspection, Advanced Modules, and Back-End Processes. Each L1 branches into L2 and L3 subcategories — for example, Patterning → Etching → Wet Etching, Dry Etching, Plasma Etching, Reactive Ion Etching, Deep Reactive Ion Etching, Atomic Layer Etching.

**The critical limitation is accessibility.** The GitHub repository (github.com/aitomatic/semikong, 389 stars) contains model code and benchmarking scripts but the `ontology/` directory referenced in the README does not appear to contain downloadable structured data files. The taxonomy is described textually in Appendix A of the paper. The LICENSE file specifies **Apache 2.0**, though the README contradictorily claims MIT. For SDKB provenance, one could manually extract the taxonomy from the paper, but there is no OWL, JSON, or CSV file to ingest programmatically. The associated LLM models (8B and 70B) are available on HuggingFace.

---

## MatKG and SemicONTO are the strongest downloadable foundations

**MatKG** (Scientific Data 2024, DOI: 10.1038/s41597-024-03039-z) is the single richest downloadable resource. Hosted on Zenodo at `zenodo.org/records/10144972`, it provides **over 70,000 entities and 5.4 million unique triples** extracted from ~5 million materials science paper abstracts. The data comes in both CSV (`SUBRELOBJ.csv`, 184 MB) and RDF N-Triples formats (~2.8 GB compressed). Seven entity types are defined: Material (CHM), Property (PRO), Application (APL), Synthesis Method (SYN), Characterization Method (CMT), Descriptor (DSC), and Symmetry/Phase Label (SPL). While not semiconductor-specific, it covers semiconductor materials extensively — the paper demonstrates CdTe, TiO₂, and bismuth telluride, and the corpus naturally includes silicon, GaAs, SiC, GaN, and InP with their associated properties and synthesis routes. MatKG captures material-property, material-application, and material-synthesis relationships that directly map to SDKB material nodes. The dataset has logged **4,149 downloads** confirming active community use.

**SemicONTO** (CEUR-WS Vol-3760, github.com/huanyu-li/SemicONTO) is the only purpose-built semiconductor OWL ontology that is both downloadable and clearly licensed. Version 0.1 defines **~12 classes** including Semiconductor, ExtrinsicSemiconductor, IntrinsicSemiconductor, Experiment, ExperimentStep, Equipment, Material, and DopingRelation, with ~10 object properties (hasStep, hasSubStep, hasEquipment, hasNextStep) and ~6 datatype properties. It reuses **PROV-O** for provenance and the **Materials Design Ontology (MDO)** for structure/composition. A live SPARQL endpoint exists at `huanyu-li.github.io/SemicONTO/demo/`, and the Turtle file is at `ontology/0.1/SemicONTO.ttl`. The ontology is small but well-structured, covering experimental workflows and equipment relationships rather than manufacturing process types. Its persistent URI is `w3id.org/SemicONTO`.

---

## BIS export controls provide the most granular equipment taxonomy

The **Commerce Control List** (15 CFR Part 774) is a surprisingly powerful provenance source for semiconductor equipment and materials classification. It is **fully public** (U.S. government work, no copyright), **machine-readable** via the eCFR REST API (`ecfr.federalregister.gov/developers/documentation/api/v1`, no API key required), and available as bulk XML from the Government Publishing Office.

ECCN **3B001** alone contains **17+ major subparagraphs** (a through q) classifying semiconductor manufacturing equipment with extraordinary specificity: epitaxial growth equipment (3B001.a), ion implantation equipment (3B001.b), dry etching equipment including anisotropic plasma etch and GAAFET-specific isotropic etch (3B001.c), deposition equipment covering CVD/PVD/ALD for cobalt and tungsten fill (3B001.d), lithography equipment with overlay and resolution thresholds (3B001.f), EUV mask substrates and pellicles (3B001.j-m), annealing equipment (3B001.o), and advanced packaging equipment (3B001.q). Materials are classified under **3C001–3C006** (hetero-epitaxial substrates, photoresists, hydrides, organo-inorganic compounds), and technology/software under 3D/3E. The classification has been significantly expanded through **five major rulemakings since October 2022**, adding GAAFET-specific controls (3E905), quantum computing items (3A901), and new material categories (3C907–3C909). The hierarchical ECCN structure (Category → Product Group → ECCN → sub-paragraphs) maps naturally to SDKB equipment and material node types.

---

## Failure mode sources remain frustratingly proprietary

No publicly available, downloadable FMEA knowledge graph for semiconductor manufacturing exists. The most relevant academic work — Bahr et al.'s "KG-enhanced RAG for FMEA" (arXiv:2406.18114, published in Journal of Industrial Information Integration 2025) — provides an MIT-licensed code framework at `github.com/lukasbahr/kg-rag-fmea` with a template CSV showing the triple structure (Process Step → Failure Mode → Failure Cause/Effect → Mitigation Action), but **the actual data is proprietary BMW automotive data**, not semiconductor. The ScienceDirect page explicitly states the authors lack permission to share data. Razouk and Kern's semiconductor-specific FMEA work (Applied Sciences 2022, IEEE Access 2023) similarly uses proprietary fab data with no public release.

**JEDEC JEP122H** partially fills this gap. It defines the canonical semiconductor failure mechanism taxonomy: Electromigration, Time-Dependent Dielectric Breakdown, Hot Carrier Injection, NBTI/PBTI, Stress-Induced Voiding, Stress-Induced Leakage Current, mobile ion contamination, and package-level mechanisms (wire bonding failures, solder fatigue, tin whiskers, corrosion). Each mechanism includes activation energy values and acceleration models. JEP122H is reportedly **free to download** after creating a free JEDEC account at `jedec.org/standards-documents`, though the FMEA-specific standard JEP131C requires purchase. The failure mechanism taxonomy itself is extensively documented in public NASA NEPP reports and reliability handbooks from companies like Kioxia. For SDKB provenance, the Hodkiewicz et al. FMEA ontology (`github.com/uwasystemhealth/Paper_Archive_CII_FMEA_Ontology`) provides a reusable OWL schema for FailureMode, FailureCause, FailureEffect, and Component classes — though it contains no semiconductor-specific instance data.

---

## Industry standards and roadmaps offer rich taxonomies behind access barriers

**SEMI Standards** (E10, E30, E40, E116) define the authoritative equipment behavior models used across the semiconductor industry but are individually priced at **$150–$380**. However, substantial taxonomic content is freely documented through third-party sources. The E10 equipment state taxonomy (Productive, Standby, Engineering, Scheduled Downtime, Unscheduled Downtime, Nonscheduled Time) and derived metrics (MTBF, MTTR, Availability, OEE) are thoroughly described in free SEMI overview articles (`semi.org/en/Standards/CTR_031244`), complimentary webinars (`semi.org/en/products-services/standards/step/equipment-performance-metrics`), and vendor summaries from Kontron AIS, PEER Group, Cimetrix, and Systema. Open-source SECS/GEM protocol implementations exist in Python (`github.com/bparzella/secsgem`), .NET (`github.com/mkjeff/secs4net`), Java, and Go — these implement communication state models from E30 but not the full equipment behavior specifications.

**IRDS** roadmap documents are **free to download** after creating a free IEEE account and subscribing to the IRDS Technical Community. The More Moore chapter contains detailed year-by-year parameter projections (metal half-pitch, gate length, device architecture transitions from FinFET to GAA to CFET, interconnect parameters) across a 15-year horizon. However, all data is embedded in **PDF tables** with no machine-readable export. Editions from 2017–2024 are available, covering ~15 focus areas including lithography, factory integration, yield enhancement, and metrology.

---

## Three lesser-known sources deserve attention for SDKB builders

**The Digital Reference Ontology** (`github.com/tibonto/dr`, Apache 2.0) from TIB Hannover and Infineon Technologies is an underappreciated gem. This OWL ontology covers the semiconductor product lifecycle holistically — manufacturing processes, supply chain logistics, organizational structures, CO₂ tracking, and planning — importing SOSA/SSN sensor ontologies and OWL-Time. It comprises multiple sub-ontologies (ecsel-dr-AH, ecsel-dr-AT, ecsel-dr-BMS, ecsel-dr-CO2Savings, ecsel-dr-GDM, and more) and is actively maintained with commits through 2024+.

**Korea's National Core Technology list** designates **11 semiconductor technologies** as protected: sub-30nm DRAM design/process/device technology and 3D stacking, DRAM stacking assembly and inspection, 64+ layer 3D NAND Flash, NAND packaging, sub-30nm foundry process technology, LTE/5G baseband modem design, and CMOS image sensor technology. The official list is published as a MOTIE Public Notice available at `law.go.kr` in Korean. English-language summaries are available from law firms including Lee & Ko, Shin & Kim, and CSET Georgetown (`cset.georgetown.edu/publication/act-on-prevention-of-divulgence-and-protection-of-industrial-technology/`). A December 2024 amendment significantly strengthened enforcement, and the total list now covers **79 technologies across 13 fields**.

**Wikidata** (CC0) provides a shallow but linkable foundation with Q-items for semiconductor device fabrication (Q1570432), individual process nodes from 180nm through 1nm, equipment types, and company entities — all queryable via SPARQL at `query.wikidata.org`. While lacking depth, Wikidata Q-items serve as universal identifiers for entity alignment across other ontologies.

---

## Conclusion: a practical assembly strategy

The landscape reveals a clear pattern: **materials knowledge is well-structured and open, process knowledge is described but locked in papers or paywalled standards, and failure mode data is entirely proprietary.** An SDKB builder should anchor material nodes on MatKG and PubChem/ChEBI, equipment nodes on BIS ECCN Category 3B, experimental workflow structure on SemicONTO, supply chain relationships on tibonto/dr, and failure mechanism types on JEDEC JEP122H's publicly documented taxonomy. The SemiKong process taxonomy should be manually extracted from its paper appendix until a machine-readable release materializes. The eCFR API for BIS data is the single most underutilized resource — it provides a legally authoritative, machine-readable, regularly updated classification of semiconductor manufacturing equipment at a granularity exceeding any academic ontology. The largest remaining gap is a downloadable, openly licensed ontology of semiconductor manufacturing process steps with parameter specifications, which currently exists nowhere in structured form.