"""공개본 생성기·검사기 회귀 테스트 (CR-015).

**왜 테스트가 필요한가.** 이 경로의 실수는 되돌릴 수 없다 — 공개된 커밋은 지워도 포크·
캐시·PR ref 로 남는다. 그래서 "비웠다"를 눈으로 확인하지 않고 기계로 고정한다.

세 가지를 고정한다:
  ① 원문 세 필드는 **값만** 비고 **키·구조는 남는다**(소비자 코드가 깨지지 않는다)
  ② 남기기로 한 서지(title·ipc·date·식별자·ground_truth_*)는 **그대로** 있다
  ③ 지문 검사기가 **누출을 실제로 잡는다** — 통과만 확인하면 항상 통과하는 검사기도 통과한다
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_public_release import (  # noqa: E402
    BLOCK_BEGIN, BLOCK_END, PRIVATE_TOKEN, flatten_dead_links, is_allowed,
    is_private_doc, scrub_abs_paths, scrub_dataset, strip_notebook, strip_private_blocks,
)
from check_public_release import (  # noqa: E402
    LEGACY_SLUG_ALLOWED, PROBE_LEN, build_probes, scan_boundary,
)
from config.namespaces import LEGACY_REPO_SLUG  # noqa: E402


def _record() -> dict:
    long_ko = "반도체 기판 위에 하드마스크 층을 형성하고 극자외선 노광으로 패터닝하는 방법에 관한 것으로서 " * 3
    return {
        "target_patent": {
            "application_number": "1020227033671",
            "title": "EUV 패터닝의 결함 감소를 위한 다층 하드마스크",
            "abstract": "초록 " + long_ko,
            "ipc": "H10P 50/28|C23C 16/448",
            "date": "2022.09.27",
            "claim1": "1. 청구항 " + long_ko,
            "claims_full": [
                {"claim_no": 1, "depends_on": [], "text": "1. 청구항 " + long_ko},
                {"claim_no": 2, "depends_on": [1], "text": "2. 제1항에 있어서 " + long_ko},
            ],
            "family": {"publication_numbers": ["US11xxxxx"], "source": "kipris"},
        },
        "ground_truth_examiner": ["KR1020190085654 A"],
        "ground_truth_all": ["KR1020190085654 A", "US20190348292 A1"],
        "meta": {"source": "kipris_plus_api"},
    }


@pytest.fixture()
def scrubbed() -> tuple[dict, dict]:
    raw = (json.dumps(_record(), ensure_ascii=False) + "\n").encode("utf-8")
    out, stats = scrub_dataset(raw)
    return json.loads(out.decode("utf-8").strip()), stats


def test_원문_세_필드가_값만_빈다(scrubbed):
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert tp["abstract"] == ""
    assert tp["claim1"] == ""
    assert [c["text"] for c in tp["claims_full"]] == ["", ""]


def test_스키마와_청구항_구조는_남는다(scrubbed):
    """항을 지우면 ingest_rejected_patents 가 세는 항수·보유 플래그가 거짓이 된다."""
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert "abstract" in tp and "claim1" in tp          # 키 삭제가 아니라 값 비우기
    assert [c["claim_no"] for c in tp["claims_full"]] == [1, 2]
    assert tp["claims_full"][1]["depends_on"] == [1]


def test_서지와_정답은_그대로다(scrubbed):
    """title 은 서지이며 kipris_biblio.parquet 에 이미 커밋돼 있다 — 비우면 손실만 난다."""
    rec, _ = scrubbed
    tp = rec["target_patent"]
    assert tp["title"] == "EUV 패터닝의 결함 감소를 위한 다층 하드마스크"
    assert tp["ipc"] and tp["date"] and tp["application_number"]
    assert rec["ground_truth_examiner"] == ["KR1020190085654 A"]
    assert len(rec["ground_truth_all"]) == 2


def test_비운_건수를_센다(scrubbed):
    _, stats = scrubbed
    assert stats == {"rows": 1, "abstract": 1, "claim1": 1, "claims_full_texts": 2}


def test_노트북_출력이_제거된다():
    nb = {"cells": [{"cell_type": "code", "execution_count": 3,
                     "outputs": [{"output_type": "stream", "text": ["초록 : ..."]}],
                     "source": []}],
          "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    out, n = strip_notebook((json.dumps(nb) + "\n").encode("utf-8"))
    got = json.loads(out.decode("utf-8"))
    assert n == 1
    assert got["cells"][0]["outputs"] == []
    assert got["cells"][0]["execution_count"] is None


def test_검사기_지문이_누출을_잡는다(tmp_path):
    """통과만 확인하면 항상 통과하는 검사기도 통과한다 — 잡는 쪽을 고정한다."""
    canonical = tmp_path / "canonical.jsonl"
    canonical.write_text(json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")
    probes, _ = build_probes(canonical)
    assert probes, "지문이 하나도 안 나오면 검사기는 아무것도 못 잡는다"
    leaked = _record()["target_patent"]["abstract"]
    assert any(p in leaked for _, _, p in probes)


def test_압축_parquet_안의_원문을_잡는다(tmp_path):
    """D-42 — 검사기가 오랫동안 못 보던 자리. **실패해야 할 입력이 실패하는가.**

    ZSTD 로 압축하면 원문 지문이 바이트에 남지 않는다. 예전 검사기는 파일을 read_text 로
    훑었으므로 이 parquet 을 **통과시켰다** — 그리고 "적중 0" 을 출력했다. 거짓 안심이다.
    """
    import pandas as pd

    from check_public_release import scan_structured

    # **원문이 서로 다를 때** 압축이 실제로 걸린다. 같은 문자열을 반복하면 parquet 이
    # 사전 인코딩으로 한 번만 저장해 바이트에 그대로 남는다 — 그래서 옛 검사기가 우연히 잡는다.
    #
    # 실측(2026-08-15 · 서로 다른 원문): 10행 3.8 KB 숨김 · 1,000행 49 KB 숨김 ·
    # 20,000행 913 KB **노출**. **크기와 단조롭지 않다** — 인코딩과 페이지 배치에 달렸다.
    # 즉 옛 검사기의 적중 여부는 내용 배치에 따라 갈리는 **우연**이었고, 그것이 D-42 다.
    # 이 테스트는 안정적으로 숨는 쪽(1,000행)을 재현한다.
    # 지문은 **변하는 자리**에서 뽑는다. 문서마다 같은 머리말을 쓰면 그 머리말은 압축
    # 출력의 리터럴 구간에 한 번 그대로 남아 옛 방식으로도 보인다 — 그것은 우리가 재현하려는
    # 상황이 아니다(실제 원문은 문서마다 다르다).
    rng = random.Random(20260815)
    words = ["식각", "증착", "노광", "세정", "이온주입", "평탄화", "확산", "검사"]
    base = _record()["target_patent"]["abstract"]
    texts = [f"{base[:20]} 제{i}항 " + " ".join(rng.choice(words) for _ in range(30))
             for i in range(1000)]
    leaked = texts[500][:PROBE_LEN]
    p = tmp_path / "leaky.parquet"
    pd.DataFrame({"doc_id": [f"kr_{i}" for i in range(1000)],
                  "feature_text": texts}).to_parquet(p, index=False, compression="zstd")

    # ① 옛 방식(바이트를 텍스트로 읽기)으로는 안 보인다 — 이것이 D-42 의 실체다.
    assert leaked not in p.read_bytes().decode("utf-8", errors="ignore")

    # ② 새 방식은 열 이름과 값 **양쪽**으로 잡는다.
    bad_cols, text = scan_structured(p)
    assert "feature_text" in bad_cols, "원문 계열 열 이름을 놓쳤다"
    assert leaked in text, "열 값 안의 원문을 놓쳤다"


def test_구조만_있는_parquet_은_통과한다(tmp_path):
    """거짓 경보도 결함이다 — 원문 없는 투영(CR-017 형태)은 깨끗하게 통과해야 한다."""
    import pandas as pd

    from check_public_release import scan_structured

    p = tmp_path / "projection.parquet"
    pd.DataFrame({"publication_id": ["kr_1"], "claim_number": [1],
                  "feature_seq": [1], "feature_concept": [["process:etch"]]}).to_parquet(
        p, index=False, compression="zstd")

    bad_cols, text = scan_structured(p)
    assert bad_cols == []
    assert "process:etch" in text, "값을 폈는지 확인 — 열지 않고 통과시키면 의미가 없다"


def test_다룰_줄_모르는_형식은_조용히_넘어가지_않는다(tmp_path):
    """검사기가 눈을 감는 방식은 늘 '예외를 삼키는 것'이었다. 그래서 올린다."""
    from check_public_release import scan_structured

    p = tmp_path / "x.7z"
    p.write_bytes(b"\x00\x01")
    with pytest.raises(RuntimeError):
        scan_structured(p)


def test_첫줄_토큰_문서는_비공개다():
    """**첫 줄에서만** 인정한다 — 본문에서 토큰을 언급하는 문서는 그것을 설명하는 것이지
    선언하는 것이 아니다. 실제로 그런 문서가 있다(readiness_review.md:53)."""
    assert is_private_doc(f"{PRIVATE_TOKEN}\n# 내부 문서\n".encode())
    assert is_private_doc(f"   {PRIVATE_TOKEN}   \n본문\n".encode())          # 앞뒤 공백
    assert not is_private_doc(f"# 공개 문서\n\n{PRIVATE_TOKEN}\n".encode())   # 셋째 줄
    assert not is_private_doc(f"> 첫 줄에 `{PRIVATE_TOKEN}` 를 단다\n".encode())  # 인용문
    assert not is_private_doc(b"")


def test_검사기가_트리의_토큰_문서를_잡는다(tmp_path):
    """생성기가 걸러도 **손으로 만든 트리**가 있다. 실패해야 할 입력이 실패하는가."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "internal.md").write_text(
        f"{PRIVATE_TOKEN}\nCONFIDENTIAL 가격표\n", encoding="utf-8")
    (tmp_path / "docs" / "public.md").write_text(
        f"비공개 문서는 첫 줄에 `{PRIVATE_TOKEN}` 를 단다.\n", encoding="utf-8")
    private, abs_hits, legacy = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert private == ["docs/internal.md"]     # 규약을 **설명**하는 문서는 통과한다
    assert abs_hits == []
    assert legacy == []


