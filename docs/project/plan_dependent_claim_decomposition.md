# PLAN — 거절특허 종속항 feature 분해 (Tier 1) · 판단 계층 완성

> **상태**: ✅ **완료** (2026-07-22) — 성공기준 4/4 충족. 실측: 종속항 10,562 분해(원천 10,568 −
> 중복 claim_no 6) · dependsOnClaim 12,058(매달린 부모 2 버림) · 종속 참조 회수율 **1.000**(1,727/1,727,
> ≥0.9) · SHACL 4종 통과 · 완전판단 595→604. 서명: Claim 64,422(독립 53,860+종속 10,562) ·
> ClaimFeature 183,651 · aboutClaim 1,588→5,917 · TTL 1,591,921 트리플. 회귀 테스트 6종 추가(pytest 90 green).
> **근거**: 판단 청구항의 **75%가 종속항**이라 현재 feature-단위 대비 불가. 이 격차는 **거절특허에만**
> 해당(판단 aboutClaim 은 거절특허 청구항만 지목).
> **관련**: [`prior_art_ontology_positioning.md`](prior_art_ontology_positioning.md) §3 C2 ·
> [`plan_claim_judgment_reextraction.md`](plan_claim_judgment_reextraction.md) · TBox `Claim`·`ClaimFeature`

## 1. 문제 (실측)
현재 분해는 세 소스 전부에서 **독립항만** 했다. 종속항은 미분해:

| 소스 | 독립(분해) | 종속(미분해) | 종속% | 목적 |
|---|---:|---:|---:|---|
| **거절특허(1,000)** | 3,117 | **10,568** | 77% | **판단 계층(Tier 1 — 본 PLAN)** |
| 인용 선행기술 | 10,023 | 30,566 | 75% | 인용측 all-elements (Tier 2) |
| G2 소부장 | 44,410 | 116,774 | 72% | 코퍼스 신규성 대비 (Tier 3) |

**판단(aboutClaim)에 직접 필요한 것 = 거절특허 종속항 10,568건뿐.** 판단이 지목한 청구항의
독립 605 / **종속 1,813 (75%)** 이 현재 링크 불가.

## 2. 왜 Tier 1 이 최우선인가
- §29②(진보성) 거절의 **결정적 added-feature 는 종속항에 있다** — 종속항 = 부모 한정 + 추가 한정.
  그 추가 한정이 진보성 판단의 초점인데 지금은 미포착.
- feature-단위 판단 능력이 판단 대상의 **25% → ~100%** 로. 논문 핵심 주장을 완성.
- 가장 작은 범위(10,568)로 가장 큰 판단 효과. Tier 2·3 과 독립적으로 값짐.

## 3. 방법 (설계)
1. **종속항 분해** — `decompose_corpus` 에 거절특허 종속항 포함(현재 `is_independent` 필터 제거/확장).
   종속항은 짧아("청구항 N에 있어서, [추가 한정]") 규칙+LLM 분해가 오히려 쉬움.
2. **청구항 상속 실체화** — TBox `ont:dependsOnClaim`(Claim→Claim) 신설. `claims_full` 의
   `depends_on` 으로 결정적 연결. **완전 한정요소 집합 = 부모 features ∪ 종속 추가 features**
   (질의/추론으로 계산 — 저장은 추가분만).
3. **판단 재연결** — 재빌드로 `aboutClaim` 이 종속항 노드에 연결(1,813 종속 참조 회수).
4. **게이트** — SHACL(기존 Shape_Claim·ClaimFeature 재사용) + 재빌드 후 통과 확인.

## 4. 성공 기준
- 거절특허 종속항 10,568 분해 · `dependsOnClaim` 으로 부모 연결.
- **판단 청구항 종속 참조 1,813 중 회수율 ≥ 0.9** (분해된 종속항에 aboutClaim 연결).
- 완전 판단(근거+대상청구항+인용) 575 → 대폭 증가(종속항 회수분).
- SHACL 통과 · 재현성.

## 5. 비목표 (이번 범위 밖)
- ~~**인용 선행기술 종속항(Tier 2)**~~ — ✅ **완료(2026-07-22)**, 아래 §8.
- ~~**G2 종속항(Tier 3)**~~ — 별개 PLAN 로 수리(2026-07-22): [`plan_tier3_g2dep_and_g1_axis.md`](plan_tier3_g2dep_and_g1_axis.md).
- **주 대비 코퍼스 G1 청구항 축 확장** — 같은 PLAN §G1(순서: Tier 3 → G1).
- "겹치는 feature" 라벨링(여전히 도출·검증).

## 8. Tier 2 — 인용 선행기술 종속항 (완료 2026-07-22)
인용측 all-elements 대비를 위해 인용 선행기술 종속항을 실체화. Tier 1과 대상 축이 다르다
(Tier 1=판단 대상 거절특허 / Tier 2=대비 기준 인용문헌).
- **실측:** 인용 종속항 **30,565** 분해(부모 추출 96.2% 성공, 매달린 부모는 가드가 흡수) →
  그래프 병합 **30,438**(나머지는 cited_map 미해결 문헌 — 독립 인용과 동일 규율). 서명:
  Claim 64,422→**98,526**(독립 57,526+종속 41,000) · ClaimFeature 183,651→**253,850** ·
  dependsOnClaim 12,058→**45,475**(매달린 부모 20 버림) · TTL **2,230,338** · aboutClaim
  5,917 불변(인용측이라 거절 판단 불변). **SHACL 4종 통과** · pytest 93 green(회귀 3종 추가).
- **LLM 재분해 = AWS Bedrock Haiku**(`global.anthropic.claude-haiku-4-5`, egress 사용자 승인).
  `llm_decompose_batch`로 캐시 미스분만 16-way 병렬 → 3,732 호출 **~6분**(순차 ollama였다면 ~2.5h).
  temperature 0 + sqlite 캐시(키에 모델 포함)로 결정적. 백엔드는 `LLM_BACKEND`로 선택(ollama 보존).
  bedrock 경로는 **boto3** 지연 import(선택 의존성 — ollama 경로는 boto3 없이 동작).
- **egress 주의:** KIPRIS 비재배포 청구항 전문이 Bedrock으로 나간다 — 사용자 명시 승인 하에서만.

## 6. 파급
- TBox 소폭 확장: `ont:dependsOnClaim` 1개 프로퍼티. 나머지 재사용.
- 볼륨: ClaimFeature 166K → ~200K(거절특허 종속분만). 로컬·결정적이라 관리 가능.
- G₀ 불변 폐기 방침(→ [[g0-frozen-abandoned-full-rebuild]]) 하에서 진행 — 실험 재실행은 가설 재정의 후.

## 7. 착수 메모 (새 세션용)
- 진입점: `scripts/decompose_corpus.py`(is_independent 필터), `build_abox_claim_features.py`(dependsOnClaim).
- 현재 데이터셋 서명: `data/reports/central_axis_dataset_signature.json`.
- 이번까지 완료: 인용노드 3,034 · Claim 53,860(독립만) · Feature 165,940 · Judgment 635 · aboutClaim 1,588 · SHACL ✓.
