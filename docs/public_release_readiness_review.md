# 공개 준비 점검 — 외부인이 이 온톨로지를 이해하고 자기 분야로 확장할 수 있는가

> **범위.** 이 저장소가 `arkwith7/sdkb-dataset` 로 거의 그대로 공개된다는 전제에서,
> ① 공개하면 안 되는 것이 섞여 있지 않은가 ② 반도체 도메인 온톨로지에 관심 있는 외부
> 연구자가 **읽고 이해하고 자기 도메인으로 확장**할 수 있는가 를 점검한다.
> **작성 2026-08-09.** 근거는 전부 이 저장소에서 실행한 결과이며 각 항목에 명령·파일·줄
> 번호를 붙였다. 추정은 "추정"이라고 적는다.
>
> 앞선 판단 문서와의 관계 — `dataset_publication_risk_review.md` 는 **논문 투고 리스크**를
> 다루고, 이 문서는 **공개 리포 자체의 준비도**를 다룬다. 겹치는 항목(그 문서 §4-1 제외목록)은
> 아래 F1·F2 가 이어받는다. **그 문서 자체는 §1-F2 판정에 따라 `docs/_private/` 로 내려갔다** —
> 로컬에서는 `docs/_private/project/dataset_publication_risk_review.md` 로 읽는다.

---

## 0. 한 줄 결론

**원문 누출은 막혔지만 공개 경계는 아직 원문에만 걸려 있고, 온톨로지를 설명하는 문서는
한 건도 없다.** 외부인이 이 저장소를 받아서 할 수 있는 것은 *"돌려 보기"* 까지이고,
*"이해하고 자기 도메인에 옮기기"* 는 지금 문서로는 불가능하다 — T-Box 를 설명하는 문서가
0건이고, 확장 절차를 적은 문장이 저장소 전체에 없다(`grep -rniE "how to extend|adapt.*your" docs/ README.md` → 0건).

우선순위는 셋이다. **① 공개 경계를 원문에서 문서로 넓힌다(차단) → ② 온톨로지 안내서를
세운다(핵심) → ③ 내부 거버넌스 문서를 공개본에서 분리한다(정리).**

---

## 1. 차단 — 공개 전에 반드시 닫아야 하는 것

### F1. 공개 트리 생성기가 독점문서를 걸러내지 않는다 🔴

| | |
|---|---|
| **사실** | `build_public_release.py:105-118` 은 `git ls-files` 전량을 복사하고, 블랙리스트는 데이터셋 파일의 `abstract`·`claim1`·`claims_full[].text` 세 필드와 노트북 셀 출력뿐이다(`TEXT_FIELDS`, `strip_notebook`). `check_public_release.py` 의 지문도 같은 세 필드에서만 뽑는다. |
| **결과** | `docs/project/commercialization_strategy_v1.md`(git 추적됨, 헤더에 *"CONFIDENTIAL — lab-internal + ARKWITH proprietary. Do not redistribute."*)가 **검사기를 통과한 채로 공개된다.** 내용은 IPBridge 가격 트랙 T1–T3, 로드맵, 내부 평가수치(`Mode C Recall@10 = 0.838` / `Mode B = 0.324`)다. |
| **왜 검사기가 못 잡나** | 검사기의 질문이 *"KIPRIS 원문이 남았는가"* 이기 때문이다. *"공개하면 안 되는 것이 들어왔는가"* 는 아무도 묻지 않는다. |
| **되돌릴 수 있나** | 없다. 검사기 docstring 이 스스로 적은 대로다 — *"공개된 커밋은 지워도 포크·캐시·PR ref 로 남는다."* |

**요구 수정.** 생성기에 **문서 블랙리스트**를 넣고, 검사기에 **금칙 마커 탐지**를 넣는다.
파일명 목록만으로는 F2 와 같은 사고가 반복되므로, 두 층으로 건다.

