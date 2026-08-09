# 반도체 도메인 용어집 — 이 온톨로지가 무엇을 표현하는가

> **English summary.** A domain primer for readers who are not semiconductor engineers,
> scoped to exactly what SDKB models: unit processes, device architectures, the patent
> lifecycle, classification codes, industry structure, and export-control regimes. Each
> section says which SDKB class or predicate carries the concept, and where the ontology
> deliberately stops. Companion documents: [`glossary_ontology.md`](glossary_ontology.md)
> (how knowledge is represented) and [`ontology_guide.md`](ontology_guide.md) (how to extend it).
>
> 이 문서는 반도체 교과서가 아니다. **SDKB 가 실제로 표현하는 만큼의 반도체 지식**만 담는다 —
> 비(非)전공자가 그래프를 읽고 질의를 쓸 수 있을 정도로. 각 절은 그 개념을 **SDKB 의 어느
> 클래스·술어가 담는지**와 **어디서 의도적으로 멈추는지**를 함께 적는다.

---

## 0. 이 온톨로지가 덮는 범위 — 먼저 경계부터

반도체 도메인 전체를 덮는 백과사전이 아니다. **어느 층을 강하게 다루고, 어느 층을 의도적으로
비워 두는가**를 먼저 밝힌다. 확장을 검토한다면 이 표가 출발점이다.

| 도메인 층위 | SDKB 커버리지 | 담는 클래스 |
|---|---|---|
| **제조 공정 (Front-End / Back-End)** | 강함 — 중심 범위 | `Process` · `SubProcess` |
| **소자 / 디바이스 아키텍처** | 강함 | `Device` · `TechnologyNode` · `Semiconductor` |
| **소재·부품·장비 (소부장)** | 강함 | `Material` · `Equipment` · `EquipmentClass` · `Vendor` |
| **특허 · 선행기술 · IP-R&D** | 강함 | `Patent` · `Claim` · `ClaimFeature` · `IPCSymbol` · `RejectionReason` |
| **불량 · 원인 · 대책 (FMEA)** | 중간 이상 | `FailureMode` · `RootCause` · `Mitigation` |
| **규제 · 수출통제 · 국가핵심기술** | 중간 | `RegulatedItem` · `NationalCoreTechnology` |
| **전문가 · 문제 · 현장 사례** | 중간 (합성 데이터) | `Expert` · `Problem` · `Skill` · `ExpertCase` |
| **팹리스 설계 · EDA · 회로** | **범위 밖 — 의도적** | 없음 |

> **"범위 밖"을 결함으로 읽지 않는다.** 설계 축(EDA·회로)을 제조 축과 같은 계층에 억지로 넣으면
> 두 축의 질의가 서로를 오염시킨다. 확장한다면 **같은 계층에 합치지 말고 별도 하위 체계로** 두는
> 것이 이 문서의 권고다.

> **이 도메인을 관통하는 단 하나의 구분부터.** 반도체 지식에는 두 축이 있다 —
> **공정(만드는 과정)** 과 **소자(만들어지는 것)**. 이 둘을 섞으면 그래프의 절반이 잘못 연결된다.
> §2 가 앞의 축이고 §3 이 뒤의 축이며, SDKB 는 이를 **다른 술어**로 잇는다
> (`realizesProcess` vs `concernsDevice`).

---

## 1. 반도체란 무엇을 만드는 일인가 — 30초 요약

**반도체 칩**은 모래(실리콘)에서 출발해 **웨이퍼(wafer)** 라는 원형 판 위에 수백 층의 미세 구조를
쌓아 만든 전자 부품이다. 머리카락 굵기의 1만분의 1 수준(나노미터, nm)의 패턴을 **한 층씩** 그리고
깎고 채우기를 수백 번 반복한다 — 이 "한 번의 반복"이 **단위 공정(unit process)** 이고, 그 사슬
전체가 **공정 흐름(process flow)** 이다.

| 국면 | 하는 일 | SDKB 에서 | 주된 주체 |
|---|---|---|---|
| **전(前)공정 (Front-End / Fab)** | 웨이퍼 위에 회로를 만든다(노광·식각·증착·이온주입…) | `Process` 대분류의 다수 | 종합반도체·파운드리 |
| **후(後)공정 (Back-End / 조립·검사)** | 웨이퍼를 잘라 칩으로 만들고 포장·검사한다 | Packaging · Dicing · Wafer Testing | OSAT·패키징 업체 |

