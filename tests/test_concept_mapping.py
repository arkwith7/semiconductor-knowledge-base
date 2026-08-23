"""CR-007 — 개념 매핑 자산·상하위 계층의 계약.

이 파일이 고정하는 것 넷.
  1. **결정성** — 같은 입력이면 같은 바이트가 나온다 (성공기준 ②).
  2. **프로파일 격리** — patent-text 의 재지정이 expert-tag 를 건드리지 않는다
     (비목표: 전문가매칭 회귀 금지 · T3).
  3. **중의성 규칙** — 후보를 지우지 않고 결정적 순서로 제시한다 (성공기준 ③).
  4. **계층** — 상위 개념 7 개가 각각 하위를 갖고, 순환이 없다 (성공기준 ⑩).

그리고 **실패해야 할 입력이 실패하는지**도 확인한다 — 하위를 떼면 SHACL 이
거부해야 한다. 거부하지 않으면 그건 게이트가 아니라 장식이다 (CLAUDE.md §2-5b).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_concept_mapping import (  # noqa: E402
    AXIS_RANK, TASK_AXES, collect, is_short_korean, norm,
)

KG_PATH = ROOT / "data" / "semiconductor_v0_3.json"
ALIASES_PATH = ROOT / "mappings" / "abox_term_aliases.json"
ASSET_PATH = ROOT / "mappings" / "concept_mapping.json"

# CR-007 §3단계 결정 ① — 뒤집으면 이 테스트가 막는다.
REASSIGNED = {
    "챔버":       ("skill:chamber_conditioning", "equipment_class:process_chamber"),
    "가스":       ("skill:gas_chemistry",        "material:process_gas"),
    "공정 가스":  ("skill:gas_chemistry",        "material:process_gas"),
    "플라즈마":   ("skill:plasma_diagnostics",   "process:plasma_processing"),
    "마스크":     ("skill:mask_engineering",     "material:photomask"),
    "포토마스크": ("skill:mask_engineering",     "material:photomask"),
    "정렬":       ("skill:overlay_optimization", "subprocess:overlay_control"),
    "alignment":  ("skill:overlay_optimization", "subprocess:overlay_control"),
    "슬러리":     ("skill:slurry_management",    "material:cmp_slurry"),
    "절연막":     ("material:sio2",              "material:dielectric"),
    "산화물":     ("material:sio2",              "material:oxide"),
}
# 결정 ④ — 어느 축에 붙여도 문서를 구분하지 못하는 일반어.
DROPPED_IN_PATENT_TEXT = ["결함", "수율"]

SUPERORDINATE = [
    "equipment_class:process_chamber", "material:process_gas",
    "process:plasma_processing", "material:photomask",
    "material:dielectric", "material:oxide", "material:cmp_slurry",
]


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


def _index(asset, profile):
    idx = {}
    for e in asset["profiles"][profile]["entries"]:
        idx.setdefault(e["surface"], []).append(e)
    return idx


class TestDeterminism:
    def test_same_input_same_output(self, kg, aliases):
        """성공기준 ② — 두 번 돌려 같은 결과."""
        exc = {norm(t) for t in aliases.get("_exceptions_short_ko_task_axis", [])}
        a1, b1 = collect(kg, aliases, "patent-text", exc)
        a2, b2 = collect(kg, aliases, "patent-text", exc)
        assert a1 == a2 and b1 == b2

    def test_asset_matches_generator(self, kg, aliases, asset):
        """파일이 생성기와 어긋나면(손편집 등) 하류 재현이 깨진다.

        R7(CR-001B)은 표면형 df 를 입력으로 받으므로, 재생성에도 그 재료를 준다.
        재료는 자산이 발행한 surface_meta 에서 읽는다 — A-Box 를 다시 세지 않고도
        **자산이 자기 규칙과 정합한지**를 묻는다.
        """
        exc = {norm(t) for t in aliases.get("_exceptions_short_ko_task_axis", [])}
        grand = frozenset(norm(s) for s in
                          (aliases.get("_r7_grandfathered") or {}).get("surfaces", {}))
        for profile in ("expert-tag", "patent-text"):
            meta = asset["profiles"][profile]["surface_meta"]
            denom = meta["df_denominator"]
            ratio = {s: n / denom for s, n in meta["surfaces"].items()}
            entries, blocked = collect(kg, aliases, profile, exc,
                                       df_ratio=ratio, grandfathered=grand)
            assert entries == asset["profiles"][profile]["entries"]


class TestProfileIsolation:
    def test_expert_tag_targets_unchanged(self, asset):
        """비목표 — expert-tag 의 현행 타깃은 그대로다 (T3)."""
        idx = _index(asset, "expert-tag")
        for surface, (expert_target, _) in REASSIGNED.items():
            ids = {e["concept_id"] for e in idx.get(surface, [])}
            assert expert_target in ids, f"{surface}: expert-tag 타깃이 사라졌다"

    def test_dropped_terms_survive_in_expert_tag(self, asset):
        idx = _index(asset, "expert-tag")
        for surface in DROPPED_IN_PATENT_TEXT:
            assert idx.get(surface), f"{surface}: expert-tag 에서 사라지면 안 된다"

    def test_patent_text_reassigned(self, asset):
        idx = _index(asset, "patent-text")
        for surface, (_, patent_target) in REASSIGNED.items():
            ids = {e["concept_id"] for e in idx.get(surface, [])}
            assert patent_target in ids, f"{surface}: 재지정 타깃이 없다"

    def test_dropped_terms_absent_in_patent_text(self, asset):
        idx = _index(asset, "patent-text")
        for surface in DROPPED_IN_PATENT_TEXT:
            assert surface not in idx, f"{surface}: patent-text 에서 비활성이어야 한다"

    def test_superordinates_absent_from_expert_tag(self, asset):
        """신설 개념의 이름은 Tier-1 에서 기존 별칭을 가린다 — expert-tag 에서 격리."""
        ids = {e["concept_id"] for e in asset["profiles"]["expert-tag"]["entries"]}
        assert not (set(SUPERORDINATE) & ids)


class TestShortKoreanRule:
    def test_rule_predicate(self):
        assert is_short_korean("챔버") and is_short_korean("플라즈마")
        assert not is_short_korean("공정 가스")      # 공백 있음
        assert not is_short_korean("chamber")       # 한글 아님
        assert not is_short_korean("플라즈마 진단")   # 공백 있음

    def test_no_short_korean_on_task_axis(self, asset, aliases):
        """결정 ③ — 예외목록에 없는 한글 단문은 태스크 축으로 가지 않는다."""
        exc = {norm(t) for t in aliases.get("_exceptions_short_ko_task_axis", [])}
        offenders = [
            e for e in asset["profiles"]["patent-text"]["entries"]
            if e["concept_type"] in TASK_AXES
            and is_short_korean(e["surface"]) and e["surface"] not in exc
        ]
        assert not offenders, offenders[:5]

    def test_blocked_pairs_are_reported(self, asset):
        """차단은 조용히 일어나면 안 된다 — 무엇을 버렸는지 남는다."""
        assert asset["profiles"]["patent-text"]["blocked"]


class TestAmbiguity:
    def test_ambiguous_surfaces_keep_all_candidates(self, asset):
        idx = _index(asset, "patent-text")
        multi = {s: es for s, es in idx.items() if len(es) > 1}
        assert multi, "중의성 있는 표면형이 하나도 없다면 규칙이 죽어 있는 것이다"
        for surface, es in multi.items():
            assert all(e["ambiguous"] for e in es), surface

    def test_candidate_order_is_deterministic(self, asset):
        """성공기준 ③ — 더 특정한 축 우선, 동순위는 node_id 사전순."""
        idx = _index(asset, "patent-text")
        for surface, es in idx.items():
            keys = [(AXIS_RANK.get(e["concept_type"], 99), e["concept_id"]) for e in es]
            assert keys == sorted(keys), surface


class TestHierarchy:
    def test_each_superordinate_has_narrower(self, kg):
        """성공기준 ⑩."""
        parents = {e["dst"] for e in kg["edges"] if e["predicate"] == "BROADER"}
        missing = [nid for nid in SUPERORDINATE if nid not in parents]
        assert not missing, missing

    def test_no_cycles(self, kg):
        """계층에 순환이 있으면 상위 질의가 끝나지 않는다."""
        up = {}
        for e in kg["edges"]:
            if e["predicate"] == "BROADER":
                up.setdefault(e["src"], set()).add(e["dst"])
        for start in list(up):
            seen, stack = set(), [start]
            while stack:
                cur = stack.pop()
                for nxt in up.get(cur, ()):
                    assert nxt != start, f"cycle through {start}"
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)

    def test_broader_endpoints_exist(self, kg):
        ids = {n["id"] for n in kg["nodes"]}
        for e in kg["edges"]:
            if e["predicate"] == "BROADER":
                assert e["src"] in ids and e["dst"] in ids, e


class TestShapeActuallyRejects:
    """실패해야 할 입력이 실패하는가 (CLAUDE.md §2-5b)."""

    def test_missing_narrower_is_rejected(self):
        pyshacl = pytest.importorskip("pyshacl")
        from rdflib import Graph
        from rdflib.namespace import SKOS

        data_path = ROOT / "ontology" / "sdkb-core-data.ttl"
        if not data_path.exists():
            pytest.skip("sdkb-core-data.ttl 미생성 — make convert")
        g = Graph()
        g.parse(str(data_path), format="turtle")

        target = "https://w3id.org/sdkb/data/process/plasma_processing"
        from rdflib import URIRef
        removed = list(g.triples((None, SKOS.broader, URIRef(target))))
        assert removed, "전제가 깨졌다 — plasma_processing 의 하위가 원래 없다"
        for t in removed:
            g.remove(t)

        shapes = Graph()
        shapes.parse(str(ROOT / "validation" / "shapes.ttl"), format="turtle")
        conforms, _, text = pyshacl.validate(g, shacl_graph=shapes, inference="none")
        assert not conforms, "하위를 떼었는데 SHACL 이 통과시켰다 — 게이트가 아니다"
        assert "narrower" in text
