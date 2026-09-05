# PLAN-005 진단 — 선행기술요소 조사 도구로서의 SDKB 실측 (2026-09-05)

> 근거 계획: [PLAN-005](../plans/PLAN-005-prior-art-tool-qualification.md) §2.
> **모든 수치는 아래 명령의 출력이다**(CLAUDE.md §1-4). 명령은 저장소 루트
> `/home/arkwith/Dev/sdkb` 에서 실행한다. 워킹트리 기준이며, gitignore 된 A-Box 빌드 산출물을
> 포함한다.

---

## 0. 결론

**현 SDKB 는 선행기술요소 조사 도구가 아니라 "심사 결과 대장 + 조립 태그"다.**

| 층 | 물음 | 답 |
|---|---|---|
| 어휘 | 기술요소·조합·포함·치환·결합을 1급 시민으로 갖는가 | **아니오** — 해당 클래스 0개 |
| 공리 | 추론으로 의미 경로를 만드는가 | **아니오** — R-Box 8건, 선행기술 판단 공리 0 |
| A-Box | 요소 조합으로 표현되고 그 조합으로 검색되는가 | **앞 절반만** — 접지 33.1%, 검색은 요소 층을 안 읽음 |
| 검증 | 판단 능력을 잰 적이 있는가 | **아니오** — CQ 전량 ground BGP, 추론 검출 표면 0 |

---

## 1. 어휘 — 판단이 아니라 행정을 서술한다

선행기술 어휘는 `Patent` · `RejectedPatent` · `CitedPatent` · `Claim` · `ClaimFeature` ·
`PriorArtJudgment` · `RejectionType` 이다(`ontology/sdkb-patent.ttl`). **기술요소 · 요소의 조합 ·
조합 사이의 포함 관계 · 치환 가능성 · 결합 용이성을 담는 클래스는 0개다.**

**증상 ① — 구조요소를 담을 축이 없다.**
`ont:featureConcept` 의 range 는 Process ⊔ SubProcess ⊔ Device ⊔ Material ⊔ Skill ⊔ FailureMode ⊔
EquipmentClass 이며, 뒤의 셋은 FMEA·전문가매칭 계열이다. 그 결과 청구항에 가장 흔한 구조요소
(게이트·기판·드레인·배선 등 15개)가 `data/reports/ko_concept_proposals.json` 에
*"축 부재 — 구조 요소를 담을 클래스가 T-Box 에 없다"* 는 사유로 등재 보류되어 있다.

**증상 ② — 태스크 질의가 특허를 요구한다.**

```bash
cat queries/cq/CQ10_prior_art_candidates_by_concept.rq
```
스스로 *"IP-R&D 선행기술조사의 핵심 질의"* 라 부르지만 본문은
`?prior a ont:Patent ; ont:realizesProcess <…/plasma_etch> ; ont:filingDate ?f . FILTER(?f < …)` —
**개념 1개 + 날짜 필터**이며, 무엇보다 **질의 대상이 `ont:Patent` 여야 한다.**

---

## 2. R-Box — 8건이 전부이고, 선행기술 판단 공리는 0

```bash
for t in "owl:inverseOf" "owl:propertyChainAxiom" "owl:TransitiveProperty" \
         "owl:SymmetricProperty" "owl:disjointWith" "owl:equivalentClass" \
         "owl:equivalentProperty" "owl:hasKey" "owl:Restriction" \
         "owl:FunctionalProperty" "rdfs:subPropertyOf" "owl:cardinality"; do
  n=$(grep -h -o "$t" ontology/sdkb-core.ttl ontology/sdkb-patent.ttl \
        ontology/sdkb-commercialization.ttl ontology/sdkb-foresight.ttl \
        ontology/sdkb-rbv.ttl ontology/sdkb-governance.ttl \
        ontology/sdkb-governance-kr.ttl | wc -l)
  printf "%-28s %s\n" "$t" "$n"
done
```