1. 생성기: 제외 경로 목록(아래 §1-F2 표)을 상수로 두고 복사에서 뺀다. 뺀 파일 수를 보고한다.
2. 검사기: 공개 트리 전체에서 `CONFIDENTIAL`·`proprietary`·`Do not redistribute`·`lab-internal`
   마커를 찾는다. 하나라도 걸리면 실패. **이것이 목록보다 강하다** — 새 문서가 생겨도 스스로
   신고한 문서는 자동으로 잡힌다.

> **⚠ 단순 grep 으로 만들면 안 된다 — 실측으로 확인했다.** 아카이빙 후 공개 트리에 같은 grep 을
> 걸었더니 **2건이 걸렸고 둘 다 정상 문서**였다: 이 문서(F1 의 증거로 그 헤더를 **인용**한다)와
> `datasheet.md`(Gebru 질문 *"Confidential or sensitive content?"*). **기밀을 담은 문서와 기밀을
> 논하는 문서를 가르지 못하면 검사기는 무시된다.**
>
> 설계 권고 — 마커를 **문서 앞머리 15줄 안**에서만 찾고, **인용 표시(`>` 인용문·백틱·따옴표)
> 안의 적중은 제외**한다. 또는 더 단단하게: 비공개 문서가 **첫 줄에 `<!-- sdkb:private -->`**
> 를 달게 하고 검사기는 그 토큰 하나만 본다 — 자연어 마커보다 오탐이 없고, 새 문서 작성자가
> 명시적으로 선언하게 만든다. 이 방식을 쓰면 §1-F2 의 파일 목록도 생성기에서 없앨 수 있다.

**검증 기준.** 빈 체크아웃에서 `make public-release && make check-public` → 제외 파일 수 ≥ 8 ·
금칙 마커 적중 0(**오탐 0 포함**) · KIPRIS 지문 적중 0.

> 이 수정은 생성기와 테스트를 바꾸므로 CLAUDE.md §2 의 정지 게이트를 탄다. **이 문서는 요구
> 정의까지이고 구현하지 않았다.**

### F2. §4-1 제외목록이 잘못된 이유로 닫혔다 🔴

`dataset_publication_risk_review.md` §0-0(2026-08-09 재판정)은 마지막 행에서 이렇게 적었다 —
*"익명 스냅샷 ✅ **해소 — 필요 없어졌다.** 더블블라인드 익명 스냅샷은 데이터셋 트랙 분리를
전제한 워크플로우였다."*

**전제는 맞고 결론은 과하다.** §4-1 의 제목은 *"익명 스냅샷 제외 목록 (**lab-internal·독점·
식별** 문서)"* 다. 익명화(누가 썼는지 감춘다)와 비공개(무엇을 담았는지 안 낸다)는 다른 요구이고,
더블블라인드가 사라진 것은 앞의 것만 없앤다. 뒤의 것은 그대로 남는다.

**제외 대상 재판정** — §4-1 목록을 공개 리포 기준으로 다시 매긴다.

| 파일 | §4-1 사유 | 공개 리포에서의 판정 | 근거 |
|---|---|---|---|
| `docs/project/commercialization_strategy_v1.md` | 독점 | **제외** | 스스로 CONFIDENTIAL 선언 · ARKWITH 가격/로드맵 |
| `docs/project/dataset_publication_risk_review.md` | lab-internal | **제외** | 투고 전략·법무 미해결 항목·자기 리스크 자백 |
| `docs/project/project_status_2026_1.md` | lab-internal | **제외** | 학과 과제 진행상황·미달 항목 |
| `docs/project/plan_amendment_v{1,2,3,3_bis}.md` | lab-internal | **제외** | 지도교수 승인 절차 문서 |
| `docs/project/feedback/` | 식별 | **제외** | 리뷰 회신 — 특정인 지목 |
| `docs/expert_validation_log.md` | 식별 | **조건부 제외** | 현재는 세션 #00 스캐폴드뿐이라 실 위험 낮다. 그러나 공개 후 실 세션이 쌓이면 역할·연차·소속이 들어간다. **규약이 아니라 습관이 결정하게 두지 않는다** |
| `docs/project/architecture_amendment_sdkb_centric.md` | lab-internal | **공개 유지** | F3 참조 — 온톨로지·생성기·shape·테스트가 참조한다. 빼면 발행된 그래프가 죽은 링크를 갖는다 |
| `*.pdf`(`SDKB_v1_0_…실행계획_v2.pdf`, 528 KB) | — | **제외 권고** | 학과 제출 실행계획서. 공개 데이터셋의 문서가 아니다 |

