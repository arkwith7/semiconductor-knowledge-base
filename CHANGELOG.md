# Changelog

All notable changes to SDKB will be documented in this file.

> **How to read this log** · 이 로그를 읽는 법
>
> This is a **contemporaneous engineering record**, not a release summary. Entries are written
> when the change happens and are **never rewritten afterwards** — where a later entry corrects
> an earlier one, both stay. That is deliberate: a downstream consumer that pinned an old commit
> needs to see what was true then, not what we wish had been true.
>
> **Vocabulary used throughout.** Entries are written for the consumers listed in
> [`CLAUDE.md`](CLAUDE.md) §0, so they use that repository's shorthand:
>
> | 표기 | 뜻 |
> |---|---|
> | **하류 (downstream)** | A repository that vendors a frozen snapshot of this graph and evaluates on it. SDKB is the *upstream* resource; it does not depend on downstream code. |
> | **CR-NNN** | *Change Request* — a defect report filed by a downstream consumer with evidence, a proposed fix, and an acceptance criterion. Entries titled `CR-NNN` record what this repository did in response. |
> | **D-NN** | The downstream defect-ledger id that a CR answers. Cited so the two records can be lined up; the ledger itself is not part of this repository. |
> | **vendor / 스냅샷** | Copying this repository's TTL at a specific commit and freezing it (commit SHA + per-file sha256). |
> | **G₀ / G₁ / G₂** | A downstream consumer's naming for its frozen baseline graph and its augmented candidate pools. Appears here only when reporting how a change moves *their* triple counts. |
>
> **Relationship to papers that cite this dataset.** This log keeps growing after any manuscript
> is frozen, so a paper and this file will diverge by design. **Cite a release tag, not `main`** —
> the tag names the state the paper actually used. Entries here describe *what was built and why*;
> they are not that research's results, and no experimental result is reported in this file.

## [Unreleased]

## [1.1.0] — 2026-08-20 · paper release

