# 거절특허 중심 데이터 정합성 메모

## 목적

이 저장소에서 유효한 데이터는 아래 조건을 동시에 만족해야 합니다.

1. 타겟이 `등록 거절된 특허`일 것
2. 그 거절에 실제로 인용·참조된 `특허/비특허 문헌`이 있을 것
3. AI Agent가 타겟 특허의 명칭, 요약, 청구항, IPC, 서지정보로부터 그 인용문헌을 찾아내는 학습 근거가 될 것

위 조건에 맞지 않는 등록특허 중심 데이터나 보조 탐색 산출물은 이 목적에서는 유지 가치가 없습니다.

## 현재 유효한 기준

### 1. 반드시 필요한 타겟 속성

- 출원번호
- 발명의 명칭
- 발명의 요약
- 청구항(최소 claim 1)
- IPC/CPC
- 거절 상태
- 가능하면 신규성/진보성 문제 설명

### 2. 반드시 필요한 정답 속성

- 거절 시 인용된 특허
- 거절 시 인용된 비특허 문헌
- 특허/비특허 구분
- 문헌을 다시 찾을 수 있는 식별자

### 3. 학습에 바로 쓰는 방식

- 전방향: 거절특허에서 키워드/검색식/질의전략을 만들고 인용문헌을 찾기
- 역방향: 인용문헌에서 왜 이 문헌이 거절 근거가 되는지 설명하기

## 현재 저장소에서의 판단 기준

### 현재 검증된 데이터셋 상태

2026-05-16 기준 현재 저장소의 기본 데이터셋은 아래 파일입니다.

- `data/processed/semiconductor_industry_rejected_patents.jsonl` (1000 건)

이 canonical dataset은 다음 두 계열을 합친 결과물입니다.

- `semiconductor_commercial`
	- KIPRIS 거절결정서 REST seed + KIPRIS Plus API 상세정보 기반 수집
- `legacy_etch_web_poc_import`
	- 기존 `etching_reject_web_poc_dataset.jsonl`을 semiconductor schema로 승격한 import

2026-05-16 [`dataset_full_collection_runbook.md`](dataset_full_collection_runbook.md) 수행으로 다음 자산이 신설/확장되었습니다.

- `target_patent.claims_full` (전체 청구항, 100%), `family` (53.4%), `legal_status` (100%) — Phase A
- `data/processed/fulltext/prior_arts/<doc_id>.txt` (2,950/3,154 distinct 인용 본문, 93.5%) — Phase B
- `data/processed/rejection_decisions/{pdf,txt,structured}/<applno>.{pdf,txt,json}` (441 structured) + `meta.rejection_decision` + `meta.ground_truth_evidence_v2` (270 records, 656 매핑) — Phase C
- `data/external/device_vocab/` (31 device classes, en 79 / ko 37 라벨) — Phase D

현재 저장소에서 바로 사용할 핵심 자산은 아래와 같이 구분합니다.

- 1차 핵심 자산
	- `data/processed/semiconductor_industry_rejected_patents.jsonl` (확장된 스키마)
	- `data/processed/fulltext/prior_arts/` (인용 외부특허 본문 통합 코퍼스)
	- `data/processed/rejection_decisions/` (거절결정서 OCR + 구조화)
- 보조/재현 자산
	- `data/processed/etching_reject_web_poc_dataset.jsonl` (legacy POC 136건)
	- `data/raw/<application_number>/` (legacy raw OCR)
	- `data/processed/fulltext/etching_prior_arts/` (legacy POC 192건 인용 본문)
- 외부 자산
	- `data/external/device_vocab/` (device 어휘 외부 인입)

즉, 현재 판단 기준은 `legacy etch PoC를 포함하되 운영 기준은 canonical semiconductor dataset에 두고, 인용 본문 + 거절근거 구조화 + device 어휘를 별도 자산 트리로 분리한다`입니다.

### KIPRIS 소스 해석

- `특허·실용 공개·등록공보`는 canonical dataset의 기본 메타/GT 소스다.
- `거절결정서` REST는 현재 commercial collector에서 rejected-only seed와 행정문서 URL 보강에 사용한다.
- `KIPRIS 웹 상세보기 + 의견제출통지서 OCR` 경로는 현재 legacy etch import의 provenance를 설명하는 보조 소스다.
- 자세한 서비스 매핑은 `docs/kipris_reject_dataset_source_mapping.md`를 따른다.
- 식각 공정 검색식 설계와 API 낭비 방지 기준은 `docs/legacy_kipris_etching_search_strategy.md`를 따른다.

### 유지 대상

- canonical semiconductor dataset을 생성/증분 확장하는 스크립트
- 공정 구분 메타를 유지한 평가/품질 리포트 스크립트
- legacy raw/OCR 재현을 위한 최소 스크립트와 문서
- KIPRIS 조회 및 특허번호 정규화 유틸리티

### 제거 대상

- 등록특허 중심 하드필터 코호트
- 외부 후보 보강 실험 산출물
- 혼합 코호트 기반 평가 샘플
- 목적 설명과 어긋나는 문서/스크립트

## 최종 판정

이 저장소는 앞으로 `거절특허 + 거절 인용문헌` 데이터셋만 중심 자산으로 보되, 운영 기준은 canonical semiconductor dataset에 둔다.

즉, legacy etch dataset은 삭제 대상이 아니라 provenance와 raw/OCR 재현을 위한 보조 자산이다.

실제 활용 우선순위는 아래와 같습니다.

1. 구조화 데이터 기본값은 `data/processed/semiconductor_industry_rejected_patents.jsonl`를 본다 (확장된 스키마: `claims_full`, `family`, `legal_status`, `rejection_decision`, `ground_truth_evidence_v2`).
2. 거절근거 → 인용발명 매핑은 `meta.ground_truth_evidence_v2` 또는 `data/processed/rejection_decisions/structured/<applno>.json` 의 `cited_evidence_map`을 본다 (270 records, 656 매핑).
3. 인용문헌 원문 실험은 `data/processed/fulltext/prior_arts/` (2,950건 통합 코퍼스) 를 1차로, `data/processed/fulltext/etching_prior_arts/` (legacy POC) 를 비교용으로 사용한다.
4. device 계층 매핑 실험은 `data/external/device_vocab/device_alias_table.json` 의 31 device 노드를 사용한다.
5. legacy provenance나 OCR 근거 문장 검토는 `data/processed/etching_reject_web_poc_dataset.jsonl`와 `data/raw/<application_number>/rejection_notice/`를 본다.
