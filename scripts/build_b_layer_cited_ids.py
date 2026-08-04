#!/usr/bin/env python3
"""CR-008 — B층 인용 식별자 목록 → 수집기·실체화기가 먹는 모집단 표.

왜 새 모듈이 필요한가. 기존 두 스크립트는 인용 문헌의 정규 IRI 를
`prior_art_edges.parquet` 에서 **조회**한다(A층 엣지표). B층 문헌은 그 표에 없고
**넣을 수도 없다** — 질의–인용 대응은 이관되지 않았고 요구해서도 안 된다(CR-008 비목표 ⓒ).
그래서 조회를 **순수 문자열 변환**으로 대체한다.

그 변환이 가능한 이유는 실측이다. 이관 파일의 각 행은 엣지표의 `cited_raw` 와 같은 표기이고,

    cited_id = "patent:" + cc.lower() + "_" + 공백제거(cited_raw)

가 **A층의 정규 표기 특허 문헌 3,135 건 전량에서 성립**한다. `tests/` 가 이 왕복을 고정한다.

**`cited_doc_id` 는 손으로 만들지 않는다 — `citation_norm.parse()` 를 쓴다.**
3단계 설계는 이것도 문자열 규칙으로 적었으나 5단계 검증에서 틀렸음이 드러났다:
KR 등록번호는 `KR101036572 B1` → `KR-G-1036572` 처럼 문서종별 접두 '10' 과 선행 0 이
**떨어진다**(A층 264 건). 그 변환의 정본은 이 저장소의 `scripts/citation_norm.py` 이고,
A층 `cited_doc_id` 를 **3,145/3,149 재현**한다(불일치 4 건은 A층 자체가 빈 값인 결손행).
직접 규칙을 쓰면 KIPRIS 캐시 키가 A층과 갈라져 이미 수집한 문서를 다시 부른다.

**A층 표기 계열 14 건(`US2015/0093880`·`JP-H08-255787`·`KR2001-29136` 등)은 이 모듈이
다루지 않는다** — 이관 파일 514 행에는 그런 표기가 **한 건도 없다**(전량 정규 표기).
새 표기가 들어오면 조용히 넘기지 말고 **중단**한다(아래 `build`).

입력 : upstream/handoff/CR-008-b-cited-ids.txt (514 행 · sha256 대조)
출력 : data/patents/b_layer_cited_population.parquet
        컬럼 = prior_art_edges 의 인용 측과 **같은 이름·같은 의미** — 수집기가 그대로 먹는다.

결정적·멱등. 같은 입력 → 같은 바이트. 타임스탬프를 넣지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from citation_norm import parse as parse_citation  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IDS = Path(
    "/home/arkwith/Dev/SKKU/sdkb-prior-art-paper/upstream/handoff/CR-008-b-cited-ids.txt"
)
DEFAULT_OUT = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"

# 이관 파일의 동결 서명 (CR-008 §입력 · 하류 data/MANIFEST.md).
# 불일치는 경고가 아니라 중단이다 — 파일이 조용히 바뀌면 동결 분모 503 이 거짓이 된다.
EXPECTED_SHA256 = "9d0a7c0fc97547a67018556504d32d0b3ac8e22d2761f98e342ab3158c4b2dff"

# 이관 파일의 정규 표기. 관할 2자 + 숫자 + (공백) + 종별코드.
# 이 형식에 **맞는 것만** 특허로 본다 — 길이·공백 같은 어림으로 NPL 을 가리면 새 표기가
# 들어왔을 때 조용히 특허로 오분류된다.
_DOC = re.compile(r"^(?P<cc>[A-Z]{2})(?P<serial>\d+)\s*(?P<kind>[A-Z]\d?)?$")

# A층 `cited_raw` 에 전례가 있는 종별코드. 뒤의 셋(X2·Y1·Y2)은 **전례가 없다**(설계 D3) —
#   Y1 KR 실용신안 등록공보 · Y2 JP 실용신안 등록공보 · X2 JP 특허공고(昭)
# 배제하지 않고 해소 결과를 5 건 개별로 리포트해 하류가 검증하게 한다.
A_LAYER_KIND_CODES = frozenset({"A", "A1", "A2", "B", "B1", "B2", "U", "U9"})
NO_A_LAYER_PRECEDENT = frozenset({"X2", "Y1", "Y2"})


@dataclass(frozen=True)
class Citation:
    country: str
    serial: str
    kind_code: str     # 표기상의 종별코드(A·B1·Y1 …). 없으면 ""
    raw: str           # 원본 표기 (공백 보존)

    @property
    def cited_id(self) -> str:
        """정규 IRI 지역명. 'KR1020090041506 A' → 'patent:kr_KR1020090041506A'.

        A층 정규 표기 3,135 건 전량에서 성립함을 테스트가 고정한다.
        """
        return f"patent:{self.country.lower()}_{re.sub(r'\s+', '', self.raw)}"

    @property
    def cited_doc_id(self) -> str:
        """수집기의 매칭 키. **정본은 `citation_norm.parse()` 다**(모듈 docstring 참조)."""
        return parse_citation(self.raw).normalized_id

    @property
    def cited_kind(self) -> str:
        """'publication' | 'grant' | 'unknown' — 같은 정본에서 나온다."""
        return parse_citation(self.raw).kind


def normalize(line: str) -> Citation | None:
    """한 행 → Citation. 정규 표기 특허 문헌이 아니면 None (= NPL 또는 미지원 표기)."""
    raw = line.strip()
    if not raw:
        return None
    m = _DOC.match(raw)
    if not m:
        return None
    return Citation(country=m.group("cc"), serial=m.group("serial"),
                    kind_code=m.group("kind") or "", raw=raw)


def verify_sha256(path: Path, expected: str = EXPECTED_SHA256) -> str:
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and got != expected:
        raise SystemExit(
            f"ERROR: 이관 파일 sha256 불일치\n"
            f"  기대 {expected}\n  실제 {got}\n"
            f"  → 동결 분모 503 이 이 파일에 걸려 있다. 파일이 바뀌었으면 CR 을 다시 받아라."
        )
    return got


def build(ids_file: Path = DEFAULT_IDS, out: Path | None = DEFAULT_OUT) -> pd.DataFrame:
    verify_sha256(ids_file)
    rows = []
    for line in ids_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        c = normalize(raw)
        if c is None:
            # NPL 은 버리지 않고 표에 남긴다 — 리포트의 별도 행이 되고, 총계 514 병기의 근거다.
            rows.append({"cited_doc_id": None, "cited_id": None, "cited_country": None,
                         "cited_kind": None, "cited_raw": raw, "kind_code": None,
                         "is_npl": True})
            continue
        doc_id = c.cited_doc_id
        if doc_id.startswith("UNKNOWN::"):
            # 특허 표기인데 정본 정규화기가 못 읽는다 = 새 표기 계열. 조용히 넘기면
            # 그 문서만 수집에서 빠지고 도달성 분모는 그대로여서 눈에 띄지 않는다.
            raise SystemExit(f"ERROR: citation_norm 이 읽지 못하는 특허 표기 — {raw!r}")
        rows.append({"cited_doc_id": doc_id, "cited_id": c.cited_id,
                     "cited_country": c.country, "cited_kind": c.cited_kind,
                     "cited_raw": c.raw, "kind_code": c.kind_code, "is_npl": False})

    df = pd.DataFrame(rows)
    # 결정적 정렬 — NPL 은 cited_id 가 없으므로 원문으로 정렬해 뒤에 둔다.
    df = df.sort_values(["is_npl", "cited_id", "cited_raw"], na_position="last")
    df = df.reset_index(drop=True)

    pat = df[~df["is_npl"]]
    if pat["cited_id"].duplicated().any():
        dups = pat.loc[pat["cited_id"].duplicated(keep=False), "cited_raw"].tolist()
        raise SystemExit(f"ERROR: 정규화 후 cited_id 중복 — {dups}")
    if pat["cited_doc_id"].duplicated().any():
        dups = pat.loc[pat["cited_doc_id"].duplicated(keep=False), "cited_raw"].tolist()
        raise SystemExit(f"ERROR: cited_doc_id 중복 — 수집 캐시 키가 충돌한다: {dups}")

    # 동결 분모(2026-08-03). 비특허로 떨어진 행이 11 이 아니면 정규화가 표기를 놓친 것이거나
    # 이관 파일이 바뀐 것이다 — 어느 쪽이든 분모 503 이 거짓이 되므로 중단한다.
    n_npl = int(df["is_npl"].sum())
    if len(pat) != 503 or n_npl != 11:
        raise SystemExit(
            f"ERROR: 동결 구성 위반 — 특허 문헌 {len(pat)}(기대 503) · NPL {n_npl}(기대 11).\n"
            f"  비특허로 떨어진 행: {df.loc[df['is_npl'], 'cited_raw'].tolist()}"
        )

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description="CR-008 B층 인용 식별자 → 모집단 표")
    ap.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()

    df = build(a.ids, a.out)
    pat = df[~df["is_npl"]]
    npl = df[df["is_npl"]]
    print(f"✓ {a.out}")
    print(f"  총계 {len(df)} · 특허 문헌 {len(pat)} (= 동결 분모) · NPL {len(npl)}")
    print(f"  관할별: {pat['cited_country'].value_counts().to_dict()}")
    odd = pat[pat["kind_code"].isin(NO_A_LAYER_PRECEDENT)]
    if len(odd):
        print(f"  A층 전례 없는 종별 {len(odd)}건 (설계 D3 · 개별 검증 대상):")
        for _, r in odd.iterrows():
            print(f"    {r['cited_raw']:<20} → {r['cited_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
