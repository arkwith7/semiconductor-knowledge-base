# 인력·문제 축 비식별 변조 프로토콜

> **English summary.** How the expert and problem axes of SDKB were built without ever ingesting
> the source documents. The real inputs — career histories of practising semiconductor engineers
> and firms' technical problem statements — contain personal and commercially confidential
> information and cannot be redistributed in any form. So the **`ont:Expert` (110)** and
> **`ont:Problem` (226)** instances are of two kinds: a small set of **de-identified derivatives**
> (5 expert profiles, altered until re-identification is not possible) and a larger set of
> **deterministically generated** instances (105 profiles, seeded, generated to be consistent
> with the process and device vocabulary). **No original source document has ever been copied
> into this repository, into a release snapshot, or into any downstream vendored artifact** —
> only the transformed outputs were kept. Papers citing this axis should cite this protocol, and
> should not describe these instances as human-expert annotation.

SDKB 의 `ont:Expert`(110) · `ont:Problem`(226) 인스턴스는 실 원천을 **그대로 사용할 수 없는**
데이터다. 실 경력기술서·실 기술문제 기술서는 개인정보와 기업 영업정보를 담고 있어 어떤 형태로도
재배포할 수 없다. 그래서 두 축은 **실 데이터를 근거로 식별 불가능하도록 변조한 파생물**과,
그 구조를 따라 **결정적으로 생성한 인스턴스**로 구성된다.

이 문서는 그 절차를 기록한다. 이 축을 인용하는 논문은 여기를 참조한다.

> **원본 미반입 원칙.** 원천 문서(경력기술서 PDF 등)는 이 저장소·릴리스 스냅샷·하류 vendor
> 산출물 어디에도 반입된 적이 없다. 보존된 것은 변조 산출물뿐이다.

---

## 1. Expert 축 (110)

### 1.1 구성

| 층 · Tier | 건수 · Count | 성격 · Nature |
|---|---:|---|
| 변조 파생 프로필 | **5** (EXP_001–005) | 실 반도체 실무자 경력기술서를 근거로 식별 불가능하도록 변조 |
| 결정적 생성 프로필 | **105** (EXP_006–110) | 공정·소자 어휘에 정합하도록 시드 고정 생성 (`scripts/gen_experts.py`) |

### 1.2 변조 대상과 방법 (EXP_001–005)

원천 경력기술서에서 **"1. 기본정보"** 와 **"4. 주요 경력 사항"** 을 대상으로 개인 식별이
불가능하도록 변조했다.

- **이름** — 가명으로 교체. `skos:prefLabel@ko` 에 실리는 값은 전부 가명이다.
- **소속·경력 수치** — 재작성. 데이터셋 값과 변조본 문서의 값이 일치하지 않는 것이 그 증거다
  (예: EXP_001 은 문서상 특허 156·삼성전자, 데이터셋에서는 `patent_count: 45` · SK hynix).
- **연락처·이메일·생년월일** — 변조본에 존재하지 않는다.
- **정합성 보정 필드** — `age` · `years_experience` · `former_employers`
  (`metadata.upgrade_log`, seed `20260131`, 2026-01-30T15:28Z).

수치 필드는 **생성값이며 실인물에 대한 주장이 아니다.** 이 선언은 데이터에도 박혀 있다
(`intellectual_property.notes: "Counts are synthetic; no claim about real individuals."`).

### 1.3 이름 재부여 (2026-07-20)

이름 풀이 좁아 **56개 이름이 110명에 배분**되어 있었다. 인스턴스는 전부 서로 다른
프로필이었고(38개 필드 정규화 해시 기준 **완전 중복 레코드 0건**, IRI 충돌 0건), 겹치는 것은
`skos:prefLabel` 문자열뿐이었다. 그런데 라벨만 프로젝션하는 CQ11 이 텍스트상 동일한 행 11건을
내놓아 **데이터 중복처럼 보였다**.

삭제는 진짜 프로필 54개를 없애므로 채택하지 않았다. 이름이 이미 가명이므로 교체에 제약이 없고,
`scripts/reassign_expert_names.py` 로 재부여했다.

- 충돌 그룹의 **최소 `expert_id` 는 이름 유지**, 나머지 54명에 새 이름 배정
- **성(姓) 보존 + 이름 교체** — EN 자리표시자(`"Kang, [Given Name]"`)가 성만 담고 있어
  성을 보존하면 EN 표기가 그대로 유효하다
- 난수 없이 정렬 순회로 배정 — **결정적**(두 번 실행해 동일 산출 확인)

결과: 고유 이름 **56 → 110**, ABox 트리플 **3,653 불변**, Expert 110 · Problem 226 불변.
변경된 트리플은 `skos:prefLabel` 54건과 `skos:altLabel` 7건(EN 파일이 한글 원본을 담고 있던
레코드)뿐이다. SHACL 통과.

### 1.4 프로비넌스 기록에서 제거한 것 (2026-07-20)

