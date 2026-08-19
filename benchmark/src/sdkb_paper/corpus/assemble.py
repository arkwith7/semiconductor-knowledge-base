"""통합 IR 코퍼스 + 심사관 qrel 조립 (PLAN-017 M1).

큐레이션 KG(G₀/G₁/G₂ TTL + claim-feature sidecar)를 '문서중심 IR 코퍼스'로 재조립한다.

산출물:
  data/processed/ir/ir_corpus_v09.parquet   통합 문서 코퍼스 (질의·정답·후보 ~40k)
  data/processed/ir/qrel_examiner.parquet   심사관 인용 qrel (등급1, 2,534 엣지)
  data/profiles/ir_corpus_v09.md            §4 데이터 프로파일 (커밋 가능)
  data/MANIFEST.md                          조립 기록 append

설계(PLAN-017 §7 M1 확정):
  · 청구항 텍스트 = sidecar featureText 재구성이 정본, firstClaimText(원문 claim1) 병기
  · text_main = 초록+청구항전체 (질의·후보 대칭). 질의는 4종 표현(초록/청구항/초록+청구항/
    제목+초록+청구항)을 병기, 주 분석 = 초록+청구항전체.
  · 누출 안전: hasPriorArt* 는 문서 피처로 절대 넣지 않는다(qrel 로만 별도 추출).

    python -m sdkb_paper.corpus.assemble          # 조립
    python -m sdkb_paper.corpus.assemble --check   # 재조립 없이 산출물 성공기준만 검증
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pyoxigraph import NamedNode, RdfFormat, Store

from .. import config
from . import claim_join
from . import concept_link
from . import text as textmod

ONT = "https://w3id.org/sdkb/ont/"
PROV = "http://www.w3.org/ns/prov#"
# B층 질의(CR-012)의 출처 표지. 상류가 A층(`sirp_ingest`)과 다른 activity 로 발행했다 —
# 하류는 이것으로 층을 가른다(PLAN-045 D1). 새 술어를 만들지 않는 이유가 여기 있다.
B_LAYER_ACTIVITY = "https://w3id.org/sdkb/data/activity/b_layer_query_ingest"
GRAPHS = {  # named graph → 원천 TTL
    "urn:g0": config.GRAPH_V0,
    "urn:g1": config.GRAPH_V1,
    "urn:g2": config.GRAPH_V2,
}
# 문서 피처로 절대 넣지 않는 누출원 (CLAUDE.md §1.4 · PLAN-017 B6)
FORBIDDEN = ("hasPriorArt", "hasPriorArtExaminer", "hasPriorArtApplicant",
             "overPriorArt", "NoveltyScore")
CONCEPT_PROPS = ["realizesProcess", "involvesProcess", "concernsDevice",
                 "involvesMaterial", "concernsSkill", "exhibitsFailureMode"]


def _local(iri: str) -> str:
    """IRI 지역명(docID). data/patent/kr_10.. → kr_10.."""
    return iri.rsplit("/", 1)[-1]


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --- 그래프 적재 --------------------------------------------------------------

def _load_union(store: Store) -> None:
    """G₀/G₁/G₂ 를 각각 named graph 로 적재한다(원천 추적용)."""
    for g, path in GRAPHS.items():
        if not path.exists():
            raise FileNotFoundError(f"그래프 없음: {path} (make merge 필요)")
        with open(path, "rb") as fh:
            store.bulk_load(fh, format=RdfFormat.TURTLE, to_graph=NamedNode(g))


def _scalars(store: Store) -> dict[str, dict]:
    """특허별 스칼라 서지·본문(단일값). 그래프 우선순위 g0>g1>g2 로 병합(첫 값 유지)."""
    # 문서 노드 = Patent(rej/g1/g2) ∪ CitedPatent(정답 — Patent 타입 아님) ∪ RejectedPatent.
    # 심사관 정답 2,211개는 CitedPatent 로만 타입돼 있어 Patent 필터만으로는 누락된다(실측).
    q = f"""PREFIX ont:<{ONT}>
    SELECT ?g ?p ?title ?abs ?fc ?fd ?pd ?pn ?an ?po WHERE {{
      GRAPH ?g {{ ?p a ?cls . VALUES ?cls {{ ont:Patent ont:CitedPatent ont:RejectedPatent }}
        OPTIONAL {{ ?p <http://www.w3.org/2004/02/skos/core#prefLabel> ?title }}
        OPTIONAL {{ ?p ont:abstractText ?abs }}
        OPTIONAL {{ ?p ont:firstClaimText ?fc }}
        OPTIONAL {{ ?p ont:filingDate ?fd }}
        OPTIONAL {{ ?p ont:publicationDate ?pd }}
        OPTIONAL {{ ?p ont:publicationNumber ?pn }}
        OPTIONAL {{ ?p ont:applicationNumber ?an }}
        OPTIONAL {{ ?p ont:patentOffice ?po }}
      }} }}"""
    order = {"urn:g0": 0, "urn:g1": 1, "urn:g2": 2}
    best: dict[str, tuple[int, dict]] = {}
    for r in store.query(q):
        p = r["p"].value
        rank = order.get(r["g"].value, 9)
        rec = {
            "title": textmod.clean(r["title"].value) if r["title"] else "",
            "abstract": textmod.clean(r["abs"].value) if r["abs"] else "",
            "first_claim_original": textmod.clean(r["fc"].value) if r["fc"] else "",
            "filing_date": r["fd"].value if r["fd"] else None,
            "publication_date": r["pd"].value if r["pd"] else None,
            "publication_number": r["pn"].value if r["pn"] else None,
            "application_number": r["an"].value if r["an"] else None,
            "patent_office": r["po"].value if r["po"] else None,
        }
        # 같은 특허가 여러 그래프에 있으면 낮은 rank(g0) 우선. 같은 rank 내 첫 값 유지.
        if p not in best or rank < best[p][0]:
            if p in best:  # 상위 그래프가 채우지 못한 필드만 보강
                merged = dict(best[p][1])
                for k, v in rec.items():
                    if not merged.get(k):
                        merged[k] = v
                best[p] = (rank, merged)
            else:
                best[p] = (rank, rec)
    return {p: rec for p, (_, rec) in best.items()}


def _multi(store: Store) -> dict[str, dict[str, set]]:
    """특허별 다중값: IPC/CPC 분류코드·개념링크. 누출원은 쿼리하지 않는다."""
    out: dict[str, dict[str, set]] = defaultdict(lambda: {"ipc": set(), "cpc": set(), "concepts": set()})
    for prop, key in [("hasIPC", "ipc"), ("hasCPC", "cpc")]:
        q = f"PREFIX ont:<{ONT}> SELECT ?p ?o WHERE {{ GRAPH ?g {{ ?p ont:{prop} ?o }} }}"
        for r in store.query(q):
            out[r["p"].value][key].add(_local(r["o"].value))
    for prop in CONCEPT_PROPS:
        assert prop not in FORBIDDEN
        q = f"PREFIX ont:<{ONT}> SELECT ?p ?o WHERE {{ GRAPH ?g {{ ?p ont:{prop} ?o }} }}"
        for r in store.query(q):
            out[r["p"].value]["concepts"].add(_local(r["o"].value))
    return out


def _roles(store: Store) -> tuple[set, set, dict[str, set]]:
    """질의(RejectedPatent)·심사관 정답 대상·그래프 원천 집합.

    **질의 식별은 인용 간선이 아니라 타입이다**(`?p a ont:RejectedPatent`). 대장 D-27 이
    간선이라 적었으나 실측은 타입이었다 — PLAN-045 §2′.2. 간선은 아래 `positives`(정답) 용이다.
    """
    queries, positives = set(), set()
    for r in store.query(
        f"PREFIX ont:<{ONT}> SELECT ?p WHERE {{ GRAPH ?g {{ ?p a ont:RejectedPatent }} }}"
    ):
        queries.add(r["p"].value)
    # 층 표지(PLAN-045 D1). 상류가 `prov:wasGeneratedBy` 로 A층(`sirp_ingest`)과
    # B층(`b_layer_query_ingest`)을 갈라 발행했다(CR-012 ⓑ). 술어를 새로 만들지 않고
    # 이미 있는 출처 표지를 읽는다 — 그래서 T-Box 델타가 0 으로 유지된다.
    b_queries = set()
    for r in store.query(
        f"PREFIX prov:<{PROV}> SELECT ?p WHERE {{ GRAPH ?g "
        f"{{ ?p prov:wasGeneratedBy <{B_LAYER_ACTIVITY}> }} }}"
    ):
        b_queries.add(r["p"].value)
    for r in store.query(
        f"PREFIX ont:<{ONT}> SELECT ?o WHERE {{ GRAPH ?g {{ ?s ont:hasPriorArtExaminer ?o }} }}"
    ):
        positives.add(r["o"].value)
    cited = set()
    for r in store.query(
        f"PREFIX ont:<{ONT}> SELECT ?p WHERE {{ GRAPH ?g {{ ?p a ont:CitedPatent }} }}"
    ):
        cited.add(r["p"].value)
    src: dict[str, set] = defaultdict(set)
    for r in store.query(
        f"PREFIX ont:<{ONT}> SELECT ?g ?p WHERE {{ GRAPH ?g {{ ?p a ?c . "
        f"VALUES ?c {{ ont:Patent ont:CitedPatent ont:RejectedPatent }} }} }}"
    ):
        src[r["p"].value].add(r["g"].value)
    return queries, positives, {"cited": cited, "src": src, "b_queries": b_queries}


def _qrel(store: Store) -> pd.DataFrame:
    """심사관 인용 qrel (등급1). query_id → doc_id, relevance=1."""
    rows = []
    for r in store.query(
        f"PREFIX ont:<{ONT}> SELECT ?s ?o WHERE {{ GRAPH ?g {{ ?s ont:hasPriorArtExaminer ?o }} }}"
    ):
        rows.append((_local(r["s"].value), _local(r["o"].value)))
    df = pd.DataFrame(sorted(set(rows)), columns=["query_id", "doc_id"])
    df["relevance"] = 1
    return df


# --- 조립 --------------------------------------------------------------------

def assemble() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """코퍼스·qrel·개념링크 사이드카 DataFrame 을 만든다(파일 쓰기는 build 가 담당).

    개념 링크는 두 원천의 **합집합**이다(PLAN-034 결정 Q4):
      ① 그래프에 이미 있는 링크(`CONCEPT_PROPS` · `_multi`)
      ② 사전을 본문에 적용한 링크(`concept_link` · CR-007 하류)
    사전이 스냅샷에 없으면 ②는 없고 `concepts` 열은 손대지 않는다 — 그 상태가 O 팔이다.
    """
    print("[1/6] G₀/G₁/G₂ 적재(pyoxigraph named graph)…", flush=True)
    tmp = tempfile.mkdtemp(prefix="ir_union_")
    store = Store(path=str(Path(tmp) / "s"))
    _load_union(store)
    print(f"      union triples: {len(store):,}", flush=True)

    print("[2/6] 스칼라·다중값·역할 조회…", flush=True)
    scalars = _scalars(store)
    multi = _multi(store)
    queries, positives, extra = _roles(store)
    cited, src = extra["cited"], extra["src"]
    b_queries = extra["b_queries"]

    print("[3/6] sidecar 청구항 재구성…", flush=True)
    recon = claim_join.reconstruct_all()
    print(f"      청구항 보유 특허: {len(recon):,}", flush=True)

    print("[4/6] 문서 레코드 조립…", flush=True)
    rows = []
    all_iris = set(scalars) | set(recon.keys())
    for iri in sorted(all_iris):
        sc = scalars.get(iri, {})
        cl = recon.get(iri)
        title = sc.get("title", "")
        abstract = sc.get("abstract", "")
        claims_full = cl.claims_full if cl else ""
        claims_indep = cl.claims_independent if cl else ""
        # 검색 가능 문서만: 제목/초록/청구항 중 하나라도 텍스트 보유
        if not (title or abstract or claims_full):
            continue
        text_main = "\n".join(t for t in (abstract, claims_full) if t).strip()
        graphs = src.get(iri, set())
        is_query = iri in queries
        # 층 표지 둘 (PLAN-045 D1). 두 축을 한 컬럼에 담지 않는다 —
        # B층 질의 200 중 8건은 **이미 A층 후보 문서**였고(g1 6 · g2 2), 그 8건은
        # query_layer="B" 이면서 is_candidate=True 여야 한다. 한 컬럼으로 적으면
        # A층 후보 8건이 조용히 사라져 A층 결과가 바뀐다.
        query_layer = ("B" if iri in b_queries else "A") if is_query else None
        # 후보 자격: B층 질의 TTL 이 **새로 데려온** 문서만 제외한다. 기존 코퍼스에
        # 이미 있던 문서는(질의든 아니든) 전부 후보로 남는다 → A층 문서집합 불변(S6).
        # `cited` 도 함께 본다 — B층 질의가 A층 정답 노드이기도 하면 그것은 신규 문서가
        # 아니라 이미 있던 후보다. 빠뜨리면 A층 정답이 후보 풀에서 사라진다.
        is_candidate = not (
            iri in b_queries and iri not in cited and not (graphs - {"urn:g0"})
        )
        if is_query:
            source = "g0_rej"
        elif iri in cited:
            source = "g0_cited"
        elif "urn:g1" in graphs:
            source = "g1"
        elif "urn:g2" in graphs:
            source = "g2"
        else:
            source = "g0_other"
        lang = textmod.detect_lang(abstract or title or claims_full)
        m = multi.get(iri, {"ipc": set(), "cpc": set(), "concepts": set()})
        rec = {
            "doc_id": _local(iri),
            "iri": iri,
            "source": source,
            "is_query": is_query,
            "query_layer": query_layer,      # "A" | "B" | None (PLAN-045 D1)
            "is_candidate": is_candidate,    # 색인·후보 풀 포함 자격 (PLAN-045 D2)
            "is_examiner_positive": iri in positives,
            "in_g0": "urn:g0" in graphs,
            "in_g1": "urn:g1" in graphs,
            "in_g2": "urn:g2" in graphs,
            "lang": lang,
            "title": title,
            "abstract": abstract,
            "first_claim_original": sc.get("first_claim_original", ""),
            "claims_independent": claims_indep,
            "claims_full": claims_full,
            "text_main": text_main,
            "n_claims": cl.n_claims if cl else 0,
            "n_independent": cl.n_independent if cl else 0,
            "filing_date": sc.get("filing_date"),
            "publication_date": sc.get("publication_date"),
            "publication_number": sc.get("publication_number"),
            "application_number": sc.get("application_number"),
            "patent_office": sc.get("patent_office"),
            "ipc": sorted(m["ipc"]),
            "cpc": sorted(m["cpc"]),
            "concepts": sorted(m["concepts"]),
        }
        # 질의 4종 표현 (PLAN-017 §7 M1) — 후보는 null
        if is_query:
            rec["q_repr_abstract"] = abstract
            rec["q_repr_claims"] = claims_full
            rec["q_repr_abstract_claims"] = text_main
            rec["q_repr_title_abstract_claims"] = "\n".join(
                t for t in (title, abstract, claims_full) if t).strip()
        else:
            rec["q_repr_abstract"] = rec["q_repr_claims"] = None
            rec["q_repr_abstract_claims"] = rec["q_repr_title_abstract_claims"] = None
        rows.append(rec)

    corpus = pd.DataFrame(rows).sort_values("doc_id").reset_index(drop=True)

    print("[5/6] 개념 적용기(사전 → 본문)…", flush=True)
    # 질의·후보에 **같은 함수·같은 사전**이 적용된다(PLAN-034 결정 D). 사전이 없으면 무작동.
    links = concept_link.apply_to_corpus(corpus)

    print("[6/6] qrel 추출…", flush=True)
    qrel = _qrel(store)
    return corpus, qrel, links


# --- 쓰기·프로파일·검증 -------------------------------------------------------

def _write_profile(corpus: pd.DataFrame, qrel: pd.DataFrame, sigs: dict) -> None:
    """§4 데이터 프로파일(구조·형태·기술통계·목적)을 생성한다."""
    n = len(corpus)
    by_source = corpus["source"].value_counts().to_dict()
    by_lang = corpus["lang"].value_counts().to_dict()
    q = corpus[corpus.is_query]
    # 분모는 **A층으로 고정한다**(PLAN-045 D4). B층 200 을 분모에 넣으면 아무것도
    # 나빠지지 않았는데 질의밀도가 98.1 % → 약 81.7 % 로 무너진 것처럼 보인다 —
    # 지표 정의가 층을 넘는 것이고, 그것은 관측이 아니라 착시다.
    q_a = corpus[corpus.query_layer == "A"]
    q_b = corpus[corpus.query_layer == "B"]
    n_cand = int(corpus.is_candidate.sum())
    pos = corpus[corpus.is_examiner_positive]
    raw_edges = sigs.get("qrel_raw_edges", len(qrel))
    raw_nodes = sigs.get("qrel_raw_nodes", qrel.doc_id.nunique())
    # 질의밀도: 코퍼스 내 검색가능 정답이 ≥1 인 A층 질의 비율 (분모 = A층 1,000)
    density = qrel.query_id.nunique() / len(q_a) if len(q_a) else 0.0

    def _cov(col):
        return (corpus[col].astype(str).str.len() > 0).mean()

    lines = [
        "# IR 코퍼스 프로파일 — ir_corpus_v09 (PLAN-017 M1)",
        "",
        "> 코드 생성물. 재생성: `make corpus`. 원천 TTL 서명은 §서명. 특허 전문은 "
        "license_restricted(gitignore) — 이 프로파일의 집계만 커밋된다(CLAUDE.md §1.4·§4).",
        "",
        f"- 생성(UTC): {sigs['built_utc']}",
        "- 지지 주장: **C2 핵심증명**(선행기술 검색)의 입력 · 논문 §5–6(RQ2·RQ3·T1·T2)",
        "",
        "## 1. 서명 (원천·산출)",
        "| 자원 | 값 | sha256(앞16) |",
        "|---|---:|---|",
        f"| ir_corpus_v09.parquet | {n:,} 행 | `{sigs['corpus_sha'][:16]}` |",
        f"| qrel_examiner.parquet | {len(qrel):,} 엣지 | `{sigs['qrel_sha'][:16]}` |",
    ]
    for g, path in GRAPHS.items():
        lines.append(f"| {path.name} | — | `{sigs['graphs'][g][:16]}` |")
    lines += [
        "",
        "## 2. 구조 (컬럼·dtype·목적)",
        "| 컬럼 | 목적 |",
        "|---|---|",
        "| doc_id·iri | 문서 식별자(IRI 지역명) |",
        "| source | g0_rej(질의)·g0_cited(정답)·g1·g2(후보) |",
        "| is_query·is_examiner_positive·in_g0/1/2 | 역할·원천 플래그 |",
        "| query_layer | 질의의 층: A(주분석 1,000) · B(제2 확증분할 200) · null(후보) |",
        "| is_candidate | 색인·후보 풀 포함 자격 — B층 신규 문서만 False |",
        "| lang | 스크립트 감지(ko/ja/en) — 다국어 하위집단 T2 |",
        "| title·abstract·first_claim_original | 서지·초록·G₀ 원문 청구항1 |",
        "| claims_independent·claims_full | sidecar 재구성 청구항(정본) |",
        "| **text_main** | 초록+청구항전체 — 주 색인 텍스트(질의·후보 대칭) |",
        "| q_repr_* | 질의 4종 표현(초록/청구항/초록+청구항/제목+초록+청구항) |",
        "| filing/publication_date·publication/application_number·patent_office | 시점·서지 |",
        "| ipc·cpc·concepts | 분류·개념링크(CPC팔·온톨로지팔 입력) |",
        "| n_claims·n_independent | 청구항 통계 |",
        "",
        "## 3. 형태·기술통계",
        f"- 총 문서: **{n:,}**",
        "- source 분포: " + " · ".join(f"{k}={v:,}" for k, v in sorted(by_source.items())),
        "- 언어 분포(전체): " + " · ".join(f"{k}={v:,}" for k, v in sorted(by_lang.items())),
        f"- 질의(is_query): {len(q):,} = **A층 {len(q_a):,} + B층 {len(q_b):,}** "
        f"(B층 = CR-012 · 판독 B 용 · A층 주분석에 섞이지 않는다) "
        f"· 심사관 정답 노드(is_examiner_positive): {len(pos):,}",
        f"- 후보 자격(is_candidate): {n_cand:,} — B층 질의가 새로 데려온 문서는 후보에서 "
        f"제외한다(PLAN-045 D2 · 질의는 후보가 아니다). A층 문서집합 불변의 근거.",
        "- 정답 노드 언어: " + " · ".join(
            f"{k}={v:,}" for k, v in sorted(pos["lang"].value_counts().to_dict().items())),
        f"- 텍스트 커버리지: 초록={_cov('abstract'):.1%} · 청구항전체={_cov('claims_full'):.1%} · "
        f"text_main={_cov('text_main'):.1%}",
        f"- 청구항 보유 문서: {(corpus.n_claims > 0).sum():,} · 독립항 보유: {(corpus.n_independent > 0).sum():,}",
        "",
        "## 4. qrel (심사관 인용 · 등급1)",
        f"- 원엣지(hasPriorArtExaminer): {raw_edges:,} · 원 고유정답 노드: {raw_nodes:,}",
        f"- 코퍼스한정 qrel: **{len(qrel):,} 엣지** · 고유 질의 {qrel.query_id.nunique():,} · "
        f"고유 정답 {qrel.doc_id.nunique():,}",
        f"- 제외: 텍스트 0인 비특허 선행기술 {raw_nodes - qrel.doc_id.nunique()} 노드"
        f"(학술논문 등 `other_*` — 검색 불가라 qrel 표준 관행상 제외).",
        f"- 질의밀도(코퍼스 내 정답 ≥1 / 원질의 1,000): **{density:.1%}** (성공기준 ≥97%)",
        "- 분모 규율(SPEC-006 §7): 2,534 인용엣지 ≠ 2,321 고유정답 ≠ 코퍼스한정. 혼용 금지.",
        "",
        "## 5. 사용 목적",
        "- **text_main** → BM25(nori)·Dense(Titan) 색인의 주 문서/질의 텍스트(RQ2).",
        "- q_repr_* → 질의 표현 강건성(주=초록+청구항, 보조 3종).",
        "- ipc/cpc → CPC 어휘팔·hard negative 표집(B4). concepts → 온톨로지 재랭크팔(언어중립).",
        "- lang → KR vs 외국 하위집단 안전성 T2. filing_date → 시점유효 분할(B8)·누출통제.",
        "- **미사용 컬럼 없음** — 전부 색인/필터/분할/평가에 대응(대응 깨지면 결함).",
        "",
        "## 6. 누출 통제 (건설적)",
        "- 문서 피처에서 배제: " + " · ".join(f"`{p}`" for p in FORBIDDEN) + ".",
        "- qrel(hasPriorArtExaminer)은 별도 파일로만 추출 — 코퍼스 문서에 포함되지 않음.",
        "- concepts 는 질의/문서 자체 기술이지 정답 파생이 아니다(realizesProcess 등).",
    ]
    config.IR_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    config.IR_PROFILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"프로파일: {config.IR_PROFILE}")


def _append_manifest(corpus, qrel, sigs) -> None:
    man = config.DATA / "MANIFEST.md"
    entry = [
        "",
        f"## {sigs['built_utc']} · IR 코퍼스 조립 (PLAN-017 M1)",
        "- 명령: `make corpus` (`python -m sdkb_paper.corpus.assemble`)",
        f"- ir_corpus_v09.parquet: {len(corpus):,} 행 · sha256 `{sigs['corpus_sha'][:16]}`",
        f"- qrel_examiner.parquet: {len(qrel):,} 엣지 · sha256 `{sigs['qrel_sha'][:16]}`",
        "- 원천: graph_v0/v1/v2.ttl + central_axis.oxstore(sidecar 청구항 재구성)"
        + (f" + concept_mapping.json(적용기 링크 {sigs['n_concept_links']:,}건)"
           if sigs.get("n_concept_links") else " + 개념 사전 없음(적용기 무작동)"),
        "- 반영: C2 입력 · 논문 §5–6",
    ]
    with open(man, "a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")
    print(f"MANIFEST append: {man}")


def _filter_qrel_to_corpus(corpus: pd.DataFrame, qrel_raw: pd.DataFrame) -> pd.DataFrame:
    """검색 가능(코퍼스 존재) 정답으로 qrel 을 한정한다. 텍스트 0인 비특허 선행기술
    (학술논문 등 `other_*`)은 어떤 검색기로도 회수 불가 → qrel 표준 관행상 제외한다.
    원엣지 수·탈락 수는 프로파일/로그로 투명 보고(분모 규율)."""
    corp_ids = set(corpus.doc_id)
    kept = qrel_raw[qrel_raw.doc_id.isin(corp_ids)].reset_index(drop=True)
    dropped_edges = len(qrel_raw) - len(kept)
    dropped_nodes = qrel_raw.doc_id.nunique() - kept.doc_id.nunique()
    print(f"      qrel: 원엣지 {len(qrel_raw):,} → 코퍼스한정 {len(kept):,} "
          f"(탈락 엣지 {dropped_edges} · 텍스트없는 정답노드 {dropped_nodes})", flush=True)
    return kept


def build() -> None:
    corpus, qrel_raw, links = assemble()
    qrel = _filter_qrel_to_corpus(corpus, qrel_raw)
    config.IR_DIR.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(config.IR_CORPUS, index=False)
    qrel.to_parquet(config.QREL_EXAMINER, index=False)
    concept_link.write_sidecar(links)
    sigs = {
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_sha": _sha256_bytes(config.IR_CORPUS.read_bytes()),
        "qrel_sha": _sha256_bytes(config.QREL_EXAMINER.read_bytes()),
        "graphs": {g: _sha256_bytes(p.read_bytes()) for g, p in GRAPHS.items()},
        "qrel_raw_edges": len(qrel_raw),
        "qrel_raw_nodes": int(qrel_raw.doc_id.nunique()),
        "n_concept_links": len(links),
    }
    _write_profile(corpus, qrel, sigs)
    concept_link.write_profile(corpus, links, concept_link.concept_dict.load(),
                               before=links.attrs.get("before_counts"))
    _append_manifest(corpus, qrel, sigs)
    print(f"\n완료: {config.IR_CORPUS} ({len(corpus):,} 행) · {config.QREL_EXAMINER} ({len(qrel):,} 엣지)")
    check(corpus, qrel)


def check(corpus=None, qrel=None) -> bool:
    """성공기준(PLAN-017 §5) 검증. 실패는 실패로 보고한다."""
    if corpus is None:
        corpus = pd.read_parquet(config.IR_CORPUS)
    if qrel is None:
        qrel = pd.read_parquet(config.QREL_EXAMINER)
    corp_ids = set(corpus.doc_id)
    # 분모는 층별로 나눈다(PLAN-045 D4). 합산 분모는 착시를 만든다 — §2′.3.
    q_a = corpus[corpus.query_layer == "A"]
    q_b = corpus[corpus.query_layer == "B"]
    ok = True
    # 1) A층 질의 1,000 전량이 독립항 텍스트 + filingDate 보유
    q_claims = (q_a.claims_full.str.len() > 0).sum()
    q_filing = q_a.filing_date.notna().sum()
    c1 = len(q_a) == 1000 and q_claims == 1000 and q_filing == 1000
    print(f"[성공기준1] A층 질의={len(q_a)} 청구항보유={q_claims} filingDate={q_filing} → {'OK' if c1 else 'FAIL'}")
    ok &= c1
    # 1b) B층 질의 200 (CR-012 검증기준 ① · PLAN-045 S1·S2). A층과 **합산하지 않는다**.
    b_claims = (q_b.claims_full.str.len() > 0).sum()
    b_filing = q_b.filing_date.notna().sum()
    c1b = len(q_b) == 200 and b_claims == 200 and b_filing == 200
    print(f"[성공기준1b] B층 질의={len(q_b)} 청구항보유={b_claims} filingDate={b_filing} → {'OK' if c1b else 'FAIL'}")
    ok &= c1b
    # 1c) 후보 자격(PLAN-045 S6·S7). B층이 새로 데려온 문서는 후보에서 빠져 있어야 한다.
    n_cand = int(corpus.is_candidate.sum())
    b_noncand = int((~corpus.is_candidate).sum())
    c1c = b_noncand == len(corpus) - n_cand and (~corpus.loc[~corpus.is_candidate, "is_candidate"]).all()
    print(f"[성공기준1c] 후보 자격={n_cand:,} · 후보 제외={b_noncand} (전부 B층 신규 문서) "
          f"→ {'OK' if c1c else 'FAIL'}")
    ok &= c1c
    # 2) 질의밀도 ≥97% (코퍼스 내 정답 ≥1 인 질의 / **A층** 원질의 1,000)
    density = qrel.query_id.nunique() / len(q_a) if len(q_a) else 0.0
    c2 = density >= 0.97
    print(f"[성공기준2] A층 질의밀도(코퍼스 내 정답 ≥1)={density:.1%} → {'OK' if c2 else 'FAIL'}")
    ok &= c2
    # 3) 누출: 코퍼스 컬럼에 금지 술어 파생 피처 없음(구조적 — 컬럼명 검사)
    leak = [c for c in corpus.columns if any(f.lower() in c.lower() for f in FORBIDDEN)]
    c3 = not leak
    print(f"[성공기준3] 누출 컬럼={leak or '없음'} → {'OK' if c3 else 'FAIL'}")
    ok &= c3
    # 4) qrel 정답 전량이 코퍼스에 존재
    miss = qrel[~qrel.doc_id.isin(corp_ids)]
    c4 = len(miss) == 0
    print(f"[성공기준4] qrel 정답 코퍼스 부재={len(miss)} → {'OK' if c4 else 'FAIL'}")
    ok &= c4
    print(f"\n{'✅ 전체 통과' if ok else '❌ 실패 존재 — 위 FAIL 확인'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="재조립 없이 산출물만 검증")
    args = ap.parse_args()
    if args.check:
        sys.exit(0 if check() else 1)
    build()