Tagged `v1.1-paper` · archived at Zenodo · version DOI [10.5281/zenodo.22030396](https://doi.org/10.5281/zenodo.22030396) ·
concept DOI [10.5281/zenodo.22030395](https://doi.org/10.5281/zenodo.22030395).

**Cite this release, not `main`.** This log keeps growing after the paper is frozen, so the tag
names the state the paper actually used. Three things enter the release that were not previously
available: the evaluation harness under `benchmark/` (127 files, with a manifest, an exclusion
list, and a crosswalk from the paper's system table to the code entry points), integrity records
for **all 323 published assets** in `provenance/PROVENANCE.json` computed over the bytes of the
published tree, and an explicit code licence (`LICENSE-CODE.txt`, Apache-2.0) alongside the data
licence. Entries below record how each of those was built.


### Added (2026-08-19 — 무결성 기록이 자산 1건만 등재하고 있었다 · 하류 재현성 P0)

`scripts/build_provenance.py` — 공개 트리의 **발행 자산 전량**(194건)에 sha256·바이트를 등재한다.
해시는 **공개 트리의 바이트**로 계산한다. 공개본은 복사되며 변형되므로(사설 블록 제거·죽은 링크
평문화·원문 스크럽·절대경로 세척) 비공개 원본의 해시를 실으면 소비자가 계산한 값과 어긋난다.
저장소의 `provenance/PROVENANCE.json` 은 사람이 유지하는 **큐레이션 씨앗**(generator·inputs·
change_request)으로 남고, 그 필드는 발행본에 병합된다. 생성 시각은 싣지 않는다 — 두 번 돌려
바이트가 같아야 무결성 기록이다. `make public-release` 가 발행하고 `make check-public` 이 대조하며,
불일치는 rc=1 이다. 어휘·IRI·T-Box·shape 변경 0.

### Fixed (2026-08-16 — 발행 계수가 그래프보다 많이 세고 있었다 · CR-019 / D-41) ⚠ 하류 통보

**계수만 바뀌었다. 그래프는 한 트리플도 바뀌지 않았고, 세 산출물의 sha256 은 전부 그대로다**
(`sdkb-abox-claim-features.ttl` `71e053b8…` · `claim_features.parquet` `2b21465c…` ·
`claim_feature_release_meta.json` `41e01f91…`). 바뀐 것은 `abox_claim_features_report.json`
하나다.

rdflib 는 같은 트리플을 합친다. 그래서 `g.add()` 호출을 세는 계수기는 **정의상 그래프를
기술하지 않는다.** 같은 파일 안에서 두 계열이 갈려 있었고 — 계수기는 방출을, CR-017 투영은
고유를 셌다 — 그 차가 발행돼 하류가 **자기 쪽에서 정확히 세고도 자기 계수를 의심했다**.

| 필드 | 구 발행값 | 정정값 | 차 | 원인 |
|---|---|---|---|---|
| `counts.features` | 1,306,419 | **1,306,191** | −228 | 중복 입력 행 143개(전량 `cited:`)의 feature 재방출 |
| `counts.depends` | 653,539 | **653,510** | −29 | 같은 중복 행이 `dependsOnFeature` 를 재방출 |
| `Σ feature_concept_by_type` | 592,779 | **529,151** | **−63,628** | 한 feature 가 같은 개념을 여러 표면형으로 맞춤 — *"EUV 포토레지스트"* 와 *"포토레지스트"* 가 같은 노드를 각각 적중 |

셋째 행은 CR-019 조사 중 **새로 발견**된 것으로, 기전이 앞의 둘과 다르고 규모가 279배 크다.
`counts.claims`(594,078)·`claims_independent`·`depends_on_claim` 계열은 **원래 정확했다** —
청구항 중복은 이미 막혀 있었고 feature 중복만 막히지 않았다.

**버린 것을 지우지 않는다.** 조용히 합치면 다음 진단이 막히므로(D-25) 재방출을 별도 필드로
남긴다 — `features_duplicate_emissions` 228 · `depends_duplicate_emissions` 29 ·
`input_duplicate_keys` 143 · `input_duplicate_rows` 143 · `duplicate_keys_by_side` ·
`concept_hits_raw` 592,779. `_README` 에 *"두 계열을 더하지 말 것"* 을 박았다.
`input_claims`(594,221)는 **이름을 바꾸지 않았다** — 하류 소비자가 있을 수 있고, 고유 청구항
수와의 차 143 은 신설 필드가 같은 자리에서 설명한다.

**재발 방지선은 생성기 안에 있다.** `_assert_count_integrity()` 가 `counts.features ==
projection.rows_features` 와 `Σfeature_concept_by_type == projection.concept_links` 를
빌드 시점에 검사하고, 어긋나면 `SystemExit` 으로 죽어 **리포트를 쓰지 않는다.** 틀린 숫자를
발행하느니 산출물이 없는 편이 낫다.

**중복 143쌍은 전부 바이트 단위로 동일했다** — 고유 기준으로 세도 버려지는 내용이 없다.
**중복의 발생 경로(`decompose_corpus.py` 증분 저장)는 이번 범위 밖이다** — 원천을 바꾸면
그래프가 움직이므로 별건이다.

검증: 256 passed · 10 skipped · ruff 통과 · 신규 `tests/test_claim_feature_counts.py` 10건
(어긋난 리포트가 실제로 거부되는지를 포함).

### Changed (2026-08-15 — 공개본이 **자기 CQ 값을 싣는다** · CR-015 ③④) ⚠ 하류 통보

**리포에 실려 있던 CQ 통과율은 이 리포를 받은 사람이 얻는 값이 아니었다.** 개발 환경에는
KIPRIS 원문이 전량 있어 특허 A-Box 가 만들어지지만, 공개본에는 원문이 없다(§10.3 · CR-015).
그래서 같은 스위트가 다른 값을 낸다 — 그리고 우리는 **개발 환경 값을 싣고 있었다.**

격리 사본에서 실측한 세 값(2026-08-15):

| 조건 | 전체 | em | tf | core | pa |
|---|---|---|---|---|---|
| 공개본을 받은 그대로 | **14/31 = 0.452** | 4/6 | 2/5 | 7/12 | 1/8 |
| 본인 KIPRIS 키로 **재인출 후** | **27/31 = 0.871** | 1.000 | 1.000 | 1.000 | 4/8 |
| (참고) 원문 전량 개발 환경 | 0.871 | 1.000 | 1.000 | 1.000 | — |

**재인출하면 개발 환경과 같은 값에 도달한다.** em·tf·core 가 전부 1.000 으로 복구되므로,
공개본 + 본인 키로 이 그래프의 기능 검증이 재현된다는 뜻이다.

**끝까지 복구되지 않는 4건은 전부 청구항 한정요소 층이다** — `CQ27_fto_claim_readiness` ·
`CQ29_claim_level_rejection_judgment` · `CQ30_independent_claim_features` ·
`CQ31_dependent_claim_hierarchy`. 그 층의 분해 입력(feature text)은 원문 그 자체라 공개할 수
없고, 재수집하더라도 분해가 언어모델을 쓰므로 같은 파일이 나온다는 보장이 없다. **결함이
아니라 라이선스가 강제하는 경계이며, 그래서 숨기지 않고 여기 적는다.**

- `make public-release` 가 **공개 트리 안에서 `run_cq.py` 를 다시 돌린다.** 발행되는 숫자가
  소비 가능한 상태를 기술하도록 하는 것이 목적이다.
- 함께 실린 것: 공유 T-Box 본체(`sdkb-core.ttl`·`sdkb-core-data.ttl`)와 전문가 매칭 A-Box,
  규제 인스턴스 둘. **원고가 공개를 약속했는데 gitignore 된 빌드 산출물이라 빠져 있었다.**
  넣을 대상은 정본 지문 2,322개로 훑어 **적중 0 인 것만** 골랐다(특허 A-Box 1,875 적중 ·
  선행기술 46 적중 → 제외 유지).

### Changed (2026-08-10 — 공개본을 **허용목록**으로 뒤집었다) ⚠ 공개 범위 변경

**이 저장소는 아무것도 잃지 않는다.** 바뀐 것은 `make public-release` 가 만드는 트리뿐이다.

예전에는 추적 파일 **전량을 복사한 뒤** 넷을 뺐다(원문 3필드 값 · 첫줄 토큰 문서 · 홈
절대경로 · 옛 슬러그). 그 근거는 *"조용히 빠지는 쪽보다 조용히 들어오는 쪽이 검사기에
걸린다"* 였다. **그 전제를 버린다** — 공개는 되돌릴 수 없고(포크·캐시·PR ref), 조용히
들어온 것을 검사기가 잡아 주는 것은 이미 늦은 뒤다. 이제 **허용목록에 있는 것만** 나가고
모르는 파일은 기본적으로 공개되지 않는다.

| | 파일 |
|---|---|
| 추적 | 681 |
| 공개 | **184** |
| 제외 | **497** — `data/patents/rejection_decisions/` 442 · `docs/` 28 · `scripts/` 14 · `notebooks/` 8 · Pages 워크플로 1 · `CLAUDE.md` 1 |

**파일은 73 % 줄지만 용량은 16.7 MB → 11 MB 다.** 빠지는 것 대부분이 발췌 제거 후 건당
300바이트인 거절결정 구조화 JSON 이고, 남는 용량의 대부분은 SIRP 메타 JSONL 하나다.
**이 정리는 용량이 아니라 신호를 줄인다.**

- **`docs/` 는 접두사 허용이 아니라 파일 열거다**(11건). 이 디렉터리가 스펙과 작업기록을
  함께 담아서, 접두사로 열면 다음에 쓰는 계획 문서가 조용히 따라 나간다. 기준은
  **온톨로지 스펙·큐레이션 방법은 공개 / 작업계획·실행결과 기록은 비공개**다.
- **`data/patents/rejection_decisions/`(442) 를 뺀다.** 수집과 A-Box 생성의 중심이 다른
  저장소로 옮겨 갔고 여기 남은 것은 초기 일부다. 읽는 테스트는 0건이었고, 읽는 스크립트
  넷은 함께 제외했다.
- **`notebooks/`(8) 를 뺀다.** 불완전한 데모이고, 실제 누출이 거기서 났다(노트북 07 출력).
- **SIRP 메타 JSONL 은 그대로 공개한다** — CR-015 가 (B) Link-Only 로 확정했고 검증기준 ③이
  거기 걸려 있다.

**빼는 것만으로는 부족했다 — 참조가 남는다.** 그래서 셋을 더 했다.

- **블록 마커** `sdkb:private-begin` … `-end`: 공개본에서 지울 *조각*을 표시한다(Makefile 의
  viz 타깃 · README 의 노트북/시각화 절 · 문서 색인의 없는 문서 안내). 마커는 **자기 줄에
  혼자** 있어야 인정한다 — 포함 검사로 만들었더니 마커를 *설명하는* docstring 이 마커가 되어
  빌드가 죽었다. `PRIVATE_TOKEN` 을 첫 줄에서만 인정한 것과 같은 이유다.
- **죽은 링크 평문화**: 공개본에 없는 파일을 가리키는 상대 링크는 **링크만 벗기고 문장은
  남긴다**(48건 · 8파일). 상류 원본은 손대지 않는다 — 거기서는 그 링크가 살아 있어야 한다.
- **표 행 삭제**: 행이 통째로 없는 문서를 소개하면 색인이 아니라 오답이므로 행째 뺀다.

**검사기에 셋을 더했다** — 허용목록 밖 파일 · 공개 Makefile 의 없는 스크립트 참조 · 공개
문서의 죽은 상대 링크. 전환 직후 실측은 **죽은 링크 60건**이었다. 목록은 파일을 빼 주지만
그 파일을 가리키던 문장은 빼 주지 않는다.

**게이트가 잡은 것 둘.** ① `scripts/sdkb_nb.py` 를 "노트북 헬퍼"로 보고 뺐더니 공개 트리
pytest 에서 **10건이 `ModuleNotFoundError` 로 죽었다** — `tests/` 셋이 임포트한다. 되돌렸고,
**이름이 아니라 누가 쓰는가로 판단한다**는 주석을 남겼다. ② 서명 블록 최신성 테스트가 공개
트리에서 거짓 실패했다(`sdkb-core.ttl` 은 gitignore 된 빌드 산출물이라 부재) — 전량 빌드가
아닐 때는 건너뛰게 고쳤다.

검증: 공개 트리 **184파일 · 11 MB** · 검사기 7종 전부 0 · 공개 트리 pytest **118 통과 ·
127 스킵 · 실패 0** · 상류 `make test` **235 통과 · 10 스킵** · SHACL 3종 PASSED.

### Changed (2026-08-10 — 어휘에 **주석 42개**를 더했다 · 점검 R5 · G5) ⚠ 하류 통보

**의미 델타 0 · 주석 델타 42.** 아래 다섯 T-Box 파일의 sha256 이 바뀐다. 바뀐 것은
`rdfs:comment` 트리플뿐이고, **클래스·술어의 수와 `rdfs:domain`/`rdfs:range` 는 한 개도
움직이지 않았다.** 스냅샷을 핀한 하류는 재측정할 것이 없다 — 그 확인을 위해 델타를 여기 적는다.

| 모듈 | 주석 보유 (전/후) | 트리플 (전/후) |
|---|---|---|
| `sdkb-patent.ttl` | 56/74 → **74/74** | 447 → 465 |
| `sdkb-commercialization.ttl` | 8/17 → **17/17** | 95 → 104 |
| `sdkb-foresight.ttl` | 8/16 → **16/16** | 99 → 107 |
| `sdkb-rbv.ttl` | 13/18 → **18/18** | 77 → 82 |
| `sdkb-governance-kr.ttl` | 5/7 → **7/7** | 58 → 60 |
| `sdkb-core.ttl` | 133/133 (불변) | 718 → 719 (아래 seeAlso) |
| **합계** | 226/268 → **268/268** | 1,534 → **1,577** |

- **결손이 가장 컸던 곳은 정렬 3모듈이 아니라 특허 모듈이었다** — 74항 중 18항. 그중
  `filingDate`·`publicationDate`·`rejectionDate` 는 서로 다른 사건인데 주석 없이 나란히
  있었다. `CLAUDE.md` §5-4 가 경고한 자리가 정확히 여기다.
- 방향이 이름에서 읽히지 않는 술어는 **어느 쪽이 주어인지** 적었다 — `ont:barrierOf` 는
  barrier → segment, `ont:scenarioDriver` 는 scenario → factor.
- **`rdfs:domain` 또는 `rdfs:range` 를 일부러 두지 않은 둘**(`ont:hasPriorArtApplicant` ·
  `ont:fundedBy`)은 그 이유를 주석에 적었다. 비어 있는 것과 뜻이 있어 비운 것은 다르다.
- `tests/test_graph_signature.py` 가 268/268 을 고정한다. **주석이 비어도 SHACL 은 통과하므로**
  이것을 잡는 층은 그 테스트뿐이다.

### Added (2026-08-10 — 그래프 서명을 **코드가 센다** · 점검 R4 · F4·F5)

`CLAUDE.md` §4 는 *"릴리스를 만들 때 그래프 서명을 CHANGELOG 에 남긴다"* 고 요구하는데
**그것을 이행하는 코드가 없었다.** 그래서 README 수치가 손으로 관리됐고, 원천이 2026-08-01 에
자란 뒤 넷이 어긋났다.

- **`scripts/report_graph_signature.py`** + `make signature` · `signature-inject` ·
  `signature-check`. 산출은 `data/reports/graph_signature.json`.
- **명명 클래스와 restriction blank node 를 분리해 센다.** `grep -c owl:Class` 는 둘을 합쳐
  `sdkb-patent.ttl` 을 22 로 보고한다 — named 는 16 이다. 둘 다 맞는 숫자지만 같은 자리에
  쓰면 틀린 말이 된다.
- **없는 층은 0 이 아니라 `not built` 로 적는다.** 0 이라고 적으면 외부인이 자기 빌드가
  실패했다고 읽는다. 같은 이유로 아무것도 빌드되지 않은 체크아웃에서는 `--inject` 가
  **README 를 덮지 않고 실패한다.**
- 899 MB `claim-features` 는 매번 재파싱하지 않고 생성기 리포트의 트리플 수를 읽는다
  (`triples_source: "report"`). 돌지 않는 절차는 절차가 아니다.
- README 두 판의 수치 자리는 **고치지 않고 없앴다** — 정본은 마커
  (`<!-- sdkb:signature:begin -->`) 안에서 코드가 쓴다. 덤으로 낡은 것 하나가 더 나왔다:
  `75 passed / 10 skipped · OWL 438 triples`.
- [`ontology_guide.md`](docs/ontology_guide.md) §2.1 표의 **ObjectProperty 총계가 93 으로
  틀려 있었다** — 모듈별 열은 처음부터 99 로 합산된다. 아무도 다시 더해 보지 않았다.

### Changed (2026-08-10 — 공개 리포 이름을 **한 곳에서** 정한다 · 점검 R3 · F3)

- **`config/namespaces.py` 의 `REPO_SLUG`.** 발행되는 `rdfs:seeAlso`·`CITATION.cff`·BibTeX·
  GitHub Pages 링크가 전부 여기서 조립된다. 흩어져 있던 곳은 TTL 한 줄이 아니라 **추적 파일
  12곳**이었고, 그중 7곳이 Pages 라이브 데모 URL 이었다.
- 공개 대상 리포는 **`arkwith7/sdkb-dataset`** 으로 확정. 옛 슬러그는 지우지 않고
  `config/namespaces.py` 의 `LEGACY_REPO_SLUG` 에 남긴다 — 검사기가 재유입을 잡는 데 쓴다.
  (이 항목이 그 슬러그를 문자 그대로 적지 않는 이유는 아래 넷째 검사에 걸리기 때문이다.
  **검사기가 이 CHANGELOG 초안을 실제로 잡았다.**)
- `sdkb-core.ttl` 의 `seeAlso` 는 이제 **둘**이다: `docs/ontology_guide.md`(1차) ·
  `docs/project/architecture_amendment_sdkb_centric.md`(2차). **앵커가 아니라 파일**을
  가리킨다 — 제목이 바뀌면 앵커는 조용히 깨진다.
- `check_public_release.py` 가 옛 슬러그를 넷째 검사로 잡는다. **첫 실행에서 스스로 한 건을
  잡아냈다**: 그 문자열을 *정의하는* `config/namespaces.py`. 인용 허용 목록은 코드에 두고
  사유를 적는다 — 파일이 스스로 면제를 선언하게 하면 검사가 아니라 우회로가 된다.
- `decompose_corpus.py` 처럼 `build_viz.py` 도 리포 링크를 하드코딩하지 않는다.

### Added (2026-08-10 — 공개 문서에 영문 요약 · 점검 R6 · F6)

- 한국어 중심 5문서 머리에 영문 요약을 넣었다 — 데이터셋 카드 · 전체 수집 runbook · canonical
  스키마 · KIPRIS 소스 매핑 · 비식별 프로토콜.
- 열 이름 병기는 **언어와 무관한 사실을 담은 표에만** 걸었다(6개 헤더). **runbook 의 운영
  표는 한국어로 남겼다** — KIPRIS/KIPO 화면과 양식의 이름이 한국어여서 옮기면 절차를
  따라가기가 더 어려워진다. 그 판단을 요약에 적었다. 전량 번역은 하지 않았다.

### Added (2026-08-09 — 공개 경계를 원문에서 **문서와 경로**로 넓혔다 · 점검 R1·F7)

- **비공개 문서 토큰 `<!-- sdkb:private -->`.** 첫 줄에 이 토큰을 단 파일은 공개 트리에
  복사되지 않고(`build_public_release.py`), 트리에 남아 있으면 검사기가 거부한다
  (`check_public_release.py`). **첫 줄에서만** 인정한다 — 본문에서 토큰을 언급하는 문서는
  그것을 *설명*하는 것이지 *선언*하는 것이 아니다.
  - 자연어 마커(`CONFIDENTIAL` 등)를 쓰지 않은 이유는 실측이다: 그 낱말이 걸리는 추적 파일
    7건이 **전부 정상 문서**였다. 기밀을 담은 문서와 기밀을 논하는 문서를 가르지 못하는
    검사기는 무시된다.
  - 두 층인 이유: 생성기만 있으면 **손으로 만든 트리**를 못 잡고, 검사기만 있으면 매번 사람이
    지워야 한다. 되돌릴 수 없는 경로라 거르는 층과 확인하는 층을 나눴다.
- **홈 절대경로 검사.** 공개 트리에 사용자 홈으로 시작하는 파일시스템 경로가 남으면 실패한다.
  URL 경로 안의 같은 문자열은 잡지 않는다 — 실측으로 둘 있었다(`irds.ieee.org/home/…` ·
  `horiba.com/kr/horiba-stec/home/`). 실행 리포트와 거절결정 인덱스는 복사 시 경로를
  **파일명으로** 줄인다(어떤 파일을 읽었는지는 남긴다).

### Changed (2026-08-09 — 공개 스크립트가 하류 저장소를 읽지 않는다 · 점검 F7)

- **`decompose_corpus.py` 의 외부 코퍼스는 경로를 인자로 받는다** — `--g1-ttl`·`--g2-ttl`.
  두 소스는 옆 저장소의 절대경로를 하드코딩하고 있었고, 그 경로가 없는 사람에게 이 진입점은
  그냥 깨진 스크립트였다. 경로 없이 `--source g2` 를 지목하면 **무엇을 줘야 하는지 적고
  실패**한다.
  - **`--source all` 의 의미가 바뀌었다**: 저장소 내부 3종(rejected·cited·b_queries)은 항상
    돌고, 외부 소스는 **경로가 주어진 것만** 돈다. 건너뛴 것은 한 줄로 출력한다 —
    조용한 스킵이 아니라 말하는 스킵이다. **산출은 불변**(`claim_features.jsonl`
    sha256 `8c8287ef…` 재실행 전후 동일).
  - docstring 에서 하류 코퍼스 구획 이름(`G1(삼성·SK하이닉스)`·`Tier 1/2/3`)을 뺐다.
    **§29②·all-elements 같은 법·도메인 근거는 남겼다** — 공개 가능한 지식이다.
- **`.env` 폴백에서 하류 경로를 지웠다** (`enrich_kipris_biblio.py`·`llm_claim_validate.py`·
  `collect_cited_biblio_claims.py`). 이 저장소의 `.env` 만 본다.
- 하류 저장소 이름·홈 절대경로를 문서·주석·테스트에서 제거했다
  (`add_superordinate_concepts.py` docstring · `test_b_layer_query_nodes.py` 는
  `SDKB_B_QUERY_IDS` 환경변수로 받고 없으면 skip · `prior_art_ontology_gap_and_data_plan.md`).

> **남은 것(F8).** `data/patents/rejection_decisions/_index.jsonl` 11행의 `pdf_path` 가
> 여전히 홈 절대경로다. **생성기는 이미 상대경로로 쓴다** — 과거 실행이 남긴 데이터 잔재이고,
> 정규화하려면 원천 트리가 있어야 한다. 공개본에서는 위 스크럽이 막는다.

### Fixed (2026-08-09 — CR-016 성공기준 ① · 빈 체크아웃에서 처음 드러난 것 넷)

**공개 트리를 실제로 격리해 `make pipeline` 을 돌려 봤다.** 넷이 걸렸고, 넷 다 **개인
컴퓨터에 옆 저장소가 있어서 우연히 통과하고 있던** 것들이다.

- **`validate` 가 `pipeline` 이 만들지 않는 A-Box 를 요구했다.** 두 TTL 은 gitignore 된
  빌드 산출물인데 파일이 없으면 검증기가 종료하고, **T-Box 재현까지 함께 막혔다.**
  고친 방향은 **건너뛰기가 아니라 짓기**다 — 이 둘은 자격이 필요 없다(커밋된 원천에서
  만든다). 없을 때만 `abox`·`abox-patents` 를 부른다. 검증은 한 칸도 느슨해지지 않았다.
- **개인 홈 절대경로 열둘을 끊었다.** `reextract_claim_judgments.py` 일곱 ·
  `llm_claim_validate.py`·`collect_cited_biblio_claims.py` 의 `.env` 순서(이 저장소를
  **먼저** 본다 — 앞서는 없는 남의 경로가 1순위라 자격이 조용히 비었다) ·
  `build_b_layer_cited_ids.py`·`collect_b_layer_queries.py` 의 기본 목록 경로.
- **테스트 여덟이 커밋되지 않은 입력에 의존하고 있었다.** B층 식별자 목록 일곱은 논문
  평가자산(§10.3 비공개)이고, `concept_mapping` 결정성 하나는 `cited_enriched/`(수집분)를
  읽는다. **입력이 없으면 물을 수 없는 질문이므로 건너뛰되, 무엇이 없어서인지 말한다.**
  비공개 리포에서는 목록 파일을 제자리에 두어 **215건 전량이 그대로 돈다**(파일은
  gitignore — 공개 트리 생성기가 `git ls-files` 만 복사하므로 공개본에 새지 않는다).
- **실측**: 빈 체크아웃 `make pipeline` **완주**(152 통과 · 73 스킵 — 스킵은 전부 자격·
  수집분 미비) · 비공개 리포 **215 통과 · 10 스킵** · SHACL **3/3** ·
  공개 트리 검사기 **파일 692 · 적중 0**.

### Added (2026-08-09 — CR-015 · 공개본 경계 · (B) 확정 · 하류 D-36)

- **원고와 리포가 서로 반대였다.** 원고 §10.3 은 *"KIPRIS 원문은 재배포할 수 없다"* 고
  쓰는데 이 저장소는 초록 전문·청구항 전문을 커밋하고 있었다. **심사자가 §10.1 의 URL 을
  누르면 그대로 드러나고, 그때 문제가 되는 것은 라이선스가 아니라 원고의 신뢰성이다.**
- **§6 (B) 확정 — 법무 자문을 기다리지 않는다.** 이전 판은 자문 후 (A)/(B)/(C) 택일로
  적혀 있었으나 **그 전제는 다른 사업 맥락의 것이었다.** 그리고 자문이 필요 없는 이유가
  따로 있다 — **결정은 이미 원고 §10.3 에 있다.** 리포를 그 문장에 맞추는 것은 법적
  판단이 아니라 정합성 작업이다.
- **`scripts/build_public_release.py`** — 공개할 트리를 매번 코드가 만든다.
  `abstract`·`claim1`·**`claims_full[].text`** 를 **빈 문자열**로 두고 스키마·`claim_no`·
  `depends_on`·식별자·IPC·날짜·`ground_truth_*` 는 남긴다. **실측: 행 1,000 · 초록 1,000 ·
  claim1 1,000 · claims_full 텍스트 13,685 · 파일 10.2 MB → 4.1 MB.**
  **`claims_full` 은 이번 조사에서 처음 범위에 들어왔다** — CR 초판은 초록·claim1 만
  열거했는데 실측하니 그 필드가 **원문 총량의 77 %** 였다.
- **노출 경로는 하나가 아니었다.** 노트북 셀 출력이 초록 발췌를 인쇄하고 있었다
  (07). 파일명을 보고 찾은 것이 아니라 **지문 3,132개로 커밋 전량을 훑어** 나왔다.
  생성기가 노트북 출력을 함께 제거한다(5개 노트북 · 21셀).
- **`scripts/check_public_release.py` — 푸시 전에 서는 검사기.** 비공개 정본에서 뽑은
  지문으로 공개 트리 전량을 훑는다. **첫 실행에서 2건이 걸렸고 조사해 보니 누출이 아니라
  `title` 이었다** — 초록이 제목을 되풀이해 시작하는 특허가 있었다. 임계를 낮추는 대신
  **남기는 필드와 겹쳐 판별력이 없는 지문을 제외**하고 **버린 개수를 리포트에 적는다.**
  **재실행 실측: 지문 3,341개 · 파일 689개 · 적중 0.**
- **되돌릴 수 없는 단계는 자동화하지 않았다.** `make public-release` 는 트리까지만 만들고
  푸시하지 않는다. 공개된 커밋은 지워도 포크·캐시·PR ref 로 남는다.
- **회귀 테스트 7건**(`tests/test_public_release.py`) — 값만 비는가 · 청구항 구조가 남는가 ·
  서지와 정답이 그대로인가 · **검사기가 실제로 잡는가**(통과만 확인하면 항상 통과하는
  검사기도 통과한다) · 겹치는 지문을 버리는가.
- **문서 둘 갱신** — `dataset_rejected_patents_card.md` §6 (B) 확정 + §7-1 #1 해소 ·
  `docs/project/dataset_publication_risk_review.md` 재판정(§0-0 신설 · 체크리스트 9항 중
  6항 닫힘 · 열린 셋은 전부 원고 소관 · **#2 는 "문서 반영 ✅" 라 적어 놓고 미체크였던
  표기 오류**였다).
- **테스트 215 통과 · 10 스킵 · SHACL 2/2 통과.** T-Box·A-Box·트리플 수 불변.

### Added (2026-08-09 — CR-016 §2 · 빌드 진입점 · CQ 스위트 · 재현 안내 · 하류 D-37)

- **없던 진입점 넷을 만들었다.** `abox-prior-art` · `abox-claim-features` ·
  `refetch-fulltext` · `cq`(+ 묶음 `abox-full`). 앞의 두 생성기는 2026-05 부터
  `scripts/` 에 실재했는데 **Makefile 에 타깃이 없었다** — 손으로 `python scripts/…` 를
  치는 사람에게만 존재하는 빌드였고, 산출 TTL 둘은 gitignore 라 외부인에게는 그 층이
  통째로 없는 것과 같았다. **비워 두고 채우는 방법을 주는 설계는 채우는 명령이 있어야
  성립한다.**
- **두 타깃을 `pipeline` 계보에 걸지 않았다.** 입력이 네트워크 수집분이라, 키 없는
  체크아웃에서 pipeline 이 죽으면 **T-Box 재현까지 함께 막힌다.** 자격이 필요한 경로는
  이름을 따로 준다.
- **CQ 스위트 31건을 여기로 들였다** (`queries/cq/` · `make cq` · `scripts/run_cq.py`).
  CQ 는 평가 하네스가 아니라 **온톨로지가 무엇에 답하는가의 명세**이므로 도메인 자산이다.
  하류 논문 저장소에만 있으면 원고가 *"CQ 스위트를 공개한다"* 고 쓴 문장이 거짓이 된다.
  **판정은 존재검사뿐**(`rows ≥ expect-min`)이고 분포검사는 하류 게이트(T3)의 몫으로
  남긴다 — 같은 이름의 다른 판정을 만들면 두 통과율을 대조할 수 없다.
  **실측**: `em 6/6 = 1.000` · `tf 5/5 = 1.000` · `core 12/12 = 1.000` — **하류 T3 값과
  일치한다.** `pa 4/8` 의 미달 넷(CQ27·29·30·31)은 899 MB 청구항 feature A-Box 를 요구하며
  기본 조합에서 제외돼 있다(rdflib 인메모리로 감당 불가). 리포트의 `graph_files_missing`
  이 그것을 이름으로 적는다 — **실패가 "온톨로지가 깨졌다"가 아니라 "무엇을 더 지어야
  하는가"를 가리키게 한다.**
- **`scripts/refetch_rejected_patents.py`** — 비운 원문을 KIPRIS 에서 다시 채운다.
  **추출 규칙을 새로 쓰지 않고** 원 수집기의 함수를 호출한다(`_abstract_from_biblio` ·
  `_claim1_from_biblio` · `_extract_claims_full`). 규칙이 갈리면 복원본이 정본과 달라진다.
  판정은 **sha256 대조**(`fc142f51…`)이고, 초록 원천 차이(`astrtCont` ↔ 서지 폴백)로
  어긋날 수 있음을 모듈 docstring 에 **미리 적었다** — 어긋나면 어긋난 대로 리포트한다.
- **README 에 "무엇이 비어 있고 어떻게 채우는가" 표**(국·영문). 층 · 비어 있는 것 · 왜 ·
  채우는 명령 · **필요한 자격** 5열. 결손 고백이 아니라 **설계의 진술**이다.
- **`sync_paper_data_assets.sh` 삭제** — 동기화할 대상이 없다(§4 흡수 완료).
- **조용한 절대경로 둘을 더 끊었다.** `decompose_corpus.py` 가 인용 보강분을 **옆
  저장소에서** 읽고 있었다(`PD = ~/Dev/paper_data`). 흡수된 수집기는 이쪽으로
  쓰므로 원천이 둘이 될 뻔했다 — 교체 전에 대조했고 읽는 5파일이 **바이트 동일**이라
  산출은 바뀌지 않는다. `collect_cited_biblio_claims.py` 의 절대경로도 상대로 바꿨다.
- **테스트 208 통과 · 10 스킵 · 실패 0.** T-Box·A-Box·트리플 수 불변.

### Changed (2026-08-09 — CR-016 §4 · paper_data 재현 경로 흡수 · 하류 D-38)

- **SDKB 가 단독으로 선다.** 데이터셋을 만들고 채우는 수집·재현 자산을 비공개 저장소
  `paper_data` 에서 **옮겨 왔다**(복사가 아니라 이관 — 사본을 남기지 않았다).
  `scripts/kipris_dataset/` 6파일(KIPRIS 클라이언트·인용 정규화·코호트·거절결정 파서) ·
  수집 스크립트 **13개** · 문서 **6건**.
- **왜 지금인가.** 논문 투고와 함께 이 저장소가 공개되는데, 비운 A-Box 를 채우는 절차가
  개인 로컬 디렉터리(`~/Dev/paper_data`)를 거치면 **외부인은 재현할 수 없다.**
  의존(pinned dependency)이 아니라 흡수를 택한 근거는 독립성이다.
- **사본 넷을 정리했다 — 그중 하나는 이미 갈라져 있었다.**
  `device_alias_table.json` 이 이쪽 **34키** 대 저쪽 **31키**로 갈렸고 빠진 셋
  (`device:diode`·`device:eprom`·`device:feram`) 중 `device:eprom` 은 하류 코퍼스의
  최빈 개념(df 5,146)이다. **저쪽 판으로 재구성했다면 논문이 조용히 재현되지 않았다.**
  이쪽 판을 정본으로 남긴다. 공통 31키의 값은 **완전히 동일**이라 데이터 변화는 0.
  `wikidata_device_classes.jsonl` 은 두 판이 **바이트 동일** ·
  `prior_art_ontology_gap_and_data_plan.md` 는 이쪽 판(273행)이 최신.
- **`citation_norm.py` 정본 통합 — 동작은 바뀌지 않는다.** 두 판의 차이는 **docstring
  참조 한 줄**뿐이었다(코드 동일). 따라서 `cited_doc_id` 정규화는 그대로이고 하류 qrel
  매칭에 영향이 없다. 사본을 지우고 `scripts/kipris_dataset/citation_norm.py` 하나만
  남겼으며, 임포터 둘(`build_b_layer_cited_ids.py`·`ingest_rejected_patents.py`)을 고쳤다.
  깨진 문서 참조는 함께 옮긴 `docs/legacy_etching_poc_schema.md` 로 해소된다.
- **조용한 외부 의존 하나가 드러나 함께 끊었다.** `collect_b_layer_queries.py`(CR-012 의
  B층 질의 수집기)가 `sys.path` 에 `~/Dev/paper_data` 를 끼워 넣고
  `enrich_unresolved.py` 를 임포트하고 있었다 — **커밋된 스크립트가 커밋되지 않은 파일에
  의존**하는 형태였고, 그대로 공개했으면 외부에서 `ImportError` 로 죽었다.
  `enrich_unresolved.py`(982행)도 이관 대상에 넣었다.
- **경로 상수는 고치지 않았다.** 이관된 수집기는 원 저장소 레이아웃(`data/processed/`)을
  그대로 쓰고, 그 디렉터리를 gitignore 에 넣었다. 고쳐 쓰면 **수집 규칙이 갈려 재인출본이
  정본과 달라진다** — 복원 대조(sha256)를 무의미하게 만드는 변경이다.
- **T-Box·A-Box·트리플 수·IRI 규칙 전부 불변.** 테스트 **208 통과 · 10 스킵 · 실패 0**.
- **하류 영향(§0)**: 없음 — vendor 대상 파일이 하나도 바뀌지 않았다.

### Added (2026-08-08 — CR-014 · B층 질의의 서지 두 칸 · 하류 D-31)

- **공개번호·공개일을 채웠다 — 200/200.** `ont:publicationNumber` 200 ·
  `ont:publicationDate` 200. `sdkb-abox-b-layer-queries.ttl` 트리플 **4,204 → 4,604**
  (+400 · B층 200 노드의 속성 추가분뿐). A층 1,000 · T-Box · IRI 규칙 · 파일 분리 구조
  **전부 불변**이고 인용 간선은 여전히 **0** 이다.
- **값은 `openNumber` 이지 `publicationNumber` 가 아니다(§1.3).** KIPRIS 응답에도
  `publicationNumber` 필드가 있는데 그것은 **공고번호**이고, 거절특허는 등록되지 않아
  **전량 `null`** 이다. A층의 `ont:publicationNumber` 는 SIRP `biblio.unex_pub_number`
  (= **공개번호** · `10-2022-0148249` 형식)이므로 같은 의미의 칸은 `openNumber` 다.
  이름만 보고 골랐으면 칸은 비고 값은 A층과 다른 것을 담았을 것이다. 형식(`10-YYYY-NNNNNNN`)과
  **공개일 ≥ 출원일**을 테스트가 고정한다.
- **`processFamily`·`valueChainStage` 는 채우지 않았다 — 이것이 이 CR 의 결론이다.**
  A층의 두 값은 특허의 속성이 아니라 **SIRP 코호트의 수집 출처**다. 원천은 KIPRIS 가
  아니라 *"어느 검색 전략(키워드 게이트+IPC)이 그 특허를 건졌는가"* 이며
  (`meta.search_strategy='plasma_H01J37' → process_family='etch'`), B층 200 은 하류가
  **다른 절차**(IPC 스트림 스크리닝)로 뽑아 그 라벨이 존재하지 않는다. A층 parquet ·
  SIRP 원본과의 교집합도 **0 건**이라 조인으로 가져올 수도 없다.
  **추정 충전을 거부한 이유는 둘이다.** ⓐ 같은 이름의 다른 것이 된다(§1.3).
  ⓑ 하류 T2 하위집단이 **"공정군"으로 갈리므로**, A층은 검색전략 라벨 · B층은 IPC 추론
  라벨이 되면 T2 가 서로 다른 규칙으로 만든 층을 같은 축으로 비교하게 된다 — **비어 있는
  것보다 나쁘다.** 못 채운 이유는 리포트
  (`data/reports/abox_b_layer_queries_report.json` → `cr014_bibliographic`)에 수치와 함께
  남는다. 빈 것을 조용히 비워 두지 않는다.
- **수집기는 백필한다.** 캐시에 있어도 두 필드가 **없으면** 다시 받는다(필드 존재 여부로
  판단 — 빈 값으로 판단하면 정말 값이 없는 건이 매번 200 콜을 되살린다). 백필 후 JSONL 을
  이관 파일 순서로 다시 써 **같은 입력 → 같은 파일**을 유지한다.
- **하류 영향(§0)**: `sdkb-prior-art-paper` — 재 `make vendor` 로 위반 **600 → 400**.
  남는 400 은 위 두 칸이고, 하류가 `prov:wasGeneratedBy activity/b_layer_query_ingest`
  를 조건으로 한 `sh:or` 로 면제한다(CR-012 가 인용 `minCount` 에 쓴 패턴과 같다 —
  A층 1,000 에 걸린 계약은 풀리지 않는다). `SDKB-Match`·공개 사이트: **영향 없음**.

### Added (2026-08-08 — CR-012 · B층 확증분할 질의 200건 · 하류 D-27)

- **질의 200건을 별도 A-Box 파일로 세웠다** — `ontology/sdkb-abox-b-layer-queries.ttl`
  (신설 · **gitignore**). `ont:Patent` + `ont:RejectedPatent` 200 · 트리플 **4,204**.
  IRI 는 A층과 같은 규칙 `data:patent/kr_{출원번호}` 이고, 이관 목록 200 과
  **정확히 일치**한다(초과 0 · 누락 0). A층 질의 1,000 과 교집합 **0**.
- **왜 별도 파일인가.** ⓐ CR-012 요구 ⓑ(층 구분)를 **새 술어 없이** 주는 형태이고
  (**T-Box 델타 0** · 새 클래스 0 · 새 술어 0 · IRI 규칙 변경 0), ⓑ 이 저장소는
  **공개되는 기반 온톨로지**인데 이 200건은 반도체 도메인 지식이 아니라 **하류 논문
  확증분할의 봉인 질의**다. 도메인 자산과 같은 파일에 섞으면 공개본을 정리할 때 다시
  갈라내야 한다. 원문(`data/patents/b_layer_queries_raw.jsonl`)도 같은 이유로
  gitignore 다 — KIPRIS 비재배포 조건이기도 하다(§1.5).
- **인용 간선 0.** `hasPriorArtExaminer`·`hasPriorArt`·`overPriorArt` **전부 0**
  (생성기가 직접 세고 0 이 아니면 **중단**한다). 상류에 실으면 하류 봉인 qrel
  `127a138f…` 이 그 자리에서 무의미해지기 때문이다(CR-012 비목표 ⓐ).
- **`Shape_RejectedPatent` 을 고쳤다 — 느슨하게가 아니라 예외에 이름을 붙였다.**
  이 shape 은 거절특허마다 심사관 인용 ≥1 을 요구하는데, CR-012 는 그 인용을 싣지
  말라고 요구한다. **둘 다 옳다.** `minCount` 를 낮추면 A층 1,000 에 걸린 계약까지
  풀리므로, `sh:or` 로 **출처(`prov:wasGeneratedBy activity/b_layer_query_ingest`)를
  가진 노드만** 면제했다. 그 출처를 붙일 수 있는 것은 생성기 하나뿐이라 손으로는
  얻을 수 없다. **음성 대조로 확인** — 무인용·무출처 거절특허는 여전히 **거부**된다
  (`tests/test_b_layer_query_nodes.py::test_negative_control_still_fails`).
- **수집은 KIPRIS 직행 조회다.** 하류 이관 파일이 출원번호를 그대로 주므로 CR-008 이
  겪은 번호 해소 단계가 없다. **200/200 전량 확보** — 청구항 200 · 초록 200 · 출원일
  200 · IPC 200 · 심사상태 200 · 미해소 **0**. 이관 파일 sha256 `ef4ad03c…` 는
  경고가 아니라 **중단** 조건이다.
- **권위 원천 대조(§1.3).** 하류가 "거절특허 200"이라고 말한 것을 상류가 KIPRIS 에서
  독립 확인했다 — `registerStatus` **200/200 전부 `거절`**. 어긋나면 `RejectedPatent`
  타입 자체가 거짓이 되므로 빌드가 중단하도록 했다.
- **청구항은 A층과 같은 분해기·같은 모델로 갈랐다** — `ollama qwen3-coder:30b`
  (CR-011 과 동일). B층 질의 **2,618 청구항 → 5,962 feature**(규칙 2,365 · LLM 253).
  pid 접두를 A층과 같은 `rej:` 로 두어 `build_abox_claim_features.py` 의 IRI 해소를
  **한 줄도 고치지 않았다**.
- **정직하게 남는 것 둘.**
  ① **청구항은 파일로 갈라지지 않는다** — 하류가 질의 본문을 읽는 경로가 중심축
  `sdkb-abox-claim-features.ttl` **한 파일**이라, 질의 노드는 갈라져도 feature 는 A층과
  섞인다. 하류는 B층 파일의 IRI 목록으로 거를 수 있으나, 공개본 정리 때 중심축에서
  200건을 빼는 작업은 남는다.
  ② **개념 링크가 A/B 비대칭이다** — A층은 큐레이터의 `process_family` 구조화 브리지 +
  자유텍스트 두 통로를 쓰는데 KIPRIS 에는 전자의 입력이 없다. **추정해서 채우지 않았다**
  (§1.3). 자유텍스트만 적용한 결과 문서당 개념 **1.105**(A층 2.909) · 링크 보유
  **117/200**(A층 977/1,000). **원인이 온톨로지 결함인지 질의 화제의 차이인지 가르라고
  IPC4 분포를 같은 리포트에 함께 실었다** — A층 C23C 20.7 % 대 B층 7.3 % ·
  A층 H01L 14.8 % 대 B층 **0.0 %** · B층에는 A층에 없는 B23K 10.9 %·C22C·C04B 가 있다.
  즉 **두 층은 화제가 실제로 다르다.** 하류가 확증분할의 교환가능성을 판단할 재료다.
- **불변**: `build_abox_patents.py`·`build_abox_claim_features.py` **변경 0** ·
  A층 질의 1,000 · T-Box 전량 · `sdkb-abox-patents.ttl` sha256 `974899fa…` 불변.
- **의존성 선언 둘 추가** — `xmltodict`·`python-dotenv`. CR-008·CR-011 이 이미 이 경로로
  수집하고 있었으나 선언이 없었다. `requests` 와 같은 종류의 누락이다(하류 D-24).
- **하류 영향(§0)**: `sdkb-prior-art-paper` 는 **새 파일을 `VENDOR_FILES` 에 추가**해야
  한다(코드 변경 → 하류 §2 전체 · §2.1 적용 불가 — CR-012 §8 이 이미 예고한 그대로).
  `SDKB-Match`·공개 사이트: **영향 없음** — 기존 파일이 하나도 바뀌지 않았다.

### Changed (2026-08-07 — CR-013 · 원소 기호 별칭의 정밀도 · 하류 D-20)

- **`patent-text` 프로파일에서 표면형 둘을 뗐다.** 단독 `hf` → `material:hf_acid`
  **제거** · `high k` → `material:hfO2` **분리 후 상위 부류 `material:dielectric`
  로 재지정**. `patent-text` 쌍 653 → **652** · 표면형 636 → **635**.
  **`expert-tag` 는 entries·blocked·concept_meta 전량 불변**(테스트가 단정).
- **재지정이 아니라 제거인 이유.** 하류가 원문 대소문자를 셌다 — 단독 `hf` 링크
  1,245 문서 중 `Hf`(하프늄) 736 · **`HF`(불산) 488** · 둘다 21. 사전 적용은
  `.lower()` 정규화 위에서 돌므로(R1) 이 표면형은 **사전 층에서 원리적으로 갈리지
  않는다.** `hfO2` 로 재지정하면 488 문서에 반대 방향 오링크가 생긴다.
  **대소문자 민감 표면형이나 새 스키마 필드를 발행하지 않았다** — 하류 적용기가
  읽지 못한다(하류 D-28 · 소관 하류).
- **`R6-SURFACE-SUPPRESS` 신설** — Tier-1 표면형을 **프로파일 단위로** 끈다.
  원천(`data/semiconductor_v0_3.json` synonyms)에서 지우면 두 프로파일과
  `skos:altLabel`·A-Box 추출이 함께 움직이므로, 끄는 자리를
  `mappings/abox_term_aliases.json` 의 `_suppress_tier1_surface` 로 뒀다.
  **끈 쌍은 `profiles[*].blocked` 에 남는다 — 지운 것이 아니라 옮긴 것이다**
  (`patent-text` blocked 6 → **8**).
- **A-Box 는 원문 대소문자로 갈랐다(상류만 가능).** `scripts/sdkb_nb.resolve_hf_case`
  — `HF` 만 있으면 불산으로 남기고, `Hf`·혼재·판별불가는 뗀다. **하프늄 링크를 새로
  만들지 않는다**(오링크의 방향만 뒤집는 일이 되므로).
  `sdkb-abox-patents.ttl` 33,937 → **33,931**(−6 · `involvesMaterial` 526 → **520**) ·
  `sdkb-abox-prior-art.ttl` 66,453 → **66,440**(−13 · `involvesMaterial` 1,580 → **1,567**).
  **제거 19 · 추가 0**(트리플 집합 차로 증명) · 릴리스 A-Box 의 `hf_acid` 링크
  **34 → 15**(patents 8 → 2 · prior-art 26 → 13).
- **T-Box·IRI·어휘 불변.** `sdkb-core.ttl`·`sdkb-core-data.ttl` sha256 불변 ·
  어휘 신설 0 · 클래스/술어 델타 0. 상위 부류 `material:dielectric` 는 CR-007 이
  이미 만든 노드다(`props.lexicon_profile = patent-text`).
- **하류 영향 (§0)**: `sdkb-prior-art-paper` 는 스냅샷 서명이 바뀌므로 §2.1
  (정지 게이트 1 개) 경로로 전량 재측정한다. **`high k` 재지정은 하류가 동결하려던
  검증기준 ⑤(고유 (doc,concept) 쌍 예측값)를 무효로 만든다** — 그 예측은 순수
  제거를 가정한 값이었다. 하류는 사전등록 동결 전에 ⑤ 를 재산출해야 한다.
  `SDKB-Match`·공개 사이트: 개념 링크 19 건 감소 외 영향 없음.
- 자산 sha256 — `mappings/concept_mapping.json` **`cdf5fa5d…`** ·
  `mappings/abox_term_aliases.json` **`9c8bbeb2…`** ·
  `ontology/sdkb-abox-patents.ttl` **`974899fa…`** ·
  `ontology/sdkb-abox-prior-art.ttl` **`e96d9873…`**.

### Added (2026-08-06 — CR-011 · B층 인용 선행기술의 청구항 ClaimFeature 분해 · 하류 D-26)

- **B층 인용 문헌 284건의 청구항을 A층과 같은 사이드카 형식으로 발행했다.**
  `ont:hasClaim` → `claimNumber`·`isIndependent` → `hasFeature` → `featureSeq`·`featureText`.
  `Claim` 586,567 → **591,460** · `ClaimFeature` 1,289,512 → **1,300,457** ·
  트리플 11,625,171 → **11,718,456**.
- **성공 기준 판정.** ① B층 KR 분해율 **235/235 = 1.0000**(청구항 3,905건) ·
  ② US **49/49 = 1.0000**(1,014건 · 본문 자체가 없는 `US-P-03517643`·`US-P-03530092` 는
  분모 제외 · 하류 §1.6a) · ③ **A층 불변** — claim/feature IRI 1,875,867 개 전량 존속,
  사라진 IRI **0**(집합 연산 검증). ④ 하류 재 vendor 후 코퍼스 확보율은 **하류가 잰다**.
- **원인은 발행 형식 하나가 아니었다 — 분해 자체가 안 돌아 있었다.** 하류 CR 은 청구항이
  `ont:claimText` 로만 있어 형식이 다르다고 진단했으나, 상류 실물은 그 앞 단계였다:
  ⓐ `decompose_corpus.py::src_cited()` 의 원천 목록에 B층 parquet 이 없었고(US 49건 미도달),
  ⓑ `kipris.jsonl` 이 CR-008 로 커진 뒤 재실행되지 않아 KR 235건 중 **2건만** 분해돼 있었다.
  하류가 관측한 **B층 KR 0.0085 = 2/235** 가 정확히 그 2건이다.
- **`build_abox_claim_features.py` 의 `cited:` IRI 해소에 B층 모집단 맵을 병합**했다.
  B층 문헌은 `prior_art_edges.parquet` 에 없어(CR-008 비목표 ⓒ) 503건 중 **3건만** 기존 맵에
  잡혔고, 나머지 500건은 `patent_unresolved` 로 조용히 버려지고 있었다.
  병합은 `setdefault` — **같은 키에서 A층 값이 이긴다**(성공기준 ③의 구조적 보장).
- **A층과 같은 분해기·같은 모델을 썼다.** 규칙 분해 + flag 시 LLM(`ollama qwen3-coder:30b` ·
  캐시 키가 모델명을 포함하므로 A층 4,117건과 동일 모델임을 캐시 대조로 확인). B층 신규
  4,903 청구항 중 LLM 채택 **506건(10.3 %)** 으로 A층 `cited` 축의 10.1 % 와 사실상 같다.
  **다른 모델을 쓰면 사이드카 안에서 A층/B층이 비균질해진다** — CR-011 이 하류 폴백을 거부한
  이유가 그것이므로, 같은 이유가 상류에도 적용된다.
- **손실 리포트 신설** — `data/reports/b_layer_claim_decomposition_loss.json`.
  관할별 분해율 + 청구항 문자열은 있으나 분해되지 않은 문헌을 **건별로**. 현재 **0건**.
- **비목표는 지켜졌다.** `ont:claimText` 삭제 0 · T-Box 불변 · 새 술어 0 · 새 클래스 0 ·
  인용 간선(`hasPriorArtExaminer`·`hasPriorArt`·`overPriorArt`) 0 · JP 167건은 손대지 않았다
  (D-05 상한 · 분모에도 넣지 않는다) · 청구항 번역 없음.
- **결정적·멱등.** 두 번 돌려 산출 TTL sha256 동일(`1b4c143d3da63bb4…`).

### Fixed (2026-08-06)

- **`pyproject.toml` 에 `requests` 선언**(하류 대장 **D-24** 해소). `llm_claim_validate.py:22` ·
  `enrich_kipris_biblio.py:32` 가 이미 임포트하고 있었으나 선언이 없어, 청정 환경에서 LLM 분해
  경로가 **임포트 단계에서 죽었다.** CR-011 구현이 실제로 여기서 막혔다.
- **LLM 캐시를 매 건 커밋한다**(`llm_claim_validate.py`). 이전에는 500건 주기라, 로컬 30B 모델
  실행 중 장비가 내려가자 **한 시간치가 통째로 유실**됐다. 캐시 내용도 반환값도 바뀌지 않고
  **내구성만** 바뀐다 — 재개는 캐시 적중으로만 가능하므로 커밋이 곧 체크포인트다.
- **손실 리포트의 결측 판정**(`build_abox_claim_features.py`). parquet 결측은 float `nan` 이고
  **`nan` 은 참**이라 `str(v or "")` 가 `"nan"`(3글자)을 내어, 결측이 "청구항 있음"으로 둔갑해
  JP 19건이 미분해로 **잘못** 계상됐다. 분모를 부풀리는 방향의 오류라 없는 손실을 하류에
  보고할 뻔했다. `pd.isna` 검사로 교정하고 회귀 테스트로 고정했다.

### Added (2026-08-04 — CR-009 · 개념별 df·일반성 메타 발행 · 하류 D-23)
- **`mappings/concept_mapping.json` 스키마 1.0 → 1.1.** 프로파일마다
  `concept_meta` 신설 — `df_denominator` + 개념별 `df_abox`·`depth`·`is_superordinate`.
  **`entries`·`blocked`·`rules` 는 값·순서 전부 무변경**(추가만 · 회귀 테스트로 고정).
- **분모 4,513** = SIRP 거절특허 1,000 + 인용 선행기술 3,513. 원천은 `data/**` 이며
  (`rejected_patents_meta.parquet`·`cited_enriched/`) TTL 이 아니다(§1-1).
  **CR-008 이 이 분모를 바꾼다.** 두 CR 은 파일이 겹치지 않지만 **데이터가 겹친다** —
  최초 산출 시점의 분모는 4,034(인용 3,034)였고, B층 노드 479 가 들어오며 4,513 이 됐다.
  CR-008 이 재수집될 때마다 이 자산도 다시 발행해야 한다.
- **실측**: `patent-text` 274 개념 중 df>0 **147**(53.6 %) · `expert-tag` 261 중 **136**(52.1 %).
  두 프로파일의 df 는 실제로 갈린다 — `material:oxide` 1,100 대 0 · `material:sio2`
  827 대 1,492 · `skill:plasma_diagnostics` 204 대 753(R4-SHORT-KO-TASK 차단의 효과).
  **한 값으로 뭉치지 않는 이유가 이것이다.**
- **CR-007 상위 개념 7 이 전부 patent-text df 상위 21 위 안**(`oxide` 6위 ·
  `dielectric` 11위 · `process_gas` 14위 · `plasma_processing` 15위 ·
  `process_chamber` 19위 · `photomask` 21위) — 고빈도와 상위어를 함께 줘야 하는 근거.
- **`depth` 는 얇다**: `skos:broader` 18 트리플 · 최대 깊이 1 · patent-text 274 중
  **16 개(5.8 %)만 depth=1**. 필드는 발행하되 실질화는 CR-002(D-02) 소관이다.
  `expert-tag` 사전에는 상위어가 **0 개**다(상위 개념 7 이 patent-text 전용이므로).
- **df 는 상류가 df 계산 전용 참조 적용기로 센다 — 하류용 적용기가 아니다.**
  CR-007 의 분업(토큰화는 하류)은 유지되며, 두 값의 어긋남은 하류가 회신할
  Spearman ρ(상위 30개념)가 검정한다.
- **가중식을 정하지 않고, 고빈도 개념을 삭제하지 않는다**(CR-009 비목표 ⓐ·ⓑ).
- **알려진 결함이 df 에 실린다(D-20)**: 단독 `hf` → `material:hf_acid` 오지정으로
  df 259. 이 CR 은 매핑을 고치지 않으며, 자산 스키마에 플래그를 만들지 않고
  `data/reports/concept_df_report.json` 에 명시한다.
- **하류 영향 (§0)**: vendor 시 개념 신호에 특이도 가중을 걸 재료가 처음 생긴다.
  A-Box 가 바뀌면 df 가 낡으므로 두 원천을 `PROVENANCE.json` `inputs` 에 등재했다.

### Added (2026-08-04 — CR-008 · B층 인용 선행기술 모집단 · 하류 D-18)
- **`scripts/build_b_layer_cited_ids.py` 신설**(결정적·멱등). 하류 이관 파일
  (514 행 · sha256 `9d0a7c0f…` 대조 강제) → `data/patents/b_layer_cited_population.parquet`.
  **특허 문헌 503 · NPL 11**(동결 분모 · 2026-08-03) · KR 235 · JP 186 · US 51 ·
  WO 24 · CN 6 · EP 1.
- **`--population` 경로 추가** — `build_abox_prior_art.py`(+`--extra-enriched`) ·
  `paper_data/scripts/collect_cited_biblio_claims.py`(+`--tag`). 인자가 없으면
  **기존 동작 그대로**이고, B층 IRI 는 기존 맵에 `setdefault` 로 병합되므로
  **A층 자산은 규칙적으로 불변**이다(성공기준 ③).
- **`cited_doc_id` 는 `scripts/citation_norm.py` 가 만든다** — 손으로 만든 규칙은
  KR 등록번호에서 틀렸다(`KR101036572 B1` → `KR-G-1036572`, 접두 '10' 과 선행 0 탈락 ·
  A층 264 건). 정본 정규화기는 A층 `cited_doc_id` 를 **3,145/3,149 재현**한다.
- **간선은 만들지 않는다**(CR-008 비목표 ⓐ). `hasPriorArtExaminer`·`hasPriorArt`·
  `overPriorArt` 가 산출 TTL 에 0 트리플임을 테스트가 단정하고, 생성기 원문에
  해당 술어가 없음도 함께 단정한다 — 상류에 간선을 두면 하류 봉인이 무의미해진다.
- **수집 실행 완료(2026-08-04)** — KIPRIS(KR 235) · BigQuery(JP·WO·CN·EP 217) ·
  BigQuery US(51). GCP 프로젝트 `starry-runner-310008` · 실측 스캔 370.5 GB + 368.4 GB.
- **`ontology/sdkb-abox-prior-art.ttl` 서명**: 트리플 57,075 → **66,453**(+9,378) ·
  `CitedPatent` 3,034 → **3,513**(+479) · `claimText` 2,197 → 2,479 ·
  `abstractText` 2,973 → 3,438 · `filingDate` 3,034 → 3,513 · IPCSymbol 2,974 ·
  CPCSymbol 4,234 · `realizesProcess` 2,786 · `involvesMaterial` 1,580 ·
  `concernsSkill` 1,486 · `concernsDevice` 262.
- **성공기준 ① 도달성 482/503 = 0.9583** (합격선 0.95 · NPL 11 별도 · 총계 514).
- **성공기준 ② 관할별** — KR 도달성 1.0000·초록 1.0000·**청구항 1.0000** ·
  US 0.9608/0.9608/**0.9608** · JP 0.8978/**0.8226**/0.0000 · WO 1.0000/1.0000/0.0000 ·
  CN 1.0000/1.0000/0.0000 · EP 1.0000/1.0000/0.0000.
  **US 청구항 0.9608 은 임계 0.99 에 미달**한다 — 해소된 49 건은 전부 청구항을 가지므로
  원인은 청구항 부재가 아니라 **문헌 2 건 미해소**다. JP·WO·CN·EP 의 청구항 0.000 은
  CR 이 미리 적어 둔 상한(D-05)이며 이 CR 의 실패가 아니다.
- **성공기준 ③ A층 자산 불변 — 트리플 집합 차로 증명.** 사라진 트리플 **0** ·
  A층 노드를 주어로 하는 트리플 45,411 → 45,411(**차이 0**) · A층 NPL 노드 9 불변.
- **간선 0 재확인**: 산출 TTL 의 `hasPriorArtExaminer`·`hasPriorArt`·`overPriorArt` = 0.
- **미해소 21 건**(JP 19 · US 2). 대부분 1990년대 JP 공개공보로 BigQuery
  `patents-public-data` 에 해당 `publication_number` 가 없다. **분모에서 빼지 않는다.**
- **A층 전례 없는 종별 5 건**: `KR…Y1` 3 · `JP2605509 Y2` 는 노드 생성 성공,
  `JP60244476 X2`(특허공고 昭60) 는 미해소.
- **SHACL** `shapes_patent.ttl` × 산출 TTL 통과(67,171 트리플 검증).
- **부수 수정**: 수집기의 dotenv 경로가 삭제된 저장소
  (`sdkb-foresight-paper/.env`)를 가리키고 있었다. `load_dotenv` 는 없는 파일에
  조용히 성공하므로 키가 빈 채로 API 가 전부 not_found 를 냈을 것이다 —
  `paper_data/.env` 를 먼저 찾도록 폴백을 넣었다.

### Added (2026-08-03 — CR-004R · 거절이유 조항(RejectionReason) 분류 · 하류 CR-004R)
- **`ont:RejectionType` 개체 7 신설**(`ontology/sdkb-patent.ttl`, 기존 5개는 무변경):
  `Rejection_ClaimRequirements`(§42④) · `Rejection_UnityOfInvention`(§45) ·
  `Rejection_ClaimFormat`(§42⑧) · `Rejection_SameDayFiling`(§36②) ·
  `Rejection_ExpandedPriorFiling`(§29③) · `Rejection_AmendmentScope`(§47②) ·
  `Rejection_DivisionalScope`(§52①). §42⑤(2014.6.11 폐지)는 의도적으로 제외.
- **신규 술어 5**: `ont:reasonGround`(ObjectProperty, domain `RejectionReason`,
  range `RejectionType`) · `ont:groundClause`·`ont:noticeRound`·`ont:noticeType`·
  `ont:noticeDate`(DatatypeProperty, domain `RejectionReason`). TBox 선언 후
  447 트리플로 파싱 확인.
- **거절이유 조항 분류 파이프라인** (`scripts/reextract_claim_judgments.py`
  `--reasons-only`/`--skip-reasons`): 의견제출통지서·거절결정서 원문에서
  법조항(조-항-호)을 추출해 `RejectionType` 으로 매핑, 발송일자·발송번호로
  정렬해 `noticeRound` 를 부여. 원천 = `paper_data/data/processed/opinion_notices`.
  결과: **994/1000 출원 커버 · RejectionReason 2,749건** · 미매핑 조항 6건
  (§42⑤ 2 · §36① 2 · §29⑤ 2, 전부 저빈도 · `data/reports/rejection_reasons_loss.json`).
  612개 출원이 서로 다른 거절근거(reason_ground) 2종 이상, 861개 출원이
  RejectionReason 2건 이상을 가진다.
- **`build_abox_claim_features.py`**: 위 산출을 `ont:rejectionEvidence` 로
  기존 `Patent` 인스턴스에 연결. **+19,240 트리플**(2,749건 × 7 술어 − 미기재
  `noticeDate` 3건). 기존 `PriorArtJudgment` 635건은 **완전히 무변경**
  (회귀 확인 — 코드 경로 분리).
- **SHACL** (`validation/shapes_patent.ttl`): 기존 `Shape_RejectionReason`
  (`sh:or` 로 `rejectionPassage`|`seeAlso` 요구, 인스턴스 0개일 때는 공허하게
  통과했으나 이번 인스턴스화로 위반이 드러남)에 `reasonGround` 분기를 추가하고,
  신규 `Shape_RejectionReason_Clause`(reasonGround 최대1·groundClause 문자열·
  noticeRound ≥1 정수·noticeType 열거값)를 신설. 500건 표본 검증 통과.
- **부수 수정**: `reextract_claim_judgments.py` 의 미사용 `import requests`
  (선언되지 않은 의존성, `pyproject.toml` 미포함)를 지연/옵션 임포트로 변경 —
  새 의존성 추가 아님, 기존 버그 수정.
- **하류 영향 (§0)**: `sdkb-abox-claim-features.ttl` 트리플 11,625,171(judgments
  635 무변경 확인). `SDKB-Match`·논문 코퍼스는 vendor 시 `RejectionReason` 신규
  트리플이 포함된다 — 조항 단위 거절근거 조회(CQ)가 처음 가능해진다.
- **알려진 한계**: opinion_notices 인용 해소를 통한 `PriorArtJudgment` 확장은
  이번 변경 범위 밖(§1.3 미검증 파서 리스크로 제외) — 별도 CR 필요.

### Added (2026-08-01 — CR-007 · 개념 매핑 자산과 상위 개념 계층 · 하류 D-14/D-15/D-16)
- **상위 개념 7 + 구체 하위 6 신설, `skos:broader` 18 트리플**
  (`scripts/add_superordinate_concepts.py`, 신규 · 결정적 · 멱등).
  `equipment_class:process_chamber` · `material:process_gas` ·
  `process:plasma_processing` · `material:photomask` · `material:dielectric` ·
  `material:oxide` · `material:cmp_slurry`.
- **왜.** 하류가 현행 별칭 사전을 특허 전문에 적용하면 `챔버`→`skill:chamber_conditioning`,
  `가스`→`skill:gas_chemistry` 처럼 문서의 주제가 **역량(Skill) 축**에 붙어 Skill 이 특허
  개념 링크의 18.1 % 를 차지했다(축 범주 오류 · D-15). 고칠 방법은 별칭 삭제가 아니라 축
  재지정인데(삭제하면 동점블록 중앙값이 9 → 28 로 악화해 해상도가 무너진다), **재지정이
  붙을 상위 개념이 온톨로지에 없었다.** 이 변경이 그 자리를 만든다.
- **구체 하위 6 을 함께 세운 이유.** `process_gas`·`photomask` 의 하위가 스냅샷 261 노드에
  **0 개**였다(Material 20 에 가스·마스크 실체가 없다). 성공기준을 느슨하게 만드는 대신
  실체를 세웠다 — `cf4`·`sf6`·`oxygen_gas`·`argon`·`euv_mask`·`duv_photomask`.
  2 글자 라틴 토큰이 자유 텍스트에서 오검출되므로 id 를 `argon`·`oxygen_gas` 로 둔다.
- **TBox.** `skos:broader` 를 `sdkb-core.ttl` 에 선언한다(A-Box 가 쓰는 술어는 TBox 가 알아야
  한다 · §1.2). **domain·range 는 걸지 않는다** — 외부 어휘에 SDKB 의 정의역을 얹으면 SKOS 를
  쓰는 다른 소비자의 의미가 달라진다. 새 술어를 발명하지 않았다.
- **`mappings/concept_mapping.json` 신설 (릴리스 자산)** — 표면형 → 개념 IRI 를
  **프로파일별로** 발행한다(`scripts/build_concept_mapping.py`). 규칙 5 개(R1 정규화 ·
  R2 Tier-1 · R3 Tier-2 · R4 한글 단문 차단 · R5 중의성)와 신뢰도·규칙 id 를 함께 싣는다.
  `provenance/PROVENANCE.json` 에 sha256 등재. 타임스탬프를 넣지 않아 재생성이 결정적이다.
  **적용기(linker)는 상류가 만들지 않는다** — 하류마다 토큰화가 다르다.
- **프로파일은 사전의 속성이다(파일 복제 없음).** `abox_term_aliases.json` 의 값이
  `{"expert-tag": …, "patent-text": …}` 형태를 받는다. `null` = 그 프로파일에서 비활성.
  14 항목만 프로파일화했고 나머지 228 항목은 모든 프로파일에 그대로 적용된다.
- **하류 영향 (§0).** 릴리스 서명이 움직인다: core-data **2,762 → 2,884 트리플(+122)** ·
  인스턴스 262 → 275 · 클래스별 Δ = Material +11 · EquipmentClass +1 · Process +1 ·
  술어 Δ = `skos:broader` +18, 그 외 노드 속성 술어 각 +13.
  `SDKB-Match` 는 새 자산을 vendor 목록에 넣어야 개념 링크를 스냅샷만으로 재현할 수 있다(D-16).
- **전문가매칭은 움직이지 않았다(T3).** `sdkb-abox-experts-problems.ttl` 8,483 트리플이
  변경 전후 **집합으로 동일**하다(added 0 · removed 0). 처음 빌드했을 때는 그렇지 않았다 —
  신설 노드의 이름(`photomask`·`oxide`)이 Tier-1 어휘집에 들어가 Tier-2 별칭을 가리면서
  `SC_PROB_007` 의 `requiresSkill → skill:mask_engineering` 이 **사라졌다.** 그래서 신설
  노드에 `props.lexicon_profile: patent-text` 를 걸어 어휘를 프로파일 범위로 묶었다.
  노드와 계층 자체는 프로파일과 무관하게 그래프에 있다 — 가려지는 것은 이름으로 텍스트를
  잡는 힘뿐이다.
- **미달로 남기는 것 (성공기준 ①).** "개념의 ≥ 95 % 가 표면형 ≥ 3 개 보유"는 **27.0 %**
  (patent-text · 74/274)로 크게 미달이다. 원인은 이 CR 이 아니라 다국어 라벨의 부재다
  (@en 632 · @ko 93 · @ja 0). CR-003 의 일이며, 여기서 채우면 어휘를 지어내는 것이 된다.
- **잔여 (기록).** `산화막` 은 patent-text 에서 `material:oxide`(재지정)와 `material:sio2`
  (기존 `skos:altLabel`) **양쪽**에 걸린다. R5 규칙대로 후보를 지우지 않고 `ambiguous` 로
  표시했다 — 어느 쪽을 고를지는 적용기의 판단이다. 따라서 sio2 접힘 해소는 이 표면형에서
  부분적이며, 실제 효과는 하류 재측정(고유 개념집합)이 판정한다.

### Added (2026-07-20 — SubProcess 한국어 별칭 승격 · 하류 G₀ 이동)
- **SubProcess 축에 한국어 `skos:altLabel` 19건 신설**
  (`scripts/promote_korean_aliases.py`, 신규 · 결정적 · 멱등). 원자층증착=ALD ·
  화학기상증착=CVD · 물리기상증착/스퍼터링=PVD · 건식(플라즈마) 식각 · 습식 식각.
  `data/semiconductor_v0_3.json` 의 `synonyms` 가 정본이고 `convert_rdf` 가 방출한다.
- **왜.** Process·Device·Material·Skill 축에는 한국어 별칭이 있는데 **SubProcess 38개만
  0개**였다. KIPRIS/SIRP 국문 명세는 한국어 산문이므로, 이 공백은 국문 텍스트에서 하위 공정을
  식별할 수 없다는 뜻이었다. 용어는 **새로 만들지 않았다** — 이미 커밋돼 있던
  `mappings/abox_term_aliases.json` 의 큐레이션을 개념 어휘로 **승격**했을 뿐이다.
  출처는 `provenance_sources.sdkb_curation_ko` 로 선언한다.
- **승격하지 않은 것과 그 이유.** 별칭 사전의 한국어 100건 중 19건만 옮겼다. 브리지 태그와
  `skos:altLabel` 은 뜻이 다르다 — 전자는 "이 텍스트를 보면 이 노드를 떠올려라", 후자는
  "이 개념은 이렇게도 불린다". 전량 승격하면 그래프가 **거짓을 주장한다**: `플라즈마`가 Skill
  Plasma Diagnostics 의 이름이 되고(물리 현상이다), `파티클`이 Process Clean 의 이름이 되며
  (`FailureMode:particle` 노드가 따로 있다), `산화물`이 SiO₂ 의 이름이 되고(상위어다),
  `감광제`가 EUV 포토레지스트 전용이 된다(`193nm PR` 노드가 있다). **Skill 축 21건은 전부**
  이 유형이라 0건 승격했다. Process·Material 축의 증분은 상하위 관계 판정(패터닝⊃노광 ·
  도핑⊃이온주입)을 요구하므로 사람 검수 후 별도로 다룬다. 축이 맞아도 의미가 어긋나는
  `극자외선`(광원)·`하드마스크`(재료)는 명시적으로 제외했다.
- **하류 영향 (§0).** `sdkb-foresight-paper` 의 G₀ 가 움직인다 — 재vendor·재동결이 필요하고
  논문의 baseline 서명(트리플 수)이 갱신된다. 특허↔공정 엣지는 만들지 않으므로 C₀·H1 은
  불변이어야 하며, 그 불변을 하류에서 실측해 확인한다.
- **미해결 (기록만).** 기존 한국어 별칭(`식각`·`증착`·`포토`·`리소그래피`·`평탄화`)은 노드 단위
  프로비넌스가 `semikong` / `Nguyen et al. 2024 arXiv Appendix A` 를 가리키는데, **영문 arXiv
  부록에 한국어 용어가 있을 리 없다.** 이 용어들은 최초 seed JSON(`created_by: seed`)에 딸려
  들어왔고 git 이력이 없어 실제 출처를 특정할 수 없다. 값을 채우면 교정이 아니라 날조이므로
  **고치지 않고 여기 남긴다.** 구조적 원인은 `synonyms` 가 용어 단위 프로비넌스를 갖지 못하고
  노드의 것을 물려받는 데 있다.

### Fixed / Documented (2026-07-20 — 인력·문제 축 프로비넌스 정본화 + 전문가 이름 충돌 해소)
- **`docs/deidentification_protocol.md` 신설.** 인력·문제 축이 실 원천을 그대로 쓸 수 없는
  데이터임을, 그리고 무엇을 어떻게 변조했는지를 기록한다. Expert 110 = **변조 파생 5**
  (EXP_001–005, 실 경력기술서 근거 · "1.기본정보"·"4.주요 경력 사항" 식별불가 처리 · 가명 ·
  수치는 생성값) **+ 결정적 생성 105**. Problem 226 = 최초 큐레이션 61 + 수출통제 시나리오 15 +
  온톨로지 추론 시나리오 10 + 공개사례 파생 18(WM-811K 8·블로그 5·TEMAZ 3·문헌 2) +
  구조 파생 생성 122. **원본 문서는 저장소·릴리스·하류 vendor 산출물 어디에도 반입된 적이 없다.**
- **왜 지금.** `docs/datasheet.md` 는 전문가 프로필을 일괄 "synthetic … not personally
  identifiable" 로 단언했는데, 이는 생성 105건에만 정밀하고 변조 파생 5건에는 부정확했다.
  하류 논문이 이 축의 출처를 인용해야 하는데 **참조할 문서 자체가 없었다.** datasheet 3개 항목과
  `build_abox_experts_problems.py` 의 "KR 파일이 실명" 주석(사실과 다름)을 함께 정정했다.
- **전문가 이름 충돌 해소** (`scripts/reassign_expert_names.py`, 신규 · 결정적 · 멱등).
  이름 풀이 좁아 **56개 이름이 110명에 배분**돼 있었다. 완전 중복 레코드는 **0건**이고(38필드
  정규화 해시), IRI 충돌도 0이며, 겹치는 것은 `skos:prefLabel` 문자열뿐이었다 — 그런데 라벨만
  프로젝션하는 CQ11 이 텍스트상 동일한 행 11건을 내 **데이터 중복처럼 보였다.** 삭제는 서로 다른
  프로필 54개를 없애므로 채택하지 않고, 이름이 이미 가명이므로 **성 보존 + 이름 교체**로 재부여했다
  (EN 자리표시자 `"Kang, [Given Name]"` 가 그대로 유효해진다). 고유 이름 **56 → 110**.
- **프로비넌스 위생** (`scripts/sanitize_expert_provenance.py`, 신규 · 멱등): `upgrade_log.resume_matched`
  의 `pdf` 필드가 담고 있던 **저장소 밖 비공개 경로 5건**을 KR·EN 양쪽에서 제거했다. 재현에 쓸 수
  없으면서 내부 디렉터리 구조만 배포물에 남겼기 때문이다. `text_sha256` 은 남긴다 — 파생 사실을
  고정하는 앵커는 해시이지 파일 위치가 아니다.
- 그래프: `sdkb-abox-experts-problems.ttl` **3,653 트리플 불변** · Expert 110 · Problem 226 불변.
  변경 트리플은 `skos:prefLabel` 54 + `skos:altLabel` 7 뿐. `make validate` SHACL 통과(양 그래프).
- **하류 통보 — `sdkb-foresight-paper`.** 트리플 수는 안 움직이지만 **TTL 내용이 바뀌어 sha256 이
  바뀐다.** 재vendor 후 G₀ 를 재동결해야 하며, **트리플 44,202 는 그대로**다. 특허↔공정 엣지를
  건드리지 않으므로 **H1·H2 결론은 불변**이다. CQ11 은 66행 유지에 distinct 가 55 → 66 으로 올라
  라벨 프로젝션의 겉보기 중복이 사라진다.

### Added (2026-07-15 — 청구항 전문 어휘: IP-R&D FTO 자기완결성)
- **`ont:claimText`**(반복 가능 · 청구항당 1트리플, 선두 번호 보존) · **`ont:claimCount`**(정수) 신설.
  TBox `ontology/sdkb-patent.ttl`, 기존 `firstClaimText`/`abstractText` 패턴 그대로(domain `ont:Patent`,
  range string/integer). **파급**: 순수 가산 — 기존 인스턴스·엣지·shape 불변, 하류 G₀ 는 TBox 선언
  2개만 늘고 ABox 0 변화(재vendor 후 재동결 시 H1 불변을 하류에서 실증).
- **왜.** KIPRIS 로 수집한 특허는 제목+링크만 있어 IP-R&D 세부 태스크(FTO·회피설계)를 그래프만으로
  실행할 수 없었다 — 태스크 시점에 청구항을 다시 긁어야 해 **온톨로지의 문제해결 자기완결성**이
  깨졌다. `firstClaimText`(청구항1)만으로는 독립·종속 청구항 전체를 못 담는다. `getBibliographyDetailInfoSearch`
  가 청구항 전문을 주므로(claimCount 포함) 이를 실체화한다. 소스 라이선스 종속 — KIPRIS 원문은
  로컬 그래프 전용(비커밋·비재배포).

### Added (2026-07-12 — SemiKong 공정 분류 복원 + 소자 어휘 보강)
- **SDKB 는 출처 분류의 3개 그룹을 통째로 빠뜨리고 있었다.** `Process` 노드의 `provenance.source_id`
  (`L1-Planarization` 등)가 보여주듯 SDKB 의 공정은 SemiKong Appendix A **Table 7 의 L1 Process Group**
  인데, Table 7 은 그룹이 **10개**이고 SDKB 는 7개만 담았다. 누락: **1. Substrate Preparation ·
  9. Advanced Modules · 10. Back-End Processes**. 즉 다이싱·패키징·금속화·웨이퍼 테스트를
  **표현할 어휘 자체가 없었다.** 있는 그룹들도 L2 모듈 대부분이 빠져 있었다(예: Film Formation 에
  Oxidation·Epitaxy 없음, Thermal Processing 에 Annealing 없음).
- `scripts/add_semikong_process_nodes.py` (신규, 멱등): Table 7 의 Group·Module 열을 **전량 복원**한다.
  **Process 8 → 11** (+3 그룹), **SubProcess 12 → 38** (+26 모듈). 기존 20개 IRI 는 **하나도 건드리지
  않는다** — 하류(특허 ABox 링크, foresight-paper 의 G₀)가 그것을 가리키기 때문이다.
  Table 7 자체의 중복(1.3 Cleaning ≡ 6. Cleaning, 7.2 Thermal Oxidation ≡ 2.1 Oxidation)은 하나로 합쳤고,
  그 판단을 노드 `provenance.note` 에 남겼다.
- **Device 31 → 34**: `EPROM`(Q378210) · `FeRAM`(Q703656) · `Diode`(Q11656) 추가.
  EPROM 누락이 특히 컸다 — IPC `H10B 69/00`(EPROM 잔여군)과 구 `H01L 21/8247`(EPROM 제조)에 걸리는
  특허가 SIRP 1,000건 중 다수인데 대응 개념이 없었다. Wikidata 상 EEPROM(Q205908)은 EPROM 의
  `P279 subclass of` 하위이므로 **별개 소자**임을 확인하고 추가했다.
  `add_device_nodes.py` 에 `discrete` 카테고리 추가(다이오드는 logic/memory/power/sensor/packaging 중
  어디에도 정직하게 들어가지 않는다).
- 그래프: core-data **2,743 트리플**. `make validate` SHACL 통과, `pytest` 75 passed / 10 skipped.
- **하류 통보**: `sdkb-foresight-paper` 의 G₀ 가 26,676 → **26,973 트리플**로 움직인다. 이 논문은 아직
  G₀ 를 동결하기 전이므로 의도된 변경이며, baseline 재조립 후 표 3·H1 관측 단위를 갱신한다.

### Fixed / Changed (2026-05-17 — figure reconciliation, reliability re-measurement, OWL regen)
- **OWL regression fixed**: committed `ontology/sdkb-core.ttl` was a stale `1.0.0-dev` build missing the enrichment layer + `dcterms:modified`/`dcterms:references`/`rdfs:seeAlso`/`versionInfo 1.1.0-dev`, causing 24 `tests/test_owl.py` failures. Regenerated via `make owl` (`scripts/build_owl.py`) → **438 triples**, `1.1.0-dev`. Full suite now **75 passed / 10 skipped (85 collected) / 0 failed**. (Earlier "46/46" and "85/85" were pre-regression counts.)
- **Verified-figure reconciliation** (single snapshot, 2026-05-17): curation graph **229 nodes / 268 edges** (baseline origin 198/264, expanded by curation incl. `Device`); SIRP raw corpus **1,000 records** (the prior "773"/"SIRP-773" was the initial cohort snapshot; the 7,500 GT pairs remain frozen at the 773-snapshot and are unchanged). README (EN/KO), datasheet, and the SIRP card synced to these figures.
- **Synthetic-rating reliability re-measured to plan spec** (v2 §12.1 specifies *weighted* κ; code had computed unweighted Fleiss κ on an ordinal/skewed scale): `scripts/ingest_curated_ratings.py` now reports mean pairwise quadratic-weighted κ = **0.550**, Krippendorff α(interval) = 0.552, ICC(2,k) consensus = **0.787** (passes the ≥0.70 gate; this is the reliability of the 3-rater consensus label actually used as GT), with original Fleiss κ = 0.258 / ICC(2,1) = 0.552 kept verbatim and kappa-paradox evidence documented. New `data/experts/reliability_report.{md,json}`.
- **Publication-integrity docs added**: `docs/project/dataset_publication_risk_review.md` (8-item dataset-dispute risk review); datasheet §8 + SIRP card §5-2/§7-1 now state explicitly that neither GT track is human-expert annotation (examiner-grounded 7,500 = objective KIPO citations; 3-rater 7,800 = algorithmically simulated).

### Added (2026-05-12 — SDKB-Centric Curation, Phase 0+1)
- Architecture amendment: [docs/project/architecture_amendment_sdkb_centric.md](docs/project/architecture_amendment_sdkb_centric.md) reverses ADR v1.1 — SDKB v1.0 is the trunk; SemicONTO becomes one of many external alignment sources via SKOS mapping, not the upper ontology (no `owl:imports`).
- SemicONTO Phase 0 curation: [ontology/imports/SemicONTO-0.2.ttl](ontology/imports/SemicONTO-0.2.ttl) cached, [data/reports/semiconto_analysis.json](data/reports/semiconto_analysis.json) inventory, [mappings/sdkb_semiconto_alignment.{csv,ttl}](mappings/) (122 SKOS triples, 107/198 nodes aligned), [data/reports/semiconto_enrichment_candidates.json](data/reports/semiconto_enrichment_candidates.json) (Bucket A 29 cls + 13 obj props / Bucket B 6 SDKB-unique types).
- SDKB v1.1 enrichment layer in [ontology/sdkb-core.ttl](ontology/sdkb-core.ttl): 6 new classes (`Semiconductor`, `Intrinsic/ExtrinsicSemiconductor`, `Dopant`, `Acceptor`, `Donor`) and 4 new ObjectProperties (`hasNextStep`, `hasSubStep` transitive, `hasAcceptor`, `hasDonor`) — all with `skos:exactMatch` back-link to SemicONTO. OWL ontology grew from 257 → 353 triples.
- Scripts: `analyze_semiconto.py`, `build_semiconto_alignment.py`, `identify_enrichment_candidates.py`. Makefile target `semiconto-phase0` (fetch + analyze + align + enrich).
- Tests: 8 new enrichment regression tests in `tests/test_owl.py::TestEnrichmentLayer` (54/54 passing).
- docs/archive/: superseded ADR v1.1 moved here; patent_*_plan.md parents rewired to the new amendment.

### Fixed (2026-05-12)
- 13 legacy `provenance.cross_ref[source=semiconto]` entries in baseline JSON were wrong (`semiconto:ExperimentStep` does not exist — actual class is `ExperimentalStep`; Process was mis-mapped to step instead of `Experiment`). **Now corrected at the source**: baseline JSON updated in-place; alignment graph reports `legacy_corrections: 0`. Each corrected entry carries an updated `note` explaining the fix.

### Added (2026-05-12 — Instance-level enrichment)
- `mappings/sdkb_instance_enrichment.json` — externalized type-refinement overrides (declarative, audit-friendly). Phase 1 v1.1 ships with `material:polysilicon → sdkb:Semiconductor`. Empty enrichment classes (Dopant/Acceptor/Donor/Intrinsic/Extrinsic) are documented in the config rather than silently absent.
- `scripts/convert_rdf.py` reads the enrichment file and emits additional `rdf:type` triples (primary type preserved, refined class added — safe because refined ⊂ primary). RDF data graph: 2117 → 2118 triples.
- `tests/test_instance_enrichment.py` — 9 regression tests covering (a) config schema, (b) refined types present in data graph, (c) baseline cross_refs reference only real SemicONTO classes.

### Added (2026-05-12 — Self-description metadata + DT prop alignment)
- `sdkb-core.ttl` ontology declaration now self-describes its external dependencies: `owl:imports` is reserved for PROV-O (the only hard import); SemicONTO 0.2 and QUDT are declared via `dcterms:references` to make the SDKB-centric policy machine-readable. Added `dcterms:modified` (2026-05-12) and bumped `owl:versionInfo` to `1.1.0-dev`. `rdfs:seeAlso` links to the architecture amendment doc and the alignment graph URI. OWL ontology: 433 → 438 triples.
- 5 SemicONTO DatatypeProperty mappings encoded in [mappings/sdkb_semiconto_alignment.ttl](mappings/sdkb_semiconto_alignment.ttl): `semi:hasExperimentName` ↔ `skos:prefLabel`, three `*Aim`/`*Description` predicates ↔ `skos:definition`, `semi:hasExperimentalStepID` ↔ `dcterms:identifier`. All recorded as `skos:closeMatch` with rdfs:comment rationale; also surfaced in `data/reports/sdkb_semiconto_alignment_report.json` under `datatype_property_alignment`. Alignment graph: 122 → 132 triples.
- 11 new regression tests: `tests/test_owl.py::TestOntologyDependencyMetadata` (6) and `tests/test_alignment_graph.py` (5). Total **85/85 passing**.

### Added (2026-05-12 — MEDIUM enrichment + SHACL + QUDT)
- Bucket A MEDIUM enrichment (8 classes + 1 obj prop): `ElectronBeamLithography`/`ThermalEvaporation` ⊂ SubProcess; `HallEffectMeasurement`/`FieldEffectMeasurement`/`PhotoelectronSpectroscopy` ⊂ Metrology; `NTypeSemiconductor`/`PTypeSemiconductor` ⊂ ExtrinsicSemiconductor; `DopingRelation` standalone; `hasEquipment` (SubProcess→Equipment). All with `skos:exactMatch` to SemicONTO. Selective absorption — SemicONTO classes tied to absent parents (Experiment, InformationObject) were intentionally skipped.
- SHACL enrichment shapes (`validation/shapes.ttl` +53 triples): `Shape_ExtrinsicSemiconductor` enforces "must have hasAcceptor or hasDonor" (SemicONTO axiom); domain shapes for `hasAcceptor`/`hasDonor` (subjects must be ExtrinsicSemiconductor); range shapes for `hasNextStep`/`hasSubStep`/`hasEquipment`; `Shape_DopantInstance` enforces Dopant ≡ Acceptor ∪ Donor at instance level.
- QUDT-aligned Quantity layer: abstract `sdkb:Quantity` (`skos:exactMatch qudt:Quantity`), `sdkb:MaterialProperty ⊂ sdkb:Quantity` (`skos:exactMatch semi:MaterialProperty`), existing `sdkb:Parameter` reclassified as `⊂ sdkb:Quantity`. New properties: `sdkb:hasProperty` (Material → MaterialProperty), `sdkb:hasMeasuredProperty` (SubProcess → MaterialProperty), `sdkb:hasNumericValue` (xsd:decimal), `sdkb:hasUnitSymbol` (xsd:string). QUDT NOT imported — referenced by IRI only, consistent with SDKB-centric policy.
- OWL ontology grew 257 → 353 → 398 → **433 triples** across the three Phase 1 enrichment passes.
- 21 additional tests in `tests/test_owl.py::TestEnrichmentMedium` and `tests/test_owl.py::TestQuantityLayer`. Total **74/74 passing**.

### Added
- Amendment v1 / v2 (`docs/project/plan_amendment_v1.md`, `v2`)
- SIRP integration: 773 examiner-grounded rejected patents → 7,500 prior-art pairs, 50 problems, 25 adversarial scenarios
- Patent module ontology: `ontology/sdkb-patent.ttl` + SHACL `validation/shapes_patent.ttl` + Korean industrial-tech-protection module `sdkb-governance-kr.ttl`
- Alignment-track ontologies: `sdkb-rbv.ttl`, `sdkb-commercialization.ttl`, `sdkb-foresight.ttl`
- Scripts: `ingest_rejected_patents.py`, `build_prior_art_pairs.py`, `sample_problems.py`, `gen_experts.py`
- Tests: `tests/test_patents.py` (26 SIRP regression tests)
- Docs: SDKB-Match architecture, leakage protocol, expert validation log, datasheet, commercialization strategy v1
- Notebook: `notebooks/04_prior_art_baseline.ipynb` (TF-IDF baseline with MRR/NDCG@5/Recall@K)
- Makefile targets: `venv`, `ingest-sirp`, `sirp-pairs`, `sirp-problems`, `sirp`, `experts`, `pipeline-full`
- CITATION.cff with advisor attribution

### Fixed
- **Bug 1**: deduplicated `equipment:asml_scanner` in `data/semiconductor_v0_3.json` (was 198 nodes including a duplicate, now 198 unique with `vendor:semes` added as a meaningful Korean 소부장 vendor)
- **Bug 2**: widened OWL property domains via `owl:unionOf` for `mitigatedBy`, `requiresSkill`, `madeBy`, `incompatibleWith` (and `notAllowedWith` range) in `scripts/build_owl.py` — closes RDFS inference cascade that mis-typed `RootCause` nodes as `FailureMode`
- **Bug 3**: added 4 missing `OBSERVED_IN` edges for `cdu` / `erosion` / `footing` / `particle` FailureModes — closes the remaining `Shape_FailureMode` SHACL gap
- `validation/shapes.ttl`: added missing `rdf:` / `rdfs:` prefix declarations (latent bug exposed under strict rdflib 7.x)
- All 20 baseline tests, 26 SIRP tests, and SHACL validation now pass; baseline 198 nodes / 268 edges

### Project scaffolding
- Namespace/ID policy: `config/namespaces.py`, `config/context.jsonld`
- Week 1 script: `scripts/parse_baseline.py` (schema report, Parquet extraction)
- Week 2 script: `scripts/build_owl.py` (OWL metamodel with 14 Core + 7 Governance classes)
- Week 3 script: `scripts/convert_rdf.py` (JSON→RDF/Turtle + JSON-LD)
- Week 4 script: `scripts/align_candidates.py` (lexical fuzzy matching engine)
- SHACL shapes: `validation/shapes.ttl` (release gate validation rules)
- PROV-O template: `provenance/prov.ttl` (agents, activities, source entities)
- JSON-LD context: `config/context.jsonld` (W3C JSON-LD 1.1 mapping)
- SPARQL examples: regulatory risk, FMEA path, tech gap queries
- Test suite: `tests/test_baseline.py`, `tests/test_owl.py`
- SHACL validator script: `scripts/validate_shacl.py`
