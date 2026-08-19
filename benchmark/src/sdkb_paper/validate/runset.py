"""자원 스냅샷별 run 세트 동결과 O/O′ 적격심사 (D-19 · CLAUDE.md §0 델타 유형표 · §2.1).

**왜 이 모듈이 있는가.** H2(갱신 승인 안전성)는 *변경 없는 동일 파이프라인에 O 와 O′ 를 넣은*
비교로만 잰다. 그런데 지금까지 T-gate 가 실제로 비교한 것은 `sys_P1` 대 `sys_B3_rrf` —
**서로 다른 두 시스템**이었고, CLAUDE.md §0 이 "P1 대 B3 는 H2 의 증거가 아니다"라고 못박은
바로 그 비교다. 원인은 비교 함수가 아니라 **산출물 보존 구조**였다: run 경로에 자원 차원이
없어(`IR_RUNS_DIR` 플랫) `make vendor` 뒤 재실행하면 O 의 run 이 그대로 덮어써진다.

이 모듈이 하는 일은 셋뿐이다.
1. **동결(freeze):** 재벤더 **전에** 현 run 세트를 사본 + 매니페스트(해시·집계)로 얼린다.
2. **서명(signature):** 스냅샷 서명(무엇을 벤더했나)과 파이프라인 서명(그것이 **어디까지
   도달했나**)을 따로 계산한다. 둘을 나누는 것이 이 모듈의 핵심이다 — D-19 의 실패는
   "스냅샷은 바뀌었는데 코퍼스가 바이트 단위로 같았다"는 것이었고, 서명이 하나뿐이면
   그 상태가 **Δ≡0 의 공허한 통과**로 보고된다.
3. **적격심사(eligibility):** 두 run 세트가 H2 를 잴 자격이 있는지 판정한다. 자격이 없으면
   T1·T2 를 **돌리지 않는다** — 부적격 비교의 수치가 남으면 언젠가 인용되기 때문이다.

**경계:** 판정과 기록만 한다. 데이터·순위·qrel·검색 설정을 고치지 않는다.

CLI: `python -m sdkb_paper.validate.runset --freeze LABEL [--split test]`
     `python -m sdkb_paper.validate.runset --list`
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from .leakage_check import sha256_file

# 적격심사 판정 — accept 는 전부 0 이지만 **사유가 다르면 논문의 문장이 다르다.**
VERDICT_OK = "eligible"
VERDICT_VACUOUS = "vacuous"              # 스냅샷 서명 동일 → Δ 는 정의상 0
VERDICT_UNREACHED = "unreached"          # 스냅샷은 바뀌었으나 파이프라인이 읽지 않음 (D-19)
VERDICT_INELIGIBLE = "ineligible"        # 비교 자체가 성립하지 않음

# 자원 델타 가시성 (D-43 · PLAN-051). 적격심사(E1–E7)와 **다른 질문**이다 — 적격심사는 두 팔을
# 놓고 "비교할 자격이 있는가"를 묻고, 이것은 팔이 하나뿐인 `system` 모드에서 "지금 이 실행이
# 어떤 자원 상태 위에 서 있는가"를 묻는다.
VIS_INVISIBLE = "invisible"        # 스냅샷이 움직였는데 파이프라인이 읽지 않았다
VIS_NO_EVIDENCE = "no_evidence"    # 비가시라는 **증거가 없다** (≠ 델타가 보였다)
VIS_UNKNOWN = "unknown"            # 판단 근거가 없다


# --- 서명 ---------------------------------------------------------------

def _digest(payload) -> str:
    """정렬된 JSON 의 sha256. 시각·절대경로를 넣지 않아 재실행에 불변이다."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def snapshot_signature(prov: Path | None = None) -> dict:
    """벤더된 스냅샷의 서명 — PROVENANCE 의 **파일별 sha256** 이 재료다.

    커밋 해시로 동결하지 않는 이유는 CLAUDE.md §2.1 에 있다: 상류의 일부 TTL 은 gitignore 된
    빌드 산출물이라 같은 커밋에서도 결과가 다를 수 있다.
    """
    p = prov or (config.EXTERNAL_SDKB / "PROVENANCE.json")
    if not Path(p).exists():
        raise FileNotFoundError(f"PROVENANCE.json 이 없다: {p} — `make vendor` 를 먼저 실행할 것.")
    doc = json.loads(Path(p).read_text(encoding="utf-8"))
    files = {e["file"]: e["sha256"] for e in doc.get("files", [])}
    sig = _digest(sorted(files.items()))
    return {"sig": sig, "short": sig[:12], "upstream_commit": doc.get("source_commit"),
            "upstream_dirty": doc.get("source_dirty"), "n_files": len(files), "files": files}