**두 국면을 모두 표현할 수 있느냐가 도메인 온톨로지의 첫 시험이다.** 공개 원천에서 만든 초기
어휘는 전공정에 편중되고 후공정 어휘가 통째로 빠지기 쉽다 — 논문·데이터셋이 전공정 중심이기
때문이다. SDKB 도 그랬고, SemiKong 원천에서 후공정·기판준비를 복원해 공정 단계를 넓혔다.

---

## 2. 단위 공정 — `Process` / `SubProcess`

칩을 만드는 개별 공정 단계다.

| 공정 | 한 일 | 쉬운 비유 |
|---|---|---|
| **산화 (Oxidation)** | 실리콘 표면에 절연막(SiO₂)을 기른다 | 쇠에 녹을 일부러 입히기 |
| **포토리소그래피 (Lithography)** | 빛으로 회로 패턴을 감광막에 새긴다 | 사진 인화 — 마스크를 빛으로 전사 |
| ├ **EUV 리소그래피** | 극자외선(13.5 nm)으로 초미세 패턴 | 더 가는 붓 |
| ├ **DUV 리소그래피** | 심자외선(193 nm)으로 패턴 | 굵은 붓 |
| ├ **감광·현상 (Coat / Develop)** | 감광막을 바르고 씻어 현상 | 필름에 감광제 바르고 현상 |
| **식각 (Etch)** | 패턴대로 막을 깎아낸다 | 조각칼로 깎기 |
| ├ **플라즈마 식각 (Plasma Etch)** | 이온화 가스로 정밀하게 깎기 | 모래분사 대신 이온 빔 |
| **증착 (Deposition)** | 새 막을 표면에 입힌다 | 페인트 칠 |
| ├ **CVD / PVD / ALD** | 화학·물리·원자층 단위 증착법 | 스프레이 / 도금 / 원자 한 겹씩 |
| **이온 주입 (Ion Implantation)** | 불순물 이온을 박아 전기 성질 부여 | 총으로 콕콕 박기 |
| **확산·어닐 (Diffusion / Anneal)** | 열로 불순물을 퍼뜨리고 결함 치유 | 오븐에 굽기 |
| **평탄화 (CMP)** | 울퉁불퉁한 표면을 갈아 평평하게 | 사포로 갈기 |
| **세정 (Clean)** | 오염·잔류물 제거 | 설거지 |
| **계측·검사 (Metrology / Inspection)** | 잘 됐는지 재고 결함 찾기 | 품질 검사 |
| **금속화 (Metallization)** | 층 사이를 금속 배선으로 잇기(BEOL) | 건물 배선 공사 |
| **패키징 (Packaging)** | 칩을 보호·연결하도록 포장 | 상품 포장 |
| **다이싱 (Dicing)** | 웨이퍼를 칩 단위로 자르기 | 판을 조각내기 |
| **웨이퍼 테스트 (Wafer Testing)** | 자르기 전 전기적 양·불량 판정 | 출고 전 검수 |

**두 층위로 나뉜다 — `Process`(대분류) vs `SubProcess`(세분류).** 예: `Deposition` 아래
`CVD`·`PVD`·`ALD`. 계층은 `ont:hasSubStep` 이, 순서는 `ont:hasNextStep` 이 잇는다.
원천은 SemiKong 온톨로지의 L1–L3 분류다.

> ⚠ **두 층위를 합산하지 않는다.** 합산하면 같은 특허가 대분류와 세분류에 **이중 계상**된다.
> 세는 단위를 먼저 정하고 질의를 쓴다.

**분류체계의 해상도 한계 — 공백을 결함으로 읽지 않는다.** 특허 분류코드(IPC/CPC)는 공정을
온톨로지만큼 잘게 나누지 않는다. *"평탄화(CMP)"* 코드는 있어도 *"금속 CMP / 산화막 CMP"* 를
가르는 코드는 없다. 그래서 상위 단계는 특허가 붙지만 그 세분은 0건으로 남는다 — **데이터가
없어서가 아니라 분류체계가 거기까지 못 미쳐서**다. 이 빈칸을 채우려 억지로 매핑하면 그것은
보강이 아니라 날조다.

