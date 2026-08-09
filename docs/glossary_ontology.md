# 온톨로지 용어집 — 이 저장소에서 실제로 사고를 낸 개념들

> **English summary.** A working glossary of the RDF / OWL / SHACL / SKOS concepts SDKB
> actually depends on. It is not a textbook: each term is followed by a **real defect this
> repository shipped** because the term was misunderstood, and by the rule adopted afterwards.
> If you are building a domain ontology, the five incident boxes are the part worth reading —
> they are the mistakes, not the theory. Companion documents:
> [`ontology_guide.md`](ontology_guide.md) (how SDKB is built and extended) and
> [`glossary_semiconductor.md`](glossary_semiconductor.md) (the domain being modelled).
>
> 이 문서는 교과서가 아니다. **이 저장소에서 실제로 사고를 낸 개념들**을 정리했다. 각 용어에
> **여기서 무엇이 어떻게 깨졌는지**와 **그래서 생긴 규칙**을 붙였다. 짝 문서는
> [`ontology_guide.md`](ontology_guide.md)(어떻게 만들고 확장하는가)와
> [`glossary_semiconductor.md`](glossary_semiconductor.md)(무엇을 표현하는가)다.

---

## 1. 기본 골격 — 트리플, IRI, 그래프

**트리플(triple)** — 지식의 최소 단위. `(주어, 술어, 목적어)`.

```turtle
data:patent/kr_1020210184131   ont:filingDate   "2021-12-21"^^xsd:date .
#          주어(IRI)              술어(IRI)          목적어(리터럴)
```

**IRI (Internationalized Resource Identifier)** — 사물의 **전역 고유 이름**. URI 를 확장해
ASCII 를 넘어 유니코드까지 식별자에 쓸 수 있게 한 것(RFC 3987). URL 처럼 생겼지만 **웹 주소일
필요는 없다** — 가리키는 것은 실체(공정·특허·회사)이지 문서가 아니다. **같은 실체는 같은 IRI 여야
하고, 다른 IRI 는 다른 실체다.** 이 등식이 깨지면 질의가 **에러 없이** 어긋난다(아래 사고 0).

**리터럴(literal)** — 값 그 자체(문자열·날짜·수). IRI 가 아니다. **리터럴은 다른 트리플의 주어가
될 수 없다.**

**네임스페이스 / 접두어(prefix)** — 긴 IRI 의 별칭. SDKB 의 분리(`config/namespaces.py`):

| 접두어 | IRI | 무엇이 사는가 |
|---|---|---|
| `ont:` | `https://w3id.org/sdkb/ont/` | **TBox** — 클래스·술어(어휘) |
| `data:` | `https://w3id.org/sdkb/data/` | **ABox** — 인스턴스 |
| `gov:` | `https://w3id.org/sdkb/gov/` | 거버넌스 모듈 |
| `sdkb:` | `https://w3id.org/sdkb/` | 온톨로지 자체 |

**그래프(graph)** — 트리플의 집합. Turtle(`.ttl`)은 그것을 사람이 읽을 수 있게 적는 **직렬화
형식**이고, RDF/XML·N-Triples·JSON-LD 는 같은 그래프의 다른 표기다. 형식이 다르다고 다른
그래프가 아니다 — 그러나 **도구는 형식을 가린다**(사고 3).

### ⚠ 사고 0 — 역할을 IRI 에 인코딩해 회사 하나가 11쌍으로 갈라졌다

같은 회사를 **역할별로 다른 접두사**에 넣고 있었다 — 장비 공급사면 `vendor:…`, 특허 출원인이면
`org:…`. 그러나 **회사는 하나의 실체**다. 역할은 `rdf:type` 이 말해야지 IRI 이름이 말하면 안 된다.

결과: 같은 회사가 **두 노드**로 갈라졌고(전체 11쌍), *"이 공정의 장비를 공급하는 회사는 누구이고
그 회사의 특허는 무엇인가"*(CQ13)는 두 IRI 를 조인하지 못해 **에러 없이 0행**을 냈다. 다른 IRI =
다른 실체이므로 그래프는 아무 모순도 없이 *"그런 회사 없음"* 이라고 답한 것이다 — 가장 잡기 어려운
종류의 결함이다.

