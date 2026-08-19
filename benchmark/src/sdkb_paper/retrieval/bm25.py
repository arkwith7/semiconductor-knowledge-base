"""BM25 색인·검색 (PLAN-018 B0/B1 · F13 사전토큰화 아키텍처).

아키텍처(§6.1·§11.6): nori(+SDKB 사용자사전)·영어 analyzer 를 **사전토큰화기**로 두고 토큰을
공백-조인해 Lucene `-pretokenized`(whitespace·무스테밍·무불용어) 색인에 넣는다. 이렇게 하면
DecompoundMode·사용자사전을 파이썬에서 완전히 통제하고, §5.3 토큰화 민감도 교체가 색인
파이프라인 무변경으로 성립한다.

- 문서 텍스트: `text_main`(초록+청구항전체 · SPEC-007 지정 주 색인 텍스트).
- 질의 표현: `claims_independent`(F8 주분석 = Claim-only 독립항 · 불완전 시 text_main 보조).
- **경계(PLAN-018 §2):** 이 모듈은 qrel 을 읽지 않는다 — run(순위)만 만든다. 평가는 analysis/metrics.

CLI: `python -m sdkb_paper.retrieval.bm25`(pretokenize → index → search → run 기록). JVM(JAVA_HOME) 필요.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .. import config
from . import layers

# 산출 경로 (대용량·재생성 가능 → gitignore)
PRETOK_DIR = config.IR_INDEX_DIR / "pretok_text_main"   # JsonCollection (사전토큰화 문서)
BM25_INDEX_DIR = config.IR_INDEX_DIR / "bm25_text_main"
RUN_B0 = config.IR_RUNS_DIR / "bm25_b0_claim.txt"       # B0: 질의=독립항

# Anserini 기본 BM25 (사전등록 F-표 미명시 → 표준 기본값 고정·문서화)
BM25_K1 = 0.9
BM25_B = 0.4


def _tokenizers():
    """(ko, en) 사전토큰화기 — nori 는 SDKB 사용자사전(SPEC-008) 적용."""
    from .tokenize import EnglishTokenizer, NoriTokenizer

    ko = NoriTokenizer(mode="NONE", userdict=config.IR_USERDICT)
    en = EnglishTokenizer()
    return ko, en


# --- 사전토큰화 → JsonCollection -----------------------------------------



def pretokenize_corpus(text_col: str = "text_main") -> int:
    """코퍼스 전 문서를 언어별 사전토큰화해 JSONL(JsonCollection)로 쓴다. 반환: 문서 수."""
    import pandas as pd

    from .tokenize import pretokenize

    cols = ["doc_id", "lang", text_col]
    df = pd.read_parquet(config.IR_CORPUS, columns=layers.with_layer_cols(cols))
    # **색인 대상 = 후보 자격 있는 문서만**(PLAN-045 D2). 질의는 후보가 아니다 —
    # 이 한 줄이 없으면 B층 신규 문서가 A층 질의의 검색 대상이 되어 §6 수치가 오염된다.
    # 기존 41,031 은 전부 is_candidate=True 이므로 **docs.jsonl 은 바이트 단위로 불변이어야 한다.**
    df = layers.candidates(df)[cols]
    ko, en = _tokenizers()
    PRETOK_DIR.mkdir(parents=True, exist_ok=True)
    out = PRETOK_DIR / "docs.jsonl"
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for doc_id, lang, text in df.itertuples(index=False):
            contents = pretokenize(str(text or ""), ko, en, str(lang or "und"))
            f.write(json.dumps({"id": doc_id, "contents": contents}, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


# --- 색인 -----------------------------------------------------------------
def build_index(threads: int = 8) -> None:
    """사전토큰화 컬렉션을 Lucene `-pretokenized` 로 색인한다(whitespace·무스테밍)."""
    config.java_home()
    BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pyserini.index.lucene",
        "-collection", "JsonCollection",
        "-generator", "DefaultLuceneDocumentGenerator",
        "-input", str(PRETOK_DIR),
        "-index", str(BM25_INDEX_DIR),
        "-threads", str(threads),
        "-pretokenized",
        "-storePositions",
    ]
    subprocess.run(cmd, check=True)


# --- 검색 → run -----------------------------------------------------------
def search(
    query_col: str = "claims_independent",
    fallback_col: str = "text_main",
    k: int = 100,
    exclude_self: bool = True,
    run_path: Path | None = None,
    tag: str = "bm25_b0",
    layer: str = layers.LAYER_A,
) -> Path:
    """질의를 사전토큰화해 top-k 검색, TREC run 파일을 쓴다(qrel 미열람).

    exclude_self: 질의 특허 자신(코퍼스 내 g0_rej 노드)을 결과에서 제외(자기 선행기술 아님).
    """
    import pandas as pd

    # JVM 부팅 전 JAVA_HOME 확정(PLAN-018 E1). 색인 단계를 건너뛰고 검색만 할 때
    # (`--search-only`) `build_index()` 를 지나지 않으므로 여기서도 불러야 한다.
    config.java_home()
    from pyserini.pyclass import autoclass
    from pyserini.search.lucene import LuceneSearcher

    from .tokenize import pretokenize

    run_path = run_path or layers.run_path_for_layer(RUN_B0, layer)
    layers.guard_run_target(run_path, layer, RUN_B0)
    run_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(
        config.IR_CORPUS,
        columns=layers.with_layer_cols(["doc_id", "lang", "is_query", query_col, fallback_col]),
    )
    queries = layers.queries_of(df, layer)
    ko, en = _tokenizers()

    searcher = LuceneSearcher(str(BM25_INDEX_DIR))
    searcher.set_analyzer(autoclass("org.apache.lucene.analysis.core.WhitespaceAnalyzer")())
    searcher.set_bm25(BM25_K1, BM25_B)

    written = 0
    with run_path.open("w", encoding="utf-8") as f:
        for row in queries.itertuples(index=False):
            qid = row.doc_id
            text = getattr(row, query_col) or getattr(row, fallback_col) or ""
            qstr = pretokenize(str(text), ko, en, str(row.lang or "und"))
            if not qstr.strip():
                continue
            hits = searcher.search(qstr, k + (1 if exclude_self else 0))
            rank = 0
            for h in hits:
                if exclude_self and h.docid == qid:
                    continue
                rank += 1
                f.write(f"{qid} Q0 {h.docid} {rank} {h.score:.6f} {tag}\n")
                if rank >= k:
                    break
            written += 1
    print(f"  질의 {written}건 검색 · run → {run_path}")
    return run_path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=[layers.LAYER_A, layers.LAYER_B], default=layers.LAYER_A,
                    help="질의 층. B 는 판독 B 전용이며 run 은 `_B` 접미로 따로 쓴다")
    ap.add_argument("--search-only", action="store_true",
                    help="색인 재사용(색인은 후보 문서만 담아 층과 무관 · PLAN-047 §12.0-3)")
    args = ap.parse_args()

    if not args.search_only:
        print("① 사전토큰화(text_main) …")
        n = pretokenize_corpus()
        print(f"   문서 {n:,}건 → {PRETOK_DIR}/docs.jsonl")
        print("② 색인(-pretokenized) …")
        build_index()
        print(f"   색인 → {BM25_INDEX_DIR}")
    print(f"③ 검색(B0 · 질의=독립항, k=1000 · layer={args.layer}) …")
    search(k=1000, layer=args.layer)   # Recall@{50,100,500,1000} 를 지지할 run 깊이
    print("✓ BM25 B0 run 완료 — 평가는 `python -m sdkb_paper.analysis.metrics`")


if __name__ == "__main__":
    main()
