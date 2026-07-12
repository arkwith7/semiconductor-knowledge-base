# Hyeonup-Project 2026-1 — Internal Status

> **Audience.** Lab-internal (advisor / graders / project owner).
> This document tracks SDKB v1.0 against the **signed 2026-1 plan (v2 PDF)** and its amendments (v1→v3),
> and records a verified gap analysis of the built dataset/concepts vs. the v2 plan's quantitative targets.
> Public-facing usage of SDKB lives in [../README.md](../../README.md) (English) / [../README.ko.md](../../README.ko.md) (한국어).

- **Plan owner.** Park HyoungSik (Ph.D. 19기, 학번 2025730080) — (주)아크위드(ARKWITH) 대표이사
- **Advisor.** Prof. Juneseuk Shin — Quantitative Technology Management Lab, SKKU GSMOT
- **Authoritative plan.** `SDKB_v1_0_온톨로지_큐레이션_구축_실행계획_v2.pdf` (Version 2.0, 2026-04-12) — supersedes the v1 PDF. 본 학기 5대 목표·12주 4단계 파이프라인·릴리스 번들·평가 지표는 v2 §1.3 / §10 / §11 / §12 기준.
- **Amendment trail.** [v1](plan_amendment_v1.md) → [v2](plan_amendment_v2.md) → [v3](plan_amendment_v3.md) → [v3-bis](plan_amendment_v3_bis.md) (IP-R&D 실습 피드백 채널 분류·이중제출 선결, 신 교수 §D-2 대기) · architecture: [active ADR](architecture_amendment_sdkb_centric.md)
- **Last verified figures (2026-05-17).** curated graph **229 nodes / 268 edges (15 types)** · SIRP **1,000 patents** · examiner GT 7,500 + 3-rater 7,800 · **85 tests collected + SHACL VALIDATION PASSED**
- **Critical milestone.** **2026-05-30 지도교수 승인** / **2026-06 첫째 주 보고 완료** (v3 §D — 3주 압축)
- **이중 trajectory.** 산업(ARKWITH 3종 응용) + 학술(신 교수 Foresight/STEEPVE 4-pillar, 박사논문 seed, 목표 저널 IP&M / Scientometrics — v2 §14.3).

## 0. 1차 목표(v2 PDF) 대비 점검 분석 ⭐

v2 PDF §1.3의 **본 학기 5대 목표** + §10~§12(파이프라인·릴리스·평가)를 실제 빌드 산출물과 대조한 결과. 수치는 2026-05-17 직접 검증값.

