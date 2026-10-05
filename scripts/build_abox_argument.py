#!/usr/bin/env python3
"""PLAN-005 §20.22 — 논증층 A-Box 생성기 (결정적 · 의견제출통지서 전량).

**무엇을 만드는가.** 의견제출통지서 원문(`data/sources/opinion_notices/txt/`)에서 §29①·② 절을
**청구항 블록**(`가. 청구항 1에 대하여` · `2-1. 청구항 제3항` …) 단위로 나눠
`sdkb-priorart-argument.ttl` 어휘의 판단(`pa:ExaminerJudgment`)으로 옮긴다. 블록이 없는 절은
절 전체가 판단 하나다. 산출은 `ontology/sdkb-abox-argument.ttl`(gitignore)과 계수만 담은 리포트.

**왜 블록인가 (§20.22 2단계 A1).** 블록은 심사관이 판단을 실제로 나눈 단위다. R1 파일럿의 판단은
카드가 단위 여러 개를 결손 유형별로 묶은 것이라 단위가 다르다 — 그래서 파일럿과는 **청구항 단위로**
대조한다(`--eval-pilot`).

**싣지 않는 것.** 선택적 근거("또는")와 기준 문헌은 규칙으로 가리지 못해 묶음을 블록당 하나로 둔다.
H3 수치 구간은 범위 밖(A2). H2 는 좌표(단락·도면)와 그 귀속 문헌만 — 청구항·문헌 용어는 원문이라
적재하지 않는다(A3). 해소된 문헌도 상식 표지도 없는 블록은 판단을 만들지 않고 사유를 센다 —
shape 를 우회하지 않기 위해서다.

**참조.** `[거절이유 2-1]에서 검토한 바와 같이` 는 그 라벨의 판단으로(`refersToJudgment`), 청구항 Y 의
거절이유를 그대로 쓰는 문장은 Y 를 다룬 판단으로 잇는다. "청구항 X 는 청구항 Y 를 카테고리를 달리하여"
는 `categoryVariantOf` 와 상위 술어 `refersToJudgment` 를 함께 적는다(1홉 실체화 — 추론기 없는
배치에서 R-e 규칙이 그대로 발화하도록). 대상이 유일하지 않으면 잇지 않고 사유를 센다.

CLI:
    python scripts/build_abox_argument.py
    python scripts/build_abox_argument.py --eval-pilot        # 동결 문턱 대조 (미달이면 exit 1)
    python scripts/build_abox_argument.py --sample            # 사람 대조 시트 (data/interim/)
    python scripts/build_abox_argument.py --gate              # 사람 대조 결과 집계
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config.namespaces import SDKB_DATA, SDKB_PA, SDKB_PA_KR  # noqa: E402
from build_priorart_modules import _emit  # noqa: E402
import build_notice_evidence as N  # noqa: E402
from build_abox_claim_features import _doc_key, _loose_map  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "data" / "sources" / "opinion_notices" / "txt"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
B_LAYER_POP = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"
CLAIMS = ROOT / "mappings" / "claim_features.parquet"
SPLIT = ROOT / "benchmark" / "assets" / "split.csv"
ARG_TTL = ROOT / "ontology" / "sdkb-priorart-argument.ttl"
OUT = ROOT / "ontology" / "sdkb-abox-argument.ttl"
REPORT = ROOT / "data" / "reports" / "abox_argument_report.json"
PILOT_DIR = ROOT / "data" / "sources" / "notice_dissection"
SAMPLE_CSV = ROOT / "data" / "interim" / "argument_abox_sample.csv"

PA, PAKR, D = SDKB_PA, SDKB_PA_KR, SDKB_DATA
GROUND = {"§29①": PAKR.Ground_29_1, "§29②": PAKR.Ground_29_2}
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"
# 원천 표기는 생성기와 원천 디렉터리만 가리킨다 — 통지서 파일명은 IRI 의 stem 으로만 남는다(abox-priorart 와 같은 examdoc).
SOURCE = "scripts/build_abox_argument.py -> data/sources/opinion_notices/txt"
PREFIXES = {"pa": str(PA), "pakr": str(PAKR), "xsd": str(XSD), "dcterms": str(DCTERMS), "rdf": str(RDF)}

#: 결과 전에 동결한 문턱 (§20.22 2단계 A4 · 사용자 승인 2026-10-04).
PILOT_CLAIM_COVERAGE_MIN = 0.90
PILOT_DOC_MATCH_MIN = 0.80
HUMAN_RATE_MIN = 0.90
# 2차 표본 (§20.22 3단계 복귀 F6 · 사용자 승인 2026-10-04). 1차(시드 20261004)는 원인 진단에 썼으므로 그
# 통지서는 표본에서 뺀다 — 진단에 쓴 사례로 다시 검정하면 고친 것을 외운 셈이다.
# 3차 표본 (§20.22 3단계 재복귀 G1–G6 · 사용자 결정 (가) 2026-10-04): train 에서 새로 뽑되 1·2차 통지서는 뺀다.
# 1·2차 통지서를 빼면 train 에 범주 변형이 1건뿐이라, 범주 변형은 2차 사람 판정(5/5)을 **이어받고** 그 5 관계가
# 고친 생성기에서도 그대로 나오는지만 기계로 확인한다(`variant_continuity`).
# 4차 (§20.22 (f⁶) · 사용자 지시 10-04): 코드를 동결한 뒤 **출원 단위**로 1–3차와 분리한 새 표본으로 판정한다
# (같은 출원의 다른 통지서가 양쪽에 섞이지 않게). 지난 표본은 회귀 확인(`--regress`)에만 쓴다.
SAMPLE_SEED = 20261007
SAMPLE_PRIOR = [ROOT / "data" / "interim" / f"argument_abox_sample_r{i}.csv" for i in (1, 2, 3)]
CARRY_KIND, CARRY_SHEET, CARRY_SEED = "categoryVariantOf", SAMPLE_PRIOR[1], 20261005
#: 채점 기준 (4차부터 고정 · PLAN §20.22 (f⁶)). 보류가 그 종류 행의 20% 를 넘으면 그 종류는 판정 불가(통과 아님).
WITHHELD_MAX = 0.20
TEXT_MAX = 3000
SAMPLE_BLOCKS = 30
SAMPLE_PER_SIGNAL = 10

# ── 블록 머리줄 ──────────────────────────────────────────────────────
# 표지(가. · (1) · 2-1. · ① · - …) 뒤의 `청구항 N`, 또는 표지 없이 `청구항 N` 뒤 40자 안에 판단 단위를
# 여는 말(인용·종속·부가·추가·에 대하여·에 관하여·에 있어서)이 오는 줄. `따라서 청구항 …` 같은 결론 문장은
# 줄 머리가 `청구항` 이 아니라 걸리지 않는다. 형식 빈도는 §20.22 2단계 관찰.
MARK = (r"(?P<mark>\d+\s*-\s*\d+(?:\s*-\s*\d+)?\s*[\.\)]?|\d+\.\d+(?:\.\d+)?\.?|[가-하]\s*[\.\)]|\(\s*(?:\d+|[가-하])\s*\)"
        r"|\d+\s*[\.\)]|[①-⑳]|[-•·□○◦▶■]|[<\[(【])")
CL = r"(?:(?:독립|종속)\s*)?(?:본원\s*(?:발명의\s*)?)?청구항\s*(?::\s*청구항\s*)?(?:제\s*)?\d{1,3}"
# 표지가 있으면 `청구항` 없이 `제N항` 만으로도 연다(`1. 제1항` · `1-1. 제10항은`).
CL_MARKED = r"(?:" + CL + r"|(?:(?:독립|종속)\s*항\s*)?제\s*\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s*항)"
HEAD_RX = re.compile(r"^[ \t]*(?:" + MARK + r"[ \t]*[<\[(【]?[ \t]*" + CL_MARKED + r"|" + CL +
                     r"(?=[^\n]{0,40}?(?:인용|종속|부가|추가|에\s*대하여|에\s*관하여|에\s*있어서"
                     r"|의\s*(?:부가적인\s*|추가적인\s*)?(?:기술적\s*)?특징|\s비고\s*$)))", re.M)
# 첫 블록 앞(절 서두)에서 독립항을 판단하고 `따라서 청구항 1 발명은` 으로 맺는 통지서가 있다 — 그 결론 문장의
# 청구항으로 서두를 판단 하나(_b0)로 둔다.
CONCL_RX = re.compile(r"따라서\s*,?\s*(?:본원\s*(?:의\s*)?)?((?:청구항|제\s*\d)[^.]{0,60}?)(?:에\s*기재된\s*)?(?:발명)?\s*(?:은|는)\s")
# 머리줄의 괄호 속 인용항(`청구항 4(청구항 1 내지 3 인용)`)은 이 블록의 청구항이 아니다.
PAREN_RX = re.compile(r"[\(\[]?[^()\[\]\n]{0,40}(?:인용|종속)[^()\[\]\n]{0,10}[\)\]]")
ADDED_RX = re.compile(r"인용|종속|부가|추가|한정")
HEAD_SPAN = 80
TITLE_MAX = 40

# ── 근거·논거 신호 ────────────────────────────────────────────────────
CK_RX = re.compile(r"(?:주지|관용)\s*(?:의\s*)?(?:기술|수단|기법|사항|기술수단)|주지\s*관용"
                   r"|기술\s*상식|통상의\s*기술\s*상식|널리\s*(?:알려진|알려져\s*있|사용되는|사용되고\s*있|쓰이는|이용되는)")
RATIONALE_RX = {
    "DesignChoice": re.compile(r"설계\s*(?:변경|사항|적\s*선택)"),
    "PredictableEffect": re.compile(r"효과[^.]{0,40}?(?:예측|예상)"),
}

# ── 좌표 (H2) ─────────────────────────────────────────────────────────
# 범위(`[0010]~[0013]` · `식별번호 0034-0049` · `도 6 ~ 10`)는 범위 하나로 싣는다 — 양 끝을 따로 싣으면 사이가 사라진다.
LOC_RX = re.compile(
    r"(?:(?:식별번호|단락|문단)\s*[\[【]?\s*(?P<p1>\d{3,5})\s*[\]】]?|[\[【](?P<p2>\d{4,5})[\]】])"
    r"(?:\s*[~∼\-]\s*[\[【]?\s*(?P<p3>\d{3,5})\s*[\]】]?)?"
    r"|(?P<fig>도(?:면)?\s*(?P<fn>\d{1,3}[A-Za-z]?)(?:\s*[~∼]\s*(?P<fn2>\d{1,3}[A-Za-z]?))?)"
    r"(?=\s*(?:및|,|~|에|의|을|를|참조|\)|과|와|>))")
LABEL_NEAR = 80
APPLICANT_RX = re.compile(r"본원|이\s*출원|출원\s*발명|본\s*발명|청구항")
APPLICANT_NEAR = 30

# ── 참조 (R-e · R-c) ─────────────────────────────────────────────────
REF_LABEL_RX = re.compile(r"\[\s*거절\s*이유\s*(\d+)(?:\s*-\s*(\d+))?\s*\]\s*(?:에서|와|과)"
                          r"|상기\s*(\d+)\s*[-.]\s*(\d+)\s*\.?\s*의\s*거절\s*이유")
REF_CLAIM_RX = re.compile(r"거절\s*이유(?:와|가|를)?\s*(?:동일|그대로|마찬가지)|동일한\s*취지|동일한\s*(?:거절\s*)?이유")
CAT_RX = re.compile(r"카테고리(?:를|만|만을)?\s*(?:달리|상이|다른)")
SENT_BOUND_RX = re.compile(r"(?:다|음|함)\s*\.|[가-힣]\.\s|\n\s*\n")

LOC_VALUE_RX = re.compile(r"^(?:\[\d{3,5}\](?:~\[\d{3,5}\])?|도\d{1,3}[A-Za-z]?(?:~\d{1,3}[A-Za-z]?)?)$")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _flat(s: str) -> str:
    return re.sub(r"\s*\n\s*", " ", s)


def _norm_mark(m: str | None) -> str:
    return re.sub(r"[\s\.\)]", "", m or "")


# ── 원천 해석 ─────────────────────────────────────────────────────────

def claim_refs(s: str) -> list[int]:
    """parse_claim_refs 에 `제N항` 단독 표기를 더한다(`청구항` 이 생략된 머리줄 · 결론 문장)."""
    return N.parse_claim_refs(_as_claim(s))


PAGE_MARK_RX = re.compile(r"-\s*\d{1,3}\s*-\s*10-\d{4}-\d{7}")


def _hyphen_range(m: re.Match) -> str:
    a, b = int(m.group(1)), int(m.group(2))
    return f"청구항 {a} 내지 {b}" if a < b <= a + N.MAX_RANGE else m.group(0)


def _as_claim(s: str) -> str:
    """해석용 정규화 — 저장하는 원문은 바꾸지 않는다. `제2-7항` · `청구항 1-4` 는 범위다(H3)."""
    # 법조문(`특허법 제29조제2항` · `제42조 제4항`)의 `제N항` 은 청구항이 아니다 — `조` 뒤는 바꾸지 않는다.
    s = re.sub(r"(?<!조)(?<!조\s)제\s*(\d{1,3})\s*[-–]\s*(\d{1,3})\s*항", r"청구항 \1 내지 \2", s)
    s = re.sub(r"(?<!청구항)(?<!청구항\s)(?<!조)(?<!조\s)제\s*(\d{1,3})\s*항", r"청구항 \1", s)
    s = re.sub(r"(?<=\d)\s*[·ㆍ+]\s*(?=\d)", ", ", s)          # `8·9항` · `청구항 2+4`
    s = re.sub(r"청\s+구\s*항|청구\s+항", "청구항", s)            # 줄바꿈에 끊긴 `청 구항`
    s = PAGE_MARK_RX.sub(" ", s)                                   # 쪽 바꿈 표기 `- 3 - 10-2014-0145438`
    return re.sub(r"청구항\s*(\d{1,3})\s*[-–]\s*(\d{1,3})(?!\d)", _hyphen_range, s)


# H1 — 종속관계 설명 속 부모항(`청구항 제11항(청구항 제1항의 종속항의 형식…)` · `청구항 1 을 인용하는` · `청구항 1 에
# 있어서`)은 판단 대상이 아니다. 괄호를 지우지 않고, 그 설명에 등장한 번호만 판단 대상에서 뺀다.
CL_LIST = (r"청구항\s*(?:제\s*)?\d{1,3}(?:\s*(?:항)?\s*(?:,|및|또는|내지|~|∼|·|ㆍ|\+)\s*(?:청구항\s*)?(?:제\s*)?\d{1,3})*\s*(?:항)?"
           r"(?:\s*중\s*(?:어느\s*)?(?:한|하나의)\s*(?:항)?)?")
# `인용` 뒤가 `발명`·`문헌` 이면 문헌 라벨(`청구항 제1항 인용발명 1 비고` 표 머리)이지 종속관계가 아니다 — 회귀 29행.
DEP_RX = re.compile(r"(" + CL_LIST + r")\s*(?:의\s*종속|을\s*인용|를\s*인용|인용(?!\s*발명|\s*문헌)|의\s*종속항|에\s*있어서"
                    r"|을\s*더\s*한정|를\s*더\s*한정)")


def dependency_parents(s: str) -> set[int]:
    return {n for m in DEP_RX.finditer(_as_claim(s)) for n in N.parse_claim_refs(m.group(1))}


def judged_claims(s: str, first_only: bool = True) -> list[int]:
    """`s` 가 판단 대상으로 적은 청구항 — 부모항 제외. first_only 면 부모항이 아닌 **첫 나열**만."""
    norm = _as_claim(s)
    parents = dependency_parents(s)
    picked: list[int] = []
    for m in N.CLAIM_REF_RX.finditer(norm):
        nums = [n for n in N.parse_claim_refs(m.group(0)) if n not in parents]
        if not nums:
            continue
        picked.extend(nums)
        if first_only:
            break
    return sorted(set(picked))


def own_claims(head: str) -> list[int]:
    """머리줄이 여는 청구항 — **첫 나열만**(범위·쉼표·및 연결 포함). 종속관계 설명 속 부모항
    (`1-1. 제10항은 제1항의 종속항` 의 제1항 · `청구항 4(청구항 1 내지 3 인용)`)은 이 블록의 청구항이 아니다."""
    return judged_claims(head[:HEAD_SPAN])


def split_blocks(seg: str) -> list[dict]:
    """절 → 청구항 블록. 머리줄이 없으면 빈 목록(절 전체가 판단 하나).

    본문 없는 머리줄(`가. 청구항 1 발명` 바로 다음 줄이 `청구항 1 발명은 …에 있어서`)은 다음 블록과
    합친다 — 따로 두면 문헌 없는 빈 판단이 된다(1차 실행 실측 1,479). 청구항은 앞 머리줄 것을 쓴다.
    """
    hs = [m for m in HEAD_RX.finditer(seg)
          if (m.group("mark") or _after_sentence_end(seg, m.start())) and not _bracket_locator(seg, m)]
    out: list[dict] = []
    carry = None
    for i, m in enumerate(hs):
        end = hs[i + 1].start() if i + 1 < len(hs) else len(seg)
        nl = seg.find("\n", m.start())
        head = seg[m.start(): nl if 0 <= nl < end else end]
        blk = {"mark": _norm_mark(m.group("mark")), "head": head, "text": seg[m.start():end]}
        if carry is not None:
            title, sub = set(own_claims(carry["head"])), set(own_claims(blk["head"]))
            # H2 — 제목만 있는 상위 머리줄(`3-1. 청구항 1 내지 13`) 바로 아래의 **더 깊은 계층** 머리줄(`(1) 청구항 1~6,
            # 8~11`)이 그 부분집합이면 본문은 하위 범위에 대한 것이다. 계층이 같거나 부분집합이 아니면 둘을 합친다.
            if sub and sub < title and _mark_level(blk["mark"]) > _mark_level(carry["mark"]):
                blk = {**blk, "text": carry["text"] + blk["text"]}
            else:
                blk = {"mark": carry["mark"] or blk["mark"], "head": carry["head"], "text": carry["text"] + blk["text"],
                       "claims_extra": sorted(sub)}
            carry = None
        # 제목만 있는 줄(본문 없음 · 짧음)만 합친다 — 머리줄 자체가 문장이면 그것이 본문이다.
        title = len(head.strip()) <= TITLE_MAX and not re.search(r"[다음함]\s*\.", head)
        if not seg[m.start() + len(head):end].strip() and title and i + 1 < len(hs):
            carry = blk
            continue
        # F4 — 청구항이 같은 연속 블록(제목 줄 + 표 머리 `청구항 6 비고`)은 한 판단이다.
        if out and _block_claims(out[-1]) == _block_claims(blk):
            out[-1] = {**out[-1], "text": out[-1]["text"] + blk["text"]}
            continue
        out.append(blk)
    split = [sub for b in out for sub in split_by_subject(_cut_at_subheading(b))]
    # G1 로 갈린 조각이 바로 뒤 블록과 청구항이 같으면 다시 하나로 둔다(F4 와 같은 이유).
    merged: list[dict] = []
    for b in split:
        if merged and _block_claims(merged[-1]) == _block_claims(b):
            merged[-1] = {**merged[-1], "text": merged[-1]["text"] + b["text"]}
            continue
        merged.append(b)
    return merged


def _mark_level(mark: str) -> int:
    """통지서 표지의 계층 — 1. > 1-1 · 1.1 · 가. > (1) > ① > - · 기타. 표지 없음은 가장 깊다."""
    if not mark:
        return 9
    if re.fullmatch(r"\d+", mark):
        return 1
    if re.fullmatch(r"\d+[-.]\d+(?:[-.]\d+)?", mark) or re.fullmatch(r"[가-하]", mark):
        return 2
    if mark.startswith("("):
        return 3
    if re.fullmatch(r"[①-⑳]", mark):
        return 4
    return 5


# G5 — 괄호 표지 줄이 좌표·`참조` 를 담으면 문헌 위치 표기(`(청구항 2~5, 도 1 참조)`)이지 머리줄이 아니다.
def _bracket_locator(seg: str, m: re.Match) -> bool:
    if (m.group("mark") or "").strip()[:1] not in "([【<":
        return False
    nl = seg.find("\n", m.start())
    line = seg[m.start(): nl if nl != -1 else len(seg)]
    return bool(LOC_RX.search(line) or "참조" in line)


# G3 — 블록은 다음 구분의 소제목(`나. 종속항` · `2. 독립 청구항`)에서 끝난다. 그 뒤는 다음 머리줄 전까지 어느
# 판단에도 속하지 않는다(2차 오답: 블록 끝에 `나. 종속항` 이 붙음).
_SUBHEAD_RX = re.compile(r"^[ \t]*" + MARK + r"[ \t]*(?:독립|종속)\s*(?:청구)?항(?:\s*(?:들|발명))?[ \t]*:?[ \t]*$", re.M)


def _cut_at_subheading(b: dict) -> dict:
    nl = b["text"].find("\n")
    if nl == -1:
        return b
    m = _SUBHEAD_RX.search(b["text"], nl)
    return {**b, "text": b["text"][:m.start()]} if m else b


# G1 — 머리줄 없이 이어지는 다른 청구항의 판단(`청구항 10 은 … 단순 선택`)에서 블록을 가른다. 주어는 문장 첫
# 청구항 나열이 곧장 `(발명)은/는` 으로 이어질 때만이다(`청구항 1 의 구성 A 는` 은 주어가 아니다). 결론 문장이
# 블록 청구항과 겹치면 그 청구항을 블록에 더한다(`따라서 제2항 및 제3항은`).
SUBJ_RX = re.compile(r"(?:^|(?<=다\.)|(?<=\n))[ \t]*(?:또한\s*,?\s*|그리고\s*,?\s*|한편\s*,?\s*)?"
                     r"((?:청구항|제)\s*(?:제\s*)?\d{1,3}(?:\s*(?:항)?\s*(?:,|및|내지|~|∼|-)\s*(?:청구항\s*)?(?:제\s*)?\d{1,3})*"
                     r"\s*(?:항)?)\s*(?:에\s*기재된\s*)?(?:발명)?\s*(?:은|는)\s")


# 블록이 그 청구항 **자신을** 다뤘다는 표지 — `청구항 2 와 3 의 (부가적인 · 기술적) 특징` · `한정사항` · `부가 사항`.
# `청구항 1 의 구성` 처럼 비교 대상으로만 언급된 것은 넣지 않는다(회귀 188행).
DISCUSS_RX = re.compile(r"(" + CL_LIST + r"(?:\s*(?:과|와)\s*(?:청구항\s*)?\d{1,3}\s*(?:항)?)?)\s*(?:발명)?\s*의\s*"
                        r"(?:(?:부가적인|추가적인|기술적인?)\s*)*(?:기술적\s*)?(?:특징|한정\s*사항|한정\s*구성|부가\s*(?:한정\s*)?사항)")


def split_by_subject(b: dict) -> list[dict]:
    claims = set(_block_claims(b))
    text = b["text"]
    nl = text.find("\n")
    body_at = nl if nl != -1 else len(text)
    # 결론 문장의 청구항은 **본문에서 다룬 것만** 더한다. `따라서 청구항 1 내지 13 은` 같은 절 전체의 종합 결론은 이 블록이
    # 그 청구항들을 판단했다는 증거가 아니다(회귀 160행). 더한 것은 따로 적어 H6 내부 관계 판정에서 뺀다(185·188·191행).
    concl_added: set[int] = set()
    summary_at = None
    for m in CONCL_RX.finditer(text):
        cc = set(judged_claims(m.group(1), first_only=False))
        if not cc & claims:
            continue
        discussed = {n for sm in SUBJ_RX.finditer(text, 0, m.start()) for n in judged_claims(sm.group(1), first_only=False)}
        discussed |= {n for dm_ in DISCUSS_RX.finditer(_as_claim(text[:m.start()])) for n in judged_claims(dm_.group(1), first_only=False)}
        add = (cc - claims) & discussed
        claims |= add
        concl_added |= add
        # 이 블록이 다루지 않은 청구항까지 묶는 **종합 결론**(`따라서 청구항 3 내지 8 은`)은 블록 본문이 아니다 — 그 문장부터
        # 본문에서 떼어 `summary` 로 **별도 표시**한다(회귀 v2 17행). 다만 그 결론이 이 블록 청구항을 **모두** 덮으면 거기 적힌
        # 문헌은 이 블록의 근거이기도 하다 — 참조만 있고 자기 문헌이 없는 블록(`청구항 9~12 는 청구항 1, 3~5 를 카테고리를
        # 달리하여` → `따라서 청구항 7 내지 12 는 인용발명 1 내지 4 의 조합`)이 근거를 잃지 않게(회귀 v3 120·194행).
        if cc - claims and summary_at is None:
            summary_at = m.start()
            summary_covers = claims <= cc
    summary = ""
    if summary_at is not None:
        summary = text[summary_at:] if summary_covers else ""
        text = text[:summary_at]
    cuts = []
    for m in SUBJ_RX.finditer(text, body_at):
        cl = set(judged_claims(m.group(1), first_only=False))
        if cl and not cl & claims:
            cuts.append((m.start(), sorted(cl)))
    out = [{**b, "text": text[:cuts[0][0]] if cuts else text, "summary": summary,
            "claims_extra": sorted(claims - set(own_claims(b["head"]))), "claims_concl": sorted(concl_added)}]
    for i, (at, cl) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        out.append({"mark": "", "head": text[at:at + HEAD_SPAN].split("\n", 1)[0], "text": text[at:end],
                    "claims_extra": cl, "split": True})
    return out


# F5 — 표지 없는 머리줄은 앞줄이 문장·항목을 끝냈을 때만 연다. 문장 중간 줄바꿈 뒤의 `청구항 3은 …` 은
# 블록이 아니다(사람 대조 1차 오답: 블록이 `있고,` 에서 잘림).
_SENT_END_RX = re.compile(r"(?:[다음함임]\s*\.?|[.:)\]】>]|발명|대하여,?|관하여,?|비고)\s*$")


_MARK_LINE_RX = re.compile(r"^[ \t]*" + MARK + r"[ \t]*\S")
_TABLE_HEAD_RX = re.compile(r"비고\s*$")


def _after_sentence_end(seg: str, at: int) -> bool:
    """앞줄이 문장·항목을 끝냈거나, 앞줄 자체가 표지 줄(`1.2 종속항 제2-7항`)이거나, 이 줄이 표 머리(`… 비고`)."""
    prev = [ln for ln in seg[:at].splitlines() if ln.strip()]
    nl = seg.find("\n", at)
    line = seg[at: nl if nl != -1 else len(seg)]
    return (not prev or bool(_SENT_END_RX.search(prev[-1])) or bool(_MARK_LINE_RX.match(prev[-1]))
            or bool(_TABLE_HEAD_RX.search(line)))


def _block_claims(b: dict) -> list[int]:
    return sorted(set(own_claims(b["head"])) | set(b.get("claims_extra", [])))


def definition_lines(body: str) -> dict[tuple[str, int], str]:
    """(라벨, 번호) → 그 라벨을 정의한 줄(문헌번호가 적힌 줄). 사람 대조 시트의 증거로만 쓴다(그래프에 싣지 않는다)."""
    out: dict[tuple[str, int], str] = {}
    for line in body.splitlines():
        for lm in N.LABEL_RX.finditer(line):
            k = N.LABEL_REF_RX.match(lm.group(0))
            if k and N.normalize_cited(line[lm.end():lm.end() + 200]):
                out.setdefault((k.group(1), int(k.group(2))), line.strip()[:200])
    return out


def declaration_lines(seg: str, app: str, sdocs: set) -> dict[str, str]:
    """절의 문헌 → 그 문헌번호가 적힌 절 안의 첫 줄(사람 대조 증거 · 그래프에 싣지 않는다)."""
    out: dict[str, str] = {}
    for line in seg.splitlines():
        for nid in N.cited_in_section(line, app):
            if nid in sdocs:
                out.setdefault(nid, line.strip()[:200])
    return out


def notice_sections(text: str, app: str) -> tuple[list[dict], dict, dict]:
    """parse_notice 와 같은 절 경계로 (절 번호, 근거, 본문)을 낸다. 라벨 정의는 문서 전체."""
    dm = N.DETAIL_RX.search(text)
    body = text[dm.end():] if dm else text
    defs = N.label_definitions(body, app)
    lines = definition_lines(body)
    am = N.ATTACH_RX.search(body)
    body = body[:am.start()] if am else body
    parts = list(N.SECTION_RX.finditer(body))
    out = []
    for i, m in enumerate(parts):
        end = parts[i + 1].start() if i + 1 < len(parts) else len(body)
        seg = body[m.start():end]
        if N.BOILER_RX.search(seg[:60]):
            continue
        bases = [N.LB[b] for b in dict.fromkeys(x.group(1) for x in N.BASIS_29_RX.finditer(seg))]
        if not bases and N.BASIS_42_RX.search(seg):
            bases = ["§42"]
        out.append({"no": int(m.group(1)) if m.group(1) else i + 1, "bases": bases, "seg": seg,
                    "offset": (len(text) - len(text[dm.end():]) if dm else 0) + m.start()})
    return out, defs, lines


# 줄바꿈이 낱말을 끊는다(`인용 발명 1`) — 라벨 용어 안의 공백을 허용한다. 번호 없는 라벨은 문헌이 하나뿐인
# 절에서만 그 문헌으로 읽는다.
LABEL_FLEX_RX = re.compile(r"(인\s*용\s*발\s*명|비\s*교\s*대\s*상\s*발\s*명|선\s*행\s*발\s*명|인\s*용\s*문\s*헌)"
                           r"(?:\s*(\d{1,2})(?!\d)((?:\s*(?:,|및|와|과|또는|내지|~|∼|ㆍ|·)\s*\d{1,2}(?!\d))*))?")
# F1 — 나열(`인용발명 1, 2` · `1 내지 3` · `1~4`)의 뒤 번호. 1차 사람 대조 블록 오답 16 중 10 이 이것이었다.
_LIST_TAIL_RX = re.compile(r"\s*(,|및|와|과|또는|내지|~|∼|ㆍ|·)\s*(\d{1,2})")
MAX_LABEL_RANGE = 10


def label_numbers(first: str, tail: str) -> list[int]:
    nums, prev = [int(first)], int(first)
    for m in _LIST_TAIL_RX.finditer(tail or ""):
        n = int(m.group(2))
        if m.group(1) in ("내지", "~", "∼") and prev < n <= prev + MAX_LABEL_RANGE:
            nums.extend(range(prev + 1, n + 1))
        else:
            nums.append(n)
        prev = n
    return list(dict.fromkeys(nums))


def section_docs(seg: str, app: str, defs: dict) -> set[str]:
    """정본 파서(parse_notice)가 그 절에 붙이는 문헌과 같은 집합."""
    out = set(N.cited_in_section(seg, app))
    for r in N.LABEL_REF_RX.finditer(seg):
        nid = defs.get((r.group(1), int(r.group(2))))
        if nid:
            out.add(nid)
    return out


def docs_in(text: str, app: str, defs: dict, sec_docs: set[str], stat: Counter | None = None,
            missing: list | None = None, how: dict | None = None) -> dict[str, list[int]]:
    """정규화 문헌 → 그 문헌을 가리키는 라벨 위치(좌표 귀속용). 직접 표기는 위치 없이 싣는다.
    `how` 에는 문헌마다 어떻게 해소했는지(직접 표기 · 라벨 정의 · 절의 유일 문헌)를 남긴다 — 사람 대조의 증거."""
    out: dict[str, list[int]] = {}
    for nid in N.cited_in_section(text, app):
        out.setdefault(nid, [])
        if how is not None:
            how.setdefault(nid, set()).add("direct")
    only = next(iter(sec_docs)) if len(sec_docs) == 1 else None
    for r in LABEL_FLEX_RX.finditer(text):
        term = re.sub(r"\s", "", r.group(1))
        if not r.group(2) and text[r.end():r.end() + 1] == "들":
            continue                                   # `인용발명들` — 특정 문헌이 아니다
        nums = label_numbers(r.group(2), r.group(3)) if r.group(2) else [None]
        for k, n in enumerate(nums):
            nid = defs.get((term, n)) if n is not None else None
            # H4 — 번호 라벨은 정의로 잇는다. 정의가 없을 때 대응이 **확정되는** 경우만 절의 유일 문헌으로 읽는다:
            # 번호 없는 라벨, 또는 `인용발명 1` (절에 문헌이 하나뿐이면 1 번은 그것이다). `인용발명 2` 는 문헌 하나뿐인
            # 절에서 그 문헌일 수 없다 — 3차 오답이 이것이었다. 그 밖은 미해결로 남긴다.
            via = ("definition", term, n)
            if nid is None and only and (n is None or (n == 1 and len(nums) == 1)):
                nid = only
                via = ("single_section_document", term, n)
                if stat is not None:
                    stat["label_resolved_by_single_section_document"] += 1
            if nid and how is not None:
                how.setdefault(nid, set()).add(via)
            if nid:
                # 좌표 귀속 위치는 단독 라벨만 남긴다 — 나열 뒤의 좌표는 어느 문헌 것인지 말하지 않는다.
                out.setdefault(nid, [])
                if len(nums) == 1:
                    out[nid].append(r.end())
                elif stat is not None and k:
                    stat["label_list_member_resolved"] += 1
            else:
                if stat is not None:
                    stat["label_unresolved__" + ("numbered" if n is not None else "bare")] += 1
                if missing is not None:
                    missing.append((term, n))          # 번호 없는 라벨도 문헌이 여럿인 절에서는 미해결이다
    return out


class DocResolver:
    """정규화 문헌 표기 → 판단층과 같은 특허 IRI (claim-features 와 같은 맵 · 같은 표기 차이 규칙)."""

    def __init__(self) -> None:
        ed = pd.read_parquet(EDGES, columns=["cited_id", "cited_doc_id"])
        canon = ed[ed["cited_id"].astype(str).str.startswith("patent:")]
        self.exact = dict(zip(canon["cited_doc_id"], canon["cited_id"]))
        if B_LAYER_POP.exists():
            b = pd.read_parquet(B_LAYER_POP)
            b = b[~b["is_npl"]]
            for doc, cid in zip(b["cited_doc_id"], b["cited_id"]):
                self.exact.setdefault(doc, cid)
        self.loose, self.ambiguous = _loose_map(self.exact)

    def __call__(self, nid: str, stat: Counter) -> URIRef | None:
        cid = self.exact.get(nid)
        if cid:
            stat["doc_resolved_exact"] += 1
        else:
            k = _doc_key(nid)
            cid = self.loose.get(k) if k else None
            if cid:
                stat["doc_resolved_loose"] += 1
            else:
                stat["doc_unresolved__" + ("ambiguous" if k in self.ambiguous else "absent")] += 1
                return None
        return URIRef(D + cid.replace("patent:", "patent/"))


def present_claims() -> set[str]:
    cf = pd.read_parquet(CLAIMS, columns=["side", "claim_id"])
    return set(cf.loc[cf["side"] == "rej", "claim_id"])


# ── 판단 추출 ─────────────────────────────────────────────────────────

def _locators(text: str, labels: dict[str, list[int]], single: str | None, stat: Counter) -> dict[str, set]:
    """좌표 → 귀속 문헌. 앞 80자 안의 가장 가까운 라벨, 없으면 단일문헌 블록의 그 문헌."""
    pos = sorted((p, nid) for nid, ps in labels.items() for p in ps)
    out: dict[str, set] = {}
    for m in LOC_RX.finditer(text):
        lo = max(0, m.start() - APPLICANT_NEAR)
        app_at = [lo + a.end() for a in APPLICANT_RX.finditer(text, lo, m.start())]
        near = [(p, nid) for p, nid in pos if m.start() - LABEL_NEAR <= p <= m.start()]
        # 본원 표지가 가장 가까운 라벨보다 뒤(좌표 쪽)에 있으면 본원 명세서의 좌표다.
        if app_at and (not near or app_at[-1] > near[-1][0]):
            stat["locator_applicant_side"] += 1
            continue
        if near:
            nid = near[-1][1]
        elif single:
            nid = single
        else:
            stat["locator_unattributed"] += 1
            continue
        if m.group("fig"):
            t, v = "Figure", "도" + m.group("fn") + (f"~{m.group('fn2')}" if m.group("fn2") else "")
        else:
            lo = m.group("p1") or m.group("p2")
            t, v = "Paragraph", f"[{lo}]" + (f"~[{m.group('p3').zfill(len(lo))}]" if m.group("p3") else "")
        out.setdefault(nid, set()).add((t, v))
        stat["locator_attributed"] += 1
    return out


def extract_notice(stem: str, text: str) -> tuple[list[dict], Counter]:
    """통지서 하나 → 판단 레코드(IRI 이전 단계). 결정적."""
    app = stem.split("_")[0]
    stat = Counter()
    sections, defs, lines = notice_sections(text, app)
    recs = []
    for s in sections:
        grounds = [b for b in s["bases"] if b in GROUND]
        if not grounds:
            stat["section_skipped__" + ("|".join(s["bases"]) or "none")] += 1
            continue
        stat["section_29"] += 1
        blocks = split_blocks(s["seg"])
        # 절마다 번호를 새로 매기는 통지서가 있어(거절이유 1 의 인용발명 1 ≠ 거절이유 2 의 인용발명 1) 문서 전체
        # 정의는 그 라벨을 모호로 버린다 — 절 안의 정의를 먼저 쓴다.
        sdefs = {**defs, **N.label_definitions(s["seg"], app)}
        def_lines = {**lines, **definition_lines(s["seg"])}
        sdocs = section_docs(s["seg"], app, sdefs)
        decl_lines = declaration_lines(s["seg"], app, sdocs)
        units = ([(i, b["mark"], b["head"], b["text"], b.get("claims_extra", [])) for i, b in enumerate(blocks, 1)]
                 if blocks else [(0, "", "", s["seg"], [])])
        concl_of = {i: set(b.get("claims_concl", [])) for i, b in enumerate(blocks, 1)}
        summary_of = {i: b.get("summary", "") for i, b in enumerate(blocks, 1)}
        if blocks:
            pre = s["seg"][:s["seg"].find(blocks[0]["text"])]
            pc = sorted({n for m in CONCL_RX.finditer(_flat(pre)) for n in claim_refs(m.group(1))})
            if pc:
                units.insert(0, (0, "", "", pre, pc))
                stat["preamble_units"] += 1
        for bi, mark, head, text_, extra in units:
            if bi:
                claims = sorted(set(own_claims(head)) | set(extra))  # = _block_claims
            else:
                claims = extra or N.parse_claim_refs(s["seg"])
            flat = _flat(text_)
            missing: list = []
            how: dict = {}
            summ = summary_of.get(bi, "")
            # 문헌은 본문 + (블록 청구항을 모두 덮는) 종합 결론에서 — 좌표 귀속 위치는 본문 범위에서만 쓰인다.
            labels = docs_in(text_ + ("\n" + summ if summ else ""), app, sdefs, sdocs, stat, missing, how)
            recs.append({
                "key": f"{stem}_s{s['no']}_b{bi}", "stem": stem, "app": app, "section": s["no"],
                "core_claims": sorted(set(claims) - concl_of.get(bi, set())),
                "offset": s["offset"] + max(0, s["seg"].find(text_)),
                "block": bi, "mark": mark, "grounds": grounds, "claims": claims,
                "scope": "added" if bi and ADDED_RX.search(head[:HEAD_SPAN]) else "whole",
                "labels": labels,
                "missing_labels": len(missing),
                "summary": summ,
                "evidence": _label_evidence(labels, how, def_lines, sdocs, decl_lines),
                "ck": bool(CK_RX.search(flat)),
                "rat": sorted(k for k, rx in RATIONALE_RX.items() if rx.search(flat)),
                "text": text_,
            })
    return recs, stat


def _label_evidence(labels: dict, how: dict, def_lines: dict, sdocs: set, decl: dict | None = None) -> str:
    """문헌마다 해소 근거 한 줄 — `KR-P-… ← 인용발명 1 정의: <정의 줄>` · `← 본문 직접 표기` · `← 절의 유일 문헌(절 문헌 1)`."""
    decl = decl or {}
    parts = []
    for nid in sorted(labels):
        ways = []
        for v in sorted(how.get(nid, ()), key=str):
            if v == "direct":
                ways.append("본문 직접 표기")
            elif v[0] == "definition":
                ways.append(f"{v[1]} {v[2]} 정의: {def_lines.get((v[1], v[2]), '(정의 줄 미발견)')}")
            else:
                ways.append(f"{v[1]}{'' if v[2] is None else ' ' + str(v[2])} → 절의 유일 문헌 (절 문헌 {len(sdocs)}) · "
                            f"절의 선언: {decl.get(nid, '(선언 줄 미발견)')}")
        parts.append(f"{nid} ← " + " ; ".join(ways))
    return " || ".join(parts)


# H5 — 참조 대상은 참조 표현에 **문법적으로 붙은** 청구항 나열이다: `청구항 Y 를 (각각) (단순히) 카테고리를 달리` ·
# `청구항 Y 의(에 대한) 거절이유와 동일` · `청구항 Y 와 동일한 취지`. 가깝다는 것만으로는 대상이 아니다 — 가까운 청구항도
# 종속관계 설명(`청구항 1~13 의 조성물을 포함하는`)일 수 있다. 붙은 나열이 없으면 잇지 않고 센다.
# 나열과 조사 사이에 인용 구절(`청구항 9 발명의 ‘…의 제조 방법’의 발명과`)이 낄 수 있다 — 회귀 186·192행.
_CL_TAIL = (r")\s*(?:발명)?\s*(?:의\s*[‘'\"「『][^’'\"」』]{0,60}[’'\"」』]\s*(?:의\s*)?(?:발명)?\s*)?"
            # 나열 뒤 구성 수식(`청구항 3,4 의 한정사항과` · `제4항 내지 제10항에서 한정 한 구성과`) — 회귀 61·67행.
            r"(?:(?:의|에서)\s*(?:한정\s*한\s*|한정된\s*|부가된\s*)?(?:한정\s*사항|구성|특징|기술적\s*특징)\s*)?")
# 조사와 `거절이유` 사이에 법조문(`특허법 제29조제2항의`)이 낄 수 있다 — 회귀 190행.
_LAW = r"(?:(?:특허법\s*)?제\s*\d+\s*조\s*(?:제\s*\d+\s*항)?\s*(?:제\s*\d+\s*호)?\s*(?:의|에\s*따른)?\s*)?"
# `와/과` 뒤에는 짧은 서술(`기술적 사상이 동일하고`)이 끼어도 같은 비교 대상이다 — 단 다른 청구항이 끼면 아니다.
_WITH = r"(?:와|과)(?:(?!청구항)[^.,]){0,40}$"              # 절 경계(쉼표)를 넘으면 붙은 것이 아니다
TARGET_RX = {
    "variant": re.compile(r"(" + CL_LIST + _CL_TAIL + r"(?:(?:을|를)\s*(?:각각\s*)?(?:단순(?:히|하게)\s*)?(?:그\s*)?$|" + _WITH + r")"),
    "claim": re.compile(r"(" + CL_LIST + _CL_TAIL + r"(?:의\s*(?:한정\s*)?구성\s*[\dA-Za-zㅇ○●◯Ｏ,\s및]{0,20}?\s*)?"
                        r"(?:(?:의|에\s*대한|에\s*관한)\s*(?:(?:상기|앞의|위의|앞서\s*본)\s*)?" + _LAW + r"$|" + _WITH + r")"),
}
_REF_HEAD_RX = re.compile(r"(?:거절\s*이유|동일한\s*취지|동일한\s*(?:거절\s*)?이유)")


def sentence_subject(text: str, at: int) -> list[int]:
    """`at` 이 속한 문장의 주어 청구항 = 문장 첫 청구항 나열(부모항 제외). 머리줄은 문장이 아니다 — `1-5. 청구항 11, 12
    발명` 다음 줄의 `청구항 11 발명(청구항 10 인용)은 …` 이 주어다(회귀 64행)."""
    nl = text.find("\n")
    first = text[:nl] if nl != -1 else ""
    # 첫 줄이 **제목 꼴**일 때만 건너뛴다. 첫 줄이 문장의 시작(`청구항 16 발명은 … 발명으로,` → 다음 줄로 이어짐)이면 그것이 주어다.
    # 제목 꼴 = 서술(주격 조사 `은/는` · `으로,` · 문장 끝)이 없는 줄.
    title = bool(first) and not re.search(r"(?:은|는)(?:\s|,|$)|으로\s*,|[다음함]\s*\.", first)
    starts = [0] + ([nl + 1] if title and 0 <= nl < at else []) + [m.end() for m in SENT_BOUND_RX.finditer(text, 0, at)]
    return judged_claims(text[max(starts):at])


def attached_targets(text: str, m: re.Match, kind: str) -> list[int] | None:
    """참조 표현 `m` 바로 앞에 붙은 청구항 나열. 없으면 None."""
    start = m.start()
    if kind == "claim":                       # `거절이유` 앞의 `의/와` 까지 포함해 붙은 나열을 찾는다
        hm = _REF_HEAD_RX.search(text, max(0, start - 15), m.end())
        start = hm.start() if hm else start
    starts = [b.end() for b in SENT_BOUND_RX.finditer(text, 0, start)]
    window = _as_claim(text[(starts[-1] if starts else 0):start])
    tm = TARGET_RX[kind].search(window)
    if not tm:
        return None
    # 부모항 제외는 **붙은 구간 안에서만** — 같은 문장 앞의 종속관계 설명(`청구항 1,2,3 중 어느 한 항 인용`)에 대상 번호가 또
    # 나오면 대상까지 지워진다(회귀 v2 63행).
    return [n for n in N.parse_claim_refs(tm.group(1)) if n not in dependency_parents(tm.group(0))] or None


def resolve_references(recs: list[dict], stat: Counter) -> None:
    """같은 통지서 안에서 참조 대상을 유일하게 해소한다. 실패는 사유별로 센다."""
    by_mark = {}
    by_section: dict[int, list[dict]] = {}
    for r in recs:
        by_section.setdefault(r["section"], []).append(r)
        if r["mark"]:
            by_mark.setdefault(r["mark"], []).append(r)

    def claim_target(r: dict, y: int) -> dict | None:
        """F3 — Y 를 담은 판단 중 같은 절 우선, 그중 **가장 좁은** 것. 동률이면 모호."""
        cands = [t for t in recs if t is not r and y in t["claims"]]
        same = [t for t in cands if t["section"] == r["section"]]
        pick = same if same else cands
        if pick:
            w = min(len(t["claims"]) for t in pick)
            pick = [t for t in pick if len(t["claims"]) == w]
        if len(pick) == 1:
            return pick[0]
        stat["ref_claim_unresolved__" + ("absent" if not pick else "ambiguous")] += 1
        return None

    for r in recs:
        r["refers"], r["variant_of"], r["groups"] = set(), set(), []
        text = r["text"]
        for m in REF_LABEL_RX.finditer(text):
            sec = int(m.group(1) or m.group(3))
            sub = m.group(2) if m.group(1) else m.group(4)
            if sub:
                cands = by_mark.get(f"{sec}-{sub}", [])
                if not cands:
                    cands = [t for t in by_section.get(sec, []) if t["mark"] == sub]
            else:
                cands = by_section.get(sec, [])
            cands = [t for t in cands if t is not r]
            if len(cands) == 1:
                r["refers"].add(cands[0]["key"])
                r["groups"].append(("label", [cands[0]["key"]]))
                stat["ref_label_resolved"] += 1
            else:
                stat["ref_label_unresolved__" + ("absent" if not cands else "ambiguous")] += 1
        flat = text
        for rx, kind in ((CAT_RX, "variant"), (REF_CLAIM_RX, "claim")):
            for m in rx.finditer(flat):
                subj = sentence_subject(flat, m.start())
                # F2 — 관계의 주어는 문장 주어(`청구항 X 는`)다. X 가 이 블록의 청구항이 아니면 이 판단의 관계가
                # 아니다(1차 오답: 청구항 9 블록 안의 "청구항 10 은 청구항 1 을 카테고리를 달리" 를 9→1 로 이음).
                if not subj or not set(subj) <= set(r["claims"]):
                    stat[f"ref_{kind}_subject_outside_block"] += 1
                    continue
                targets = attached_targets(flat, m, kind)
                if not targets:
                    stat[f"ref_{kind}_no_attached_target"] += 1
                    continue
                # H6 — 대상이 이 블록 안의 청구항이면 블록 **내부** 관계다. 다른 판단으로 잇지 않는다(그것이 다른 절로의
                # 오연결이었다). 내부 관계는 리포트에 센다 — 판단↔판단 술어로는 담을 자리가 없다.
                core = set(r.get("core_claims", r["claims"]))
                inner = [y for y in targets if y in core]
                ys = [y for y in targets if y not in core and y not in subj]
                if inner:
                    stat[f"ref_{kind}_intra_block_targets"] += len(inner)
                # G6 — 블록 밖 대상을 **모두** 해소할 때만 잇는다.
                if not ys:
                    stat[f"ref_{kind}_no_external_target"] += 1
                    continue
                found = [claim_target(r, y) for y in ys]
                if any(f is None for f in found):
                    stat[f"ref_{kind}_partial_dropped"] += 1
                    continue
                keys = sorted({f["key"] for f in found})
                r["groups"].append((kind, keys))
                r["refers"].update(keys)
                if kind == "variant":
                    r["variant_of"].update(keys)
                stat[f"ref_{kind}_resolved"] += 1


def _jiri(key: str) -> URIRef:
    return D[f"argument/judgment/{key}"]


def build(recs: list[dict], resolver: DocResolver, claims_ok: set[str], stat: Counter) -> Graph:
    """레코드 → 그래프. 문헌·청구항이 그래프에 없으면 버리고 센다."""
    keep: dict[str, dict] = {}
    for r in recs:
        docs: dict[URIRef, str] = {}
        for nid in sorted(r["labels"]):
            iri = resolver(nid, stat)
            if iri is not None:
                docs.setdefault(iri, nid)
        claims = [n for n in r["claims"] if f"rej_{r['app']}_c{n}" in claims_ok]
        stat["claim_link_dropped_not_in_graph"] += len(r["claims"]) - len(claims)
        if not r["claims"]:
            stat["judgment_dropped__no_claim"] += 1
            continue
        if not claims:
            stat["judgment_dropped__claims_not_in_graph"] += 1
            continue
        if not docs and not r["ck"]:
            stat["judgment_dropped__no_document_no_common_knowledge"] += 1
            continue
        # G2 — 본문이 가리킨 번호 라벨 중 정의를 못 찾은 것이 있으면 묶음이 결합의 일부만 담는다. 묶음 안 = 결합이므로
        # 그것은 틀린 주장이다 — 적재하지 않고 센다(2차 오답 4 · 정본 파서가 정의 줄을 정규화하지 못한 통지서).
        if r.get("missing_labels"):
            stat["judgment_dropped__label_definition_missing"] += 1
            continue
        keep[r["key"]] = {**r, "docs": docs, "claims_ok": claims}

    g = Graph()
    for key in sorted(keep):
        r = keep[key]
        j = _jiri(key)
        exdoc = D[f"examdoc/{r['stem']}"]
        g.add((exdoc, RDF.type, PA.ExaminationDocument))
        g.add((j, RDF.type, PA.ExaminerJudgment))
        g.add((j, PA.assertedIn, exdoc))
        for gr in r["grounds"]:
            g.add((j, PA.onGround, GROUND[gr]))
        g.add((j, DCTERMS.source, Literal(SOURCE, datatype=XSD.string)))
        g.add((j, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
        for n in r["claims_ok"]:
            g.add((j, PA.judgesClaim, D[f"claim/rej_{r['app']}_c{n}"]))
        g.add((j, PA.judgmentScope, PA.ScopeAddedLimitation if r["scope"] == "added" else PA.ScopeWholeClaim))
        sn = URIRef(f"{j}_s1")
        g.add((sn, RDF.type, PA.EvidenceSet))
        g.add((j, PA.supportedBy, sn))
        for iri in r["docs"]:
            g.add((sn, PA.includesDocument, iri))
        if r["ck"]:
            g.add((sn, PA.reliesOnCommonKnowledge, Literal(True)))
        for rat in r["rat"]:
            g.add((sn, PA.hasRationale, PA["Rationale" + rat]))
        single = next(iter(r["labels"])) if len(r["labels"]) == 1 else None
        locs = _locators(r["text"], r["labels"], single, stat)
        by_iri = {iri: nid for iri, nid in r["docs"].items()}
        for li, iri in enumerate(sorted(i for i in by_iri if by_iri[i] in locs), 1):
            ln = URIRef(f"{j}_l{li}")
            g.add((ln, RDF.type, PA.EvidenceLink))
            g.add((ln, PA.partOfJudgment, j))
            g.add((ln, PA.inDocument, iri))
            for ti, (t, v) in enumerate(sorted(locs[by_iri[iri]]), 1):
                loc = URIRef(f"{ln}_loc{ti}")
                g.add((loc, RDF.type, PA.DocumentLocator))
                g.add((ln, PA.locator, loc))
                g.add((loc, PA.locatorType, PA["Loc" + t]))
                g.add((loc, PA.locatorValue, Literal(v, datatype=XSD.string)))
        # G6 — 관계 하나(문장 하나)의 대상이 하나라도 적재되지 않았으면 그 관계 전체를 싣지 않는다.
        for kind, keys in r["groups"]:
            if any(k not in keep for k in keys):
                stat["ref_dropped__target_not_emitted"] += 1
                continue
            for k in keys:
                g.add((j, PA.refersToJudgment, _jiri(k)))
                if kind == "variant":
                    g.add((j, PA.categoryVariantOf, _jiri(k)))
    return g


def check(g: Graph) -> None:
    """어기면 죽는다 — shape 와 별개로 생성기 자신의 계약."""
    arg = Graph().parse(ARG_TTL)
    allowed = {o for o in arg.subjects(RDF.type, PA.Rationale)} | {o for o in arg.subjects(RDF.type, PA.LocatorType)}
    judgments = set(g.subjects(RDF.type, PA.ExaminerJudgment))
    for j in judgments:
        for p in (PA.assertedIn, PA.onGround, PA.judgesClaim, PA.supportedBy):
            if (j, p, None) not in g:
                raise SystemExit(f"{j}: {p} 가 없다")
    for s, p, o in g.triples((None, PA.refersToJudgment, None)):
        if s == o:
            raise SystemExit(f"{s}: 자기 참조")
        if o not in judgments:
            raise SystemExit(f"{s}: 참조 대상 {o} 가 그래프에 없다")
    for s, p, o in g.triples((None, PA.categoryVariantOf, None)):
        if (s, PA.refersToJudgment, o) not in g:
            raise SystemExit(f"{s}: categoryVariantOf 에 상위 술어 refersToJudgment 가 없다")
    for p in (PA.hasRationale, PA.locatorType):
        for o in g.objects(None, p):
            if o not in allowed:
                raise SystemExit(f"{o} 가 T-Box 개체가 아니다")
    for o in g.objects(None, PA.locatorValue):
        if not LOC_VALUE_RX.match(str(o)):
            raise SystemExit(f"좌표 값 {o!r} 가 형식 밖이다 — 원문이 새는지 확인할 것")
    for p in (PA.claimTerm, PA.documentTerm):
        if (None, p, None) in g:
            raise SystemExit(f"{p} 는 적재하지 않는다(§20.22 A3)")


HEADER = """# ═══════════════════════════════════════════════════════════════════
# SDKB Prior-Art Argument — 논증층 A-Box (의견제출통지서 전량 · 청구항 블록 단위)
#
# **생성물이다. 손으로 고치지 않는다** — scripts/build_abox_argument.py 가 만든다.
# 원천(data/sources/opinion_notices/)은 공개되지 않으며, 이 파일도 공개 트리에 싣지 않는다.
# 재생성: make abox-argument
# ═══════════════════════════════════════════════════════════════════"""


