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

# CR-009 — df 의 문서 모집단. **TTL 이 아니라 `data/**` 를 읽는다**(§1-1: TTL 은 빌드 산출물).
# 두 파일은 A-Box 생성기가 쓰는 것과 **같은 원천**이므로, 여기서 센 df 의 분모는
# 그래프에 실제로 들어간 문서 수와 일치한다(실측 1,000 + 3,513 = 4,513 · CR-008 B층 479 포함 —
# tests/test_concept_df_meta.py 가 핀한다).
SIRP_META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
CITED_ENRICHED = ROOT / "data" / "patents" / "cited_enriched"
DF_REPORT = ROOT / "data" / "reports" / "concept_df_report.json"

PROFILES = ("expert-tag", "patent-text")

# CR-001B — R7-DF-CEILING. A-Box 문서빈도 비율이 이 값을 넘는 표면형은 patent-text 에서
# entries 가 아니라 blocked 로 발행한다. 문턱은 **기존 사전 한글 표면형 154개의 A-Box df
# 90분위 0.0561 을 올림**해 얻었고(CR-001B §9.3), 하류 성능에서 역산하지 않았다.
# 유예: `_r7_grandfathered.surfaces` 에 오른 기존 등재 표면형에는 걸지 않는다.
DF_CEILING = 0.06

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


def suppressions(aliases: dict, profile: str) -> set[tuple[str, str]]:
    """R6 — 이 프로파일에서 끌 (정규화 표면형, node_id) 쌍 (CR-013).

    원천(KG synonyms)에서 지우지 않는 이유: Tier-1 동의어는 프로파일 구분이 없어
    한쪽을 지우면 다른 프로파일과 skos:altLabel·A-Box 추출이 함께 움직인다.
    """
    out: set[tuple[str, str]] = set()
    for surface, per_profile in (aliases.get("_suppress_tier1_surface") or {}).items():
        if surface.startswith("_") or not isinstance(per_profile, dict):
            continue
        for nid in per_profile.get(profile) or []:
            out.add((norm(surface), nid))
    return out


def collect(kg: dict, aliases: dict, profile: str,
            exceptions: set[str],
            df_ratio: dict[str, float] | None = None,
            grandfathered: frozenset[str] = frozenset()) -> tuple[list[dict], list[dict]]:
    """(entries, blocked) — 이 프로파일에서 유효한 표면형 → 개념 매핑.

    df_ratio 가 주어지면 patent-text 에 R7-DF-CEILING 을 건다. 주지 않으면 R7 이 돌지
    않는다 — 표면형 df 를 아직 세지 않은 호출(단위 테스트·진단)에서 조용히 다른 답을
    내지 않게 하기 위해서다.
    """
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
    # R6 — 억제는 후보 확정 **전에** 건다. 뒤에 걸면 ambiguous 플래그가 이미
    # 지워질 후보를 세어 버려, 남은 후보가 하나인데 다의로 발행된다.
    suppress = suppressions(aliases, profile)
    for surface in sorted(acc):
        cands = []
        for nid, (rule, conf, lang) in acc[surface].items():
            axis = node_type[nid]
            if (surface, nid) in suppress:
                blocked.append({"surface": surface, "concept_id": nid,
                                "concept_type": axis,
                                "rule_id": "R6-SURFACE-SUPPRESS"})
                continue
            if (profile == "patent-text" and axis in TASK_AXES
                    and is_short_korean(surface) and surface not in exceptions):
                blocked.append({"surface": surface, "concept_id": nid,
                                "concept_type": axis, "rule_id": "R4-SHORT-KO-TASK"})
                continue
            # R7 — 적용 순서는 R6 → R4 → R7 → R5 다(CR-001B §9.3).
            if (profile == "patent-text" and df_ratio is not None
                    and surface not in grandfathered
                    and df_ratio.get(surface, 0.0) > DF_CEILING):
                blocked.append({"surface": surface, "concept_id": nid,
                                "concept_type": axis, "rule_id": "R7-DF-CEILING",
                                "df_ratio": round(df_ratio.get(surface, 0.0), 4)})
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
    "R6-SURFACE-SUPPRESS": "CR-013 — 사전의 _suppress_tier1_surface 에 오른 (표면형, 개념) "
                           "쌍을 그 프로파일에서만 끈다. 지운 것이 아니라 blocked 로 옮긴 "
                           "것이며, 다른 프로파일과 원천(KG synonyms)·skos:altLabel 은 "
                           "움직이지 않는다. 억제는 R5 의 다의 판정 **앞**에 걸린다.",
    "R7-DF-CEILING": "CR-001B — patent-text 한정. 표면형의 A-Box 문서빈도 비율이 "
                     f"{DF_CEILING} 을 넘으면 entries 가 아니라 blocked 로 발행한다. "
                     "문턱은 기존 사전 한글 표면형 154개의 df 90분위(0.0561)를 올린 값이며 "
                     "하류 성능에서 역산하지 않았다. 넓은 낱말은 비가중 Jaccard 의 교집합과 "
                     "합집합에 동시에 더해져 순위 정보를 희석한다(하류 D-23). 기존 등재 "
                     "표면형에는 소급하지 않는다 — 사전의 _r7_grandfathered 참조.",
    "R5-AMBIGUITY": "한 표면형이 여러 개념에 걸리면 **후보를 지우지 않는다**. 더 특정한 축을 "
                    "앞에 두고(SubProcess > … > Process) 같은 순위는 node_id 사전순으로 "
                    "정렬한 뒤 ambiguous=true 로 표시한다. 어느 하나를 고르는 것은 "
                    "적용기(하류)의 판단이며, 그 판단에 필요한 재료를 전부 넘긴다.",
    "CONFIDENCE": "측정값이 아니라 **출처 강도의 규약**이다: 그래프가 그렇게 부른다=1.0 · "
                  "slug 파생=0.9 · 큐레이션 브리지=0.8.",
}


