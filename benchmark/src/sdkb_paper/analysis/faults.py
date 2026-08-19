"""결함주입 × 게이트 층 검출 매트릭스 + McNemar (원고 §4.10·§6.5 · H1 · PLAN-020 W4).

각 결함 인스턴스(결함 12종 × 강도 3 × 반복 R)에 대해 **7개 층 전부**를 돌려 "어느 층이 이
결함을 잡는가"를 기록한다. H1 의 직접 검정은 마지막 두 교차결함(F11 동의어 오병합 · F12 공유
계층 역전)이 **L0–L3·T1·T2 를 통과하고 T3 에서만** 검출되는가다.

층 판정 (사전 정의 · 결과를 보고 바꾸지 않는다):

| 층 | 검출 조건 |
|---|---|
| L0 | 산출물이 입력보다 낡음(mtime 역전) |
| L1 | SHACL 비적합 |
| L2 | HermiT 비일관 |
| L3 | 전 스위트(pa 포함) CQ 통과 수 < 정상 그래프 |
| 누출 | 그래프 누출 표면 G-1 위반>0 또는 G-3 이 정상 기준선 초과 |
| T1 | LB₉₅(ΔR₁₀₀) ≤ −ε — 결함본 P1 vs 정상 B3 |
| T2 | max_s drop_s ≥ δ |
| T3 | {em,tf,core} 통과율이 정상 세대보다 하락 |

**CQ 조회 대상 고정 (PLAN-023 · 2026-07-28).** 이 모듈의 `run_cqs` 호출은 전부
`targets=("graph",)` 다. 결함은 격리본 **TTL 에만** 주입되므로 사이드카(청구항 층) 조회는
무의미하고, 무엇보다 표 6.5·6.5v2·6.5v3 이 **28-CQ 체제로 동결**돼 있어 CQ 를 늘린 뒤에도
같은 명령이 같은 수를 내야 한다. 이 인자를 빼면 동결된 결함 실험의 재현성이 깨진다.

**오염 규율.** 결함 그래프·파생 뷰는 `validate.quarantine` 격리 디렉터리에만 쓰고, 인스턴스마다
정본 해시를 재검증한다. 정본이 한 바이트라도 변하면 즉시 중단한다(부분 오염으로 가둔다).

**비용.** 인스턴스당 L2(HermiT)가 55초로 지배적이고 최대 RSS 는 750MB 다 — GPU 가속 대상이
아니며(기호 추론), 24코어 CPU 병렬이 유일한 지렛대다. 기본 워커 수는 12.

CLI: `python -m sdkb_paper.analysis.faults --reps 3 --workers 12`
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .. import config
from ..validate import fault_inject as FI
from ..validate import quarantine as Q

LAYERS = ("L0", "L1", "L2", "L3", "leak", "T1", "T2", "T3")
REPORT = config.PROCESSED / "fault_matrix.json"
BASELINE = config.PROCESSED / "fault_baseline.json"


# --- 정상 그래프 기준선 (오염 **전에** 한 번 재고 동결) -------------------------
def measure_baseline(graph: Path | None = None) -> dict:
    """결함 없는 G₀ 의 층별 기준값. 모든 검출 판정이 이 값과의 차분이다."""
    from ..validate.cq_runner import run_cqs, suite_pass_rates
    from ..validate.leakage_check import audit_graph

    g = graph or config.GRAPH_V0
    res = run_cqs(g, targets=("graph",))
    leak = audit_graph(g)
    return {"graph": str(g), "n_cq_pass": sum(r.passed for r in res), "n_cq": len(res),
            "suites": suite_pass_rates(res),
            # T3′(세분화 대리지표)의 기준선 — PLAN-020 §5-1 에서 **결과를 보기 전에** 예고한
            # 약점(CQ 28개 중 26개가 `expect-min: 1` 존재검사)을 계량하기 위한 것이다.
            # 통과/불통과가 아니라 **결과행 수**가 줄었는지를 본다: 세분화된 CQ 라면 잡았을
            # 회귀를 현행 CQ 가 얼마나 놓치는가의 측정. 게이트 판정에는 넣지 않는다.
            "cq_rows": {r.name: r.rows for r in res},
            "cq_suite": {r.name: r.suite for r in res},
            "g1_doc_as_concept": leak["g1_doc_as_concept"],
            "g3_gold_concept_copy_pairs": leak["g3_gold_concept_copy_pairs"]}


def load_baseline() -> dict:
    if not BASELINE.exists():
        raise FileNotFoundError(f"기준선 없음: {BASELINE} (--baseline 먼저)")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


# --- 결함 그래프에서 온톨로지 뷰 재유도 ----------------------------------------
def faulted_features(fault_key: str, strength: float, seed: int, ws: Path):
    """**검색이 실제로 보는 자원 전체**(G₀∪G₁∪G₂)에 같은 결함을 넣고 개념·분류·축 뷰를 다시 만든다.

    왜 G₀ 사본만으로는 안 되는가 — 실측(2026-07-28): 개념 링크 81,504건 중 G₀ 는 9,184건
    (**11.3%**)뿐이다. G₀ 에만 10% 를 주입하면 검색이 보는 자원의 1.1% 만 오염돼 T1 이 둔감해지고,
    그 둔감함은 **게이트의 성질이 아니라 주입 범위의 산물**이 된다. 그래서 형식층(L0–L3·T3)은
    G₀ 사본에서, 성능층(T1·T2)은 합집합에서 판정한다 — 결함 사양·강도·시드는 같다.

    합집합 오염본은 **디스크에 쓰지 않는다**(인스턴스당 ~370MB × 108 = 40GB). 임시 스토어에서
    주입하고 뷰만 뽑는다. 텍스트 팔(B0·B2·B3)·임베딩·색인은 결함군 12종이 건드리지 않으므로
    동결본을 그대로 쓴다 — 비용 절감이자 통제다(텍스트 변동이 T1 판정에 섞이지 않는다).
    """
    import random
    import tempfile

    from pyoxigraph import NamedNode, RdfFormat, Store

    from ..corpus.assemble import GRAPHS, _multi
    from ..ontology.concept_axis import extract
    from ..retrieval.ontology_rerank import OntologyFeatures

    spec = FI.BY_KEY[fault_key]
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(path=str(Path(tmp) / "s"))
        for gname, path in GRAPHS.items():
            with open(path, "rb") as fh:
                store.bulk_load(fh, format=RdfFormat.TURTLE, to_graph=NamedNode(gname))
        spec.fn(store, strength, random.Random(seed))   # 합집합 전체에 같은 결함
        multi = _multi(store)
        # 축·계층도 **오염된 합집합**에서 뽑는다(계층 결함 F06·F12 는 여기서만 보인다)
        axis_df, tree = extract(store=store)

    feats = OntologyFeatures()
    def _get(iri_key, key):
        return frozenset(multi.get(iri_key, {}).get(key, set()))

    # 코퍼스 row 순서를 유지한 채 값만 교체한다 (doc_id → IRI 는 지역명 일치로 되짚는다)
    iri_by_local = {k.rsplit("/", 1)[-1]: k for k in multi}
    for i, doc in enumerate(feats.doc_ids):
        iri = iri_by_local.get(doc)
        feats.concepts[i] = _get(iri, "concepts")
        feats.ipc[i] = _get(iri, "ipc")
        feats.cpc[i] = _get(iri, "cpc")

    feats.axis = dict(zip(axis_df["slug"], axis_df["axis_class"]))
    feats.depth, feats._parent = tree["depth"], tree["parent"]
    OntologyFeatures._ancestors.cache_clear()

    feats.inv_concept = {}
    for i, cs in enumerate(feats.concepts):
        for c in cs:
            feats.inv_concept.setdefault(c, set()).add(i)
    feats.inv_ipc = {}
    for i, cs in enumerate(feats.ipc):
        for c in cs:
            for p in feats._ipc_prefixes(c):
                if len(p) >= 4:
                    feats.inv_ipc.setdefault(p, set()).add(i)
    return feats


FC_CACHE = config.PROCESSED / "fault_fc_cache.json"


def _pool(split: str):
    """(qids, B3 풀, 마스크) — 결함과 무관하게 고정된 재랭크 무대."""
    from ..analysis.metrics import load_run
    from ..analysis.results_table import run_path
    from ..retrieval.candidate import CandidateMask

    from .results_table import _split_qrel

    qrel = _split_qrel(split)
    qids = [q for q, p in qrel.items() if p]
    return qids, load_run(run_path("B3_rrf", split)), CandidateMask()


def build_fc_cache(split: str = "dev") -> Path:
    """FeatureCoverage 성분을 **한 번만** 계산해 굳힌다 (τ = 동결 P1_TAU).

    왜 필요한가 — `FeatureCoverageIndex` 는 featureText 임베딩을 올려 인스턴스당 최대 RSS
    **24.8GB** 를 쓴다(실측 2026-07-28). 108 인스턴스를 병렬로 돌리면 즉시 OOM 이고, 순차로
    돌리면 같은 값을 108번 다시 계산한다. 결함군 12종 중 **청구항·featureText 를 건드리는
    것은 없으므로** FC 성분은 결함과 무관한 상수다 — 한 번 계산해 재사용하는 것이 정확히
    옳다(근사가 아니다). 정합성은 `verify_fc_cache()` 가 동결 P1 run 재현으로 확인한다.
    """
    from ..analysis.results_table import P1_TAU
    from ..retrieval import systems as S
    from ..retrieval.feature_coverage import FeatureCoverageIndex

    qids, b3, mask = _pool(split)
    pool_docs = set(qids)
    pools = {}
    for qid in qids:
        pools[qid] = [d for d in b3.get(qid, []) if mask.is_allowed(qid, d)][:S.POOL_K]
        pool_docs.update(pools[qid])

    fc = FeatureCoverageIndex(restrict_docs=pool_docs)
    out = {}
    for qid, docs in pools.items():
        row = {}
        for d in docs:
            bs = fc.best_sims(qid, d)
            row[d] = float((bs >= P1_TAU).mean()) if bs.size else 0.0
        out[qid] = row
    FC_CACHE.write_text(json.dumps({"split": split, "tau": P1_TAU, "fc": out}), encoding="utf-8")
    return FC_CACHE


def load_fc_cache(split: str = "dev") -> dict:
    if not FC_CACHE.exists():
        raise FileNotFoundError(f"FC 캐시 없음: {FC_CACHE} (--fc-cache 먼저)")
    d = json.loads(FC_CACHE.read_text(encoding="utf-8"))
    if d["split"] != split:
        raise ValueError(f"FC 캐시 분할 불일치: {d['split']} ≠ {split}")
    return d["fc"]


def p1_run_from(feats, split: str, fc: dict) -> dict:
    """주어진 (오염되었을 수 있는) 뷰로 P1 을 재랭크. 동결 τ·α·w₄ — 재선택 없음.

    점수식은 `ontology_eval.rerank_p1` 과 같다: (1−α)·text̃ + α(w_c·c + w_h·p + w_i·ipc + w_f·fc).
    """
    from ..analysis.results_table import P1_ALPHA, P1_W4
    from ..retrieval import systems as S
    from ..retrieval.ontology_rerank import _query_features

    wc, wh, wi, wf = P1_W4
    qids, b3, mask = _pool(split)
    qrows = _query_features(feats)
    out = {}
    for qid in qids:
        qrow = qrows.get(qid)
        pool = [d for d in b3.get(qid, []) if mask.is_allowed(qid, d)][:S.POOL_K]
        m = len(pool)
        scored = []
        for rank0, d in enumerate(pool):
            drow = feats.row.get(d)
            tn = 1.0 - (rank0 / (m - 1)) if m > 1 else 1.0
            if qrow is None or drow is None:
                scored.append(((1.0 - P1_ALPHA) * tn, d))
                continue
            qc, dc = feats.concepts[qrow], feats.concepts[drow]
            ont_s = (wc * feats.concept_overlap(qc, dc)
                     + wh * feats.path_sim(qc, dc)
                     + wi * feats.ipc_sim(feats.ipc[qrow], feats.ipc[drow])
                     + wf * fc.get(qid, {}).get(d, 0.0))
            scored.append(((1.0 - P1_ALPHA) * tn + P1_ALPHA * ont_s, d))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out[qid] = [d for _, d in scored]
    return out


def verify_fc_cache(split: str = "dev") -> dict:
    """정상 뷰 + FC 캐시로 만든 P1 이 **동결 P1 run 과 같은가**. 다르면 실험 경로가 틀린 것이다."""
    from ..analysis.metrics import load_run
    from ..analysis.results_table import run_path
    from ..retrieval.ontology_rerank import OntologyFeatures

    frozen = load_run(run_path("P1", split))
    rebuilt = p1_run_from(OntologyFeatures(), split, load_fc_cache(split))
    same = sum(1 for q in frozen if frozen[q][:100] == rebuilt.get(q, [])[:100])
    return {"n_queries": len(frozen), "identical_top100": same,
            "pass": same == len(frozen)}


_FC: dict = {}


def _fc(split: str) -> dict:
    """워커 프로세스당 FC 캐시 1회 적재 (인스턴스마다 다시 읽지 않는다)."""
    if split not in _FC:
        _FC[split] = load_fc_cache(split)
    return _FC[split]


def faulted_p1_run(fault_key: str, strength: float, seed: int, ws: Path,
                   split: str = "dev", fc: dict | None = None) -> dict:
    """오염 뷰로 P1 을 다시 재랭크한다 (동결 τ·α·w₄ · 재선택 없음)."""
    feats = faulted_features(fault_key, strength, seed, ws)
    return p1_run_from(feats, split, fc if fc is not None else _fc(split))


# --- 한 인스턴스: 결함 주입 → 7층 판정 -----------------------------------------
def run_instance(fault_key: str, strength: float, rep: int, run_id: str,
                 split: str = "dev", skip_t12: bool = False) -> dict:
    """결함 하나를 만들어 전 층에 통과시킨다. 산출물은 전부 격리 디렉터리 안에 남는다."""
    from ..collect.bq_family_ir import load_family_map
    from ..validate.cq_runner import run_cqs, suite_pass_rates
    from ..validate.leakage_check import audit_graph
    from ..validate.t1_noninferiority import t1_gate
    from ..validate.t2_subgroup import t2_gate
    from ..validate.t3_cross_task_cq import load_generation, t3_gate

    from .metrics import load_run
    from .results_table import _split_qrel, run_path
    from .subgroup import query_labels

    base = load_baseline()
    spec = FI.BY_KEY[fault_key]
    seed = FI.seed_for(fault_key, strength, rep)
    label = f"{fault_key}_s{int(strength * 100):02d}_r{rep}"
    ws = Q.workspace(run_id, label, {"fault": fault_key, "strength": strength,
                                     "rep": rep, "seed": seed})
    t0 = time.time()

    # 1) 주입 — 정본은 읽기만 한다
    store = FI.load(config.GRAPH_V0, ws)
    stats = spec.inject(store, strength, seed)
    faulted = FI.dump(store, ws / "graph_faulted.ttl")
    del store

    out = {"fault": fault_key, "label": spec.label, "expected": spec.expected,
           "cross_task": spec.cross_task, "strength": strength, "rep": rep,
           "seed": seed, "workspace": str(ws), "stats": stats, "detected": {}}

    # 2) L0 — F01 은 산출물을 입력보다 낡게 만든다(파일시스템 사실)
    src_mtime = max(p.stat().st_mtime for p in config.EXTERNAL_SDKB.glob("*.ttl"))
    if fault_key == "F01":
        os.utime(faulted, (src_mtime - 86400, src_mtime - 86400))
    out["detected"]["L0"] = faulted.stat().st_mtime < src_mtime

    # 3) L1 SHACL
    from ..validate.shacl_gate import validate_graph
    conforms, _ = validate_graph(faulted, shapes="graph")
    out["detected"]["L1"] = not conforms

    # 4) L2 HermiT
    from ..validate.reasoner_gate import check_consistency
    out["detected"]["L2"] = not check_consistency(faulted)

    # 5) L3 · T3 — CQ 는 한 번만 돌려 두 층이 나눠 쓴다
    cq = run_cqs(faulted, targets=("graph",))
    n_pass = sum(r.passed for r in cq)
    suites = suite_pass_rates(cq)
    out["n_cq_pass"] = n_pass
    out["detected"]["L3"] = n_pass < base["n_cq_pass"]
    t3 = t3_gate(suites, load_generation("g0")["suites"])
    out["detected"]["T3"] = not t3["pass"]
    out["t3"] = t3

    # 6) 누출 감사 (그래프 층 — F09·F10 표적)
    leak = audit_graph(faulted, baseline=base["g3_gold_concept_copy_pairs"])
    out["detected"]["leak"] = not leak["pass"]
    out["leak"] = {k: leak[k] for k in ("g1_doc_as_concept", "g3_gold_concept_copy_pairs",
                                        "g3_exceeds")}

    # 7) T1·T2 — 오염 뷰로 P1 재랭크 후 정상 B3 와 비교
    if skip_t12:
        out["detected"]["T1"] = out["detected"]["T2"] = None
    else:
        qrel = _split_qrel(split)
        fam = load_family_map()
        b3 = load_run(run_path("B3_rrf", split))
        p1f = faulted_p1_run(fault_key, strength, seed, ws, split)
        t1 = t1_gate(p1f, b3, qrel, family=fam, k=100)
        t2 = t2_gate(p1f, b3, qrel, fam, query_labels(qrel), k=100)
        out["detected"]["T1"] = not t1["pass"]
        out["detected"]["T2"] = not t2["pass"]
        out["t1"], out["t2"] = t1, t2

    out["elapsed_s"] = round(time.time() - t0, 1)
    out["first_layer"] = next((L for L in LAYERS if out["detected"].get(L)), None)

    # 8) 오염 봉인 + 정본 무결성 재검증 (매 인스턴스)
    (ws / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    Q.log({"run_id": run_id, "label": label, "fault": fault_key, "strength": strength,
           "rep": rep, "seed": seed, "first_layer": out["first_layer"]})
    Q.verify_pristine(strict=True)
    return out


def _worker(args: tuple) -> dict:
    try:
        return run_instance(*args)
    except Exception as e:                    # 한 인스턴스 실패가 배치를 죽이지 않게
        return {"fault": args[0], "strength": args[1], "rep": args[2],
                "error": f"{type(e).__name__}: {e}", "detected": {}}


# --- 매트릭스 · 검정 ----------------------------------------------------------
def mcnemar(pairs: list[tuple[bool, bool]]) -> dict:
    """대응 McNemar (양측·연속성 보정). pairs = [(L0–L3 검출, T-gate 검출)] 결함 단위.

    b = 형식층만 잡음 · c = T-gate 만 잡음. c ≫ b 이면 T-gate 가 추가 판별력을 갖는다.
    표본이 작으면(b+c < 25) 정확 이항검정을 쓴다 — χ² 근사가 깨지는 구간이다.
    """
    from scipy import stats

    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "n_discordant": 0, "p": 1.0, "test": "none(불일치 0)"}
    if n < 25:
        p = float(stats.binomtest(c, n, 0.5).pvalue)
        test = "exact binomial"
    else:
        chi2 = (abs(b - c) - 1) ** 2 / n
        p = float(stats.chi2.sf(chi2, 1))
        test = "chi2 (연속성 보정)"
    return {"b": b, "c": c, "n_discordant": n, "p": p, "test": test}


def summarize(results: list[dict]) -> dict:
    """결함별 층 검출률 · 최초 검출층 · McNemar · 교차결함 H1 판정."""
    ok = [r for r in results if not r.get("error")]
    by_fault: dict[str, dict] = {}
    for spec in FI.FAULTS + FI.NORMALS:
        rs = [r for r in ok if r["fault"] == spec.key]
        if not rs:
            continue
        rates = {L: (sum(1 for r in rs if r["detected"].get(L)) / len(rs)) for L in LAYERS}
        firsts = [r["first_layer"] for r in rs]
        by_fault[spec.key] = {
            "label": spec.label, "expected": spec.expected, "cross_task": spec.cross_task,
            "n": len(rs), "rates": rates,
            "first_layer": max(set(firsts), key=firsts.count) if firsts else None,
            "undetected": sum(1 for f in firsts if f is None),
        }

    # 분류는 접두어가 아니라 **등록부**로 한다 — N03A 는 'N' 으로 시작하지만 결함이다.
    ok = [r for r in ok if r["fault"] not in NORMAL_KEYS]
    normals = [r for r in results if r["fault"] in NORMAL_KEYS and not r.get("error")]
    fp = [r for r in normals if r["first_layer"]]
    pairs = [(any(r["detected"].get(L) for L in ("L0", "L1", "L2", "L3")),
              any(r["detected"].get(L) for L in ("T1", "T2", "T3")))
             for r in ok]
    cross = [r for r in ok if r["cross_task"]]
    t3_only = [r for r in cross
               if r["detected"].get("T3")
               and not any(r["detected"].get(L) for L in ("L0", "L1", "L2", "L3", "T1", "T2"))]
    return {"n_instances": len(ok), "n_errors": sum(1 for r in results if r.get("error")),
            "false_positive": {"n_normal": len(normals), "n_rejected": len(fp),
                               "rate": (len(fp) / len(normals)) if normals else None,
                               "rejected": [{"fault": r["fault"], "strength": r["strength"],
                                             "layer": r["first_layer"]} for r in fp]},
            "by_fault": by_fault, "mcnemar": mcnemar(pairs),
            "h1": {"n_cross_instances": len(cross), "n_t3_only": len(t3_only),
                   "rate_t3_only": (len(t3_only) / len(cross)) if cross else 0.0}}


def run_matrix(reps: int = 3, strengths: tuple = FI.STRENGTHS, workers: int = 12,
               split: str = "dev", faults: tuple | None = None,
               skip_t12: bool = False, run_id: str | None = None,
               report: Path = REPORT, rep_offset: int = 0) -> dict:
    """`rep_offset` 은 홀드아웃용이다 — 1차가 rep ∈ {0,1,2} 를 썼으므로 offset 3 이면
    rep ∈ {3,4,5} 가 되고 `seed_for` 가 sha256(key,rate,rep) 이라 **겹치지 않는 결함 그래프**다.
    """
    run_id = run_id or f"w4_r{reps}"
    keys = faults or tuple(f.key for f in FI.FAULTS + FI.NORMALS)
    jobs = [(k, s, r, run_id, split, skip_t12)
            for k in keys for s in strengths
            for r in range(rep_offset, rep_offset + reps)]
    results = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_worker, j): j for j in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            print(f"  [{i}/{len(jobs)}] {r['fault']} s={r['strength']} r={r['rep']} "
                  f"→ {r.get('first_layer') or r.get('error') or '미검출'}", flush=True)
    results.sort(key=lambda r: (r["fault"], r["strength"], r["rep"]))
    out = {"run_id": run_id, "split": split, "reps": reps, "rep_offset": rep_offset,
           "strengths": list(strengths),
           "workers": workers, "elapsed_s": round(time.time() - t0, 1),
           "summary": summarize(results), "instances": results}
    report.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    Q.lock(Q.QUARANTINE / run_id)
    return out


def t3_prime(run_id: str = "w4_r3") -> dict:
    """**T3′ — CQ 세분화 대리지표** (탐색적 진단 · 게이트 판정 아님).

    현행 CQ 는 28개 중 26개가 `expect-min: 1` 이라 "결과행이 하나라도 있는가"만 묻는다. 결함이
    CQ 를 **0행으로 만들어야만** L3·T3 가 반응하므로, 1–10% 강도의 국소 결함은 원리적으로 통과한다
    (PLAN-020 §5-1 에서 실행 **전에** 예고했다). 이 진단은 통과/불통과 대신 **결과행 수**를 보고
    "CQ 를 세분화했다면 잡혔을 회귀"를 계량한다 — 부록 F 처방의 기대효과 측정이자, T3 가 놓친
    것이 게이트 구조의 문제인지 CQ 해상도의 문제인지를 가른다.

    격리된 결함 그래프를 **읽기만 한다**(재주입 없음 · 정본 불변).
    """
    from ..validate.cq_runner import run_cqs

    base = load_baseline()
    rows_base, suite_of = base["cq_rows"], base["cq_suite"]
    cross = {"em", "tf", "core"}
    out = []
    for d in sorted((Q.QUARANTINE / run_id).iterdir()):
        g = d / "graph_faulted.ttl"
        res_path = d / "result.json"
        if not (g.exists() and res_path.exists()):
            continue
        inst = json.loads(res_path.read_text(encoding="utf-8"))
        rows = {r.name: r.rows for r in run_cqs(g, targets=("graph",))}
        dropped = {k: (rows_base[k], rows[k]) for k in rows_base
                   if rows.get(k, 0) < rows_base[k]}
        dropped_cross = {k: v for k, v in dropped.items() if suite_of[k] in cross}
        out.append({"fault": inst["fault"], "strength": inst["strength"], "rep": inst["rep"],
                    "cross_task": inst["cross_task"], "t3_detected": inst["detected"].get("T3"),
                    "n_cq_dropped": len(dropped), "n_cross_dropped": len(dropped_cross),
                    "cross_cqs": sorted(dropped_cross)})
    by_fault: dict[str, dict] = {}
    for r in out:
        rec = by_fault.setdefault(r["fault"], {"n": 0, "t3": 0, "t3_prime": 0, "cqs": set()})
        rec["n"] += 1
        rec["t3"] += int(bool(r["t3_detected"]))
        rec["t3_prime"] += int(r["n_cross_dropped"] > 0)
        rec["cqs"].update(r["cross_cqs"])
    for rec in by_fault.values():
        rec["cqs"] = sorted(rec["cqs"])
    return {"run_id": run_id, "by_fault": by_fault, "instances": out}


# --- W4b 재판정 (PLAN-021) — 결함을 다시 넣지 않는다 ---------------------------
REPORT_V2 = config.PROCESSED / "fault_matrix_v2.json"
REPORT_V3 = config.PROCESSED / "fault_matrix_v3.json"
REJUDGE_RUNS = ("w4_r3", "w4b_n03")
# PLAN-022 재판정 대상 — W4·W4b 격리본에 면제 악용 결함(N03A) 신규 run 을 더한다.
REJUDGE_RUNS_V3 = ("w4_r3", "w4b_n03", "w5_n03adv")
# 정상 델타 키(위양성 분모). **N03A 는 여기 없다** — 'N' 으로 시작하지만 결함이다(거짓 dedup
# 선언으로 서명이 다른 개체를 합쳐 정보를 파괴한다). 접두어로 분류하면 결함이 위양성 분모에
# 섞여 위양성률을 부풀리고 검출률을 떨어뜨린다.
NORMAL_KEYS = frozenset(f.key for f in FI.NORMALS)


def _rejudge_one(args: tuple) -> dict:
    """격리 인스턴스 하나를 **읽기만 해서** CQ 를 다시 세고 τ 격자 전체로 판정한다.

    PLAN-022 부터 L3 를 두 벌로 센다 — `L3_all`(구 귀속 · 전 스위트)과 `L3_pa`(신 귀속 · 주
    태스크). 둘을 같은 인스턴스에서 같이 남기는 이유는 §0.1 의 **검출력 불변**
    (`L3_all ⟺ L3_pa ∨ T3`)을 주장이 아니라 실측으로 보이기 위해서다.
    """
    from ..validate.cq_runner import layer_pass_counts, regressions, run_cqs, suite_pass_rates

    d, taus, exempt = Path(args[0]), args[1], bool(args[2])
    base = load_baseline()
    inst = json.loads((d / "result.json").read_text(encoding="utf-8"))
    res = run_cqs(d / "graph_faulted.ttl", targets=("graph",))
    base_rows = base["cq_rows"]
    gen_suites = json.loads((config.CQ_GEN_DIR / "cq_g0.json").read_text(encoding="utf-8"))["suites"]
    base_pa = base["suites"].get("pa", {}).get("n_pass", 0)

    from ..validate.t3_cross_task_cq import t3_gate
    per_tau = {}
    for tau in taus:
        n_pass = sum(1 for r in res if r.judge(base_rows.get(r.name), tau, exempt))
        rates = suite_pass_rates(res, base_rows, tau, exempt)
        layers = layer_pass_counts(res, base_rows, tau, exempt)
        t3 = t3_gate(rates, gen_suites)
        regs = regressions(res, base_rows, tau)
        per_tau[f"{tau:.2f}"] = {
            "L3_all": n_pass < base["n_cq_pass"],          # 구 귀속 (전 스위트)
            "L3_pa": layers["L3"]["n_pass"] < base_pa,     # 신 귀속 (주 태스크 · PLAN-022 §1)
            "T3": not t3["pass"],
            "n_cq_pass": n_pass, "n_pa_pass": layers["L3"]["n_pass"], "base_pa_pass": base_pa,
            "regressed_suites": t3["regressed"],
            "regressed_cqs": [r["cq"] for r in regs],
            "pa_regressed_cqs": [r["cq"] for r in regs if r["suite"] in config.L3_SUITES],
            "cross_regressed_cqs": [r["cq"] for r in regs if r["suite"] in config.T3_SUITES],
        }
    return {"fault": inst["fault"], "label": inst["label"], "expected": inst["expected"],
            "cross_task": inst["cross_task"], "strength": inst["strength"], "rep": inst["rep"],
            "exempt": exempt, "v1": inst["detected"], "v2_by_tau": per_tau}


def dedup_exemptions(dirs: list[Path]) -> dict[str, bool]:
    """중복제거 면제 승인 여부를 인스턴스별로 판정한다 (PLAN-022 §2).

    격리본에는 병합쌍이 기록돼 있지 않으므로 `FI.dedup_selection` 으로 **결정적으로 복원**한다
    (정본 G₀ 는 읽기만 한다). 선언이 "dedup" 이어도 자동 검증이 서명 불일치를 찾으면 면제는
    **불승인**이고 일반 델타로 판정된다 — 선언은 주장일 뿐이고 근거는 데이터다.

    면제 승인은 로그에 남는다. 조용한 면제는 게이트를 장식으로 만든다.
    """
    from pyoxigraph import RdfFormat, Store

    from ..validate.dedup_exempt import log_exemption, verify_groups

    pending = []
    for d in dirs:
        inst = json.loads((d / "result.json").read_text(encoding="utf-8"))
        spec = FI.BY_KEY.get(inst["fault"])
        if spec is not None and spec.delta_type == "dedup":
            pending.append((d, inst))
    if not pending:
        return {}

    store = Store()                      # 정본 G₀ — 읽기 전용으로 한 번만 적재
    with open(config.GRAPH_V0, "rb") as fh:
        store.bulk_load(fh, format=RdfFormat.TURTLE)

    out: dict[str, bool] = {}
    for d, inst in pending:
        groups = FI.dedup_selection(store, inst["fault"], inst["strength"], inst["seed"])
        v = verify_groups(store, groups)
        out[str(d)] = v["ok"]
        log_exemption({"instance": d.name, "fault": inst["fault"],
                       "strength": inst["strength"], "seed": inst["seed"],
                       "delta_type": "dedup", "exempt": v["ok"],
                       "n_groups": v["n_groups"], "n_mismatch": v["n_mismatch"]})
    return out


def rejudge(runs: tuple = REJUDGE_RUNS, taus: tuple = config.CQ_TAU_GRID,
            workers: int = 10, report: Path | None = None) -> dict:
    """**W4b — 판정 규칙만 바꿔 W4 격리본을 다시 읽는다** (PLAN-021 §4).

    결함을 다시 주입하지 않는다: 바뀐 것은 CQ 판정 규칙(v1 존재검사 → v2 존재∧분포)뿐이고,
    L0·L1·L2·누출·T1·T2 는 결함 그래프의 함수라 v1 인스턴스의 저장값을 그대로 승계한다.
    같은 인스턴스의 **대응 비교**가 되므로 McNemar 가 정당하고, 1,908초 배치·47GB 재생성이
    사라진다. 격리본은 0444 잠금 그대로 — 읽기만 한다.
    """
    dirs = []
    for run_id in runs:
        root = Q.QUARANTINE / run_id
        if not root.exists():
            continue
        dirs += [d for d in sorted(root.iterdir())
                 if (d / "graph_faulted.ttl").exists() and (d / "result.json").exists()]
    if not dirs:
        raise FileNotFoundError(f"재판정할 격리 인스턴스가 없다: {runs}")

    exempt_by_dir = dedup_exemptions(dirs)

    t0 = time.time()
    out = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_rejudge_one, (str(d), taus, exempt_by_dir.get(str(d), False)))
                for d in dirs]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            out.append(r)
            print(f"  [{i}/{len(dirs)}] {r['fault']} s={r['strength']} r={r['rep']} "
                  f"→ v2(τ={config.CQ_TAU}) "
                  f"L3(전)={r['v2_by_tau'][f'{config.CQ_TAU:.2f}']['L3_all']} "
                  f"L3(pa)={r['v2_by_tau'][f'{config.CQ_TAU:.2f}']['L3_pa']} "
                  f"T3={r['v2_by_tau'][f'{config.CQ_TAU:.2f}']['T3']}", flush=True)
    out.sort(key=lambda r: (r["fault"], r["strength"], r["rep"]))
    res = {"runs": list(runs), "taus": list(taus), "rule_version": config.CQ_RULE_VERSION,
           "tau_main": config.CQ_TAU, "elapsed_s": round(time.time() - t0, 1),
           "l3_suites": list(config.L3_SUITES), "t3_suites": list(config.T3_SUITES),
           "n_exempt": sum(1 for r in out if r.get("exempt")),
           # 두 귀속을 **같은 인스턴스에서** 요약한다 — 비교가 곧 §0.1 검출력 불변의 증거다.
           "summary": {f"{t:.2f}": summarize_v2(out, t, "all") for t in taus},
           "summary_split": {f"{t:.2f}": summarize_v2(out, t, "split") for t in taus},
           "invariant": union_invariance(out, taus),
           "instances": out}
    (report or REPORT_V2).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    Q.verify_pristine(strict=True)
    return res


def union_invariance(instances: list[dict], taus: tuple) -> dict:
    """**검출력 불변 검사** (PLAN-022 §0.1) — `L3_all ⟺ L3_pa ∨ T3` 가 모든 인스턴스에서 성립하는가.

    성립하면 층 재정의는 게이트를 완화한 것이 아니라 **귀속만 바꾼 것**이다. 위반이 하나라도
    나오면 재정의가 검출력을 건드린 것이므로 즉시 보고 대상이다 — 주장으로 덮지 않는다.
    """
    out = {}
    for tau in taus:
        k = f"{tau:.2f}"
        viol = []
        for r in instances:
            v = r["v2_by_tau"][k]
            l3_all = v.get("L3_all", v.get("L3"))
            if bool(l3_all) != bool(v["L3_pa"] or v["T3"]):
                viol.append({"fault": r["fault"], "strength": r["strength"], "rep": r["rep"],
                             "L3_all": l3_all, "L3_pa": v["L3_pa"], "T3": v["T3"]})
        out[k] = {"n_checked": len(instances), "n_violation": len(viol),
                  "holds": not viol, "violations": viol[:10]}
    return out


def _merged_layers(inst: dict, tau: float, attribution: str = "all") -> dict:
    """v1 의 층 판정에 v2 의 L3·T3 를 얹은 최종 검출 벡터.

    `attribution="all"` = 구 귀속(L3 가 전 스위트를 센다 · W4b 까지) ·
    `"split"` = 신 귀속(L3 = 주 태스크 pa · PLAN-022). **T3 는 어느 쪽에서도 같다.**
    """
    v2 = inst["v2_by_tau"][f"{tau:.2f}"]
    d = dict(inst["v1"])
    l3_all = v2.get("L3_all", v2.get("L3"))          # 구 산출(fault_matrix_v2.json) 호환
    d["L3"] = v2["L3_pa"] if attribution == "split" else l3_all
    d["T3"] = v2["T3"]
    return d


def summarize_v2(instances: list[dict], tau: float, attribution: str = "all") -> dict:
    """τ 하나에서의 v1 vs v2 요약 — 검출률·McNemar·H1′·위양성."""
    by_fault: dict[str, dict] = {}
    for spec in FI.FAULTS + FI.NORMALS:
        rs = [r for r in instances if r["fault"] == spec.key]
        if not rs:
            continue
        merged = [_merged_layers(r, tau, attribution) for r in rs]
        firsts = [next((L for L in LAYERS if m.get(L)), None) for m in merged]
        by_fault[spec.key] = {
            "label": spec.label, "expected": spec.expected, "cross_task": spec.cross_task,
            "n": len(rs),
            "rates": {L: sum(1 for m in merged if m.get(L)) / len(rs) for L in LAYERS},
            "v1_L3": sum(1 for r in rs if r["v1"].get("L3")),
            "v1_T3": sum(1 for r in rs if r["v1"].get("T3")),
            "v2_L3": sum(1 for m in merged if m["L3"]),
            "v2_T3": sum(1 for m in merged if m["T3"]),
            "delta_type": spec.delta_type,
            "n_exempt": sum(1 for r in rs if r.get("exempt")),
            "first_layer": max(set(firsts), key=firsts.count) if firsts else None,
            "undetected": sum(1 for f in firsts if f is None),
            "cross_cqs": sorted({c for r in rs
                                 for c in r["v2_by_tau"][f"{tau:.2f}"]["cross_regressed_cqs"]}),
        }
    faults = [r for r in instances if r["fault"] not in NORMAL_KEYS]
    normals = [r for r in instances if r["fault"] in NORMAL_KEYS]
    fp = [r for r in normals
          if any(_merged_layers(r, tau, attribution).get(L) for L in LAYERS)]
    pairs = [(any(_merged_layers(r, tau, attribution).get(L) for L in ("L0", "L1", "L2", "L3")),
              any(_merged_layers(r, tau, attribution).get(L) for L in ("T1", "T2", "T3")))
             for r in faults]
    cross = [r for r in faults if r["cross_task"]]
    t3_only = [r for r in cross
               if _merged_layers(r, tau, attribution)["T3"]
               and not any(_merged_layers(r, tau, attribution).get(L)
                           for L in ("L0", "L1", "L2", "L3", "T1", "T2"))]
    return {"tau": tau, "attribution": attribution,
            "n_instances": len(faults), "by_fault": by_fault,
            "n_t3_v1": sum(1 for r in faults if r["v1"].get("T3")),
            "n_t3_v2": sum(1 for r in faults if _merged_layers(r, tau, attribution)["T3"]),
            "n_l3_v1": sum(1 for r in faults if r["v1"].get("L3")),
            "n_l3_v2": sum(1 for r in faults if _merged_layers(r, tau, attribution)["L3"]),
            "false_positive": {"n_normal": len(normals), "n_rejected": len(fp),
                               "rate": (len(fp) / len(normals)) if normals else None,
                               "rejected": [{"fault": r["fault"], "strength": r["strength"]}
                                            for r in fp]},
            "mcnemar": mcnemar(pairs),
            "h1p": {"n_cross_instances": len(cross), "n_t3_only": len(t3_only),
                    "n_t3_detected": sum(1 for r in cross
                                         if _merged_layers(r, tau, attribution)["T3"]),
                    "rate_t3_only": (len(t3_only) / len(cross)) if cross else 0.0}}


def render_table_v2(res: dict) -> str:
    """원고 표 6.5v2 — 판정 규칙 v1 vs v2. 수기 기입 없음(CLAUDE §1-7)."""
    tau = res["tau_main"]
    s = res["summary"][f"{tau:.2f}"]
    lines = [
        "# 표 6.5v2 결함 주입 재판정 — CQ 판정 v1(존재검사) vs v2(존재∧분포검사)",
        "",
        f"판정 규칙 {res['rule_version']} · 주 τ={tau} · 사전 동결 격자 {res['taus']} · "
        f"결함 재주입 없음(격리본 재판정 · PLAN-021 §4)",
        "",
        "**H1 은 사전등록대로 기각된 채다.** 아래는 부록 F 가 실행 전에 예고한 처방(CQ 세분화)을 "
        "수행한 뒤의 **사후 재설계 검정 H1′**이며, 같은 데이터의 재판정이므로 독립 증거가 아니다.",
        "",
        "| 결함 | 예상층 | " + " | ".join(LAYERS) + " | L3 v1→v2 | T3 v1→v2 | 최초 검출층 | 미탐지 |",
        "|---|---|" + "---:|" * len(LAYERS) + "---:|---:|---|---:|",
    ]
    for key, r in s["by_fault"].items():
        if key.startswith("N"):
            continue
        name = f"**{r['label']}**" if r["cross_task"] else r["label"]
        cells = " | ".join(f"{r['rates'][L]:.2f}" for L in LAYERS)
        lines.append(f"| {name} | {r['expected']} | {cells} | "
                     f"{r['v1_L3']}→{r['v2_L3']} | {r['v1_T3']}→{r['v2_T3']} | "
                     f"{r['first_layer'] or '—'} | {r['undetected']}/{r['n']} |")
    m, h, fp = s["mcnemar"], s["h1p"], s["false_positive"]
    lines += [
        "",
        f"- **T3 검출** v1 {s['n_t3_v1']}/{s['n_instances']} → **v2 {s['n_t3_v2']}/{s['n_instances']}** · "
        f"L3 검출 v1 {s['n_l3_v1']} → v2 {s['n_l3_v2']}",
        f"- **H1′ 교차결함 T3 단독검출**: {h['n_t3_only']}/{h['n_cross_instances']} "
        f"(T3 가 잡은 교차결함은 {h['n_t3_detected']}/{h['n_cross_instances']})",
        f"- **McNemar**(L0–L3 vs T-gate · 결함 단위 대응): b={m['b']} · c={m['c']} · "
        f"p={m['p']:.4f} ({m['test']})",
        f"- **위양성**(정상 델타 거부): {fp['n_rejected']}/{fp['n_normal']}"
        + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else ""),
    ]
    for key in ("N01", "N02", "N03"):
        r = s["by_fault"].get(key)
        if r:
            lines.append(f"  - {key} {r['label']}: 거부 {r['n'] - r['undetected']}/{r['n']}")
    lines += ["", "## τ 민감도 (사전 동결 격자 · 결과를 보고 고르지 않는다)", "",
              "| τ | T3 검출 | L3 검출 | 위양성 | H1′ T3 단독 |", "|---:|---:|---:|---:|---:|"]
    for t in res["taus"]:
        st = res["summary"][f"{t:.2f}"]
        lines.append(f"| {t:.2f} | {st['n_t3_v2']}/{st['n_instances']} | "
                     f"{st['n_l3_v2']}/{st['n_instances']} | "
                     f"{st['false_positive']['n_rejected']}/{st['false_positive']['n_normal']} | "
                     f"{st['h1p']['n_t3_only']}/{st['h1p']['n_cross_instances']} |")
    cross_rows = [(k, r) for k, r in s["by_fault"].items() if r["cross_task"] or r["cross_cqs"]]
    if cross_rows:
        lines += ["", "## v2 에서 회귀로 판정된 교차 태스크 CQ", "",
                  "| 결함 | 하락한 교차 태스크 CQ |", "|---|---|"]
        for k, r in cross_rows:
            lines.append(f"| {r['label']} | {', '.join(c.split('_')[0] for c in r['cross_cqs']) or '—'} |")
    return "\n".join(lines) + "\n"


def render_table_v3(res: dict) -> str:
    """원고 표 6.5c — **L3–T3 검출 표면 분리 후** 재판정 (PLAN-022 · H1″). 수기 기입 없음."""
    from ..validate.dedup_exempt import exemption_count

    tau = res["tau_main"]
    s_all = res["summary"][f"{tau:.2f}"]
    s = res["summary_split"][f"{tau:.2f}"]
    inv = res["invariant"][f"{tau:.2f}"]
    lines = [
        "# 표 6.5c 결함 주입 재판정 — L3·T3 검출 표면 분리 (PLAN-022 · H1″)",
        "",
        f"L3 = {'·'.join(res['l3_suites'])} 스위트(주 태스크) · T3 = {'·'.join(res['t3_suites'])} "
        f"(교차 태스크) · 두 집합은 **서로소**이며 합집합은 CQ 전량 · 판정 규칙 "
        f"{res['rule_version']} · 주 τ={tau} · 격자 {res['taus']} · 결함 재주입 없음(격리본 재판정)",
        "",
        "**H1·H1′ 은 사전등록대로 기각된 채다.** 아래 H1″ 는 **같은 결함 데이터의 3회차 재판정**"
        "이며, 층 재정의를 떠올리게 만든 것이 W4b 의 결과이므로 **탐색적**이다. 확증은 차기 세대 "
        "델타의 몫이다.",
        "",
        "## 검출력 불변 검사 (§0.1 — 이 표를 읽기 전에 확인해야 하는 것)",
        "",
        f"`L3_all ⟺ L3_pa ∨ T3` 위반 **{inv['n_violation']}/{inv['n_checked']}** — "
        + ("성립. 층 재정의는 검출력이 아니라 **귀속**만 바꿨다(개정 전 거부가 개정 후 승인이 "
           "되는 인스턴스는 없다)."
           if inv["holds"] else
           "**위반이 있다.** 재정의가 검출력을 건드렸다는 뜻이므로 아래 결과를 그대로 쓸 수 없다."),
        "",
        "| 결함 | 예상층 | " + " | ".join(LAYERS) + " | L3 구→신 | T3 | 최초 검출층 | 미탐지 |",
        "|---|---|" + "---:|" * len(LAYERS) + "---:|---:|---|---:|",
    ]
    for key, r in s["by_fault"].items():
        if key in NORMAL_KEYS:
            continue
        name = f"**{r['label']}**" if r["cross_task"] else r["label"]
        cells = " | ".join(f"{r['rates'][L]:.2f}" for L in LAYERS)
        r_all = s_all["by_fault"].get(key, {})
        lines.append(f"| {name} | {r['expected']} | {cells} | "
                     f"{r_all.get('v2_L3', '—')}→{r['v2_L3']} | {r['v2_T3']} | "
                     f"{r['first_layer'] or '—'} | {r['undetected']}/{r['n']} |")
    m, h, fp = s["mcnemar"], s["h1p"], s["false_positive"]
    lines += [
        "",
        f"- **L3 검출** 구 귀속 {s_all['n_l3_v2']}/{s_all['n_instances']} → "
        f"신 귀속(pa) **{s['n_l3_v2']}/{s['n_instances']}** · T3 검출 "
        f"{s['n_t3_v2']}/{s['n_instances']}(불변 — 조작 변인은 L3 하나다)",
        f"- **H1″ 교차결함 T3 단독검출**: {h['n_t3_only']}/{h['n_cross_instances']} "
        f"(T3 가 잡은 교차결함은 {h['n_t3_detected']}/{h['n_cross_instances']}) · "
        f"구 귀속에서는 {s_all['h1p']['n_t3_only']}/{s_all['h1p']['n_cross_instances']} "
        "(L3 ⊇ T3 라 **원리적으로 0**이었다)",
        f"- **McNemar**(L0–L3 vs T-gate · 결함 단위 대응): b={m['b']} · c={m['c']} · "
        f"p={m['p']:.4f} ({m['test']})",
        f"- **위양성**(정상 델타 거부): {fp['n_rejected']}/{fp['n_normal']}"
        + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else "")
        + f" · 중복제거 면제 승인 {res['n_exempt']}건 "
        + f"(누적 승인 {exemption_count()[0]}건 · 판정 로그 {exemption_count()[1]}행)",
    ]
    for key in sorted(NORMAL_KEYS):
        r = s["by_fault"].get(key)
        if r:
            lines.append(f"  - {key} {r['label']}: 거부 {r['n'] - r['undetected']}/{r['n']}"
                         + (f" · 면제 승인 {r['n_exempt']}/{r['n']}"
                            if r["delta_type"] == "dedup" else ""))
    adv = s["by_fault"].get("N03A")
    if adv:
        lines += ["", "## 면제 규칙이 여는 구멍 (N03A · 거짓 dedup 선언 · PLAN-022 §2.1)", "",
                  f"- 검출 {adv['n'] - adv['undetected']}/{adv['n']} · 면제 승인 "
                  f"{adv['n_exempt']}/{adv['n']} (승인되면 자동 검증이 뚫린 것이다)",
                  f"- 최초 검출층 {adv['first_layer'] or '—'} · 미탐지 {adv['undetected']}/{adv['n']}"]
    lines += ["", "## τ 민감도 (사전 동결 격자 · 결과를 보고 고르지 않는다)", "",
              "| τ | T3 검출 | L3 검출(신) | L3 검출(구) | 위양성 | H1″ T3 단독 | 불변량 |",
              "|---:|---:|---:|---:|---:|---:|:--:|"]
    for t in res["taus"]:
        st, sa = res["summary_split"][f"{t:.2f}"], res["summary"][f"{t:.2f}"]
        iv = res["invariant"][f"{t:.2f}"]
        lines.append(f"| {t:.2f} | {st['n_t3_v2']}/{st['n_instances']} | "
                     f"{st['n_l3_v2']}/{st['n_instances']} | "
                     f"{sa['n_l3_v2']}/{sa['n_instances']} | "
                     f"{st['false_positive']['n_rejected']}/{st['false_positive']['n_normal']} | "
                     f"{st['h1p']['n_t3_only']}/{st['h1p']['n_cross_instances']} | "
                     f"{'✅' if iv['holds'] else '❌ ' + str(iv['n_violation'])} |")
    return "\n".join(lines) + "\n"


# --- W9 홀드아웃 확증 (PLAN-025 · H1‴) ----------------------------------------
# 1차(W4·W4b·W4c)는 **같은 결함 인스턴스를 세 번 판정**했다 — 성립한 판정(H1″)이 전부 사후적이다.
# 여기서는 판정 규칙을 하나도 바꾸지 않고(조작 변인 없음) **아직 판정한 적 없는 72 인스턴스**로
# 복제한다: 축 A(F11·F12 를 새 rep 으로) + 축 B(신규 교차결함 F13·F14·F15) + 정상 델타 27.
REPORT_HOLDOUT = config.PROCESSED / "fault_matrix_holdout.json"
REPORT_HOLDOUT_V4 = config.PROCESSED / "fault_matrix_v4.json"
HOLDOUT_KEYS = tuple(config.FAULT_HOLDOUT_CROSS_KEYS) + tuple(config.FAULT_HOLDOUT_NORMAL_KEYS)
HOLDOUT_NEW_KEYS = ("F13", "F14", "F15")            # 축 B(일반화) — 보조 판정의 부분집합
# "T3 단독검출" 의 배제 조건. **누출감사(leak) 발화도 '다른 층 검출'로 센다**(PLAN-025 §3.4).
OTHER_LAYERS = tuple(L for L in LAYERS if L != "T3")


def mcnemar_one_sided(pairs: list[tuple[bool, bool]]) -> dict:
    """단측 McNemar 정확검정 — 방향은 **사전 지정**(T3 우세)이다 (PLAN-025 §3.4-2).

    pairs = [(L3 검출, T3 검출)]. b = L3 만 · c = T3 만. 반대 방향(b > c)이 나오면 p 가 크게
    나와 자동으로 기각되며, 그 사실을 `direction` 에 남긴다 — 방향을 결과에 맞춰 바꾸지 않는다.
    """
    from scipy import stats

    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    n = b + c
    direction = "T3" if c > b else ("L3" if b > c else "tie")
    if n == 0:
        return {"b": 0, "c": 0, "n_discordant": 0, "p": 1.0, "direction": "none",
                "test": "none(불일치 0)"}
    return {"b": b, "c": c, "n_discordant": n,
            "p": float(stats.binomtest(c, n, 0.5, alternative="greater").pvalue),
            "direction": direction, "test": "exact binomial (단측 · 사전지정 방향 T3 우세)"}


def holdout_kill_switch(res: dict) -> dict:
    """정지 규칙 (PLAN-025 §3.4) — 위반이 **하나라도** 있으면 판정하지 않고 구현 오류로 처리한다.

    검사 셋: (1) 검출력 불변량 `L3_all ⟺ L3_pa ∨ T3` 가 τ 격자 전량에서 성립 (2) L3∩T3 = ∅
    (3) L3∪T3 = 게이트 CQ 전량. 판정 전에 이걸 먼저 보는 이유는, 층 정의가 미끄러지면 "T3
    단독검출" 이라는 수치 자체가 의미를 잃기 때문이다.
    """
    viol = []
    for tau, inv in res.get("invariant", {}).items():
        if not inv["holds"]:
            viol.append(f"검출력 불변량 위반 τ={tau}: {inv['n_violation']}/{inv['n_checked']}")
    l3, t3 = set(config.L3_SUITES), set(config.T3_SUITES)
    if l3 & t3:
        viol.append(f"L3∩T3 ≠ ∅: {sorted(l3 & t3)}")
    try:
        suite_of = load_baseline()["cq_suite"]
    except FileNotFoundError:
        suite_of = {}
    if suite_of:
        covered = sum(1 for s in suite_of.values() if s in l3 | t3)
        if covered != len(suite_of):
            viol.append(f"L3∪T3 가 CQ 전량을 덮지 못한다: {covered}/{len(suite_of)}")
    return {"pass": not viol, "violations": viol,
            "l3_suites": sorted(l3), "t3_suites": sorted(t3), "n_cq": len(suite_of)}


def _holdout_verdict(instances: list[dict], tau: float) -> dict:
    """교차결함 부분집합 하나에 대한 §3.4 주 판정 (1 T3 단독검출 ≥1 · 2 단측 McNemar)."""
    merged = [_merged_layers(r, tau, "split") for r in instances]
    t3_only = [(r, m) for r, m in zip(instances, merged)
               if m.get("T3") and not any(m.get(L) for L in OTHER_LAYERS)]
    mc = mcnemar_one_sided([(bool(m.get("L3")), bool(m.get("T3"))) for m in merged])
    return {"n_cross": len(instances),
            "n_t3_detected": sum(1 for m in merged if m.get("T3")),
            "n_l3_detected": sum(1 for m in merged if m.get("L3")),
            "n_t3_only": len(t3_only),
            "t3_only": [{"fault": r["fault"], "strength": r["strength"], "rep": r["rep"]}
                        for r, _ in t3_only],
            "by_fault": {k: sum(1 for r, _ in t3_only if r["fault"] == k)
                         for k in sorted({r["fault"] for r in instances})},
            "mcnemar": mc,
            "c1_t3_only": len(t3_only) >= 1,
            "c2_mcnemar": mc["direction"] == "T3" and mc["p"] < 0.05}


def judge_holdout(res: dict, tau: float | None = None) -> dict:
    """**H1‴ 판정** — 사전등록 §3.4 그대로. 결과를 본 뒤 규칙을 바꾸지 않는다.

    지지 = (T3 단독검출 ≥ 1) ∧ (단측 McNemar c>b · p<0.05) ∧ (위양성률 ≤ 5%). 셋 중 하나라도
    깨지면 **기각**이며 §3.5 에 미리 적어둔 서술 경로로 간다.
    """
    tau = res["tau_main"] if tau is None else tau
    insts = res["instances"]
    cross = [r for r in insts if r["cross_task"]]
    normals = [r for r in insts if r["fault"] in NORMAL_KEYS]
    fp = [r for r in normals
          if any(_merged_layers(r, tau, "split").get(L) for L in LAYERS)]
    fp_rate = (len(fp) / len(normals)) if normals else None
    main = _holdout_verdict(cross, tau)
    c3 = fp_rate is not None and fp_rate <= config.FAULT_FP_MAX_RATE
    out = {"tau": tau, "attribution": "split",
           "main": main,
           "false_positive": {"n_normal": len(normals), "n_rejected": len(fp), "rate": fp_rate,
                              "threshold": config.FAULT_FP_MAX_RATE,
                              "rejected": [{"fault": r["fault"], "strength": r["strength"],
                                            "rep": r["rep"]} for r in fp]},
           "c3_false_positive": c3,
           # 보조(사전 지정) — 복제 축과 일반화 축이 갈리면 **갈린 대로** 보고한다
           "replicate_only": _holdout_verdict([r for r in cross
                                               if r["fault"] in ("F11", "F12")], tau),
           "novel_only": _holdout_verdict([r for r in cross
                                           if r["fault"] in HOLDOUT_NEW_KEYS], tau)}
    out["supported"] = bool(main["c1_t3_only"] and main["c2_mcnemar"] and c3)
    out["verdict"] = "지지" if out["supported"] else "기각"
    return out


def holdout_judgment(res: dict) -> dict:
    """τ 격자 전량 + 주 τ 판정 + 정지 규칙을 한 덩이로 (표 6.5d 의 입력)."""
    kill = holdout_kill_switch(res)
    return {"kill_switch": kill,
            "tau_main": res["tau_main"],
            "main": None if not kill["pass"] else judge_holdout(res, res["tau_main"]),
            "by_tau": {} if not kill["pass"]
                      else {f"{t:.2f}": judge_holdout(res, t) for t in res["taus"]}}


def render_table_v4(res: dict) -> str:
    """원고 표 6.5d — **홀드아웃** 결함 검출 매트릭스 (PLAN-025 · H1‴). 수기 기입 없음."""
    j = res["holdout"]
    tau = res["tau_main"]
    s = res["summary_split"][f"{tau:.2f}"]
    kill, m = j["kill_switch"], j["main"]
    lines = [
        "# 표 6.5d 홀드아웃 결함 주입 — H1‴ 확증 (PLAN-025 · 사전등록 동결 `a474126`)",
        "",
        f"판정 규칙·층 정의는 **하나도 바꾸지 않았다**(조작 변인 없음) — 바뀐 것은 데이터뿐이다. "
        f"L3 = {'·'.join(res['l3_suites'])} ⊥ T3 = {'·'.join(res['t3_suites'])} · 규칙 "
        f"{res['rule_version']} · 주 τ={tau} · 격자 {res['taus']} · 분할 dev(확증 분할 미개봉).",
        "",
        "홀드아웃 = 축 A 복제(F11·F12 × 새 rep "
        f"{{{','.join(str(config.FAULT_HOLDOUT_REP_OFFSET + i) for i in range(config.FAULT_HOLDOUT_REPS))}}}) "
        "+ 축 B 일반화(신규 교차결함 F13·F14·F15) + 정상 델타(위양성 분모). "
        "**비교차 결함군 F01–F10 은 재주입하지 않았다** — H1‴ 판정식에 들어가지 않으며 1차 결과는 "
        "이미 표 6.5·6.5c 에 있다(PLAN-025 §3.3 · 은폐된 절단 금지).",
        "",
        "## 정지 규칙 (판정 전에 확인해야 하는 것)",
        "",
        f"위반 **{len(kill['violations'])}건** — "
        + ("검출력 불변량·층 서로소·CQ 전량 피복이 모두 성립한다. 판정을 진행한다."
           if kill["pass"] else
           "**판정을 진행하지 않는다**(구현 오류): " + " · ".join(kill["violations"])),
        "",
    ]
    if not kill["pass"]:
        return "\n".join(lines) + "\n"

    lines += ["| 결함 | 예상층 | " + " | ".join(LAYERS) + " | T3 단독 | 최초 검출층 | 미탐지 |",
              "|---|---|" + "---:|" * len(LAYERS) + "---:|---|---:|"]
    for key, r in s["by_fault"].items():
        if key in NORMAL_KEYS:
            continue
        name = f"**{r['label']}**" if r["cross_task"] else r["label"]
        cells = " | ".join(f"{r['rates'][L]:.2f}" for L in LAYERS)
        lines.append(f"| {name} | {r['expected']} | {cells} | "
                     f"{m['main']['by_fault'].get(key, 0)}/{r['n']} | "
                     f"{r['first_layer'] or '—'} | {r['undetected']}/{r['n']} |")
    mc, fp = m["main"]["mcnemar"], m["false_positive"]
    lines += [
        "",
        f"## H1‴ 판정 — **{m['verdict']}** (사전등록 §3.4 · 세 조건 모두 충족해야 지지)",
        "",
        f"1. **T3 단독검출 ≥ 1**: {m['main']['n_t3_only']}/{m['main']['n_cross']} → "
        f"{'충족' if m['main']['c1_t3_only'] else '미충족'} "
        f"(T3 가 잡은 교차결함 {m['main']['n_t3_detected']}/{m['main']['n_cross']} · "
        f"L3 {m['main']['n_l3_detected']}/{m['main']['n_cross']})",
        f"2. **단측 McNemar**(L3 vs T3 · 사전지정 방향 T3 우세): b={mc['b']} · c={mc['c']} · "
        f"불일치 {mc['n_discordant']} · p={mc['p']:.4f} ({mc['test']}) · 방향 {mc['direction']} → "
        f"{'충족' if m['main']['c2_mcnemar'] else '미충족'}",
        f"3. **위양성률 ≤ {fp['threshold']:.0%}**: {fp['n_rejected']}/{fp['n_normal']}"
        + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else "")
        + f" → {'충족' if m['c3_false_positive'] else '미충족'}",
        "",
        "## 보조 판정 (사전 지정 — 갈리면 갈린 대로 보고한다)",
        "",
        "| 부분집합 | n | T3 단독 | T3 검출 | McNemar b/c | p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lbl, key in (("전체 교차결함(주 판정)", "main"),
                     ("축 A 복제 F11·F12", "replicate_only"),
                     ("축 B 일반화 F13·F14·F15", "novel_only")):
        vv = m[key]
        mcx = vv["mcnemar"]
        lines.append(f"| {lbl} | {vv['n_cross']} | {vv['n_t3_only']} | {vv['n_t3_detected']} | "
                     f"{mcx['b']}/{mcx['c']} | {mcx['p']:.4f} |")
    lines += ["", "## τ 민감도 (사전 동결 격자 · 결과를 보고 고르지 않는다)", "",
              "| τ | T3 단독 | T3 검출 | L3 검출 | 위양성 | McNemar p | 판정 |",
              "|---:|---:|---:|---:|---:|---:|:--:|"]
    for t in res["taus"]:
        jt = j["by_tau"][f"{t:.2f}"]
        mm, ff = jt["main"], jt["false_positive"]
        lines.append(f"| {t:.2f} | {mm['n_t3_only']}/{mm['n_cross']} | "
                     f"{mm['n_t3_detected']}/{mm['n_cross']} | "
                     f"{mm['n_l3_detected']}/{mm['n_cross']} | "
                     f"{ff['n_rejected']}/{ff['n_normal']} | "
                     f"{mm['mcnemar']['p']:.4f} | {jt['verdict']} |")
    lines += ["", "## 정상 델타(위양성 분모) 상세", ""]
    for key in sorted(NORMAL_KEYS):
        r = s["by_fault"].get(key)
        if r:
            lines.append(f"- {key} {r['label']}: 거부 {r['n'] - r['undetected']}/{r['n']}")
    return "\n".join(lines) + "\n"


def run_holdout(workers: int = 9, split: str = "dev") -> dict:
    """홀드아웃 72 인스턴스 주입 → 격리본 재판정 → H1‴ 판정. 정본은 읽기만 한다."""
    Q.verify_pristine(strict=True)
    inj = run_matrix(reps=config.FAULT_HOLDOUT_REPS, workers=workers, split=split,
                     faults=HOLDOUT_KEYS, run_id=config.FAULT_HOLDOUT_RUN_ID,
                     report=REPORT_HOLDOUT, rep_offset=config.FAULT_HOLDOUT_REP_OFFSET)
    print(f"\n[홀드아웃 주입] {len(inj['instances'])}인스턴스 · "
          f"오류 {inj['summary']['n_errors']} · {inj['elapsed_s']}초 → {REPORT_HOLDOUT}")
    return judge_holdout_run(workers=workers)


def judge_holdout_run(workers: int = 9) -> dict:
    """이미 격리된 홀드아웃 인스턴스를 **읽기만 해서** 재판정한다(재주입 없음)."""
    res = rejudge(runs=(config.FAULT_HOLDOUT_RUN_ID,), workers=workers,
                  report=REPORT_HOLDOUT_V4)
    res["holdout"] = holdout_judgment(res)
    REPORT_HOLDOUT_V4.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def render_table(res: dict) -> str:
    """원고 표 6.5 — 결함 × 게이트 층 검출 매트릭스. 수기 기입 없음(CLAUDE §1-7)."""
    s = res["summary"]
    head = ("| 결함 | 예상층 | " + " | ".join(LAYERS) + " | 최초 검출층 | 미탐지 |")
    sep = "|---|---|" + "---:|" * len(LAYERS) + "---|---:|"
    lines = ["# 표 6.5 결함 주입 × 게이트 층 검출 매트릭스",
             "",
             f"분할 {res['split']} · 결함 {len(s['by_fault']) - len(NORMAL_KEYS)}종 × 강도 "
             f"{res['strengths']} × 반복 {res['reps']} "
             f"= {s['n_instances']}인스턴스 (정상 델타 {s['false_positive']['n_normal']}건 별도) · "
             f"셀 = 해당 층 검출률", "", head, sep]
    for key, r in s["by_fault"].items():
        if key.startswith("N"):
            continue
        name = f"**{r['label']}**" if r["cross_task"] else r["label"]
        cells = " | ".join(f"{r['rates'][L]:.2f}" for L in LAYERS)
        lines.append(f"| {name} | {r['expected']} | {cells} | "
                     f"{r['first_layer'] or '—'} | {r['undetected']}/{r['n']} |")
    m, h, fp = s["mcnemar"], s["h1"], s["false_positive"]
    lines += ["",
              f"- **McNemar**(L0–L3 검출 vs T-gate 검출, 결함 단위 대응): b={m['b']} · c={m['c']} · "
              f"불일치 {m['n_discordant']} · p={m['p']:.4f} ({m['test']})",
              f"- **H1 교차결함 T3 단독검출**: {h['n_t3_only']}/{h['n_cross_instances']} "
              f"= {h['rate_t3_only']:.1%}",
              f"- **위양성률**(정상 델타 거부): {fp['n_rejected']}/{fp['n_normal']}"
              + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else "")]
    for key in ("N01", "N02"):
        r = s["by_fault"].get(key)
        if r:
            lines.append(f"  - {key} {r['label']}: 거부 {r['n'] - r['undetected']}/{r['n']}")

    tp_path = config.PROCESSED / "fault_t3_prime.json"
    if tp_path.exists():
        tp = json.loads(tp_path.read_text(encoding="utf-8"))
        lines += ["", "## 표 6.5b T3′ — CQ 세분화 대리지표 (탐색적 진단 · 게이트 판정 아님)", "",
                  "현행 CQ 는 28개 중 26개가 `expect-min: 1` 존재검사라 결함이 CQ 를 **0행으로**",
                  "만들어야만 T3 가 발화한다. T3′ 는 통과/불통과 대신 **결과행 수 하락**을 보아",
                  "\"CQ 를 세분화했다면 잡혔을 회귀\"를 계량한다(PLAN-020 §5-1 에서 실행 전 예고).", "",
                  "| 결함 | T3 검출 | **T3′ 행수하락** | n | 하락한 교차 태스크 CQ |",
                  "|---|---:|---:|---:|---|"]
        for key, r in sorted(tp["by_fault"].items()):
            spec = FI.BY_KEY.get(key)
            name = spec.label if spec else key
            if key.startswith("N"):
                name += " ※위양성 분모"
            lines.append(f"| {name} | {r['t3']}/{r['n']} | **{r['t3_prime']}/{r['n']}** | "
                         f"{r['n']} | {', '.join(c.split('_')[0] for c in r['cqs']) or '—'} |")
        tot = sum(r["t3_prime"] for k, r in tp["by_fault"].items() if not k.startswith("N"))
        n_f = sum(r["n"] for k, r in tp["by_fault"].items() if not k.startswith("N"))
        fp = sum(r["t3_prime"] for k, r in tp["by_fault"].items() if k.startswith("N"))
        n_n = sum(r["n"] for k, r in tp["by_fault"].items() if k.startswith("N"))
        lines += ["", f"- 결함 검출 **{tot}/{n_f}** (T3 는 0/{n_f}) · 정상 델타 오탐 **{fp}/{n_n}**"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="정상 그래프 기준선 측정·동결")
    ap.add_argument("--fc-cache", action="store_true",
                    help="FeatureCoverage 성분 1회 계산·동결(+동결 P1 재현 검증)")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--split", default="dev", choices=["dev"], help="dev 전용(test 재개봉 금지)")
    ap.add_argument("--faults", default=None, help="쉼표구분 결함키(기본 전량)")
    ap.add_argument("--skip-t12", action="store_true", help="T1·T2 생략(연기 진단용)")
    ap.add_argument("--write", action="store_true", help="표 6.5 를 paper/tables/ 에 기록")
    ap.add_argument("--from-report", action="store_true", help="재실행 없이 기존 매트릭스로 표만")
    ap.add_argument("--t3-prime", action="store_true",
                    help="CQ 세분화 대리지표(탐색적 진단 · 격리 그래프 재질의)")
    ap.add_argument("--n03", action="store_true",
                    help="W4b 정상 델타 N03(완전중복 병합)만 주입 → run_id w4b_n03")
    ap.add_argument("--rejudge", action="store_true",
                    help="W4b 재판정 — 격리본을 읽어 CQ 판정 v1 vs v2 × τ 격자 (재주입 없음)")
    ap.add_argument("--n03adv", action="store_true",
                    help="PLAN-022 N03A(거짓 dedup 선언) 주입 → run_id w5_n03adv")
    ap.add_argument("--rejudge-v3", action="store_true",
                    help="PLAN-022 재판정 — L3·T3 표면 분리 + 중복제거 면제 (재주입 없음)")
    ap.add_argument("--holdout", action="store_true",
                    help="PLAN-025 W9 홀드아웃 72 인스턴스 주입 + H1‴ 판정 (run_id w9_holdout)")
    ap.add_argument("--holdout-judge", action="store_true",
                    help="홀드아웃 격리본만 재판정 (재주입 없음)")
    args = ap.parse_args()

    if args.baseline:
        Q.seal()
        b = measure_baseline()
        BASELINE.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[기준선] CQ {b['n_cq_pass']}/{b['n_cq']} · G-1 {b['g1_doc_as_concept']} · "
              f"G-3 {b['g3_gold_concept_copy_pairs']} → {BASELINE}")
        return

    if args.fc_cache:
        p = build_fc_cache(args.split)
        v = verify_fc_cache(args.split)
        print(f"[FC 캐시] {p}")
        print(f"  동결 P1 재현: top-100 일치 {v['identical_top100']}/{v['n_queries']} "
              f"→ {'PASS' if v['pass'] else 'FAIL — 실험 경로가 정본과 다르다'}")
        raise SystemExit(0 if v["pass"] else 1)

    if args.t3_prime:
        tp = t3_prime()
        out = config.PROCESSED / "fault_t3_prime.json"
        out.write_text(json.dumps(tp, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[T3′ CQ 세분화 대리지표 · 탐색적]  결함  T3 검출 / T3′ 행수하락 / n")
        for k, r in sorted(tp["by_fault"].items()):
            print(f"  {k}  {r['t3']:>2} / {r['t3_prime']:>2} / {r['n']:>2}   "
                  f"{','.join(r['cqs'][:6])}")
        print(f"  → {out}")
        return

    if args.n03:
        Q.verify_pristine(strict=True)
        res = run_matrix(args.reps, workers=min(args.workers, 9), split=args.split,
                         faults=("N03",), run_id="w4b_n03",
                         report=config.PROCESSED / "fault_matrix_n03.json")
        s = res["summary"]
        print(f"\n[N03 정상 델타] {s['n_instances'] + s['false_positive']['n_normal']}인스턴스 · "
              f"오류 {s['n_errors']} · {res['elapsed_s']}초 · "
              f"거부 {s['false_positive']['n_rejected']}/{s['false_positive']['n_normal']}")
        return

    if args.rejudge:
        res = rejudge(workers=args.workers)
        tau = res["tau_main"]
        s = res["summary"][f"{tau:.2f}"]
        print(f"\n[W4b 재판정] 규칙 {res['rule_version']} · 주 τ={tau} · {res['elapsed_s']}초")
        print(f"  T3 검출 v1 {s['n_t3_v1']}/{s['n_instances']} → v2 {s['n_t3_v2']}/{s['n_instances']}"
              f"  ·  L3 v1 {s['n_l3_v1']} → v2 {s['n_l3_v2']}")
        print(f"  H1′ 교차결함 T3 단독검출 {s['h1p']['n_t3_only']}/{s['h1p']['n_cross_instances']} "
              f"(T3 검출 {s['h1p']['n_t3_detected']}/{s['h1p']['n_cross_instances']})")
        print(f"  McNemar b={s['mcnemar']['b']} c={s['mcnemar']['c']} p={s['mcnemar']['p']:.4f}")
        print(f"  위양성 {s['false_positive']['n_rejected']}/{s['false_positive']['n_normal']}")
        out = config.ROOT / "paper" / "tables" / "fault_matrix_v2.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_table_v2(res), encoding="utf-8")
        print(f"  표 → {out}\n  → {REPORT_V2}")
        return

    if args.n03adv:
        Q.verify_pristine(strict=True)
        res = run_matrix(args.reps, workers=min(args.workers, 9), split=args.split,
                         faults=("N03A",), run_id="w5_n03adv",
                         report=config.PROCESSED / "fault_matrix_n03adv.json")
        s = res["summary"]
        r = s["by_fault"].get("N03A", {})
        print(f"\n[N03A 면제 악용] {s['n_instances']}인스턴스 · 오류 {s['n_errors']} · "
              f"{res['elapsed_s']}초 · 미탐지 {r.get('undetected')}/{r.get('n')} · "
              f"최초 검출층 {r.get('first_layer') or '—'}")
        return

    if args.rejudge_v3:
        res = rejudge(runs=REJUDGE_RUNS_V3, workers=args.workers, report=REPORT_V3)
        tau = res["tau_main"]
        s, sa = res["summary_split"][f"{tau:.2f}"], res["summary"][f"{tau:.2f}"]
        inv = res["invariant"][f"{tau:.2f}"]
        print(f"\n[PLAN-022 재판정] L3={res['l3_suites']} ⊥ T3={res['t3_suites']} · "
              f"주 τ={tau} · {res['elapsed_s']}초")
        print(f"  검출력 불변량 L3_all ⟺ L3_pa ∨ T3 : 위반 {inv['n_violation']}/{inv['n_checked']}"
              f" → {'성립' if inv['holds'] else '❌ 위반 — 결과를 그대로 쓸 수 없다'}")
        print(f"  L3 검출 구 {sa['n_l3_v2']}/{sa['n_instances']} → 신(pa) "
              f"{s['n_l3_v2']}/{s['n_instances']}  ·  T3 {s['n_t3_v2']}/{s['n_instances']}")
        print(f"  H1″ 교차결함 T3 단독검출 {s['h1p']['n_t3_only']}/{s['h1p']['n_cross_instances']} "
              f"(구 귀속 {sa['h1p']['n_t3_only']}/{sa['h1p']['n_cross_instances']})")
        print(f"  McNemar b={s['mcnemar']['b']} c={s['mcnemar']['c']} p={s['mcnemar']['p']:.4f}")
        print(f"  위양성 {s['false_positive']['n_rejected']}/{s['false_positive']['n_normal']} · "
              f"면제 승인 {res['n_exempt']}건")
        out = config.ROOT / "paper" / "tables" / "fault_matrix_v3.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_table_v3(res), encoding="utf-8")
        print(f"  표 → {out}\n  → {REPORT_V3}")
        return

    if args.holdout or args.holdout_judge:
        res = (judge_holdout_run(workers=args.workers) if args.holdout_judge
               else run_holdout(workers=min(args.workers, 9), split=args.split))
        j = res["holdout"]
        kill = j["kill_switch"]
        print(f"\n[W9 홀드아웃] 규칙 {res['rule_version']} · 주 τ={res['tau_main']} · "
              f"{res['elapsed_s']}초")
        print(f"  정지 규칙: 위반 {len(kill['violations'])}건"
              + ("" if kill["pass"] else " → " + " · ".join(kill["violations"])))
        out = config.ROOT / "paper" / "tables" / "fault_matrix_v4.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_table_v4(res), encoding="utf-8")
        if not kill["pass"]:
            print("  ❌ 판정하지 않는다 — 구현 오류로 처리한다(PLAN-025 §3.4 정지 규칙)")
            print(f"  표 → {out}\n  → {REPORT_HOLDOUT_V4}")
            raise SystemExit(2)
        m = j["main"]
        mm, mc, fp = m["main"], m["main"]["mcnemar"], m["false_positive"]
        print(f"  T3 단독검출 {mm['n_t3_only']}/{mm['n_cross']} · "
              f"T3 검출 {mm['n_t3_detected']} · L3 검출 {mm['n_l3_detected']}")
        print(f"  단측 McNemar b={mc['b']} c={mc['c']} p={mc['p']:.4f} (방향 {mc['direction']})")
        print(f"  위양성 {fp['n_rejected']}/{fp['n_normal']}"
              + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else ""))
        print(f"  축 A 복제 T3 단독 {m['replicate_only']['n_t3_only']}/"
              f"{m['replicate_only']['n_cross']} · 축 B 일반화 "
              f"{m['novel_only']['n_t3_only']}/{m['novel_only']['n_cross']}")
        print(f"  ★ H1‴ **{m['verdict']}** (c1={m['main']['c1_t3_only']} · "
              f"c2={m['main']['c2_mcnemar']} · c3={m['c3_false_positive']})")
        print(f"  표 → {out}\n  → {REPORT_HOLDOUT_V4}")
        return

    if args.from_report:
        res = json.loads(REPORT.read_text(encoding="utf-8"))
        out = config.ROOT / "paper" / "tables" / "fault_matrix.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_table(res), encoding="utf-8")
        print(render_table(res))
        print(f"→ {out}")
        return

    Q.verify_pristine(strict=True)
    faults = tuple(args.faults.split(",")) if args.faults else None
    res = run_matrix(args.reps, workers=args.workers, split=args.split,
                     faults=faults, skip_t12=args.skip_t12)
    s = res["summary"]
    print(f"\n[결함주입 매트릭스] {s['n_instances']}인스턴스 · 오류 {s['n_errors']} · "
          f"{res['elapsed_s']}초")
    print(f"  McNemar b={s['mcnemar']['b']} c={s['mcnemar']['c']} "
          f"p={s['mcnemar']['p']:.4f} ({s['mcnemar']['test']})")
    print(f"  H1 교차결함 T3 단독검출 {s['h1']['n_t3_only']}/{s['h1']['n_cross_instances']}")
    fp = s["false_positive"]
    print(f"  위양성(정상 델타 거부) {fp['n_rejected']}/{fp['n_normal']}"
          + (f" = {fp['rate']:.1%}" if fp["rate"] is not None else ""))
    if args.write:
        out = config.ROOT / "paper" / "tables" / "fault_matrix.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_table(res), encoding="utf-8")
        print(f"  표 → {out}")
    print(f"  → {REPORT}")


if __name__ == "__main__":
    main()
