#!/usr/bin/env python3
"""PLAN-005 단계 7-A′ — 청구항이 실제로 구별하는 저-df 개념을 KG 에 주입한다 (2026-09-10 · 사용자 승인).

왜 필요한가. 단계 7 판정(계획서 §16)이 확정한 병목은 어휘의 **해상도**다 — 문헌 33,274건이 개시집합
12,311가지로 뭉치고(`{dielectric}` 하나뿐인 문헌 1,040), 질의 후보집합 중앙값이 961 이다. 2단계
실측(계획서 §17)에서 rej 독립항 feature 의 47.5% 가 미접지였고 그 손실의 본체는 표면형이 아니라
**없는 노드**였다 — 미접지 텍스트 상위 명사: 메모리 485 · 트랜지스터 182 · 비휘발 174 · 전하 · 터널 ·
플로팅 · 층간 · 콘택 · 배선 · 도전막 · 반도체층. `data/reports/ko_concept_proposals.json`(CR-001B) 이
같은 표면형을 R7 통과 후보로 이미 들고 있었다(청구항 df 와 A-Box df 비율 병기).

무엇을 넣는가 (idempotent — 재실행해도 중복되지 않는다).
  - 노드 19: StructuralElement 12 · Device 3 · Material 4. 전부 이미 `pa:TechnicalConcept` 에 바인딩되고
    링커 축(`CONCEPT_TYPES`)·`featureConcept` range 에 있는 클래스라 **T-Box 는 바뀌지 않는다**(semi 불변).
    설계 초안의 Parameter 1(전압)은 그 축이 링커·range 에 없어 뺐다(아래 NODES 주석).
  - 한글 표면형 synonyms (lang ko · lexicon_profile patent-text) — 표면형은 후보 파일·미접지 명사에서
    **그대로**, 변형 철자는 넣지 않는다(5-B 원칙).
  - 기존 노드 표면형 2: `device:pcram` ← 상변화 · `structural_element:capacitor` ← 커패시터.

넣지 않는 것. 영역·패턴·라인·연결·배치(관계·위치어) · 웰·셀(단독 중의) · **R7 차단 7개 해제**(해상도
규칙 유지 · `기판` df 비율 0.43). `transistor`·`memory_cell` 처럼 df 가 상한을 넘을 수 있는 노드는
넣되 **R7 판정에 맡긴다**(5-B 선례 — 차단되면 그 사실을 적고 나머지로 판정).

주입 후 `make parse owl convert concept-mapping abox-claim-features abox-priorart` 가 따른다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
_REF = ("PLAN-005 §17 (단계 7-A′) · 계획서 §16 판정 · CR-001B data/reports/ko_concept_proposals.json "
        "proposals · 단계 7-A′ 2단계 미접지 명사 실측")

#: (id, type, canonical_name(en), ko surfaces, props, description)
#: 영문 canonical 은 Tier-1 표면형으로 patent-text 에 들어가 US·JP(영문 초록) 문헌에 닿는다.
NODES: list[tuple[str, str, str, tuple[str, ...], dict, str]] = [
    # ── StructuralElement 12 ─────────────────────────────────────────────
    ("structural_element:floating_gate", "StructuralElement", "Floating Gate", ("플로팅 게이트",),
     {}, "Floating gate of a charge-storage (flash) memory cell."),
    ("structural_element:tunnel_dielectric", "StructuralElement", "Tunnel Dielectric",
     ("터널 절연막", "터널 산화막", "터널 유전막"), {},
     "Tunnel dielectric/oxide layer through which carriers tunnel into a storage node."),
    ("structural_element:charge_storage_layer", "StructuralElement", "Charge Storage Layer",
     ("전하 저장층", "전하 트랩층", "전하 축적층"), {},
     "Charge storage / charge trap layer of a memory cell (e.g. nitride trap layer)."),
    ("structural_element:interlayer_dielectric", "StructuralElement", "Interlayer Dielectric",
     ("층간 절연막", "층간절연막"), {},
     "Interlayer dielectric (ILD) separating wiring levels — a layer, distinct from the dielectric material nodes."),
    ("structural_element:contact_plug", "StructuralElement", "Contact Plug", ("콘택", "콘택 플러그"), {},
     "Contact / contact plug connecting a device region to wiring."),
    ("structural_element:bit_line", "StructuralElement", "Bit Line", ("비트라인", "비트 라인"), {},
     "Bit line of a memory array."),
    ("structural_element:word_line", "StructuralElement", "Word Line", ("워드라인", "워드 라인"), {},
     "Word line of a memory array."),
    ("structural_element:conductive_layer", "StructuralElement", "Conductive Layer", ("도전막", "도전층"), {},
     "Conductive film/layer as a structural layer in a claim."),
    ("structural_element:semiconductor_layer", "StructuralElement", "Semiconductor Layer", ("반도체층",), {},
     "Semiconductor layer (e.g. channel/body layer) as a structural layer."),
    ("structural_element:active_region", "StructuralElement", "Active Region", ("활성 영역", "활성영역"), {},
     "Active region of a substrate defined by device isolation."),
    ("structural_element:hard_mask", "StructuralElement", "Hard Mask", ("하드마스크", "하드 마스크"), {},
     "Hard mask layer as a structure — a different level from subprocess:hardmask_etch (the step)."),
    ("structural_element:device_isolation", "StructuralElement", "Device Isolation", ("소자분리", "소자 분리"), {},
     "Device isolation structure (e.g. STI) separating active regions."),
    # ── Device 3 ────────────────────────────────────────────────────────
    ("device:flash_memory", "Device", "Flash Memory", ("플래시 메모리", "플래시메모리"), {"category": "memory"},
     "Flash memory device (superordinate of NAND/NOR flash)."),
    ("device:nonvolatile_memory", "Device", "Non-volatile Memory",
     ("비휘발성 메모리", "불휘발성 메모리", "비휘발성 기억"), {"category": "memory"},
     "Non-volatile memory device in general."),
    ("device:transistor", "Device", "Transistor", ("트랜지스터",), {"category": "logic"},
     "Transistor in general — superordinate of MOSFET/FinFET/BJT nodes. R7 decides whether the surface "
     "is admitted in patent-text."),
    # ── Material 4 ──────────────────────────────────────────────────────
    ("material:indium", "Material", "Indium", ("인듐",), {"category": "metal"},
     "Indium (In) — e.g. InGaZnO oxide semiconductors, In-based compounds."),
    ("material:titanium", "Material", "Titanium", ("티타늄",), {"category": "metal"},
     "Titanium (Ti) metal — distinct from titanium nitride (material:tin)."),
    ("material:nitrogen_gas", "Material", "Nitrogen Gas", ("질소",), {"category": "gas"},
     "Nitrogen (N2) as a process/carrier gas or nitridation source."),
    ("material:silicide", "Material", "Silicide", ("실리사이드",), {"category": "compound"},
     "Metal silicide (e.g. CoSi2, NiSi, TiSi2) contact/gate material."),
    # `parameter:voltage`(전압)는 넣지 않는다 — 4단계에서 드러난 사실(사용자 결정 2026-09-10): Parameter 축은
    # 링커 축 `CONCEPT_TYPES` 와 `ont:featureConcept` range(sdkb-patent.ttl · 하류 핀)에 없어 등록해도 접지가
    # 0 이다. 기존 파라미터 5개도 같은 이유로 feature 에 붙은 적이 없다. 축 편입은 T-Box 변경이라 별도 안건.
]

#: 기존 노드에 보태는 한글 표면형 — 노드는 이미 있고 청구항이 부르는 이름만 없었다.
EXTRA_SYNONYMS: list[tuple[str, str]] = [
    ("device:pcram", "상변화"),
    ("structural_element:capacitor", "커패시터"),
]

NEW_IDS = {nid for nid, *_ in NODES}
_SOURCE = "PLAN-005 stage 7-A prime (ko_concept_proposals.proposals / unmapped-noun census)"


def _node(nid: str, typ: str, name: str, props: dict, desc: str) -> dict:
    return {
        "id": nid,
        "type": typ,
        "canonical_name": name,
        "description": desc,
        # patent-text 프로파일에서만 산다 — expert-tag(전문가·문제 A-Box)는 이번 비목표이고 사전 원장의
        # expert-tag 델타를 0 으로 둔다(5-B 선례).
        "props": {**props, "lexicon_profile": "patent-text"},
        "provenance": {
            "source": "author",
            "reference": _REF,
            "license": "CDLA-Permissive-2.0",
            "modified": False,
            "interpretation": "author-defined",
            "validation_required": True,
            "note": "Registered by PLAN-005 stage 7-A prime to raise concept-layer resolution: the surface "
                    "form is frequent in KR independent claims, unmapped before, and below the R7 df ceiling "
                    "where measured.",
        },
    }


def _synonym(nid: str, term: str) -> dict:
    return {"node_id": nid, "term": term, "lang": "ko", "term_type": "synonym", "source": _SOURCE}


def main() -> int:
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))

    # 재실행 안전: 이 단계가 넣은 것만 걷어내고 다시 넣는다.
    kg["nodes"] = [n for n in kg["nodes"] if n["id"] not in NEW_IDS]
    kg["synonyms"] = [s for s in kg["synonyms"]
                      if s["node_id"] not in NEW_IDS and s.get("source") != _SOURCE]

    existing_ko = {s["term"] for s in kg["synonyms"] if s.get("lang") == "ko"}
    planned = [ko for *_, kos, _p, _d in NODES for ko in kos] + [t for _, t in EXTRA_SYNONYMS]
    clash = sorted(set(planned) & existing_ko)
    if clash:
        raise SystemExit(f"ERROR: 한글 표면형이 기존 synonym 과 겹친다: {clash}")
    if len(planned) != len(set(planned)):
        raise SystemExit("ERROR: 주입 표면형에 중복이 있다")
    existing_ids = {n["id"] for n in kg["nodes"]}
    missing = [nid for nid, _ in EXTRA_SYNONYMS if nid not in existing_ids]
    if missing:
        raise SystemExit(f"ERROR: 표면형을 보탤 기존 노드가 없다: {missing}")

    n_syn = 0
    for nid, typ, name, kos, props, desc in NODES:
        kg["nodes"].append(_node(nid, typ, name, props, desc))
        for ko in kos:
            kg["synonyms"].append(_synonym(nid, ko)); n_syn += 1
    for nid, ko in EXTRA_SYNONYMS:
        kg["synonyms"].append(_synonym(nid, ko)); n_syn += 1

    KG_PATH.write_text(json.dumps(kg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_type: dict[str, int] = {}
    for _, typ, *_ in NODES:
        by_type[typ] = by_type.get(typ, 0) + 1
    print(f"✓ nodes +{len(NODES)} {by_type} → {len(kg['nodes'])}")
    print(f"✓ synonyms +{n_syn} (ko · 기존 노드 {len(EXTRA_SYNONYMS)} 포함) → {len(kg['synonyms'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
