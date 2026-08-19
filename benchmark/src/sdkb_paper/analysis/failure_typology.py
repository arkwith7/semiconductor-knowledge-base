"""실패 유형 분류 — 온톨로지 팔이 **악화시킨** 질의의 코딩 (C4 · PLAN-048 §10).

**이 모듈이 하는 일과 하지 않는 일.** P1 의 점수식은 동결 상수이므로 *"어느 항이 역전을
만들었는가"* 는 **계산할 수 있다**. 계산할 수 없는 것은 *"왜 그 항이 그렇게 나왔는가"* 이고,
그것만 코더(로컬 LLM 2종 + 사람 표본)에게 묻는다. 그래서 이 모듈은 **숫자를 전부 만들고
라벨은 하나도 만들지 않는다** — CLAUDE.md §1-7(수기 기입 금지)이 이 구조에서 자동으로 지켜진다.

**동결 대상(PLAN-048 §10.2·§10.5).** 모집단 규칙(하락 임계 20) · 경쟁 문서 수 3 ·
사람 표본 40 · 시드 20260809 · 유형 7종 · 모델 태그 · 프롬프트 sha256. 결과를 본 뒤 고치지 않는다.

**산출물은 특허 본문을 포함하므로 `data/processed/` 아래에만 쓴다**(§1-5 · gitignore).
커밋되는 것은 집계표(`paper/tables/failure_typology.md`)뿐이다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from .metrics import SPLIT_B, load_run
from .results_table import P1_ALPHA, P1_TAU, P1_W4, _split_qrel, run_path

# --- 동결 상수 (PLAN-048 §10.2) ---------------------------------------------
SEV_RANK_DROP = 20          # 중대 하락 임계(위)
N_COMPETITORS = 3           # 밀려난 정답을 앞지른 문서 중 몇 건을 보여주는가
HUMAN_SAMPLE = 40           # 사람 코딩 표본 크기
SEED = 20260809
EXCERPT_CHARS = 1200        # 코딩 시트 본문 발췌 길이

TYPES: dict[str, str] = {
    "F1": "과잉일반 개념 — 공유된 개념이 이 분야에서 너무 흔해 변별력이 없다",
    "F2": "개념 오부착 — 표층 문자열 때문에 잘못 붙은 개념이 점수를 만들었다",
    "F3": "정답 자원 결손 — 밀려난 문헌에 개념이 없거나 질의와 공유가 0이다",
    "F4": "청구항 특징 오정렬 — 임베딩상 가깝지만 실제 기술 내용은 다르다",
    "F5": "분류 밀집 — 같은 IPC 분류 문서가 많아 분류 항이 변별하지 못했다",
    "F6": "텍스트 우위 희석 — 온톨로지 항은 유리했으나 텍스트 순위 우위가 눌렸다",
    "F7": "판단 불가 — 주어진 재료로 유형을 정할 수 없다",
}

TYPOLOGY_DIR = config.IR_DIR / "typology"
PROMPT_PATH = Path(__file__).with_name("typology_prompt.txt")

# 점수식 항 이름 → (가중치) · P1_W4 = (w_c, w_h, w_i, w_f)
_WC, _WH, _WI, _WF = P1_W4


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# --- 1. 모집단 추출 ----------------------------------------------------------
@dataclass
class Pair:
    """코딩 단위 = (질의, 밀려난 정답 문헌) 한 쌍."""

    split: str
    qid: str
    lost_fam: str               # 밀려난 정답(family 식별자)
    lost_doc: str               # 그 family 를 대표해 순위에 오른 문서
    rank_b3: int
    rank_p1: int
    r100_loss: bool             # 이 질의가 R@100 에서도 졌는가
    competitors: list[str] = field(default_factory=list)   # P1 이 위로 올린 문서(문서 단위)

    @property
    def drop(self) -> int:
        return self.rank_p1 - self.rank_b3

    @property
    def key(self) -> str:
        return f"{self.split}:{self.qid}:{self.lost_fam}"


def _fold(docs: list[str], fam: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """fold-then-cut 과 같은 접기 — family 순위와 대표 문서를 함께 돌려준다."""
    out: list[str] = []
    rep: dict[str, str] = {}
    for d in docs:
        f = fam.get(d, d)
        if f in rep:
            continue
        rep[f] = d
        out.append(f)
    return out, rep


def population(split: str, *, unseal: bool = False, reason: str = "") -> list[Pair]:
    """동결 규칙 `R@100 패 ∨ 순위 하락 ≥ 20` 을 만족하는 (질의, 밀려난 정답) 쌍 전량."""
    from ..collect.bq_family_ir import load_family_map

    qrel = _split_qrel(split, unseal=unseal, reason=reason)
    fam = load_family_map()
    b3 = load_run(run_path("B3_rrf", split))
    p1 = load_run(run_path("P1", split))

    pairs: list[Pair] = []
    for qid, pos in qrel.items():
        if not pos:
            continue
        posf = {fam.get(d, d) for d in pos}
        fb3, _ = _fold(b3.get(qid, []), fam)
        fp1, rep1 = _fold(p1.get(qid, []), fam)
        rb3 = {f: i + 1 for i, f in enumerate(fb3)}
        rp1 = {f: i + 1 for i, f in enumerate(fp1)}
        r100_loss = (len({f for f in fp1[:100]} & posf)
                     < len({f for f in fb3[:100]} & posf))
        for f in posf:
            if f not in rb3 or f not in rp1:
                continue
            drop = rp1[f] - rb3[f]
            if drop <= 0:
                continue
            if not (r100_loss or drop >= SEV_RANK_DROP):
                continue
            comp = [rep1[g] for g in fp1[: rp1[f] - 1]
                    if g in rb3 and rb3[g] > rb3[f]][-N_COMPETITORS:]
            pairs.append(Pair(split=split, qid=qid, lost_fam=f, lost_doc=rep1[f],
                              rank_b3=rb3[f], rank_p1=rp1[f], r100_loss=r100_loss,
                              competitors=comp))
    pairs.sort(key=lambda p: (p.qid, p.lost_fam))
    return pairs


# --- 2. 기계 분해 ------------------------------------------------------------
def _component_rows(split: str, qids: list[str], docs: set[str]) -> dict[str, dict[str, tuple]]:
    """질의별 {doc: (text_norm, concept, path, ipc, fc)} — P1 이 실제로 쓴 항 그대로."""
    from ..retrieval import layers
    from ..retrieval.candidate import CandidateMask
    from ..retrieval.feature_coverage import FeatureCoverageIndex
    from ..retrieval.hybrid import RUN_B3
    from ..retrieval.ontology_rerank import OntologyFeatures
    from .ontology_eval import TAUS, component_cache_p1

    layer = layers.LAYER_B if split == SPLIT_B else layers.LAYER_A
    b3_raw = load_run(layers.run_path_for_layer(RUN_B3, layer))
    pool_docs = set(qids) | docs
    for q in qids:
        pool_docs.update(b3_raw.get(q, []))
    feats = OntologyFeatures()
    mask = CandidateMask()
    fc = FeatureCoverageIndex(restrict_docs=pool_docs)
    cache = component_cache_p1(feats, mask, b3_raw, qids, fc)
    ti = list(TAUS).index(P1_TAU)
    return {q: {d: (tn, c, p, ic, f[ti]) for d, tn, c, p, ic, f in rows}
            for q, rows in cache.items()}


def score_terms(row: tuple) -> dict[str, float]:
    """항별 **점수 기여도**(가중치 반영). 합 = P1 최종 점수."""
    tn, c, p, ic, f = row
    return {
        "text": (1.0 - P1_ALPHA) * tn,
        "concept": P1_ALPHA * _WC * c,
        "path": P1_ALPHA * _WH * p,
        "ipc": P1_ALPHA * _WI * ic,
        "feature": P1_ALPHA * _WF * f,
    }


def decompose(lost_row: tuple, comp_row: tuple) -> dict:
    """경쟁 문서가 밀려난 정답을 앞지른 이유의 항별 분해 — 결정적."""
    a, b = score_terms(lost_row), score_terms(comp_row)
    delta = {k: b[k] - a[k] for k in a}
    gap = sum(delta.values())
    driver = max(delta, key=lambda k: delta[k])
    # 분모는 **밀어 올린 힘의 총량**(양의 델타 합)이다. 순 격차(gap)를 분모로 쓰면 상쇄가
    # 일어난 사례에서 비율이 1 을 크게 넘어 해석 불가능해진다 — 실제로 그랬다.
    push = sum(v for v in delta.values() if v > 0)
    return {"lost": a, "competitor": b, "delta": delta, "gap": gap,
            "driver": driver, "driver_share": (delta[driver] / push) if push > 0 else 0.0}


TERM_KO = {"text": "본문 점수", "concept": "개념 겹침", "path": "개념 계층",
           "ipc": "IPC 분류 유사도", "feature": "청구항 특징 커버리지"}


def explain(comp_slot: str, focus_slot: str, dec: dict) -> str:
    """분해를 사람이 읽는 한 문장으로. **코더가 영어 필드명을 오독하는 것을 막는다**(실측)."""
    d = dec["delta"]
    up = " · ".join(f"{TERM_KO[k]} +{v:.4f}" for k, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0)
    down = " · ".join(f"{TERM_KO[k]} {v:.4f}" for k, v in sorted(d.items(), key=lambda x: x[1]) if v < 0)
    return (f"{comp_slot} 이 {focus_slot} 보다 앞선 것은 [{up or '없음'}] 때문이고, "
            f"[{down or '없음'}] 에서는 뒤졌다. 가장 크게 밀어 올린 것은 "
            f"{TERM_KO[dec['driver']]}(밀어 올린 힘의 {dec['driver_share']:.0%})다.")


# --- 3. 코딩 시트 ------------------------------------------------------------
def _corpus_view(doc_ids: set[str]) -> dict[str, dict]:
    import pandas as pd

    cols = ["doc_id", "lang", "ipc", "concepts", "claims_independent", "text_main", "title"]
    df = pd.read_parquet(config.IR_CORPUS, columns=cols)
    df = df[df["doc_id"].isin(doc_ids)]
    links = pd.read_parquet(config.IR_CONCEPT_LINKS) if config.IR_CONCEPT_LINKS.exists() else None
    lk: dict[str, list[dict]] = {}
    if links is not None:
        links = links[links["doc_id"].isin(doc_ids)]
        for r in links.itertuples():
            lk.setdefault(r.doc_id, []).append(
                {"slug": r.slug, "surface": r.surface, "rule_id": r.rule_id,
                 "ambiguous": bool(r.ambiguous), "confidence": float(r.confidence)})
    out = {}
    for r in df.itertuples():
        out[r.doc_id] = {
            "lang": r.lang,
            "ipc": list(r.ipc) if r.ipc is not None else [],
            "concepts": list(r.concepts) if r.concepts is not None else [],
            "links": lk.get(r.doc_id, []),
            "claims": (r.claims_independent or "")[:EXCERPT_CHARS],
            "text": (r.text_main or "")[:EXCERPT_CHARS],
        }
    return out


def build_sheet(split: str, *, unseal: bool = False, reason: str = "") -> tuple[Path, Path]:
    """코딩 시트(가림)와 열쇠 파일을 쓴다. 반환 (sheet, key).

    **가림 범위**: 팔 이름(B3/P1)·순위 수치·정답 여부를 시트에서 제거하고 문서를 셔플해
    `문서 1..N` 으로 익명화한다. **기계 분해는 보여주므로 완전 가림은 아니다**(PLAN-048 §10.4).
    """
    pairs = population(split, unseal=unseal, reason=reason)
    qids = sorted({p.qid for p in pairs})
    docs = {p.lost_doc for p in pairs} | {c for p in pairs for c in p.competitors}
    rows = _component_rows(split, qids, docs)
    view = _corpus_view(docs | set(qids))

    TYPOLOGY_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = TYPOLOGY_DIR / f"sheet_{split}.jsonl"
    key_path = TYPOLOGY_DIR / f"key_{split}.jsonl"
    rng = random.Random(SEED)

    with sheet_path.open("w", encoding="utf-8") as sf, key_path.open("w", encoding="utf-8") as kf:
        for p in pairs:
            qrow = rows.get(p.qid, {})
            if p.lost_doc not in qrow:
                continue
            cand = [p.lost_doc] + [c for c in p.competitors if c in qrow]
            order = list(range(len(cand)))
            rng.shuffle(order)
            items, dec = [], []
            for slot, idx in enumerate(order, 1):
                d = cand[idx]
                v = view.get(d, {})
                items.append({"slot": f"문서 {slot}", **v})
                if idx != 0:      # 경쟁 문서만 분해 대상
                    dd = decompose(qrow[p.lost_doc], qrow[d])
                    dec.append({"slot": f"문서 {slot}", "요약": explain(f"문서 {slot}",
                                                                      f"문서 {order.index(0) + 1}", dd),
                                **dd})
            sf.write(json.dumps({
                "unit_id": p.key,
                "query": {"claims": view.get(p.qid, {}).get("claims", ""),
                          "concepts": view.get(p.qid, {}).get("concepts", []),
                          "links": view.get(p.qid, {}).get("links", []),
                          "ipc": view.get(p.qid, {}).get("ipc", []),
                          "lang": view.get(p.qid, {}).get("lang", "")},
                "documents": items,
                "focus_slot": f"문서 {order.index(0) + 1}",
                "decomposition": dec,
            }, ensure_ascii=False) + "\n")
            kf.write(json.dumps({
                "unit_id": p.key, "qid": p.qid, "lost_fam": p.lost_fam,
                "lost_doc": p.lost_doc, "rank_b3": p.rank_b3, "rank_p1": p.rank_p1,
                "drop": p.drop, "r100_loss": p.r100_loss, "competitors": p.competitors,
                "driver": (dec[0]["driver"] if dec else None),
            }, ensure_ascii=False) + "\n")
    return sheet_path, key_path


def human_sample(splits: tuple[str, ...] = ("test", "test_b"), n: int = HUMAN_SAMPLE) -> Path:
    """사람 코더용 층화 무작위 표본 — **두 층을 합쳐 n 건**(설계 §10.2). 시드 동결.

    층 = (분할 × 역전 주도항). 층별 배분은 크기 비례이며, 각 층에 최소 1건을 준 뒤 넘치면
    사전순으로 잘라 **정확히 n 건**을 만든다. 층이 비면 그 층은 그냥 빠진다 — 채우지 않는다.
    """
    keys: list[dict] = []
    for split in splits:
        key_path = TYPOLOGY_DIR / f"key_{split}.jsonl"
        if not key_path.exists():
            continue
        for x in key_path.read_text(encoding="utf-8").splitlines():
            if x:
                k = json.loads(x)
                k["_split"] = split
                keys.append(k)
    if not keys:
        raise FileNotFoundError("열쇠 파일이 없다 — 시트를 먼저 생성한다")
    strata: dict[str, list[str]] = {}
    for k in keys:
        strata.setdefault(f"{k['_split']}|{k.get('driver') or 'none'}", []).append(k["unit_id"])
    rng = random.Random(SEED)
    picked: list[str] = []
    for s in sorted(strata):
        ids = sorted(strata[s])
        rng.shuffle(ids)
        share = max(1, round(n * len(ids) / len(keys)))
        picked.extend(ids[:share])
    picked = sorted(set(picked))[:n]
    out = TYPOLOGY_DIR / "human_sample.json"
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# --- 4. 신뢰도 --------------------------------------------------------------
def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's κ — 두 라벨 열의 우연 보정 일치도. 빈 입력은 0.0."""
    if not a or len(a) != len(b):
        return 0.0
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 0.0 if pe == 1.0 else (po - pe) / (1.0 - pe)


