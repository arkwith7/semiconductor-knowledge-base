#!/usr/bin/env python3
"""공개본 트리 생성기 — KIPRIS 원문을 뺀 릴리스 트리를 만든다 (CR-015 출력 (1)·(1-b)·(4)).

**왜 생성기인가.** 원고 §10.3 은 *"KIPRIS 원문은 재배포할 수 없다"* 고 쓰는데 이 저장소는
초록·청구항 전문 1,000건을 커밋하고 있(었)다. 두 문장이 같은 것을 가리키며 서로 반대다.
손으로 지우면 다음에 또 어긋나므로, **공개할 트리를 매번 코드가 만든다.**

만드는 것:
  1. `data/patents/raw/…rejected_patents.jsonl` — abstract · claim1 · claims_full[].text 를
     **빈 문자열로** 둔다. **키는 지우지 않는다** — 스키마·claim_no·depends_on 은 서지
     구조이고, `ingest_rejected_patents.py:216-259` 가 항수와 보유 플래그를 읽는다.
     `title` 은 남긴다(서지이며 이미 `kipris_biblio.parquet` 에 커밋돼 있다).
  2. 노트북 셀 출력 제거 — 07 의 출력 하나가 초록 발췌를 인쇄한다. 같은 정책이 이미
     노트북 08 에 적용된 전례가 있다.
  3. **첫 줄이 `<!-- sdkb:private -->` 인 문서는 복사하지 않는다**(R1). 뺀 목록은 manifest 에
     적는다 — 조용히 0 이 되면 경계가 없는 것과 같다.
  4. 실행 리포트·거절결정 인덱스의 **홈 절대경로를 파일명으로 줄인다**. 공개본에 남의 홈
     경로가 박혀 있으면 외부인에게는 그냥 깨진 참조다.
  5. **허용목록에 있는 것만 복사한다** (2026-08-10 전환). 예전에는 반대였다 — 전량을
     복사한 뒤 몇 가지를 뺐고, 그 근거는 *"조용히 빠지는 쪽보다 조용히 들어오는 쪽이
     검사기에 걸린다"* 였다. 그 전제가 바뀌었다: 공개는 **되돌릴 수 없고**, 조용히
     들어온 것을 검사기가 잡아 주는 것은 **이미 늦은 뒤**다. 이제 모르는 파일은
     공개되지 않는다. 필요하면 `ALLOW_*` 에 한 줄을 더한다.
  6. 공개본에 **없는 파일을 가리키는 상대 링크는 평문으로 푼다.** 허용목록은 파일을
     빼 주지만 그 파일을 가리키던 문장은 빼 주지 않는다.

만들지 않는 것: 공개 리포에 푸시하지 않는다. 이 스크립트는 트리까지만 만들고, orphan
커밋과 푸시는 사람이 검사기 통과를 확인한 뒤에 한다 — **되돌릴 수 없는 단계는 자동화하지
않는다.**

CLI:
    python scripts/build_public_release.py --out /tmp/sdkb-public
    python scripts/build_public_release.py --out /tmp/sdkb-public --rev 212fe62
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_REL = "data/patents/raw/semiconductor_industry_rejected_patents.jsonl"

# ═══════════════════════════════════════════════════════════════════
# 공개 허용목록 (2026-08-10 · 사용자 결정)
#
# **목록의 방향을 뒤집었다.** 예전에는 추적 파일 전량을 복사한 뒤 넷을 뺐다. 이제는
# 아래에 있는 것만 복사한다. 이유는 비대칭이다 — 뺐다가 넣는 것은 릴리스 한 번이고,
# 올렸다가 빼는 것은 불가능하다(포크·캐시·PR ref). 그래서 **새로 생긴 파일은 기본적으로
# 공개되지 않는다.** 필요하면 여기 한 줄을 더한다.
#
# 대원칙: 엄격·최소. `~/Dev/sdkb` 는 유지되므로 나중에 다시 올릴 수 있다.
# ═══════════════════════════════════════════════════════════════════

# 통째로 공개하는 디렉터리 (아래 DENY 로 구멍을 낸다)
ALLOW_PREFIXES = (
    "ontology/",        # T-Box + import
    "data/",            # 어휘·큐레이션 원천 (DENY 로 일부 제외)
    "scripts/",         # 생성기·재현 사슬 (DENY 로 일부 제외)
    "queries/cq/",      # CQ 스위트 — 이 온톨로지가 무엇을 답하는가
    "validation/",      # SHACL — 하류와의 구조 계약
    "mappings/",        # 개념 매핑·외부 정렬
    "provenance/",      # PROV-O
    "config/",          # 네임스페이스·IRI 정책
    "examples/",        # 예제 질의
    "tests/",           # 게이트가 실제로 돈다는 증거
    # 평가 하네스 — 논문 §4 표가 코드 진입점을 적으므로 그 파일이 실재해야 표가
    # 검증 가능한 주장이 된다. **이 디렉터리는 논문 리포가 생성해 적재한다** —
    # 여기서 편집하면 사본이 갈린다(D-38 이 그 실패다).
    "benchmark/",
)

# 개별로 공개하는 루트 파일
ALLOW_FILES = {
    "README.md", "README.ko.md", "CHANGELOG.md", "CITATION.cff", "LICENSE.txt",
    "LICENSE-CODE.txt", ".zenodo.json",
    "Makefile", "pyproject.toml", "uv.lock", ".gitignore",
}

# 공개하는 문서 11건. **docs/ 는 접두사 허용이 아니라 파일 열거다** — 이 디렉터리가
# 스펙과 작업기록을 함께 담아서, 접두사로 열면 다음에 쓰는 계획 문서가 조용히 따라 나간다.
ALLOW_DOCS = {
    "docs/README.md",                                       # 색인
    "docs/ontology_guide.md",                               # 스펙 본체
    "docs/glossary_ontology.md",
    "docs/glossary_semiconductor.md",
    "docs/datasheet.md",                                    # 산출물 명세(Gebru)
    "docs/deidentification_protocol.md",                    # 큐레이션 방법
    "docs/semiconductor_ontology_provenance_research.md",   # 외부 원천 근거
    "docs/dataset_rejected_patents_card.md",
    "docs/semiconductor_industry_rejected_patents_schema.md",
    "docs/kipris_reject_dataset_source_mapping.md",
    # 발행되는 그래프의 rdfs:seeAlso 가 가리킨다. 빼면 공개 첫날 죽은 링크가 된다.
    "docs/project/architecture_amendment_sdkb_centric.md",
}

# 허용 접두사 안에 내는 구멍. 사유는 옆에 적는다 — 목록만 있고 이유가 없으면
# 다음 사람이 되돌린다.
DENY_PREFIXES = (
    # 수집은 paper_data, A-Box 생성은 논문 리포가 전담했다. 여기 남은 것은 초기 일부다.
    "data/patents/rejection_decisions/",
    # ── 원천 계층 (2026-08-23 · CLAUDE.md §1-5 개정 · 사용자 승인)
    # 의견제출통지서·거절결정서·인용문헌 전문의 **원문**이 산다. 이 저장소가 비공개로
    # 확정되어 원문을 보존하기로 했고(구 규약은 보관 자체를 금지처럼 읽혔다), 그래서
    # **공개 경계가 저장소에서 이 한 줄로 옮겨 왔다.**
    # 두 가지 이유로 절대 공개하지 않는다 —
    #   ① KIPRIS 학술이용·비재배포 조건 (§1-5)
    #   ② 출원인·대리인·심사관 **실명**이 사실상 전 문서에 있다 (하류 D-46 §6.5 실측)
    # pdf 는 .gitignore 로도 막히지만 txt·structured 는 **git 에 추적되므로**
    # `git ls-files` 를 읽는 이 생성기에는 이 DENY 가 유일한 방어선이다.
    "data/sources/",
    # ── 평가 질의 세트 (2026-09-05 · PLAN-005 §5 V4)
    # `data/queries/v4/` 는 거절특허 **청구항 원문**(variant=claim)·**초록**(abstract)과
    # 그것을 LLM 으로 다시 쓴 의역문을 담는다. 원문은 KIPRIS 수집물이므로 §1-5 재배포
    # 금지에 걸리고, 의역문은 그 원문에서 파생된 것이라 같은 조건을 물려받는다.
    # **`data/` 가 통째로 ALLOW 이므로, 이 한 줄이 없으면 그대로 발행된다.**
    # 새 평가 자산을 `data/` 아래 새 디렉터리로 만들 때는 여기부터 확인할 것.
    "data/queries/",
    # ── 작업 캐시·코딩 시트 (2026-09-06 · PLAN-005 §5 V4-2)
    # `data/interim/` 은 LLM 캐시와 **사람 코딩 시트**가 사는 곳이고, 시트는 청구항 원문과
    # arXiv 초록을 그대로 담는다. `.gitignore` 로도 막히지만 **이중으로 막는다** —
    # 위 `data/sources/` 와 같은 이유다: 누군가 한 파일이라도 추적하는 순간
    # `git ls-files` 를 읽는 이 생성기에는 DENY 만이 방어선이 된다.
    "data/interim/",
)

DENY_FILES = {
    # ── 통지서 유래 거절근거 정본 (2026-09-06 · PLAN-005 §10 · 사용자 결정)
    # 원문이 아니라 파생 구조((출원, 인용문헌, 근거, 절, 청구항))라 §1-5 재배포 금지에는
    # 걸리지 않는다. 그럼에도 발행하지 않기로 했다 — **어느 인용문헌이 어느 조항으로
    # 걸렸는가**는 심사 판단의 세부이고, 한 번 발행하면 회수가 어렵다.
    # 재현성은 생성기가 진다: `scripts/build_notice_evidence.py` 는 발행되고 결정적이므로,
    # 원문을 가진 사람은 동일 산출을 다시 만들 수 있다.
    "data/patents/notice_legal_basis.parquet",
    # ── 일회성 백필·정정 (한 번 돌고 끝난 코드)
    "scripts/backfill_admin_docs.py",
    "scripts/backfill_pdfinfo_v2.py",
    "scripts/apply_phase_c_to_canonical.py",
    "scripts/merge_legacy_etch_into_semiconductor_dataset.py",
    "scripts/reassign_expert_names.py",
    "scripts/scrub_rejection_excerpts.py",
    "scripts/sanitize_expert_provenance.py",
    "scripts/expand_dataset_via_api.py",
    # ── 산출물이 공개되지 않는 생성기 (아무도 돌릴 수 없다)
    "scripts/build_rejection_decisions.py",
    "scripts/reextract_claim_judgments.py",
    # ── 평가·진단 (데이터셋이 아니라 실험의 산출)
    "scripts/eval_explanation_precision.py",
    "scripts/eval_prior_art_realgt.py",
    "scripts/report_unresolved_gt.py",
    "data/reports/explanation_precision_report.json",
    "data/reports/prior_art_realgt_report.json",
    "data/reports/rejection_reasons_loss.json",
    # ── 시각화 (Pages 배포와 함께 뺀다)
    "scripts/build_viz.py",
    # `scripts/sdkb_nb.py` 는 **빼지 않는다.** 이름이 노트북 헬퍼처럼 보여서 제외했다가
    # 공개 트리에서 테스트 10개가 ModuleNotFoundError 로 죽었다 — tests/ 셋이 임포트한다.
    # 이름이 아니라 **누가 쓰는가**로 판단한다.
    #
    # ── 청구항 한정요소 투영 (CR-017) — 2026-08-15 사용자 결정으로 **공개하지 않는다**
    # 원문은 0열이므로 CR-015 의 (B) Link-Only 와 충돌하지는 않는다. 그럼에도 빼는 이유는
    # **범주가 다르기 때문**이다 — 이 파일은 KIPRIS 청구항을 분해한 **구조 1,306,191행**이고,
    # 지금까지 공개 대상으로 합의된 것은 어휘·T-Box·shape·CQ·메타였다. 새 범주를 접두사 허용
    # (`mappings/`)에 묻어 조용히 내보내지 않는다.
    # **메타(`claim_feature_release_meta.json`)는 남긴다** — 개념별 df 와 커버리지 집계뿐이라
    # 행 단위 구조가 없고, 이 리포가 이미 공개하는 다른 통계 보고서와 같은 성격이다.
    "mappings/claim_features.parquet",
}

# 텍스트 파일에서 이 두 줄 사이는 공개본에서 지운다. Makefile 의 viz 타깃처럼
# **제외한 스크립트를 부르는 조각**을 지우기 위한 것이다 — 부를 수 없는 타깃을 남기면
# 공개본은 "돌지 않는 명령을 가진 리포"가 된다.
BLOCK_BEGIN = "sdkb:private-begin"
BLOCK_END = "sdkb:private-end"

# 원문을 담는 필드. title 은 여기 없다 — 서지다.
TEXT_FIELDS = ("abstract", "claim1")

# 비공개 선언 토큰 (R1). **첫 줄에서만** 인정한다 — 본문에서 이 토큰을 언급하는 문서는
# 토큰을 *설명*하는 것이지 *선언*하는 것이 아니다. 실제로 그런 문서가 이미 있다
# (`docs/public_release_readiness_review.md:53` — 이 규약을 제안한 문서 자신).
#
# 자연어 마커(CONFIDENTIAL·proprietary…)를 쓰지 않는 이유: 추적 파일 7건이 걸리는데
# **전부 정상 문서**였다. 기밀을 담은 문서와 기밀을 논하는 문서를 가르지 못하는 검사기는
# 무시되고, 무시되는 검사기는 없는 것과 같다.
PRIVATE_TOKEN = "<!-- sdkb:private -->"

# 파일시스템 절대경로만 잡는다. URL 안의 `/home/` 은 앞에 `/` 나 문자가 있어 걸리지 않는다 —
# 실측으로 둘 있었다(irds.ieee.org/home/… · horiba.com/kr/horiba-stec/home/).
_ABS_PATH = re.compile(r'(?<![\w./-])/(?:home|Users)/[^\s"\'`,)\]}]+')

INDEX_REL = "data/patents/rejection_decisions/_index.jsonl"


def wants_abs_scrub(rel: str) -> bool:
    """스크럽 대상. **전 파일에 걸지 않는다** — 넓히면 위 오탐을 다시 만든다.

    둘뿐이다: 실행 리포트(호출 인자를 그대로 적는다)와 거절결정 인덱스(과거 실행이 남긴
    `pdf_path` 잔재 11행. 생성기는 이미 상대경로로 쓴다 — 원본 정규화는 F8 로 분리했다).

    셋째는 하네스 평가 자산이다 — 결함행렬 JSON 이 격리 산출물의 **실행 경로**를 값이
    아니라 흔적으로 담고 있고(실측 218건), 그 흔적이 이 저장소의 옛 이름을 노출한다.
    """
    return (rel == INDEX_REL
            or (rel.startswith("data/reports/") and rel.endswith(".json"))
            or rel.startswith("benchmark/assets/"))


def is_private_doc(raw: bytes) -> bool:
    """첫 줄이 비공개 토큰인가. 둘째 줄부터는 보지 않는다."""
    head = raw[:512].decode("utf-8", errors="ignore").splitlines()
    return bool(head) and head[0].strip() == PRIVATE_TOKEN


def scrub_abs_paths(raw: bytes) -> tuple[bytes, int]:
    """홈 절대경로를 **파일명만** 남긴다. 경로를 지우는 것이지 사실을 지우는 것이 아니다 —
    어떤 파일을 읽었는지는 남는다."""
    txt = raw.decode("utf-8", errors="ignore")
    n = 0

    def _repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return m.group(0).rsplit("/", 1)[-1]

    out = _ABS_PATH.sub(_repl, txt)
    return (out.encode("utf-8"), n) if n else (raw, 0)


def tracked_files(rev: str | None) -> list[str]:
    cmd = ["git", "ls-tree", "-r", "--name-only", rev] if rev else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def read_blob(rel: str, rev: str | None) -> bytes:
    if rev:
        return subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT,
                              capture_output=True, check=True).stdout
    return (ROOT / rel).read_bytes()


def scrub_dataset(raw: bytes) -> tuple[bytes, dict]:
    """원문 세 필드를 비운다. 스키마·키·항수는 건드리지 않는다."""
    stats = {"rows": 0, "abstract": 0, "claim1": 0, "claims_full_texts": 0}
    lines = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        tp = rec.get("target_patent") or {}
        stats["rows"] += 1
        for f in TEXT_FIELDS:
            if (tp.get(f) or "").strip():
                tp[f] = ""
                stats[f] += 1
        for c in (tp.get("claims_full") or []):
            if (c.get("text") or "").strip():
                c["text"] = ""
                stats["claims_full_texts"] += 1
        # ensure_ascii=False 왕복이 원본과 바이트 동일함을 확인하고 고른 직렬화다.
        lines.append(json.dumps(rec, ensure_ascii=False))
    return ("\n".join(lines) + "\n").encode("utf-8"), stats


def strip_notebook(raw: bytes) -> tuple[bytes, int]:
    nb = json.loads(raw.decode("utf-8"))
    n = 0
    for cell in nb.get("cells", []):
        if cell.get("outputs"):
            cell["outputs"] = []
            n += 1
        if "execution_count" in cell:
            cell["execution_count"] = None
    return (json.dumps(nb, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), n


def is_allowed(rel: str) -> bool:
    """허용목록에 있는가. **모르는 파일은 공개하지 않는다** — 그것이 뒤집은 이유다."""
    if rel in DENY_FILES or any(rel.startswith(p) for p in DENY_PREFIXES):
        return False
    if rel in ALLOW_FILES or rel in ALLOW_DOCS:
        return True
    if rel.startswith("docs/"):
        return False          # docs 는 접두사 허용이 아니라 파일 열거다
    return any(rel.startswith(p) for p in ALLOW_PREFIXES)


def _marker(line: str, token: str) -> bool:
    """마커는 **자기 줄에 혼자** 있어야 한다 (주석 기호와 공백만 허용).

    포함(`in`) 검사로 만들면 마커를 *설명하는* 줄이 마커가 된다 — 이 파일의 docstring 이
    바로 그랬고, 첫 실행에서 빌드가 "닫히지 않은 블록"으로 죽었다. `PRIVATE_TOKEN` 을
    첫 줄에서만 인정한 것과 같은 이유다: 선언과 언급을 가르지 못하는 규약은 사고를 낸다.
    """
    s = line.strip()
    if s.startswith("<!--") and s.endswith("-->"):     # 마크다운
        s = s[4:-3]
    return s.lstrip("#;/ \t").strip() == token         # Makefile·파이썬·YAML


def strip_private_blocks(raw: bytes, rel: str = "?") -> tuple[bytes, int]:
    """`sdkb:private-begin` … `sdkb:private-end` 사이를 지운다 (마커 줄 포함).

    닫히지 않은 블록은 **조용히 넘기지 않는다** — 파일 끝까지 지워 버리면 그 사실이
    아무에게도 보이지 않는다. 예외를 던져 빌드를 세운다.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw, 0
    if BLOCK_BEGIN not in text:
        return raw, 0
    out, depth, dropped = [], 0, 0
    for line in text.splitlines(keepends=True):
        if _marker(line, BLOCK_BEGIN):
            depth += 1
            dropped += 1
            continue
        if _marker(line, BLOCK_END):
            if depth == 0:
                raise ValueError(f"{rel}: {BLOCK_END} 가 열린 블록 없이 나왔다")
            depth -= 1
            dropped += 1
            continue
        if depth:
            dropped += 1
            continue
        out.append(line)
    if depth:
        raise ValueError(f"{rel}: {BLOCK_BEGIN} 가 닫히지 않았다 — 파일 끝까지 지워질 뻔했다")
    return "".join(out).encode("utf-8"), dropped