# ── CR-009 · 개념 단위 메타 (df · 계층) ─────────────────────────────
def load_abox_docs() -> list[str]:
    """A-Box 문서의 정규화 본문. 결정적 — 문서 순서가 df 에 영향을 주지 않는다.

    SIRP 거절특허 1,000 = abstract + claim1 (= TBox 의 abstractText/firstClaimText)
    인용 선행기술 3,034 = abstract + claims  (= 같은 술어)
    """
    import pandas as pd

    docs: list[str] = []
    meta = pd.read_parquet(SIRP_META)
    for _, r in meta.iterrows():
        docs.append(norm(f"{r.get('abstract') or ''} {r.get('claim1') or ''}"))

    # **캐시 전량을 읽는다.** 고정 목록으로 두면 CR-008 이 더한 `*_b_layer.parquet` 이 빠져
    # KR 만 분모에 들어오는 부분 반영이 된다(실측: 4,034 → 4,267 로 233 건만 늘었다).
    # df 의 정의가 "A-Box 문서 중"이므로, A-Box 에 있는 문서는 전부 분모여야 한다.
    frames = []
    kj = CITED_ENRICHED / "kipris.jsonl"
    if kj.exists():
        frames.append(pd.DataFrame([json.loads(x) for x in kj.open()]))
    for pq in sorted(CITED_ENRICHED.glob("*.parquet")):
        frames.append(pd.read_parquet(pq))
    if frames:
        cited = pd.concat(frames, ignore_index=True)
        cited = cited[cited["resolved"] == True].drop_duplicates("cited_doc_id")  # noqa: E712
        for _, r in cited.iterrows():
            docs.append(norm(f"{r.get('abstract') or ''} {r.get('claims') or ''}"))
    return docs


