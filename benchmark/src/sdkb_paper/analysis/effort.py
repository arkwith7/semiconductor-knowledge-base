"""운용 효율 — Effort@Recall · Candidate Reduction (PLAN-036 · 원고 §6.3 탐색적 표).

**동결된 run 을 다시 읽어내는 판독이다 — 새 검색·새 데이터·새 질의셋이 없다.** 산출은
"같은 회수를 얻는 데 몇 건을 검토해야 하는가"이며, R@100 이라는 지표를 실무 단위(검토 건수)로
옮긴 것이다(CLAUDE.md §0.4 **등급 1 · 측정된 이익**).

**경계 — 확증이 아니다.** test 분할은 이미 개봉됐다(CLAUDE.md §2.1 *"개봉된 표본으로 우월성을
다시 확증하지 않는다"*). 여기 나오는 값은 **탐색적 기술통계**이며 원고 §6.3 탐색적 표에만 싣는다.
결론·초록·기여에 올리지 않는다. 확증 승격은 B층 사전등록(PLAN-031)에서 이 상수들을 그대로
물려받아 수행한다.

**우측 절단(right-censoring) 처리 — PLAN-036 §10.1 동결.**
`K_q(R)` 은 run 깊이 안에서 목표 회수 R 에 도달하지 못한 질의에서 정의되지 않는다. 실측상 이것은
예외가 아니라 다수 사건이다(R=0.5 에서 27% · R=1.0 에서 55%). 미도달 질의를 버리면 어려운 질의가
사라져 이익이 부풀려지므로 **버리지 않는다.**
- 미도달 질의는 `K_q := D+1` 로 **보수적 대입**하고, 집계는 **중앙값만** 쓴다(평균은 대입값이
  좌우하므로 보고하지 않는다). 절단율이 50% 미만이면 중앙값은 대입값에 **불변**이다.
- **R=1.0 에서는 절단율이 모든 D 에서 55% 이상**이라 중앙값이 식별되지 않는다 — 대입 중앙값을
  쓰면 숫자가 아니라 `D+1` 이라는 상수를 보고하는 꼴이다. 그래서 R=1.0 은 **도달률(%)만** 낸다.
- Candidate Reduction 은 두 시스템이 **모두 도달한 질의**에서만 계산하고, 나머지 세 경우의 건수를
  **2×2 교차표로 함께** 싣는다 — 한쪽만 도달한 질의가 가장 유리·불리한 사례이기 때문이다.

**팔 고정 — 최상위 `runs/` 를 쓰지 않는다.** `data/processed/ir/runs/` 는 PLAN-035 실행 때 O′ 팔로
덮여 있어 P1 R@100=0.4556 이며 **원고 §6 의 0.4849 가 아니다.** 원고를 재현하는 팔은
`runsets/O_pre_linker/` 이고, 이 모듈은 그 경로만 읽는다(§9.1).

CLI: `python -m sdkb_paper.analysis.effort [--write] [--sensitivity]`
"""
from __future__ import annotations

import argparse
import hashlib
import math
import statistics as st
from pathlib import Path

from .. import config
from .metrics import _fold, load_qrel, load_run

# ── 동결 상수 (PLAN-036 §10.1 · 결과를 본 뒤 바꾸지 않는다) ──────────────────────
ARM_DIR = config.IR_RUNSETS_DIR / "O_pre_linker"   # 원고 §6 재현 팔 (§9.1)
SPLIT = "test"
D_CAP = 500                        # 공통 상한 (검토 깊이). 전 시스템·전 질의 동일 적용
D_SENSITIVITY = (100, 200, 313, 500)   # 313 = 세 팔 공통 최소 family 깊이 (풀 고갈 0)
R_MEDIAN = ("first", 0.5)          # 중앙값을 낼 목표 회수 (R=0.8 은 §9.2 로 삭제)
R_REACH_ONLY = 1.0                 # 중앙값 금지 · 도달률만 (§9.4-2)
KS_CURVE = (20, 50, 100, 200, 500)
MAIN_SYSTEMS = ("B3_rrf", "P0star", "P1")          # 깊이가 완전히 동일한 재랭크 3팔 (§9.3)
CURVE_SYSTEMS = ("B0_bm25", "B2_dense", "B3_rrf", "B5_concept", "P0star", "P1")
BASELINE, PROPOSED = "B3_rrf", "P1"                # Candidate Reduction 의 두 팔

