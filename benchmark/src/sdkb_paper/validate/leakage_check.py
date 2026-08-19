"""누출 감사 단일 진입점 (PLAN-017 B6 · PLAN-018 §4 · PLAN-019 W3 · 원고 §4.5·§5.6·§10).

**왜 조립 시점 검사만으로는 부족한가.** `corpus/assemble.py` 는 코퍼스를 만들 때 금지 술어를
질의하지 않는다(FORBIDDEN 상수). 그러나 순위 산출은 그 뒤에도 여러 자원을 더 읽는다 — 개념축·
claim-feature sidecar·family 지도·후보 마스크. 조립이 깨끗해도 **런타임 피처 생성 시점**에
정답 파생 정보가 되돌아올 수 있다. 이 모듈은 그 잔여를 독립적으로 재검증하고, 하나라도 걸리면
비영 종료한다(우회 경로를 만들지 않는다 · CLAUDE.md §5).

다섯 검사:

- **L-1 코퍼스 피처** — IR 코퍼스의 컬럼명·개념값에 금지 술어(`hasPriorArt*`·`overPriorArt`·
  `NoveltyScore`) 유래 흔적이 0 인가.
- **L-2 런타임 피처 자원** — 개념축·feature sidecar 의 컬럼에 금지 술어 유래·qrel 파생
  (`relevance`·`qrel`·`is_positive` 류) 컬럼이 0 인가.
- **L-2b 개념 매핑 사전** — 개념 적용기의 입력 사전(CR-007)에 금지 술어·qrel 파생어·**문서
  식별자 모양의 표면형**이 0 인가. 사전이 없으면(=O 팔) 검사 대상이 없는 것이지 위반이 아니다.
- **L-3 run 마스크 잔여** — 산출된 run 상위 K 에 F10 위반(자기 자신·동일 패밀리·시점 미래)이
  0 인가. 마스크가 코드에 있다는 것과 산출물이 실제로 지켜졌다는 것은 다른 명제다.
- **L-4 qrel 봉인 상태** — qrel 파일 sha256 과 봉인 test qrel 존재 여부를 기록한다(차단 아님·기록).

- **경계:** 이 모듈은 데이터를 고치지 않는다. 판정하고 보고할 뿐이다(CLAUDE.md §3).

CLI: `python -m sdkb_paper.validate.leakage_check [--split dev] [--k 100]`  → 위반 시 exit 1.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tempfile
from pathlib import Path

from .. import config

# 문서 피처로 절대 들어오면 안 되는 누출원 (corpus/assemble.FORBIDDEN 과 같은 목록 · 단일 정의).
from ..corpus.assemble import FORBIDDEN

# qrel 에서 파생된 값임을 드러내는 컬럼명 조각. 피처 자원에 있으면 정답이 새어든 것이다.
QREL_DERIVED = ("relevance", "qrel", "is_positive", "prior_art", "priorart", "cited_by_examiner")


def _norm(s: str) -> str:
    return s.replace("_", "").replace("-", "").lower()


def check_names(names: list[str], forbidden: tuple[str, ...] = FORBIDDEN) -> list[str]:
    """이름 목록(컬럼·필드)에서 금지 술어 유래 항목을 찾는다. 대소문자·구분자 무시."""
    bad = []
    for n in names:
        nn = _norm(str(n))
        if any(_norm(f) in nn for f in forbidden):
            bad.append(str(n))
    return bad


def check_qrel_derived(names: list[str]) -> list[str]:
    """qrel 파생 컬럼(정답 라벨 그 자체)이 피처 자원에 섞였는지."""
    return check_names(names, QREL_DERIVED)


# 문서 식별자로 보이는 표면형 — 사전이 개념 어휘가 아니라 **정답 문서**를 가리키면 그것은 누출이다.
# 특허 식별자는 국가코드+긴 숫자이거나 6자리 이상 숫자열이다(정상 표면형에는 나오지 않는다).
_DOC_ID_RX = re.compile(r"(?:\b(?:kr|us|jp|ep|wo|cn)[\s_-]?\d{4,})|(?:\d{6,})")


def check_doc_identifiers(values: list[str]) -> list[str]:
    """사전 표면형에 문서 식별자 모양이 섞였는지(개념 사전은 어휘만 담아야 한다)."""
    return sorted({str(v) for v in values if _DOC_ID_RX.search(str(v).lower())})


def audit_concept_dict(path: Path | None = None) -> dict:
    """L-2b: 개념 매핑 사전 자체(PLAN-034 §3.6).

    상류는 `leakage_note` 로 "인용 간선을 보지 않았다"고 진술한다. 그 진술을 믿지 않고
    **파일을 열어** 표면형·concept_id 를 전량 검사한다 — 사전은 이제 코퍼스 `concepts` 열의
    절반 이상을 만드는 런타임 피처 자원이다.
    """
    from ..ontology import concept_dict as CD

    p = Path(path) if path is not None else config.SDKB_CONCEPT_MAP
    if not p.exists():   # O 팔(CR-007 이전 스냅샷) — 검사할 사전이 없는 것은 위반이 아니다
        return {"check": "L-2b 개념 매핑 사전", "exists": False, "pass": True}
    surfaces = CD.load(p)
    surf_texts = [s.text for s in surfaces]
    cids = [e.concept_id for s in surfaces for e in s.entries]
    bad_forbidden = sorted(set(check_names(surf_texts + cids)))
    bad_qrel = sorted(set(check_qrel_derived(surf_texts + cids)))
    bad_docid = check_doc_identifiers(surf_texts)
    return {"check": "L-2b 개념 매핑 사전", "exists": True, "file": p.name,
            "sha256": sha256_file(p), "n_surfaces": len(surfaces), "n_concepts": len(set(cids)),
            "bad_columns": bad_forbidden + bad_qrel, "bad_doc_identifiers": bad_docid,
            "pass": not bad_forbidden and not bad_qrel and not bad_docid}


def check_concept_values(values: list[str]) -> list[str]:
    """개념 링크 값에 금지 술어 유래 IRI/지역명이 섞였는지 (샘플이 아니라 전량 검사)."""
    return sorted(set(check_names(values)))


def check_run_mask(run: dict[str, list[str]], is_allowed, k: int = 100) -> list[dict]:
    """run 상위 K 의 F10 위반 목록. 빈 목록 = 통과.

    `is_allowed(qid, doc_id) -> bool` 은 `retrieval.candidate.CandidateMask.is_allowed` 를 받는다
    (analysis 가 마스크를 재구현하지 않는다 — 정본은 retrieval 쪽 하나뿐).
    """
    viol = []
    for qid, ranked in run.items():
        for rank, doc in enumerate(ranked[:k], start=1):
            if not is_allowed(qid, doc):
                viol.append({"query_id": qid, "doc_id": doc, "rank": rank})
    return viol


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- 파일을 실제로 여는 층 (테스트는 위의 순수 함수를 때린다) -------------------

def audit_corpus() -> dict:
    """L-1: IR 코퍼스 컬럼·개념값."""
    import pandas as pd

    df = pd.read_parquet(config.IR_CORPUS)
    bad_cols = check_names(list(df.columns))
    vals: list[str] = []
    if "concepts" in df.columns:
        for c in df["concepts"]:
            if c is not None:
                vals.extend(str(x) for x in c)
    bad_vals = check_concept_values(vals)
    return {"check": "L-1 코퍼스 피처", "n_rows": len(df), "n_cols": len(df.columns),
            "bad_columns": bad_cols, "bad_concept_values": bad_vals,
            "pass": not bad_cols and not bad_vals}


def audit_feature_sources() -> dict:
    """L-2: 런타임 피처 자원(개념축·claim-feature sidecar)."""
    import pandas as pd

    bad: dict[str, list[str]] = {}
    checked = []
    for name, path in (("concept_axis", config.IR_CONCEPT_AXIS),
                       ("feature_sidecar", config.IR_FEATURE_SIDECAR)):
        if not Path(path).exists():
            continue
        cols = list(pd.read_parquet(path).columns)
        checked.append(name)
        hits = check_names(cols) + check_qrel_derived(cols)
        if hits:
            bad[name] = sorted(set(hits))
    return {"check": "L-2 런타임 피처 자원", "checked": checked, "bad_columns": bad,
            "pass": not bad}


def audit_runs(split: str, k: int = 100) -> dict:
    """L-3: 동결 run 상위 K 의 F10 마스크 잔여."""
    from ..analysis.metrics import load_run
    from ..analysis.results_table import SYSTEM_LABELS, run_path
    from ..retrieval.candidate import CandidateMask

    mask = CandidateMask()
    rows, total_viol = [], 0
    for sysname, _label in SYSTEM_LABELS:
        p = run_path(sysname, split)
        if not p.exists():
            continue
        viol = check_run_mask(load_run(p), mask.is_allowed, k)
        total_viol += len(viol)
        rows.append({"system": sysname, "run": p.name, "violations": len(viol),
                     "examples": viol[:3]})
    return {"check": f"L-3 run 마스크 잔여 (top-{k} · split={split})", "systems": rows,
            "n_violations": total_viol, "n_runs": len(rows), "pass": total_viol == 0}


def audit_graph(graph_path: Path, baseline: int | None = None) -> dict:
    """G-층: **그래프 자체**의 누출 표면 (PLAN-020 W4 · 결함주입 F09·F10 표적).

    L-1/L-2 는 산출물의 **컬럼명**을 본다. 그런데 정답 간선을 개념 링크로 **위장**해 넣으면
    (`hasPriorArtExaminer` 의 대상 문서를 `realizesProcess` 의 객체로) 이름 검사는 그대로
    통과한다 — 실제로 결함주입 F10 이 그렇게 만든다. 이름이 아니라 **모양**을 봐야 한다.

    - **G-1 문서-as-개념:** 개념 술어의 객체가 문서(Patent/RejectedPatent/CitedPatent) 타입인가.
      개념 자리에 문서가 들어오는 것은 정상 그래프에 없어야 할 모양이다 → 위반 수가 판정.
    - **G-2 금지 술어 개념화:** 금지 술어가 개념 링크 술어로 쓰였는가(구조적으로 0 이어야).
    - **G-3 정답 개념 복사:** 질의의 개념 집합이 자기 정답 문서의 개념 집합을 **통째로 포함**하는
      (질의, 정답) 쌍 수. 정답을 보지 않고는 만들기 어려운 모양이라 F09(시간 누출)의 서명이다.
      정상 그래프에서도 우연한 포함이 **552쌍** 있으므로(실측 2026-07-28 · graph_v0) 이 값은
      절대 임계로 쓸 수 없다. 판정은 **같은 기준 그래프 대비 증가**로 한다 — 결함주입은 기준
      그래프에서 결함만 다른 사본을 만들므로, 증가분은 전부 주입에 귀속된다(통계가 아니라 차분).
      `baseline` 미지정 시 G-3 은 기록만 하고 판정에 넣지 않는다.
    """
    from pyoxigraph import RdfFormat, Store

    from ..corpus.assemble import CONCEPT_PROPS
    from .fault_inject import DOC_TYPES, ONT

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(path=str(Path(tmp) / "audit"))
        with open(graph_path, "rb") as fh:
            store.bulk_load(fh, format=RdfFormat.TURTLE)

        props = " ".join(f"ont:{p}" for p in CONCEPT_PROPS)
        types = " ".join(f"ont:{t}" for t in DOC_TYPES)
        g1 = int(next(iter(store.query(
            f"PREFIX ont:<{ONT}> SELECT (COUNT(*) AS ?n) WHERE {{"
            f" VALUES ?p {{ {props} }} VALUES ?t {{ {types} }} ?s ?p ?o . ?o a ?t }}")))["n"].value)

        concepts: dict[str, set[str]] = {}
        for r in store.query(f"PREFIX ont:<{ONT}> SELECT ?s ?c WHERE "
                             f"{{ VALUES ?p {{ {props} }} ?s ?p ?c }}"):
            concepts.setdefault(r["s"].value, set()).add(r["c"].value)
        gold: dict[str, set[str]] = {}
        for r in store.query(f"PREFIX ont:<{ONT}> SELECT ?q ?g WHERE "
                             f"{{ ?q a ont:RejectedPatent ; ont:hasPriorArtExaminer ?g }}"):
            gold.setdefault(r["q"].value, set()).add(r["g"].value)

    g3 = sum(1 for q, gs in gold.items() for g in gs
             if concepts.get(g) and concepts[g] <= concepts.get(q, set()))

    bad_props = [p for p in CONCEPT_PROPS if any(_norm(f) in _norm(p) for f in FORBIDDEN)]
    g3_over = baseline is not None and g3 > baseline
    return {"check": f"G 그래프 누출 표면 ({Path(graph_path).name})",
            "g1_doc_as_concept": g1, "g2_forbidden_concept_props": bad_props,
            "g3_gold_concept_copy_pairs": g3, "g3_baseline": baseline, "g3_exceeds": g3_over,
            "pass": g1 == 0 and not bad_props and not g3_over}


def audit_qrel() -> dict:
    """L-4: qrel 해시·봉인 상태 기록(차단하지 않는다 — 증거 기록이 목적)."""
    out = {"check": "L-4 qrel 봉인·해시", "pass": True}
    for key, path in (("qrel_examiner", config.QREL_EXAMINER),
                      ("qrel_test_sealed", config.IR_QREL_TEST_SEALED)):
        out[key] = {"exists": Path(path).exists(),
                    "sha256": sha256_file(path) if Path(path).exists() else None}
    return out


def run_audit(split: str = "dev", k: int = 100) -> dict:
    checks = [audit_corpus(), audit_feature_sources(), audit_concept_dict(),
              audit_runs(split, k), audit_qrel()]
    return {"split": split, "k": k, "checks": checks,
            "pass": all(c["pass"] for c in checks)}


def format_report(res: dict) -> str:
    lines = [f"[leakage_check] split={res['split']} · top-{res['k']}",
             "─" * 60]
    for c in res["checks"]:
        lines.append(f"  {'✅' if c['pass'] else '❌'} {c['check']}")
        for key in ("bad_columns", "bad_concept_values", "bad_doc_identifiers"):
            if c.get(key):
                lines.append(f"       {key}: {c[key]}")
        if "n_violations" in c:
            lines.append(f"       위반 {c['n_violations']}건 · 검사 run {c['n_runs']}개")
            for row in c["systems"]:
                if row["violations"]:
                    lines.append(f"       - {row['system']}: {row['violations']}건 "
                                 f"예 {row['examples']}")
        if c["check"].startswith("L-4"):
            for key in ("qrel_examiner", "qrel_test_sealed"):
                v = c[key]
                lines.append(f"       {key}: exists={v['exists']} sha256="
                             f"{(v['sha256'] or '')[:16]}")
    lines.append("─" * 60)
    lines.append(f"  누출 감사 = {'PASS (금지간선 잔여 0)' if res['pass'] else 'FAIL'}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    # test_b: 판독 B 의 run 도 같은 감사를 받는다 — qrel 은 읽지 않으므로 개봉과 무관하다
    # (L-4 는 봉인 파일의 **해시만** 본다 · PLAN-047 §5 G3).
    ap.add_argument("--split", choices=["train", "dev", "test", "test_b", "all"], default="dev")
    ap.add_argument("--k", type=int, default=100)
    args = ap.parse_args()
    res = run_audit(args.split, args.k)
    print(format_report(res))
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
