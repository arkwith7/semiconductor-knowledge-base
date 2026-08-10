#!/usr/bin/env python3
"""공개 트리 검사기 — 원문·비공개 문서·홈 절대경로·옛 리포 URL 이 남지 않았는지 **기계로** 센다.

넷을 본다 (CR-015 성공기준 ①② + R1·F7 + R3).
  ① KIPRIS 원문 지문 — 아래 본문
  ② **비공개 토큰**: 첫 줄이 `<!-- sdkb:private -->` 인 파일이 트리에 있는가
  ③ **홈 절대경로**: 사용자 홈으로 시작하는 파일시스템 경로가 남았는가
  ④ **옛 리포 URL**: 공개 전 리포 슬러그를 가리키는 링크가 남았는가 (R3 · 점검 F3)

④ 가 필요한 이유는 ③ 과 같다 — 한 번 발행되면 되돌릴 수 없고, 죽은 링크는 공개 첫날 보인다.
잡는 것은 **슬러그 문자열 전량**이지 URL 형태만이 아니다: BibTeX·CITATION·Pages 링크가 서로
다른 형태로 같은 이름을 쓰기 때문에 URL 패턴으로 좁히면 셋 중 하나를 놓친다.

②③ 이 왜 검사기에도 있나 — 생성기가 이미 거른다. 그러나 생성기만 있으면 **사람이 손으로
만든 트리**를 못 잡고, 검사기만 있으면 매번 사람이 지워야 한다. 되돌릴 수 없는 경로라
거르는 층과 확인하는 층을 나눈다.


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

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_public_release import _ABS_PATH, PRIVATE_TOKEN, is_private_doc  # noqa: E402
from config.namespaces import LEGACY_REPO_SLUG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "patents" / "raw" / "semiconductor_industry_rejected_patents.jsonl"
PROBE_LEN = 60
PROBE_OFFSET = 40          # 앞머리(청구항 번호·정형 문구)를 피한다
MAX_BYTES = 200 * 1024 * 1024

# 옛 슬러그를 **인용하는 것이 그 파일의 일**인 곳. 목록은 코드에 두고 사유를 적는다 —
# 파일이 스스로 면제를 선언하게 하면(인라인 마커) 그것은 검사가 아니라 우회로가 된다(§1-6).
LEGACY_SLUG_ALLOWED = {
    # F3 은 "온톨로지가 옛 리포를 가리킨다"가 결함이라는 증거로 그 URL 을 그대로 인용한다.
    # 인용을 지우면 무엇이 왜 틀렸는지 읽을 수 없게 된다.
    "docs/public_release_readiness_review.md",
    # 이 검사가 찾는 문자열을 **정의하는** 파일. 검사기가 첫 실행에서 스스로 잡아냈다 —
    # 여기를 빼면 슬러그를 상수로 두는 것 자체가 불가능해진다.
    "config/namespaces.py",
}


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


def scan_boundary(files: list[Path], tree: Path) -> tuple[list[str], list[dict], list[dict]]:
    """비공개 토큰 파일 · 홈 절대경로 · 옛 리포 슬러그를 찾는다 (R1·F7 + R3).

    토큰은 **첫 줄에서만** 본다 — 본문에서 토큰을 언급하는 문서는 그것을 설명하는 것이지
    선언하는 것이 아니다. 절대경로 정규식은 URL 경로 안의 같은 문자열을 잡지 않는다
    (생성기 주석 참조).
    """
    private: list[str] = []
    abs_hits: list[dict] = []
    legacy_hits: list[dict] = []
    for p in files:
        try:
            raw = p.read_bytes()
        except Exception:
            continue
        rel = str(p.relative_to(tree))
        if is_private_doc(raw):
            private.append(rel)
        txt = raw.decode("utf-8", errors="ignore")
        for m in _ABS_PATH.finditer(txt):
            abs_hits.append({"file": rel, "path": m.group(0)})
        if LEGACY_REPO_SLUG in txt and rel not in LEGACY_SLUG_ALLOWED:
            legacy_hits.append({"file": rel, "count": txt.count(LEGACY_REPO_SLUG)})
    return private, abs_hits, legacy_hits


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

    # sorted: rglob 순서는 파일시스템 의존이다. 적중 목록의 순서가 흔들리면 리포트 diff 가
    # 거짓 변경을 낸다.
    files = sorted(p for p in args.tree.rglob("*")
                   if p.is_file() and ".git" not in p.parts and p.stat().st_size <= MAX_BYTES)
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

    private, abs_hits, legacy_hits = scan_boundary(files, args.tree)
    print(f"[check] 비공개 토큰({PRIVATE_TOKEN}) 적중 {len(private)}건 · "
          f"홈 절대경로 적중 {len(abs_hits)}건 · "
          f"옛 리포 슬러그({LEGACY_REPO_SLUG}) 적중 {len(legacy_hits)}건 "
          f"(인용 허용 {len(LEGACY_SLUG_ALLOWED)}파일 제외)")
    for rel in private[:20]:
        print(f"   ✗ {rel}  ← 첫 줄 비공개 선언")
    for h in abs_hits[:20]:
        print(f"   ✗ {h['file']}  ← {h['path']}")
    for h in legacy_hits[:20]:
        print(f"   ✗ {h['file']}  ← 옛 리포 슬러그 {h['count']}회")

    # 리포트는 커밋된다 — 여기서 절대경로를 적으면 그것이 다음 공개본의 누출이 된다.
    try:
        tree_label = str(args.tree.resolve().relative_to(ROOT))
    except ValueError:
        tree_label = args.tree.name

    if args.report:
        args.report.write_text(json.dumps(
            {"tree": tree_label, "probes": len(probes),
             "probes_dropped_overlapping_retained_fields": dropped,
             "files_scanned": scanned, "hits": hits,
             "private_token_hits": private, "absolute_path_hits": abs_hits,
             "legacy_repo_slug_hits": legacy_hits,
             "legacy_repo_slug_allowed": sorted(LEGACY_SLUG_ALLOWED)},
            ensure_ascii=False, indent=2), encoding="utf-8")

    if hits or private or abs_hits or legacy_hits:
        why = " · ".join(w for w, n in (("원문", len(hits)), ("비공개 문서", len(private)),
                                        ("홈 절대경로", len(abs_hits)),
                                        ("옛 리포 URL", len(legacy_hits))) if n)
        print(f"\n[check] ❌ 실패 — {why} 가 남아 있다. **푸시하지 않는다.**")
        return 1
    print("\n[check] ✅ 통과 — 지문·비공개 토큰·홈 절대경로·옛 리포 URL "
          "어느 것도 공개 트리에 없다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
