"""T-gate 종합 판정 — Accept(ΔG) (PLAN-019 W3 · 원고 §4.9).

    Accept(ΔG) = 1[L0=L1=L2=L3=pass] · 1[LB95(ΔR100) > −ε]_T1
                 · 1[max_s Drop_s < δ]_T2 · 1[∀f∈{em,tf,core}: PassRate_f ≥]_T3

승인식은 **곱**이다. 하나라도 0 이면 승인은 0 이고, 우회 경로는 없다(CLAUDE.md §5). 이 모듈은
T1·T2·T3 를 한 번에 돌려 판정과 근거를 JSON 으로 남기고 실패 시 비영 종료한다. L0–L3 는 별도
타깃(`make gate` 의 선행 단계)이 판정하며, 여기서는 그 결과를 인자로 받아 곱에 넣는다 —
`--l0-l3-pass/--l0-l3-fail`(기본: 통과로 가정하지 않고 `make gate` 가 넘겨준다).

- **누출 전제:** T1 은 누출 감사 통과가 전제다(CLAUDE.md §5). `--skip-leakage` 없이는 감사부터 돈다.
- **경계:** 판정만 한다. 데이터·순위·qrel 을 고치지 않는다.

**두 가지 모드(D-19).** 기본 `--mode system` 은 시스템 대 시스템 비교이고(P1 대 B3 — 기존 동작
불변), **H2(갱신 승인 안전성)의 증거가 아니다**(CLAUDE.md §0). H2 는 `--mode resource` 로만
잰다: 같은 시스템·같은 코드·같은 정답지에 **자원 스냅샷만 다른** 두 run 세트를 넣는다. 적격심사
(`runset.eligibility`)를 통과하지 못하면 T1·T2 를 **돌리지 않고** 미검정으로 끝낸다 — 부적격
비교의 수치는 남기지 않는다. 종료코드: 0 승인 · 1 게이트 불통과 · **2 미검정**.

**자원 델타 가시성(D-43 · PLAN-051).** 모드와 무관하게 `resource_visibility` 를 기록한다 —
`system` 모드에는 비교할 짝이 없어 E6 이 돌지 않으므로, 스냅샷이 움직였는데 파이프라인이 읽지
않은 상태에서도 `Accept = 1` 이 나온다. 이 필드는 **판정에 관여하지 않고** 그 승인이 무엇을 본
승인인지만 적는다. `accept`·종료코드·T1·T2·T3 는 이 필드의 값에 따라 달라지지 않는다.

CLI: `python -m sdkb_paper.validate.t_gate [--split dev] [--graph PATH] [--baseline g0]`
     `python -m sdkb_paper.validate.t_gate --mode resource --old-runset O --new-runset O_prime
      --system P1 --split test`
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .. import config


def accept(l0_l3: bool, t1: bool, t2: bool, t3: bool) -> bool:
    """승인식 — 네 조건의 곱. 완충재 없음."""
    return bool(l0_l3 and t1 and t2 and t3)


def run_tgate(split: str = "dev", new: Path | None = None, old: Path | None = None,
              graph: Path | None = None, baseline: str = "g0",
              l0_l3: bool = True, k: int = 100, skip_leakage: bool = False,
              mode: str = "system", old_runset: str | None = None,
              new_runset: str | None = None, system: str = "P1") -> dict:
    """T1·T2·T3(+누출 감사)를 돌려 종합 판정 dict 를 만든다.

    `mode="resource"` 면 적격심사를 먼저 통과해야 한다 — 실패하면 T1·T2 를 돌리지 않는다.
    """
    out: dict = {"mode": mode, "split": split, "k": k,
                 "epsilon": config.T_EPSILON, "delta": config.T_DELTA}

    # 자원 델타 가시성 (D-43 · PLAN-051) — **판정에 들어가지 않는 기록이다.**
    # 적격심사보다 앞에 두는 이유: 미검정으로 조기 반환하는 경로에서도 "어느 자원 상태 위에서
    # 돌았는가"는 남아야 한다. 이 값은 accept 에도 종료코드에도 관여하지 않는다.
    from . import runset as _RS

    out["resource_visibility"] = _RS.resource_visibility()

    # 적격심사가 **가장 먼저다** — 검색·평가 모듈을 적재하기 전에 끝낸다. 자격 없는 비교의
    # T1·T2 수치는 아예 만들지 않는다(남으면 언젠가 인용된다).
    mf_old = mf_new = None
    if mode == "resource":
        from . import runset as RS

        if not (old_runset and new_runset):
            raise ValueError("--mode resource 에는 --old-runset 과 --new-runset 이 모두 필요하다")
        mf_old, mf_new = RS.load(old_runset), RS.load(new_runset)
        elig = RS.eligibility(mf_old, mf_new, system)
        out.update({"eligibility": elig, "h2_eligible": elig["eligible"],
                    "verdict": elig["verdict"], "delta_type": elig["delta_type"],
                    "system": system})
        if not elig["eligible"]:
            out.update({"leakage": None, "leakage_pass": None, "t1": None, "t2": None,
                        "t3": None, "l0_l3": l0_l3, "untested": True, "accept": False})
            return out
        split = mf_new["split"]
        out["split"] = split
    else:
        # 시스템 대 시스템 비교는 검색 유용성 비교이지 H2 의 증거가 아니다(CLAUDE.md §0).
        out.update({"h2_eligible": False, "verdict": "system_comparison"})
    out["untested"] = False

    from ..analysis.metrics import load_run
    from ..analysis.results_table import _split_qrel, run_path
    from ..analysis.subgroup import query_labels
    from ..collect.bq_family_ir import load_family_map
    from .leakage_check import run_audit
    from .t1_noninferiority import t1_gate
    from .t2_subgroup import t2_gate
    from .t3_cross_task_cq import (
        commit_waiver,
        load_generation,
        log_waiver,
        run_cqs,
        suite_pass_rates,
        t3_gate,
    )

    if mode == "resource":
        pnew, pold = RS.run_file(mf_new, system), RS.run_file(mf_old, system)
    else:
        pnew = new or run_path("P1", split)
        pold = old or run_path("B3_rrf", split)

    leak = None if skip_leakage else run_audit(split, k)
    out["leakage"] = leak

    qrel = _split_qrel(split)
    fam = load_family_map()
    run_new, run_old = load_run(pnew), load_run(pold)
    out["runs"] = {"new": pnew.name, "old": pold.name}

    out["t1"] = t1_gate(run_new, run_old, qrel, family=fam, k=k)
    out["t2"] = t2_gate(run_new, run_old, qrel, fam, query_labels(qrel), k=k)

    g = graph or config.GRAPH_V1
    old_gen = load_generation(baseline)
    waiver = commit_waiver()
    out["t3"] = t3_gate(suite_pass_rates(run_cqs(g)), old_gen["suites"], waiver=waiver)
    out["t3"]["graph"] = str(g)
    out["t3"]["baseline_generation"] = old_gen["generation"]
    if out["t3"]["waived"]:
        log_waiver({"generation_old": old_gen["generation"], "graph": str(g),
                    "regressed": out["t3"]["regressed"], "reason": out["t3"]["waiver_reason"]})

    out["l0_l3"] = l0_l3
    # 누출 실패는 T1 의 전제 파괴다 — 승인식 앞단에서 곧바로 거부한다.
    leak_ok = True if leak is None else leak["pass"]
    out["leakage_pass"] = leak_ok
    out["accept"] = accept(l0_l3 and leak_ok, out["t1"]["pass"], out["t2"]["pass"],
                           out["t3"]["pass"])
    return out


_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _slug(text: str) -> str:
    """파일명 조각 정규화 — 라벨은 사람이 붙이므로 경로 문자가 섞일 수 있다."""
    return _SAFE.sub("-", str(text)).strip("-") or "na"


def report_path(mode: str, split: str, system: str = "P1",
                old_runset: str | None = None, new_runset: str | None = None,
                new: Path | None = None, old: Path | None = None) -> Path:
    """판정 JSON 의 기본 경로 — **실행 정체성을 파일명에 넣는다**(PLAN-060 §10).

    고정 경로 하나에 쓰면 다음 실행이 앞 실행을 지운다. 실제로 그렇게 지워졌다 —
    EP3(통제된 자원 교체)의 판정 JSON 이 2026-08-15 의 시스템 비교 실행에 덮여
    `data/processed` 가 gitignore 라 복구 경로가 없었고, −0.0293·+0.0401 은 동결
    사전등록(PLAN-035 §B)과 `concept_values.json` 에만 남았다. 파일명이 다르면
    두 실행은 서로를 지우지 못한다.
    """
    if mode == "resource":
        stem = f"resource__{_slug(old_runset)}__{_slug(new_runset)}__{_slug(system)}"
    else:
        n = _slug(new.stem if new else "P1")
        o = _slug(old.stem if old else "B3_rrf")
        stem = f"system__{n}__vs__{o}"
    return config.PROCESSED / f"tgate_report__{stem}__{_slug(split)}.json"


def guard_overwrite(path: Path, force: bool = False) -> None:
    """이미 있는 판정 파일을 말없이 덮지 않는다 — 판정 기록은 재생성이 보장되지 않는다.

    자원 팔은 `make vendor` 로 지나가면 되돌릴 수 없으므로, 같은 이름의 앞 실행을
    덮는 것은 사실상 삭제다. 덮으려면 **의도를 인자로 밝힌다**(`--force`).
    """
    if force or not path.exists():
        return
    raise SystemExit(
        f"[t-gate] 판정 파일이 이미 있다: {path}\n"
        "         덮으면 앞 실행의 판정이 사라진다(data/processed 는 gitignore 라 복구 경로가 "
        "없다).\n"
        "         다른 실행이면 --out 으로 이름을 나누고, 정말 덮을 것이면 --force 를 붙인다."
    )


def _visibility_lines(res: dict) -> list[str]:
    """자원 델타 가시성을 `Accept` 줄 **위**에 놓는다 (D-43 · PLAN-051).

    승인을 읽기 전에 그 승인이 무엇을 본 승인인지 읽게 하는 것이 이 줄의 존재 이유다.
    """
    from .runset import VIS_INVISIBLE, VIS_NO_EVIDENCE

    v = res.get("resource_visibility")
    if not v:
        return []
    note = v.get("note")
    mark = {VIS_INVISIBLE: "⚠", VIS_NO_EVIDENCE: "·"}.get(note, "?")
    lines = [f"  {mark} 자원 델타 가시성 = {note} "
             f"(pipeline={v.get('pipeline_short')} · snapshot={v.get('snapshot_short')})"]
    if v.get("detail"):
        lines.append(f"       {v['detail']}")
    if v.get("error"):
        lines.append(f"       ERROR: {v['error']}")
    if note == VIS_INVISIBLE:
        lines.append("       ⇒ 이 게이트로는 보이지 않는 델타다 — 결과를 '통과했다'로 적지 "
                     "않는다(CLAUDE.md §2.1).")
    return lines + [""]


def format_report(res: dict) -> str:
    from .leakage_check import format_report as leak_fmt
    from .t1_noninferiority import format_report as t1_fmt
    from .t2_subgroup import format_report as t2_fmt
    from .t3_cross_task_cq import format_report as t3_fmt

    from .runset import format_eligibility

    mode = res.get("mode", "system")
    lines = [f"═══ T-gate 종합 판정 (mode={mode} · split={res['split']} · "
             f"ε={res['epsilon']} · δ={res['delta']})"]
    if mode == "resource":
        lines += [format_eligibility(res["eligibility"]), ""]
        if res.get("untested"):
            lines += _visibility_lines(res)
            lines += [f"  ⇒ H2 미검정 ({res['verdict']}) — T1·T2 를 돌리지 않았다.",
                      "     자격 없는 비교로 '지지'를 만들지 않는다(CLAUDE.md §1-2).",
                      "  ⇒ Accept(ΔG) = 0  미검정"]
            return "\n".join(lines)
    lines += [f"  run: new={res['runs']['new']}  old={res['runs']['old']}", ""]
    if res["leakage"] is not None:
        lines += [leak_fmt(res["leakage"]), ""]
    lines += [t1_fmt(res["t1"]), "", t2_fmt(res["t2"]), "", t3_fmt(res["t3"]), ""]
    flags = [("L0–L3", res["l0_l3"]), ("누출감사", res["leakage_pass"]),
             ("T1", res["t1"]["pass"]), ("T2", res["t2"]["pass"]), ("T3", res["t3"]["pass"])]
    lines.append("  " + " · ".join(f"{n}={'✅' if v else '❌'}" for n, v in flags))
    lines.append("")
    lines += _visibility_lines(res)
    lines.append(f"  ⇒ Accept(ΔG) = {'1  승인' if res['accept'] else '0  거부'}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", "test_b", "all"], default="dev")
    ap.add_argument("--mode", choices=["system", "resource"], default="system",
                    help="system=시스템 대 시스템(기본) · resource=O 대 O′(H2 는 이쪽만)")
    ap.add_argument("--old-runset", default=None, help="resource 모드의 구 자원 run 세트 라벨")
    ap.add_argument("--new-runset", default=None, help="resource 모드의 신 자원 run 세트 라벨")
    ap.add_argument("--system", default="P1", help="resource 모드에서 비교할 단일 시스템")
    ap.add_argument("--new", type=Path, default=None, help="신 버전 run(기본 P1)")
    ap.add_argument("--old", type=Path, default=None, help="구 버전 run(기본 B3)")
    ap.add_argument("--graph", type=Path, default=None, help="T3 대상 그래프(기본 graph_v1)")
    ap.add_argument("--baseline", default="g0", help="T3 기준 세대 라벨")
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--l0-l3", dest="l0_l3", choices=["pass", "fail"], default="pass",
                    help="선행 L0–L3 결과(기본 pass — `make gate` 가 앞단에서 실행)")
    ap.add_argument("--skip-leakage", action="store_true", help="누출 감사 생략(진단 전용)")
    ap.add_argument("--out", type=Path, default=None,
                    help="판정 JSON 경로(기본: 실행 정체성이 들어간 이름 · report_path)")
    ap.add_argument("--force", action="store_true",
                    help="같은 이름의 앞 판정 파일을 덮는다 — 기본은 거부다")
    args = ap.parse_args()
    if args.split == "test_b":
        # T2 하위집단 판정은 A층 전용이다(PLAN-045 D5 · PLAN-047 §13.4). B층에는 공정군·
        # 거절근거 라벨의 원천이 없고, 그 상태로 δ 를 적용하면 사전등록이 정한 것과 **다른
        # 표본으로 같은 이름의 판정**을 내게 된다. 선택지로 받아 두고 **여기서 거부**하는
        # 이유는, 조용히 빠지는 것보다 시끄럽게 막히는 편이 안전하기 때문이다.
        raise SystemExit(
            "[t-gate] split=test_b 는 T-gate 대상이 아니다 — T1·T2 는 A층 판정 전용이다"
            "(PLAN-047 §13.4). 판독 B 는 results_table/ablation 으로 판정한다."
        )

    # 경로 결정과 덮어쓰기 가드는 **게이트를 돌리기 전에** 끝낸다 — 다 돌린 뒤에 거부하면
    # 계산을 버리게 되고, 그러면 다음 사람이 --force 를 습관적으로 붙인다.
    out = args.out or report_path(args.mode, args.split, args.system,
                                  args.old_runset, args.new_runset, args.new, args.old)
    guard_overwrite(out, args.force)

    res = run_tgate(args.split, args.new, args.old, args.graph, args.baseline,
                    l0_l3=(args.l0_l3 == "pass"), k=args.k, skip_leakage=args.skip_leakage,
                    mode=args.mode, old_runset=args.old_runset, new_runset=args.new_runset,
                    system=args.system)
    print(format_report(res))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"✓ {out}")
    # 0 승인 · 1 게이트 불통과 · 2 미검정. "떨어졌다"와 "재보지도 못했다"는 다른 문장이다.
    sys.exit(0 if res["accept"] else (2 if res.get("untested") else 1))


if __name__ == "__main__":
    main()
