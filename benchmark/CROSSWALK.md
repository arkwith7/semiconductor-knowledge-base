# CROSSWALK — 원고 §4 표의 코드 진입점과 공개 경로

**이 표는 생성기가 만든다**(`scripts/export_benchmark.py`). 원고의 표가 바뀌면 다시 조립한다.

| 구성 | 원고가 적은 진입점 | 공개 트리 접두어 | 산출 순위 파일 |
|---|---|---|---|
| **B0** BM25-Claim | `retrieval/bm25.py::search` (nori 사전 토큰화) | `benchmark/src/sdkb_paper/` 하위 | `sys_B0_bm25_*.txt` |
| **B2** Dense | `retrieval/dense.py::search` (Titan v2 · FAISS flat) | `benchmark/src/sdkb_paper/` 하위 | `sys_B2_dense_*.txt` |
| **B3** Text Hybrid | `retrieval/hybrid.py::rrf` | `benchmark/src/sdkb_paper/` 하위 | `sys_B3_rrf_*.txt` |
| **B4** 분류 단독 | `retrieval/systems.py::build_b4` | `benchmark/src/sdkb_paper/` 하위 | `sys_B4_ipc_*.txt` |
| **B5** 개념 단독 | `retrieval/systems.py::build_b5` | `benchmark/src/sdkb_paper/` 하위 | `sys_B5_concept_*.txt` |
| **P0★** Text+Ontology | `retrieval/systems.py::rerank_p0` | `benchmark/src/sdkb_paper/` 하위 | `sys_P0star_*.txt` |
| **P1** +ClaimFeature | `analysis/ontology_eval.py::rerank_p1` | `benchmark/src/sdkb_paper/` 하위 | `sys_P1_*.txt` |