def concept_df(entries: list[dict], docs: list[str]) -> dict[str, int]:
    """개념 IRI → **문서빈도**. 한 문서에서 표면형이 몇 번 나오든 1 이다.

    매칭 단위는 R1 로 정규화한 표면형 **전체의 포함**이다(형태소 분석 없음 · 결정적).
    이것은 df 계산 전용 참조 적용기이며 **하류용 적용기가 아니다** — 하류는 자기
    토큰화로 구현한다(CR-007 분업). 두 값이 얼마나 어긋나는지는 하류가 회신할
    Spearman ρ 가 검정한다(CR-009 성공기준 ②).
    """
    by_concept: dict[str, set[str]] = {}
    for e in entries:
        s = norm(e["surface"])
        if s:
            by_concept.setdefault(e["concept_id"], set()).add(s)
    df = {cid: 0 for cid in by_concept}
    for doc in docs:
        if not doc:
            continue
        for cid, surfaces in by_concept.items():
            if any(s in doc for s in surfaces):
                df[cid] += 1
    return df


def surface_df(surfaces: list[str], docs: list[str]) -> dict[str, int]:
    """표면형 → **문서**빈도. concept_df 와 같은 참조 적용기(정규화 부분문자열)다.

    R7 의 입력이자 하류 특이도 가중의 재료다 — 개념 단위 df 만으로는 어느 표면형이
    넓은지 알 수 없다(한 개념에 넓은 표면형과 좁은 표면형이 함께 달린다).
    """
    counts = {s: 0 for s in surfaces}
    for doc in docs:
        if not doc:
            continue
        for s in surfaces:
            if s in doc:
                counts[s] += 1
    return counts


def surfaces_of(kg: dict, aliases: dict, profile: str, exceptions: set[str]) -> list[str]:
    """R7 판정 전 후보 표면형 — R7 없이 한 번 돌려 얻는다(닭과 달걀 회피)."""
    entries, _ = collect(kg, aliases, profile, exceptions)
    return sorted({e["surface"] for e in entries})


