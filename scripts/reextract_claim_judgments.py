#!/usr/bin/env python3
"""거절결정 OCR 원문 → 청구항-단위 판단 재추출 (PLAN plan_claim_judgment_reextraction).

기존 evidence_v2 는 근거 원문이 라이선스로 제거돼 청구항 번호가 절반(407행/160특허)만 남았다.
발췌 삭제 **전** OCR 원문(paper_data)에서 (청구항, 인용발명, 근거)를 로컬 LLM 으로 재추출한다.
로컬 처리 — OCR 원문이 기기를 벗어나지 않는다(라이선스 안전). 캐시로 결정화.

인용발명N → 실제 doc_id 는 sdkb 구조화 JSON 의 cited_evidence_map 으로 해소(이미 보유).
'제17항 내지 제19항' 같은 범위는 확장한다.

CR-004R (2026-08-02): 의견제출통지서(999건·1,155문서)를 두 번째 입력으로 union 한다.
① 기존 판단(§29 근거 · 인용문헌 연결 · PriorArtJudgment)은 거절결정서 표만 그대로 쓴다 —
   의견제출통지서에는 cited_evidence_map(구조화 인용문헌 해소)이 없고, 새로 만드는 것은
   범위 밖이다(§1.3 — 검증 못 한 인용 해소를 쓰지 않는다). 이 경로는 **변경 없음**.
② 신규: 조-항-호 전 조항(§29 한정 아님)을 표에서 뽑아 RejectionReason 재료(rejection_reasons.jsonl)
   를 만든다. 인용문헌이 필요 없어(그 조항이 출원 내에서 제기됐다는 사실만 기록) 위 제약과
   무관하다. 회차(round)는 출원 내 전 문서(통지서+결정서)를 발송일자 오름차순으로 매겨 결정적.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    # 이 스크립트에서 실제로 쓰이지 않는 죽은 의존성이었다(cache/requests 미참조) — CR-004R 의
    # --reasons-only 경로(순수 파이썬, 네트워크 불필요)가 uv 환경에 requests 가 없어 막히던
    # 것을 고치는 김에 지연 임포트로 바꾼다. 신규 의존성 추가 아님(§1.9 무관).
    from llm_claim_validate import _conn  # noqa: E402
except ImportError:
    _conn = None  # type: ignore[assignment]

# 2026-08-09(CR-016): 경로 일곱 개가 개인 홈 절대경로였다 — 넷은 이 저장소를 스스로
# 가리켰고(그런데 남의 컴퓨터에서는 없는 경로다) 둘은 흡수 전 paper_data 를 가리켰다.
# 흡수(§4)로 통지서·OCR 산출물의 자리는 이 저장소의 data/processed/ 다.
REPO = Path(__file__).resolve().parents[1]
OCR_DIR = REPO / "data" / "processed" / "rejection_decisions" / "txt"
STRUCT_DIR = REPO / "data" / "patents" / "rejection_decisions" / "structured"
OPINION_DIR = REPO / "data" / "processed" / "opinion_notices"
OPINION_INDEX = OPINION_DIR / "_index.json"
OUT = REPO / "data" / "interim" / "reextracted_judgments.jsonl"
REASONS_OUT = REPO / "data" / "interim" / "rejection_reasons.jsonl"
REASONS_REPORT = REPO / "data" / "reports" / "rejection_reasons_loss.json"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3-coder:30b"

# 거절결정서의 '거절이유가 해소되지 않은 부분' 표 — 순번 · 청구항식 · 법조항.
# 매우 규칙적이라 결정적 파싱이 LLM 보다 신뢰 가능하고, **최종 거절결정의 authoritative
# 청구항**을 준다(GT evidence_v2 는 이전 의견제출통지서 청구항을 섞은 노이즈를 포함).
_TABLE = re.compile(r"거절이유가\s*해소되지\s*않은\s*부분", re.S)
_ROW = re.compile(r"청구항\s*(?P<claims>[^\n]*?)\s*특허법\s*(?P<law>제\s*\d+\s*조[^\n]*)")
_G29 = re.compile(r"제\s*29\s*조\s*제?\s*(?P<para>[12])\s*항")
_EXAMINED = re.compile(r"심사\s*대상\s*청구항\s*[:：]\s*(?P<list>[^\n\[]+)")

# ── CR-004R: 전 조항 근거 파서 (RejectionReason 용 · §29 한정 아님) ──────────
# 의견제출통지서·거절결정서 둘 다 같은 표 헤더 변형을 쓴다:
#   거절결정서 = "거절이유가 해소되지 않은 부분과 관련 법조항"
#   의견제출통지서 = "거절이유가 있는 부분과 관련 법조항"
_TABLE_HEADERS = re.compile(r"거절이유가\s*(?:해소되지\s*않은|있는)\s*부분(?:과\s*관련\s*법조항)?")
# "특허법 제45조 및 특허법 시행령 제6조제2호" 에서 뒤의 "특허법 시행령 제N조"는 "특허법" 바로 뒤가
# "시행령"이라 아래 패턴이 매치하지 않는다 — 시행령 참조를 걸러내기 위한 별도 처리 불필요.
_LAW_FULL = re.compile(
    r"특허법\s*제\s*(?P<art>\d+)\s*조"
    r"(?:\s*제\s*(?P<para>\d+)\s*항)?"
    r"(?:\s*제\s*(?P<item>\d+)\s*호)?"
)
_NOTICE_DATE = re.compile(r"발송일자\s*[:：]?\s*(?P<y>\d{4})\.(?P<m>\d{1,2})\.(?P<d>\d{1,2})\.?")
_NOTICE_SEND = re.compile(r"발송번호\s*[:：]?\s*(?P<send>[\d\-]+)")

# 조-항 → RejectionType 로컬 이름 (조-항 단위 분류. 호(號)는 groundClause 문자열에만 보존).
# 제42조5항(2014.6.11. 삭제)은 여기 없다 — 개체를 발행하지 않는다(확인 못한 의미에 이름 안 붙임).
GROUND_MAP: dict[str, str] = {
    "29-1": "Rejection_Novelty",
    "29-2": "Rejection_Inventiveness",
    "29-3": "Rejection_ExpandedPriorFiling",
    "36-2": "Rejection_SameDayFiling",
    "42": "Rejection_ClarityScope",
    "42-3": "Rejection_Disclosure",
    "42-4": "Rejection_ClaimRequirements",
    "42-8": "Rejection_ClaimFormat",
    "45": "Rejection_UnityOfInvention",
    "47-2": "Rejection_AmendmentScope",
    "52-1": "Rejection_DivisionalScope",
    "2": "Rejection_Eligibility",
}


def _clause_str(art: str, para: str | None, item: str | None) -> str:
    """조-항-호 → groundClause 문자열. 항 없으면 조만, 호 없으면 끝에 '-'만 남긴다."""
    if not para:
        return art
    if not item:
        return f"{art}-{para}-"
    return f"{art}-{para}-{item}"


def _ground_key(art: str, para: str | None) -> str:
    """조-항 → GROUND_MAP 조회 키 (호는 분류에 영향 없음)."""
    return f"{art}-{para}" if para else art


def parse_clauses(text: str) -> list[tuple[str, str]]:
    """표 영역에서 근거 조항 전부 추출 → [(ground_key, groundClause_문자열), ...] · 중복 제거.

    §29 한정이던 parse_table() 과 달리 전 조항(42/45/36/47/52 등)을 다룬다. 인용문헌·청구항
    번호는 다루지 않는다 — RejectionReason 은 (출원×조항×회차) 단위이지 청구항 단위가 아니다.
    """
    tm = _TABLE_HEADERS.search(text)
    if not tm:
        return []
    rest = text[tm.end():]
    stop = rest.find("[")
    region = rest[: stop if 0 < stop < 900 else 900]
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for m in _LAW_FULL.finditer(region):
        art, para, item = m.group("art"), m.group("para"), m.group("item")
        gkey = _ground_key(art, para)
        clause = _clause_str(art, para, item)
        if clause in seen:
            continue
        seen.add(clause)
        out.append((gkey, clause))
    return out


def _parse_notice_date(text: str) -> str | None:
    m = _NOTICE_DATE.search(text)
    if not m:
        return None
    return f"{m.group('y')}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"


def _parse_notice_send(text: str) -> str:
    m = _NOTICE_SEND.search(text)
    return m.group("send").replace("-", "") if m else ""


def _opinion_docs_for(app: str, opinion_index: dict) -> list[Path]:
    entry = opinion_index.get(app)
    if not entry:
        return []
    return [OPINION_DIR / "txt" / f"{d['file']}.txt" for d in entry.get("docs", [])]


def extract_rejection_reasons(app: str, opinion_index: dict) -> list[dict]:
    """한 출원의 모든 통지 문서(의견제출통지서 + 거절결정서)에서 RejectionReason 재료를 만든다.

    회차는 출원 내 문서를 발송일자(동일자면 발송번호) 오름차순으로 매긴 결정적 순번(1부터).
    조항이 GROUND_MAP 에 없으면(예: 42-5, 42-1/2/6/7/9, 36-1 등) 그 조항은 인스턴스를 만들지
    않고 건너뛴다 — reasonGround 는 SHACL 상 정확히 1개가 필요하므로, 확인 안 된 매핑을
    지어내지 않는다(§1.3). 스킵된 조항은 호출자가 loss report 에 집계한다.
    """
    docs: list[tuple[str, Path]] = [("의견제출통지서", p) for p in _opinion_docs_for(app, opinion_index)]
    decision_p = OCR_DIR / f"{app}.txt"
    if decision_p.exists():
        docs.append(("거절결정서", decision_p))

    parsed = []
    for notice_type, p in docs:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        date = _parse_notice_date(text)
        send = _parse_notice_send(text)
        clauses = parse_clauses(text)
        parsed.append({
            "notice_type": notice_type, "path": p, "date": date or "9999-99-99",
            "send": send, "clauses": clauses,
        })
    if not parsed:
        return []
    parsed.sort(key=lambda d: (d["date"], d["send"]))

    out = []
    skipped: list[str] = []
    for round_no, d in enumerate(parsed, start=1):
        for gkey, clause in d["clauses"]:
            local_name = GROUND_MAP.get(gkey)
            if local_name is None:
                skipped.append(clause)
                continue
            out.append({
                "application": app,
                "clause": clause,
                "reason_ground": local_name,
                "notice_round": round_no,
                "notice_type": d["notice_type"],
                "notice_date": d["date"] if d["date"] != "9999-99-99" else None,
            })
    if skipped:
        out.append({"application": app, "_skipped_clauses": skipped})
    return out


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


def build_reasons() -> None:
    """CR-004R: 통지서(전 조항) → rejection_reasons.jsonl + 손실 리포트.

    입력 모집단 = 의견제출통지서 999건 ∪ 거절결정서 존재분(OCR_DIR). 기존 reextract() 판단
    경로(§29·인용문헌)와 독립 — 이 함수는 OUT/reextract() 를 건드리지 않는다.
    """
    opinion_index = json.loads(OPINION_INDEX.read_text(encoding="utf-8")) if OPINION_INDEX.exists() else {}
    apps = sorted(set(opinion_index) | {p.stem for p in OCR_DIR.glob("*.txt")})

    REASONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    REASONS_REPORT.parent.mkdir(parents=True, exist_ok=True)

    n_apps = n_reasons = n_docs_no_table = 0
    clause_counts: dict[str, int] = {}
    skipped_counts: dict[str, int] = {}
    apps_with_reason = set()

    with REASONS_OUT.open("w") as fh:
        for app in apps:
            rows = extract_rejection_reasons(app, opinion_index)
            for r in rows:
                if "_skipped_clauses" in r:
                    for c in r["_skipped_clauses"]:
                        skipped_counts[c] = skipped_counts.get(c, 0) + 1
                    continue
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                n_reasons += 1
                apps_with_reason.add(app)
                clause_counts[r["clause"]] = clause_counts.get(r["clause"], 0) + 1
            n_apps += 1

    report = {
        "n_applications_scanned": n_apps,
        "n_applications_with_reason": len(apps_with_reason),
        "n_reason_instances": n_reasons,
        "clause_counts": dict(sorted(clause_counts.items(), key=lambda kv: -kv[1])),
        "skipped_unmapped_clause_counts": dict(sorted(skipped_counts.items(), key=lambda kv: -kv[1])),
    }
    REASONS_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {n_apps} 출원 스캔 → {len(apps_with_reason)} 출원 · {n_reasons} RejectionReason 재료 "
          f"→ {REASONS_OUT.name} (미매핑 조항 {sum(skipped_counts.values())}건 → {REASONS_REPORT.name})")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0=전량")
    ap.add_argument("--validate", action="store_true", help="기존 GT 대비 검증만")
    ap.add_argument("--skip-reasons", action="store_true", help="rejection_reasons.jsonl 생성 생략")
    ap.add_argument("--reasons-only", action="store_true", help="rejection_reasons.jsonl 만 생성")
    args = ap.parse_args()

    if args.reasons_only:
        build_reasons()
        return 0

    apps = sorted(p.stem for p in OCR_DIR.glob("*.txt"))
    cache = _conn()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    if args.validate:
        # 기존 GT(evidence_v2 target_claims) 있는 특허에서 청구항 집합 일치율
        gt = {}
        for line in open(REPO / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"):
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

    if not args.skip_reasons:
        build_reasons()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
