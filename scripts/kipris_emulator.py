#!/usr/bin/env python3
"""PLAN-006 T4 S3 — KIPRIS 검색식 문법 에뮬레이터 (로컬 코퍼스 · 순위 없는 집합).

검색식 효과를 재려면 문자열 처리 규칙이 고정·명시돼 있어야 한다 — 규칙이 흔들리면 검색식이
아니라 에뮬레이터를 재게 된다(PLAN-006 §3.3′). 아래 명세의 **(가정)** 항목은 라이브 KIPRIS
표본과의 차이로 따로 보고한다.

문법 (우선순위 높은 것부터)
  ( … )        묶음
  !A           NOT
  A*B          AND
  A+B          OR
  "구문"        정규화 후 연속 부분 문자열
  A B          따옴표 밖 공백 = AND (가정)

일치 규칙
  정규화: NFKC · 소문자 · 공백 묶음 1칸
  한글이 든 항: 부분 일치 — "식각" 은 "식각하는" 에 맞는다 (가정: KIPRIS 형태소 검색의 근사)
  ASCII 항: 단어 시작 접두 일치 — "etch" 는 "etching" 에 맞고 "sketch" 에는 안 맞는다
  필드: TI 제목 · AB 초록 · CL 청구항(claims_full, 없으면 claims_independent) · 기본 TI+AB+CL

IPC
  한정 코드: 서브클래스 `H01L` · 메인그룹 `H01L21` · 그룹 `H01L21/306`(그룹은 정확 일치)
  문서 IPC 정규화: `H01J_37-32` · `C04B41-85` · `H01L21/306` → `H01J37/32` 꼴
  판 대응: mappings/ipc_concordance.csv 간선을 양방향으로 이어(닫힘) 같은 세부 분류 계열을 OR 확장
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONCORDANCE = ROOT / "mappings" / "ipc_concordance.csv"
FIELDS = ("TI", "AB", "CL")
_HANGUL = re.compile(r"[가-힣]")


def norm_text(s: str | None) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"\s+", " ", s).strip()


# ── IPC ───────────────────────────────────────────────────────────────────────
_IPC = re.compile(r"^([A-H]\d\d[A-Z])_?(\d+)?(?:[/\-](\d+))?$")


def norm_ipc(code: str) -> str | None:
    """`H01J_37-32` · `C04B41-85` · `H01L21/306` · `H01L21` · `H01L` → `H01J37/32` 꼴. 해석 못 하면 None."""
    m = _IPC.match((code or "").strip().upper().replace(" ", ""))
    if not m:
        return None
    sub, grp, sg = m.groups()
    if grp is None:
        return None if sg else sub
    return f"{sub}{int(grp)}" + (f"/{sg}" if sg is not None else "")


def _ipc_keys(doc_code: str) -> tuple[str, ...]:
    """문서 기호가 걸리는 한정 키: 서브클래스 · 메인그룹 · 그룹 자신.

    그룹(`/`)은 **정확 일치만** — IPC 서브그룹 계층은 점(들여쓰기)으로 정해지지 숫자 접두로
    정해지지 않는다(`21/30` 아래에 `21/306` 이 있다는 보장이 없다).
    """
    sub = doc_code[:4]
    main = doc_code.split("/", 1)[0]
    return tuple(dict.fromkeys((sub, main, doc_code)))


def _ipc_prefix_match(doc_code: str, q: str) -> bool:
    return q in _ipc_keys(doc_code)


class Concordance:
    """판 대응 간선의 양방향 닫힘. 일괄 서브클래스 동등은 만들지 않는다."""

    def __init__(self, path: Path = CONCORDANCE):
        self.adj: dict[str, set[str]] = {}
        with Path(path).open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                a, b = r["from_symbol"], r["to_symbol"]
                if a == b:
                    continue
                self.adj.setdefault(a, set()).add(b)
                self.adj.setdefault(b, set()).add(a)
        self._syms = sorted(self.adj)

    def expand(self, q: str) -> list[str]:
        """q 에 걸리는 대응표 기호에서 출발해 간선을 닫힘까지 따라간 기호 + q 자신. 정렬된 결과."""
        seeds = [s for s in self._syms if _ipc_prefix_match(s, q)]
        seen, stack = set(seeds), list(seeds)
        while stack:
            for n in sorted(self.adj.get(stack.pop(), ())):
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
        return sorted(seen | {q})


# ── 문법 ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Node:
    op: str              # "term" | "phrase" | "and" | "or" | "not"
    value: str = ""
    kids: tuple = ()


_TOKEN = re.compile(r'\s*(?:(\()|(\))|(\+)|(\*)|(!)|"([^"]*)"|([^\s()+*!"]+))')


def tokenize(q: str) -> list[tuple[str, str]]:
    if q is None or not q.strip():
        raise ValueError("빈 검색식")
    out, pos = [], 0
    q = q.strip()
    while pos < len(q):
        m = _TOKEN.match(q, pos)
        if not m or m.end() == pos:
            raise ValueError(f"해석할 수 없는 문자: {q[pos:pos + 10]!r}")
        pos = m.end()
        lp, rp, plus, star, bang, phr, word = m.groups()
        if lp: out.append(("(", "("))
        elif rp: out.append((")", ")"))
        elif plus: out.append(("+", "+"))
        elif star: out.append(("*", "*"))
        elif bang: out.append(("!", "!"))
        elif phr is not None:
            if not phr.strip():
                raise ValueError("빈 구문")
            out.append(("phrase", phr))
        else:
            out.append(("term", word))
    return out


def parse(q: str) -> Node:
    toks = tokenize(q)
    i = 0

    def peek():
        return toks[i][0] if i < len(toks) else None

    def eat(kind):
        nonlocal i
        if peek() != kind:
            raise ValueError(f"{kind!r} 가 와야 할 자리: {toks[i:i + 3]}")
        i += 1
        return toks[i - 1]

    def p_or():
        kids = [p_and()]
        while peek() == "+":
            eat("+"); kids.append(p_and())
        return kids[0] if len(kids) == 1 else Node("or", kids=tuple(kids))

    def p_and():
        kids = [p_not()]
        while peek() in ("*", "term", "phrase", "(", "!"):
            if peek() == "*":
                eat("*")
            kids.append(p_not())  # 공백 인접 = AND (가정)
        return kids[0] if len(kids) == 1 else Node("and", kids=tuple(kids))

    def p_not():
        if peek() == "!":
            eat("!")
            return Node("not", kids=(p_atom(),))
        return p_atom()

    def p_atom():
        k = peek()
        if k == "(":
            eat("("); n = p_or(); eat(")"); return n
        if k == "term":
            return Node("term", eat("term")[1])
        if k == "phrase":
            return Node("phrase", eat("phrase")[1])
        raise ValueError(f"항이 와야 할 자리: {toks[i:i + 3]}")

    node = p_or()
    if i != len(toks):
        raise ValueError(f"남은 토큰: {toks[i:]}")
    if _only_negative(node):
        raise ValueError("NOT 만으로 된 검색식은 코퍼스 전체를 돌려준다 — 거부")
    return node


def _only_negative(n: Node) -> bool:
    if n.op == "not":
        return True
    if n.op == "and":
        return all(_only_negative(k) for k in n.kids)
    if n.op == "or":
        return any(_only_negative(k) for k in n.kids)
    return False


# ── 실행 ──────────────────────────────────────────────────────────────────────
class Emulator:
    """후보 코퍼스 위에서 검색식을 집합으로 실행한다. 순위는 없다."""

    def __init__(self, corpus, concordance: Concordance | None = None):
        import numpy as np

        self._np = np
        c = corpus[corpus["is_candidate"]].sort_values("doc_id").reset_index(drop=True)
        self.doc_ids = c["doc_id"].tolist()
        claims = c["claims_full"].where(c["claims_full"].fillna("").str.len() > 0, c["claims_independent"])
        self.text = {
            "TI": [norm_text(x) for x in c["title"]],
            "AB": [norm_text(x) for x in c["abstract"]],
            "CL": [norm_text(x) for x in claims],
        }
        self.ipc = [sorted({n for n in (norm_ipc(x) for x in (v if v is not None else [])) if n}) for v in c["ipc"]]
        self.conc = concordance or Concordance()
        self._cache: dict[tuple, object] = {}
        self._ipc_index: dict[str, list[int]] | None = None

    def _match(self, node: Node, fields: tuple[str, ...]):
        np = self._np
        key = (node, fields)
        if key in self._cache:
            return self._cache[key]
        if node.op in ("term", "phrase"):
            t = norm_text(node.value)
            if node.op == "term" and not _HANGUL.search(t):
                rx = re.compile(r"(?<![a-z0-9])" + re.escape(t))
                hit = lambda s: rx.search(s) is not None
            else:
                hit = lambda s: t in s
            m = np.zeros(len(self.doc_ids), bool)
            for f in fields:
                m |= np.fromiter((hit(s) for s in self.text[f]), bool, len(self.doc_ids))
        elif node.op == "and":
            m = np.ones(len(self.doc_ids), bool)
            for k in node.kids:
                m &= self._match(k, fields)
        elif node.op == "or":
            m = np.zeros(len(self.doc_ids), bool)
            for k in node.kids:
                m |= self._match(k, fields)
        elif node.op == "not":
            m = ~self._match(node.kids[0], fields)
        else:
            raise ValueError(node.op)
        self._cache[key] = m
        return m

    def ipc_mask(self, codes: list[str]):
        np = self._np
        if self._ipc_index is None:
            idx: dict[str, list[int]] = {}
            for i, ds in enumerate(self.ipc):
                for k in {k for d in ds for k in _ipc_keys(d)}:
                    idx.setdefault(k, []).append(i)
            self._ipc_index = idx
        qs = sorted({e for c in codes for e in self.conc.expand(norm_ipc(c) or c)})
        m = np.zeros(len(self.doc_ids), bool)
        for q in qs:
            m[self._ipc_index.get(q, [])] = True
        return m

    def run(self, query: str, *, fields: tuple[str, ...] = FIELDS, ipc: list[str] | None = None,
            exclude: tuple[str, ...] = ()) -> list[str]:
        bad = set(fields) - set(FIELDS)
        if bad or not fields:
            raise ValueError(f"알 수 없는 검색 필드: {sorted(bad) or fields}")
        m = self._match(parse(query), tuple(sorted(fields))).copy()
        if ipc:
            m &= self.ipc_mask(ipc)
        ex = set(exclude)
        return [d for d, ok in zip(self.doc_ids, m) if ok and d not in ex]
