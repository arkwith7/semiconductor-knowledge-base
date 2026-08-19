"""SDKB 도메인 어휘 → nori 사용자사전 빌더 (PLAN-018 §6.2.1 · F13 · SPEC-008).

세 원천을 누출-안전하게 합쳐 nori `UserDictionary` 파일(`config.IR_USERDICT`)을 만든다:

- **A. 온톨로지 통제어휘** — 벤더 스냅샷의 도메인 클래스 14종 prefLabel(en)+altLabel(ko·en).
  회사명(Organization/Vendor)·특허 제목(CitedPatent…)·인명(Expert)은 배제(U2).
- **B. 동결 매핑 CSV** — term_aliases·si_concepts·dart_terms 의 표층형(정규식 메타 제거·U3).
- **C. 코퍼스 수확** — `IR_CORPUS.text_main`(질의+후보 대칭)을 Kiwi 로 토큰화해 도메인-일반
  명사/외래어를 수확한다(df≥30·nori 파편화·고유명 배제·상한 2000 · U4–U6).

동결 파라미터는 PLAN-018 §6.2.1 표(U1–U8). 결과(Recall)를 보기 전에 동결됐다 — 값을 바꾸지
않는다(CLAUDE §1.2·1.3). 산출 통계는 `build()` 가 반환하고 SPEC-008 이 기록한다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

# --- U1/U2 · 온톨로지 도메인 클래스 화이트리스트 / 배제 --------------------
DOMAIN_CLASSES = (
    "Process", "SubProcess", "Device", "Material", "Equipment", "EquipmentClass",
    "EquipmentModel", "FailureMode", "RootCause", "Mitigation", "Skill",
    "Parameter", "Metrology", "TechnologyNode",
)
# 회사명·특허제목·인명은 사용자사전에서 배제(U2). 스톱리스트는 수확 고유명 필터에도 쓴다.
EXCLUDED_CLASSES = (
    "Patent", "CitedPatent", "RejectedPatent", "Expert", "Organization", "Vendor",
)

# --- U5/U6 · 수확 동결값 --------------------------------------------------
DF_MIN = 30            # 문서빈도 하한 (도메인-일반 보증 = 누출 가드)
HARVEST_MAX = 2000     # df 내림차순 상한 (초과 절단 보고)
_MIN_LEN = 2           # 표층형 최소 글자수
_KIWI_KEEP = ("SL", "NNG")   # 외래어·일반명사만 수확 후보

_SKOS = "http://www.w3.org/2004/02/skos/core#"
_HANGUL = re.compile(r"[가-힣]")
_WS = re.compile(r"\s+")
# si_concepts/dart_terms 패턴에서 벗겨낼 정규식 메타·논리토큰
# `\b`(단어경계) 를 먼저 통째로 제거한 뒤 남은 단일 메타문자를 제거한다.
_REGEX_META = re.compile(r"\\b|[\\?()\[\]{}^$*+.]")
_LOGIC = {"and", "or"}


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _norm(s: str) -> str:
    """표층형 정규화: 앞뒤 공백 제거·내부 공백 단일화."""
    return _WS.sub(" ", (s or "").strip())


@dataclass
class UserDictStats:
    """빌드 산출 통계 — SPEC-008 이 기록한다."""

    from_ontology: int = 0
    from_mappings: int = 0
    from_corpus: int = 0
    corpus_capped: int = 0          # 상한 초과로 버린 수확 후보 수
    dropped_multiword: int = 0      # 공백 포함이라 제외한 항 수
    total_terms: int = 0
    sha256_16: str = ""
    ontology_samples: list[str] = field(default_factory=list)
    corpus_samples: list[str] = field(default_factory=list)


# --- 원천 A · 온톨로지 통제어휘 -------------------------------------------
def _from_ontology() -> tuple[set[str], set[str]]:
    """도메인 클래스 인스턴스의 prefLabel(en)+altLabel(ko·en) 표층형과 회사명 스톱리스트."""
    import rdflib
    from rdflib import RDF

    g = rdflib.Graph()
    for ttl in sorted(config.EXTERNAL_SDKB.glob("*.ttl")):
        try:
            g.parse(ttl, format="turtle")
        except Exception:  # noqa: BLE001 — 파싱 불가 파일은 건너뛴다(원천 견고성)
            continue

    pref = rdflib.URIRef(_SKOS + "prefLabel")
    alt = rdflib.URIRef(_SKOS + "altLabel")

    # 인스턴스 → 클래스 지역명 집합
    cls_of: dict = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        cls_of.setdefault(s, set()).add(_local(o))

    terms: set[str] = set()
    company_stop: set[str] = set()
    for s, classes in cls_of.items():
        labels = [_norm(str(o)) for _, _, o in g.triples((s, pref, None))]
        labels += [_norm(str(o)) for _, _, o in g.triples((s, alt, None))]
        labels = [x for x in labels if x]
        if classes & set(DOMAIN_CLASSES) and not (classes & set(EXCLUDED_CLASSES)):
            terms.update(labels)
        if classes & {"Organization", "Vendor"}:
            company_stop.update(labels)
    return terms, company_stop


# --- 원천 B · 동결 매핑 CSV ------------------------------------------------
def _split_pattern(cell: str) -> list[str]:
    """si_concepts/dart_terms 셀에서 표층형만 추출(파이프 분리·메타/논리 제거)."""
    out: list[str] = []
    for chunk in str(cell).split("|"):
        piece = _REGEX_META.sub("", chunk)
        piece = _norm(piece)
        if not piece or piece.lower() in _LOGIC:
            continue
        # 'A AND B' 같은 잔여 논리는 공백분리 후 논리토큰 제거
        toks = [t for t in piece.split() if t.lower() not in _LOGIC]
        if toks:
            out.append(" ".join(toks))
    return out


def _from_mappings() -> set[str]:
    import csv

    terms: set[str] = set()
    ta = config.MAPPINGS / "term_aliases.csv"
    if ta.exists():
        with ta.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = _norm(row.get("term", ""))
                if t:
                    terms.add(t)
    for name, col in (("si_concepts.csv", "variant"), ("dart_terms.csv", "pattern")):
        p = config.MAPPINGS / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                terms.update(_split_pattern(row.get(col, "")))
    return {t for t in terms if t}


# --- 원천 C · 코퍼스 수확 --------------------------------------------------
def _harvest_corpus(company_stop: set[str], nori) -> tuple[list[str], int]:
    """text_main 을 Kiwi 로 토큰화 → 도메인-일반 명사/외래어 수확(U4–U6).

    반환: (채택 표층형 df 내림차순, 상한초과로 절단된 수)
    """
    import pandas as pd
    from kiwipiepy import Kiwi

    df = pd.read_parquet(config.IR_CORPUS, columns=["text_main", "title"])
    kiwi = Kiwi()

    # 특허 제목 토큰(고유명 배제용) — 제목을 Kiwi 로 쪼갠 표층형 집합
    title_tokens: set[str] = set()
    for title in df["title"].dropna().unique():
        for tok in kiwi.tokenize(_norm(str(title))):
            if tok.tag == "NNP":
                title_tokens.add(tok.form)

    # 후보별 문서빈도(df): 한 문서에서 중복 카운트 방지 위해 문서당 집합
    doc_freq: dict[str, int] = {}
    is_nnp: set[str] = set()
    for text in df["text_main"].dropna():
        seen: set[str] = set()
        for tok in kiwi.tokenize(_norm(str(text))):
            form = tok.form
            if tok.tag == "NNP":
                is_nnp.add(form)
            if tok.tag not in _KIWI_KEEP or len(form) < _MIN_LEN:
                continue
            if not _HANGUL.search(form):   # 한글 표층형만(영문은 standard analyzer 담당)
                continue
            seen.add(form)
        for form in seen:
            doc_freq[form] = doc_freq.get(form, 0) + 1

    # 채택 조건 (U5): df≥30 · nori 파편화 · 고유명 아님
    candidates = []
    for form, freq in doc_freq.items():
        if freq < DF_MIN:
            continue
        if form in is_nnp or form in title_tokens or form in company_stop:
            continue
        nori_toks = nori(form)
        if len(nori_toks) == 1 and nori_toks[0] == form:
            continue  # nori 가 이미 단일 토큰으로 안다 → 불필요
        candidates.append((freq, form))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    capped = max(0, len(candidates) - HARVEST_MAX)
    kept = [form for _, form in candidates[:HARVEST_MAX]]
    return kept, capped


# --- 조립 -----------------------------------------------------------------
def build(out_path: Path | None = None) -> UserDictStats:
    """세 원천을 합쳐 nori 사용자사전을 쓰고 통계를 반환한다."""
    from .tokenize import NoriTokenizer

    out_path = out_path or config.IR_USERDICT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    onto_terms, company_stop = _from_ontology()
    map_terms = _from_mappings()

    # 무사전 nori (수확 파편화 판정·U5b)
    nori = NoriTokenizer(mode="NONE", userdict=None)
    corpus_terms, capped = _harvest_corpus(company_stop, nori)

    stats = UserDictStats(
        from_ontology=len(onto_terms),
        from_mappings=len(map_terms),
        from_corpus=len(corpus_terms),
        corpus_capped=capped,
        ontology_samples=sorted(t for t in onto_terms if _HANGUL.search(t))[:20],
        corpus_samples=corpus_terms[:20],
    )

    # 합집합 → 공백 없는 표층형만(U7). 다어절은 nori 단일토큰 불가 → 제외·보고.
    merged = onto_terms | map_terms | set(corpus_terms)
    single, dropped = [], 0
    for t in merged:
        if " " in t:
            dropped += 1
            continue
        if len(t) < _MIN_LEN:
            continue
        single.append(t)
    single = sorted(set(single))
    stats.dropped_multiword = dropped
    stats.total_terms = len(single)

    header = (
        "# SDKB nori 사용자사전 (PLAN-018 §6.2.1 · SPEC-008)\n"
        f"# 원천 A(온톨로지) {stats.from_ontology} · B(매핑) {stats.from_mappings} · "
        f"C(코퍼스수확 df≥{DF_MIN}) {stats.from_corpus} (절단 {capped})\n"
        f"# 다어절 제외 {dropped} · 최종 표층형 {stats.total_terms}\n"
    )
    body = "\n".join(single) + "\n"
    text = header + body
    out_path.write_text(text, encoding="utf-8")
    stats.sha256_16 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return stats


def main() -> None:
    stats = build()
    print(f"✓ nori 사용자사전 → {config.IR_USERDICT}")
    print(f"  표층형 {stats.total_terms}  (A {stats.from_ontology} · "
          f"B {stats.from_mappings} · C {stats.from_corpus}, 절단 {stats.corpus_capped})")
    print(f"  다어절 제외 {stats.dropped_multiword} · sha256[:16]={stats.sha256_16}")
    print(f"  온톨로지 표본: {stats.ontology_samples[:8]}")
    print(f"  수확 표본:     {stats.corpus_samples[:8]}")


if __name__ == "__main__":
    main()