---

## 3. 소자(디바이스) — `Device` / `TechnologyNode`

**소자(device)** 는 공정으로 *만들어지는 결과물*의 구조·아키텍처다.

| 소자 | 무엇인가 | 왜 중요한가 |
|---|---|---|
| **HBM (고대역폭 메모리)** | DRAM 여러 장을 수직으로 쌓고 TSV 로 연결한 메모리 | AI 가속기의 메모리 병목을 뚫음 |
| **TSV (실리콘 관통 전극)** | 칩을 위아래로 관통해 수직 연결하는 배선 | 3D 적층을 가능케 함 |
| **3D NAND** | 저장 셀을 수직으로 쌓은 낸드 플래시 | 평면 미세화 한계를 높이로 돌파 |
| **FinFET** | 채널이 지느러미(fin)처럼 선 3D 트랜지스터 | 평면 트랜지스터의 누설전류 한계 극복 |
| **GAA / MBCFET / 나노시트** | 채널을 게이트가 사방에서 감싼 차세대 트랜지스터 | FinFET 다음 세대 |
| **MRAM (자기저항 메모리)** | 자성으로 정보를 저장하는 비휘발성 메모리 | 차세대 메모리 후보 |
| **FOWLP (팬아웃 패키징)** | 웨이퍼 단위 첨단 패키징 기법 | 후공정 고도화 |
| **DRAM / NAND Flash** | 휘발성 주기억 / 비휘발성 저장 메모리 | 주력 제품군 |

**공정 vs 소자 — 절대 섞지 말 것.** *"식각(Etch)"* 은 **하는 일**(공정), *"FinFET"* 은
**만들어지는 것**(소자)이다. SDKB 에서 특허→공정은 `ont:realizesProcess`, 특허→소자는
`ont:concernsDevice` 로 **다른 술어**다.

> **특허는 기술을 이름으로 부르지 않는다.** 새 기술의 초기 특허는 그것을 상용 명칭으로 부르지
> 않고 **구조로** 서술한다(예: *"적층 메모리 ∧ 관통 전극"*). 그래서 **명칭 검색은 늦고 구조 검색이
> 이르다** — 온톨로지가 키워드보다 앞설 수 있는 근거이자, 소자 축을 별도로 두는 이유다.

**기술 노드(technology node, "3 nm·5 nm").** 세대를 나타내는 이름표다. 과거엔 실제 최소 선폭이었으나
지금은 성능·집적도를 아우르는 **마케팅·세대 명칭**에 가깝다 — *3 nm 라고 3 나노 구조물이 있는 게
아니다.*

---

## 4. 불량과 대책 — FMEA 사슬

| 클래스 | 뜻 | 잇는 술어 |
|---|---|---|
| `FailureMode` | 관측되는 불량 양상 (예: 식각 프로파일 기울어짐) | `ont:occursAtProcessStep` → 공정 |
| `RootCause` | 그 불량의 근본 원인 | `ont:isDueTo` |
| `Mitigation` | 원인을 없애거나 줄이는 조치 | `ont:mitigatedBy` · `ont:mitigationProvidesSkill` |

**FMEA(Failure Mode and Effects Analysis)** 는 제조업 전반의 표준 기법이고, 이 세 클래스 사슬은
**반도체에 특화된 것이 아니다** — 배터리·디스플레이·화학공정으로 그대로 옮겨간다
([`ontology_guide.md`](ontology_guide.md) §5 레시피 C).

> ⚠ **SDKB 의 FMEA 인과 링크는 문헌에서 유도한 것이고 현장 검증을 거치지 않았다.**
> `ont:validationRequired` 와 `ont:confidence` 가 그 상태를 표시한다. 안전·품질 판단에 그대로
> 쓰지 않는다.

---

## 5. 특허의 생애 — 날짜를 틀리면 전부 틀린다

```
발명 → [출원] → (18개월 뒤) [공개] → 심사 → [등록] 또는 [거절]
        ↑출원일                ↑공개일           ↑선행기술로 거절
```

