# Dataset Card — Semiconductor Industry Rejected Patents

> **English summary.** SIRP (Semiconductor Industry Rejected Patents) is a Gebru-style dataset
> card for `semiconductor_industry_rejected_patents.jsonl`: **1,000 Korean patent applications
> that were refused by a KIPO examiner**, each paired with the prior art the examiner cited as
> the ground for refusal. Collection ran 2026-04 → 2026-05-06, primarily through the KIPRIS Plus
> API. One record = one refused application + its examiner-cited prior art + the refusal grounds.
> The label is therefore **examiner-grounded, not annotator-generated**: the positives come from
> an official examination record rather than from human raters or heuristics.
> **What is redistributed here is metadata only.** KIPRIS full text (abstracts, claims) is
> licensed for academic use and cannot be redistributed, so the public tree carries identifiers,
> classifications, dates, family links and ground-truth pointers, plus a re-fetch script for
> anyone holding a KIPRIS key (§6). Statistics in §4 were computed on an earlier 773-record
> cohort; the file itself has since grown to 1,000 — the sections below say which is which.

> Gebru-style 데이터셋 카드. `semiconductor_industry_rejected_patents.jsonl` 의 출처·구성·통계·라이선스·활용·한계를 기술한다.

---

## 1. 데이터셋 요약

- **이름**: Semiconductor Industry Rejected Patents (SIRP)
- **버전**: 2026-05 (수집 종료 2026-05-06)
- **규모**: **1,000 레코드** (jsonl 실측, 2026-05-17 검증). 본 카드 내 "773"은 초기 코호트 스냅샷 수치 — 통계(§4)는 773 시점 산출이며 1,000 기준 재산출은 §7 후속 항목
- **포맷**: JSONL (1행 = 1 거절 특허 + 정답 선행기술)
- **원 수집 목적**: 반도체 IP-R&D 실습 — AI Agent 기반 선행기술조사 보고서 자동 작성 시스템의 개발·평가
- **본 프로젝트 통합 목적**: SDKB의 산출물 ③·④ 보강 + `sdkb-patent.ttl` 인스턴스 풀 + SDKB-Match PriorArt 트랙의 벤치마크

## 2. 출처 (Provenance)

| 항목 · Item | 값 · Value |
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

| 축 · Axis | 분포 · Distribution |
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
> 프로필 *설계 자문*에만
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
- **결정: (B) 확정 — 2026-08-09 (CR-015).** 보류를 끝낸다.
  - **왜 자문 없이 확정하는가.** 이전 판은 *"SKKU 산학협력단·법무팀 자문 후 (A)/(B)/(C)
    중 택일"* 로 적혀 있었다. **그 전제는 다른 사업 맥락의 것이었고 지금은 해당 사항이
    없다.** 그리고 자문이 필요 없는 이유가 따로 있다 — **결정은 이미 논문에 있다.**
    원고 §10.3 이 *"KIPRIS 원문(특허 전문·서지)은 학술이용 조건상 재배포할 수 없다"* 고
    쓴 시점에 선택지는 (B) 하나로 좁혀졌다. 리포를 그 문장에 맞추는 것은 법적 판단이
    아니라 **정합성 작업**이다.
  - ~~(A) 본 형태 그대로 학술 목적 재배포~~ — 원고 §10.3 과 정면 충돌이므로 선택 불가
  - **(B) 본문 재배포 불가 → 메타 + `ground_truth_*` + Link-Only** ← **확정**
  - ~~(C) abstract 만 공개~~ — 초록도 KIPRIS 원문이므로 같은 이유로 불가
- **(B)를 구현한 형태 — 격리가 아니라 두 트리다.**
  - **비공개 개발 리포**는 정본 jsonl 을 **그대로 추적한다.** 재배포하지 않으므로 문제가
    되지 않는다. (이 문서는 공개본에도 실린다 — 공개본에서 읽는 사람에게 "현재 이곳"은
    아래의 공개 트리다.)
  - **공개본은 별도 트리**이며 `scripts/build_public_release.py` 가 만든다 —
    `abstract` · `claim1` · **`claims_full[].text`** 를 **빈 문자열**로 두고
    스키마·`claim_no`·`depends_on`·식별자·IPC·날짜·`ground_truth_*` 는 남긴다.
    `title` 은 서지이므로 남긴다(이미 `kipris_biblio.parquet` 에 커밋돼 있다).
    노트북 셀 출력도 함께 제거한다 — 07 의 출력 하나가 초록 발췌를 인쇄하고 있었다.
  - **채우는 방법을 함께 준다**: `scripts/refetch_rejected_patents.py`(본인 KIPRIS 키).
    복원 판정은 sha256 대조(`fc142f51…`)다. **복원본은 추적 파일을 덮지 않는다**(2026-08-15) —
    `data/patents/raw/*.fulltext.jsonl`(gitignore)에 쓰고 `ingest` 가 그것을 먼저 읽는다.
    제자리 갱신은 `--in-place` 로 명시할 때만이다. 이렇게 가른 이유는 하나다: 추적 파일을
    채우면 직후 `git status` 가 원문 1,000행을 변경으로 잡고, `git commit -a` 한 번에
    공개 리포로 올라간다. **깨끗한 클론에서 실제로 재현했다.**
  - **재현 범위는 실측했다(2026-08-15 · 깨끗한 클론).** 받은 그대로 CQ 14/31 = 0.452 ·
    본인 키로 재인출 후 **27/31 = 0.871**(`em`·`tf`·`core` 전부 1.000) · 특허 A-Box
    33,934 트리플(논문 스냅샷 33,931 · 0.009 %). 끝내 복구되지 않는 넷(CQ27·CQ29–31)은
    전부 청구항 한정요소 층이다 — 그 층의 분해 입력이 청구항 원문 그 자체라 공개할 수 없다.
  - **푸시 전 검사기가 선다**: `scripts/check_public_release.py` 가 비공개 정본에서 뽑은
    지문으로 공개 트리 전량을 훑는다. 적중 0건이어야 푸시한다.
    (2026-08-09 실측: 파일 689개 · 적중 0. **2026-08-15 재실측: 지문 2,322개 · 파일 194개
    — 압축·열지향 파일 2개 포함 — · 적중 0.** 검사기가 `.parquet`·`.gz`·`.zst` 안까지
    열어 보게 된 것이 이때다. 파일 수가 준 것은 공개본이 별도 트리로 좁혀졌기 때문이다.)
  - **공개는 새 리포에 orphan 루트 커밋 1개로 한다** (2026-08-15 실행 — `arkwith7/sdkb-dataset` 생성 · 현재 **비공개**로 유지하며 공개 전환은 별도 판단이다). 현 리포의 이력에는 원문이 담긴
    커밋 둘(`b3969b8`·`4be52e1`)이 네 브랜치에 걸쳐 **이미 원격에 푸시돼 있어**, 이
    리포를 공개 전환하면 과거 커밋에서 원문을 받을 수 있기 때문이다. 이력 재작성
    (`git filter-repo`)을 택하지 않은 이유는 **모든 커밋 해시가 바뀌어** 하류
    `PROVENANCE.json` 과 논문의 상류 해시 인용이 전부 무효가 되기 때문이다.
