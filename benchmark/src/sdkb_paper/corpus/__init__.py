"""IR 벤치마크 코퍼스 조립 (v0.9 · PLAN-017 M1).

이 패키지는 큐레이션 KG(G₀/G₁/G₂ + claim-feature sidecar)를 '문서중심 IR 코퍼스'로
재조립한다. 검색 로직(BM25/Dense/Hybrid)은 넣지 않는다 — 그것은 `retrieval/` 소관이다
(CLAUDE.md §3 모듈 배치표). 지지 주장: C2 핵심증명(선행기술 검색)의 입력.
"""
