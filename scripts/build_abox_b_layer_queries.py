#!/usr/bin/env python3
"""CR-012 ⓐ+ⓑ (+CR-014) — B층 확증분할 질의 200건을 별도 A-Box 파일로 세운다.

CR-014 로 서지 두 칸(publicationNumber·publicationDate)이 들어왔다. 하류가 요구한 셋 중
processFamily·valueChainStage 는 **채우지 않는다** — 원천이 없고, 추정하면 하류 T2 의
공정군 하위집단이 A/B 서로 다른 규칙으로 만든 축을 비교하게 된다. 근거는 리포트의
`cr014_bibliographic.unfilled_reason` 에 수치와 함께 남는다.

## 왜 `build_abox_patents.py` 를 고치지 않고 새 생성기인가 — ⓑ 가 요구하는 것이 파일이다

CR-012 요구 ⓑ 는 "A층과 B층을 그래프만으로 가르는 분리 표지"이고, 성질 셋 중 하나가
**T-Box 술어를 늘리지 않는 형태를 우선**한다. 층 구분을 **파일**로 주면 새 술어가 0 이고
(델타 유형 ①이 아니다), 하류는 파일 하나를 읽는 것만으로 200 건을 가른다.

여기에 이 저장소 고유의 이유가 하나 더 붙는다. `~/Dev/sdkb` 는 **공개되는 기반 온톨로지**이고
B층 200 은 **논문 확증분할의 봉인 질의**다 — 반도체 도메인 지식이 아니라 평가 자산이다.
같은 파일에 섞으면 공개본을 정리할 때 다시 갈라내야 한다. 파일을 나누면 그 작업이 사라진다.

## IRI 규칙은 A층과 같다 — 그리고 그것이 청구항 경로를 공짜로 연다

    https://w3id.org/sdkb/data/patent/kr_{출원번호}

A층 질의 1,000 과 **같은 규칙**이다(CR-012 §4ⓐ). 그래서 청구항 사이드카에서도
`build_abox_claim_features.py::_patent_iri()` 의 기존 분기 `rej:{출원번호}` 가 그대로
해소한다 — 해소 코드를 한 줄도 고치지 않는다.

## 만들지 않는 것 (CR-012 §5 비목표)

  ⓐ 인용 간선 3종(hasPriorArtExaminer·hasPriorArt·overPriorArt) — 상류에 두면 하류 봉인이
     무의미해진다. 이 파일에는 **한 건도 없다**(검증기준 ④).
  ⓔ rejectedFor·거절근거 — 이번 범위는 질의 노드와 그 청구항뿐이다.
  그리고 출원인 Organization 노드도 만들지 않는다 — 공개 그래프에 논문 평가용 노드를
  늘리지 않기 위해서다. 하류 코퍼스는 출원인을 쓰지 않는다.

## 개념 링크의 A/B 비대칭 — 숨기지 않고 센다

A층은 통로가 둘이다: ① 큐레이터가 붙인 `process_family` 구조화 브리지 ② 자유텍스트 추출.
B층 원천(KIPRIS)에는 ①의 입력이 **없다**. 추정해서 채우면 같은 이름의 다른 것이 되므로
(CLAUDE.md §1.3) **②만 적용하고 비대칭을 리포트에 수치로 남긴다.**

입력 : data/patents/b_layer_queries_raw.jsonl  (collect_b_layer_queries.py)
출력 : ontology/sdkb-abox-b-layer-queries.ttl   (**gitignore** — 빌드 산출물)
       data/reports/abox_b_layer_queries_report.json  (집계만 · 커밋)

결정적. 같은 입력 → 같은 그래프(타임스탬프·난수 없음).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS as _DCTERMS, OWL, RDF, RDFS, SKOS, XSD  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sdkb_nb as S  # noqa: E402

# A층 생성기의 상수를 **가져다 쓴다** — 복사하면 두 파일이 갈라진다.
from build_abox_patents import (  # noqa: E402
    KIPRIS_SOURCE,
    PATENT_LICENSE,
    PATENT_ROUTING,
    _u,
)

IN_JSONL = ROOT / "data" / "patents" / "b_layer_queries_raw.jsonl"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-b-layer-queries.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_b_layer_queries_report.json"

ONT = S.ONT
DCTERMS = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# 이 A-Box 를 만든 적재 활동. 클래스는 기존 prov:Activity 이고 새 어휘가 아니다 —
# A층(activity/sirp_ingest)과 **다른 인스턴스**라 출처가 파일 안에서도 갈린다.
INGEST_ACTIVITY = "activity/b_layer_query_ingest"

# 인용 간선 3종. 이 파일이 한 건도 만들지 않음을 빌드 시점에 스스로 확인한다(검증기준 ④).
FORBIDDEN_PREDICATES = ("hasPriorArtExaminer", "hasPriorArt", "overPriorArt")


def _ipc_codes(raw: str) -> list[str]:
    return [c.strip() for c in str(raw or "").split("|") if c.strip()]


def _ipc4_share(counter: Counter, top: int = 10) -> list[dict]:
    total = sum(counter.values())
    return [{"ipc4": k, "count": v, "share": round(v / total, 4) if total else 0.0}
            for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]


def _a_layer_ipc4() -> Counter:
    """A층 질의 1,000 의 IPC4 분포. 비교 대상이 없으면 B층 수치는 해석할 수 없다."""
    import pandas as pd

    meta_path = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
    out: Counter = Counter()
    if not meta_path.exists():
        return out
    for v in pd.read_parquet(meta_path, columns=["ipc_codes"])["ipc_codes"]:
        codes = v if isinstance(v, (list, tuple)) else str(v).split("|")
        for c in codes:
            c = str(c).strip()
            if c:
                out[c.split()[0][:4]] += 1
    return out


def _first_claim(claims_blob: str) -> str:
    """청구항 덩어리 → 제1항 본문. A층 firstClaimText 와 같은 의미로 채운다."""
    from decompose_claims import split_claims

    for no, txt in split_claims(str(claims_blob or "")):
        if no == 1:
            return txt
    return ""


def build() -> int:
    if not IN_JSONL.exists():
        print(f"ERROR: {IN_JSONL} 없음 — `make collect-b-layer-queries` 먼저.", file=sys.stderr)
        return 1

    rows = [json.loads(line) for line in IN_JSONL.read_text().splitlines() if line.strip()]
    if not rows:
        print("ERROR: 입력이 비었다.", file=sys.stderr)
        return 1

    try:
        br = S.make_bridge(ROOT, morph=True)
        mode = "morph(Kiwi)+substring, title+abstract+claim1"
    except SystemExit:
        br = S.make_bridge(ROOT)
        mode = "substring-only (kiwipiepy missing), title+abstract+claim1"
    print(f"  bridge mode: {mode}")

    g = Graph()
    g.bind("ont", ONT)
    g.bind("data", S.DATA)
    g.bind("dcterms", DCTERMS)
    g.bind("prov", PROV)
    g.bind("skos", str(SKOS))

    ONT_R = lambda local: URIRef(ONT + local)  # noqa: E731

    activity = _u(INGEST_ACTIVITY)
    g.add((activity, RDF.type, PROV.Activity))
    g.add((activity, RDFS.label,
           Literal("CR-012 B-layer confirmation-split query ingest", lang="en")))

    type_dist: Counter = Counter()
    matched_terms: Counter = Counter()
    text_props: Counter = Counter()
    nodes_per: list[int] = []
    n_typed = n_text_linked = 0
    n_pub_no = n_pub_dt = 0          # CR-014 — 하류 SHACL 이 세는 칸
    no_text: list[str] = []
    orphans: list[str] = []
    ipc4_b: Counter = Counter()
    exam_status: Counter = Counter()

    # 권위 원천 대조 (§1.3) — 하류가 "거절특허"라고 말한 것을 상류가 KIPRIS 에서 독립 확인한다.
    # 하나라도 어긋나면 RejectedPatent 타입이 거짓이 되므로 **세지 말고 중단**한다.
    not_rejected = [str(r["application_number"]) for r in rows
                    if str(r.get("register_status") or "") != "거절"]
    if not_rejected:
        print(f"ERROR: KIPRIS registerStatus 가 '거절'이 아닌 건 {len(not_rejected)}건 — 중단. "
              f"RejectedPatent 로 세우면 이름이 의미와 달라진다(§1.3). 예: {not_rejected[:5]}",
              file=sys.stderr)
        return 1

    # 출원번호 순서로 돈다 — 입력 순서가 바뀌어도 같은 그래프가 나와야 한다.
    for r in sorted(rows, key=lambda x: str(x["application_number"])):
        an = str(r["application_number"])
        title = str(r.get("invention_title") or "")
        abstract = str(r.get("abstract") or "")
        claims = str(r.get("claims") or "")
        claim1 = _first_claim(claims)

        if not (title or abstract or claims):
            no_text.append(an)      # 노드를 세우지 않는다 — 검색 가능 문서가 아니다
            continue

        pu = _u(f"patent:kr_{an}")
        # RejectedPatent ⊑ Patent (TBox) — 두 타입은 모순이 아니다. 하류 조립기가
        # 질의를 세는 조건은 이 RejectedPatent 타입 **하나**다(assemble.py:131-134).
        g.add((pu, RDF.type, ONT_R("Patent")))
        g.add((pu, RDF.type, ONT_R("RejectedPatent")))
        n_typed += 1

        g.add((pu, SKOS.prefLabel, Literal(title or f"patent:kr_{an}", lang="ko")))
        g.add((pu, ONT_R("applicationNumber"), Literal(an)))
        g.add((pu, ONT_R("patentOffice"), Literal("KR")))

        # shapes_patent.ttl 의 Shape_RejectedPatent 가 요구한다(하류 bibliographic_shape 도 같다).
        # 값의 원천은 KIPRIS finalDisposal — "거절결정(재심사)" 처럼.
        exam = str(r.get("examination_status") or "")
        if exam:
            g.add((pu, ONT_R("examinationStatus"), Literal(exam, datatype=XSD.string)))
            exam_status[exam] += 1

        fd = str(r.get("filing_date") or "")
        if fd:
            g.add((pu, ONT_R("filingDate"), Literal(fd, datatype=XSD.date)))

        # CR-014 — 공개번호·공개일. 하류 bibliographic_shape 가 RejectedPatent 마다
        # publicationNumber 를 요구한다(위반 200). 값은 KIPRIS openNumber(공개번호)이고
        # A층 ont:publicationNumber(=SIRP unex_pub_number)와 **같은 의미의 같은 형식**이다.
        # 리터럴은 평문으로 둔다 — A층과 term 이 달라지면 같은 술어가 두 모양을 갖는다
        # (build_abox_patents.py 의 같은 이유 주석 참조).
        pn = str(r.get("publication_number") or "")
        if pn:
            g.add((pu, ONT_R("publicationNumber"), Literal(pn)))
            n_pub_no += 1
        # 공개일은 CR-014 §5-5(선택·강하게 권장) — 채워지면 하류가 B층 문서를 시점 필터로
        # 거를 수 있다. 하류는 이것에 의존하지 않는다.
        pdt = str(r.get("publication_date") or "")
        if pdt:
            g.add((pu, ONT_R("publicationDate"), Literal(pdt, datatype=XSD.date)))
            n_pub_dt += 1

        for code in _ipc_codes(r.get("ipc_codes")):
            ipc4_b[code.split()[0][:4]] += 1
            sym = _u(f"ipc/{code.replace(' ', '_').replace('/', '-')}")
            g.add((sym, RDF.type, ONT_R("IPCSymbol")))
            g.add((sym, SKOS.notation, Literal(code, datatype=XSD.string)))
            g.add((pu, ONT_R("hasIPC"), sym))

        for value, prop in ((abstract, "abstractText"), (claim1, "firstClaimText")):
            if value:
                g.add((pu, ONT_R(prop), Literal(value)))
                text_props[prop] += 1

        g.add((pu, DCTERMS.source, Literal(KIPRIS_SOURCE, datatype=XSD.string)))
        g.add((pu, DCTERMS.license, Literal(PATENT_LICENSE, datatype=XSD.string)))
        g.add((pu, PROV.wasGeneratedBy, activity))

        # 개념 링크 — 자유텍스트 통로만. A층의 구조화 브리지(process_family)는 입력이 없다.
        # 추출 규칙·라우팅·hf 대소문자 처리는 전부 A층과 같은 함수를 쓴다.
        text = f"{title} {abstract} {claim1}"
        linked: set[str] = set()
        for term, hits in S.resolve_hf_case(br.extract_from_text(text), text).items():
            for nid, typ in hits:
                prop = PATENT_ROUTING.get(typ)
                if not prop:
                    continue
                if nid not in linked:
                    g.add((pu, ONT_R(prop), _u(nid)))
                    type_dist[typ] += 1
                linked.add(nid)
            if hits:
                matched_terms[term] += 1
        if linked:
            n_text_linked += 1
        else:
            orphans.append(an)
        nodes_per.append(len(linked))

    # 비목표 ⓐ 의 자체 확인 — 만들지 않았다고 적는 대신 만들지 않았음을 센다.
    leaked = {p: sum(1 for _ in g.triples((None, ONT_R(p), None))) for p in FORBIDDEN_PREDICATES}
    if any(leaked.values()):
        print(f"ERROR: 인용 간선이 새어 들어갔다 — {leaked}", file=sys.stderr)
        return 1

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    n = n_typed
    report = {
        "cr": "CR-012",
        "input": str(IN_JSONL.relative_to(ROOT)),
        "output": str(OUT_TTL.relative_to(ROOT)),
        "rows_in": len(rows),
        "typed_RejectedPatent": n_typed,
        "skipped_no_text": no_text,
        "triples": len(g),
        "text": dict(text_props),
        "examination_status": dict(exam_status),
        # CR-014 — 하류 pat:RejectedPatentContentShape 가 요구하는 서지 여섯 중 셋이 비어
        # L1 이 막혔다(위반 600 = 200 × 3). 채운 것과 **채우지 않은 것**을 같은 자리에 적는다.
        "cr014_bibliographic": {
            "publicationNumber": n_pub_no,
            "publicationDate": n_pub_dt,
            "processFamily": 0,
            "valueChainStage": 0,
            "unfilled_reason":
                "processFamily·valueChainStage 는 특허의 속성이 아니라 A층 SIRP 코호트의 "
                "수집 출처다 — 값의 원천은 KIPRIS 가 아니라 '어느 검색 전략(키워드 게이트+IPC)이 "
                "그 특허를 건졌는가'이며(paper_data/scripts/expand_dataset_via_api.py), "
                "B층 200 은 다른 절차(IPC 스트림 스크리닝)로 뽑혀 그 라벨이 존재하지 않는다. "
                "A층 parquet·SIRP 원본과의 교집합도 0 건이라 조인으로 가져올 수도 없다. "
                "IPC·개념링크로 추정해 채우면 ① 같은 이름의 다른 것이 되고(§1.3) "
                "② 하류 T2 하위집단의 '공정군' 축이 A/B 서로 다른 규칙으로 만든 층을 "
                "비교하게 된다 — 비어 있는 것보다 나쁘다. 그래서 채우지 않는다.",
            "downstream_action":
                "하류가 prov:wasGeneratedBy activity/b_layer_query_ingest 를 조건으로 한 "
                "sh:or 로 이 두 칸을 면제한다(CR-012 가 인용 minCount 에 쓴 패턴과 같다). "
                "A층 1,000 에 걸린 계약은 풀리지 않는다.",
        },
        "register_status_verified_rejected": len(rows) - len(not_rejected),
        "forbidden_predicate_triples": leaked,
        "concept_links": {
            "bridge_mode": mode + " (free-text ONLY — no structured process_family bridge)",
            "patents_with_link": n_text_linked,
            "orphans": len(orphans),
            "nodes_per_patent_mean": round(sum(nodes_per) / n, 3) if n else 0,
            "by_node_type": dict(type_dist.most_common()),
            "top_matched_terms": [
                {"term": t, "patents": c}
                for t, c in sorted(matched_terms.items(), key=lambda kv: (-kv[1], kv[0]))[:40]
            ],
            "asymmetry_note": "A층은 process_family 구조화 브리지 + 자유텍스트 두 통로를 쓴다. "
                              "B층 원천(KIPRIS)에는 process_family 가 없어 자유텍스트만 적용했다. "
                              "추정으로 채우지 않는다 — 같은 이름의 다른 것이 된다(§1.3). "
                              "하류는 이 수치를 A층 문서당 개념 수와 나란히 놓고 판단한다.",
        },
        "topical_composition": {
            "b_layer_ipc4_top": _ipc4_share(ipc4_b),
            "a_layer_ipc4_top": _ipc4_share(_a_layer_ipc4()),
            "note": "두 층의 IPC4 구성이 다르면 개념링크 밀도 차이는 온톨로지 결함이 아니라 "
                    "질의 화제의 차이다. 어느 쪽인지는 이 표와 위 concept_links 를 함께 봐야 "
                    "가려지므로 둘을 같은 리포트에 싣는다. 하류가 확증분할의 교환가능성을 "
                    "판단할 때 쓰는 재료다.",
        },
        "note": "층 구분은 파일 분리로 준다(CR-012 ⓑ). T-Box 델타 0 · 새 술어 0 · 새 클래스 0.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"✓ B-layer query A-Box ({len(g):,} triples) → {OUT_TTL.relative_to(ROOT)}")
    print(f"  RejectedPatent={n_typed}  text={dict(text_props)}  본문없어 제외={len(no_text)}")
    print(f"  서지(CR-014): publicationNumber={n_pub_no}/{n}  publicationDate={n_pub_dt}/{n}  "
          f"processFamily=0  valueChainStage=0 (원천 없음 — 회신 참조)")
    print(f"  개념링크: 보유 {n_text_linked}/{n}  고아 {len(orphans)}  "
          f"평균 {report['concept_links']['nodes_per_patent_mean']}개/문서 (자유텍스트만)")
    print(f"  인용 간선: {leaked}  ← 전부 0 이어야 한다(비목표 ⓐ)")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
