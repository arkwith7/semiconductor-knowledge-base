#!/usr/bin/env python3
"""PLAN-005 R0-CAL-0 — 누설 검사 K-1…K-6 (읽기 전용 · 그래프를 바꾸지 않는다).

§11.4 가 *"존재하지 않는다"* 고 적은 그 파일이다. 상류 `benchmark/` 의 감사기를 되살리지
않은 이유 셋(§20.7): ① `build_public_release.py:76` 이 그 디렉터리를 통째로 공개 트리에
싣고 *"여기서 편집하면 사본이 갈린다(D-38)"* 를 못박는다 ② 그쪽은 자산 스냅샷이지 입력
디렉터리를 갖는 파이프라인이 아니다 ③ 검사 대상이 다르다(IR run·qrel 대 우리의 질의∩채굴
범위·사전·분할·봉인). **재사용은 파일이 아니라 술어를 한다** — 정의를 옮기고 혈통을 여기 적는다.

상태 넷:
  PASS          검사가 돌았고 통과했다
  FAIL          검사가 돌았고 위반이다 — 종료코드 1
  PENDING       검사 대상 산출물이 **아직 만들어지지 않았다**(CAL-3 이 만든다 · 사용자 결정 B).
                거짓 FAIL 로 두지 않고 상태를 인쇄한다. CAL-3 완료 후에도 남아 있으면 CAL-3 이 미완이다
  UNMEASURABLE  데이터가 없어 잴 수 없다 — **0 으로 보고하지 않는다**(§20.7 K-6)

결정성: 같은 워킹트리 → 산출 JSON 이 바이트 동일하다. 그래서 `generated` 날짜 키를 넣지
않는다 — 넣으면 두 실행의 바이트가 갈려 재현성 검사 자체가 못 돈다. 대신 입력 sha256 을 적는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import seal
from scripts.splits import (
    ROOT,
    SEALED,
    SPLIT_CSV,
    HARVEST_SCOPE,
    assert_scope_agreement,
    load_split,
    sha256_of,
    split_composition,
)

OUT = ROOT / "data" / "reports" / "leakage_check.json"

HARVEST_ARTIFACTS = [
    ROOT / "data" / "reports" / "ko_surface_candidates.json",
    ROOT / "data" / "reports" / "ko_concept_proposals.json",
    ROOT / "data" / "reports" / "notice_element_judgments_report.json",
]
MAPPING_ARTIFACTS = [
    ROOT / "mappings" / "abox_term_aliases.json",
    ROOT / "mappings" / "concept_mapping.json",
]
EVAL_REPORTS = [
    ROOT / "data" / "reports" / "priorart_stage7_remeasure.json",
    ROOT / "data" / "reports" / "prior_art_realgt_report.json",
    ROOT / "data" / "reports" / "priorart_baseline.json",
    ROOT / "data" / "reports" / "v4_robustness.json",
    ROOT / "data" / "reports" / "v7_coverage_rank.json",   # CAL-2 — split=dev 를 선언하므로 봉인 id 가 0 이어야 한다
] + sorted(                                    # CAL-3 — 분할 산출물도 같은 규율을 받는다
    p for pat in ("v4_robustness.*.json", "prior_art_realgt_report.*.json")
    for p in (ROOT / "data" / "reports").glob(pat)
)
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
FEATURES = ROOT / "mappings" / "claim_features.parquet"

# 분할표의 doc_id 모양. 키 이름이 아니라 **값의 모양**으로 찾는 이유는, 스키마가 바뀌어
# 다른 키로 새면 키 기반 검사는 그것을 못 잡기 때문이다.
DOC_ID_RX = re.compile(r"(?<![0-9A-Za-z_])kr_10\d{11}(?![0-9])")
# K-3 — 사전에 문서 식별자가 섞이면 개념이 문서를 외운 것이 된다.
IDENTIFIER_RX = [
    ("doc_id", DOC_ID_RX),
    ("kipris_pub", re.compile(r"(?<![0-9A-Za-z])KR\d{10,13}(?![0-9])")),
    ("app_no_dashed", re.compile(r"(?<![0-9])10-\d{4}-\d{7}(?![0-9])")),
]


def _rel(p: Path) -> str:
    """ROOT 기준 상대경로. 밖이면 그대로 — 주입 픽스처는 저장소 밖에 있다."""
    p = Path(p)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def _walk_strings(o, path="$"):
    """JSON 을 재귀 순회하며 (경로, 문자열) 을 낸다. 키 이름도 문자열로 본다."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{path}.{k}", str(k)
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


def _result(cid, status, detail, **numbers):
    return {"id": cid, "status": status, "detail": detail, "numbers": numbers}


def k1_split_frozen(split_map):
    try:
        facts = assert_scope_agreement(split_map=split_map)
    except SystemExit as e:
        return _result("K-1", "FAIL", str(e))
    return _result(
        "K-1",
        "PASS",
        "split.csv sha · 상류 parquet sha · dev∪train == 채굴 범위 · excluded_splits 넷 모두 일치",
        **{k: v for k, v in facts.items() if k != "scope_file"},
    )