# 파이프라인이 자원을 실제로 읽는 세 지점. 코퍼스(concepts 열) · 개념축/계층 · 병합 그래프.
PIPELINE_PARTS: tuple[tuple[str, str], ...] = (
    ("ir_corpus", "IR_CORPUS"),
    ("concept_axis", "IR_CONCEPT_AXIS"),
    ("graph_v1", "GRAPH_V1"),
)


def pipeline_signature() -> dict:
    """자원이 **도달한 지점**의 서명. 스냅샷 서명과 따로 재는 것이 이 모듈의 요점이다.

    스냅샷이 바뀌어도 이 서명이 그대로면 파이프라인은 그 변경을 읽지 않은 것이고, 그 상태의
    ΔR₁₀₀ 은 정의상 0 이다. 0 으로 비열등성을 통과하는 것은 H2 지지가 아니다.
    """
    parts: dict[str, str | None] = {}
    for name, attr in PIPELINE_PARTS:
        path = Path(getattr(config, attr))
        parts[name] = sha256_file(path) if path.exists() else None
    sig = _digest(sorted(parts.items()))
    return {"sig": sig, "short": sig[:12], "parts": parts}


def qrel_signature() -> dict:
    """봉인 qrel 해시 — 두 run 세트가 **같은 정답지**를 봤는지 확인하는 재료."""
    out: dict[str, str | None] = {}
    for key, attr in (("examiner", "QREL_EXAMINER"),
                      ("test_sealed", "IR_QREL_TEST_SEALED"),
                      # B층 봉인은 **열지 않고 해시만** 잰다 — 두 run 세트가 같은 정답지를
                      # 겨냥했는지는 바이트로 확인되고, 그것으로 충분하다(PLAN-047 §13.4).
                      ("b_sealed", "B_QREL_SEALED")):
        path = Path(getattr(config, attr))
        out[key] = sha256_file(path) if path.exists() else None
    return out


# E4(동일 코드)가 보는 경로. **자원·산출물은 코드가 아니다.**
# 왜 좁히는가(2026-08-01 · 사용자 승인): O 팔의 정의 자체가 git 추적 파일인
# `data/external/sdkb/` 를 구 스냅샷으로 되돌린 상태다. 트리 전체를 보면 O 팔은 동결 시점에
# 반드시 dirty 이고 E4 가 영구히 실격을 내, 자원 델타를 재는 일이 원리적으로 불가능해진다.
# E4 가 묻는 것은 "두 팔이 같은 코드로 돌았는가"이고, 자원 교체는 팔의 정의 그 자체다.
CODE_PATHS: tuple[str, ...] = ("src", "tests", "Makefile", "pyproject.toml", "uv.lock")


def code_signature() -> dict:
    """코드 상태 — 코드가 바뀌면 그것은 재측정이 아니라 새 방법이다(CLAUDE.md §2.1 안전장치).

    dirty 는 **`CODE_PATHS` 안의 tracked 변경**만 센다. 추적되지 않는 파일(데이터 산출물·
    프로파일)과 `data/` 아래의 자원·산출물 변경은 코드 변경이 아니다.
    """
    def _git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = _git("status", "--porcelain", "--untracked-files=no", "--", *CODE_PATHS)
    return {"commit": _git("rev-parse", "HEAD"),
            "dirty": bool(status) if status is not None else None,
            "dirty_scope": list(CODE_PATHS)}


