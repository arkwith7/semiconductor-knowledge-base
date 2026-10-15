#!/usr/bin/env python3
"""PLAN-006 T4 §3.5 — LLM 비교군 b(LLM 단독) · d(LLM + 온톨로지 도구) (산출물 동결 · 그래프를 바꾸지 않는다).

b 와 d 는 모델·effort·입력·기본 프롬프트·검색 도구·검색 호출 상한·합집합 규칙이 **같다**. d 에만 온톨로지 도구가 있다 —
그래서 d − b 가 "LLM 에 온톨로지를 준 추가 효과" 다(§3.1′ 조건 1). 합집합은 LLM 이 아니라 시스템이 판정한다
(검색식 단위 채택 · 전체 합집합 ≤ 예산 · 절단 금지 — `build_search_query.plan_multi` 와 같은 규칙).

호출: Amazon Bedrock bedrock-runtime 전역 프로파일(`global.anthropic.claude-opus-5-5` · AnthropicBedrock · fallback 없음).
Opus 5.5 는 강제 tool_choice 를 받지 않으므로 auto + 지시로 이끈다. thinking 블록이 든 응답은 그대로 되돌려 보낸다.
보내는 것: 공개 청구항 1항·초록과 도구 결과(문헌 수·식별자 없음)뿐 — 통지서·결정서 원문은 보내지 않는다(§1-5).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

MODEL = "global.anthropic.claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 16000
SEARCH_CALLS = 12      # count_results + submit 합계 (R1 의 MULTI_MAX_RUNS 와 같다)
ONTO_CALLS = 6         # d 의 온톨로지 도구 합계
MAX_TURNS = 24
MAX_RETRIES = 3

SYNTAX = """KIPRIS-style boolean query syntax (this is exactly how queries are executed):
- `A+B` OR, `A*B` AND, `!A` NOT, parentheses for grouping, precedence ! > * > +.
- `"..."` exact phrase. Unquoted words separated by spaces are ANDed.
- Korean terms match as substrings ("식각" also matches "식각하는"). English terms match at word starts ("etch" matches "etching").
- Searched fields: title, abstract, claims. The collection contains Korean patents and English/Japanese-origin documents (mostly English text).
- Optional `ipc`: list of IPC codes (subclass "H01L", main group "H01L21", or group "H01L21/306"); old/new IPC versions are mapped automatically. A query with ipc only returns documents having one of those codes."""

SYSTEM_BASE = f"""You are a patent search specialist building structured prior-art searches for a new technical idea.
Goal: collect a candidate set that contains as many documents as possible that a patent examiner would cite against the idea
(novelty / inventive step), while the total number of unique candidate documents stays within the review budget.
Examiners often combine several documents, each disclosing only some of the idea's elements, so partial-element searches are useful.

Rules of the search system:
- `count_results` runs a query and reports how many documents it returns and how many would be new to your accepted set. It does not add anything.
- `submit` runs a query and adds ALL its documents to the accepted set only if the accepted set stays within the budget; otherwise it is rejected and nothing is added. Documents are never truncated.
- Search calls (`count_results` + `submit`) are limited in total. When you are done, reply with a short final message and no tool call.