| v2 1차 목표 | 계획 기준 (v2 PDF) | 실제 검증값 | 판정 |
|---|---|---|---|
| **① SDKB 온톨로지 설계** | ≥198 노드 / ≥264 간선, 14 Core 타입, Foresight 프레임워크 | `data/semiconductor_v0_3.json` **229 노드 / 268 간선, 15 타입** (baseline 198/264 → 큐레이션 확장; Device 31 신규) | ✅ 충족 |
| **② 전문가 프로필 100** | 100명 비식별 합성 + 도메인 자문 검증 | `experts/curated_profiles_en.json` **100** + `curated_profiles_kr.json` **110** (dual-track) | ✅ 초과 |
| **③ 문제 50 + 규제 25** | 소부장 SME 문제 50 + 다중관할 적대 25 | SIRP 거절특허 기반 **50 층화 + 25 적대** ([card](../dataset_rejected_patents_card.md) §5-1) + 외부 SME 226 / 적대 30 / 컴플 49 | ✅ 충족·초과 |
| **④ GT 7,500 + 신뢰도** | 100×50×3 = **7,500 평점**, weighted κ **≥ 0.6**, ICC **≥ 0.7** (v2 §12.1) | examiner GT **7,500** ✅ + 합성 3-rater **7,800** / **ICC(2,k) 합의라벨 = 0.787 → ICC 게이트 ✅ 통과** · weighted κ(quadratic) = **0.550**(0.05 미달) · (투명성) Fleiss κ=0.258, ICC(2,1)=0.552 | ⚠️ **ICC 게이트 통과 / weighted κ 0.05 미달** — §0-1 |
| **⑤ 사업화 전략 초안** | 시장·고객·BM·경쟁 분석 | [commercialization_strategy_v1.md](commercialization_strategy_v1.md) — ARKWITH 3종 응용 행 분리 + §10 측정 가능 지표 (v3 §C-1) | ⏳ W2 결선 |
| 릴리스 번들 (§11.1) | core/governance/**links-semi**.ttl, nodes/edges/expert_profiles/problems/ground_truth `.parquet`, prov.ttl, shapes.ttl, card, LICENSE | core/core-data/abox-patents·patent·rbv·commercialization·foresight·governance·governance-kr `.ttl` ✅ · shapes.ttl ✅ · **`sdkb-links-semi.ttl` 미구축** · expert/problems/GT는 JSON·CSV (parquet 경로 상이) | ⚠️ 부분 |
| 대표 SPARQL 3 (§12.2) | 규제리스크(BIS+ECCN) / FMEA경로 / 기술격차 | `examples/sparql/01_regulatory_risk.rq`·`02_fmea_path.rq`·`03_tech_gap.rq` — v2 §12.2와 정확 일치 | ✅ 충족 |
| SHACL 릴리스 게이트 (§8.3) | SHACL 통과 = 릴리스 기준, 유닛/통합 테스트 | `validation/shapes.ttl`+`shapes_patent.ttl`, `scripts/validate_shacl.py` → ✓ PASSED, **pytest 85 collected** | ✅ 충족 |

### 0-1. 짚어야 할 갭 (보고서 5장 "한계 및 후속 연구"에 반영)

1. **합성 3-rater 신뢰도 — 측정 정합 후 ICC 게이트 통과, weighted κ 0.05 잔여 미달** — v2 §12.1은 **weighted** κ ≥ 0.6 / ICC ≥ 0.7을 명시하나, 기존 코드는 순서형 점수(0–3, 우세범주 prevalence 0.539)에 대해 **가중 없는 명목형 Fleiss κ**를 계산하고 있었음(스크립트 docstring은 "weighted κ"라 기재 — 측정 버그). [scripts/ingest_curated_ratings.py](../../scripts/ingest_curated_ratings.py)를 계획 정합 통계로 보강(2026-05-17) 후 [reliability_report.md](../../data/experts/reliability_report.md):
   - **ICC(2,k) 합의라벨 = 0.787 → ICC ≥ 0.70 게이트 ✅ 통과**. 다운스트림 GT는 단일 평가자가 아니라 3인 합의 라벨이므로 ICC(2,k)가 결정 관련 지표(ICC(2,1)=0.552는 투명성 위해 병기).
   - **weighted κ(quadratic) = 0.550**, Krippendorff α(interval) = 0.552 — Fleiss 0.258 대비 "fair→moderate"로 상승하나 0.60 게이트에 **0.05 미달**(절반은 측정 오류, 절반은 실제 moderate 수준이라는 정직한 결론).
   - 원본 Fleiss κ=0.258 / ICC(2,1)=0.552, kappa-paradox 증거(우세 prevalence 0.539, pairwise exact 0.576)를 보고서에 **그대로 병기**(분식 아님, 측정 정합).
   - 1차 평가 기준 GT는 examiner-grounded 7,500 pairs(KIPO 심사관 인용 근거)이며 충족 — v3 dual-GT에서 합성 ratings는 **보조** 트랙. 보고서 5장: (a) examiner GT를 주 기준, (b) ICC 게이트 통과·weighted κ 0.05 잔여를 정직 명시, (c) rater rubric 강화(앵커 예시·척도 축약·calibration) → κ 재측정을 **후속 학기**(Tier C) 과제로 이관.
2. **`sdkb-links-semi.ttl` (SEMI Link-Only) 미구축** — v2 §11.1 릴리스 번들 및 §4.3 SEMI 내재화의 명세 항목. 현재 SEMI E10/E30/E40/E116은 식별자/링크 노드로 별도 TTL 미생성. v3 압축 일정상 T-후순위 — 보고서에서 "Link-Only 레이어 설계 완료, TTL 직렬화는 후속" 으로 명시(라이선스 리스크 회피 정책 자체는 [v3 §E](plan_amendment_v3.md) 유지).
3. **타입 정책 편차(경미)** — v2 §3.2는 "14 Core 타입 고정, 추가 타입은 Governance 레이어에서만 확장" 권고. 실제는 Domain에 `Device`(31) 추가로 15타입. Device는 반도체 도메인 핵심 엔티티로 합리적 확장이나, 보고서 3장에서 "Core 14 + 도메인 확장 1(Device)" 로 명시적으로 기록(정책 일탈이 아닌 의도적 큐레이션 결정임을 문서화).
4. **문서 수치 재조정 완료** — SIRP 773 → 실제 jsonl **1,000 레코드**, baseline 표기 "198 노드/268 엣지"(내부 모순) → **229/268** 통일, README "46/46 tests" → **85 collected**. 본 문서는 검증값 기준으로 갱신. README/CHANGELOG/card는 별도 동기화 필요(후속 정리 항목, §10).

### 0-2. v2 핵심 설계요소 충족 현황 (§2·§4·§5·§6·§8)

| v2 설계요소 | 상태 | 근거 |
|---|---|---|
| §2 Foresight/STEEPVE 프레임워크 | ⏳ 정렬 트랙 | [research_alignment.md](research_alignment.md) 4-pillar 매핑 — foresight 모듈 TTL은 스키마 단계 |
| §4.2 다중 스케일 융합 (SemiKong+SemicONTO) | ◑ 부분 | SemicONTO Phase 0~1 SKOS 정합 132 triples (CHANGELOG); SemiKong L1~L3는 매핑 설계 단계 |
| §4.3 SEMI 내재화 (E10/E30/E40/E116) | ⬜ Link-Only 미직렬화 | 위 0-1 항목 2 |
| §5 FBSFM 기반 FMEA 인과 | ✅ 그래프 충족 | FailureMode/RootCause/Mitigation/Skill + CAUSED_BY/MITIGATED_BY/OBSERVED_IN edge, SHACL FailureMode shape |
| §6 규제 코드화 (BIS§744.23/NIST/ECHA) | ✅ 충족 | `compliance/` KR 12 + US 8 controls, scenarios 34, leakage 4; governance-kr.ttl |
| §8 PROV-O / JSON-LD / SHACL / FAIR | ✅ 충족 | prov 메타데이터, JSON-LD context, shapes.ttl 릴리스 게이트, CDLA-Permissive-2.0 |

## 1. 메인 트랙 — 계획서 채점 항목 (v2 §1.3)

| # | 산출물 | 수량 요건 (v2) | 상태 | 경로 |
|---|---|---|---|---|
| ① | SDKB 온톨로지 | ≥198 노드 / ≥264 간선, 14 타입 | ✅ 충족 — **229 노드 / 268 간선 / 15 타입** (baseline 198/264 → 큐레이션 확장) | [../data/semiconductor_v0_3.json](../../data/semiconductor_v0_3.json) |
| ② | 합성 전문가 프로필 | 100명, 비식별, 도메인 자문 | ✅ **Dual track**: 합성/큐레이션 100(EN) + 110(KR) | `../data/experts/curated_profiles_en.json` + `curated_profiles_kr.json` |
| ③ | 기술 문제 + 규제 시나리오 | 50 + 25 (적대적, 다중 관할) | ✅ SIRP 50 층화 + 25 적대 + 외부 SME 226/적대 30/컴플 49 | [card §5-1](../dataset_rejected_patents_card.md), `../data/problems_external/*.json` |
| ④ | 정답 평가체계 | 7,500 ratings · weighted κ≥0.6 / ICC≥0.7 | ⚠️ 수량 충족(examiner 7,500 + 3-rater 7,800) · **ICC(2,k)=0.787 게이트 ✅** · weighted κ=0.550 (0.05 미달) · 원본 Fleiss 0.258/ICC(2,1) 0.552 병기 — §0-1 | `../data/patents/prior_art_pairs.parquet` (examiner) + `../data/experts/curated_ratings_3rater.csv` (3-rater) + [reliability_report.md](../../data/experts/reliability_report.md) |
| ⑤ | 기술사업화 전략 v1 | 시장·고객·BM·경쟁 + 자원·가치·규제 + IP-R&D | ⏳ W2 결선 — ARKWITH 3종 응용 §3 행 분리, §10 SDKB 도입 후 측정 가능 지표 (v3 §C-1) | [commercialization_strategy_v1.md](commercialization_strategy_v1.md) |

## 2. 정렬 트랙 — 신 교수 4-pillar 방향

상세 매핑: [research_alignment.md](research_alignment.md). v2 PDF §2(Foresight/STEEPVE) 정렬.

| 모듈 | 목적 | 상태 | 경로 |
|---|---|---|---|
| `sdkb-core.ttl` (+ core-data) | 14 Core + Device + enrichment 스키마 & 229 인스턴스 | ✅ 스키마+데이터 | `../ontology/sdkb-core.ttl`, `sdkb-core-data.ttl` |
| `sdkb-abox-patents.ttl` | SIRP 특허 인스턴스 풀 | ✅ 1,000 인스턴스 | `../ontology/sdkb-abox-patents.ttl` |
| `sdkb-patent.ttl` | Patent / CPC / IPC / RejectionReason / hasPriorArt | ◑ 스키마 완성, 인스턴스 abox로 분리 | `../ontology/sdkb-patent.ttl` |
| `sdkb-rbv.ttl` | Firm / Resource / Capability / EntryBarrier | ◑ 스키마 완성, 인스턴스 stub | `../ontology/sdkb-rbv.ttl` |
| `sdkb-commercialization.ttl` | TRL / License / Spinoff / IPTransaction | ◑ 스키마 완성, 인스턴스 stub | `../ontology/sdkb-commercialization.ttl` |
| `sdkb-foresight.ttl` | Scenario / STEEPVE / RealOption | ◑ 스키마 완성, 인스턴스 stub | `../ontology/sdkb-foresight.ttl` |
| `sdkb-governance-kr.ttl` (+ governance) | 한국 산업기술보호법 / 다중 관할 | ◑ 스키마 완성, controls는 `compliance/`에 별도 | `../ontology/sdkb-governance-kr.ttl` |
| `sdkb-links-semi.ttl` | SEMI E10/E30/E40/E116 Link-Only | ⬜ **미구축** (v2 §11.1 명세 항목 — §0-1 참조) | (예정) `../ontology/sdkb-links-semi.ttl` |

## 3. 1차 실 데이터 — SIRP 거절특허 ⭐

| 항목 | 값 |
|---|---|
| 파일 | [../data/patents/raw/semiconductor_industry_rejected_patents.jsonl](../../data/patents/raw/semiconductor_industry_rejected_patents.jsonl) |
| 규모 | **1,000 레코드** (jsonl 실측). [card](../dataset_rejected_patents_card.md) 기재 "773"은 초기 코호트 스냅샷 — 카드/README 동기화는 §10 후속 항목 |
| GT | examiner-cited 인용 풀 → `prior_art_pairs.parquet` 7,500 pairs (positive 2,723 + hard-neg 2,723 + easy-neg 2,054) |
| 출처 | KIPRIS Plus API + KIPRIS 웹 (KIPO) |
| 데이터 카드 | [dataset_rejected_patents_card.md](../dataset_rejected_patents_card.md) |
| 라이선스 | KIPRIS Plus API 약관 — 학교 자문 후 조정 (v3 §E 3-option 분기) |

## 4. 큐레이션 ExpDataSet 통합 (외부 자산 흡수) ⭐

| 자산 | 통합 위치 | 규모 |
|---|---|---|
| KR 거버넌스 마스터 (산업기술보호법 §33/§34) | `../data/compliance/kr_standards_v1.json` + `../ontology/sdkb-governance-kr.ttl` | 12 controls |
| US 거버넌스 마스터 (EAR/CCL + Deemed Export) | `../data/compliance/us_standards_v1.json` | 8 controls |
| 큐레이션 전문가 풀 (KR + EN) | `../data/experts/curated_profiles_{en,kr}.json` | 100 + 110 profiles |
| 3-rater synthetic ratings | `../data/experts/curated_ratings_3rater.csv` | 7,800 ratings · weighted κ=0.550 / Krippendorff α=0.552 / ICC(2,k)=0.787 · (투명성) Fleiss κ=0.258 / ICC(2,1)=0.552 |
| Compliance scenarios | `../data/compliance/scenarios_v1.json` | 34 scenarios |
| Leakage incidents L1~L4 | `../data/compliance/leakage_incidents_v1.json` | 4 cases |
| SME problems (external reference) | `../data/problems_external/sme_problems_v1.json` | **226** problems (+ adversarial 30 / compliance 49) |

## 5. Plan reference

- **Authoritative.** `SDKB_v1_0_온톨로지_큐레이션_구축_실행계획_v2.pdf` (v2.0, 2026-04-12) — 본 학기 5대 목표·12주 파이프라인·릴리스 번들·평가 지표.
- Superseded: `SDKB v1.0 온톨로지 큐레이션 구축 실행계획.pdf` (v1).
- Signed 현업프로젝트1 계획서 (서명 2026-03-23) — see lab project memory.

## 6. Verified figures (2026-05-17 실측)

- 큐레이션 그래프 **229 노드 / 268 엣지 / 15 타입** (baseline v0.3 원본 198/264 → 큐레이션 확장; Device 31 신규)
- SIRP **1,000** rejected patents (jsonl 실측) · 7,500 examiner-grounded pairs
- 50 stratified problems · 25 adversarial scenarios (all anchored) + 외부 SME 226 / 적대 30 / 컴플 49
- 100 (EN) + 110 (KR) curated experts = **dual-track pool**
- 7,500 examiner + 7,800 3-rater synthetic = **dual-track GT** (3-rater: ICC(2,k)=0.787 ✅ / weighted κ=0.550 / Fleiss κ=0.258·ICC(2,1)=0.552 병기 — §0-1)
- KR+US governance: 20 controls
- **85 tests collected (pytest) + ✓ SHACL VALIDATION PASSED** (README "46/46"은 구수치 — 동기화 필요)
- 대표 SPARQL 3 (v2 §12.2): `examples/sparql/0{1,2,3}_*.rq` 일치

## 7. ARKWITH 3종 응용 정렬 — v3 합의 ⭐

[Amendment v3 §A-1](plan_amendment_v3.md) — SDKB는 (주)아크위드의 3종 핵심 응용 공통 백본. 동시에 v2 §14.3 학술 기여(IP&M / Scientometrics 투고)의 seed dataset.

> ⚠️ **재정렬 플래그 (2026-05-17, 소유자 결정).** 사업화 deliverable ⑤는
> 실제 ARKWITH repo(arkwith-web/api) 검토 결과 **단일 제품 IPBridge** 현실에
> 맞춰 **SDKB-자산 중심(T1 IPBridge 앵커 / T2 백본 라이선싱 / T3 데이터셋)**
> 으로 전면 재작성됨 — [commercialization_strategy_v1.md](commercialization_strategy_v1.md).
> 아래 v3 "3종 응용" 표는 **서명 트랙 기록으로 보존**하되, ⑤ 채점·5장 framing
> 에서는 본 재정렬이 우선. v3/§8 정합은 **신 교수 미팅 결정항목**([v3 §D-2](plan_amendment_v3.md)):
> ①매칭·②기술현황은 현 제품 라인 아닌 SDKB-enabled 인접 기회로 강등.

| ARKWITH 응용 | SDKB가 공급하는 백본 | 보고서 4장 시연 |
|---|---|---|
| **① 기술문제 ↔ 기술인력 매칭** | Expert pool 100+110 + governance 20 controls + SDKB-Match Expert 아키텍처 | UC1 SPARQL + GitHub Pages `usecases/uc1_*.html` |
| **② 반도체 소부장 R&D 기술현황 정보** | 큐레이션 그래프 229 nodes + 4-pillar 정렬 + SIRP 1,000 patents | GitHub Pages 4-pillar view + baseline view + SIRP view |
| **③ R&D 선행기술 보고서** (IPBridge가 한 구현체) | examiner-grounded 7,500 pairs + SDKB-Match PriorArt 아키텍처 | UC2 SPARQL + (T3) IPBridge v0 strata별 비교 |

## 8. 현업프로젝트 결과보고서(5장) framing — v3 합의 ⭐

[Amendment v3 §C-2](plan_amendment_v3.md) 매핑. v2 §1.3 5대 목표를 ARKWITH 3종 응용 prism으로 재구성.

- **참여기업**: (주)아크위드(ARKWITH) — 학생소속기업
- **외부 참여자**: Bespin Global · POSCO DX · KUKKUK 팀(김범수 FST 부사장 외)
- **기업수요 반영여부**: 기획 시 ☑ — 3종 응용 공통의 도메인 백본 부재가 SDKB 큐레이션 기획에 직접 반영

| 보고서 장 | 본 프로젝트 산출물 |
|---|---|
| 1장 문제와 기업 현황 | ARKWITH 회사 개요 + 3종 응용 + 도메인 백본 부재의 정량/정성 증거 |
| 2장 기존 방법 | 도메인 온톨로지 없는 매칭/기술현황/선행기술 도구의 한계 + 학계 부분 ontology 부재 |
| 3장 신규 방법 | SDKB v1.0 4-layer 아키텍처 + PROV-O + SHACL + SDKB-centric curation (Core 14 + Device 확장 명시) |
| 4장 적용 결과 | UC1 매칭 + UC2 선행기술 + 시각화 인터랙티브 증빙 + 품질지표 + **§0-1 한계(κ/ICC, links-semi) 정직 명시** |
| 5장 성과 및 기대효과 | ARKWITH 3종 응용 적용 가설 + HuggingFace 공개 + 박사논문 seed + v2 §14.3 4-pillar 학술 어젠다(IP&M/Scientometrics) 기여 |

SPARQL 시연: `examples/sparql/uc{1,2}_*.rq` + `data/use_cases/uc{1,2}_result.tsv` (현재 미구축 — W2 신규). GitHub Pages: `site/usecases/uc{1,2}_*.html` (현재 미구축 — W3 신규). 빌더는 [`scripts/build_viz.py`](../../scripts/build_viz.py)에 entry 2개 추가([`visualization_plan.md`](visualization_plan.md) Phase 2 일부 앞당김). 기존 v2 §12.2 대표 3쿼리(`0{1,2,3}_*.rq`)는 이미 충족.

## 9. 3주 압축 실행 일정 (2026-05-16 → 2026-06-07)

[Amendment v3 §D](plan_amendment_v3.md) 그대로 인용. 원 v2 PDF 12주(2026.04~06) 4단계 파이프라인이 현업프로젝트 결선·시연 중심으로 압축됨. 주당 12~15시간 집중.

| 주차 | 작업 | 산출물 |
|---|---|---|
| W1 (5/16-22) | 행정 정보 + 보고서 골격 + 1·2·3장 본문 초안 + UC1 시나리오 확정 | 보고서 50% + 시나리오 메모 1p |
| W2 (5/23-29) | UC1·UC2 SPARQL 결선 + 4·5장 본문 + 부록 + 신준석 교수 1차 검토 | 보고서 90% + SPARQL 결과 |
| **5/30 (토)** | **지도교수 승인 ☑** | 합격확인서 서명 준비 |
| W3 (6/1-7) | 최종 수정 + 부록 B 결선 + 합격확인서 서명 + 제출 | 최종 .docx + 합격확인서 ☑ |

**Tier 우선순위 (절단 순서)**: T1 보고서 5장 + UC1 / T2 UC2 + 시각화 view / T3 IPBridge 정량 비교 / T4 pytest 회귀(후속 학기). 자세한 절단 정책은 [v3 §D-1](plan_amendment_v3.md).

**SME 리뷰**: 김범수 FST 부사장 (W1-W2 30분). 결과는 `docs/project/feedback/2026w22_kim_review.md`. 이영주 POSCO DX PM 리뷰는 후속 학기로 연기.

## 10. 후속 정리 항목 (보고 완료 후 / 비채점)

- ✅ (2026-05-17 해소) **테스트 회귀** — 원인: 커밋된 `sdkb-core.ttl`이 stale `1.0.0-dev`(enrichment·메타데이터 누락). `make owl` 재생성(438 triples, 1.1.0-dev) → **75 passed / 10 skipped / 0 failed**. CHANGELOG 2026-05-17 항목에 기록.
- ✅ (2026-05-17 완료) README(EN/KO)/CHANGELOG/datasheet/card SIRP·노드·테스트·κ 수치를 검증 스냅샷으로 일괄 동기화 (CHANGELOG 과거 일자 항목은 보존). 커밋 `46230c6` (private origin push 완료).
- ⚠️ **익명 스냅샷 제외 갱신 필요** — [commercialization_strategy_v1.md](commercialization_strategy_v1.md)가 실제 ARKWITH 독점정보(IPBridge 시장·가격·로드맵)로 재작성됨 → project_status/risk_review처럼 **익명 스냅샷 제외 대상**. 다음 스냅샷 재빌드 시 rsync `--exclude='docs/project/commercialization_strategy_v1.md'` 추가(제출 직전 재빌드 필수). [risk_review](dataset_publication_risk_review.md) 동기화 완료.
- `sdkb-links-semi.ttl` 직렬화 (v2 §11.1 릴리스 번들 완성).
- ✅ (2026-05-17 완료) 합성 3-rater 신뢰도 측정 정합 — weighted κ/Krippendorff α/ICC(2,k) 산출, [reliability_report.md](../../data/experts/reliability_report.md) 재생성. **잔여**: rater rubric 강화(앵커·척도 축약·calibration) → weighted κ 0.05 미달분 재도전 (Tier C, 후속 학기).
- `examples/sparql/uc{1,2}_*.rq` + `data/use_cases/` + `site/usecases/` + `scripts/build_viz.py` UC entry (v3 W2~W3).
- 학술 trajectory: v2 §14.3 목표 저널(IP&M / Scientometrics) 초록 draft — 박사논문 seed와 연계.
- **데이터 확장 검토의견 대응(2026-2 Stage 2 귀속)** — KIPRIS 최신·생태계 데이터 4종(융합기술 IPC/CPC · 대기업↔소부장 공동출원/인용 · 국가핵심기술/R&D · 심판·분쟁) 채택 방안. 현 학기 승인 범위 불변, 보고서 5장 "확장 로드맵" 절에 서술만 반영 → [feedback/2026w22_dataset_expansion_review_response.md](feedback/2026w22_dataset_expansion_review_response.md).
