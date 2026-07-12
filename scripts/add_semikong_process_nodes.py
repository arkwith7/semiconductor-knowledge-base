#!/usr/bin/env python3
"""Restore the SemiKong process taxonomy groups/modules that SDKB never ingested.

SDKB's 8 `Process` nodes are SemiKong L1 *Process Groups* (see each node's
`provenance.source_id`, e.g. `L1-Planarization`). But SemiKong Appendix A
(Table 7) enumerates **10** groups, and SDKB carries only 7 of them — groups
1 (Substrate Preparation), 9 (Advanced Modules) and 10 (Back-End Processes)
are missing entirely, and most L2 modules under the groups we do have were
dropped too.

That truncation is a real defect: a knowledge base that claims to cover
semiconductor manufacturing cannot represent dicing, packaging, metallisation
or wafer test at all. This script restores the Group and Module columns of
Table 7 in full.

Only the *missing* concepts are injected — the 20 existing process/subprocess
IRIs are never touched, because downstream consumers (patent links in
sdkb-abox-patents, the foresight paper's frozen G0) point at them.

Re-run `make convert` afterwards to regenerate sdkb-core-data.ttl.
Safe to run repeatedly (previously-injected nodes are replaced, not duplicated).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"

_REF = "Nguyen et al. 2024, arXiv:2411.13802, Appendix A (Table 7)"
_URL = "https://github.com/aitomatic/semikong"

# SemiKong Table 7 groups that SDKB never ingested. (id, canonical_name, source_id, description)
GROUPS = [
    ("process:substrate_preparation", "Substrate Preparation", "L1-Substrate_Preparation",
     "Wafer manufacturing, polishing and incoming cleaning, before device fabrication."),
    ("process:advanced_modules", "Advanced Modules", "L1-Advanced_Modules",
     "Device-enabling integration modules, e.g. high-k/metal gate, strain, 3D structures."),
    ("process:back_end", "Back-End Processes", "L1-Back_End_Processes",
     "Post-FEOL processes: interconnect, passivation, thinning, test, dicing and packaging."),
]

# Table 7 modules (L2) that SDKB lacks, keyed to the Process (L1 group) that owns them.
# Modules already represented by an existing Process node are NOT duplicated:
#   1.3 Cleaning -> process:clean;  2.2 Deposition -> process:deposition;
#   3.1 Lithography -> process:lithography;  3.2 Etching -> process:etch;
#   4.1 Ion Implantation -> process:implant; 4.2 Diffusion -> process:diffusion;
#   5.1 CMP -> process:cmp;  7.2 Thermal Oxidation -> merged into 2.1 Oxidation.
MODULES = [
    # (id, canonical_name, parent_process, source_id, description)
    ("subprocess:wafer_manufacturing", "Wafer Manufacturing", "process:substrate_preparation",
     "L2-Substrate_Preparation/Wafer_Manufacturing", "Crystal growth, wafer slicing, edge rounding."),
    ("subprocess:wafer_polishing", "Wafer Polishing", "process:substrate_preparation",
     "L2-Substrate_Preparation/Wafer_Polishing", "Lapping and polishing of the incoming wafer."),

    ("subprocess:oxidation", "Oxidation", "process:deposition",
     "L2-Film_Formation/Oxidation",
     "Growth of oxide films (thermal, plasma-enhanced, high/low pressure, anodic). "
     "Table 7 lists oxidation twice (2.1 and 7.2 Thermal Oxidation); modelled once."),
    ("subprocess:epitaxial_growth", "Epitaxial Growth", "process:deposition",
     "L2-Film_Formation/Epitaxial_Growth", "Silicon and compound-semiconductor epitaxy."),

    ("subprocess:in_situ_doping", "In-situ Doping", "process:implant",
     "L2-Doping/In_situ_Doping", "Dopant incorporation during epitaxy or deposition."),

    ("subprocess:etchback_planarization", "Etchback Planarization", "process:cmp",
     "L2-Planarization/Etchback_Planarization", "Planarisation by resist or sacrificial-layer etchback."),

    ("subprocess:wet_cleaning", "Wet Cleaning", "process:clean",
     "L2-Cleaning_and_Surface_Preparation/Wet_Cleaning", "RCA clean, piranha clean, HF dip."),
    ("subprocess:dry_cleaning", "Dry Cleaning", "process:clean",
     "L2-Cleaning_and_Surface_Preparation/Dry_Cleaning", "Plasma and UV-ozone cleaning."),
    ("subprocess:advanced_cleaning", "Advanced Cleaning", "process:clean",
     "L2-Cleaning_and_Surface_Preparation/Advanced_Cleaning", "Supercritical CO2 and cryogenic cleaning."),

    ("subprocess:annealing", "Annealing", "process:diffusion",
     "L2-Thermal_Processing/Annealing", "Furnace, rapid thermal and laser annealing."),
    ("subprocess:dopant_activation", "Dopant Activation", "process:diffusion",
     "L2-Thermal_Processing/Dopant_Activation", "Spike and flash annealing for dopant activation."),

    ("subprocess:physical_metrology", "Physical Metrology", "process:metrology",
     "L2-Metrology_and_Inspection/Physical_Metrology", "Profilometry, ellipsometry, X-ray reflectometry."),
    ("subprocess:electrical_metrology", "Electrical Metrology", "process:metrology",
     "L2-Metrology_and_Inspection/Electrical_Metrology", "Sheet resistance and C-V measurement."),
    ("subprocess:defect_inspection", "Defect Inspection", "process:metrology",
     "L2-Metrology_and_Inspection/Defect_Inspection", "Optical, e-beam and wafer inspection."),

    ("subprocess:high_k_metal_gate", "High-k/Metal Gate", "process:advanced_modules",
     "L2-Advanced_Modules/High_k_Metal_Gate", "Gate dielectric and metal gate formation."),
    ("subprocess:strain_engineering", "Strain Engineering", "process:advanced_modules",
     "L2-Advanced_Modules/Strain_Engineering", "Strained silicon and SiGe channels."),
    ("subprocess:three_d_structures", "3D Structures", "process:advanced_modules",
     "L2-Advanced_Modules/3D_Structures", "FinFET formation and gate-all-around structures."),

    ("subprocess:multilayer_interconnect", "Multilayer Interconnect", "process:back_end",
     "L2-Back_End_Processes/Multilayer_Interconnect", "Interlayer dielectric and metal layers, with CMP."),
    ("subprocess:metallization", "Metallization", "process:back_end",
     "L2-Back_End_Processes/Metallization", "PVD, CVD, electroplating and sputtering of interconnect metal."),
    ("subprocess:interconnect_patterning", "Interconnect Patterning", "process:back_end",
     "L2-Back_End_Processes/Interconnect_Patterning", "Damascene and dual-damascene patterning."),
    ("subprocess:passivation", "Passivation", "process:back_end",
     "L2-Back_End_Processes/Passivation", "Silicon nitride deposition, polyimide coating."),
    ("subprocess:wafer_thinning", "Wafer Thinning", "process:back_end",
     "L2-Back_End_Processes/Wafer_Thinning", "Backside grinding and chemical etching."),
    ("subprocess:wafer_testing", "Wafer Testing", "process:back_end",
     "L2-Back_End_Processes/Wafer_Testing", "Parametric and functional test at wafer level."),
    ("subprocess:dicing", "Dicing", "process:back_end",
     "L2-Back_End_Processes/Dicing", "Mechanical, laser and plasma dicing."),
    ("subprocess:packaging", "Packaging", "process:back_end",
     "L2-Back_End_Processes/Packaging", "Die attach, wire bonding, flip-chip bonding, encapsulation."),
    ("subprocess:advanced_packaging", "Advanced Packaging", "process:back_end",
     "L2-Back_End_Processes/Advanced_Packaging", "TSV, wafer-level packaging, 3D integration."),
]

NEW_IDS = {g[0] for g in GROUPS} | {m[0] for m in MODULES}


def _prov(source_id: str, note: str | None = None) -> dict:
    p = {
        "source": "semikong",
        "source_id": source_id,
        "reference": _REF,
        "license": "Apache-2.0",
        "url": _URL,
        "modified": False,
        "interpretation": "mapped",
    }
    if note:
        p["note"] = note
    return p


def main() -> int:
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))

    # idempotent: drop anything this script injected before, keep the originals
    kg["nodes"] = [n for n in kg["nodes"] if n["id"] not in NEW_IDS]
    kg["edges"] = [
        e for e in kg["edges"]
        if not (e["predicate"] == "HAS_SUBPROCESS" and e["dst"] in NEW_IDS)
    ]

    existing = {n["id"] for n in kg["nodes"]}
    for pid, name, source_id, desc in GROUPS:
        kg["nodes"].append({
            "id": pid, "type": "Process", "canonical_name": name, "description": desc,
            "props": {"priority": 1},
            "provenance": _prov(source_id, "Process group enumerated in Table 7 but absent from SDKB v0.3."),
        })

    for sid, name, parent, source_id, desc in MODULES:
        if parent not in existing and parent not in {g[0] for g in GROUPS}:
            raise SystemExit(f"parent process missing: {parent}")
        kg["nodes"].append({
            "id": sid, "type": "SubProcess", "canonical_name": name, "description": desc,
            "props": {"parent_process": parent},
            "provenance": _prov(source_id, "Process module enumerated in Table 7 but absent from SDKB v0.3."),
        })
        kg["edges"].append({
            "src": parent, "predicate": "HAS_SUBPROCESS", "dst": sid, "weight": 0.9,
            "provenance": {
                "source": "semikong", "reference": "SemiKong L1->L2 taxonomy hierarchy",
                "license": "Apache-2.0", "interpretation": "mapped",
                "note": "Process group -> process module nesting, per Table 7",
            },
        })

    KG_PATH.write_text(json.dumps(kg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_proc = sum(1 for n in kg["nodes"] if n["type"] == "Process")
    n_sub = sum(1 for n in kg["nodes"] if n["type"] == "SubProcess")
    print(f"[semikong] +{len(GROUPS)} Process, +{len(MODULES)} SubProcess")
    print(f"[semikong] totals: Process {n_proc}, SubProcess {n_sub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
