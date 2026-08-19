"""결함 주입 — 게이트 판별력(H1)의 직접 검정 입력 (원고 §4.10 · PLAN-020 W4).

정상 그래프(G₀)에 **통제된 결함**을 주입해 "어느 층이 이 결함을 잡는가"를 실측한다. 결함군은
원고 §4.10 표의 12종이며 세 층으로 설계돼 있다 — (i) 형식 검증(L0–L3)이 잡아야 할 것,
(ii) 게이트 태스크 성능(T1·T2)이 잡아야 할 의미 결함, (iii) **교차 태스크(T3)만 잡을 수 있는 것**.
마지막 2종(동의어 오병합·공유 계층 역전)이 L0–L3·T1·T2 를 통과하고 T3 에서만 걸리면 H1 지지다.

**W9 홀드아웃(PLAN-025 · 동결 `a474126`)에서 교차결함 3종(F13·F14·F15)이 추가됐다.** 판정 규칙은
바뀌지 않는다 — 추가된 것은 데이터(아직 판정한 적 없는 결함 인스턴스)뿐이며, 이 3종의 조작 술어는
주 태스크(pa) CQ 가 읽는 술어와 **교집합이 공집합**임을 테스트가 `.rq` 정적 추출로 강제한다.

**오염 규율(사용자 요구 2026-07-28).** 이 모듈은 정본을 **절대 쓰지 않는다**. 입력 그래프는 읽기
전용으로 열고, 결함본은 `validate.quarantine` 이 발급한 격리 디렉터리에만 쓴다. 러너는 매
인스턴스 뒤 정본 해시를 재검증한다(`quarantine.verify_pristine`).

**결정성(F16).** 결함마다 `seed = hash(fault_key, strength, rep)` 로 고정하고, 후보 트리플은
정렬 후 표본한다 — 같은 (결함·강도·반복)은 언제 돌려도 같은 그래프를 낸다.

**강도.** 1%/5%/10% 는 **적격 단위 수 대비 비율**이며 `n = max(1, round(rate·N))` 이다. 하한 1 을
두는 이유는 Skill 12개·hasSubprocess 38개처럼 모수가 작은 축에서 1% 가 0 이 되어 "결함 없는
결함 주입"이 되는 것을 막기 위해서다. 이 규칙은 결과를 보기 전에 고정했다.

CLI: `python -m sdkb_paper.validate.fault_inject --list`
"""
from __future__ import annotations

import argparse
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

from pyoxigraph import DefaultGraph, NamedNode, Quad, RdfFormat, Store

from .. import config

ONT = str(config.ONT)
SKOS = "http://www.w3.org/2004/02/skos/core#"
RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_SUBCLASS = NamedNode("http://www.w3.org/2000/01/rdf-schema#subClassOf")

# 코퍼스가 문서 피처로 읽는 개념 술어 (corpus.assemble.CONCEPT_PROPS 와 같은 목록)
CONCEPT_PROPS = ("realizesProcess", "involvesProcess", "concernsDevice",
                 "involvesMaterial", "concernsSkill", "exhibitsFailureMode")
DOC_TYPES = ("Patent", "RejectedPatent", "CitedPatent")

STRENGTHS = (0.01, 0.05, 0.10)   # 원고 §4.10 동결


def ont(name: str) -> NamedNode:
    return NamedNode(ONT + name)


def skos(name: str) -> NamedNode:
    return NamedNode(SKOS + name)


def load(path: Path, workdir: Path) -> Store:
    """그래프를 격리 작업공간의 스토어로 적재한다(정본 파일은 읽기만 한다)."""
    store = Store(path=str(workdir / "store"))
    with open(path, "rb") as fh:
        store.bulk_load(fh, format=RdfFormat.TURTLE)
    return store


def dump(store: Store, out: Path) -> Path:
    """Turtle 은 데이터셋(명명그래프)을 못 담으므로 기본 그래프만 명시해 덤프한다."""
    store.dump(str(out), RdfFormat.TURTLE, from_graph=DefaultGraph())
    return out


def _sorted_quads(store: Store, s=None, p=None, o=None) -> list[Quad]:
    """결정적 순회 — 트리플 문자열 정렬. pyoxigraph 반복 순서에 의존하지 않는다."""
    return sorted(store.quads_for_pattern(s, p, o, None),
                  key=lambda q: (str(q.subject), str(q.predicate), str(q.object)))


def _subjects_of_type(store: Store, cls: str) -> list[Quad]:
    """해당 클래스 인스턴스의 rdf:type 쿼드(주어와 **명명그래프**를 함께 들고 다닌다).

    합집합 스토어에서는 추가 트리플이 어느 명명그래프에 들어가는지가 중요하다 — 기본 그래프에
    떨어지면 `GRAPH ?g` 로 도는 뷰 추출이 그 결함을 못 본다.
    """
    return _sorted_quads(store, None, RDF_TYPE, ont(cls))


