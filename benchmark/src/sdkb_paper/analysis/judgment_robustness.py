"""불완전 정답 아래의 비교 강건성 (PLAN-055 · 원고 §4.5·§5.4.1).

**묻는 것 한 문장 — 짝지은 비교의 결론이 미판정 문헌의 관련성에 의존하는가.**

정답은 심사관 인용이므로 **양성 전용**이다. 판정된 비적합 집합이 없어 `unjudged@K = 1 − P@K` 가
항등이 되므로, 미판정 비율의 대조는 새 정보를 주지 않는다(PLAN-055 §1.1). 그래서 이 모듈은
다른 둘을 산출한다.

- **조성 대조**(`composition`) — 두 구성이 상위 K 에 올린 **미판정 문서의 종류**가 같은가.
  축은 넷으로 고정한다: 언어 · 공개 연도(결측은 `미상` 범주) · CPC 주분류 · 문서당 개념 수.
- **판정 전복 문턱**(`reversal_threshold`) — 미판정 패밀리 가운데 **몇 건이 실제로 관련 문헌이면서
  한쪽 구성에만 유리하게 분포해야** 짝지은 차이가 0 에 도달하는가.

**전복 문턱의 정의(최악 배치).** 질의 q 의 정답 패밀리 수를 R_q, 구성 a 의 상위 100 회수 수를
r_{q,a} 라 하면 Recall_{q,a} = r_{q,a}/R_q 다. 여기에 **비교 우위 구성에 최대로 불리하게**
미판정 패밀리를 추가한다 — 열위 구성의 상위 100 에는 있고 우위 구성의 상위 100 에는 없는
패밀리만 고른다. 한 건 추가마다 R_q += 1 · r_{q,열위} += 1 · r_{q,우위} 불변이므로 짝지은 차이가
단조 감소한다. n\\* 는 판정량(점추정 · 부트스트랩 95 % CI 하한)이 0 에 도달하는 최소 추가 건수다.

**배치 규칙과 그 귀결.** 배치는 **점추정을 가장 빠르게 낮추는 탐욕 배치**다(질의당 한계 감소량
(R_q + r_{q,우위} − r_{q,열위}) / (R'(R'+1)) 이 단조 감소하므로 점추정에 대해서는 최적이다).
**CI 하한에 대해서는 최적이 아닐 수 있으므로 `n_star_lb95` 는 상한으로 읽는다** — 더 나쁜 배치가
있다면 그것은 더 적은 건수로 하한을 0 에 닿게 한다.

**이 모듈은 판정을 만들지 않는다.** run·qrel·코퍼스를 읽기만 하고, 지표 정의와 부트스트랩 절차는
`metrics`·`bootstrap` 의 것을 그대로 호출한다. n\\* 에 합격선을 두지 않는다(PLAN-055 §3.1).

CLI: `python -m sdkb_paper.analysis.judgment_robustness [--split test] [--runset O_pre_linker]`
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config
from .metrics import _fold, load_qrel_for_split, load_run

# --- 동결 상수 (PLAN-055 §4 · 결과 보기 전 고정) ------------------------------
TOP_K = 100                     # 주지표와 동일
N_BOOT = 10000                  # 기존 부트스트랩과 동일
AXES = ("lang", "pub_year", "cpc_main", "n_concepts")   # 넷 고정 · 늘리지 않는다
YEAR_UNKNOWN = "미상"           # 결측을 버리지 않는다 — 버리면 두 구성의 분모가 달라진다

#: 원고 §5 의 수치를 재현하는 run 집합. `runs/` 는 이후 세대이므로 기본값이 아니다(§5.1 OBS-R4).
DEFAULT_RUNSET = "O_pre_linker"
#: 판독 B 분할의 run 은 별도 집합에 있다.
RUNSET_B = "B_layer_readout"

SYS_FILES = {
    "B3": "sys_B3_rrf_{split}.txt",
    "P1": "sys_P1_{split}.txt",
    "P0star": "sys_P0star_{split}.txt",
}


def runset_dir(name: str) -> Path:
    return Path(config.IR_DIR) / "runsets" / name


def _load_family_map() -> dict[str, str]:
    from ..collect.bq_family_ir import load_family_map

    return load_family_map()


def _split_qids(split: str) -> set[str]:
    sp = pd.read_parquet(config.IR_SPLIT, columns=["doc_id", "split"])
    return set(sp.loc[sp["split"] == split, "doc_id"].astype(str))


def _fold_top(run: dict[str, list[str]], qid: str, fam: dict[str, str], k: int) -> list[str]:
    """질의의 문서 순위 → 상위 k **패밀리**(fold-then-cut · metrics 와 같은 규칙)."""
    return _fold(run.get(qid, []), fam)[:k]


def _family_representative(run: dict[str, list[str]], qid: str, fam: dict[str, str],
                           k: int) -> dict[str, str]:
    """상위 k 패밀리 → 그 패밀리의 **첫 등장 문서**. 조성 대조의 메타데이터는 이 문서에서 읽는다.

    fold-then-cut 이 남기는 것이 첫 등장이므로, 대표 문서의 선택 규칙은 지표의 규칙과 같다.
    """
    seen: dict[str, str] = {}
    for d in run.get(qid, []):
        f = fam.get(d, d)
        if f not in seen:
            seen[f] = d
            if len(seen) >= k:
                break
    return seen


# --- 조성 대조 ----------------------------------------------------------------

def _corpus_meta() -> pd.DataFrame:
    """조성 대조가 읽는 네 축. 파생 컬럼을 만들지 않고 있는 열에서 읽는다."""
    cols = ["doc_id", "lang", "publication_date", "cpc", "ipc", "concepts"]
    c = pd.read_parquet(config.IR_CORPUS, columns=cols)
    c["doc_id"] = c["doc_id"].astype(str)
    year = pd.to_datetime(c["publication_date"], errors="coerce").dt.year
    c["pub_year"] = year.astype("Int64")
    # 축은 사전등록대로 "CPC/IPC 주분류"다. 후보의 97.2 % 에서 CPC 가 비어 있으므로(실측)
    # CPC 가 있으면 CPC, 없으면 IPC 를 읽는다. 축을 늘리는 것이 아니라 같은 축의 대체 표기다.
    c["cpc_main"] = [_cpc_main(a) if _cpc_main(a) != YEAR_UNKNOWN else _cpc_main(b)
                     for a, b in zip(c["cpc"], c["ipc"], strict=True)]
    c["n_concepts"] = c["concepts"].map(lambda v: 0 if v is None else len(v))
    return c.set_index("doc_id")[["lang", "pub_year", "cpc_main", "n_concepts"]]


def _cpc_main(v) -> str:
    """CPC 주분류 = 첫 부호의 **섹션+클래스**(예: `H01`). 값이 없으면 `미상`."""
    if v is None:
        return YEAR_UNKNOWN
    if isinstance(v, str):
        first = v.split(";")[0].split(",")[0].strip()
    else:
        seq = list(v)
        if not seq:
            return YEAR_UNKNOWN
        first = str(seq[0]).strip()
    return first[:3] if len(first) >= 3 else (first or YEAR_UNKNOWN)


def composition(unjudged_docs: list[str], meta: pd.DataFrame) -> dict:
    """미판정 대표 문서 집합의 조성. **기술통계이며 검정을 붙이지 않는다**(PLAN-055 §2.2)."""
    if not unjudged_docs:
        return {"n": 0}
    m = meta.reindex(unjudged_docs)
    lang = m["lang"].fillna(YEAR_UNKNOWN).value_counts(normalize=True).round(4).to_dict()
    yr = m["pub_year"]
    ncon = m["n_concepts"].fillna(0)
    return {
        "n": int(len(m)),
        "lang_share": {str(k): float(v) for k, v in lang.items()},
        "pub_year_median": (float(yr.dropna().median()) if yr.notna().any() else None),
        "pub_year_unknown_share": float(yr.isna().mean()),
        "cpc_main_top5": {str(k): float(v) for k, v in
                          m["cpc_main"].fillna(YEAR_UNKNOWN)
                          .value_counts(normalize=True).head(5).round(4).items()},
        "n_concepts_q1": float(ncon.quantile(0.25)),
        "n_concepts_median": float(ncon.median()),
        "n_concepts_q3": float(ncon.quantile(0.75)),
    }


# --- 전복 문턱 ----------------------------------------------------------------

def _delta(rw: np.ndarray, rl: np.ndarray, R: np.ndarray, add: np.ndarray) -> np.ndarray:
    """추가 건수 `add` 를 반영한 질의별 짝지은 차이 (우위 − 열위).

    우위 구성은 회수 수가 불변이고 열위 구성만 추가분을 회수하며, 분모는 둘 다 늘어난다.
    """
    return (rw - rl - add) / (R + add)


def _greedy_add(rw: np.ndarray, rl: np.ndarray, R: np.ndarray, U: np.ndarray,
                n: int) -> np.ndarray:
    """총 n 건을 **점추정을 가장 빠르게 낮추는** 순서로 배치한다(질의당 U 건 상한)."""
    import heapq

    add = np.zeros_like(R)
    if n <= 0:
        return add
    # 한계 감소량 = (R + rw − rl) / (R'(R'+1)) — a 에 대해 단조 감소하므로 탐욕이 최적이다.
    heap = []
    for i in range(len(R)):
        if U[i] > 0:
            gain = (R[i] + rw[i] - rl[i]) / (R[i] * (R[i] + 1))
            heapq.heappush(heap, (-gain, i))
    placed = 0
    while heap and placed < n:
        _, i = heapq.heappop(heap)
        add[i] += 1
        placed += 1
        if add[i] < U[i]:
            rp = R[i] + add[i]
            gain = (R[i] + rw[i] - rl[i]) / (rp * (rp + 1))
            heapq.heappush(heap, (-gain, i))
    return add


def reversal_threshold(rw: np.ndarray, rl: np.ndarray, R: np.ndarray, U: np.ndarray,
                       *, n_boot: int = N_BOOT, seed: int = config.SEED) -> dict:
    """n\\*(점추정) 과 n\\*(부트스트랩 95 % CI 하한). 합격선을 두지 않는다."""
    rng = np.random.default_rng(seed)
    m = len(R)
    idx = rng.integers(0, m, size=(n_boot, m))     # 기존 절차와 같은 질의 단위 페어드

    def stats(n: int) -> tuple[float, float]:
        d = _delta(rw, rl, R, _greedy_add(rw, rl, R, U, n))
        return float(d.mean()), float(np.percentile(d[idx].mean(axis=1), 2.5))

    cap = int(U.sum())
    base_point, base_lb = stats(0)

    def first_zero(which: int) -> int | None:
        """단조 감소하므로 이분 탐색. 상한까지 채워도 0 에 못 닿으면 None."""
        if stats(cap)[which] > 0:
            return None
        lo, hi = 0, cap
        while lo < hi:
            mid = (lo + hi) // 2
            if stats(mid)[which] <= 0:
                hi = mid
            else:
                lo = mid + 1
        return lo

    n_point = first_zero(0)
    n_lb = first_zero(1)

    def touched(n: int | None) -> int | None:
        """n\\* 를 만드는 배치가 **몇 개 질의**에 걸치는가 — 건수만으로는 취약도가 읽히지 않는다."""
        return None if n is None else int((_greedy_add(rw, rl, R, U, n) > 0).sum())

    return {
        "n_queries": m,
        "R_median": float(np.median(R)),
        "R_one_share": float((R == 1).mean()),      # 정답이 하나뿐인 질의의 비중
        "n_star_point_queries": touched(n_point),
        "n_star_lb95_queries": touched(n_lb),
        "delta_point": base_point,
        "delta_lb95": base_lb,
        "U_total": cap,
        "U_mean": float(U.mean()),
        "U_median": float(np.median(U)),
        "U_zero_queries": int((U == 0).sum()),
        "n_star_point": n_point,
        "n_star_lb95": n_lb,
        "n_star_point_ratio": (None if n_point is None else n_point / cap),
        "n_star_lb95_ratio": (None if n_lb is None else n_lb / cap),
        "n_boot": n_boot,
        "seed": seed,
    }


# --- 상위 배선 ----------------------------------------------------------------

def analyse(split: str, *, runset: str | None = None, winner: str = "P1",
            loser: str = "B3", unseal_reason: str = "") -> dict:
    """한 분할의 조성 대조와 전복 문턱. **읽기 전용** — 어떤 산출물도 덮어쓰지 않는다."""
    rs = runset or (RUNSET_B if split == "test_b" else DEFAULT_RUNSET)
    d = runset_dir(rs)
    fam = _load_family_map()
    qrel = load_qrel_for_split(
        split, unseal=(split == "test_b"),
        reason=unseal_reason or f"PLAN-055 조성 대조·전복 문턱 (탐색적 · 확증 아님 · split={split})",
    )
    qrel_f = {q: {fam.get(x, x) for x in pos} for q, pos in qrel.items()}
    qids = sorted(_split_qids(split) & {q for q, pos in qrel_f.items() if pos})

    runs = {s: load_run(d / f.format(split=split)) for s, f in SYS_FILES.items()
            if (d / f.format(split=split)).exists()}
    meta = _corpus_meta()

    comp: dict[str, dict] = {}
    for sysname, run in runs.items():
        unjudged: list[str] = []
        for qid in qids:
            pos = qrel_f[qid]
            rep = _family_representative(run, qid, fam, TOP_K)
            unjudged += [doc for f_, doc in rep.items() if f_ not in pos]
        comp[sysname] = composition(unjudged, meta)

    R, rw, rl, U = [], [], [], []
    for qid in qids:
        pos = qrel_f[qid]
        fw = set(_fold_top(runs[winner], qid, fam, TOP_K))
        fl = set(_fold_top(runs[loser], qid, fam, TOP_K))
        R.append(len(pos))
        rw.append(len(fw & pos))
        rl.append(len(fl & pos))
        U.append(len((fl - fw) - pos))       # 열위에만 있고 미판정 = 적대적 추가 가능 후보
    thr = reversal_threshold(*(np.array(v, dtype=float) for v in (rw, rl, R, U)))

    return {
        "split": split, "runset": rs, "top_k": TOP_K,
        "winner": winner, "loser": loser,
        "recall_winner": float(np.mean(np.array(rw) / np.array(R))),
        "recall_loser": float(np.mean(np.array(rl) / np.array(R))),
        "composition": comp, "reversal": thr,
        "axes": list(AXES),
    }


def _fmt(r: dict) -> str:
    t = r["reversal"]
    lines = [
        f"[{r['split']} · runset {r['runset']} · top-{r['top_k']} · {r['winner']}−{r['loser']}]",
        f"  R@100  {r['winner']} {r['recall_winner']:.4f}   {r['loser']} {r['recall_loser']:.4f}"
        f"   Δ {t['delta_point']:+.4f}  LB95 {t['delta_lb95']:+.4f}",
        f"  U  총 {t['U_total']:,} · 평균 {t['U_mean']:.1f} · 중앙 {t['U_median']:.0f}"
        f" · U=0 질의 {t['U_zero_queries']}",
    ]
    for key, label in (("point", "점추정"), ("lb95", "CI 하한")):
        n = t[f"n_star_{key}"]
        ratio = t[f"n_star_{key}_ratio"]
        lines.append(f"  n*({label}) = " + ("상한 내 도달 없음" if n is None
                     else f"{n:,}  (n*/U = {ratio:.4f} · 질의 {t[f'n_star_{key}_queries']}개에 배치)"))
    lines.append(f"  R  중앙 {t['R_median']:.0f} · 정답 1건뿐인 질의 {t['R_one_share']:.3f}")
    for sysname, c in r["composition"].items():
        if not c.get("n"):
            continue
        lines.append(
            f"  조성 {sysname:7s} n={c['n']:,} · 언어 "
            + " ".join(f"{k}:{v:.3f}" for k, v in sorted(c["lang_share"].items()))
            + f" · 연도중앙 {c['pub_year_median']:.0f}"
              f"(미상 {c['pub_year_unknown_share']:.3f})"
              f" · 개념수 {c['n_concepts_q1']:.0f}/{c['n_concepts_median']:.0f}/"
              f"{c['n_concepts_q3']:.0f}"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["test", "test_b"], nargs="+", default=["test", "test_b"])
    ap.add_argument("--runset", default=None, help="기본: test=O_pre_linker · test_b=B_layer_readout")
    ap.add_argument("--out", type=Path,
                    default=Path(config.IR_DIR) / "judgment_robustness.json")
    args = ap.parse_args()

    out = {}
    for split in args.split:
        r = analyse(split, runset=args.runset)
        print(_fmt(r))
        out[split] = r
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
