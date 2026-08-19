"""특허 -> SDKB 개념(Process ∪ Device) 매핑.

개념 축이 두 개인 것은 데이터가 그렇게 생겼기 때문이다. IPC 개편으로 신설된 H10 계열은
**공정(H10P)과 소자(H10B·H10D)로 갈리고**, 소자 분류 특허를 공정에 억지로 매핑하는 것은 날조다.
그래서 룰 테이블은 `axis` 컬럼으로 축을 명시하고, 병합 단계가 `ont:realizesProcess` 와
`ont:concernsDevice` 를 가른다.

두 경로를 쓴다:

1. **IPC/CPC 룰 테이블** (`mappings/code_to_concept.csv`) — 결정적·재현가능. 1차 경로.
   코드 제목은 CPC 2026.01 공식 스킴 원문이다 (`mappings/PROVENANCE.md`).
2. **용어 매칭** (SDKB 의 skos:prefLabel / altLabel) — IPC 로 분해되지 않는 단계용 보완 경로.
   EUV/DUV 리소그래피가 대표적이다: 공식 스킴을 확인한 결과 H10P 에도 EUV/DUV 를 가르는 그룹은
   **없다**. SDKB 가 가진 별칭("EUV", "ArF", "KrF")으로 명세 텍스트를 봐야만 갈린다.

미매핑 코드는 버그가 아니라 **관측값**이다 — 커버리지 공백 분석의 입력이자, SHACL 게이트가
개념 링크 없는 특허를 막는 근거다(그런 특허는 graph 에 들어가지 않는다).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from rdflib import RDF, SKOS, Graph, URIRef

from sdkb_paper.config import CODE_MAPPING, ONT

AXES = ("process", "device")


# ── 1. IPC/CPC 룰 경로 ──────────────────────────────────────────────────
def load_code_mapping(csv_path: Path = CODE_MAPPING) -> dict[str, list[tuple[str, str]]]:
    """code_to_concept.csv -> {code_prefix: [(concept_iri, axis), ...]}

    code_prefix / concept_iri / axis 외의 컬럼(제목·근거·신뢰도·출처)은 사람이 읽고 검수하기
    위한 것이며 매칭에는 쓰이지 않는다.
    """
    df = pd.read_csv(csv_path)
    table: dict[str, list[tuple[str, str]]] = {}
    for _, row in df.iterrows():
        axis = str(row["axis"]).strip()
        if axis not in AXES:
            raise ValueError(f"알 수 없는 axis: {axis!r} (code={row['code_prefix']})")
        table.setdefault(_norm_code(row["code_prefix"]), []).append(
            (str(row["concept_iri"]).strip(), axis)
        )
    return table


def _norm_code(code: object) -> str:
    """KIPRIS 는 'H10P  50/26' 처럼 공백을 넣어 준다 — 공백 제거 후 대문자."""
    return re.sub(r"\s+", "", str(code)).upper()


def map_codes_to_concepts(
    codes: list[str], table: dict[str, list[tuple[str, str]]]
) -> dict[str, list[str]]:
    """가장 긴 prefix 우선 매칭. 축별 개념 IRI 를 돌려준다.

    긴 접두어 우선이 핵심이다 — H10P50/20(플라즈마 식각)은 H10P50(식각 일반)보다 먼저 잡혀야
    하위 공정으로 내려간다. 매칭되는 코드가 없으면 두 축 모두 빈 리스트다(= 병합 불가).
    """
    hits: dict[str, set[str]] = {axis: set() for axis in AXES}
    prefixes = sorted(table, key=len, reverse=True)
    for code in codes:
        code = _norm_code(code)
        for p in prefixes:
            if code.startswith(p):
                for iri, axis in table[p]:
                    hits[axis].add(iri)
                break
    return {axis: sorted(hits[axis]) for axis in AXES}


# ── 2. 용어 매칭 경로 (IPC 로 안 갈리는 단계) ───────────────────────────
def load_term_table(graph: Graph) -> dict[str, list[str]]:
    """SDKB 그래프에서 {공정 IRI: [prefLabel, altLabel...]} 를 뽑는다.

    한국어 altLabel("식각", "평탄화")과 영문 약어("EUV", "ArF")가 섞여 있다 — KIPRIS 국문
    명세에 그대로 걸리는 것이 이 경로의 존재 이유다.
    """
    table: dict[str, list[str]] = {}
    for cls in (ONT.Process, ONT.SubProcess):
        for step in graph.subjects(RDF.type, cls):
            terms = [str(t) for t in graph.objects(step, SKOS.prefLabel)]
            terms += [str(t) for t in graph.objects(step, SKOS.altLabel)]
            if terms:
                table[str(step)] = terms
    return table


def map_text_to_concepts(text: str, terms: dict[str, list[str]]) -> list[str]:
    """명세 텍스트에서 공정 용어를 찾아 IRI 로 되돌린다 (결정적 단어경계 매칭).

    보조 경로일 뿐이다 — 이 결과만으로 그래프에 넣지 않는다. IPC 룰이 상위 공정까지만
    찍어줄 때 하위 공정으로 내리는 근거로 쓰고, 사람이 검수한다.
    """
    hay = text.lower()
    hits = []
    for iri, labels in terms.items():
        for label in labels:
            # 한글은 단어경계(\b)가 동작하지 않으므로 ASCII 용어일 때만 경계를 강제한다.
            pattern = rf"\b{re.escape(label.lower())}\b" if label.isascii() else re.escape(label)
            if re.search(pattern, hay):
                hits.append(iri)
                break
    return sorted(set(hits))


# ── 3. 룰 커버리지 진단 ─────────────────────────────────────────────────
def rule_coverage(
    graph: Graph, table: dict[str, list[tuple[str, str]]] | None = None
) -> pd.DataFrame:
    """SDKB 개념 중 룰이 하나도 없는 것을 드러낸다.

    특허를 한 건도 수집하기 전에 매핑의 사각지대를 알 수 있다 — 룰이 없는 개념은
    H1/H2 에서 영원히 공백으로 남을 수밖에 없고, 그건 데이터가 아니라 룰의 한계다.
    """
    table = table if table is not None else load_code_mapping()
    mapped = {iri for pairs in table.values() for iri, _ in pairs}
    rows = []
    for cls in ("Process", "SubProcess", "Device"):
        for concept in graph.subjects(RDF.type, ONT[cls]):
            iri = str(concept)
            rows.append({
                "level": cls.lower(),
                "label": str(graph.value(URIRef(iri), SKOS.prefLabel)),
                "concept": iri,
                "n_rules": sum(iri in [i for i, _ in pairs] for pairs in table.values()),
            })
    df = pd.DataFrame(rows).sort_values(["level", "n_rules", "label"])
    df["has_rule"] = df["concept"].isin(mapped)
    return df.set_index(["level", "label"])[["n_rules", "has_rule", "concept"]]


def main() -> None:
    """CLI: baseline 대비 룰 커버리지를 두 축 모두 보고한다."""
    from sdkb_paper.config import GRAPH_V0

    g = Graph().parse(GRAPH_V0)
    df = rule_coverage(g)
    print(df[["n_rules", "has_rule"]].to_string())
    print(f"\n[mapping] 룰 있는 개념: {df['has_rule'].sum()}/{len(df)}")
    for level in ("process", "subprocess", "device"):
        sub = df.loc[level]
        print(f"           {level:11} {sub['has_rule'].sum()}/{len(sub)}")
    gaps = df[~df["has_rule"]]
    if len(gaps):
        print(f"\n[mapping] 룰 없는 개념 {len(gaps)}개 — 텍스트 매칭 경로가 필요하다:")
        for level, label in gaps.index:
            print(f"           - {level}/{label}")


if __name__ == "__main__":
    main()