def k2_harvest_outputs(split_map):
    sealed_ids = {d for d, s in split_map.items() if s in SEALED}
    hits, scanned, missing = defaultdict(list), [], []
    for p in HARVEST_ARTIFACTS:
        if not p.exists():
            missing.append(_rel(p))
            continue
        scanned.append(_rel(p))
        doc = json.loads(p.read_text(encoding="utf-8"))
        for where, s in _walk_strings(doc):
            for m in DOC_ID_RX.findall(s):
                if m in sealed_ids:
                    hits[_rel(p)].append({"doc_id": m, "at": where})
    n = sum(len(v) for v in hits.values())
    if missing:
        return _result(
            "K-2", "FAIL", f"채굴 산출물이 없다: {missing}", files_scanned=scanned, missing=missing
        )
    status = "PASS" if n == 0 else "FAIL"
    detail = (
        "채굴 산출물 전 문자열에 봉인 분할 문서 식별자 0건"
        if n == 0
        else f"봉인 문서가 채굴 산출물에 {n}건 적중 — 어휘가 봉인을 보았다"
    )
    return _result(
        "K-2",
        status,
        detail,
        files_scanned=scanned,
        sealed_hits=n,
        hits={k: v[:20] for k, v in sorted(hits.items())},
    )


def k3_dictionaries():
    found, scanned, missing = defaultdict(list), [], []
    for p in MAPPING_ARTIFACTS:
        if not p.exists():
            missing.append(_rel(p))
            continue
        scanned.append(_rel(p))
        doc = json.loads(p.read_text(encoding="utf-8"))
        for where, s in _walk_strings(doc):
            for name, rx in IDENTIFIER_RX:
                for m in rx.findall(s):
                    found[_rel(p)].append({"kind": name, "value": m, "at": where})
    n = sum(len(v) for v in found.values())
    if missing:
        return _result("K-3", "FAIL", f"사전 파일이 없다: {missing}", missing=missing)
    status = "PASS" if n == 0 else "FAIL"
    detail = (
        "별칭·개념 매핑에 문서 식별자 모양 0건"
        if n == 0
        else f"사전에 문서 식별자 모양 {n}건 — 개념이 문서를 외웠을 수 있다"
    )
    return _result(
        "K-3", status, detail, files_scanned=scanned, identifier_hits=n,
        hits={k: v[:20] for k, v in sorted(found.items())},
    )


def k4_eval_reports(split_map):
    sealed_ids = {d for d, s in split_map.items() if s in SEALED}
    per_file, pending, failing = {}, [], []
    for p in EVAL_REPORTS:
        rel = _rel(p)
        if not p.exists():
            per_file[rel] = "MISSING"
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if "split" not in doc or "split_sha256" not in doc:
            per_file[rel] = "PENDING(CAL-3)"
            pending.append(rel)
            continue
        if doc.get("split") == "all":
            per_file[rel] = "scope=all"
            continue
        ids = {m for _, s in _walk_strings(doc) for m in DOC_ID_RX.findall(s)}
        bad = sorted(ids & sealed_ids)
        per_file[rel] = f"split={doc['split']} · 봉인 적중 {len(bad)}"
        if bad:
            failing.append({"file": rel, "split": doc["split"], "sealed_hits": bad[:20]})
    if failing:
        return _result("K-4", "FAIL", "분할을 선언한 리포트에 봉인 질의가 있다",
                       files=per_file, failing=failing)
    if pending:
        return _result(
            "K-4", "PENDING",
            f"평가 리포트 {len(pending)}종에 split·split_sha256 키가 없다 — CAL-3 이 만든다 (사용자 결정 B)",
            files=per_file, pending=pending,
        )
    return _result("K-4", "PASS", "분할을 선언한 평가 리포트에 봉인 질의 0건", files=per_file)


def k5_seal_ledger():
    rows = seal.ledger_rows(seal.LEDGER)
    ok, problems = seal.ledger_is_wellformed(seal.LEDGER)
    if not ok:
        return _result("K-5", "FAIL", "봉인 원장 서식 위반", ledger_rows=len(rows), problems=problems[:20])
    declared = {}
    for p in EVAL_REPORTS:
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if "seal_ledger_rows" in doc:
            declared[_rel(p)] = doc["seal_ledger_rows"]
    mismatch = {k: v for k, v in declared.items() if v != len(rows)}
    if mismatch:
        return _result("K-5", "FAIL", "리포트가 적은 원장 행 수가 실제와 다르다",
                       ledger_rows=len(rows), declared=declared)
    if not declared:
        return _result(
            "K-5", "PENDING",
            f"원장 {len(rows)}행 · 서식 정상. 평가 리포트에 seal_ledger_rows 키가 없다 — "
            "CAL-3 이 만든다 (사용자 결정 B 와 같은 부류)",
            ledger_rows=len(rows),
        )
    return _result("K-5", "PASS", "원장 서식 정상 · 리포트의 행 수 선언과 일치",
                   ledger_rows=len(rows), declared=declared)


