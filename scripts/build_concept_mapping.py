#!/usr/bin/env python3
"""CR-007 출력 (1)~(5) — 개념 매핑 자산을 릴리스 산출물로 발행한다.

왜 필요한가. 지금까지 "어떤 표면형이 어떤 개념을 뜻하는가"는 상류 스크립트 안에
흩어져 있었다(build_lexicon · load_aliases · Bridge.extract_from_text). 그래서
하류는 **동결 스냅샷만으로 개념 링크를 재현할 수 없었다**(D-16). 이 생성기는 그
지식을 하나의 파일로 모아 발행한다 — 규칙·신뢰도·규칙 id 를 달고, 프로파일별로.

**분업(CR-007 ⚠).** 상류는 **규칙과 사전**을 낸다. 텍스트에 적용하는 적용기(linker)는
하류가 구현한다 — 하류마다 토큰화·전처리가 다르기 때문이다.

산출: mappings/concept_mapping.json  (+ provenance/PROVENANCE.json 에 sha256 등재)

결정적이다. 같은 입력 → 같은 바이트. 타임스탬프를 넣지 않는 이유가 그것이다
(생성 시각을 넣으면 재실행마다 파일이 달라져 성공기준 ②가 무의미해진다).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
ALIASES_PATH = ROOT / "mappings" / "abox_term_aliases.json"
OUT_PATH = ROOT / "mappings" / "concept_mapping.json"
PROV_PATH = ROOT / "provenance" / "PROVENANCE.json"

PROFILES = ("expert-tag", "patent-text")

# 태스크 축 — 문서가 "무엇에 관한 것인가"가 아니라 "누가 무엇을 할 수 있는가"를
# 담는 축이다. 자유 텍스트(특허 전문)에서 이 축으로 이월되면 축 범주 오류가 된다(D-15).
TASK_AXES = frozenset({"Skill", "RootCause", "Mitigation"})

# 중의성 해소 — 더 특정한 축을 앞에 둔다. 같은 순위면 node_id 사전순(결정성).
# 예: `etch` 가 Process·SubProcess 양쪽에 걸리면 SubProcess 를 먼저 제시한다.
AXIS_RANK = {
    "SubProcess": 0, "Equipment": 1, "Device": 2, "Material": 3,
    "Metrology": 4, "Parameter": 5, "EquipmentClass": 6, "Process": 7,
}

_WS = re.compile(r"[\s/_\-.\(\)]+")
_HANGUL = re.compile(r"[가-힣]")


def norm(s: object) -> str:
    """R1 — lowercase; / _ - . ( ) 와 공백을 단일 공백으로 접는다.

    scripts/build_abox_experts_problems.norm 과 **같은 규칙**이어야 한다.
    두 곳이 갈라지면 상류가 만든 사전과 상류가 만든 A-Box 가 어긋난다.
    """
    return _WS.sub(" ", str(s or "").lower()).strip()


def is_short_korean(surface: str) -> bool:
    """R4 판정 — 공백 없는 ≤4자 한글 표면형인가 (CR-007 결정 ③)."""
    return bool(_HANGUL.search(surface)) and " " not in surface and len(surface) <= 4


def _alias_targets(value: object, profile: str) -> list[str]:
    """프로파일 객체 · 문자열 · 리스트 세 형태를 모두 받는다."""
    if isinstance(value, dict):
        picked = value.get(profile)
        if picked is None:
            return []
        return [picked] if isinstance(picked, str) else list(picked)
    if isinstance(value, str):
        return [value]
    return list(value)


def collect(kg: dict, aliases: dict, profile: str,
            exceptions: set[str]) -> tuple[list[dict], list[dict]]:
    """(entries, blocked) — 이 프로파일에서 유효한 표면형 → 개념 매핑."""
    node_type = {n["id"]: n["type"] for n in kg["nodes"]}
    scoped_out = {
        n["id"] for n in kg["nodes"]
        if (n.get("props") or {}).get("lexicon_profile") not in (None, profile)
    }

    # surface -> {node_id: (rule_id, confidence, lang)}  — 같은 표면형이 여러 경로로
    # 같은 노드를 가리키면 신뢰도가 높은 경로를 남긴다.
    acc: dict[str, dict[str, tuple[str, float, str]]] = {}

    def put(surface: str, nid: str, rule: str, conf: float, lang: str) -> None:
        s = norm(surface)
        if not s or nid not in node_type:
            return
        slot = acc.setdefault(s, {})
        if nid not in slot or conf > slot[nid][1]:
            slot[nid] = (rule, conf, lang)

    # ── R2 Tier-1: 그래프가 개념을 부르는 이름 ──────────────────────────
    for n in kg["nodes"]:
        nid = n["id"]
        if nid in scoped_out:
            continue
        put(n.get("canonical_name"), nid, "T1-CANONICAL", 1.0, "en")
        local = nid.split(":", 1)[1] if ":" in nid else nid
        put(local, nid, "T1-IDLOCAL", 0.9, "und")
        put(local.replace("_", " "), nid, "T1-IDLOCAL", 0.9, "und")
    for s in kg.get("synonyms", []):
        if s["node_id"] in scoped_out:
            continue
        put(s.get("term"), s["node_id"], "T1-SYNONYM", 1.0, s.get("lang", "und"))

    # ── R3 Tier-2: 큐레이션 브리지 (프로파일 해석) ──────────────────────
    for term, value in aliases.items():
        if term.startswith("_"):
            continue
        reassigned = isinstance(value, dict)
        for nid in _alias_targets(value, profile):
            put(term, nid, "T2-ALIAS-REASSIGN" if reassigned else "T2-ALIAS",
                0.8, "und")

    # ── R4 patent-text 한글 단문 → 태스크 축 이월 금지 ──────────────────
    blocked: list[dict] = []
    entries: list[dict] = []
    for surface in sorted(acc):
        cands = []
        for nid, (rule, conf, lang) in acc[surface].items():
            axis = node_type[nid]
            if (profile == "patent-text" and axis in TASK_AXES
                    and is_short_korean(surface) and surface not in exceptions):
                blocked.append({"surface": surface, "concept_id": nid,
                                "concept_type": axis, "rule_id": "R4-SHORT-KO-TASK"})
                continue
            cands.append((AXIS_RANK.get(axis, 99), nid, axis, rule, conf, lang))
        if not cands:
            continue
        cands.sort()
        ambiguous = len({c[1] for c in cands}) > 1
        for _, nid, axis, rule, conf, lang in cands:
            entries.append({
                "surface": surface,
                "lang": lang,
                "concept_id": nid,
                "concept_type": axis,
                "rule_id": rule,
                "confidence": conf,
                "ambiguous": ambiguous,
            })
    return entries, blocked


RULES = {
    "R1-NORMALIZE": "lowercase; '/ _ - . ( )' 와 공백을 단일 공백으로 접고 양끝을 자른다. "
                    "매칭 단위는 정규화된 표면형 전체다(형태소 분석 없음 · 결정적).",
    "R2-TIER1": "그래프가 개념을 부르는 이름 — canonical_name(1.0) · id local(0.9) · "
                "synonym(1.0). props.lexicon_profile 이 걸린 노드는 그 프로파일에서만 나온다.",
    "R3-TIER2": "큐레이션 브리지 사전(0.8). 값이 프로파일 객체면 해당 프로파일 타깃만 쓰고, "
                "null 이면 그 프로파일에서 비활성이다.",
    "R4-SHORT-KO-TASK": "patent-text 한정 — 공백 없는 ≤4자 한글 표면형은 태스크 축"
                        "(Skill·RootCause·Mitigation)으로 이월하지 않는다. "
                        "예외는 사전의 _exceptions_short_ko_task_axis 에 명시한다.",
    "R5-AMBIGUITY": "한 표면형이 여러 개념에 걸리면 **후보를 지우지 않는다**. 더 특정한 축을 "
                    "앞에 두고(SubProcess > … > Process) 같은 순위는 node_id 사전순으로 "
                    "정렬한 뒤 ambiguous=true 로 표시한다. 어느 하나를 고르는 것은 "
                    "적용기(하류)의 판단이며, 그 판단에 필요한 재료를 전부 넘긴다.",
    "CONFIDENCE": "측정값이 아니라 **출처 강도의 규약**이다: 그래프가 그렇게 부른다=1.0 · "
                  "slug 파생=0.9 · 큐레이션 브리지=0.8.",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="쓰지 않고 현재 파일과 같은지만 확인한다(결정성 회귀).")
    args = ap.parse_args()

    kg = json.loads(KG_PATH.read_text(encoding="utf-8"))
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    exceptions = {norm(t) for t in aliases.get("_exceptions_short_ko_task_axis", [])}

    asset = {
        "_README": "CR-007 개념 매핑 자산. 표면형 → 개념 IRI 를 프로파일별로 발행한다. "
                   "적용기(linker)는 하류가 구현한다 — 이 파일은 규칙과 사전이다.",
        "schema_version": "1.0",
        "source_graph": "data/semiconductor_v0_3.json",
        "profiles": {p: {} for p in PROFILES},
        "rules": RULES,
        "leakage_note": "이 사전은 도메인 어휘(개념 라벨·큐레이션 별칭)에서만 만들었다. "
                        "심사관 인용 정답 문서는 사전 구축 입력이 아니다(CR-007 누출 규율).",
    }

    summary = {}
    for profile in PROFILES:
        entries, blocked = collect(kg, aliases, profile, exceptions)
        asset["profiles"][profile] = {
            "entries": entries,
            "blocked": sorted(blocked, key=lambda b: (b["surface"], b["concept_id"])),
        }
        concepts = {e["concept_id"] for e in entries}
        per_concept = {}
        for e in entries:
            per_concept.setdefault(e["concept_id"], set()).add(e["surface"])
        ge3 = sum(1 for v in per_concept.values() if len(v) >= 3)
        axis_share = {}
        for e in entries:
            axis_share[e["concept_type"]] = axis_share.get(e["concept_type"], 0) + 1
        summary[profile] = {
            "surfaces": len({e["surface"] for e in entries}),
            "pairs": len(entries),
            "concepts_covered": len(concepts),
            "concepts_with_ge3_surfaces": ge3,
            "blocked_pairs": len(blocked),
            "task_axis_pairs": sum(v for k, v in axis_share.items() if k in TASK_AXES),
        }

    payload = json.dumps(asset, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    if args.check:
        cur = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        same = cur == payload
        print(f"{'✓' if same else '✗'} deterministic: 재생성 결과가 현재 파일과 "
              f"{'동일' if same else '다름'}")
        return 0 if same else 1

    OUT_PATH.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    prov = json.loads(PROV_PATH.read_text(encoding="utf-8")) if PROV_PATH.exists() else {
        "_README": "릴리스 자산의 무결성 기록. 하류는 이 해시로 자기 스냅샷을 검증한다.",
        "assets": {},
    }
    prov["assets"]["mappings/concept_mapping.json"] = {
        "sha256": digest,
        "generator": "scripts/build_concept_mapping.py",
        "inputs": ["data/semiconductor_v0_3.json", "mappings/abox_term_aliases.json"],
        "change_request": "CR-007",
    }
    PROV_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROV_PATH.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")

    n_concepts = len({n["id"] for n in kg["nodes"]})
    print(f"✓ {OUT_PATH.relative_to(ROOT)}  sha256={digest[:16]}…")
    for profile, s in summary.items():
        pct = 100.0 * s["concepts_with_ge3_surfaces"] / n_concepts
        print(f"  [{profile}] 표면형 {s['surfaces']} · 쌍 {s['pairs']} · "
              f"개념 {s['concepts_covered']}/{n_concepts} · "
              f"표면형≥3 개념 {s['concepts_with_ge3_surfaces']} ({pct:.1f} %) · "
              f"태스크축 쌍 {s['task_axis_pairs']} · 차단 {s['blocked_pairs']}")
    print(f"✓ {PROV_PATH.relative_to(ROOT)} 등재", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