> `CITATION.cff` 는 §4-1 에서 제외 대상이었으나 그것은 **더블블라인드** 사유다. 공개 리포에서는
> 반대로 **반드시 있어야 한다.** — 이것이 F2 가 말하는 두 요구의 차이다.

---

## 2. 정합성 — 공개하면 외부인에게 보이는 어긋남

### F3. 온톨로지가 가리키는 URL 이 옛 리포다 🟠

> **갱신 2026-08-09 — 절반은 닫혔다.** 아카이빙에서 `architecture_amendment_sdkb_centric.md` 는
> **공개 쪽에 남겼다.** 온톨로지·생성기·shape·테스트가 그것을 참조하므로 빼면 발행된 그래프가
> 죽은 링크를 갖는다. 남은 문제는 **URL 이 옛 리포를 가리킨다**는 것 하나다.

`ontology/sdkb-core.ttl:24-26` —

```turtle
rdfs:comment "… SDKB-centric architecture: external ontologies (SemicONTO, QUDT, etc.)
              are REFERENCED via SKOS mappings …, NOT imported.
              See docs/project/architecture_amendment_sdkb_centric.md."@en ;
rdfs:seeAlso <https://github.com/arkwith7/semiconductor-knowledge-base/blob/main/docs/project/architecture_amendment_sdkb_centric.md> ;
```

**두 갈래뿐이고 지금 골라야 한다.** 그 문서를 공개하면 §4-1 제외 사유(lab-internal 계획 개정)를
어기고, 제외하면 **온톨로지가 죽은 링크를 발행한다.** 게다가 URL 이 옛 리포(`semiconductor-knowledge-base`)를
가리키는데 공개는 새 리포(`arkwith7/sdkb-dataset`)로 확정됐다 — 지금 그대로면 **공개 첫날부터 404** 다.

**권고.** 그 문서에서 *설계 근거*(왜 import 하지 않고 SKOS 로 참조하는가)만 뽑아 공개용
[`ontology_guide.md`](ontology_guide.md) §3 으로 승격하고, `seeAlso` 를 새 리포의 그 앵커로 옮긴다.
계획 개정 이력(누가 언제 무엇을 승인했는가)은 공개하지 않는다. **근거는 공개하고 절차는 감춘다.**

### F4. README 의 클래스 수가 실측과 다르다 🟡

`README.md:109` 은 `sdkb-core.ttl # 14 core classes` 라 적는다. 실측은 **43개**(named;
blank node 13 제외)다.

```
$ .venv/bin/python -c "…rdflib inventory…"
sdkb-core.ttl   C named=43(blank 13)  OP=45  DP=45  triples=718
```

14 는 큐레이션 그래프의 **노드 타입 수**(datasheet §2 의 Process·SubProcess·…·Skill 열거)이고
T-Box 클래스 수가 아니다. 둘 다 맞는 숫자지만 같은 자리에 쓰면 틀린 말이 된다 — CLAUDE.md §1-4.

같은 이유로 `sdkb-patent.ttl` 을 `grep -c "owl:Class"` 로 세면 22 가 나오는데 그중 6개는
restriction blank node 다. **named 는 16개.**

### F5. 큐레이션 그래프 수치가 실물보다 45 노드 낡았다 🟠

README:250 과 datasheet §2 는 *"Verified snapshot 2026-05-17: 229 nodes / 268 edges"* 라 적는다.
**실물은 274 노드 / 312 엣지**이고, 빌드된 그래프는 **275 인스턴스 / 2,884 트리플**이다.