- **사용자(연구자) 권고**: 본 데이터를 학술 목적 외(상업적 제품·서비스)로 활용할 경우 KIPRIS에 별도 문의.
- **2026-05-17 인입 자산의 공개 범위** (plan §7.1, 미해결 라이선스 보수적 적용):
  - ❌ 공개 레포 비포함(gitignore, paper_data sync로 재현): 인용 외부특허 본문 `data/patents/fulltext/`·파생 `fulltext_corpus.parquet`·`citation_resolution_full_cache.json` — 제3자(KR/JP/US, Google Patents 스크랩 포함) 특허 본문 대량 = §6(B) "본문 재배포 불가" 선제 적용.
  - ⚠️ excerpt 스크럽 후 커밋: `data/patents/rejection_decisions/structured/*.json` 에서 KIPRIS 거절결정서 OCR 원문(`excerpt`) 제거(`scripts/scrub_rejection_excerpts.py`), 구조화 매핑(`cited_evidence_map`·`legal_bases`·`target_claims`)만 §5(4) GT로 유지.
  - ✅ 공개: 온톨로지 KG·device 어휘(Wikidata CC0)·코드·지표 리포트·문서 (KIPRIS 본문 비포함).
  - ~~jsonl 본문은 기존 §6 "보류" 정책을 승계 — 법무팀 자문 시 (B)/(C) 결정 적용 대상.~~
    **2026-08-09 해소** — (B) 확정으로 공개본에서 `abstract`·`claim1`·`claims_full[].text` 가
    비워진다(위 참조). `structured/*.json` 은 이미 excerpt 스크럽이 끝나 추가 조치가 없다.

## 7. 한계

- `ground_truth_evidence` 결손 97.8% (KIPRIS Plus API가 OCR된 인용 구절을 미노출). → 거절결정서 PDF 재인출 + OCR/LLM 추출 보강은 2026-2학기 작업.
- 외국 특허(JP/US 등)의 본문은 미포함, 식별자만 — 후속 학기에 EPO OPS / USPTO PEDS로 보강.
- 거절특허만 포함 — 등록특허·심사중 특허는 미포함 (의도된 sampling bias).
- 일부 GT 식별자가 비특허·논문 인용 (`논문`, `비특` 등 23건) — ingest 단계에서 별도 분기 처리.
- 날짜 포맷 이상치 일부 (`20260430` 8자리) — 정규화 필요.

### 7-1. 논문 투고 무결성 한계 (위험 #2·#3·#7)

- **#2 합성 ≠ 전문가**: 7,500 = examiner-grounded(객관, 전문가 주석 아님);
  3-rater 7,800 = 합성 시뮬레이션(전문가 아님). 논문에서 어느 쪽도 "전문가
  평가"로 서술 금지 (§5-2 주석 참조).
- **#3 수치 비일관**: 본 카드 §4 통계는 **773 시점** 산출, 실제 jsonl은
  **1,000**. 논문·README·CHANGELOG·datasheet 수치를 단일 검증 스냅샷으로
  일괄 동기화 후 투고 (1,000 기준 §4 재산출은 후속).
- **#7 leakage 미측정**: [leakage_protocol.md](leakage_protocol.md)는 v0.1
  **설계만** — 본 학기 정량 leakage 결과 없음(2026-2 알고리즘 단계). 논문에
  측정 수치 주장 금지.
- ~~**#1 라이선스**: §6 KIPRIS 미해결 — §6(B) 법무 확정 전 보류.~~
  **2026-08-09 해소** — §6 에서 (B) 확정. 보류 사유가 사라졌다.

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
  url         = {https://github.com/arkwith7/sdkb-dataset}
}
```

## 9. 갱신 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-12 | v1.0 | 초안 작성 — Amendment v2 동시 도입 |
| 2026-05-17 | v1.1 | 규모 773→1,000 검증 반영, §5-2 합성≠전문가 주석, §7-1 논문 투고 무결성 한계(#2·#3·#7) 추가, citation size 갱신 |
| 2026-08-09 | v1.2 | **§6 (B) 확정**(CR-015) — 공개본은 별도 트리·원문 3필드 비움·재인출 스크립트·푸시 전 검사기·새 리포 orphan 공개. §7-1 #1 해소 |
