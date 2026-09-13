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

**단계 7-A′ 모드 (2026-09-10 · 사용자 승인 · 계획서 §17).** 현 parquet 의 sha 가 단계 7 판정 커밋
(`0a9344b` · `1e8b14ca…`)과 다르면 사다리를 L_A · L_C(그 커밋의 parquet 소급 · 확장 on) · [추가 층] ·
L_D(현 parquet · 확장 on) 로 세우고, **레버 게이트는 L_D 대 L_C**, V2 세 조건은 **L_D 대 L_A** · τ 불변으로
다시 판정한다. 레버 게이트(FROZEN["stage7a"] · 결과 전 동결): rej 독립항 미매핑 ≤ 0.20 ∧ median|R∀| 감소의
페어드 95% CI 가 0 배제 ∧ 적중(∞) 저하 ≤ 0.02.

마스킹은 구성으로 충족된다 — Reach 계산은 정답 간선을 읽지 않는다. 계산은 전부 파이썬 집합이다
(같은 정의의 rdflib COUNT 는 6-A 실측에서 15분 넘게 미완). 현 parquet 층의 프로파일·개시집합은 A-Box
생성기의 함수로 재파생하고 `abox_priorart_report.json` 의 수와 대조한다 — 어긋나면 죽는다.

CLI:
    python scripts/report_stage7_remeasure.py                       # 전량 (수 분)
    python scripts/report_stage7_remeasure.py --baseline-parquet P  # git show 대신 파일 지정
    python scripts/report_stage7_remeasure.py --layer L_D0=PATH     # 추가 층(확장 on · 이름=parquet)
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

sys.path.insert(0, str(ROOT))
from scripts import seal, splits  # noqa: E402

OUT = ROOT / "data" / "reports" / "priorart_stage7_remeasure.json"
STAGE1 = ROOT / "data" / "reports" / "priorart_baseline.json"
ABOX_REPORT = ROOT / "data" / "reports" / "abox_priorart_report.json"
V4_REPORT = ROOT / "data" / "reports" / "v4_robustness.json"


def v4_report_path(scope: str) -> Path:
    """분할별 V4 산출물. `all` 은 기존 경로 그대로 — 질의 세트 sha 동결은 불변이다 (CAL-3)."""
    return V4_REPORT if scope == "all" else V4_REPORT.with_name(f"v4_robustness.{scope}.json")
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
FEATURES_REL = "mappings/claim_features.parquet"

INF = float("inf")

#: 결과를 보기 전에 동결한 값 — 계획 파일 2026-09-09 (사용자 결정 D-τ · D-R · D-S) · 7-A′ 는 2026-09-10.
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
    # 문면(위)은 처음부터 옳았고 틀린 것은 코드였다 (§20 E-1 · CAL-1). 기계 표현을 병기해
    # 리포트가 "실행하지 않은 정의를 인쇄"하는 일을 구조적으로 막는다 — 둘이 어긋나면 죽는다.
    "v3_gate_strata": ["§29②-only", "§29①∧②"],
    "predictions_registered": {
        "P1": "Δ>0 비율은 §29②-only 층이 §29①-only 층보다 높다 (게이트 아님 · §29①-only 는 저검정력)",
        "P2": "L_C 의 best_single 중앙값 ≥ L_B (확장은 단일 문헌 포함률을 내리지 않는다)",
    },
    # 단계 7-A′ — 레버 게이트 (2026-09-10 · 결과 전 · 사용자 승인 A)
    "stage7a": {
        "c_commit": "0a9344b",
        "c_parquet_sha256_prefix": "1e8b14cae533",
        "rej_unmapped_max": 0.20,
        "hit_drop_max": 0.02,
        "lever_gate": "median|R∀| 감소(L_D−L_C)의 페어드 95% CI 가 0 을 배제 ∧ Δ<0",
        "gate": "레버는 L_D 대 L_C · V2 세 조건은 L_D 대 L_A · τ 불변",
    },
}


#: 판정 범위 (CAL-3 · §20.2 E-3). 개념 사전이 dev+train 800 통지서에서 채굴됐으므로
#: **train 은 상한이지 성능이 아니고**, test·test_b 는 봉인이다(D17 — 코드 게이트로만 연다).
PRIMARY_SPLIT = "dev"
REPORT_SCOPES = ("dev", "train", "all")

#: 하류가 분기하는 키 (§20.11). 같은 키(`verdict`)가 이 버전부터 **dev 주 판정**을 담는다.
INSTRUMENT_VERSION = "R0-CAL-3"

LEGACY_SCOPE_NOTE = (
    "전량(train+dev+test) · 분할 미존중 · 교정 전 범위. 개념 사전이 dev+train 통지서에서 채굴됐으므로 "
    "**홀드아웃 성능이 아니다** — 개발 지표로만 읽는다 (§20.2 E-3 · D13 이력 보존)."
)
TRAIN_SCOPE_NOTE = (
    "개념 사전이 이 문서들에서 채굴됐다 — **상한이지 성능이 아니다** (§20.7 CAL-3)."
)