해결: 회사 노드를 `data:organization/` **한 스킴**에만 두고 역할은 타입으로 표현했다
(`mappings/org_identity_crosswalk.csv` 가 병합 근거). **IRI 만 합쳐서는 부족했다** —
`skos:prefLabel` 도 회사당·언어당 하나여야 질의가 회사를 다시 쪼개지 않는다(§4).

> **규칙: 회사 하나 = IRI 하나. 역할은 IRI 접두사가 아니라 `rdf:type` 이 말한다.**

---

## 2. TBox vs ABox — 가장 비싼 구분

| | **TBox** (Terminological Box) | **ABox** (Assertional Box) |
|---|---|---|
| 담는 것 | **어휘·스키마.** 어떤 클래스가 있고 어떤 술어가 허용되는가 | **사실·인스턴스.** 개별 공정·특허·기업 |
| 예 | `ont:Patent a owl:Class`<br>`ont:filingDate a owl:DatatypeProperty ; rdfs:range xsd:date` | `data:patent/kr_… a ont:Patent ;`<br>`  ont:filingDate "2021-12-21"^^xsd:date` |
| SDKB 파일 | `sdkb-core.ttl` · `sdkb-patent.ttl` · `sdkb-rbv.ttl` … (7개 모듈 1,534 트리플) | `sdkb-core-data.ttl` · `sdkb-abox-*.ttl` |
| 비유 | 데이터베이스의 **스키마** | 데이터베이스의 **행(row)** |

**클래스(Class)** — 개체의 종류. `ont:Process`, `ont:Patent`, `ont:Device`.
**인스턴스(individual)** — 클래스에 속하는 구체적 사물. `data:process/lithography`.
**타입 선언** — `rdf:type`(Turtle 에서 `a`). `data:… a ont:Patent` = *"이것은 Patent 의 인스턴스다"*.

이 저장소에서 TBox 는 **손으로 쓰고**, ABox 는 **언제나 생성한다.** 생성된 TTL 을 손으로 고치면
다음 빌드에 조용히 사라지고, 그 사이에 그 파일을 가져간 소비자는 유령 데이터를 갖는다.

### ⚠ 사고 1 — ABox 가 어휘를 발명했다

특허 ABox 가 `ont:concernsProcess` 라는 술어를 **ABox 파일 안에서 인라인 선언**해 쓰고 있었다.
TBox(`sdkb-patent.ttl`)에는 그 술어가 **없었다.** 정작 TBox 는 같은 뜻의 `ont:realizesProcess` 를
정의해 두고 있었다.

결과: TBox 만 읽는 소비자에게 `concernsProcess` 는 **존재하지 않는 술어**였고, SHACL 도 추론기도
검증할 수 없었다. **1,558개 링크**가 그렇게 검증 밖에 떠 있었다.

> **규칙: 선언은 TBox 에서만 한다. ABox 는 사실만 적는다.**
> 테스트로 고정한다 — *ABox 의 모든 술어가 TBox 에 정의되어 있는가*(인라인 선언 탐지).

---

## 3. 술어(Property)의 두 종류 — 틀리면 range 위반이 난다

| | **ObjectProperty** | **DatatypeProperty** |
|---|---|---|
| 목적어 | **IRI** (다른 개체) | **리터럴** (값) |
| 예 | `ont:realizesProcess` → `ont:Process` | `ont:filingDate` → `xsd:date` |

**domain / range** — 술어의 정의역·치역. `ont:realizesProcess` 는 `rdfs:domain ont:Patent`,
`rdfs:range ont:Process` 다. 즉 **특허가 아닌 것에 붙이거나 공정이 아닌 것을 가리키면 위반**이다.

SDKB 전체에서 ObjectProperty **93** · DatatypeProperty **85** 이고, 모듈별 목록과 주석 보유율은
[`ontology_guide.md`](ontology_guide.md) §2 에 있다. 주석이 없는 술어는 **이름뿐**이므로,
쓰기 전에 `rdfs:domain`/`rdfs:range` 를 직접 확인한다.

### ⚠ 사고 2 — 리터럴 vs IRI