def concept_hierarchy(kg: dict) -> tuple[dict[str, int], dict[str, bool]]:
    """BROADER 엣지 → (depth, is_superordinate). 루트 = 0.

    사이클은 **ValueError** 다 — 조용히 자르면 깊이가 입력 순서에 의존하게 된다.
    """
    parent: dict[str, str] = {}
    children: dict[str, int] = {}
    for e in kg.get("edges", []):
        if str(e.get("predicate", "")).upper() != "BROADER":
            continue
        parent[e["src"]] = e["dst"]
        children[e["dst"]] = children.get(e["dst"], 0) + 1

    def depth_of(nid: str) -> int:
        seen, d, cur = {nid}, 0, nid
        while cur in parent:
            cur = parent[cur]
            if cur in seen:
                raise ValueError(f"BROADER 사슬에 사이클: {nid} → … → {cur}")
            seen.add(cur)
            d += 1
        return d

    ids = [n["id"] for n in kg["nodes"]]
    return ({nid: depth_of(nid) for nid in ids},
            {nid: children.get(nid, 0) > 0 for nid in ids})


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
                   "적용기(linker)는 하류가 구현한다 — 이 파일은 규칙과 사전이다. "
                   "CR-009: profiles[*].concept_meta 는 특이도 가중의 **재료**다. "
                   "df 는 상류가 df 계산 전용 참조 적용기로 센 값이며 하류용 적용기가 "
                   "아니다 — 하류는 자기 토큰화로 구현하고, 두 값의 어긋남은 "
                   "Spearman ρ 로 검정한다. 가중식은 상류가 정하지 않는다.",
        "schema_version": "1.2",
        "source_graph": "data/semiconductor_v0_3.json",
        "profiles": {p: {} for p in PROFILES},
        "rules": RULES,
        "leakage_note": "이 사전은 도메인 어휘(개념 라벨·큐레이션 별칭)에서만 만들었다. "
                        "심사관 인용 정답 문서는 사전 구축 입력이 아니다(CR-007 누출 규율).",
    }

    # CR-009 — 문서 모집단과 계층은 프로파일과 무관하므로 한 번만 읽는다.
    docs = load_abox_docs()
    depth, is_super = concept_hierarchy(kg)

    grandfathered = frozenset(
        norm(s) for s in ((aliases.get("_r7_grandfathered") or {}).get("surfaces") or {}))

    summary = {}
    df_report: dict[str, dict] = {}
    for profile in PROFILES:
        # R7 은 표면형 df 를 입력으로 받으므로 한 번 돌려 후보를 얻은 뒤 센다.
        s_df = surface_df(surfaces_of(kg, aliases, profile, exceptions), docs)
        ratio = {s: (n / len(docs) if docs else 0.0) for s, n in s_df.items()}
        entries, blocked = collect(kg, aliases, profile, exceptions,
                                   df_ratio=ratio, grandfathered=grandfathered)
        # 그 프로파일의 개념 **전량**이 키를 갖는다 — 빠지면 하류가 "없음"과 "0"을
        # 구별할 수 없고, 없음을 최대 특이도로 오해한다.
        df = concept_df(entries, docs)
        asset["profiles"][profile] = {
            "entries": entries,
            "blocked": sorted(blocked, key=lambda b: (b["surface"], b["concept_id"])),
            "surface_meta": {
                # CR-001B — 표면형 단위 df. R7 의 근거이자 하류 특이도 가중의 재료다.
                "df_denominator": len(docs),
                "df_ceiling": DF_CEILING,
                "grandfathered": sorted(grandfathered),
                "surfaces": {s: s_df[s] for s in sorted(s_df)},
            },
            "concept_meta": {
                # 분모를 프로파일 안에 둔다 — 지금은 두 프로파일이 같지만, 같다는 보장이
                # 스키마에 없으면 하류가 가정하게 된다.
                "df_denominator": len(docs),
                "concepts": {
                    cid: {"df_abox": df[cid],
                          "depth": depth.get(cid, 0),
                          "is_superordinate": bool(is_super.get(cid, False))}
                    for cid in sorted(df)
                },
            },
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
        # CR-009 설계 D3·D4 — 자산 스키마에 플래그를 만들지 않고 리포트에 낸다.
        nz = {c: v for c, v in df.items() if v > 0}
        df_report[profile] = {
            "df_denominator": len(docs),
            "concepts": len(df),
            "concepts_with_df_gt0": len(nz),
            "concepts_with_df_0": len(df) - len(nz),
            "top30": sorted(df.items(), key=lambda x: (-x[1], x[0]))[:30],
            "superordinates": sorted(c for c in df if is_super.get(c)),
            "depth_distribution": {
                str(d): sum(1 for c in df if depth.get(c, 0) == d)
                for d in sorted({depth.get(c, 0) for c in df})},
            "d20_affected_note": (
                "D-20 — CR-013 에서 해소. 단독 'hf'(→ material:hf_acid) 와 'high k'"
                "(→ material:hfO2) 를 patent-text 에서 R6 로 끄고, 'high k' 는 상위 부류 "
                "material:dielectric 로 재지정했다. 재지정이 아니라 제거인 이유는 정규화가 "
                "대소문자를 지워 Hf/HF 가 사전 층에서 갈리지 않기 때문이다(CR-013 §3.2). "
                f"현재 df: hf_acid={df.get('material:hf_acid', 0)} · "
                f"hfO2={df.get('material:hfO2', 0)} · "
                f"dielectric={df.get('material:dielectric', 0)}. "
                "주의 — 이 참조 적용기는 단어경계가 없는 부분문자열 포함이라 df 가 하류 값과 "
                "같지 않다(CR-013 §2.6 · 이번 범위 밖)."),
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
        # CR-009 — df 의 원천 두 개를 등재한다. 그래야 A-Box 가 바뀌었을 때
        # 하류의 freshness 증명이 "df 가 낡았다"를 드러낸다.
        "inputs": ["data/semiconductor_v0_3.json", "mappings/abox_term_aliases.json",
                   "data/patents/rejected_patents_meta.parquet",
                   "data/patents/cited_enriched/"],
        "change_request": "CR-007, CR-009, CR-013, CR-001B",
    }
    DF_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DF_REPORT.write_text(json.dumps(df_report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
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
