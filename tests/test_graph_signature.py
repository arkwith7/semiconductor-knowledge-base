"""릴리스 서명 계약 — 세는 것은 코드이고, 문서는 그 값을 **따라간다** (R3·R4·R5).

CLAUDE.md §2 (b) 의 "그래프 → 하류" 경계다. 고정하는 계약 셋.

  ① **모든 명명 T-Box 항이 `rdfs:comment` 를 갖는다.** 42곳이 비어 있었고(2026-08-10 보강),
     비어도 SHACL 은 통과하므로 이것을 잡는 층은 여기뿐이다.
  ② **README 두 판의 서명 블록이 생성기 출력과 일치한다.** 손으로 관리했더니 넷이 어긋났다.
  ③ **발행되는 `rdfs:seeAlso` 가 현재 리포 슬러그를 쓴다.** 옛 슬러그면 공개 첫날 404 다.

②③ 이 테스트인 이유 — 사람이 `make signature` 를 잊는 것이 정상이기 때문이다. 잊어도
CI 가 잡으면 어긋남이 릴리스에 도달하지 못한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rdflib import Graph, RDF, RDFS, OWL
from rdflib.term import BNode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from config.namespaces import LEGACY_REPO_SLUG, REPO_SLUG  # noqa: E402
from report_graph_signature import (  # noqa: E402
    MARK_BEGIN, MARK_END, TBOX_MODULES, build, render_block,
)


@pytest.mark.parametrize("module", TBOX_MODULES)
def test_모든_명명_항이_주석을_갖는다(module):
    path = ROOT / "ontology" / f"{module}.ttl"
    if not path.exists():
        pytest.skip(f"{module}.ttl 이 아직 생성되지 않았다 — build_owl.py 를 먼저 돌린다")
    g = Graph()
    g.parse(path, format="turtle")
    missing = [
        str(s)
        for t in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty)
        for s in g.subjects(RDF.type, t)
        if not isinstance(s, BNode) and (s, RDFS.comment, None) not in g
    ]
    assert missing == [], (
        f"{module}: 이름만 있고 뜻이 없는 항 {len(missing)}개 — 외부인은 이 술어의 방향을 "
        f"알 수 없다: {sorted(missing)}")


def test_README_서명_블록이_최신이다():
    """`make signature-inject` 를 잊었으면 여기서 실패한다."""
    block = render_block(build())
    for name in ("README.md", "README.ko.md"):
        s = (ROOT / name).read_text(encoding="utf-8")
        assert MARK_BEGIN in s and MARK_END in s, f"{name}: 서명 블록 마커가 없다"
        start, end = s.index(MARK_BEGIN), s.index(MARK_END) + len(MARK_END)
        assert s[start:end] == block, (
            f"{name}: 서명 블록이 낡았다 — `make signature-inject` 를 돌려라")


def test_발행되는_seeAlso_가_현재_리포를_가리킨다():
    path = ROOT / "ontology" / "sdkb-core.ttl"
    if not path.exists():
        pytest.skip("sdkb-core.ttl 이 아직 생성되지 않았다")
    g = Graph()
    g.parse(path, format="turtle")
    urls = [str(o) for o in g.objects(None, RDFS.seeAlso) if "github.com" in str(o)]
    assert urls, "문서를 가리키는 seeAlso 가 하나도 없다 — 발행된 그래프가 자기 설명을 잃었다"
    assert not [u for u in urls if LEGACY_REPO_SLUG in u], (
        f"옛 리포 슬러그가 발행된다 — 공개 첫날 404: {urls}")
    assert all(REPO_SLUG in u for u in urls), urls
