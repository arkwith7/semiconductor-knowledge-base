# PLAN — 거절특허 종속항 feature 분해 (Tier 1) · 판단 계층 완성

> **상태**: 대기 · **새 세션에서 착수** (사용자 지시 2026-07-22)
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
- **인용 선행기술 종속항(Tier 2)** · **G2 종속항(Tier 3)** — 별개 PLAN.
- "겹치는 feature" 라벨링(여전히 도출·검증).

## 6. 파급
- TBox 소폭 확장: `ont:dependsOnClaim` 1개 프로퍼티. 나머지 재사용.
- 볼륨: ClaimFeature 166K → ~200K(거절특허 종속분만). 로컬·결정적이라 관리 가능.
- G₀ 불변 폐기 방침(→ [[g0-frozen-abandoned-full-rebuild]]) 하에서 진행 — 실험 재실행은 가설 재정의 후.

## 7. 착수 메모 (새 세션용)
- 진입점: `scripts/decompose_corpus.py`(is_independent 필터), `build_abox_claim_features.py`(dependsOnClaim).
- 현재 데이터셋 서명: `data/reports/central_axis_dataset_signature.json`.
- 이번까지 완료: 인용노드 3,034 · Claim 53,860(독립만) · Feature 165,940 · Judgment 635 · aboutClaim 1,588 · SHACL ✓.
