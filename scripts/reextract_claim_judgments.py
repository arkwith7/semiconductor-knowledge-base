#!/usr/bin/env python3
"""거절결정 OCR 원문 → 청구항-단위 판단 재추출 (PLAN plan_claim_judgment_reextraction).

기존 evidence_v2 는 근거 원문이 라이선스로 제거돼 청구항 번호가 절반(407행/160특허)만 남았다.
발췌 삭제 **전** OCR 원문(paper_data)에서 (청구항, 인용발명, 근거)를 로컬 LLM 으로 재추출한다.
로컬 처리 — OCR 원문이 기기를 벗어나지 않는다(라이선스 안전). 캐시로 결정화.

인용발명N → 실제 doc_id 는 sdkb 구조화 JSON 의 cited_evidence_map 으로 해소(이미 보유).
'제17항 내지 제19항' 같은 범위는 확장한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_claim_validate import _conn  # 캐시 재사용 패턴  # noqa: E402
import requests  # noqa: E402

OCR_DIR = Path("/home/arkwith/Dev/paper_data/data/processed/rejection_decisions/txt")
STRUCT_DIR = Path("/home/arkwith/Dev/sdkb/data/patents/rejection_decisions/structured")
OUT = Path("/home/arkwith/Dev/sdkb/data/interim/reextracted_judgments.jsonl")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3-coder:30b"

# 거절결정서의 '거절이유가 해소되지 않은 부분' 표 — 순번 · 청구항식 · 법조항.
# 매우 규칙적이라 결정적 파싱이 LLM 보다 신뢰 가능하고, **최종 거절결정의 authoritative
# 청구항**을 준다(GT evidence_v2 는 이전 의견제출통지서 청구항을 섞은 노이즈를 포함).
_TABLE = re.compile(r"거절이유가\s*해소되지\s*않은\s*부분", re.S)
_ROW = re.compile(r"청구항\s*(?P<claims>[^\n]*?)\s*특허법\s*(?P<law>제\s*\d+\s*조[^\n]*)")
_G29 = re.compile(r"제\s*29\s*조\s*제?\s*(?P<para>[12])\s*항")
_EXAMINED = re.compile(r"심사\s*대상\s*청구항\s*[:：]\s*(?P<list>[^\n\[]+)")


def expand_claims(text: str) -> list[int]:
    """'제17항 내지 제19항' → [17,18,19] · '17-19' → [17,18,19] · '제6항' → [6]."""
    out: set[int] = set()
    t = text.replace("제", " ").replace("항", " ")
    for m in re.finditer(r"(\d+)\s*(?:내지|~|-|—)\s*(\d+)", t):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b <= a + 100:
            out.update(range(a, b + 1))
    # 단독 번호
    ranges = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r"(\d+)\s*(?:내지|~|-|—)\s*(\d+)", t)]
    for m in re.finditer(r"\b(\d+)\b", t):
        n = int(m.group(1))
        if not any(a <= n <= b for a, b in ranges) and n < 500:
            out.add(n)
    return sorted(out)


def _examined_claims(text: str) -> list[int]:
    m = _EXAMINED.search(text)
    return expand_claims(m.group("list")) if m else []


def parse_table(text: str) -> list[tuple[list[int], str]]:
    """'거절이유가 해소되지 않은 부분' 표 → [(청구항들, §29①/②)]. §29 근거만."""
    tm = _TABLE.search(text)
    if not tm:
        return []
    # 표는 헤더와 다음 대괄호 절([거절결정의 이유] 등) 사이에만 있다. 본문까지 넘기면
    # 본문의 긴 청구항 서술을 흡수해 과대추출된다.
    rest = text[tm.end():]
    stop = rest.find("[")
    region = rest[: stop if 0 < stop < 900 else 900]
    examined = _examined_claims(text)
    out = []
    for r in _ROW.finditer(region):
        g = _G29.search(r.group("law"))
        if not g:
            continue                              # §42 등 선행기술 무관 근거 제외
        ground = "§29①" if g.group("para") == "1" else "§29②"
        cexpr = r.group("claims")
        claims = examined if ("전항" in cexpr or "전 항" in cexpr) else expand_claims(cexpr)
        if claims:
            out.append((claims, ground))
    return out


def reextract(app: str, cache=None) -> list[dict]:
    """한 특허의 재추출 판단 [{target_patent, cited_doc, ground, target_claims}].

    결정적 표 파싱 — 청구항×근거는 표에서, 인용 doc 는 cited_evidence_map 에서.
    한 (청구항,근거) 는 그 특허의 모든 인용발명과 짝짓는다(evidence_v2 와 같은 형식 —
    거절은 통상 인용발명들의 결합에 대한 것).
    """
    txt_p = OCR_DIR / f"{app}.txt"
    st_p = STRUCT_DIR / f"{app}.json"
    if not txt_p.exists() or not st_p.exists():
        return []
    cev = json.load(st_p.open()).get("cited_evidence_map") or {}
    cited_docs = sorted(set(cev.values()))
    text = txt_p.read_text(encoding="utf-8", errors="ignore")
    out = []
    for claims, ground in parse_table(text):
        for doc in cited_docs:
            out.append({"target_patent": app, "cited_doc": doc,
                        "ground": ground, "target_claims": claims})
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0=전량")
    ap.add_argument("--validate", action="store_true", help="기존 GT 대비 검증만")
    args = ap.parse_args()

    apps = sorted(p.stem for p in OCR_DIR.glob("*.txt"))
    cache = _conn()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    if args.validate:
        # 기존 GT(evidence_v2 target_claims) 있는 특허에서 청구항 집합 일치율
        gt = {}
        for line in open("/home/arkwith/Dev/sdkb/data/patents/raw/semiconductor_industry_rejected_patents.jsonl"):
            d = json.loads(line); a = d["target_patent"]["application_number"]
            cl = set()
            for e in (d["meta"].get("ground_truth_evidence_v2") or []):
                cl.update(int(x) for x in (e.get("target_claims") or []) if str(x).isdigit())
            if cl:
                gt[a] = cl
        val = [a for a in apps if a in gt][:(args.limit or 30)]
        agree = 0
        for a in val:
            re_cl = set(c for j in reextract(a, cache) for c in j["target_claims"])
            inter = len(re_cl & gt[a]); union = len(re_cl | gt[a])
            jac = inter / union if union else 0
            agree += jac
            print(f"  {a}: GT={sorted(gt[a])} 재추출={sorted(re_cl)} Jaccard={jac:.2f}")
        print(f"\n검증 {len(val)}건 평균 Jaccard: {agree/len(val):.2f}")
        return 0

    n = rows = 0
    with OUT.open("w") as fh:
        for a in apps:
            js = reextract(a, cache)
            for j in js:
                fh.write(json.dumps(j, ensure_ascii=False) + "\n")
            rows += len(js); n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(apps)} 특허 · {rows} 판단행")
    print(f"✓ {n} 특허 → {rows} 판단행 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
