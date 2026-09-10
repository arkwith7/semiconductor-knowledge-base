#!/usr/bin/env python3
"""PLAN-005 단계 7 — V2·V3 재측정과 동결 목표 대조 (읽기 전용 · 그래프를 바꾸지 않는다).

**모든 정의·문턱·검정은 결과를 보기 전에 동결됐다** (계획 파일 2026-09-09 · 사용자 결정
D-τ · D-R · D-S · 계획서 §16). 이 스크립트가 하는 일은 그 정의를 계산해 PASS/FAIL 을 적는 것뿐이며,
미달을 보고 문턱·정의를 고치지 않는다(§1-2 · §6 "7에서 미달하면 멈춘다").

동결 정의 (아래 FROZEN 상수 · tests/test_stage7_remeasure.py 가 계획서와 일치를 고정한다)

  q          rej 출원(publication_id). 프로파일 p = q 의 독립항 하나(개념 ≥ 1).
  E(q)       q 의 모든 프로파일 필수개념 합집합 (단계 1 과 동일).
  Disc(d)    문헌 d 의 전 청구항 개념 합집합. Disc*(d) = Disc(d) ∪ {u : u coveredBy f, f ∈ Disc(d)}
             — 깊이 1 · 전이 없음(§3.3 {0,1}).
  Target(q)  심사관 인용문헌 중 목표 노드가 있는 것 ∖ {q}.
  R∃(q)      {d ≠ q : E(q) ∩ Disc*(d) ≠ ∅}                 ← 단계 1 정의 (연속성 · 병기)
  R∀(q)      ∪_p {d ≠ q : essential(p) ⊆ Disc*(d)}          ← CQ32 의 신규성 경로 (주 판정)
  SPR@S      |{q : Target ∩ R ≠ ∅ ∧ |R| ≤ S}| / |Q|

  사다리     L_A = 단계 1 커밋(460806d)의 parquet · 개념 필터 없음 · 확장 off · 퇴화형 목표(접지 문헌)
             L_B = 현 parquet · 바인딩 개념 · 확장 off · Disclosure 목표
             L_C = L_B + coveredBy 확장 on            ← 게이트는 L_C 대 L_A. L_B 는 귀속(데이터/공리)용.

  V2 PASS ⟺ (i) Q_A∩Q_C 위 페어드 부트스트랩 95% CI 가 Δ=SPR∀@50(L_C)−SPR∀@50(L_A) 에서 0 을 배제 ∧ Δ>0
           ∧ (ii) Q_KR 위 SPR∀@50(L_C) ≥ τ=0.6708  (대조군 tfidf KR R@50 · priorart_baseline.json control_group)
           ∧ (iii) median|R∀(L_C)| ≤ median|R∀(L_A)|
  V3 PASS ⟺ §29② 포함 층 · 인용 2문헌 이상 · L_C 의 Δ=best_pair−best_single 평균의 부트스트랩 95% CI 가 0 배제 ∧ 양수.
           신규성(§29①)은 정량 판정 없음 — 서술만.
  V4 PASS ⟺ (report_v4_robustness.py 의 산출을 읽어) L1·L2·L3 의 회수율이 claim 대비 −0.05 이내(R∃·R∀ 각각)
           ∧ 자카드 Q1 회수율 ≥ Q4 − 0.10.

마스킹은 구성으로 충족된다 — Reach 계산은 정답 간선을 읽지 않는다. 계산은 전부 파이썬 집합이다
(같은 정의의 rdflib COUNT 는 6-A 실측에서 15분 넘게 미완). L_B·L_C 의 프로파일·개시집합은 A-Box
생성기의 함수로 재파생하고 `abox_priorart_report.json` 의 수와 대조한다 — 어긋나면 죽는다.

CLI:
    python scripts/report_stage7_remeasure.py                       # 전량 (수 분)
    python scripts/report_stage7_remeasure.py --baseline-parquet P  # git show 대신 파일 지정
    python scripts/report_stage7_remeasure.py --markdown PATH       # 판정 리포트 렌더
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics as st
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_abox_priorart as gen  # noqa: E402

OUT = ROOT / "data" / "reports" / "priorart_stage7_remeasure.json"
STAGE1 = ROOT / "data" / "reports" / "priorart_baseline.json"
ABOX_REPORT = ROOT / "data" / "reports" / "abox_priorart_report.json"
V4_REPORT = ROOT / "data" / "reports" / "v4_robustness.json"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
FEATURES_REL = "mappings/claim_features.parquet"

INF = float("inf")

#: 결과를 보기 전에 동결한 값 — 계획 파일 2026-09-09 (사용자 결정 D-τ · D-R · D-S).
FROZEN = {
    "tau": 0.6708,
    "tau_source": "data/reports/priorart_baseline.json · control_group.language_stratified_R@50.tfidf_KR",
    "tau_stratum": "Q_KR = {q ∈ Q_C : Target(q) 에 KR 인용문헌 있음}",
    "S_primary": 50,
    "S_all": [50, 100, 1000, "inf"],
    "primary_reach": "R∀",
    "bootstrap_B": 10000,
    "seed": 20260909,
    "ci": 0.95,
    "v4_drop_max": 0.05,
    "v4_quartile_drop_max": 0.10,
    "baseline_commit": "460806d",
    "baseline_parquet_sha256_prefix": "16f8300dbf15",
    "gate": "L_C 대 L_A (§1 '기준선 대비') · L_B 는 귀속(데이터 효과 / 공리 효과)",
    "v3_gate_stratum": "§29② 포함 층 (§29②-only ∪ §29①∧②) · 인용 2문헌 이상",
    "predictions_registered": {
        "P1": "Δ>0 비율은 §29②-only 층이 §29①-only 층보다 높다 (게이트 아님 · §29①-only 는 저검정력)",
        "P2": "L_C 의 best_single 중앙값 ≥ L_B (확장은 단일 문헌 포함률을 내리지 않는다)",
    },
}


# ── 원천 ─────────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def baseline_parquet(path: Path | None) -> Path:
    """단계 1 커밋의 parquet. 지정이 없으면 git 에서 꺼내고, 동결된 sha 접두와 대조한다."""
    if path is None:
        tmp = Path(tempfile.mkdtemp(prefix="sdkb_stage7_")) / "claim_features_460806d.parquet"
        blob = subprocess.run(["git", "show", f"{FROZEN['baseline_commit']}:{FEATURES_REL}"],
                              cwd=ROOT, check=True, capture_output=True).stdout
        tmp.write_bytes(blob)
        path = tmp
    if not _sha(path).startswith(FROZEN["baseline_parquet_sha256_prefix"]):
        raise SystemExit(f"ERROR: 기준선 parquet 의 sha 가 동결값({FROZEN['baseline_parquet_sha256_prefix']}…)과 다르다: {path}")
    return path


def load_gt() -> tuple[dict[str, set[str]], dict[str, str]]:
    """심사관 인용 정답과 (q, cited) 별 legal_bases 문자열. Reach 계산은 이것을 읽지 않는다."""
    ed = pd.read_parquet(EDGES)
    ex = ed[ed.source_type == "examiner"].copy()
    ex["tgt"] = ex.target_patent_id.str.replace("^patent:", "", regex=True)
    ex["cid"] = ex.cited_id.str.replace("^patent:", "", regex=True)
    gt = {q: set(s) for q, s in ex.groupby("tgt").cid}
    lb = {}
    if "legal_bases" in ex.columns:
        for q, c, v in zip(ex.tgt, ex.cid, ex.legal_bases.fillna("").astype(str)):
            lb[(q, c)] = v
    return gt, lb


def stratum_of(q: str, gt: dict, lb: dict) -> str:
    s = {lb.get((q, c), "") for c in gt[q]}
    has1 = any("§29①" in x for x in s)
    has2 = any("§29②" in x for x in s)
    return "§29①∧②" if (has1 and has2) else "§29②-only" if has2 else "§29①-only" if has1 else "없음"


class Layer:
    """한 층의 자료 — 프로파일(질의별 필수개념 집합들) · 개시집합 · 목표 노드 집합."""

    def __init__(self, name: str, profiles: dict[str, list[frozenset[str]]],
                 disc: dict[str, frozenset[str]], expansion: dict[str, set[str]] | None):
        self.name = name
        self.profiles = profiles                              # q → [essential(p), …]
        self.disc = disc                                      # d → Disc(d)
        self.expansion = expansion or {}                      # f → {u : u coveredBy f}
        self.disc_star = self._expand() if expansion else disc
        self.inv: dict[str, set[str]] = defaultdict(set)      # c → {d : c ∈ Disc*(d)}
        for d, cs in self.disc_star.items():
            for c in cs:
                self.inv[c].add(d)

    def _expand(self) -> dict[str, frozenset[str]]:
        out = {}
        for d, cs in self.disc.items():
            extra: set[str] = set()
            for f in cs:
                extra |= self.expansion.get(f, set())
            out[d] = frozenset(cs | extra)
        return out

    def E(self, q: str) -> frozenset[str]:
        return frozenset().union(*self.profiles[q])

    def reach_exist(self, q: str) -> set[str]:
        R: set[str] = set()
        for c in self.E(q):
            R |= self.inv.get(c, set())
        R.discard(q)
        return R

    def reach_all(self, q: str) -> set[str]:
        R: set[str] = set()
        for ess in self.profiles[q]:
            cs = sorted(ess, key=lambda c: len(self.inv.get(c, ())))
            acc = set(self.inv.get(cs[0], set()))
            for c in cs[1:]:
                if not acc:
                    break
                acc &= self.inv.get(c, set())
            R |= acc
        R.discard(q)
        return R


def layer_stage1(parquet: Path) -> Layer:
    """L_A — 단계 1 `report_priorart_baseline.load_concepts` 와 같은 정의. 개념 필터·확장 없음."""
    cf = pd.read_parquet(parquet, columns=["publication_id", "side", "is_independent", "claim_id", "feature_concept"])
    cf["feature_concept"] = cf.feature_concept.apply(lambda v: [] if v is None else [str(x) for x in v])
    ex = cf.explode("feature_concept").dropna(subset=["feature_concept"])
    doc = {d: frozenset(s) for d, s in ex.groupby("publication_id").feature_concept}
    ind = ex[ex.is_independent & (ex.side == "rej")]
    prof: dict[str, list[frozenset[str]]] = defaultdict(list)
    for (pid, _cid), s in ind.groupby(["publication_id", "claim_id"]).feature_concept:
        prof[pid].append(frozenset(s))
    return Layer("L_A", dict(prof), doc, None)


def layers_current(expand: bool) -> tuple[Layer, dict]:
    """L_B / L_C — A-Box 생성기의 함수로 재파생한다. 리포트와 어긋나면 죽는다."""
    core_data = Graph().parse(gen.CORE_DATA, format="turtle")
    core = Graph().parse(gen.CORE, format="turtle")
    semi = Graph().parse(gen.SEMI, format="turtle")
    bound = gen.bound_concepts(core_data, gen.technical_concept_classes(semi))
    df = gen.load_features(gen.FEATURES)
    concepts, _ = gen.claim_concepts(df, bound)
    claims = df[["claim_id", "side", "is_independent"]].drop_duplicates("claim_id")
    is_indep = dict(zip(claims["claim_id"], claims["is_independent"].astype(bool)))
    parents = {cid: list(dep) for cid, dep in
               df[["claim_id", "depends_on_claim"]].drop_duplicates("claim_id").itertuples(index=False) if len(dep)}
    roots, _ = gen.root_independents(is_indep, parents)
    profiles, _ = gen.build_profiles(claims, concepts, roots)
    disclosures, d_stat = gen.build_disclosures(df, concepts)
    pid_of = dict(zip(df["claim_id"], df["publication_id"]))
    prof: dict[str, list[frozenset[str]]] = defaultdict(list)
    for p in profiles:
        if p.side == "rej":
            prof[pid_of[p.claim_id]].append(frozenset(p.essential))
    disc = {d.publication_id: frozenset(d.concepts) for d in disclosures}
    exp, _ = gen.covered_by_sources(core, core_data, bound)
    pairs = sorted({(gen._concept_curie(a), gen._concept_curie(b)) for ps in exp.values() for a, b in ps})
    expansion: dict[str, set[str]] = defaultdict(set)
    for u, f in pairs:                                   # u broaderConcept f  ⇒  u coveredBy f
        expansion[f].add(u)
    rep = json.loads(ABOX_REPORT.read_text(encoding="utf-8"))
    identity = {
        "profiles": [len(profiles), rep["profiles"]["emitted"]],
        "disclosures": [len(disclosures), rep["disclosures"]["emitted"]],
        "essential_links": [sum(len(p.essential) for p in profiles), rep["profiles"]["essential_links"]],
        "covered_by_pairs": [len(pairs), rep["hierarchy"]["covered_by_total"]],
        "bound_concepts": [len(bound), rep["concepts"]["bound_in_core_data"]],
    }
    bad = {k: v for k, v in identity.items() if v[0] != v[1]}
    if bad:
        raise SystemExit(f"ERROR: parquet 재파생이 A-Box 리포트와 다르다 — `make abox-priorart` 후 다시: {bad}")
    identity["cited_without_disclosure_by_prefix"] = {
        k.split("__", 1)[1]: v for k, v in d_stat.items() if k.startswith("cited_without_disclosure__")}
    layer = Layer("L_C" if expand else "L_B", dict(prof), disc, dict(expansion) if expand else None)
    layer.bound = bound                                   # V4 가 텍스트 링커 개념을 pa: 경로에 맞춰 거를 때 쓴다
    return layer, identity


def conj_reach(layer: Layer, essential: frozenset[str], q: str) -> set[str]:
    """단일 필수개념 집합의 R∀ — V4 처럼 프로파일 대신 텍스트 한 덩어리가 질의일 때."""
    if not essential:
        return set()
    cs = sorted(essential, key=lambda c: len(layer.inv.get(c, ())))
    acc = set(layer.inv.get(cs[0], set()))
    for c in cs[1:]:
        if not acc:
            break
        acc &= layer.inv.get(c, set())
    acc.discard(q)
    return acc


# ── V2 · V3 계수 ──────────────────────────────────────────────────────────
def per_query(layer: Layer, gt: dict[str, set[str]]) -> dict[str, dict]:
    """질의마다 두 Reach 의 크기·적중과 목표 크기. Q = 프로파일 ≥ 1 ∧ Target ≠ ∅."""
    out = {}
    for q in sorted(gt):
        if q not in layer.profiles or not layer.profiles[q]:
            continue
        T = (gt[q] & layer.disc.keys()) - {q}
        if not T:
            continue
        Re, Ra = layer.reach_exist(q), layer.reach_all(q)
        out[q] = {
            "n_target": len(T), "target_kr": any(t.startswith("kr_") for t in T),
            "target_us": any(t.startswith("us_") for t in T),
            "exist": {"reach": len(Re), "hit": bool(T & Re)},
            "all": {"reach": len(Ra), "hit": bool(T & Ra)},
        }
    return out


def _spr(recs: dict[str, dict], fam: str, S: float, qs=None) -> float | None:
    qs = list(recs) if qs is None else [q for q in qs if q in recs]
    if not qs:
        return None
    return sum(1 for q in qs if recs[q][fam]["hit"] and recs[q][fam]["reach"] <= S) / len(qs)


def summarize(recs: dict[str, dict]) -> dict:
    out = {"queries": len(recs), "target_size_median": st.median(r["n_target"] for r in recs.values()) if recs else None,
           "queries_kr": sum(r["target_kr"] for r in recs.values()),
           "queries_us": sum(r["target_us"] for r in recs.values())}
    kr = [q for q, r in recs.items() if r["target_kr"]]
    us = [q for q, r in recs.items() if r["target_us"]]
    for fam in ("exist", "all"):
        sizes = [r[fam]["reach"] for r in recs.values()]
        out[fam] = {
            "reach_median": st.median(sizes) if sizes else None,
            "reach_mean": round(sum(sizes) / len(sizes), 1) if sizes else None,
            "reach_max": max(sizes) if sizes else None,
            "reach_zero_queries": sum(1 for s in sizes if s == 0),
            "hit_rate_any_S": round(sum(r[fam]["hit"] for r in recs.values()) / len(recs), 6) if recs else None,
            **{f"SPR@{S}": _spr(recs, fam, S if S != "inf" else INF) for S in FROZEN["S_all"]},
            "SPR@50_KR": _spr(recs, fam, 50, kr), "SPR@50_US": _spr(recs, fam, 50, us),
        }
    return out


def paired_bootstrap(a: list[int], c: list[int], B: int, seed: int, ci: float) -> dict:
    """같은 질의 위 두 지시자의 평균 차 Δ 와 퍼센타일 CI. 결정적(seed)."""
    a_, c_ = np.asarray(a, dtype=float), np.asarray(c, dtype=float)
    n = len(a_)
    if n == 0:
        return {"n": 0, "delta": None, "ci": None}
    rng = np.random.RandomState(seed)
    idx = rng.randint(0, n, size=(B, n))
    deltas = c_[idx].mean(axis=1) - a_[idx].mean(axis=1)
    lo, hi = np.percentile(deltas, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return {"n": n, "delta": float(c_.mean() - a_.mean()), "ci": [float(lo), float(hi)], "B": B, "seed": seed}


def mcnemar_exact(a: list[int], c: list[int]) -> dict:
    b01 = sum(1 for x, y in zip(a, c) if x == 0 and y == 1)   # C 만 성공
    b10 = sum(1 for x, y in zip(a, c) if x == 1 and y == 0)   # A 만 성공
    n = b01 + b10
    if n == 0:
        return {"c_only": 0, "a_only": 0, "p": 1.0}
    k = min(b01, b10)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"c_only": b01, "a_only": b10, "p": p}


def v2_verdict(recA: dict[str, dict], recC: dict[str, dict], frozen: dict = FROZEN) -> dict:
    S = frozen["S_primary"]
    common = sorted(set(recA) & set(recC))
    a = [int(recA[q]["all"]["hit"] and recA[q]["all"]["reach"] <= S) for q in common]
    c = [int(recC[q]["all"]["hit"] and recC[q]["all"]["reach"] <= S) for q in common]
    boot = paired_bootstrap(a, c, frozen["bootstrap_B"], frozen["seed"], frozen["ci"])
    i_ok = bool(boot["ci"] and boot["ci"][0] > 0 and boot["delta"] > 0)
    kr = [q for q, r in recC.items() if r["target_kr"]]
    spr_kr = _spr(recC, "all", S, kr)
    ii_ok = spr_kr is not None and spr_kr >= frozen["tau"]
    medA = st.median(r["all"]["reach"] for r in recA.values()) if recA else None
    medC = st.median(r["all"]["reach"] for r in recC.values()) if recC else None
    iii_ok = medA is not None and medC is not None and medC <= medA
    return {
        "i_significant_rise": {"pass": i_ok, "common_queries": len(common),
                               "SPR_all@50_A": (sum(a) / len(a)) if a else None,
                               "SPR_all@50_C": (sum(c) / len(c)) if c else None,
                               "bootstrap": boot, "mcnemar": mcnemar_exact(a, c)},
        "ii_tau": {"pass": ii_ok, "tau": frozen["tau"], "SPR_all@50_KR_C": spr_kr, "queries_kr": len(kr)},
        "iii_specificity": {"pass": iii_ok, "reach_all_median_A": medA, "reach_all_median_C": medC},
        "pass": bool(i_ok and ii_ok and iii_ok),
        "failed_conditions": [k for k, ok in (("i", i_ok), ("ii", ii_ok), ("iii", iii_ok)) if not ok],
    }


def v3_rows(layer: Layer, gt: dict[str, set[str]], lb: dict) -> list[dict]:
    """cov*(q,d)=|E∩Disc*(d)|/|E| · best_single · best_pair · Δ. 단계 1 v3_coverage 와 같은 형식."""
    rows = []
    for q in sorted(gt):
        if q not in layer.profiles or not layer.profiles[q]:
            continue
        E = layer.E(q)
        cited = sorted(d for d in gt[q] if d in layer.disc_star)
        if not E or not cited:
            continue
        cov = {d: len(E & layer.disc_star[d]) / len(E) for d in cited}
        best1 = max(cov.values())
        best2 = best1
        for i in range(len(cited)):
            for j in range(i + 1, len(cited)):
                u = layer.disc_star[cited[i]] | layer.disc_star[cited[j]]
                best2 = max(best2, len(E & u) / len(E))
        rows.append({"q": q, "nE": len(E), "n_cited": len(cited), "best_single": best1,
                     "best_pair": best2, "delta": best2 - best1, "stratum": stratum_of(q, gt, lb)})
    return rows


def v3_summary(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    if df.empty:
        return {"queries": 0}
    multi = df[df.n_cited >= 2]
    by_stratum = {}
    for s, g in df.groupby("stratum"):
        m = g[g.n_cited >= 2]
        by_stratum[s] = {"queries": int(len(g)), "pair_queries": int(len(m)),
                         "best_single_median": float(g.best_single.median()),
                         "delta_mean": round(float(m.delta.mean()), 4) if len(m) else None,
                         "delta_gt0_frac": round(float((m.delta > 0).mean()), 4) if len(m) else None}
    return {
        "queries": int(len(df)),
        "essential_concepts_per_query": {"median": float(df.nE.median()), "mean": round(float(df.nE.mean()), 2),
                                         "p10": float(df.nE.quantile(.10)), "p90": float(df.nE.quantile(.90))},
        "best_single_coverage": {"median": float(df.best_single.median()), "mean": round(float(df.best_single.mean()), 4),
                                 "eq0": int((df.best_single == 0).sum()), "eq1": int((df.best_single == 1).sum()),
                                 "saturated_frac": round(float(((df.best_single == 0) | (df.best_single == 1)).mean()), 4)},
        "pair_queries": int(len(multi)),
        "delta_coverage": {"median": float(multi.delta.median()) if len(multi) else None,
                           "mean": round(float(multi.delta.mean()), 4) if len(multi) else None,
                           "gt0_frac": round(float((multi.delta > 0).mean()), 4) if len(multi) else None},
        "by_stratum": by_stratum,
    }


def v3_verdict(rowsB: list[dict], rowsC: list[dict], frozen: dict = FROZEN) -> dict:
    gate = [r for r in rowsC if r["n_cited"] >= 2 and "§29②" in r["stratum"]]
    d = [r["delta"] for r in gate]
    boot = paired_bootstrap([0.0] * len(d), d, frozen["bootstrap_B"], frozen["seed"], frozen["ci"])
    ok = bool(boot["ci"] and boot["ci"][0] > 0 and boot["delta"] > 0)
    # 사전 등록 예측 (게이트 아님)
    only2 = [r["delta"] > 0 for r in rowsC if r["n_cited"] >= 2 and r["stratum"] == "§29②-only"]
    only1 = [r["delta"] > 0 for r in rowsC if r["n_cited"] >= 2 and r["stratum"] == "§29①-only"]
    p1 = {"frac_29_2_only": (sum(only2) / len(only2)) if only2 else None, "n_29_2_only": len(only2),
          "frac_29_1_only": (sum(only1) / len(only1)) if only1 else None, "n_29_1_only": len(only1),
          "underpowered": len(only1) < 30 or len(only2) < 30}
    if only1 and only2:
        p1["diff_bootstrap"] = _two_sample_bootstrap([int(x) for x in only1], [int(x) for x in only2], frozen)
        p1["holds"] = p1["frac_29_2_only"] > p1["frac_29_1_only"]
    else:
        p1["holds"] = None
    medB = st.median(r["best_single"] for r in rowsB) if rowsB else None
    medC = st.median(r["best_single"] for r in rowsC) if rowsC else None
    p2 = {"best_single_median_B": medB, "best_single_median_C": medC,
          "holds": (medC >= medB) if (medB is not None and medC is not None) else None}
    return {"gate_stratum": frozen["v3_gate_stratum"], "gate_queries": len(gate),
            "delta_mean_C": boot["delta"], "bootstrap": boot, "pass": ok,
            "novelty": "정량 판정 없음 (§5 · §29① 표본 < 문서 254건 규모) — by_stratum 서술만",
            "P1": p1, "P2": p2}


def _two_sample_bootstrap(x: list[int], y: list[int], frozen: dict) -> dict:
    rng = np.random.RandomState(frozen["seed"])
    x_, y_ = np.asarray(x, float), np.asarray(y, float)
    B = frozen["bootstrap_B"]
    dx = y_[rng.randint(0, len(y_), (B, len(y_)))].mean(1) - x_[rng.randint(0, len(x_), (B, len(x_)))].mean(1)
    lo, hi = np.percentile(dx, [2.5, 97.5])
    return {"delta": float(y_.mean() - x_.mean()), "ci": [float(lo), float(hi)]}


def v4_verdict(v4: dict | None, frozen: dict = FROZEN) -> dict:
    """report_v4_robustness.py 산출을 읽는다. R∀·Disclosure 키가 없으면 미산출로 적는다."""
    if not v4:
        return {"status": "미산출", "pass": None}
    bv = v4.get("by_variant", {})
    if "claim" not in bv:
        return {"status": "미산출", "pass": None}
    checks = {}
    for fam, key in (("exist", "hit_rate"), ("all", "conj_disclosure")):
        base = bv["claim"].get(key) if fam == "exist" else (bv["claim"].get(key) or {}).get("hit_rate")
        if base is None:
            checks[fam] = {"status": "미산출"}
            continue
        per = {}
        for v in ("L1", "L2", "L3"):
            h = bv.get(v, {}).get(key) if fam == "exist" else (bv.get(v, {}).get(key) or {}).get("hit_rate")
            per[v] = {"hit_rate": h, "drop": (base - h) if h is not None else None,
                      "pass": (h is not None and base - h <= frozen["v4_drop_max"])}
        checks[fam] = {"claim_hit_rate": base, "variants": per, "pass": all(p["pass"] for p in per.values())}
    quart = v4.get("llm_jaccard_quartiles", {})
    q1, q4 = quart.get("Q1_먼", {}).get("hit_rate"), quart.get("Q4_가까운", {}).get("hit_rate")
    qk = {"Q1": q1, "Q4": q4, "pass": (q1 is not None and q4 is not None and q1 >= q4 - frozen["v4_quartile_drop_max"])}
    conj_missing = checks.get("all", {}).get("status") == "미산출"
    ok = all(c.get("pass") for c in checks.values() if "pass" in c) and qk["pass"] and not conj_missing
    return {"status": "부분 (R∀ 미산출)" if conj_missing else "산출", "checks": checks,
            "quartile": qk, "human_coding_reference": "data/reports/v4_human_coding.json (κ 0.6934 · 재코딩 없음)",
            "pass": bool(ok) if not conj_missing else None}


# ── 실행 ──────────────────────────────────────────────────────────────────
def run(baseline: Path | None, log=print) -> dict:
    gt, lb = load_gt()
    bp = baseline_parquet(baseline)
    log("· L_A (단계 1 parquet) 적재")
    LA = layer_stage1(bp)
    log("· L_B / L_C (현 parquet · 생성기 재파생) 적재")
    LB, identity = layers_current(expand=False)
    LC, _ = layers_current(expand=True)
    layers = {"L_A": LA, "L_B": LB, "L_C": LC}

    recs = {k: per_query(L, gt) for k, L in layers.items()}
    rows = {k: v3_rows(L, gt, lb) for k, L in layers.items()}
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))
    s1v2, s1v3 = stage1["V2_semantic_path_recall"], stage1["V3_coverage"]
    sumA = summarize(recs["L_A"])
    v3A = v3_summary(rows["L_A"])
    repro = {
        "V2": {k: [s1v2[k], obs] for k, obs in (
            ("queries", sumA["queries"]), ("target_size_median", sumA["target_size_median"]),
            ("reach_size_median", sumA["exist"]["reach_median"]), ("reach_size_mean", sumA["exist"]["reach_mean"]),
            ("reach_size_max", sumA["exist"]["reach_max"]), ("hit_rate_any_S", sumA["exist"]["hit_rate_any_S"]),
            ("SemanticPathRecall@100", sumA["exist"]["SPR@100"]), ("SemanticPathRecall@1000", sumA["exist"]["SPR@1000"]),
            ("SemanticPathRecall@inf", sumA["exist"]["SPR@inf"]))},
        "V3": {"queries": [s1v3["queries"], v3A["queries"]], "pair_queries": [s1v3["pair_queries"], v3A["pair_queries"]],
               "best_single_mean": [s1v3["best_single_coverage"]["mean"], v3A["best_single_coverage"]["mean"]],
               "eq1": [s1v3["best_single_coverage"]["eq1"], v3A["best_single_coverage"]["eq1"]],
               "delta_mean": [s1v3["delta_coverage"]["mean"], v3A["delta_coverage"]["mean"]],
               "delta_gt0_frac": [s1v3["delta_coverage"]["gt0_frac"], v3A["delta_coverage"]["gt0_frac"]]},
    }
    repro["ok"] = all(abs(float(a) - float(b)) < 1e-6 for sec in ("V2", "V3") for a, b in repro[sec].values())

    v2 = v2_verdict(recs["L_A"], recs["L_C"])
    v3 = v3_verdict(rows["L_B"], rows["L_C"])
    v4 = v4_verdict(json.loads(V4_REPORT.read_text(encoding="utf-8")) if V4_REPORT.exists() else None)
    S = FROZEN["S_primary"]
    sums = {k: summarize(r) for k, r in recs.items()}
    return {
        "plan": "PLAN-005 단계 7 · V2–V4 재측정 · 동결 목표 대조",
        "generator": "scripts/report_stage7_remeasure.py",
        "generated": str(date.today()),
        "read_only": True,
        "frozen": FROZEN,
        "inputs": {
            "baseline_parquet_sha256": _sha(bp), FEATURES_REL: _sha(ROOT / FEATURES_REL),
            "ontology/sdkb-priorart-core.ttl": _sha(gen.CORE), "ontology/sdkb-core-data.ttl": _sha(gen.CORE_DATA),
            "ontology/sdkb-priorart-semi.ttl": _sha(gen.SEMI), "data/patents/prior_art_edges.parquet": _sha(EDGES),
            "data/reports/abox_priorart_report.json": _sha(ABOX_REPORT),
            "data/reports/v4_robustness.json": _sha(V4_REPORT) if V4_REPORT.exists() else None,
        },
        "identity_check_vs_abox_report": identity,
        "stage1_reproduction": repro,
        "descriptive": {
            "Q": {k: s["queries"] for k, s in sums.items()},
            "Q_A_and_Q_C": len(set(recs["L_A"]) & set(recs["L_C"])),
            "Q_C_strata": dict(Counter(stratum_of(q, gt, lb) for q in recs["L_C"])),
            "gt_targets_total": len(gt),
        },
        "ladder": {k: {"reach": sums[k], "coverage": v3_summary(rows[k])} for k in layers},
        "attribution": {
            "measure": f"SPR∀@{S}",
            "data_effect_B_minus_A": (sums["L_B"]["all"][f"SPR@{S}"] - sums["L_A"]["all"][f"SPR@{S}"]),
            "axiom_effect_C_minus_B": (sums["L_C"]["all"][f"SPR@{S}"] - sums["L_B"]["all"][f"SPR@{S}"]),
            "total_C_minus_A": (sums["L_C"]["all"][f"SPR@{S}"] - sums["L_A"]["all"][f"SPR@{S}"]),
        },
        "verdict": {"V2": v2, "V3": v3, "V4": v4},
        "limitations": [
            "SPR 은 순위 없는 후보집합이 S 이하여야 하는 지표이고 τ 의 원천 tfidf R@50 은 순위 지표다 — "
            "비대칭은 τ 를 유리하게 하지 않는다 (계획 파일 · 결과 전 명시).",
            "Disclosure 는 KR/US 분해 문헌에만 있다 — 인용문헌 중 JP 등 비 KR/US 는 목표에서 빠진다 (§4 결손 · 수는 identity_check 에).",
            "§29①-only 층은 질의가 적어 P1 은 저검정력이다 — 결론을 얹지 않는다.",
            "V4-2(사람 코딩)는 재실행하지 않고 인용한다.",
        ],
    }


def _f(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else f"{x:,}")


def render_markdown(rep: dict) -> str:
    v = rep["verdict"]
    S = rep["frozen"]["S_primary"]
    L = ["# PLAN-005 단계 7 — V2–V4 재측정 · 동결 목표 대조 (기계 산출)", "",
         f"> 생성: `scripts/report_stage7_remeasure.py` · {rep['generated']} · **손으로 고치지 않는다** — "
         "`make stage7-remeasure` 가 다시 만든다. 정의·문턱은 스크립트 `FROZEN`(결과 전 동결).", "",
         "## 판정", "", "| 검증 | 판정 | 걸린 조건 |", "|---|:-:|---|",
         f"| V2 도달 | **{'PASS' if v['V2']['pass'] else 'FAIL'}** | {', '.join(v['V2']['failed_conditions']) or '—'} |",
         f"| V3 업무 목적(진보성) | **{'PASS' if v['V3']['pass'] else 'FAIL'}** | 게이트 층 q={v['V3']['gate_queries']} · Δ평균 {_f(v['V3']['delta_mean_C'])} · CI {v['V3']['bootstrap']['ci']} |",
         f"| V4 질의 비종속성 | **{('PASS' if v['V4']['pass'] else 'FAIL') if v['V4'].get('pass') is not None else v['V4']['status']}** | — |", ""]
    i, ii, iii = v["V2"]["i_significant_rise"], v["V2"]["ii_tau"], v["V2"]["iii_specificity"]
    L += ["### V2 세 조건", "", "| 조건 | 값 | 판정 |", "|---|---|:-:|",
          f"| (i) 유의 상승 · Q_A∩Q_C={i['common_queries']} | SPR∀@{S} A {_f(i['SPR_all@50_A'])} → C {_f(i['SPR_all@50_C'])} · Δ {_f(i['bootstrap']['delta'])} · 95% CI {i['bootstrap']['ci']} · McNemar p {_f(i['mcnemar']['p'])} | {'✓' if i['pass'] else '✗'} |",
          f"| (ii) τ={ii['tau']} · Q_KR={ii['queries_kr']} | SPR∀@{S}(KR) {_f(ii['SPR_all@50_KR_C'])} | {'✓' if ii['pass'] else '✗'} |",
          f"| (iii) 특이도 | median\\|R∀\\| A {_f(iii['reach_all_median_A'])} → C {_f(iii['reach_all_median_C'])} | {'✓' if iii['pass'] else '✗'} |", ""]
    L += ["## 사다리", "", "| 층 | Q | R | SPR@50 | SPR@100 | SPR@1000 | 적중(∞) | median\\|R\\| | SPR@50 KR | SPR@50 US |",
          "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, d in rep["ladder"].items():
        r = d["reach"]
        for fam, lab in (("exist", "R∃"), ("all", "R∀")):
            s = r[fam]
            L.append(f"| {k} | {r['queries']} | {lab} | {_f(s['SPR@50'])} | {_f(s['SPR@100'])} | {_f(s['SPR@1000'])} | "
                     f"{_f(s['hit_rate_any_S'])} | {_f(s['reach_median'])} | {_f(s['SPR@50_KR'])} | {_f(s['SPR@50_US'])} |")
    a = rep["attribution"]
    L += ["", f"귀속({a['measure']}): 데이터 효과 B−A {_f(a['data_effect_B_minus_A'])} · 공리 효과 C−B "
          f"{_f(a['axiom_effect_C_minus_B'])} · 합 C−A {_f(a['total_C_minus_A'])}", ""]
    L += ["## V3 커버 (층별 · L_C)", "", "| 층 | q | 2문헌+ | best_single 중앙 | Δ 평균 | Δ>0 비율 |", "|---|---:|---:|---:|---:|---:|"]
    for s, d in rep["ladder"]["L_C"]["coverage"].get("by_stratum", {}).items():
        L.append(f"| {s} | {d['queries']} | {d['pair_queries']} | {_f(d['best_single_median'])} | {_f(d['delta_mean'])} | {_f(d['delta_gt0_frac'])} |")
    p1, p2 = v["V3"]["P1"], v["V3"]["P2"]
    L += ["", f"사전 등록 P1(게이트 아님): §29②-only {_f(p1['frac_29_2_only'])}(n={p1['n_29_2_only']}) 대 §29①-only "
          f"{_f(p1['frac_29_1_only'])}(n={p1['n_29_1_only']}) · 성립 {p1['holds']} · 저검정력 {p1['underpowered']}",
          f"사전 등록 P2: best_single 중앙 B {_f(p2['best_single_median_B'])} → C {_f(p2['best_single_median_C'])} · 성립 {p2['holds']}", ""]
    rp = rep["stage1_reproduction"]
    L += ["## 계측기 검사 — 단계 1 재현 (L_A · R∃)", "", f"재현 {'OK' if rp['ok'] else '**실패**'}: " +
          " · ".join(f"{k} {a}→{b}" for k, (a, b) in rp["V2"].items()), ""]
    L += ["## 한계", ""] + [f"- {x}" for x in rep["limitations"]]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-parquet", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--markdown", type=Path, default=None)
    a = ap.parse_args()
    rep = run(a.baseline_parquet)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.markdown:
        a.markdown.write_text(render_markdown(rep), encoding="utf-8")
    v = rep["verdict"]
    print(f"V2 {'PASS' if v['V2']['pass'] else 'FAIL ' + str(v['V2']['failed_conditions'])} · "
          f"V3 {'PASS' if v['V3']['pass'] else 'FAIL'} · V4 {v['V4'].get('pass')} ({v['V4']['status']})")
    print(f"단계 1 재현 {'OK' if rep['stage1_reproduction']['ok'] else 'FAIL'} · "
          f"Q {rep['descriptive']['Q']} · 귀속 {rep['attribution']}")
    print(f"→ {a.out}" + (f" · {a.markdown}" if a.markdown else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
