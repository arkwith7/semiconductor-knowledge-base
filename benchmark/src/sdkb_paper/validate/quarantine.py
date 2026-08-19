"""오염 격리 — 결함주입 산출물이 정본으로 새지 않게 하는 장치 (PLAN-020 W4).

결함주입(§4.10)은 그래프를 **고의로** 망가뜨린다. 망가진 산출물이 하류(코퍼스·검색·게이트·논문
표)로 한 번이라도 새어 들어가면 논문 전체가 조용히 오염되고, 그 사고는 사후에 발견하기가 거의
불가능하다(2026-07-14 낡은 스냅샷 사고가 정확히 그런 종류였다 — 게이트는 내내 초록불이었다).
이 모듈은 그 경로를 **물리적으로** 막는다. 세 장치다.

1. **PRISTINE 봉인.** 실험 전에 정본 산출물의 sha256 을 `data/PRISTINE.json` 에 굳히고, 주입
   대상 그래프는 `data/pristine_backup/` 에 실제로 복사한다. 실험 후 재검증해 **원본이 한 바이트도
   바뀌지 않았음을 증명**한다(증명 실패 = 실험 무효, 백업에서 복원).
2. **격리 작업공간.** 오염 산출물은 `data/quarantine/<run_id>/<label>/` 밖에 쓰지 못한다. 각
   디렉터리에 `_CONTAMINATED.json` 스탬프(결함 사양·시드·커밋·시각)를 남긴다.
3. **재사용 차단.** `assert_pristine(path)` 가 격리 경로나 오염 스탬프를 감지하면 즉시 예외를
   던진다. 정본 경로를 읽는 진입점(t_gate·코퍼스 조립)이 이 함수를 호출한다. 실험이 끝나면
   격리본은 읽기전용으로 잠기고 `data/quarantine/LEDGER.jsonl` 에 원장이 남는다.

**경계:** 이 모듈은 데이터를 만들지도 고치지도 않는다 — 봉인·검증·격리·차단만 한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import config

PRISTINE_MANIFEST = config.DATA / "PRISTINE.json"
QUARANTINE = config.DATA / "quarantine"
BACKUP = config.DATA / "pristine_backup"
LEDGER = QUARANTINE / "LEDGER.jsonl"
STAMP_NAME = "_CONTAMINATED.json"


class ContaminationError(RuntimeError):
    """오염된(또는 오염 가능성 있는) 산출물을 정본 경로에서 쓰려 할 때."""


class PristineViolation(RuntimeError):
    """실험 전후로 정본 산출물이 변경됐을 때 — 실험 결과는 무효다."""


# --- 봉인 대상 ----------------------------------------------------------------
def protected_paths() -> list[Path]:
    """결함주입이 절대 건드리면 안 되는 정본 산출물. 없는 파일은 봉인에서 제외한다."""
    cands = [
        config.GRAPH_V0, config.GRAPH_V1, config.GRAPH_V2,
        config.IR_CONCEPT_AXIS, config.IR_CONCEPT_AXIS.with_suffix(".tree.json"),
        config.IR_CORPUS, config.QREL_EXAMINER, config.IR_QREL_TEST_SEALED,
        config.IR_SPLIT, config.IR_OVERLAP_THRESHOLD,
        config.CQ_GEN_DIR / "cq_g0.json",
    ]
    cands += sorted(config.IR_RUNS_DIR.glob("*.txt")) if config.IR_RUNS_DIR.exists() else []
    return [p for p in cands if p.exists()]


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:       # git 없는 환경에서도 봉인 자체는 성립한다
        return "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- 1. 봉인 · 검증 -----------------------------------------------------------
def seal(backup: tuple[Path, ...] = (config.GRAPH_V0,)) -> dict:
    """정본 해시를 굳히고 주입 대상은 실복사 백업한다. 실험 **전에** 반드시 부른다."""
    entries = {}
    for p in protected_paths():
        entries[str(p.relative_to(config.ROOT))] = {"sha256": sha256(p), "bytes": p.stat().st_size}

    BACKUP.mkdir(parents=True, exist_ok=True)
    backed = []
    for p in backup:
        if not p.exists():
            raise FileNotFoundError(f"백업 대상 없음: {p}")
        dst = BACKUP / p.name
        if not dst.exists() or sha256(dst) != entries[str(p.relative_to(config.ROOT))]["sha256"]:
            shutil.copy2(p, dst)
        backed.append(str(dst.relative_to(config.ROOT)))

    manifest = {"sealed_at": _now(), "commit": _commit(), "n_files": len(entries),
                "backups": backed, "files": entries}
    PRISTINE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    PRISTINE_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verify_pristine(strict: bool = True) -> list[dict]:
    """봉인 이후 정본이 변했는지 검사. 반환 = 위반 목록(빈 리스트면 무결).

    strict 면 위반 시 `PristineViolation` 을 던진다 — 결함주입 러너는 **매 인스턴스 뒤에**
    이걸 부른다. 한 번이라도 새면 그 지점에서 멈춰야 오염 범위가 한 인스턴스로 갇힌다.
    """
    if not PRISTINE_MANIFEST.exists():
        raise FileNotFoundError(f"봉인이 없다: {PRISTINE_MANIFEST} (quarantine.seal() 선행)")
    manifest = json.loads(PRISTINE_MANIFEST.read_text(encoding="utf-8"))
    bad = []
    for rel, rec in manifest["files"].items():
        p = config.ROOT / rel
        if not p.exists():
            bad.append({"path": rel, "reason": "삭제됨"})
        elif sha256(p) != rec["sha256"]:
            bad.append({"path": rel, "reason": "해시 불일치", "expected": rec["sha256"]})
    if bad and strict:
        raise PristineViolation(
            f"정본 산출물 {len(bad)}건이 변경됐다 — 실험 무효. 백업({BACKUP})에서 복원하라: {bad}")
    return bad


def restore(name: str) -> Path:
    """백업본으로 정본을 되돌린다. 사고 복구용 — 자동 호출하지 않는다."""
    src, dst = BACKUP / name, config.PROCESSED / name
    if not src.exists():
        raise FileNotFoundError(f"백업 없음: {src}")
    if dst.exists():
        os.chmod(dst, 0o644)
    shutil.copy2(src, dst)
    return dst


# --- 2. 격리 작업공간 ---------------------------------------------------------
def workspace(run_id: str, label: str, spec: dict | None = None) -> Path:
    """격리 디렉터리를 만들고 오염 스탬프를 찍는다. 결함 산출물은 여기 밖으로 못 나간다."""
    d = QUARANTINE / run_id / label
    d.mkdir(parents=True, exist_ok=True)
    # 앞선 실행이 lock() 으로 잠갔을 수 있다 — 재실행은 격리 안에서만 허용한다(정본과 무관).
    for p in d.rglob("*"):
        if p.is_file():
            os.chmod(p, 0o644)
    (d / STAMP_NAME).write_text(json.dumps(
        {"contaminated": True, "run_id": run_id, "label": label, "spec": spec or {},
         "stamped_at": _now(), "commit": _commit(),
         "warning": "결함이 주입된 실험용 산출물이다. 정본·논문 수치로 절대 사용하지 않는다."},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def is_contaminated(path: Path) -> bool:
    """격리 트리 안이거나 같은 디렉터리에 오염 스탬프가 있으면 오염이다."""
    p = Path(path).resolve()
    q = QUARANTINE.resolve()
    if p == q or q in p.parents:
        return True
    d = p if p.is_dir() else p.parent
    return (d / STAMP_NAME).exists()


def assert_pristine(path: Path, what: str = "산출물") -> Path:
    """정본 경로여야 하는 자리에서 부른다. 오염이면 즉시 멈춘다(우회 인자 없음)."""
    if is_contaminated(path):
        raise ContaminationError(
            f"오염된 {what}을(를) 정본 경로에서 쓰려 한다: {path}\n"
            f"  결함주입 산출물은 {QUARANTINE} 안에서 실험 코드로만 쓴다 (PLAN-020 W4).")
    return Path(path)


def lock(path: Path) -> int:
    """격리 산출물을 읽기전용으로 잠근다. 실수로 덮어써서 이력이 사라지는 것을 막는다."""
    n = 0
    for p in sorted(Path(path).rglob("*")):
        if p.is_file():
            os.chmod(p, 0o444)
            n += 1
    return n


def log(record: dict) -> None:
    """격리 원장 1행 추가 — 어떤 결함을 언제 어디에 만들었는지의 감사 기록."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **record}, ensure_ascii=False) + "\n")
