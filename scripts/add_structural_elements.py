#!/usr/bin/env python3
"""PLAN-005 단계 5-B — 등재 보류된 구조요소 15개를 `StructuralElement` 로 KG 에 주입한다.

왜 필요한가. CR-001B 가 한국어 한정요소 표면형을 수확했을 때 `게이트`·`기판`·`전극` 같은
청구항의 가장 흔한 구조요소 15개는 *"축 부재 — 구조 요소를 담을 클래스가 TBox 에 없다"* 로
등재 보류됐다(data/reports/ko_concept_proposals.json · 결정 ㉢). PLAN-005 단계 4 가 그 축
`ont:StructuralElement`(⊑ pa:TechnicalConcept)를 세웠지만 인스턴스는 0 이었다 — 5-A 실측에서
feature 접지 33.1% 의 한 원인이다. 이 스크립트가 그 15개를 노드로 세운다.

주입물 (idempotent — 재실행해도 중복되지 않는다):
  - StructuralElement 노드 15 (id · 영문 canonical · 한글 표면형은 synonyms 로)
  - synonyms 15 (lang ko · term_type synonym) — 수확된 표면형 **그대로**, 변형 철자는 넣지 않는다

**synonyms 를 넣는다** — add_superordinate_concepts.py 가 넣지 않은 이유(과대일반화 표면형이
Tier-2 별칭을 가려 expert-tag 가 움직인다)는 여기 해당하지 않는다: 이 표면형은 개념의 이름
그 자체이고, `props.lexicon_profile = "patent-text"` 로 expert-tag 프로파일에서는 살지 않는다.

**R7-DF-CEILING 은 그대로 걸린다.** 15개 중 7개(기판·전극·게이트·적층·소스·드레인·채널)는 A-Box
문서빈도 비율이 0.06 을 넘어 `patent-text` 에서 `blocked` 로 발행된다(사용자 결정 · 1단계).
노드는 어휘 완전성을 위해 등록하고, 접지 효과는 나머지 8개분이다. 예외는 별도 안건이다.

주입 후 `make parse owl convert` 로 schema_report · sdkb-core.ttl · sdkb-core-data.ttl 을 재생성한다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"

_REF = "PLAN-005 §14 (단계 5-B) · CR-001B data/reports/ko_concept_proposals.json basic_terms"
TYPE = "StructuralElement"

# (id, canonical_name(en), ko surface, description)
# 영문 canonical 은 Tier-1 표면형으로 patent-text 에 들어가 US 인용문헌에 닿는다. `source`·`drain`·
# `channel` 은 범용 영단어라 canonical 을 "… Region" 으로 두어 오검출 면을 줄인다(id-local 은 그대로
# 표면형이 되며 R7 이 같은 규칙으로 판정한다).
ELEMENTS: list[tuple[str, str, str, str]] = [
    ("structural_element:substrate", "Substrate", "기판",
     "Substrate on which layers are formed — wafer body or carrier as a structural element."),
    ("structural_element:electrode", "Electrode", "전극",
     "Conductive electrode structure (gate/source/drain/capacitor electrodes in general)."),
    ("structural_element:gate", "Gate", "게이트",
     "Gate structure of a transistor (gate electrode and gate stack)."),
    ("structural_element:stack", "Stacked Structure", "적층",
     "Stacked (laminated) layer structure — multilayer stack as a structural element."),
    ("structural_element:source", "Source Region", "소스",
     "Source region/electrode of a transistor."),
    ("structural_element:drain", "Drain Region", "드레인",
     "Drain region/electrode of a transistor."),
    ("structural_element:channel", "Channel Region", "채널",
     "Channel region of a transistor between source and drain."),
    ("structural_element:wiring", "Wiring", "배선",
     "Interconnect wiring line as a structural element."),
    ("structural_element:wafer", "Wafer", "웨이퍼",
     "Semiconductor wafer as a structural object in a claim."),
    ("structural_element:trench", "Trench", "트렌치",
     "Trench structure formed in a substrate or layer."),
    ("structural_element:spacer", "Spacer", "스페이서",
     "Sidewall spacer structure."),
    ("structural_element:via", "Via", "비아",
     "Vertical via / contact hole structure connecting wiring levels."),
    ("structural_element:capacitor", "Capacitor", "캐패시터",
     "Capacitor structure (e.g. DRAM cell capacitor) as a structural element."),
    ("structural_element:photoresist_layer", "Photoresist Layer", "감광막",
     "Photoresist film/layer as a structural layer — distinct from the photoresist "
     "material nodes (material:photoresist_*): a different level of description."),
    ("structural_element:metal_wiring", "Metal Wiring", "금속배선",
     "Metal interconnect wiring."),
]

NEW_IDS = {nid for nid, *_ in ELEMENTS}


def _node(nid: str, name: str, desc: str) -> dict:
    return {
        "id": nid,
        "type": TYPE,
        "canonical_name": name,
        "description": desc,
        # 이 어휘는 patent-text 프로파일에서만 산다 — expert-tag(전문가·문제 A-Box)는 5-B 의
        # 비목표이고, 사전 원장(tests/test_concept_df_meta.py)의 expert-tag 델타를 0 으로 둔다.
        "props": {"lexicon_profile": "patent-text"},
        "provenance": {
            "source": "author",
            "reference": _REF,
            "license": "CDLA-Permissive-2.0",
            "modified": False,
            "interpretation": "author-defined",
            "validation_required": True,
            "note": "Structural element registered by PLAN-005 stage 5-B; the surface form "
                    "was harvested from KR claim texts (CR-001B) and held back for lack of an axis.",
        },
    }


def _synonym(nid: str, term: str) -> dict:
    return {"node_id": nid, "term": term, "lang": "ko", "term_type": "synonym",
            "source": "ko_concept_proposals.basic_terms"}


def main() -> int:
    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))

    # 재실행 안전: 이 단계가 넣은 것만 걷어내고 다시 넣는다.
    kg["nodes"] = [n for n in kg["nodes"] if n["id"] not in NEW_IDS]
    kg["synonyms"] = [s for s in kg["synonyms"] if s["node_id"] not in NEW_IDS]

    existing_ko = {s["term"] for s in kg["synonyms"] if s.get("lang") == "ko"}
    clash = [ko for _, _, ko, _ in ELEMENTS if ko in existing_ko]
    if clash:
        raise SystemExit(f"ERROR: 한글 표면형이 기존 synonym 과 겹친다: {clash}")

    for nid, name, ko, desc in ELEMENTS:
        kg["nodes"].append(_node(nid, name, desc))
        kg["synonyms"].append(_synonym(nid, ko))

    KG_PATH.write_text(
        json.dumps(kg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✓ nodes +{len(ELEMENTS)} ({TYPE}) → {len(kg['nodes'])}")
    print(f"✓ synonyms +{len(ELEMENTS)} (ko) → {len(kg['synonyms'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