def _n(rate: float, total: int) -> int:
    """강도 → 적용 단위 수. 하한 1(모수가 작아도 결함이 실제로 들어가게)."""
    return 0 if total == 0 else max(1, round(rate * total))


def _sample(rng: random.Random, items: list, rate: float) -> list:
    k = min(len(items), _n(rate, len(items)))
    return rng.sample(items, k) if k else []


# --- 결함 12종 ----------------------------------------------------------------
# 각 함수: (store, rate, rng) -> stats dict. store 를 제자리에서 변형한다.

def f01_stale_artifact(store: Store, rate: float, rng: random.Random) -> dict:
    """L0 표적 — 그래프 내용은 그대로 두고 **산출물을 낡게** 만든다.

    실제 되돌리기는 러너가 파일 mtime 을 입력보다 이전으로 되돌려 수행한다(파일시스템 사실이라
    트리플로 표현할 수 없다). 여기서는 결함 사실만 선언한다.
    """
    return {"mutation": "none(graph)", "file_level": "backdate_mtime", "n_affected": 1}


def f02_missing_required(store: Store, rate: float, rng: random.Random) -> dict:
    """L1 표적 — 필수 서지 속성(filingDate) 제거."""
    quads = _sorted_quads(store, None, ont("filingDate"), None)
    hit = _sample(rng, quads, rate)
    for q in hit:
        store.remove(q)
    return {"predicate": "filingDate", "n_candidates": len(quads), "n_affected": len(hit)}


def f03_logic_contradiction(store: Store, rate: float, rng: random.Random) -> dict:
    """L2 표적 — 클래스 계층에 순환을 만들고 문서에 상호배타적 타입을 동시 부여한다.

    ⚠️ as-built: SDKB TBox 에는 `owl:disjointWith`·카디널리티 제약이 **하나도 없다**(실측
    2026-07-28). 따라서 이 주입이 L2 에서 검출되지 않아도 그것은 주입 실패가 아니라 **TBox 의
    논리 표면이 비어 있다는 관측**이다 — 결과를 그대로 보고한다(CLAUDE.md §1-2).
    """
    classes = sorted({q.object.value
                      for q in store.quads_for_pattern(None, RDFS_SUBCLASS, None, None)
                      if isinstance(q.object, NamedNode)})
    pairs = _sample(rng, classes, rate)
    for c in pairs:                      # A ⊑ B 가 이미 있는 곳에 B ⊑ A 를 더해 순환을 만든다
        for q in _sorted_quads(store, None, RDFS_SUBCLASS, NamedNode(c)):
            store.add(Quad(NamedNode(c), RDFS_SUBCLASS, q.subject, q.graph_name))
    docs = _sample(rng, _subjects_of_type(store, "Patent"), rate)
    for d in docs:                       # 문서에 개념 클래스 타입을 동시 부여(타입 모순 시도)
        store.add(Quad(d.subject, RDF_TYPE, ont("Process"), d.graph_name))
    return {"n_class_cycles": len(pairs), "n_type_conflicts": len(docs),
            "n_affected": len(pairs) + len(docs),
            "caveat": "TBox 에 disjointWith·카디널리티 제약 0 — L2 검출 표면 자체가 좁다"}


def f04_cq_path_deleted(store: Store, rate: float, rng: random.Random) -> dict:
    """L3 표적 — CQ 필수 경로(개념 라벨) 삭제. 다수 CQ 가 skos:prefLabel 을 요구한다."""
    concepts = _subjects_of_type(store, "Process") + _subjects_of_type(store, "SubProcess")
    hit = _sample(rng, sorted(concepts, key=str), rate)
    n = 0
    for c in hit:
        for q in _sorted_quads(store, c.subject, skos("prefLabel"), None):
            store.remove(q)
            n += 1
    return {"n_concepts": len(hit), "n_labels_removed": n, "n_affected": len(hit)}


def f05_concept_misalignment(store: Store, rate: float, rng: random.Random) -> dict:
    """T1 표적 — 의미 정렬 오류. 문서→공정 링크의 대상을 무관한 공정으로 재배선."""
    quads = _sorted_quads(store, None, ont("realizesProcess"), None)
    targets = sorted({q.object.value for q in quads if hasattr(q.object, "value")})
    hit = _sample(rng, quads, rate)
    for q in hit:
        other = [t for t in targets if t != getattr(q.object, "value", None)]
        if not other:
            continue
        store.remove(q)
        store.add(Quad(q.subject, q.predicate, NamedNode(rng.choice(other)), q.graph_name))
    return {"predicate": "realizesProcess", "n_candidates": len(quads), "n_affected": len(hit)}


