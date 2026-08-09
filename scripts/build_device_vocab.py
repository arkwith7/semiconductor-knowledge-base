"""B4 + A2: 외부 device 어휘 인입 (Wikidata SPARQL 기반).

근거: `docs/dataset_full_collection_runbook.md` Phase D.

대상 device classes (시드):
- logic: FinFET, GAA-FET, MOSFET, CMOS, BJT, HEMT, JFET
- memory: DRAM, SRAM, NAND flash, NOR flash, EEPROM, PCRAM, ReRAM, MRAM, 3D NAND
- power: IGBT, SiC MOSFET, GaN HEMT, thyristor
- sensor: CMOS image sensor, CCD, photodiode, MEMS
- packaging: BGA, flip chip, wire bonding, TSV, HBM, interposer, fan-out WLP

각 시드에 대해 Wikidata SPARQL 로 (item, label_ko, label_en, aliases) 조회 →
JSONL + `mappings/abox_term_aliases.json` 호환 형식의 alias table 생성.

사용
====
    .venv/bin/python scripts/build_device_vocab.py --plan
    .venv/bin/python scripts/build_device_vocab.py --run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data/external/device_vocab"
OUT_JSONL = OUT_DIR / "wikidata_device_classes.jsonl"
OUT_ALIAS = OUT_DIR / "device_alias_table.json"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# 시드: device id (node_id) → search label (영어/한글 양방향)
SEED_DEVICES: List[Dict[str, Any]] = [
    # logic
    {"node_id": "device:finfet", "category": "logic", "search": "FinFET"},
    {"node_id": "device:gaa_fet", "category": "logic", "search": "gate-all-around field-effect transistor"},
    {"node_id": "device:mosfet", "category": "logic", "search": "MOSFET"},
    {"node_id": "device:cmos", "category": "logic", "search": "CMOS"},
    {"node_id": "device:bjt", "category": "logic", "search": "bipolar junction transistor"},
    {"node_id": "device:hemt", "category": "logic", "search": "high-electron-mobility transistor"},
    {"node_id": "device:jfet", "category": "logic", "search": "JFET"},
    # memory
    {"node_id": "device:dram", "category": "memory", "search": "DRAM"},
    {"node_id": "device:sram", "category": "memory", "search": "static random-access memory"},
    {"node_id": "device:nand_flash", "category": "memory", "search": "NAND flash"},
    {"node_id": "device:nor_flash", "category": "memory", "search": "NOR flash"},
    {"node_id": "device:eeprom", "category": "memory", "search": "EEPROM"},
    {"node_id": "device:pcram", "category": "memory", "search": "phase-change memory"},
    {"node_id": "device:reram", "category": "memory", "search": "resistive random-access memory"},
    {"node_id": "device:mram", "category": "memory", "search": "magnetoresistive random-access memory"},
    {"node_id": "device:3d_nand", "category": "memory", "search": "3D V-NAND"},
    # power
    {"node_id": "device:igbt", "category": "power", "search": "insulated-gate bipolar transistor"},
    {"node_id": "device:sic_mosfet", "category": "power", "search": "silicon carbide MOSFET"},
    {"node_id": "device:gan_hemt", "category": "power", "search": "gallium nitride HEMT"},
    {"node_id": "device:thyristor", "category": "power", "search": "thyristor"},
    # sensor
    {"node_id": "device:cmos_image_sensor", "category": "sensor", "search": "CMOS image sensor"},
    {"node_id": "device:ccd", "category": "sensor", "search": "charge-coupled device"},
    {"node_id": "device:photodiode", "category": "sensor", "search": "photodiode"},
    {"node_id": "device:mems", "category": "sensor", "search": "microelectromechanical systems"},
    # packaging
    {"node_id": "device:bga", "category": "packaging", "search": "ball grid array"},
    {"node_id": "device:flip_chip", "category": "packaging", "search": "flip chip"},
    {"node_id": "device:wire_bonding", "category": "packaging", "search": "wire bonding"},
    {"node_id": "device:tsv", "category": "packaging", "search": "through-silicon via"},
    {"node_id": "device:hbm", "category": "packaging", "search": "high-bandwidth memory"},
    {"node_id": "device:interposer", "category": "packaging", "search": "silicon interposer"},
    {"node_id": "device:fan_out_wlp", "category": "packaging", "search": "fan-out wafer-level packaging"},
]


SPARQL_QUERY = """
SELECT ?item ?itemLabel ?itemLabelKo ?itemLabelEn ?aliasEn ?aliasKo WHERE {{
  ?item rdfs:label "{search}"@en .
  OPTIONAL {{ ?item rdfs:label ?itemLabelKo FILTER(lang(?itemLabelKo) = "ko") }}
  OPTIONAL {{ ?item rdfs:label ?itemLabelEn FILTER(lang(?itemLabelEn) = "en") }}
  OPTIONAL {{ ?item skos:altLabel ?aliasEn FILTER(lang(?aliasEn) = "en") }}
  OPTIONAL {{ ?item skos:altLabel ?aliasKo FILTER(lang(?aliasKo) = "ko") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 50
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_one(seed: Dict[str, Any], session: requests.Session) -> Dict[str, Any]:
    query = SPARQL_QUERY.format(search=seed["search"].replace('"', ''))
    resp = session.get(
        WIKIDATA_SPARQL,
        params={"query": query, "format": "json"},
        headers={
            "User-Agent": "paper-data-runbook/0.1 (https://github.com/arkwith7/paper_data)",
            "Accept": "application/sparql-results+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    bindings = data.get("results", {}).get("bindings", [])
    en_labels = set()
    ko_labels = set()
    wikidata_qids = set()
    en_labels.add(seed["search"])
    for b in bindings:
        item = b.get("item", {}).get("value", "")
        if item:
            wikidata_qids.add(item.rsplit("/", 1)[-1])
        for k_src, target in (
            ("itemLabel", en_labels),
            ("itemLabelEn", en_labels),
            ("aliasEn", en_labels),
            ("itemLabelKo", ko_labels),
            ("aliasKo", ko_labels),
        ):
            v = b.get(k_src, {}).get("value", "")
            if v:
                target.add(v)
    return {
        "node_id": seed["node_id"],
        "category": seed["category"],
        "search_seed": seed["search"],
        "wikidata_qids": sorted(wikidata_qids),
        "labels": {
            "en": sorted(en_labels),
            "ko": sorted(ko_labels),
        },
        "fetched_at": _utc_now(),
    }


def run(args: argparse.Namespace) -> None:
    if args.plan:
        from collections import Counter
        cat = Counter(s["category"] for s in SEED_DEVICES)
        print(f"[plan] seeds: {len(SEED_DEVICES)}")
        print(f"[plan] by category: {dict(cat)}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    rows: List[Dict[str, Any]] = []
    alias_table: Dict[str, Dict[str, List[str]]] = {}

    for i, seed in enumerate(SEED_DEVICES):
        try:
            row = fetch_one(seed, session)
        except Exception as exc:
            print(f"  [{i+1}] {seed['node_id']} ERROR: {exc}")
            row = {
                "node_id": seed["node_id"],
                "category": seed["category"],
                "search_seed": seed["search"],
                "wikidata_qids": [],
                "labels": {"en": [seed["search"]], "ko": []},
                "error": str(exc),
                "fetched_at": _utc_now(),
            }
        rows.append(row)
        alias_table[row["node_id"]] = {
            "category": [row["category"]],
            "en": row["labels"]["en"],
            "ko": row["labels"]["ko"],
            "wikidata": row.get("wikidata_qids", []),
        }
        ko_n = len(row["labels"]["ko"])
        en_n = len(row["labels"]["en"])
        print(f"  [{i+1}/{len(SEED_DEVICES)}] {row['node_id']}: en={en_n} ko={ko_n}")
        time.sleep(args.interval)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    OUT_ALIAS.write_text(json.dumps(alias_table, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] wrote {OUT_JSONL} ({len(rows)}) and {OUT_ALIAS}")


def main() -> None:
    ap = argparse.ArgumentParser(description="B4+A2 device 어휘 인입 (Wikidata SPARQL)")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--interval", type=float, default=1.2, help="Wikidata 호출 간격 (초)")
    args = ap.parse_args()
    if not (args.plan or args.run):
        args.plan = True
    run(args)


if __name__ == "__main__":
    main()
