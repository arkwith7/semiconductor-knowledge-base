# CR-013 회신 — 원소 기호 별칭의 정밀도 (하류 D-20)

> 상류: `~/Dev/sdkb` · 하류 CR: `sdkb-prior-art-paper/upstream/CR-013-element-symbol-alias-precision.md`
> 회신일 2026-08-07 · 절차: 상류 CLAUDE.md §2 (2단계 분석 → 3단계 설계 승인 → 4단계 구현 → 5단계 검증)
> **모든 수치는 실행된 코드의 출력이다. 산출 불가한 항목은 왜 불가한지를 적었다.**

---

## 0. 한 문장

**요구한 두 줄을 고쳤다 — 단독 `hf` 는 제거하고 `high k` 는 상위 부류 `material:dielectric`
로 재지정했다.** 다만 그 자리는 사전 파일이 아니라 **생성기와 큐레이션 원천**이었고(사전은
빌드 산출물이다), Tier-1 동의어는 프로파일 구분이 없어 **프로파일 단위 억제 규칙(R6)을 새로
만들어야 했다.** A-Box 34 건은 **원문 대소문자로 갈랐다 — 상류에서는 갈린다.**

**그리고 하류가 동결하려는 검증기준 ⑤ 는 이 회신으로 무효가 된다** — §4 를 먼저 읽어 주기
바란다. 사전등록 동결 **전에** 재산출해야 한다.

---

## 1. 검증기준 ①②⑥ 의 실측값

| # | 기준 | 합격선 | **실측** | 판정 |
|---|---|---|---:|---|
| ① | 재발행 사전 `patent-text` entries 에 단독 `hf` 표면형 | 0 건 | **0 건** | **통과** |
| ② | `high k` 가 `material:hfO2` 를 가리킴 | 0 건 | **0 건** | **통과** |
| ⑥ | 교차 태스크 CQ(em·tf·core) 통과율 하락 | 0 | **산출 불가** | §1.1 |

출처: `scripts/build_concept_mapping.py` 재실행 → `mappings/concept_mapping.json` ·
`tests/test_cr013_hf_precision.py` 17 항목 전량 통과.

부수 실측 — `patent-text` 쌍 **653 → 652** · 표면형 **636 → 635** · blocked **6 → 8**.
`expert-tag` 는 **entries·blocked·concept_meta 전량 불변**(비목표 ⓕ · 테스트가 단정).

### 1.1 ⑥ 이 산출 불가한 이유와, 대신 잰 것

**CQ 스위트 `em`·`tf`·`core` 는 상류에 없다.** 상류에 있는 SPARQL 은 `examples/sparql/` 의
예시 3 개뿐이고, 스위트 분할(pa·em·tf·core)은 **하류 자산**(`queries/cq/*.rq`)이다.
상류가 통과율을 세면 그것은 하류의 스위트가 아니라 **상류가 새로 만든 질의**의 통과율이므로,
같은 이름을 붙이면 하류가 다른 것을 같은 것으로 읽는다. 지어내지 않는다.

**대신 상류가 실제로 돌린 것:**

| 검증 | 결과 |
|---|---|
| `validate_shacl.py --data sdkb-core-data.ttl sdkb-abox-experts-problems.ttl` | **PASSED** (data 12,085 · shapes 315) |
| `validate_shacl.py --shapes shapes_patent.ttl --data sdkb-abox-patents.ttl …` | **PASSED** (data 37,967 · shapes 134) |
| `pytest tests/` | **183 passed · 10 skipped** |
| 사전 결정성 (`build_concept_mapping.py --check`) | **동일 바이트** |
| T-Box 불변 | `sdkb-core.ttl`·`sdkb-core-data.ttl` **sha256 불변** |

**⑥ 은 하류가 재 vendor 후 자기 스위트로 재는 것이 정확하다.** 상류 변경이 T-Box 를 건드리지
않았고(클래스·술어 델타 0) 개념 링크만 19 건 줄었으므로, T3 가 하락하면 그것은 어휘가 아니라
**그 19 건에 의존하던 질의**를 뜻한다.

---

## 2. ⓑ 의 최종 형태 — **재지정이다. 상위 부류 개념이 있었다.**

**`material:dielectric`("Dielectric Material")가 이미 있다.** 어휘를 새로 만들지 않았다
(비목표 ⓔ 준수).

```json
{"surface": "high k", "lang": "und", "concept_id": "material:dielectric",
 "concept_type": "Material", "rule_id": "T2-ALIAS-REASSIGN",
 "confidence": 0.8, "ambiguous": false}
```

