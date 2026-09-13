#!/usr/bin/env python3
"""PLAN-005 R0-CAL-2 — V7 CoverageRank 순위 계측과 τ 대칭 사다리 (읽기 전용 · **판정 없음**).

왜 이 계측기가 필요한가 (§20.2 E-2).
V2 (ii) 는 SPR∀@50(KR) 을 τ = 0.6708(tfidf KR R@50)에 댄다. 그런데 둘은 네 곳에서 다르게 잰다 —
(a) 순위 없는 집합 크기 ≤ 50 대 순위 ≤ 50 · (b) 분모가 질의 대 인용 건 · (c) 후보 풀
(Disclosure 36,880 대 코퍼스 2,926 · 2026-09-13 실측 — 계획서는 인용문헌만 셌다) · GT 의 `~is_npl`.
그래서 dev 0.02 대 0.67 이 자원의 한계인지 지표 불일치인지 **말할 수 없었고**, 그 방어는 산문 한 줄이었다.
이 스크립트는 τ 를 원 조건에서 먼저 재현하고(못 하면 죽는다) **한 번에 조건 하나씩** 바꾼 사다리를
세워 각 비대칭의 몫을 값으로 낸다.

정의는 FROZEN_V7 에 결과 전에 동결했고 **문턱은 없다**(사용자 결정 2026-09-13 · 서술 전용).
V2 정의·τ·판정은 `report_stage7_remeasure.py` 가 그대로 갖는다 — 여기서는 읽기만 한다.
점수·순위 코드는 복제하지 않는다: tfidf 는 `eval_prior_art_realgt`, 층·Reach 는 `report_stage7_remeasure`.

CLI:
    python scripts/report_v7_coverage_rank.py --markdown PATH
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import eval_prior_art_realgt as rg  # noqa: E402
from scripts import report_stage7_remeasure as s7  # noqa: E402
from scripts import seal, splits  # noqa: E402

OUT = ROOT / "data" / "reports" / "v7_coverage_rank.json"
REALGT = rg.OUT

INSTRUMENT_VERSION = "R0-CAL-2"
PRIMARY_SPLIT = "dev"
SCOPES = ("dev", "train", "all")
BUCKETS = ("KR", "FOREIGN")

#: 결과를 보기 전에 동결한 **정의** (§20.7 CAL-2 · 사용자 승인 2026-09-13). 값·문턱은 없다.
FROZEN_V7 = {
    "k": 50,
    "layer": "L_D (현 parquet · 생성기 재파생 · coveredBy 확장 on) — report_stage7_remeasure.layers_current",
    "score": "score(q,d) = max_p |ess(p) ∩ Disc*(d)| / |ess(p)| · 동률 argmax 는 (score, |∩|) 사전식 최대 · d ≠ q",
    "identity": "{d : score = 1} == R∀(q) — 어긋나면 계측기 오류(결과가 아니다)",
    "order_key": ["score 내림", "|∩| 내림", "|Disc*(d)| 오름 (특이도)", "id 사전순"],
    "unranked": "score = 0 은 순위가 없다 = 미회수 (tfidf 도 0 점 문헌은 순위가 없다 — 대칭)",
    "tfidf_order": "eval_prior_art_realgt.tfidf_rank 그대로 — (sim, doc_idx) 내림",
    "tfidf_pool_restriction": "idf 는 전체 코퍼스로 고정 · 풀 안에서 상대 순서만 다시 매긴다",
    "gt": "source_type = examiner ∧ ~is_npl ∧ cited ∈ 풀 (eval_prior_art_realgt.load_examiner_gt)",
    "bucket": "코퍼스 country = KR 이면 KR, 아니면 FOREIGN (realgt 와 같다)",
    "micro": "Σ 적중 / Σ 정답 쌍 — τ 대조는 이것만 (§20.7 (b))",
    "macro": "질의별 (적중 쌍 / 쌍) 의 평균 — 병기",
    "pools": {
        "P_corpus": "fulltext_corpus has_content (tfidf 원 조건)",
        "P_disc": "L_D Disclosure 보유 문헌 (배경 g1·g2 포함)",
        "P_common": "코퍼스 ∩ Disclosure — **주**",
    },
    "U_common": "정답 쌍 중 cited 가 P_common 에 있는 것",
    "tie_band": ("m = 경계 키보다 엄격히 앞선 수 · g = 같은 동점 키 그룹 크기 · "
                 "m+g ≤ k → 1 · m ≥ k → 0 · 그 사이 → 기대 (k−m)/g · 최선 1 · 최악 0. "
                 "동점 키: CoverageRank 는 순위 키 앞 셋 · tfidf 는 sim"),
    "tie_band_caveat": "최선·최악은 쌍별 한계다 — 모든 쌍이 동시에 최선/최악일 수는 없다",
    "ladder": ["0 원 조건", "1 질의 → 페어드 Q", "2 GT → U_common", "3 풀 → P_common", "4 범위 → dev(주)·train·all"],
    "verdict": None,
    "verdict_note": "판정 아님 — 사전등록된 문턱이 없다. 이 수로 PASS/FAIL 을 말하지 않는다",
}


# ── 순수 함수 ─────────────────────────────────────────────────────────────
def coverage_scores(layer, q: str, pool=None) -> dict[str, tuple[float, int]]:
    """{d: (score, |∩|)} — 프로파일별 cov 의 (score, |∩|) 사전식 최대. score > 0 인 문헌만.

    E(q) 합집합 cov(`v3_rows`)가 아니라 프로파일 단위여야 `score = 1 ⟺ d ∈ R∀(q)` 가 성립한다
    (2026-09-13 dev 186 질의 불일치 0). 같은 식을 프로파일마다 적용한 것이지 새 점수가 아니다.
    """
    scores: dict[str, tuple[float, int]] = {}
    for ess in layer.profiles.get(q, ()):
        if not ess:
            continue
        n = len(ess)
        cnt = Counter(d for c in ess for d in layer.inv.get(c, ()))
        for d, k in cnt.items():
            if d == q or (pool is not None and d not in pool):
                continue
            s = (k / n, k)
            if s > scores.get(d, (0.0, 0)):
                scores[d] = s
    return scores


def coverage_sort_key(layer):
    return lambda d, s: (-s[0], -s[1], len(layer.disc_star[d]), d)


def coverage_tie_key(layer):
    return lambda d, s: (s[0], s[1], len(layer.disc_star[d]))


def tfidf_sort_key(di: int, sim: float):
    return (-sim, -di)                     # tfidf_rank 의 (sim, di) 내림과 같다


def tfidf_tie_key(di: int, sim: float):
    return sim


def rank_with_ties(cands: dict, sort_key, tie_key) -> dict:
    """후보 {doc: score} → {doc: (pos, group_start, group_size)} (0 기반).

    tie_key 는 sort_key 의 앞부분이어야 한다 — 그래야 동점 그룹이 정렬에서 연속한다.
    """
    order = sorted(cands.items(), key=lambda it: sort_key(*it))
    out, i, n = {}, 0, len(order)
    while i < n:
        t = tie_key(*order[i])
        j = i + 1
        while j < n and tie_key(*order[j]) == t:
            j += 1
        for p in range(i, j):
            out[order[p][0]] = (p, i, j - i)
        i = j
    return out


def tie_band(placed, k: int) -> dict:
    """한 정답 쌍의 적중과 동점 띠. placed = (pos, group_start, group_size) 또는 None(미순위)."""
    if placed is None:
        return {"hit": 0, "exp": 0.0, "best": 0, "worst": 0}
    pos, g0, gn = placed
    hit = int(pos < k)
    if g0 + gn <= k:
        return {"hit": hit, "exp": 1.0, "best": 1, "worst": 1}
    if g0 >= k:
        return {"hit": hit, "exp": 0.0, "best": 0, "worst": 0}
    return {"hit": hit, "exp": (k - g0) / gn, "best": 1, "worst": 0}


def aggregate(pairs: list[dict]) -> dict:
    """정답 쌍 목록 → micro(버킷·전체) · macro(KR·전체). 필드 hit=주 값 · exp/best/worst=동점 띠."""
    micro = {}
    for b in BUCKETS + ("ALL",):
        ps = [p for p in pairs if b == "ALL" or p["bucket"] == b]
        n = len(ps)
        micro[b] = {"pairs": n, "queries": len({p["q"] for p in ps}),
                    **{f: (sum(p[f] for p in ps) / n if n else None) for f in ("hit", "exp", "best", "worst")}}
    macro = {}
    for b in ("KR", "ALL"):
        byq: dict[str, list[dict]] = defaultdict(list)
        for p in pairs:
            if b == "ALL" or p["bucket"] == b:
                byq[p["q"]].append(p)
        macro[b] = {"queries": len(byq),
                    **{f: (st.fmean(sum(x[f] for x in v) / len(v) for v in byq.values()) if byq else None)
                       for f in ("hit", "exp")}}
    return {"micro": micro, "macro": macro}


def assert_identity(layer, queries, score_fn=coverage_scores) -> dict:
    """모든 질의에서 {d : score = 1} == R∀(q). 어긋나면 죽는다 — V7 이 V2 의 일반화라는 증명이다."""
    bad = 0
    for q in sorted(queries):
        ones = {d for d, s in score_fn(layer, q).items() if s[0] == 1.0}
        if ones != layer.reach_all(q):
            bad += 1
    if bad:
        raise SystemExit(f"ERROR: score=1 집합이 R∀ 와 다른 질의 {bad}건 — 계측기 오류다(결과가 아니다)")
    return {"queries_checked": len(queries), "mismatch": 0}


def corpus_crosswalk(edges: pd.DataFrame, doc_ids) -> dict[str, str]:
    """코퍼스 doc_id → A-Box 식별자. `patent:` 형식만 쓴다.

    비심사관 간선은 cited_id 자리에 doc_id(`KR-P-…`)를 그대로 적어 간선 전체로는 1:1 이 아니다
    (2026-09-13 실측). 코퍼스 문서마다 `patent:` 형식은 정확히 하나여야 하고, 아니면 죽는다.
    """
    e = edges[edges["cited_id"].str.startswith("patent:")]
    forms: dict[str, set[str]] = defaultdict(set)
    for d, c in zip(e["cited_doc_id"], e["cited_id"]):
        forms[d].add(c[len("patent:"):])
    bad = [d for d in doc_ids if len(forms.get(d, ())) != 1]
    if bad:
        raise SystemExit(f"ERROR: 코퍼스 문서 {len(bad)}건의 patent: 형식이 1개가 아니다 — 크로스워크가 흔들린다")
    return {d: next(iter(forms[d])) for d in doc_ids}


# ── 실행 ──────────────────────────────────────────────────────────────────
def run(log=print) -> dict:
    k = FROZEN_V7["k"]
    log("· L_D 층 적재 (생성기 재파생 · A-Box 리포트 대조)")
    L, identity = s7.layers_current(expand=True, name="L_D")
    meta = pd.read_parquet(rg.META)
    edges = pd.read_parquet(rg.EDGES)
    corp = pd.read_parquet(rg.CORPUS)
    corp = corp[corp["has_content"]].reset_index(drop=True)
    cid = corp["doc_id"].tolist()
    cidx = {d: i for i, d in enumerate(cid)}
    country = corp["country"].tolist()
    corp_text = [f"{t} {a}" for t, a in zip(corp["title"], corp["abstract"])]

    gt = rg.load_examiner_gt(edges, cidx)
    by_pid = meta.set_index("patent_id")
    targets = [t for t in gt if t in by_pid.index]
    xw = corpus_crosswalk(edges, cid)
    P_disc = set(L.disc_star)
    common_idx = {i for i, d in enumerate(cid) if xw[d] in P_disc}
    common_pid = {xw[cid[i]] for i in common_idx}

    def qpid(t: str) -> str:
        return t.replace("patent:", "", 1)

    Q = [t for t in targets if L.profiles.get(qpid(t))]
    Qset, Qpids = set(Q), {qpid(t) for t in Q}
    log(f"· 계측기 검사 — score=1 ⟺ R∀ ({len(Qpids)} 질의)")
    ident = assert_identity(L, Qpids)

    log("· tfidf 색인 · 질의별 순위(두 풀) · CoverageRank(두 풀)")
    inv, idf, norms = rg.tfidf_index(corp_text)
    cv_sort, cv_tie = coverage_sort_key(L), coverage_tie_key(L)
    bands: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for n, tp in enumerate(targets, 1):
        row = by_pid.loc[tp]
        qtext = f"{row.get('title') or ''} {row.get('abstract') or ''} {row.get('claim1') or ''}"
        self_idx = cidx.get(tp.replace("patent:kr_", "KR-P-"))
        sims = rg.tfidf_scores(qtext, inv, idf, norms)
        full = rank_with_ties(sims, tfidf_sort_key, tfidf_tie_key)
        in_q = tp in Qset
        if in_q:
            comm = rank_with_ties({di: s for di, s in sims.items() if di in common_idx}, tfidf_sort_key, tfidf_tie_key)
            cov = coverage_scores(L, qpid(tp))
            cov_disc = rank_with_ties(cov, cv_sort, cv_tie)
            cov_comm = rank_with_ties({d: s for d, s in cov.items() if d in common_pid}, cv_sort, cv_tie)
        for c in gt[tp]:
            di = cidx[c]
            if di == self_idx:
                continue
            rec = {"q": qpid(tp), "bucket": "KR" if country[di] == "KR" else "FOREIGN", "common": di in common_idx}
            bands[("tfidf", "corpus")].append({**rec, **tie_band(full.get(di), k)})
            if in_q and rec["common"]:
                bands[("tfidf", "common")].append({**rec, **tie_band(comm.get(di), k)})
                bands[("cov", "disc")].append({**rec, **tie_band(cov_disc.get(xw[c]), k)})
                bands[("cov", "common")].append({**rec, **tie_band(cov_comm.get(xw[c]), k)})
        if n % 200 == 0:
            log(f"  …{n}/{len(targets)}")

    def sel(key, qs=None, *, in_q=False, common=False):
        return [p for p in bands[key] if (qs is None or p["q"] in qs)
                and (not in_q or p["q"] in Qpids) and (not common or p["common"])]

    ladder = [
        {"rung": 0, "change": "원 조건 — realgt 질의 · 코퍼스 풀 · 코퍼스 GT · 전량",
         "tfidf": aggregate(sel(("tfidf", "corpus"))), "coverage_rank": None, "coverage_rank_pool": None},
        {"rung": 1, "change": "질의 → 페어드 Q (L_D 프로파일 보유 ∩ realgt)",
         "tfidf": aggregate(sel(("tfidf", "corpus"), in_q=True)), "coverage_rank": None, "coverage_rank_pool": None},
        {"rung": 2, "change": "GT → U_common (cited ∈ 코퍼스 ∩ Disclosure)",
         "tfidf": aggregate(sel(("tfidf", "corpus"), in_q=True, common=True)),
         "coverage_rank": aggregate(bands[("cov", "disc")]), "coverage_rank_pool": "P_disc"},
        {"rung": 3, "change": "풀 → P_common (둘 다)",
         "tfidf": aggregate(bands[("tfidf", "common")]),
         "coverage_rank": aggregate(bands[("cov", "common")]), "coverage_rank_pool": "P_common"},
    ]

    # 계측기 검사 — 원 조건이 τ 와 커밋된 realgt 를 재현하지 못하면 사다리 전체가 무의미하다
    r0 = ladder[0]["tfidf"]["micro"]
    committed = json.loads(REALGT.read_text(encoding="utf-8"))["incremental_recall_sec5_2"]
    tau_repro = {
        "tau_frozen": s7.FROZEN["tau"], "tau_reproduced": round(r0["KR"]["hit"], 4),
        "FOREIGN_reproduced": round(r0["FOREIGN"]["hit"], 4),
        "pairs": {b: r0[b]["pairs"] for b in BUCKETS},
        "committed_realgt": {"Recall@50_tfidf": committed["Recall@50_tfidf"],
                             "gt_positives_in_corpus": committed["gt_positives_in_corpus"]},
    }
    if (tau_repro["tau_reproduced"] != s7.FROZEN["tau"]
            or tau_repro["FOREIGN_reproduced"] != committed["Recall@50_tfidf"]["FOREIGN"]
            or tau_repro["pairs"] != committed["gt_positives_in_corpus"]):
        raise SystemExit(f"ERROR: 원 조건 tfidf 가 τ·커밋된 realgt 를 재현하지 못한다 — 계측기 오류: {tau_repro}")
    log(f"· τ 재현 OK ({tau_repro['tau_reproduced']} · 쌍 {tau_repro['pairs']})")

    split_map = splits.load_split()
    ledger_n = len(seal.ledger_rows())
    scope_qs = {}
    for sc in SCOPES:
        s7.assert_scope_allowed(sc, ledger_rows=ledger_n)
        scope_qs[sc] = None if sc == "all" else splits.queries_in(sc, split_map=split_map)
    by_scope = {sc: {"tfidf": aggregate(sel(("tfidf", "common"), qs)),
                     "coverage_rank": aggregate(sel(("cov", "common"), qs)),
                     "coverage_rank_P_disc": aggregate(sel(("cov", "disc"), qs))}
                for sc, qs in scope_qs.items()}

    def per_query_kr(pairs):
        d: dict[str, list[int]] = defaultdict(list)
        for p in pairs:
            if p["bucket"] == "KR":
                d[p["q"]].append(p["hit"])
        return {q: sum(v) / len(v) for q, v in d.items()}

    tq = per_query_kr(sel(("tfidf", "common"), scope_qs[PRIMARY_SPLIT]))
    cq = per_query_kr(sel(("cov", "common"), scope_qs[PRIMARY_SPLIT]))
    qq = sorted(set(tq) & set(cq))
    boot = s7.paired_bootstrap([tq[q] for q in qq], [cq[q] for q in qq],
                               s7.FROZEN["bootstrap_B"], s7.FROZEN["seed"], s7.FROZEN["ci"])

    gt7, _ = s7.load_gt()
    recs = s7.per_query(L, gt7)
    kr7 = [q for q, r in recs.items() if q in scope_qs[PRIMARY_SPLIT] and r["target_kr"]]
    v2_ref = {"SPR_all@50_KR_dev": s7._spr(recs, "all", k, kr7), "queries_kr": len(kr7), "tau": s7.FROZEN["tau"],
              "note": "report_stage7_remeasure 의 V2 (ii) 정의 그대로 — 질의·GT·풀이 V7 과 다르다. 비교가 아니라 위치 표시다"}

    ex = edges[(edges["source_type"] == "examiner") & (~edges["is_npl"])].drop_duplicates("cited_id")
    cset = set(cidx)
    universe: dict[str, Counter] = defaultdict(Counter)
    for ctry, doc, pid in zip(ex["cited_country"], ex["cited_doc_id"], ex["cited_id"].str.replace("^patent:", "", regex=True)):
        inc, ind = doc in cset, pid in P_disc
        universe[str(ctry)]["corpus∧disc" if inc and ind else "corpus_only" if inc else "disc_only" if ind else "neither"] += 1

    outside = Counter(country[i] for i in range(len(cid)) if i not in common_idx)
    pools = {
        "P_corpus": {"n": len(cid), "by_country": dict(Counter(country))},
        "P_disc": {"n": len(P_disc), "by_prefix": dict(Counter(d.split("_", 1)[0] for d in P_disc))},
        "P_common": {"n": len(common_idx), "by_country": dict(Counter(country[i] for i in common_idx))},
        "P_corpus_outside_common": {"n": sum(outside.values()), "by_country": dict(outside)},
    }
    unalignable = [
        {"what": "입력 자료", "why": "tfidf 질의는 제목+초록+청구항1 텍스트·후보는 제목+초록, CoverageRank 질의는 독립항 필수개념·후보는 전 청구항 개념이다. 같은 입력을 주면 다른 랭커가 된다",
         "direction": "부호를 말할 수 없다 — 이 사다리가 가르는 것은 입력 차이를 뺀 나머지다"},
        {"what": f"풀 밖 코퍼스 문헌 {pools['P_corpus_outside_common']['n']:,}건 ({_counts(pools['P_corpus_outside_common']['by_country'])})",
         "why": "청구항 분해가 없어 Disclosure 가 없다 — CoverageRank 가 순위를 매길 수 없다",
         "direction": "P_common 은 양쪽에서 뺀다(대칭). 그 대가로 FOREIGN 은 US 만 남는다 — JP·WO·CN 에 대해 아무것도 말하지 않는다"},
        {"what": f"P_disc 위 tfidf (본문 없는 문헌 {len(P_disc) - len(common_pid):,}건)",
         "why": "코퍼스에 제목·초록이 없다",
         "direction": "배경 문헌 부담은 CoverageRank 에만 걸린다(사다리 2 대 3 으로 그 몫을 잰다). 그래서 2칸의 두 랭커 차는 랭커 차와 배경 부담이 섞인 값이고, 대칭 비교는 3칸이다"},
        {"what": f"개념 접지 손실 (rej 독립항 미매핑 {identity.get('rej_independent_unmapped_rate')})",
         "why": "프로파일이 없는 질의는 CoverageRank 질의가 될 수 없다",
         "direction": "선택 효과는 사다리 0→1 의 tfidf 변화로 잰다"},
        {"what": "family · 공개시점 마스킹", "why": "인용문헌 family·출원일 열이 없다(check_leakage K-6 UNMEASURABLE)",
         "direction": "양쪽 모두 없다 — 대칭이지만 방향은 말할 수 없다"},
        {"what": "realgt 온톨로지 랭커(onto·onto_idf·hybrid)",
         "why": ("커밋된 2026-09-05 스냅샷(onto R@50 0.1606)이 오늘 생성기로 재현되지 않고, **같은 코드도 실행마다 다르다** — "
                 "2026-09-13 실측 PYTHONHASHSEED 1 대 2 에서 onto R@50 0.2061 대 0.2177 (동점 순서가 문자열 해시에 걸린다). "
                 "tfidf 블록은 시드와 무관하게 커밋본과 같다"),
         "direction": "V7 은 bridge 를 쓰지 않고 해시 시드가 달라도 바이트 동일하다 — 다만 onto 와의 비교는 이 리포트가 하지 않는다"},
    ]

    return {
        "plan": "PLAN-005 R0-CAL-2 · V7 CoverageRank 순위 계측 · τ 대칭 사다리 (판정 없음)",
        "generator": "scripts/report_v7_coverage_rank.py",
        "generated": str(date.today()),
        "read_only": True,
        "instrument_version": INSTRUMENT_VERSION,
        "split": PRIMARY_SPLIT,
        "split_sha256": splits.sha256_of(splits.SPLIT_CSV),
        "seal_ledger_rows": ledger_n,
        "frozen_v7": FROZEN_V7,
        "verdict": None,
        "inputs": {
            "data/patents/rejected_patents_meta.parquet": s7._sha(rg.META),
            "data/patents/prior_art_edges.parquet": s7._sha(rg.EDGES),
            "data/patents/fulltext_corpus.parquet": s7._sha(rg.CORPUS),
            "data/reports/prior_art_realgt_report.json": s7._sha(REALGT),
            "data/reports/abox_priorart_report.json": s7._sha(s7.ABOX_REPORT),
            "benchmark/assets/split.csv": splits.sha256_of(splits.SPLIT_CSV),
        },
        "identity_check_vs_abox_report": identity,
        "instrument_checks": {"score_eq1_is_R_all": ident, "tau_reproduction": tau_repro},
        "pools": pools,
        "cited_universe_by_country": {c: dict(v) for c, v in sorted(universe.items())},
        "queries": {"realgt_targets": len(targets), "Q_paired": len(Q),
                    "Q_paired_by_split": splits.split_composition(Qpids, split_map=split_map)},
        "tau_ladder": ladder,
        "by_scope_at_P_common": by_scope,
        "paired_bootstrap_dev_KR": {"definition": "dev · P_common · KR 쌍 보유 질의 · 질의별 적중률 · Δ = CoverageRank − tfidf",
                                    "note": "서술 — 판정 아님", **boot},
        "v2_ii_reference": v2_ref,
        "unalignable": unalignable,
        "limitations": [
            FROZEN_V7["verdict_note"],
            FROZEN_V7["tie_band_caveat"],
            f"주 범위는 {PRIMARY_SPLIT} 이다 — 분모가 작다. train 은 개념 사전이 채굴된 문서라 상한이지 성능이 아니다.",
            "봉인 분할(test·test_b)의 수는 이 리포트에 없다 — 코드가 막는다(D17 · assert_scope_allowed).",
        ],
    }


def _f(x, nd=4):
    if x is None:
        return "—"
    return f"{x:.{nd}f}" if isinstance(x, float) else f"{x:,}" if isinstance(x, int) else str(x)


def _counts(d: dict) -> str:
    return " · ".join(f"{k} {v:,}" for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))


def _cell(agg: dict | None, b: str = "KR") -> str:
    if not agg:
        return "—"
    m = agg["micro"][b]
    return f"**{_f(m['hit'])}** [{_f(m['worst'])}–{_f(m['best'])}] · 기대 {_f(m['exp'])} · n={m['pairs']}"


def render_markdown(rep: dict) -> str:
    ic = rep["instrument_checks"]
    tr = ic["tau_reproduction"]
    L = ["# PLAN-005 R0-CAL-2 — V7 CoverageRank · τ 대칭 사다리 (기계 산출)", "",
         f"> 생성: `scripts/report_v7_coverage_rank.py` · {rep['generated']} · 계측기 `{rep['instrument_version']}` · "
         "**손으로 고치지 않는다** — `make v7-rank` 가 다시 만든다.", "",
         "> **판정이 아니다** — 사전등록된 문턱이 없어 이 수로 PASS/FAIL 을 말하지 않는다. V2 정의·τ·판정은 `PLAN-005-stage7-verdict.md` 가 그대로 갖는다. "
         f"주 범위 `{rep['split']}` · 분할표 sha256 `{rep['split_sha256'][:12]}…` · 봉인 원장 {rep['seal_ledger_rows']}행.", "",
         "## 계측기 검사", "",
         f"- score = 1 ⟺ R∀: 질의 {ic['score_eq1_is_R_all']['queries_checked']:,} · 불일치 **{ic['score_eq1_is_R_all']['mismatch']}**",
         f"- τ 재현(원 조건 tfidf KR micro R@50): **{tr['tau_reproduced']}** = 동결 τ {tr['tau_frozen']} · "
         f"FOREIGN {tr['FOREIGN_reproduced']} · 쌍 {tr['pairs']} — 커밋된 realgt 와 일치", "",
         "## 후보 풀", "", "| 풀 | 문헌 | 구성 |", "|---|---:|---|"]
    for name, p in rep["pools"].items():
        L.append(f"| {name} | {p['n']:,} | {_counts(p.get('by_country', p.get('by_prefix')))} |")
    L += ["", "심사관 인용문헌(`~is_npl`)의 국가별 소속:", "", "| 국가 | 코퍼스∧Disclosure | 코퍼스만 | Disclosure만 | 둘 다 없음 |", "|---|---:|---:|---:|---:|"]
    for c, v in rep["cited_universe_by_country"].items():
        L.append(f"| {c} | {v.get('corpus∧disc', 0)} | {v.get('corpus_only', 0)} | {v.get('disc_only', 0)} | {v.get('neither', 0)} |")
    L += ["", "## τ 사다리 — 한 칸에 조건 하나 (KR micro R@50 · [최악–최선] · 기대)", "",
          "| 칸 | 바뀐 조건 | tfidf | CoverageRank | CR 풀 |", "|---:|---|---|---|---|"]
    for r in rep["tau_ladder"]:
        L.append(f"| {r['rung']} | {r['change']} | {_cell(r['tfidf'])} | {_cell(r['coverage_rank'])} | {r['coverage_rank_pool'] or '—'} |")
    L += ["", "## 4칸 — 범위별 (P_common)", "",
          "| 범위 | 지표 | tfidf | CoverageRank (P_common) | CoverageRank (P_disc) |", "|---|---|---|---|---|"]
    for sc, blk in rep["by_scope_at_P_common"].items():
        lab = f"**{sc} (주)**" if sc == rep["split"] else sc
        L.append(f"| {lab} | KR micro | {_cell(blk['tfidf'])} | {_cell(blk['coverage_rank'])} | {_cell(blk['coverage_rank_P_disc'])} |")
        L.append(f"| {lab} | FOREIGN micro | {_cell(blk['tfidf'], 'FOREIGN')} | {_cell(blk['coverage_rank'], 'FOREIGN')} | {_cell(blk['coverage_rank_P_disc'], 'FOREIGN')} |")
        mk = lambda a: f"{_f(a['macro']['KR']['hit'])} (q={a['macro']['KR']['queries']})"
        L.append(f"| {lab} | KR macro | {mk(blk['tfidf'])} | {mk(blk['coverage_rank'])} | {mk(blk['coverage_rank_P_disc'])} |")
    b = rep["paired_bootstrap_dev_KR"]
    v2 = rep["v2_ii_reference"]
    L += ["", f"페어드 부트스트랩(서술 · {b['definition']}): n={b['n']} · Δ {_f(b['delta'])} · 95% CI "
          f"{[round(x, 4) for x in b['ci']] if b['ci'] else '—'}", "",
          f"V2 (ii) 위치 표시(비교 아님): dev SPR∀@50(KR) {_f(v2['SPR_all@50_KR_dev'])} · Q_KR={v2['queries_kr']} · τ {v2['tau']} — {v2['note']}", "",
          "## 정렬할 수 없는 것", "", "| 무엇 | 왜 불가 | 방향에 대해 말할 수 있는 것 |", "|---|---|---|"]
    for u in rep["unalignable"]:
        L.append(f"| {u['what']} | {u['why']} | {u['direction']} |")
    L += ["", "## 동결 정의 (FROZEN_V7)", ""]
    for key, val in rep["frozen_v7"].items():
        L.append(f"- `{key}`: {val}")
    L += ["", "## 한계", ""] + [f"- {x}" for x in rep["limitations"]]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--markdown", type=Path, default=None)
    a = ap.parse_args()
    rep = run()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.markdown:
        a.markdown.write_text(render_markdown(rep), encoding="utf-8")
    for r in rep["tau_ladder"]:
        t, c = r["tfidf"]["micro"]["KR"], (r["coverage_rank"] or {}).get("micro", {}).get("KR")
        print(f"  칸 {r['rung']} · tfidf KR {_f(t['hit'])} (n={t['pairs']})"
              + (f" · CR KR {_f(c['hit'])} [{r['coverage_rank_pool']}]" if c else ""))
    d = rep["by_scope_at_P_common"][PRIMARY_SPLIT]
    print(f"  {PRIMARY_SPLIT} · P_common · tfidf KR {_f(d['tfidf']['micro']['KR']['hit'])} · "
          f"CR KR {_f(d['coverage_rank']['micro']['KR']['hit'])} · 판정 없음")
    print(f"→ {a.out}" + (f" · {a.markdown}" if a.markdown else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
