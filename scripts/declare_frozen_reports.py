#!/usr/bin/env python3
"""PLAN-005 R0-CAL-3 — 동결 산출물의 **범위 선언**과 τ 출처의 코드화 (값을 재계산하지 않는다).

왜 별도 생성기인가.
`data/reports/priorart_baseline.json` 과 `prior_art_realgt_report.json` 은 2026-09-05 상태의
**동결 스냅샷**인데, 두 생성기에는 그 상태로 되돌릴 핀이 없다 — `report_stage7_remeasure.py` 가
기준선 parquet 에 `baseline_parquet_sha256_prefix` 를 거는 것과 달리, 저 둘은 오늘의 원천을 읽는다.
2026-09-12 실측: `report_priorart_baseline.py` 를 그대로 돌리면 값 **55개**가 달라진다
(V2·V3 질의 **759 → 804** — 단계 1 상태가 아니라 오늘 상태의 기준선이 나온다).
그래서 이 스크립트는 **값을 만들지 않는다.** 더하는 것은 선언뿐이다:
범위(`split="all"`) · 분할표 sha256 · 봉인 원장 행수 · 계측기 버전 · 동결 사유.

τ 의 출처도 여기서 코드가 된다.
`control_group`(τ = 0.6708 이 사는 블록)은 **생성기 산출이 아니었다** — 저장소 어디에도 그 키를
만드는 코드가 없고, `eval_prior_art_realgt.py` 산출에서 손으로 옮겨진 사본이었다. 즉 누구든
`report_priorart_baseline.py` 를 기본 경로로 돌리면 V2 게이트의 문턱이 조용히 사라지는 상태였다.
이 스크립트가 realgt 산출에서 그 블록을 **조립**하고, 기존 손 블록과 **한 자리라도 다르면 죽는다.**
그 실행은 두 가지를 동시에 한다 — 그 사본이 충실했다는 증명, 그리고 다음부터는 사람이 아니라
코드가 만든다는 선언.

**멱등이다.** 두 번 돌려도 같은 파일이 나온다(`--check` 는 쓰지 않고 대조만 한다).

CLI:
    python scripts/declare_frozen_reports.py            # 선언을 심는다
    python scripts/declare_frozen_reports.py --check    # 심긴 상태인지 대조만 (게이트용)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import seal, splits  # noqa: E402

BASELINE = ROOT / "data" / "reports" / "priorart_baseline.json"
REALGT = ROOT / "data" / "reports" / "prior_art_realgt_report.json"

INSTRUMENT_VERSION = "R0-CAL-3"

#: 이 선언이 더하는 키. 이 밖의 키는 한 자리도 건드리지 않는다(아래 _assert_values_untouched).
DECLARATION_KEYS = ("instrument_version", "split", "split_sha256", "seal_ledger_rows", "frozen_snapshot")

FROZEN_SNAPSHOT_NOTE = (
    "2026-09-05 상태의 동결 스냅샷이다. 생성기에 그 상태로 되돌릴 핀이 없어 **오늘 재실행하면 "
    "다른 값이 나온다**(2026-09-12 실측 · 값 55개 차이 · V2 질의 759 → 804). 그래서 CAL-3 은 값을 "
    "재계산하지 않고 범위 선언만 심었다 — 생성기 핀 부재는 별도 안건이다(PLAN-005 §20.13)."
)

SCOPE_NOTE = (
    "전량 범위다 — τ 의 출처이자 단계 7 `stage1_reproduction` 의 대조 기준이므로 분할을 걸지 "
    "않는다(§20.7 CAL-3). **홀드아웃 성능이 아니다.**"
)

CONTROL_GROUP_PROSE = {
    "decision": "2026-09-05 · 사용자 승인 — 기존 리포트 값을 그대로 쓴다. 재실행하지 않는다.",
    "source": "data/reports/prior_art_realgt_report.json (scripts/eval_prior_art_realgt.py 산출)",
    "caveat": (
        "대조군 0.4330 은 단일 수로 읽으면 안 된다 — 언어로 가르면 KR 0.6708 · FOREIGN 0.0074 다. "
        "온톨로지가 넘어야 할 선은 층별로 완전히 다르며, FOREIGN 층에서는 tfidf 가 사실상 0 이다. "
        "이 층화를 무시하면 '온톨로지가 tfidf 를 못 넘었다'와 '온톨로지가 tfidf 가 못 하는 층에서 "
        "이겼다'가 같은 수 하나에 뭉개진다(PLAN-003 §2.5 T2 하위집단 '언어')."
    ),
    "assembled_by": "scripts/declare_frozen_reports.py (CAL-3) — 손으로 쓰지 않는다",
}

METRICS = ("Recall@50", "Recall@10", "MRR", "NDCG@5")
RANKERS = ("tfidf", "onto", "onto_idf", "hybrid")


def build_control_group(realgt: dict) -> dict:
    """realgt 산출에서 대조군 블록을 조립한다 — τ 가 사는 자리다. 값을 새로 재지 않는다."""
    rs, inc = realgt["ranker_summary"], realgt["incremental_recall_sec5_2"]
    cg = {
        "decision": CONTROL_GROUP_PROSE["decision"],
        "source": CONTROL_GROUP_PROSE["source"],
        "n_queries": realgt["evaluable_targets"],
        **{r: {m: rs[r][m] for m in METRICS} for r in RANKERS},
        "language_stratified_R@50": {
            "tfidf_KR": inc["Recall@50_tfidf"]["KR"],
            "tfidf_FOREIGN": inc["Recall@50_tfidf"]["FOREIGN"],
            "hybrid_KR": inc["Recall@50_hybrid"]["KR"],
            "hybrid_FOREIGN": inc["Recall@50_hybrid"]["FOREIGN"],
            "gt_positives_KR": inc["gt_positives_in_corpus"]["KR"],
            "gt_positives_FOREIGN": inc["gt_positives_in_corpus"]["FOREIGN"],
        },
        "caveat": CONTROL_GROUP_PROSE["caveat"],
        "assembled_by": CONTROL_GROUP_PROSE["assembled_by"],
    }
    return cg


def assert_matches_handwritten(assembled: dict, existing: dict | None) -> list[str]:
    """조립한 블록이 손으로 들어간 블록과 같은지. 다르면 죽는다 — 사본의 충실성이 여기서 증명된다."""
    if not existing:
        return []
    bad = []
    for k, v in assembled.items():
        if k in ("assembled_by",) or k not in existing:
            continue
        if existing[k] != v:
            bad.append(f"{k}: 손 블록 {existing[k]!r} ≠ 조립 {v!r}")
    if bad:
        raise SystemExit("ERROR: 조립한 control_group 이 기존 손 블록과 다르다 — τ 의 출처가 흔들린다\n  "
                         + "\n  ".join(bad))
    return sorted(set(existing) - set(assembled))


def _assert_values_untouched(before: dict, after: dict, added: set[str]) -> None:
    """선언 키 밖의 값이 하나라도 달라졌으면 죽는다 — 이 스크립트는 값을 만들지 않는다."""
    for k, v in before.items():
        if k in added:
            continue
        if after.get(k) != v:
            raise SystemExit(f"ERROR: 값을 건드렸다 — '{k}' 가 달라졌다. 이 스크립트는 선언만 더한다")


def declare(doc: dict, *, control_group: dict | None = None) -> dict:
    """범위 선언을 심은 새 문서. 원 키의 순서와 값은 보존한다."""
    out = dict(doc)
    out["instrument_version"] = INSTRUMENT_VERSION
    out["split"] = "all"
    out["split_sha256"] = splits.sha256_of(splits.SPLIT_CSV)
    out["seal_ledger_rows"] = len(seal.ledger_rows())
    out["frozen_snapshot"] = {"note": FROZEN_SNAPSHOT_NOTE, "scope_note": SCOPE_NOTE,
                              "declared_by": "scripts/declare_frozen_reports.py"}
    if control_group is not None:
        out["control_group"] = control_group
    _assert_values_untouched(doc, out, set(DECLARATION_KEYS) | ({"control_group"} if control_group else set()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="쓰지 않고 심긴 상태인지 대조만 한다")
    a = ap.parse_args()

    realgt = json.loads(REALGT.read_text(encoding="utf-8"))
    base = json.loads(BASELINE.read_text(encoding="utf-8"))

    cg = build_control_group(realgt)
    dropped = assert_matches_handwritten(cg, base.get("control_group"))
    if dropped:
        raise SystemExit(f"ERROR: 손 블록에만 있던 키가 조립에서 빠진다: {dropped}")
    print(f"· control_group 조립 = 손 블록과 일치 (τ tfidf_KR {cg['language_stratified_R@50']['tfidf_KR']})")

    targets = [(REALGT, declare(realgt)), (BASELINE, declare(base, control_group=cg))]
    changed = []
    for path, new in targets:
        cur = path.read_text(encoding="utf-8")
        txt = json.dumps(new, ensure_ascii=False, indent=2) + "\n" if cur.endswith("\n") else \
            json.dumps(new, ensure_ascii=False, indent=2)
        rel = path.relative_to(ROOT)
        if txt == cur:
            print(f"· {rel} — 이미 선언됨 (멱등)")
            continue
        changed.append(str(rel))
        if a.check:
            print(f"· {rel} — **선언 없음** (make declare-scope 를 돌려야 한다)")
        else:
            path.write_text(txt, encoding="utf-8")
            print(f"· {rel} — 선언 심음 (split=all · 값 불변)")
    if a.check and changed:
        raise SystemExit(f"ERROR: 선언이 심기지 않은 리포트 {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
