#!/usr/bin/env python3
"""§5(1)+§5(2) real examiner-GT prior-art evaluation (plan §7.4-1/2).

The collection (paper_data Phase B) removed the single bottleneck: examiner
citations are now ~93.5 % in-corpus, so retrieval can finally be scored
against the REAL cited prior art instead of the IPC-4 proxy used by nb 04/07.

Query  : the 1000 SIRP rejected patents (title+abstract+claim1).
Corpus : data/patents/fulltext_corpus.parquet, has_content==True only
         (stub filter — plan §7.3-2).
GT     : prior_art_edges.parquet, source_type=='examiner', ~is_npl
         (NPL excluded from the patent-recall denominator — plan §7.3-4),
         cited_doc_id intersected with the content corpus.

Rankers (same corpus, same metric code S.pa_metrics):
  tfidf      — title+abstract TF-IDF cosine (numpy inverted index)  = §5(1) floor
  onto       — shared ontology-concept count (bridge extraction)
  onto_idf   — corpus-IDF-weighted shared concepts (A6)
  hybrid     — Reciprocal-Rank Fusion(tfidf, onto_idf)             = §5(2)

Outputs data/reports/prior_art_realgt_report.json. §5(2) incremental recall
and a KR-vs-foreign breakdown (foreign = lexically-dissimilar, where a
domain ontology is expected to add the most) are reported explicitly.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
META = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
CORPUS = ROOT / "data" / "patents" / "fulltext_corpus.parquet"
OUT = ROOT / "data" / "reports" / "prior_art_realgt_report.json"

_TOK = re.compile(r"[0-9A-Za-z]+|[가-힣]+")


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for m in _TOK.finditer((text or "").lower()):
        w = m.group(0)
        if w.isascii():
            if len(w) >= 2:
                out.append(w)
        else:  # Hangul: 2-gram (matches nb04's ngram(1,2) spirit for CJK)
            out += [w] + [w[i:i + 2] for i in range(len(w) - 1)]
    return out


def tfidf_index(corpus_texts: list[str]):
    """Inverted index {term: [(doc_idx, tfidf_weight)]} + doc L2 norms."""
    N = len(corpus_texts)
    df: Counter = Counter()
    tfs: list[Counter] = []
    for t in corpus_texts:
        tf = Counter(tokenize(t))
        tfs.append(tf)
        df.update(tf.keys())
    idf = {w: math.log((N + 1) / (d + 1)) + 1.0 for w, d in df.items()}
    inv: dict[str, list[tuple[int, float]]] = defaultdict(list)
    norms = [0.0] * N
    for i, tf in enumerate(tfs):
        s = 0.0
        for w, c in tf.items():
            wt = (1.0 + math.log(c)) * idf[w]
            inv[w].append((i, wt))
            s += wt * wt
        norms[i] = math.sqrt(s) or 1.0
    return inv, idf, norms


def tfidf_rank(query: str, inv, idf, norms, n_docs: int) -> dict[int, int]:
    qtf = Counter(tokenize(query))
    qvec = {w: (1.0 + math.log(c)) * idf[w]
            for w, c in qtf.items() if w in idf}
    qn = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
    score = defaultdict(float)
    for w, qw in qvec.items():
        for di, dw in inv.get(w, ()):  # inverted index = only nonzero docs
            score[di] += qw * dw
    sims = sorted(((s / (qn * norms[di]), di) for di, s in score.items()),
                  reverse=True)
    return {di: r + 1 for r, (_, di) in enumerate(sims)}


def concepts(br, text: str) -> set[str]:
    return {nid for hits in br.extract_from_text(text).values()
            for nid, _ in hits}


def rank_from_scores(scores: dict[int, float]) -> dict[int, int]:
    order = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return {di: r + 1 for r, (di, sc) in enumerate(order) if sc > 0}


def main() -> int:
    meta = pd.read_parquet(META)
    edges = pd.read_parquet(EDGES)
    corp = pd.read_parquet(CORPUS)
    corp = corp[corp["has_content"]].reset_index(drop=True)  # §7.3-2 stub filter

    cid = corp["doc_id"].tolist()
    cidx = {d: i for i, d in enumerate(cid)}
    corp_country = corp["country"].tolist()
    corp_text = [f"{t} {a}" for t, a in zip(corp["title"], corp["abstract"])]

    ex = edges[(edges["source_type"] == "examiner") & (~edges["is_npl"])]
    gt: dict[str, list[str]] = defaultdict(list)
    for tp, cd in zip(ex["target_patent_id"], ex["cited_doc_id"]):
        if cd in cidx:
            gt[tp].append(cd)

    by_pid = meta.set_index("patent_id")
    targets = [t for t in gt if t in by_pid.index]
    print(f"corpus(content)={len(cid)}  evaluable targets={len(targets)} "
          f"(>=1 examiner GT in content corpus)")

    print("indexing TF-IDF …")
    inv, idf, norms = tfidf_index(corp_text)

    print("extracting corpus ontology concepts …")
    br = S.make_bridge(ROOT, morph=False)  # kiwi absent → documented substring
    corp_concepts = [concepts(br, t) for t in corp_text]
    cdf: Counter = Counter()
    for cs in corp_concepts:
        cdf.update(cs)
    Nc = len(cid)
    cidf = {c: math.log(Nc / df) for c, df in cdf.items()}
    concept_docs: dict[str, list[int]] = defaultdict(list)
    for i, cs in enumerate(corp_concepts):
        for c in cs:
            concept_docs[c].append(i)

    METHODS = ("tfidf", "onto", "onto_idf", "hybrid")
    agg: dict[str, list[dict]] = {m: [] for m in METHODS}
    # §5(2): recall@50 hit flags per GT positive, split KR vs foreign
    rec_flags = {m: {"KR": [0, 0], "FOREIGN": [0, 0]} for m in METHODS}

    for n, tp in enumerate(targets, 1):
        row = by_pid.loc[tp]
        qtext = f"{row.get('title') or ''} {row.get('abstract') or ''} {row.get('claim1') or ''}"
        pos = [c for c in gt[tp] if c in cidx]
        if not pos:
            continue
        self_idx = cidx.get(tp.replace("patent:kr_", "KR-P-"))

        r_tfidf = tfidf_rank(qtext, inv, idf, norms, len(cid))
        qc = concepts(br, qtext)
        s_onto: dict[int, float] = defaultdict(float)
        s_oidf: dict[int, float] = defaultdict(float)
        for c in qc:
            for di in concept_docs.get(c, ()):
                s_onto[di] += 1.0
                s_oidf[di] += cidf.get(c, 0.0)
        r_onto = rank_from_scores(s_onto)
        r_oidf = rank_from_scores(s_oidf)

        # RRF hybrid (k=60) over tfidf + onto_idf
        rrf = defaultdict(float)
        for rk in (r_tfidf, r_oidf):
            for di, rr in rk.items():
                rrf[di] += 1.0 / (60 + rr)
        r_hyb = rank_from_scores(rrf)

        big = len(cid) + 1
        for m, rmap in (("tfidf", r_tfidf), ("onto", r_onto),
                        ("onto_idf", r_oidf), ("hybrid", r_hyb)):
            pranks = []
            for c in pos:
                di = cidx[c]
                if di == self_idx:
                    continue
                pranks.append(rmap.get(di, big))
                bucket = "KR" if corp_country[di] == "KR" else "FOREIGN"
                rec_flags[m][bucket][1] += 1
                if rmap.get(di, big) <= 50:
                    rec_flags[m][bucket][0] += 1
            if pranks:
                agg[m].append(S.pa_metrics(pranks))
        if n % 200 == 0:
            print(f"  …{n}/{len(targets)}")

    def mean(rows, k):
        return round(sum(r[k] for r in rows) / len(rows), 4) if rows else 0.0

    summary = {
        m: {
            "n": len(agg[m]),
            "MRR": mean(agg[m], "mrr"),
            "NDCG@5": mean(agg[m], "ndcg_at_5"),
            "Recall@10": mean(agg[m], "recall_at_10"),
            "Recall@50": mean(agg[m], "recall_at_50"),
        } for m in METHODS
    }

    def rr(m, b):
        hit, tot = rec_flags[m][b]
        return round(hit / tot, 4) if tot else 0.0

    incremental = {
        "Recall@50_tfidf": {b: rr("tfidf", b) for b in ("KR", "FOREIGN")},
        "Recall@50_hybrid": {b: rr("hybrid", b) for b in ("KR", "FOREIGN")},
        "delta_hybrid_minus_tfidf": {
            b: round(rr("hybrid", b) - rr("tfidf", b), 4)
            for b in ("KR", "FOREIGN")
        },
        "gt_positives_in_corpus": {
            b: rec_flags["tfidf"][b][1] for b in ("KR", "FOREIGN")
        },
    }

    report = {
        "corpus_content_docs": len(cid),
        "evaluable_targets": len(targets),
        "ranker_summary": summary,
        "incremental_recall_sec5_2": incremental,
        "notes": [
            "Real examiner GT (not IPC-4 proxy) — first measurable after P0/B1.",
            "bridge morph=False (kiwipiepy absent): documented substring fallback.",
            "NPL excluded from denominator (plan §7.3-4); stub docs excluded (§7.3-2).",
            "FOREIGN = non-KR cited (JP/US/…): lexically dissimilar to KR query "
            "text, where the domain ontology is expected to add the most (§5-2).",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("\n=== ranker summary (real examiner GT) ===")
    for m in METHODS:
        s = summary[m]
        print(f"  {m:9} n={s['n']:4}  MRR={s['MRR']:.4f}  "
              f"NDCG@5={s['NDCG@5']:.4f}  R@10={s['Recall@10']:.4f}  "
              f"R@50={s['Recall@50']:.4f}")
    print("\n=== §5(2) incremental recall@50 (hybrid − tfidf) ===")
    for b in ("KR", "FOREIGN"):
        print(f"  {b:8} tfidf={rr('tfidf', b):.4f}  hybrid={rr('hybrid', b):.4f}"
              f"  Δ={incremental['delta_hybrid_minus_tfidf'][b]:+.4f}"
              f"  (n_pos={rec_flags['tfidf'][b][1]})")
    print(f"\n✓ report → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