def tbox_counts(prov: Path | None = None) -> dict:
    """T-Box 규모 집계 — 델타 유형 분류의 재료(CLAUDE.md §0 실측 D-12 와 같은 항목).

    병합 그래프(246MB)가 아니라 **스냅샷의 T-Box TTL** 만 읽는다. T-Box 는 상류의 선언이고,
    병합 그래프에는 A-Box 가 섞여 있어 같은 질문에 더 비싸게 답하기 때문이다.
    """
    from rdflib import OWL, RDF, Graph
    from rdflib.namespace import SKOS

    p = Path(prov or (config.EXTERNAL_SDKB / "PROVENANCE.json"))
    doc = json.loads(p.read_text(encoding="utf-8"))
    g = Graph()
    for e in doc.get("files", []):
        if not str(e.get("role", "")).startswith("TBox"):
            continue
        f = p.parent / e["file"]
        if f.exists():
            g.parse(str(f), format="turtle")
    return {
        "triples": len(g),
        "owl_class": sum(1 for _ in g.subjects(RDF.type, OWL.Class)),
        "object_property": sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty)),
        "datatype_property": sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty)),
        "skos_broader": sum(1 for _ in g.triples((None, SKOS.broader, None))),
    }


# --- 델타 유형 분류 (CLAUDE.md §0 표) ---------------------------------------

# ③ A-Box 코퍼스 델타의 표지 — 문서집합을 늘리는 파일들. 이 델타는 H2 자격이 없다.
ABOX_FILE_MARKERS = ("abox-patents", "abox-prior-art")
TBOX_COUNT_KEYS = ("owl_class", "object_property", "datatype_property")


def classify_delta(old: dict, new: dict) -> dict:
    """두 매니페스트 사이의 자원 델타를 ①T-Box ②개념층 ③A-Box 중 하나로 분류한다.

    분류는 **판정이지 해석이 아니다** — 파일 sha256 과 T-Box 카운트만 본다. 여러 유형이
    섞이면 A-Box 오염이 우선이다(자격 없음을 흡수하지 않는다).
    """
    of, nf = old["snapshot"]["files"], new["snapshot"]["files"]
    changed = sorted({f for f in set(of) | set(nf) if of.get(f) != nf.get(f)})
    abox = [f for f in changed if any(m in f for m in ABOX_FILE_MARKERS)]

    oc, nc = old.get("tbox_counts") or {}, new.get("tbox_counts") or {}
    tbox_moved = {k: [oc.get(k), nc.get(k)] for k in TBOX_COUNT_KEYS if oc.get(k) != nc.get(k)}

    if not changed:
        dtype = "none"
    elif abox:
        dtype = "abox"
    elif tbox_moved:
        dtype = "tbox"
    else:
        dtype = "concept"
    return {"type": dtype, "changed_files": changed, "abox_files": abox,
            "tbox_delta": tbox_moved}


# --- 동결 ---------------------------------------------------------------

def manifest_path(label: str) -> Path:
    return config.RUNSET_DIR / f"{label}.json"


def runs_dir(label: str) -> Path:
    return config.IR_RUNSETS_DIR / label


def arm_label(pipeline_sig: str | None = None) -> str | None:
    """파이프라인 서명이 동결 runset 매니페스트 중 하나와 일치하면 그 이름을 돌려준다.

    산출물(표·패널)이 **자기가 어느 팔에서 나왔는지 말할 수 있게** 하는 조회다. 일치하는
    매니페스트가 없으면 None — 그것도 정보다("동결되지 않은 상태에서 만든 산출물").
    """
    sig = pipeline_sig or pipeline_signature()["sig"]
    if not config.RUNSET_DIR.exists():
        return None
    for mf in sorted(config.RUNSET_DIR.glob("*.json")):
        try:
            d = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("pipeline", {}).get("sig") == sig:
            return str(d.get("label") or mf.stem)
    return None


def _iter_manifests() -> list[tuple[str, dict]]:
    """읽을 수 있는 동결 매니페스트를 (라벨, 문서) 로 정렬해 돌려준다.

    `arm_label()` 이 같은 순회를 갖고 있으나 **합치지 않는다** — 그 함수는 원고 표
    (`results_table`)가 부르는 경로라 동작을 건드릴 이유가 없다(CLAUDE.md §1-10).
    """
    if not config.RUNSET_DIR.exists():
        return []
    out: list[tuple[str, dict]] = []
    for mf in sorted(config.RUNSET_DIR.glob("*.json")):
        try:
            d = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append((str(d.get("label") or mf.stem), d))
    return sorted(out, key=lambda t: t[0])


