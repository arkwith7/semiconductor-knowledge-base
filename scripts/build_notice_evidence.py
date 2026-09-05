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
    _CLAIM_FOCUS_RX, _normalize_cited_id,
)

# **콜론을 필수로 한다 (교정 3).** 공유 `_CITED_LINE_RX` 는 콜론이 선택이라
# `인용발명 1"이라 함)` 같은 서술을 정의줄로 오탐한다(정규화 실패 176건의 다수).
# 공유 함수를 고치지 않는 이유: 거절결정서 파이프라인이 만든 656건의 확립된 값이
# 함께 흔들린다 — 그것은 별개의 계약이다.
CITED_LINE_RX = re.compile(r"인용발명\s*(\d+)\s*[:：]\s*([^\n]{5,200})")

# **공유 정규화가 놓치는 표기의 보완 (교정 4).** 원문 실측에서 나온 두 형태다.
KR_REG_DASH_RX = re.compile(r"등록특허공보\s*제\s*10[-\s]?(\d{6,7})\s*호")
JP_KOR_RX = re.compile(r"일본[^\n]{0,12}공개특허공보\s*제?\s*(?:평|소|H|S)?\s*(\d{2,4})\s*[-\s]\s*(\d{4,7})")


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
    return None


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


def parse_notice(text: str) -> list[dict]:
    """절 단위로 (법조항, 인용발명 식별자, 대상 청구항)을 뽑는다."""
    dm = DETAIL_RX.search(text)
    body = text[dm.end():] if dm else text        # 표지가 있으면 그 뒤만 본다
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

        cited = []
        for c in CITED_LINE_RX.finditer(seg):
            nid = normalize_cited(c.group(2))
            if nid:
                cited.append(nid)
        claims = sorted({int(n) for cm in _CLAIM_FOCUS_RX.finditer(seg)
                         for n in re.findall(r"\d+", cm.group(1))})

        out.append({"section": int(m.group(1)) if m.group(1) else i + 1, "legal_bases": bases,
                    "cited_ids": sorted(dict.fromkeys(cited)),
                    "target_claims": claims})
    return out


SAMPLE_CSV = ROOT / "data" / "interim" / "notice_legal_basis_sample.csv"


def _gate_result() -> dict:
    """주-2′ — 사람이 채운 표본이 있으면 그 값으로 게이트를 판정한다(§10.10).

    시트 자체는 통지서 원문 발췌를 담으므로 `data/interim/`(gitignore·발행 DENY)에 있고,
    여기에는 **집계만** 남긴다.
    """
    g = {"name": "주-2′ 사람 표본 원문 대조", "threshold": 0.90}
    if not SAMPLE_CSV.exists():
        return {**g, "status": "미산출 — 이것 없이 A 를 완료로 보고하지 않는다"}
    d = pd.read_csv(SAMPLE_CSV)
    v = d["correct"].astype(str).str.strip().map({"1": 1, "0": 0}).dropna()
    if v.empty:
        return {**g, "status": "시트는 있으나 미기입"}
    rate = float(v.mean())
    return {**g, "status": "충족" if rate >= 0.90 else "미달",
            "n": int(len(v)), "correct": int(v.sum()), "rate": round(rate, 4),
            "residual_error_mode": ("틀린 건은 절 경계 오귀속이다 — `이 출원은/의` 앵커가 "
                                    "근거 진술이 아닌 논의 문장에도 걸려, 이웃 구간의 근거가 "
                                    "잘못 붙는다(§42 논의에 §29② 가 붙은 사례 확인)."),}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="엣지 parquet 에 legal_bases(다중값) 컬럼을 채운다 (멱등)")
    ap.add_argument("--write-structured", action="store_true",
                    help="출원별 structured JSON 을 쓴다 (거절결정서와 대칭)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample", type=int, default=0,
                    help="주-2′ 사람 대조 표본 N건을 data/interim/ 에 쓴다 (시드 고정)")
    a = ap.parse_args()

    files = sorted(TXT_DIR.glob("*.txt"))
    if a.limit:
        files = files[:a.limit]

    rows, per_doc, stat = [], [], Counter()
    for f in files:
        app = f.name.split("_")[0]
        text = f.read_text(encoding="utf-8", errors="replace")
        secs = parse_notice(text)
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
                                 "target_claims": ",".join(map(str, s["target_claims"])),
                                 "source_file": f.name})
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

    canon = pd.DataFrame(rows).drop_duplicates(
        subset=["application_number", "cited_doc_id", "legal_basis"])
    CANON.parent.mkdir(parents=True, exist_ok=True)
    canon.to_parquet(CANON, index=False)

    # ── 엣지 부착 ──────────────────────────────────────────────────────────
    ed = pd.read_parquet(EDGES)
    ed["app_no"] = ed.target_patent_id.str.replace("^patent:kr_", "", regex=True)
    ex = ed.source_type == "examiner"
    before = int((ed.loc[ex, "legal_basis"].astype(str).str.len() > 0).sum())

    # §10.9 — tie-break 없음. (출원, 인용) 의 근거 **집합**을 그대로 싣는다.
    sets = (canon.groupby(["application_number", "cited_doc_id"]).legal_basis
                 .apply(lambda s: "|".join(sorted(set(s)))).to_dict())
    # 자릿수 채움 차이를 흡수해 매칭한다 (교정 5) — 실측 35건이 이것만으로 갈렸다
    loose = {}
    for (app, cid), v in sets.items():
        loose.setdefault((app, loose_key(cid)), set()).update(v.split("|"))
    loose = {k: "|".join(sorted(v)) for k, v in loose.items()}
    newvals = [loose.get((r.app_no, loose_key(r.cited_doc_id)), "") for r in ed.itertuples()]
    filled = sum(1 for v, e in zip(newvals, ex) if v and e)
    multi = sum(1 for v, e in zip(newvals, ex) if e and "|" in v)

    # ── 서술 통계: 결정서 유래(evidence_v2)와의 대조 ────────────────────────
    # **게이트가 아니다**(§10.10). 단일값 비교는 폐기된 tie-break 를 재는 것이고
    # 집합 비교는 결과를 본 뒤의 수다. 두 값을 모두 남긴다.
    v2 = ed[(ed.source_type == "evidence_v2")
            & (ed.legal_basis.astype(str).str.len() > 0)][["app_no", "cited_doc_id", "legal_basis"]]
    v2 = v2.assign(ns=[loose.get((r.app_no, loose_key(r.cited_doc_id))) for r in v2.itertuples()])
    v2 = v2[v2.ns.notna() & (v2.ns != "")]
    contain = float(v2.apply(lambda r: r.legal_basis in r.ns.split("|"), axis=1).mean()) if len(v2) else None
    exact = float((v2.legal_basis == v2.ns).mean()) if len(v2) else None

    if a.apply:
        ed["legal_bases"] = ["" if not e else v for v, e in zip(newvals, ex)]
        ed.drop(columns=["app_no"]).to_parquet(EDGES, index=False)

    by_lb = Counter(b for v, e in zip(newvals, ex) if v and e for b in v.split("|"))
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

    print(f"{'적용됨' if a.apply else '미적용 (--apply 로 반영)'} · 리포트 {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
