"""R1 해부 표본 추출기의 계약을 고정한다 — PLAN-005 §20.15.

고정하는 것.

  ① **결정적인가.** 같은 seed·같은 원천 → 같은 목록. 손으로 고르면 결손 목록이 자원의 상태가
     아니라 고른 사람의 기대를 재게 된다.
  ② **층이 배타인가.** 구성대비표 보유는 근거 조합과 무관하게 `table` 이다. 흡수되면 22건짜리
     희소 층의 정원이 성립하지 않는다.
  ③ **실패해야 할 입력이 실패하는가.** train 밖 출원 · sha256 불일치 · 정원 부족.
  ④ **사람 게이트가 sha 를 다시 문다.** 확인한 파일과 해부할 파일이 달라지면 기록이 거부된다.

픽스처는 전부 합성이다. 실물 통지서를 쓰지 않는다(§1-5) — 본문 자리에 `x` 를 채운다.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sample_notice_dissection as sd  # noqa: E402

pd = pytest.importorskip("pandas")

#: 층별로 정원과 **같은 수**를 만든다 — 그래야 전수가 뽑히고 주입이 반드시 걸린다.
PLAN = {
    "novelty": ("§29①", False),
    "table": ("§29②", True),
    "mixed": ("§29①|§29②", False),
    "no_basis": (None, False),
    "inventive": ("§29②", False),
}


def build(tmp: Path, *, extra: list[tuple[str, str, str | None, bool]] | None = None):
    """합성 원천 한 벌. extra 는 (파일명, 출원, 근거, 표보유) 추가분."""
    scrub = tmp / "scrubbed"
    scrub.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, str | None, bool]] = []
    for sn_i, (stratum, (basis, table)) in enumerate(PLAN.items()):
        for i in range(sd.QUOTA[stratum]):
            # 출원번호는 층 순번으로 짓는다 — hash() 는 프로세스마다 달라져 결정적이지 않다.
            app = f"10201{sn_i + 10}{i:07d}"
            rows.append((f"{app}_9520000000{i:03d}.txt", app, basis, table))
    rows.extend(extra or [])

    files, lb, ej = [], [], []
    for name, app, basis, table in rows:
        body = ("L1\t" + "x" * 40 + "\n").encode("utf-8")
        (scrub / name).write_bytes(body)
        files.append({
            "application": app, "source": name,
            "source_sha256": hashlib.sha256(b"src").hexdigest(),
            "output": name, "output_sha256": hashlib.sha256(body).hexdigest(), "lines": 1,
        })
        for g in (basis.split("|") if basis else []):
            lb.append({"source_file": name, "legal_basis": g})
        if table:
            ej.append({"source_file": name})
    (scrub / "_manifest.json").write_text(
        json.dumps({"rule_version": "N1", "files": files}, ensure_ascii=False), encoding="utf-8")

    lb_p, ej_p = tmp / "lb.parquet", tmp / "ej.parquet"
    pd.DataFrame(lb or [{"source_file": "", "legal_basis": ""}]).to_parquet(lb_p)
    pd.DataFrame(ej or [{"source_file": ""}]).to_parquet(ej_p)

    split_p = tmp / "split.csv"
    with split_p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "split"])
        for app in sorted({app for _, app, _, _ in rows}):   # 분할은 출원 단위다
            w.writerow([f"kr_{app}", "train"])
    return scrub, lb_p, ej_p, split_p


def go(tmp: Path, scrub, lb, ej, split, **kw):
    return sd.run(out=tmp / "sample.json", scrub_dir=scrub, legal_basis=lb,
                  element_judgments=ej, split_path=split, verify_split=False, **kw)


def test_deterministic_and_complete(tmp_path):
    a = go(tmp_path, *build(tmp_path))
    b = go(tmp_path, *build(tmp_path))
    assert [r["source_file"] for r in a["files"]] == [r["source_file"] for r in b["files"]]
    assert len(a["files"]) == sd.TOTAL
    assert len({r["application"] for r in a["files"]}) == sd.TOTAL


def test_table_stratum_is_exclusive(tmp_path):
    """구성대비표 보유 파일은 §29② 를 가져도 inventive 로 새지 않는다."""
    d = go(tmp_path, *build(tmp_path))
    per = {}
    for r in d["files"]:
        per.setdefault(r["stratum"], []).append(r["source_file"])
    assert {s: len(v) for s, v in per.items()} == sd.QUOTA


def test_one_notice_per_application(tmp_path):
    """같은 출원의 2차 통지서가 뒤 층에 있어도 두 번 뽑히지 않는다."""
    scrub, lb, ej, split = build(tmp_path)
    first = json.loads((scrub / "_manifest.json").read_text())["files"][0]
    extra = [(f"{first['application']}_952999999999.txt", first["application"], "§29②", False)]
    d = go(tmp_path, *build(tmp_path, extra=extra))
    apps = [r["application"] for r in d["files"]]
    assert len(apps) == len(set(apps))


def test_split_violation_dies(tmp_path):
    scrub, lb, ej, split = build(tmp_path)
    rows = list(csv.DictReader(split.open(encoding="utf-8")))
    rows[0]["split"] = "test"          # 봉인 분할을 표본에 심는다
    with split.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["doc_id", "split"])
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit, match="train 밖 출원"):
        go(tmp_path, scrub, lb, ej, split)


def test_sha_mismatch_dies(tmp_path):
    scrub, lb, ej, split = build(tmp_path)
    victim = sorted(scrub.glob("*.txt"))[0]
    victim.write_bytes(b"L1\t\xea\xb0\x9c\xeb\xb3\x80\n")   # 산출을 손으로 고친 상황
    with pytest.raises(SystemExit, match="sha256"):
        go(tmp_path, scrub, lb, ej, split)


def test_quota_shortage_dies(tmp_path):
    """정원을 채울 수 없으면 조용히 줄이지 않고 죽는다(§1-2 — 결과를 보고 문턱을 고치지 않는다)."""
    scrub, lb, ej, split = build(tmp_path)
    m = json.loads((scrub / "_manifest.json").read_text())
    keep = [f for f in m["files"] if f["output"] != m["files"][0]["output"]]
    (scrub / m["files"][0]["output"]).unlink()
    m["files"] = keep
    (scrub / "_manifest.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="적격 후보가 정원보다 적다"):
        go(tmp_path, scrub, lb, ej, split)


def test_mark_verified_rebinds_to_bytes(tmp_path):
    scrub, lb, ej, split = build(tmp_path)
    out = tmp_path / "sample.json"
    go(tmp_path, scrub, lb, ej, split)
    assert json.loads(out.read_text())["human_verified"] is False

    d = sd.mark_verified("2026-09-24", out=out, scrub_dir=scrub)
    assert d["human_verified"] is True and d["verified_on"] == "2026-09-24"

    target = scrub / d["files"][0]["source_file"]
    target.write_bytes(target.read_bytes() + b"L2\tyy\n")     # 확인 뒤에 산출이 바뀌었다
    with pytest.raises(SystemExit, match="사람이 확인한 파일과 해부할 파일이 같지 않다"):
        sd.mark_verified("2026-09-24", out=out, scrub_dir=scrub)


def test_non_prior_art_ground_excluded_from_population(tmp_path):
    """§42 단독 통지서는 선행기술 판단이 아니므로 모집단에 들지 않는다."""
    extra = [("1029999999999_952999999999.txt", "1029999999999", "§42", False)]
    d = go(tmp_path, *build(tmp_path, extra=extra))
    assert d["population"] == sd.TOTAL
    assert "1029999999999" not in {r["application"] for r in d["files"]}
