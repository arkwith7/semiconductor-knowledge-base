# Dataset Card — Semiconductor Industry Rejected Patents

> Gebru-style 데이터셋 카드. `semiconductor_industry_rejected_patents.jsonl` 의 출처·구성·통계·라이선스·활용·한계를 기술한다.

---

## 1. 데이터셋 요약

- **이름**: Semiconductor Industry Rejected Patents (SIRP)
- **버전**: 2026-05 (수집 종료 2026-05-06)
- **규모**: **1,000 레코드** (jsonl 실측, 2026-05-17 검증). 본 카드 내 "773"은 초기 코호트 스냅샷 수치 — 통계(§4)는 773 시점 산출이며 1,000 기준 재산출은 §7·[dataset_publication_risk_review.md](project/dataset_publication_risk_review.md) #3 후속 항목
- **포맷**: JSONL (1행 = 1 거절 특허 + 정답 선행기술)
- **원 수집 목적**: 반도체 IP-R&D 실습 — AI Agent 기반 선행기술조사 보고서 자동 작성 시스템의 개발·평가
- **본 프로젝트 통합 목적**: SDKB의 산출물 ③·④ 보강 + `sdkb-patent.ttl` 인스턴스 풀 + SDKB-Match PriorArt 트랙의 벤치마크

## 2. 출처 (Provenance)

| 항목 | 값 |
|---|---|
| 1차 출처 | KIPRIS Plus API (`kipris_plus_api`, 763건) |
| 보조 출처 | KIPRIS 웹 고급검색 (`kipris_web_advanced_search`, 10건) |
| 수집 기간 | 2026-04 ~ 2026-05-06 |
| 수집 코호트 | `semiconductor_ontology_rejected_patents` 431 / `semiconductor_fullstack_rejected_patents` 342 |
| 거절결정서 | 각 레코드 `meta.evidence_document_url` 에 KIPRIS 거절결정서 PDF URL 포함 |

## 3. 스키마

```jsonc
{
  "target_patent": {
    "application_number": "1020227033671",
    "title": "...",
    "abstract": "...",
    "ipc": "H10P 50/28|C23C 16/448|...",
    "date": "YYYY.MM.DD",
    "claim1": "...",
    "registration": {"register_status": "거절", "register_number": "", "register_date": ""},
    "biblio": {"examination_status": "거절결정(일반)|거절결정(재심사)|원결정유지(심사전치)|취소환송후 재거절결정",
               "unex_pub_number": "...", "unex_pub_date": "...", "source": "..."}
  },
  "ground_truth_examiner": ["KR1020190085654 A", "US20190348292 A1"],
  "ground_truth_all":      ["KR...", "JP...", "US...", "WO...", ...],
  "ground_truth_evidence": [],
  "meta": {
    "source": "kipris_plus_api",
    "collection_plan": "semiconductor_commercial",
    "collection_stage": "etch_core | feol_depo | mol_beol_interconnect | ...",
    "search_strategy": "plasma_H01J37 | profile_H01L21 | ...",
    "search_query": "...",
    "process_family": "etch | deposition | metallization | general | ...",
    "value_chain": ["process","material","equipment","device","component"],
    "evidence_document_type": "거절결정서",
    "evidence_document_url": "https://plus.kipris.or.kr/openapi/...",
    "collection_ts": "2026-05-06T12:50:23Z"
  }
}
```

## 4. 통계 (2026-05-12 산출)

| 축 | 분포 |
|---|---|
| 거절 상태 | 거절결정(일반) 528 / 거절결정(재심사) 231 / 원결정유지 13 / 취소환송 1 |
| process_family | etch 231 · deposition 135 · metallization 77 · general 52 · oxidation/diffusion 47 · photo 46 · memory 40 · implant 38 · materials 31 · backend_packaging 18 · components 13 · packaging 11 · mems 8 · equipment 7 · 기타 19 |
| value_chain | process 728 · material 304 · equipment 303 · device 145 · component 42 |
| IPC 상위 4-digit | H01L 642 · H10P 460 · C23C 408 · H10B 301 · H10D 283 · H10W 165 · H01J 134 · H10K 115 · G11C 41 · H10F 39 · G02F 35 · C09K 29 · C09G 26 · G03F 25 · B23K 23 |
| IPC/특허 | min 1, mean 4.0, max 23 |
| GT examiner | total 1,961 / mean 2.54 / max 10 (zero 0) |
| GT all | total 2,731 / mean 3.53 / max 13 (zero 0) |
| GT evidence (OCR) | total 17, 결손 756/773 (97.8%) |
| GT 국가 | KR 1,565 · JP 648 · US 396 · WO 56 · CN 16 · EP 10 외 |
| abstract 길이 | mean 326자, p50 312, max 1,350 |
| claim1 길이 | mean 300자, p50 264, max 1,237 |
| 수집 시기 | 1997-12-31 ~ 2026-04-30 |