LABELS = {
    "B0_bm25": "BM25 (B0)", "B2_dense": "Dense (B2)", "B3_rrf": "Text Hybrid (B3)",
    "B5_concept": "Ontology-only (B5)", "P0star": "Text+Ontology (P0★)", "P1": "+ClaimFeature (P1)",
}

EFFORT_TABLE = config.TABLES / f"ir_effort_{SPLIT}.md"
EFFORT_CURVE_CSV = config.IR_DIR / f"effort_curve_{SPLIT}.csv"


# ── 적재 ────────────────────────────────────────────────────────────────────────
def load_arm() -> tuple[dict[str, dict[str, list[str]]], dict[str, set[str]], list[str], dict[str, str]]:
    """동결 팔의 run 을 family 로 접어 반환. (runs, qrel_family, qids, sha256)."""
    from ..collect.bq_family_ir import load_family_map

    fam = load_family_map()
    qrel_doc = load_qrel(config.IR_QREL_TEST_SEALED)
    qrel = {q: {fam.get(d, d) for d in pos} for q, pos in qrel_doc.items()}
    qids = sorted(q for q, pos in qrel.items() if pos)       # 정답≥1 (분모 규율 §0)

    runs: dict[str, dict[str, list[str]]] = {}
    sha: dict[str, str] = {}
    for s in CURVE_SYSTEMS:
        path = ARM_DIR / f"sys_{s}_{SPLIT}.txt"
        if not path.exists():
            raise FileNotFoundError(f"동결 팔의 run 이 없다: {path}")
        sha[s] = hashlib.sha256(path.read_bytes()).hexdigest()
        raw = load_run(path)
        runs[s] = {q: _fold(raw.get(q, []), fam) for q in qids}
    return runs, qrel, qids, sha


# ── 핵심 정의 ───────────────────────────────────────────────────────────────────
def need_at(n_pos: int, target: float | str) -> int:
    """목표 회수 → 찾아야 할 정답 건수. `first` = 1건, 비율 R = ⌈R·|Rel|⌉."""
    if target == "first":
        return 1
    return max(1, math.ceil(float(target) * n_pos - 1e-9))


def k_at_recall(ranked: list[str], pos: set[str], target: float | str, cap: int) -> int | None:
    """`min{K ≤ cap : Recall@K ≥ target}`. 상한 안에서 도달 못하면 **None(우측 절단)**."""
    need = need_at(len(pos), target)
    hit = 0
    for i, d in enumerate(ranked[:cap], 1):
        if d in pos:
            hit += 1
            if hit >= need:
                return i
    return None


def effort_at_recall(runs, qrel, qids, system: str, target, cap: int = D_CAP) -> dict:
    """Effort@Recall — 절단은 `cap+1` 대입 · **중앙값만**. 절단율을 함께 돌려준다."""
    ks = [k_at_recall(runs[system][q], qrel[q], target, cap) for q in qids]
    censored = sum(1 for k in ks if k is None)
    imputed = [k if k is not None else cap + 1 for k in ks]
    reached = [k for k in ks if k is not None]
    return {
        "system": system, "target": target, "cap": cap, "n": len(qids),
        "censored": censored, "censored_rate": censored / len(qids),
        # 절단율 ≥ 50% 면 중앙값은 대입값이 결정한다 → 숫자를 내지 않는다
        "median": st.median(imputed) if censored / len(qids) < 0.5 else None,
        "q1": st.quantiles(imputed, n=4)[0] if censored / len(qids) < 0.25 else None,
        "reach_rate": len(reached) / len(qids),
    }


def candidate_reduction(runs, qrel, qids, target, cap: int = D_CAP,
                        baseline: str = BASELINE, proposed: str = PROPOSED) -> dict:
    """(K_base − K_prop)/K_base 의 중앙값 — **둘 다 도달한 질의만** + 2×2 절단 교차표."""
    both, only_prop, only_base, neither = [], 0, 0, 0
    for q in qids:
        kb = k_at_recall(runs[baseline][q], qrel[q], target, cap)
        kp = k_at_recall(runs[proposed][q], qrel[q], target, cap)
        if kb is not None and kp is not None:
            both.append((kb - kp) / kb)
        elif kp is not None:
            only_prop += 1          # 제안법만 도달 = 제안법이 이긴 사례
        elif kb is not None:
            only_base += 1          # 기준선만 도달 = 제안법이 진 사례
        else:
            neither += 1
    assert len(both) + only_prop + only_base + neither == len(qids)
    return {
        "target": target, "cap": cap, "n": len(qids),
        "n_both": len(both), "only_proposed": only_prop, "only_baseline": only_base,
        "neither": neither,
        "median_reduction": st.median(both) if both else None,
        "wins": sum(1 for x in both if x > 0), "ties": sum(1 for x in both if x == 0),
        "losses": sum(1 for x in both if x < 0),
    }


