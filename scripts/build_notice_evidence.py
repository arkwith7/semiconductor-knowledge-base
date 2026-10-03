#!/usr/bin/env python3
"""PLAN-005 단계 2-A — 의견제출통지서에서 거절근거(`legal_basis`)를 추출해 엣지에 부착한다.

설계: [PLAN-005 §10](../01.code_spec/plans/PLAN-005-prior-art-tool-qualification.md)
관찰: [단계 2 분석](../01.code_spec/reports/PLAN-005-stage2-notice-analysis.md)

**왜 하는가.** 심사관 엣지 2,534건의 `legal_basis` 가 전량 공란이라 거절근거별 하위집단
분석 자체가 막혀 있다. 채워진 656건은 전부 거절결정서 유래(`source_type=evidence_v2`)다.

**재사용한다 — 재구현하지 않는다.** 인용발명 표기를 문헌 식별자로 바꾸는 로직은
`build_rejection_decisions.py` 에 이미 있고 거절결정서에서 검증됐다. import 해서 쓴다.
두 벌이 되면 갈린다.

**정본은 엣지 parquet 이 아니다 (§1-1).**
`data/patents/prior_art_edges.parquet` 는 `ingest_rejected_patents.py` 가 만드는 **빌드
산출물**이고 Makefile 이 `rm -f` 한다. 거기에 직접 쓰면 다음 빌드에 조용히 사라지고, 그 사이
벤더해 간 하류는 유령 데이터를 갖는다 — TTL 에 대한 §1-1 의 경고가 그대로 적용된다.
그러므로:

    정본  data/patents/notice_legal_basis.parquet   ← 이 생성기의 산출물
    부착  --apply 로 엣지의 legal_basis 컬럼을 채운다 (멱등 · 재빌드 후 다시 돌리면 된다)
          --edges-only 는 커밋된 정본만 읽어 부착만 한다 (평가 타깃 선행조건 · §20.18)

**다중 근거를 뭉개지 않는다 (§10.9 개정).** 첫 설계는 한 (출원, 인용) 쌍에 근거가 여럿이면
§29① 을 우선했고, 그 tie-break 가 결정서와의 교차 검증을 0.8807 로 끌어내렸다 — 불일치 76건
중 48건은 통지서가 결정서 값도 **함께** 담고 있었다. 뭉개기를 없애고 **새 컬럼 `legal_bases`**
에 `|` 결합 다중값을 쓴다.

**기존 `legal_basis` 는 건드리지 않는다 (§1-3).** 그 컬럼은 `evidence_v2` 의 단일값 계약으로
이미 소비되고 있고(`build_abox_claim_features.py:428`), 같은 이름에 두 가지 값 모양을 두면
이름이 의미와 달라진다. 새 의미에는 새 이름을 준다.

**하류를 깨지 않는다.** 새 `source_type` 을 만들지 않는다. 테스트는 `source_type` 을
부분집합으로만 검사하고 엣지의 컬럼 집합을 고정하지 않는다. ABox 생성기는 `evidence_v2` 만
읽으므로 **ABox·TBox·shape·IRI 는 불변**이다.

**누출 규율.** `legal_basis` 는 정답 간선의 속성이다(§1.6-4). **평가 하위집단 분해에만 쓰고
랭커 입력에 넣지 않는다.**

**LLM 을 쓰지 않는다** — 통지서에는 심사관 실명이 있어 §1-5 가 외부 전송을 금한다. 정규식과
정렬만 쓰므로 결정적이다: 같은 원천 → 같은 산출.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_rejection_decisions import (  # noqa: E402  재사용 — 재구현 금지
    _normalize_cited_id,
)

# **콜론을 필수로 한다 (교정 3).** 공유 `_CITED_LINE_RX` 는 콜론이 선택이라
# `인용발명 1"이라 함)` 같은 서술을 정의줄로 오탐한다(정규화 실패 176건의 다수).
# 공유 함수를 고치지 않는 이유: 거절결정서 파이프라인이 만든 656건의 확립된 값이
# 함께 흔들린다 — 그것은 별개의 계약이다.
CITED_LINE_RX = re.compile(r"인용발명\s*(\d+)\s*[:：]\s*([^\n]{5,200})")

# **공유 정규화가 놓치는 표기의 보완 (교정 4).** 원문 실측에서 나온 두 형태다.
KR_REG_DASH_RX = re.compile(r"등록특허공보\s*제\s*10[-\s]?(\d{6,7})\s*호")
JP_KOR_RX = re.compile(r"일본[^\n]{0,12}공개특허공보\s*제?\s*(?:평|소|H|S)?\s*(\d{2,4})\s*[-\s]\s*(\d{4,7})")


# **관청별 보완 (파서 교정 2026-09-30 · §20.17).** 미채움 심사관 간선의 최대 원인은 콜론이 아니라
# 정규화 실패였다(콜론형 정의줄 350줄 · 간선 235건). 출력 형식은 간선의 KIPRIS 식별자 형식에
# 맞춘다 — claim-features A-Box 가 `cited_map` 을 **정확 일치**로 조회하기 때문이다.
# 기존 규칙 **뒤에만** 둔다: 기존 규칙이 잡던 표기의 출력은 한 글자도 바뀌지 않는다.
WO_RX = re.compile(r"WO\s*(\d{4})\s*/\s*(\d{5,6})(?!\d)")
CN_RX = re.compile(r"(?:중국|CN)[^\n]{0,20}?(?<!\d)(\d{9})(?!\d)")
EP_RX = re.compile(r"EP\s*(\d{6,7})(?!\d)")
JP_TOKUHYO_RX = re.compile(r"특표\s*(\d{4})\s*-\s*(\d{1,6})(?!\d)")
JP_GRANT_RX = re.compile(r"일본[^\n]{0,15}?특허공보[^\n]{0,6}?특허\s*제?\s*(\d{7})\s*호")
KR_OLD_PUB_RX = re.compile(r"공개특허(?:공보)?\s*제?\s*((?:19|20)\d{2})\s*-\s*(\d{4,7})\s*호")
KR_UTIL_RX = re.compile(r"실용신안[^\n]{0,8}?제?\s*20\s*-\s*((?:19|20)\d{2})\s*-\s*(\d{7})(?!\d)")
US_PUB_KOR_RX = re.compile(r"미국[^\n]{0,12}?공개[^\n]{0,8}?(?:US\s*)?((?:19|20)\d{2})\s*/?\s*(\d{7})(?!\d)")
US_PUB_WORD_RX = re.compile(r"공개\s*특허|특허\s*공개|공개\s*공보")
US_GRANT_KOR_RX = re.compile(r"미국[^\n]{0,15}?(?:US\s*)?제?\s*(\d{7,8})(?!\d)")


def normalize_cited(raw: str) -> str | None:
    """공유 정규화를 먼저 쓰고, 놓친 형태만 보완한다."""
    n = _normalize_cited_id("", raw)
    if n:
        return n
    m = KR_REG_DASH_RX.search(raw)
    if m:
        return f"KR-G-{m.group(1)}"
    m = JP_KOR_RX.search(raw)
    if m:
        return f"JP-P-{m.group(1)}{m.group(2).zfill(6)}"
    # ── 교정 2026-09-30 보완 ──
    m = WO_RX.search(raw)
    if m:
        return f"WO-P-{m.group(1)}{m.group(2).zfill(6)}"
    m = JP_TOKUHYO_RX.search(raw)
    if m:
        return f"JP-P-{m.group(1)}{m.group(2).zfill(6)}"
    m = JP_GRANT_RX.search(raw)
    if m:
        return f"JP-G-{m.group(1)}"
    m = CN_RX.search(raw)
    if m:
        return f"CN-P-{m.group(1)}"
    m = EP_RX.search(raw)
    if m:
        return f"EP-P-{m.group(1).zfill(8)}"
    m = KR_UTIL_RX.search(raw)
    if m:
        return f"KR-G-20{m.group(1)}{m.group(2)}"
    m = KR_OLD_PUB_RX.search(raw)
    if m:
        return f"KR-P-10{m.group(1)}{m.group(2).zfill(7)}"
    m = US_PUB_KOR_RX.search(raw)
    if m:
        return f"US-P-{m.group(1)}{m.group(2)}"
    if not US_PUB_WORD_RX.search(raw):     # `(2006.10.10. 공개)` 같은 날짜 주석의 '공개' 는 막지 않는다
        m = US_GRANT_KOR_RX.search(raw)
        if m:
            return f"US-G-{m.group(1).zfill(8)}"
    return None


# ── 인용 인식 (교정 2026-09-30) ─────────────────────────────────────────────
# 라벨은 콜론이 선택이고 용어가 넷이다(실측: 무콜론 194 · 비교대상발명 68 · 선행발명 13 · 인용문헌 3).
# 라벨이 없는 줄도 근거절 안에서 정규화에 성공하면 인정한다(2단계 결정 ① · 151건) — 정밀도는
# 새 채움 표본(주-2″)이 막는다.
LABEL_RX = re.compile(r"(?:인용발명|비교대상발명|선행발명|인용문헌)\s*\d+\s*([:：])?")
FORM_RANK = {"colon": 0, "label": 1, "unlabeled": 2, "reference": 3}


def cited_in_section(seg: str, app: str = "") -> dict[str, str]:
    """절 안의 인용문헌 → 인식 경로(`colon`·`label`·`unlabeled`). 본원 번호는 제외한다.

    옛 콜론 규칙의 결과를 **합집합으로 보존**한다 — 교정이 기존 인식을 잃지 않게.
    """
    found: dict[str, str] = {}

    def put(nid: str | None, form: str) -> None:
        if not nid or (app and loose_key(nid) == loose_key(f"KR-P-{app}")):
            return
        if nid not in found or FORM_RANK[form] < FORM_RANK[found[nid]]:
            found[nid] = form

    for c in CITED_LINE_RX.finditer(seg):
        put(normalize_cited(c.group(2)), "colon")
    for line in seg.splitlines():
        labels = list(LABEL_RX.finditer(line))
        cuts = [0] + [m.start() for m in labels] + [len(line)]
        for a, b in zip(cuts, cuts[1:]):
            chunk = line[a:b]
            if not chunk.strip():
                continue
            lm = LABEL_RX.match(chunk)
            form = "unlabeled" if not lm else ("colon" if lm.group(1) else "label")
            body = chunk[lm.end():] if lm else chunk
            put(normalize_cited(body[:200]), form)
    return found


# ── 대상 청구항 (교정 2026-09-30) ───────────────────────────────────────────
# 공유 `_CLAIM_FOCUS_RX` 는 `청구항 제N항`(6,630회)을 못 잡고 `N 내지 M`·`N~M` 의 가운데를
# 잃는다. 공유 함수는 거절결정서 계약이라 두고, 통지서 전용으로 새로 둔다.
CLAIM_REF_RX = re.compile(
    r"청구항\s*(?:제\s*)?(\d{1,3})\s*(?:항)?"
    r"((?:\s*(?:,|및|또는|내지|~|∼)\s*(?:청구항\s*)?(?:제\s*)?\d{1,3}\s*(?:항)?)*)")
_CL_TAIL_RX = re.compile(r"\s*(,|및|또는|내지|~|∼)\s*(?:청구항\s*)?(?:제\s*)?(\d{1,3})\s*(?:항)?")
# 인용문헌의 청구항 — `인용발명 1의 청구항 3`, `비교대상발명2에 기재된 청구항 5`
CITED_CLAIM_CTX_RX = re.compile(
    r"(?:인용발명|비교대상발명|선행발명|인용문헌)\s*\d+\s*(?:의|에\s*기재된)\s*(?:\S{0,8}\s*)?$")
MAX_RANGE = 200


def parse_claim_refs(seg: str) -> list[int]:
    """절이 겨냥하는 본원 청구항 번호. 범위를 전개하고 인용문헌 문맥의 번호를 뺀다."""
    out: set[int] = set()
    for m in CLAIM_REF_RX.finditer(seg):
        if CITED_CLAIM_CTX_RX.search(seg[max(0, m.start() - 25):m.start()]):
            continue
        prev = int(m.group(1))
        nums = {prev}
        for t in _CL_TAIL_RX.finditer(m.group(2) or ""):
            n = int(t.group(2))
            if t.group(1) in ("내지", "~", "∼") and prev < n <= prev + MAX_RANGE:
                nums.update(range(prev, n + 1))
            else:
                nums.add(n)
            prev = n
        out.update(x for x in nums if x > 0)
    return sorted(out)


# §29① 의 호 — 제1호 공지·공연실시 / 제2호 간행물·전기통신회선. 실측 제2호 281 · 제1호 4 · 무표기 4.
# `legal_basis` 값에 넣지 않는다: A-Box 는 `GROUND[legal_basis]`, 평가 층은 `"§29①" in x` 로 읽는다.
SUBCLAUSE_RX = re.compile(r"제\s*29\s*조\s*(?:제)?\s*1\s*항\s*제\s*([12])\s*호")


def subclause_of(seg: str) -> str:
    return "|".join(sorted({m.group(1) for m in SUBCLAUSE_RX.finditer(seg)}))


def loose_key(doc_id: str) -> str:
    """자릿수 채움 차이를 흡수한 매칭 키 — `US-G-07118954` 와 `US-G-7118954` 는 같은 문헌이다."""
    m = re.match(r"([A-Z]{2}-[A-Z])-0*(\d+)$", str(doc_id))
    return f"{m.group(1)}-{m.group(2)}" if m else str(doc_id)

TXT_DIR = ROOT / "data" / "sources" / "opinion_notices" / "txt"
STRUCT_DIR = ROOT / "data" / "sources" / "opinion_notices" / "structured"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
CANON = ROOT / "data" / "patents" / "notice_legal_basis.parquet"
REPORT = ROOT / "data" / "reports" / "notice_evidence_report.json"

# ① 절 분할 — 통지서의 96.3% 가 이 형태를 갖는다.
# **[구체적인 거절이유] 이후로 한정한다 (2026-09-06 교정).** 문서 머리의 정형 안내
# ("1. 이 출원에 대한 심사결과 … 제63조에 따라 …")도 같은 형태라, 그대로 두면 그 절이
# 뒤따르는 [심사결과] 표를 통째로 삼켜 **출원 전체의 근거를 개별 인용문헌에 잘못 붙인다**.
# 실측: 정형절 1,018개 중 **294개가 §29 와 인용발명을 함께 담고 있었다.**
# 표지는 1,148/1,155(99.4%)에 있고, 없으면 정형절만 제외하고 진행한다.
# **절 번호는 선택이다 (2026-09-06 교정 2).** 번호 없이 "이 출원의 청구범위의 …" 로 바로
# 시작하는 문서가 있고, 번호를 필수로 두면 그런 문서는 **절 0개**가 되어 통째로 버려진다.
# 실측: 미채움 1,471건 중 **679건이 "정의줄은 문서에 있으나 절 밖"** 이었고 그 원인이 이것이다.
SECTION_RX = re.compile(r"^\s*(?:(\d+)\s*\.\s*)?이\s*출원(?=[은의])", re.M)
DETAIL_RX = re.compile(r"\[\s*구체적인\s*거절이유\s*\]")
BOILER_RX = re.compile(r"이\s*출원에\s*대한\s*심사결과")
# ② 절 → 법조항. 조문 표기 흔들림(제29조제1항 / 제 29 조 제 1 항)을 흡수한다
BASIS_29_RX = re.compile(r"제\s*29\s*조\s*(?:제)?\s*([1-4])\s*항")
BASIS_42_RX = re.compile(r"제\s*42\s*조")

LB = {"1": "§29①", "2": "§29②", "3": "§29③", "4": "§29④"}


# **첨부 목록은 절이 아니다 (교정 2026-09-30 · 4단계 발견 · 3단계 복귀 승인).** 절은 다음 절까지
# 이어지므로 마지막 절이 통지서 끝의 `[첨 부]` 인용문헌 목록을 삼킨다. 라벨 없는 번호를 인정하자
# 그 목록이 마지막 절의 근거에 붙었다(§42 간선 2 → 163). 표지는 1,155/1,155 에 있고 표지 뒤에서
# 근거 절이 시작되는 문서는 0 이므로, 절은 표지 앞에서 끊는다.
ATTACH_RX = re.compile(r"\[\s*첨\s*부\s*\]|<<\s*안\s*내\s*>>")
# 절이 라벨로만 가리키는 문헌(`인용발명 2 에 의하여 …`)은 **문서 전체의 정의**로 해소한다 — 정의가
# 첨부 목록에만 있는 통지서가 있다. 정의가 둘 이상으로 갈리는 라벨은 해소하지 않는다.
LABEL_REF_RX = re.compile(r"(인용발명|비교대상발명|선행발명|인용문헌)\s*(\d+)")


def label_definitions(body: str, app: str = "") -> dict[tuple[str, int], str]:
    """(라벨 용어, 번호) → 문헌. 정의가 유일한 라벨만 싣는다."""
    seen: dict[tuple[str, int], set[str]] = {}
    for line in body.splitlines():
        labels = list(LABEL_RX.finditer(line))
        for i, lm in enumerate(labels):
            end = labels[i + 1].start() if i + 1 < len(labels) else len(line)
            nid = normalize_cited(line[lm.end():end][:200])
            if not nid or (app and loose_key(nid) == loose_key(f"KR-P-{app}")):
                continue
            k = LABEL_REF_RX.match(lm.group(0))
            seen.setdefault((k.group(1), int(k.group(2))), set()).add(nid)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def parse_notice(text: str, app: str = "") -> list[dict]:
    """절 단위로 (법조항, 인용발명 식별자, 대상 청구항, 호, 인식 경로)를 뽑는다."""
    dm = DETAIL_RX.search(text)
    body = text[dm.end():] if dm else text        # 표지가 있으면 그 뒤만 본다
    defs = label_definitions(body, app)           # 정의는 첨부 목록까지 포함해 모은다
    am = ATTACH_RX.search(body)
    body = body[:am.start()] if am else body      # 절은 첨부 표지 앞에서 끊는다
    parts = list(SECTION_RX.finditer(body))
    out = []
    for i, m in enumerate(parts):
        end = parts[i + 1].start() if i + 1 < len(parts) else len(body)
        seg = body[m.start():end]
        if BOILER_RX.search(seg[:60]):            # 정형 안내 절은 버린다
            continue

        bases = [LB[b] for b in dict.fromkeys(x.group(1) for x in BASIS_29_RX.finditer(seg))]
        if not bases and BASIS_42_RX.search(seg):
            bases = ["§42"]
        if not bases:
            continue

        forms = cited_in_section(seg, app)
        for r in LABEL_REF_RX.finditer(seg):
            nid = defs.get((r.group(1), int(r.group(2))))
            if nid and nid not in forms:
                forms[nid] = "reference"
        out.append({"section": int(m.group(1)) if m.group(1) else i + 1, "legal_bases": bases,
                    "cited_ids": sorted(forms),
                    "cite_forms": {k: forms[k] for k in sorted(forms)},
                    "target_claims": parse_claim_refs(seg),
                    "subclause": subclause_of(seg) if "§29①" in bases else ""})
    return out


SAMPLE_CSV = ROOT / "data" / "interim" / "notice_legal_basis_sample.csv"
SAMPLE_V2_CSV = ROOT / "data" / "interim" / "notice_legal_basis_sample_v2.csv"
KEY = ["application_number", "cited_doc_id", "legal_basis"]


def collapse_rows(rows: list[dict]) -> pd.DataFrame:
    """(출원, 인용, 근거) 한 행으로 모은다.

    `section`·`source_file` 은 **첫 기여 절**(옛 `drop_duplicates` 와 같은 값)이고,
    `target_claims` 는 기여한 모든 절의 **합집합**이다 — 옛 방식은 첫 절 밖의 청구항을 버렸다.
    호는 합집합, 인식 경로는 가장 강한 것(colon > label > unlabeled).
    """
    cols = KEY + ["section", "target_claims", "source_file", "subclause", "cite_form"]
    agg: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(r[c] for c in KEY)
        if k not in agg:
            agg[k] = {**r, "target_claims": set(r["target_claims"]),
                      "subclause": set(filter(None, r["subclause"].split("|")))}
            continue
        a = agg[k]
        a["target_claims"].update(r["target_claims"])
        a["subclause"].update(filter(None, r["subclause"].split("|")))
        if FORM_RANK[r["cite_form"]] < FORM_RANK[a["cite_form"]]:
            a["cite_form"] = r["cite_form"]
    out = [{**a, "target_claims": ",".join(map(str, sorted(a["target_claims"]))),
            "subclause": "|".join(sorted(a["subclause"]))} for a in agg.values()]
    return pd.DataFrame(out, columns=cols)


#: 손실 기준의 **동결 예외** (3단계 복귀 승인 2026-09-30). 옛 값이 첨부 목록에서 나온 오귀속이라
#: 교정이 값을 바꾸는 간선이다. 목록 밖의 손실·변경이 하나라도 있으면 `--apply` 는 멈춘다.
LOSS_EXCEPTIONS = {
    ("1020120130403", "KR-P-1020070090814"): "옛 §42 는 [첨 부] 목록 유래 오귀속 → §29②",
}


def edge_delta(before: list[str], after: list[str], keys: list[tuple[str, str]] | None = None) -> dict:
    """간선별 근거 집합의 전후. **손실·변경은 예외 목록 밖에서 0 이어야 한다**(추가만 허용)."""
    d = Counter()
    keys = keys or [("", "")] * len(before)
    for b, a, k in zip(before, after, keys):
        sb, sa = set(filter(None, b.split("|"))), set(filter(None, a.split("|")))
        if not sb and not sa:
            continue
        d["filled_before"] += bool(sb)
        d["filled_after"] += bool(sa)
        if not sb:
            d["newly_filled"] += 1
        elif not sb <= sa:
            d["changed_by_exception" if k in LOSS_EXCEPTIONS else "lost_or_changed"] += 1
        elif sb < sa:
            d["extended"] += 1
        else:
            d["unchanged"] += 1
    return {k: int(d[k]) for k in ("filled_before", "filled_after", "unchanged", "extended",
                                   "newly_filled", "changed_by_exception", "lost_or_changed")}


def assert_additive(delta: dict) -> None:
    if delta["lost_or_changed"]:
        raise SystemExit(f"ERROR: 기존 legal_bases 가 줄거나 바뀐 간선 {delta['lost_or_changed']}건 — "
                         "교정은 추가만 허용한다(2단계 동결 기준 · 예외는 LOSS_EXCEPTIONS). 엣지에 쓰지 않았다.")


def ground_sets(canon: pd.DataFrame) -> tuple[dict, dict]:
    """정본의 (출원, 인용) 근거 집합과, 자릿수 채움 차이를 흡수한 느슨한 키 판."""
    # §10.9 — tie-break 없음. (출원, 인용) 의 근거 **집합**을 그대로 싣는다.
    sets = (canon.groupby(["application_number", "cited_doc_id"]).legal_basis
                 .apply(lambda s: "|".join(sorted(set(s)))).to_dict())
    # 자릿수 채움 차이를 흡수해 매칭한다 (교정 5) — 실측 35건이 이것만으로 갈렸다
    loose = {}
    for (app, cid), v in sets.items():
        loose.setdefault((app, loose_key(cid)), set()).update(v.split("|"))
    return sets, {k: "|".join(sorted(v)) for k, v in loose.items()}


def _app_no(ed: pd.DataFrame) -> pd.Series:
    return ed.target_patent_id.str.replace("^patent:kr_", "", regex=True)


def _prior_bases(ed: pd.DataFrame) -> list[str]:
    if "legal_bases" not in ed.columns:
        return [""] * len(ed)
    return list(ed["legal_bases"].fillna("").astype(str))


def edge_values(ed: pd.DataFrame, loose: dict) -> list[str]:
    """간선 행 순서대로 붙일 legal_bases — examiner 가 아닌 간선은 빈 값."""
    ex = ed.source_type == "examiner"
    return ["" if not e else loose.get((a, loose_key(c)), "")
            for a, c, e in zip(_app_no(ed), ed.cited_doc_id, ex)]


def attach_edges_only(canon_path: Path | None = None, edges_path: Path | None = None) -> dict:
    """커밋된 정본만 읽어 간선에 붙인다 — 통지서를 다시 파싱하지 않고 정본·리포트·structured 를 쓰지 않는다.

    평가 타깃의 선행조건이다(PLAN-005 §20.18). 전체 재생성(`main`)을 선행조건으로 걸면 실행마다
    커밋된 리포트의 교정 전후 델타가 "전부 불변" 으로 덮인다 — 두 번째 실행부터 전이 곧 후이기 때문이다.
    """
    canon_path, edges_path = canon_path or CANON, edges_path or EDGES
    ed = pd.read_parquet(edges_path)
    _, loose = ground_sets(pd.read_parquet(canon_path))
    applied = edge_values(ed, loose)
    delta = edge_delta(_prior_bases(ed), applied, list(zip(_app_no(ed), ed.cited_doc_id)))
    assert_additive(delta)
    ed["legal_bases"] = applied
    ed.to_parquet(edges_path, index=False)
    return delta


def _over_claims(canon: pd.DataFrame) -> dict:
    """서술 통계 — 공개 시점 청구항 수를 넘는 번호. **오염 판정이 아니다**: 심사 시점 청구항 수의
    권위 원천이 없고(`kipris_biblio` 에 없음), 자진보정으로 청구항이 늘었을 수 있다(2단계 실측)."""
    meta = pd.read_parquet(ROOT / "data" / "patents" / "rejected_patents_meta.parquet")
    lim = dict(zip(meta.application_number, pd.to_numeric(meta.n_claims_full, errors="coerce")))
    checked = over = 0
    for app, tc in zip(canon.application_number, canon.target_claims):
        nums = [int(x) for x in str(tc).split(",") if x]
        n = lim.get(app)
        if not nums or n is None or n != n:
            continue
        checked += 1
        over += any(x > n for x in nums)
    return {"checked": checked, "over": over, "is_gate": False}


def _gate_result(path: Path = SAMPLE_CSV, name: str = "주-2′ 사람 표본 원문 대조") -> dict:
    """사람이 채운 표본이 있으면 그 값으로 게이트를 판정한다(§10.10).

    시트 자체는 통지서 원문 발췌를 담으므로 `data/interim/`(gitignore·발행 DENY)에 있고,
    여기에는 **집계만** 남긴다.
    """
    g = {"name": name, "threshold": 0.90}
    if not path.exists():
        return {**g, "status": "미산출 — 이것 없이 A 를 완료로 보고하지 않는다"}
    # 문자열로 읽는다 — 빈 칸(보류)이 섞이면 pandas 가 열을 실수로 읽어 `1` 이 `"1.0"` 이 되고
    # 매핑이 전부 빠져 "미기입" 으로 오판된다(2026-10-03 실측).
    d = pd.read_csv(path, dtype=str)
    v = d["correct"].fillna("").str.strip().map({"1": 1, "0": 0}).dropna()
    if v.empty:
        return {**g, "status": "시트는 있으나 미기입"}
    rate = float(v.mean())
    res = {**g, "status": "충족" if rate >= 0.90 else "미달",
           "n": int(len(v)), "correct": int(v.sum()), "rate": round(rate, 4),
           "withheld": int(len(d) - len(v))}     # 판정 보류 — 분모에서 빠진 행
    if path == SAMPLE_CSV:
        res["residual_error_mode"] = ("틀린 건은 절 경계 오귀속이다 — `이 출원은/의` 앵커가 "
                                      "근거 진술이 아닌 논의 문장에도 걸려, 이웃 구간의 근거가 "
                                      "잘못 붙는다(§42 논의에 §29② 가 붙은 사례 확인).")
    return res


#: 교정 전 정본이 있는 커밋 — "새로 채워진 쌍" 의 기준. 엣지 상태에 기대면 `--apply` 뒤 재실행에서
#: 새 쌍이 사라지므로 커밋에 핀한다.
BASELINE_COMMIT = "ea72adf"
SAMPLE_SEED = 20260930


def _baseline_pairs() -> set[tuple[str, str]]:
    import io
    import subprocess
    blob = subprocess.run(["git", "show", f"{BASELINE_COMMIT}:{CANON.relative_to(ROOT)}"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    b = pd.read_parquet(io.BytesIO(blob))
    return {(x, loose_key(y)) for x, y in zip(b.application_number, b.cited_doc_id)}


def _pair_excerpt(app: str, cid: str, rows: pd.DataFrame) -> str:
    """근거 진술(절 머리)과 그 문헌이 인식된 줄. 원문이므로 data/interim 에만 쓴다."""
    segs = []
    for r in rows.sort_values("section").drop_duplicates(["source_file", "section"]).itertuples():
        t = (TXT_DIR / r.source_file).read_text(encoding="utf-8", errors="replace")
        dm = DETAIL_RX.search(t)
        t = t[dm.end():] if dm else t
        parts = list(SECTION_RX.finditer(t))
        for i, mm in enumerate(parts):
            if (int(mm.group(1)) if mm.group(1) else i + 1) != int(r.section):
                continue
            seg = t[mm.start():parts[i + 1].start() if i + 1 < len(parts) else len(t)]
            lines = seg.splitlines()
            hit = [j for j, ln in enumerate(lines) if cid in cited_in_section(ln, app)]
            if not hit:     # reference — 정의는 첨부 목록에 있고 절은 라벨로만 가리킨다
                lines = t.splitlines()
                hit = [j for j, ln in enumerate(lines) if cid in cited_in_section(ln, app)]
            around = " / ".join(" ".join(lines[k].split()) for j in hit[:1]
                                for k in range(max(0, j - 1), min(len(lines), j + 2)))
            segs.append(f"[{r.legal_basis}] {' '.join(seg.split())[:250]} … ⟪{around[:400]}⟫")
            break
    return "\n\n".join(segs)


def sample_new_pairs(canon: pd.DataFrame, examiner: pd.DataFrame, n: int) -> list[dict]:
    import random
    base = _baseline_pairs()
    edge_keys = {(a, loose_key(c)) for a, c in zip(
        examiner.target_patent_id.str.replace("^patent:kr_", "", regex=True), examiner.cited_doc_id)}
    pairs = sorted({(a, c) for a, c in zip(canon.application_number, canon.cited_doc_id)
                    if (a, loose_key(c)) in edge_keys and (a, loose_key(c)) not in base})
    random.Random(SAMPLE_SEED).shuffle(pairs)
    out = []
    for app, cid in pairs[:n]:
        rows = canon[(canon.application_number == app) & (canon.cited_doc_id == cid)]
        out.append({"application_number": app, "cited_doc_id": cid,
                    "extracted_legal_bases": "|".join(sorted(rows.legal_basis)),
                    "subclause": "|".join(sorted(set(filter(None, rows.subclause)))),
                    "cite_form": rows.cite_form.iloc[0],
                    "target_claims": rows.target_claims.iloc[0],
                    # 발췌가 부족하면 원문을 연다 — 파일과 절 번호(`[구체적인 거절이유]` 뒤 순서)
                    "source_file": "|".join(sorted(set(rows.source_file))),
                    "section": "|".join(map(str, sorted(set(rows.section)))),
                    "notice_section_excerpt": _pair_excerpt(app, cid, rows),
                    "correct": "", "note": ""})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="엣지 parquet 에 legal_bases(다중값) 컬럼을 채운다 (멱등)")
    ap.add_argument("--write-structured", action="store_true",
                    help="출원별 structured JSON 을 쓴다 (거절결정서와 대칭)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample", type=int, default=0,
                    help="주-2′ 사람 대조 표본 N건을 data/interim/ 에 쓴다 (시드 고정)")
    ap.add_argument("--sample-new", type=int, default=0,
                    help="주-2″ 교정으로 **새로 채워진** 쌍 N건 표본 (기준: 교정 전 커밋의 정본)")
    ap.add_argument("--edges-only", action="store_true",
                    help="커밋된 정본만 읽어 엣지에 붙인다 — 파싱·정본·리포트·structured 를 쓰지 않는다 (§20.18)")
    a = ap.parse_args()

    if a.edges_only:
        d = attach_edges_only()
        print(f"엣지 legal_bases 부착 (정본 {CANON.relative_to(ROOT)}) · 채움 {d['filled_after']} · "
              f"불변 {d['unchanged']} · 확장 {d['extended']} · 신규 {d['newly_filled']} · "
              f"예외 {d['changed_by_exception']} · 손실 {d['lost_or_changed']}")
        return 0

    files = sorted(TXT_DIR.glob("*.txt"))
    if a.limit:
        files = files[:a.limit]

    rows, per_doc, stat = [], [], Counter()
    for f in files:
        app = f.name.split("_")[0]
        text = f.read_text(encoding="utf-8", errors="replace")
        secs = parse_notice(text, app)
        stat["문서"] += 1
        if not secs:
            stat["절_0"] += 1
        stat["절"] += len(secs)
        stat["절_인용보유"] += sum(1 for s in secs if s["cited_ids"])
        for s in secs:
            for cid in s["cited_ids"]:
                for lb in s["legal_bases"]:
                    rows.append({"application_number": app, "cited_doc_id": cid,
                                 "legal_basis": lb, "section": s["section"],
                                 "target_claims": s["target_claims"],
                                 "source_file": f.name,
                                 "subclause": s["subclause"] if lb == "§29①" else "",
                                 "cite_form": s["cite_forms"][cid]})
        per_doc.append({"application_number": app, "sections": secs, "source_file": f.name})
        if a.write_structured:
            STRUCT_DIR.mkdir(parents=True, exist_ok=True)
            # **파일명은 출원번호가 아니라 원문 파일명이다 (교정 6).** 한 출원에 통지서가
            # 여러 차(라운드) 있어, 출원번호로 쓰면 뒤 파일이 앞 파일을 덮어써 라운드가
            # 사라진다 — 실측 1,155 txt 가 999 json 이 되었다. txt 와 1:1 로 맞춘다.
            (STRUCT_DIR / f"{f.stem}.json").write_text(
                json.dumps({"application_number": app, "sections": secs,
                            "source_file": f.name, "generator": "build_notice_evidence.py"},
                           ensure_ascii=False, indent=1), encoding="utf-8")

    canon = collapse_rows(rows)
    CANON.parent.mkdir(parents=True, exist_ok=True)
    canon.to_parquet(CANON, index=False)

    # ── 엣지 부착 ──────────────────────────────────────────────────────────
    ed = pd.read_parquet(EDGES)
    prior = _prior_bases(ed)
    ed["app_no"] = _app_no(ed)
    ex = ed.source_type == "examiner"
    before = int((ed.loc[ex, "legal_basis"].astype(str).str.len() > 0).sum())

    sets, loose = ground_sets(canon)
    applied = edge_values(ed, loose)
    filled = sum(1 for v in applied if v)
    multi = sum(1 for v in applied if "|" in v)

    # ── 서술 통계: 결정서 유래(evidence_v2)와의 대조 ────────────────────────
    # **게이트가 아니다**(§10.10). 단일값 비교는 폐기된 tie-break 를 재는 것이고
    # 집합 비교는 결과를 본 뒤의 수다. 두 값을 모두 남긴다.
    v2 = ed[(ed.source_type == "evidence_v2")
            & (ed.legal_basis.astype(str).str.len() > 0)][["app_no", "cited_doc_id", "legal_basis"]]
    v2 = v2.assign(ns=[loose.get((r.app_no, loose_key(r.cited_doc_id))) for r in v2.itertuples()])
    v2 = v2[v2.ns.notna() & (v2.ns != "")]
    contain = float(v2.apply(lambda r: r.legal_basis in r.ns.split("|"), axis=1).mean()) if len(v2) else None
    exact = float((v2.legal_basis == v2.ns).mean()) if len(v2) else None

    delta = edge_delta(prior, applied, [(r.app_no, r.cited_doc_id) for r in ed.itertuples()])
    if a.apply:
        assert_additive(delta)
        ed["legal_bases"] = applied
        ed.drop(columns=["app_no"]).to_parquet(EDGES, index=False)

    by_lb = Counter(b for v in applied if v for b in v.split("|"))
    rep = {
        "generated": str(date.today()), "plan": "PLAN-005 §10 (단계 2-A)",
        "deterministic": True, "llm_used": False,
        "canonical_artifact": str(CANON.relative_to(ROOT)),
        "note": ("정본은 이 parquet 이다. 엣지 parquet 은 빌드 산출물이라 재빌드 시 지워지므로 "
                 "--apply 를 다시 돌린다(§1-1). legal_basis 는 정답 간선의 속성이며 "
                 "평가 하위집단 분해에만 쓴다 — 랭커 입력 금지(§1.6-4)."),
        "documents": stat["문서"], "sections": stat["절"],
        "documents_without_section": stat["절_0"],
        "sections_with_citation": stat["절_인용보유"],
        "canonical_rows": len(canon),
        "distinct_app_cited_pairs": len(sets),
        "examiner_edges": int(ex.sum()),
        "legal_basis_untouched_on_examiner": before,  # §1-3: 기존 컬럼은 건드리지 않는다
        "legal_bases_filled": filled,
        "multi_ground_edges": multi,
        "fill_rate": round(filled / int(ex.sum()), 4),
        "by_legal_basis": dict(by_lb),
        "cross_check_vs_evidence_v2": {
            "gate": False,
            "why_not_gate": ("단일값 비교는 폐기된 tie-break 를 재고, 집합 비교는 결과를 본 뒤의 "
                             "수다(§10.10). 서술 통계로만 싣는다."),
            "overlapping_pairs": int(len(v2)),
            "exact_equality": None if exact is None else round(exact, 4),
            "containment": None if contain is None else round(contain, 4)},
        "primary_gate": _gate_result(),
        "applied_to_edges": bool(a.apply),
        # 교정 2026-09-30 (§20.17). `edges_before` 는 **이 실행 직전** 엣지 값이다 — 교정을
        # 이미 적용한 뒤 다시 돌리면 before == after 가 되는 것이 정상(멱등).
        "correction_2026_09_30": {
            "edges_before_after": delta,
            "cite_form_rows": dict(sorted(Counter(canon.cite_form).items())),
            "subclause_on_29_1": dict(sorted(Counter(
                canon.loc[canon.legal_basis == "§29①", "subclause"].replace("", "없음")).items())),
            "target_claims_empty_rows": int((canon.target_claims == "").sum()),
            "target_claims_over_n_claims": _over_claims(canon),
            "new_pair_gate": _gate_result(SAMPLE_V2_CSV, "주-2″ 새 채움 표본 원문 대조"),
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"통지서 {stat['문서']} · 절 {stat['절']} (절 없음 {stat['절_0']}) · 인용 보유 절 {stat['절_인용보유']}")
    print(f"정본 {len(canon)}행 → {CANON.relative_to(ROOT)}")
    print(f"\nexaminer 엣지 {int(ex.sum())}건 · legal_bases 채움 **{filled}** ({filled/int(ex.sum()):.1%}) · 다중근거 {multi}")
    print(f"  근거별(중복 포함): {dict(by_lb)}")
    print(f"서술통계 — 결정서 대비 겹치는 쌍 {len(v2)} · 완전일치 {exact} · 포함 {contain}  (게이트 아님)")
    # ── 주-2′ 사람 대조 표본 (§10.10 의 최종 게이트) ────────────────────────
    if a.sample:
        import random
        # 한 쌍에 여러 절이 기여했으면 **전부** 싣는다 — 한 절만 보이면 다중근거를 검증할 수 없다
        from collections import defaultdict
        contrib = defaultdict(list)
        for r in canon.itertuples():
            contrib[(r.application_number, r.cited_doc_id)].append(r)
        pairs = sorted(sets)
        random.Random(20260906).shuffle(pairs)
        out = []
        for app, cid in pairs[:a.sample]:
            segs = []
            for r in sorted(contrib[(app, cid)], key=lambda x: x.section):
                f = TXT_DIR / r.source_file
                if not f.exists():
                    continue
                t = f.read_text(encoding="utf-8", errors="replace")
                dm = DETAIL_RX.search(t)
                t = t[dm.end():] if dm else t
                parts = list(SECTION_RX.finditer(t))
                for i, mm in enumerate(parts):
                    sec_no = int(mm.group(1)) if mm.group(1) else i + 1
                    if sec_no == int(r.section):
                        end = parts[i + 1].start() if i + 1 < len(parts) else len(t)
                        segs.append(f"[{r.legal_basis}] " + " ".join(t[mm.start():end].split())[:600])
                        break
            out.append({"application_number": app, "cited_doc_id": cid,
                        "extracted_legal_bases": sets[(app, cid)],
                        "n_sections": len(segs),
                        "notice_section_excerpt": "\n\n".join(segs),
                        "correct": "", "note": ""})
        sp = ROOT / "data" / "interim" / "notice_legal_basis_sample.csv"
        sp.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out).to_csv(sp, index=False, encoding="utf-8-sig")
        print(f"\n주-2′ 대조 표본 {len(out)}행 → {sp.relative_to(ROOT)}")
        print("   `correct` 에 1/0 을 적어 주십시오 — 추출된 근거가 원문 발췌와 맞는가.")

    if a.sample_new:
        out = sample_new_pairs(canon, ed[ex], a.sample_new)
        SAMPLE_V2_CSV.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out).to_csv(SAMPLE_V2_CSV, index=False, encoding="utf-8-sig")
        print(f"\n주-2″ 새 채움 표본 {len(out)}행 → {SAMPLE_V2_CSV.relative_to(ROOT)}")
        print("   `correct` 에 1/0 — 이 문헌이 이 근거(와 호·청구항)로 인용되었는가.")

    print(f"{'적용됨' if a.apply else '미적용 (--apply 로 반영)'} · 리포트 {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