def resource_visibility(pipeline: dict | None = None,
                        snapshot: dict | None = None) -> dict:
    """지금 이 실행의 자원 델타가 **게이트에 보이는 상태인가**를 판정한다 (D-43 · PLAN-051).

    `system` 모드에는 비교할 짝이 없어 적격심사 E6 이 돌지 않는다. 그래서 스냅샷이 움직였는데
    파이프라인이 그것을 읽지 않은 상태에서도 `Accept = 1` 이 나오고, 리포트는 그 사실을 적지
    않았다. 판정을 바꾸지는 않되 **승인이 무엇을 근거로 한 승인인지**는 남긴다.

    근거는 동결 매니페스트다: 파이프라인 서명이 같은데 **스냅샷 서명이 다른** 매니페스트가
    있으면, 그 스냅샷 차이는 파이프라인에 도달하지 않은 것이다.

    **예외를 올리지 않는다. 그러나 삼키지도 않는다** — 사유는 `error` 에 남고 리포트가 찍는다.
    """
    out: dict = {"note": VIS_UNKNOWN, "pipeline_sig": None, "pipeline_short": None,
                 "snapshot_sig": None, "snapshot_short": None,
                 "matched": [], "basis": [], "detail": "", "error": None}
    try:
        pipe = pipeline or pipeline_signature()
    except (FileNotFoundError, OSError) as e:            # noqa: BLE001 - 사유를 남기고 계속한다
        out["error"] = f"파이프라인 서명 계산 실패: {e}"
        out["detail"] = "판단 근거 없음 — 파이프라인 서명을 구하지 못했다"
        return out
    out["pipeline_sig"], out["pipeline_short"] = pipe.get("sig"), pipe.get("short")

    # 규칙 1 — 구성요소가 하나라도 없으면 서명은 계산되지만 **비교할 의미가 없다.**
    missing = sorted(k for k, v in (pipe.get("parts") or {}).items() if v is None)
    if missing:
        out["detail"] = f"파이프라인 구성요소 결측: {', '.join(missing)} — 가시성을 판단하지 않는다"
        return out

    # 규칙 2 — 스냅샷 서명이 없으면(PROVENANCE 부재 등) 근거가 없다.
    try:
        snap = snapshot or snapshot_signature()
    except (FileNotFoundError, OSError) as e:            # noqa: BLE001 - 위와 같은 이유
        out["error"] = f"스냅샷 서명 계산 실패: {e}"
        out["detail"] = "판단 근거 없음 — 스냅샷 서명을 구하지 못했다"
        return out
    out["snapshot_sig"], out["snapshot_short"] = snap.get("sig"), snap.get("short")

    matched = [lab for lab, d in _iter_manifests()
               if (d.get("pipeline") or {}).get("sig") == pipe.get("sig")]
    basis = [lab for lab, d in _iter_manifests()
             if (d.get("pipeline") or {}).get("sig") == pipe.get("sig")
             and (d.get("snapshot") or {}).get("sig") != snap.get("sig")]
    out["matched"], out["basis"] = matched, basis

    # 규칙 3 — 비가시의 증거는 흡수되지 않는다(`classify_delta` 가 A-Box 오염을 우선하는 것과 같다).
    if basis:
        out["note"] = VIS_INVISIBLE
        out["detail"] = (
            f"동결 runset {', '.join(basis)} 이 같은 파이프라인 서명({pipe.get('short')})을 "
            f"다른 스냅샷({snap.get('short')} 아님)에서 냈다 — 스냅샷 델타가 파이프라인에 "
            "도달하지 않았다. 이 실행의 ΔR₁₀₀ 은 측정된 0 이 아니라 구성상 0 이다")
        return out
    # 규칙 4 — 매치는 있으나 전부 같은 스냅샷. **가시라는 뜻이 아니라 비가시의 증거가 없다는 뜻.**
    if matched:
        out["note"] = VIS_NO_EVIDENCE
        out["detail"] = (f"동결 runset {', '.join(matched)} 과 파이프라인·스냅샷 서명이 함께 "
                         "일치한다 — 비가시라는 증거는 없다(델타가 보였다는 뜻은 아니다)")
        return out
    # 규칙 5 — 대조할 매니페스트가 없다. 근거 없음은 통과가 아니다.
    out["detail"] = (f"파이프라인 서명 {pipe.get('short')} 과 일치하는 동결 runset 이 없다 — "
                     "대조 근거가 없어 가시성을 판단하지 않는다")
    return out


