# CR-009 · 개념별 df·일반성 메타의 릴리스 발행 — 3단계 설계

> 정본 CR: `~/Dev/SKKU/sdkb-prior-art-paper/upstream/CR-009-concept-df-release-meta.md`
> 절차: 상류 CLAUDE.md §2 · 1단계(하류 발행) 완료 · **2단계 분석 완료(아래 §1) · 이 문서가 3단계**
> 상태: **승인 대기 🛑** — 승인 전 4단계 착수 금지

---

## 0. 한 줄

`mappings/concept_mapping.json` 에 개념 단위 메타 넷(`df_abox`·`df_denominator`·`depth`·
`is_superordinate`)을 **프로파일별로** 더한다. 스키마 1.0 → 1.1.
T-Box 불변 · A-Box 불변 · 새 술어 0 · **기존 `entries` 값 변경 0**.

---

## 1. 2단계 분석 — 관측된 사실 다섯

문서 모집단 = 상류 A-Box 특허 **4,034건**(SIRP 거절 1,000 + 인용 3,034).

### 1.1 df 를 어디서 세느냐가 곧 설계 결정이다

| 계산 경로 | df>0 개념 (patent-text 274 중) | 문서당 개념 |
|---|---:|---:|
| A-Box 그래프 링크로 세기 | 95 (34.7 %) | 2.163 |
| 사전 표면형을 본문에 적용해 세기 (R1 정규화) | **145 (52.9 %)** | 6.174 |

그래프 링크로 세면 **174 개념이 `df_abox`=0** 이 되고, 그 0 은 희소성이 아니라 **링크 부재**다.
idf 재료로 쓰면 링크 없는 개념에 **최대 특이도**를 주게 되어 정확히 반대로 작동한다.
**df 는 본문 적용으로 센다**(결정 D1).

### 1.2 프로파일별 발행 요구는 실측으로 정당하다

| 개념 | patent-text | expert-tag |
|---|---:|---:|
| `material:oxide` | 1,100 | 0 |
| `material:sio2` | 827 | 1,492 |
| `skill:gas_chemistry` | 20 | 635 |
| `skill:plasma_diagnostics` | 204 | 753 |
| `equipment_class:process_chamber` | 498 | 0 |

주된 원인은 R4-SHORT-KO-TASK 가 patent-text 에서 짧은 한글 태스크 축 표면형을 막는 것이다.
**한 값으로 뭉치지 않는다**는 CR 지시가 옳다.

### 1.3 `is_superordinate` 는 실제로 잡아낸다

CR-007 이 세운 상위어 7개가 patent-text df 상위 21위 안에 **전부** 든다 —
`oxide` 6위 · `dielectric` 11위 · `process_gas` 14위 · `plasma_processing` 15위 ·
`process_chamber` 19위 · `photomask` 21위. 고빈도와 상위어를 함께 줘야 한다는 CR 논거가
실측으로 확인된다.

### 1.4 `depth` 는 거의 신호가 없다 — 그래도 발행한다

`skos:broader` 18트리플 · 상위어 7 · **최대 깊이 1**.
274 개념 중 **16개(5.8 %)만 `depth`=1**, 나머지는 전부 0.

### 1.5 분포와 idf 폭

patent-text: `df`=0 129개 · `df`>0 중앙값 18 · 상위 10개념이 전체 df 합의 **51.8 %** ·
idf 폭 0.73(df 1,941) ~ 8.30(df 1). 가중 여지는 충분하다.

**먼저 알린다 — D-20 이 df 에 그대로 실린다.** `material:hf_acid` 가 df 259 로 나온다.
단독 `Hf`(하프늄)를 불산으로 오지정한 매핑 위에서 센 값이다.

---

## 2. 설계

### 2.1 어디에 넣는가

`scripts/build_concept_mapping.py` **한 파일**만 바꾼다. 새 스크립트를 만들지 않는다 —
사전과 메타가 갈라지면 둘의 동기화가 새 결함이 된다.

```python
def load_abox_docs(root: Path) -> list[str]:
    """A-Box 문서의 정규화 본문. 결정적·정렬 고정.
    RejectedPatent : abstractText + firstClaimText   (1,000)
    CitedPatent    : abstractText + claimText        (3,034)
    → norm() 적용 (= 기존 R1 함수 재사용, 새 규칙 없음)"""

def concept_df(entries: list[dict], docs: list[str]) -> dict[str, int]:
    """개념 IRI → 그 개념의 **어느 표면형이든** 포함하는 문서 수.
    한 문서에서 여러 표면형이 걸려도 1 (문서빈도이지 출현빈도가 아니다)."""

def concept_depth(kg: dict) -> tuple[dict[str, int], dict[str, bool]]:
    """skos:broader 사슬 → (depth, is_superordinate). 루트 = 0.
    사이클은 ValueError — 조용히 자르지 않는다."""
```

### 2.2 산출 스키마 (1.0 → 1.1)