def f06_hierarchy_flatten(store: Store, rate: float, rng: random.Random) -> dict:
    """T1(+일부 L3) 표적 — 공정 하위계층 평탄화. hasSubprocess 를 끊어 층을 무너뜨린다."""
    quads = _sorted_quads(store, None, ont("hasSubprocess"), None)
    hit = _sample(rng, quads, rate)
    for q in hit:
        store.remove(q)
    return {"predicate": "hasSubprocess", "n_candidates": len(quads), "n_affected": len(hit)}


def f07_rejection_shuffle(store: Store, rate: float, rng: random.Random) -> dict:
    """T1·T2 표적 — 판단 문맥 치환. 거절근거(rejectedFor) 대상을 질의 간에 섞는다."""
    quads = _sorted_quads(store, None, ont("rejectedFor"), None)
    hit = _sample(rng, quads, rate)
    objs = [q.object for q in hit]
    rng.shuffle(objs)
    for q, o in zip(hit, objs):
        store.remove(q)
        store.add(Quad(q.subject, q.predicate, o, q.graph_name))
    return {"predicate": "rejectedFor", "n_candidates": len(quads), "n_affected": len(hit)}


def f08_metadata_deleted(store: Store, rate: float, rng: random.Random) -> dict:
    """T1(약한 신호) 표적 — 분류코드·출원인 메타데이터 삭제."""
    n = 0
    for pred in ("hasCPC", "hasIPC", "assignedTo"):
        quads = _sorted_quads(store, None, ont(pred), None)
        for q in _sample(rng, quads, rate):
            store.remove(q)
            n += 1
    return {"predicates": ["hasCPC", "hasIPC", "assignedTo"], "n_affected": n}


def f09_temporal_leak(store: Store, rate: float, rng: random.Random) -> dict:
    """누출 감사 표적 — 질의 이후 공개된 문서에서만 얻을 수 있는 개념 링크를 질의에 삽입.

    질의(RejectedPatent)에 그 질의의 **심사관 정답 문서**가 가진 개념을 복사해 붙인다. 정답을
    보지 않고는 만들 수 없는 링크이므로 시점·정답 양쪽으로 오염된 피처다.
    """
    queries = _subjects_of_type(store, "RejectedPatent")
    hit = _sample(rng, queries, rate)
    n = 0
    for q in hit:
        golds = [x.object for x in _sorted_quads(store, q.subject, ont("hasPriorArtExaminer"), None)]
        for g in golds[:1]:
            for prop in CONCEPT_PROPS:
                for c in _sorted_quads(store, g, ont(prop), None):
                    store.add(Quad(q.subject, ont(prop), c.object, q.graph_name))
                    n += 1
    return {"n_queries": len(hit), "n_links_added": n, "n_affected": len(hit)}


def f10_qrel_leak(store: Store, rate: float, rng: random.Random) -> dict:
    """누출 감사 표적 — 정답 인용 간선 자체를 **개념 링크로 위장**해 검색 피처에 복원한다.

    `hasPriorArtExaminer` 의 대상 문서를 `realizesProcess` 의 객체로 붙인다. 술어 이름 기반
    검사는 통과하므로, 이 결함을 잡으려면 "개념 자리에 문서가 들어왔는가"를 봐야 한다(G-1).
    """
    quads = _sorted_quads(store, None, ont("hasPriorArtExaminer"), None)
    hit = _sample(rng, quads, rate)
    for q in hit:
        store.add(Quad(q.subject, ont("realizesProcess"), q.object, q.graph_name))
    return {"n_candidates": len(quads), "n_affected": len(hit),
            "disguise": "hasPriorArtExaminer → realizesProcess"}