이 노드를 고른 근거 셋 — ① **CR-007 §3단계 결정 ①이 정확히 이 용도로 만든 노드**다
(*"과대일반 표면형을 상위 개념으로 재지정"* · `절연막` → dielectric 이 이미 같은 방식으로 산다) ·
② `props.lexicon_profile = "patent-text"` 로 **이미 프로파일 한정**이라 `expert-tag` 에 새는
경로가 없다 · ③ KG 에 `material:hfO2 --BROADER--> material:dielectric` 엣지가 이미 있어
**계층상 hfO2 의 상위**다.

**`ambiguous` 는 false 다** — Tier-1 의 hfO2 지정을 R6 로 껐기 때문에 후보가 하나만 남는다.
끄지 않고 별칭만 더했다면 R5 가 두 후보를 모두 실어 하류 Q3 가 오링크를 그대로 받았을 것이다
(CR §3.1 이 지적한 그 실패). **억제가 R5 의 다의 판정 앞에 걸리는 것이 이 설계의 핵심이다.**

---

## 3. ⓒ — A-Box 34 건은 **원문에서 갈렸다**

**갈린다.** 상류 생성기는 정규화 전 원문(`title`·`abstract`·`claim1`)을 갖고 있으므로
`(?<![A-Za-z])(HF|Hf)(?![A-Za-z])` 로 판별할 수 있다. 실측 결과:

| | 원문 `Hf` | 원문 `HF` | 어느쪽도아님 | 계 |
|---|---:|---:|---:|---:|
| 단독 `hf` 로만 붙은 링크 | **19** | **11** | 0 | 30 |
| `불산`·`hydrofluoric acid` 도 있음 | 1 | 1 | 2 | 4 |
| **계** | 20 | 12 | 2 | **34** |

**정리 방식 — 보수적으로 갔다(`scripts/sdkb_nb.resolve_hf_case`).** `HF` 만 있을 때만 불산으로
남기고, `Hf`·혼재·판별불가는 **뗀다**. **하프늄 링크를 새로 만들지 않았다** — 그것은 CR §3.2 가
거부한 재지정을 상류에서 하는 일이고, 오링크의 방향만 뒤집는다.

**결과 (트리플 집합 차로 증명 · 제거 19 · 추가 0):**

| 자산 | 트리플 | `involvesMaterial` | `hf_acid` 링크 |
|---|---|---|---|
| `sdkb-abox-patents.ttl` | 33,937 → **33,931** (−6) | 526 → **520** | 8 → **2** |
| `sdkb-abox-prior-art.ttl` | 66,453 → **66,440** (−13) | 1,580 → **1,567** | 26 → **13** |
| **합계** | −19 | | **34 → 15** |

**하류 사전에는 되돌려 넣지 않았다**(§5 대로). 이 판별자는 A-Box 생성기 안에만 있고 발행
자산의 스키마에는 나타나지 않는다.

> **재빌드 위험은 착수 전에 확인했다.** `sdkb-abox-prior-art.ttl` 은 make 타깃이 없는 수동
> 빌드 산출물이라, 먼저 **무변경 재빌드**를 돌려 baseline sha256 `1abbf5e5…` 가 **바이트 단위로
> 재현**되는 것을 확인한 뒤에 코드를 넣었다. 그래서 위 −13 은 CR-013 이 만든 차이가 전부다.
> 빌드 명령: `--population data/patents/b_layer_cited_population.parquet --extra-enriched
> bigquery_b_layer.parquet bigquery_us_b_layer.parquet`.

---

## 4. ⚠ 검증기준 ⑤ 는 이 회신으로 **무효다** — 동결 전에 재산출하라

하류는 ③④⑤ 를 결과 보기 전에 적었고 그 규율은 옳다. 다만 **⑤ 의 예측은 ⓑ 를 순수 제거로
가정한 값**이다(*"−1,203, 전량 ①②분"*). 상류는 CR §3.4 의 문언대로 **재지정**했으므로:

- **③④ 는 영향 없다** — `hf_acid` 1,522 → 412 · `hfO2` 391 → 298 은 그대로 성립한다.
  `high k` 를 hfO2 에서 떼는 것은 두 안이 같다.
- **⑤ 는 어긋난다** — `high k` 문서(하류 실측 111) 중 **아직 `material:dielectric` 링크가 없는
  문서 수만큼 쌍이 되돌아온다.** 그 수는 하류 코퍼스에서만 셀 수 있다. 상류 A-Box 에서 같은
  비율을 재면 `high k` 14 문서 중 **3 건만** 신규 획득이었다(patents 0 / prior-art 3) —
  **참고값일 뿐 하류 값의 예측이 아니다.**