```
$ python -c "import json;d=json.load(open('data/semiconductor_v0_3.json'));print(len(d['nodes']),len(d['edges']))"
274 312
$ git log -1 --format=%ci -- data/semiconductor_v0_3.json
2026-08-01 17:21:32 +0900        ← 검증 스냅샷(2026-05-17) 이후에 원천이 자랐다
```

노드 타입도 **15종**이다(Device 포함). README:102 의 *"14-type process KG"* 는 Device 추가 전
숫자다. 빌드 그래프의 16종은 `ont:Semiconductor` 인스턴스 1건이 더해진 것이다.

**왜 이것이 중요한가.** 외부인이 가장 먼저 하는 검증이 *"README 숫자가 나오는가"* 이고, 지금은
`make owl convert` 한 번에 어긋난다. risk review #3(수치 일관성)은 2026-05-17 에 "닫힘"으로
판정됐지만 **그 뒤에 원천이 바뀌었으므로 다시 열렸다.** CLAUDE.md §1-4 — *"규모가 바뀌면
README·CHANGELOG 를 같은 커밋에서 고친다."*

**권고.** 숫자를 손으로 고치지 말고, 릴리스 서명(클래스별 인스턴스 수)을 **코드가 뽑아** README 에
넣는 절차를 만든다. 손으로 고치면 다음에 또 어긋난다 — 이번이 그 증거다.

### F7. 공개 스크립트가 비공개 하류 저장소를 읽는다 🟠 (2026-08-09 추가)

**의존 방향이 뒤집혔다.** `CLAUDE.md` §0 은 *"하류가 커밋 SHA + sha256 으로 우리를 핀한다"* 고
적는다 — 즉 상류는 하류를 모르는 것이 계약이다. 그런데 커밋된 스크립트 셋이 **옆 디렉터리의
비공개 논문 저장소를 하드코딩**하고 있다.

```
scripts/decompose_corpus.py:81   …/SKKU/sdkb-foresight-paper/data/processed/graph_v2.ttl
scripts/decompose_corpus.py:100  …/SKKU/sdkb-foresight-paper/data/processed/graph_v1.ttl
scripts/enrich_kipris_biblio.py:51 · llm_claim_validate.py:30 · collect_cited_biblio_claims.py:32  (.env 폴백)
```

문제는 셋이다.

1. **외부인에게 재현 불가.** 그 경로는 남의 컴퓨터에 없다. 빈 체크아웃 검증(CR-016)이 잡아낸
   것과 **같은 종류의 결함이 아직 셋 남아 있다.**
2. **경로 자체가 낡았다.** `sdkb-foresight-paper` 는 현재 `sdkb-prior-art-paper` 다.
3. **docstring 이 하류의 코퍼스 설계를 공개한다.** `decompose_corpus.py:92-95` 는
   *"주 대비 코퍼스 G1(삼성·SK하이닉스)"* · *"판단(Tier 1)·인용(Tier 2)·코퍼스(Tier 3)"* ·
   *"§29② 진보성 판단의 초점"* 을 적는다. **결과는 아니지만 설계이고, CHANGELOG 보다 구체적이다.**

**권고.** `.env` 폴백 셋은 지운다(자기 `.env` 를 쓰게 한다). `decompose_corpus.py` 의 두
`src_g1`/`src_g2` 는 **경로를 인자로 받게** 바꾸고, 입력이 없으면 명확히 실패시킨다 —
그러면 공개본은 "이 진입점은 자기 코퍼스를 준다"가 되고 하류 이름이 사라진다.
docstring 의 하류 설계 서술은 일반 문장으로 바꾼다.

> **닫혔다 (2026-08-09).** R1 과 한 요구정의로 묶어 §2 절차를 탔다 —
> `docs/_private/project/plan_r1_f7_public_boundary.md`. 범위는 여기 적힌 3파일이 아니라
> **8곳**이었다(측정 결과). 외부 코퍼스는 `--g1-ttl`·`--g2-ttl` 로 받고, 경로 없이 지목하면
> 실패한다. `--source all` 은 내부 3종만 돌리고 건너뛴 것을 출력한다.
>
> **F8 로 남긴 것 하나.** `data/patents/rejection_decisions/_index.jsonl` 11행의 `pdf_path` 가
> 홈 절대경로다. 생성기는 이미 상대경로로 쓰므로(`build_rejection_decisions.py:357`) 이것은
> **과거 실행이 남긴 데이터 잔재**이고, 정규화하려면 원천 트리가 있어야 한다. 공개본에서는
> 생성기의 절대경로 스크럽이 막는다.

