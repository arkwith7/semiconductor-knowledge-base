#!/usr/bin/env python3
"""청구항 → 한정요소(feature) 결정적 분해 — 신규성/진보성 판단의 실제 단위.

청구항은 전제부(preamble)와 열거된 한정요소로 구성된다. 한국어·영어 청구항 모두
열거 마커(a./i./1./단계)와 접속(및·그리고·;·wherein)으로 요소를 구분하고, '상기'(said)로
앞선 요소를 참조한다. 이 모듈은 그 구조 신호로 청구항을 요소 단위로 자른다.

결정적이다 — 같은 청구항이면 같은 분해. LLM 을 부르지 않는다(검증 계층은 별도).
규칙이 깨지는 청구항은 flag 로 표시해 LLM 검증 대상으로 넘긴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 전제부 종결 신호 — 여기까지가 preamble, 이후가 한정요소부.
_PREAMBLE_KO = re.compile(r"에\s*있어서\s*[,:]")
_PREAMBLE_EN = re.compile(r"\b(comprising|consisting of|including|which comprises)\s*[:,]", re.I)

# 요소 경계 마커. 줄머리/공백 뒤의 열거 기호 + 한국어 절 종결.
# 열거: a. / A) / (a) / i. / ii) / 1. / 1)  — 라틴·로마·숫자
_ENUM = re.compile(
    r"(?:^|\s)(?:\(?[a-zA-Z]\)|\(?[ivxIVX]{1,4}\)|\(?\d{1,2}\)|[a-zA-Z]\.|[ivxIVX]{1,4}\.|\d{1,2}\.)\s"
)
# 세미콜론 — 언어 무관 1급 요소 구분자(장치·조성 청구항이 요소를 ';'로 나열한다).
_SEMI = re.compile(r"\s*;\s*")
# 한국어 절 종결(요소 끝) — '~단계와,' '~하는 것,' '~하며,' '~하고,' '~을 포함하고,'
_KO_CLAUSE = re.compile(r"(단계(?:와|로서|를)?|하는\s*것|하며|하고|포함하고|포함하며|구비하고)\s*[,;]")
# 영어 요소 경계
_EN_CLAUSE = re.compile(r";\s*|\bwherein\b|\bwhereby\b", re.I)
# feature 선두 접속어(및·그리고·또는·and·or) — 요소 텍스트에서 제거한다.
_LEAD_CONJ = re.compile(r"^\s*(?:및|그리고|또는|and|or)\s*", re.I)


@dataclass
class Feature:
    seq: int
    text: str
    marker: str = ""          # 이 요소를 연 열거 기호(a/i/1…)
    refs: tuple[str, ...] = ()  # '상기 X' 로 참조한 앞선 요소 표현


@dataclass
class DecomposedClaim:
    claim_no: int
    preamble: str
    features: list[Feature] = field(default_factory=list)
    flagged: bool = False     # 규칙이 신뢰도 낮음 → LLM 검증 대상
    flag_reason: str = ""


def _lang(text: str) -> str:
    return "ko" if any("가" <= c <= "힣" for c in text[:200]) else "en"


# 청구항 블록(1항+2항+…)을 개별 청구항으로 자르는 선두 번호 마커.
_CLAIM_HEAD = re.compile(r"(?m)^\s*(\d{1,3})\s*[.\.]\s+")
# 종속항 신호 — 다른 청구항을 참조하면 종속(독립항이 신규성/진보성 판단의 단위).
_DEP = re.compile(r"(제\s*\d+\s*항|청구항\s*\d+|claim\s+\d+|of\s+claims?\s+\d+)", re.I)


def split_claims(blob: str) -> list[tuple[int, str]]:
    """다중 청구항 텍스트('1. … 2. … 3. …') → [(번호, 텍스트)].

    KIPRIS/BigQuery 는 청구항을 한 덩어리로 준다. feature 분해는 청구항 1건 단위이므로
    먼저 선두 번호로 자른다. 번호 마커가 없으면 전체를 1항으로 본다.
    """
    marks = list(_CLAIM_HEAD.finditer(blob))
    if not marks:
        return [(1, blob.strip())] if blob.strip() else []
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(blob)
        no = int(m.group(1))
        text = blob[m.start():end].strip()
        if text:
            out.append((no, text))
    return out


def is_independent(claim_text: str) -> bool:
    """종속 참조가 없으면 독립항. 신규성/진보성 대비의 단위."""
    body = re.sub(r"^\s*\d+\s*[.)]\s*", "", claim_text.strip())
    return not _DEP.search(body[:120])   # 참조는 청구항 앞머리에 온다


def _split_preamble(text: str, lang: str) -> tuple[str, str]:
    pat = _PREAMBLE_KO if lang == "ko" else _PREAMBLE_EN
    m = pat.search(text)
    if m:
        return text[: m.end()].strip(), text[m.end():].strip()
    return "", text.strip()   # 전제부를 못 찾으면 전체를 요소부로


def _refs(span: str) -> tuple[str, ...]:
    """'상기 하드마스크' / 'said mask' 참조 표현 — 요소 간 의존의 신호."""
    ko = re.findall(r"상기\s+([가-힣A-Za-z0-9 ]{2,20}?)(?:층|막|부|재료|구조물|단계|는|를|을|가|이|의|에)", span)
    en = re.findall(r"\bsaid\s+([a-z][a-z0-9 ]{2,30}?)\b", span, re.I)
    return tuple(dict.fromkeys(s.strip() for s in ko + en if s.strip()))


def _clean(span: str) -> str:
    """요소 텍스트 정제 — 선두 접속어 제거 + 공백 정규화(OCR 런온 완화)."""
    s = _LEAD_CONJ.sub("", span.strip(" ,;\n"))
    return re.sub(r"\s+", " ", s).strip()


def decompose(claim_text: str, claim_no: int = 0) -> DecomposedClaim:
    """청구항 1건 → 전제부 + 한정요소 목록. 열거 → ';' → 절종결 3단 신호."""
    text = re.sub(r"^\s*\d+\s*[.)]\s*", "", claim_text.strip())  # 선두 청구항 번호 제거
    lang = _lang(text)
    preamble, body = _split_preamble(text, lang)
    features: list[Feature] = []

    # 1차: 열거 마커(a./i./1.) — 가장 신뢰도 높은 신호.
    marks = list(_ENUM.finditer(body))
    if len(marks) >= 2:
        spans = []
        head = body[: marks[0].start()]
        if len(head.strip(" ,;")) > 8:
            spans.append(("", head))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
            spans.append((m.group().strip(), body[m.end():end]))
        features = [Feature(0, c, mk, _refs(c)) for mk, s in spans if (c := _clean(s))]

    # 2차: 세미콜론 — 장치·조성 청구항의 1급 구분자(언어 무관).
    if not features:
        parts = [p for p in _SEMI.split(body) if p.strip()]
        if len(parts) >= 2:
            features = [Feature(0, c, "", _refs(c)) for p in parts if (c := _clean(p))]

    # 3차: 절 종결 신호(그 외 청구항).
    if not features:
        clause = _KO_CLAUSE if lang == "ko" else _EN_CLAUSE
        parts, last = [], 0
        for m in clause.finditer(body):
            parts.append(body[last:m.end()]); last = m.end()
        parts.append(body[last:])
        features = [Feature(0, c, "", _refs(c)) for p in parts if (c := _clean(p))]

    for j, f in enumerate(features):
        f.seq = j + 1
    dc = DecomposedClaim(claim_no, preamble, features)
    # 신뢰도 flag: 요소가 1개거나, 유난히 긴 요소(분해 실패 징후)가 있으면 LLM 검증.
    if len(features) <= 1:
        dc.flagged, dc.flag_reason = True, "single_feature"
    elif max((len(f.text) for f in features), default=0) > 600:
        dc.flagged, dc.flag_reason = True, "oversized_feature"
    return dc