#: V3 게이트가 겨냥하는 층 라벨의 기계 표현 (CAL-1 · §20 E-1).
#: 라벨 **문자열 값은 불변**이다 — 이미 공표된 JSON 키이자 판정 리포트의 행 이름이다.
#: 혼합 라벨 "§29①∧②" 는 "§29②" 를 부분문자열로 갖지 않는다(§29 다음 코드포인트가 ① U+2460).
#: 그래서 부분문자열 판정은 혼합층을 조용히 버렸다 — 집합 소속으로 판정한다.
INVENTIVE_STRATA = frozenset({"§29②-only", "§29①∧②"})


def assert_gate_strata_agree(frozen: dict = FROZEN, strata: frozenset = INVENTIVE_STRATA) -> None:
    """동결된 문면과 기계 표현이 같은 층을 가리키는지. 어긋나면 죽는다 (임포트 시점에 판정)."""
    machine = set(frozen["v3_gate_strata"])
    if machine != set(strata):
        raise SystemExit(f"ERROR: v3_gate_strata {sorted(machine)} 가 INVENTIVE_STRATA {sorted(strata)} 와 다르다")
    missing = [x for x in sorted(machine) if x not in frozen["v3_gate_stratum"]]
    if missing:
        raise SystemExit(f"ERROR: 동결 문면 v3_gate_stratum 이 층 {missing} 을 적지 않는다 — 문면과 코드가 갈렸다")


assert_gate_strata_agree()


def assert_scope_allowed(scope: str, *, ledger_rows: int = 0) -> None:
    """봉인 분할의 지표는 **원장에 이 실행의 행이 없으면 낼 수 없다** (D17 · §20.10).

    "test 행에 숫자를 찍을 수 없다" 를 산문이 아니라 코드가 막는다 — 봉인을 여는 길은
    `scripts/seal.py:open_sealed()` 하나뿐이고, 그것은 원장에 행을 남긴다.
    """
    if scope in splits.SEALED and not ledger_rows:
        raise SystemExit(
            f"ERROR: 봉인 분할 '{scope}' 의 지표를 내려 한다 — 봉인 원장({seal.LEDGER.name})에 행이 0이다. "
            "seal.open_sealed() 를 거치지 않은 접근은 막는다(D17)."
        )


# ── 원천 ─────────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parquet_from_git(commit: str, sha_prefix: str | None = None, label: str = "") -> Path:
    """git 커밋의 claim_features.parquet 를 임시 파일로 꺼내고 동결된 sha 접두와 대조한다."""
    tmp = Path(tempfile.mkdtemp(prefix=f"sdkb_stage7_{label}_")) / f"claim_features_{commit}.parquet"
    blob = subprocess.run(["git", "show", f"{commit}:{FEATURES_REL}"],
                          cwd=ROOT, check=True, capture_output=True).stdout
    tmp.write_bytes(blob)
    if sha_prefix and not _sha(tmp).startswith(sha_prefix):
        raise SystemExit(f"ERROR: {commit} 의 parquet sha 가 동결값({sha_prefix}…)과 다르다")
    return tmp


def baseline_parquet(path: Path | None) -> Path:
    """단계 1 커밋의 parquet. 지정이 없으면 git 에서 꺼내고, 동결된 sha 접두와 대조한다."""
    if path is None:
        return parquet_from_git(FROZEN["baseline_commit"], FROZEN["baseline_parquet_sha256_prefix"], "A")
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
        self.bound: set[str] = set()

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
            R |= conj_reach(self, ess, q)
        return R


def conj_reach(layer: Layer, essential: frozenset[str], q: str) -> set[str]:
    """단일 필수개념 집합의 R∀ — 프로파일 하나, 또는 V4 처럼 텍스트 한 덩어리가 질의일 때."""
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