```jsonc
{
  "schema_version": "1.1",
  "profiles": {
    "patent-text": {
      "entries": [ /* 값 변경 0 · 추가 0 · 순서 불변 */ ],
      "blocked": [ /* 불변 */ ],
      "concept_meta": {                      // ← 신설
        "df_denominator": 4034,              // 파일 1회가 아니라 프로파일 1회
        "concepts": {
          "material:sio2": {"df_abox": 827, "depth": 1, "is_superordinate": false},
          "material:oxide": {"df_abox": 1100, "depth": 0, "is_superordinate": true}
        }
      }
    },
    "expert-tag": { }
  }
}
```

- **`concepts` 는 그 프로파일의 개념 전량**(patent-text 274 · expert-tag 261)을 담는다.
  df=0 인 개념도 키를 갖는다 — 빠지면 하류가 "없음"과 "0"을 구별할 수 없다.
- `df_denominator` 를 프로파일 안에 두는 이유: 두 프로파일의 문서 모집단이 지금은 같지만
  (둘 다 4,034), **같다는 보장이 스키마에 없으면 하류가 가정하게 된다.**
- **키 정렬은 사전순 고정**(재실행 바이트 동일).

### 2.3 결정성

- 타임스탬프 없음(CR 뒤집지말것 ⓒ · CR-007 규율 동일)
- `docs` 는 IRI 사전순, `concepts` 는 개념 IRI 사전순
- 두 번 돌려 `sha256` 동일함을 테스트가 단정

### 2.4 `PROVENANCE.json`

`mappings/concept_mapping.json` 의 sha256 갱신 + 새 입력 두 개
(`ontology/sdkb-abox-patents.ttl`·`ontology/sdkb-abox-prior-art.ttl`)를 `artifact_inputs` 에 등재.
**하류의 freshness 증명이 이 두 파일을 덮게 된다** — 즉 A-Box 가 바뀌면 df 가 낡았음이 드러난다.

---

## 3. 승인이 필요한 설계 결정

| | 결정 | 권고 | 이유 |
|---|---|---|---|
| **D1** | df 를 **본문 적용**으로 센다 | **채택** | 그래프 링크는 174/274 를 df=0 으로 만들고, 그 0 이 idf 를 뒤집는다(§1.1) |
| **D2** | 그러면 상류가 R1–R5 적용기를 갖게 된다 — CR-007 분업과 충돌하는가 | **충돌하지 않는다고 본다. 단 명시적으로 좁힌다** | 상류가 만드는 것은 **df 계산 전용 참조 적용기**이고, `_README` 에 *"하류용 적용기가 아니다 — 하류는 자기 토큰화로 구현한다"* 를 못박는다. CR-007 이 분업한 이유(하류마다 토큰화가 다름)는 그대로 유효하며, 성공기준 ②(Spearman ρ)가 바로 이 차이를 검정한다 |
| **D3** | `depth` 를 발행한다 | **발행한다** | 274 중 16개만 비0이라 신호는 얇지만, CR 이 지정한 필드를 상류 판단으로 빼는 것은 범위 축소다. **얇다는 사실을 리포트에 명시**하고 실질화는 CR-002(D-02)로 넘긴다 |
| **D4** | D-20 오지정 개념 표시 | **스키마에 플래그를 만들지 않는다. 산출 리포트에 목록으로 낸다** | 자산에 새 필드를 더하면 CR 범위 밖이고, 침묵하면 결함이 자원 메타로 승격된다. 리포트가 둘 사이의 정직한 자리다 |
| **D5** | 고빈도 개념 삭제 | **하지 않는다**(CR 뒤집지말것 ⓑ) | CR-007 §2단계 G4 에서 삭제 경로 3종이 전부 동점블록 중앙값을 밀어 올려 D-01 기준을 깼다 |

---

## 4. 5단계 검증 계획

**(a) 단위**
- `concept_df` — 한 문서에 같은 개념의 표면형이 2회 나와도 **1**
- `concept_depth` — 루트 0 · 자식 1 · **사이클 입력에 ValueError**
- `norm()` 이 기존 함수와 **같은 객체**인지(사전과 df 가 다른 정규화를 쓰면 어긋난다)

**(b) 통합**
- **기존 `entries` 불변**: 1.0 판과 1.1 판의 `entries`·`blocked` 를 JSON 동등 비교해 **차 0**
- 두 프로파일 개념 전량(274·261)이 `concept_meta.concepts` 에 키를 갖는가
- 두 번 빌드 → **sha256 동일**
- `PROVENANCE.json` 이 새 입력 2개를 덮는가

**(c) 릴리스 게이트**
- `make test`
- 그래프는 바뀌지 않으므로 `make validate` 결과 불변임을 확인(회귀 없음의 증명)
- `CHANGELOG.md` 에 스키마 bump 와 df 요약(개념 수·df>0 수·분모) 기록

**하류가 되돌려줄 것**: 성공기준 ② 의 Spearman ρ(상위 30개념) · df 가중 재측정
(**새 사전등록 아래** · 이 CR 의 승인 조건 아님) · 동점블록 문서가중 중앙값 변화.

---

## 5. 비목표 (재확인)

- 가중식을 정하지 않는다(idf 를 어떻게 쓸지는 하류 점수식)
- 고빈도 개념을 삭제하지 않는다
- 어휘를 늘리지 않는다(CR-001B) · 다국어 라벨을 채우지 않는다(CR-003) ·
  축 재지정을 하지 않는다(D-20 후속 CR)