`upgrade_log.resume_matched` 의 `pdf` 필드는 **저장소 밖 비공개 작업 경로**를 담고 있어
누구도 그것으로 재현할 수 없으면서 내부 디렉터리 구조만 배포물에 남겼다.
`scripts/sanitize_expert_provenance.py` 로 경로를 제거하고 `text_sha256` 은 남겼다 —
파생 사실을 고정하는 앵커는 해시이지 파일 위치가 아니다.

### 1.5 상세 경력의 그래프 적재 — 배포 노출 재검토 (2026-07-21)

그간 그래프에는 전문가 노드의 `skos:prefLabel`·`region`·`complianceFlag` 과 온톨로지 링크만
실려 있었다. 이번에 **큐레이션된 상세 경력 필드를 A-Box 로 실체화**한다 —
SubProcess 별칭 승격과 같은 패턴이다(데이터는 정본에 있으나 그래프에만 없던 것). 그래프는 CDLA 로 배포되므로, **A-Box 는 지울 수 있어도 배포된
값은 지울 수 없다** — 이 비대칭 때문에 적재 전에 노출을 다시 못박는다.

**새로 그래프에 실리는 필드(전 110명 · datatype property):**
`age` · `education`(학위·전공·기관·연도 서술) · `currentStatus` · `formerEmployer` ·
`yearsExperience` · `retirementYear` · `patentCount` · `publicationCount` ·
`hasCertification` · `language` · `toeicScore` · `securityClearance` ·
`consultingAvailability` · `specialization` · `profileSummary`(경력 서술문) ·
`majorProject` · `hasNCT` · `preferredProjectType` · `hourlyRateRange` ·
`nationality` · `workHistoryCountry` · `lastActivity`. 추가로 `equipment_models` 를
`ont:EquipmentModel` 노드로, `case_experience` 를 `ont:ExpertCase` 로 실체화한다.

**이 값들은 §1.1–1.2 의 비식별 지위를 그대로 승계한다.** EXP_001–005 의 경력·수치·소속은
전부 **변조/재작성값**이고(데이터셋 값이 원천 문서와 불일치하는 것이 그 증거),
EXP_006–110 은 시드 고정 생성값이다. 그래프에 실린 어떤 경력 수치도 **실인물에 대한 주장이
아니다** — 원천 데이터의 `intellectual_property.notes` 선언이 이 축 전체에 적용된다.
연락처·이메일·생년월일은 원천에도 변조본에도 없어 그래프에도 없다. `age` 는 변조/생성값이다.

> **`hourlyRateRange` 에 관한 한계 표기.** 시급대는 배포 위험 검토가 공개 스냅샷에서
> 제외를 권고했던 **상업 성격의 필드**다. 사용자 결정(2026-07-21)으로 그래프에 싣되,
> 값은 **합성 프로필의 생성값**이며 실 자문 단가·시장 가격을 나타내지 않는다.
> 이 필드를 뺄 필요가 있으면 `hourlyRateRange` 트리플만 필터링해 재직렬화한다(엣지 불변).

**CEO·전화·팩스는 싣지 않는다(소부장 벤더 축).** KSIA 명부의 `대표자`·`전화번호`·`팩스`
는 실 개인/기업 연락정보라 그래프에서 계속 제외한다 — 벤더 노드에는 `companyType`·명칭·
웹사이트만 남는다.

**규모(실측).** 이 적재로 `ontology/sdkb-abox-experts-problems.ttl` 은 **3,653 → 8,483 트리플**
로 커졌다(§1.3 의 3,653 은 이 적재 **이전** 이름 재부여 시점 값이다). 하류 G₀ 기준으로는
**+4,906**(44,221 → 49,210)이며, `ont:ExpertCase` **163** · `ont:EquipmentModel` **29** 노드가
새로 실체화됐다. Expert **110** · Problem **226** 은 불변이다. **특허↔공정 엣지는 한 건도
움직이지 않았다** → 이 그래프를 baseline 으로 쓰는 하류 분석의 결론은 움직이지 않는다.

---

## 2. Problem 축 (226)

### 2.1 구성 (`data_source` 필드 실집계)

| 층 · Tier | 건수 · Count | 원천 · Source |
|---|---:|---|
| 최초 큐레이션 | **61** | 실 기술문제 기술서의 데이터 구조를 근거로 작성 (`PROB_001–050` + `prob_*` 11) |
| 수출통제 트리거 시나리오 | **15** | 목적 설계 (`SC_PROB_*`) |
| 온톨로지 추론 시나리오 | **10** | 목적 설계 (`OT_PROB_*`) |
| 공개 사례 파생 | **18** | WM-811K 결함패턴 8 · 기술블로그 사례 5 · TEMAZ 사고사례 3 · 문헌 2 |
| 구조 파생 생성 | **122** | 위 구조를 따라 생성 (교차오염 82 · 미세노드 20 · 장비신뢰성 20) |
| **계** | **226** | |

앞의 86건(61+15+10)은 `data_source` 필드가 **도입되기 이전**에 만들어져 값이 비어 있다 —
출처 불명이 아니라 필드 도입 시점의 문제다. 확장분 140건은 전부 출처가 표기되어 있다.

### 2.2 변조 방법

