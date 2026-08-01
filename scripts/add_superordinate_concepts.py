#!/usr/bin/env python3
"""CR-007 결정 ① · ①-b — 상위 개념 7개와 그 하위 계층을 KG 에 주입한다.

왜 필요한가. 하류(sdkb-prior-art-paper)가 특허 전문에 현행 별칭 사전을 적용하면
`챔버`→`skill:chamber_conditioning`, `가스`→`skill:gas_chemistry` 처럼 **역량(Skill) 축**에
문서 개념이 붙어 Skill 축이 특허 개념 링크의 18.1 % 를 차지한다(D-15 · 축 범주 오류).
고칠 방법은 별칭 삭제가 아니라 **축 재지정**인데, 재지정이 붙을 상위 개념이 온톨로지에
없었다. 이 스크립트가 그 자리를 만든다.

주입물 (idempotent — 재실행해도 중복되지 않는다):
  - 상위 개념 7  (CR-007 §3단계 결정 ① 표 그대로)
  - 구체 하위 6  (process_gas · photomask 의 하위가 스냅샷에 0 개였다 — 2026-08-01 승인)
  - BROADER 엣지 18 (하위 → 상위. convert_rdf 가 skos:broader 로 직렬화)

**synonyms 는 넣지 않는다.** 표면형은 프로파일을 가진 매핑 자산
(mappings/concept_mapping.json)이 담당한다. Tier-1 어휘집에 `챔버` 같은 표면형을 넣으면
expert-tag 프로파일의 현행 동작이 함께 바뀌어 CR-007 비목표(전문가매칭 회귀 금지 · T3)를
깬다.

주입 후 `make convert` 로 sdkb-core-data.ttl 을 재생성한다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"

_CR = "CR-007 §3단계 결정 ①"

# ── 상위 개념 7 (축 배치 근거는 CR-007 §3단계 결정 ① 표) ────────────────
SUPERORDINATE: list[tuple[str, str, str, str]] = [
    ("equipment_class:process_chamber", "EquipmentClass", "Process Chamber",
     "Generic process chamber. Equipment 축의 41 노드는 전부 모델·부품 단위라 "
     "일반 개념은 EquipmentClass 층에 둔다."),
    ("material:process_gas", "Material", "Process Gas",
     "Generic process gas consumed in etch/deposition. 소모재는 Material 축 "
     "(hf_acid·barc 선례)."),
    ("process:plasma_processing", "Process", "Plasma Processing",
     "Plasma-based processing in general. subprocess:plasma_etch 는 과대특정이라 "
     "Process 층에 상위를 세운다."),
    ("material:photomask", "Material", "Photomask",
     "Photomask / reticle. Device 34 노드는 전부 반도체 소자라 마스크 자리가 없다."),
    ("material:dielectric", "Material", "Dielectric Material",
     "Dielectric material superclass of sio2 · sin · low_k_dielectric · hfO2."),
    ("material:oxide", "Material", "Oxide Material",
     "Oxide material superclass of sio2 · teOs · hfO2."),
    ("material:cmp_slurry", "Material", "CMP Slurry",
     "CMP slurry superclass of cmp_slurry_cu · cmp_slurry_oxide."),
]

# ── 구체 하위 6 — process_gas·photomask 의 하위가 스냅샷에 0 개였다 ──────
# 성공기준 ⑩(상위 7 개가 각각 broader 하위 ≥1)을 느슨하게 만드는 대신
# 실체를 세운다. 2 글자 라틴 토큰(ar·o2)은 자유 텍스트에서 오검출되므로
# id 를 argon·oxygen_gas 로 둔다.
NARROWER_NEW: list[tuple[str, str, str, str]] = [
    ("material:cf4", "Material", "Carbon Tetrafluoride",
     "CF4 — fluorocarbon etch gas."),
    ("material:sf6", "Material", "Sulfur Hexafluoride",
     "SF6 — fluorine-source etch gas."),
    ("material:oxygen_gas", "Material", "Oxygen Gas",
     "O2 — oxidant / ashing gas."),
    ("material:argon", "Material", "Argon",
     "Ar — inert carrier and sputtering gas."),
    ("material:euv_mask", "Material", "EUV Mask",
     "Reflective multilayer mask for EUV lithography."),
    ("material:duv_photomask", "Material", "DUV Photomask",
     "Transmissive photomask for DUV lithography."),
]

# ── 계층 (하위, 상위) — convert_rdf 가 skos:broader 로 직렬화 ─────────────
BROADER: list[tuple[str, str]] = [
    # 교차형 Equipment → EquipmentClass (2026-08-01 승인 · 기존 IS_INSTANCE_OF 와 같은 층위)
    ("equipment:pvd_chamber",     "equipment_class:process_chamber"),
    ("equipment:cvd_reactor",     "equipment_class:process_chamber"),
    ("material:cf4",              "material:process_gas"),
    ("material:sf6",              "material:process_gas"),
    ("material:oxygen_gas",       "material:process_gas"),
    ("material:argon",            "material:process_gas"),
    ("subprocess:plasma_etch",    "process:plasma_processing"),
    ("material:euv_mask",         "material:photomask"),
    ("material:duv_photomask",    "material:photomask"),
    ("material:sio2",             "material:dielectric"),
    ("material:sin",              "material:dielectric"),
    ("material:low_k_dielectric", "material:dielectric"),
    ("material:hfO2",             "material:dielectric"),
    ("material:sio2",             "material:oxide"),
    ("material:teOs",             "material:oxide"),
    ("material:hfO2",             "material:oxide"),
    ("material:cmp_slurry_cu",    "material:cmp_slurry"),
    ("material:cmp_slurry_oxide", "material:cmp_slurry"),
]

NEW_IDS = {nid for nid, *_ in SUPERORDINATE} | {nid for nid, *_ in NARROWER_NEW}


def _node(nid: str, typ: str, name: str, desc: str) -> dict:
    return {
        "id": nid,
        "type": typ,
        "canonical_name": name,
        "description": desc,
        # 이 노드들의 이름은 `photomask`·`oxide` 처럼 **과대일반화 표면형 그 자체**다.
        # Tier-1 어휘집(canonical_name·id local)에 그대로 들어가면 Tier-2 별칭을 가려
        # (build_abox_experts_problems.py:364-371 — Tier-1 우선) 전문가매칭의 기존
        # 링크가 사라진다. 실측으로 SC_PROB_007 의 requiresSkill→mask_engineering 이
        # 소실됐다. CR-007 비목표(expert-tag 동작 불변 · T3)를 지키려면 이 노드들의
        # 어휘는 patent-text 프로파일에서만 산다. 그래프 자체(노드·계층)는 무조건 존재한다.
        "props": {"lexicon_profile": "patent-text"},
        "provenance": {
            "source": "author",
            "reference": _CR,
            "license": "CDLA-Permissive-2.0",
            "modified": False,
            "interpretation": "author-defined",
            "validation_required": True,
            "note": "Superordinate concept introduced so that over-general surface "
                    "forms can be re-targeted off the Skill axis (D-15).",
        },
    }


def _edge(src: str, dst: str) -> dict:
    return {
        "src": src,
        "predicate": "BROADER",
        "dst": dst,
        # weight 를 두지 않는다 — convert_rdf 는 weight 를 **엣지 주어 노드**에
        # ont:confidence 로 붙인다. 계층 엣지에 1.0 을 달면 material:sio2 같은
        # 기존 노드에 없던 트리플이 생겨 릴리스 서명이 이유 없이 움직인다.
        "provenance": {
            "source": "author",
            "reference": _CR + "-b",
            "license": "CDLA-Permissive-2.0",
            "interpretation": "author-defined",
            "note": "skos:broader — CR-002 가 제안한 술어의 최소 선착수.",
        },
    }


def main() -> int:
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))

    # 재실행 안전: 이 CR 이 넣은 것만 걷어내고 다시 넣는다.
    kg["nodes"] = [n for n in kg["nodes"] if n["id"] not in NEW_IDS]
    kg["edges"] = [e for e in kg["edges"] if e.get("predicate") != "BROADER"]

    node_ids = {n["id"] for n in kg["nodes"]}
    for nid, typ, name, desc in SUPERORDINATE + NARROWER_NEW:
        kg["nodes"].append(_node(nid, typ, name, desc))
        node_ids.add(nid)

    dangling = [(s, d) for s, d in BROADER if s not in node_ids or d not in node_ids]
    if dangling:
        raise SystemExit(f"ERROR: dangling BROADER edge(s): {dangling}")

    for src, dst in BROADER:
        kg["edges"].append(_edge(src, dst))

    KG_PATH.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 상위 7 개가 각각 하위 ≥1 인가 (성공기준 ⑩ 의 앞단 검사)
    parents = {p for _, p in BROADER}
    orphan = [nid for nid, *_ in SUPERORDINATE if nid not in parents]
    print(f"✓ nodes +{len(SUPERORDINATE) + len(NARROWER_NEW)} "
          f"(상위 {len(SUPERORDINATE)} · 하위 {len(NARROWER_NEW)}) → {len(kg['nodes'])}")
    print(f"✓ BROADER edges +{len(BROADER)} → {len(kg['edges'])}")
    print(f"{'✓' if not orphan else '✗'} 상위 개념 하위 보유: "
          f"{len(SUPERORDINATE) - len(orphan)}/{len(SUPERORDINATE)}"
          + (f" · orphan={orphan}" if orphan else ""))
    return 1 if orphan else 0


if __name__ == "__main__":
    raise SystemExit(main())
