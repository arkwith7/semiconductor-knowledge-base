"""큐레이션된 한국어 별칭을 개념 어휘로 승격한다 (mappings → data/semiconductor_v0_3.json).

`mappings/abox_term_aliases.json` 은 자유 텍스트 태그를 노드 ID 로 잇는 **브리지 층**으로
만들어졌고, 그래서 전문가·실무문제 적재에서만 쓰였다. 그 결과 큐레이션된 한국어 용어
100개가 그래프에 **실리지 않은 채** 남아 있었다 — 온톨로지는 '식각'은 알아듣고
'플라즈마 식각'은 못 알아듣는 상태였다.

여기서 하는 일은 번역이 아니라 **승격**이다. 새 용어를 만들지 않는다:
이미 큐레이션돼 커밋된 별칭만, 이미 존재하는 노드에만, `synonyms` 로 옮긴다.
`convert_rdf.convert_synonyms` 가 그것을 `skos:altLabel@ko` 로 방출한다.

멱등이다 — 두 번 돌려도 같은 결과다.

    python scripts/promote_korean_aliases.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALIASES = ROOT / "mappings" / "abox_term_aliases.json"
BASELINE = ROOT / "data" / "semiconductor_v0_3.json"

# 승격 대상은 **SubProcess 뿐이다.**
#
# 브리지 태그와 `skos:altLabel` 은 다른 것을 뜻한다 — 전자는 "이 텍스트를 보면 이 노드를
# 떠올려라", 후자는 "이 개념은 이렇게도 불린다". 별칭 사전 전량을 승격하면 그래프가 거짓을
# 주장하게 된다: '플라즈마'가 Skill 의 이름이 되고(플라즈마는 물리 현상이다), '파티클'이
# Process Clean 의 이름이 되며(FailureMode 노드가 따로 있다), '산화물'이 SiO₂ 의 이름이 된다
# (상위어다). Skill 축 21건은 **전부** 이 유형이라 승격 대상이 아니다.
#
# SubProcess 만 남긴 이유는 두 가지다. (1) 이 축은 한국어 별칭이 **0개**였다 — 실제 공백이다.
# (2) 대상 용어가 전부 표준 1:1 대응(원자층증착=ALD, 화학기상증착=CVD)이라 도메인 판정이
# 필요 없다. Process·Material 축의 증분은 상하위 관계 판정(패터닝⊃노광, 도핑⊃이온주입)을
# 요구하므로 사람의 검수를 거쳐 별도로 다룬다.
PROMOTE_PREFIXES = ("subprocess",)

# 축이 맞아도 **의미가 어긋나는** 것은 뺀다. 별칭 사전이 태깅용으로는 옳지만
# 개념의 이름은 아닌 경우다.
EXCLUDE_TERMS = {
    "극자외선": "광원(EUV)이지 공정이 아니다 — EUV Lithography 의 이름이 아니다",
    "하드마스크": "재료·구조지 공정이 아니다 — Hardmask Etch 의 이름이 아니다",
}

# 이 승격분의 출처. 값을 지어내지 않는다 — 별칭 사전 자체가 저장소에 커밋된 큐레이션 기록이고,
# 그 파일의 `_comment` 가 채택 정책(보수적·감사 가능)을 명시하고 있다.
SOURCE = "sdkb_curation_ko"


def is_korean(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def load_alias_pairs() -> list[tuple[str, str]]:
    """[(용어, node_id)] — 한국어이고 승격 대상 축인 것만. 주석 항목은 걸러낸다."""
    raw = json.loads(ALIASES.read_text(encoding="utf-8"))
    out = []
    for term, node in raw.items():
        # 프로파일 객체({"expert-tag": …, "patent-text": …}, CR-007)는 승격하지 않는다.
        # 그 항목들은 축이 프로파일마다 다르다 — 어느 한쪽을 개념의 이름(altLabel)으로
        # 올리면 다른 프로파일에서 그래프가 거짓을 주장하게 된다(이 파일 상단 doctrine).
        if isinstance(node, dict):
            continue
        if not isinstance(node, str) or ":" not in node:
            continue  # `_comment` 류
        prefix = node.split(":", 1)[0]
        if prefix not in PROMOTE_PREFIXES or not is_korean(term):
            continue
        if term in EXCLUDE_TERMS:
            continue
        out.append((term, node))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 무엇이 바뀔지만 보고")
    args = ap.parse_args()

    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    known_nodes = {n["id"] for n in data["nodes"]}
    synonyms = data["synonyms"]
    existing = {(s["node_id"], s["term"]) for s in synonyms}

    added: list[dict] = []
    skipped: Counter = Counter()
    for term, node in load_alias_pairs():
        if node not in known_nodes:
            skipped["대상 노드 없음"] += 1
            continue
        if (node, term) in existing:
            skipped["이미 있음"] += 1
            continue
        added.append(
            {
                "node_id": node,
                "term": term,
                "lang": "ko",
                "term_type": "synonym",
                "source": SOURCE,
            }
        )
        existing.add((node, term))

    by_axis = Counter(a["node_id"].split(":", 1)[0] for a in added)
    print(f"[승격] 신규 {len(added)}건  축별 {dict(by_axis)}")
    print(f"[생략] {dict(skipped)}")
    for a in added[:10]:
        print(f"    {a['node_id']:32} ← {a['term']}")
    if len(added) > 10:
        print(f"    … 외 {len(added) - 10}건")

    if args.dry_run or not added:
        return

    synonyms.extend(added)
    # 승격분의 출처를 선언한다. 노드 단위 provenance 는 이 용어들의 출처가 아니므로
    # (노드는 semikong, 용어는 이 저장소의 큐레이션) 별도 항목으로 남긴다.
    data.setdefault("provenance_sources", {})[SOURCE] = {
        "full_name": "SDKB Korean term curation (bridge alias table)",
        "reference": "mappings/abox_term_aliases.json — conservative, audited Korean alias curation",
        "license": "CDLA-Permissive-2.0",
        "url": "https://github.com/arkwith7/sdkb",
        "data_format": "JSON (term → node id)",
        "note": "KIPRIS/SIRP 국문 명세에 걸리도록 큐레이션된 한국어 표기. 번역 생성이 아니라 승격.",
    }
    BASELINE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[기록] {BASELINE.relative_to(ROOT)} · synonyms {len(synonyms)}건")


if __name__ == "__main__":
    main()
