#!/usr/bin/env python3
"""CQ(역량 질문) 스위트 실행기 — 온톨로지가 무엇에 답할 수 있는지를 재는 도구.

`queries/cq/*.rq` 를 전부 실행해 스위트별 통과율을 낸다. CQ 는 평가 하네스가 아니라
**온톨로지가 답해야 할 것의 명세**, 즉 도메인 자산이다 — 그래서 논문 저장소가 아니라
여기 있어야 하고(CR-016 §3), 그래야 "CQ 스위트를 공개한다"는 서술이 참이 된다.

각 `.rq` 파일 첫머리 주석이 메타데이터다(하류 게이트와 **같은 규약**을 쓴다 — 규약이
갈리면 같은 파일이 위아래에서 다른 뜻이 된다):

    # desc: <자연어 질문>
    # suite: <pa|em|tf|core>   태스크 스위트. 라벨 없는 파일은 기본값으로 떨어지지 않고 **에러**다
    # monotone: <up|down|flat> 회귀 방향
    # expect-min: <최소 결과 행 수, 기본 1>

**판정은 존재검사다** — `rows >= expect-min` 이면 통과. 분포검사(기준 세대 대비 하락)는
하류 게이트(T3)의 몫이고 여기서 흉내 내지 않는다. 같은 이름의 다른 판정을 만들면
상류 통과율과 하류 T3 값을 대조할 수 없게 된다.

엔진은 rdflib 다. 추론은 쓰지 않는다 — 질의가 필요한 층위를 명시적으로 열도록 쓰여 있다.

CLI:
    python scripts/run_cq.py                       # 기본 그래프 조합
    python scripts/run_cq.py --data a.ttl b.ttl    # 그래프 직접 지정
    python scripts/run_cq.py --min-pass 1.0        # 통과율 미달이면 exit 1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
CQ_DIR = ROOT / "queries" / "cq"
OUT_REPORT = ROOT / "data" / "reports" / "cq_report.json"

VALID_SUITES = ("pa", "em", "tf", "core")

# 기본 그래프 — 있는 것만 싣는다. A-Box 는 gitignore 된 빌드 산출물이라 빈 체크아웃에는
# 없고, 그때는 T-Box 만으로 도는 것이 맞다(무엇이 비어 있어서 무엇이 실패하는지가 보인다).
# sdkb-abox-claim-features.ttl 은 899 MB 라 기본에서 뺀다 — rdflib 인메모리로는 감당이
# 안 되고, 그것이 필요한 CQ 는 --data 로 명시해서 돌린다.
DEFAULT_DATA = [
    ROOT / "ontology" / "sdkb-core.ttl",
    ROOT / "ontology" / "sdkb-core-data.ttl",
    ROOT / "ontology" / "sdkb-patent.ttl",
    ROOT / "ontology" / "sdkb-governance.ttl",
    ROOT / "ontology" / "sdkb-governance-kr.ttl",
    # 수출통제 CQ(23·24·25·26)는 **인스턴스**를 본다. 두 파일은 gitignore 된 빌드
    # 산출물이라 빈 체크아웃에는 없고, 그때 이 넷은 0행으로 실패한다 — 온톨로지의
    # 결함이 아니라 **아직 안 지은 A-Box** 다. 리포트의 graph_files_missing 이 그것을 말한다.
    ROOT / "ontology" / "sdkb-governance-kr-instances.ttl",
    ROOT / "ontology" / "sdkb-governance-us-instances.ttl",
    ROOT / "ontology" / "sdkb-abox-experts-problems.ttl",
    ROOT / "ontology" / "sdkb-abox-patents.ttl",
    ROOT / "ontology" / "sdkb-abox-vendors.ttl",
    ROOT / "ontology" / "sdkb-abox-b-layer-queries.ttl",
    # PLAN-005 단계 4·5-A — 선행기술 판단층. T-Box 셋은 커밋된 파일이고, A-Box 는
    # gitignore 된 빌드 산출물이다(`make abox-priorart`). 없으면 CQ32 가 0행으로 실패하며
    # 그것은 온톨로지 결함이 아니라 **아직 안 지은 A-Box** 다.
    # 비용 실측(2026-09-07): A-Box 675,934 트리플 · 53 MB → 기본 그래프 730,214 트리플,
    # `make cq` 전체 2분 47초. 899 MB 를 뺀 사유와는 자릿수가 다르다.
    ROOT / "ontology" / "sdkb-priorart-core.ttl",
    ROOT / "ontology" / "sdkb-priorart-semi.ttl",
    ROOT / "ontology" / "sdkb-priorart-kr.ttl",
    ROOT / "ontology" / "sdkb-abox-priorart.ttl",
]


@dataclass
class CQ:
    name: str
    desc: str
    suite: str
    monotone: str
    expect_min: int
    query: str


@dataclass
class Result:
    name: str
    suite: str
    rows: int
    expect_min: int
    passed: bool
    seconds: float
    error: str | None = None


@dataclass
class SuiteTally:
    total: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)


def parse_cq(path: Path) -> CQ:
    """헤더 주석을 읽는다. 스위트 라벨이 없으면 **에러** — 조용히 분모가 바뀌면 안 된다."""
    meta: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        body = line.lstrip("#").strip()
        if ":" in body:
            k, _, v = body.partition(":")
            meta[k.strip().lower()] = v.strip()
    suite = meta.get("suite")
    if suite not in VALID_SUITES:
        raise SystemExit(
            f"ERROR: {path.name} 의 '# suite:' 라벨이 없거나 알 수 없다 ({suite!r}). "
            f"허용: {VALID_SUITES}. 라벨 없는 파일을 core 로 떨어뜨리지 않는다 — "
            f"분모가 조용히 바뀌면 통과율이 공허해진다."
        )
    return CQ(
        name=path.stem,
        desc=meta.get("desc", ""),
        suite=suite,
        monotone=meta.get("monotone", "up"),
        expect_min=int(meta.get("expect-min", 1)),
        query=path.read_text(encoding="utf-8"),
    )


def load_graph(paths: list[Path]) -> tuple[Graph, list[str], list[str]]:
    g = Graph()
    loaded, missing = [], []
    for p in paths:
        if not p.exists():
            missing.append(str(p.relative_to(ROOT)))
            continue
        g.parse(p, format="turtle")
        loaded.append(str(p.relative_to(ROOT)))
    return g, loaded, missing


def run(g: Graph, cqs: list[CQ]) -> list[Result]:
    out = []
    for cq in cqs:
        t0 = time.time()
        try:
            rows = len(list(g.query(cq.query)))
            out.append(Result(cq.name, cq.suite, rows, cq.expect_min,
                              rows >= cq.expect_min, time.time() - t0))
        except Exception as exc:                      # 질의 오류는 통과가 아니라 실패다
            out.append(Result(cq.name, cq.suite, 0, cq.expect_min, False,
                              time.time() - t0, f"{type(exc).__name__}: {exc}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, nargs="*", default=None,
                    help="질의할 TTL. 생략하면 기본 조합(있는 것만).")
    ap.add_argument("--min-pass", type=float, default=None,
                    help="전체 통과율이 이 값 미만이면 exit 1.")
    ap.add_argument("--report", type=Path, default=OUT_REPORT)
    args = ap.parse_args()

    paths = list(args.data) if args.data else DEFAULT_DATA
    cqs = sorted((parse_cq(p) for p in CQ_DIR.glob("*.rq")), key=lambda c: c.name)
    if not cqs:
        raise SystemExit(f"ERROR: {CQ_DIR} 에 .rq 가 없다.")

    g, loaded, missing = load_graph(paths)
    print(f"[cq] 그래프 {len(g):,} 트리플 · 파일 {len(loaded)}개 적재 · {len(missing)}개 없음")
    for m in missing:
        print(f"      없음: {m}  (빌드: make abox…)")

    results = run(g, cqs)

    tally: dict[str, SuiteTally] = {s: SuiteTally() for s in VALID_SUITES}
    for r in results:
        t = tally[r.suite]
        t.total += 1
        if r.passed:
            t.passed += 1
        else:
            t.failures.append(r.name)

    print(f"\n{'CQ':<40} {'suite':<6} {'rows':>6}  판정")
    for r in results:
        mark = "pass" if r.passed else "FAIL"
        note = f"  ({r.error})" if r.error else ""
        print(f"{r.name:<40} {r.suite:<6} {r.rows:>6}  {mark}{note}")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print("\n[cq] 스위트별 통과율")
    for s in VALID_SUITES:
        t = tally[s]
        rate = t.passed / t.total if t.total else float("nan")
        print(f"      {s:<5} {t.passed:>2}/{t.total:<2} = {rate:.3f}"
              + (f"   실패: {', '.join(t.failures)}" if t.failures else ""))
    overall = passed / total
    print(f"      {'전체':<4} {passed:>2}/{total:<2} = {overall:.3f}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "graph_files_loaded": loaded,
        "graph_files_missing": missing,
        "graph_triples": len(g),
        "n_cq": total,
        "n_passed": passed,
        "pass_rate": round(overall, 4),
        "by_suite": {s: {"total": tally[s].total, "passed": tally[s].passed,
                         "pass_rate": round(tally[s].passed / tally[s].total, 4) if tally[s].total else None,
                         "failures": tally[s].failures} for s in VALID_SUITES},
        "results": [{"name": r.name, "suite": r.suite, "rows": r.rows,
                     "expect_min": r.expect_min, "passed": r.passed,
                     "seconds": round(r.seconds, 3), "error": r.error} for r in results],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cq] 리포트 → {args.report.relative_to(ROOT)}")

    if args.min_pass is not None and overall < args.min_pass:
        print(f"[cq] 통과율 {overall:.3f} < {args.min_pass} — 실패")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