def test_검사기가_옛_리포_URL_을_잡는다(tmp_path):
    """R3 회귀 — 리포명을 바꾼 뒤 누가 옛 URL 을 다시 심으면 공개 첫날 404 가 된다.
    실패해야 할 입력이 실패하는가, 그리고 **인용 허용 파일은 통과하는가.**"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "new.md").write_text(
        f"소스: https://github.com/arkwith7/{LEGACY_REPO_SLUG}\n", encoding="utf-8")
    (tmp_path / "docs" / "clean.md").write_text(
        "소스: https://github.com/arkwith7/sdkb-dataset\n", encoding="utf-8")
    _, _, legacy = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert [h["file"] for h in legacy] == ["docs/new.md"]

    # 허용 목록의 파일은 그 슬러그를 **인용하는 것이 일**이다 — F3 의 증거다.
    allowed = tmp_path / next(iter(LEGACY_SLUG_ALLOWED))
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text(f"F3 의 증거: …/{LEGACY_REPO_SLUG}/…\n", encoding="utf-8")
    _, _, legacy2 = scan_boundary(sorted(tmp_path.rglob("*.md")), tmp_path)
    assert [h["file"] for h in legacy2] == ["docs/new.md"]


def test_URL_의_home_은_스크럽되지_않는다():
    """실측 회귀 — 추적 파일 둘이 URL 안에 `/home/` 을 담는다
    (irds.ieee.org/home/… · horiba.com/kr/horiba-stec/home/). 지우면 발행된 링크가 죽는다."""
    keep = b'{"url": "https://irds.ieee.org/home/how-to-download-irds"}'
    out, n = scrub_abs_paths(keep)
    assert (out, n) == (keep, 0)

    # 리터럴로 적으면 **이 테스트 파일 자신이** 검사기에 걸린다 — 조립해서 만든다.
    abs_path = "/" + "home/u/Dev/private-repo/ids.txt"
    out, n = scrub_abs_paths(f'{{"input_ids": "{abs_path}"}}'.encode())
    assert n == 1
    assert out == b'{"input_ids": "ids.txt"}'   # 경로는 지우되 **어떤 파일인지는 남긴다**


def test_남기는_필드와_겹치는_지문은_버린다(tmp_path):
    """초록이 제목을 되풀이하는 특허가 있다 — 그 지문은 누출과 정상 발행을 구분하지 못한다."""
    rec = _record()
    title = "가" * 200
    rec["target_patent"]["title"] = title
    rec["target_patent"]["abstract"] = title
    canonical = tmp_path / "canonical.jsonl"
    canonical.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    probes, dropped = build_probes(canonical)
    assert dropped >= 1
    assert all(field != "abstract" for _, field, _ in probes)


# ═══════════════════════════════════════════════════════════════════
# 허용목록 전환 (2026-08-10) — 목록의 방향이 뒤집혔다.
# 예전 계약은 "빼기로 한 것이 빠졌는가"였고, 새 계약은 **"넣기로 한 것만 들어왔는가"** 다.
# ═══════════════════════════════════════════════════════════════════

def test_모르는_파일은_공개되지_않는다():
    """허용목록의 존재 이유 — **새로 생긴 파일이 기본값으로 공개되지 않는다.**"""
    assert not is_allowed("notebooks/99_new_experiment.ipynb")
    assert not is_allowed("docs/plan_next_quarter.md")        # docs 는 파일 열거다
    assert not is_allowed("secrets.env")
    assert not is_allowed("data/patents/rejection_decisions/structured/1020200000000.json")
    assert is_allowed("ontology/sdkb-patent.ttl")
    assert is_allowed("docs/ontology_guide.md")
    assert is_allowed("scripts/build_abox_patents.py")
    assert is_allowed("tests/test_owl.py")


def test_제외_결정이_조용히_뒤집히지_않는다():
    """사용자 결정(2026-08-10)을 코드에 고정한다. 되돌리려면 이 테스트를 함께 고쳐야 한다."""
    assert not is_allowed("scripts/build_viz.py")            # 시각화·Pages
    assert not is_allowed("scripts/eval_prior_art_realgt.py")  # 평가
    assert not is_allowed("scripts/build_rejection_decisions.py")
    # 이름이 노트북 헬퍼처럼 보이지만 tests/ 가 임포트한다 — 이름이 아니라 쓰임으로 판단한다.
    assert is_allowed("scripts/sdkb_nb.py")


def test_청구항_투영은_공개되지_않는다():
    """사용자 결정(2026-08-15) — 청구항 구조 1,306,191행은 공개 트리에 넣지 않는다.

    **접두사 허용이 기본 비공개 원칙을 무력화한 자리**라서 테스트로 고정한다.
    `mappings/` 는 통째 허용이므로 이 파일은 아무도 결정하지 않아도 공개된다 —
    실제로 그렇게 될 뻔했다. 원문이 0열이라 KIPRIS 조건과 충돌하지는 않지만,
    **범주가 다른 자산**(어휘·T-Box·shape·CQ·메타가 아니라 청구항 분해 구조)이다.

    되돌리려면 이 테스트를 함께 고쳐야 한다 — 그것이 이 테스트의 목적이다.
    """
    assert not is_allowed("mappings/claim_features.parquet")
    # 메타는 남는다 — 개념별 df 와 커버리지 집계뿐이고 행 단위 구조가 없다.
    assert is_allowed("mappings/claim_feature_release_meta.json")
    # 같은 접두사의 기존 자산은 그대로 공개된다(이 제외가 mappings/ 를 통째로 닫지 않는다).
    assert is_allowed("mappings/concept_mapping.json")


def test_비공개_블록은_자기_줄에_혼자_있어야_인정된다():
    """마커를 **설명하는** 줄이 마커가 되면 안 된다. 실제로 그래서 빌드가 죽었다."""
    body = ("살린다\n"
            f"# {BLOCK_BEGIN}\n지운다\n# {BLOCK_END}\n"
            f"`{BLOCK_BEGIN}` 와 `{BLOCK_END}` 를 설명하는 줄은 마커가 아니다\n").encode()
    out, dropped = strip_private_blocks(body, "t.md")
    text = out.decode()
    assert "지운다" not in text and "살린다" in text
    assert "설명하는 줄은 마커가 아니다" in text
    assert dropped == 3


def test_닫히지_않은_블록은_빌드를_세운다():
    """조용히 파일 끝까지 지우면 그 사실이 아무에게도 보이지 않는다."""
    with pytest.raises(ValueError):
        strip_private_blocks(f"# {BLOCK_BEGIN}\n본문\n".encode(), "t.md")


def test_없는_문서를_가리키는_링크는_평문이_된다():
    """허용목록은 파일을 빼 주지만 그 파일을 가리키던 문장은 빼 주지 않는다."""
    published = {"docs/ontology_guide.md"}
    raw = ("[가이드](ontology_guide.md) 와 [계획서](plan_secret.md) 와 "
           "[외부](https://example.org/x.md)\n").encode()
    out, n = flatten_dead_links(raw, "docs/README.md", published)
    text = out.decode()
    assert n == 1
    assert "[가이드](ontology_guide.md)" in text      # 살아 있는 링크는 그대로
    assert "계획서" in text and "plan_secret.md" not in text
    assert "https://example.org/x.md" in text          # 외부 URL 은 검사 대상이 아니다


def test_없는_문서만_가리키는_표_행은_통째로_빠진다():
    """행이 통째로 없는 문서를 소개하면 색인이 아니라 오답이 된다."""
    published = {"docs/ontology_guide.md"}
    raw = ("| Doc | What |\n|---|---|\n"
           "| [가이드](ontology_guide.md) | 스펙 |\n"
           "| [계획서](plan_secret.md) | 계획 |\n").encode()
    out, _ = flatten_dead_links(raw, "docs/README.md", published)
    text = out.decode()
    assert "가이드" in text
    assert "계획" not in text
