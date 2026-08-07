"""CR-013 (하류 D-20) — 원소 기호 별칭이 틀린 물질에 붙는 것을 막는 계약.

고정하는 것 넷.
  1. **사전 층** — patent-text 에 단독 `hf` 가 없고, `high k` 가 hfO2 를 가리키지
     않으며 상위 부류 material:dielectric 로 간다 (검증기준 ①②).
  2. **프로파일 격리** — expert-tag 는 한 글자도 움직이지 않는다 (비목표 ⓕ).
     원천(KG synonyms)에서 지웠다면 이 테스트가 실패한다 — 그것이 이 규칙의 존재
     이유다. 사전 층에서 끄는 것과 원천에서 지우는 것은 다른 일이다.
  3. **A-Box 층** — 상류는 원문 대소문자를 갖고 있으므로 `HF`(불산)만 남기고
     `Hf`(하프늄)·혼재·판별불가는 뗀다. **하프늄 링크를 새로 만들지 않는다**
     (설계 C2 — 재지정은 오링크의 방향만 뒤집는다).
  4. **억제는 조용히 일어나지 않는다** — 무엇을 왜 뺐는지가 blocked 에 남는다.

그리고 **뒤집으면 실패하는지**도 확인한다: 억제 목록을 비우면 두 표면형이
되살아나야 한다. 되살아나지 않으면 억제가 아니라 우연이다 (CLAUDE.md §2-5b).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_concept_mapping import (  # noqa: E402
    collect, norm, suppressions,
)

KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
ALIASES_PATH = ROOT / "mappings" / "abox_term_aliases.json"
ASSET_PATH = ROOT / "mappings" / "concept_mapping.json"

SUPPRESSED = {("hf", "material:hf_acid"), ("high k", "material:hfO2")}


@pytest.fixture(scope="module")
def kg():
    return json.loads(KG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def aliases():
    return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def asset():
    if not ASSET_PATH.exists():
        pytest.skip("concept_mapping.json 미생성 — scripts/build_concept_mapping.py")
    return json.loads(ASSET_PATH.read_text(encoding="utf-8"))


def _pairs(asset, profile):
    return {(e["surface"], e["concept_id"])
            for e in asset["profiles"][profile]["entries"]}


class TestDictionaryLayer:
    def test_criterion_1_no_bare_hf(self, asset):
        """검증기준 ① — patent-text 에 단독 `hf` 표면형이 0 건."""
        hits = [e for e in asset["profiles"]["patent-text"]["entries"]
                if e["surface"] == "hf"]
        assert hits == [], hits

    def test_criterion_2_high_k_not_hfo2(self, asset):
        """검증기준 ② — `high k` 가 material:hfO2 를 가리키지 않는다."""
        assert ("high k", "material:hfO2") not in _pairs(asset, "patent-text")

    def test_high_k_goes_to_superordinate(self, asset):
        """ⓑ 의 최종 형태 — 제거가 아니라 상위 부류 재지정이다."""
        es = [e for e in asset["profiles"]["patent-text"]["entries"]
              if e["surface"] == "high k"]
        assert len(es) == 1, es
        assert es[0]["concept_id"] == "material:dielectric"
        # 부류 개념은 큐레이션 브리지에서 온다 — Tier-1 로 오면 원천을 고친 것이다.
        assert es[0]["rule_id"] == "T2-ALIAS-REASSIGN"
        assert es[0]["ambiguous"] is False

    def test_hf_concepts_still_reachable(self, asset):
        """개념이 사라진 것이 아니라 판별 불가한 표면형 하나가 빠진 것이다."""
        pairs = _pairs(asset, "patent-text")
        assert ("불산", "material:hf_acid") in pairs
        assert ("hydrofluoric acid", "material:hf_acid") in pairs
        assert ("hfo2", "material:hfO2") in pairs
        assert ("hafnium oxide", "material:hfO2") in pairs


class TestProfileIsolation:
    def test_expert_tag_keeps_both_surfaces(self, asset):
        """비목표 ⓕ — expert-tag 는 건드리지 않는다."""
        pairs = _pairs(asset, "expert-tag")
        assert ("hf", "material:hf_acid") in pairs
        assert ("high k", "material:hfO2") in pairs

    def test_source_synonyms_untouched(self, kg):
        """원천에서 지우면 두 프로파일과 skos:altLabel 이 함께 움직인다."""
        terms = {(s["node_id"], s["term"]) for s in kg.get("synonyms", [])}
        assert ("material:hf_acid", "HF") in terms
        assert ("material:hfO2", "High-k") in terms

    def test_suppression_is_profile_scoped(self, aliases):
        assert suppressions(aliases, "patent-text") == SUPPRESSED
        assert suppressions(aliases, "expert-tag") == set()


class TestSuppressionIsVisible:
    def test_blocked_records_r6(self, asset):
        """억제는 삭제가 아니라 이동이다 — 무엇을 뺐는지 자산에 남는다."""
        r6 = {(b["surface"], b["concept_id"])
              for b in asset["profiles"]["patent-text"]["blocked"]
              if b["rule_id"] == "R6-SURFACE-SUPPRESS"}
        assert r6 == SUPPRESSED

    def test_rule_is_documented(self, asset):
        assert "R6-SURFACE-SUPPRESS" in asset["rules"]


class TestSuppressionActuallyDoesTheWork:
    """실패해야 할 입력이 실패하는가 — 억제를 끄면 두 표면형이 되살아난다."""

    def test_without_suppression_pairs_return(self, kg, aliases):
        off = copy.deepcopy(aliases)
        off.pop("_suppress_tier1_surface", None)
        exc = {norm(t) for t in off.get("_exceptions_short_ko_task_axis", [])}
        entries, _ = collect(kg, off, "patent-text", exc)
        pairs = {(e["surface"], e["concept_id"]) for e in entries}
        assert SUPPRESSED <= pairs, "억제를 껐는데도 안 돌아왔다 — 다른 것이 지우고 있다"
        # 억제가 없으면 `high k` 는 두 개념에 걸려 다의가 된다 — 그래서 뗀 것이다.
        hk = [e for e in entries if e["surface"] == "high k"]
        assert len(hk) == 2 and all(e["ambiguous"] for e in hk)


class TestAboxCaseResolution:
    """ⓒ — 사전 층에서 못 가르는 것을 A-Box 층에서는 원문으로 가른다."""

    @staticmethod
    def _hits():
        return {"hf": [("material:hf_acid", "Material")],
                "식각": [("process:etch", "Process")]}

    def test_uppercase_hf_is_kept(self):
        import sdkb_nb as S
        out = S.resolve_hf_case(self._hits(), "HF 용액으로 세정한다")
        assert out["hf"] == [("material:hf_acid", "Material")]

    def test_hafnium_hf_is_dropped(self):
        import sdkb_nb as S
        out = S.resolve_hf_case(self._hits(), "Hf 산화막을 증착한다")
        assert "hf" not in out
        assert out["식각"], "다른 표면형까지 지우면 안 된다"

    def test_mixed_case_is_dropped(self):
        """혼재는 판별 불가다 — 어느 쪽으로도 찍지 않는다."""
        import sdkb_nb as S
        assert "hf" not in S.resolve_hf_case(self._hits(), "HF 세정 후 Hf 막 형성")

    def test_undecidable_lowercase_is_dropped(self):
        import sdkb_nb as S
        assert "hf" not in S.resolve_hf_case(self._hits(), "hf 처리한다")

    def test_never_creates_hafnium_links(self):
        """설계 C2 — 재지정하지 않는다. 링크를 새로 만들면 이 테스트가 막는다."""
        import sdkb_nb as S
        for raw in ("Hf 막", "HF 용액", "HF 와 Hf", "hf"):
            out = S.resolve_hf_case(self._hits(), raw)
            assert not any(nid == "material:hfO2"
                           for hits in out.values() for nid, _ in hits)

    def test_other_surfaces_are_untouched(self):
        """`불산`·`hydrofluoric acid` 로 붙은 링크는 이 규칙의 대상이 아니다."""
        import sdkb_nb as S
        hits = {"불산": [("material:hf_acid", "Material")]}
        assert S.resolve_hf_case(hits, "Hf 산화막") == hits

    def test_word_boundary(self):
        """`hfo2`·`shf` 안의 hf 는 판별자가 아니다."""
        import sdkb_nb as S
        assert "hf" not in S.resolve_hf_case(self._hits(), "HfO2 게이트 유전막")