def extract_all() -> tuple[list[list[dict]], Counter]:
    stat = Counter()
    per_notice = []
    for f in sorted(TXT_DIR.glob("*.txt")):
        recs, st = extract_notice(f.stem, f.read_text(encoding="utf-8", errors="ignore"))
        resolve_references(recs, st)
        stat.update(st)
        stat["notices"] += 1
        per_notice.append(recs)
    return per_notice, stat


def render() -> tuple[str, Graph, Counter, list[dict]]:
    per_notice, stat = extract_all()
    flat = [r for recs in per_notice for r in recs]
    stat["blocks"] = sum(1 for r in flat if r["block"])
    stat["whole_section_units"] = sum(1 for r in flat if not r["block"])
    g = build(flat, DocResolver(), present_claims(), stat)
    check(g)
    return _emit(g, PREFIXES, HEADER), g, stat, flat


def _split_map() -> dict[str, str]:
    return {r["doc_id"].removeprefix("kr_"): r["split"] for r in csv.DictReader(SPLIT.open())}


def counts(g: Graph) -> dict:
    out = {cls: len(set(g.subjects(RDF.type, PA[cls]))) for cls in
           ("ExaminerJudgment", "EvidenceSet", "EvidenceLink", "DocumentLocator", "ExaminationDocument")}
    out["refersToJudgment"] = len(set(g.triples((None, PA.refersToJudgment, None))))
    out["categoryVariantOf"] = len(set(g.triples((None, PA.categoryVariantOf, None))))
    out["commonKnowledgeSets"] = len(set(g.subjects(PA.reliesOnCommonKnowledge, Literal(True))))
    for rat in RATIONALE_RX:
        out["rationale_" + rat] = len(set(g.subjects(PA.hasRationale, PA["Rationale" + rat])))
    for t in ("Paragraph", "Figure"):
        out["locator_" + t] = len(set(g.subjects(PA.locatorType, PA["Loc" + t])))
    return out