| 용어 | 뜻 | 왜 중요한가 |
|---|---|---|
| **출원 (application)** | 특허청에 발명을 접수 | **출원번호**가 중복 제거의 키 |
| **출원일 (filing date)** | 접수한 날 = 우선권 날짜 | **시계열 분석의 시간축.** 발명 시점의 가장 이른 공적 기록 |
| **공개 (publication)** | 출원 **18개월 후** 내용이 공개됨 | 최근 1~2년 건수가 덜 드러나는 **우측 절단**의 원인. *"감소"가 아니라 "아직 미공개"* |
| **공개일 (publication date)** | 공개된 날 (≠ 출원일!) | ⚠ 아래 경고 참조 |
| **등록 (registration / grant)** | 심사를 통과해 권리 확정 | `GrantedPatent` |
| **거절 (rejection)** | 심사관이 등록을 거부 | `RejectedPatent` · `RejectionReason` |
| **선행기술 (prior art)** | 발명보다 앞선 기존 기술·문헌 | 거절의 근거 |
| **심사관 인용 (examiner citation)** | 심사관이 거절 근거로 든 선행문헌 | **가장 권위 있는 정답 데이터**(합성이 아님) — `ont:hasPriorArtExaminer` |
| **청구항 (claims)** | 특허가 보호받는 권리 범위(법적 정의) | `Claim` · `ClaimFeature` |
| **특허 패밀리 (patent family)** | 같은 발명을 여러 나라에 낸 출원들의 묶음 | 국가별 중복을 접는 단위 |

> ⚠ **출원일과 공개일을 섞으면 시계열 연구가 통째로 무효가 된다.** 이 저장소에서 실제로 그랬다 —
> `filing_date` 라는 이름의 컬럼에 **공개일**이 들어 있었고(권위 원천 대조로 발각), 두 값이 99 %
> 일치하는 바람에 오랫동안 눈에 띄지 않았다. **컬럼 이름은 의미의 증거가 아니다. 권위 원천과
> 대조한다.**

**왜 거절특허를 모으나.** 등록특허가 아니라 **거절**특허를 쓰는 이유는, 거절이유서에 **심사관이
직접 고른 선행기술**이 붙어 있어 *"선행기술조사"* 라는 태스크의 정답이 되기 때문이다. 사람이
새로 라벨링한 것이 아니라 심사 과정에서 이미 생산된 판단이라는 점이 핵심이다.

---

## 6. 특허 분류 — 코드는 소급 재분류된다

| 코드 체계 | 뜻 |
|---|---|
| **IPC** | 국제특허분류 (전 세계 공통) |
| **CPC** | 협력특허분류 (IPC 보다 세밀, 미국·유럽) |
| **F-term** | 일본 특허청의 다면 분류 |

자주 나오는 접두어:

| 코드 | 무슨 기술인가 |
|---|---|
| **H10B** | 메모리 **소자** (DRAM·NAND 등) |
| **H10D** | 개별 반도체 **소자**(트랜지스터·다이오드) |
| **H10W** | 웨이퍼 레벨 패키징·상호연결 |
| **G11C** | 메모리 **회로**(저장·읽기 로직) |
| **H01L** | 반도체 장치 일반(구 분류) |
| **G03F** | 포토리소그래피(노광) |

> ⚠ **소급(遡及) 재분류 함정.** 특허 분류는 **나중에 새 코드가 생기면 과거 특허에 소급 적용**된다.
> H10 계열은 최근 신설인데 특허청은 이를 십수 년 전 출원에도 붙였다. 즉 *"지금 보이는 코드"* 로
> 과거를 재면, **당시엔 존재하지도 않던 코드가 그 기술을 이미 알고 있었던 것처럼 보인다.**
> 코드 기반 시계열을 만들 때는 **당시 스냅샷**을 써야 하며, 그것이 없으면 그 분석은 성립하지 않는다.

**분류코드는 리터럴이 아니라 노드다.** SDKB 는 `IPCSymbol`/`CPCSymbol` 인스턴스로 올리고
`skos:notation` 에 코드 문자열을 단다 — 그래야 코드끼리의 계층을 표현할 수 있다
([`glossary_ontology.md`](glossary_ontology.md) 사고 2).

---

## 7. 산업 구조 — `Vendor` / `Organization` / `Firm`