def agreement(a: list[str], b: list[str]) -> float:
    return (sum(x == y for x, y in zip(a, b)) / len(a)) if a and len(a) == len(b) else 0.0


# --- 5. LLM 코딩 (로컬 · 순차 · 동결 계측기) ---------------------------------
MODELS = ("gemma3:27b", "qwen3-coder:30b")
REPS = 2
TEMPERATURE = 0.0
NUM_PREDICT = 512
OLLAMA_URL = "http://localhost:11434/api/generate"

# **태그가 아니라 다이제스트가 버전이다**(§1-11 넷째). `gemma3:27b` 는 나중에 다른 가중치를
# 가리킬 수 있으므로, 재현 명세에는 다이제스트·아키텍처·파라미터 수·양자화를 함께 적는다.
MODEL_SPEC: dict[str, dict[str, str]] = {
    "gemma3:27b": {"digest": "a418f5838eaf", "arch": "gemma3", "params": "27.4B",
                   "quant": "Q4_K_M", "ctx": "131072"},
    "qwen3-coder:30b": {"digest": "06c1097efce0", "arch": "qwen3moe", "params": "30.5B",
                        "quant": "Q4_K_M", "ctx": "262144"},
}

# 사례 **뒤에** 다시 붙이는 지시. 긴 입력에서 앞쪽 지시는 묻힌다 — 실측으로 확인했다.
CLOSING = ("위 사례에서 `focus_slot` 문서가 밀려난 이유의 유형을 하나 고르십시오. "
           "F1~F7 중 하나입니다. JSON 하나만 출력하십시오.")