## 5. 본 프로젝트에서의 활용

### 5-1. 산출물 ③ (기술 문제 50 + 적대적 시나리오 25)
- **문제 50건**: `process_family` 분포 기반 층화추출. 각 거절특허의 (title, abstract, claim1, IPC, 거절사유)가 "기술 문제" 한 단위.
- **적대적 시나리오 25건**: 거절사유 패턴에서 도출 — 진보성 부정, 신규성 부정, 청구범위 불명확, 출원인-인용인 다중관할 충돌 (예: KR 출원 × US/JP 인용), 자국-타국 검증 비대칭 등.

### 5-2. 산출물 ④ (7,500 examiner-grounded pairs)

> **표현 정밀성 (논문 투고 필수, 위험 #2).** 본 7,500쌍은 **KIPO 심사관 인용
> 근거(examiner-grounded)** 의 객관 GT이며 **인간 전문가 주석이 아니다**.
> 별도 `data/experts/curated_ratings_3rater.csv`(7,800)는 **알고리즘 시뮬레이션
> 3-rater 합성 라벨**(전문가 아님, 보조 일관성 레이어)로, 두 트랙을 혼동하거나
> 어느 쪽이든 "전문가 평가"로 서술하면 허위표시 시비 대상이다. 도메인 전문가는
> 프로필 *설계 자문*([expert_validation_log.md](expert_validation_log.md))에만
> 참여했고 평점을 산출하지 않았다. 합성 트랙 신뢰도(weighted κ=0.550 /
> ICC(2,k)=0.787 / 투명성 Fleiss κ=0.258)는
> [reliability_report.md](../data/experts/reliability_report.md) 참조.

- Positive(high-confidence): `ground_truth_examiner` 1,961쌍
- Positive(broad): `ground_truth_all` 추가 770쌍 → 합계 ≈2,731
- Hard negative: 같은 IPC 4-digit 내·다른 `process_family`에서 추출 ≈2,300
- Easy negative: 다른 IPC section에서 무작위 ≈2,500
- 총 ≈7,500 (계획서 수량과 일치)
- 평가 지표: MRR, NDCG@5, Recall@K, leakage rate

### 5-3. `sdkb-patent.ttl` 인스턴스 풀
- 773 → `:Patent`
- IPC → `:IPCSymbol` (계층 자동 생성)
- examiner 인용 → `:hasPriorArt` (sub-property of `:cites`)
- 거절사유 → `:RejectionReason`
- `process_family` × `value_chain` → SDKB 코어 노드 (`:realizes`, `:occursIn`)

### 5-4. 신 교수 4-pillar 매핑
| Pillar | 활용 |
|---|---|
| 기술전략 | family × IPC × 가치사슬 그리드 |
| 기술예측 | 거절패턴 × IPC 진화 → novelty 임계 추정 (TFSC 2015 정렬) |
| 기술평가 | 거절률 = TRL/사업가치의 음의 신호 |
| 기술상업화 | SDKB-Match PriorArt 시장 (변리사·IP 부서) |

## 6. 라이선스 및 재배포

- **출처 권리**: KIPRIS / KIPO. KIPRIS Plus API의 약관에 따른다.
- **현 상태**: 본 레포에 그대로 포함 (`semiconductor_industry_rejected_patents.jsonl`).
- **확정 사항**: 학기 중 SKKU 산학협력단/도서관·법무팀 자문 후 다음 중 하나로 조정.
  - (A) 본 형태 그대로 학술 목적 재배포 허용 → 현 상태 유지
  - (B) 본문(abstract/claim1) 재배포 불가 → `data/patents/raw/` 로 격리 + `.gitattributes`로 별도 관리, 공개 레이어는 `(application_number, IPC, date, family, ground_truth_*)` 메타+URL Link-Only (`sdkb-patent-linkonly.ttl`)
  - (C) 부분 재배포 가능 → abstract만 공개, claim 본문은 Link-Only
- **사용자(연구자) 권고**: 본 데이터를 학술 목적 외(상업적 제품·서비스)로 활용할 경우 KIPRIS에 별도 문의.
- **2026-05-17 인입 자산의 공개 범위** (plan §7.1, 미해결 라이선스 보수적 적용):
  - ❌ 공개 레포 비포함(gitignore, paper_data sync로 재현): 인용 외부특허 본문 `data/patents/fulltext/`·파생 `fulltext_corpus.parquet`·`citation_resolution_full_cache.json` — 제3자(KR/JP/US, Google Patents 스크랩 포함) 특허 본문 대량 = §6(B) "본문 재배포 불가" 선제 적용.
  - ⚠️ excerpt 스크럽 후 커밋: `data/patents/rejection_decisions/structured/*.json` 에서 KIPRIS 거절결정서 OCR 원문(`excerpt`) 제거(`scripts/scrub_rejection_excerpts.py`), 구조화 매핑(`cited_evidence_map`·`legal_bases`·`target_claims`)만 §5(4) GT로 유지.
  - ✅ 공개: 온톨로지 KG·device 어휘(Wikidata CC0)·코드·지표 리포트·문서 (KIPRIS 본문 비포함).
  - jsonl(773→1000) 본문(abstract/claim1)은 기존 §6 "보류" 정책을 그대로 승계 — 법무팀 자문 시 (B)/(C) 결정이 이 jsonl·structured 매핑에 동일 적용 대상.

## 7. 한계

- `ground_truth_evidence` 결손 97.8% (KIPRIS Plus API가 OCR된 인용 구절을 미노출). → 거절결정서 PDF 재인출 + OCR/LLM 추출 보강은 2026-2학기 작업.
- 외국 특허(JP/US 등)의 본문은 미포함, 식별자만 — 후속 학기에 EPO OPS / USPTO PEDS로 보강.
- 거절특허만 포함 — 등록특허·심사중 특허는 미포함 (의도된 sampling bias).
- 일부 GT 식별자가 비특허·논문 인용 (`논문`, `비특` 등 23건) — ingest 단계에서 별도 분기 처리.
- 날짜 포맷 이상치 일부 (`20260430` 8자리) — 정규화 필요.

### 7-1. 논문 투고 무결성 한계 (위험 #2·#3·#7 — [risk review](project/dataset_publication_risk_review.md))

- **#2 합성 ≠ 전문가**: 7,500 = examiner-grounded(객관, 전문가 주석 아님);
  3-rater 7,800 = 합성 시뮬레이션(전문가 아님). 논문에서 어느 쪽도 "전문가
  평가"로 서술 금지 (§5-2 주석 참조).
- **#3 수치 비일관**: 본 카드 §4 통계는 **773 시점** 산출, 실제 jsonl은
  **1,000**. 논문·README·CHANGELOG·datasheet 수치를 단일 검증 스냅샷으로
  일괄 동기화 후 투고 (1,000 기준 §4 재산출은 후속).
- **#7 leakage 미측정**: [leakage_protocol.md](leakage_protocol.md)는 v0.1
  **설계만** — 본 학기 정량 leakage 결과 없음(2026-2 알고리즘 단계). 논문에
  측정 수치 주장 금지.
- **#1 라이선스**: §6 KIPRIS 미해결 — 데이터셋-리소스 논문은 §6(B) 법무
  확정 전 보류.

## 8. 인용 (citation)

데이터 활용 시 본 데이터셋과 원 출처(KIPRIS)를 함께 인용한다.

```bibtex
@dataset{sirp_2026,
  title       = {Semiconductor Industry Rejected Patents (SIRP)},
  author      = {Park, HyoungSik},
  advisor     = {Shin, Juneseuk},
  institution = {Sungkyunkwan University, Graduate School of
                 Management of Technology, Quantitative MOT Lab},
  year        = {2026},
  source      = {KIPRIS Plus API, KIPO},
  size        = {1000 records},
  url         = {https://github.com/arkwith7/semiconductor-knowledge-base}
}
```

## 9. 갱신 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-12 | v1.0 | 초안 작성 — Amendment v2 동시 도입 |
| 2026-05-17 | v1.1 | 규모 773→1,000 검증 반영, §5-2 합성≠전문가 주석, §7-1 논문 투고 무결성 한계(#2·#3·#7) 추가, citation size 갱신 |
