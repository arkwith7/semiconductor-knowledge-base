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
