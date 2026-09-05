#!/usr/bin/env python3
"""PLAN-005 §5 V4-2 — 사람 2인 코딩 시트 생성 (블라인드).

**왜 별도 시트가 필요한가.** `data/reports/v4_screening.csv` 를 그대로 코더에게 주면 안 된다 —
`j1`·`j2` 와 그 근거가 그대로 보이므로 **앵커링**이 생기고, 그러면 κ 가 재는 것이
*"두 사람이 독립적으로 얼마나 일치하는가"* 가 아니라 *"사람이 LLM 에 얼마나 동의했는가"* 가 된다.
이 시트는 **LLM 판정·순위·점수를 전부 뺀다.**

표본 (560쌍 중 129):
  불일치(j1≠j2)      56  전량 — LLM 이 갈린 지점의 정보량이 가장 크다
  둘다 관련           13  전량 — 희소하며 스크리너 정밀도를 재는 자리
  둘다 무관 층화표본  60  순위대(1–3/4–6/7–10) 비례배분 · 주제 순환 — 스크리너가
                          **놓친** 관련 문헌 비율을 추정하는 자리

산출은 **결정적**이다(고정 시드). 시트 자체는 청구항 원문과 arXiv 초록을 담으므로
`data/interim/`(gitignore) 에 쓴다 — 재현은 이 생성기가 보장하고, 커밋되는 것은 생성기다(§1-5).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUTDIR = ROOT / "data" / "interim" / "v4_coding"
SEED = 20260906

CODEBOOK = """# V4-2 사람 코딩 지침 (코더용)

## 무엇을 판정하는가

각 행에는 **연구 아이디어**(논문 초록)와 **후보 문헌**(특허) 하나가 있습니다.
물음은 하나입니다.

> **이 후보 문헌을, 이 연구 아이디어의 "선행기술 검토 대상"으로 볼 만한가?**

- **동일 발명일 필요는 없습니다.** 검토할 가치가 있으면 관련입니다.
- 기준은 둘 중 하나면 충족입니다 — **같은 기술 문제**를 다루거나, **같은 기술 수단**을 씁니다.
- 같은 분야라는 것만으로는 부족합니다(예: "둘 다 반도체").

## 어떻게 적는가

`relevance` 칸에 다음 하나를 적습니다.

| 값 | 뜻 |
|---|---|
| `1` | 관련 — 검토 대상으로 볼 만하다 |
| `0` | 무관 |
| `NA` | 판단 불가 — 본문이 부실하거나 내용을 알 수 없다 |

`confidence` 칸(선택): `H`(확신) / `M` / `L`(애매).
`note` 칸(선택): 한 줄 근거. **나중에 두 분의 판정이 갈린 행을 조정할 때 씁니다.**

## 규칙 넷

1. **혼자 하십시오.** 다른 코더와 상의하지 않습니다. 상의는 3단계(조정)에서 합니다.
2. **행 순서를 바꾸지 마십시오.** 두 시트는 순서가 서로 다르게 섞여 있습니다.
3. **모르면 `NA`.** 억지로 0/1 을 고르지 마십시오 — `NA` 는 집계에서 제외되고 건수만 보고됩니다.
4. 다 채우면 파일을 그대로 돌려주십시오. 컬럼을 추가·삭제하지 마십시오.

## 분량

129행입니다. 건당 1–2분이면 2~4시간입니다. 나눠서 하셔도 됩니다.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--both-no", type=int, default=60)
    ap.add_argument("--outdir", type=Path, default=OUTDIR)
    a = ap.parse_args()

    from screen_v4_candidates import load_texts
    texts = load_texts()
    notes = {n["arxiv_id"]: n for n in json.loads(
        (ROOT / "data" / "sources" / "arxiv" / "notes_cohort.json").read_text(encoding="utf-8"))["items"]}

    d = pd.read_csv(ROOT / "data" / "reports" / "v4_screening.csv")
    d = d[d.j1.notna() & d.j2.notna()].copy()
    d["cell"] = ["둘다관련" if (r.j1 and r.j2) else "둘다무관" if (not r.j1 and not r.j2)
                 else "불일치" for r in d.itertuples()]

    take = [d[d.cell == "불일치"], d[d.cell == "둘다관련"]]
    # 둘다무관 — 순위대 비례배분 후 주제 순환으로 결정적 추출
    bn = d[d.cell == "둘다무관"].copy()
    bn["band"] = pd.cut(bn["rank"], [0, 3, 6, 10], labels=["1-3", "4-6", "7-10"])
    picked = []
    for band, g in bn.groupby("band", observed=True):
        n = round(a.both_no * len(g) / len(bn))
        g = g.sort_values(["topic", "arxiv_id", "doc"])
        # 주제를 순환하며 뽑아 한 주제에 몰리지 않게 한다
        by_topic = {t: list(gg.index) for t, gg in g.groupby("topic")}
        order, i = [], 0
        while len(order) < n and any(by_topic.values()):
            for t in sorted(by_topic):
                if by_topic[t] and len(order) < n:
                    order.append(by_topic[t].pop(i % max(len(by_topic[t]), 1)))
            i += 1
        picked += order
    take.append(bn.loc[picked])
    sample = pd.concat(take).drop_duplicates(subset=["arxiv_id", "doc"])

    rows = []
    for i, r in enumerate(sample.itertuples(), 1):
        nt = notes.get(r.arxiv_id, {})
        tx = texts.get(r.doc, {})
        rows.append({
            "item_id": f"V4-{i:03d}",
            "note_title": nt.get("title", ""),
            "note_abstract": nt.get("abstract", ""),
            "doc_title": tx.get("title", ""),
            "doc_text": tx.get("body", ""),
            "relevance": "", "confidence": "", "note": "",
        })
    key = [{"item_id": f"V4-{i:03d}", "arxiv_id": r.arxiv_id, "doc": r.doc,
            "topic": r.topic, "rank": int(r.rank), "cell": r.cell,
            "j1": bool(r.j1), "j2": bool(r.j2)}
           for i, r in enumerate(sample.itertuples(), 1)]

    a.outdir.mkdir(parents=True, exist_ok=True)
    cols = ["item_id", "note_title", "note_abstract", "doc_title", "doc_text",
            "relevance", "confidence", "note"]
    for coder, seed in (("A", SEED), ("B", SEED + 1)):
        rr = rows[:]
        random.Random(seed).shuffle(rr)
        p = a.outdir / f"v4_coding_sheet_{coder}.csv"
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader(); w.writerows(rr)
        print(f"  코더 {coder}: {p}  ({len(rr)}행)")
    (a.outdir / "v4_coding_key.json").write_text(
        json.dumps({"generated": str(date.today()), "seed": SEED,
                    "note": "집계 전에는 코더에게 보여주지 않는다 — LLM 판정이 들어 있다.",
                    "items": key}, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.outdir / "CODEBOOK.md").write_text(CODEBOOK, encoding="utf-8")

    from collections import Counter
    c = Counter(k["cell"] for k in key)
    print(f"\n표본 {len(key)}행 · 셀 구성 {dict(c)}")
    print(f"키 파일: {a.outdir/'v4_coding_key.json'}  (코더 비공개)")
    print(f"지침서:  {a.outdir/'CODEBOOK.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