| 주체 | 하는 일 | 예 |
|---|---|---|
| **종합반도체 (IDM)** | 설계+제조+판매를 다 함 | 삼성전자·SK하이닉스·인텔 |
| **팹리스 (fabless)** | 설계만, 제조는 위탁 | 퀄컴·엔비디아·AMD |
| **파운드리 (foundry)** | 남의 설계를 위탁 생산 | TSMC·삼성 파운드리 |
| **OSAT** | 조립·검사 위탁 | 앰코·ASE |
| **소부장 (素·部·裝)** | **소재·부품·장비** 공급 | 아래 표 |

**소부장 = 소재(Materials) · 부품(Parts) · 장비(Equipment).** 반도체를 *직접 만들지는 않지만*
만드는 데 필요한 것을 대는 후방 산업이다. 2019년 일본의 수출규제를 계기로 한국 정부의 핵심
정책 대상이 되었다.

| 층 | 무엇을 대는가 | 예 |
|---|---|---|
| **장비 (Equipment)** | 공정 장비 | ASML(EUV)·AMAT·Lam·TEL·SEMES |
| **재료 (Materials)** | 소재·화학물질 | 포토레지스트·특수가스·CMP 슬러리 |
| **부품 (Parts)** | 장비 부품 | 챔버·밸브·정밀부품 |

**밸류체인 (value chain).** 소재→부품→장비→소자→모듈로 이어지는 사슬. *"이 공정의 장비를
공급하는 회사는 누구이고 그 회사의 특허는 무엇인가"* 가 밸류체인 질의이며, `ont:valueChainStage`
와 `ont:providedBy`·`ont:madeBy` 가 그것을 잇는다.

> ⚠ **회사 하나 = IRI 하나.** 같은 회사가 장비 공급사이면서 특허 출원인일 수 있다. 역할별로 다른
> IRI 를 주면 밸류체인 질의가 **에러 없이 0행**을 낸다 —
> [`glossary_ontology.md`](glossary_ontology.md) 사고 0 이 그 기록이다.

**IP-R&D.** 특허 정보를 R&D 기획 단계에서 활용하는 실무 — 선행기술조사·공백기술 발굴·회피설계·
경쟁사 포트폴리오 분석.

---

## 8. 규제·수출통제 — `gov:` 모듈

반도체는 전략물자여서 국가가 수출·보호를 통제한다.

| 용어 | 뜻 | 주체 |
|---|---|---|
| **EAR / CCL** | 수출관리규정 / 상무부 통제품목 목록 | 미국(BIS) |
| **ECCN** | 수출통제 분류번호(품목별 코드) | 미국 · 예: EUV 장비 3B001 |
| **국가핵심기술 (NCT)** | 유출 시 국가안보에 영향을 주는 지정 기술 | 한국(산업기술보호법) |
| **디미니미스 / 해외직접생산품규칙(FDPR)** | 미국 기술이 일정 비율 이상이면 제3국 제품도 통제 | 미국 |
| **SVHC / SCIP** | 고위험 우려물질 · 유럽 신고 데이터베이스 | EU(ECHA) |

*"이 특허가 다루는 기술이 수출통제 대상인가"* 를 그래프로 물을 수 있다(`CQ23`·`CQ26`).

> ⚠ **규제 데이터는 수집 시점의 스냅샷이다.** 통제 목록은 자주 바뀐다. `ont:retrievedDate` 와
> `ont:effectiveDate` 를 반드시 함께 읽고, **법적 판단의 근거로 쓰지 않는다** — 이 그래프는
> 스크리닝 보조이지 준법 판정기가 아니다.

---

## 9. 원천 데이터

| 원천 | 무엇 | 라이선스 |
|---|---|---|
| **KIPRIS** | 한국 특허청 특허정보 검색 서비스(학술 API) | 학술 이용 · **비재배포** |
| **SemiKong** | 공개 반도체 공정 온톨로지 (arXiv:2411.13802) | Apache-2.0 |
| **SemicONTO** | 반도체 재료·장비 온톨로지 (CEUR-WS Vol-3760) | CC BY 4.0 |
| **MatKG** | 재료 지식그래프 (Scientific Data 2024) | CC BY 4.0 |
| **BIS CCL / NIST / ECHA SCIP** | 규제·거버넌스 원천 | Public |
| **한국 산업기술보호법** | 국가핵심기술 지정 | Public |
| **Wikidata** | 엔티티 링킹 | CC0 |
| **SEMI E10/E30/E40/E116** | 장비 상태·통신 표준 | 독점 — **식별자만 참조(Link-Only)** |