def by_split(g: Graph) -> dict:
    sp = _split_map()
    c = Counter()
    for j in g.subjects(RDF.type, PA.ExaminerJudgment):
        app = str(j).rsplit("/", 1)[1].split("_")[0]
        c[sp.get(app, "none")] += 1
    return dict(sorted(c.items()))


# ── 파일럿 대조 (A4 ①②) ────────────────────────────────────────────

def _tail(doc: str) -> tuple[str, str] | None:
    """파일럿 카드 표기(`KR10-2011-0015231` · `JP특개평10-195609` · `공개특허 제2007-14837호`)와 정규 표기를
    함께 받는 대조 전용 키. 정규화되면 정규 표기로, 아니면 국가 접두가 있을 때만 끝 6자리로. 라벨뿐이거나
    번호가 없는 카드 표기(`비교대상발명1` · `(첨부로만 제시 …)`)는 식별할 수 없어 None."""
    nid = N.normalize_cited(doc) or doc
    cc = re.match(r"[A-Z]{2}", nid.upper())
    digits = re.sub(r"\D", "", nid)
    if not cc or len(digits) < 6:
        return None
    return cc.group(0), digits[-6:]


def eval_pilot(flat: list[dict]) -> dict:
    """파일럿 판단의 청구항이 같은 통지서·근거의 블록 청구항에 덮이는가, 문헌이 맞는가."""
    cards = {c["card_id"]: c for c in map(json.loads, (PILOT_DIR / "cards_v1.jsonl").open(encoding="utf-8"))}
    recs = [json.loads(l) for l in (PILOT_DIR / "pilot_v1.jsonl").open(encoding="utf-8")]
    idx: dict[tuple[str, str], list[dict]] = {}
    for r in flat:
        for gr in r["grounds"]:
            idx.setdefault((r["stem"], gr), []).append(r)
    tot = hit = full = doc_ok = doc_n = doc_single = unident = 0
    for p in recs:
        c = cards[p["card_id"]]
        ours = idx.get((c["source_file"].removesuffix(".txt"), c["legal_ground"].replace("제1호", "")), [])
        cl = set(p["claims"] or map(int, c["target_claims"]))
        mine = set().union(*(set(r["claims"]) for r in ours)) if ours else set()
        tot += len(cl)
        hit += len(cl & mine)
        full += cl <= mine
        keys = [_tail(c["cited_docs"][i]) for s in p["sets"] for i in s["d"]]
        unident += sum(k is None for k in keys)
        pd_ = {k for k in keys if k is not None}
        if not pd_:
            continue
        doc_n += 1
        # A1: 파일럿 판단은 블록 여럿을 묶은 것이라, 그 청구항을 다룬 블록들의 문헌 합집합과 대조한다.
        # 블록 하나와의 대조(single)는 서술로 함께 싣는다.
        cand = [r for r in ours if set(r["claims"]) & cl]
        mine_docs = set().union(*({_tail(n) for n in r["labels"]} for r in cand)) if cand else set()
        doc_ok += pd_ <= mine_docs
        doc_single += any(pd_ <= {_tail(n) for n in r["labels"]} for r in cand)
    cov = round(hit / tot, 4) if tot else None
    dm = round(doc_ok / doc_n, 4) if doc_n else None
    return {"pilot_sha256": _sha(PILOT_DIR / "pilot_v1.jsonl"), "judgments": len(recs),
            "claims": tot, "claims_covered": hit, "claim_coverage": cov, "judgments_fully_covered": full,
            "judgments_with_documents": doc_n, "document_exact_or_superset": doc_ok, "document_match": dm,
            "document_match_single_block": round(doc_single / doc_n, 4) if doc_n else None,
            "pilot_documents_unidentifiable": unident,
            "thresholds": {"claim_coverage": PILOT_CLAIM_COVERAGE_MIN, "document_match": PILOT_DOC_MATCH_MIN},
            "pass": bool(cov is not None and dm is not None and cov >= PILOT_CLAIM_COVERAGE_MIN
                         and dm >= PILOT_DOC_MATCH_MIN)}


