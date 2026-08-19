"""동결 상수와 프롬프트 전문 — PLAN-038 §12.1·§12.3 (2026-08-03 · 결과 열람 전 확정).

**이 파일의 값은 A층 실행 후에도 바뀌지 않는다**(CLAUDE.md §1-11 첫 금지). 바꿀 수 있는 것은
§12.4 가 열거한 고장 수리뿐이며, 그때도 **수정 전후를 기록하고 A층을 전량 재실행**한다.

`PROMPT_SHA256` 은 프롬프트가 조용히 바뀌지 않게 하는 잠금이다 — 값이 어긋나면 테스트가 막는다.
"""
from __future__ import annotations

import hashlib

# ── §12.1 동결표 ────────────────────────────────────────────────────────────────
# 1 · 생성 모델. `global.` 접두 프로파일이 이 리전에서 호출되는 유일한 ID 다(§11.9 실측).
#     모델 스냅샷 날짜(20251001)가 ID 에 남아 있으므로 §1-11 "모델 버전 고정"을 충족한다.
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
# 1b · 호출 리전. **서빙 리전은 가변**이므로(global 프로파일) 응답 메타데이터를 매 호출 기록한다.
CALL_REGION = "ap-northeast-2"
# 1c · 토큰 계수 전용 ID(무과금 · §12.5 해소 기록). `global.` 프로파일은 CountTokens 를 받지
#      않으므로 **베이스 ID** 로 센다 — 같은 모델 스냅샷(20251001)이라 버전 고정은 유지된다.
COUNT_TOKENS_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
# 2 · 컨텍스트 K. §12.2 예산 규칙(성능 미참조)의 산출값 — 결과를 보고 바꾸지 않는다.
K = 10
# 3 · 온도 0 · 3c · top_p/top_k 는 보내지 않는다 · 3d · max_tokens 1024(절단율을 보고한다).
TEMPERATURE = 0
N_REPEATS = 3
# §12.4 고장 수리 (2026-08-03 · 스모크 절단율 0.400 ≥ 0.05). 1024 → 4096.
# 인용 10건 × 긴 한국어 청구항 원문이면 1024 로는 JSON 이 닫히지 않는다. **길이만 바꾼다** —
# 프롬프트·모델·온도·K 는 그대로이며, 이 값은 판독값을 본 뒤가 아니라 절단율을 본 뒤 바꿨다.
MAX_TOKENS = 4096
# 7 · 팔은 둘뿐이다. 생성기는 상수이고 변인은 이 이름 하나다(§0.5-1).
ARMS = ("B3_rrf", "P1")
# 8 · 질의·run. 새 질의셋을 만들지 않는다(§0.5-2).
RUNSET = "O_pre_linker"
SPLIT = "test"
# 10 · 지위. A층은 계측기 동결이며 **확증이 아니다**(§7 결정 "다").
STATUS = "exploratory"

# ── §12.4 고장의 정의 (판독값과 무관한 실패만 수리 대상) ────────────────────────
FAILURE_THRESHOLD_PARSE = 0.05      # JSON 파싱 실패율 ≥ 5 %
FAILURE_THRESHOLD_TRUNCATION = 0.05  # stop_reason == "max_tokens" 비율 ≥ 5 %

# ── §12.3 프롬프트 전문 (문자 단위로 두 팔에 동일) ──────────────────────────────
SYSTEM_PROMPT = """당신은 특허 선행기술 조사를 돕는 보조자다. 주어진 후보 문헌만을 근거로 답한다.

규칙:
1. 후보 문헌에 없는 내용을 쓰지 않는다. 모르면 모른다고 쓴다.
2. 모든 주장에는 근거 문헌의 식별자를 [DOC_ID] 형식으로 붙인다.
3. 근거가 되는 문장을 후보 문헌에서 그대로 인용한다(요약하지 않는다).
4. 아래 JSON 형식으로만 출력한다. 다른 텍스트를 덧붙이지 않는다.

출력 형식:
{"cited": ["<DOC_ID>", ...],
 "evidence": [{"doc_id": "<DOC_ID>", "quote": "<문헌에서 그대로 옮긴 문장>",
               "why": "<이 문장이 왜 선행기술로서 관련되는가 · 2문장 이내>"}],
 "insufficient": <true|false>}

"cited" 에는 실제로 선행기술로 관련된다고 판단한 문헌만 넣는다. 하나도 없으면 빈 배열과
"insufficient": true 를 쓴다. 억지로 채우지 않는다."""

USER_TEMPLATE = """아래는 어떤 특허출원의 독립항이다.

<청구항>
{QUERY_CLAIMS}
</청구항>

아래는 검색된 후보 문헌 10건이다.

<후보문헌>
{DOCS}
</후보문헌>

이 출원의 신규성·진보성을 판단할 때 근거가 될 수 있는 선행기술 문헌을 위 후보 중에서만
고르고, 지정된 JSON 형식으로 답하라."""

# 각 후보는 `[DOC_ID] <text_main>` 형태이며 **순위 순서**로 들어간다(§12.3 말미).
# 팔 이름·시스템 이름·"온톨로지" 같은 단어는 프롬프트에 넣지 않는다 — 모델이 어느 팔인지
# 알면 그것이 변인이 된다.
DOC_TEMPLATE = "[{doc_id}] {text}"
DOC_SEPARATOR = "\n\n"

# 프롬프트 동결 잠금. 문자 하나만 바뀌어도 어긋난다.
PROMPT_SHA256 = hashlib.sha256(
    (SYSTEM_PROMPT + "\x00" + USER_TEMPLATE + "\x00" + DOC_TEMPLATE).encode("utf-8")
).hexdigest()


def frozen_manifest(runset: str | None = None, split: str | None = None,
                    status: str | None = None) -> dict:
    """동결값 전량을 한 dict 로 — 생성 산출물의 머리글과 채점 산출물에 그대로 박힌다.

    **계측기 상수는 인자로 받지 않는다**(모델·프롬프트·K·온도·max_tokens·회차·팔·고장 임계).
    받는 셋은 *무엇을 읽고 어떤 지위로 싣는가*이며 계측기가 아니다 — 판독 B 는 같은 계측기로
    다른 분할을 읽는다(PLAN-047 §13.5).
    """
    return {
        "model_id": MODEL_ID,
        "call_region": CALL_REGION,
        "k": K,
        "temperature": TEMPERATURE,
        "n_repeats": N_REPEATS,
        "max_tokens": MAX_TOKENS,
        "arms": list(ARMS),
        "runset": runset or RUNSET,
        "split": split or SPLIT,
        "status": status or STATUS,
        "prompt_sha256": PROMPT_SHA256,
        "plan": "PLAN-038 §12",
    }


# ── 판독 B (PLAN-047 §13.5) — 계측기는 그대로, 읽는 대상만 다르다 ──────────────
SPLIT_B = "test_b"
RUNSET_B = "B_layer_readout"
STATUS_B = "confirmatory"
