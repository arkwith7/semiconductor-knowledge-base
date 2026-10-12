#!/usr/bin/env python3
"""PLAN-006 T4 — 라이브 KIPRIS 표본 확인: 검색 문법·필드·매칭 동작이 에뮬레이터와 같은가 (읽기 전용 · T4 v1 결과를 바꾸지 않는다).

목적은 **전체 결과 집합 일치가 아니다** — KIPRIS 전체 DB 와 로컬 코퍼스는 모집단·갱신 시점이 다르다. 대신
(1) 같은 검색식이 라이브에서 몇 건인지(전문 검색 `word` 와 필드 한정 각각) (2) 라이브 결과를 **모두** 받은 검색식에 한해
로컬 코퍼스 문헌과 교차해 에뮬레이터가 넘치게·모자라게 맞히는지를 본다. 일부 페이지만 받은 검색식에서 "미발견" 을 불일치로 판정하지 않는다.

표본(결정적 · 시드 고정): dev b·d 로그의 채택 검색식 · 예산 초과로 거부된 검색식 · 0 건 검색식 · 연산자(OR·AND·괄호·구문·NOT) ·
영어 포함 · IPC 한정 검색식을 층마다 뽑는다. 보낸 파라미터·검색 필드·페이지 처리·실행 시각을 모두 기록한다.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SEED = 20261012
PAGE_ROWS = 500          # 라이브 페이지 크기(요청값 — 실제 반환 수는 기록)
FULL_FETCH_MAX = 1500    # 이 이하 총건수만 전부 받아 교차 비교한다
STRATA = {"accepted": 6, "rejected_over_budget": 4, "zero_result": 3, "phrase": 3, "not": 2, "english": 3, "ipc": 3}


def load_logs(paths):
    rows = []
    for p in paths:
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            for e in r["log"]:
                if e.get("tool") in ("count_results", "submit") and "error" not in e and e.get("query"):
                    rows.append({"q": r["q"], "arm": r["arm"], **e})
    return rows


def sample(rows):
    rnd = random.Random(SEED)
    pick, used = [], set()

    def take(name, pred, n):
        pool = sorted([r for r in rows if pred(r) and (r["query"], tuple(r.get("ipc") or ())) not in used],
                      key=lambda r: (r["q"], r["arm"], r["query"]))
        rnd.shuffle(pool)
        for r in pool[:n]:
            used.add((r["query"], tuple(r.get("ipc") or ())))
            pick.append({**r, "stratum": name})

    take("accepted", lambda r: r["tool"] == "submit" and r.get("accepted") and not r.get("ipc"), STRATA["accepted"])
    take("rejected_over_budget", lambda r: r["tool"] == "submit" and not r.get("accepted") and r.get("size", 0) > 0, STRATA["rejected_over_budget"])
    take("zero_result", lambda r: r.get("size") == 0, STRATA["zero_result"])
    take("phrase", lambda r: '"' in r["query"], STRATA["phrase"])
    take("not", lambda r: "!" in r["query"], STRATA["not"])
    take("english", lambda r: re.search(r"[A-Za-z]{3,}", r["query"]) is not None and not r.get("ipc"), STRATA["english"])
    take("ipc", lambda r: bool(r.get("ipc")), STRATA["ipc"])
    return pick


def main(argv=None) -> int:
    import ir_corpus
    import kipris_emulator as K
    from dotenv import load_dotenv
    from kipris_dataset.kipris import KiprisClient

    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", type=Path, default=[ROOT / "data/queries/t4_dev_v1/dev_b.jsonl", ROOT / "data/queries/t4_dev_v1/dev_d.jsonl"])
    ap.add_argument("--out", type=Path, default=ROOT / "data/reports/t4_live_check_v1.json")
    a = ap.parse_args(argv)
    load_dotenv(ROOT / ".env")
    client = KiprisClient(os.environ["KIPRIS_API_KEY"], min_request_interval=0.6)

    C = ir_corpus.load(["doc_id", "is_candidate", "title", "abstract", "claims_full", "claims_independent", "ipc", "application_number"])
    emu = K.Emulator(C)
    an2doc = {}
    for d, an in zip(C["doc_id"], C["application_number"]):
        if isinstance(an, str) and an:
            an2doc[re.sub(r"\D", "", an)] = d

    def live(params, fetch_all=False):
        base = {**params, "patent": "true", "utility": "true", "numOfRows": PAGE_ROWS if fetch_all else 1, "pageNo": 1}
        resp = client.get("getAdvancedSearch", base).get("response", {})
        total = int((resp.get("count") or {}).get("totalCount") or -1)
        out = {"params_sent": {k: v for k, v in base.items()}, "total": total, "fetched": 0, "pages": 0, "app_numbers": []}
        if not fetch_all or total < 0 or total > FULL_FETCH_MAX:
            return out
        page, ans = 1, []
        while True:
            items = (((resp.get("body") or {}).get("items") or {}).get("item")) or []
            items = [items] if isinstance(items, dict) else items
            ans += [re.sub(r"\D", "", str(it.get("applicationNumber", ""))) for it in items]
            out["pages"] = page
            if len(ans) >= total or not items:
                break
            page += 1
            resp = client.get("getAdvancedSearch", {**base, "pageNo": page}).get("response", {})
        out["fetched"], out["app_numbers"] = len(ans), sorted(set(ans))
        return out

    picks = sample(load_logs(a.logs))
    results = []
    for p in picks:
        q, ipc = p["query"], p.get("ipc") or []
        local = emu.run(q, ipc=ipc or None)
        local_kr = sorted(d for d in local if d.startswith("kr_"))
        rec = {"stratum": p["stratum"], "arm": p["arm"], "query": q, "ipc": ipc, "logged_size": p.get("size"),
               "local_size": len(local), "local_kr": len(local_kr), "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        ipc_param = {"ipcNumber": ipc[0]} if ipc else {}
        rec["live_word"] = live({"word": q, **ipc_param}, fetch_all=True)
        for field, key in (("claimScope", "live_claims"), ("astrtCont", "live_abstract"), ("inventionTitle", "live_title")):
            rec[key] = live({field: q, **ipc_param})
        lw = rec["live_word"]
        if lw["fetched"] and lw["fetched"] >= lw["total"] > 0:
            live_docs = {an2doc[n] for n in lw["app_numbers"] if n in an2doc}
            rec["cross"] = {"live_in_corpus": len(live_docs),
                            "local_kr_missing_in_live": len(set(local_kr) - live_docs),
                            "live_in_corpus_missing_locally": len(live_docs - set(local))}
        else:
            rec["cross"] = "라이브 결과를 모두 받지 않음(총건수 > %d 또는 실패) — 교차 판정 안 함" % FULL_FETCH_MAX
        if len(ipc) > 1:
            rec["note"] = "API 는 ipcNumber 하나만 받는다 — 첫 코드만 보냄"
        for k in ("live_word",):
            rec[k] = {kk: vv for kk, vv in rec[k].items() if kk != "app_numbers"}
        results.append(rec)
        print(json.dumps({k: rec[k] for k in ("stratum", "local_size", "logged_size")}, ensure_ascii=False),
              rec["live_word"]["total"], rec["live_claims"]["total"], rec["cross"] if isinstance(rec["cross"], dict) else "-", flush=True)
    out = {"name": "T4 라이브 KIPRIS 표본 확인 v1", "seed": SEED, "operation": "getAdvancedSearch",
           "page_rows": PAGE_ROWS, "full_fetch_max": FULL_FETCH_MAX, "strata": STRATA, "logs": [str(p) for p in a.logs],
           "corpus_sha256": ir_corpus.manifest()["sha256"], "results": results}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
