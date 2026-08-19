"""텍스트 정제와 언어 감지 (결정적·무작위 없음).

sidecar `featureText` 에는 KIPRIS 원문의 HTML 조각(`</P><P>` 등)이 남아 있다. 색인 전에
태그를 제거하고 공백을 정규화한다. 언어는 스크립트(한글/가나) 존재로 결정한다 —
PLAN-017 §1.6 의 다국어 지형(질의=ko, qrel=ko57/en39/ja2)을 텍스트에서 재현하기 위함이다.
"""
from __future__ import annotations

import html
import re
import unicodedata

# HTML 태그 · 엔티티 · 잔여 제어문자
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# 유니코드 블록: 한글 음절/자모, 히라가나, 가타카나
_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_KANA = re.compile(r"[぀-ゟ゠-ヿ]")


def clean(text: str | None) -> str:
    """HTML 태그·엔티티를 제거하고 공백을 정규화한다. None/빈값 → ''."""
    if not text:
        return ""
    t = html.unescape(text)
    t = _TAG.sub(" ", t)
    t = unicodedata.normalize("NFC", t)
    t = _WS.sub(" ", t)
    return t.strip()


def detect_lang(text: str | None) -> str:
    """스크립트 기반 언어 감지 — ko(한글) > ja(가나) > en(그 외).

    한글이 하나라도 있으면 ko. 없고 가나가 있으면 ja. 둘 다 없으면 en.
    한자 단독(중국어/일본어 한자표기)은 en 으로 떨어진다 — 어휘검색 관점에선 비-한국어이고,
    §1.6 의 'JP 영문MT=en / JP 원문=ja' 구분과 정합(원문 ja 는 가나를 포함)."""
    if not text:
        return "und"
    if _HANGUL.search(text):
        return "ko"
    if _KANA.search(text):
        return "ja"
    return "en"
