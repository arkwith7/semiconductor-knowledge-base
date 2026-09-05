#!/usr/bin/env python3
"""PLAN-005 §5 V4-2 — 연구노트 프록시 코호트 수집 (arXiv).

**이것은 연구노트가 아니라 프록시다. 그렇게 적는다.**
arXiv 초록은 학술 논문 문체이고 연구노트는 비정형 메모다. V4-1 의 L3(연구노트 메모 문체)
과 함께 읽어야 하며, 단독으로 *"연구노트에서 작동한다"* 의 근거가 되지 않는다.

**코호트를 코퍼스에 맞춘다.** SDKB 코퍼스는 소자물리가 아니라 **반도체 제조공정**이다
(IPC C23C 215 · H10B 196 · H10P 142 / process_family deposition 330 · etch 234 ·
metallization 82). arXiv 반도체 논문의 다수는 물성·소자 쪽이라 주제가 어긋나면 회수 0 이
나오고, 그때 *"도구가 안 통한다"* 와 *"코호트가 안 맞는다"* 가 구분되지 않는다.
그래서 검색어를 `process_family` 축에 맞추고, **개념 접지 0건을 따로 보고한다.**

**정답지는 없다.** 코퍼스의 NPL 엣지는 91건(심사관 유래 30건)뿐이라 arXiv 참고문헌을
정답으로 쓸 경로가 없다. 그래서 V4-2 는 사람 판정이 필요하다(PLAN-004 §4-1 순환 금지).

라이선스: arXiv API 이용약관(https://arxiv.org/help/api/tou) 아래 메타데이터(제목·초록)만
가져온다. 전문 PDF 는 받지 않는다. 출처별 조건은 산출물에 기록한다(§1-5).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sources" / "arxiv" / "notes_cohort.json"
API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

# 검색어는 코퍼스의 process_family 분포에서 나왔다 — 임의로 고르지 않는다.
TOPICS = {
    "deposition": '(abs:"atomic layer deposition" OR abs:"chemical vapor deposition" OR abs:"thin film deposition")',
    "etch": '(abs:"plasma etching" OR abs:"reactive ion etching" OR abs:"dry etching")',
    "metallization": '(abs:"interconnect metallization" OR abs:"copper interconnect" OR abs:"barrier layer")',
    "photo": '(abs:"photolithography" OR abs:"EUV lithography" OR abs:"photoresist")',
    "oxidation_diffusion": '(abs:"thermal oxidation" OR abs:"dopant diffusion" OR abs:"annealing" AND abs:"semiconductor")',
    "memory": '(abs:"resistive switching" OR abs:"NAND flash" OR abs:"DRAM capacitor")',
    "implant": '(abs:"ion implantation" AND abs:"semiconductor")',
}
CATS = '(cat:cond-mat.mtrl-sci OR cat:physics.app-ph OR cat:cond-mat.mes-hall)'


def fetch(topic: str, expr: str, n: int) -> list[dict]:
    q = f"{expr} AND {CATS}"
    url = (f"{API}?search_query={urllib.parse.quote(q)}"
           f"&start=0&max_results={n}&sortBy=relevance")
    with urllib.request.urlopen(url, timeout=60) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.findall("a:entry", NS):
        aid = (e.findtext("a:id", "", NS) or "").rsplit("/", 1)[-1]
        out.append({
            "arxiv_id": aid,
            "topic": topic,
            "title": " ".join((e.findtext("a:title", "", NS) or "").split()),
            "abstract": " ".join((e.findtext("a:summary", "", NS) or "").split()),
            "published": (e.findtext("a:published", "", NS) or "")[:10],
            "categories": [c.get("term") for c in e.findall("a:category", NS)],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-topic", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    rows, seen = [], set()
    for topic, expr in TOPICS.items():
        try:
            got = fetch(topic, expr, a.per_topic)
        except Exception as e:  # noqa: BLE001
            print(f"  {topic}: 실패 {type(e).__name__} {str(e)[:100]}")
            continue
        new = [g for g in got if g["arxiv_id"] not in seen]
        seen.update(g["arxiv_id"] for g in new)
        rows += new
        print(f"  {topic:20} 응답 {len(got):3} · 신규 {len(new):3}")
        time.sleep(3)  # arXiv API 예의 (3초 간격)

    rep = {
        "generated": str(date.today()),
        "plan": "PLAN-005 §5 V4-2 (연구노트 프록시 코호트)",
        "proxy_note": ("arXiv 초록은 연구노트가 아니라 **프록시**다 — 학술 논문 문체이며 "
                       "비정형 연구 메모가 아니다. 단독으로 '연구노트에서 작동한다'의 근거가 되지 않는다."),
        "cohort_rationale": ("검색어는 코퍼스 process_family 분포(deposition 330 · etch 234 · "
                             "metallization 82 · memory 58 · oxidation_diffusion 47 · photo 46 · "
                             "implant 38)에서 유도했다. 임의 선정이 아니다."),
        "license": {"source": "arXiv API", "terms": "https://arxiv.org/help/api/tou",
                    "scope": "메타데이터(제목·초록)만. 전문 PDF 는 받지 않는다.",
                    "note": "재배포 조건은 arXiv 약관을 따른다 — 공개 파생 경로에 넣지 않는다(§1-5)."},
        "n": len(rows), "items": rows,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n수집 {len(rows)}건 → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
