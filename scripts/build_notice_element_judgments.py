#!/usr/bin/env python3
"""PLAN-005 단계 2-C — 의견제출통지서 구성 대비표에서 **구조 키**를 채굴한다.

설계 정본 [PLAN-005 §11](../01.code_spec/plans/PLAN-005-prior-art-tool-qualification.md),
관찰 정본 [PLAN-005-stage2c-table-analysis.md](../01.code_spec/reports/PLAN-005-stage2c-table-analysis.md).

    산출  data/patents/notice_element_judgments.parquet
          (출원, 통지서, 표번호, 구성그룹, 구성번호, 캡션청구항, 판정)

**`구성 N-M` 의 앞 숫자는 청구항 번호가 아니다 (2026-09-06 · 3단계 복귀 · 사용자 승인).**
초판 설계는 그것을 `claim_no` 라 불렀다. 실물은 다르다 — 앞 숫자는 **표 단위의 구성 그룹
번호**이고, 청구항 번호는 표 캡션("청구항 3 발명과 인용발명1, 2를 비교해 보면 아래 표2와
같습니다")에 있다. 한 문서에서 `<표2>` 의 `구성 2-1…2-6` 이 전부 **청구항 3** 의 구성인
사례를 실측했다(`1020127009380`).

전수 대조: 캡션과 앞 숫자가 **일치 258(84.6%) · 불일치 9(3.0%) · 캡션 없음 38(12.5%)**.
즉 `claim_no` 라는 이름은 3.0% 에서 거짓이고 12.5% 에서 미검증이었다 — §1-3 위반이며,
그 규칙이 나온 사고(부채 대장 1번, `filing_date` 가 공개일이었던 건)와 같은 양식이다.

그래서 **이름을 사실대로 바꾸고 둘 다 담는다.** `element_group` 은 원문 표기 그대로이고,
`caption_claim_no` 는 캡션에서 온 별개의 값이다(결측 가능). 둘이 다른 9행도 그대로 둔다 —
어느 쪽을 쓸지는 단계 4 가 정한다. 여기서 하나로 뭉개면 그 판단이 사라진다.

**텍스트 열을 담지 않는다 (§11.1).** OCR 이 표의 열 정렬을 무너뜨려 (본원 구성, 인용 개시)
쌍이 조각으로만 남는다 — 실측으로 엄격 규칙이 잡은 305행 중 **142행의 본문이 4자 미만**이다.
조각을 개시 텍스트로 승격하면 이름이 의미와 달라진다(§1-3). 담지 않으므로 이 산출물은
원문 발췌를 갖지 않고, 따라서 공개 파생 경로의 스크럽 대상도 아니다(§1-5).

**LLM 을 쓰지 않는다 (§11.2).** 통지서에는 심사관 실명이 있어 외부 전송이 금지되고
(§1-5), 우리가 뽑는 구조 키 `구성 N-M` 은 숫자와 하이픈뿐이라 OCR 에 강하다.

**느슨한 규칙을 쓰지 않는다.** `<표 N>` 블록 안에서 `구성 N-M` 을 아무 데서나 찾으면 672행이
잡히지만 **45.4%(305행)만 표 행**이고 나머지는 *"…구성 1-4는 인용발명 1의 타깃(3)이…"* 같은
본문 산문이다. 그러므로 **행이 판정으로 끝나는 형태만** 받는다.

결정적이다 — 정렬 순회 · 난수 없음 · 시각 없음. 같은 원천 → 같은 parquet.

    python scripts/build_notice_element_judgments.py
    python scripts/build_notice_element_judgments.py --sample 30   # 주 게이트용 사람 대조 시트
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "data" / "sources" / "opinion_notices" / "txt"
SCOPE = ROOT / "data" / "sources" / "harvest_scope_dev_train.json"
CANON = ROOT / "data" / "patents" / "notice_element_judgments.parquet"
REPORT = ROOT / "data" / "reports" / "notice_element_judgments_report.json"
SAMPLE_CSV = ROOT / "data" / "interim" / "notice_element_judgments_sample.csv"
#: 사람이 채운 시트는 **별도 파일**로 받는다 (2026-09-06 · 사용자 관행을 코드로 고정).
#: `--sample` 은 SAMPLE_CSV 를 덮어쓴다 — 같은 파일에 채우게 하면 재생성 한 번으로 사람의
#: 작업이 지워진다. 실제로 계측기 교정 중 두 번 재생성했다.
RESULT_CSV = ROOT / "data" / "interim" / "notice_element_judgments_sample_result.csv"

#: 결과 시트가 **현재 표본과 같은 행**인지 확인하는 키. 표본이 바뀐 뒤 옛 결과가 게이트를
#: 통과시키면 그것은 게이트가 아니다.
GATE_KEY = ["application_number", "source_file", "table_index", "element_group", "element_no"]

#: `<표 N>` 이 자기 줄에 혼자 있는 형태만 표의 시작으로 본다. 빈 줄에서 닫는다.
TABLE_OPEN = re.compile(r"^\s*<\s*표\s*(\d+)\s*>\s*$")

#: 판정 어휘. **긴 것을 먼저 둔다** — `실질적 동일` 이 `동일` 에 먹히면 라벨이 뭉개진다.
JUDGMENT_ALT = r"실질적\s*동일|주지관용|설계변경|동일|차이|유사|대응"

#: 표 행 — 줄이 `구성 <청구항>-<구성>` 으로 **시작**하고 판정으로 **끝난다**.
#: 가운데 `(.*?)` 는 앵커일 뿐이며 버린다(§11.2).
ROW_RX = re.compile(rf"^\s*구성\s*(\d+)\s*[-–]\s*(\d+)\s+(.*?)\s*({JUDGMENT_ALT})\s*$")

#: 원문 어휘 → 정규화 라벨. 원문도 함께 싣는다(`judgment_raw`) — 정규화가 틀렸을 때
#: 되짚을 수 있어야 하고, 그것이 없으면 이 컬럼은 검증 불가능한 파생값이 된다.
JUDGMENT_LABEL = {
    "동일": "Identical", "실질적동일": "Identical",
    "차이": "Different", "유사": "Similar", "대응": "Corresponding",
    "주지관용": "WellKnown", "설계변경": "DesignChange",
}

#: 표 캡션의 청구항 번호. 표 여는 줄 **앞 5줄 + 블록 안 6줄** 에서 찾는다 — 창을 더
#: 넓혀도 회복이 멈춘다(앞 8줄+안 8줄도 캡션없음 38 로 동일). 즉 남는 12.5% 는 원문에
#: 캡션이 없거나 다른 형태다. 없으면 **비운다**(추측하지 않는다).
CAPTION_RX = re.compile(r"청구항\s*(\d+)\s*발명")
CAPTION_BEFORE, CAPTION_INSIDE = 5, 6

COLUMNS = ["application_number", "source_file", "table_index",
           "element_group", "element_no", "caption_claim_no",
           "judgment_raw", "judgment"]

#: 정렬 키 — 결측이 있는 caption_claim_no 를 넣지 않는다(정렬이 흔들린다).
SORT_KEY = ["application_number", "source_file", "table_index", "element_group", "element_no"]


def normalize_app(value: str) -> str:
    """숫자만 남긴다. 범위 파일과 파일명의 표기 흔들림을 흡수한다."""
    return re.sub(r"\D", "", str(value))


def scope_applications() -> set[str]:
    """누출 통제 범위 — dev+train 800 출원. `test`·`test_b` 는 열지 않는다(§11.4).

    **이 파일을 새로 만들지 않는다.** CR-001B 가 하류 동결 분할에서 파생해 두었고
    자기 출처와 sha256 을 담는다. 누출 규율의 실물은 이것 하나다 —
    `check_leakage.py` 는 이 저장소에 **존재하지 않는다**(PLAN-001 이 이름만 적어 두었다).
    """
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    return {normalize_app(a) for a in scope["application_numbers"]}


def find_caption_claim(lines: list[str], open_at: int) -> int | None:
    """표 캡션이 말하는 청구항 번호. 없으면 None — **앞 숫자로 대신하지 않는다.**"""
    found = None
    for k in range(max(0, open_at - CAPTION_BEFORE), open_at):
        m = CAPTION_RX.search(lines[k])
        if m:
            found = int(m.group(1))          # 가장 가까운 것이 이긴다
    if found is not None:
        return found
    for k in range(open_at + 1, min(len(lines), open_at + 1 + CAPTION_INSIDE)):
        m = CAPTION_RX.search(lines[k])
        if m:
            return int(m.group(1))
    return None


def parse_table_rows(text: str) -> list[dict]:
    """`<표 N>` 블록 안의 표 행만 뽑는다. 블록 밖의 `구성 N-M` 은 본문 산문이다."""
    lines = text.split("\n")
    out: list[dict] = []
    table_index = 0
    caption_claim: int | None = None
    in_table = False
    for i, line in enumerate(lines):
        opened = TABLE_OPEN.match(line)
        if opened:
            in_table = True
            table_index = int(opened.group(1))
            caption_claim = find_caption_claim(lines, i)
            continue
        if in_table and not line.strip():
            in_table = False
            continue
        if not in_table:
            continue
        m = ROW_RX.match(line)
        if not m:
            continue
        raw = m.group(4).strip()
        out.append({"table_index": table_index,
                    "element_group": int(m.group(1)), "element_no": int(m.group(2)),
                    "caption_claim_no": caption_claim,
                    "judgment_raw": raw,
                    "judgment": JUDGMENT_LABEL[re.sub(r"\s+", "", raw)]})
    return out


def build(files: list[Path], scope: set[str]) -> tuple[pd.DataFrame, Counter]:
    rows: list[dict] = []
    stat: Counter = Counter()
    for f in sorted(files):
        app = normalize_app(f.name.split("_")[0])   # 파일명은 `{출원번호}_{발송번호}` (2-A 교정 6)
        stat["문서"] += 1
        parsed = parse_table_rows(f.read_text(encoding="utf-8", errors="replace"))
        if not parsed:
            continue
        stat["표행보유문서"] += 1
        stat["행_전수"] += len(parsed)
        if app not in scope:
            stat["범위밖문서"] += 1
            stat["행_범위밖"] += len(parsed)
            continue
        for r in parsed:
            rows.append({"application_number": app, "source_file": f.name, **r})
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        # 정렬 고정 — 파일 순회 순서에 기대지 않는다(재현성).
        df["caption_claim_no"] = df.caption_claim_no.astype("Int64")   # 결측 보존
        df = df.sort_values(SORT_KEY, kind="stable").reset_index(drop=True)
    return df, stat


#: 시트에 싣는 표 블록의 최대 줄 수. 사람이 읽을 분량으로 자른다.
SAMPLE_BLOCK_LINES = 45


def sample_context(source_file: str, table_index: int, group: int, element: int) -> tuple[str, str]:
    """(캡션 줄, 표 블록 발췌) — 사람이 실제로 대조할 수 있는 최소 문맥.

    **행 한 줄만 주면 대조가 불가능하다 (2026-09-06 · 사용자 지적).** 초판 시트가 그랬고,
    그래서 `구성 2-3` 의 `2` 가 청구항 번호가 아니라는 것을 사람이 볼 수 없었다.

    **블록은 `table_index` 로 고른다. "대상 행을 포함하는 첫 블록"으로 고르면 안 된다
    (2026-09-06 · 계측기 교정 2).** 이 코퍼스에는 **빈 줄이 없는 문서가 있어 블록이 닫히지
    않는다** — 앞 표의 창이 뒤 표의 행을 삼켜, `<표 4>` 의 행에 `<표 3>` 의 캡션이 붙었다.
    실측으로 30행 표본 중 **5행**이 그렇게 어긋난 문맥을 받았고, 검토자는 그 모순을 보고
    전부 `0` 을 찍었다 — **판정이 옳았고 계측기가 틀렸다.** 다섯 행 모두 원문 대조에서
    parquet 값이 맞는 것으로 확인됐다.

    그래서 블록의 끝도 빈 줄에 기대지 않고 **다음 `<표 N>` 표지**로 자른다.
    """
    lines = (TXT_DIR / source_file).read_text(encoding="utf-8", errors="replace").split("\n")
    opens = [(i, int(m.group(1))) for i, ln in enumerate(lines)
             if (m := TABLE_OPEN.match(ln))]
    at = next((i for i, num in opens if num == table_index), None)
    if at is None:
        return "", ""
    nxt = next((i for i, _ in opens if i > at), len(lines))
    end = min(nxt, at + 1 + SAMPLE_BLOCK_LINES)
    block = lines[at:end]
    cap = ""
    for k in range(max(0, at - CAPTION_BEFORE), at):
        if CAPTION_RX.search(lines[k]):
            cap = lines[k].strip()          # 가장 가까운 것이 이긴다 — 파서와 같은 규칙
    return cap, "\n".join(b.strip() for b in block)


def write_sample(df: pd.DataFrame, n: int) -> None:
    """주 게이트(§11.5)용 사람 대조 시트. 시드 고정.

    **원문 발췌를 담는다** — 사람이 대조하려면 필요하다. 그래서 `data/interim/`
    (gitignore · 발행 DENY)에만 쓰고 정본 parquet 에는 넣지 않는다(2-A 선례).
    """
    take = df.sample(n=min(n, len(df)), random_state=20260906).sort_values(SORT_KEY)
    caps, blocks = [], []
    for r in take.itertuples():
        cap, block = sample_context(r.source_file, r.table_index, r.element_group, r.element_no)
        caps.append(cap); blocks.append(block)
    take = take.assign(caption_line=caps, table_block=blocks, correct="", note="")
    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    take.to_csv(SAMPLE_CSV, index=False)
    empty = sum(1 for b in blocks if not b)
    print(f"✓ 사람 대조 시트 {len(take)}행 → {SAMPLE_CSV.relative_to(ROOT)}"
          f"  (`correct` 에 1/0 을 채우고 다시 돌리십시오)")
    if empty:
        print(f"  ⚠ 표 블록을 못 찾은 행 {empty} — 그 행은 대조 불가이므로 확인이 필요하다")


def gate_result() -> dict:
    """주 게이트 — 사람 표본 원문 대조 ≥ 0.90 (§11.5).

    **행 수는 게이트가 아니다.** 305·447 은 설계 시점에 이미 본 수이므로 문턱으로 쓰면
    결과를 보고 문턱을 고르는 것이 된다(§1-2 · 2-A §10.10 에서 같은 실수를 한 번 했다).
    """
    g = {"name": "주 · 사람 표본 원문 대조", "threshold": 0.90}
    src = RESULT_CSV if RESULT_CSV.exists() else SAMPLE_CSV
    if not src.exists():
        return {**g, "status": "미산출 — 이것 없이 2-C 를 완료로 보고하지 않는다"}
    d = pd.read_csv(src)
    g["source"] = str(src.relative_to(ROOT))

    # **옛 결과가 새 표본을 통과시키지 못하게 한다.** 표본이 바뀌었는데 이전 답이 그대로
    # 집계되면 게이트가 재는 것은 지금의 데이터가 아니다.
    if SAMPLE_CSV.exists() and src is RESULT_CSV:
        cur = pd.read_csv(SAMPLE_CSV)
        keys_now = {tuple(r) for r in cur[GATE_KEY].astype(str).itertuples(index=False)}
        keys_res = {tuple(r) for r in d[GATE_KEY].astype(str).itertuples(index=False)}
        if keys_now != keys_res:
            return {**g, "status": "결과 시트가 현재 표본과 다르다 — 다시 대조해야 한다",
                    "sample_rows": len(keys_now), "result_rows": len(keys_res),
                    "only_in_sample": len(keys_now - keys_res),
                    "only_in_result": len(keys_res - keys_now)}

    v = d["correct"].astype(str).str.strip().map({"1": 1, "0": 0}).dropna()
    if v.empty:
        return {**g, "status": "시트는 있으나 미기입"}
    rate = float(v.mean())
    return {**g, "status": "충족" if rate >= 0.90 else "미달",
            "n": int(len(v)), "correct": int(v.sum()), "rate": round(rate, 4),
            # 계측기 교정 이력을 지우지 않는다 (§7 보고 규율 · 2-A 선례).
            "instrument_corrections": [
                {"n": 1, "what": "`구성 N-M` 앞 숫자를 claim_no 라 부른 것을 element_group 으로 개명하고 "
                                 "caption_claim_no 를 분리 (§11.1-a)", "found_by": "사용자 지적"},
                {"n": 2, "what": "대조 시트가 다른 표의 캡션을 보여줬다 — 블록을 table_index 로 고르도록 교정",
                 "found_by": "1차 대조 25/30 의 오답 5건 전량이 이 형태였다",
                 "rate_before_correction": 0.8333},
            ]}


def main() -> int:
    ap = argparse.ArgumentParser(description="통지서 구성 대비표 → 구성요소 판정 채굴")
    ap.add_argument("--sample", type=int, default=0,
                    help="사람 대조 표본 N행을 data/interim/ 에 쓴다 (시드 고정)")
    a = ap.parse_args()

    scope = scope_applications()
    df, stat = build(sorted(TXT_DIR.glob("*.txt")), scope)

    CANON.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CANON, index=False)

    rep = {
        "generated": str(date.today()),
        "plan": "PLAN-005 §11 (단계 2-C)",
        "deterministic": True, "llm_used": False,
        "canonical_artifact": str(CANON.relative_to(ROOT)),
        "note": ("구조 키만 담는다 — 텍스트 열은 OCR 로 무너져 있어 담지 않는다(§11.1). "
                 "그래프에 들어가는 것은 단계 4 이며 별도 승인 대상이다. "
                 "누출 범위는 harvest_scope_dev_train.json 하나이고 check_leakage.py 는 없다."),
        "leakage_scope": {"file": str(SCOPE.relative_to(ROOT)), "applications": len(scope)},
        "documents_scanned": stat["문서"],
        "documents_with_table_rows": stat["표행보유문서"],
        "rows_all": stat["행_전수"],
        "rows_out_of_scope": stat["행_범위밖"],
        "documents_out_of_scope": stat["범위밖문서"],
        "rows": int(len(df)),
        "applications": int(df.application_number.nunique()) if len(df) else 0,
        "element_groups": int(df.groupby(["application_number", "source_file",
                                          "table_index", "element_group"]).ngroups) if len(df) else 0,
        # 캡션 유래 청구항 번호의 회수율과, **앞 숫자와 어긋나는 행 수**. 후자가 이
        # 개정의 이유이므로 리포트에 상시 남긴다 — 다시 뭉개지면 여기서 보인다.
        "caption_claim_resolved": int(df.caption_claim_no.notna().sum()) if len(df) else 0,
        "caption_differs_from_group": int((df.caption_claim_no.notna()
                                           & (df.caption_claim_no != df.element_group)).sum())
                                      if len(df) else 0,
        "judgment_distribution": dict(Counter(df.judgment).most_common()) if len(df) else {},
        # 정규화 전 원문 어휘도 남긴다 — `실질적 동일` 이 `Identical` 로 접히므로,
        # 원문 분포가 없으면 그 접힘이 얼마나 큰지 사후에 알 수 없다(§5 프로파일 의무).
        "judgment_raw_distribution": dict(Counter(df.judgment_raw).most_common()) if len(df) else {},
        "gate": gate_result(),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"✓ {len(df)}행 · 출원 {rep['applications']} · 구성그룹 {rep['element_groups']}"
          f"  → {CANON.relative_to(ROOT)}")
    print(f"  캡션 청구항 회수 {rep['caption_claim_resolved']}/{len(df)}"
          f" · 앞 숫자와 어긋남 {rep['caption_differs_from_group']}")
    print(f"  범위 밖으로 버린 행 {stat['행_범위밖']} (문서 {stat['범위밖문서']}) — 누출 통제")
    print(f"  판정 분포 {rep['judgment_distribution']}")
    print(f"  게이트 {rep['gate']['status']}")

    if a.sample:
        write_sample(df, a.sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