# 출력 스키마를 **디코딩 단계에서 강제**한다. 프롬프트로만 부탁하면 모델은 산문으로
# 답한다 — 실측으로 확인했다(gemma3:27b 6/6 파싱 실패 · 전부 한국어 분석문). C2′ §17.2 는
# 펜스 뒤 산문이었고 여기는 JSON 자체가 없었다. 그래서 파서를 고치는 대신 **디코더를 묶는다.**
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "primary": {"type": "string", "enum": ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]},
        "secondary": {"type": ["string", "null"]},
        "evidence": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["primary", "evidence", "confidence"],
}


def _ollama(model: str, prompt: str, seed: int) -> str:
    """로컬 ollama 1회 호출. **순차 전용** — 이 장비는 병렬 시 VRAM 이 넘친다."""
    import urllib.request

    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "format": OUTPUT_SCHEMA,
        "options": {"temperature": TEMPERATURE, "seed": seed, "num_predict": NUM_PREDICT},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8")).get("response", "")


def parse_label(raw: str) -> dict | None:
    """엄격 JSON 파싱. 펜스 뒤 산문은 C2′ §17.2 와 같은 고장이라 **같은 파서를 재사용**한다."""
    from ..rag.score import strip_code_fence

    try:
        obj = json.loads(strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or obj.get("primary") not in TYPES:
        return None
    return obj


def code_with_llm(split: str, *, models=MODELS, reps: int = REPS,
                  limit: int | None = None) -> Path:
    """시트 전수를 모델별·반복별로 코딩해 원라벨을 남긴다(집계하지 않는다)."""
    sheet = TYPOLOGY_DIR / f"sheet_{split}.jsonl"
    units = [json.loads(x) for x in sheet.read_text(encoding="utf-8").splitlines() if x]
    if limit:
        units = units[:limit]
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    out_path = TYPOLOGY_DIR / f"labels_llm_{split}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for model in models:
            for rep in range(reps):
                for i, u in enumerate(units, 1):
                    prompt = (instructions + "\n\n## 사례\n\n"
                              + json.dumps(u, ensure_ascii=False) + "\n\n" + CLOSING)
                    raw = _ollama(model, prompt, seed=SEED + rep)
                    lab = parse_label(raw)
                    f.write(json.dumps({
                        "unit_id": u["unit_id"], "model": model, "rep": rep,
                        "primary": (lab or {}).get("primary"),
                        "secondary": (lab or {}).get("secondary"),
                        "evidence": (lab or {}).get("evidence"),
                        "confidence": (lab or {}).get("confidence"),
                        "parse_ok": lab is not None,
                        # 실패는 진단 가능해야 한다 — 첫 구현이 원문을 버려 원인을 못 봤다.
                        "raw_head": None if lab else raw[:400],
                        "prompt_sha256": sha256_text(instructions),
                    }, ensure_ascii=False) + "\n")
                    f.flush()
                    if i % 10 == 0:
                        print(f"  {model} rep{rep}: {i}/{len(units)}", flush=True)
    return out_path


# --- 5b. 사람 코더 작업지 --------------------------------------------------
def build_worksheet(splits: tuple[str, ...] = ("test", "test_b")) -> tuple[Path, Path]:
    """사람 표본 40쌍을 **읽는 문서**로 렌더링하고 빈 라벨 서식을 함께 낸다.

    **이 함수는 무엇도 동결값을 바꾸지 않는다** — 표본도 유형 정의도 프롬프트도 그대로이고,
    바뀌는 것은 *보여주는 방식*뿐이다. 사람에게 JSONL 을 직접 읽히면 코딩 품질이 재료가 아니라
    가독성에 좌우된다.
    """
    ids = json.loads((TYPOLOGY_DIR / "human_sample.json").read_text(encoding="utf-8"))
    want = set(ids)
    units: dict[str, dict] = {}
    for split in splits:
        p = TYPOLOGY_DIR / f"sheet_{split}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line:
                u = json.loads(line)
                if u["unit_id"] in want:
                    units[u["unit_id"]] = u

    out = [
        "# 실패 유형 코딩 작업지 — 사람 코더용 (PLAN-048)", "",
        f"**{len(units)}건**입니다. 각 건마다 `primary` 하나를 고르고 근거를 한 문장 적으십시오.", "",
        "## 무엇을 판단하는가", "",
        "어떤 검색 시스템이 본문 점수에 **온톨로지 신호**(개념 겹침 · IPC 분류 유사도 · 청구항 특징",
        "커버리지)를 섞어 순위를 다시 매겼습니다. 그 결과 **정답 문헌 하나가 아래로 밀렸습니다.**",
        "각 건의 `밀려난 문서`가 그것입니다. **왜 밀렸는지의 유형**을 고르는 것이 당신의 일입니다.", "",
        "어느 항이 밀었는지는 이미 계산돼 있습니다(각 건의 `무엇이 밀어냈는가`). 당신이 답하는 것은",
        "**그 항이 왜 그렇게 나왔는가**입니다.", "",
        "## 유형", "",
    ]
    out += [f"- **{c}** — {d}" for c, d in TYPES.items()]
    out += [
        "", "**F7 을 피하려 억지로 고르지 마십시오.** 재료가 부족하면 F7 이 맞는 답입니다.", "",
        "## 적는 방법", "",
        "`data/processed/ir/typology/labels_human.jsonl` 에 한 줄씩 적습니다",
        "(빈 서식이 `labels_human_template.jsonl` 로 나와 있으니 `primary` 와 `evidence` 만 채우면 됩니다).", "",
        '```json',
        '{"unit_id": "test:kr_1020210107301:42826412", "primary": "F5", "evidence": "세 경쟁 문서 모두 IPC만으로 앞섰고 개념·본문에서는 뒤졌다"}',
        '```', "",
        "> **LLM 이 매긴 라벨을 보기 전에** 하십시오(`labels_llm_*.jsonl` 을 열지 마십시오).",
        "> 먼저 보면 사람–모델 일치도가 검증이 아니라 따라 적기가 됩니다.", "",
        "---", "",
    ]

    for i, uid in enumerate(sorted(units), 1):
        u = units[uid]
        q = u["query"]
        out += [f"## {i}. `{uid}`", "",
                f"**밀려난 문서: {u['focus_slot']}**", "",
                "### 질의 특허", "",
                f"- 언어 `{q['lang']}` · IPC `{', '.join(q['ipc'][:6]) or '없음'}`",
                f"- 붙은 개념: `{', '.join(q['concepts']) or '없음'}`", ""]
        if q["links"]:
            out.append("- 개념이 붙은 근거(표층어 → 개념):")
            seen = set()
            for lk in q["links"]:
                sig = (lk["slug"], lk["surface"])
                if sig in seen:
                    continue
                seen.add(sig)
                amb = " ⚠모호" if lk["ambiguous"] else ""
                out.append(f"  - `{lk['surface']}` → `{lk['slug']}` "
                           f"(규칙 {lk['rule_id']} · 확신 {lk['confidence']:.2f}{amb})")
            out.append("")
        out += ["- 독립항:", "", "> " + (q["claims"][:700].replace("\n", " ") or "(없음)"), ""]

        out += ["### 후보 문헌", ""]
        for d in u["documents"]:
            mark = " ← **밀려난 문서**" if d["slot"] == u["focus_slot"] else ""
            out += [f"**{d['slot']}**{mark}", "",
                    f"- 언어 `{d['lang']}` · IPC `{', '.join(d['ipc'][:6]) or '없음'}`",
                    f"- 개념: `{', '.join(d['concepts']) or '없음'}`",
                    "- 본문: " + (d["text"][:500].replace("\n", " ") or "(없음)"), ""]

        out += ["### 무엇이 밀어냈는가 (계산된 것 · 판단 아님)", ""]
        out += [f"- {x['요약']}" for x in u["decomposition"]]
        out += ["", "### 당신의 판단", "",
                "```json",
                f'{{"unit_id": "{uid}", "primary": "F_", "evidence": ""}}',
                "```", "", "---", ""]

    ws = TYPOLOGY_DIR / "worksheet_human.md"
    ws.write_text("\n".join(out) + "\n", encoding="utf-8")
    tpl = TYPOLOGY_DIR / "labels_human_template.jsonl"
    tpl.write_text("\n".join(
        json.dumps({"unit_id": uid, "primary": "", "evidence": ""}, ensure_ascii=False)
        for uid in sorted(units)) + "\n", encoding="utf-8")
    return ws, tpl


# --- 6. 집계 표 (수기 기입 금지 · §1-7) --------------------------------------
HUMAN_LABELS = TYPOLOGY_DIR / "labels_human.jsonl"
TABLE_PATH = config.TABLES / "failure_typology.md"


def _load_labels(split: str) -> list[dict]:
    p = TYPOLOGY_DIR / f"labels_llm_{split}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]


def llm_consensus(rows: list[dict]) -> dict[str, str | None]:
    """두 모델의 합의 라벨 — **일치할 때만** 값을 준다. 불일치는 None(다수결 금지 · §10.6)."""
    per_model: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        if r["parse_ok"]:
            per_model.setdefault(r["unit_id"], {}).setdefault(r["model"], []).append(r["primary"])
    out: dict[str, str | None] = {}
    for uid, bym in per_model.items():
        # 모델별 대표 = 반복 2회가 같을 때만. 반복이 갈리면 그 모델은 기권.
        reps = {m: (v[0] if len(set(v)) == 1 else None) for m, v in bym.items()}
        vals = [v for v in reps.values() if v]
        out[uid] = vals[0] if len(vals) == len(MODELS) and len(set(vals)) == 1 else None
    return out


def self_consistency(rows: list[dict]) -> dict[str, float]:
    """모델별 반복 2회 라벨 일치 비율 — 온도 0 에서도 보고한다(§1-11 셋째)."""
    byu: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        if r["parse_ok"]:
            byu.setdefault((r["model"], r["unit_id"]), []).append(r["primary"])
    out: dict[str, list[int]] = {}
    for (m, _u), v in byu.items():
        out.setdefault(m, []).append(1 if len(v) > 1 and len(set(v)) == 1 else 0)
    return {m: (sum(v) / len(v) if v else 0.0) for m, v in out.items()}


def f3_eligible(split: str) -> dict[str, bool]:
    """단위별 **F3 자격**(밀려난 문헌에 개념이 없거나 질의와 공유 0) — 기계가 계산한다.

    F3 은 *밀려난 문헌의 상태*로 정의되고 F1·F4·F5 는 *역전의 메커니즘*으로 정의된다. 두 축이
    섞여 있어 한 사례가 양쪽에 해당할 수 있으므로, 겹침을 **표에 드러낸다** — 라벨을 고치지 않고.
    """
    import pandas as pd

    from ..collect.bq_family_ir import load_family_map

    key_path = TYPOLOGY_DIR / f"key_{split}.jsonl"
    if not key_path.exists():
        return {}
    df = pd.read_parquet(config.IR_CORPUS, columns=["doc_id", "concepts"])
    con = {r.doc_id: (set(r.concepts) if r.concepts is not None and len(r.concepts) else set())
           for r in df.itertuples()}
    fam = load_family_map()
    famcon: dict[str, set] = {}
    for d, s in con.items():
        famcon.setdefault(fam.get(d, d), set()).update(s)

    def cs(x: str) -> set:
        return famcon.get(x) or con.get(x) or set()

    out = {}
    for line in key_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        k = json.loads(line)
        out[k["unit_id"]] = len(cs(k["qid"]) & cs(k["lost_fam"])) == 0
    return out


def build_table(splits: tuple[str, ...] = ("test", "test_b")) -> Path:
    """κ·합의율·유형 빈도 → 논문 표. 사람 라벨이 없으면 **그 사실을 표에 적는다**."""
    from collections import Counter

    human = {}
    if HUMAN_LABELS.exists():
        for x in HUMAN_LABELS.read_text(encoding="utf-8").splitlines():
            if x:
                r = json.loads(x)
                human[r["unit_id"]] = r["primary"]

    lines = ["# 실패 유형 분류 — 온톨로지 팔이 악화시킨 질의 (C4 · PLAN-048)", "",
             "> **LLM 보조 코딩 + 사람 표본 검증**이며 2인 전문가 독립 코딩이 아니다(§5.3).",
             "> 가림은 팔 소속과 정답 여부에 대한 것이고, 기계 분해를 보여주므로 **완전 가림이",
             "> 아니다**(§10.4). 코드가 생성한다 — 수기 기입 없음.", ""]
    # --- 계측기 재현 명세 (§1-11 첫째·넷째) ---------------------------------
    lines += ["## 계측기 명세 (동결 · 결과를 본 뒤 고치지 않았다)", "",
              "| 코더 | 다이제스트 | 아키텍처 | 파라미터 | 양자화 | 문맥 길이 |",
              "|---|---|---|---|---|---|"]
    for m in MODELS:
        s = MODEL_SPEC.get(m, {})
        lines.append(f"| `{m}` | `{s.get('digest', '?')}` | {s.get('arch', '?')} | "
                     f"{s.get('params', '?')} | {s.get('quant', '?')} | {s.get('ctx', '?')} |")
    lines += ["",
              "**태그가 아니라 다이제스트가 버전이다** — 태그는 나중에 다른 가중치를 가리킬 수 있다.", "",
              "| 항목 | 값 |", "|---|---|",
              f"| 실행 | 로컬 ollama (`{OLLAMA_URL}`) · **순차**(`LLM_WORKERS=1`) · 유료 호출 0 |",
              f"| 온도 | {TEMPERATURE} |",
              f"| 시드 | {SEED} (반복 r 에서 {SEED}+r) |",
              f"| 반복 | {REPS} 회 (자기일치율 보고용) |",
              f"| 최대 생성 토큰 | {NUM_PREDICT} |",
              "| 출력 강제 | ollama `format` 에 JSON Schema — `primary` 는 F1–F7 **enum** |",
              f"| 컨텍스트 구성 | 질의 독립항 + 밀려난 정답 + 경쟁 문서 **{N_COMPETITORS}건** · "
              f"본문 발췌 각 **{EXCERPT_CHARS}자** · 기계 분해(항별 델타 + 한국어 요약) |",
              "| 문서 제시 | 슬롯 익명화 + 질의별 셔플(시드 동결) · 팔 이름·순위·정답 여부 제거 |"]
    if PROMPT_PATH.exists():
        pt = PROMPT_PATH.read_text(encoding="utf-8")
        lines += [f"| 프롬프트 | `src/sdkb_paper/analysis/typology_prompt.txt` "
                  f"({len(pt)}자) · sha256 `{sha256_text(pt)}` |",
                  "| 지시 위치 | 사례 **앞**(유형 정의·판단 재료) + 사례 **뒤**(1문장 재지시) |"]
    lines += ["", "> 프롬프트 전문은 저장소에 커밋돼 있고 sha256 이 위 값과 일치해야 한다.",
              "> 모델·프롬프트·파라미터가 바뀌면 재측정이 아니라 **새 실험**이다(§1-11 넷째).", ""]

    for split in splits:
        rows = _load_labels(split)
        lines.append(f"## {split}")
        lines.append("")
        if not rows:
            lines += ["**미수행** — 코딩 라벨이 없다.", ""]
            continue
        n_unit = len({r["unit_id"] for r in rows})
        ok = sum(r["parse_ok"] for r in rows)
        lines.append(f"코딩 단위 {n_unit} · 호출 {len(rows)} · 파싱 성공률 {ok / len(rows):.3f}")
        sc = self_consistency(rows)
        lines.append("자기일치율(반복 2회): " + " · ".join(f"{m} {v:.3f}" for m, v in sorted(sc.items())))

        # 모델 간 κ — 두 모델 모두 rep0 이 파싱된 단위만
        pick = {}
        for r in rows:
            if r["parse_ok"] and r["rep"] == 0:
                pick.setdefault(r["unit_id"], {})[r["model"]] = r["primary"]
        both = sorted(u for u, d in pick.items() if len(d) == len(MODELS))
        a = [pick[u][MODELS[0]] for u in both]
        b = [pick[u][MODELS[1]] for u in both]
        lines.append(f"κ(모델1, 모델2) = **{cohen_kappa(a, b):.3f}** · 합의율 {agreement(a, b):.3f} "
                     f"(n={len(both)}) — 재현성 진단이지 코더 간 신뢰도가 아니다")

        # **쏠림을 드러낸다.** 한 범주로 몰린 코딩은 합의율을 높이면서 정보를 주지 않는다 —
        # κ 만 보면 그 사실이 보이지 않으므로 모델별 최빈 범주 점유율을 함께 싣는다.
        for m in MODELS:
            labs = [r["primary"] for r in rows if r["parse_ok"] and r["model"] == m]
            if not labs:
                continue
            c = Counter(labs)
            top, cnt = c.most_common(1)[0]
            lines.append(f"- {m} 라벨 분포 {dict(sorted(c.items()))} · "
                         f"최빈 {top} {cnt / len(labs):.3f} · 사용 범주 {len(c)}/7")

        cons = llm_consensus(rows)
        pairs = [(human[u], cons[u]) for u in cons
                 if u in human and cons.get(u)]
        if pairs:
            hk = cohen_kappa([x for x, _ in pairs], [y for _, y in pairs])
            lines.append(f"**κ(사람, LLM 합의) = {hk:.3f}** · 합의율 "
                         f"{agreement([x for x, _ in pairs], [y for _, y in pairs]):.3f} "
                         f"(n={len(pairs)}) → {'본문' if hk >= 0.4 else '부록'}(§10.6)")
        else:
            lines.append("**κ(사람, LLM 합의) = 미수행** — 사람 표본 코딩이 아직 없다. "
                         "이 표는 그때까지 **부록 후보**다(§10.6).")
        lines += ["", "| 유형 | 정의 | LLM 합의 빈도 | 비율 |", "|---|---|---:|---:|"]
        freq = Counter(v for v in cons.values() if v)
        tot = sum(freq.values()) or 1
        for code, desc in TYPES.items():
            lines.append(f"| {code} | {desc} | {freq.get(code, 0)} | {freq.get(code, 0) / tot:.3f} |")
        undecided = sum(1 for v in cons.values() if not v)
        lines += ["", f"두 모델이 갈려 합의가 서지 않은 단위 **{undecided}** — 다수결로 만들지 않는다.", ""]

        # --- 사람 라벨 (표본) — LLM 합의가 무너진 이상 **유일한 유효 신호**다 ---
        hs = {u: v for u, v in human.items() if u.startswith(split + ":")}
        if not hs:
            continue
        keys = {}
        kp = TYPOLOGY_DIR / f"key_{split}.jsonl"
        if kp.exists():
            for line in kp.read_text(encoding="utf-8").splitlines():
                if line:
                    k = json.loads(line)
                    keys[k["unit_id"]] = k
        elig = f3_eligible(split)
        lines += [f"### 사람 표본 라벨 (n={len(hs)} · 단독 코더 · LLM 출력 열람 전)", "",
                  "| 유형 | 빈도 | 비율 | 그중 **F3 자격**(개념 공유 0) |", "|---|---:|---:|---:|"]
        hf = Counter(hs.values())
        for code in TYPES:
            n = hf.get(code, 0)
            e = sum(1 for u, v in hs.items() if v == code and elig.get(u))
            lines.append(f"| {code} | {n} | {n / len(hs):.3f} | {e} |")
        drv = Counter((keys.get(u, {}).get("driver"), v) for u, v in hs.items())
        lines += ["", "기계 주도항 × 사람 라벨: "
                  + " · ".join(f"{d}→{lab} {n}" for (d, lab), n in sorted(drv.items(), key=lambda x: -x[1])),
                  "",
                  "> **F3 자격 열이 유형 축의 겹침을 드러낸다.** F3 은 *밀려난 문헌의 상태*로, "
                  "F1·F4·F5 는 *역전의 메커니즘*으로 정의돼 있어 한 사례가 양쪽에 해당할 수 있다. "
                  "코더는 지배적 원인을 골랐고, 겹침은 κ 를 구조적으로 낮춘다. "
                  "**정의는 동결돼 있으므로 고치지 않고 드러낸다.**", ""]

    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TABLE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TABLE_PATH


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실패 유형 분류 (PLAN-048)")
    ap.add_argument("--split", default="test")
    ap.add_argument("--unseal", action="store_true")
    ap.add_argument("--reason", default="PLAN-048 실패 유형 코딩 시트 (탐색적)")
    ap.add_argument("--sample", type=int, default=HUMAN_SAMPLE)
    ap.add_argument("--code", action="store_true", help="로컬 LLM 코딩 실행(시트가 이미 있어야 한다)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--table", action="store_true", help="κ·빈도표 산출")
    ap.add_argument("--worksheet", action="store_true", help="사람 코더 작업지 생성")
    a = ap.parse_args(argv)
    if a.worksheet:
        ws, tpl = build_worksheet()
        print(f"작업지 → {ws}\n빈 서식 → {tpl}")
        return 0
    if a.table:
        print(f"표 → {build_table()}")
        return 0
    if a.code:
        out = code_with_llm(a.split, limit=a.limit)
        rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x]
        ok = sum(r["parse_ok"] for r in rows)
        print(f"코딩 {len(rows)}행 · 파싱 성공 {ok} ({ok / len(rows):.3f}) → {out}")
        return 0
    sheet, key = build_sheet(a.split, unseal=a.unseal, reason=a.reason)
    n = sum(1 for _ in sheet.open(encoding="utf-8"))
    hs = human_sample(n=a.sample)
    print(f"코딩 단위 {n} → {sheet}")
    print(f"열쇠 {key}")
    print(f"사람 표본 {len(json.loads(hs.read_text(encoding='utf-8')))} → {hs}")
    print(f"프롬프트 sha256 = {sha256_text(PROMPT_PATH.read_text(encoding='utf-8'))[:16]}…"
          if PROMPT_PATH.exists() else "프롬프트 파일 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
