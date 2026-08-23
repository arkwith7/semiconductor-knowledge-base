#!/usr/bin/env python3
"""CR-001B — 한국어 한정요소 표면형 후보 수확기 (제안 파일만 낸다).

**이 스크립트는 사전을 쓰지 않는다.** 후보와 판정 재료를 리포트로 낼 뿐이고, 실제 등재는
사람이 `mappings/abox_term_aliases.json` 을 큐레이션해서 한다(CR-001B §9.1). 자동 등재를
막는 이유는 성공기준 ④(위양성 검수)이 사람의 판단을 요구하기 때문이다.

수확 범위는 **dev + train 질의 800 건**뿐이다 — test·test_b 문서는 열지 않는다(§1-4 누출
통제). 범위는 `data/sources/harvest_scope_dev_train.json` 이 정하며, 그 파일은 하류 동결
분할에서 파생됐고 자기 출처와 sha256 을 담는다.

통로 둘 (CR-001B §8):
  (a) 주 통로 — 범위 질의의 **독립항 한정요소 본문**. 한정요소 어휘가 실제로 사는 자리다.
  (b) 고정밀 씨앗 — 의견제출통지서의 `<표 N>` 구성 대비표. 청구항 한정요소와 인용발명
      대응물을 같은 행에 담는다. 다만 얇다(dev 2.6 % · train 3.7 % 파일).

R7-DF-CEILING 판정 재료를 함께 낸다 — A-Box 문서빈도 비율(분모 = CR-009 df_denominator).
문턱 0.06 은 **결과가 아니라 기존 사전의 분포**에서 유도했다(CR-001B §9.3).

결정적이다. 정렬 순회 · 타임스탬프 없음 · 난수 없음. 같은 원천 → 같은 바이트.
**제안 파일에 원문 문장을 담지 않는다** — 표면형·빈도·출처 통로만 담는다(상류 §1-5).

    python scripts/harvest_ko_surfaces.py
    python scripts/harvest_ko_surfaces.py --check      # 재생성이 현재 파일과 같은지만 확인
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_concept_mapping import ALIASES_PATH, load_abox_docs, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCOPE_PATH = ROOT / "data" / "sources" / "harvest_scope_dev_train.json"
FEATURES_JSONL = ROOT / "data" / "interim" / "claim_features.jsonl"
CLAIM_FEATURES_PQ = ROOT / "mappings" / "claim_features.parquet"
NOTICES_DIR = ROOT / "data" / "sources" / "opinion_notices" / "txt"
MAPPING_PATH = ROOT / "mappings" / "concept_mapping.json"
OUT_CANDIDATES = ROOT / "data" / "reports" / "ko_surface_candidates.json"
OUT_PROPOSALS = ROOT / "data" / "reports" / "ko_concept_proposals.json"

PROFILE = "patent-text"
DF_CEILING = 0.06          # CR-001B §9.3 — 기존 사전 한글 표면형 154개의 A-Box df 90분위 0.0561 올림
MIN_QUERY_DF_CLAIM = 10    # 주 통로 최소 질의 문서빈도
MIN_QUERY_DF_TABLE = 1     # 씨앗 통로는 얇으므로 문턱을 두지 않는다

# CR-001B 성공기준 ②′ 의 대상 — 1단계 §2.2 가 센 기본 도메인 낱말 19.
# **전량 판정한다**: entries · blocked · 제안(축 부재) 셋 중 하나로 반드시 자리를 갖는다.
BASIC_19 = ("기판", "웨이퍼", "전극", "게이트", "배선", "트렌치", "비아", "감광막", "유전체",
            "금속배선", "스페이서", "채널", "소스", "드레인", "캐패시터", "적층", "온도",
            "압력", "유량")

# 등재하지 않은 기본 낱말의 사유 — §5.6 실측(그래프에 담을 축이 없다)에 근거한다.
BASIC_REASON = {
    "감광막": "층위 보류 — 물질(photoresist)과 그 막의 층위가 달라 기존 노드에 붙이지 않았다.",
}
NO_AXIS_REASON = ("축 부재 — 구조 요소를 담을 클래스가 TBox 에 없다(CR-001B §5.6). "
                  "기존 Device·Process 축에 넣는 것은 축 범주 오류다(D-15·R4).")

_HANGUL_RUN = re.compile(r"[가-힣]{2,6}")
_TABLE_OPEN = re.compile(r"^\s*<\s*표\s*\d+\s*>\s*$")
_TABLE_ROW = re.compile(r"구성\s*\d+\s*[-–]\s*[가-힣0-9]+")
_JUDGMENT = re.compile(r"(실질적\s*동일|차이|대응|동일|주지관용|설계변경)")

# 굴절·법리·서식 어휘를 거르는 접미 규칙. 하류 적용기가 부분문자열로 보므로 형태소 경계가
# 필요 없고(CR-001B §9.2), 남는 굴절형은 이 필터와 사람 큐레이션이 거른다.
_INFLECTION_SUFFIX = (
    "하는", "되는", "하고", "하며", "되어", "된다", "한다", "이고", "있는", "없는",
    "하여", "되며", "지는", "시키", "되도", "하도", "하기", "되기", "라고", "으로",
    "에서", "부터", "까지", "이며", "이나", "또는", "및는", "같은", "따라", "위한",
    "대한", "의해", "통해", "포함", "구비", "형성", "제공", "구성",
)
# 조사·어미 한 글자 꼬리 (3자 이상에만 적용 — 위 docstring 참조).
_JOSA_TAIL = frozenset("을를이가은는의에와과로며고서인된한도만")

_LEGAL_STOP = frozenset("""
청구항 발명 인용 기재 특허 출원 심사 통상 기술자 용이 곤란 진보 신규 거절 이유 의견 제출
통지 보정 명세서 도면 참조 상기 이상 이하 경우 방법 장치 시스템 단계 부분 하나 복수 각각
소정 임의 실시 예를 있습니다 판단 대비 대응 동일 차이 구성 효과 목적 문헌 공개 공보 번호
발송 일자 제출인 대리인 특허청 심사관 성명 주소 전화 참고 사항 안내 기간 연장 신청 서식
""".split())


def load_scope() -> dict:
    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    if set(scope["counts"]) - {"dev", "train"}:
        raise ValueError(f"수확 범위에 dev·train 밖 분할이 있다: {sorted(scope['counts'])}")
    return scope


def independent_claim_keys(doc_ids: set[str]) -> set[tuple[str, int]]:
    """(publication_id, claim_number) — 범위 질의의 독립항만."""
    import pandas as pd

    df = pd.read_parquet(CLAIM_FEATURES_PQ,
                         columns=["publication_id", "side", "claim_number", "is_independent"])
    df = df[(df["side"] == "rej") & (df["is_independent"]) & (df["publication_id"].isin(doc_ids))]
    return {(str(p), int(c)) for p, c in zip(df["publication_id"], df["claim_number"])}


def harvest_claims(keys: set[tuple[str, int]]) -> tuple[Counter[str], int]:
    """(a) 주 통로 — 독립항 한정요소 본문 → 표면형 **문서**빈도. (df, 읽은 문서 수)."""
    per_doc: dict[str, set[str]] = defaultdict(set)
    with FEATURES_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("source") != "rejected":
                continue
            patent = str(rec.get("patent") or "")
            if not patent.startswith("rej:"):
                continue
            doc_id = "kr_" + patent.split(":", 1)[1]
            key = (doc_id, int(rec.get("claim_no") or 0))
            if key not in keys:
                continue
            text = " ".join(str(f.get("text") or "") for f in rec.get("features") or [])
            per_doc[doc_id].update(_HANGUL_RUN.findall(norm(text)))
    df: Counter[str] = Counter()
    for surfaces in per_doc.values():
        df.update(surfaces)
    return df, len(per_doc)


def harvest_tables(paths: list[Path]) -> tuple[Counter[str], int, int]:
    """(b) 씨앗 통로 — 통지서 `<표 N>` 구성 대비표 셀. (df, 표를 가진 파일 수, 읽은 파일 수)."""
    per_doc: dict[str, set[str]] = defaultdict(set)
    with_table = 0
    for path in sorted(paths):
        in_table = False
        found = False
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if _TABLE_OPEN.match(raw):
                in_table = True
                continue
            if in_table and not raw.strip():
                in_table = False
                continue
            if not in_table:
                continue
            m = _TABLE_ROW.search(raw)
            if not m:
                continue
            cell = _JUDGMENT.split(raw[m.end():])[0]
            surfaces = _HANGUL_RUN.findall(norm(cell))
            if surfaces:
                found = True
                per_doc[path.stem].update(surfaces)
        with_table += int(found)
    df: Counter[str] = Counter()
    for surfaces in per_doc.values():
        df.update(surfaces)
    return df, with_table, len(paths)


def registered_surfaces() -> set[str]:
    asset = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    prof = asset["profiles"][PROFILE]
    return ({norm(e["surface"]) for e in prof["entries"]}
            | {norm(b["surface"]) for b in prof["blocked"]})


def is_noun_like(surface: str) -> bool:
    """명사구 필터 — 굴절 접미와 법리·서식 어휘를 거른다(성공기준 ④의 1차 방어).

    조사·어미 한 글자 꼬리는 **3자 이상에서만** 거른다. 2자 명사에는 그 글자가 어간의
    일부인 경우가 많기 때문이다(회로·온도·효과 — 3자 이상에서는 `재료를`·`형성된` 이 된다).
    """
    if surface in _LEGAL_STOP:
        return False
    if surface.endswith(_INFLECTION_SUFFIX):
        return False
    return not (len(surface) >= 3 and surface[-1] in _JOSA_TAIL)


def abox_df(surfaces: list[str], docs: list[str]) -> dict[str, int]:
    """A-Box 문서빈도 — build_concept_mapping.concept_df 와 **같은 참조 적용기**(부분문자열)."""
    counts = {s: 0 for s in surfaces}
    for doc in docs:
        if not doc:
            continue
        for s in surfaces:
            if s in doc:
                counts[s] += 1
    return counts


def rank(claim_df: Counter[str], table_df: Counter[str], known: set[str],
         docs: list[str]) -> list[dict]:
    """후보 확정 · R7 판정. 정렬은 (표면형) 사전순 — 결정성."""
    cands: set[str] = set()
    for surface, n in claim_df.items():
        if n >= MIN_QUERY_DF_CLAIM:
            cands.add(surface)
    for surface, n in table_df.items():
        if n >= MIN_QUERY_DF_TABLE:
            cands.add(surface)
    cands = {s for s in cands if is_noun_like(s)}
    fresh = sorted(s for s in cands if s not in known)
    df = abox_df(fresh, docs)
    denom = len(docs)
    out = []
    for s in fresh:
        ratio = df[s] / denom if denom else 0.0
        channels = []
        if claim_df.get(s, 0) >= MIN_QUERY_DF_CLAIM:
            channels.append("claim")
        if table_df.get(s, 0) >= MIN_QUERY_DF_TABLE:
            channels.append("table")
        out.append({
            "surface": s,
            "channels": channels,
            "query_df_claim": claim_df.get(s, 0),
            "query_df_table": table_df.get(s, 0),
            "abox_df": df[s],
            "abox_df_ratio": round(ratio, 4),
            "r7": "pass" if ratio <= DF_CEILING else "blocked",
        })
    return out


def curated_surfaces() -> set[str]:
    """이미 큐레이션으로 사전에 오른 표면형 — 제안 목록에서 뺀다."""
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    return {norm(t) for t in aliases if not t.startswith("_")}


def basic_term_ledger(mapping: dict, df: dict[str, int], denom: int) -> list[dict]:
    """성공기준 ②′ — 기본 낱말 19 의 판정 대장. 미판정이 남으면 그것이 실패의 증거다."""
    pt = mapping["profiles"][PROFILE]
    entries = {norm(e["surface"]): e["concept_id"] for e in pt["entries"]}
    blocked = {norm(b["surface"]): b for b in pt["blocked"]}
    out = []
    for term in sorted(BASIC_19):
        s = norm(term)
        ratio = df.get(s, 0) / denom if denom else 0.0
        row = {
            "surface": s,
            "abox_df": df.get(s, 0),
            "abox_df_ratio": round(ratio, 4),
            "r7": "pass" if ratio <= DF_CEILING else "blocked",
        }
        if s in entries:
            row["disposition"] = "entry"
            row["concept_id"] = entries[s]
        elif s in blocked:
            row["disposition"] = "blocked"
            row["concept_id"] = blocked[s]["concept_id"]
            row["rule_id"] = blocked[s]["rule_id"]
        else:
            row["disposition"] = "proposal"
            row["reason"] = BASIC_REASON.get(s, NO_AXIS_REASON)
        out.append(row)
    return out


def build(scope: dict) -> tuple[dict, dict]:
    doc_ids = set(scope["doc_ids"])
    keys = independent_claim_keys(doc_ids)
    claim_df, n_claim_docs = harvest_claims(keys)
    appnums = set(scope["application_numbers"])
    notices = [p for p in sorted(NOTICES_DIR.glob("*.txt"))
               if p.stem.split("_", 1)[0] in appnums]
    table_df, n_with_table, n_notices = harvest_tables(notices)
    docs = load_abox_docs()
    known = registered_surfaces()
    cands = rank(claim_df, table_df, known, docs)

    n_pass = sum(1 for c in cands if c["r7"] == "pass")
    candidates = {
        "_README": "CR-001B 한국어 표면형 후보. **제안이지 등재가 아니다** — 등재는 "
                   "mappings/abox_term_aliases.json 큐레이션으로만 이뤄진다. 원문 문장을 "
                   "담지 않는다(표면형·빈도·통로만). candidates 는 **아직 등재되지 않은** "
                   "표면형이다 — 큐레이션으로 오른 것은 여기서 빠지고 concept_mapping.json 에 "
                   "있다. 그래서 이 파일은 사전 재생성 **뒤에** 다시 낸다.",
        "scope": {
            "splits": scope["counts"],
            "queries": len(doc_ids),
            "independent_claims": len(keys),
            "claim_docs_read": n_claim_docs,
            "notices_in_scope": n_notices,
            "notices_with_table": n_with_table,
            "excluded_splits": scope["excluded_splits"],
            "split_sha256": scope["_source"]["sha256"],
        },
        "rule": {
            "id": "R7-DF-CEILING",
            "df_ceiling": DF_CEILING,
            "df_denominator": len(docs),
            "min_query_df_claim": MIN_QUERY_DF_CLAIM,
            "min_query_df_table": MIN_QUERY_DF_TABLE,
            "note": "abox_df 는 build_concept_mapping 의 참조 적용기(정규화 부분문자열)로 "
                    "센 값이며 하류 적용기와 같지 않다(CR-009 · 하류가 ρ 로 회신한다).",
        },
        "summary": {
            "candidates": len(cands),
            "r7_pass": n_pass,
            "r7_blocked": len(cands) - n_pass,
            "from_table": sum(1 for c in cands if "table" in c["channels"]),
        },
        "candidates": cands,
    }

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    basic = basic_term_ledger(mapping, abox_df(sorted({norm(t) for t in BASIC_19}), docs),
                              len(docs))
    candidates["basic_terms"] = {
        "_README": "성공기준 ②′ — 기본 낱말 19 의 판정. 미판정 0 이어야 한다.",
        "counts": {k: sum(1 for r in basic if r["disposition"] == k)
                   for k in ("entry", "blocked", "proposal")},
        "terms": basic,
    }

    curated = curated_surfaces()
    unresolved = [c for c in cands if c["r7"] == "pass" and c["surface"] not in curated]
    proposals = {
        "_README": "CR-001B 출력 (2) — 기존 개념으로 해소되지 않은 R7 통과 후보. "
                   "**신규 개념 IRI 등재는 이 파일에 포함되지 않는다**(CR-001B §9.6 갈래 ㉢). "
                   "구조 요소 축은 TBox 에 없으며 신설은 별도 승인 사항이다.",
        "decision": "㉢ 보류 — 제안 목록만 내고, 표면형은 기존 개념에만 붙인다.",
        "summary": {"unresolved": len(unresolved), "curated": len(cands) - len(unresolved),
                    "basic_terms_without_axis": sum(
                        1 for r in basic if r["disposition"] == "proposal")},
        "basic_terms": [r for r in basic if r["disposition"] == "proposal"],
        "proposals": unresolved,
    }
    return candidates, proposals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="쓰지 않고 현재 파일과 같은지만 확인한다(결정성 회귀).")
    args = ap.parse_args()

    candidates, proposals = build(load_scope())
    pairs = [(OUT_CANDIDATES, candidates), (OUT_PROPOSALS, proposals)]
    rc = 0
    for path, payload in pairs:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            cur = path.read_text(encoding="utf-8") if path.exists() else ""
            same = cur == text
            print(f"{'✓' if same else '✗'} deterministic: {path.relative_to(ROOT)} "
                  f"{'동일' if same else '다름'}")
            rc |= 0 if same else 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"✓ {path.relative_to(ROOT)}")
    if not args.check:
        bt = candidates["basic_terms"]["counts"]
        print(f"  기본 낱말 19 — 등재 {bt['entry']} · 차단 {bt['blocked']} · 제안 {bt['proposal']}"
              f" · 미판정 {19 - sum(bt.values())}")
        s = candidates["summary"]
        sc = candidates["scope"]
        print(f"  범위 질의 {sc['queries']} · 독립항 {sc['independent_claims']} · "
              f"통지서 {sc['notices_in_scope']}(표 보유 {sc['notices_with_table']})")
        print(f"  후보 {s['candidates']} · R7 통과 {s['r7_pass']} · 차단 {s['r7_blocked']} · "
              f"씨앗 통로 {s['from_table']}")
        print(f"  미해소 제안 {proposals['summary']['unresolved']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