def recall_at_k(runs, qrel, qids, system: str, k: int) -> float:
    """family 매크로 Recall@K — `make eval` 과 같은 정의(회귀 테스트로 강제)."""
    return sum(len(set(runs[system][q][:k]) & qrel[q]) / len(qrel[q]) for q in qids) / len(qids)


def extra_found(runs, qrel, qids, k: int,
                baseline: str = BASELINE, proposed: str = PROPOSED) -> dict:
    """질의당 **추가 발견 문헌 수(건)** — 절단의 영향을 받지 않는 유일한 지표."""
    diffs = [len(set(runs[proposed][q][:k]) & qrel[q]) - len(set(runs[baseline][q][:k]) & qrel[q])
             for q in qids]
    qs = st.quantiles(diffs, n=4)
    return {"k": k, "median": st.median(diffs), "q1": qs[0], "q3": qs[2],
            "mean": sum(diffs) / len(diffs), "total": sum(diffs),
            "gain_queries": sum(1 for d in diffs if d > 0),
            "loss_queries": sum(1 for d in diffs if d < 0)}


# ── 보고 ────────────────────────────────────────────────────────────────────────
def _fmt(x, nd=1, pct=False):
    if x is None:
        return "—"
    return f"{x:.1%}" if pct else f"{x:.{nd}f}"


