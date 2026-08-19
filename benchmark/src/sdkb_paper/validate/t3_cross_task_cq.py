"""T3 — 교차 태스크 CQ 비회귀 게이트 (PLAN-018 §5.1 · PLAN-019 W3 · 원고 §4.9·§6.6·§10).

`1[∀f∈{em,tf,core}: PassRate_f(new) ≥ PassRate_f(old)]`.

**이것은 통계 검정이 아니다.** CQ 는 명세이고, 명세는 확률적으로 통과하지 않는다. 그래서 T3 는
결정론적 통과율 비교이며 하락은 곧 실패다 — 표본 부족·유의성 같은 완충재가 없다. 예외는 커밋
메시지의 명시적 waiver 토큰(`config.T3_WAIVER_TOKEN`)뿐이고, 그 **횟수는 로그에 남아 표 6.6에
보고된다**(면제가 조용해지면 게이트는 장식이 된다).

주 태스크(pa)는 T3 의 분모가 아니다 — 검색 성능 회귀는 T1 이 통계적으로, **CQ 기능 회귀는 L3 가
결정론적으로** 담당한다(`config.L3_SUITES` · 2026-07-28 PLAN-022 개정). 두 표면은 서로소이며
합집합이 CQ 전량이라 검출력은 불변이고 귀속만 갈린다. T3 가 지키는 것은 "다른 뷰가 조용히
부서지지 않았는가"다(원고 §7.6 태스크 결합 발견이 근거).

**세대 아티팩트.** 기준값은 `data/cq_generations/<label>.json` 에 얼린다(집계·해시만 → 커밋 가능).
`--freeze <label>` 로 현재 그래프의 통과율을 세대로 기록하고, 이후 델타는 그 세대와 비교한다.
누적된 세대 파일이 곧 표 6.6(세대별 CQ 통과율 추이)의 원천이다.

CLI:
  python -m sdkb_paper.validate.t3_cross_task_cq <graph.ttl> --freeze g0     # 세대 동결
  python -m sdkb_paper.validate.t3_cross_task_cq <graph.ttl> --baseline g0   # 비회귀 판정
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .. import config
from .cq_runner import run_cqs, sidecar_provenance, suite_pass_rates, target_measurements


def compare_rates(new: dict[str, dict], old: dict[str, dict],
                  suites: tuple[str, ...] = config.T3_SUITES) -> dict:
    """스위트별 (old→new) 비교. 하나라도 하락하면 regressed.

    스위트가 새 쪽에 아예 없으면(=CQ 가 사라졌으면) 통과율 0 으로 본다 — CQ 삭제로 게이트를
    통과하는 우회로를 막는다.
    """
    rows, regressed = [], []
    for f in suites:
        o = old.get(f, {}).get("rate", 0.0)
        n = new.get(f, {"rate": 0.0, "n_pass": 0, "n_total": 0})
        rate_new = n.get("rate", 0.0)
        drop = o - rate_new
        row = {"suite": f, "rate_old": o, "rate_new": rate_new, "drop": drop,
               "n_pass_new": n.get("n_pass", 0), "n_total_new": n.get("n_total", 0),
               "n_total_old": old.get(f, {}).get("n_total", 0),
               "regressed": rate_new < o}
        rows.append(row)
        if row["regressed"]:
            regressed.append(f)
    return {"rows": rows, "regressed": regressed}


def commit_waiver(message: str | None = None) -> str | None:
    """커밋 메시지에서 waiver 토큰 뒤의 사유를 뽑는다. 없으면 None."""
    if message is None:
        try:
            message = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=config.ROOT,
                                     capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
    tok = config.T3_WAIVER_TOKEN
    if tok not in message:
        return None
    return message.split(tok, 1)[1].strip().splitlines()[0].strip() or "(사유 미기재)"


def t3_gate(new_rates: dict[str, dict], old_rates: dict[str, dict],
            suites: tuple[str, ...] = config.T3_SUITES,
            waiver: str | None = None) -> dict:
    """T3 판정. waiver 가 있으면 하락에도 통과시키되 waived=True 로 남긴다."""
    cmp = compare_rates(new_rates, old_rates, suites)
    regressed = bool(cmp["regressed"])
    return {"gate": "T3", "suites": suites, "rows": cmp["rows"],
            "regressed": cmp["regressed"], "waived": bool(regressed and waiver),
            "waiver_reason": waiver if regressed else None,
            "pass": (not regressed) or bool(waiver)}


def generation_path(label: str) -> Path:
    return config.CQ_GEN_DIR / f"cq_{label}.json"


def freeze_generation(graph_path: Path, label: str, against: str | None = None,
                      rule: str = config.CQ_RULE_VERSION,
                      tau: float = config.CQ_TAU) -> dict:
    """현재 그래프의 스위트별 통과율을 세대 아티팩트로 얼린다(표 6.6 축적).

    `against` 를 주면 **그 세대 대비 T3 판정까지 계산해 아티팩트에 넣는다**(N5e). 판정을
    동결 시점에 붙이지 않으면 표 6.6 의 T3 열이 사람 손을 타고, 그것이 정확히 CLAUDE.md
    §1-7 이 금지하는 수기 기입이다 — 원고 표 6.6 의 `graph_v1` 행이 그렇게 생겼다.

    `against` 가 없으면 **기준 세대**다. 기준 세대는 판정하지 않는다 — 자기 자신 대비 회귀는
    정의상 0 이므로 v1 과 v2 가 일치한다(그래서 규칙 열도 "기준"으로 렌더한다).
    """
    from .leakage_check import sha256_file

    results = run_cqs(graph_path)
    prev = load_generation(against) if against else None
    base = baseline_rows(prev) if (prev is not None and rule == "v2") else None
    suites = suite_pass_rates(results, base, tau)
    gpath = Path(graph_path).resolve()
    rel = gpath.relative_to(config.ROOT) if gpath.is_relative_to(config.ROOT) else gpath
    meas = target_measurements(results, base, tau)
    rec = {"generation": label, "graph": str(rel),
           "graph_sha256": sha256_file(graph_path),
           # 판정 규칙과 τ 는 표 6.6 의 **스위트 버전 이력**으로 함께 실린다(PLAN-021 §1).
           "rule_version": rule, "tau": tau, "against": against,
           "n_cq": len(results), "suites": suites,
           # 조회 대상별 측정 — 사이드카 CQ 는 게이트 분모 밖이라 여기서만 보인다(PLAN-023 §1).
           # 출처를 함께 핀한다: 사이드카가 상류 재벤더로 바뀌었는데 세대 비교가 조용히
           # 진행되는 일을 막는다(§3-2).
           "measurements": meas,
           "sidecar_provenance": (sidecar_provenance()
                                  if any(r.target == "sidecar" for r in results) else None),
           "per_cq": {r.name: {"suite": r.suite, "rows": r.rows, "monotone": r.monotone,
                               "expect_min": r.expect_min, "passed": r.passed}
                      for r in results}}
    if prev is not None:
        waiver = commit_waiver()
        v = t3_gate(suites, prev["suites"], waiver=waiver)
        rec["verdict"] = {"baseline": prev["generation"], "pass": v["pass"],
                          "regressed": v["regressed"], "waived": v["waived"],
                          "waiver_reason": v["waiver_reason"], "rows": v["rows"]}
        if v["waived"]:
            log_waiver({"generation_old": prev["generation"], "generation_new": label,
                        "graph": str(rel), "regressed": v["regressed"],
                        "reason": v["waiver_reason"]})
    config.CQ_GEN_DIR.mkdir(parents=True, exist_ok=True)
    generation_path(label).write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return rec


def baseline_rows(gen: dict) -> dict[str, int]:
    """세대 아티팩트에서 CQ별 기준 결과행을 뽑는다 — 판정 v2 의 분모(PLAN-021 §1)."""
    return {k: v["rows"] for k, v in gen.get("per_cq", {}).items()}


def load_generation(label: str) -> dict:
    p = generation_path(label)
    if not p.exists():
        raise FileNotFoundError(
            f"세대 아티팩트 없음: {p} — 먼저 `--freeze {label}` 로 기준 세대를 동결하라")
    return json.loads(p.read_text(encoding="utf-8"))


def log_waiver(rec: dict) -> None:
    """waiver 사용 이력 append (횟수를 논문 표 6.6 에 보고하기 위한 원장)."""
    config.CQ_GEN_DIR.mkdir(parents=True, exist_ok=True)
    with config.T3_WAIVER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def waiver_count() -> int:
    if not config.T3_WAIVER_LOG.exists():
        return 0
    return sum(1 for line in config.T3_WAIVER_LOG.read_text(encoding="utf-8").splitlines()
               if line.strip())


def render_generations() -> str:
    """원고 표 6.6 — 세대별 CQ 통과율 추이 + **판정 규칙 버전 이력**(부록 F 요구).

    세대 아티팩트가 있는 만큼만 싣는다. 없는 세대를 만들어 채우지 않는다 — 표를 채우려고
    세대를 지어내면 그 순간 게이트 이력이 허구가 된다(CLAUDE.md §1-1).

    **판정 열은 아티팩트에서만 온다.** 판정 없는 비-기준 세대는 `[기입]` 자리표시자를 찍지
    않고 **에러로 떨어뜨린다** — 자리표시자를 남기면 사람이 채우게 되고, 그것이 §1-7 위반의
    발생 경로였다(N5e). 고치는 법은 `--freeze <세대> --against <이전세대>` 재동결이다.
    """
    gens = sorted(config.CQ_GEN_DIR.glob("cq_*.json"), key=lambda p: p.stat().st_mtime)
    lines = ["# 표 6.6 세대별 CQ 통과율 추이 (T3 이력 · 게이트 표류 감시)", "",
             "| 보강 세대 | 판정 규칙 | CQ-PA | CQ-EM | CQ-TF | CQ-CORE | 청구항층(측정) | T3 판정 | waiver |",
             "|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for p in gens:
        g = json.loads(p.read_text(encoding="utf-8"))
        s = g.get("suites", {})
        cells = " | ".join(
            f"{s[k]['rate']:.3f} ({s[k]['n_pass']}/{s[k]['n_total']})" if k in s else "—"
            for k in ("pa", "em", "tf", "core"))
        side = (g.get("measurements") or {}).get("sidecar")
        cells += " | " + (f"{side['rate']:.3f} ({side['n_pass']}/{side['n_total']})"
                          if side else "— (미측정)")
        v = g.get("verdict")
        if v is None:
            if g.get("against"):
                raise ValueError(
                    f"세대 '{g['generation']}' 에 T3 판정이 없다: {p.name} — "
                    "`--freeze <세대> --against <이전세대>` 로 재동결하라 (수기 기입 금지)")
            # 기준 세대: 판정하지 않는다(자기 대비 회귀는 정의상 0 → v1≡v2).
            rule_s, verdict, waiver_s = "— (기준 세대)", "— (기준)", "—"
        else:
            tau = g.get("tau")
            rule = g.get("rule_version", "v1")
            rule_s = rule + (f" (τ={tau})" if rule != "v1" and tau is not None else "")
            drops = ", ".join(v["regressed"])
            verdict = ("**승인** (하락 0)" if v["pass"] and not v["regressed"]
                       else f"**승인**(waiver · {drops} 하락)" if v["pass"]
                       else f"**거부** ({drops} 하락)")
            verdict += f" vs {v['baseline']}"
            waiver_s = "1" if v["waived"] else "0"
        lines.append(f"| {g['generation']} | {rule_s} | {cells} | {verdict} | {waiver_s} |")
    from .dedup_exempt import exemption_count

    lines += ["", f"- 누적 waiver {waiver_count()}회 (T3 예외 승인 이력 · 0 이 아니면 사유를 함께 읽어야 한다)",
              f"- 누적 중복제거 면제 승인 {exemption_count()[0]}건 "
              f"(판정 로그 {exemption_count()[1]}행 — 불승인·재판정 반복분 포함 · PLAN-022 §2). "
              "조용한 면제는 게이트를 장식으로 만든다.",
              "- **L3 = pa · T3 = em·tf·core 로 검출 표면이 서로소다**(2026-07-28 개정 · PLAN-022). "
              "주 태스크 CQ 의 기능 회귀는 L3, 검색 성능 회귀는 T1, 타 태스크 CQ 회귀는 T3 가 맡는다. "
              "구 정의(L3 가 전 스위트를 셈)에서는 L3 ⊇ T3 가 성립해 T3 단독검출이 원리적으로 0 이었다.",
              "- **청구항층 열은 게이트가 아니라 측정이다**(2026-07-28 신설 · PLAN-023 §1). "
              "CQ29–31 은 사이드카(`central_axis.oxstore` · Claim 586,567 · ClaimFeature 1,289,300)를 "
              "조회하며 **시험 대상 그래프에 무반응인 상수항**이라 L3·T3 분모에 넣지 않는다 — "
              "넣으면 항상 통과하는 CQ 가 실패를 희석해 검출력이 떨어진다. 이 층의 회귀는 델타 "
              "단위가 아니라 **세대 간 비교**로 잡으며, 세대 아티팩트에 상류 출처(PROVENANCE)를 핀한다.",
              "- **판정 규칙 이력**: v1 = 존재검사(`rows ≥ expect-min`) · v2 = 존재검사 ∧ 기준선 대비 "
              "분포검사(PLAN-021 동결 · 극성 `# monotone:` 선언 · τ 사전 동결). 규칙이 바뀌면 "
              "통과율의 의미가 바뀌므로 세대 비교는 같은 규칙끼리만 유효하다."]
    return "\n".join(lines) + "\n"


def format_report(r: dict) -> str:
    lines = [f"[T3 교차 태스크 CQ 비회귀] 스위트 {', '.join(r['suites'])} "
             "(주 태스크 pa 는 L3·T1 담당 — T3 분모 아님)",
             f"    {'스위트':<8}{'구':>10}{'신':>10}{'하락':>10}"]
    for row in r["rows"]:
        flag = "  ❌ 회귀" if row["regressed"] else ""
        lines.append(f"    {row['suite']:<8}{row['rate_old']:>10.3f}{row['rate_new']:>10.3f}"
                     f"{row['drop']:>+10.3f}{flag}"
                     f"   ({row['n_pass_new']}/{row['n_total_new']})")
    if r["waived"]:
        lines.append(f"  ⚠ waiver 적용 — 사유: {r['waiver_reason']} "
                     f"(누적 {waiver_count()}회 · 표 6.6 보고 대상)")
    lines.append(f"  판정: {'PASS (비회귀)' if r['pass'] else 'FAIL (타 태스크 CQ 하락)'}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("graph", type=Path, nargs="?", help="판정 대상 그래프 TTL")
    ap.add_argument("--freeze", metavar="LABEL", default=None,
                    help="현재 통과율을 세대 아티팩트로 동결(판정하지 않는다)")
    ap.add_argument("--against", metavar="LABEL", default=None,
                    help="--freeze 와 함께: 이 세대 대비 T3 판정을 계산해 아티팩트에 넣는다"
                         " (없으면 기준 세대로 동결 — 판정 없음)")
    ap.add_argument("--baseline", metavar="LABEL", default=None,
                    help="비교 기준 세대 라벨(기본 g0)")
    ap.add_argument("--rule", choices=("v1", "v2"), default=config.CQ_RULE_VERSION,
                    help="CQ 판정 규칙. v1=존재검사 · v2=존재검사∧분포검사(PLAN-021 동결)")
    ap.add_argument("--tau", type=float, default=config.CQ_TAU,
                    help=f"v2 허용 변동폭(동결 주값 {config.CQ_TAU} · 격자 {config.CQ_TAU_GRID})")
    ap.add_argument("--table", action="store_true",
                    help="표 6.6(세대별 통과율·규칙 버전 이력) 생성 — 그래프 인자 무시")
    args = ap.parse_args()

    if args.table:
        out = config.ROOT / "paper" / "tables" / "cq_generations.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_generations(), encoding="utf-8")
        print(render_generations())
        print(f"→ {out}")
        return

    if args.freeze:
        rec = freeze_generation(args.graph, args.freeze, against=args.against,
                                rule=args.rule, tau=args.tau)
        kind = f"vs 세대 '{args.against}' 판정 포함" if args.against else "기준 세대(판정 없음)"
        print(f"[T3] 세대 '{args.freeze}' 동결 ({kind}) → {generation_path(args.freeze)}")
        for f, s in sorted(rec["suites"].items()):
            print(f"  · {f:<5} {s['rate']:.3f} ({s['n_pass']}/{s['n_total']})")
        if "verdict" in rec:
            print(format_report(t3_gate(rec["suites"],
                                        load_generation(args.against)["suites"],
                                        waiver=rec["verdict"]["waiver_reason"])))
            sys.exit(0 if rec["verdict"]["pass"] else 1)
        return

    old = load_generation(args.baseline or "g0")
    base = None if args.rule == "v1" else baseline_rows(old)
    new_rates = suite_pass_rates(run_cqs(args.graph), base, args.tau)
    waiver = commit_waiver()
    r = t3_gate(new_rates, old["suites"], waiver=waiver)
    print(f"[T3] new={args.graph.name}  old=세대 '{old['generation']}'  "
          f"판정규칙 {args.rule}" + (f" (τ={args.tau})" if args.rule != "v1" else ""))
    print(format_report(r))
    if r["waived"]:
        log_waiver({"generation_old": old["generation"], "graph": str(args.graph),
                    "regressed": r["regressed"], "reason": r["waiver_reason"]})
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
