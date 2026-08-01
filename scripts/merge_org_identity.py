"""회사 하나 = IRI 하나. 역할별로 갈라져 있던 조직 노드 id 를 `organization:` 으로 통일한다.

SDKB 는 같은 회사에 그 회사가 맡은 **역할에 따라 다른 id** 를 줬다 — 큐레이션된 기업은
`org:`, 장비 공급사는 `vendor:`, 특허 출원인은 `organization:` (build_abox_patents.py).
convert_rdf.py 는 `prefix:local` 을 그대로 `data/prefix/local` IRI 로 옮기므로, 역할이
IRI 에 인코딩되면서 **같은 회사가 여러 노드로 갈라졌다**.

역할은 이미 rdf:type(`ont:Organization` · `ont:Vendor`)으로 모델링돼 있다 — 삼성은 이미
두 타입을 다 갖는다. 그러니 IRI 접두사는 타입과 중복이면서, 정체성만 깬다.

갈라진 채로 두면 IP-R&D 의 핵심 질의가 **에러 없이 0행**을 낸다:
`vendor/lam_research` 가 장비를 공급하고 `organization/lam_research` 가 특허 19건을 갖는데,
"이 회사가 공급하는 장비와 이 회사의 특허"를 함께 묻는 순간 두 노드가 조인되지 않는다.

병합 근거는 `mappings/org_identity_crosswalk.csv` 에 한 행씩 명시한다 — 별개 법인을
기업집단 단위로 접은 6건(SCREEN·ASM·3M …)이 섞여 있으므로, 추론이 아니라 **검토 가능한
표**로 남긴다. 근거 없는 병합은 하지 않는다.

`vendor:generic` 은 병합하지 않는다 — canonical_name 이 "Generic Equipment" 인
**플레이스홀더**이지 실재 회사가 아니다. 실재하지 않는 것에 정체성을 주지 않는다.

멱등이다. 실행 뒤 `make convert` 로 sdkb-core-data.ttl 을 다시 만들어야 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
KB = ROOT / "data" / "semiconductor_v0_3.json"
ALIASES = ROOT / "mappings" / "abox_term_aliases.json"
CROSSWALK = ROOT / "mappings" / "org_identity_crosswalk.csv"

# 노드 id 를 **살아있는 참조**로 담는 자리. edges 는 양끝, synonyms 는 node_id,
# Equipment 는 props.vendor_id 로 공급사를 비정규화해 들고 있다.
#
# provenance.source_id 는 **고치지 않는다.** 그것은 이 노드가 어디서 왔는지의 기록이지
# 그래프 참조가 아니다 — equipment:amat_endura 는 실제로 AMAT 카탈로그의
# `vendor:applied_materials/AMAT_Endura` 항목에서 왔다. 새 id 로 고쳐 쓰면 출처가 거짓이 된다.
# (convert_rdf.py 는 props 도 source_id 도 RDF 로 내보내지 않는다 — 그래도 원천의 dangling
#  참조는 나중에 그것을 읽는 빌더를 조용히 깨뜨리므로 살아있는 참조는 고친다.)
REF_FIELDS = {"edges": ("src", "dst"), "synonyms": ("node_id",)}


def _rewrite_kb(rename: dict[str, str]) -> tuple[int, int]:
    kb = json.loads(KB.read_text(encoding="utf-8"))
    ids = {n["id"] for n in kb["nodes"]}

    # 목표 id 가 JSON 안에 이미 있으면 rename 이 아니라 노드 병합이 된다. 지금 원천에는
    # `organization:` 노드가 없어 그럴 일이 없지만, 조용히 덮어쓰는 것을 막으려면 확인해야 한다.
    collide = {rename[k] for k in rename if k in ids} & ids
    if collide:
        raise SystemExit(f"ERROR: 목표 id 가 이미 존재한다 — 수동 병합 필요: {sorted(collide)}")

    n_nodes = n_refs = 0
    for n in kb["nodes"]:
        if n["id"] in rename:
            n["id"] = rename[n["id"]]
            n_nodes += 1
        vid = (n.get("props") or {}).get("vendor_id")
        if vid in rename:
            n["props"]["vendor_id"] = rename[vid]
            n_refs += 1

    for coll, fields in REF_FIELDS.items():
        for item in kb.get(coll, []):
            for f in fields:
                if item.get(f) in rename:
                    item[f] = rename[item[f]]
                    n_refs += 1

    KB.write_text(json.dumps(kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n_nodes, n_refs


def _rewrite_aliases(rename: dict[str, str]) -> int:
    """별칭 테이블의 타깃도 옮긴다 — 죽은 id 를 가리키면 별칭이 조용히 버려진다."""
    al = json.loads(ALIASES.read_text(encoding="utf-8"))
    n = 0
    for term, target in al.items():
        if isinstance(target, str) and target in rename:
            al[term] = rename[target]
            n += 1
        elif isinstance(target, list):
            for i, t in enumerate(target):
                if t in rename:
                    target[i] = rename[t]
                    n += 1
        elif isinstance(target, dict):
            # 프로파일 객체(CR-007). 여기를 빼먹으면 개명 후 죽은 id 를 가리키는
            # 별칭이 프로파일 안에 조용히 남는다 — 이 함수가 존재하는 이유 그대로.
            for prof, t in list(target.items()):
                if isinstance(t, str) and t in rename:
                    target[prof] = rename[t]
                    n += 1
    if n:
        ALIASES.write_text(json.dumps(al, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def main() -> int:
    xw = pd.read_csv(CROSSWALK)
    rename = dict(zip(xw["from_id"], xw["to_id"], strict=True))

    n_nodes, n_refs = _rewrite_kb(rename)
    n_alias = _rewrite_aliases(rename)

    if not (n_nodes or n_refs or n_alias):
        print("이미 통일돼 있다 — 바꿀 것 없음.")
        return 0

    n_merge = int((xw["kind"] == "merge").sum())
    print(f"노드 id {n_nodes}개 통일 (병합 {n_merge} · 스킴 rename {len(rename) - n_merge}) · "
          f"그래프 참조 {n_refs}건 · 별칭 타깃 {n_alias}건 갱신")
    print("다음: make convert && make abox-patents && make abox-vendors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