_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def flatten_dead_links(raw: bytes, rel: str, published: set[str]) -> tuple[bytes, int]:
    """공개본에 **없는 파일**을 가리키는 상대 링크를 링크 표시만 벗겨 평문으로 만든다.

    지우는 것이 아니라 **푸는 것**이다 — 문장은 그대로 읽히고 클릭만 사라진다. 상류
    저장소의 원본은 손대지 않는다: 거기서는 그 링크가 살아 있고 살아 있어야 한다.
    공개본은 파생물이며, 파생물에서만 푼다.

    이것이 없으면 허용목록 전환은 **죽은 링크 60개짜리 리포**를 만든다(실측). 목록은
    파일을 빼 주지만 그 파일을 가리키던 문장은 빼 주지 않는다.
    """
    if not rel.endswith(".md"):
        return raw, 0
    text = raw.decode("utf-8", errors="ignore")
    base = Path(rel).parent
    n = 0

    def _published(target: str) -> bool:
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return True
        path = target.split("#", 1)[0]
        if not path:
            return True
        key = os.path.normpath(str(base / path)) if str(base) != "." else os.path.normpath(path)
        return key in published or any(k.startswith(key.rstrip("/") + "/") for k in published)

    # 표의 **행 하나가 통째로** 없는 문서를 소개하면 링크만 푸는 것으로는 부족하다 —
    # 색인이 있지도 않은 문서를 안내하게 된다. 행은 자기완결적이므로 통째로 뺀다.
    # 산문 안의 링크는 문장을 깨뜨리므로 여기서 빼지 않고 아래에서 풀기만 한다.
    kept_lines = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("|"):
            links = [t for _, t in _MD_LINK.findall(line)]
            if links and not any(_published(t) for t in links):
                n += len(links)
                continue
        kept_lines.append(line)
    text = "".join(kept_lines)

    def _repl(m: re.Match) -> str:
        nonlocal n
        label, target = m.group(1), m.group(2)
        if _published(target):
            return m.group(0)
        n += 1
        return label

    out = _MD_LINK.sub(_repl, text)
    return (out.encode("utf-8"), n) if n else (raw, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="공개 트리를 쓸 빈 디렉터리")
    ap.add_argument("--rev", default=None,
                    help="기준 커밋(기본: 현재 워킹트리의 추적 파일)")
    ap.add_argument("--force", action="store_true", help="--out 이 비어 있지 않아도 덮어쓴다")
    args = ap.parse_args()

    out: Path = args.out
    if out.exists() and any(out.iterdir()) and not args.force:
        raise SystemExit(f"ERROR: {out} 가 비어 있지 않다. --force 를 주거나 다른 경로를 쓴다.")
    if out.exists() and args.force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    files = tracked_files(args.rev)
    # 두 벌 돈다 — 링크를 풀려면 **무엇이 공개되는지 먼저 알아야** 한다.
    published = {rel for rel in files if is_allowed(rel)}
    published.add("data/reports/public_release_manifest.json")
    scrub_stats, nb_stripped, copied = {}, {}, 0
    links_flattened: dict[str, int] = {}
    private_excluded: list[str] = []
    not_allowed: list[str] = []
    blocks_stripped: dict[str, int] = {}
    abs_scrubbed: dict[str, int] = {}
    for rel in files:
        if not is_allowed(rel):
            not_allowed.append(rel)
            continue
        raw = read_blob(rel, args.rev)
        if is_private_doc(raw):
            private_excluded.append(rel)      # 복사하지 않는다
            continue
        raw, nblock = strip_private_blocks(raw, rel)
        if nblock:
            blocks_stripped[rel] = nblock
        raw, nlink = flatten_dead_links(raw, rel, published)
        if nlink:
            links_flattened[rel] = nlink
        if rel == DATASET_REL:
            raw, scrub_stats = scrub_dataset(raw)
        elif rel.endswith(".ipynb"):
            raw, n = strip_notebook(raw)
            if n:
                nb_stripped[rel] = n
        if wants_abs_scrub(rel):
            raw, n = scrub_abs_paths(raw)
            if n:
                abs_scrubbed[rel] = n
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
        copied += 1

    from collections import Counter
    by_dir = Counter(r.split("/")[0] if "/" in r else "(root)" for r in not_allowed)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rev": args.rev or "working-tree",
        "files": copied,
        "dataset_scrub": scrub_stats,
        # 뺀 목록을 남긴다 — 수가 조용히 0 이 되는 것을 막는 유일한 장치다.
        "private_docs_excluded": sorted(private_excluded),
        # **경로 목록은 싣지 않는다 — 건수만 싣는다.** 전체 목록은 공개할 필요가 없는
        # 비공개 리포의 파일 인벤토리다. 감사에 필요한 것은 "얼마나 빠졌는가"이고,
        # "무엇이 빠졌는가"는 상류에서 본다(아래 full 매니페스트).
        "not_allowlisted_count": len(not_allowed),
        "not_allowlisted_by_dir": dict(sorted(by_dir.items())),
        "private_blocks_stripped": blocks_stripped,
        "dead_links_flattened": links_flattened,
        "absolute_paths_scrubbed": abs_scrubbed,
        "notebook_outputs_stripped": nb_stripped,
    }
    (out / "data" / "reports").mkdir(parents=True, exist_ok=True)
    (out / "data" / "reports" / "public_release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 전체 제외 목록은 **트리 밖**에 쓴다. 감사에는 필요하고 공개에는 불필요하다.
    full = out.parent / f"{out.name}_manifest_full.json"
    full.write_text(json.dumps(
        {**manifest, "not_allowlisted": sorted(not_allowed)},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[public] {copied}개 파일 → {out}  (추적 {len(files)} · 허용목록 밖 {len(not_allowed)} 제외)")
    print(f"[public] 허용목록 밖 구성: {dict(by_dir.most_common())}")
    print(f"[public] 데이터셋 비움: {scrub_stats}")
    print(f"[public] 비공개 블록 제거: {blocks_stripped or '없음'}")
    print(f"[public] 죽은 링크 평문화: {sum(links_flattened.values())}건 "
          f"({len(links_flattened)}파일)")
    print(f"[public] 비공개 토큰 문서 제외: {len(private_excluded)}건")
    for rel in sorted(private_excluded):
        print(f"         − {rel}")
    print(f"[public] 절대경로 스크럽: {abs_scrubbed or '없음'}")
    print(f"[public] 노트북 출력 제거: {nb_stripped or '없음'}")
    print("[public] 다음 단계는 검사기다 — 통과 전에는 푸시하지 않는다:")
    print(f"         python scripts/check_public_release.py --tree {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