# ── 사람 대조 (A4 ③④) ──────────────────────────────────────────────

def _graph_relations(g: Graph) -> dict[str, dict[str, set]]:
    """판단 지역명 → 그래프에 **실린** 참조·범주 변형 대상(지역명). 시트는 생성기 레코드가 아니라 이것을 보여 준다."""
    out: dict[str, dict[str, set]] = {}
    for p, name in ((PA.refersToJudgment, "refers"), (PA.categoryVariantOf, "variant")):
        for s, o in g.subject_objects(p):
            out.setdefault(str(s).rsplit("/", 1)[1], {"refers": set(), "variant": set()})[name].add(str(o).rsplit("/", 1)[1])
    return out


def make_sample(g: Graph, flat: list[dict]) -> list[dict]:
    """train 판단에서 블록 30 + 신호별 10(이어받는 종류 제외). 시트는 data/interim/(DENY · gitignore)에만 쓴다."""
    sp = _split_map()
    emitted = {str(j).rsplit("/", 1)[1] for j in g.subjects(RDF.type, PA.ExaminerJudgment)}
    rel = _graph_relations(g)
    used = set()
    for prior in SAMPLE_PRIOR:
        if prior.exists():
            used |= {n.split("_")[0] for n in pd.read_csv(prior, dtype=str)["notice"]}   # 출원 단위로 뺀다
    fresh = [r for r in flat if r["key"] in emitted and r["app"] not in used]
    pool = sorted((r for r in fresh if sp.get(r["app"]) == "train"), key=lambda r: r["key"])
    dev_pool = sorted((r for r in fresh if sp.get(r["app"]) == "dev"), key=lambda r: r["key"])
    links = _graph_links(g)
    by_key = {r["key"]: r for r in flat}

    def describe(keys: set) -> str:
        """대상 판단을 시트에서 바로 대조할 수 있게 — 청구항과 첫 줄."""
        return " | ".join(f"{k.rsplit('_', 2)[-2]}_{k.rsplit('_', 1)[-1]}: 청구항 "
                          f"{','.join(map(str, by_key[k]['claims']))} — {_flat(by_key[k]['text'])[:120]}"
                          for k in sorted(keys))
    none = {"refers": set(), "variant": set()}
    rng = random.Random(SAMPLE_SEED)
    rows = [("block", r) for r in rng.sample(pool, SAMPLE_BLOCKS)]
    signals = {
        "DesignChoice": lambda r: "DesignChoice" in r["rat"],
        "PredictableEffect": lambda r: "PredictableEffect" in r["rat"],
        "categoryVariantOf": lambda r: bool(rel.get(r["key"], none)["variant"]),
        "refersToJudgment": lambda r: bool(rel.get(r["key"], none)["refers"] - rel.get(r["key"], none)["variant"]),
    }
    for name, pred in signals.items():
        cand = [r for r in pool if pred(r)]
        # 관계 두 종류는 출처별 할당을 고정한다(사용자 결정 (가) 10-05 · train 우선이 아니라 명시한 수) — dev 행은 판정에만
        # 쓰고 그 결과로 코드를 고치지 않는다. 고치면 그 출원의 행은 회귀용으로 돌리고 다음 판정은 미열람 출원에서 뽑는다.
        if name in DEV_FILL:
            n_tr, n_dev = DEV_FILL[name]
            dcand = [r for r in dev_pool if pred(r)]
            take = rng.sample(cand, min(n_tr, len(cand))) + rng.sample(dcand, min(n_dev, len(dcand)))
        else:
            take = rng.sample(cand, min(SAMPLE_PER_SIGNAL, len(cand)))
        rows += [(name, r) for r in take]
    # 좌표: 단락 5 · 도면 5 (사용자 결정 10-05 · "10건 표본 검증")
    for t_, n_ in (("Paragraph", 5), ("Figure", 5)):
        cand = [r for r in pool if any(lt == t_ for lk in links.get(r["key"], {}).values() for lt, _ in lk)]
        rows += [("locator", r) for r in rng.sample(cand, min(n_, len(cand)))]
    out = []
    for kind, r in rows:
        rr = rel.get(r["key"], none)
        out.append({"kind": kind, "split": sp.get(r["app"], ""), "judgment": r["key"], "notice": r["stem"],
                    "section": r["section"],
                    "block_mark": r["mark"], "grounds": "|".join(r["grounds"]),
                    "claims": " ".join(map(str, r["claims"])), "documents": " ".join(sorted(r["labels"])),
                    "common_knowledge": int(r["ck"]), "rationale": " ".join(r["rat"]),
                    "refers_to": " ".join(sorted(rr["refers"])), "variant_of": " ".join(sorted(rr["variant"])),
                    "targets": describe(rr["refers"]), "targets_detail": _targets_detail(r, rel, by_key),
                    "evidence": r["evidence"],
                    "locators": " || ".join(f"{d.rsplit('/', 1)[1]}: " + ", ".join(v for _, v in sorted(lk))
                                            for d, lk in sorted(links.get(r["key"], {}).items())),
                    "rationale_scope": "", "relation_exists": "", "correct": "", "note": "",
                    "block_text": _sheet_text(r)})
    return out