| 공리 | 건수 |
|---|---:|
| `owl:TransitiveProperty` | **2** (`hasSubStep` · `broaderClassification`) |
| `rdfs:subPropertyOf` | **5** |
| `owl:equivalentClass` | **1** (`Dopant ≡ Acceptor ⊔ Donor` — 특허와 무관) |
| `inverseOf` · `propertyChainAxiom` · `SymmetricProperty` · `disjointWith` · `equivalentProperty` · `hasKey` · `Restriction` · `FunctionalProperty` · `cardinality` | **각 0** |

**합계 8건.** `owl:Restriction` 이 병합 그래프에 15건 있으나 **전부 `ontology/imports/SemicONTO-0.2.ttl`
안이며 SDKB 자체 T-Box 는 0건**이다.

**가장 결정적인 결손** — `ont:dependsOnClaim` 이 전이가 아니어서 **"종속항을 포함한 완전
한정요소집합"조차 추론으로 낼 수 없다.** 소스가 그것을 인정한다:

```bash
sed -n '551p' ontology/sdkb-patent.ttl
# → "완전 한정요소집합 = 부모 features ∪ 종속 추가 features(질의/추론으로 계산)"
```

---

## 3. A-Box — 요소로 표현까지만 되어 있다

```bash
cat data/reports/abox_claim_features_report.json
cat mappings/claim_feature_release_meta.json
```

| 항목 | 실측 |
|---|---|
| `ClaimFeature` | **1,306,191** / 문헌 40,187 |
| `Claim` | 594,078 (독립 143,485 / 종속 450,593) |
| 개념 접지 feature | **432,305 = 33.1%** |
| 접지에 쓰인 개념 종류 | **122** |
| 질의측(rej) / 후보측(cited) 접지율 | 48.6% / 39.6% |
| 비 KR/US 인용문헌 청구항 분해율 | **0%** (JP 0/186 · WO 0/24 · CN 0/6 · EP 0/1) |

```bash
grep -c "a ont:PriorArtJudgment" ontology/sdkb-abox-claim-features.ttl   # 635
grep -c "ont:aboutClaim"          ontology/sdkb-abox-claim-features.ttl   # 584
```
→ 판단 635건 중 **51건은 청구항에 접지되지 않는다.**

**그리고 검색 평가가 이 층을 읽지 않는다.** `scripts/eval_prior_art_realgt.py` 의 코퍼스 텍스트는
`title + abstract` 이고 개념 추출은 문서 단위다 — **`ClaimFeature`/`featureConcept` 를 한 번도
참조하지 않는다.** 130만 건의 요소 A-Box 는 현재 평가 경로 밖에 있다.

---

## 4. 검증 — 판단 능력을 잰 적이 없다

**CQ 31개 전부 ground BGP.**

```bash
grep -Hn "[a-zA-Z:]\+[*+]\|\^[a-zA-Z]" queries/cq/*.rq
# 적중 3건은 전부 "…"^^xsd:date 타입 리터럴 (CQ02·CQ06·CQ10)
```
재귀·전이 경로 0 · 역경로 0 · 시퀀스 경로 0. 실행기 `scripts/run_cq.py` 가 *"추론은 쓰지 않는다"* 고
명시한다. 최종 실측 통과율은 `data/reports/cq_report.json` 기준 **27/31 = 0.871** 이고,
**선행기술 스위트(pa)는 4/8 = 0.5** 다.

**SHACL 33 NodeShape**(`validation/shapes.ttl` 21 · `shapes_patent.ttl` 8 ·
`shapes_claim_features.ttl` 4)는 구조 계약만 본다. 추론기는 파이프라인에 타깃이 없고, 있어도
**검출 표면이 0**이다 — `disjointWith`·카디널리티·함수적 속성이 전부 0이라 모순이 원리적으로
생기지 않는다.

**의미검색 능력.** `data/reports/prior_art_realgt_report.json`:

| 랭커 | MRR | R@10 | R@50 |
|---|---:|---:|---:|
| tfidf | 0.2753 | 0.2758 | **0.4330** |
| onto | 0.0612 | 0.0614 | **0.1606** |
| onto_idf | 0.0656 | 0.0678 | 0.1684 |
| hybrid | 0.2098 | 0.2226 | 0.4234 |

