"""한국어/영어 사전토큰화기 (PLAN-018 F13 · E2).

아키텍처 결정(PLAN-018 §11.6): nori·Kiwi 를 **사전토큰화기**로 두고, 토큰을 공백으로 이어
Lucene whitespace 색인에 넣는다. 이렇게 하면 (1) DecompoundMode·사용자사전을 파이썬에서 완전히
통제하고 (2) §5.3 토큰화 민감도 분석(nori↔Kiwi)이 색인 파이프라인 교체 없이 성립한다.

- 주 토큰화(F13): nori `KoreanAnalyzer(DecompoundMode.NONE)` + SDKB 어휘 사용자사전.
- 민감도 비교자(§5.3): Kiwi(kiwipiepy).
- 영어(en) 문서/질의: Lucene standard analyzer (소문자·불용어).

모두 결정적이다. nori 는 JVM(JAVA_HOME) 을 요구한다(config.java_home).
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import config

_WS = re.compile(r"\s+")


# --- nori (JVM) -----------------------------------------------------------
class NoriTokenizer:
    """Lucene KoreanAnalyzer 기반 사전토큰화기 (DecompoundMode 지정 가능)."""

    def __init__(self, mode: str = "NONE", userdict: Path | None = None) -> None:
        config.java_home()  # JVM 부팅 전 JAVA_HOME 확정 (E1)
        # pyserini.pyclass.autoclass 는 anserini fatjar 클래스패스를 JVM 에 등록한 뒤
        # jnius.autoclass 를 노출한다 — 순수 jnius.autoclass 는 Lucene 클래스를 못 찾는다(E1 후속).
        from pyserini.analysis import Analyzer
        from pyserini.pyclass import autoclass

        KA = autoclass("org.apache.lucene.analysis.ko.KoreanAnalyzer")
        DecompoundMode = autoclass(
            "org.apache.lucene.analysis.ko.KoreanTokenizer$DecompoundMode"
        )
        decompound = getattr(DecompoundMode, mode)

        user_dict = None
        if userdict is not None and Path(userdict).exists():
            # UserDictionary.open(Reader) — 각 줄이 사용자 어휘 (surface [pos] 또는 복합어 규칙)
            UserDictionary = autoclass("org.apache.lucene.analysis.ko.dict.UserDictionary")
            StringReader = autoclass("java.io.StringReader")
            text = Path(userdict).read_text(encoding="utf-8")
            if text.strip():
                user_dict = UserDictionary.open(StringReader(text))

        # KoreanAnalyzer(userDict, mode, stopTags, outputUnknownUnigrams)
        # 기본 stopTags(조사·어미 등 품사 불용어 30종) = KoreanPartOfSpeechStopFilter.DEFAULT_STOP_TAGS.
        stop_filter = autoclass("org.apache.lucene.analysis.ko.KoreanPartOfSpeechStopFilter")
        stop_tags = stop_filter.DEFAULT_STOP_TAGS
        self._analyzer = Analyzer(KA(user_dict, decompound, stop_tags, False))

    def __call__(self, text: str) -> list[str]:
        if not text:
            return []
        return self._analyzer.analyze(text)


# --- Kiwi (순수 C++) ------------------------------------------------------
class KiwiTokenizer:
    """kiwipiepy 기반 사전토큰화기 (§5.3 민감도 비교자). 내용어(체언·용언·외래어)만 남긴다."""

    # 남길 품사 접두: N*(체언) V*(용언) SL(외래어) SH(한자) SN(숫자) XR(어근)
    _KEEP = ("N", "V", "SL", "SH", "SN", "XR")

    def __init__(self, userwords: list[str] | None = None) -> None:
        from kiwipiepy import Kiwi

        self._kiwi = Kiwi()
        for w in userwords or []:
            self._kiwi.add_user_word(w, "NNP")

    def __call__(self, text: str) -> list[str]:
        if not text:
            return []
        return [t.form for t in self._kiwi.tokenize(text) if t.tag.startswith(self._KEEP)]


# --- 영어 (Lucene standard) ----------------------------------------------
class EnglishTokenizer:
    def __init__(self) -> None:
        config.java_home()
        from pyserini.analysis import Analyzer, get_lucene_analyzer

        self._analyzer = Analyzer(get_lucene_analyzer(language="en"))

    def __call__(self, text: str) -> list[str]:
        if not text:
            return []
        return self._analyzer.analyze(text)


def pretokenize(text: str, ko, en, lang: str) -> str:
    """언어에 맞는 토큰화기로 사전토큰화해 공백-조인 문자열을 돌려준다.

    lang: 'ko'|'ja'→ko 토큰화기(한국어 코퍼스가 다수, ja 는 소수·ko 로 근사),
          그 외('en'/'und')→ en 토큰화기. 색인·질의 대칭 적용.
    """
    tok = ko if lang in ("ko", "ja", "und") else en
    return " ".join(tok(_WS.sub(" ", text or "")))
