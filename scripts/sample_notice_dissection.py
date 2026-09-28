#!/usr/bin/env python3
"""PLAN-005 R1 — 정답 해부의 표본 30건을 **층화·결정적**으로 뽑는다 (그래프를 바꾸지 않는다).

설계: [PLAN-005 §20.15](../01.code_spec/plans/PLAN-005-prior-art-tool-qualification.md)

**왜 추출기가 따로 필요한가.** 해부는 LLM(에이전트)이 본문을 읽는 일이라 재현이 보장되지
않는다. 그러므로 **무엇을 읽을지는 코드가 결정적으로 정하고**, 읽은 결과만 산출물로 동결한다
(§20.8 R2 선례). 표본을 손으로 고르면 "결손이 잘 보이는 문서"를 고르게 되고, 그 순간 결손
목록은 자원의 상태가 아니라 고른 사람의 기대를 재는 것이 된다.

**이 스크립트는 본문을 열지 않는다.** 파일명·sha256·층 라벨만 다룬다. 산출의 본문이 LLM 으로
넘어가는 자격은 사람 확인이 준다(§20.14(g)) — `--mark-verified` 가 그 사실을 기록하는 자리이고,
집계기(`report_r1_dissection.py`)가 그 플래그를 검사한다.

층 (배타 · 구성대비표 보유가 최우선):

    S1 table        구성대비표 보유            요소 단위 판정이 가장 짙다
    S2 mixed        §29①∧② (표 없음)         신규성·진보성이 한 문서에
    S3 novelty      §29①만   (표 없음)        §5 가 "소실이 아니라 경계"로 적은 축
    S4 inventive    §29②만   (표 없음)        최다 유형
    S5 no_basis     근거행 없음 (표 없음)      심사관 엣지는 있는데 legal_bases 가 전량 공란

**정원은 비례배분이 아니다.** 희소 층을 일부러 과표집한다 — 목적이 결손 탐색이지 빈도 추정이
아니기 때문이다. 그래서 이 표본으로 **발생률을 모집단에 일반화하지 않는다**(보고서에 명시).

출원당 최대 1건이다. 같은 출원의 2·3차 통지서가 겹치면 독립 사례가 30 미만이 된다(실측:
산출 688건 = 고유 출원 587).

사용
  make sample-dissection
  python3 scripts/sample_notice_dissection.py --mark-verified 2026-09-24
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splits  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
SCRUB_DIR = SOURCES / "notice_excerpts_scrubbed"
SCRUB_MANIFEST = SCRUB_DIR / "_manifest.json"
LEGAL_BASIS = ROOT / "data" / "patents" / "notice_legal_basis.parquet"
ELEMENT_JUDGMENTS = ROOT / "data" / "patents" / "notice_element_judgments.parquet"
OUT = SOURCES / "notice_dissection" / "sample_v1.json"

SAMPLE_VERSION = "S1"
SEED = 20260922
SCOPE = "train"

#: 희소 층 우선. 출원당 1건 제약이 앞선 층에 유리하게 걸리므로 순서 자체가 설계다.
STRATA_ORDER = ("novelty", "table", "mixed", "no_basis", "inventive")
QUOTA = {"table": 6, "mixed": 7, "novelty": 4, "inventive": 7, "no_basis": 6}
TOTAL = 30

G1, G2 = "§29①", "§29②"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_parquet(path: Path):
    try:
        import pandas as pd
    except ModuleNotFoundError as e:  # 의존성은 새로 만들지 않는다 — 있는 것을 쓴다.
        raise SystemExit(f"ERROR: pandas 가 없다 ({e}). 가상환경에서 실행할 것.")
    return pd.read_parquet(path)


def strata_of(produced: list[str], *, legal_basis: Path = LEGAL_BASIS,
              element_judgments: Path = ELEMENT_JUDGMENTS) -> dict[str, str]:
    """산출 파일명 → 층 라벨. 어느 층에도 안 드는 파일은 돌려주지 않는다(모집단 제외).

    배타성은 우선순위로 만든다 — 구성대비표를 가진 파일은 근거 조합과 무관하게 `table` 이다.
    그러지 않으면 22건짜리 희소 층이 다른 층에 흡수돼 정원이 성립하지 않는다.
    """
    keep = set(produced)
    lb = _read_parquet(legal_basis)
    lb = lb[lb.source_file.isin(keep)]
    grounds: dict[str, set[str]] = {}
    for f, g in zip(lb.source_file, lb.legal_basis):
        grounds.setdefault(f, set()).add(str(g).strip())
    tables = set(_read_parquet(element_judgments).source_file) & keep

    out: dict[str, str] = {}
    for f in produced:
        if f in tables:
            out[f] = "table"
            continue
        g = grounds.get(f)
        if g is None:
            out[f] = "no_basis"
        elif G1 in g and G2 in g:
            out[f] = "mixed"
        elif G1 in g:
            out[f] = "novelty"
        elif G2 in g:
            out[f] = "inventive"
        # 그 밖(§42 단독 등)은 선행기술 판단이 아니므로 모집단에서 뺀다.
    return out


def select(manifest: dict, labels: dict[str, str], *, seed: int = SEED) -> dict:
    """층별 정원만큼 · 출원당 1건 · 같은 seed 면 같은 목록."""
    app_of = {e["output"]: e["application"] for e in manifest["files"] if e.get("output")}
    by_stratum: dict[str, list[str]] = {s: [] for s in STRATA_ORDER}
    for f, s in sorted(labels.items()):
        by_stratum[s].append(f)

    rng = random.Random(seed)
    taken_apps: set[str] = set()
    picked: dict[str, list[str]] = {}
    for s in STRATA_ORDER:
        eligible = [f for f in by_stratum[s] if app_of[f] not in taken_apps]
        need = QUOTA[s]
        if len(eligible) < need:
            raise SystemExit(
                f"ERROR: 층 {s} 의 적격 후보가 정원보다 적다 — 적격 {len(eligible)} < 정원 {need}. "
                "정원을 결과를 보고 고치지 말 것(§1-2): 설계로 돌아간다.")
        chosen = sorted(rng.sample(eligible, need))
        picked[s] = chosen
        taken_apps.update(app_of[f] for f in chosen)
    return picked


def run(*, out: Path = OUT, scrub_dir: Path = SCRUB_DIR,
        manifest_path: Path | None = None, legal_basis: Path = LEGAL_BASIS,
        element_judgments: Path = ELEMENT_JUDGMENTS,
        split_path: Path = splits.SPLIT_CSV, verify_split: bool = True,
        seed: int = SEED) -> dict:
    scrub_dir = Path(scrub_dir)
    manifest_path = Path(manifest_path or (scrub_dir / "_manifest.json"))
    if not manifest_path.exists():
        raise SystemExit(f"ERROR: 스크럽 매니페스트가 없다 — {manifest_path}. `make scrub-notices` 가 선행이다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    produced = sorted(e["output"] for e in manifest["files"] if e.get("output"))
    sha_of = {e["output"]: e["output_sha256"] for e in manifest["files"] if e.get("output")}
    app_of = {e["output"]: e["application"] for e in manifest["files"] if e.get("output")}
    labels = strata_of(produced, legal_basis=legal_basis, element_judgments=element_judgments)
    picked = select(manifest, labels, seed=seed)

    split_map = splits.load_split(split_path, verify=verify_split)
    train_apps = {d[len("kr_"):] for d, s in split_map.items() if s == SCOPE and d.startswith("kr_")}

    rows: list[dict] = []
    for s in STRATA_ORDER:
        for f in picked[s]:
            app = app_of[f]
            if app not in train_apps:
                raise SystemExit(f"ERROR: {SCOPE} 밖 출원이 표본에 있다: {app} ({f})")
            path = scrub_dir / f
            if not path.exists():
                raise SystemExit(f"ERROR: 표본 파일이 없다 — {path}. 스크럽 산출을 다시 만들 것.")
            got = sha256_of(path)  # 본문을 읽지 않는다 — 바이트를 해시할 뿐이다.
            if got != sha_of[f]:
                raise SystemExit(f"ERROR: 표본 파일의 sha256 이 매니페스트와 다르다: {f}")
            rows.append({"stratum": s, "source_file": f, "application": app, "sha256": got})

    if len(rows) != TOTAL or len({r["application"] for r in rows}) != len(rows):
        raise SystemExit(
            f"ERROR: 표본이 {TOTAL}건·출원 유일이 아니다: {len(rows)}행 · "
            f"고유 출원 {len({r['application'] for r in rows})}")

    doc = {
        "sample_version": SAMPLE_VERSION,
        "seed": seed,
        "scope": SCOPE,
        "split_sha256": splits.sha256_of(split_path),
        "scrub_rule_version": manifest["rule_version"],
        "population": len(labels),
        "population_by_stratum": dict(sorted(Counter(labels.values()).items())),
        "quota": dict(sorted(QUOTA.items())),
        "strata_order": list(STRATA_ORDER),
        "not_a_frequency_estimate":
            "희소 층을 일부러 과표집했다. 결손 발생률을 모집단으로 일반화하지 않는다.",
        "human_verified": False,
        "verified_on": None,
        "pii": "사람이 30건 전수를 확인하기 전에는 본문을 LLM 에 보내지 않는다(§1-5 · §20.14(g))",
        "files": rows,
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def mark_verified(date: str, *, out: Path = OUT, scrub_dir: Path = SCRUB_DIR) -> dict:
    """사람이 전수 확인했다는 사실을 기록한다 — **확인 자체를 대신하지 않는다.**

    확인한 파일과 해부할 파일이 같아야 하므로 sha256 을 다시 검사한다. 스크럽을 다시 돌려
    바이트가 달라졌다면 그 확인은 다른 파일에 대한 것이다.
    """
    out = Path(out)
    if not out.exists():
        raise SystemExit(f"ERROR: 표본 파일이 없다 — {out}. 먼저 `make sample-dissection`.")
    doc = json.loads(out.read_text(encoding="utf-8"))
    for r in doc["files"]:
        got = sha256_of(Path(scrub_dir) / r["source_file"])
        if got != r["sha256"]:
            raise SystemExit(
                f"ERROR: {r['source_file']} 의 sha256 이 표본 기록과 다르다 — "
                "사람이 확인한 파일과 해부할 파일이 같지 않다.")
    doc["human_verified"] = True
    doc["verified_on"] = date
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--mark-verified", metavar="YYYY-MM-DD",
                    help="사람이 표본 전수를 확인했음을 기록한다(확인을 대신하지 않는다)")
    a = ap.parse_args()
    if a.mark_verified:
        d = mark_verified(a.mark_verified, out=a.out)
        print(f"[sample-dissection] 사람 확인 기록 · {d['verified_on']} · {len(d['files'])}건")
        return
    d = run(out=a.out)
    print(f"[sample-dissection] 표본 {SAMPLE_VERSION} · seed {d['seed']} · "
          f"모집단 {d['population']} → {len(d['files'])}건")
    print(f"[sample-dissection] 층별 모집단 {d['population_by_stratum']} · 정원 {d['quota']}")
    print("[sample-dissection] 사람이 30건을 확인하기 전에는 본문을 LLM 에 보내지 않는다.")


if __name__ == "__main__":
    main()
