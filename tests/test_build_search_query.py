"""PLAN-006 T4 S4·S5 — 패싯·축소/완화 절차의 계약 (가짜 에뮬레이터로 격리)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_search_query as Q  # noqa: E402


class FakeEmu:
    """검색식의 AND 항 수 k 와 IPC 로 집합 크기가 정해지는 에뮬레이터. 호출 기록을 남긴다."""

    def __init__(self, sizes: dict, ipc_sizes: dict | None = None):
        self.sizes, self.ipc_sizes, self.calls = sizes, ipc_sizes or {}, []

    def run(self, q, ipc=None, exclude=()):
        k = q.count("*") + 1
        self.calls.append((k, tuple(ipc or ())))
        n = self.ipc_sizes.get((k, tuple(ipc or ())), self.sizes[k]) if ipc else self.sizes[k]
        return [f"d{i}" for i in range(n)]


def facets(n):
    return [Q.Facet(seq=i, term=f"t{i}", df=1000 - i) for i in range(1, n + 1)]


def test_empty_facets_rejected():
    with pytest.raises(ValueError):
        Q.adjust([], FakeEmu({}), budget=200, m_min=10, ipc_codes=None, exclude=())


def test_narrows_until_within_budget():
    emu = FakeEmu({2: 900, 3: 400, 4: 150})
    hist, best, S = Q.adjust(facets(4), emu, budget=200, m_min=10, ipc_codes=None, exclude=())
    assert [r.k for r in hist] == [2, 3, 4] and best.k == 4 and len(S) == 150


def test_few_results_relaxes_not_only_zero():
    emu = FakeEmu({3: 2, 2: 60})   # 2건 — 0 이 아니어도 완화한다
    hist, best, _ = Q.adjust(facets(6), emu, budget=200, m_min=10, ipc_codes=None, exclude=())
    assert [r.k for r in hist] == [3, 2] and best.k == 2


def test_no_cycle_and_run_cap():
    emu = FakeEmu({k: (500 if k % 2 else 3) for k in range(1, 20)})
    hist, _, _ = Q.adjust(facets(12), emu, budget=200, m_min=10, ipc_codes=None, exclude=())
    states = [(r.k, r.ipc_level) for r in hist]
    assert len(states) == len(set(states)) and len(hist) <= Q.MAX_RUNS


def test_ipc_tightens_after_facets_exhausted():
    emu = FakeEmu({1: 900, 2: 800}, {(2, ("H01L",)): 120})
    hist, best, _ = Q.adjust(facets(2), emu, budget=200, m_min=10,
                             ipc_codes={"subclass": ["H01L"], "main_group": ["H01L21"]}, exclude=())
    assert [r.ipc_level for r in hist][-1] == "subclass" and best.size == 120


def test_final_prefers_min_size_then_more_facets():
    # k=3 → 1건(예산 안이지만 m_min 미달) · k=2 → 40건 → 최종은 k=2
    emu = FakeEmu({3: 1, 2: 40})
    _, best, _ = Q.adjust(facets(6), emu, budget=200, m_min=10, ipc_codes=None, exclude=())
    assert best.k == 2


def test_failure_when_nothing_within_budget():
    emu = FakeEmu({k: 5000 for k in range(1, 10)})
    hist, best, S = Q.adjust(facets(3), emu, budget=200, m_min=10, ipc_codes=None, exclude=())
    assert best is None and S == [] and len(hist) <= Q.MAX_RUNS


def test_deterministic():
    emu1, emu2 = FakeEmu({3: 2, 2: 60, 1: 900}), FakeEmu({3: 2, 2: 60, 1: 900})
    a = Q.adjust(facets(6), emu1, budget=200, m_min=10, ipc_codes=None, exclude=())
    b = Q.adjust(facets(6), emu2, budget=200, m_min=10, ipc_codes=None, exclude=())
    assert a[0] == b[0] and emu1.calls == emu2.calls


def test_facet_clause_or_within_and_across():
    f = [Q.Facet(1, "측벽 보호막", 50, synonyms=["sidewall passivation"]), Q.Facet(2, "식각", 900)]
    assert Q.build_query(f, 2) == '(측벽 보호막+"sidewall passivation")*식각'


def test_positional_words_break_compounds():
    out = Q.noun_compounds("산화물 반도체막 위에 측벽 보호막을 형성하는 단계")
    assert "산화물 반도체막 위" not in out and any("보호막" in c for c in out)


class SetEmu:
    """검색식 문자열 → 고정 문헌 집합."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def run(self, q, ipc=None, exclude=()):
        self.calls.append(q)
        return list(self.table.get(q, []))


def F4():
    return [Q.Facet(1, "a", 900), Q.Facet(2, "b", 50), Q.Facet(3, "c", 40), Q.Facet(4, "d", 500)]


def test_multi_keeps_full_and_query_first_and_core_is_most_specific():
    core, peri = Q.core_split(F4())
    assert [f.term for f in core] == ["c", "b"] and [f.term for f in peri] == ["d", "a"]
    emu = SetEmu({})
    out, union = Q.plan_multi(F4(), emu, budget=200, exclude=())
    assert out[0].role == "all" and emu.calls[0] == "a*b*c*d" and union == []


def test_multi_union_is_query_level_never_truncated():
    t = {"a*b*c*d": ["x1"], "b*c": [f"y{i}" for i in range(150)], "c*d": [f"z{i}" for i in range(100)],
         "a*c": ["w1", "w2"]}
    out, union = Q.plan_multi(F4(), SetEmu(t), budget=200, exclude=())
    acc = {o.query: o.accepted for o in out}
    assert acc["a*b*c*d"] and acc["b*c"] and not acc["c*d"]      # c*d 를 넣으면 251 > 200 → 통째로 건너뜀
    assert acc["a*c"] and len(union) == 153 and len(union) <= 200


def test_multi_narrows_oversized_query_once_then_drops():
    big = [f"n{i}" for i in range(500)]
    t = {"b*c": big, "b*c*d": big[:300]}
    out, _ = Q.plan_multi(F4(), SetEmu(t), budget=200, exclude=())
    core = next(o for o in out if o.role == "core")
    assert core.narrowed and not core.accepted and core.query == "b*c*d"


def test_multi_run_cap():
    emu = SetEmu({})
    many = [Q.Facet(i, f"t{i}", 1000 - i) for i in range(1, 9)]
    Q.plan_multi(many, emu, budget=200, exclude=())
    assert len(emu.calls) <= Q.MULTI_MAX_RUNS


def test_multi_empty_rejected():
    with pytest.raises(ValueError):
        Q.plan_multi([], SetEmu({}), budget=200, exclude=())
