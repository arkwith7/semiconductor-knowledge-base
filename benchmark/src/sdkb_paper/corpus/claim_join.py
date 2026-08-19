"""sidecar 청구항 재구성 (PLAN-017 B1).

청구항 본문은 `claimText` 단일 문자열이 아니라 `ClaimFeature.featureText` 로 분해 저장돼 있다
(SPEC-006 §5·§8). 특허별로 (claimNumber, featureSeq) 순서로 feature 를 이어붙여 청구항 전체를
재구성한다. 이것이 v0.9 코퍼스 청구항 텍스트의 **정본**이다(PLAN-017 §7 M1).

    from sdkb_paper.corpus import claim_join
    recon = claim_join.reconstruct_all()   # {patent_iri: ClaimText}

sidecar(11.6M 트리플)는 rdflib 금지 — pyoxigraph 온디스크로만 조회한다
(메모리 central-axis-use-oxigraph-ondisk).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..ontology import central_axis
from . import text as textmod

ONT = "https://w3id.org/sdkb/ont/"

# 특허 → 청구항 (claimNumber, isIndependent)
_Q_CLAIMS = f"""PREFIX ont:<{ONT}>
SELECT ?pat ?c ?cn ?ind WHERE {{
  ?pat ont:hasClaim ?c .
  ?c ont:claimNumber ?cn ; ont:isIndependent ?ind .
}}"""

# 청구항 → feature (featureSeq, featureText)
_Q_FEATURES = f"""PREFIX ont:<{ONT}>
SELECT ?c ?seq ?txt WHERE {{
  ?c ont:hasFeature ?f .
  ?f ont:featureSeq ?seq ; ont:featureText ?txt .
}}"""


@dataclass
class ClaimText:
    """한 특허의 재구성된 청구항 텍스트."""

    claims_full: str = ""          # 전체 청구항(독립+종속), claimNumber 순
    claims_independent: str = ""   # 독립항만
    first_independent: str = ""    # 최소 번호 독립항 (질의단위 후보)
    n_claims: int = 0
    n_independent: int = 0


def _to_int(v: str) -> int:
    """claimNumber/featureSeq 리터럴 → 정수 정렬키. 비정수는 큰 값으로 밀어 안정 정렬."""
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return 10**9


def _reconstruct(claims: list[tuple[int, bool, str]]) -> ClaimText:
    """[(claimNumber, isIndependent, claim_text)] → ClaimText.

    claim_text 는 이미 feature 를 순서대로 이어붙여 정제한 결과. 여기서는 청구항 단위로
    번호순 결합만 한다. 청구항 사이 구분은 개행(색인 토큰 오염 없음)."""
    claims = sorted(claims, key=lambda x: x[0])
    full = "\n".join(t for _, _, t in claims if t)
    indep = [(cn, t) for cn, ind, t in claims if ind and t]
    indep_txt = "\n".join(t for _, t in indep)
    first = indep[0][1] if indep else (claims[0][2] if claims else "")
    return ClaimText(
        claims_full=full,
        claims_independent=indep_txt,
        first_independent=first,
        n_claims=len(claims),
        n_independent=sum(1 for _, ind, _ in claims if ind),
    )


def reconstruct_all(store=None) -> dict[str, ClaimText]:
    """sidecar 전체를 훑어 특허별 재구성 청구항 텍스트를 반환한다.

    2회 조회(청구항 메타 · feature)를 파이썬에서 조인해 SPARQL 5중 조인의 비용을 피한다.
    결정적: 정렬 순서가 고정돼 실행마다 동일 출력."""
    store = store or central_axis.open_store()

    # 1) feature 텍스트를 청구항별로 모은다: claim_iri -> [(seq, text)]
    feats: dict[str, list[tuple[int, str]]] = {}
    for row in store.query(_Q_FEATURES):
        c = row["c"].value
        feats.setdefault(c, []).append((_to_int(row["seq"].value), textmod.clean(row["txt"].value)))

    # 2) 청구항 메타를 모으고 feature 를 이어붙여 청구항 텍스트를 만든다: patent -> [(cn, ind, text)]
    per_patent: dict[str, list[tuple[int, bool, str]]] = {}
    for row in store.query(_Q_CLAIMS):
        pat = row["pat"].value
        c = row["c"].value
        cn = _to_int(row["cn"].value)
        ind = str(row["ind"].value).lower() in ("true", "1")
        parts = sorted(feats.get(c, []), key=lambda x: x[0])
        claim_text = " ".join(t for _, t in parts if t).strip()
        per_patent.setdefault(pat, []).append((cn, ind, claim_text))

    return {pat: _reconstruct(cl) for pat, cl in per_patent.items()}