실 기술문제 기술서는 기업·공정·수율 수치를 담아 재배포할 수 없다. 보존한 것은 **문제 기술의
데이터 구조**(증상 · 공정영역 · 장비 · 사업영향 · 요구전문성 등 22개 필드)이고, 그 구조를 채우는
값은 공개 자료(공개 특허 문헌 · 결함 데이터셋 · 사고사례 · 기술블로그)를 참조해 **재작성**했다.
개별 문제와 실 기업·실 사건의 대응 관계는 보존되지 않는다.

> **한계 표기.** 최초 큐레이션 61건은 참조한 공개 문헌의 서지정보가 레코드 단위로 보존되지
> 않았다. 문헌 단위 추적이 필요한 연구에는 확장분 18건(출처 표기분)을 쓸 것.

### 2.3 하류 특허 문제층과의 경계 — 공개 파생, 이 프로토콜 밖 (2026-07-22)

하류 분석 저장소가 **특허 초록에서 결함모드를 추출하는 층**을 신설했다(2026-07 · 커밋 `dfdb9dd`). 이름이 "문제"라 위 §2 의 기밀 `ont:Problem`(226) 축과 혼동되기 쉬우나 **원천과
비식별 지위가 전혀 다르다** — 이 경계를 못박는다.

| | 위 §2 `ont:Problem` (226) | 하류 특허 문제층 `ont:FailureMode` |
|---|---|---|
| 원천 | **실 기술문제 기술서**(기밀) → 구조 보존·값 재작성 | **공개 특허 초록**(KIPRIS 공개공보) → LLM 추출 |
| 비식별 필요 | **필요**(이 프로토콜의 대상) | **불필요**(공개 문헌 파생) |
| 산출 위치 | SDKB `sdkb-abox-experts-problems.ttl` | 하류 `graph_v1.ttl`(SDKB 미승격) |

- 추출기(`problems.py`)는 특허의 **제목·초록만** 읽는다 — 기밀 Expert/Problem 원천을 참조하지 않는다.
- `ont:FailureMode` 는 두 갈래다: **기존 25개**는 SDKB 큐레이션 결함모드 어휘로 §1.5 의 `ont:ExpertCase`
  가 `ont:caseFailureMode` 로 참조하는 값이고(전문가 사례 파생 — §1.1–1.2 지위 승계), **신규 30개**
  (어휘 25→55)는 일반 반도체 결함 용어(비트라인 커플링 노이즈·전하 손실·콘택 저항 등)로 공개 특허
  초록에서 자란 것이다. 신규분은 사용자 채택·frozen(하류 `data/failuremode_concepts_new.csv`).
  **어휘 발명 0**(기존 SDKB TBox 술어 `ont:exhibitsFailureMode`).
- 두 축은 CQ28(특허↔문제↔전문가)에서 **연결**되지만, 연결이 곧 혼합은 아니다 — 기밀 축(전문가 역량)과
  공개 축(특허 결함모드)을 잇는 다리일 뿐 기밀 값을 특허 쪽으로 흘리지 않는다.
- **이 층은 이 프로토콜의 비식별 대상이 아니다.** 공개 특허 파생물의 배포 조건은 KIPRIS 소스
  라이선스(학술 이용·원문 비재배포)를 따르며, 그래프에는 집계·개념 링크만 실린다.

---

## 2.4 정본 위치

`data/experts/curated_profiles_kr.json` **이 정본이다.** 같은 내용의 사본이
`kukkukpool/ExpDataSet/expert_profiles_dataset.json` 에 있었고(md5 동일, 415,148 bytes),
그쪽은 AFCP 계열 실험의 입력으로 보존한다. **온톨로지 빌드가 읽는 것은 이 저장소의 파일뿐이며,
이름 재부여(§1.3)와 경로 제거(§1.4)는 이 저장소 쪽에만 적용되어 두 파일은 더 이상 동일하지 않다.**
AFCP 재실험 시에는 이 저장소의 정본을 다시 가져간다.

---

## 3. 이 축의 연구상 위치

인력·문제 축은 **어휘 커버리지와 CQ 배터리의 심문 대상**이며(특히 CQ11·CQ12·CQ20, 그리고
2026-07-22 신설 **CQ28** 특허↔문제↔전문가 다리 — 40행 응답), 하류 분석의 검정에는
**관여하지 않는다.** 그 검정의 관측 단위는 공정과 개념 축(Process ∪ Device)이고,
특허↔공정 엣지는 이 축의 변경에 영향받지 않는다.

따라서 §1.3 이름 재부여·§1.4 경로 제거·§1.5 상세 경력 적재는 **하류 결론을 움직이지 않는다.**
다만 TTL 내용이 바뀌므로 sha256 은 바뀐다 — 이 그래프를 얼려 쓰는 소비자는 재vendor 후
스냅샷을 재동결해야 한다(트리플 수는 불변).

---

## 4. 재현

```bash
python3 scripts/reassign_expert_names.py      # 이름 재부여 (결정적·멱등)
python3 scripts/sanitize_expert_provenance.py # 외부 경로 제거 (멱등)
make abox                                      # ABox 재빌드 — §1.5 상세 경력·ExpertCase·EquipmentModel 포함
make validate                                  # SHACL (expert_shape 포함)
```