DEV_FILL = {"categoryVariantOf": (6, 4), "refersToJudgment": (3, 7)}   # (train, dev)


def _graph_links(g: Graph) -> dict[str, dict[str, set]]:
    """판단 지역명 → {문헌 IRI: {(좌표 종류, 값)}} — 그래프에 실린 근거 링크."""
    out: dict[str, dict[str, set]] = {}
    for ln in g.subjects(RDF.type, PA.EvidenceLink):
        j = str(g.value(ln, PA.partOfJudgment)).rsplit("/", 1)[1]
        doc = str(g.value(ln, PA.inDocument))
        for loc in g.objects(ln, PA.locator):
            t_ = str(g.value(loc, PA.locatorType)).rsplit("Loc", 1)[1]
            out.setdefault(j, {}).setdefault(doc, set()).add((t_, str(g.value(loc, PA.locatorValue))))
    return out


_TARGET_CLAIMS_RX = re.compile(r"청구항 ([\d,]+) —")


def variant_continuity(g: Graph, flat: list[dict], sheet: Path = CARRY_SHEET) -> dict:
    """2차에서 사람이 맞다고 한 범주 변형이 지금 그래프에도 같은 (통지서, 주어 청구항) → (대상 청구항 집합)으로 있는가.
    블록 번호는 G1 분할로 바뀔 수 있어 지역명이 아니라 청구항으로 대조한다."""
    df = pd.read_csv(sheet, dtype=str).fillna("")
    df = df[df["kind"] == CARRY_KIND]
    rel = _graph_relations(g)
    by_key = {r["key"]: r for r in flat}
    have = set()
    for k, rr in rel.items():
        if k in by_key and rr["variant"]:
            have.add((by_key[k]["stem"], tuple(by_key[k]["claims"]),
                      tuple(sorted(tuple(by_key[t]["claims"]) for t in rr["variant"] if t in by_key))))
    rows = []
    for _, r in df.iterrows():
        want = (r["notice"], tuple(int(x) for x in r["claims"].split()),
                tuple(sorted(tuple(int(x) for x in m.split(",")) for m in _TARGET_CLAIMS_RX.findall(r["targets"]))))
        rows.append({"judgment": r["judgment"], "human_correct": r["correct"], "preserved": want in have})
    return {"sheet": str(sheet.relative_to(ROOT)), "rows": len(rows),
            "preserved": sum(x["preserved"] for x in rows), "detail": rows}