`onto` 랭커는 온톨로지를 **표면형 사전으로만** 쓰는 문자열 매칭이다(`scripts/sdkb_nb.py::Bridge` —
SPARQL 없음, 그래프 순회 없음, 추론 없음). 설명 정밀도는 coverage **0.6003** 으로 문턱 0.70 미달
(`data/reports/explanation_precision_report.json`).

---

## 5. 업무 목적별 표본 — 신규성 축은 **소실이 아니라 문서화된 경계**다

### 5.1 실측

```bash
grep -o "ont:onGround ont:Rejection_[A-Za-z]*" ontology/sdkb-abox-claim-features.ttl \
  | sort | uniq -c | sort -rn
```
| `PriorArtJudgment.onGround` | 건수 |
|---|---:|
| `Rejection_Inventiveness` | **626** |
| `Rejection_Novelty` | **9** |

```bash
grep -A6 "a ont:RejectionReason" ontology/sdkb-abox-claim-features.ttl \
  | grep -o "ont:Rejection_[A-Za-z]*" | sort | uniq -c | sort -rn | head
```
| `RejectionReason` 근거 | 건수 |
|---|---:|
| `Rejection_Inventiveness` | 1,713 |
| `Rejection_ClaimRequirements` | 503 |
| **`Rejection_Novelty`** | **277** |
| `Rejection_Disclosure` | 95 |

```bash
python - <<'PY'
import pandas as pd
d = pd.read_parquet('data/patents/rejected_patents_meta.parquet')
n1 = sum('§1' in str(v) for v in d['rejection_legal_bases'].fillna(''))
n2 = sum('§2' in str(v) for v in d['rejection_legal_bases'].fillna(''))
print(n1, n2, len(d))          # → 14 400 1000
PY
```
```bash
python - <<'PY'
import json, glob, collections
c = collections.Counter()
for f in glob.glob('data/patents/rejection_decisions/structured/*'):
    for lb in json.load(open(f)).get('legal_bases', []):
        c[lb.get('paragraph')] += 1
print(len(glob.glob('data/patents/rejection_decisions/structured/*')), c.most_common())
# → 441  [('2', 400), ('1', 14), ('3', 1)]
PY
```

**핵심 대비.** 신규성 근거는 자원에 **`RejectionReason` 277건으로 존재한다.** 그러나 **선행기술
문헌과 연결된 판단(`PriorArtJudgment`)에는 9건만 있다.**

### 5.2 그 차이의 원인 — 결함이 아니라 명시된 범위 제한

```bash
sed -n '10,17p' scripts/reextract_claim_judgments.py
```
> **CR-004R (2026-08-02)** … ① 기존 판단(§29 근거 · 인용문헌 연결 · PriorArtJudgment)은 **거절결정서
> 표만** 그대로 쓴다 — 의견제출통지서에는 `cited_evidence_map`(구조화 인용문헌 해소)이 없고,
> 새로 만드는 것은 **범위 밖이다**(§1.3 — 검증 못 한 인용 해소를 쓰지 않는다). ② 신규: 조-항-호
> 전 조항을 표에서 뽑아 `RejectionReason` 재료를 만든다. **인용문헌이 필요 없어** 위 제약과 무관하다.

**그러므로 판정은 이렇다.**

- 신규성 **9건**은 거절결정서(§29① 14문서) 유래이며, 그 수는 정상이다.
- 신규성 **277건**은 통지서 유래인데, **인용문헌이 해소되지 않아 판단으로 승격되지 못했다.**
- **이것은 파이프라인 결함이 아니라 CR-004R 이 명시적으로 그은 경계다.** 결함 등재 대상이 아니며,
  **그 경계를 넘는 작업이 곧 "통지서 인용 해소"**(PLAN-005 §6 단계 2)다.

### 5.3 회복 가능성 — 통지서 원문 실측

