#!/usr/bin/env python3
"""KSIA(한국반도체산업협회) 회원사 명부를 ont:Vendor A-Box 로 올린다.

SDKB 의 벤더 축은 16개뿐이었다 — 소부장(소재·부품·장비) 생태계를 표현하기에 너무 얕다.
KSIA 회원사 명부(329개사)는 국내 반도체 밸류체인의 권위 있는 공개 명부이고, 업체구분
(장비·재료·부분품·설계·소자/파운드리 …)이 곧 밸류체인 역할이다.

■ 정체성 해소 (중복 노드를 만들지 않는다)
  회원사 일부는 **이미 그래프에 있다** — 특허 출원인(ont:Organization)으로. 삼성전자·
  SK하이닉스가 그렇다. 이들에게 새 Vendor 노드를 따로 만들면 같은 회사가 두 개의 IRI 로
  쪼개진다. 그래서 이름을 정규화해 대조하고, 이미 있는 노드에는 **rdf:type ont:Vendor 를
  더할 뿐** 새 IRI 를 만들지 않는다.

■ 정직한 한계 (리포트에 남긴다)
  대부분의 회원사는 providedBy(장비→벤더)·madeBy(소재→벤더) 엣지가 **없다**. 무엇을
  공급하는지가 명부에 없기 때문이다. 그런 벤더는 그래프에서 고립 노드다. 공급관계는
  별도 수집이 필요하며 이 적재의 범위 밖이다 — 지어내지 않는다.

Inputs:
  data/vendors/ksia_member_industry_list_20260714.csv
  ontology/sdkb-core-data.ttl        (기존 Vendor 16)
  ontology/sdkb-abox-patents.ttl     (기존 Organization = 특허 출원인)
Outputs:
  ontology/sdkb-abox-vendors.ttl
  data/reports/abox_vendors_report.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
CSV = ROOT / "data" / "vendors" / "ksia_member_industry_list_20260714.csv"
CORE_DATA = ROOT / "ontology" / "sdkb-core-data.ttl"
ABOX_PATENTS = ROOT / "ontology" / "sdkb-abox-patents.ttl"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-vendors.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_vendors_report.json"

# sdkb_nb.ONT / .DATA 는 str 이다 (Namespace 가 아니다) — 다른 빌더와 같은 관용을 쓴다.
ONT = Namespace(S.ONT)
DATA = Namespace(S.DATA)
DCTERMS = Namespace("http://purl.org/dc/terms/")

SOURCE = "KSIA member directory (https://www.ksia.or.kr), retrieved 2026-07-14"
LICENSE = "Public information (KSIA member directory)"

# 법인격 접미사·공백은 회사의 이름이 아니다 — 대조 전에 벗긴다.
_STRIP = re.compile(
    r"\(주\)|㈜|주식회사|유한회사|\(유\)|co\.,?\s*ltd\.?|corporation|corp\.?|inc\.?"
    r"|ltd\.?|limited|\s|,|\.|·|-|_|\(|\)",
    re.I,
)


def norm(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return _STRIP.sub("", unicodedata.normalize("NFKC", str(s)).lower())


def website(v) -> str | None:
    """명부의 웹사이트 칸은 지저분하다 — 스킴이 빠지거나("www.x.com"), 두 개가
    한 칸에 들어 있다("a.com / b.com"). 단일 http(s) URL 로 정규화할 수 있을 때만
    rdfs:seeAlso 를 낸다. 억지로 URI 를 만들지 않는다."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or re.search(r"[\s,;]", s):   # 공백/구분자가 있으면 단일 URL 이 아니다
        return None
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    return s if re.fullmatch(r"https?://[^\s/]+(/\S*)?", s) else None


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"[^a-z0-9가-힣]+", "_", s).strip("_")
    return s or "unknown"


def _existing_labels(graph: Graph, cls: str) -> dict[str, URIRef]:
    """정규화된 라벨 → IRI. prefLabel·altLabel 을 모두 키로 삼는다."""
    out: dict[str, URIRef] = {}
    for iri in graph.subjects(RDF.type, ONT[cls]):
        for prop in (SKOS.prefLabel, SKOS.altLabel):
            for lbl in graph.objects(iri, prop):
                k = norm(lbl)
                if k:
                    out.setdefault(k, iri)
    return out