### F6. 공개 대상 문서가 한국어 중심인데 정본 README 는 영문이다 🟡

| 문서 | 한국어 줄 / 전체 |
|---|---|
| `docs/dataset_rejected_patents_card.md` | 124 / 202 |
| `docs/dataset_full_collection_runbook.md` | 230 / 374 |
| `docs/semiconductor_industry_rejected_patents_schema.md` | 150 / 308 |
| `docs/kipris_reject_dataset_source_mapping.md` | 154 / 261 |
| `docs/deidentification_protocol.md` | 126 / 189 |

영문 README 가 *"see the dataset card"* 라 쓰고 링크를 따라가면 한국어 문서가 나온다.
KIPRIS·KIPO 절차 설명은 한국어가 자연스럽지만, **스키마 표와 필드 정의는 언어와 무관한 사실**이라
영문이 있어야 한다. 전량 번역은 과하다 — 권고는 **각 문서 머리에 영문 요약 5–10줄 + 표의 열
이름 영문 병기**다.

---

## 3. 핵심 질문 — 외부인이 이해하고 확장할 수 있는가

**현 상태로는 아니다.** 근거 넷.

### G1. T-Box 를 설명하는 문서가 0건

`docs/` 15건 중 온톨로지의 클래스·술어·모델링 결정을 설명하는 문서는 없다. 있는 것은 데이터셋
카드(SIRP 특허), 수집 런북, 스키마(parquet 컬럼), 프로토콜(누수·비식별), 그리고 내부 계획서다.
**온톨로지에 관심 있는 사람이 정확히 찾는 것만 없다.**

지금 외부인이 읽어야 하는 것은 TTL 원문이다 — 실측 **명명 클래스 84 · ObjectProperty 93 ·
DatatypeProperty 85**, 7개 모듈에 흩어져 있다.

### G2. `docs/` 에 색인이 없다

디렉터리를 열면 15개 파일 + `project/`(26건) + `references/`(19건)이 알파벳 순으로 나열된다.
어디서부터 읽는지, 무엇이 규범이고 무엇이 이력인지 알 방법이 없다.

### G3. 문서의 절반 이상이 내부 거버넌스다

파일 수 기준 `docs/project/` 26건 + `feedback/` 2건 = **전체 60건 중 28건**. 바이트로는
361 KB 중 약 200 KB. 공개 리포에서 이것은 문서가 아니라 **소음**이고, 외부인에게는 "이 저장소는
연구 노트다" 라는 신호를 준다 — 데이터셋 리포에 필요한 신호의 반대다.

### G4. 확장 절차를 적은 문장이 없다

```
$ grep -rniE "how to extend|extend the ontology|reuse this|adapt.*your" docs/ README.md
(0건)
```

README 의 *"What is empty, and how to fill it"* 는 훌륭하지만 **이 온톨로지를 그대로 채우는**
방법이고, **다른 도메인으로 옮기는** 방법이 아니다. 사용자의 질문(*"자신의 분야에 응용 확장"*)은
정확히 이 공백에 걸린다.

### G5. 정렬 모듈의 술어에 주석이 없다

`rdfs:comment` 보유율 실측:

| 모듈 | 클래스 | ObjectProperty | DatatypeProperty |
|---|---|---|---|
| `sdkb-core.ttl` | 43/43 | 45/45 | 45/45 |
| `sdkb-patent.ttl` | 16/16 | 23/32 | 17/26 |
| `sdkb-rbv.ttl` | 9/9 | **1/6** | 3/3 |
| `sdkb-foresight.ttl` | **4/6** | **1/6** | 3/4 |
| `sdkb-commercialization.ttl` | **5/7** | **1/6** | 2/4 |
| `sdkb-governance-kr.ttl` | 3/3 | **1/2** | 1/2 |