def gate(path: Path = SAMPLE_CSV, g: Graph | None = None, flat: list[dict] | None = None) -> dict:
    df = pd.read_csv(path, dtype=str).fillna("")
    res = {}
    for kind, grp in df.groupby("kind"):
        judged = grp[grp["correct"].isin(["0", "1"])]
        n = len(judged)
        rate = round((judged["correct"] == "1").sum() / n, 4) if n else None
        withheld = len(grp) - n
        res[kind] = {"rows": len(grp), "judged": n, "correct": int((judged["correct"] == "1").sum()),
                     "withheld": withheld, "rate": rate,
                     "decidable": withheld <= WITHHELD_MAX * len(grp),
                     "pass": bool(rate is not None and rate >= HUMAN_RATE_MIN and withheld <= WITHHELD_MAX * len(grp))}
        if "split" in grp:
            res[kind]["by_split"] = {s_: {"judged": int(gg["correct"].isin(["0", "1"]).sum()),
                                          "correct": int((gg["correct"] == "1").sum())}
                                     for s_, gg in grp.groupby("split")}
        if "relation_exists" in grp and kind in ("refersToJudgment", "categoryVariantOf"):
            ex = grp[grp["relation_exists"].isin(["0", "1"])]
            res[kind]["relation_exists"] = {"judged": len(ex), "yes": int((ex["relation_exists"] == "1").sum())}
    if False and g is not None and flat is not None and CARRY_SHEET.exists():  # 3차까지의 이어받기 — 4차는 새 표본만
        # 이어받기: 2차 판정 중 관계가 그대로인 것 + 바뀌어 이번 시트에서 다시 판정한 것.
        cont = variant_continuity(g, flat)
        kept = {d["judgment"] for d in cont["detail"] if d["preserved"]}
        prior = pd.read_csv(CARRY_SHEET, dtype=str).fillna("")
        prior = prior[(prior["kind"] == CARRY_KIND) & prior["judgment"].isin(kept) & prior["correct"].isin(["0", "1"])]
        now = df[(df["kind"] == CARRY_KIND) & df["correct"].isin(["0", "1"])]
        n = len(prior) + len(now)
        c = int((prior["correct"] == "1").sum() + (now["correct"] == "1").sum())
        rate = round(c / n, 4) if n else None
        res[CARRY_KIND] = {"carried_from_seed": CARRY_SEED, "carried": len(prior), "rejudged": len(now),
                           "withheld": int((df["kind"] == CARRY_KIND).sum()) - len(now),
                           "judged": n, "correct": c, "rate": rate,
                           "continuity": {k: cont[k] for k in ("rows", "preserved")},
                           "pass": bool(rate is not None and rate >= HUMAN_RATE_MIN
                                        and len(now) == cont["rows"] - cont["preserved"])}
    return {"sheet": str(path.relative_to(ROOT)), "seed": SAMPLE_SEED, "threshold": HUMAN_RATE_MIN, "by_kind": res,
            "pass": bool(res) and all(v["pass"] for v in res.values())}


