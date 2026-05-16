"""정답(prior-art) 인용 식별자 정규화.

`docs/etching_reject_web_poc_dataset_schema.md` §3을 코드로 옮긴 모듈.

관측된 표기들을 `Citation(country, kind, serial, original)` 정규형으로 변환하고,
검색 결과와 매칭 가능한 단일 문자열 키 `normalized_id`를 제공한다.

대표 케이스:

    >>> parse("10-1998202").normalized_id
    'KR-G-1998202'
    >>> parse("10-2017-0126049").normalized_id
    'KR-P-1020170126049'
    >>> parse("KR2001-29136").normalized_id
    'KR-P-1020010029136'
    >>> parse("KR2005-10679").normalized_id
    'KR-P-1020050010679'
    >>> parse("JP-2007-009988").normalized_id
    'JP-P-2007009988'
    >>> parse("JP-H08-255787").normalized_id
    'JP-P-H08255787'
    >>> parse("US2002-0063106").normalized_id
    'US-P-20020063106'
    >>> parse("US2010/0213162").normalized_id
    'US-P-20100213162'
    >>> parse("US5308414").normalized_id
    'US-G-5308414'
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

__all__ = [
    "Citation",
    "parse",
    "parse_many",
    "match",
]


@dataclass(frozen=True)
class Citation:
    country: str       # "KR" | "JP" | "US" | ""
    kind: str          # "publication" | "grant" | "unknown"
    serial: str        # 정규화된 일련번호 (대문자, 영숫자만)
    original: str      # 원본 표기 (보존용)

    @property
    def normalized_id(self) -> str:
        if not self.country or not self.serial:
            return f"UNKNOWN::{self.original}"
        kind_code = {"publication": "P", "grant": "G"}.get(self.kind, "U")
        return f"{self.country}-{kind_code}-{self.serial}"


_UNKNOWN = Citation(country="", kind="unknown", serial="", original="")


def _strip(s: str) -> str:
    return re.sub(r"\s+", "", s or "").strip()


_NPL_HINTS = (
    "VOL.", " PP.", "PP.", "ET AL", "DOI", "ISSN", "ISBN", "JOURNAL",
    "PROCEEDINGS", "IEEE", "ACM", "SOC.",
)


def _looks_like_npl(s: str) -> bool:
    """비특허 문헌 휴리스틱."""
    up = s.upper()
    if any(h in up for h in _NPL_HINTS):
        return True
    if s.count('"') >= 2 or s.count("'") >= 2:
        # 따옴표로 감싼 논문 제목이 자주 등장
        return True
    if "," in s and any(t in s.lower() for t in (" 외 ", " 제", "권", "호")):
        # 한국 학회지 인용 (예: "김동환 외 7인 ... 한국세라믹학회지 제48권제1호")
        return True
    return False


def _kind_from_kindcode(code: str) -> str:
    """WIPO ST.16 kind code의 첫 글자로 publication/grant 구분."""
    if not code:
        return ""
    head = code[0].upper()
    if head == "A":
        return "publication"
    if head == "B":
        return "grant"
    if head == "U":
        return "grant"  # utility model registration
    if head == "Y":
        return "grant"  # utility model registration (KR)
    return ""


def parse(raw: str) -> Citation:
    """단일 인용 표기를 `Citation`으로 변환. 실패 시 `kind='unknown'`."""
    if not raw:
        return _UNKNOWN
    original = str(raw)
    if _looks_like_npl(original):
        return Citation("", "unknown", "", original)

    s = _strip(original).upper().replace("/", "-")

    if not s:
        return Citation("", "unknown", "", original)

    # ── WIPO ST.16 (kind code suffix): "KR1019980011729 A", "JP4469023 B2" ───
    # 공백 제거 전에 trailing kind code 분리.
    m_kc = re.fullmatch(r"([A-Z]{2})(\d+)([A-Z]\d?)", _strip(original).upper().replace("/", "-").replace(" ", ""))
    # NOTE: 공백 제거된 형태로도 매칭 시도
    if not m_kc:
        # 공백을 살린 표기: "KR1019980011729 A"
        m2 = re.fullmatch(r"([A-Z]{2})(\d+)\s+([A-Z]\d?)", _strip(original).upper().replace("/", "-"))
        if m2:
            m_kc = m2
    if m_kc:
        cc, digits, kc = m_kc.group(1), m_kc.group(2), m_kc.group(3)
        kind_hint = _kind_from_kindcode(kc)
        if cc == "KR":
            if kind_hint == "publication" and len(digits) >= 11:
                return Citation("KR", "publication", digits[-13:].zfill(13), original)
            if kind_hint == "grant":
                # 10NNNNNNN(N) → 7~8자리 등록번호. 앞 2자리 '10' 제거.
                if digits.startswith("10") and len(digits) >= 8:
                    serial = digits[2:].lstrip("0") or digits[2:]
                    return Citation("KR", "grant", serial, original)
                return Citation("KR", "grant", digits, original)
            # kind 모호 → digits 길이로 추정
            if len(digits) >= 11:
                return Citation("KR", "publication", digits[-13:].zfill(13), original)
            return Citation("KR", "grant", digits.lstrip("0") or digits, original)
        if cc == "JP":
            return Citation("JP", kind_hint or "publication", digits, original)
        if cc == "US":
            return Citation("US", kind_hint or ("publication" if len(digits) >= 11 else "grant"), digits, original)
        if cc in ("CN", "EP", "WO", "DE", "FR", "GB", "TW"):
            return Citation(cc, kind_hint or "publication", digits, original)

    # ── KR ──────────────────────────────────────────────────────────────────
    # 풀 공개번호: 10-YYYY-NNNNNNN (year-dash 필수)
    m = re.fullmatch(r"(?:KR-?)?10-(\d{4})-(\d{1,7})", s)
    if m:
        year, serial = m.group(1), m.group(2).zfill(7)
        return Citation("KR", "publication", f"10{year}{serial}", original)

    # 13자리 직접 표기 (출원/공개번호 모두 이 형식): 10YYYYNNNNNNN
    raw_digits = s.replace("-", "")
    m = re.fullmatch(r"10(\d{4})(\d{7})", raw_digits)
    if m and (s.startswith("10") or s.startswith("KR10")):
        return Citation("KR", "publication", raw_digits[-13:], original)

    # 약식 공개번호: KR<YY>-<NNNNN>  또는  KR<YYYY>-<NNNNN> (year-dash 필수)
    m = re.fullmatch(r"KR-?(\d{2}|\d{4})-(\d{1,7})", s)
    if m:
        yy = m.group(1)
        if len(yy) == 2:
            # 두 자리 연도는 KIPO 정책상 모호. 휴리스틱: 50 이상은 19xx, 미만은 20xx
            yyyy = ("19" if int(yy) >= 50 else "20") + yy
        else:
            yyyy = yy
        serial = m.group(2).zfill(7)
        return Citation("KR", "publication", f"10{yyyy}{serial}", original)

    # 풀 등록번호: 10-NNNNNNN (year-dash 없음, 6~7자리 일련번호)
    m = re.fullmatch(r"(?:KR-?)?10-(\d{6,7})", s)
    if m:
        return Citation("KR", "grant", m.group(1).lstrip("0") or m.group(1), original)

    # ── JP ──────────────────────────────────────────────────────────────────
    # 헤이세이/쇼와 표기: JP-H08-255787, JP-S60-12345
    m = re.fullmatch(r"JP-?([HSR]\d{2})-?(\d{1,7})", s)
    if m:
        era, serial = m.group(1), m.group(2).zfill(6)
        return Citation("JP", "publication", f"{era}{serial}", original)

    # 서기 표기: JP-2007-009988
    m = re.fullmatch(r"JP-?(\d{4})-?(\d{1,7})", s)
    if m:
        year, serial = m.group(1), m.group(2).zfill(6)
        return Citation("JP", "publication", f"{year}{serial}", original)

    # ── US ──────────────────────────────────────────────────────────────────
    # 공개번호: US-YYYY-NNNNNNN  (slash는 위에서 dash로 정규화됨, dash 필수)
    m = re.fullmatch(r"US-?(\d{4})-(\d{1,7})", s)
    if m:
        year, serial = m.group(1), m.group(2).zfill(7)
        return Citation("US", "publication", f"{year}{serial}", original)

    # 등록번호: US<digits> (5-8자리 utility/design patent grant number)
    m = re.fullmatch(r"US-?(\d{5,8})", s)
    if m:
        return Citation("US", "grant", m.group(1), original)

    # ── EP / WO 등 (간단 처리) ───────────────────────────────────────────────
    m = re.fullmatch(r"(EP|WO|CN|DE|FR|GB|TW)-?(\d{4,12})", s)
    if m:
        return Citation(m.group(1), "publication", m.group(2), original)

    return Citation("", "unknown", "", original)


def parse_many(raws: Iterable[str]) -> List[Citation]:
    return [parse(r) for r in raws]


def match(a: Citation, b: Citation) -> bool:
    """두 Citation이 동일 문헌을 가리키는지.

    원칙: country + kind + serial이 모두 같으면 일치.
    KR 공개번호의 정확한 등록번호 lookup은 별도 매핑이 필요하므로
    여기서는 시도하지 않는다.
    """
    if a.kind == "unknown" or b.kind == "unknown":
        return False
    return a.country == b.country and a.kind == b.kind and a.serial == b.serial


def _selftest() -> None:
    cases = {
        # 기존 OCR 표기
        "10-1998202": ("KR", "grant", "1998202"),
        "10-2017-0126049": ("KR", "publication", "1020170126049"),
        "KR2001-29136": ("KR", "publication", "1020010029136"),
        "KR2005-10679": ("KR", "publication", "1020050010679"),
        "KR2001-46153": ("KR", "publication", "1020010046153"),
        "JP-2007-009988": ("JP", "publication", "2007009988"),
        "JP-H08-255787": ("JP", "publication", "H08255787"),
        "US2002-0063106": ("US", "publication", "20020063106"),
        "US2010/0213162": ("US", "publication", "20100213162"),
        "US2015/0093880": ("US", "publication", "20150093880"),
        "US5308414": ("US", "grant", "5308414"),
        # WIPO ST.16 (API 출처)
        "KR1019980011729 A": ("KR", "publication", "1019980011729"),
        "KR101998202 B1": ("KR", "grant", "1998202"),
        "JP07221208 A": ("JP", "publication", "07221208"),
        "JP4469023 B2": ("JP", "grant", "4469023"),
        "CN111621760 A": ("CN", "publication", "111621760"),
        "WO2007056753 A2": ("WO", "publication", "2007056753"),
    }
    for raw, (country, kind, serial) in cases.items():
        c = parse(raw)
        assert (c.country, c.kind, c.serial) == (country, kind, serial), (raw, c)
    # match 확인
    a = parse("KR2001-29136")
    b = parse("10-2001-0029136")
    assert match(a, b), (a, b)
    # NPL 감지
    npl = parse('JJAP. Vol.47, 2008, pp.1435-1455, "Developments of Plasma Etching Technology"')
    assert npl.country == "" and npl.kind == "unknown", npl
    print("citation_norm self-test OK")


if __name__ == "__main__":
    _selftest()
