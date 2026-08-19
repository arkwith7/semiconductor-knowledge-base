"""SDKB 온톨로지 스냅샷 vendoring.

근간 온톨로지(semiconductor-knowledge-base)를 이 repo 로 **얼려서** 가져온다.
살아있는 워킹트리를 참조하지 않는 이유:

1. H1(보강 전/후 커버리지 비교)의 baseline 이 움직이면 재현이 불가능하다.
2. 필요한 TTL(sdkb-core.ttl, sdkb-core-data.ttl)은 SDKB repo 의 .gitignore 대상 —
   즉 git 에 없는 **빌드 산출물**이다. submodule/pip 로는 가져올 수 없고,
   SDKB 쪽에서 `make owl convert` 로 생성한 결과를 복사하는 수밖에 없다.

그래서 스냅샷을 `data/external/sdkb/` 에 커밋하고, 출처(커밋 SHA)와 무결성(sha256)을
PROVENANCE.json 에 박아둔다. SDKB 를 갱신하려면 이 스크립트를 재실행하고 MANIFEST 를 갱신한다.

라이선스: SDKB 는 CDLA-Permissive-2.0 — 재배포 가능. (KIPRIS 원문 금지 규칙과 무관)

CLI:  python -m sdkb_paper.ontology.vendor [--sdkb-home PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sdkb_paper.config import EXTERNAL_SDKB, PROCESSED, SDKB_HOME

# vendor 대상: (SDKB 내 상대경로, 역할)
#
# SIRP 특허 ABox(sdkb-abox-patents.ttl)를 **포함한다**. 예전에는 baseline 을 특허 0건으로
# 두려고 제외했지만, 그러면 모든 공정 단계에서 C₀(s)=0 이 되어 H1 이 기각될 수 없는 자명한
# 가설이 된다. G₀ 는 "현행 SDKB" 여야 한다 (CLAUDE.md §0).
VENDOR_FILES: list[tuple[str, str]] = [
    ("ontology/sdkb-core.ttl", "TBox: 제조 코어(Process/SubProcess/Equipment/Material/Device/FailureMode)"),
    ("ontology/sdkb-patent.ttl", "TBox: 특허 모듈(Patent/IPC/realizesProcess/concernsDevice)"),
    ("ontology/sdkb-foresight.ttl", "TBox: 예측 모듈(Scenario/Signal/STEEPVE) — H2 의 기반"),
    ("ontology/sdkb-core-data.ttl", "ABox: 도메인 인스턴스 (공정 20 · 디바이스 31 …)"),
    ("ontology/sdkb-abox-patents.ttl", "ABox: SIRP 거절특허 1,000건 — H1 의 before 를 구성한다"),
    # CR-012(D-27)가 낸 B층 확증분할 질의 200. **인용 간선은 일부러 없다** — 있으면 그 간선이
    # 곧 봉인 qrel 의 내용이라 하류 봉인이 무의미해진다(CR-008 비목표 ⓐ · CR-011 ⓓ).
    # 층 구분은 술어가 아니라 **파일과 prov:wasGeneratedBy** 로 한다 → T-Box 델타 0.
    # PLAN-045 D5: 이 목록과 `baseline.BASELINE_PARTS` 는 **별개다.** 하나만 고치면
    # 스냅샷에는 들어오고 G₀ 에는 안 들어와 `is_query` 가 1,000 그대로다.
    ("ontology/sdkb-abox-b-layer-queries.ttl",
     "ABox: B층 제2 확증분할 질의 200건 (CR-012 · 인용 간선 0) — 판독 B 의 질의 측"),
    ("ontology/sdkb-abox-experts-problems.ttl", "ABox: 인력 110 · 소부장 실문제 226 — 인력·문제 축"),
    ("ontology/sdkb-abox-vendors.ttl", "ABox: KSIA 회원사 326 — 소부장 벤더 축"),
    ("ontology/sdkb-abox-prior-art.ttl", "ABox: 심사관 인용 선행기술 3,034 노드(CitedPatent) + 개념링크 — 선행기술조사 정답지"),
    ("ontology/sdkb-commercialization.ttl", "TBox+ABox: 상용화 축(TRL·라이선싱·spinoff)"),
    ("ontology/sdkb-rbv.ttl", "TBox: 자원기반관점(VRIO·역량·진입장벽) — 핵심자원조합 축"),
    ("ontology/sdkb-governance.ttl", "TBox: 규제 코어(hasJurisdiction·controlLevel·subjectToControl·관할개념·EARRule 앵커) — RQ3 수출통제"),
    ("ontology/sdkb-governance-kr.ttl", "TBox: KR 규제(NationalCoreTechnology·designatedAsNCT·산업기술보호법)"),
    ("ontology/sdkb-governance-us-instances.ttl", "ABox: US EAR/CCL 수출통제 8건 + G₀ 개념 연결"),
    ("ontology/sdkb-governance-kr-instances.ttl", "ABox: KR-ITPA 국가핵심기술 12건 + G₀ 개념 연결"),
    # CR-007 이 낸 개념 매핑 사전. 이것이 vendor 되지 않아 하류가 CR-007 을 읽지 못했고,
    # 그래서 O 대 O′ 의 ΔR₁₀₀ 이 정의상 0 이 되어 H2 가 공허하게 통과했다(D-16·D-19).
    ("mappings/concept_mapping.json",
     "매핑: 특허 본문 → 개념 링크 사전(patent-text 프로파일) — 개념 적용기의 입력"),
    # CR-007(D-16)이 함께 낸 별칭 사전. 하류에 아직 독자는 없지만, 이것이 없으면 상류가 만든
    # 개념 링크를 **스냅샷만으로 재현할 수 없다** — 재현 주장의 구멍이라 얼려 둔다.
    # (하류 `mappings/term_aliases.csv` 와 이름이 비슷하나 다른 자산이다 — 그쪽은 구 패러다임.)
    ("mappings/abox_term_aliases.json",
     "매핑: A-Box 별칭 사전 — 상류 개념 링크 생성의 표층형 원천(재현용)"),
    # CR-017 이 낸 청구항 한정요소 투영. 899 MB TTL 은 벤더 대상이 될 수 없어(§1-5) 하류는
    # `central_axis` oxstore 우회로로 feature 를 읽어 왔는데, 그 sidecar 에는 **개념 열이 없고**
    # 원문 때문에 커밋되지 않으며 신선한 클론은 재현하지 못한다(상류에서도 TTL 이 gitignore).
    # 이 파일은 원문 0 · 5.6 MB · 개념 링크 529,151 이라 셋을 한꺼번에 푼다.
    # **읽는 코드는 아직 없다** — 편입은 스냅샷까지이고 소비는 새 방법이다(§2 전체).
    ("mappings/claim_features.parquet",
     "매핑: 청구항 한정요소 투영 1,306,191행 (CR-017 · 원문 0 · featureConcept 529,151)"),
    ("data/semiconductor_v0_3.json", "ABox 의 커밋된 원천(=재현 기준점)"),
    ("data/schema_report.json", "원천의 sha256 + 노드/엣지 카운트"),
]

# 산출물이 커밋된 원천과 정합한지 확인하는 기준
SOURCE_JSON = "data/semiconductor_v0_3.json"
SCHEMA_REPORT = "data/schema_report.json"

# 특허 전문을 담아 gitignore 되는 스냅샷 (CLAUDE.md §1-5). verify_snapshot 은 이 파일들의
# **부재만** 관용한다 — 신선한 클론·CI 에는 정당하게 없기 때문이다(논문 §7.2 재현성 주장).
#
# **왜 상수인가.** 이 플래그는 2026-07-30(04ab68b)에 PROVENANCE.json 에 **손으로** 들어갔고,
# vendor() 는 그것을 쓸 줄 몰랐다. 그래서 다음 `make vendor`(fa16f2f)가 플래그를 조용히
# 지웠고, 신선한 클론의 L0 는 다시 깨졌다 — 통합 테스트가 2026-08-01 에 그것을 잡았다.
# 사람이 넣은 메타데이터는 다음 재생성에서 사라진다. 코드가 박아야 남는다.
LICENSE_RESTRICTED: frozenset[str] = frozenset({
    "sdkb-abox-patents.ttl",      # SIRP 거절특허 1,000건 (청구항·초록 원문)
    "sdkb-abox-prior-art.ttl",    # 심사관 인용 선행기술 3,034 노드
    # B층 확증분할 질의 200 (CR-012). `abstractText`·`firstClaimText` 원문을 담으므로
    # 앞의 둘과 같은 등급이다 — 커밋하지 않는다(CLAUDE.md §1-5 · KIPRIS 비재배포).
    "sdkb-abox-b-layer-queries.ttl",
})

# --- 파생 스냅샷: 거절근거 법조 (원고 §5.2·§6.4 하위집단 라벨 전용) --------------------
#
# 왜 파생인가: 상류 `data/patents/rejected_patents_meta.parquet` 은 title/abstract/claim1 원문을
# 담고 있어 **커밋할 수 없다**(CLAUDE.md §1-5). 그래서 파일을 통째로 vendor 하지 않고 식별자 +
# 법조 라벨만 추출해 CSV 로 얼린다. 원문 0열.
#
# 왜 필요한가: TTL 스냅샷(sdkb-abox-patents.ttl)은 `§1×n|§2×m` 문자열을 `Rejection_Inventiveness`
# 하나로 접어 **신규성(제29조 제1항) 축을 잃는다**(실측 2026-07-27: 상류 원본 신규성 14건 →
# TTL 0건). 상류 결함이며 별건으로 고칠 것 — 이 CSV 는 그때까지의 라벨 원천이 아니라
# **원본이 가진 해상도를 잃지 않고 옮기는 통로**다.
#
# **누출 규율(CLAUDE.md §1-4):** 이 라벨은 질의(거절특허) 속성이며 **하위집단 분해에만** 쓴다.
# 순위 함수 입력이 아니다(oracle-free 주모드 — ablation A5 가 구조적 0 인 것과 같은 이유).
# 인용 엣지별 법조(cited_doc_id 동반)는 정답 표면을 넓히므로 **의도적으로 vendor 하지 않는다**.
REJECTION_SRC = "data/patents/rejected_patents_meta.parquet"
REJECTION_OUT = "rejection_basis.csv"
LEGAL_BASIS_NAMES = {"§1": "novelty", "§2": "inventiveness"}   # 특허법 제29조 제1항·제2항

# --- 파생 스냅샷: 거절근거 조항 인스턴스 (CR-004R `84ea514`) --------------------------
#
# 왜 파생인가: 원천 `ontology/sdkb-abox-claim-features.ttl` 은 **888MB** 다. 통째로 vendor 하면
# 매 `make vendor` 가 888MB 를 복사하고, 이미 이 파일을 sha256 으로 얼려 두는 별도 경로
# (`central_axis.py` → `data/external/sdkb-central-axis/PROVENANCE.json` + oxstore)와 이중화된다.
# 그래서 rejection_basis.csv 와 같은 패턴을 쓴다 — 필요한 부분만 뽑아 작은 CSV 로 얼리고,
# **원본 sha256 을 PROVENANCE 에 남겨** 출처를 잃지 않는다.
#
# 왜 필요한가: CR-004R 이 채운 `ont:RejectionReason` 2,749건은 **조항(項) 단위 해상도**를 갖는다.
# 기존 rejection_basis.csv 는 `§1×n|§2×m` 을 신규성/진보성 두 축으로만 펼치므로 제42조(기재불비)
# 계열과 회차(noticeRound)를 잃는다. 이 CSV 는 그 해상도를 옮기는 통로다.
#
# **누출 규율(CLAUDE.md §1-4):** 질의(거절특허) 속성이며 **하위집단 분해 전용**이다. 순위 함수
# 입력이 아니다. 인용 문헌 식별자는 담지 않는다 — 담으면 정답 표면이 넓어진다.
# **원문 0열**(청구항·초록 텍스트 없음)이라 커밋 가능하다(§1-5).
REJECTION_REASON_SRC = "ontology/sdkb-abox-claim-features.ttl"
REJECTION_REASON_OUT = "rejection_reasons.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(sdkb_home: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(sdkb_home), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _verify_source(sdkb_home: Path) -> dict:
    """빌드 산출물이 커밋된 원천 JSON 에서 나온 것인지 검증.

    schema_report.json 에 기록된 sha256 != 실제 JSON sha256 이면, 산출물이 낡았거나
    원천이 바뀐 것 — 그대로 vendor 하면 출처가 거짓이 된다.
    """
    src = sdkb_home / SOURCE_JSON
    report = json.loads((sdkb_home / SCHEMA_REPORT).read_text(encoding="utf-8"))
    actual, recorded = sha256(src), report["file_sha256"]
    if actual != recorded:
        raise SystemExit(
            f"[vendor] 원천 불일치: {SOURCE_JSON} 의 sha256={actual[:12]}… 인데 "
            f"schema_report 기록은 {recorded[:12]}… 이다.\n"
            f"         SDKB 에서 `make owl convert` 로 산출물을 다시 빌드한 뒤 재실행할 것."
        )
    return report


def verify_freshness(dest: Path = EXTERNAL_SDKB, derived: Path | None = None) -> list[str]:
    """L0 신선도 — 산출물이 입력보다 낡지 않았는가. **SDKB 원본 없이** 검사한다.

    sha256(=verify_snapshot)은 "바뀌지 않았음"만 보장하고 "옳게 빌드되었음"은 보장하지 않는다.
    2026-07-14 사고가 정확히 그 틈으로 났다 — 해시는 내내 맞았고 L1–L3 는 내내 통과했는데
    공정 어휘 복원 이전에 빌드된 특허 ABox 가 얼려져 H1 의 before 가 낮게 잡혔다.
    그래서 신선도는 별도 층이어야 한다 (논문 §7.2).

    상류 워킹트리는 CI 에 없으므로 오프라인에서 검사 가능한 두 가지를 본다:

    (a) **이행 증명** — vendor 가 `_reject_stale_artifacts()` 를 실제로 돌렸는지.
        PROVENANCE 의 freshness 블록이 그 증거다. 블록이 없으면 그 스냅샷은 신선도 검사를
        거치지 않고 얼려진 것이고, 그것이 사고 당시의 상태다.
    (b) **파생 산출물 신선도** — baseline(graph_v0)이 스냅샷보다 새로운가.
        스냅샷을 갱신하고 `make baseline` 을 잊으면 분석이 옛 그래프를 읽는다.

    상류가 있을 때의 강한 검사(입력 mtime 대조)는 `_reject_stale_artifacts()` 가 맡는다 —
    이 함수는 그 검사가 남긴 서명을 검증할 뿐이다.
    """
    problems: list[str] = []
    prov_path = dest / "PROVENANCE.json"
    if not prov_path.exists():
        return [f"PROVENANCE.json 이 없다: {prov_path}"]
    prov = json.loads(prov_path.read_text(encoding="utf-8"))

    fresh = prov.get("freshness")
    if not isinstance(fresh, dict) or not fresh.get("checked"):
        problems.append(
            "PROVENANCE 에 freshness 이행 증명이 없다 — 이 스냅샷은 신선도 검사를 거치지 않고 "
            "얼려졌다. sha256 은 '바뀌지 않았음'만 보장하지 '옳게 빌드되었음'을 보장하지 않는다.\n"
            "         `make vendor` 로 재vendor 하여 증명을 남길 것 (상류가 같은 커밋이면 "
            "파일 내용·G₀ 는 바뀌지 않는다)."
        )
    else:
        # 증명이 대상 산출물 전부를 덮는가. 일부만 덮은 증명은 증명이 아니다.
        attested = set(fresh.get("artifacts", {}))
        vendored = {rel for rel, _ in VENDOR_FILES}
        for rel in sorted(ARTIFACT_INPUTS.keys() & vendored):
            if rel not in attested:
                problems.append(f"freshness 증명이 {rel} 을 덮지 않는다")
        if prov.get("source_dirty"):
            problems.append(
                "vendor 시점 상류 워킹트리가 dirty 였다 — 스냅샷이 source_commit 만으로 재현되지 않는다"
            )

    # (b) 파생 산출물이 스냅샷보다 낡았는가.
    derived = derived if derived is not None else (PROCESSED / "graph_v0.ttl")
    if derived.exists():
        newest = max((p.stat().st_mtime for p in dest.glob("*.ttl")), default=0.0)
        if derived.stat().st_mtime < newest:
            problems.append(
                f"{derived.name} 이 스냅샷보다 낡았다 — `make baseline` 을 다시 실행할 것. "
                "낡은 baseline 위에서 나온 H1 의 before 는 거짓이다."
            )
    return problems


def verify_snapshot(dest: Path = EXTERNAL_SDKB) -> list[str]:
    """커밋된 스냅샷이 PROVENANCE.json 의 sha256 과 여전히 일치하는지 검사.

    SDKB 원본이 필요 없다 — 커밋된 파일만 본다. 그래서 CI 에서 매 push 마다 돌 수 있다.
    스냅샷이 제자리에서 수정되면(누가 TTL 을 손으로 고치면) baseline 의 출처가 거짓이 되고
    H1 의 before 가 조용히 움직인다. 이 검사가 그걸 막는다.

    **라이선스 제한 파일**(`license_restricted: true`)은 특허 전문을 담아 gitignore 되므로
    (CLAUDE.md §1.4) 신선한 클론/CI 에는 없다. 이 부재는 실패가 아니다 — sha256 은 파일이
    있을 때만 검사하고, 없으면 관용한다(무결성은 유지, 재현성 게이트는 통과). 손으로 고친
    변조는 파일이 있을 때 여전히 잡힌다.

    문제 목록을 반환한다 (빈 리스트 = 정상). 라이선스 제한 파일의 부재는 문제가 아니며,
    그 가시성은 별도 함수 license_restricted_absences() 가 제공한다 — CLI 가 정보성으로 출력한다.
    """
    prov_path = dest / "PROVENANCE.json"
    if not prov_path.exists():
        return [f"PROVENANCE.json 이 없다: {prov_path} — `make vendor` 를 먼저 실행할 것."]

    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    problems = []
    for entry in prov["files"]:
        f = dest / entry["file"]
        if not f.exists():
            # 라이선스 제한 파일은 gitignore 되어 클론/CI 에 정당하게 없다 — 관용한다.
            # (부재의 가시성은 license_restricted_absences() 가 별도로 제공한다.)
            if not entry.get("license_restricted"):
                problems.append(f"{entry['file']}: 스냅샷에 파일이 없다")
            continue
        actual = sha256(f)
        if actual != entry["sha256"]:
            problems.append(
                f"{entry['file']}: sha256 불일치 — 기록 {entry['sha256'][:12]}… / 실제 {actual[:12]}…"
            )

    # PROVENANCE 가 모르는 TTL 이 스냅샷에 섞여 있으면 baseline 이 조용히 오염될 수 있다.
    known = {e["file"] for e in prov["files"]} | {"PROVENANCE.json"}
    for stray in sorted(p.name for p in dest.glob("*.ttl") if p.name not in known):
        problems.append(f"{stray}: PROVENANCE 에 없는 파일이 스냅샷에 있다 (SIRP ABox 유입?)")

    return problems


def license_restricted_absences(dest: Path = EXTERNAL_SDKB) -> list[str]:
    """라이선스 제한 파일 중 로컬에 **없는** 것의 파일명 목록.

    verify_snapshot 은 이 부재를 관용(문제 아님)하므로, 게이트를 통과시키되 "이 스냅샷은
    로컬에서 불완전하다 — `make vendor` 로 재생성하라"를 사용자에게 알릴 창구가 필요하다.
    빈 목록 = 라이선스 제한 파일이 전부 로컬에 있음.
    """
    prov_path = dest / "PROVENANCE.json"
    if not prov_path.exists():
        return []
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    return [
        e["file"]
        for e in prov["files"]
        if e.get("license_restricted") and not (dest / e["file"]).exists()
    ]


# 산출물 → 그것을 만드는 입력(생성기 + 원천 데이터). make 의 의존관계와 같은 뜻이다.
# 입력이 산출물보다 새로우면 그 산출물은 낡은 것이다.
ARTIFACT_INPUTS: dict[str, list[str]] = {
    "ontology/sdkb-core.ttl": ["scripts/build_owl.py"],
    "ontology/sdkb-core-data.ttl": [
        "scripts/convert_rdf.py", "data/semiconductor_v0_3.json",
    ],
    "ontology/sdkb-abox-patents.ttl": [
        "scripts/build_abox_patents.py",
        "data/patents/rejected_patents_meta.parquet",
        "data/patents/prior_art_edges.parquet",
    ],
    "ontology/sdkb-abox-experts-problems.ttl": [
        "scripts/build_abox_experts_problems.py", "data/semiconductor_v0_3.json",
    ],
    "ontology/sdkb-abox-vendors.ttl": [
        "scripts/build_abox_vendors_ksia.py",
        "data/vendors/ksia_member_industry_list_20260714.csv",
        "ontology/sdkb-abox-patents.ttl",
    ],
    "ontology/sdkb-abox-prior-art.ttl": [
        "scripts/build_prior_art_pairs.py",
    ],
    # 규제 인스턴스: seed 스크립트 + 마스터 JSON + 사전동결 크로스워크에서 생성된다.
    # core-data 도 의존이다 — 링크 대상 개념이 사라지면 seed 의 검증이 실패해야 한다.
    "ontology/sdkb-governance-us-instances.ttl": [
        "scripts/seed_compliance_governance.py",
        "data/compliance/us_standards_v1.json",
        "data/compliance/concept_control_crosswalk.csv",
        "ontology/sdkb-core-data.ttl",
    ],
    "ontology/sdkb-governance-kr-instances.ttl": [
        "scripts/seed_compliance_governance.py",
        "data/compliance/kr_standards_v1.json",
        "data/compliance/concept_control_crosswalk.csv",
        "ontology/sdkb-core-data.ttl",
    ],
}


def _reject_stale_artifacts(sdkb_home: Path) -> dict:
    """입력보다 오래된 빌드 산출물을 거부한다.

    이 가드가 없어서 실제로 사고가 났다 (2026-07-14). vendor 대상 TTL 중 다수는 상류에서
    **gitignore 되는 빌드 산출물**이라 git 이 지켜주지 않는다. 그런데 vendor 는 파일이
    존재하는지만 보고 디스크에 있는 것을 그대로 복사했다. 그 결과 공정 어휘 복원
    (SDKB `ad7fe3d`, 공정 20 → 49) **이전에 빌드된** sdkb-abox-patents.ttl 이 그대로 얼려졌고,
    복원된 네 단계(annealing·metallization·oxidation·passivation)는 실제로 특허가 있는데도
    G₀ 에서 C₀(s)=0 으로 기록됐다 — **H1 의 before 가 낮게 잡혀 검정이 실제보다 쉬웠다.**

    PROVENANCE 의 sha256 은 이것을 못 잡는다: 해시는 파일이 *바뀌지 않았음*만 보장하지
    *옳게 빌드됐음*을 보장하지 않는다.
    """
    stale = []
    attested: dict[str, list[dict]] = {}
    for rel, inputs in ARTIFACT_INPUTS.items():
        art = sdkb_home / rel
        if not art.exists():
            continue
        built = art.stat().st_mtime
        seen = []
        for dep in inputs:
            src = sdkb_home / dep
            if src.exists() and src.stat().st_mtime > built:
                stale.append(f"{rel}  ← {dep} 가 더 새롭다")
            if src.exists():
                seen.append({"input": dep, "sha256": sha256(src)})
        attested[rel] = seen

    if stale:
        raise SystemExit(
            "[vendor] 빌드 산출물이 입력보다 낡았다 — 최신 어휘·데이터가 반영되지 않았다.\n  "
            + "\n  ".join(stale)
            + "\n\n  스냅샷의 sha256 은 '바뀌지 않았음'만 보장하지 '옳게 빌드됐음'을 보장하지 않는다.\n"
            f"  cd {sdkb_home} && make owl convert abox abox-patents abox-vendors"
        )

    # 검사를 통과했다는 사실 자체를 스냅샷에 남긴다 — 상류가 없는 CI 에서 L0 가 검증할 증거다.
    return {
        "checked": True,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifacts": attested,
    }


def _derive_rejection_basis(sdkb_home: Path, dest: Path) -> dict | None:
    """상류 거절특허 메타 → 식별자 + 법조 라벨 CSV (원문 0열). 원천 부재면 None.

    `rejection_legal_bases` 는 `"§1×2|§2×3"` 형식(법조×해당 청구항 수). 이를 조항별 카운트로
    펼치고 boolean 플래그를 붙인다. 결정적(정렬·고정 열 순서) — 재실행하면 같은 sha256.
    """
    import csv
    import re

    src = sdkb_home / REJECTION_SRC
    if not src.exists():
        return None
    import pandas as pd

    df = pd.read_parquet(src, columns=["patent_id", "rejection_legal_bases",
                                       "has_rejection_structured"])
    rows = []
    for r in df.itertuples(index=False):
        counts: dict[str, int] = {}
        for tok in str(r.rejection_legal_bases or "").split("|"):
            m = re.match(r"§(\d+)×(\d+)$", tok.strip())
            if m:
                counts[f"§{m.group(1)}"] = counts.get(f"§{m.group(1)}", 0) + int(m.group(2))
        rows.append({
            "doc_id": str(r.patent_id).replace("patent:", ""),
            "has_novelty": int("§1" in counts),
            "has_inventiveness": int("§2" in counts),
            "n_claims_novelty": counts.get("§1", 0),
            "n_claims_inventiveness": counts.get("§2", 0),
            "has_structured": int(bool(r.has_rejection_structured)),
            "raw_bases": str(r.rejection_legal_bases or ""),
        })
    rows.sort(key=lambda x: x["doc_id"])
    out = dest / REJECTION_OUT
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n_nov = sum(r["has_novelty"] for r in rows)
    n_inv = sum(r["has_inventiveness"] for r in rows)
    print(f"[vendor] 거절근거 파생: {len(rows)}건 (신규성 {n_nov} · 진보성 {n_inv}) -> {out.name}")
    return {"file": out.name, "source_path": REJECTION_SRC,
            "role": "파생: 거절근거 법조 라벨(하위집단 전용 · 원문 0열 · 순위 입력 아님)",
            "sha256": sha256(out), "derived": True,
            "counts": {"rows": len(rows), "novelty": n_nov, "inventiveness": n_inv}}


_REASON_IRI = re.compile(r"^<https://w3id\.org/sdkb/data/rejection/([^>]+)> a ont:RejectionReason\b")
_REASON_REF = re.compile(r"<https://w3id\.org/sdkb/data/rejection/([^>]+)>")
_PATENT_SUBJ = re.compile(r"^<https://w3id\.org/sdkb/data/patent/([^>]+)>")
_PRED = re.compile(r"^\s+ont:(groundClause|noticeDate|noticeRound|noticeType|reasonGround)\s+(.+?)\s*[;.]\s*$")


def _ttl_value(raw: str) -> str:
    """`"29-2-"^^xsd:string` · `1` · `ont:Rejection_Inventiveness` → 값 문자열."""
    raw = raw.strip()
    if raw.startswith("ont:"):
        return raw[4:]
    if raw.startswith('"'):
        end = raw.rfind('"')
        return raw[1:end] if end > 0 else raw.strip('"')
    return raw


def _derive_rejection_reasons(sdkb_home: Path, dest: Path) -> dict | None:
    """상류 claim-features TTL(888MB) → 거절근거 조항 인스턴스 CSV. 원천 부재면 None.

    **rdflib 을 쓰지 않는다** — 인메모리 파싱은 피크 15GB·4분이다(config.py:83 실측).
    상류 산출물은 `ont:` 접두 · 4칸 들여쓰기 · 술어 정렬이 고정된 결정적 직렬화라
    한 번의 라인 스캔으로 충분하다. 형식이 바뀌면 개수 검사가 실패시킨다.

    결정적: doc_id·조항·회차로 정렬하고 고정 열 순서로 쓴다 — 재실행하면 같은 sha256.
    """
    import csv

    src = sdkb_home / REJECTION_REASON_SRC
    if not src.exists():
        return None

    rows: dict[str, dict] = {}
    linked: set[str] = set()          # rejectionEvidence 로 Patent 에 걸린 reason 지역명
    subj: str | None = None
    in_patent = False
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            m = _REASON_IRI.match(line)
            if m:
                subj, in_patent = m.group(1), False
                rows[subj] = {"reason_id": subj}
                continue
            if _PATENT_SUBJ.match(line):
                subj, in_patent = None, True
                continue
            if in_patent:
                # Patent 블록 안의 rejectionEvidence 목적어(여러 줄에 걸친다)
                for ref in _REASON_REF.findall(line):
                    linked.add(ref)
                if line.rstrip().endswith("."):
                    in_patent = False
                continue
            if subj is None:
                continue
            p = _PRED.match(line)
            if p:
                rows[subj][p.group(1)] = _ttl_value(p.group(2))
            if line.rstrip().endswith("."):
                subj = None

    if not rows:
        raise SystemExit(
            f"[vendor] {REJECTION_REASON_SRC} 에서 ont:RejectionReason 을 하나도 읽지 못했다 — "
            "상류 직렬화 형식이 바뀐 것이다. 파서를 고치기 전에 스냅샷을 얼리지 않는다."
        )

    out_rows = []
    for rid, r in rows.items():
        doc_id = rid.split("__", 1)[0]
        out_rows.append({
            "doc_id": doc_id,
            "clause": r.get("groundClause", ""),
            "ground": r.get("reasonGround", ""),
            "notice_round": r.get("noticeRound", ""),
            "notice_type": r.get("noticeType", ""),
            "notice_date": r.get("noticeDate", ""),
            "reason_id": rid,
        })
    out_rows.sort(key=lambda x: (x["doc_id"], x["clause"], str(x["notice_round"]), x["reason_id"]))

    out = dest / REJECTION_REASON_OUT
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    n_docs = len({r["doc_id"] for r in out_rows})
    orphan = len(set(rows) - linked)      # Patent 에 걸리지 않은 reason — 있으면 상류 결함이다
    print(f"[vendor] 거절근거 조항 파생: {len(out_rows)}건 · 출원 {n_docs}"
          f"{f' · 미연결 {orphan}' if orphan else ''} -> {out.name}")
    return {
        "file": out.name, "source_path": REJECTION_REASON_SRC,
        "role": "파생: 거절근거 조항 인스턴스(CR-004R · 하위집단 전용 · 원문 0열 · 순위 입력 아님)",
        "sha256": sha256(out), "derived": True,
        "source_sha256": sha256(src), "source_bytes": src.stat().st_size,
        "counts": {"reasons": len(out_rows), "applications": n_docs,
                   "unlinked_to_patent": orphan},
    }


def vendor(sdkb_home: Path = SDKB_HOME, dest: Path = EXTERNAL_SDKB) -> Path:
    if not (sdkb_home / ".git").exists():
        raise SystemExit(f"[vendor] SDKB git repo 를 찾을 수 없음: {sdkb_home}")

    missing = [rel for rel, _ in VENDOR_FILES if not (sdkb_home / rel).exists()]
    if missing:
        raise SystemExit(
            "[vendor] SDKB 에 다음 파일이 없음 (빌드 산출물은 git 에 없다):\n  "
            + "\n  ".join(missing)
            + f"\n\n  cd {sdkb_home} && make owl convert   # 를 먼저 실행할 것"
        )

    freshness = _reject_stale_artifacts(sdkb_home)
    report = _verify_source(sdkb_home)
    commit = _git(sdkb_home, "rev-parse", "HEAD")
    dirty = bool(_git(sdkb_home, "status", "--porcelain"))

    dest.mkdir(parents=True, exist_ok=True)
    files = []
    for rel, role in VENDOR_FILES:
        out = dest / Path(rel).name
        shutil.copy2(sdkb_home / rel, out)
        entry = {"file": out.name, "source_path": rel, "role": role, "sha256": sha256(out)}
        if out.name in LICENSE_RESTRICTED:
            entry["license_restricted"] = True
        files.append(entry)

    for derive in (_derive_rejection_basis, _derive_rejection_reasons):
        entry = derive(sdkb_home, dest)
        if entry is not None:
            files.append(entry)

    prov = {
        "source_repo": _git(sdkb_home, "remote", "get-url", "origin"),
        "source_commit": commit,
        "source_commit_date": _git(sdkb_home, "log", "-1", "--format=%cI", commit),
        "source_dirty": dirty,
        "source_license": "CDLA-Permissive-2.0",
        "vendored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline_counts": report["counts"],
        "freshness": freshness,
        "excluded": {},
        "files": files,
    }
    (dest / "PROVENANCE.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[vendor] {len(files)} files -> {dest}")
    print(f"[vendor] source commit = {commit[:12]}{'  ⚠ DIRTY WORKTREE' if dirty else ''}")
    if dirty:
        print("[vendor] ⚠ SDKB 워킹트리에 커밋되지 않은 변경이 있다 — 스냅샷의 출처가 "
              "커밋 SHA 만으로 재현되지 않는다. SDKB 를 먼저 커밋할 것.", file=sys.stderr)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description="SDKB 온톨로지 스냅샷을 data/external/sdkb/ 로 vendor")
    ap.add_argument("--sdkb-home", type=Path, default=SDKB_HOME)
    ap.add_argument(
        "--verify", action="store_true",
        help="스냅샷 무결성만 검사한다 (SDKB 원본 불필요 — CI 게이트용). 갱신하지 않는다.",
    )
    ap.add_argument(
        "--verify-freshness", action="store_true",
        help="L0 신선도 — 신선도 검사 이행 증명과 파생 산출물 신선도를 본다 (SDKB 원본 불필요).",
    )
    ap.add_argument(
        "--derive-rejection", action="store_true",
        help="거절근거 라벨 CSV 만 파생·추가한다 (TTL 스냅샷 재동결 없음 — G₀ 서명 불변).",
    )
    args = ap.parse_args()

    if args.derive_rejection:
        # 전면 vendor 는 상류 재빌드 + 전 TTL 재동결을 뜻해 G₀ 서명을 흔든다(CLAUDE.md §1-8).
        # 여기서는 파생 CSV 한 개만 추가하고 PROVENANCE 의 files 항목을 제자리 갱신한다.
        entry = _derive_rejection_basis(args.sdkb_home, EXTERNAL_SDKB)
        if entry is None:
            print(f"[vendor] ✗ 원천 없음: {args.sdkb_home / REJECTION_SRC}", file=sys.stderr)
            sys.exit(1)
        pf = EXTERNAL_SDKB / "PROVENANCE.json"
        prov = json.loads(pf.read_text(encoding="utf-8"))
        prov["files"] = [f for f in prov["files"] if f["file"] != entry["file"]] + [entry]
        prov["derived_updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        pf.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[vendor] ✓ PROVENANCE 갱신 — {entry['file']} sha256={entry['sha256'][:12]}…")
        return

    if args.verify_freshness:
        problems = verify_freshness()
        for p in problems:
            print(f"[L0] ✗ {p}", file=sys.stderr)
        if problems:
            print(
                "[L0] 신선도 검사 실패 — 산출물이 원천을 옳게 반영한다는 보장이 없다.\n"
                "     sha256(L1 이전의 무결성)은 이 실패 양식을 원리적으로 잡지 못한다.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[L0] ✓ 신선도 — vendor 이행 증명 유효 · baseline 이 스냅샷보다 새롭다")
        return

    if args.verify:
        problems = verify_snapshot()
        for p in problems:
            print(f"[vendor] ✗ {p}", file=sys.stderr)
        if problems:
            print(
                "[vendor] 스냅샷이 PROVENANCE 와 어긋난다 — baseline 의 출처가 거짓이 된다.\n"
                "         의도한 갱신이라면 `make vendor` 로 PROVENANCE 를 재작성하고 "
                "data/MANIFEST.md 에 새 줄을 추가할 것.",
                file=sys.stderr,
            )
            sys.exit(1)
        absent = license_restricted_absences()
        for a in absent:
            print(
                f"[vendor] ⚠ 라이선스 제한 파일 부재(로컬 재생성 필요): {a} — "
                "`make vendor` 로 재생성. gitignore 되어 클론/CI 에 없는 것은 정상이다.",
                file=sys.stderr,
            )
        prov = json.loads((EXTERNAL_SDKB / "PROVENANCE.json").read_text(encoding="utf-8"))
        present = len(prov["files"]) - len(absent)
        print(
            f"[vendor] ✓ 스냅샷 무결 — {present}/{len(prov['files'])} files 검증"
            f"{f' ({len(absent)} 라이선스 제한 파일 부재·관용)' if absent else ''}, "
            f"SDKB commit {prov['source_commit'][:12]}"
        )
        return

    vendor(args.sdkb_home)


if __name__ == "__main__":
    main()
