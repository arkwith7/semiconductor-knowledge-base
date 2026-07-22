# PLAN — Tier 3(G2 종속항) + 주 대비 코퍼스 G1 청구항 축 확장

> **상태**: 수리(2026-07-22) · 사용자 결정 — **순서 C(Tier 3 먼저 → G1)** · **egress 승인(Bedrock Haiku)**.
> 착수 전. 설계 승인 후 4단계(구현). 선행: [`plan_dependent_claim_decomposition.md`](plan_dependent_claim_decomposition.md)(Tier 1·2 완료).
> **G₀ 동결 폐기 방침 하에서 진행** — 이 PLAN 은 중심축 구축까지만이며, **H1/H2/RQ3 재검정을 트리거하지 않는다**
> (재검정은 "재구축 가설 재정의" 이후 별도 게이트). 근거: memory `g0-frozen-abandoned-full-rebuild`.

## 0. 문제 (실측 2026-07-22)
중심축(선행기술조사 feature 대비)이 **주 대비 코퍼스에 안 걸린다**.

| 축 | claimText | 독립 분해 | 종속 분해 | 판정 |
|---|---:|---:|---:|---|
| 거절특허(판단측) | — | 3,117 | 10,562 ✅ | Tier 1 완료 |
| 인용 선행기술(대비 기준) | — | 10,023 | 30,565 ✅ | Tier 2 완료 |
| **G2 소부장(코퍼스)** | 12,339 | 44,410 ✅ | **116,774 ❌** | **Tier 3 — 본 PLAN §T3** |
| **G1 삼성·SK하이닉스(주 대비축)** | **2(≈0)** | **0 ❌** | **0 ❌** | **본 PLAN §G1** |

- H1/RQ1/RQ2 의 핵심 대비는 **G₀→G₁** 인데, feature-단위 all-elements 대비 층이 G1 에 **커버리지 0**.
  즉 논문이 주장하는 선행기술조사 능력이 정작 주 대비축에서 실증되지 않는다.
- 원인: [`sdkb-foresight-paper`](../../SKKU/sdkb-foresight-paper) `delta.py` 의 `samsung-hynix` 분기가
  `build_delta(df)` 를 **`details=None`** 로 호출한다(청구항 미수집). `ksia-equipment`(G2)만 details 를 실어
  claimText 를 심는다. 우회가 아니라 **미수집**이다.

## 1. 순서 (사용자 결정 C)
**Tier 3 먼저**(이미 claimText 보유 → 수집 불필요) → **그다음 G1**(수집부터). 근거: 수집 없는 작업을 먼저
털고, "주 대비축 공백"은 수집 리드타임이 있으므로 뒤에 둔다. G1 종속항은 최대 볼륨(≈2배)이라 독립항으로
축을 먼저 닫고 종속은 별도 게이트(§G1 D).

---

## §T3. Tier 3 — G2 종속항 116,774 (선행)

> **상태**: ✅ **완료(2026-07-22)**. 실측: G2 종속항 **116,774** 분해 → feature 201,788(LLM 재분해
> 11,479/12,119 flag·Bedrock Haiku·0요소 스킵 0). **부모추출 회수율 1.0000**(매달린 부모 1건만 가드가 버림).
> 서명 변화: Claim 98,526→**215,300**(독립 57,526+종속 41,000→**157,774**) · ClaimFeature 253,850→**455,638** ·
> dependsOnClaim 45,475→**174,010** · 매달린부모버림 20→**21** · TTL 2,230,338→**4,201,318**.
> **aboutClaim 5,917·PriorArtJudgment 635 불변**(G2는 코퍼스측 — 거절 판단 안 건드림). **SHACL 4종
> CONFORMS=True**(전체 4.2M 트리플, shapes_claim_features + sdkb-patent TBox) · pytest **93 passed**.
> G2 전체 청구항 161,184 = 독립 44,410 + 종속 116,774. 코드 변경 1곳: `src_g2()` is_independent 필터 제거.

### 목적
코퍼스 신규성 대비의 all-elements 완성. Tier 1(판단측)·Tier 2(인용측)에 이어 G2 소부장 코퍼스의
**종속 added-feature**(§29① 완전 한정요소집합 = 부모 features ∪ 종속 추가 features)를 실체화.

### 설계 (Tier 1/2 와 동일 패턴 — 신규 로직 최소)
1. **`scripts/decompose_corpus.py` `src_g2()`** — `if is_independent(txt)` 필터 제거, 종속항 포함.
   부모 번호는 `_parents(txt)`(텍스트 추출, G2 는 구조화 depends_on 없음). Tier 2 의 cited 와 동형.
2. **`build_abox_claim_features.py`** — 기존 종속 경로 재사용: `dependsOnClaim` 엣지 + **실재-부모 가드**
   (`present_claims`)로 매달린 부모 IRI 차단(이 프로젝트 핵심 결함패턴 — memory `prior-art-cited-docs-are-dangling-iris`).
3. **LLM 재분해** — flag 청구항만 Bedrock Haiku 16-way 병렬(`LLM_BACKEND=bedrock`, temperature 0 + sqlite 캐시).
   egress 승인분(§공통). 볼륨 추정: Tier 2 (30,565 종속 → 3,732 호출 ~6분)의 ~3.8배 → **~14k 호출 ~25분**.
4. **게이트** — SHACL 4종 재사용 + 재빌드 후 통과. 회귀 테스트 추가.

### 성공 기준
- G2 종속항 116,774 분해 · `dependsOnClaim` 부모 연결 · **종속 참조 회수율 ≥ 0.9**.
- SHACL 4종 통과 · pytest green · 결정성(캐시). 서명(`data/reports/central_axis_dataset_signature.json`) 갱신.
- 예상 서명 변화(추정): ClaimFeature 253,850 → ~450k · dependsOnClaim 확장 · TTL 2.23M → ~3.5M.
  **aboutClaim 5,917 불변**(G2 는 인용/코퍼스측 — 거절 판단 안 건드림).