> **KIPRIS 원문은 이 저장소에 없다.** 학술 이용은 되지만 재배포는 안 되는 조건이라, 공개본은
> 초록·청구항 본문을 **빈 문자열로** 담고 스키마·식별자·서지·인용 라벨만 남긴다. 자기 키로
> 복원하는 절차는 루트 README 의 *"What is empty, and how to fill it"* 표에 있다.

---

## 10. 자주 혼동되는 것 (비전공 독자가 걸리는 지점)

| 혼동 | 사실 | 함의 |
|---|---|---|
| 공정 = 소자 | **다르다.** 공정=만드는 일(식각), 소자=만들어진 것(FinFET) | 술어가 다르다(`realizesProcess` vs `concernsDevice`) |
| 출원일 = 공개일 | **다르다.** 공개는 출원 18개월 뒤 | 컬럼명만 믿으면 시계열이 밀린다 |
| "후공정" = 금속배선(BEOL) | **다르다.** BEOL 은 **웨이퍼 안**, 후공정(패키징·다이싱)은 **웨이퍼 밖** | 둘 다 "back-end" 라 불려 헷갈림 |
| 종합반도체 = 소부장 | **반대편이다.** IDM 은 칩을 만들고, 소부장은 만들 재료·장비를 댄다 | 성격이 다른 코퍼스 |
| HBM(기술) = 특정사 HBM3E(제품) | **다르다.** 아키텍처 ≠ 상용 제품명 | 기술 데이터와 시장 데이터를 섞지 않음 |
| 지금 코드로 과거를 재도 된다 | **안 된다.** 코드는 소급 재분류된다 | 당시 스냅샷이 필요 |
| 기술 이름으로 검색하면 다 잡힌다 | **아니다.** 특허는 이름 대신 구조로 말한다 | 구조 기반 표현이 명칭보다 이르다 |
| "3 nm"에 3나노 구조물이 있다 | **아니다.** 세대 명칭이다 | 기술 노드는 마케팅·세대 이름 |
| EUV = DUV | **다르다.** EUV(13.5 nm)가 DUV(193 nm)보다 미세 | 첨단 노드는 EUV 필요 |
| 특허가 공정에 안 걸리면 결함 | **아니다.** IPC 가 회로·소자를 가리키면 그게 사실 | 억지 매핑 = 날조 |

---

## 11. 약어

**공정·소자** — **CMP** Chemical Mechanical Planarization(평탄화) · **CVD / PVD / ALD**
Chemical / Physical / Atomic-Layer Deposition(증착) · **EUV / DUV** Extreme / Deep
Ultraviolet(리소그래피) · **BEOL / FEOL** Back / Front End of Line(배선 / 소자 형성) ·
**HBM** High Bandwidth Memory · **GAA** Gate-All-Around · **MBCFET** Multi-Bridge-Channel FET ·
**FinFET** Fin Field-Effect Transistor · **TSV** Through-Silicon Via · **MRAM** Magnetoresistive
RAM · **FOWLP** Fan-Out Wafer-Level Packaging · **DRAM** Dynamic Random-Access Memory ·
**FMEA** Failure Mode and Effects Analysis

**산업·특허** — **IDM** Integrated Device Manufacturer(종합반도체) · **OSAT** Outsourced
Semiconductor Assembly and Test · **소부장** 소재·부품·장비 · **IP-R&D** Intellectual
Property-based R&D · **FTO** Freedom To Operate(회피설계) · **IPC / CPC**
International / Cooperative Patent Classification

**규제·원천** — **EAR** Export Administration Regulations · **CCL** Commerce Control List ·
**ECCN** Export Control Classification Number · **NCT** National Core Technology(국가핵심기술) ·
**FDPR** Foreign Direct Product Rule · **SVHC** Substances of Very High Concern ·
**KIPRIS** 한국 특허정보검색서비스 · **SIRP** Semiconductor Industry Rejected Patents ·
**SDKB** Semiconductor Domain Knowledge Base
