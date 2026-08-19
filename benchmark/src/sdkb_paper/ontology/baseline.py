"""baseline 그래프(graph_v0) 조립 — H1 의 "before".

vendor 한 SDKB 스냅샷(TBox + 도메인 ABox)을 합쳐 `data/processed/graph_v0.ttl` 로 굳힌다.
특허는 한 건도 들어있지 않다 — KIPRIS 보강 델타가 머지되면서 graph_v1 이 되고,
H1 은 v0 대비 v1 의 공정 단계 커버리지 증가를 검정한다.

산출물은 결정적(deterministic)이다: 같은 스냅샷 -> 같은 그래프. 그래서 graph_v0.ttl 자체는
gitignore 두고, 커밋되는 것은 `data/external/sdkb/` 스냅샷 + PROVENANCE.json 이다.

CLI:  python -m sdkb_paper.ontology.baseline
"""
from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, Graph

from sdkb_paper.config import EXTERNAL_SDKB, GRAPH_V0, ONT, bind_namespaces

# TBox 3종 + 도메인 ABox 1종. 순서 = 머지 순서.
BASELINE_PARTS = [
    "sdkb-core.ttl",
    "sdkb-patent.ttl",
    "sdkb-foresight.ttl",
    "sdkb-core-data.ttl",
    "sdkb-abox-patents.ttl",   # SIRP 거절특허 1,000건 — H1 의 before
    # B층 확증분할 질의 200 (CR-012 · D-27 · PLAN-045). 인용 간선 0 이므로 정답지·누출 통제에
    # 아무것도 더하지 않는다 — 더하는 것은 `RejectedPatent` 200 과 그 본문·개념링크뿐이다.
    "sdkb-abox-b-layer-queries.ttl",
    # 심사관 인용 선행기술 (CitedPatent 3,034 + 개념링크). 선행기술조사 정답지를
    # 분석 그래프 안에서 개념 도달 가능하게 만든다. 정답지(hasPriorArtExaminer distinct 2,321)
    # 도달성 (재측정 2026-07-23 · graph_v0 전수): 노드(CitedPatent 타입) 0%→95.3% ·
    # 개념링크는 정의에 따라 곡선 — Process∪Device 54.6% / +material 63.4% / +전의미링크 70.5% /
    # +분류(CPC·IPC) 95.3%. (54.6 vs 63.4 는 "개념링크" 정의차일 뿐 둘 다 실측이다.)
    # CitedPatent ⊑ Patent 이나 명시 타입은 CitedPatent 라 EXPECTED_PATENTS(=1000)는 불변이다.
    "sdkb-abox-prior-art.ttl",
    # 인력·문제 축 (Expert 110 · Problem 226). 상류가 `make abox` 로 만드는데
    # 이 논문이 vendor 하지 않아 G₀ 에서 통째로 빠져 있었다 (PLAN-013 §6.5).
    # 특허를 더하지 않으므로 H1 의 C₀(s) 는 움직이지 않는다 — 그래도 재실행해 확인한다.
    "sdkb-abox-experts-problems.ttl",
    # 소부장 벤더 축 (KSIA 회원사 326). 특허를 더하지 않으므로 C₀(s) 는 움직이지 않는다.
    "sdkb-abox-vendors.ttl",
    # 규제 축 (RQ3 수출통제). TBox 2종 + 인스턴스 2종. 개념에 gov:subjectToControl 을
    # 더할 뿐 특허↔공정 링크를 건드리지 않으므로 C₀(s)·H1 은 불변이어야 한다 — 재실행해 확인한다.
    "sdkb-governance.ttl",
    "sdkb-governance-kr.ttl",
    "sdkb-governance-us-instances.ttl",
    "sdkb-governance-kr-instances.ttl",
    # 상용화 축(TRL·라이선싱) · 자원기반관점(VRIO·역량·진입장벽). 특허↔공정 링크를
    # 건드리지 않는 소규모 TBox/ABox — IP-R&D·기술기획 태스크 어휘를 넓힌다.
    "sdkb-commercialization.ttl",
    "sdkb-rbv.ttl",
]

# G₀ 의 서명. 스냅샷을 의도적으로 갱신하면 바뀐다 — 그때는 data/MANIFEST.md 와
# tests/test_baseline_integration.py 를 같은 커밋에서 고친다.
# 2026-08-08 · PLAN-045: 1,000 → 1,200. A층 SIRP 1,000 + B층 확증분할 200(CR-012).
# **완화가 아니라 승계다** — 기대값을 없애지 않고 층별 내역으로 쪼갠다. 둘 중 하나라도
# 어긋나면 여전히 즉시 멈춘다.
EXPECTED_PATENTS_A = 1000
EXPECTED_PATENTS_B = 200
EXPECTED_PATENTS = EXPECTED_PATENTS_A + EXPECTED_PATENTS_B


def build_baseline(snapshot: Path = EXTERNAL_SDKB, out: Path = GRAPH_V0) -> Graph:
    prov_path = snapshot / "PROVENANCE.json"
    if not prov_path.exists():
        raise SystemExit(
            f"[baseline] 스냅샷이 없다: {snapshot}\n"
            f"           먼저 `make vendor` 를 실행할 것."
        )

    g = Graph()
    bind_namespaces(g)
    for part in BASELINE_PARTS:
        g.parse(snapshot / part, format="turtle")

    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(out, format="turtle")

    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    counts = summarize(g)
    print(f"[baseline] {out}  ({len(g):,} triples)")
    print(f"[baseline] SDKB commit {prov['source_commit'][:12]}")
    print(f"[baseline] Process={counts['Process']}  SubProcess={counts['SubProcess']}  "
          f"Device={counts['Device']}  Patent={counts['Patent']}")
    if counts["Patent"] != EXPECTED_PATENTS:
        raise SystemExit(
            f"[baseline] ✗ G₀ 의 특허가 {counts['Patent']:,}건이다 (기대 {EXPECTED_PATENTS:,}건). "
            f"SIRP ABox 가 빠졌거나 상류가 바뀌었다 — before 가 움직이면 H1 이 재현되지 않는다."
        )
    return g


def summarize(g: Graph) -> dict[str, int]:
    """G₀ 의 관측 단위(공정 계층)·개념 축(디바이스)·특허 수.

    SubProcess ⊑ Process 이므로 명시 타입으로 센다. H1 의 관측 단위는 Process+SubProcess(20),
    H2 의 개념 축은 거기에 Device(31)를 더한 51 이다.
    """
    return {
        name: sum(1 for _ in g.subjects(RDF.type, ONT[name]))
        for name in ("Process", "SubProcess", "Device", "Patent")
    }


def main() -> None:
    build_baseline()


if __name__ == "__main__":
    main()