def freeze(label: str, split: str = "test", systems: list[str] | None = None,
           note: str | None = None, sources: dict[str, Path] | None = None) -> Path:
    """현 자원 상태의 run 세트를 얼린다. **`make vendor` 전에** 실행해야 의미가 있다.

    `sources` 를 주면 그 경로에서 복사한다(테스트용 주입) — 기본은 동결 run 디렉터리.
    """
    if sources is None:
        from ..analysis.results_table import SYSTEM_LABELS, run_path

        names = systems or [n for n, _ in SYSTEM_LABELS]
        sources = {n: run_path(n, split) for n in names}

    dest = runs_dir(label)
    dest.mkdir(parents=True, exist_ok=True)

    runs: dict[str, dict] = {}
    for name, src in sources.items():
        src = Path(src)
        if not src.exists():
            continue
        tgt = dest / src.name
        shutil.copy2(src, tgt)
        n_q = len({line.split()[0] for line in tgt.read_text(encoding="utf-8").splitlines() if line})
        runs[name] = {"file": tgt.name, "sha256": sha256_file(tgt), "n_queries": n_q}
    if not runs:
        raise FileNotFoundError(
            f"동결할 run 이 없다 (split={split}) — `make retrieve` 를 먼저 실행할 것.")

    mf = {
        "label": label, "split": split,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
        "code_git": code_signature(),
        "snapshot": snapshot_signature(),
        "pipeline": pipeline_signature(),
        "tbox_counts": tbox_counts(),
        "qrel": qrel_signature(),
        "runs": runs,
    }
    config.RUNSET_DIR.mkdir(parents=True, exist_ok=True)
    out = manifest_path(label)
    out.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load(label: str) -> dict:
    p = manifest_path(label)
    if not p.exists():
        raise FileNotFoundError(
            f"run 세트 매니페스트 없음: {p} — 먼저 `make freeze-runset LABEL={label}` 로 얼려라")
    return json.loads(p.read_text(encoding="utf-8"))


def run_file(mf: dict, system: str) -> Path:
    entry = (mf.get("runs") or {}).get(system)
    if not entry:
        raise KeyError(f"run 세트 '{mf['label']}' 에 시스템 '{system}' 의 run 이 없다")
    return runs_dir(mf["label"]) / entry["file"]


# --- 적격심사 -----------------------------------------------------------