def k6_family(split_map):
    fam = defaultdict(set)
    import csv as _csv

    for r in _csv.DictReader(SPLIT_CSV.open(encoding="utf-8")):
        if r.get("family_id", "").strip():
            fam[r["family_id"]].add(r["split"])
    crossing = sorted(f for f, s in fam.items() if len(s) > 1)

    import pandas as pd

    cols = list(pd.read_parquet(EDGES).columns)
    cited_family_cols = [c for c in cols if "famil" in c.lower() and "cited" in c.lower()]
    cited_date_cols = [c for c in cols if ("date" in c.lower() or "filing" in c.lower()) and "cited" in c.lower()]
    unmeasurable = {
        "cited_family": {
            "reason": "prior_art_edges 에 인용문헌 family 열이 없다",
            "columns_present": cols,
            "matched": cited_family_cols,
        },
        "cited_filing_date": {
            "reason": "prior_art_edges 에 인용문헌 출원일 열이 없다",
            "matched": cited_date_cols,
        },
    }
    if cited_family_cols or cited_date_cols:
        return _result(
            "K-6", "FAIL",
            "인용문헌 family·출원일 열이 생겼다 — UNMEASURABLE 선언이 낡았다. 검사를 구현하라",
            families=len(fam), crossing=len(crossing), unmeasurable=unmeasurable,
        )
    if crossing:
        return _result("K-6", "FAIL", f"family 가 분할을 넘는다: {len(crossing)}건",
                       families=len(fam), crossing_examples=crossing[:20])
    return _result(
        "K-6", "UNMEASURABLE",
        f"질의 family {len(fam)}개가 분할을 넘지 않는다(교차 0 · 회귀 고정). "
        "인용문헌 family·출원일은 데이터가 없어 잴 수 없다 — 0 으로 보고하지 않는다",
        families=len(fam), crossing=0, unmeasurable=unmeasurable,
    )


def query_universe(split_map):
    """부수 산출 (사용자 결정 A) — 평가 분모의 분할 구성을 처음으로 실측한다."""
    import pandas as pd

    ed = pd.read_parquet(EDGES)
    ex = ed[ed.source_type == "examiner"].copy()
    ex["tgt"] = ex.target_patent_id.str.replace("^patent:", "", regex=True)
    ex["cit"] = ex.cited_id.str.replace("^patent:", "", regex=True)
    gt_targets = set(ex.tgt)

    disc = set(pd.read_parquet(FEATURES, columns=["publication_id"]).publication_id.unique())
    ok = ex[ex.cit.isin(disc) & (ex.cit != ex.tgt)]
    approx_q = set(ok.tgt)

    return {
        "gt_bearing": {
            "definition": "prior_art_edges 의 examiner 간선을 가진 target",
            "n": len(gt_targets),
            "composition": split_composition(gt_targets, split_map=split_map),
            "approximate": False,
        },
        "reachable_target_approx": {
            "definition": "위 중 인용문헌 하나 이상이 claim_features 에 publication_id 로 있고 자기 자신이 아닌 것",
            "n": len(approx_q),
            "composition": split_composition(approx_q, split_map=split_map),
            "approximate": True,
            "note": "평가 스크립트의 Q(개념 바인딩·Disclosure 조건)는 이보다 좁다. "
                    "정확한 구성비는 CAL-3 이 낸다 (사용자 결정 A)",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="PLAN-005 R0-CAL-0 누설 검사")
    ap.add_argument("--json", type=Path, default=OUT)
    args = ap.parse_args()

    split_map = load_split()
    checks = [
        k1_split_frozen(split_map),
        k2_harvest_outputs(split_map),
        k3_dictionaries(),
        k4_eval_reports(split_map),
        k5_seal_ledger(),
        k6_family(split_map),
    ]
    tally = Counter(c["status"] for c in checks)
    report = {
        "plan": "PLAN-005 R0-CAL-0 · 평가 무결성 배선 (§20.7)",
        "generator": "scripts/check_leakage.py",
        "read_only": True,
        "inputs": {
            _rel(p): sha256_of(p)
            for p in [SPLIT_CSV, HARVEST_SCOPE, *HARVEST_ARTIFACTS, *MAPPING_ARTIFACTS, EDGES, FEATURES]
            if p.exists()
        },
        "checks": checks,
        "query_universe": query_universe(split_map),
        "summary": {
            "pass": tally["PASS"], "fail": tally["FAIL"],
            "pending": tally["PENDING"], "unmeasurable": tally["UNMEASURABLE"],
            "ok": tally["FAIL"] == 0,
        },
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                         encoding="utf-8")

    for c in checks:
        mark = {"PASS": "  ok", "FAIL": "FAIL", "PENDING": "PEND", "UNMEASURABLE": "UNMS"}[c["status"]]
        print(f"[{mark}] {c['id']}  {c['detail']}")
    print(f"\n→ {_rel(args.json)}  "
          f"(PASS {tally['PASS']} · FAIL {tally['FAIL']} · PENDING {tally['PENDING']} · "
          f"UNMEASURABLE {tally['UNMEASURABLE']})")
    if tally["PENDING"]:
        print("※ PENDING 은 CAL-3 이 만들 산출물을 기다리는 상태다. CAL-3 완료 후에도 남으면 CAL-3 이 미완이다.")
    return 1 if tally["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
