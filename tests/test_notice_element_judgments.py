"""단계 2-C 채굴기의 계약을 고정한다 — PLAN-005 §11.

고정하는 것 셋.

  ① **거부해야 할 줄이 거부되는가.** 이 채굴기의 위험은 회수 부족이 아니라 **오검출**이다.
     `<표 N>` 블록 안에서 `구성 N-M` 을 아무 데서나 찾으면 672행이 잡히지만 그중
     **45.4%(305행)만 표 행**이고 나머지는 본문 산문이다(관찰 §3.1). 산문이 한 줄이라도
     산출에 들어오면 이 데이터는 이름과 다른 것을 담게 된다(§1-3).

  ② **판정 어휘가 뭉개지지 않는가.** 실측에서 이 서식의 `Identical` 188건은 **전부
     `실질적 동일`** 이고 단순 `동일` 은 0건이다 — 이 어휘가 잘리면 전량이 잘못
     라벨링된다. `judgment_raw` 를 함께 싣는 이유도 같다.

  ③ **누출 범위를 벗어난 출원이 산출에 없는가.** `check_leakage.py` 는 이 저장소에
     존재하지 않으므로(PLAN-001 이 이름만 적어 두었다), 누출을 실제로 막는 것은
     `harvest_scope_dev_train.json` 과 이 테스트뿐이다.

합성 텍스트로 ①②를 걸고, ③은 산출 parquet 이 있을 때만 건다(빌드 산출물이라 없을 수 있다).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_notice_element_judgments import (  # noqa: E402
    CANON, COLUMNS, TXT_DIR, normalize_app, parse_table_rows, sample_context,
    scope_applications,
)

#: 실물에서 온 형태만 쓴다 — 지어낸 형태로 통과시키면 계약이 실물과 갈린다.
GOOD = """
<표 3>
구성 8-3 타겟을 세정하는 단계 타겟을 세정하는 단계 실질적 동일
구성 24-2 실질적 동일
구성 1-1 차이
"""

#: 전부 거부되어야 하는 줄들.
#:
#: **줄머리가 `구성 N-M` 인 것만 고른다.** 처음에는 `위 표 4에 기재된 바와 같이 …` 처럼
#: 줄머리가 다른 산문도 넣었는데, 그런 줄은 줄머리에서 이미 걸러져 **경계(`\s+`)와 줄끝
#: 앵커(`$`)가 하는 일을 재지 못했다** — 변이 검사로 확인했다. 아래는 전부 실물 발췌이며
#: 줄머리·판정 어휘를 모두 갖췄으나 표 행이 아닌 줄이다.
BAD_CASES = {
    # 판정 어휘가 줄 **가운데** 있고 서술어로 끝난다 → 줄끝 앵커 `$` 가 거부한다.
    "산문_판정이_가운데": "<표 1>\n구성 11-1 내지 11-3과 각각 실질적으로 동일합니다.\n",
    "산문_판정이_가운데2": "<표 1>\n구성 11-1 내지 11-5와 각각 실질적으로 동일합니다.\n",
    # 구성번호 바로 뒤에 조사가 붙는다("22-5는"). 실제로 거부하는 것은 줄끝 앵커다 —
    # `\s+` 경계를 `\s*` 로 풀어도 산출이 305행 그대로였다(전수 확인). 경계를 계약이라
    # 적지 않는 이유이며, 이 줄은 그래도 거부되어야 하므로 사례로 남긴다.
    "산문_조사가_붙음": "<표 1>\n구성 22-5는 구성상 곤란성이 있다고 할 수 없습니다.\n",
    # 판정 없이 다음 줄로 이어지는 산문.
    "산문_판정없음": "<표 1>\n구성 1-4는 인용발명 1의 타깃(3)이 평면형상을 가진 구성으로부터 통상의\n",
    # `<표 N>` 블록 **밖**이다. 블록 밖의 표 행 형태는 표가 아니다.
    "블록밖": "구성 1-1 반응 챔버 실질적 동일\n",
    # 구성 번호가 `N-M` 이 아니다(한글 가지번호) — 청구항 구성요소 키가 되지 못한다.
    "한글가지번호": "<표 1>\n구성 1-가 반응 챔버 실질적 동일\n",
}


def test_정상_표행이_구조키로_뽑힌다() -> None:
    rows = parse_table_rows(GOOD)
    assert [(r["element_group"], r["element_no"]) for r in rows] == [(8, 3), (24, 2), (1, 1)]
    assert [r["judgment"] for r in rows] == ["Identical", "Identical", "Different"]
    assert all(r["table_index"] == 3 for r in rows)


#: 실물(`1020127009380`)에서 온 형태 — `<표2>` 의 `구성 2-N` 이 **청구항 3** 의 구성이다.
CAPTIONED = """
3. 청구항 3 발명과 인용발명1, 2를 비교해 보면 아래 표2와 같습니다.
<표2>
청구항 3 발명 비고
구성 2-1 순도 99.99% 구리 구리 순도 6N 이상 실질적 동일
구성 2-5 경도가 51~100Hv - 차이
"""


def test_앞_숫자를_청구항_번호로_쓰지_않는다() -> None:
    """§1-3 — 초판이 `구성 N-M` 의 앞 숫자를 `claim_no` 라 불렀고, 그것은 거짓이었다.

    실측 `1020127009380` 에서 `<표2>` 의 `구성 2-1…2-6` 은 전부 **청구항 3** 의 구성이다.
    전수 대조로 일치 258 · **불일치 9** · 캡션없음 38 이었다. 두 값은 별개의 컬럼이며,
    한쪽을 다른 쪽으로 대신하면 이름이 의미와 달라진다.
    """
    rows = parse_table_rows(CAPTIONED)
    assert [r["element_group"] for r in rows] == [2, 2], "구성 그룹은 원문 표기 그대로다"
    assert [r["caption_claim_no"] for r in rows] == [3, 3], "청구항 번호는 캡션에서 온다"
    assert "claim_no" not in rows[0], "앞 숫자를 청구항 번호로 부르는 이름이 남아 있다"


def test_캡션이_없으면_비운다() -> None:
    """추측하지 않는다 — 캡션 없는 12.5% 를 앞 숫자로 메우면 그 순간 §1-3 위반이다."""
    rows = parse_table_rows(GOOD)          # GOOD 에는 캡션 줄이 없다
    assert all(r["caption_claim_no"] is None for r in rows)


@pytest.mark.parametrize("name", sorted(BAD_CASES))
def test_표행이_아닌_줄은_거부된다(name: str) -> None:
    rows = parse_table_rows(BAD_CASES[name])
    assert not rows, f"{name}: 표 행이 아닌 줄이 {len(rows)}건 뽑혔다 — 산문 오검출(§1-3)"


def test_빈줄에서_블록이_닫힌다() -> None:
    """표는 빈 줄에서 끝난다. 닫지 않으면 문서 나머지가 통째로 표로 읽힌다."""
    rows = parse_table_rows("<표 1>\n구성 1-1 차이\n\n구성 2-2 실질적 동일\n")
    assert [(r["element_group"], r["element_no"]) for r in rows] == [(1, 1)], (
        "빈 줄 뒤의 줄까지 표 행으로 읽었다 — 블록이 닫히지 않는다")


def test_실질적동일이_한_어휘로_읽힌다() -> None:
    """`실질적 동일` 이 `동일` 로 잘려 라벨이 뭉개지지 않는지 고정한다.

    **교대 순서 때문이 아니다.** 처음에는 그렇게 적었으나, 교대를 뒤집어도 결과가 같다
    (변이 검사로 확인). 줄끝 앵커가 있어 `(.*?)` 가 `실질적` 을 삼키면 `동일` 앞의
    공백까지 맞춰야 하는데 그 경로가 더 길기 때문이다. 순서에 기대지 않는다는 사실
    자체가 계약이므로, 재는 것은 **결과 라벨**이다.
    """
    rows = parse_table_rows("<표 1>\n구성 1-1 실질적 동일\n")
    assert rows[0]["judgment_raw"] == "실질적 동일"
    assert rows[0]["judgment"] == "Identical"


def test_본문은_버려진다() -> None:
    """`(.*?)` 는 앵커일 뿐이다 — 산출 컬럼에 텍스트가 있으면 설계 계약이 깨진 것이다(§11.1)."""
    keys = set(parse_table_rows(GOOD)[0])
    assert keys == {"table_index", "element_group", "element_no", "caption_claim_no",
                    "judgment_raw", "judgment"}
    assert not any("text" in k or "본문" in k for k in COLUMNS)


def test_출원번호는_파일명_앞부분이다() -> None:
    """파일명은 `{출원번호}_{발송번호}` 다(2-A 교정 6). 통째로 숫자만 남기면 두 번호가
    이어붙어 범위 교집합이 0 이 된다 — 이 관찰에서 실제로 한 번 그렇게 나왔다."""
    name = "1019970082313_952000003500048.txt"
    assert normalize_app(name.split("_")[0]) == "1019970082313"
    assert normalize_app(name) != "1019970082313"


@pytest.mark.skipif(not CANON.exists(), reason="정본 parquet 미빌드")
def test_누출_범위를_벗어난_출원이_없다() -> None:
    pd = pytest.importorskip("pandas")
    df = pd.read_parquet(CANON)
    outside = sorted(set(df.application_number) - scope_applications())
    assert not outside, f"test/test_b 유래 출원이 산출에 있다: {outside[:5]}"


# ── 대조 시트의 문맥 (계측기 교정 2 · 2026-09-06) ─────────────────────────
#: 실물. `<표 3>` 과 `<표 4>` 가 **빈 줄 없이** 이어지는 문서다.
CONTEXT_FILE = "1020127014740_952016073593459.txt"


@pytest.mark.skipif(not (TXT_DIR / CONTEXT_FILE).exists(), reason="통지서 원천 없음")
def test_시트_문맥은_table_index_로_고른다() -> None:
    """**대조 시트가 틀리면 게이트가 사람의 판단이 아니라 계측기를 잰다.**

    초판 `sample_context` 는 *"대상 행을 포함하는 첫 블록"* 을 골랐다. 이 코퍼스에는
    빈 줄이 없는 문서가 있어 블록이 닫히지 않고, 앞 표의 창이 뒤 표의 행을 삼킨다 —
    `<표 4>` 의 행에 `<표 3>` 의 캡션이 붙었다. 30행 표본 중 **5행**이 그렇게 어긋난
    문맥을 받았고 검토자는 전부 `0` 을 찍었다. **판정이 옳았고 계측기가 틀렸다** —
    그 다섯 행은 원문 대조에서 parquet 값이 맞는 것으로 확인됐다.
    """
    cap, block = sample_context(CONTEXT_FILE, 4, 4, 1)
    assert block.split("\n")[0].strip() == "<표 4>", "요청한 표가 아닌 블록을 돌려줬다"
    assert "청구항 4 발명" in cap and "표 4" in cap, f"캡션이 다른 표의 것이다: {cap}"
    # 앞 표의 캡션이 새어 들어오면 안 된다.
    assert "표 3" not in cap


@pytest.mark.skipif(not (TXT_DIR / CONTEXT_FILE).exists(), reason="통지서 원천 없음")
def test_시트_블록이_다음_표에서_잘린다() -> None:
    """빈 줄에 기대지 않는다 — 이 코퍼스에는 빈 줄이 없는 문서가 있다."""
    _, block = sample_context(CONTEXT_FILE, 3, 3, 1)
    assert block.count("<표") == 1, "블록이 다음 표까지 삼켰다"