```bash
python - <<'PY'
import glob, re
files = glob.glob('data/sources/opinion_notices/txt/*.txt')
pats = {'인용발명 N': r'인용발명\s*\d', '문헌번호': r'제\s*[0-9][0-9\-]{4,}\s*호',
        '공보종류': r'(공개특허|등록특허|공개실용|미국특허|일본공개|특허공보)',
        '§29①': r'제?\s*29\s*조\s*제?\s*1\s*항', '§29②': r'제?\s*29\s*조\s*제?\s*2\s*항'}
n = len(files); texts = [open(f, encoding='utf-8', errors='ignore').read() for f in files]
print(n, {k: sum(bool(re.search(p, t)) for t in texts) for k, p in pats.items()})
PY
```
| 통지서 1,155건 | 보유 | 비율 |
|---|---:|---:|
| `인용발명 N` 표기 | 955 | 82.7% |
| **문헌번호(`제…호`)** | **869** | **75.2%** |
| 공보 종류 표기 | 1,061 | 91.9% |
| **§29①(신규성)** | **259** | 22.4% |
| §29②(진보성) | 1,108 | 95.9% |

```bash
python - <<'PY'
import glob, os, pandas as pd
apps = {os.path.basename(f).split('_')[0] for f in glob.glob('data/sources/opinion_notices/txt/*.txt')}
a = set(pd.read_parquet('data/patents/rejected_patents_meta.parquet')['application_number'].astype(str))
print(len(apps), len(a), len(apps & a))     # → 999 1000 999
PY
```

**통지서 보유 출원 999건은 현 질의 1,000건과 999건이 겹친다.** 곧 인용 해소는 **새 벤치마크를
만드는 것이 아니라 있는 질의를 근거와 함께 두껍게 하는 작업**이며, 문헌번호가 75.2%에 있어
원리적으로 가능하다. 남은 약 1/4은 `인용발명 N` ↔ 번호 대응이 본문에 없는 건이라 별도 처리가
필요하다.

### 5.4 진보성 표본

```bash
python - <<'PY'
import pandas as pd, collections
e = pd.read_parquet('data/patents/prior_art_edges.parquet')
ex = e[e.source_type == 'examiner']
g = ex.groupby('target_patent_id').cited_id.nunique()
print(len(ex), collections.Counter(ex.legal_basis.fillna('')).most_common(3))
print('인용 1건:', (g == 1).sum(), '2건 이상:', (g >= 2).sum())
# → 2534  [('', 2534)]   /   200  800
PY
```

**심사관 인용 엣지 2,534건의 `legal_basis` 는 전량 공란이다** — 근거가 **엣지 단위로 붙어 있지
않다.** 질의당 인용은 1건 200 · 2건 이상 800 이며, 판단 단위로는 진보성 청구항 2,305개 중
인용 2건 이상이 걸린 것이 1,732개다. **진보성은 표본이 충분하고, 신규성은 §5.2 의 경계를 넘어야
성립한다.**

---

## 6. 진단 → 재구성 대응표

| 진단 | 대응 (PLAN-005) |
|---|---|
| §1 구조요소 축 부재 | §4 어휘 — `TechnicalConcept` / `StructuralElement` 신설 |
| §1 태스크 질의가 특허 요구 | §3.4 검사 규칙 + 태스크층/증거층 분리 |
| §2 R-Box 8건 · 판단 공리 0 | §3.3 원소층 `coveredBy` · §4 공리 |
| §2 `dependsOnClaim` 비전이 | §4 공리 (완전 요소집합 도출) |
| §3 접지 33.1% · 122종 | §4 A-Box 접지율 개선 |
| §3 검색이 요소 층 미참조 | §5 V3 커버율 지표 |
| §4 CQ 전량 ground BGP | §4 질의 — 확장 경로를 쓰는 태스크 질의 |
| §4 추론 검출 표면 0 | §5 V1 절제 (소비되지 않는 공리 배제) |
| §5.2 통지서 인용 미해소 | §6 단계 2 — **결함이 아니라 범위 확장** |
| §5.4 엣지 단위 근거 부재 | §6 단계 2 — 근거를 판단 단위로 부착 |
