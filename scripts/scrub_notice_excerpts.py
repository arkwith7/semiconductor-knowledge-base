#!/usr/bin/env python3
"""PLAN-005 R1 — 의견제출통지서의 판단 이유 발췌를 **성명 없이** 만든다 (그래프를 바꾸지 않는다).

왜 필요한가. R1 은 train 출원의 정답 사례를 해부해 T-Box·R-Box·A-Box 의 표현 결손을 찾는다.
해부하려면 심사관이 쓴 이유 문단을 읽어야 하는데, 원천 통지서에는 출원인·대리인·심사관 성명이
있어 그대로는 LLM API 로 보낼 수 없다(CLAUDE.md §1-5). 이 스크립트가 그 사이의 게이트다.

기존 `scrub_rejection_excerpts.py` 와 다르다 — 그쪽은 2026-05 일회성으로 결정서 structured
JSON 의 `excerpt` 키를 지웠다. 같은 이름을 다른 일에 쓰지 않는다(§1-3).

규칙 N1 (결정적 — 같은 원천 → 같은 바이트):
  R1 창     `[구체적인 거절이유]` 부터 처음 `[첨 부]`·`<< 안내 >>`·`특 허 청` 까지.
            표지가 없으면 **추측하지 않고 제외**한다.
  R2 줄삭제 페이지 표지 · 반복 출원번호 줄 · 머리 이름표 줄 · 서명형 줄(역할어 + 한글 2~4자로 끝남).
            성명이 페이지 경계마다 반복되는 자리다(2단계 관찰: 서명형 45줄 중 25줄이 페이지 표지 곁).
  R3 성명   역할어(연쇄 허용) 뒤 공백/콜론 다음의 한글 2~4자 → «성명». 과잉 가림은 감수한다.
  R4 연락처 이메일 · 전화 · 특허고객번호 → «연락처»
  R5 저자   `Kim, H.` · `Smith et al` → «저자»
  잔여 검출 R2~R5 와 **다른 패턴**으로 산출을 다시 훑는다. 걸리면 그 파일을 **고치지 않고 뺀다**.
            가리는 규칙과 검사하는 규칙이 같으면 검사가 아니다.

범위는 train 뿐이다 — 해부가 train 에서만 이루어지므로 dev·봉인 분할의 파생물을 만들지 않는다.
각 산출 줄은 `L<원문 줄번호>\\t<본문>` 이다. 줄번호가 해부의 원문 좌표다.
매니페스트에는 원문을 싣지 않는다(sha256 · 건수 · 제외 사유뿐).

사용
  make scrub-notices
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splits  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
TXT_DIR = SOURCES / "opinion_notices" / "txt"
INDEX = SOURCES / "opinion_notices" / "_index.json"
MANIFEST = SOURCES / "MANIFEST.json"
OUT_DIR = SOURCES / "notice_excerpts_scrubbed"

RULE_VERSION = "N1"
SCOPE = "train"
REVIEW_N = 20
REVIEW_SEED = 20260914

# ── R1 창 ──
START = re.compile(r"^\[구체적인\s*거절이유\]")
END = re.compile(r"^(\[첨\s*부\]|<<\s*안내\s*>>|특\s*허\s*청$)")

ROLE = r"(?:출원인|대리인|심사관보|심사관|심사장|담당자|담당|파트장|과장|팀장|국장|변리사|발명자|대표자)"

# ── R2 줄 삭제 ──
DROP_LINE = {
    "page_marker": re.compile(r"^(-\s*\d+\s*-|\d+\s*/\s*\d+)$"),
    "app_number_line": re.compile(r"^\d{2}-\d{4}-\d{7}$"),
    "header_label": re.compile(
        r"^(발송번호|발송일자|수\s*신\s*[:：]|주\s+소|출\s+원\s+번\s+호|출\s+원\s+인|대\s+리\s+인"
        r"|특허고객번호|\(?\s*특허고객번호|(출원인|대리인)\s*(성명|명칭|\())"
    ),
    "signature": re.compile(rf"(^|\s){ROLE}\s+[가-힣]{{2,4}}\s*$"),
}

# ── R3–R5 치환 ──
NAME_AFTER_ROLE = re.compile(
    rf"({ROLE}(?:\s+{ROLE})*)(\s*[:：]\s*|\s+)([가-힣]{{2,4}})(?=$|[\s,.)\]·ㆍ(])"
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\d)0\d{1,2}[-)\s.]\d{3,4}[-\s.]\d{4}(?!\d)")
CUSTOMER_NO = re.compile(r"(특허고객번호\s*[:：]?\s*)[\d-]{9,}")
LATIN_INITIAL = re.compile(r"\b[A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)*")
#: 이니셜을 포함한 전체를 먼저 가린다 — `Kim, H. et al.` 에서 이니셜만 먼저 가리면 `et al` 이
#: 주인 없이 남아 잔여 검출에 걸린다(5단계 전 테스트가 드러냈다).
LATIN_ETAL = re.compile(r"\b[A-Z][a-z]+(?:,\s*[A-Z]\.(?:\s*[A-Z]\.)*)?\s+et\s+al\b\.?")

MASK_NAME, MASK_CONTACT, MASK_AUTHOR = "«성명»", "«연락처»", "«저자»"

# ── 잔여 검출 (치환 규칙과 일부러 다른 패턴) ──
RESIDUAL = {
    "role_paren_name": re.compile(rf"{ROLE}\s*[(\[]\s*[가-힣]{{2,4}}\s*[)\]]"),
    "role_glued_name_eol": re.compile(rf"{ROLE}[가-힣]{{2,4}}\s*$"),
    "role_name_eol": re.compile(rf"{ROLE}\s*[:：]?\s*[가-힣]{{2,4}}\s*$"),
    "name_label": re.compile(r"(성\s*명|명\s*칭|귀\s*하)\s*[:：]?\s*[가-힣]{2,4}"),
    "at_sign": re.compile(r"@"),
    "phone_like": re.compile(r"(?<!\d)\d{2,3}-\d{3,4}-\d{4}(?!\d)"),
    "latin_etal": re.compile(r"\bet\s*al\b"),
    "latin_initial": re.compile(r"[A-Z][a-z]+,\s?[A-Z]\."),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def source_sha_table(manifest_path: Path = MANIFEST) -> dict[str, str]:
    """원천 매니페스트의 통지서 txt sha256 — 원천 무결성의 기준."""
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    files = m["dirs"]["opinion_notices/txt"]["files"]
    return {name: meta["sha256"] for name, meta in files.items()}


def scope_documents(split_map: dict[str, str], index: dict) -> list[tuple[str, str]]:
    """train 출원의 통지서 (출원번호, 파일 stem). 다른 분할은 아예 돌려주지 않는다.

    색인이 같은 파일을 두 번 적는 출원이 있다(실측 1건) — 파일 단위로 한 번만 센다.
    그러지 않으면 매니페스트의 산출 수가 디렉터리의 파일 수보다 커진다.
    """
    out, seen = [], set()
    for doc_id, s in sorted(split_map.items()):
        if s != SCOPE:
            continue
        app = doc_id[len("kr_"):] if doc_id.startswith("kr_") else doc_id
        for d in index.get(app, {}).get("docs", []):
            if d["file"] in seen:
                continue
            seen.add(d["file"])
            out.append((app, d["file"]))
    return out


def find_window(lines: list[str]) -> tuple[int, int] | None:
    """(시작 표지 줄 index, 끝 표지 줄 index). 둘 중 하나라도 없으면 None."""
    start = next((i for i, l in enumerate(lines) if START.search(l.strip())), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if END.search(lines[i].strip())), None)
    if end is None:
        return None
    return start, end


def scrub_line(text: str) -> tuple[str | None, Counter]:
    """한 줄 → (가린 줄 | 삭제면 None, 규칙별 건수)."""
    c: Counter = Counter()
    for rule, pat in DROP_LINE.items():
        if pat.search(text):
            c[f"R2_{rule}"] += 1
            return None, c

    def _name(m: re.Match) -> str:
        c["R3_name"] += 1
        return f"{m.group(1)}{m.group(2)}{MASK_NAME}"

    text = NAME_AFTER_ROLE.sub(_name, text)
    for rule, pat, repl in (
        ("R4_email", EMAIL, MASK_CONTACT),
        ("R4_phone", PHONE, MASK_CONTACT),
        ("R5_latin_etal", LATIN_ETAL, MASK_AUTHOR),
        ("R5_latin_initial", LATIN_INITIAL, MASK_AUTHOR),
    ):
        text, n = pat.subn(repl, text)
        c[rule] += n
    text, n = CUSTOMER_NO.subn(lambda m: m.group(1) + MASK_CONTACT, text)
    c["R4_customer_no"] += n
    return text, +c


def residual_hits(text: str) -> list[str]:
    """가린 뒤에도 남은 개인정보 모양 — 규칙 이름만 돌려준다(값은 돌려주지 않는다)."""
    cleaned = text.replace(MASK_NAME, "").replace(MASK_CONTACT, "").replace(MASK_AUTHOR, "")
    return [rule for rule, pat in RESIDUAL.items() if pat.search(cleaned)]


def scrub_document(raw: str) -> tuple[list[tuple[int, str]] | None, Counter, str | None]:
    """원문 → ([(원문 줄번호 1-base, 가린 줄)] | None, 규칙 건수, 제외 사유 | None)."""
    lines = raw.split("\n")
    win = find_window(lines)
    if win is None:
        return None, Counter(), "no_window"
    start, end = win
    out: list[tuple[int, str]] = []
    counts: Counter = Counter()
    residual: Counter = Counter()
    for i in range(start + 1, end):
        t = lines[i].strip()
        if not t:
            continue
        scrubbed, c = scrub_line(t)
        counts.update(c)
        if scrubbed is None:
            continue
        residual.update(residual_hits(scrubbed))
        out.append((i + 1, scrubbed))
    if residual:
        counts.update({f"residual_{k}": v for k, v in residual.items()})
        return None, counts, "residual:" + ",".join(sorted(residual))
    if not out:
        return None, counts, "empty_window"
    return out, counts, None


def render(rows: list[tuple[int, str]]) -> bytes:
    return ("".join(f"L{n:04d}\t{t}\n" for n, t in rows)).encode("utf-8")


def run(out_dir: Path = OUT_DIR, *, split_path: Path = splits.SPLIT_CSV,
        index_path: Path = INDEX, txt_dir: Path = TXT_DIR,
        manifest_path: Path = MANIFEST, verify_split: bool = True) -> dict:
    split_map = splits.load_split(split_path, verify=verify_split)
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    shas = source_sha_table(manifest_path)
    docs = scope_documents(split_map, index)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.txt"):
        stale.unlink()

    totals: Counter = Counter()
    excluded: Counter = Counter()
    files: list[dict] = []
    for app, stem in docs:
        name = f"{stem}.txt"
        raw_b = (Path(txt_dir) / name).read_bytes()
        got = sha256_bytes(raw_b)
        if shas.get(name) != got:
            raise SystemExit(f"ERROR: 원천 sha256 이 매니페스트와 다르다: {name}")
        rows, counts, reason = scrub_document(raw_b.decode("utf-8"))
        totals.update(counts)
        entry = {"application": app, "source": name, "source_sha256": got}
        if reason is not None:
            excluded[reason.split(":")[0]] += 1
            entry["excluded"] = reason
        else:
            body = render(rows)
            (out_dir / name).write_bytes(body)
            entry.update(output=name, output_sha256=sha256_bytes(body), lines=len(rows))
        files.append(entry)

    produced = sorted(e["output"] for e in files if "output" in e)
    # 범위 계약의 마지막 확인 — train 이 아닌 출원이 산출에 있으면 죽는다.
    train_apps = {d[len("kr_"):] for d, s in split_map.items() if s == SCOPE}
    leaked = sorted({e["application"] for e in files if "output" in e} - train_apps)
    if leaked:
        raise SystemExit(f"ERROR: train 밖 출원이 산출에 있다: {len(leaked)}건")

    review = sorted(random.Random(REVIEW_SEED).sample(produced, min(REVIEW_N, len(produced))))
    manifest = {
        "rule_version": RULE_VERSION,
        "scope": SCOPE,
        "split_sha256": splits.sha256_of(split_path),
        "documents_in_scope": len(docs),
        "produced": len(produced),
        "excluded": dict(sorted(excluded.items())),
        "rule_counts": dict(sorted(totals.items())),
        "human_review_sample": review,
        "pii": "성명·연락처·저자명을 가렸으나 사람 확인 전에는 LLM 에 보내지 않는다(§1-5)",
        "files": files,
    }
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    m = run(a.out)
    print(f"[scrub-notices] 규칙 {m['rule_version']} · 범위 {m['scope']} · "
          f"문서 {m['documents_in_scope']} → 산출 {m['produced']} · 제외 {m['excluded']}")
    print(f"[scrub-notices] 규칙 건수 {m['rule_counts']}")
    print(f"[scrub-notices] 사람 확인 표본 {len(m['human_review_sample'])}건 — 경로만 적는다:")
    for p in m["human_review_sample"]:
        print(f"  {a.out / p}")


if __name__ == "__main__":
    main()