ABox 가 IPC 분류코드를 `ont:primaryIpc "H01L 21/3065"` 처럼 **리터럴**로 적고 있었다. TBox 의
`ont:hasIPC` 는 **range 가 `ont:IPCSymbol`(IRI)** 인 ObjectProperty 다. 두 세계가 따로 놀았다.

해결: IPC 를 `data:ipc/H01L21-3065` 라는 **인스턴스 노드**로 승격하고 `skos:notation` 으로 코드
문자열을 달았다. 코드를 노드로 올리면 코드끼리의 계층(`broaderClassification`)도 표현된다 —
리터럴로는 불가능하다.

> **규칙: "다른 것과 이어질 수 있는 값"은 리터럴이 아니라 노드다.**

---

## 4. 레이블 — `rdfs:label` 이 아니라 `skos:prefLabel`

SDKB 는 인스턴스 레이블에 SKOS 어휘를 쓴다. **여기서 `rdfs:label` 을 쓰면 질의가 조용히 0행을
반환한다.**

| 술어 | 뜻 | 예 |
|---|---|---|
| `skos:prefLabel` | **대표 명칭** (인스턴스) | `"Plasma Etch"@en` |
| `skos:altLabel` | 이명·번역 | `"플라즈마 식각"@ko` |
| `skos:notation` | 코드값 | `"H01L 21/3065"` |
| `rdfs:label` | TBox 용어의 이름 | `ont:Process` 의 `"Process"@en` |

`"…"@en` 의 `@en` 은 **언어 태그**다. **언어 태그가 다르면 다른 리터럴이다** — `"Etch"` 와
`"Etch"@en` 은 같지 않고, `FILTER(?l = "Etch")` 는 후자를 잡지 못한다.

**대표 레이블은 개체당·언어당 하나여야 한다.** 둘이면 질의가 같은 개체를 두 행으로 돌려주고,
집계에서 조용히 두 배가 된다(사고 0 의 후반부가 정확히 이것이었다).

---

## 5. 계층과 추론 — `SubProcess ⊑ Process`

**`rdfs:subClassOf`** — 클래스 포함 관계. SDKB 에는 `ont:SubProcess rdfs:subClassOf ont:Process`
가 있다.

**RDFS 추론(inference)** — 명시되지 않은 사실을 규칙으로 도출하는 것. 위 공리가 있으면
`data:… a ont:SubProcess` 로부터 **`data:… a ont:Process`** 가 자동으로 따라온다.

이것이 중요한 이유: `ont:realizesProcess` 의 range 는 `ont:Process` 인데, 특허가 **SubProcess** 를
가리켜도 위반이 아니다 — 추론 하에서 SubProcess 는 Process 이기 때문이다. SHACL 검증은 RDFS
추론을 켜고 돈다.

> ⚠ **그러나 SPARQL 은 추론하지 않는다.** 역량질문 실행기는 추론 없이 질의하므로, 질의는 두 층위를
> **명시적으로 열어야** 한다:
> ```sparql
> VALUES (?stepType ?level) { (ont:Process "process") (ont:SubProcess "subprocess") }
> ```
> `queries/cq/CQ01_patents_per_process_step.rq` 가 이 패턴의 실물이다. **추론을 가정하고 쓴 질의는
> 데이터가 멀쩡해도 0행을 낸다.**

**`skos:broader`** — 클래스가 아니라 **개념 사이**의 계층(좁은 개념 → 넓은 개념). SDKB 는 이것을
과도하게 일반적인 표면형이 엉뚱한 축에 붙는 것을 막으려고 도입했고, **도메인·레인지를 일부러
제약하지 않았다** — SKOS 는 외부 어휘이고, SDKB 가 다른 소비자를 위해 그것을 좁혀서는 안 되기
때문이다.

---

## 6. 검증의 세 층 — 각각 **다른 것**을 본다

이 셋을 뭉뚱그리는 것이 가장 흔한 오해다. **하나가 통과해도 다른 하나는 실패할 수 있다.**

