"""개념→축(axis)·T-Box 계층 지도 (PLAN-018 §7.3 M4-3/M4-4 · M4 온톨로지팔 입력).

코퍼스 `concepts` 컬럼의 슬러그(예: `etch`·`cmos`·`copper`)는 SDKB 온톨로지 개념 IRI 의 지역명이다
(`corpus/assemble.CONCEPT_PROPS` 로 링크된 객체). 이 모듈은 **코퍼스가 조립된 것과 동일한 그래프
G₀∪G₁∪G₂**(assemble 와 같은 원천)에서 각 개념의 **축(rdf:type ont:클래스)** 과 **클래스 subClassOf
계층**을 결정적으로 추출해 커밋 가능한 지도로 굳힌다. (벤더 스냅샷만으로는 problems/emerging 이 추가한
FailureMode 46개가 축 미상 → A3 ablation 이 고장 개념을 못 빼는 오류가 되므로 처리 그래프에서 소싱한다.)

- **ConceptOverlap(M4-3)** = 개념 집합의 축 가중 Jaccard(축 가중치 균등). 축 구분은 A2/A3 ablation 분할용.
- **PathSim(M4-4)** = 개념→클래스 Wu-Palmer(TBox subClassOf DAG). ⚠️ as-built: 개념 계층이 사실상
  평면(개념간 관계 4·subClassOf 9건) → WP 는 거의 축-일치로 퇴화한다. 이 모듈이 그 사실을 계량 보고한다.

**어휘 발명 0(CLAUDE §1.6):** 축·계층은 벤더 TTL 의 `a ont:X`·`rdfs:subClassOf` 에서만 온다.
**경계:** 런타임은 `~/Dev/sdkb` 를 읽지 않는다 — 얼린 `config.EXTERNAL_SDKB` 스냅샷만(CLAUDE §0.1).

출력: `config.IR_CONCEPT_AXIS`(parquet: slug·iri·axis_class·axis_segment) + 동반 `.tree.json`
(클래스 parent·depth — PathSim WP 계산용). 재측정: `python -m sdkb_paper.ontology.concept_axis`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..corpus.assemble import CONCEPT_PROPS

ONT = str(config.ONT)
_TREE_SUFFIX = ".tree.json"


def _tree_path() -> Path:
    return config.IR_CONCEPT_AXIS.with_suffix(_TREE_SUFFIX)


def _local(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def _segment(iri: str) -> str:
    """`.../sdkb/data/<seg>/<slug>` → <seg> (축의 IRI-경로 근거). 아니면 ''。"""
    parts = iri.rstrip("/").split("/")
    return parts[-2] if len(parts) >= 2 and "/data/" in iri else ""


def extract(graphs: dict[str, Path] | None = None, store=None,
            extra_iris: dict[str, str] | None = None) -> tuple:
    """그래프 집합(또는 이미 적재된 store) → (axis_df, tree). **파일을 쓰지 않는다.**

    `build()` 가 정본 산출물을 만들 때도, 결함주입 실험(PLAN-020 W4)이 **오염된 합집합 store**
    에서 대체 뷰를 만들 때도 **같은 이 함수**를 쓴다 — 추출 로직이 두 벌로 갈라지면 실험이
    정본과 다른 것을 재고 있게 된다. `store` 를 주면 적재를 건너뛴다(오염본을 디스크에 쓰지
    않기 위해 필요하다).

    `extra_iris`(IRI → 축 후보)는 **개념 적용기가 새로 링크한 개념**의 우주다(PLAN-034 §3.2 A′).
    적용기가 붙인 개념은 `CONCEPT_PROPS` 의 객체가 아니라서 이 우주를 넓히지 않으면 축이 미상이
    되고, 그러면 A2·A3·A8 절제가 신규 개념을 통째로 누락해 **기여를 오귀속**한다(실측 2026-08-01:
    발화 슬러그 157 중 58 이 축 미상). 축은 ①그래프 `rdf:type` ②이 인자의 값(사전 concept_type)
    ③IRI 세그먼트 순으로 정한다. **스키마는 넓히지 않는다** — 무작동 동치성(§3.3) 때문이다.
    """
    import contextlib
    import tempfile

    import pandas as pd
    from pyoxigraph import NamedNode, RdfFormat, Store

    from ..corpus.assemble import GRAPHS

    graphs = graphs or GRAPHS

    with (contextlib.nullcontext(None) if store is not None
          else tempfile.TemporaryDirectory()) as tmp:
        if store is None:
            store = Store(path=str(Path(tmp) / "s"))
            for gname, path in graphs.items():
                if not Path(path).exists():
                    raise FileNotFoundError(f"그래프 없음: {path} (make merge 필요)")
                with open(path, "rb") as fh:
                    store.bulk_load(fh, format=RdfFormat.TURTLE, to_graph=NamedNode(gname))

        # ① 개념 IRI 우주 = CONCEPT_PROPS 의 객체 (누출원 미포함 — assemble 과 동일 규율)
        vals = " ".join(f"ont:{p}" for p in CONCEPT_PROPS)
        q_iri = (f"PREFIX ont:<{ONT}> SELECT DISTINCT ?c WHERE {{ GRAPH ?g {{ "
                 f"?s ?prop ?c . VALUES ?prop {{ {vals} }} }} }}")
        incumbent = {r["c"].value for r in store.query(q_iri)
                     if r["c"].value.startswith(str(config.SDKB_DATA))}
        # 적용기 우주를 더한다. **기존(그래프 링크) 개념이 우선**이다 — 신규가 기존 슬러그의
        # 축을 뒤집으면 절제(A2/A3/A8)의 정의가 조용히 바뀐다(§3.2 A′).
        extra = {k: v for k, v in (extra_iris or {}).items()
                 if str(k).startswith(str(config.SDKB_DATA))}
        concept_iris = incumbent | set(extra)

        # ② 각 개념 IRI → axis_class(rdf:type ont:X 지역명)
        types: dict[str, set[str]] = {}
        q_type = (f"PREFIX ont:<{ONT}> SELECT ?c ?cls WHERE {{ GRAPH ?g {{ "
                  f"?c a ?cls }} }}")
        want = concept_iris
        for r in store.query(q_type):
            c = r["c"].value
            if c in want and r["cls"].value.startswith(ONT):
                types.setdefault(c, set()).add(_local(r["cls"].value))

        # ③ 클래스 subClassOf DAG (ont: 클래스만)
        parent: dict[str, list[str]] = {}
        q_sub = ("SELECT ?s ?o WHERE { GRAPH ?g { "
                 "?s <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?o } }")
        for r in store.query(q_sub):
            s, o = r["s"].value, r["o"].value
            if s.startswith(ONT) and o.startswith(ONT):
                parent.setdefault(_local(s), []).append(_local(o))

    rows = []
    for iri in sorted(concept_iris):
        slug = _local(iri)
        seg = _segment(iri)
        classes = types.get(iri, set())
        # 축 클래스: ①그래프 타입(유일하면 그것·다중이면 사전순 첫) ②사전 concept_type
        # ③세그먼트. 셋 다 없으면 빈 문자열.
        if classes:
            axis_class = sorted(classes)[0]
        else:
            axis_class = extra.get(iri) or (seg if seg else "")
        rows.append(
            {"slug": slug, "iri": iri, "axis_class": axis_class,
             "axis_segment": seg, "n_types": len(classes), "ambiguous": len(classes) > 1,
             "_incumbent": iri in incumbent}
        )
    # 슬러그 중복 시: **기존(그래프 링크) 우선** → 타입보유 → iri 사전순 (전부 결정적)
    axis_df = (pd.DataFrame(rows)
               .sort_values(["slug", "_incumbent", "n_types", "iri"],
                            ascending=[True, False, False, True])
               .drop_duplicates("slug").sort_values("slug")
               .drop(columns=["_incumbent"]).reset_index(drop=True))

    parent = {k: sorted(set(v)) for k, v in parent.items()}
    classes_all = set(axis_df["axis_class"]) | set(parent) | {
        c for cs in parent.values() for c in cs
    }
    classes_all.discard("")

    def depth(c: str, _seen: frozenset[str] = frozenset()) -> int:
        """가상 루트(owl:Thing) = 0. 부모 없는 최상위 클래스 = 1. 하위로 +1.

        이 오프셋으로 같은 최상위 클래스 두 개념의 Wu-Palmer 가 2·1/(1+1)=1(0/0 회피),
        다른 최상위끼리는 LCA=가상루트(0) → WP=0 이 된다(rerank 의 pathsim 참조).
        """
        ps = parent.get(c, [])
        if not ps or c in _seen:  # 최상위(부모 없음) 또는 순환 방지
            return 1
        return 1 + min(depth(p, _seen | {c}) for p in ps)

    tree = {
        "parent": parent,
        "depth": {c: depth(c) for c in sorted(classes_all)},
    }
    return axis_df, tree


def build(snapshot: Path | None = None) -> dict:
    """G₀∪G₁∪G₂ → 개념 축·클래스 계층 추출 → parquet + tree.json. 요약 dict 반환.

    코퍼스와 동일 원천(assemble 의 GRAPHS)에서 pyoxigraph 온디스크로 적재해 SPARQL 로 뽑는다
    (rdflib 는 대용량 그래프서 메모리 폭주 — 메모리 `central-axis-use-oxigraph-ondisk`).
    """
    from . import concept_dict

    # 적용기가 링크할 개념도 축 지도에 들어와야 한다(§3.2 A′). 사전이 없으면 빈 dict → 무작동.
    surfaces = concept_dict.load()
    axis_df, tree = extract(extra_iris=concept_dict.concept_types(surfaces))

    config.IR_CONCEPT_AXIS.parent.mkdir(parents=True, exist_ok=True)
    axis_df.to_parquet(config.IR_CONCEPT_AXIS, index=False)
    _tree_path().write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")

    n_ambig = int(axis_df["ambiguous"].sum())
    n_typed = int((axis_df["n_types"] > 0).sum())
    from collections import Counter
    axis_dist = dict(Counter(axis_df["axis_class"]).most_common())
    max_depth = max(tree["depth"].values()) if tree["depth"] else 0
    return {
        "n_concepts": len(axis_df),
        "n_typed": n_typed,
        "n_seg_only": len(axis_df) - n_typed,
        "n_ambiguous": n_ambig,
        "axis_dist": axis_dist,
        "n_classes": len(tree["depth"]),
        "n_subclassof_edges": sum(len(v) for v in tree["parent"].values()),
        "max_class_depth": max_depth,
        "out": str(config.IR_CONCEPT_AXIS),
    }


# --- 로더 (rerank 가 쓰는 경량 인터페이스) ----------------------------------
def load_axis() -> dict[str, str]:
    """slug → axis_class. 없으면 build() 를 요구(명시적 실패)."""
    import pandas as pd

    if not config.IR_CONCEPT_AXIS.exists():
        raise SystemExit("[concept_axis] 지도 없음 — `python -m sdkb_paper.ontology.concept_axis` 먼저")
    df = pd.read_parquet(config.IR_CONCEPT_AXIS)
    return dict(zip(df["slug"], df["axis_class"]))


def load_tree() -> dict:
    """{parent: {class:[parents]}, depth: {class:int}} — PathSim WP 용."""
    p = _tree_path()
    if not p.exists():
        raise SystemExit("[concept_axis] 계층 없음 — build() 먼저")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    s = build()
    print("✓ 개념 축·계층 지도 →", s["out"])
    print(f"  개념 {s['n_concepts']}개 · 타입보유 {s['n_typed']} · 세그먼트유도 {s['n_seg_only']}"
          f" · 다중타입 {s['n_ambiguous']}")
    print(f"  축 분포: {s['axis_dist']}")
    print(f"  클래스 {s['n_classes']}개 · subClassOf {s['n_subclassof_edges']}엣지"
          f" · 최대깊이 {s['max_class_depth']}  ← 평면일수록 PathSim 퇴화(M4-4)")


if __name__ == "__main__":
    main()