def eligibility(old: dict, new: dict, system: str) -> dict:
    """O 대 O′ 비교가 H2 를 잴 자격이 있는지 판정한다. 자격 없음은 **불통과가 아니라 미검정**이다.

    일곱 검사는 순서가 있다. 앞의 넷은 "비교가 성립하는가"(시스템·분할·정답지·코드), 뒤의 셋은
    "델타가 존재하며 자격이 있는가"(스냅샷 서명·파이프라인 서명·델타 유형)다.
    """
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, verdict: str = VERDICT_INELIGIBLE) -> bool:
        checks.append({"check": name, "pass": bool(ok), "detail": detail,
                       "verdict_if_failed": verdict})
        return bool(ok)

    o_runs, n_runs = old.get("runs") or {}, new.get("runs") or {}
    add("E1 동일 시스템", system in o_runs and system in n_runs,
        f"system={system} · old={'있음' if system in o_runs else '없음'} · "
        f"new={'있음' if system in n_runs else '없음'} — P1 대 B3 같은 시스템 간 비교는 H2 가 아니다")
    add("E2 동일 분할", old.get("split") == new.get("split"),
        f"old={old.get('split')} · new={new.get('split')}")
    add("E3 동일 qrel", old.get("qrel") == new.get("qrel"),
        "정답지가 다르면 ΔR₁₀₀ 은 자원 효과가 아니다")
    add("E4 동일 코드", (old.get("code_git", {}).get("commit")
                     == new.get("code_git", {}).get("commit")
                     and not old.get("code_git", {}).get("dirty")
                     and not new.get("code_git", {}).get("dirty")),
        f"old={str(old.get('code_git', {}).get('commit'))[:8]} · "
        f"new={str(new.get('code_git', {}).get('commit'))[:8]} — 코드가 바뀌면 재측정이 아니라 "
        "새 방법이다(CLAUDE.md §2.1)")
    add("E5 스냅샷 서명 상이", old["snapshot"]["sig"] != new["snapshot"]["sig"],
        f"old={old['snapshot']['short']} · new={new['snapshot']['short']} — 같으면 Δ 는 정의상 0",
        VERDICT_VACUOUS)
    add("E6 파이프라인 서명 상이", old["pipeline"]["sig"] != new["pipeline"]["sig"],
        f"old={old['pipeline']['short']} · new={new['pipeline']['short']} — 자원이 바뀌었어도 "
        "코퍼스·개념축·그래프가 그대로면 파이프라인이 그것을 읽지 않은 것이다(D-19)",
        VERDICT_UNREACHED)

    delta = classify_delta(old, new)
    add("E7 델타 유형 자격", delta["type"] in config.H2_ELIGIBLE_DELTA_TYPES,
        f"type={delta['type']} — ③A-Box 코퍼스 델타는 비교 불성립(CLAUDE.md §0 델타 유형표)")

    failed = [c for c in checks if not c["pass"]]
    verdict = VERDICT_OK if not failed else failed[0]["verdict_if_failed"]
    return {"eligible": not failed, "verdict": verdict, "delta_type": delta["type"],
            "delta": delta, "checks": checks, "system": system,
            "runsets": {"old": old["label"], "new": new["label"]}}


def format_eligibility(res: dict) -> str:
    lines = [f"─── O/O′ 적격심사 (system={res['system']} · "
             f"old={res['runsets']['old']} → new={res['runsets']['new']})"]
    for c in res["checks"]:
        lines.append(f"  {'✅' if c['pass'] else '❌'} {c['check']}")
        if not c["pass"]:
            lines.append(f"       {c['detail']}")
    lines.append(f"  델타 유형 = {res['delta_type']} · 변경 파일 {len(res['delta']['changed_files'])}개")
    if res["delta"]["tbox_delta"]:
        lines.append(f"       T-Box 이동: {res['delta']['tbox_delta']}")
    verdict = "있음" if res["eligible"] else f"없음 ({res['verdict']})"
    lines.append(f"  ⇒ H2 자격 = {verdict}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", metavar="LABEL", help="현 run 세트를 이 라벨로 동결")
    ap.add_argument("--split", default="test",
                    choices=["train", "dev", "test", "test_b", "all"])
    ap.add_argument("--note", default=None, help="매니페스트에 남길 메모(예: CR-007 적용 전)")
    ap.add_argument("--list", action="store_true", help="동결된 run 세트 목록")
    args = ap.parse_args()

    if args.list:
        for p in sorted(config.RUNSET_DIR.glob("*.json")):
            mf = json.loads(p.read_text(encoding="utf-8"))
            print(f"{mf['label']:24s} split={mf['split']:5s} "
                  f"snap={mf['snapshot']['short']} pipe={mf['pipeline']['short']} "
                  f"runs={len(mf['runs'])}  {mf.get('note') or ''}")
        return
    if not args.freeze:
        ap.error("--freeze LABEL 또는 --list 중 하나가 필요하다")

    out = freeze(args.freeze, args.split, note=args.note)
    mf = json.loads(out.read_text(encoding="utf-8"))
    print(f"✓ {out}")
    print(f"  스냅샷 서명   = {mf['snapshot']['short']} (상류 {str(mf['snapshot']['upstream_commit'])[:8]})")
    print(f"  파이프라인 서명 = {mf['pipeline']['short']}")
    print(f"  동결 run      = {', '.join(mf['runs'])}")


if __name__ == "__main__":
    main()
