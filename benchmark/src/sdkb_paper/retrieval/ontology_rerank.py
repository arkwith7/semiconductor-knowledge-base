"""온톨로지 순위 함수 (PLAN-018 §7.3 M4-2/M4-3/M4-4 · 원고 §4.7 §3.2).

`S_ont(q,d) = w_c·ConceptOverlap(q,d) + w_h·PathSim(q,d)`  (둘 다 [0,1]).
- **ConceptOverlap(M4-3):** 개념 슬러그 집합의 **축 가중 Jaccard**(축 가중치 균등 1.0 → 표준 Jaccard).
- **PathSim(M4-4):** 개념→ont:클래스 **Wu-Palmer**(TBox subClassOf DAG), 집합간 `mean_q max_d WP`.
  ⚠️ 계층이 얕아(최상위 클래스 다수·최대깊이 4) 대개 축-일치로 퇴화 — 정직 보고 대상.
- **B4(M4-7):** IPC/CPC 접두 계층 겹침(`ipc_sim`). IPC 주(전 문서), CPC 희소 보조.

효율: 정확 개념·IPC 겹침은 **역색인**으로 후보를 좁힌다(전 코퍼스 완전탐색 회피). 온톨로지팔은
개념·분류 링크가 있는 곳에서만 점수를 낸다 — 이는 온톨로지팔의 정직한 회수 상한이다.

- **경계(PLAN-018 §2):** run(순위)만 만든다 — qrel 미열람. 누출 피처(정답 파생) 미사용(§4 누출).
"""
from __future__ import annotations

from functools import lru_cache


from .. import config