def render(runs, qrel, qids, sha, sensitivity: bool = False) -> str:
    L: list[str] = []
    L.append(f"# 표 6.3x — 운용 효율 (Effort@Recall · Candidate Reduction) · {SPLIT} 분할\n")
    L.append("> **탐색적 기술통계다 — 확증이 아니다.** test 분할은 이미 개봉됐다"
             "(CLAUDE.md §2.1). 결론·초록·기여에 인용하지 않는다.\n")
    L.append(f"> 팔 `{ARM_DIR.name}` · 질의 {len(qids)}(정답≥1) · family 단위 · 공통 상한 D={D_CAP} · "
             f"미도달은 K:=D+1 대입 후 **중앙값만**.\n")
    L.append("> 허용 표현: *같은 회수를 더 적은 검토 건수로 달성*. "
             "금지: 조사 시간·비용 절감률 · 변리사 검토 대체 · FTO (CLAUDE.md §0.4).\n")

    L.append(f"\n## (1) Effort@Recall — 중앙 검토 건수 (D={D_CAP})\n")
    L.append("| 시스템 | 첫 관련 문헌까지 | 절단 | 정답 절반까지 (R=0.5) | 절단 | 완전 회수 도달률 (R=1.0) |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for s in MAIN_SYSTEMS:
        a = effort_at_recall(runs, qrel, qids, s, "first")
        b = effort_at_recall(runs, qrel, qids, s, 0.5)
        c = effort_at_recall(runs, qrel, qids, s, R_REACH_ONLY)
        L.append(f"| {LABELS[s]} | {_fmt(a['median'])} | {_fmt(a['censored_rate'], pct=True)} | "
                 f"{_fmt(b['median'])} | {_fmt(b['censored_rate'], pct=True)} | "
                 f"{_fmt(c['reach_rate'], pct=True)} |")
    L.append("\n**R=1.0 은 중앙값을 내지 않는다** — 절단율이 55% 이상이라 대입 중앙값은 D+1 이라는 "
             "상수를 보고하는 것과 같다(PLAN-036 §9.4). 도달률만 싣는다.")
    L.append("`|Rel|=1` 인 질의 47건(23.7%)에서는 '첫 관련 문헌'과 R=0.5·R=1.0 이 같은 값이다.")

    L.append(f"\n## (2) Candidate Reduction — (K_B3 − K_P1)/K_B3 · D={D_CAP}\n")
    L.append("| 목표 회수 | 둘 다 도달 n | 중앙 감소율 | 승/무/패 | P1만 도달 | B3만 도달 | 둘 다 미도달 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for t in R_MEDIAN:
        c = candidate_reduction(runs, qrel, qids, t)
        name = "첫 관련 문헌" if t == "first" else f"R={t}"
        L.append(f"| {name} | {c['n_both']} | {_fmt(c['median_reduction'], pct=True)} | "
                 f"{c['wins']}/{c['ties']}/{c['losses']} | {c['only_proposed']} | "
                 f"{c['only_baseline']} | {c['neither']} |")
    L.append("\n**네 칸의 합 = 평가 질의 수**다. 감소율은 '둘 다 도달' 칸에서만 나오므로 "
             "나머지 세 칸을 같이 읽어야 한다 — 한쪽만 도달한 질의가 가장 유리·불리한 사례다.")

    L.append("\n## (3) 깊이별 회수 곡선 — family Recall@K\n")
    L.append("| 시스템 | " + " | ".join(f"K={k}" for k in KS_CURVE) + " |")
    L.append("|---|" + "---:|" * len(KS_CURVE))
    for s in CURVE_SYSTEMS:
        L.append(f"| {LABELS[s]} | " +
                 " | ".join(f"{recall_at_k(runs, qrel, qids, s, k):.4f}" for k in KS_CURVE) + " |")
    L.append("\nK=100 열은 `make eval` 의 family Recall@100 과 일치한다(회귀 테스트). "
             "회수 곡선은 절단의 영향을 받지 않는다 — 후보 풀이 마르면 평평해질 뿐이다.")

    L.append("\n## (4) 질의당 추가 발견 문헌 수 (P1 − B3 · 건수)\n")
    L.append("| K | 중앙값 | Q1 | Q3 | 평균 | 합계 | 늘어난 질의 | 줄어든 질의 |")
    L.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in KS_CURVE:
        e = extra_found(runs, qrel, qids, k)
        L.append(f"| {k} | {e['median']:.1f} | {e['q1']:.1f} | {e['q3']:.1f} | {e['mean']:+.3f} | "
                 f"{e['total']:+d} | {e['gain_queries']} | {e['loss_queries']} |")
    L.append("\n**절단의 영향을 받지 않는 유일한 지표**이므로 본문 문장은 이 값을 우선 인용한다.")

    if sensitivity:
        L.append("\n## (부) 공통 상한 D 민감도 — 절단율\n")
        L.append("| D | " + " | ".join(f"{LABELS[s]} R=0.5" for s in MAIN_SYSTEMS) +
                 " | " + " | ".join(f"{LABELS[s]} R=1.0" for s in MAIN_SYSTEMS) + " |")
        L.append("|---|" + "---:|" * (2 * len(MAIN_SYSTEMS)))
        for cap in D_SENSITIVITY:
            row = [_fmt(effort_at_recall(runs, qrel, qids, s, 0.5, cap)["censored_rate"], pct=True)
                   for s in MAIN_SYSTEMS]
            row += [_fmt(effort_at_recall(runs, qrel, qids, s, 1.0, cap)["censored_rate"], pct=True)
                    for s in MAIN_SYSTEMS]
            L.append(f"| {cap} | " + " | ".join(row) + " |")

    L.append("\n## 출처\n")
    L.append(f"- 팔: `{ARM_DIR}` · qrel: `{config.IR_QREL_TEST_SEALED.name}`")
    for s in CURVE_SYSTEMS:
        L.append(f"  - `sys_{s}_{SPLIT}.txt` sha256 `{sha[s][:16]}…`")
    L.append("- 생성: `make effort` (`sdkb_paper.analysis.effort`) · 수기 기입 없음 (CLAUDE.md §1-7)")
    return "\n".join(L) + "\n"


def write_curve_csv(runs, qrel, qids, path: Path = EFFORT_CURVE_CSV) -> Path:
    """그림 입력 — viz/figures.py 가 읽는다(계산은 여기서, 그리기는 거기서)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["system,label,k,recall"]
    for s in CURVE_SYSTEMS:
        for k in KS_CURVE:
            lines.append(f"{s},{LABELS[s]},{k},{recall_at_k(runs, qrel, qids, s, k):.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Effort@Recall · Candidate Reduction (PLAN-036)")
    ap.add_argument("--write", action="store_true", help="표·CSV 를 파일로 기록")
    ap.add_argument("--sensitivity", action="store_true", default=True,
                    help="공통 상한 D 민감도 표 포함 (기본 포함)")
    args = ap.parse_args()

    runs, qrel, qids, sha = load_arm()
    md = render(runs, qrel, qids, sha, sensitivity=args.sensitivity)
    print(md)
    if args.write:
        EFFORT_TABLE.parent.mkdir(parents=True, exist_ok=True)
        EFFORT_TABLE.write_text(md, encoding="utf-8")
        csv = write_curve_csv(runs, qrel, qids)
        print(f"[written] {EFFORT_TABLE}\n[written] {csv}")


if __name__ == "__main__":
    main()
