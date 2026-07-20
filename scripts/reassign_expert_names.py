"""Expert 프로필의 이름 충돌을 해소한다 (110명 전원 고유 이름).

원천 데이터는 이름 풀이 좁아 56개 이름이 110명에 배분되어 있었다. 인스턴스는
전부 서로 다른 프로필인데(완전 중복 레코드 0건) `skos:prefLabel` 문자열만 겹쳐,
라벨만 프로젝션하는 CQ11 이 텍스트상 동일한 행 11건을 내놓았다 — 데이터 중복처럼
보이지만 아니다. 삭제는 진짜 프로필을 없애므로 이름을 재부여한다.

이름은 이미 비식별 변조 단계에서 부여된 가명이므로 교체에 제약이 없다.
**성(姓)은 유지하고 이름만 바꾼다** — EN 파일의 자리표시자("Kang, [Given Name]")가
성만 담고 있어, 성을 보존하면 EN 표기가 그대로 유효하고 로마자 변환표가 필요 없다.

결정적이다: 같은 입력 → 같은 출력. 난수를 쓰지 않고 정렬 순회로만 배정한다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KR_PATH = ROOT / "data" / "experts" / "curated_profiles_kr.json"
EN_PATH = ROOT / "data" / "experts" / "curated_profiles_en.json"

REASSIGNED_AT = "2026-07-20"


def reassign(experts: list[dict]) -> dict[str, tuple[str, str]]:
    """충돌 그룹에서 최소 ID 를 남기고 나머지에 새 이름을 준다.

    반환: expert_id -> (old_name, new_name) — 실제로 바뀐 것만.
    """
    by_name: dict[str, list[str]] = {}
    for e in sorted(experts, key=lambda x: x["expert_id"]):
        by_name.setdefault(e["name"], []).append(e["expert_id"])

    given_pool = sorted({e["name"][1:] for e in experts})
    taken = set(by_name)  # 기존 56개 전부 예약 — 유지되는 이름과도 부딪히면 안 된다
    name_of = {e["expert_id"]: e["name"] for e in experts}

    changes: dict[str, tuple[str, str]] = {}
    for eid in sorted(x for ids in by_name.values() for x in ids[1:]):
        old = name_of[eid]
        surname = old[0]
        for given in given_pool:
            cand = surname + given
            if cand not in taken:
                taken.add(cand)
                changes[eid] = (old, cand)
                break
        else:  # pragma: no cover - 성 23 × 이름 51 이라 고갈될 수 없다
            raise RuntimeError(f"{eid}: 성 {surname} 에 남은 이름이 없다")
    return changes


def main() -> None:
    kr = json.loads(KR_PATH.read_text())
    changes = reassign(kr["experts"])

    for e in kr["experts"]:
        if e["expert_id"] in changes:
            new = changes[e["expert_id"]][1]
            e["name"] = new
            if e.get("name_korean"):
                e["name_korean"] = new

    kr["metadata"]["name_reassignment"] = {
        "date": REASSIGNED_AT,
        "reason": "이름 풀이 좁아 56개 이름이 110명에 배분돼 있었다. 프로필은 전부 "
                  "상이(완전 중복 0건)하나 prefLabel 문자열만 겹쳐 라벨 프로젝션 "
                  "질의가 동일해 보이는 행을 냈다. 삭제 대신 이름을 재부여한다.",
        "method": "충돌 그룹의 최소 expert_id 는 유지, 나머지는 성 보존 + 이름 교체. "
                  "난수 없이 정렬 순회로 배정 — 결정적.",
        "changed_count": len(changes),
        "unique_names_before": 56,
        "unique_names_after": len({e["name"] for e in kr["experts"]}),
        "changes": {k: {"from": v[0], "to": v[1]} for k, v in sorted(changes.items())},
    }
    KR_PATH.write_text(json.dumps(kr, ensure_ascii=False, indent=2) + "\n")

    if EN_PATH.exists():
        en = json.loads(EN_PATH.read_text())
        for e in en["experts"]:
            ch = changes.get(e["expert_id"])
            # EN 은 대부분 "Kang, [Given Name]" 자리표시자라 성 보존으로 이미 유효하다.
            # 다만 일부 레코드는 한글 원본을 그대로 담고 있어 그것만 따라 바꾼다.
            if ch and e.get("name") == ch[0]:
                e["name"] = ch[1]
        en.setdefault("metadata", {})["name_reassignment_synced"] = REASSIGNED_AT
        EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n")

    print(f"재부여 {len(changes)}명 / 고유 이름 "
          f"{len({e['name'] for e in kr['experts']})} / 총 {len(kr['experts'])}명")


if __name__ == "__main__":
    main()
