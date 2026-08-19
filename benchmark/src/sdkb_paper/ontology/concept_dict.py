"""개념 매핑 사전 읽기 (PLAN-034 §3.4 신규① · CR-007 하류 · D-19).

상류가 낸 `mappings/concept_mapping.json` 의 **`patent-text` 프로파일**을 표면형 사전으로 읽는다.
이 모듈은 **텍스트를 모르고 코퍼스를 모른다** — 적용은 `corpus/concept_link.py` 가 한다.

- **어휘 발명 0(CLAUDE §1-6):** 개념·축은 사전에 적힌 것만. 하류에서 표면형을 더하거나 고치지
  않는다. 사전이 틀렸으면(D-20 `hf`→불산) 그대로 통과시키고 상류 CR 로 회신한다(§0.1).
- **`expert-tag` 프로파일은 쓰지 않는다** — D-15 축 범주 오류를 되살리는 경로(PLAN-034 §5-4).
- **사전이 없으면 빈 사전을 돌려준다.** 그것이 CR-007 이전 스냅샷(O 팔)의 상태이고, 그때
  적용기는 아무것도 하지 않아야 한다(PLAN-034 §3.3 무작동 동치성).
- **결정성(S1):** 반환은 표면형 사전순 정렬 튜플이다 — JSON 기재 순서에 결과가 의존하지 않는다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .. import config

PROFILE = "patent-text"          # 동결 (PLAN-034 §5-4)

# R1-NORMALIZE (상류 규칙 그대로): lowercase · `/ _ - . ( )` 와 공백 → 단일 공백 · 양끝 trim.
# 형태소 분석 없음 — 하류가 상류와 다른 정규화를 하면 사전의 표면형이 의미를 잃는다.
_NORM_CHARS = re.compile(r"[/_\-.()\s]+")
_LATIN = re.compile(r"[a-z0-9]")


@dataclass(frozen=True)
class Entry:
    """사전 한 줄. 필드는 상류 스키마 그대로(concept_id 는 `<세그먼트>:<지역명>`)."""

    concept_id: str
    concept_type: str
    rule_id: str
    confidence: float
    ambiguous: bool

    @property
    def slug(self) -> str:
        """IRI 지역명 — 코퍼스 `concepts` 열의 키(PLAN-034 §3.2 결정 A)."""
        return self.concept_id.split(":", 1)[-1]

    @property
    def segment(self) -> str:
        return self.concept_id.split(":", 1)[0] if ":" in self.concept_id else ""


@dataclass(frozen=True)
class Surface:
    """정규화된 표면형 하나와 그것이 가리키는 개념들.

    `bound=True`(라틴/숫자 포함)면 양끝에 `[a-z0-9]` 가 오면 안 된다 — 2단계 실측에서
    `al` 이 *metal* 안에서, `co` 가 *coating* 안에서 걸린 위양성을 막는 규칙이다(BOUND 채택).
    한글 전용 표면형은 부분문자열로 본다(교착어라 경계가 공백으로 서지 않는다).
    """

    text: str
    bound: bool
    entries: tuple[Entry, ...]


def normalize(s: str) -> str:
    """R1-NORMALIZE. None·빈 문자열은 빈 문자열."""
    if not s:
        return ""
    return _NORM_CHARS.sub(" ", str(s).lower()).strip()


def needs_boundary(surface: str) -> bool:
    """라틴/숫자를 포함하는가 = 경계를 요구하는가."""
    return bool(_LATIN.search(surface))


def load(path: Path | None = None, profile: str = PROFILE) -> tuple[Surface, ...]:
    """벤더 스냅샷의 사전 → 표면형 튜플(표면형 사전순).

    **파일이 없으면 빈 튜플**(O 팔 · 무작동). 프로파일이 없으면 그것은 사전의 결함이므로
    조용히 넘기지 않고 실패한다.
    """
    p = Path(path) if path is not None else config.SDKB_CONCEPT_MAP
    if not p.exists():
        return ()
    doc = json.loads(p.read_text(encoding="utf-8"))
    profiles = doc.get("profiles") or {}
    if profile not in profiles:
        raise SystemExit(
            f"[concept_dict] 사전에 프로파일 '{profile}' 이 없다: {p} "
            f"(있는 것: {sorted(profiles)}) — 상류 스키마가 바뀌었다면 CR 로 확인할 것."
        )
    by_surface: dict[str, list[Entry]] = {}
    for e in profiles[profile].get("entries", []):
        text = normalize(e.get("surface", ""))
        if not text:
            continue
        by_surface.setdefault(text, []).append(
            Entry(
                concept_id=str(e["concept_id"]),
                concept_type=str(e.get("concept_type", "")),
                rule_id=str(e.get("rule_id", "")),
                confidence=float(e.get("confidence", 1.0)),
                ambiguous=bool(e.get("ambiguous", False)),
            )
        )
    return tuple(
        Surface(
            text=text,
            bound=needs_boundary(text),
            # 같은 표면형의 개념들도 정렬해 둔다(사이드카 행 순서까지 결정적으로).
            entries=tuple(sorted(by_surface[text], key=lambda x: x.concept_id)),
        )
        for text in sorted(by_surface)
    )


def concept_universe(surfaces: tuple[Surface, ...]) -> dict[str, str]:
    """concept_id → IRI. `concept_axis` 우주 확장의 입력(PLAN-034 §3.2 A′).

    IRI 는 `https://w3id.org/sdkb/data/<세그먼트>/<지역명>` — 코퍼스·그래프가 쓰는 형식과 같다.
    """
    out: dict[str, str] = {}
    for s in surfaces:
        for e in s.entries:
            if e.segment:
                out[e.concept_id] = f"{config.SDKB_DATA}{e.segment}/{e.slug}"
    return out


def concept_types(surfaces: tuple[Surface, ...]) -> dict[str, str]:
    """IRI → concept_type(축 후보). 그래프 `rdf:type` 이 없을 때의 2순위 근거."""
    uni = concept_universe(surfaces)
    types: dict[str, str] = {}
    for s in surfaces:
        for e in s.entries:
            iri = uni.get(e.concept_id)
            if iri and e.concept_type:
                types[iri] = e.concept_type
    return types


def summary(surfaces: tuple[Surface, ...]) -> dict:
    """프로파일·보고용 집계(발화 여부는 모른다 — 그것은 적용기의 관측이다)."""
    ents = [e for s in surfaces for e in s.entries]
    return {
        "n_surfaces": len(surfaces),
        "n_bound": sum(1 for s in surfaces if s.bound),
        "n_hangul_only": sum(1 for s in surfaces if not s.bound),
        "n_entries": len(ents),
        "n_concepts": len({e.concept_id for e in ents}),
        "n_slugs": len({e.slug for e in ents}),
        "n_ambiguous_surfaces": sum(1 for s in surfaces if len(s.entries) > 1),
    }