코어와 특허는 문서화가 잘 돼 있다. 정렬 3종은 **술어가 이름뿐**이다 — 외부인은 `ont:combines`
가 무엇과 무엇을 잇는지, `ont:scenarioDriver` 의 방향이 어느 쪽인지 알 수 없다.
`rdfs:domain`/`range` 는 붙어 있으므로(9/9 · 9/10 · 8/10) 형태는 읽히지만 **의도는 읽히지 않는다.**

### G6. 예제 질의가 적고 CQ 는 설명이 없다

`examples/sparql/` 3건 · `queries/cq/` 31건. CQ 는 `# desc:` 주석이 **한국어**로 한 줄씩 붙어
있을 뿐 목록·분류·기대 출력을 설명하는 문서가 없다. README 는 `make cq` 만 알려준다.
**31건은 이 온톨로지가 무엇을 답할 수 있는지의 가장 좋은 증거인데 지금은 파일명으로만 존재한다.**

---

## 4. 이번에 한 것 · 승인이 필요한 것

### 이번에 한 것

**1차 — 문서 추가.**

| 산출물 | 무엇을 닫는가 |
|---|---|
| [`docs/README.md`](README.md) | **G2** — 독자 유형별 읽기 경로 색인 |
| [`docs/ontology_guide.md`](ontology_guide.md) | **G1·G4·G6** — 모듈 지도, IRI 규칙, 설계 결정 3종, **확장 레시피 A/B/C**, 릴리스 게이트, CQ 스위트 안내 |
| [`docs/glossary_ontology.md`](glossary_ontology.md) | **G1** — RDF/OWL/SHACL/SKOS 용어 + **이 저장소가 실제로 낸 사고 다섯**과 그로부터 나온 규칙 |
| [`docs/glossary_semiconductor.md`](glossary_semiconductor.md) | **G1** — 표현 대상인 반도체 도메인. 각 절이 어느 클래스·술어에 대응하는지, 어디서 의도적으로 멈추는지 |
| 이 문서 | 점검 결과와 남은 요구 |

> **두 용어집은 하류 논문 저장소의 `01.code_spec/GLOSSARY-*.md` 에서 옮겨 썼다(사용자 지시).**
> 그대로 복사하지 않았다 — **논문 라벨(H1–H5·RQ·S1–S3)·절 참조·`G₀/G₁/G₂`·미발표 실험 수치를
> 전부 걷어냈다.** 남긴 것은 ① 일반 도메인 지식 ② **SDKB 자신의 결함 기록**이며, 후자는 이
> 저장소의 자산이므로 공개에 문제가 없다. **미발표 결과를 공개 리포에 싣는 것은 스스로 논문을
> 선행공개하는 것**이라 특히 조심했다 — 걷어낸 것에는 보강 전후 특허 건수, 커버리지 포화 수치,
> 개념·명칭 시계열의 선행 연수, 소급 재분류 비율, 수출통제 노출 건수가 포함된다.

**2차 — 내부 문서 아카이빙(R2 실행 · 사용자 승인).** 21개 파일을 `docs/_private/` 로 옮기고
`.gitignore` 에 등재했다. 공개 트리는 `git ls-files` 로 만들어지므로 **추적에서 빠지는 순간
공개본에서도 빠진다** — 별도 제외 목록이 필요 없다는 뜻이고, F1 의 요구 R1 을 **문서에 한해서는**
코드 변경 없이 충족한다.