def layers_current(expand: bool, parquet: Path | None = None, name: str | None = None,
                   check_identity: bool | None = None) -> tuple[Layer, dict]:
    """A-Box 생성기의 함수로 재파생한 층. 현 parquet(기본)이면 리포트와 대조해 어긋나면 죽는다.
    `parquet` 를 주면(git 소급 층 · 추가 층) 현 T-Box 바인딩을 그 parquet 에 적용하고 대조는 건너뛴다."""
    if check_identity is None:
        check_identity = parquet is None
    core_data = Graph().parse(gen.CORE_DATA, format="turtle")
    core = Graph().parse(gen.CORE, format="turtle")
    semi = Graph().parse(gen.SEMI, format="turtle")
    bound = gen.bound_concepts(core_data, gen.technical_concept_classes(semi))
    df = gen.load_features(parquet or gen.FEATURES)
    concepts, _ = gen.claim_concepts(df, bound)
    claims = df[["claim_id", "side", "is_independent"]].drop_duplicates("claim_id")
    is_indep = dict(zip(claims["claim_id"], claims["is_independent"].astype(bool)))
    parents = {cid: list(dep) for cid, dep in
               df[["claim_id", "depends_on_claim"]].drop_duplicates("claim_id").itertuples(index=False) if len(dep)}
    roots, _ = gen.root_independents(is_indep, parents)
    profiles, p_stat = gen.build_profiles(claims, concepts, roots)
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
    rej_total = p_stat.get("independent_total__rej", 0)
    rej_unmapped = p_stat.get("independent_unmapped__rej", 0)
    identity = {
        "profiles": [len(profiles), None], "disclosures": [len(disclosures), None],
        "essential_links": [sum(len(p.essential) for p in profiles), None],
        "covered_by_pairs": [len(pairs), None], "bound_concepts": [len(bound), None],
        "rej_independent_unmapped_rate": round(rej_unmapped / rej_total, 4) if rej_total else None,
        "parquet_sha256": _sha(parquet or gen.FEATURES),
    }
    if check_identity:
        rep = json.loads(ABOX_REPORT.read_text(encoding="utf-8"))
        for k, v in (("profiles", rep["profiles"]["emitted"]), ("disclosures", rep["disclosures"]["emitted"]),
                     ("essential_links", rep["profiles"]["essential_links"]),
                     ("covered_by_pairs", rep["hierarchy"]["covered_by_total"]),
                     ("bound_concepts", rep["concepts"]["bound_in_core_data"])):
            identity[k][1] = v
        bad = {k: v for k, v in identity.items() if isinstance(v, list) and v[0] != v[1]}
        if bad:
            raise SystemExit(f"ERROR: parquet 재파생이 A-Box 리포트와 다르다 — `make abox-priorart` 후 다시: {bad}")
        identity["cited_without_disclosure_by_prefix"] = {
            k.split("__", 1)[1]: v for k, v in d_stat.items() if k.startswith("cited_without_disclosure__")}
    layer = Layer(name or ("L_C" if expand else "L_B"), dict(prof), disc, dict(expansion) if expand else None)
    layer.bound = bound                                   # V4 가 텍스트 링커 개념을 pa: 경로에 맞춰 거를 때 쓴다
    return layer, identity


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


def summarize(recs: dict[str, dict], qs=None) -> dict:
    """qs 를 주면 그 질의 부분집합만 요약한다 (CAL-3 · 계산은 그대로 두고 보고 시점에 분할한다)."""
    recs = recs if qs is None else {q: r for q, r in recs.items() if q in qs}
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


def paired_bootstrap(a: list, c: list, B: int, seed: int, ci: float, stat_fn=None) -> dict:
    """같은 질의 위 두 벡터의 통계량 차 Δ 와 퍼센타일 CI. 결정적(seed). stat_fn 기본은 평균."""
    a_, c_ = np.asarray(a, dtype=float), np.asarray(c, dtype=float)
    n = len(a_)
    if n == 0:
        return {"n": 0, "delta": None, "ci": None}
    rng = np.random.RandomState(seed)
    idx = rng.randint(0, n, size=(B, n))
    if stat_fn is None:
        deltas = c_[idx].mean(axis=1) - a_[idx].mean(axis=1)
        delta = float(c_.mean() - a_.mean())
    else:
        deltas = stat_fn(c_[idx], axis=1) - stat_fn(a_[idx], axis=1)
        delta = float(stat_fn(c_) - stat_fn(a_))
    lo, hi = np.percentile(deltas, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return {"n": n, "delta": delta, "ci": [float(lo), float(hi)], "B": B, "seed": seed}


def mcnemar_exact(a: list[int], c: list[int]) -> dict:
    b01 = sum(1 for x, y in zip(a, c) if x == 0 and y == 1)   # C 만 성공
    b10 = sum(1 for x, y in zip(a, c) if x == 1 and y == 0)   # A 만 성공
    n = b01 + b10
    if n == 0:
        return {"c_only": 0, "a_only": 0, "p": 1.0}
    k = min(b01, b10)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"c_only": b01, "a_only": b10, "p": p}


def v2_verdict(recA: dict[str, dict], recC: dict[str, dict], frozen: dict = FROZEN, qs=None) -> dict:
    S = frozen["S_primary"]
    if qs is not None:                                    # CAL-3 — 판정 범위를 질의 집합으로 좁힌다
        qs = set(qs)
        recA = {q: r for q, r in recA.items() if q in qs}
        recC = {q: r for q, r in recC.items() if q in qs}
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