**하류에 요청한다:** 사전등록 동결(§8 순서 ①) **전에** ⑤ 를 재산출하라. 지금 알리는 이유가
그것이다 — 동결한 뒤에 어긋나면 "상류가 다른 것도 바꿨다"로 읽히지만, **바꾼 것은 CR 이
지시한 그 두 줄뿐**이고 예측이 두 안 중 하나만 가정했을 뿐이다.

순수 제거(⑤ 무손상)를 원하면 되돌리는 것은 별칭 한 줄이다. **다만 그 경우 `high k` 로만 개념을
얻던 문서 93 건이 유전체 신호를 잃는다** — 어느 쪽이 나은지는 하류가 결정할 문제이고, 상류는
CR 문언(*"상위 부류 개념이 있으면 거기에 붙이고"*)을 따랐다.

---

## 5. 재발행 자산의 sha256 (하류가 사전등록에 동결할 값)

| 자산 | sha256 | 비고 |
|---|---|---|
| `mappings/concept_mapping.json` | `cdf5fa5dc1dcc2b41eec61cae2c470b8c866d838eadb20ba38f93d4a4d4698f4` | **변경** (구 `b2da08e7…`) |
| `mappings/abox_term_aliases.json` | `9c8bbeb2067beab4a0f592e54e6103906c2d95a47b6f14f0825d6b954d17030b` | **변경** (큐레이션 원천) |
| `ontology/sdkb-abox-patents.ttl` | `974899fa414f7444f64e578399056b4b1d014b2cfdcfe120685cbb8af458fcf5` | **변경** (구 `3c16ad25…`) |
| `ontology/sdkb-abox-prior-art.ttl` | `e96d987358206f75f2fe2b444753c33dfd4e972ee006d18bea3af9068d5ff76b` | **변경** (구 `1abbf5e5…`) |
| `ontology/sdkb-core-data.ttl` | `f366a764569113608e467797a7422ba5f4503cacd3b6a470671a63b2abbaa3fa` | **불변** |
| `ontology/sdkb-core.ttl` | `256346fcb83bcf286e1cc66d49e131e36d3e0095701d46d1612a3e5694097f1f` | **불변** |

`provenance/PROVENANCE.json` 의 `change_request` = `CR-007, CR-009, CR-013`.

---

## 6. 다른 프로파일·다른 하류 소비자에 미치는 영향

| 소비자 | 영향 | 근거 |
|---|---|---|
| **`expert-tag` 프로파일** | **없음** — entries·blocked·concept_meta 전량 불변 | `test_cr013_hf_precision.py::TestProfileIsolation` |
| **`sdkb-prior-art-paper`** | 스냅샷 서명 변경 → **§2.1 전량 재측정**. 코드 변경 없음(사전 값·A-Box 링크만) · **⑤ 재산출 필요**(§4) | 위 sha256 표 |
| **`sdkb-foresight-paper`** | 얼린 커밋을 vendor 하므로 **자동 영향 없음**. 새로 vendor 하면 개념 링크 19 건 감소 | §0 표 |
| **SDKB-Match (Expert)** | **없음** — expert-tag 경로 불변 | 위와 같음 |
| **SDKB-Match (PriorArt) · 공개 사이트** | 개념 링크 **19 건 감소**(전부 `involvesMaterial → hf_acid`) · 신규 링크 0 | 트리플 집합 차 |
| **`concept_df_report.json`** | `hf_acid` df 272 → **26** · `hfO2` 76 → **57** · `dielectric` 875 → **881** | 재생성 출력 |

> **부수 관측 (이번 범위 밖 · 보고만).** 상류의 df 참조 적용기(`concept_df`)는 **단어경계가
> 없는 부분문자열 포함**이라 `hf` 가 `hfo2` 안에서도 걸렸다. 그래서 구 `hf_acid` df 272 는
> 부풀려진 값이었다(하류 적용기는 단어경계가 있다). **이번에 고치지 않았다** — 한 스냅샷의
> 변인을 늘리면 하류가 원인을 가르지 못한다(CR 비목표 ⓓ 의 논리). 별건으로 다룰지는
> 하류 판단에 맡긴다.

---

## 7. 하지 않은 것 (비목표 준수 확인)

`hf` → hfO2 재지정 **안 함**(ⓐ) · `ambiguous=true` 병기 **안 함**(ⓑ) · 새 스키마 필드
**안 만듦**(ⓒ — 대소문자 판별자는 A-Box 생성기 안에만 있다) · `co`·`w`·`al`·`cu`
**무수정**(ⓓ) · **어휘 신설 0**(ⓔ) · `expert-tag` **무변경**(ⓕ) · **CR-001A 미포함**(ⓖ —
별도 커밋).