REGRESS_SHEETS = [ROOT / "data" / "interim" / f"argument_abox_sample_r{i}.csv" for i in (1, 2, 3)]
# 기준 = 가장 최근에 사람이 판정한 회귀 시트. v1 은 `targets`(청구항), v2 부터는 `targets_detail`(판단 식별자)을 싣는다.
REGRESS_JUDGED = ROOT / "data" / "interim" / "argument_abox_regression_judged_v3.csv"
REGRESS_CSV = ROOT / "data" / "interim" / "argument_abox_regression_v4.csv"
_TARGET_KEY_RX = re.compile(r"\[(범주 변형(?: \+ 참조)?|참조)\] (s\d+_b\d+) \(")


def _target_keys(detail: str) -> list[str]:
    """`targets_detail` → 대상 판단 지역명(`s1_b3`) · 종류(범주 변형 / 참조). 표시 라벨 변경(`+ 참조`)은 같은 것으로 본다."""
    return sorted(f"{'V' if k.startswith('범주') else 'R'}:{s}" for k, s in _TARGET_KEY_RX.findall(detail))
REGRESS_KEY_LEN = 100
TARGET_TEXT_MAX = 3000          # 대상 판단 본문 — 300 · 1,200 자에서 잘려 대상 범위를 확인할 수 없던 행(회귀 v2 보류 2 · v3 보류 1)


def _sheet_text(r: dict) -> str:
    """시트 본문 — 종합 결론은 `⟦절 종합 결론 · 문헌 근거로만 사용⟧` 표시 뒤에 따로 보인다."""
    s = _flat(r["text"])
    if r.get("summary"):
        s += " ⟦절 종합 결론 · 문헌 근거로만 사용⟧ " + _flat(r["summary"])
    return s[:TEXT_MAX]


