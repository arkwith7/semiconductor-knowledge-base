#!/usr/bin/env python3
"""PLAN-006 T4 S4·S5 — 아이디어(청구항) → KIPRIS 구조화 검색식 + 결정적 축소·완화 (그래프를 바꾸지 않는다).

S4 패싯 — 청구항 요소 표현을 보존한다 (PLAN-006 §3.1″·§3.3′)
  독립항 → 규칙 분해(`decompose_claims.decompose`) → 요소마다 Kiwi 명사 복합어 후보 →
  df 대역 [DF_MIN, DF_MAX_FRAC·N] 안에서 **요소의 대표 표현 하나** = 가장 구체적인 표현(어절 수 → 글자 수)을 고른다.
  같은 요소의 동의어 = OR · 다른 요소 = AND. 개념은 표현을 묶고 확장하는 역할만 한다.

비교군별 차이 (나머지는 같다)
  a′  요소 구조 없이 청구항 전체에서 df 기준 키워드 상위 N 을 단일어 패싯으로 · 동의어 없음 · IPC 없음
  c1  요소 패싯 + 개념 표면형 동의어(ko·en) · IPC 없음
  c2  c1 + 개념↔IPC 동시출현으로 **IPC 를 고른다**(질의 자신의 IPC 는 쓰지 않는다 — 아이디어에는 IPC 가 없다)
  c3  c2 + train 심사관 판단 가중으로 패싯 순서를 정한다 (가중 표는 train 만 읽는다)

S5 축소·완화 (결정적 · 정답을 보지 않는다 · 총 실행 MAX_RUNS = 초기 포함 6)
  상태 = (포함 패싯 수 k, IPC 단계). 패싯은 df 내림차순(넓은 것 먼저)으로 쌓는다.
  시작 k = ceil(n/2), IPC = 없음.
  |S| > 예산      → k+1 (패싯 소진 시 IPC 강화: 없음 → 서브클래스 → 메인그룹)
  |S| < M_MIN     → IPC 완화가 가능하면 완화, 아니면 k−1 (가장 좁은 패싯부터 뺀다)
  이미 실행한 상태로 가야 하면 순환 — 멈춘다.
  최종 선택 = 실행 이력 중 (1) 예산 안 (2) |S| ≥ M_MIN (3) k 큰 것(입력 요소 충족) (4) |S| 가 예산에 가까운 것.
  예산 안 상태가 없으면 실패(집합 없음).
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

MAX_RUNS = 6
DF_MIN = 3            # 대표 표현은 코퍼스에 최소 이만큼 있어야 한다(오탈자·희귀 표기 회피)
DF_MAX_FRAC = 0.30    # 이보다 흔한 표현은 패싯이 되지 못한다(좁히지 못한다)
MAX_FACETS = 8
SYN_MAX = 6
IPC_LEVELS = ("none", "subclass", "main_group")
_NOUN_TAGS = {"NNG", "NNP", "SL", "XR"}
STOP = frozenset("""
단계 상기 방법 장치 포함 형성 구비 제공 사용 이용 구성 부재 부분 위치 상 하 측 내 외 것 수 및 또는 또 제 제1 제2 제3
일 이 각 복수 적어도 하나 이상 이하 경우 상태 대응 연결 배치 갖 가지 따른 의한 통해 위한 관한 특징 청구항 항
위 아래 상부 하부 상단 하단 상면 하면 영역 일부 전체 주변 내부 외부 표면 면 방향 사이 쪽 단 부 층
""".split())  # 위치·방향어는 요소를 구분하지 못한다 — 복합어를 여기서 끊는다


# ── 표면형 사전 (c1 이후) ───────────────────────────────────────────────────────
def _norm_surface(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[/_\-.()]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Lexicon:
    """표면형 ↔ 개념. 원천: concept_mapping(patent-text) · abox_term_aliases. 모호 항목은 쓰지 않는다."""

    def __init__(self, mapping=ROOT / "mappings" / "concept_mapping.json",
                 aliases=ROOT / "mappings" / "abox_term_aliases.json"):
        self.s2c: dict[str, str] = {}
        self.c2s: dict[str, set[str]] = {}
        m = json.loads(Path(mapping).read_text(encoding="utf-8"))
        for e in m["profiles"]["patent-text"]["entries"]:
            if e.get("ambiguous"):
                continue
            self._add(e["surface"], e["concept_id"])
        a = json.loads(Path(aliases).read_text(encoding="utf-8"))
        for k, v in a.items():
            if not k.startswith("_") and isinstance(v, str):
                self._add(k, v)

    def _add(self, surface: str, cid: str):
        s = _norm_surface(surface)
        if len(s) < 2:
            return
        self.s2c.setdefault(s, cid)
        self.c2s.setdefault(cid, set()).add(s)

    def concept_of(self, term: str) -> str | None:
        t = _norm_surface(term)
        if t in self.s2c:
            return self.s2c[t]
        head = t.split(" ")[-1]
        return self.s2c.get(head)

    def synonyms(self, term: str) -> tuple[str | None, list[str]]:
        cid = self.concept_of(term)
        if not cid:
            return None, []
        t = _norm_surface(term)
        syn = sorted(self.c2s.get(cid, set()) - {t}, key=lambda x: (-len(x), x))[:SYN_MAX]
        return cid, syn


# ── 명사 복합어 후보 ───────────────────────────────────────────────────────────
_KIWI = None


def noun_compounds(text: str) -> list[str]:
    """Kiwi 명사(NNG·NNP·SL·XR) 연속을 복합어로 묶는다. 붙어 있거나 한 칸 띄운 것만 잇는다."""
    global _KIWI
    if _KIWI is None:
        from kiwipiepy import Kiwi
        _KIWI = Kiwi()
    out, cur, end = [], [], -1
    for t in _KIWI.tokenize(text or ""):
        if t.tag in _NOUN_TAGS and t.form not in STOP and not re.fullmatch(r"\d+", t.form):
            if cur and t.start - end <= 1:
                cur.append(text[t.start:t.start + t.len] if t.start - end == 0 else " " + text[t.start:t.start + t.len])
            else:
                if cur:
                    out.append("".join(cur))
                cur = [text[t.start:t.start + t.len]]
            end = t.start + t.len
        else:
            if cur:
                out.append("".join(cur))
            cur, end = [], -1
    if cur:
        out.append("".join(cur))
    seen, res = set(), []
    for c in out:
        c = c.strip()
        if len(c) >= 2 and c not in seen:
            seen.add(c)
            res.append(c)
    return res


# ── 패싯 ──────────────────────────────────────────────────────────────────────
@dataclass
class Facet:
    seq: int
    term: str
    df: int
    concept: str | None = None
    synonyms: list[str] = field(default_factory=list)       # 온톨로지 표면형(검증된 개념명·별칭 · 개념 IRI 에 연결)
    translations: list[str] = field(default_factory=list)   # 공통 번역 후보(동결 파일 · LLM 산출) — 출처가 다르므로 따로 둔다

    def clause(self) -> str:
        alts = [self.term] + self.synonyms + [t for t in self.translations if t not in self.synonyms]
        q = [f'"{a}"' if (" " in a and not re.search(r"[가-힣]", a)) else a for a in alts]
        return q[0] if len(q) == 1 else "(" + "+".join(q) + ")"


class DF:
    """표현의 코퍼스 문서빈도 — 에뮬레이터 실행 결과 수. 질의 문서 자신은 빼고 센다."""

    def __init__(self, emu):
        self.emu, self.n, self._c = emu, len(emu.doc_ids), {}

    def __call__(self, term: str) -> int:
        if term not in self._c:
            try:
                self._c[term] = len(self.emu.run(term))
            except ValueError:
                self._c[term] = 0
        return self._c[term]


def pick(cands: list[str], df: DF) -> tuple[str, int] | None:
    """요소의 대표 표현: df 대역 안에서 **가장 구체적인 표현**(어절 수 → 글자 수가 큰 것), 동률이면 df 작은 것."""
    ok = [(df(c), c) for c in cands]
    ok = [(d, c) for d, c in ok if DF_MIN <= d <= DF_MAX_FRAC * df.n]
    if not ok:
        return None
    d, c = max(ok, key=lambda x: (len(x[1].split()), len(x[1]), -x[0], x[1]))
    return c, d


def facets_elements(claim: str, df: DF, lex: Lexicon | None) -> list[Facet]:
    from decompose_claims import decompose
    dc = decompose(claim)
    parts = [f.text for f in dc.features] or [claim]
    out, used = [], set()
    for i, p in enumerate(parts, 1):
        got = pick([c for c in noun_compounds(p) if c not in used], df)
        if not got:
            continue
        term, d = got
        used.add(term)
        f = Facet(seq=i, term=term, df=d)
        if lex is not None:
            f.concept, syn = lex.synonyms(term)
            f.synonyms = [s for s in syn if df(s) >= 1]
        out.append(f)
    return out[:MAX_FACETS]


def facets_keywords(claim: str, df: DF, n: int) -> list[Facet]:
    cands = [(df(c), c) for c in noun_compounds(claim)]
    cands = sorted([(d, c) for d, c in cands if DF_MIN <= d <= DF_MAX_FRAC * df.n], key=lambda x: (x[0], x[1]))
    return [Facet(seq=i, term=c, df=d) for i, (d, c) in enumerate(cands[:n], 1)]


# ── S5 ─────────────────────────────────────────────────────────────────────────
@dataclass
class Run:
    k: int
    ipc_level: str
    query: str
    ipc: list[str]
    size: int


def build_query(facets: list[Facet], k: int) -> str:
    return "*".join(f.clause() for f in facets[:k])


def adjust(facets: list[Facet], emu, *, budget: int, m_min: int, ipc_codes: dict[str, list[str]] | None,
           exclude: tuple[str, ...]) -> tuple[list[Run], Run | None, list[str]]:
    """facets 는 이미 쌓을 순서로 정렬돼 있어야 한다. 반환: (이력, 최종, 최종 집합)."""
    if not facets:
        raise ValueError("패싯이 없다 — 검색식을 만들 수 없는 입력")
    levels = IPC_LEVELS if ipc_codes else ("none",)
    k, li = max(1, math.ceil(len(facets) / 2)), 0
    hist: list[Run] = []
    sets: dict[tuple[int, int], list[str]] = {}
    while len(hist) < MAX_RUNS:
        state = (k, li)
        if state in sets:
            break
        lvl = levels[li]
        codes = (ipc_codes or {}).get(lvl, []) if lvl != "none" else []
        q = build_query(facets, k)
        res = emu.run(q, ipc=codes or None, exclude=exclude)
        sets[state] = res
        hist.append(Run(k, lvl, q, codes, len(res)))
        if len(res) > budget:
            if k < len(facets):
                k += 1
            elif li + 1 < len(levels):
                li += 1
            else:
                break
        elif len(res) < m_min:
            if li > 0:
                li -= 1
            elif k > 1:
                k -= 1
            else:
                break
        else:
            break
    inside = [r for r in hist if r.size <= budget and r.size > 0]
    if not inside:
        return hist, None, []
    best = max(inside, key=lambda r: (r.size >= m_min, r.k, -abs(budget - r.size), -IPC_LEVELS.index(r.ipc_level)))
    li_best = levels.index(best.ipc_level)
    return hist, best, sets[(best.k, li_best)]


# ── R1 다중 부분 검색식 (PLAN-006 T4 4단계 설계 변경 · 2026-10-09 승인) ────────────────
MULTI_MAX_RUNS = 12   # 다중 전략의 총 에뮬레이터 실행 상한(좁힘 포함)
PAIR_MAX = 4          # 핵심 요소 + 주변 요소 쌍 검색식 수 상한


@dataclass
class SubQuery:
    role: str            # all | core | pair | single
    facets: tuple[int, ...]
    query: str
    size: int
    narrowed: bool
    accepted: bool


def core_split(facets: list[Facet]) -> tuple[list[Facet], list[Facet]]:
    """핵심 = df 가 가장 작은(가장 구체적인) 패싯 2개 · 주변 = 나머지(df 오름차순). 정답을 보지 않는다."""
    by_spec = sorted(facets, key=lambda f: (f.df, f.seq))
    return by_spec[:2], by_spec[2:]


def plan_multi(facets: list[Facet], emu, *, budget: int, exclude: tuple[str, ...],
               ipc_narrow: list[str] | None = None, splitter=None) -> tuple[list[SubQuery], list[str]]:
    """전체 AND 를 유지하고 부분 검색식을 더한다. 순위 없는 집합이므로 **검색식 단위로만** 채택한다.

    순서(고정): all → core → pair(core1·core2 × 주변, PAIR_MAX) → single(core 각각)
    개별 과대(> budget): 쓰지 않은 주변 요소 중 가장 구체적인 것 하나를 AND 해 한 번 좁힌다 — 그래도 크면 버린다.
    누적: 합집합이 budget 을 넘게 되는 검색식은 통째로 건너뛴다(문헌 ID 순 절단 금지). 200 은 상한이지 목표가 아니다.
    """
    if not facets:
        raise ValueError("패싯이 없다 — 검색식을 만들 수 없는 입력")
    core, peri = (splitter or core_split)(facets)
    order = list(range(len(facets)))
    pos = {id(f): i for i, f in enumerate(facets)}
    plan: list[tuple[str, tuple[int, ...]]] = [("all", tuple(order))]
    if len(core) == 2:
        plan.append(("core", tuple(sorted(pos[id(f)] for f in core))))
    pairs = [(c, p) for c in core for p in peri][:PAIR_MAX]
    plan += [("pair", tuple(sorted((pos[id(c)], pos[id(p)])))) for c, p in pairs]
    plan += [("single", (pos[id(c)],)) for c in core]
    seen, out, union, runs = set(), [], [], 0
    useful_extra = [pos[id(f)] for f in peri]
    for role, ids in plan:
        if ids in seen or runs >= MULTI_MAX_RUNS:
            continue
        seen.add(ids)
        q = "*".join(facets[i].clause() for i in ids)
        res = emu.run(q, exclude=exclude); runs += 1
        narrowed = False
        if len(res) > budget and ipc_narrow and runs < MULTI_MAX_RUNS:
            # c2: 넓은 검색식만 IPC 로 좁힌다 — 예산 안 검색식에는 IPC 를 붙이지 않는다(정답 재탈락 방지)
            res_i = emu.run(q, ipc=ipc_narrow, exclude=exclude); runs += 1
            if len(res_i) <= budget:
                res, narrowed = res_i, True
                q = q + "  [IPC " + "+".join(ipc_narrow) + "]"
        if len(res) > budget:
            extra = next((i for i in useful_extra if i not in ids), None)
            if extra is None or runs >= MULTI_MAX_RUNS:
                out.append(SubQuery(role, ids, q, len(res), False, False)); continue
            ids2 = tuple(sorted(ids + (extra,)))
            q = "*".join(facets[i].clause() for i in ids2)
            res = emu.run(q, exclude=exclude); runs += 1; narrowed = True
            seen.add(ids2)
            if len(res) > budget:
                out.append(SubQuery(role, ids2, q, len(res), True, False)); continue
            ids = ids2
        merged = sorted(set(union) | set(res))
        ok = bool(res) and len(merged) <= budget
        if ok:
            union = merged
        out.append(SubQuery(role, ids, q, len(res), narrowed, ok))
    return out, union


# ── R2 공통 번역 (a′·c 공통 · 동결 파일) ───────────────────────────────────────────
TRANSLATIONS = ROOT / "data" / "queries" / "t4_term_translations_v1.jsonl"
TRANSLATIONS_MANIFEST = ROOT / "data" / "queries" / "t4_term_translations_v1.manifest.json"


class Translations:
    """동결 번역 파일. sha 가 매니페스트와 다르면 중단한다 — 다른 번역으로 같은 이름의 결과를 내지 않기 위해."""

    def __init__(self, path: Path = TRANSLATIONS, manifest: Path = TRANSLATIONS_MANIFEST):
        import hashlib
        m = json.loads(Path(manifest).read_text(encoding="utf-8"))
        got = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if got != m["sha256"]:
            raise SystemExit(f"ERROR: 번역 파일 sha 가 매니페스트와 다르다\n  매니페스트 {m['sha256']}\n  실측 {got}")
        self.sha = got
        self.ko2en = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            self.ko2en[r["ko"]] = r["en"]

    def apply(self, facets: list[Facet], df: "DF") -> list[Facet]:
        """번역 후보를 붙인다. 코퍼스에 없거나(df 0) 패싯 상한보다 넓은 후보는 버린다 — 넓은 영어 단어가
        수천 건 후보 문제를 되풀이하지 않게(패싯과 같은 규칙 · 정답을 보지 않는다)."""
        for f in facets:
            f.translations = [t for t in self.ko2en.get(f.term, []) if 1 <= df(f'"{t}"' if " " in t else t) <= DF_MAX_FRAC * df.n]
        return facets


# ── §3.4 공통 적응 확장 (원 결과 보존) ─────────────────────────────────────────────
ADAPT_TRIES = 2       # 부분 검색식마다 확장 시도: (1) 모든 확장어 (2) 패싯당 첫 확장어 하나


def _strip(f: Facet) -> Facet:
    return Facet(f.seq, f.term, f.df, f.concept)


def _top1(f: Facet) -> Facet:
    alts = [a for a in f.synonyms + f.translations if a != f.term]
    return Facet(f.seq, f.term, f.df, f.concept, synonyms=alts[:1])


def plan_multi_adaptive(facets: list[Facet], emu, *, budget: int, exclude: tuple[str, ...],
                        ipc_narrow: list[str] | None = None, splitter=None) -> tuple[list[SubQuery], list[str]]:
    """원 표현으로 얻은 합집합을 먼저 확보하고 보존한 뒤, 같은 부분 검색식 순서로 확장을 시도한다.

    확장 결과는 **전체 합집합 기준** 잔여 예산 안일 때만 더한다 — 넘으면 패싯당 첫 확장어 하나로 줄여 한 번 더,
    그래도 넘으면 그 확장을 취소한다. 원 결과는 어떤 경우에도 빼지 않는다. 정답을 보지 않는다.
    확장어가 없는 입력은 plan_multi 와 같은 결과를 낸다.
    """
    bare = [_strip(f) for f in facets]
    base_subs, union = plan_multi(bare, emu, budget=budget, exclude=exclude, ipc_narrow=ipc_narrow, splitter=splitter)
    union_set = set(union)
    out = list(base_subs)
    if not any(f.synonyms or f.translations for f in facets):
        return out, union
    for s in base_subs:
        ids = s.facets
        if not any(facets[i].synonyms or facets[i].translations for i in ids):
            continue
        for attempt in range(ADAPT_TRIES):
            fs = [facets[i] if attempt == 0 else _top1(facets[i]) for i in ids]
            q = "*".join(f.clause() for f in fs)
            res = emu.run(q, exclude=exclude)
            merged = union_set | set(res)
            if res and len(merged) <= budget:
                union_set = merged
                out.append(SubQuery(f"{s.role}+exp{attempt + 1}", ids, q, len(res), False, True))
                break
            out.append(SubQuery(f"{s.role}+exp{attempt + 1}", ids, q, len(res), False, False))
    return out, sorted(union_set)


# ── §3.4-③ c2 개념↔IPC (넓은 부분 검색식을 좁히는 데만) ────────────────────────────
IPC_MIN_DOCS = 20     # 개념당 이보다 적은 문서로는 IPC 연결을 세우지 않는다
IPC_TOP = 2           # 질의당 고르는 메인그룹 수


def concept_local(cid: str | None) -> str | None:
    return cid.split(":", 1)[-1] if cid else None


class IpcSelector:
    """코퍼스 후보 문서의 개념 × IPC 메인그룹 동시출현(lift)으로 질의의 IPC 를 고른다.

    비지도 통계다 — 질의·인용 관계(정답)는 읽지 않는다. 다만 **dev·test·test_b 질의 문서는 표에서 뺀다**(§3.4).
    판 정규화(H01L↔H10)는 에뮬레이터가 공통으로 하므로 여기서는 기호를 고르기만 한다.
    """

    def __init__(self, corpus, exclude_docs: set[str]):
        from collections import Counter
        from kipris_emulator import norm_ipc

        c = corpus[corpus["is_candidate"] & ~corpus["doc_id"].isin(exclude_docs)]
        self.n = len(c)
        self.ipc_n: Counter = Counter()
        self.con_n: Counter = Counter()
        self.pair: Counter = Counter()
        for cons, ipcs in zip(c["concepts"], c["ipc"]):
            mg = sorted({x.split("/")[0] for x in (norm_ipc(i) for i in (ipcs if ipcs is not None else [])) if x and len(x) > 4})
            cs = sorted(set(cons)) if cons is not None else []
            self.ipc_n.update(mg)
            self.con_n.update(cs)
            for k in cs:
                for g in mg:
                    self.pair[(k, g)] += 1

    def choose(self, concepts: list[str]) -> list[str]:
        import math
        score: dict[str, float] = {}
        for k in sorted({x for x in concepts if x and self.con_n[x] >= IPC_MIN_DOCS}):
            for (kk, g), n in self.pair.items():
                if kk != k or n < 3:
                    continue
                lift = (n / self.con_n[k]) / (self.ipc_n[g] / self.n)
                if lift > 1:
                    score[g] = score.get(g, 0.0) + math.log(lift) * n / self.con_n[k]
        return [g for g, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:IPC_TOP]]


# ── §3.4-④ c3 심사관 판단 기반 요소 우선순위 ──────────────────────────────────────
C3_LEARN_FRAC = 7     # 패밀리 해시 % 10 < 7 → 학습 · 나머지 → 점검 (train 안에서 출원·패밀리 단위 분리)
C3_PRIOR = (1, 4)     # 베타 사전(성공 1 · 실패 4) — 드문 개념의 가중이 튀지 않게


def family_bucket(family_id: str) -> int:
    import hashlib
    return int(hashlib.sha256(str(family_id).encode()).hexdigest(), 16) % 10


class JudgmentWeights:
    """train **학습 구간** 질의의 심사관 인용으로 개념별 가중 w(c) = P(인용문헌이 c 를 가짐 | 질의가 c 를 가짐).

    학습 구간 밖(점검 구간·dev·test)의 인용은 읽지 않는다. 요소 우선순위(핵심 패싯 선택)에만 쓴다.
    """

    def __init__(self, learn_gt: dict[str, set[str]], doc_concepts: dict[str, set[str]]):
        from collections import Counter
        hit, tot = Counter(), Counter()
        for q in sorted(learn_gt):
            qc = doc_concepts.get(q, set())
            for d in sorted(learn_gt[q]):
                dc = doc_concepts.get(d, set())
                for k in qc:
                    tot[k] += 1
                    hit[k] += k in dc
        a, b = C3_PRIOR
        self.w = {k: (hit[k] + a) / (tot[k] + a + b) for k in tot}
        self.default = a / (a + b)

    def weight(self, f: Facet) -> float:
        return self.w.get(concept_local(f.concept), self.default)


def core_split_weighted(facets: list[Facet], jw: JudgmentWeights) -> tuple[list[Facet], list[Facet]]:
    by = sorted(facets, key=lambda f: (-jw.weight(f), f.df, f.seq))
    return by[:2], by[2:]


def save_weights(jw: JudgmentWeights, path: Path, meta: dict) -> str:
    """c3 가중을 결정적 JSON 으로 동결한다. 반환: sha256."""
    import hashlib
    body = {"meta": meta, "prior": list(C3_PRIOR), "default": jw.default, "w": {k: jw.w[k] for k in sorted(jw.w)}}
    text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def load_weights(path: Path, sha: str | None = None) -> JudgmentWeights:
    import hashlib
    raw = Path(path).read_bytes()
    if sha and hashlib.sha256(raw).hexdigest() != sha:
        raise SystemExit(f"ERROR: c3 가중 파일 sha 가 동결값과 다르다: {path}")
    body = json.loads(raw)
    jw = JudgmentWeights.__new__(JudgmentWeights)
    jw.w, jw.default = body["w"], body["default"]
    return jw
