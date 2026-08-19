"""Competency Question 러너.

queries/cq/*.rq 를 전부 실행해 통과율을 리포트한다.
각 .rq 파일 첫 줄들의 주석 메타데이터를 해석한다:
    # desc: <자연어 질문>
    # suite: <pa|em|tf|core — 태스크 스위트, T3 의 분모 · PLAN-019 §3.2 동결>
    # monotone: <up|down|flat — 판정 v2 의 회귀 방향 · PLAN-021 §2 동결>
    # expect-min: <최소 결과 행 수, 기본 1>

**판정 규칙 v1 / v2 (PLAN-021 동결).** v1 은 존재검사(`rows ≥ expect-min`)뿐이라 결함이 CQ 를
0행으로 만들어야만 발화했고, 그래서 W4 결함주입에서 T3 가 0/108 을 냈다. v2 는 여기에 **기준
세대 대비 분포검사**를 더한다 — `regress = rows < (1−τ)·base` (극성 up). 극성이 필요한 이유는
CQ03·CQ06 이 **공백 탐색 질의**여서 행 수 감소가 개선이기 때문이다(극성 없이 하락=회귀로 두면
정당한 보강이 게이트에 걸린다). `base_rows` 를 주지 않으면 v1 그대로다(하위호환).

**스위트는 T3(교차 태스크 CQ 비회귀)의 전제다.** 어떤 CQ 가 어느 태스크의 명세인지 파일 안에
적어 두어야 "타 태스크 통과율이 떨어졌는가"를 물을 수 있다(원고 §4.9). 라벨 없는 파일은 `core`
로 떨어지지 않고 **에러**다 — 조용히 분모가 바뀌면 게이트가 공허해진다.

**엔진(PLAN-020 W4-0).** 기본은 `oxigraph` 다 — rdflib 인메모리는 graph_v0(23MB)에서 150초가 걸려
결함주입 108 인스턴스를 감당하지 못한다. 두 엔진은 `--verify-engines` 로 CQ 28개 전량 결과행이
동일함을 확인한 뒤에만 교체됐다(불일치 1건이라도 나오면 게이트 판정이 엔진에 의존한다는 뜻이므로
전환하지 않는다). `--engine rdflib` 로 언제든 되돌릴 수 있다.

CLI:  python -m sdkb_paper.validate.cq_runner <graph.ttl> [--report] [--min-pass 1.0]
      python -m sdkb_paper.validate.cq_runner <graph.ttl> --verify-engines
      통과율 < min-pass 이면 exit code 1 (CI 게이트)
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sdkb_paper.config import (
    CENTRAL_AXIS_PROVENANCE,
    CENTRAL_AXIS_STORE,
    CQ_GATE_TARGET,
    CQ_MONOTONE,
    CQ_SUITES,
    CQ_TARGETS,
    CQ_TAU,
    L3_SUITES,
    QUERIES_CQ,
    ROOT,
    T3_SUITES,
)

ENGINES = ("oxigraph", "rdflib")
DEFAULT_ENGINE = "oxigraph"


@dataclass
class CQResult:
    name: str
    desc: str
    expect_min: int
    rows: int
    suite: str = "core"
    monotone: str = "up"
    target: str = "graph"

    @property
    def in_gate(self) -> bool:
        """L3·T3 판정 분모에 드는가 (PLAN-023 §1 희석 금지).

        사이드카 CQ 는 시험 대상 그래프에 무반응인 상수항이라 게이트 분모에 넣으면 실패를
        희석한다. 측정으로는 보고하되 판정에는 넣지 않는다.
        """
        return self.target == CQ_GATE_TARGET

    @property
    def passed(self) -> bool:
        """v1 존재검사. v2 판정은 기준선이 필요하므로 `judge()` 가 따로 한다."""
        return self.rows >= self.expect_min

    def regressed(self, base_rows: int, tau: float = CQ_TAU) -> bool:
        """기준선 대비 분포 회귀인가 (v2). base=0 이면 비율이 정의되지 않아 항상 False."""
        if base_rows <= 0:
            return False
        if self.monotone == "up":
            return self.rows < (1.0 - tau) * base_rows
        if self.monotone == "down":
            return self.rows > (1.0 + tau) * base_rows
        return abs(self.rows - base_rows) > tau * base_rows

    def judge(self, base_rows: int | None = None, tau: float = CQ_TAU,
              exempt_regress: bool = False) -> bool:
        """v2 통과 판정 = 존재검사 ∧ ¬회귀. base 를 주지 않으면 v1 과 같다.

        `exempt_regress` 는 **중복제거 면제**(PLAN-022 §2)다 — 분포검사만 면제하고 존재검사는
        면제하지 않는다. 중복 병합은 CQ 를 0행으로 만들 수 없으므로(중복이 아닌 개체는 남는다)
        존재검사까지 풀어 줄 근거가 없다.
        """
        if not self.passed:
            return False
        if exempt_regress:
            return True
        return base_rows is None or not self.regressed(base_rows, tau)


def _parse_meta(rq_text: str) -> tuple[str, int, str, str, str]:
    """(desc, expect_min, suite, monotone, target). 라벨 누락·오값은 ValueError(조용한 기본값 금지).

    `# target:` 만은 생략 가능하며 기본이 `graph` 다 — 기존 28개 CQ 를 건드리지 않기 위한
    하위호환이고, 기본값이 **게이트에 드는 쪽**이라 누락이 감시를 약화시키지 않는다.
    """
    desc, expect_min, suite, monotone, target = "", 1, "", "", "graph"
    for line in rq_text.splitlines():
        line = line.strip()
        if line.startswith("# desc:"):
            desc = line.removeprefix("# desc:").strip()
        elif line.startswith("# expect-min:"):
            expect_min = int(line.removeprefix("# expect-min:").strip())
        elif line.startswith("# suite:"):
            suite = line.removeprefix("# suite:").strip()
        elif line.startswith("# monotone:"):
            monotone = line.removeprefix("# monotone:").strip()
        elif line.startswith("# target:"):
            target = line.removeprefix("# target:").strip()
        elif line and not line.startswith("#"):
            break
    if target not in CQ_TARGETS:
        raise ValueError(f"CQ 조회 대상 라벨이 잘못됐다: '{target}' (허용 {CQ_TARGETS})")
    if suite not in CQ_SUITES:
        raise ValueError(f"CQ 스위트 라벨이 없거나 잘못됐다: '{suite}' (허용 {CQ_SUITES})")
    if monotone not in CQ_MONOTONE:
        raise ValueError(f"CQ 극성 라벨이 없거나 잘못됐다: '{monotone}' (허용 {CQ_MONOTONE}) — "
                         "극성 없이 '행수 하락=회귀'로 판정하면 공백 탐색 질의(CQ03·CQ06)의 "
                         "정당한 개선이 회귀로 오판된다(PLAN-021 §2)")
    return desc, expect_min, suite, monotone, target


def suite_predicates(cq_dir: Path = QUERIES_CQ) -> dict[str, set[str]]:
    """스위트 → 그 스위트 CQ 가 **실제로 참조하는 술어** 집합 (`.rq` 정적 추출).

    PLAN-025 §2.3 의 "교차성은 결과가 아니라 구성으로 보증한다"를 코드가 지탱하게 하는 함수다.
    신규 교차결함군의 조작 술어가 주 태스크(pa) 스위트와 교집합이 없음은 결과와 무관하게 사전
    검증 가능한 성질이므로, 수기 목록이 아니라 질의 원문에서 뽑는다(문서는 표류한다).

    소문자로 시작하는 지역명만 술어로 센다 — 대문자는 클래스다(`ont:Patent` 등).
    주석 줄은 제외한다(설명문에 적힌 술어 이름이 섞이면 교집합이 거짓으로 커진다).
    """
    import re

    out: dict[str, set[str]] = {}
    for rq in sorted(cq_dir.glob("*.rq")):
        text = rq.read_text(encoding="utf-8")
        suite = _parse_meta(text)[2]
        body = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))
        preds = set(re.findall(r"\bont:([a-z][A-Za-z0-9_]*)", body))
        preds |= {f"skos:{m}" for m in re.findall(r"\bskos:([a-z][A-Za-z0-9_]*)", body)}
        out.setdefault(suite, set()).update(preds)
    return out


def _count_rdflib(graph_path: Path, texts: list[str]) -> list[int]:
    from rdflib import Graph

    g = Graph().parse(graph_path)
    return [len(list(g.query(t))) for t in texts]


def _count_oxigraph(graph_path: Path, texts: list[str]) -> list[int]:
    """pyoxigraph 온디스크 스토어로 같은 질의를 센다 (rdflib 대비 ~10배 빠름).

    대용량 그래프에서 인메모리는 메모리를 폭주시킨다(메모리 `central-axis-use-oxigraph-ondisk`)
    — 임시 디렉터리 스토어에 적재하고 종료 시 버린다. **기본 그래프에 적재**하므로 CQ 의
    `?s ?p ?o` 패턴 의미가 rdflib 과 같다.
    """
    from pyoxigraph import RdfFormat, Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(path=str(Path(tmp) / "cq"))
        with open(graph_path, "rb") as fh:
            store.bulk_load(fh, format=RdfFormat.TURTLE)
        return [sum(1 for _ in store.query(t)) for t in texts]


def _count_sidecar(texts: list[str]) -> list[int]:
    """청구항 분해 사이드카(`central_axis.oxstore`)에 같은 질의를 센다 (PLAN-023 §3).

    **읽기 전용**이다 — 결함주입은 이 스토어를 건드리지 않는다. 스토어가 없으면 **에러**다:
    조용히 건너뛰면 분모가 소리 없이 바뀌고, 그것이 정확히 게이트를 공허하게 만드는 경로다
    (스위트 라벨 누락을 에러로 처리한 것과 같은 규율).
    """
    from pyoxigraph import Store

    if not CENTRAL_AXIS_STORE.exists():
        raise FileNotFoundError(
            f"사이드카 스토어 없음: {CENTRAL_AXIS_STORE} — "
            "`python -m sdkb_paper.ontology.central_axis build` 로 빌드하라. "
            "target=sidecar CQ 를 조용히 건너뛰지 않는다(PLAN-023 §3-1)")
    store = Store(path=str(CENTRAL_AXIS_STORE))
    return [sum(1 for _ in store.query(t)) for t in texts]


def sidecar_provenance() -> dict:
    """세대 아티팩트에 핀할 사이드카 출처 (PLAN-023 §3-2). 없으면 에러."""
    import json as _json

    if not CENTRAL_AXIS_PROVENANCE.exists():
        raise FileNotFoundError(f"사이드카 PROVENANCE 없음: {CENTRAL_AXIS_PROVENANCE}")
    p = _json.loads(CENTRAL_AXIS_PROVENANCE.read_text(encoding="utf-8"))
    return {"sdkb_commit": p.get("sdkb_commit"), "triples": p.get("triples"),
            "source_sha256": {k: v.get("sha256") for k, v in p.get("source_files", {}).items()}}


def run_cqs(graph_path: Path, cq_dir: Path = QUERIES_CQ,
            engine: str = DEFAULT_ENGINE,
            targets: tuple[str, ...] = CQ_TARGETS) -> list[CQResult]:
    """CQ 전량 실행. `# target:` 에 따라 그래프와 사이드카로 나눠 조회한다(PLAN-023 §1).

    `targets` 로 조회 대상을 좁힐 수 있다. **게이트 경로는 절대 이 인자를 쓰지 않는다** —
    분모를 줄이는 우회로가 되기 때문이다. 쓰는 곳은 둘뿐이며 이유가 다르다:
      · `analysis/faults.py` — 결함주입은 TTL 만 건드리므로 사이드카 조회가 무의미하고,
        28-CQ 체제로 동결된 표 6.5 계열의 **재현성**을 위해 graph 로 고정한다.
      · 사이드카 스토어(gitignore·1.8GB)가 없는 환경의 테스트.
    """
    if engine not in ENGINES:
        raise ValueError(f"알 수 없는 CQ 엔진: '{engine}' (허용 {ENGINES})")
    bad = set(targets) - set(CQ_TARGETS)
    if bad:
        raise ValueError(f"알 수 없는 CQ 조회 대상: {sorted(bad)} (허용 {CQ_TARGETS})")
    rqs = sorted(cq_dir.glob("*.rq"))
    texts = [rq.read_text(encoding="utf-8") for rq in rqs]
    metas = [_parse_meta(t) for t in texts]
    keep = [i for i, m in enumerate(metas) if m[4] in targets]
    rqs = [rqs[i] for i in keep]
    texts = [texts[i] for i in keep]
    metas = [metas[i] for i in keep]
    idx_graph = [i for i, m in enumerate(metas) if m[4] == "graph"]
    idx_side = [i for i, m in enumerate(metas) if m[4] == "sidecar"]
    counts: list[int] = [0] * len(rqs)
    counter = _count_oxigraph if engine == "oxigraph" else _count_rdflib
    for i, n in zip(idx_graph, counter(graph_path, [texts[i] for i in idx_graph])):
        counts[i] = n
    if idx_side:
        for i, n in zip(idx_side, _count_sidecar([texts[i] for i in idx_side])):
            counts[i] = n
    return [CQResult(rq.stem, desc, expect_min, rows, suite, mono, target)
            for rq, (desc, expect_min, suite, mono, target), rows in zip(rqs, metas, counts)]


def verify_engines(graph_path: Path, cq_dir: Path = QUERIES_CQ) -> list[dict]:
    """두 엔진의 CQ 별 결과행을 대조한다. 불일치가 있으면 엔진 전환은 무효다.

    사이드카 CQ 는 **엔진 고정**이다 — rdflib 인메모리는 11.6M 에서 OOM 이다(메모리
    `central-axis-use-oxigraph-ondisk`). 조용히 빼지 않고 `engine_fixed` 로 명시 보고한다.
    """
    rqs = sorted(cq_dir.glob("*.rq"))
    texts = [rq.read_text(encoding="utf-8") for rq in rqs]
    targets = [_parse_meta(t)[4] for t in texts]
    g = [i for i, t in enumerate(targets) if t == "graph"]
    ox = _count_oxigraph(graph_path, [texts[i] for i in g])
    rd = _count_rdflib(graph_path, [texts[i] for i in g])
    out = [{"cq": rqs[i].stem, "oxigraph": o, "rdflib": r, "same": o == r,
            "engine_fixed": False} for i, o, r in zip(g, ox, rd)]
    out += [{"cq": rqs[i].stem, "oxigraph": None, "rdflib": None, "same": True,
             "engine_fixed": True} for i, t in enumerate(targets) if t == "sidecar"]
    return sorted(out, key=lambda d: d["cq"])


def suite_pass_rates(results: list[CQResult], base_rows: dict[str, int] | None = None,
                     tau: float = CQ_TAU, exempt_regress: bool = False) -> dict[str, dict]:
    """스위트별 {n_pass, n_total, rate} — T3 의 입력. 결정론적 집계이며 검정이 아니다.

    `base_rows`(CQ명 → 기준 세대 결과행)를 주면 **판정 v2**(존재검사 ∧ ¬분포회귀)로 센다.
    주지 않으면 v1 이다 — 기존 호출부·세대 아티팩트가 그대로 동작한다.
    `exempt_regress` 는 검증된 중복제거 델타의 분포검사 면제(PLAN-022 §2).

    **사이드카 CQ 는 세지 않는다**(PLAN-023 §1 희석 금지) — 시험 대상 그래프에 무반응인
    상수항을 판정 분모에 넣으면 실패가 희석돼 검출력이 떨어진다. 측정은
    `target_measurements()` 가 따로 보고한다.
    """
    out: dict[str, dict] = {}
    for r in results:
        if not r.in_gate:
            continue
        rec = out.setdefault(r.suite, {"n_pass": 0, "n_total": 0})
        rec["n_total"] += 1
        base = None if base_rows is None else base_rows.get(r.name)
        rec["n_pass"] += int(r.judge(base, tau, exempt_regress))
    for rec in out.values():
        rec["rate"] = rec["n_pass"] / rec["n_total"] if rec["n_total"] else 0.0
    return out


def layer_pass_counts(results: list[CQResult], base_rows: dict[str, int] | None = None,
                      tau: float = CQ_TAU, exempt_regress: bool = False) -> dict[str, dict]:
    """**층 귀속** — 같은 28개 CQ 를 L3(주 태스크)와 T3(교차 태스크)로 나눠 센다 (PLAN-022 §1).

    W4b 실측: L3 가 전 스위트를 세고 T3 가 그 부분집합을 보아 **L3 ⊇ T3 가 정의상 성립**했고,
    그래서 "T3 단독검출"은 원리적으로 0 이었다(원고 §6.5.2). 두 표면을 서로소로 가른다.

    **검출력은 불변이다** — `L3_SUITES ∪ T3_SUITES = CQ_SUITES` 이고 승인식은 곱이므로 어느
    층에 귀속되든 하나라도 떨어지면 거부다. 바뀌는 것은 귀속뿐이며, 이 성질은
    `tests/test_layer_separation.py` 가 불변량으로 강제한다.
    """
    per = suite_pass_rates(results, base_rows, tau, exempt_regress)
    out = {}
    for layer, suites in (("L3", L3_SUITES), ("T3", T3_SUITES)):
        n_pass = sum(per.get(s, {}).get("n_pass", 0) for s in suites)
        n_total = sum(per.get(s, {}).get("n_total", 0) for s in suites)
        out[layer] = {"suites": tuple(suites), "n_pass": n_pass, "n_total": n_total,
                      "rate": n_pass / n_total if n_total else 0.0}
    return out


def target_measurements(results: list[CQResult], base_rows: dict[str, int] | None = None,
                        tau: float = CQ_TAU) -> dict[str, dict]:
    """조회 대상별 통과 계수 — **게이트가 아니라 측정**이다 (PLAN-023 §1).

    사이드카 CQ 는 승인식에 들어가지 않으므로 여기서만 보이며, 세대 아티팩트와 표 6.6 에
    별도로 실린다. 보이지 않는 검사는 없는 검사와 같으므로 조용히 빼지 않는다.
    """
    out: dict[str, dict] = {}
    for r in results:
        rec = out.setdefault(r.target, {"n_pass": 0, "n_total": 0, "cqs": []})
        rec["n_total"] += 1
        base = None if base_rows is None else base_rows.get(r.name)
        ok = r.judge(base, tau)
        rec["n_pass"] += int(ok)
        rec["cqs"].append({"cq": r.name, "suite": r.suite, "rows": r.rows, "passed": ok})
    for rec in out.values():
        rec["rate"] = rec["n_pass"] / rec["n_total"] if rec["n_total"] else 0.0
    return out


def regressions(results: list[CQResult], base_rows: dict[str, int],
                tau: float = CQ_TAU) -> list[dict]:
    """v2 에서 회귀로 판정된 CQ 목록(진단·표 6.5v2 의 '어느 CQ 가 떨어졌나' 열)."""
    out = []
    for r in results:
        base = base_rows.get(r.name)
        if base is not None and r.regressed(base, tau):
            out.append({"cq": r.name, "suite": r.suite, "monotone": r.monotone,
                        "rows": r.rows, "base": base,
                        "delta_rate": (r.rows - base) / base if base else None})
    return out


def report_path(graph_path: Path) -> Path:
    """그래프별 리포트 경로. G₀ 와 G₁ 의 리포트가 서로 덮어쓰지 않아야 논문 §4.2 의
    '보강 전후 CQ 응답률 비교표'를 만들 수 있다."""
    return ROOT / "paper" / "figures" / f"cq_report_{graph_path.stem}.md"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("graph", type=Path)
    ap.add_argument("--report", action="store_true", help="markdown 리포트 파일 생성")
    ap.add_argument("--out", type=Path, default=None, help="리포트 경로 (기본: cq_report_<graph>.md)")
    ap.add_argument(
        "--min-pass", type=float, default=1.0,
        help="요구 통과율 (0~1). baseline(graph_v0)처럼 특허 0건인 그래프는 "
             "CQ01/CQ02 가 응답 불가인 것이 정상이므로 0 으로 두고 '측정'으로 쓴다.",
    )
    ap.add_argument("--engine", choices=ENGINES, default=DEFAULT_ENGINE,
                    help="SPARQL 엔진. 기본 oxigraph — rdflib 은 되돌림용/대조용")
    ap.add_argument("--verify-engines", action="store_true",
                    help="두 엔진 결과행 대조(전환 근거). 불일치 1건이라도 있으면 exit 1")
    args = ap.parse_args()

    if args.verify_engines:
        rows = verify_engines(args.graph)
        bad = [r for r in rows if not r["same"]]
        print(f"[cq_runner] 엔진 대조 · graph = {args.graph}  ({len(rows)} CQ)")
        for r in rows:
            mark = "✅" if r["same"] else "❌"
            print(f"  {mark} {r['cq']:<40} oxigraph={r['oxigraph']:<8} rdflib={r['rdflib']}")
        print(f"\n[cq_runner] 불일치 {len(bad)}건")
        sys.exit(0 if not bad else 1)

    results = run_cqs(args.graph, engine=args.engine)
    if not results:
        print("[cq_runner] no CQ files found")
        sys.exit(2)

    lines = ["| CQ | 스위트 | 대상 | 질문 | 결과행 | 기준 | 통과 |",
             "|---|---|---|---|---:|---:|:--:|"]
    for r in results:
        lines.append(f"| {r.name} | {r.suite} | {r.target} | {r.desc} | {r.rows} | "
                     f"≥{r.expect_min} | {'✅' if r.passed else '❌'} |")
    # **종료코드는 게이트 대상(target=graph)만 센다** — 사이드카 CQ 는 시험 대상 그래프에
    # 무반응인 상수항이라 판정에 넣으면 통과율을 희석한다(PLAN-023 §1). 측정은 아래에 따로 찍는다.
    gated = [r for r in results if r.in_gate]
    n_pass = sum(r.passed for r in gated)
    rate = n_pass / len(gated) if gated else 0.0
    table = "\n".join(lines)
    print(f"[cq_runner] graph = {args.graph}")
    print(table)
    print(f"\n[cq_runner] pass rate = {rate:.0%} ({n_pass}/{len(gated)})  [게이트 대상 target=graph]")
    meas = target_measurements(results)
    for tgt, rec in sorted(meas.items()):
        if tgt != CQ_GATE_TARGET:
            print(f"  ~ [측정·게이트 아님] target={tgt:<9} {rec['rate']:.0%} "
                  f"({rec['n_pass']}/{rec['n_total']})  ← PLAN-023 §1 희석 금지")
    for suite, rec in sorted(suite_pass_rates(results).items()):
        print(f"  · {suite:<5} {rec['rate']:.0%} ({rec['n_pass']}/{rec['n_total']})")
    # 층 귀속 표시 (PLAN-022 §1). **종료코드는 여전히 28개 전량의 곱이다** — 귀속을 나누는 것이
    # 게이트를 완화하는 것이 되어서는 안 된다(§0.1 검출력 불변). 여기서 pa 만 보고 종료했다면
    # mini_graph 의 em·tf·core CQ 실패가 통과가 되어 개정 전 거부가 개정 후 승인이 됐을 것이다.
    for layer, rec in layer_pass_counts(results).items():
        print(f"  [{layer}] {'·'.join(rec['suites']):<14} {rec['rate']:.0%} "
              f"({rec['n_pass']}/{rec['n_total']})")

    if args.report:
        out = args.out or report_path(args.graph)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            f"# CQ 응답률 — `{args.graph}`\n\n{table}\n\n"
            f"pass rate (게이트 대상 target=graph): {rate:.0%} ({n_pass}/{len(gated)})\n",
            encoding="utf-8",
        )
        print(f"[cq_runner] report -> {out}")

    sys.exit(0 if rate >= args.min_pass else 1)


if __name__ == "__main__":
    main()
