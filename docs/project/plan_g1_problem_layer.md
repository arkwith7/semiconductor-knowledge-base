# PLAN — G1 특허 문제층 (Patent Problem-Atom Layer · 데이터셋 논문)

> **상태**: ✅ **완료(2026-07-22)** · 사용자 결정 — **(A) 문제원자 추출층 구축** · **(나) 두 논문 분리·연결**
> · **(ㄱ) Bedrock** · **(ㄴ) C1 함께** · **신규 개념 (1) 전부 채택**. 선행: [`plan_tier3_g2dep_and_g1_axis.md`](plan_tier3_g2dep_and_g1_axis.md) §G1(Phase A·B).
> 근거: memory `expert-matching-pilot-bottleneck-flipped` · `g0-frozen-abandoned-full-rebuild`.
>
> **실측 결과.** C1: src_g1 84,079 독립항 → 334k feature · claim-feature TTL 6.9M 트리플 · SHACL PASS.
> C2: 24,179 특허 abstract → 문제 추출(Bedrock Haiku · solves 3,761/24,179 = 16% · 실패 0).
> C3(사용자 원칙 "특허 문제는 모두 공식 문제 — 버리지 말고 재배치·추가정의"): 기존 45개념 **재배치
> 3,378** + 잔차 383 중 **신규 FailureMode 개념 30개 채택**(Sonnet canonical 통합 · Haiku 배정 243특허) →
> **3,621 특허 문제엣지 보유**. FailureMode 어휘 25→55. 순수 설계 61건은 정직 제외.
> C4: graph_v1 재조립 **868,669 트리플** · exhibitsFailureMode 2,816 · relatedToTopic 3,236 ·
> **H1 불변 검증**(realizesProcess 11,647·concernsDevice 23,342·Patent 25,179 전부 불변) · L1 SHACL PASS.
> C5: **CQ28(특허↔문제↔전문가) 비공허 11,794행**(423특허↔70전문가) · vocab 검증 술어 36→38(+caseFailureMode·
> hasCaseExperience) · CQ 배터리 27→28. 신규 어휘 발명 0(exhibitsFailureMode·relatedToTopic 는 기존 TBox).
>
> **미해결/후속**: 신규 30개념은 특허엔 실렸으나 전문가 사례가 없어 CQ28 커버는 기존 5모드 교집합만
> (신규개념↔전문가 매칭은 전문가층 확충 또는 AFCP-EM 몫). 신규 개념 상류 SDKB 승격은 별도(현재 paper
> delta 의 frozen CSV `data/failuremode_concepts_new.csv` 에 산다). G2 문제층 확장 미착수.

## 0. 목적 · 범위
특허 코퍼스를 **문제(FailureMode/RootCause) 공간**에 연결하는 데이터층을 온톨로지에 추가한다.
데이터셋 논문(sdkb-foresight)의 **task-fitness** 지지: (a) 선행기술 설명("이 선행특허가 왜 관련 =
어떤 결함을 다룸") (b) 하류 매칭(AFCP-EM · 별도 논문·별도 저널)이 참조할 substrate.

- **NOT** 매칭 알고리즘·MRR — AFCP-EM 몫. 데이터셋 논문이 완성되면 그 위에서 진행.
- **NOT** G0/G2 확장(G1 먼저) · Phase D(종속항).

## 1. 근거 (파일럿 실측 2026-07-22)
- 상향식 문제 추출 89%(133/150) · 104종 결함모드(전문가 어휘 5종 대비) · 변별력 확인.
- 병목은 특허측이 아니라 전문가측 얇음이었으나, **AFCP-EM에 226문제·110전문가·GT 7,801행 이미 존재** →
  데이터셋 논문은 층·다리만 만들고 매칭 평가는 AFCP-EM.
- **T-Box 브리지 이미 존재**(발명 0): `ont:exhibitsFailureMode`(Patent∪Problem→FailureMode) ·
  `ont:relatedToTopic`(→RootCause∪Mitigation∪TopicCluster). 개념 FailureMode 25·RootCause 20 기존.
  sme_problems `defect_types`(bridging·residue)가 기존 FailureMode 개념과 동일 어휘.

## 2. 파이프라인
| 단계 | 무엇 | 백엔드/재사용 |
|---|---|---|
| **C1** | `src_g1` claim-feature 분해(독립항만) → build_abox → SHACL. 선행기술 all-elements 축 | Bedrock Haiku(flag) · 코드 준비됨 |
| **C2** | 특허 abstract+title → {process·defect(FailureMode)·rootCause·symptom} 구조 추출. sme_problems 스키마 few-shot 타깃 | Bedrock · temp 0 · 캐시 |
| **C3** | 원문 결함어 → 기존 25 FailureMode/20 RootCause 매핑(임베딩 유사도+임계). 신규는 후보 분리(사람 채택) | 로컬 임베딩 · 방법 사전동결 |
| **C4** | delta에 `exhibitsFailureMode`·`relatedToTopic` 엣지 → graph_v1 재조립. 신규 개념은 상류 SDKB 제안 | 신규 어휘 0 |
| **C5** | 새 CQ(특허↔문제↔전문가 경로) + SHACL patent-failuremode shape + 서명 | 측정 |

## 3. 사전동결 (결과 보기 전)
추출 프롬프트·스키마 · 정규화 임계·임베딩 모델 · 신규개념 채택 규칙(후보→사람) · CQ 정의.

## 4. 성공 기준
- 추출수율 보고 · 특허→FailureMode 커버리지 · 새 CQ 비공허 · populated cell(CMP×Dishing) 사슬 폐합.
- **H1 불변**: exhibitsFailureMode는 realizesProcess/concernsDevice·병합집합 안 건드림 → C₀/C₁ 불변(회귀테스트).
- SHACL 통과 · pytest green · 사람 표본검증.

## 5. 비목표
매칭 MRR·EM 하네스 재배선(AFCP-EM) · G0/G2 확장 · Phase D.

## 진입점
- SDKB: `scripts/decompose_corpus.py`(`src_g1` 준비됨) · **신규** `scripts/extract_patent_problems.py`(C2) ·
  `scripts/normalize_problem_atoms.py`(C3) · `build_abox_*`(C4) · CQ(C5).
- paper: `src/sdkb_paper/ontology/delta.py`(exhibitsFailureMode 배선) · graph_v1 재조립.
