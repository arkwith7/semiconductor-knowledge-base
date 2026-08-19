"""중복제거 델타 면제 — 자동 검증 (PLAN-022 §2 · 2026-07-28 동결 · 원고 §4.9).

**왜 필요한가.** W4b 에서 승인된 정상 델타 N03(완전중복 개체 병합)이 τ=0 에서 3/27(11.1%)
거부됐다 — 사전등록 위양성 기준 5% 초과다. CQ 분포검사는 **행이 준 이유**를 구분하지 못한다:
지식이 사라진 것과 중복이 정리된 것을 같게 본다. τ 를 올리는 것은 처방이 아니다(검출력이
55→34→18 로 붕괴한다). 그래서 **이유를 델타가 선언하고, 그 선언을 데이터가 검증**한다.

**면제 규칙(동결).**

```
delta_type == "dedup" 이고 verify_groups() 가 통과할 때에만 → 분포검사만 면제
                                                            → 존재검사는 면제하지 않는다
```

**정당성을 사람이 판단하지 않는다.** 두 개체가 병합돼도 정보가 손실되지 않으려면 그래프에서
**구별 불가능**해야 하고, 그것은 나가는 간선과 들어오는 간선이 **모두** 같다는 뜻이다. 라벨
유사도는 근거가 될 수 없다 — 실측에서 `raon_tech`(㈜라온테크·장비)와 `raontech_inc`
(㈜라온텍·설계)는 ASCII 정규화만 같고 **서로 다른 회사**였다(PLAN-021 §3). 그런 쌍을 정상
델타로 라벨했다면 결함을 정상으로 세어 위양성률을 조작하는 셈이 된다.

**들어오는 간선을 함께 보는 이유(실측).** 나가는 쪽만 보면 CitedPatent 12군이 중복으로 잡히는데
그중 10군은 **인용 주체가 서로 달라** 실제로는 별개 개체다.

**이 규칙이 만드는 구멍은 스스로 잰다.** 면제는 델타 단위이므로 dedup 을 선언하고 그 안에
비동일 쌍을 섞으면 분포검사를 빠져나갈 수 있다. 그 시나리오를 결함 `N03A` 로 주입해 실측한다
(PLAN-022 §2.1) — 검증이 못 잡으면 면제 규칙의 결함으로 보고한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from pyoxigraph import NamedNode, RdfFormat, Store

from .. import config


def entity_signature(store: Store, iri: NamedNode | str) -> tuple[tuple, tuple]:
    """(나가는 서명, 들어오는 서명) — IRI 자신을 제외한 트리플 집합.

    두 개체의 서명이 모두 같으면 그래프 안에서 구별 불가능하고, 그때만 병합이 정보를 잃지 않는다.
    """
    # `str(NamedNode)` 는 `<iri>` 형태의 N-Triples 표기를 낸다 — 꺾쇠를 벗겨야 다시 노드가 된다.
    node = iri if isinstance(iri, NamedNode) else NamedNode(str(iri).strip("<>"))
    out_sig = tuple(sorted((str(q.predicate), str(q.object))
                           for q in store.quads_for_pattern(node, None, None)))
    in_sig = tuple(sorted((str(q.subject), str(q.predicate))
                          for q in store.quads_for_pattern(None, None, node)))
    return out_sig, in_sig


def verify_groups(store: Store, groups: list[list[str]]) -> dict:
    """병합 대상 개체군이 **전부** 완전중복인지 검증한다. 하나라도 어긋나면 면제 불승인.

    엄격한 쪽(all-or-nothing)을 택한 이유: 부분 승인은 "어떤 병합은 정당하고 어떤 병합은
    아니다"를 게이트가 판단하는 것이고, 그 판단의 근거가 없다. 선언이 틀렸으면 일반 델타로
    돌려보내 분포검사를 그대로 받게 한다.
    """
    mismatches = []
    for grp in groups:
        if len(grp) < 2:
            continue
        sigs = [entity_signature(store, m) for m in grp]
        if any(s != sigs[0] for s in sigs[1:]):
            mismatches.append([str(m) for m in grp])
    n_groups = sum(1 for g in groups if len(g) >= 2)
    return {"ok": not mismatches, "n_groups": n_groups, "n_mismatch": len(mismatches),
            "mismatches": mismatches[:10],
            "criterion": "IRI 제외 나가는·들어오는 간선 서명 완전 동일"}


def verify_delta(graph_path: Path, groups: list[list[str]], delta_type: str = "generic") -> dict:
    """델타 유형 선언 + 자동 검증 → 면제 승인 여부. `graph_path` 는 **병합 전** 그래프다."""
    if delta_type not in config.DELTA_TYPES:
        raise ValueError(f"델타 유형이 잘못됐다: '{delta_type}' (허용 {config.DELTA_TYPES})")
    if delta_type != "dedup":
        return {"delta_type": delta_type, "exempt": False,
                "reason": "dedup 선언 아님 — 분포검사 그대로 적용"}
    store = Store()
    with open(graph_path, "rb") as fh:
        store.bulk_load(fh, format=RdfFormat.TURTLE)
    v = verify_groups(store, groups)
    return {"delta_type": delta_type, "exempt": v["ok"], "verification": v,
            "reason": "완전중복 검증 통과 — 분포검사 면제" if v["ok"]
                      else f"완전중복 아님 {v['n_mismatch']}군 — 면제 불승인(일반 델타로 판정)"}


def log_exemption(rec: dict) -> None:
    """면제 사용 이력 append. **횟수는 표 6.6 에 보고한다** — 조용한 면제는 게이트를 장식으로
    만든다(T3 waiver 와 같은 규율)."""
    config.CQ_GEN_DIR.mkdir(parents=True, exist_ok=True)
    with config.DEDUP_EXEMPTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def exemption_count() -> tuple[int, int]:
    """(승인된 **고유 델타** 수, 판정 로그 행 수).

    로그는 append-only 이고 승인·불승인을 모두 남기며, 같은 델타를 다시 판정하면 행이 늘어난다
    (재판정 시도·폐기된 run 포함). 행 수를 그대로 "면제 승인 건수"로 읽으면 부풀려진다 —
    그래서 승인분만 (결함·강도·시드)로 중복 제거해 센다. **감사 이력이므로 행은 지우지 않는다.**
    """
    if not config.DEDUP_EXEMPTION_LOG.exists():
        return 0, 0
    lines = [ln for ln in config.DEDUP_EXEMPTION_LOG.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    granted = set()
    for ln in lines:
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("exempt"):
            granted.add((r.get("fault"), r.get("strength"), r.get("seed")))
    return len(granted), len(lines)