def lever_verdict(recC: dict[str, dict], recD: dict[str, dict], rej_unmapped_rate: float | None,
                  frozen: dict = FROZEN, qs=None) -> dict:
    """단계 7-A′ 레버 게이트 — L_D 대 L_C (결과 전 동결 · FROZEN['stage7a'])."""
    f = frozen["stage7a"]
    if qs is not None:                                    # CAL-3
        qs = set(qs)
        recC = {q: r for q, r in recC.items() if q in qs}
        recD = {q: r for q, r in recD.items() if q in qs}
    common = sorted(set(recC) & set(recD))
    rc = [recC[q]["all"]["reach"] for q in common]
    rd = [recD[q]["all"]["reach"] for q in common]
    boot = paired_bootstrap(rc, rd, frozen["bootstrap_B"], frozen["seed"], frozen["ci"], stat_fn=np.median)
    reach_ok = bool(boot["ci"] and boot["ci"][1] < 0 and boot["delta"] < 0)
    hc = [int(recC[q]["all"]["hit"]) for q in common]
    hd = [int(recD[q]["all"]["hit"]) for q in common]
    hit_c, hit_d = (sum(hc) / len(hc)) if hc else None, (sum(hd) / len(hd)) if hd else None
    drop = (hit_c - hit_d) if (hit_c is not None and hit_d is not None) else None
    hit_ok = drop is not None and drop <= f["hit_drop_max"]
    unm_ok = rej_unmapped_rate is not None and rej_unmapped_rate <= f["rej_unmapped_max"]
    return {
        "gate": f["gate"], "common_queries": len(common),
        "rej_unmapped": {"pass": unm_ok, "rate": rej_unmapped_rate, "max": f["rej_unmapped_max"]},
        "reach_median_decrease": {"pass": reach_ok, "median_C": st.median(rc) if rc else None,
                                  "median_D": st.median(rd) if rd else None, "bootstrap": boot},
        "hit_inf_drop": {"pass": hit_ok, "hit_C": hit_c, "hit_D": hit_d, "drop": drop, "max": f["hit_drop_max"]},
        "pass": bool(unm_ok and reach_ok and hit_ok),
        "failed_conditions": [k for k, ok in (("rej_unmapped", unm_ok), ("reach_median", reach_ok),
                                              ("hit_drop", hit_ok)) if not ok],
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


def _rows_in(rows: list[dict], qs) -> list[dict]:
    return rows if qs is None else [r for r in rows if r["q"] in qs]


def _legacy_substring_gate(rowsC: list[dict], frozen: dict = FROZEN, qs=None) -> dict:
    """교정 전(§20 E-1) 게이트를 **같은 실행에서** 재현한다 — 판정이 아니라 증거다.

    `"§29②" in stratum` 은 혼합 라벨을 떨어뜨렸다. 과거 커밋을 꺼내지 않고 여기서 다시 계산해
    리포트가 스스로 자기 교정을 증명하게 한다. 이 값은 어떤 PASS/FAIL 에도 들어가지 않는다.
    """
    rowsC = _rows_in(rowsC, qs)
    gate = [r for r in rowsC if r["n_cited"] >= 2 and "§29②" in r["stratum"]]
    d = [r["delta"] for r in gate]
    boot = paired_bootstrap([0.0] * len(d), d, frozen["bootstrap_B"], frozen["seed"], frozen["ci"])
    matched = sorted({r["stratum"] for r in gate})
    dropped = sorted(x for x in INVENTIVE_STRATA if x not in matched)
    return {"definition": '`"§29②" in stratum` (부분문자열)',
            "gate_queries": len(gate), "delta_mean": boot["delta"], "bootstrap": boot,
            "pass": bool(boot["ci"] and boot["ci"][0] > 0 and boot["delta"] > 0),
            "strata_matched": matched, "strata_dropped_by_bug": dropped,
            "note": "판정 아님 (§20 E-1 · CAL-1). 동결 정의는 gate_strata 쪽이다."}


def v3_verdict(rowsB: list[dict], rowsC: list[dict], frozen: dict = FROZEN, qs=None) -> dict:
    if qs is not None:                                    # CAL-3
        qs = set(qs)
        rowsB, rowsC = _rows_in(rowsB, qs), _rows_in(rowsC, qs)
    gate = [r for r in rowsC if r["n_cited"] >= 2 and r["stratum"] in INVENTIVE_STRATA]
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
    return {"gate_stratum": frozen["v3_gate_stratum"], "gate_strata": sorted(INVENTIVE_STRATA),
            "gate_queries": len(gate),
            "delta_mean_C": boot["delta"], "bootstrap": boot, "pass": ok,
            "legacy_substring_gate": _legacy_substring_gate(rowsC, frozen),   # 이미 qs 로 좁혀진 rowsC
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
def run(baseline: Path | None, extra_layers: list[tuple[str, Path]] | None = None, log=print) -> dict:
    gt, lb = load_gt()
    bp = baseline_parquet(baseline)
    log("· L_A (단계 1 parquet) 적재")
    LA = layer_stage1(bp)
    f7a = FROZEN["stage7a"]
    current_sha = _sha(ROOT / FEATURES_REL)
    mode = "stage7" if current_sha.startswith(f7a["c_parquet_sha256_prefix"]) else "stage7a"
    layers: dict[str, Layer] = {"L_A": LA}
    idents: dict[str, dict] = {}
    if mode == "stage7":
        log("· L_B / L_C (현 parquet · 생성기 재파생) 적재")
        layers["L_B"], identity = layers_current(expand=False)
        layers["L_C"], _ = layers_current(expand=True)
        idents["L_C"] = identity
        gate_layer, prev_layer = "L_C", "L_B"
    else:
        log(f"· L_C (커밋 {f7a['c_commit']} parquet 소급 · 확장 on) 적재")
        cp = parquet_from_git(f7a["c_commit"], f7a["c_parquet_sha256_prefix"], "C")
        layers["L_C"], idents["L_C"] = layers_current(expand=True, parquet=cp, name="L_C")
        for name, path in (extra_layers or []):
            log(f"· {name} ({path}) 적재")
            layers[name], idents[name] = layers_current(expand=True, parquet=path, name=name)
        log("· L_D (현 parquet · 생성기 재파생 · 확장 on) 적재")
        layers["L_D"], identity = layers_current(expand=True, name="L_D")
        idents["L_D"] = identity
        gate_layer, prev_layer = "L_D", "L_C"

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

    # CAL-3 — 계산(per_query·v3_rows)은 전량 1회로 끝났다. 판정만 분할별로 부른다.
    split_map = splits.load_split()
    ledger_n = len(seal.ledger_rows())
    scope_qs = {sc: (None if sc == "all" else splits.queries_in(sc, split_map=split_map))
                for sc in REPORT_SCOPES}

    def _verdict(scope: str) -> dict:
        assert_scope_allowed(scope, ledger_rows=ledger_n)
        qs = scope_qs[scope]
        v4p = v4_report_path(scope)
        v4doc = json.loads(v4p.read_text(encoding="utf-8")) if v4p.exists() else None
        out = {
            "scope": scope,
            "queries": {k: (len(r) if qs is None else sum(1 for q in r if q in qs)) for k, r in recs.items()},
            "v4_source": str(v4p.relative_to(ROOT)) if v4p.exists() else None,
            "V2": v2_verdict(recs["L_A"], recs[gate_layer], qs=qs),
            "V3": v3_verdict(rows[prev_layer], rows[gate_layer], qs=qs),
            "V4": v4_verdict(v4doc),
        }
        if mode == "stage7a":
            out["lever"] = lever_verdict(recs["L_C"], recs["L_D"],
                                         identity.get("rej_independent_unmapped_rate"), qs=qs)
            # 추가 층(예: L_D0 원소기호 규칙만)은 L_C 대비 서술로만 남긴다
            out["lever"]["extra_layers_vs_L_C"] = {
                name: lever_verdict(recs["L_C"], recs[name],
                                    idents[name].get("rej_independent_unmapped_rate"), qs=qs)
                for name, _ in (extra_layers or [])}
        return out

    verdict = _verdict(PRIMARY_SPLIT)                      # 주 판정
    verdict_legacy_all = {**_verdict("all"), "note": LEGACY_SCOPE_NOTE}
    verdict_train = {**_verdict("train"), "note": TRAIN_SCOPE_NOTE}
    log(f"· 판정 범위 dev n={verdict['queries'][gate_layer]} (주) · train n={verdict_train['queries'][gate_layer]} · "
        f"전량 n={verdict_legacy_all['queries'][gate_layer]} · 봉인 원장 {ledger_n}행")
    S = FROZEN["S_primary"]
    sums = {k: summarize(r) for k, r in recs.items()}
    names = list(layers)
    attribution = {"measure": f"SPR∀@{S}", "steps": {}}
    for prev, cur in zip(names, names[1:]):
        attribution["steps"][f"{cur}−{prev}"] = sums[cur]["all"][f"SPR@{S}"] - sums[prev]["all"][f"SPR@{S}"]
    attribution[f"total_{gate_layer}−L_A"] = sums[gate_layer]["all"][f"SPR@{S}"] - sums["L_A"]["all"][f"SPR@{S}"]
    return {
        "plan": "PLAN-005 단계 7 · V2–V4 재측정 · 동결 목표 대조" + (" · 7-A′ 레버 판정" if mode == "stage7a" else ""),
        "generator": "scripts/report_stage7_remeasure.py",
        "generated": str(date.today()),
        "read_only": True,
        "mode": mode,
        # ── CAL-3 선언 (§20.7 · check_leakage K-4·K-5 가 읽는다) ──────────────
        "instrument_version": INSTRUMENT_VERSION,
        "split": PRIMARY_SPLIT,
        "split_sha256": splits.sha256_of(splits.SPLIT_CSV),
        "seal_ledger_rows": ledger_n,
        "split_composition": {k: splits.split_composition(r, split_map=split_map) for k, r in recs.items()},
        "frozen": FROZEN,
        "inputs": {
            "baseline_parquet_sha256": _sha(bp), FEATURES_REL: current_sha,
            "ontology/sdkb-priorart-core.ttl": _sha(gen.CORE), "ontology/sdkb-core-data.ttl": _sha(gen.CORE_DATA),
            "ontology/sdkb-priorart-semi.ttl": _sha(gen.SEMI), "data/patents/prior_art_edges.parquet": _sha(EDGES),
            "data/reports/abox_priorart_report.json": _sha(ABOX_REPORT),
            "data/reports/v4_robustness.json": _sha(V4_REPORT) if V4_REPORT.exists() else None,
            **{f"data/reports/{v4_report_path(sc).name}": _sha(v4_report_path(sc))
               for sc in REPORT_SCOPES if sc != "all" and v4_report_path(sc).exists()},
            "benchmark/assets/split.csv": splits.sha256_of(splits.SPLIT_CSV),
            **{f"layer_parquet_sha256[{k}]": v["parquet_sha256"] for k, v in idents.items()},
        },
        "identity_check_vs_abox_report": identity,
        "layer_identity": {k: {kk: vv for kk, vv in v.items() if kk != "cited_without_disclosure_by_prefix"}
                           for k, v in idents.items()},
        "stage1_reproduction": repro,
        "descriptive": {
            "Q": {k: s["queries"] for k, s in sums.items()},
            "Q_A_and_Q_C": len(set(recs["L_A"]) & set(recs["L_C"])),
            "Q_C_strata": dict(Counter(stratum_of(q, gt, lb) for q in recs[gate_layer])),
            "gt_targets_total": len(gt),
        },
        "ladder": {k: {"reach": sums[k], "coverage": v3_summary(rows[k])} for k in layers},
        "attribution": attribution,
        "verdict": verdict,
        "verdict_legacy_all": verdict_legacy_all,
        "verdict_train": verdict_train,
        "limitations": [
            "SPR 은 순위 없는 후보집합이 S 이하여야 하는 지표이고 τ 의 원천 tfidf R@50 은 순위 지표다 — "
            "비대칭은 τ 를 유리하게 하지 않는다 (계획 파일 · 결과 전 명시).",
            "Disclosure 는 KR/US 분해 문헌에만 있다 — 인용문헌 중 JP 등 비 KR/US 는 목표에서 빠진다 (§4 결손 · 수는 identity_check 에).",
            "§29①-only 층은 질의가 적어 P1 은 저검정력이다 — 결론을 얹지 않는다.",
            "V4-2(사람 코딩)는 재실행하지 않고 인용한다.",
            f"주 판정은 {PRIMARY_SPLIT} 분할이다 (CAL-3 · §20.2 E-3). 분모가 작아져 검정력이 낮다 — "
            "전량 값은 verdict_legacy_all 에 병기하되 홀드아웃이 아니다(D13).",
            "봉인 분할(test·test_b)의 지표는 이 리포트에 없다 — 코드가 막는다(D17 · assert_scope_allowed).",
        ],
    }


def _f(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else f"{x:,}")


def render_markdown(rep: dict) -> str:
    v = rep["verdict"]
    S = rep["frozen"]["S_primary"]
    gate_layer = "L_D" if rep.get("mode") == "stage7a" else "L_C"
    L = ["# PLAN-005 단계 7 — V2–V4 재측정 · 동결 목표 대조 (기계 산출)", "",
         f"> 생성: `scripts/report_stage7_remeasure.py` · {rep['generated']} · 모드 {rep.get('mode')} · **손으로 고치지 않는다** — "
         "`make stage7-remeasure` 가 다시 만든다. 정의·문턱은 스크립트 `FROZEN`(결과 전 동결).", "",
         ""]
    va, vt = rep.get("verdict_legacy_all", {}), rep.get("verdict_train", {})
    L += ["## 판정 범위 (CAL-3 · §20.2 E-3)", "",
          f"> **주 판정은 `{rep.get('split')}` 분할이다.** 개념 사전이 dev+train 통지서에서 채굴됐으므로 "
          "train 은 **상한이지 성능이 아니고**, test·test_b 는 **봉인**이다 — 숫자를 찍지 않는다(D17). "
          f"분할표 sha256 `{str(rep.get('split_sha256', ''))[:12]}…` · 봉인 원장 **{rep.get('seal_ledger_rows')}행** · "
          f"계측기 `{rep.get('instrument_version')}`.", "",
          "| 분할 | 게이트 층 질의 | 지위 |", "|---|---:|---|",
          f"| **{rep.get('split')}** | {v['queries'][gate_layer]} | **주 판정** |",
          f"| train | {vt.get('queries', {}).get(gate_layer, '—')} | 참고 — 개념 사전이 여기서 채굴됐다(상한) |",
          "| test · test_b | **—** | **봉인** |",
          f"| 전량 | {va.get('queries', {}).get(gate_layer, '—')} | 개발 지표(교정 전 범위) · 병기 |", "",
          "## 판정", "", "| 검증 | 판정 | 걸린 조건 |", "|---|:-:|---|"]
    if "lever" in v:
        lv = v["lever"]
        L.append(f"| 7-A′ 레버 (L_D 대 L_C) | **{'PASS' if lv['pass'] else 'FAIL'}** | {', '.join(lv['failed_conditions']) or '—'} |")
    L += [f"| V2 도달 ({gate_layer} 대 L_A) | **{'PASS' if v['V2']['pass'] else 'FAIL'}** | {', '.join(v['V2']['failed_conditions']) or '—'} |",
          f"| V3 업무 목적(진보성) | **{'PASS' if v['V3']['pass'] else 'FAIL'}** | 게이트 층 q={v['V3']['gate_queries']} · Δ평균 {_f(v['V3']['delta_mean_C'])} · CI {v['V3']['bootstrap']['ci']} |",
          f"| V4 질의 비종속성 | **{('PASS' if v['V4']['pass'] else 'FAIL') if v['V4'].get('pass') is not None else v['V4']['status']}** | — |",
          "", "**범위 병기**(판정 아님 · D13):", ""]
    for lab, blk in (("전량 · 교정 전 범위", va), ("train · 상한", vt)):
        if not blk:
            continue
        L.append(f"- {lab}: V2 {'PASS' if blk['V2']['pass'] else 'FAIL'}"
                 f"({', '.join(blk['V2']['failed_conditions']) or '조건 전부 충족'}) · "
                 f"V3 {'PASS' if blk['V3']['pass'] else 'FAIL'}(q={blk['V3']['gate_queries']} · "
                 f"Δ {_f(blk['V3']['delta_mean_C'])} · CI {[round(x, 4) for x in blk['V3']['bootstrap']['ci']] if blk['V3']['bootstrap']['ci'] else '—'})"
                 + (f" · 레버 {'PASS' if blk['lever']['pass'] else 'FAIL'}" if 'lever' in blk else ""))
    L += [f"- 각 범위의 근거: `verdict`(주) · `verdict_legacy_all` · `verdict_train` (JSON)", ""]
    if "lever" in v:
        lv = v["lever"]
        u, r, h = lv["rej_unmapped"], lv["reach_median_decrease"], lv["hit_inf_drop"]
        L += ["### 7-A′ 레버 게이트 (결과 전 동결)", "", "| 조건 | 값 | 판정 |", "|---|---|:-:|",
              f"| rej 독립항 미매핑 ≤ {u['max']} | {_f(u['rate'])} | {'✓' if u['pass'] else '✗'} |",
              f"| median\\|R∀\\| 감소 CI 가 0 배제 · Q={lv['common_queries']} | {_f(r['median_C'])} → {_f(r['median_D'])} · Δ {_f(r['bootstrap']['delta'])} · CI {r['bootstrap']['ci']} | {'✓' if r['pass'] else '✗'} |",
              f"| 적중(∞) 저하 ≤ {h['max']} | {_f(h['hit_C'])} → {_f(h['hit_D'])} · 저하 {_f(h['drop'])} | {'✓' if h['pass'] else '✗'} |", ""]
        for name, x in lv.get("extra_layers_vs_L_C", {}).items():
            r2, h2, u2 = x["reach_median_decrease"], x["hit_inf_drop"], x["rej_unmapped"]
            L.append(f"추가 층 {name} 대 L_C(서술): 미매핑 {_f(u2['rate'])} · median|R∀| {_f(r2['median_C'])} → {_f(r2['median_D'])} · 적중(∞) {_f(h2['hit_C'])} → {_f(h2['hit_D'])}")
        L.append("")
    i, ii, iii = v["V2"]["i_significant_rise"], v["V2"]["ii_tau"], v["V2"]["iii_specificity"]
    L += ["### V2 세 조건", "", "| 조건 | 값 | 판정 |", "|---|---|:-:|",
          f"| (i) 유의 상승 · Q_A∩Q={i['common_queries']} | SPR∀@{S} A {_f(i['SPR_all@50_A'])} → {gate_layer} {_f(i['SPR_all@50_C'])} · Δ {_f(i['bootstrap']['delta'])} · 95% CI {i['bootstrap']['ci']} · McNemar p {_f(i['mcnemar']['p'])} | {'✓' if i['pass'] else '✗'} |",
          f"| (ii) τ={ii['tau']} · Q_KR={ii['queries_kr']} | SPR∀@{S}(KR) {_f(ii['SPR_all@50_KR_C'])} | {'✓' if ii['pass'] else '✗'} |",
          f"| (iii) 특이도 | median\\|R∀\\| A {_f(iii['reach_all_median_A'])} → {gate_layer} {_f(iii['reach_all_median_C'])} | {'✓' if iii['pass'] else '✗'} |", ""]
    L += ["## 사다리", "", "| 층 | Q | R | SPR@50 | SPR@100 | SPR@1000 | 적중(∞) | median\\|R\\| | SPR@50 KR | SPR@50 US |",
          "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, d in rep["ladder"].items():
        r = d["reach"]
        for fam, lab in (("exist", "R∃"), ("all", "R∀")):
            s = r[fam]
            L.append(f"| {k} | {r['queries']} | {lab} | {_f(s['SPR@50'])} | {_f(s['SPR@100'])} | {_f(s['SPR@1000'])} | "
                     f"{_f(s['hit_rate_any_S'])} | {_f(s['reach_median'])} | {_f(s['SPR@50_KR'])} | {_f(s['SPR@50_US'])} |")
    a = rep["attribution"]
    L += ["", f"귀속({a['measure']}): " + " · ".join(f"{k} {_f(val)}" for k, val in a["steps"].items()) +
          " · " + " · ".join(f"{k} {_f(val)}" for k, val in a.items() if k.startswith("total_")), ""]
    L += [f"## V3 커버 (층별 · {gate_layer})", "", "| 층 | q | 2문헌+ | best_single 중앙 | Δ 평균 | Δ>0 비율 |", "|---|---:|---:|---:|---:|---:|"]
    for s, d in rep["ladder"][gate_layer]["coverage"].get("by_stratum", {}).items():
        L.append(f"| {s} | {d['queries']} | {d['pair_queries']} | {_f(d['best_single_median'])} | {_f(d['delta_mean'])} | {_f(d['delta_gt0_frac'])} |")
    p1, p2 = v["V3"]["P1"], v["V3"]["P2"]
    lg = v["V3"].get("legacy_substring_gate")
    if lg:
        L += ["", f"게이트 정의 교정(CAL-1 · §20 E-1): 교정 전 {lg['definition']} 은 층 {lg['strata_matched']} 만 잡아 "
              f"q={lg['gate_queries']} · Δ평균 {_f(lg['delta_mean'])} · CI {lg['bootstrap']['ci']} · "
              f"{'PASS' if lg['pass'] else 'FAIL'} 였다 (층 {lg['strata_dropped_by_bug']} 을 떨어뜨림 · **판정 아님**). "
              f"동결 정의 {v['V3']['gate_strata']} 로 실행한 현 게이트는 q={v['V3']['gate_queries']} · "
              f"Δ평균 {_f(v['V3']['delta_mean_C'])} 이다."]
    L += ["", f"사전 등록 P1(게이트 아님): §29②-only {_f(p1['frac_29_2_only'])}(n={p1['n_29_2_only']}) 대 §29①-only "
          f"{_f(p1['frac_29_1_only'])}(n={p1['n_29_1_only']}) · 성립 {p1['holds']} · 저검정력 {p1['underpowered']}",
          f"사전 등록 P2: best_single 중앙 이전 층 {_f(p2['best_single_median_B'])} → {gate_layer} {_f(p2['best_single_median_C'])} · 성립 {p2['holds']}", ""]
    rp = rep["stage1_reproduction"]
    L += ["## 계측기 검사 — 단계 1 재현 (L_A · R∃)", "", f"재현 {'OK' if rp['ok'] else '**실패**'}: " +
          " · ".join(f"{k} {a}→{b}" for k, (a, b) in rp["V2"].items()), ""]
    L += ["## 한계", ""] + [f"- {x}" for x in rep["limitations"]]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-parquet", type=Path, default=None)
    ap.add_argument("--layer", action="append", default=[],
                    help="추가 층 NAME=PARQUET (확장 on · L_C 와 L_D 사이에 놓인다 · 7-A′ 모드)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--markdown", type=Path, default=None)
    a = ap.parse_args()
    extras = []
    for spec in a.layer:
        name, _, path = spec.partition("=")
        if not name or not path:
            raise SystemExit(f"--layer 는 NAME=PATH 형식이다: {spec}")
        extras.append((name, Path(path)))
    rep = run(a.baseline_parquet, extras)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.markdown:
        a.markdown.write_text(render_markdown(rep), encoding="utf-8")
    v = rep["verdict"]
    if "lever" in v:
        print(f"7-A′ 레버 {'PASS' if v['lever']['pass'] else 'FAIL ' + str(v['lever']['failed_conditions'])}")
    print(f"V2 {'PASS' if v['V2']['pass'] else 'FAIL ' + str(v['V2']['failed_conditions'])} · "
          f"V3 {'PASS' if v['V3']['pass'] else 'FAIL'} · V4 {v['V4'].get('pass')} ({v['V4']['status']})")
    print(f"단계 1 재현 {'OK' if rep['stage1_reproduction']['ok'] else 'FAIL'} · "
          f"Q {rep['descriptive']['Q']} · 귀속 {rep['attribution']}")
    print(f"→ {a.out}" + (f" · {a.markdown}" if a.markdown else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