| | **SHACL** | **추론기 (HermiT 등)** | **SPARQL / 역량질문** |
|---|---|---|---|
| 묻는 것 | "**필수 속성이 있는가**" | "**논리적으로 모순이 없는가**" | "**태스크 질문에 답할 수 있는가**" |
| 세계 가정 | **닫힌 세계** — 없으면 위반 | **열린 세계** — 없으면 그냥 모를 뿐 | — |
| 예 | 출원일이 없다 → **위반** | 출원일이 없다 → 문제 없음 | 시계열 질의가 0행 |
| 통과의 뜻 | 구조가 갖춰졌다 | 모순이 없다 | 질문에 답이 나온다 |

**SHACL(Shapes Constraint Language)** — 데이터가 지켜야 할 **모양(shape)** 을 선언하는 언어.

- `sh:NodeShape` — 하나의 제약 묶음
- `sh:targetClass ont:Process` — 이 shape 를 **어떤 노드에 적용할지**
- `sh:minCount 1` / `sh:maxCount 1` — 개수 제약
- `sh:datatype xsd:date` — 리터럴의 타입
- `sh:class ont:Process` — 목적어가 그 클래스여야 함
- `sh:or ( … )` — 둘 중 하나면 통과

**열린 세계 가정(OWA, Open World Assumption)** — OWL/추론기의 전제. *"적혀 있지 않다"* 는
*"거짓"* 이 아니라 **"모른다"** 이다. 그래서 **필수 속성 검사는 추론기가 아니라 SHACL 의 일**이다.
이 하나를 모르면 *"리즈너를 돌렸는데 왜 빠진 값을 안 잡지?"* 에서 며칠을 잃는다.

### ⚠ 사고 3 — 리즈너가 처음부터 죽어 있었다

추론 게이트는 **한 번도 동작한 적이 없었다.** 세 가지가 겹쳐 있었다.

1. **owlready2 는 Turtle 을 파싱하지 못한다** (RDF/XML·N-Triples 만 읽는다).
2. **HermiT 는 `xsd:date` 를 지원하지 않는다.** OWL 2 datatype map 에 `xsd:dateTime` 은 있지만
   `xsd:date` 는 **없다** → `UnsupportedDatatypeException`.
3. **`owl:imports`** 때문에 리즈너가 import IRI 를 HTTP 로 가져오려다 404 로 죽었다.

해결: **추론 전용 뷰**(RDF/XML 변환 · `owl:imports` 제거 · `xsd:date`→`xsd:dateTime` 승격)를 만들어
넘긴다. **원본의 `xsd:date` 는 손대지 않는다** — 시계열 분석의 전제이고 SHACL 이 그것을 검사한다.

> **규칙: 쓰여만 있고 돌지 않는 게이트는 게이트가 아니라 장식이다.**
> 그리고 그 반대도 확인한다 — **실패해야 할 입력이 실제로 실패하는가.**

### ⚠ 사고 4 — SHACL 이 겨냥한 그래프에 걸린 적이 없었다

`validation/shapes_patent.ttl` 은 존재했지만 `make validate` 의 기본 대상이 코어 데이터 그래프여서
**특허 ABox 에는 한 번도 적용되지 않았다.** 적용해 보니 `dcterms:license`·`dcterms:source`·
`prov:wasGeneratedBy` 각 1,000건, **총 3,000건 위반**이 나왔다.

> **규칙: shape 는 그것이 겨냥하는 실제 그래프와 명시적으로 짝지어 실행한다.**

---

## 7. 역량질문(CQ)과 SPARQL

**역량질문(Competency Question)** — *"이 온톨로지가 답할 수 있어야 하는 질문"*
(Grüninger & Fox, 1995). 온톨로지 평가의 **기능적(task-based)** 축이며, 구조 검증(SHACL)이나
논리 검증(추론기)이 대신할 수 없는 것을 본다.

SDKB 는 `queries/cq/*.rq` 에 **31개**를 SPARQL 로 정식화했고, 각 질의가 스위트·기대치를 자기
헤더에 들고 있다(`# suite:` `# monotone:` `# expect-min:` `# target:`). 스위트는 넷 —
`core` 12 · `pa` 선행기술 8 · `em` 전문가매칭 6 · `tf` 기술예측 5. 실행은 `make cq`.