# --- 개념·분류 피처 적재 ------------------------------------------------------
class OntologyFeatures:
    """코퍼스 concepts·ipc·cpc + 개념 축·계층을 적재해 순위함수 항을 제공한다."""

    def __init__(self) -> None:
        import pandas as pd

        from ..ontology.concept_axis import load_axis, load_tree

        df = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "concepts", "ipc", "cpc"])
        self.doc_ids: list[str] = df["doc_id"].astype(str).tolist()
        self.row: dict[str, int] = {d: i for i, d in enumerate(self.doc_ids)}

        def _sets(col):
            return [frozenset(a.tolist() if hasattr(a, "tolist") else (a or [])) for a in df[col]]

        self.concepts: list[frozenset[str]] = _sets("concepts")
        self.ipc: list[frozenset[str]] = _sets("ipc")
        self.cpc: list[frozenset[str]] = _sets("cpc")

        self.axis: dict[str, str] = load_axis()      # slug → axis_class
        tree = load_tree()
        self.depth: dict[str, int] = tree["depth"]
        self._parent: dict[str, list[str]] = tree["parent"]

        # 역색인: 개념 → 보유 doc row 집합 (정확 겹침 후보 축소용)
        self.inv_concept: dict[str, set[int]] = {}
        for i, cs in enumerate(self.concepts):
            for c in cs:
                self.inv_concept.setdefault(c, set()).add(i)
        # 역색인: IPC 계층 접두(서브클래스 이상 · 길이≥4) → doc row. B4 후보 축소.
        # 섹션(H)·클래스(H01)는 너무 광범위해 후보생성서 제외하되 유사도에는 반영.
        self.inv_ipc: dict[str, set[int]] = {}
        for i, cs in enumerate(self.ipc):
            for c in cs:
                for p in self._ipc_prefixes(c):
                    if len(p) >= 4:
                        self.inv_ipc.setdefault(p, set()).add(i)

    # -- 개념 클래스 조상(LCA용) --
    @lru_cache(maxsize=None)
    def _ancestors(self, cls: str) -> frozenset[str]:
        """cls 자신 + 모든 상위 클래스(DAG 전이폐포)."""
        out, stack = {cls}, [cls]
        while stack:
            c = stack.pop()
            for p in self._parent.get(c, []):
                if p not in out:
                    out.add(p)
                    stack.append(p)
        return frozenset(out)

    def _wp(self, c1: str, c2: str) -> float:
        """개념 슬러그 두 개의 Wu-Palmer(클래스 기준). 클래스 미상 → 0."""
        a1, a2 = self.axis.get(c1), self.axis.get(c2)
        if not a1 or not a2 or a1 not in self.depth or a2 not in self.depth:
            return 0.0
        common = self._ancestors(a1) & self._ancestors(a2)
        if not common:
            return 0.0
        lca_depth = max(self.depth.get(x, 0) for x in common)
        denom = self.depth[a1] + self.depth[a2]
        return (2.0 * lca_depth / denom) if denom else 0.0

    # -- 항 --
    @staticmethod
    def concept_overlap(a: frozenset[str], b: frozenset[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        return inter / len(a | b) if inter else 0.0

    def path_sim(self, a: frozenset[str], b: frozenset[str]) -> float:
        """mean_{qa} max_{db} WP(qa,db). 정확 겹침이면 WP=1 기여(자기클래스)."""
        if not a or not b:
            return 0.0
        tot = 0.0
        for qa in a:
            best = 0.0
            for db in b:
                w = 1.0 if qa == db else self._wp(qa, db)
                if w > best:
                    best = w
                    if best >= 1.0:
                        break
            tot += best
        return tot / len(a)

    @staticmethod
    def _ipc_prefixes(code: str) -> set[str]:
        """IPC/CPC 코드 → 계층 접두 집합(섹션·클래스·서브클래스·메인그룹).

        'H01L21-02' → {'H', 'H01', 'H01L', 'H01L21'}. 공유 접두가 깊을수록 근접.
        """
        code = code.replace("/", "-").strip()
        if not code:
            return set()
        out = {code[0]}                       # 섹션 (H)
        if len(code) >= 3:
            out.add(code[:3])                 # 클래스 (H01)
        # 서브클래스 = 섹션+클래스+알파 (H01L)
        i = 3
        while i < len(code) and code[i].isalpha():
            i += 1
        if i > 3:
            out.add(code[:i])
        maingroup = code.split("-")[0]        # 메인그룹 (H01L21)
        if maingroup and maingroup != code[:i]:
            out.add(maingroup)
        out.add(code)                          # 풀코드(서브그룹)
        return out

    def ipc_sim(self, a: frozenset[str], b: frozenset[str]) -> float:
        """두 분류 집합의 접두 계층 Jaccard. 깊은 공유 접두가 유사도를 끌어올린다."""
        if not a or not b:
            return 0.0
        pa: set[str] = set()
        pb: set[str] = set()
        for c in a:
            pa |= self._ipc_prefixes(c)
        for c in b:
            pb |= self._ipc_prefixes(c)
        if not pa or not pb:
            return 0.0
        return len(pa & pb) / len(pa | pb)

    # -- 후보 채점(역색인 기반) --
    def concept_candidates(self, q_concepts: frozenset[str]) -> set[int]:
        """질의 개념과 ≥1 정확 공유하는 doc row 집합."""
        out: set[int] = set()
        for c in q_concepts:
            out |= self.inv_concept.get(c, set())
        return out

    def ipc_candidates(self, q_ipc: frozenset[str]) -> set[int]:
        """질의 IPC 와 서브클래스 이상(길이≥4) 접두를 ≥1 공유하는 doc row 집합."""
        out: set[int] = set()
        for c in q_ipc:
            for p in self._ipc_prefixes(c):
                if len(p) >= 4:
                    out |= self.inv_ipc.get(p, set())
        return out


def _query_features(feats: OntologyFeatures) -> dict[str, int]:
    """질의 doc_id → 코퍼스 row (질의도 코퍼스 문서다)."""
    import pandas as pd

    q = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "is_query"])
    return {str(d): feats.row[str(d)] for d, isq in zip(q["doc_id"], q["is_query"]) if isq}