### 비목표
- G1(§G1). "겹치는 feature" 라벨링. H1/H2/RQ3 재검정.

---

## §G1. 주 대비 코퍼스 G1 청구항 축 확장 (후행)

### 목적
RQ2(선행기술조사) — feature-단위 대비를 **H1/RQ1 의 G₀→G₁ 대비축에 실제로 걸리게** 한다.

### 설계 — G2 와 완전 대칭. `build_delta` 의 `details` 만 채우면 된다.
아키텍처가 이미 대칭이라 신규 발명 0: [delta.py:127-142](../../SKKU/sdkb-foresight-paper/src/sdkb_paper/ontology/delta.py#L127-L142)
는 details 를 받으면 claimText/abstractText/claimCount 를 심는다. G1 은 details 만 없다.

**Phase A · 수집(paper 저장소 collect 모듈).**
- G₁ 병합 특허 **24,179건**(삼성 23,901·SK하이닉스 10,620 델타의 병합분) 전량의 초록+전체청구항을
  KIPRIS `getBibliographyDetailInfoSearch` 로 수집(G2 와 동일 클라이언트 `collect/kipris_client.py`).
  호출량 ~24k(G2 12,337 의 약 2배 — 레이트리밋으로 수 시간).
- 산출: details parquet(G2 의 `KSIA_DETAILS` 와 동형) + **프로파일(CLAUDE.md §4 의무: 구조·형태·기술통계·목적)**
  + `data/MANIFEST.md` 행(일시·검색식·건수·저장파일·반영 그래프).

**Phase B · claimText 실체화(엣지 중립).**
- `delta.py` `samsung-hynix` 분기(`else`, 현재 `build_delta(df)`)에 details 를 실어 재조립 → graph_v1.ttl.
- **claimText/abstractText/claimCount 는 datatype 속성** → `realizesProcess`·`concernsDevice` 엣지 불변.
  claim 은 개념 매핑 필터([delta.py:102](../../SKKU/sdkb-foresight-paper/src/sdkb_paper/ontology/delta.py#L102)) **뒤**에 붙으므로
  병합 특허 집합도 불변. **H1 커버리지(C₀/C₁·realizesProcess 1,565·concernsDevice)는 원리적으로 불변** —
  G2 청구항 수집이 G₀·H1 을 안 건드린 것과 같은 이유.

**Phase C · 분해(SDKB `decompose_corpus.py` `src_g1()` 신설).**
- `src_g2()` 와 동형: graph_v1.ttl 의 `ont:claimText` 를 읽어 (patent, claim_no, text, depends_on) 방출.
- **독립항만**(현 G2 베이스라인과 대칭). build_abox → Claim/ClaimFeature 실체화. SHACL·회귀 테스트.
- 볼륨 추정: 24,179 특허 → 독립 ~90k 청구항. flag 청구항만 Bedrock 재분해(egress 승인분).

**Phase D · G1 종속항 (별도 게이트 · Tier 4 후보).**
- G1 종속 ~230k 추정 — 중심축을 약 2배로. **여기서 착수하지 않는다.** Phase C 완료 후 비용/필요를 재평가해
  사용자와 확정(silent drop 아님 — 명시적 후속 항목).

### 성공 기준
- graph_v1 claimText ≈ 24,179(특허당 청구항 블록) · **H1 커버 한 자리도 불변(엣지 중립 검증 — 회귀 테스트)**.
- `src_g1` 독립 분해 → Claim/ClaimFeature 서명 갱신 · SHACL 4종 통과 · pytest green.
- 프로파일·MANIFEST 산출(§4 의무). 수집 건수 ↔ 병합 특허 수 정합(매핑≠병합 축 혼동 금지 —
  memory `paper-corpus-counts-mapped-vs-merged`).

### 비목표
- Phase D(G1 종속항). H1/H2/RQ3 재검정. 룰 매핑 재계산(청구항은 매핑에 안 쓰임 — 초록·명칭만).

---

## §공통. 규율
- **egress(사용자 승인 2026-07-22)** — flag 청구항 전문이 Bedrock Haiku 로 나간다(KIPRIS 비재배포).
  Tier 2 와 동일 규율: temperature 0 + sqlite 캐시(키에 모델 문자열 포함 → 백엔드 교차오염 없음·결정적).
  ollama 로컬 경로 보존(`LLM_BACKEND`).
- **G₀ 동결 폐기 하 진행** — 그래프가 바뀌어도 H1/H2/RQ3 재실행은 **재구축 가설 재정의** 이후.
  이 PLAN 은 축 구축까지. (memory `g0-frozen-abandoned-full-rebuild`)
- **매달린 IRI 재발 차단** — dependsOnClaim 실재-부모 가드는 SHACL range 추론이 잡는 결함이므로 반드시 유지.
- **정직 계상** — 0요소 청구항은 노드 만들지 않음. cited_map/부모 미해결분은 지어내지 않고 그대로 보고.

## 진입점 (새 세션)
- SDKB: `scripts/decompose_corpus.py`(`src_g2` 필터·`src_g1` 신설) · `build_abox_claim_features.py` ·
  `scripts/llm_claim_validate.py`(bedrock) · 서명 `data/reports/central_axis_dataset_signature.json`.
- paper: `src/sdkb_paper/collect/kipris_client.py`·`collect/collect.py`(G1 details 수집) ·
  `src/sdkb_paper/ontology/delta.py`(`samsung-hynix` details 배선) · `data/MANIFEST.md`·`data/profiles/`.