def f11_synonym_merge(store: Store, rate: float, rng: random.Random) -> dict:
    """**교차결함(T3 표적)** — 유사 Skill/Material 개념을 강제 병합.

    B 를 가리키던 모든 참조를 A 로 돌리고 B 의 자체 트리플을 지운다. 검색에는 무해하거나 오히려
    유리할 수 있다(개념 겹침이 늘어난다) — 그래서 T1 이 못 잡고 T3(전문가매칭 CQ)만 잡아야 한다.
    """
    merged = []
    for cls in ("Skill", "Material"):
        items = _subjects_of_type(store, cls)
        k = min(len(items) // 2, _n(rate, len(items)))
        pool = list(items)
        rng.shuffle(pool)
        for i in range(k):
            a, b = pool[2 * i].subject, pool[2 * i + 1].subject
            for q in _sorted_quads(store, None, None, b):        # 참조를 A 로 이전
                store.remove(q)
                store.add(Quad(q.subject, q.predicate, a, q.graph_name))
            for q in _sorted_quads(store, b, None, None):        # B 자체 소멸
                store.remove(q)
            merged.append({"class": cls, "kept": a.value, "removed": b.value})
    return {"n_merges": len(merged), "merges": merged, "n_affected": len(merged)}


def f12_hierarchy_inversion(store: Store, rate: float, rng: random.Random) -> dict:
    """**교차결함(T3 표적)** — 공유 계층의 부모–자식 역전(hasSubprocess 방향 뒤집기).

    상하위가 뒤집혀도 링크 수는 그대로라 구조 검증은 통과한다. 기술예측·전문가매칭 CQ 가
    계층 방향에 의존하면 T3 에서 걸린다.
    """
    quads = _sorted_quads(store, None, ont("hasSubprocess"), None)
    hit = _sample(rng, quads, rate)
    for q in hit:
        store.remove(q)
        store.add(Quad(q.object, q.predicate, q.subject, q.graph_name))
    return {"predicate": "hasSubprocess", "n_candidates": len(quads), "n_affected": len(hit)}


# --- W9 홀드아웃 신규 교차결함 3종 (PLAN-025 §3.2 · 사전등록 동결 후 구현) -------
# 교차성을 **결과가 아니라 구성**으로 보증한다: 아래 술어 집합은 pa 스위트(주 태스크) CQ 가
# 참조하는 술어 20개와 교집합이 **공집합**이며, 이는 `queries/cq/*.rq` 정적 추출로 테스트가
# 강제한다(tests/test_holdout_faults.py). 조작 술어는 전량 상류 스냅샷 실물이다(CLAUDE.md §1-6).
CROSS_FAULT_PREDICATES: dict[str, tuple[str, ...]] = {
    "F13": ("hasProcessExpertise", "hasEquipmentExperience", "hasMaterialExpertise", "hasSkill"),
    "F14": ("caseFailureMode",),
    "F15": ("providedBy", "madeBy"),
}
HUB_K = 2          # 허브 집중화가 몰아넣는 목적지 수 (술어·타입군당)


def _pooled_quads(store: Store, preds: tuple[str, ...]) -> list[Quad]:
    """여러 술어의 후보를 **풀링**해 정렬한다 (PLAN-025 §0 개정 3).

    술어별로 따로 표본하면 희소 술어(`hasMaterialExpertise` N=5)에서 `_n` 하한 1 때문에 강도
    격자가 1/1/1 로 붕괴해 강도 단조성을 잴 수 없다. 풀링하면 강도가 총량에 걸린다.
    """
    quads: list[Quad] = []
    for p in preds:
        quads += list(store.quads_for_pattern(None, ont(p), None, None))
    return sorted(quads, key=lambda q: (str(q.subject), str(q.predicate), str(q.object)))


def _type_sig(store: Store, node) -> tuple[str, ...]:
    """개체의 rdf:type 서명. 이 서명이 같은 개체끼리만 바꿔치기해 **range 를 보존**한다."""
    return tuple(sorted(str(q.object) for q in store.quads_for_pattern(node, RDF_TYPE, None, None)))


def _rewire(store: Store, hit: list[Quad], pool_of, rng: random.Random) -> dict:
    """간선의 **객체만** 바꾼다 — 링크 수는 보존한다(중복이 될 재배선은 건너뛴다).

    왜 중복을 건너뛰는가: RDF 는 집합이라 (s,p,hub) 가 이미 있으면 제거+추가가 간선 1개를
    **없앤다**. 그러면 결함이 "분포 왜곡"이 아니라 "삭제"가 되어 표적 층이 달라진다. 건너뛴
    수는 stats 에 남긴다 — 조용한 절단은 금지다(CLAUDE.md §8).
    """
    n_rewired = n_skipped = 0
    for q in hit:
        cands = [o for o in pool_of(q) if str(o) != str(q.object)]
        rng.shuffle(cands)
        tgt = next((o for o in cands
                    if not list(store.quads_for_pattern(q.subject, q.predicate, o, None))), None)
        if tgt is None:
            n_skipped += 1
            continue
        store.remove(q)
        store.add(Quad(q.subject, q.predicate, tgt, q.graph_name))
        n_rewired += 1
    return {"n_rewired": n_rewired, "n_skipped_collision": n_skipped}


def f13_expertise_hub_collapse(store: Store, rate: float, rng: random.Random) -> dict:
    """**교차결함(T3·em 표적)** — 전문가 역량 간선을 소수 **허브**로 몰아 조인 분포를 붕괴시킨다.

    간선 수를 보존하고 객체만 **같은 타입 서명 안에서** 바꾸므로 SHACL(L1)의 range 제약을
    통과하고, TBox 에 disjointness 가 없어 L2 도 무반응이며(PLAN-025 §3.3a), pa 스위트 CQ 는
    이 술어를 하나도 읽지 않는다. 검색 피처는 개념·IPC 라 T1 도 무영향이다 — 남는 것은
    전문가매칭 CQ 의 **분포**뿐이다.
    """
    preds = CROSS_FAULT_PREDICATES["F13"]
    quads = _pooled_quads(store, preds)
    hubs: dict[tuple, list] = {}
    for q in quads:
        hubs.setdefault((str(q.predicate), _type_sig(store, q.object)), []).append(q.object)
    for k, objs in hubs.items():        # 허브 = 그 (술어·타입군)에서 사전순 앞 HUB_K 개 (결정적)
        hubs[k] = sorted({str(o): o for o in objs}.values(), key=str)[:HUB_K]
    hit = _sample(rng, quads, rate)
    st = _rewire(store, hit, lambda q: hubs[(str(q.predicate), _type_sig(store, q.object))], rng)
    return {"predicates": list(preds), "pooled": True, "hub_k": HUB_K,
            "n_candidates": len(quads), "n_affected": len(hit), **st}


def f14_case_failuremode_rewire(store: Store, rate: float, rng: random.Random) -> dict:
    """**교차결함(T3·em 표적)** — 전문가 사례–결함모드 간선을 FailureMode 풀 안에서 재배치.

    객체가 `ont:FailureMode` 로 남으므로 `expert_shape.ttl` 의 `sh:class` 를 통과한다. F11(노드
    병합)과 **다른 축**(간선 재배치)이라 판정 규칙이 특정 결함에 맞춰진 게 아님을 잰다. CQ28 의
    `?case ont:caseFailureMode ?fm` 조인이 특허↔전문가 다리를 끊는다.
    """
    quads = _pooled_quads(store, CROSS_FAULT_PREDICATES["F14"])
    pool = sorted({str(q.object): q.object for q in quads}.values(), key=str)
    hit = _sample(rng, quads, rate)
    st = _rewire(store, hit, lambda q: list(pool), rng)
    return {"predicates": ["caseFailureMode"], "n_candidates": len(quads),
            "n_pool": len(pool), "n_affected": len(hit), **st}


def f15_supply_direction_flip(store: Store, rate: float, rng: random.Random) -> dict:
    """**교차결함(T3·core 표적)** — 밸류체인 공급관계의 방향을 뒤집는다(`providedBy`·`madeBy` 풀링).

    링크 수 불변 · 두 술어는 `queries/shapes/` 에 제약이 없어 L1 미제약 · TBox 에 disjointness 가
    0 이라 L2 도 모순을 못 만든다(§3.3a). core CQ13·14 가 방향에 의존하면 T3 에서 걸린다.
    """
    preds = CROSS_FAULT_PREDICATES["F15"]
    quads = _pooled_quads(store, preds)
    hit = _sample(rng, quads, rate)
    n_flipped = n_skipped = 0
    for q in hit:
        if list(store.quads_for_pattern(q.object, q.predicate, q.subject, None)):
            n_skipped += 1               # 역방향이 이미 있으면 뒤집기가 간선을 지운다 — 건너뛴다
            continue
        store.remove(q)
        store.add(Quad(q.object, q.predicate, q.subject, q.graph_name))
        n_flipped += 1
    return {"predicates": list(preds), "pooled": True, "n_candidates": len(quads),
            "n_affected": len(hit), "n_flipped": n_flipped, "n_skipped_collision": n_skipped}


# --- 정상 델타 (위양성률 분모 · 결함이 아니다) --------------------------------
# 게이트가 **거부하면 안 되는** 변경이다. 여기서 거부가 나오면 그것이 위양성이다.

def n01_real_merge_subdelta(store: Store, rate: float, rng: random.Random) -> dict:
    """실제 병합 이력에서 온 무해 부분델타 — G₁ 에만 있는 트리플의 층화 부분집합을 G₀ 에 더한다.

    ⚠️ **T1·T2 에 대해서는 구조적으로 공허하다**(주입 전 실측으로 확인): 검색이 보는 뷰는
    G₀∪G₁∪G₂ 이고 이 트리플들은 **이미 G₁ 에 있다** — 합집합이 변하지 않으므로 성능층은
    아무것도 보지 못한다. 그래서 형식층(L0–L3·T3)의 위양성만 이 델타로 재고, 성능층은
    N02(의미보존 보강)로 잰다. 사전 설계(PLAN-020 §4-다)에서 이 공허성을 발견해 분모를
    둘로 나눴다 — 결과를 보고 바꾼 것이 아니다.
    """
    from .. import config as _c

    src = Store()
    with open(_c.GRAPH_V1, "rb") as fh:
        src.bulk_load(fh, format=RdfFormat.TURTLE)
    new_q = [q for q in src if not store.quads_for_pattern(q.subject, q.predicate, q.object, None)]
    new_q.sort(key=lambda q: (str(q.subject), str(q.predicate), str(q.object)))
    hit = _sample(rng, new_q, rate)
    for q in hit:
        store.add(Quad(q.subject, q.predicate, q.object))
    return {"source": "graph_v1 델타", "n_candidates": len(new_q), "n_affected": len(hit)}


def n02_label_preserving(store: Store, rate: float, rng: random.Random) -> dict:
    """의미보존 보강 — 기존 prefLabel 을 altLabel 로 복제한다(SDKB 가 실제로 하는 종류의 보강).

    의미를 바꾸지 않으므로 어느 층도 거부하면 안 된다. N01 과 달리 합집합에도 **새로운**
    트리플이라 T1·T2 가 실제로 판정에 참여한다.
    """
    quads = _sorted_quads(store, None, skos("prefLabel"), None)
    hit = _sample(rng, quads, rate)
    for q in hit:
        store.add(Quad(q.subject, skos("altLabel"), q.object, q.graph_name))
    return {"predicate": "skos:altLabel(복제)", "n_candidates": len(quads),
            "n_affected": len(hit)}


def _signature_index(store: Store) -> tuple[dict, dict]:
    """타입이 붙은 개체 전량의 (나가는·들어오는) 서명. `_dup_groups`·`_fake_dup_groups` 공용.

    한 번의 주사로 둘 다 만든다 — 완전중복군(정당 병합의 근거)과 서명 불일치 쌍(면제 악용
    N03A 의 재료)은 같은 서명표의 앞뒷면이다.
    """
    # **명명 노드만 본다.** 공백노드 라벨은 적재할 때마다 새로 붙으므로(pyoxigraph bulk_load),
    # 정렬 키에 섞이면 같은 시드가 같은 선택을 내지 못한다 — F16 결정성 위반이다. 실측: G₀ 의
    # N03 후보 13군에는 공백노드가 0개라 이 필터는 W4b 격리본 재현에 영향이 없고(대조로 확인),
    # N03A 후보 6,496쌍 중 9쌍이 공백노드였다.
    subjects = {q.subject for q in store.quads_for_pattern(None, RDF_TYPE, None)
                if isinstance(q.subject, NamedNode)}
    sig_of, by_sig = {}, {}
    for s in sorted(subjects, key=str):
        out_sig = tuple(sorted((str(p.predicate), str(p.object))
                               for p in store.quads_for_pattern(s, None, None)))
        in_sig = tuple(sorted((str(p.subject), str(p.predicate))
                              for p in store.quads_for_pattern(None, None, s)))
        sig_of[str(s)] = (out_sig, in_sig)
        by_sig.setdefault((out_sig, in_sig), []).append(s)
    return sig_of, by_sig


def _dup_groups(store: Store) -> list[list]:
    """완전중복 개체군 — N03 의 후보. **정렬·순서를 바꾸면 W4b 격리본 재현이 깨진다.**"""
    _, by_sig = _signature_index(store)
    groups = [g for g in by_sig.values() if len(g) > 1]
    groups.sort(key=lambda g: str(g[0]))
    return groups


def _fake_dup_groups(store: Store) -> list[list]:
    """**서명이 다른** 같은 클래스 개체를 짝짓는다 — N03A(면제 악용)의 후보.

    같은 클래스로 제한하는 이유: 클래스가 다르면 dedup 선언 자체가 육안으로도 거짓이라 규칙의
    구멍을 시험하지 못한다. 어려운 쪽(그럴듯한 위장)을 고른다.
    """
    sig_of, _ = _signature_index(store)
    by_class: dict[str, list] = {}
    for q in _sorted_quads(store, None, RDF_TYPE, None):
        if isinstance(q.subject, NamedNode):        # 공백노드 제외 — 위 결정성 사유와 같다
            by_class.setdefault(str(q.object), []).append(q.subject)
    groups = []
    for _cls, items in sorted(by_class.items()):
        uniq = sorted({str(s): s for s in items}.values(), key=str)
        for i in range(0, len(uniq) - 1, 2):
            a, b = uniq[i], uniq[i + 1]
            if sig_of.get(str(a)) != sig_of.get(str(b)):     # 완전중복이면 제외 — 그건 정당 병합이다
                groups.append([a, b])
    return groups


def _merge_groups(store: Store, groups: list[list]) -> int:
    """개체군을 첫 원소로 병합한다(참조 이전 후 나머지 소멸). 반환 = 제거된 개체 수."""
    n_removed = 0
    for grp in groups:
        keep, rest = grp[0], grp[1:]
        for b in rest:
            for q in _sorted_quads(store, None, None, b):
                store.remove(q)
                store.add(Quad(q.subject, q.predicate, keep, q.graph_name))
            for q in _sorted_quads(store, b, None, None):
                store.remove(q)
            n_removed += 1
    return n_removed


def dedup_selection(store: Store, key: str, rate: float, seed: int) -> list[list[str]]:
    """격리본에 기록되지 않은 **병합쌍을 결정적으로 복원**한다 (PLAN-022 §2 면제 검증 입력).

    같은 (결함·강도·시드)면 주입 때와 같은 쌍이 나온다 — 선택은 정본 G₀ 의 함수이고 표본은
    고정 시드이기 때문이다. 결함을 다시 주입하지 않고도 면제 자동 검증을 돌릴 수 있다.
    """
    selector = {"N03": _dup_groups, "N03A": _fake_dup_groups}.get(key)
    if selector is None:
        return []
    return [[str(m) for m in g]
            for g in _sample(random.Random(seed), selector(store), rate)]


def n03_exact_duplicate_merge(store: Store, rate: float, rng: random.Random) -> dict:
    """**정당 중복 병합** — IRI 를 제외한 트리플 집합이 **완전히 동일한** 개체들을 하나로 합친다.

    v2(분포 검사) 의 진짜 시험대다. N01·N02 는 행 수를 사실상 건드리지 않아 τ 규칙에 무자극인데,
    실제 큐레이션이 하는 정당한 변경 중에는 **행 수를 줄이는 것**이 있다 — 중복 제거가 그것이다.
    게이트가 이것을 거부하면 진짜 개선을 차단하는 것이므로 위양성이다.

    정당성을 **데이터가 자동 검증**한다(트리플 동일성). 라벨 유사도로 동의어를 판정하지 않는다 —
    실측에서 `raon_tech`(㈜라온테크·장비)와 `raontech_inc`(㈜라온텍·설계)는 ASCII 정규화만 같고
    서로 다른 회사였다(PLAN-021 §3). 그런 쌍을 병합했다면 결함을 정상 델타로 라벨해 위양성률을
    조작하는 셈이 된다.

    **서명은 나가는 간선과 들어오는 간선을 모두 본다.** 나가는 쪽만 보면 실측에서 CitedPatent
    12군이 중복으로 잡히는데, 그중 10군은 **인용 주체가 서로 달라** 실제로는 별개 개체다
    (엄격 기준 적용 시 13군·126개체가 남는다). 들어오는 간선까지 같아야 두 개체가 그래프에서
    구별 불가능하고, 그때만 병합이 정보를 잃지 않는다.

    **선택 로직은 `_dup_groups` 로 분리했다** — PLAN-022 재판정이 같은 seed 로 병합쌍을 정확히
    복원해 면제 자동 검증(§2)에 넣어야 하는데 W4b 격리본에는 쌍이 기록돼 있지 않기 때문이다.
    정렬·표본 규칙은 한 글자도 바꾸지 않았다(바꾸면 격리본 재현이 어긋난다).
    """
    groups = _dup_groups(store)
    hit = _sample(rng, groups, rate)
    n_removed = _merge_groups(store, hit)
    return {"criterion": "IRI 제외 트리플 집합 완전 동일", "n_candidates": len(groups),
            "n_affected": len(hit), "n_entities_merged": n_removed,
            "groups": [[str(m) for m in g] for g in hit]}


def n03a_fake_dedup_merge(store: Store, rate: float, rng: random.Random) -> dict:
    """**면제 악용 결함(N03A)** — `delta_type=dedup` 을 선언하되 **완전중복이 아닌** 쌍을 합친다.

    PLAN-022 §2 의 면제 규칙은 델타 단위다 — dedup 을 선언하고 그 안에 다른 변경을 숨기면
    분포검사를 빠져나갈 수 있다. **규칙과 함께 그 구멍도 잰다.** 기대는 자동 검증(`dedup_exempt.
    verify_groups`)이 서명 불일치를 잡아 면제를 불승인하고, 그 결과 일반 델타로 판정돼 검출되는
    것이다. 검증이 통과시키면 그것은 면제 규칙의 결함이며 **그대로 보고한다**(CLAUDE.md §1-2).

    이것은 결함이지 정상 델타가 아니다 — 위양성 분모에 넣지 않는다. 서명이 다른 개체를 합치는
    것은 실제로 정보를 파괴한다.
    """
    groups = _fake_dup_groups(store)
    hit = _sample(rng, groups, rate)
    n_removed = _merge_groups(store, hit)
    return {"criterion": "같은 클래스 · 서명 불일치 쌍(dedup 선언은 거짓)",
            "n_candidates": len(groups), "n_affected": len(hit),
            "n_entities_merged": n_removed,
            "groups": [[str(m) for m in g] for g in hit]}


@dataclass(frozen=True)
class FaultSpec:
    key: str
    label: str          # 원고 §4.10 결함군 이름
    expected: str       # 원고가 예상한 검출층 (사전 예측 — 결과로 고치지 않는다)
    cross_task: bool    # H1 직접 검정 대상(교차결함)인가
    fn: object
    # 델타가 **선언하는** 유형(PLAN-022 §2). "dedup" 은 자동 검증을 통과할 때만 분포검사를
    # 면제받는다 — 선언은 주장일 뿐이고 근거는 데이터다. N03A 는 이 선언이 거짓인 경우다.
    delta_type: str = "generic"

    def inject(self, store: Store, rate: float, seed: int) -> dict:
        return self.fn(store, rate, random.Random(seed))


FAULTS: tuple[FaultSpec, ...] = (
    FaultSpec("F01", "신선도·무결성", "L0", False, f01_stale_artifact),
    FaultSpec("F02", "구조(필수 속성 누락)", "L1", False, f02_missing_required),
    FaultSpec("F03", "논리(순환·타입 모순)", "L2", False, f03_logic_contradiction),
    FaultSpec("F04", "기능(CQ 경로 삭제)", "L3", False, f04_cq_path_deleted),
    FaultSpec("F05", "의미 정렬 오류", "T1", False, f05_concept_misalignment),
    FaultSpec("F06", "계층 평탄화", "T1(+L3)", False, f06_hierarchy_flatten),
    FaultSpec("F07", "판단 문맥 치환", "T1·T2", False, f07_rejection_shuffle),
    FaultSpec("F08", "메타데이터 삭제", "T1(약)", False, f08_metadata_deleted),
    FaultSpec("F09", "시간 누출", "L0/누출감사", False, f09_temporal_leak),
    FaultSpec("F10", "qrel 누출", "누출감사", False, f10_qrel_leak),
    FaultSpec("F11", "동의어 오병합(교차)", "T3", True, f11_synonym_merge),
    FaultSpec("F12", "공유 계층 역전(교차)", "T3", True, f12_hierarchy_inversion),
    # PLAN-025 W9 §3.2 — 홀드아웃 신규 교차결함. 판정 규칙은 한 글자도 바꾸지 않고 **데이터만
    # 새것**이다(F11·F12 두 결함에 맞춘 규칙이 아님을 보이는 일반화 축).
    FaultSpec("F13", "전문가 역량 허브 집중(교차)", "T3(em)", True, f13_expertise_hub_collapse),
    FaultSpec("F14", "전문가 사례–결함모드 재배치(교차)", "T3(em)", True,
              f14_case_failuremode_rewire),
    FaultSpec("F15", "밸류체인 방향 역전(교차)", "T3(core)", True, f15_supply_direction_flip),
    # PLAN-022 §2.1 — 면제 규칙이 새로 여는 구멍을 스스로 잰다. 기대 검출 경로는 면제 자동
    # 검증의 불승인이며, 불승인되면 일반 델타로 판정돼 분포검사를 그대로 받는다.
    FaultSpec("N03A", "면제 악용(거짓 dedup 선언)", "면제검증", False,
              n03a_fake_dedup_merge, delta_type="dedup"),
)

NORMALS: tuple[FaultSpec, ...] = (
    FaultSpec("N01", "정상 델타(실제 병합 부분집합)", "none", False, n01_real_merge_subdelta),
    FaultSpec("N02", "정상 델타(의미보존 보강)", "none", False, n02_label_preserving),
    FaultSpec("N03", "정상 델타(완전중복 병합)", "none", False, n03_exact_duplicate_merge,
              delta_type="dedup"),
)

BY_KEY = {f.key: f for f in FAULTS + NORMALS}


def seed_for(key: str, rate: float, rep: int) -> int:
    """(결함·강도·반복) → 고정 시드. 언제 돌려도 같은 결함 그래프가 나온다.

    파이썬 내장 `hash()` 는 프로세스마다 문자열 해시가 달라져(PYTHONHASHSEED) 재현이 깨진다 —
    sha256 을 쓴다.
    """
    h = hashlib.sha256(f"{key}|{rate:.4f}|{rep}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="결함군 목록과 예상 검출층")
    args = ap.parse_args()
    if args.list:
        print(f"{'키':<5} {'결함군':<24} {'예상 검출층':<14} 교차")
        for f in FAULTS:
            print(f"{f.key:<5} {f.label:<24} {f.expected:<14} {'★' if f.cross_task else ''}")
        print()
        for f in NORMALS:
            print(f"{f.key:<5} {f.label:<24} {'(거부되면 위양성)':<14}")
        print(f"\n강도 {STRENGTHS} · n = max(1, round(rate·N))")


if __name__ == "__main__":
    main()
