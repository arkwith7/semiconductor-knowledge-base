"""PLAN-005 별건 — 통지서 판단의 인용문헌 해소 (미해소 277 · 2026-10-03).

**왜 이 파일이 있는가.** 같은 통지서 정본을 두 생성기가 읽는데 문헌을 맞추는 규칙이 달랐다.
간선 근거 부착(`build_notice_evidence.loose_key`)은 앞자리 0 을 흡수했고, A-Box 생성기는 정확 일치만
봤다. 그래서 통지서 판단 277 키 중 195 가 같은 문헌의 표기 차이만으로 그래프에서 빠졌다.

여기서 고정하는 계약은 셋이다.
1. 표기 차이(앞자리 0 · US P/G · 일본 연호)는 같은 문헌으로 본다. 국가가 다르면 같은 문헌이 아니다.
2. 고를 수 없는 키(같은 문헌이 IRI 둘로 들어간 경우)는 해소하지 않고 사유를 센다.
3. 정확 일치 판단은 이전과 같은 IRI·같은 트리플로 남는다 — 이미 배포된 판단은 움직이지 않는다.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_abox_claim_features import (  # noqa: E402
    OUT_REPORT,
    _doc_key,
    _emit_judgments,
    _loose_map,
    _slug,
)

ONT = "https://w3id.org/sdkb/ont/"
DATA = "https://w3id.org/sdkb/data/"


# --- 계약 1 · 같은 문헌의 표기 차이 ---------------------------------------

@pytest.mark.parametrize("a, b", [
    ("KR-G-0697293", "KR-G-697293"),            # 앞자리 0
    ("US-G-05814854", "US-P-05814854"),         # KIPRIS 가 1998 년 등록특허를 P 로 적는다
    ("US-G-7118954", "US-G-07118954"),
    ("JP-P-08255787", "JP-P-H08255787"),        # 헤이세이 8 년
    ("JP-P-12174270", "JP-P-2000174270"),       # 헤이세이 12 년 = 2000
    ("JP-P-H08255787", "JP-P-1996255787"),
    ("JP-P-S61123456", "JP-P-61123456"),        # YY 32 이상은 쇼와
    ("JP-G-07091636", "JP-G-7091636"),          # 등록번호의 8자리는 0 채움 — 연호가 아니다
])
def test_same_document_spelled_differently_gets_one_key(a, b):
    assert _doc_key(a) == _doc_key(b) is not None


@pytest.mark.parametrize("a, b", [
    ("KR-G-5836506", "US-P-05836506"),          # 파서가 국가를 잘못 붙인 실례 — 맞추면 안 된다
    ("JP-G-5102191", "KR-G-5102191"),
    ("JP-P-31123456", "JP-P-S31123456"),        # 경계: 31 은 헤이세이(2019), 쇼와 31 과 다르다
    ("JP-P-2007266413", "JP-P-2007266143"),     # 원천 간 번호 불일치 — 오타를 고치지 않는다
])
def test_different_documents_stay_apart(a, b):
    assert _doc_key(a) != _doc_key(b)


@pytest.mark.parametrize("bad", ["", "NPL-123", "KR-X-123", "kr-g-123", "KR-G-12a", None])
def test_malformed_ids_have_no_key(bad):
    assert _doc_key(bad) is None


def test_loose_map_refuses_keys_that_reach_two_iris():
    """같은 문헌이 IRI 둘로 들어가 있으면 어느 쪽에 붙일지 맵 순서가 정한다 — 고르지 않는다."""
    unique, ambiguous = _loose_map({
        "US-P-5874131": "patent:us_US5874131A",
        "US-P-05874131": "patent:us_US05874131A",
        "KR-G-697293": "patent:kr_KR100697293B1",
    })
    assert ("US", "5874131") in ambiguous and ("US", "5874131") not in unique
    assert unique[("KR", "697293")] == "patent:kr_KR100697293B1"


# --- 계약 2·3 · 방출 ------------------------------------------------------

CITED = {
    "KR-G-697293": "patent:kr_KR100697293B1",
    "US-P-5874131": "patent:us_US5874131A",
    "US-P-05874131": "patent:us_US05874131A",
}
CLAIMS = {f"{DATA}claim/rej_1020000000001_c{n}" for n in (1, 2, 3)}
T = "patent:kr_1020000000001"
INV = "Rejection_Inventiveness"


def _run(judg, src):
    g, stat = Graph(), Counter()
    _emit_judgments(g, judg, src, CITED, CLAIMS, stat)
    return g, stat


def _j(doc, ground=INV):
    return URIRef(f"{DATA}judgment/{_slug(T + '__' + doc + '__' + ground)}")


def test_exact_judgment_triples_do_not_move_when_loose_keys_are_added():
    """정확 일치 판단의 트리플은 표기 차이 키가 더해져도 그대로다(배포된 IRI 불변)."""
    exact = {(T, "KR-G-697293", INV): {1}}
    src = {(T, "KR-G-697293", INV): {"evidence_v2"}}
    before, _ = _run(exact, src)
    more = {**exact, (T, "US-G-05874131", "Rejection_Novelty"): {2}}   # 모호 → 해소 안 됨
    after, _ = _run(more, {**src, (T, "US-G-05874131", "Rejection_Novelty"): {"opinion_notice"}})
    assert set(before) == set(after)
    assert (_j("KR-G-697293"), URIRef(ONT + "overPriorArt"),
            URIRef(DATA + "patent/kr_KR100697293B1")) in before


def test_loose_key_becomes_a_new_judgment_on_the_canonical_iri():
    g, stat = _run({(T, "KR-G-0697293", INV): {2}}, {(T, "KR-G-0697293", INV): {"opinion_notice"}})
    j = _j("KR-G-0697293")
    assert (j, URIRef(ONT + "overPriorArt"), URIRef(DATA + "patent/kr_KR100697293B1")) in g
    assert (j, URIRef(ONT + "aboutClaim"), URIRef(DATA + "claim/rej_1020000000001_c2")) in g
    assert stat["judgments"] == 1 and stat["judgment_cited_resolved_loose"] == 1
    assert stat["judgment_cited_resolved_loose__opinion_notice"] == 1
    assert stat["judgment_cited_unresolved"] == 0


def test_loose_key_merges_into_the_existing_judgment_instead_of_a_second_node():
    """같은 (출원, 문헌, 근거)를 표기만 달리 두 노드로 만들면 판단 수가 표기 수를 센다."""
    judg = {(T, "KR-G-697293", INV): {1}, (T, "KR-G-0697293", INV): {1, 3}}
    src = {(T, "KR-G-697293", INV): {"evidence_v2"}, (T, "KR-G-0697293", INV): {"opinion_notice"}}
    g, stat = _run(judg, src)
    nodes = set(g.subjects(URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                           URIRef(ONT + "PriorArtJudgment")))
    assert nodes == {_j("KR-G-697293")}
    assert stat["judgments"] == 1 and stat["judgment_loose_merged"] == 1
    assert stat["judgments"] == (stat["judgment_cited_exact"] + stat["judgment_cited_resolved_loose"]
                                 - stat["judgment_loose_merged"])
    assert stat["about_claim"] == 2                    # c1 은 다시 세지 않는다 · c3 추가
    assert stat["judgments_by_source__opinion_notice"] == 1
    assert stat["judgments_notice_only"] == 0          # 원천이 둘이 됐다


def test_unresolved_keys_are_counted_by_reason():
    judg = {(T, "US-G-05874131", INV): {1},           # 모호
            (T, "JP-P-2007266413", INV): {1}}         # 맵에 없음
    src = {k: {"opinion_notice"} for k in judg}
    g, stat = _run(judg, src)
    assert len(g) == 0
    assert stat["judgment_cited_unresolved"] == 2
    assert stat["judgment_cited_unresolved__reason__ambiguous"] == 1
    assert stat["judgment_cited_unresolved__reason__absent"] == 1
    assert stat["judgment_cited_unresolved__opinion_notice"] == 2


# --- 실물 통합 ------------------------------------------------------------

@pytest.mark.skipif(not OUT_REPORT.exists(), reason="리포트 없음 — make abox-claim-features 후")
def test_published_report_accounts_for_every_judgment_key():
    """방출 + 병합 + 미해소 = 키 전부, 미해소 사유의 합 = 미해소."""
    c = json.loads(OUT_REPORT.read_text(encoding="utf-8"))["counts"]
    reasons = sum(v for k, v in c.items() if k.startswith("judgment_cited_unresolved__reason__"))
    assert reasons == c["judgment_cited_unresolved"]
    assert "judgment_cited_resolved_loose" in c, "표기 차이 해소 계수가 리포트에 없다"
    assert c["judgments"] == (c["judgment_cited_exact"] + c["judgment_cited_resolved_loose"]
                              - c.get("judgment_loose_merged", 0))
