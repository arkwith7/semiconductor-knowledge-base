#!/usr/bin/env python3
"""공개 트리 검사기 — 원문이 한 조각도 남지 않았는지 **기계로** 센다 (CR-015 성공기준 ①②).

grep 한 번으로는 부족하다. 원문은 데이터셋 파일에만 있는 것이 아니라 노트북 셀 출력·리포트·
문서 예시로도 샌다 — 실제로 이 저장소에서 **노트북 07 의 출력 하나**가 그랬고, 그것은
파일명을 보고 찾은 것이 아니라 지문 대조로 나왔다.

방법: 비공개 정본에서 특허마다 원문 지문(연속 60자)을 뽑아, 공개 트리의 **모든 텍스트
파일**에서 찾는다. 하나라도 걸리면 실패다.

지문을 60자로 잡은 이유 — 너무 짧으면 흔한 기술 표현이 걸려 거짓 경보가 나고, 너무 길면
줄바꿈·공백이 다른 사본을 놓친다. 초록·claim1·claims_full 앞 두 항에서 각각 뽑는다.

**이 검사기가 통과해야 푸시한다.** 순서를 뒤집으면 되돌릴 수 없다 — 공개된 커밋은 지워도
포크·캐시·PR ref 로 남는다.

CLI:
    python scripts/check_public_release.py --tree /tmp/sdkb-public
    python scripts/check_public_release.py --tree /tmp/sdkb-public --canonical <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
PROBE_LEN = 60
PROBE_OFFSET = 40          # 앞머리(청구항 번호·정형 문구)를 피한다
MAX_BYTES = 200 * 1024 * 1024


def build_probes(canonical: Path) -> tuple[list[tuple[str, str, str]], int]:
    """(출원번호, 필드, 지문) 목록과 **버린 지문 수**.

    **남기기로 한 필드와 겹치는 지문은 버린다.** 제목은 공개한다(서지이고 이미
    `kipris_biblio.parquet` 에 커밋돼 있다). 그런데 초록이 제목을 되풀이해 시작하는
    특허가 있어서, 그런 지문은 공개 트리에서 반드시 걸린다 — 누출이 아니라 **제목**인데도.
    실제로 첫 실행에서 2건(1020190091628 · 1020230169126)이 그렇게 잡혔다.

    남기는 필드에 이미 있는 문자열은 **누출과 정상 발행을 구분하지 못하므로** 지문 자격이
    없다. 임계를 낮추는 것이 아니라 **판별력 없는 지문을 빼는 것**이다 — 버린 개수를
    보고해 조용히 줄어들지 않게 한다.
    """
    probes: list[tuple[str, str, str]] = []
    dropped = 0
    for line in canonical.open(encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        tp = rec.get("target_patent") or {}
        app = str(tp.get("application_number") or "?")
        retained = " ".join(str(tp.get(k) or "") for k in ("title", "ipc", "date"))

        def add(field: str, value: str) -> None:
            nonlocal dropped
            v = (value or "").strip()
            if len(v) <= PROBE_OFFSET + PROBE_LEN:
                return
            probe = v[PROBE_OFFSET:PROBE_OFFSET + PROBE_LEN]
            if probe in retained:
                dropped += 1
                return
            probes.append((app, field, probe))

        for f in ("abstract", "claim1"):
            add(f, tp.get(f) or "")
        for c in (tp.get("claims_full") or [])[:2]:
            add(f"claims_full[{c.get('claim_no')}]", c.get("text") or "")
    return probes, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True, help="검사할 공개 트리")
    ap.add_argument("--canonical", type=Path, default=CANONICAL,
                    help="지문을 뽑을 비공개 정본")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    if not args.canonical.exists():
        raise SystemExit(f"ERROR: 정본이 없다 — {args.canonical}. 지문 없이는 검사가 무의미하다.")

    probes, dropped = build_probes(args.canonical)
    by_text = {}
    for app, field, text in probes:
        by_text.setdefault(text, (app, field))
    print(f"[check] 지문 {len(probes)}개 ({len(by_text)}개 고유) · "
          f"판별력 없어 버린 지문 {dropped}개 · 트리 {args.tree}")

    files = [p for p in args.tree.rglob("*")
             if p.is_file() and ".git" not in p.parts and p.stat().st_size <= MAX_BYTES]
    hits: list[dict] = []
    scanned = 0
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned += 1
        for text, (app, field) in by_text.items():
            if text in txt:
                hits.append({"file": str(p.relative_to(args.tree)),
                             "application_number": app, "field": field,
                             "probe": text[:30] + "…"})

    print(f"[check] {scanned}개 파일 검사 · 적중 {len(hits)}건")
    for h in hits[:40]:
        print(f"   ✗ {h['file']}  ← {h['application_number']} {h['field']}")
    if len(hits) > 40:
        print(f"   … 그리고 {len(hits) - 40}건 더")

    if args.report:
        args.report.write_text(json.dumps(
            {"tree": str(args.tree), "probes": len(probes),
             "probes_dropped_overlapping_retained_fields": dropped,
             "files_scanned": scanned, "hits": hits}, ensure_ascii=False, indent=2), encoding="utf-8")

    if hits:
        print("\n[check] ❌ 실패 — 원문이 남아 있다. **푸시하지 않는다.**")
        return 1
    print("\n[check] ✅ 통과 — 지문 어느 것도 공개 트리에 없다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