def _state(r: dict, rel: dict, by_key: dict) -> dict:
    rr = rel.get(r["key"], {"refers": set(), "variant": set()})
    return {"claims": " ".join(map(str, r["claims"])), "documents": " ".join(sorted(r["labels"])),
            "common_knowledge": str(int(r["ck"])), "rationale": " ".join(r["rat"]),
            "targets": " | ".join(",".join(map(str, c)) for c in
                                  sorted(tuple(by_key[k]["claims"]) for k in rr["refers"] if k in by_key)),
            "block_text": _sheet_text(r)}


def _targets_detail(r: dict, rel: dict, by_key: dict) -> str:
    """대상 판단을 시트만으로 대조할 수 있게 — 식별자 · 절 · 표지 · 청구항 · 본문 앞 300자."""
    rr = rel.get(r["key"], {"refers": set(), "variant": set()})
    out = []
    for k in sorted(rr["refers"]):
        t = by_key.get(k)
        if t:
            # 범주 변형은 상위 술어 refersToJudgment 도 같은 대상으로 실린다(1홉 실체화) — 둘 다 보여 준다(회귀 v2 참조 7행).
            kind = "범주 변형 + 참조" if k in rr["variant"] else "참조"
            out.append(f"[{kind}] {k.rsplit('_', 2)[-2]}_{k.rsplit('_', 1)[-1]} (절 {t['section']} · 표지 {t['mark'] or '-'}) "
                       f"청구항 {','.join(map(str, t['claims']))}: {_flat(t['text'])[:TARGET_TEXT_MAX]}")
    return " || ".join(out)


def regress(g: Graph, flat: list[dict]) -> tuple[list[dict], dict]:
    """1–3차 표본 전 행을 지금 산출과 대조한다(4차 · 사용자 지시 10-05).

    대응은 **원래 블록의 본문 위치**로 찾는다(통지서 · 지난 시트 본문 앞 100자가 들어 있는 지금 단위). 청구항 겹침으로 찾으면
    11항 판단이 1항 판단에 대응되는 일이 생긴다(1차 회귀 142·160행). 지난 판정(1차 회귀 재판정 포함)은 **대응한 판단도
    같고 추출값도 같을 때만** 그대로 둔다. 1차 회귀에서 증거 부족으로 보류된 행은 증거 칸을 더했으므로 다시 판정한다."""
    rel = _graph_relations(g)
    emitted = {str(j).rsplit("/", 1)[1] for j in g.subjects(RDF.type, PA.ExaminerJudgment)}
    by_key = {r["key"]: r for r in flat}
    by_stem: dict[str, list[dict]] = {}
    for r in flat:
        by_stem.setdefault(r["stem"], []).append(r)
    v1 = pd.read_csv(REGRESS_JUDGED, dtype=str).fillna("") if REGRESS_JUDGED.exists() else None
    rows, summary, i = [], Counter(), 0
    for sheet in REGRESS_SHEETS:
        if not sheet.exists():
            continue
        rnd = sheet.stem.rsplit("_", 1)[1]
        for _, p in pd.read_csv(sheet, dtype=str).fillna("").iterrows():
            j1 = v1.iloc[i] if v1 is not None else None
            i += 1
            if j1 is not None and (j1["round"], j1["prior_judgment"], j1["kind"]) != (rnd, p["judgment"], p["kind"]):
                raise SystemExit(f"1차 회귀 시트의 행 순서가 원래 표본과 다르다: {i}행")
            units = by_stem.get(p["notice"], [])
            key = p["block_text"][:REGRESS_KEY_LEN]
            hit = [u for u in units if key and key in _flat(u["text"])]
            hit.sort(key=lambda u: (_flat(u["text"]).find(key) != 0, u["key"] not in emitted, u["block"]))
            match = "text" if hit else "claims"
            if not hit:
                pc = {int(x) for x in p["claims"].split()}
                hit = sorted((u for u in units if set(u["claims"]) & pc),
                             key=lambda u: -len(set(u["claims"]) & pc) / len(set(u["claims"]) | pc))
            u = hit[0] if hit else None
            v1_state = None
            if j1 is not None and j1["status"] != "dropped" and j1["new_judgment"]:
                v1_state = {k: j1[k] for k in ("claims", "documents", "common_knowledge", "rationale", "block_text")}
                v1_state["targets"] = " ".join(_target_keys(j1.get("targets_detail", "")))
            row = {"round": rnd, "kind": p["kind"], "prior_judgment": p["judgment"], "prior_correct": p["correct"],
                   "prior_note": p["note"], "v1_new_judgment": j1["new_judgment"] if j1 is not None else "",
                   "v1_correct": j1["correct"] if j1 is not None else "", "v1_note": j1["note"] if j1 is not None else "",
                   "match": match}
            if u is None or u["key"] not in emitted:
                reason = "" if u is None else ("label_definition_missing" if u["missing_labels"] else
                                               "no_document_no_common_knowledge" if not u["labels"] and not u["ck"] else "other")
                status, diff = "dropped", reason
                row.update(new_judgment=u["key"] if u else "", section="", block_mark="", claims="", documents="",
                           evidence=u["evidence"] if u else "", common_knowledge="", rationale="", targets_detail="",
                           block_text=_flat(u["text"])[:TEXT_MAX] if u else "")
            else:
                st = _state(u, rel, by_key)
                st["targets"] = " ".join(_target_keys(_targets_detail(u, rel, by_key)))
                diffs = []
                if j1 is not None and j1["new_judgment"] != u["key"]:
                    diffs.append("rematched")
                ref = v1_state or {"claims": p["claims"], "documents": p["documents"],
                                   "common_knowledge": p["common_knowledge"], "rationale": p["rationale"],
                                   "targets": "", "block_text": p["block_text"]}
                for k in ("claims", "documents", "common_knowledge", "rationale", "targets"):
                    if " ".join(sorted(st[k].split())) != " ".join(sorted(ref[k].split())):
                        diffs.append(k)
                if st["block_text"][:len(ref["block_text"])] != ref["block_text"] or (
                        len(ref["block_text"]) < TEXT_MAX and len(st["block_text"]) != len(ref["block_text"])):
                    diffs.append("text")
                if j1 is not None and j1["status"] == "changed" and j1["correct"] == "":
                    diffs.append("evidence_added")          # 지난 회귀에서 증거 부족으로 보류 — 증거 칸을 보강했다
                # 지난 회귀에서 "범주 변형만 있고 참조가 없다" 로 판정된 행 — 그래프에는 참조도 있었고 표시가 하나만 보였다.
                if j1 is not None and j1["correct"] == "0" and "관계 종류 불일치" in j1["note"]:
                    diffs.append("display_fixed")
                status, diff = ("unchanged" if not diffs else "changed"), " ".join(diffs)
                row.update(new_judgment=u["key"], section=u["section"], block_mark=u["mark"], claims=st["claims"],
                           documents=st["documents"], evidence=u["evidence"], common_knowledge=st["common_knowledge"],
                           rationale=st["rationale"], targets_detail=_targets_detail(u, rel, by_key),
                           block_text=st["block_text"])
            carried = j1["correct"] if j1 is not None and j1["status"] != "dropped" else p["correct"]
            summary[f"{ {'1': 'v1_correct', '0': 'v1_wrong'}.get(carried, 'v1_withheld') }__{status}"] += 1
            row.update(status=status, diff=diff, rationale_scope="",
                       relation_exists=(j1["relation_exists"] if j1 is not None and status == "unchanged" else ""),
                       correct=carried if status == "unchanged" else "", note="")
            rows.append(row)
    return rows, dict(sorted(summary.items()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-pilot", action="store_true", help="파일럿 대조만 인쇄 (미달이면 exit 1)")
    ap.add_argument("--sample", action="store_true", help="사람 대조 시트를 data/interim/ 에 쓴다")
    ap.add_argument("--gate", action="store_true", help="사람 대조 시트를 집계해 리포트에 싣는다")
    ap.add_argument("--regress", action="store_true", help="지난 표본 전 행을 지금 산출과 대조한 회귀 시트를 쓴다")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--report", type=Path, default=REPORT)
    args = ap.parse_args()

    if not TXT_DIR.exists():
        raise SystemExit("원천 계층(data/sources/opinion_notices/)이 없다 — 공개 트리에서는 짓지 않는다.")
    text, g, stat, flat = render()

    if args.eval_pilot:
        ev = eval_pilot(flat)
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 0 if ev["pass"] else 1
    if args.regress:
        rows, summary = regress(g, flat)
        with REGRESS_CSV.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        print(f"  {REGRESS_CSV.relative_to(ROOT)} · 다시 판정할 행 {sum(r['status'] == 'changed' for r in rows)}")
        return 0
    if args.sample:
        rows = make_sample(g, flat)
        SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
        with SAMPLE_CSV.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"  {SAMPLE_CSV.relative_to(ROOT)} · {Counter(r['kind'] for r in rows)}")
        return 0

    args.out.write_text(text, encoding="utf-8")
    Graph().parse(args.out, format="turtle")  # 스스로 파싱되지 않는 것은 내지 않는다
    rep_old = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {}
    report = {
        "_README": "논증층 A-Box 계수. 원문·통지서 파일명은 싣지 않는다. 판단 단위 = 청구항 블록(§20.22 A1).",
        "output": str(args.out.relative_to(ROOT)) if args.out.is_relative_to(ROOT) else str(args.out),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "triples": len(g),
        "counts": counts(g),
        "judgments_by_split": by_split(g),
        "extraction": dict(sorted(stat.items())),
        "pilot_eval": eval_pilot(flat),
        "human_gate": gate(g=g, flat=flat) if args.gate else rep_old.get("human_gate"),
        "variant_continuity": variant_continuity(g, flat) if CARRY_SHEET.exists() else None,
        # 지난 회차는 지우지 않는다 — 1차 FAIL 이 3단계 복귀의 근거다.
        "human_gate_history": rep_old.get("human_gate_history", []) + (
            [rep_old["human_gate"]] if args.gate and rep_old.get("human_gate") else []),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = report["counts"]
    print(f"  {report['output']}  {len(g)} triples · 판단 {c['ExaminerJudgment']} · 링크 {c['EvidenceLink']} · "
          f"좌표 {c['DocumentLocator']} · 참조 {c['refersToJudgment']} · 범주 변형 {c['categoryVariantOf']}")
    ev = report["pilot_eval"]
    print(f"  파일럿 대조: 청구항 피복 {ev['claim_coverage']} · 문헌 {ev['document_match']} → "
          f"{'PASS' if ev['pass'] else 'FAIL'}")
    hg = report["human_gate"]
    print("  사람 대조: " + ("미완 — `--sample` 시트를 채운 뒤 `--gate`" if not hg
                          else ("PASS" if hg["pass"] else "FAIL") + f" ({hg['sheet']})"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