{SYNTAX}"""

SEARCH_TOOLS = [
    {"name": "count_results", "description": "Run a query without accepting it. Returns result count, how many are new versus the accepted set, and the remaining budget.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Boolean query in the syntax described in the system prompt."},
         "ipc": {"type": "array", "items": {"type": "string"}, "description": "Optional IPC codes to restrict the query."}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "submit", "description": "Run a query and accept all its documents into the candidate set if the set stays within the budget; otherwise reject.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "ipc": {"type": "array", "items": {"type": "string"}}},
         "required": ["query"], "additionalProperties": False}},
]
ONTO_TOOLS = [
    {"name": "ontology_facets", "description": "Semiconductor ontology analysis of the idea's claim: element facets (representative Korean expression per claim element, its document frequency in the collection), verified ontology synonyms (Korean/English, linked to concept IRIs), shared Korean-to-English translations, and an element priority learned from examiner citations.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "suggest_ipc", "description": "IPC main groups associated with the idea's ontology concepts (co-occurrence in the collection).",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "lookup_term", "description": "Look up one term in the ontology: concept IRI, verified synonyms (ko/en), shared translation, document frequency.",
     "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"], "additionalProperties": False}},
]


def prompt_sha(arm: str) -> str:
    tools = SEARCH_TOOLS + (ONTO_TOOLS if arm == "d" else [])
    return hashlib.sha256(json.dumps({"system": SYSTEM_BASE, "tools": tools, "model": MODEL, "effort": EFFORT,
                                      "max_tokens": MAX_TOKENS, "search_calls": SEARCH_CALLS, "onto_calls": ONTO_CALLS},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Session:
    """한 질의의 검색 상태. 합집합 판정은 여기서 한다(LLM 이 아니라)."""

    def __init__(self, emu, q: str, budget: int, onto: dict | None):
        self.emu, self.q, self.budget, self.onto = emu, q, budget, onto
        self.union: set[str] = set()
        self.search_calls = self.onto_calls = 0
        self.log: list[dict] = []

    def _run(self, query: str, ipc):
        return set(self.emu.run(query, ipc=ipc or None, exclude=(self.q,)))

    def tool(self, name: str, inp: dict) -> str:
        if name in ("count_results", "submit"):
            if self.search_calls >= SEARCH_CALLS:
                return json.dumps({"error": "search call limit reached — finish now"})
            self.search_calls += 1
            try:
                res = self._run(inp.get("query", ""), inp.get("ipc"))
            except ValueError as e:
                self.log.append({"tool": name, "query": inp.get("query"), "ipc": inp.get("ipc"), "error": str(e)})
                return json.dumps({"error": f"invalid query: {e}", "search_calls_left": SEARCH_CALLS - self.search_calls})
            new = len(res - self.union)
            accepted = False
            if name == "submit":
                merged = self.union | res
                accepted = bool(res) and len(merged) <= self.budget
                if accepted:
                    self.union = merged
            self.log.append({"tool": name, "query": inp.get("query"), "ipc": inp.get("ipc"), "size": len(res),
                             "new": new, "accepted": accepted})
            out = {"results": len(res), "new_vs_accepted": new, "accepted_set_size": len(self.union),
                   "budget_left": self.budget - len(self.union), "search_calls_left": SEARCH_CALLS - self.search_calls}
            if name == "submit":
                out["accepted"] = accepted
            return json.dumps(out)
        if self.onto is None or name not in ("ontology_facets", "suggest_ipc", "lookup_term"):
            return json.dumps({"error": f"unknown tool {name}"})
        if self.onto_calls >= ONTO_CALLS:
            return json.dumps({"error": "ontology call limit reached"})
        self.onto_calls += 1
        self.log.append({"tool": name, "input": inp})
        if name == "ontology_facets":
            return json.dumps(self.onto["facets"], ensure_ascii=False)
        if name == "suggest_ipc":
            return json.dumps({"ipc_main_groups": self.onto["ipc"]})
        return json.dumps(self.onto["lookup"](inp.get("term", "")), ensure_ascii=False)


def _with_cache(msg: dict) -> dict:
    c = msg["content"]
    blocks = [{"type": "text", "text": c}] if isinstance(c, str) else [dict(b) if isinstance(b, dict) else b for b in c]
    last = blocks[-1]
    if isinstance(last, dict):
        blocks[-1] = {**last, "cache_control": {"type": "ephemeral"}}
        return {**msg, "content": blocks}
    return msg   # 응답 블록 객체(assistant) — 마지막이 assistant 인 경우는 없다(항상 user 로 끝난다)


def run_one(client, arm: str, claim: str, abstract: str, sess: Session) -> dict:
    tools = SEARCH_TOOLS + (ONTO_TOOLS if arm == "d" else [])
    user = (f"Review budget: at most {sess.budget} unique candidate documents. Search calls available: {SEARCH_CALLS}.\n\n"
            f"Idea (claim 1):\n{claim}\n\nAbstract:\n{abstract}")
    messages = [{"role": "user", "content": user}]
    usage = {"input_tokens": 0, "output_tokens": 0, "turns": 0}
    status = "ok"
    for _ in range(MAX_TURNS):
        # 명시적 캐시 지점(Bedrock 은 자동 캐싱 없음): 고정 접두(system·tools) + 매 턴 마지막 메시지.
        # 비용만 줄이고 요청 내용은 바꾸지 않는다. 지점은 이 요청에만 붙이고 기록용 messages 는 건드리지 않는다.
        req = messages[:-1] + [_with_cache(messages[-1])]
        resp = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS,
                                      system=[{"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}}],
                                      tools=tools, output_config={"effort": EFFORT}, messages=req)
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        usage["cache_read"] = usage.get("cache_read", 0) + (resp.usage.cache_read_input_tokens or 0)
        usage["cache_write"] = usage.get("cache_write", 0) + (resp.usage.cache_creation_input_tokens or 0)
        usage["turns"] += 1
        if resp.stop_reason == "refusal":
            status = "refusal"; break
        if resp.stop_reason == "max_tokens":
            status = "max_tokens"; break
        calls = [b for b in resp.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": resp.content})   # thinking 블록 포함 그대로
        if not calls:
            break
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": sess.tool(c.name, c.input)} for c in calls]})
    else:
        status = "max_turns"
    return {"status": status, "usage": usage, "served_model": resp.model}


def onto_context(F, ipc, lex, tr, df, jw):
    import build_search_query as Q
    facets = [{"element": f.seq, "expression": f.term, "doc_freq": f.df, "concept_iri": f.concept,
               "verified_synonyms": f.synonyms, "shared_translations": f.translations,
               "examiner_priority": round(jw.weight(f), 3) if jw else None} for f in F]

    def lookup(term: str):
        cid, syn = lex.synonyms(term)
        return {"term": term, "concept_iri": cid, "verified_synonyms": syn,
                "shared_translations": tr.ko2en.get(term, []) if tr else [], "doc_freq": df(term) if term.strip() else 0}
    return {"facets": {"facets": facets}, "ipc": ipc, "lookup": lookup}


def main(argv=None) -> int:
    import csv

    import build_search_query as Q
    import ir_corpus
    import kipris_emulator as K
    import report_t4_query as R
    from splits import SEALED, load_split

    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["b", "d"])
    ap.add_argument("--split", required=True, choices=["train", "dev"])
    ap.add_argument("--subset", default="all", choices=["all", "learn", "check"])
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--freeze", type=Path, help="dev 실행에 필요한 동결 명세")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.split in SEALED:
        raise SystemExit("ERROR: 봉인 분할은 열 수 없다")
    spec = None
    if a.split == "dev":
        if not a.freeze or not a.freeze.exists():
            raise SystemExit("ERROR: dev 는 동결 명세(--freeze) 없이 돌지 않는다")
        spec = json.loads(a.freeze.read_text(encoding="utf-8"))
        R.verify_freeze(spec)
        want = spec["llm"]["prompt_sha256"][a.arm]
        if prompt_sha(a.arm) != want:
            raise SystemExit(f"ERROR: 프롬프트가 동결값과 다르다 ({a.arm})")

    smap = load_split()
    gt = R.load_gt(a.split, smap)
    fam = {r["doc_id"]: r["family_id"] for r in csv.DictReader(open(ROOT / "benchmark" / "assets" / "split.csv", encoding="utf-8"))}
    learn = {q for q, s in smap.items() if s == "train" and Q.family_bucket(fam[q]) < Q.C3_LEARN_FRAC}
    if a.split == "train" and a.subset != "all":
        gt = {q: v for q, v in gt.items() if (q in learn) == (a.subset == "learn")}
    queries = sorted(gt)[: a.limit or None]
    C = ir_corpus.load(["doc_id", "is_candidate", "title", "abstract", "claims_full", "claims_independent",
                        "first_claim_original", "ipc", "concepts"])
    claim = dict(zip(C["doc_id"], C["first_claim_original"]))
    abstract = dict(zip(C["doc_id"], C["abstract"]))
    emu = K.Emulator(C)
    df, lex, tr = Q.DF(emu), Q.Lexicon(), Q.Translations()
    sel = jw = None
    if a.arm == "d":
        sel = Q.IpcSelector(C, exclude_docs={q for q, s in smap.items() if s != "train"})
        train_gt = R.load_gt("train", smap)
        if a.split == "train":
            learn_gt = {q: v for q, v in train_gt.items() if q in learn}
            jw = Q.JudgmentWeights(learn_gt, {d: set(v) for d, v in zip(C["doc_id"], C["concepts"]) if v is not None})
        else:
            w = spec["resources"]["c3_weights"]
            jw = Q.load_weights(ROOT / w["path"], w["sha256"])

    from dotenv import load_dotenv
    import os
    from anthropic import AnthropicBedrock
    load_dotenv(ROOT / ".env")
    client = AnthropicBedrock(aws_region=os.environ["AWS_REGION"], max_retries=MAX_RETRIES)

    done = set()
    if a.out.exists():
        done = {json.loads(l)["q"] for l in a.out.read_text(encoding="utf-8").splitlines()}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("a", encoding="utf-8") as fh:
        for i, q in enumerate(queries):
            if q in done:
                continue
            onto = None
            if a.arm == "d":
                F = tr.apply(Q.facets_elements(claim.get(q) or "", df, lex), df)
                onto = onto_context(F, sel.choose([Q.concept_local(f.concept) for f in F]), lex, tr, df, jw)
            sess = Session(emu, q, a.budget, onto)
            t0 = time.time()
            try:
                meta = run_one(client, a.arm, claim.get(q) or "", abstract.get(q) or "", sess)
            except Exception as e:  # 권한·요청 오류는 멈춘다 — 일시 오류는 SDK 가 이미 재시도했다
                import anthropic
                if isinstance(e, (anthropic.PermissionDeniedError, anthropic.BadRequestError, anthropic.NotFoundError)):
                    raise
                meta = {"status": f"error:{type(e).__name__}", "usage": {}, "served_model": None}
            hit = sorted(sess.union & gt[q])
            fh.write(json.dumps({"q": q, "arm": a.arm, "budget": a.budget, **meta, "seconds": round(time.time() - t0, 1),
                                 "union": sorted(sess.union), "hit_ids": hit, "hit": len(hit), "gt": len(gt[q]),
                                 "search_calls": sess.search_calls, "onto_calls": sess.onto_calls, "log": sess.log},
                                ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{i + 1}/{len(queries)} {q} {meta['status']} hit {len(hit)}/{len(gt[q])} union {len(sess.union)} "
                  f"calls {sess.search_calls}+{sess.onto_calls} tok {meta['usage']}", flush=True)
    print(f"prompt_sha {prompt_sha(a.arm)[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
