# Commercialization Strategy v1 (Deliverable ⑤)

> **CONFIDENTIAL — lab-internal + ARKWITH proprietary.** Excluded from the
> anonymized public/double-blind snapshot (treated like project_status /
> risk_review). Do not redistribute.
>
> v1 — 2026-05-17. **Subject = SDKB itself** (this project's deliverable/asset).
> This document answers: *how is SDKB's value converted to revenue?* IPBridge
> (ARKWITH's single product) is the **anchor commercialization vehicle / first
> customer / proof-of-value**, not the subject. The prior v3 "ARKWITH 3종 응용"
> framing is superseded; v3/project_status reconciliation is a
> [v3 §D-2](plan_amendment_v3.md) advisor decision item.
>
> Evidence: ARKWITH internal `arkwith-web/01.docs/*`, `arkwith-api/01.docs/*`,
> `arkwith-api/eval_results/comparison.md` (proprietary; cited for advisor
> traceability).

## 1. Executive summary

**The asset being commercialized is SDKB** — a provenance-grounded, SHACL-
validated semiconductor domain knowledge base (229-node curation graph + SIRP
1,000 examiner-grounded patents + multi-jurisdiction governance + 4-pillar
alignment). The thesis: a structured semiconductor sub-domain backbone is the
**scarce, hard-to-replicate input** that IP-tech and 소부장 decision tools
cannot build alone, and its value is captured through three monetization
tracks of increasing reach:

| # | SDKB monetization track | Vehicle | Maturity |
|---|---|---|---|
| **T1 — Embedded value (anchor)** | SDKB powers ARKWITH **IPBridge**'s per-vertical domain packs → revenue via IPBridge SaaS | IPBridge (real product, pre-rev v0.5) | Near-term, evidence-backed |
| **T2 — Backbone licensing** | SDKB-as-API / domain-pack-as-a-service to other IP-tech vendors & corporate 소부장 IP teams | Licensing / OEM | Mid-term, contingent on T1 proof |
| **T3 — Dataset / benchmark** | SDKB + SIRP as a licensed research/eval dataset | Academic now (IP&M/Scientometrics seed); commercial later | KIPRIS-#1 gated |

T1 is the wedge that produces the first revenue and the proof that SDKB's
domain backbone materially moves a paid metric; T2/T3 scale the same asset.

## 2. Why SDKB is the commercializable scarcity

IPBridge's measured accuracy depends entirely on a **hand-authored etching
domain pack** (`etching.py`, strata plasma `H01J37` / profile `H01L21` / wet).
Internal measurement (`arkwith-api/eval_results/comparison.md`): with the
domain pack, dispute-response **Mode C Recall@10 = 0.838** (strata 0.857 /
0.750 / 0.909); without domain structure, generic LLM **Mode B = 0.324**.
**The domain knowledge — not the LLM or the UI — is the moat.** But that moat
is today a single non-scalable file. Expanding to 6–10 verticals (deposition,
litho, packaging, device, display) by hand does not scale
(`arkwith-web/01.docs/00_thiel_thesis.md` §0-2 ⑥⑦). **SDKB converts that moat
from an unscalable artifact into a reusable, governed, measurable asset** —
that conversion is the commercializable event.

## 3. Solution — SDKB as the asset; tracks T1/T2/T3

| Track | Customer (who pays) | Pain SDKB removes | SDKB's edge |
|---|---|---|---|
| **T1 IPBridge-embedded** | 한국 반도체/디스플레이 사내 IP팀(5–30인) + 협업 변리사; pay for IPBridge | vertical 확장 시 도메인팩 수작업 = 정확도·확장 병목 | 구조화 IPC·개념·키워드 온톨로지에서 도메인팩 합성·일관성 |
| **T2 Backbone licensing** | 타 IP-tech 벤더·대기업 IP센터(커스텀 도메인팩 수요) | 자체 반도체 온톨로지 구축 불가 | PROV-O·SHACL 거버넌스 포함 backbone API |
| **T3 Dataset/benchmark** | 학계(우선)·후속 상업 | examiner-grounded 반도체 GT 부재 | SIRP 1,000 + 7,500 pairs + datasheet/PROV |

IPBridge 제품 자체(W1 거절대응 / W2 무효·FTO, §A~§G 리포트)는 **T1의 구현
수단**으로만 기술 — 제품 전략 문서가 아니라 SDKB 가치 전달 경로.

## 4. Market — sized by the value SDKB unlocks (via T1 first)

T1 수익이 발생하는 시장 = IPBridge 1차 진입(분쟁대응, 사전조사 제외;
`arkwith-web/01.docs/02_market_analysis.md` §2-2):

| 세그먼트 | 연 건수(KR) | 단가 | 시장 |
|---|---|---|---|
| 거절대응(OA) | ~12,000 | ₩2.5M | ₩300B |
| 무효심판 | ~600 | ₩8M | ₩48B |
| FTO | ~3,000 | ₩5M | ₩150B |
| 라이선스 실사 | ~400 | ₩15M | ₩60B |
| **1차 합계** | ~16,000 | — | **~₩558B/년** |

- **SOM = SDKB가 직접 기여하는 부분**: 도메인팩 확장으로 열리는 vertical별
  분쟁대응 매출. 1년차 IPBridge ARR ~₩110M(`01_company_overview.md §1-6`)
  중 도메인팩 의존 비중이 SDKB 귀속 가치.
- **T2 TAM(확장)**: 타 벤더·대기업 백본 라이선싱 — T1 검증 후 산정.
- **T3**: 학술(비수익, seed)→상업 데이터셋(KIPRIS #1 해제 조건부).

## 5. Customers / who pays for SDKB-derived value

- **T1 (직접 매출 경로)**: 사내 IP팀(~150) + 변리사 사무소(~800) — IPBridge
  구독료로 SDKB 가치를 간접 지불. 채널: SKKU 학술 referral(2026-06 강좌).
- **T2**: 대기업 IP센터·타 IP-tech 벤더 — 커스텀 도메인팩/백본 API.
- **T3**: 연구기관(논문 seed); 상업 데이터셋 수요자(후속).

## 6. RBV — SDKB is the core resource (the heart of this strategy)

| Resource | VRIO | 보유 | SDKB가 바꾸는 것 |
|---|---|---|---|
| **SDKB 도메인 백본** | **V/R/I/O** | 본 프로젝트 구축중 | 수작업 자산 → 조직 재현·확장 가능 자산(O) |
| examiner GT (SIRP 1,000 / 7,500) | V/R/I/O | ✅ | 평가 재현성·벤치마크 자산(T3) |
| 식각 도메인팩(strata) | V/R/-/- | ✅(식각만) | SDKB로 vertical 일반화 |
| 다중관할 거버넌스 게이트 | V/R/I/- | 부분 | sdkb-governance-kr + SHACL |
| IPBridge 파이프라인(10-Phase) | V/R/I/O | ✅(ARKWITH) | SDKB 가치의 *전달 채널* |
| 변리사·법무 파트너십 | V/-/-/- | 미보유 | 제휴 필요 |

핵심 논거: **SDKB가 유일하게 V/R/I/O를 동시에 충족하는 자산**이고, 다른
자산은 SDKB 가치의 전달·증명 수단. 따라서 사업화의 주체는 SDKB.

## 7. Revenue model — how SDKB converts to cash

- **T1 (value capture via IPBridge SaaS)**: Starter ₩800K/월·Team ₩2.5M/월·
  Enterprise ₩5M+·PAYG ₩300K/건(`01_company_overview.md §1-6`). SDKB 귀속
  가치 = (도메인팩 의존 vertical 매출). 1년차 IPBridge ARR ~₩110M.
- **T2 (backbone licensing)**: 도메인팩/백본 API 연 단위 라이선스 또는 OEM
  — T1으로 "도메인팩 #2 제작 리드타임·정확도" 증명 후 가격 산정.
- **T3 (dataset)**: 학술 무상 공개(seed, CDLA) → KIPRIS #1 해제 시 상업
  데이터셋/벤치마크 라이선스 옵션.
- 가격 임계: IP팀 외주비 ₩100M+/년 절감 → Team(₩30M/년) ROI 명확.

## 8. Competitive — why an SDKB-backed offering wins

| 대안 | 한계 | SDKB-backed 차별 |
|---|---|---|
| PatSnap/Orbit, Wips | 영어중심·KIPRIS depth·AI분석 약함 | examiner-grounded + 한국어 도메인 백본 |
| 범용 LLM | plasma 한·외 어휘격차로 무력(0.324) | strata 온톨로지(0.838) |
| 경쟁사 자체 온톨로지 시도 | PROV-O·SHACL·다중관할 결합 사례 부재 | SDKB의 거버넌스+정합 통합 |
| 수작업 도메인팩(현 IPBridge) | 단일 vertical·비확장 | SDKB 합성으로 vertical 일반화 |

## 9. Go-to-market & roadmap — SDKB monetization milestones

| 시점 | 이벤트 | SDKB 사업화 의미 |
|---|---|---|
| 2026-05~06 | IPBridge v0.5 게이트 + 6월 강좌 | T1 채널 개시(SDKB 가치 전달 경로 확보) |
| 2026-07~09 | ICP 파일럿 1사·첫 유료 | T1 첫 매출 = SDKB 간접 수익화 시작 |
| 2026-10~12 | Starter 5사 ~₩30M ARR | T1 반복 매출 |
| **2027-H1** | **도메인팩 #2(증착) — SDKB 백본 적용** | **SDKB의 직접 가치 증명 1순위 지점**: 제작 리드타임·정확도 측정 → T2 가격 근거 |
| 2027-H2+ | T2 백본 라이선싱 / T3 데이터셋 | 동일 SDKB 자산의 확장 수익화 |

## 10. SDKB 도입 후 측정 가능해지는 지표 (사업화 가치의 정량 증거)

| 지표 | SDKB 전 | SDKB 후 목표 | 측정 |
|---|---|---|---|
| 신규 vertical 도메인팩 리드타임 | 수작업 수주(식각 1건) | 합성으로 수일 | 도메인팩 #2 제작시간 |
| vertical 간 IPC·개념 일관성 | 측정불가(단일파일) | 정량 일관성 | SDKB SHACL/정합 리포트 |
| 신규 vertical Mode C Recall@10 | 식각 0.838만 | ≥0.70 유지 | strata Recall harness |
| 컴플라이언스 게이트 | 사후 수작업 | 구조적 자동 | leakage_rate@K(설계, 2026-2) |
| 평가 재현성 | 식각 100건 | SIRP 1,000 | SIRP GT 7,500 |
| T2 라이선스 가격 근거 | 없음 | 리드타임·정확도 델타 | Phase 4 측정 |

## 11. Risks

- **#1 KIPRIS** — T3 데이터셋 상업화의 게이트. 제품(T1, 약관 내 사용)과
  데이터셋 공개는 분리; 학술 트랙은 §6(B) 확정 전 보류
  ([dataset_publication_risk_review.md](dataset_publication_risk_review.md) #1).
- **T1 의존 리스크** — SDKB 수익이 초기엔 IPBridge 단일 채널·단일 운영자·
  pre-revenue에 종속. T2/T3로 채널 다변화가 완화책이나 T1 증명이 선행.
- **SDKB 미완 시** — 도메인팩 백본이 약하면 T1의 vertical 확장 ROI·T2 근거
  소멸. 본 프로젝트 산출물 품질이 사업화 전제.
- **포지셔닝 일관성** — "prior-art search"로 오포지셔닝 금지
  (`00_thiel_thesis` §0-4); 데이터셋도 examiner-grounded ≠ 사전조사.
- 컴플라이언스 규정 변동 — 월간 갱신 파이프라인.

## 12. Funding / next-step asks (advisor memo 사전 송부)
- 신 교수 결정항목(v3 §D-2): (a) **사업화 주체를 SDKB-자산(T1/T2/T3)으로
  재정렬** 승인, (b) v3 "3종 응용"→본 framing 승계, (c) 학술(T3 seed) vs
  제품(T1) 트랙 분리 확인, (d) 채점 시 deliverable ⑤를 "SDKB 사업화 전략"
  으로 평가.

---

### 작성자 체크리스트 (W2 결선)
- [x] **주체 = SDKB**, IPBridge는 T1 앵커로 종속 재배치
- [x] T1/T2/T3 수익화 트랙 + RBV에서 SDKB가 V/R/I/O 핵심
- [x] 시장·BM·경쟁 정량(회사 문서 출처) — T1 기준
- [x] SDKB 가치의 정량 측정 지표(§10) + 사업화 마일스톤(§9)
- [ ] §12 신 교수 미팅 결정항목 합의 (advisor memo)
