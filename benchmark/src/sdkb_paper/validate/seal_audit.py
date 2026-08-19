"""봉인 열람 감사 — 기본은 **거부**, 열면 원장에 남는다 (PLAN-047 §13.3 · G7).

**왜 이 모듈이 있는가.** 판독 B 의 순서는 "run 을 먼저 만들고, 그 다음에 봉인을 연다"이다
(PLAN-047 §5 G7). 그런데 순서를 사람의 기억에 맡기면 지켜졌는지 사후에 증명할 수 없고,
한 번 열린 봉인은 되돌릴 수 없다. 그래서 순서를 **프로그램이 지키게** 한다 —

- 봉인 파일을 여는 유일한 통로는 `open_sealed()` 이고 **기본 인자는 거부**다.
- 여는 데에는 명시적 `allow=True`(CLI `--unseal`)와 **사유 문자열**이 필요하다.
- 열린 사실은 `config.SEAL_ACCESS_LOG` 에 **추가전용 1행**으로 남는다(시각·커밋·호출자·
  파일 sha256·사유). 배관 검증이 끝난 시점에 이 원장이 **0행**이면 "열람 0회"가 증명되고,
  개봉 후에는 정확히 **1행**이어야 한다.

**이 모듈은 파일을 읽지 않는다** — 경로를 돌려줄 뿐이고, 해시는 바이트를 스트리밍해 계산한다.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import config


class SealedAccessError(RuntimeError):
    """봉인 파일을 허가 없이 열려 했다 — 사전등록 순서 위반."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _caller() -> str:
    """호출자 모듈:함수 — 누가 열었는지 원장이 지목할 수 있어야 한다."""
    for frame in inspect.stack()[1:]:
        mod = frame.frame.f_globals.get("__name__", "")
        if mod != __name__:
            return f"{mod}:{frame.function}"
    return "unknown"


def access_log() -> list[dict]:
    """원장 전량(없으면 빈 리스트). G7 증거 판독용."""
    path = Path(config.SEAL_ACCESS_LOG)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def open_sealed(path: Path, *, reason: str, allow: bool) -> Path:
    """봉인 파일 경로를 돌려준다 — `allow=False` 면 열지 않고 예외를 던진다.

    반환값은 경로일 뿐이며 읽기는 호출자가 한다. 그럼에도 이 함수를 "여는 통로"라 부르는
    이유는, 봉인 경로가 **여기를 거치지 않고는 소비자에게 도달하지 않도록** 배선했기
    때문이다(`analysis.metrics.load_qrel_for_split`).
    """
    path = Path(path)
    if not allow:
        raise SealedAccessError(
            f"봉인 파일 열람 거부: {path.name} — 개봉은 사전등록(PLAN-047) 동결 커밋 이후 "
            f"`--unseal` 로만 한다. 사유='{reason}'"
        )
    if not reason.strip():
        raise SealedAccessError("개봉에는 사유가 필요하다 — 빈 사유로는 열지 않는다")
    rec = {
        "opened_at": _now(),
        "commit": _commit(),
        "caller": _caller(),
        "file": str(path.relative_to(config.ROOT)) if path.is_relative_to(config.ROOT) else str(path),
        "sha256": sha256_file(path) if path.exists() else None,
        "reason": reason,
    }
    log = Path(config.SEAL_ACCESS_LOG)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"🔓 봉인 개봉 기록 → {log} · {rec['file']} · 사유={reason}")
    return path