> **CQ 를 "지금 그래프가 실패하도록" 만들면 안 된다.** CQ 는 **태스크 요구**에서 도출한다.
> 현 그래프가 전부 답한다면 그것은 **발견**이지 설계 실패가 아니다. 반대로 채우려고 CQ 를
> 지어내면 그 순간 평가가 아니라 분량이 된다.

**스위트가 넷인 이유**가 이 설계의 핵심이다. 하나의 T-Box 를 여러 태스크가 공유할 때,
**한 태스크의 지표만으로 변경을 승인하면 다른 태스크가 조용히 망가진다.** 특허 술어를 하나
바꿨는데 전문가매칭 스위트가 깨지는지를 여기서 알게 된다.

---

## 8. 출처와 해석 — 이 그래프가 스스로에 대해 말하는 것

| 술어 | 뜻 |
|---|---|
| `dcterms:source` / `dcterms:bibliographicCitation` | 어느 원천의 무엇에서 왔는가 |
| `dcterms:license` | **원천별** 라이선스. 저장소 전체 라이선스가 아니다 |
| `ont:interpretationType` | `verbatim`(그대로) · `mapped`(옮김) · `author-defined`(큐레이터가 주장) |
| `ont:validationRequired` | 전문가 검증이 필요하다는 표시 |
| `prov:wasGeneratedBy` / `wasDerivedFrom` / `wasAttributedTo` | PROV-O — 어느 활동이 만들었나 |

**`interpretationType` 이 이 저장소의 정직성 장치다.** 문헌·표준·벤더 자료로 만든 도메인 그래프에는
큐레이터의 주장이 **반드시** 섞인다. 문제는 섞이는 것이 아니라 **소비자가 구분할 수 없는 것**이다.
SHACL 이 이 필드 없는 큐레이션 노드를 거부한다.

---

## 9. 자주 혼동되는 것 (사고 기록 요약)

| 혼동 | 사실 | 대가 |
|---|---|---|
| IRI 접두사가 역할을 말한다(`vendor:`·`org:`) | **아니다.** 역할은 `rdf:type`, 회사 하나 = IRI 하나 | 회사가 11쌍으로 갈라져 CQ13 이 0행 |
| ABox 에서 술어 선언 = 어휘 정의 | **아니다.** TBox 가 정의해야 검증 가능 | 1,558 링크가 검증 밖에 |
| 코드값은 문자열이면 된다 | **아니다.** 다른 것과 이어질 값은 노드다 | 분류 계층을 표현할 수 없었음 |
| 레이블은 `rdfs:label` | 인스턴스는 **`skos:prefLabel`** | 질의가 조용히 0행 |
| SPARQL 이 계층을 알아서 편다 | **아니다.** 추론 없이 돈다 | 데이터가 멀쩡해도 0행 |
| `xsd:date` 는 어디서나 통한다 | **HermiT 는 못 다룬다**(OWL 2 map 밖) | 추론 게이트가 죽어 있었음 |
| SHACL 통과 = 논리적으로 옳음 | **다른 검사다**(닫힌 세계 vs 열린 세계) | 세 층이 필요한 이유 |
| shape 를 썼다 = 검증했다 | **아니다.** 겨냥한 그래프에 걸어야 한다 | 3,000건 위반이 숨어 있었음 |
| 컬럼 이름이 곧 의미 | **아니다.** `filing_date` 에 **공개일**이 들어 있었다 | 시계열이 1~2년 밀릴 뻔 |
| 생성된 TTL 을 고치면 된다 | **아니다.** 다음 빌드에 사라진다 | 가져간 소비자가 유령 데이터를 가짐 |

---

## 10. 약어

**TBox** Terminological Box · **ABox** Assertional Box · **IRI** Internationalized Resource
Identifier · **RDF** Resource Description Framework · **RDFS** RDF Schema · **OWL** Web Ontology
Language · **SHACL** Shapes Constraint Language · **SKOS** Simple Knowledge Organization System ·
**SPARQL** SPARQL Protocol and RDF Query Language · **PROV-O** Provenance Ontology ·
**CQ** Competency Question · **OWA** Open World Assumption ·
**IPC / CPC** International / Cooperative Patent Classification
