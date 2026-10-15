"""PLAN-006 T4 R2 — 번역 응답 파싱의 계약 (호출 없음)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import translate_terms as T  # noqa: E402


def test_parse_keeps_only_asked_terms_and_dedups():
    text = json.dumps({"items": [
        {"ko": "측벽 보호막", "en": ["sidewall protective film", "Sidewall  protective film", "sidewall passivation layer", "x", "y"]},
        {"ko": "묻지 않은 것", "en": ["nope"]},
    ]})
    got = T.parse_items(text, ["측벽 보호막"])
    assert got == {"측벽 보호막": ["sidewall protective film", "sidewall passivation layer", "x"]}


def test_missing_term_is_bad_output():
    text = json.dumps({"items": [{"ko": "측벽 보호막", "en": []}]})
    with pytest.raises(T.BadOutput):
        T.parse_items(text, ["측벽 보호막", "식각"])


def test_code_fence_tolerated_and_shape_checked():
    assert T.parse_items('```json\n{"items": [{"ko": "a", "en": ["b"]}]}\n```', ["a"]) == {"a": ["b"]}
    with pytest.raises(T.BadOutput):
        T.parse_items('{"result": []}', ["a"])
    with pytest.raises(T.BadOutput):
        T.parse_items('{"items": [{"ko": "a", "en": "b"}]}', ["a"])


def test_parse_rejects_non_json():
    with pytest.raises(json.JSONDecodeError):
        T.parse_items("not json", ["a"])


def test_sealed_splits_refused():
    with pytest.raises(SystemExit):
        T.collect_terms(splits=("test",))


def test_prompt_sha_is_stable():
    assert T.prompt_sha() == T.prompt_sha() and len(T.prompt_sha()) == 64
