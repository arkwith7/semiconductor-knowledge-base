# EXCLUDED — 싣지 않은 것과 사유

**빠진 것이 은폐가 아니라 결정임을 보이는 목록이다.** 목록 없이 빠지면 누락으로 읽힌다.

| 대상 | 사유 |
|---|---|
| `data/raw/ · data/interim/ · data/processed/ 원문 계열` | KIPRIS 학술이용 조건상 재배포 불가. 식별자와 재인출 절차로 대체한다 |
| `src/sdkb_paper/explore/ (6 파일)` | 내부 뷰어 — 재현에 쓰이지 않는다 |
| `src/sdkb_paper/collect/ 나머지 (kipris_client·bq_cpc·dart·collect·b_layer)` | §4 경로가 호출하지 않는다. 재인출은 상류 scripts/refetch_rejected_patents.py 가 담당한다 |
| `src/sdkb_paper/analysis/{census,s1_coverage*,s2_timeseries*,applicant_cli,ksia_strata_cli,robustness_cli}` | 구 커버리지 패러다임 산출물 — 현 원고가 인용하지 않는다 |
| `01.code_spec/ · upstream/ · paper/ 원고 정본` | 감사 기록이며 재현물이 아니다. 사전등록 대응은 supplementary S6 이 담당한다 |
| `tests/ (54 파일)` | 지문 검사를 통과한 것만 선별 반입한다 — 이번 판에서는 반입하지 않는다 |