| | 내용 |
|---|---|
| **옮긴 것** | 사업화 전략(독점) · 리스크 검토 · 진척표 · 계획개정 v1–v3bis · 피드백 2건 · 자문 로그 · CR 계획/회신 8건 · 포지셔닝·변환성능 2건 · 실행계획 PDF |
| **남긴 것** | `architecture_amendment_sdkb_centric.md`(온톨로지가 `rdfs:seeAlso` 로 가리키고 생성기·shape·테스트가 참조) · `prior_art_ontology_gap_and_data_plan.md`(공개 runbook 의 근거) · `matching_architecture` · `research_alignment` · `visualization_plan` |
| **기준** | **산출물을 설명하는가(공개), 과정을 기록하는가(비공개).** 판정표는 §1-F2 |
| **부수 작업** | 아카이브 내부 상대링크 15건 재계산 · 공개 문서 8곳의 끊어질 링크 제거(README·README.ko·datasheet·card·deid·matching_arch·research_alignment·docs/README) |
| **남은 흠** | `CHANGELOG.md` 가 아카이브된 문서를 4곳에서 링크한다. 이력 문서라 손대지 않았다 — 공개본에서 죽은 링크가 된다 |

**수치는 전부 실행 출력이다**(rdflib 인벤토리 · `git ls-files` · `grep -c`). 손으로 옮겨 적은
숫자는 없다.

### 승인이 필요한 것 (하지 않았다)

| # | 요구 | 왜 멈췄나 |
|---|---|---|
| ~~R1~~ | ~~생성기·검사기에 문서 경계 추가 (F1)~~ | **완료 (2026-08-09)** — F7 과 한 요구정의로 묶어 §2 정지 게이트를 탔다(`docs/_private/project/plan_r1_f7_public_boundary.md`). 첫 줄 토큰 `<!-- sdkb:private -->` · 생성기 제외 + 검사기 거부 두 층 · 주입 시험으로 양쪽 확인 |
| ~~R2~~ | ~~`docs/project/` 를 공개본에서 분리~~ | **완료 (2026-08-09)** — 위 2차 참조 |
| **R3** | `sdkb-core.ttl` 의 `seeAlso` URL 교체 (F3) | TTL 은 빌드 산출물 → `build_owl.py` 를 고쳐야 하고, 어휘 메타데이터 변경은 하류 통보 대상 |
| **R4** | README 클래스 수·그래프 규모 정정 + 서명 자동 산출 (F4·F5) | README 는 정본이고, 수치는 손이 아니라 코드가 넣어야 반복되지 않는다 |
| **R5** | 정렬 3모듈 술어에 `rdfs:comment` 보강 (G5) | T-Box 변경 → §2 전체 · 하류 서명이 바뀐다 |
| **R6** | 공개 대상 문서 영문 요약 (F6) | 분량이 크다 — 우선순위 판단 필요 |

**권고 순서: ~~R1~~ → R3 → R4 → R6 → R5.** (R1·R2 완료.)

**R1 은 R2 로 대체되지 않는다.** R2 는 *지금 아는* 문서를 뺐고, R1 은 *앞으로 생길* 문서를 막는다.
검사기의 금칙 마커 탐지가 없으면, 다음에 누가 `docs/` 에 내부 문서를 새로 쓰는 순간 같은 사고가
반복된다 — 이번에 걸린 문서도 스스로 *"CONFIDENTIAL"* 이라 적어 두었는데 아무도 그것을 읽지
않았다. **읽는 것을 사람이 아니라 검사기로 만든다.**

---

## 5. 이 문서가 답하지 못한 것

- **외부인이 실제로 이해하는가는 측정하지 않았다.** 위 판단은 *"이해에 필요한 문서가 존재하는가"*
  까지이고, 존재하는 문서로 실제 확장이 되는지는 **한 명이라도 시도해 봐야 안다**. 가장 싼 검증은
  빈 체크아웃 + `ontology_guide.md` 만으로 새 클래스 하나를 추가해 보는 것이다(§확장 레시피가
  그 절차를 적어 두었다).
- **라이선스 혼합의 법적 적합성은 다루지 않았다.** CDLA-Permissive-2.0 × SemiKong Apache-2.0 ×
  SemicONTO/MatKG CC BY 4.0 의 조합은 risk review #5 에서 "닫힘"으로 판정됐으나, 그 근거는
  *"README 가 원천별 라이선스를 명시한다"* 이지 법률 검토가 아니다. **이 문서도 법률 자문이 아니다.**