def main() -> int:
    if not CSV.exists():
        print(f"ERROR: {CSV} not found", file=sys.stderr)
        return 1

    known = Graph()
    for p in (CORE_DATA, ABOX_PATENTS):
        if p.exists():
            known.parse(p, format="turtle")
    orgs = _existing_labels(known, "Organization")
    vendors = _existing_labels(known, "Vendor")

    df = pd.read_csv(CSV)
    g = Graph()
    g.bind("ont", ONT)
    g.bind("data", DATA)
    g.bind("skos", str(SKOS))
    g.bind("dcterms", DCTERMS)

    stats = Counter()
    by_type = Counter()
    seen: set[URIRef] = set()

    for _, r in df.iterrows():
        ko = str(r["업체명(국문)"]).strip()
        en = str(r["업체명(영문)"]).strip()
        ctype = str(r["업체구분"]).strip()
        site = r.get("웹사이트")

        keys = [k for k in (norm(ko), norm(en)) if k]

        iri = next((vendors[k] for k in keys if k in vendors), None)
        if iri is not None:
            stats["matched_existing_vendor"] += 1
        else:
            iri = next((orgs[k] for k in keys if k in orgs), None)
            if iri is not None:
                # 특허 출원인으로 이미 있는 회사다 — 새 노드를 만들지 않고 타입만 더한다.
                stats["matched_existing_organization"] += 1
            else:
                iri = URIRef(DATA[f"vendor/ksia_{slug(en or ko)}"])
                stats["new_vendor_node"] += 1
        is_new = iri not in orgs.values() and iri not in vendors.values()

        if iri in seen:
            stats["duplicate_row_skipped"] += 1
            continue
        seen.add(iri)

        g.add((iri, RDF.type, ONT.Vendor))
        # Shape_CoreNode: prefLabel(langString) · dcterms:license · interpretationType
        #
        # 이미 있는 노드에는 prefLabel 을 **덧붙이지 않는다**. skos:prefLabel 은 언어당
        # 하나여야 하는데, KSIA 표기는 기존 표기와 미세하게 다르다("SEMES" ↔ "SEMES Co., Ltd.").
        # 덧붙이면 한 노드에 prefLabel@en 이 둘이 되어 SKOS 를 위반하고, 라벨로 묶는 질의
        # (CQ08 출원인 포트폴리오)가 같은 회사를 두 행으로 쪼갠다. 별칭으로 싣는다.
        if is_new:
            g.add((iri, SKOS.prefLabel, Literal(en or ko, lang="en")))
        elif en:
            g.add((iri, SKOS.altLabel, Literal(en, lang="en")))
        if ko:
            g.add((iri, SKOS.altLabel, Literal(ko, lang="ko")))
        g.add((iri, ONT.companyType, Literal(ctype)))
        g.add((iri, DCTERMS.source, Literal(SOURCE, datatype=XSD.string)))
        g.add((iri, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
        g.add((iri, ONT.interpretationType, Literal("verbatim")))
        url = website(site)
        if url:
            g.add((iri, RDFS.seeAlso, URIRef(url)))
        else:
            stats["website_unusable"] += 1

        by_type[ctype] += 1

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")

    report = {
        "input": str(CSV.relative_to(ROOT)),
        "rows": int(len(df)),
        "vendors_emitted": len(seen),
        "identity": dict(stats),
        "by_company_type": dict(by_type.most_common()),
        "triples": len(g),
        "known_limitation": (
            "KSIA 명부는 각 회원사가 무엇을 공급하는지 담지 않는다. 따라서 새로 만든 "
            "벤더 노드에는 providedBy(장비→벤더)·madeBy(소재→벤더) 엣지가 없다 — "
            "그래프에서 고립 노드다. 공급관계는 별도 수집이 필요하며 지어내지 않는다."
        ),
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"✓ Vendor A-Box ({len(g):,} triples) → {OUT_TTL.relative_to(ROOT)}")
    print(f"  rows={len(df)}  vendors={len(seen)}  {dict(stats)}")
    print(f"  by company type: {dict(by_type.most_common(6))}")
    print(f"  report → {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
