"""청구항 분해 중심축 데이터셋을 pyoxigraph 온디스크 스토어로 적재한다.

이 데이터셋(11.6M 트리플)은 선행기술조사·IP-R&D 태스크의 기질이며, 분석 그래프
(G₀/G₁/G₂)에 **병합하지 않는다** — H1 엣지 중립이다. rdflib 인메모리는 피크 15GB·4분이라
OOM 위험이 있어(실측 2026-07-23) Oxigraph 온디스크로만 다룬다.

소스는 상류 SDKB 이므로, vendor 와 같은 규율로 **빌드 시점의 sha256·SDKB 커밋을 PROVENANCE
에 핀**한다 — 그 뒤로는 스토어가 자족적이며 런타임에 ~/Dev/sdkb 를 읽지 않는다.

    python -m sdkb_paper.ontology.central_axis build      # 스토어 재빌드
    python -m sdkb_paper.ontology.central_axis verify     # 서명·샘플질의 확인
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from pyoxigraph import RdfFormat, Store

from .. import config


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sdkb_commit() -> str:
    out = subprocess.run(
        ["git", "-C", str(config.SDKB_HOME), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def build() -> None:
    """소스 TTL(ABox+TBox)을 온디스크 Oxigraph 스토어로 결정적 재빌드하고 출처를 핀한다."""
    src, tbox = config.CENTRAL_AXIS_SRC, config.CENTRAL_AXIS_TBOX
    if not src.exists():
        raise FileNotFoundError(f"소스 없음: {src} (SDKB_HOME 확인)")

    store_path = config.CENTRAL_AXIS_STORE
    if store_path.exists():
        shutil.rmtree(store_path)  # 결정적 재빌드 — 잔여 상태 없이 새로 만든다
    store_path.parent.mkdir(parents=True, exist_ok=True)

    store = Store(path=str(store_path))
    for f in (tbox, src):  # TBox 먼저, 그다음 대용량 ABox
        if f.exists():
            with open(f, "rb") as fh:
                store.bulk_load(fh, format=RdfFormat.TURTLE)
    n = len(store)

    prov = {
        "dataset": "claim-decomposition central axis (분석 그래프 미병합)",
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "sdkb_commit": _sdkb_commit(),
        "source_files": {
            src.name: {"sha256": _sha256(src), "bytes": src.stat().st_size},
            tbox.name: {"sha256": _sha256(tbox), "bytes": tbox.stat().st_size},
        },
        "store_path": str(store_path.relative_to(config.ROOT)),
        "triples": n,
        "loader": "pyoxigraph on-disk (rdflib 금지 — OOM)",
    }
    config.CENTRAL_AXIS_PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    config.CENTRAL_AXIS_PROVENANCE.write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"빌드 완료: {n:,} 트리플 → {store_path}")
    print(f"출처 핀: {config.CENTRAL_AXIS_PROVENANCE}")


def open_store() -> Store:
    """질의용 스토어를 연다. 새 세션은 이 함수로 접근한다(rdflib 로 파싱하지 말 것)."""
    if not config.CENTRAL_AXIS_STORE.exists():
        raise FileNotFoundError("스토어 없음 — 먼저 `python -m sdkb_paper.ontology.central_axis build`")
    return Store(path=str(config.CENTRAL_AXIS_STORE))


def verify() -> None:
    """서명과 대표 질의로 스토어가 정상인지 확인한다."""
    store = open_store()
    print(f"트리플: {len(store):,}")
    checks = {
        "PriorArtJudgment": "SELECT (COUNT(*) AS ?n) WHERE { ?j a <https://w3id.org/sdkb/ont/PriorArtJudgment> }",
        "ClaimFeature": "SELECT (COUNT(*) AS ?n) WHERE { ?f a <https://w3id.org/sdkb/ont/ClaimFeature> }",
        "정답지 feature 조인": (
            "PREFIX ont: <https://w3id.org/sdkb/ont/> "
            "SELECT (COUNT(*) AS ?n) WHERE { ?j a ont:PriorArtJudgment ; ont:aboutClaim ?c . ?c ont:hasFeature ?f }"
        ),
    }
    for name, q in checks.items():
        rows = list(store.query(q))
        print(f"  {name}: {rows[0][0].value}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "verify": verify}[cmd]()
