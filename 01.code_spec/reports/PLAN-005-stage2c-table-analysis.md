# PLAN-005 단계 2-C · §2 2단계(분석) — 구성 대비표 원천 재관찰 (2026-09-06)

> **이 문서는 [PLAN-005-stage2-notice-analysis.md](PLAN-005-stage2-notice-analysis.md) §3 을
> 대체하지 않고 보정한다.** 그 문서의 수치는 재현했고 전부 맞다. 다만 **직렬화 서식 하나만
> 보고 있었다.** 원 진단을 지우지 않는 이유는 CHANGELOG 의 규율과 같다 — 그때 무엇이 참으로
> 보였는지가 기록이다.

---

## 0. 결론 먼저

1. **구성 대비표는 서식이 둘이고, 둘은 교집합이 0 이다.** 원 분석이 쓴 보유 신호
   (`구\s*성.{0,40}?비\s*고`, 201문서)는 `<표 N>` 서식 **32문서를 한 건도 잡지 못한다.**
   두 모집단은 겹치지 않는다.
2. **그러나 회수량이 늘어난다고 재료가 좋아지는 것은 아니다.** 원 분석이 센 "행"은 대부분
   **열이 잘려 한쪽 텍스트만 남거나 단어 중간에서 끊긴다.** 이 조각을 `coveredBy` 의 개시
   텍스트로 승격하면 §1-3(이름이 의미와 다른 필드를 만들지 않는다) 위반이다.
3. **신뢰할 수 있는 것은 텍스트가 아니라 구조 키다.** `<표 N>` 서식은 행 머리에
   **`구성 <그룹>-<구성번호>`** 를 담고 여기에 판정 라벨이 붙어 **305행**이 나온다.
   **다만 앞 숫자는 청구항 번호가 아니다 — §7 을 함께 읽을 것.**
4. **누출 분할을 적용해도 이 층은 거의 줄지 않는다** — 305행 **전량**이 dev+train 안이다.
5. **`check_leakage.py` 는 존재하지 않는다.** PLAN-001 이 이름만 적어 두었고 구현이 없다.
   누출 통제의 실물은 `data/sources/harvest_scope_dev_train.json` 이다.

---

## 1. 관찰 대상

| 원천 | 규모 |
|---|---|
| 의견제출통지서 txt | 1,155 파일 · 출원 1,000 (`_index.json`) |
| 거절결정서 structured | 979 (`data/sources/rejection_decisions/`) |
| 누출 범위 파일 | `data/sources/harvest_scope_dev_train.json` — dev 200 + train 600 = **800 출원**, `excluded_splits = [test, test_b]` |

> **함정 하나를 적어 둔다.** `rejection_decisions/structured` 는 **두 곳**에 있다 —
> `data/sources/`(979) 와 `data/patents/`(441). 원 분석의 384 는 전자이며 재현된다.
> 후자를 세면 270 이 나온다. 경로를 적지 않은 수는 이 저장소에서 재현되지 않는다.

> **파일명은 출원번호가 아니다.** 통지서 파일명은 `{출원번호}_{발송번호}` 이다(2-A 교정 6).
> `\D` 제거만 하면 두 번호가 이어붙어 **범위 교집합이 0 으로 나온다** — 이 관찰에서 실제로
> 한 번 그렇게 나왔고, 색인으로 바로잡았다.

---

## 2. 서식이 둘이다 — 그리고 겹치지 않는다

전수 1,155 파일에 대해 세 규칙을 각각 적용했다.

| 규칙 | 무엇을 잡는가 |
|---|---|
| **HAS** | `구\s*성.{0,40}?비\s*고` — 원 분석의 보유 신호 |
| **A** | `<표 N>` 블록 안의 `구성 N-M …` 행 |
| **C** | `^\d{1,2}\s+…\s+(동일\|차이\|유사\|대응)$` — 원 분석의 행 규칙 |

```
HAS 보유 문서 = 201            (원 분석 재현: 360행 · 한 행도 못 잡은 문서 116 = 57.7%)

(A행>0, B머리, C행>0) 조합별 문서 수 — 전수 1,155
   A=0 B=0 C=0 : 949      A=0 B=0 C=1 : 140
   A=1 B=0 C=0 :  32      A=0 B=1 C=1 :  26      A=0 B=1 C=0 : 8

같은 조합 — HAS 보유 201 안에서만
   A=0 B=0 C=0 : 109      A=0 B=0 C=1 : 65
   A=0 B=1 C=1 :  20      A=0 B=1 C=0 : 7
```

**201 안에서 A 는 언제나 0 이다.** `<표 N>` 서식 32문서·672행(느슨)은 원 분석의 시야 밖에
있었다. 반대로 C 행을 가진 문서 140건은 HAS 신호가 없다 — **보유 신호 자체가 표를 놓친다.**

---

## 3. 회수량이 아니라 "이름대로인가"가 문제다

### 3.1 느슨한 규칙은 본문 산문을 표 행으로 센다

`<표 N>` 블록 안에서 `구성 N-M` 을 **줄 어디에서나** 찾으면 672행이지만, 행이 판정으로
끝나는 **표 행의 형태**만 세면 305행이다.

| | 값 |
|---|---:|
| 느슨 A (블록 안 `구성 N-M` 등장) | 672행 |
| **엄격 A** (`^구성 N-M … <판정>$`) | **305행** |
| 정밀도 대리값 | **45.4%** |

나머지 54.6% 는 *"…구성 1-4는 인용발명 1의 타깃(3)이 평면형상을 가진 구성으로부터…"* 같은
**본문 문장**이다. 표 행으로 세면 안 된다.

### 3.2 인식된 행조차 텍스트 열이 무너져 있다

C 경로의 실제 행(발췌 · 기술 텍스트만):

```
1 반응 챔버 동일                                     ← 한쪽 열만 남음
2 다수의 셀 다이오드 동일                            ← 한쪽 열만 남음
1 하여 선택적으로 등방성 에칭하는 드라 SiO 를 선택적으로 사이드 에칭하는 플 동일
                                                     ↑ 두 열이 있으나 양쪽 다 단어 중간에서 끊김
10 at.% 내지 약 40 at.% 범위의 탄소 함 25.1 내지 39%의 탄소 농도를 갖는 방 동일
```

**이것은 (본원 구성, 인용 개시) 쌍이 아니다.** 조각이다. 엄격 A 에서도 본문이 4자 미만인
행이 **142 / 305** 다.

> **그러므로 이 층에서 텍스트 쌍을 추출한다고 주장하면 안 된다.** 원 분석 §3.1 이
> *"삼중항이 표로 있다"* 고 적은 것은 **PDF 원본에 대해서는 참**이지만 **OCR 산출 텍스트에
> 대해서는 참이 아니다.** 우리가 가진 것은 후자다.

### 3.3 신뢰할 수 있는 것 — 구조 키와 판정 라벨

`<표 N>` 서식의 행 머리 `구성 <청구항번호>-<구성번호>` 는 **청구항 구성요소를 직접 가리키는
키**이고, OCR 로 뭉개지지 않는다(숫자와 하이픈뿐). 여기에 판정 라벨이 붙는다.

| 산출 | 값 |
|---|---:|
| **(출원, 청구항, 구성, 판정) 고유 키** | **305** |
| 그 키를 가진 출원 | **26** |
| C 경로 — 청구항 키 없음, 행번호와 판정만 | 611행 / 151출원 |

판정 어휘 분포(문서 전체 출현): `동일` 8,498 · `차이` 4,050 · `대응` 1,645 ·
`설계변경` 663 · `실질적 동일` 396 · `유사` 327 · `주지관용` 103.

---

## 4. 누출 분할을 적용하면

`harvest_scope_dev_train.json`(dev 200 + train 600) 기준. 통지서 출원 1,000 중 **799** 가
범위 안이다.

| | 전수 | scope 안 | 손실 |
|---|---:|---:|---:|
| 엄격 A 행 | 305 (26출원) | **305 (26출원)** | **0%** |
| C 행 | 611 (151출원) | 447 (103출원) | 27% |

**핵심 축(엄격 A)은 누출 통제로 한 행도 잃지 않는다.**

**`check_leakage.py` 는 없다.** `grep -rn check_leakage scripts/ tests/` 는 빈 출력이고,
이름은 PLAN-001 §O-4 에만 있다. 지금 누출을 실제로 막는 것은 위 scope 파일 하나다.

---

## 5. 결정서와의 관계

| | 값 |
|---|---:|
| 결정서 `cited_evidence_map` 보유 | **384 / 979 문서** · 항목 **900** |
| 통지서 `legal_basis` 보유 출원 (2-A 정본) | 697 |
| 교집합 | **357** · 결정서만 27 · 통지서만 340 |

즉 2-C 가 다룰 통지서 표는 **대부분 이미 2-A·2-B 가 인용 해소를 끝낸 출원**에 있다.
인용발명 번호 → 문헌 해소를 **새로 만들 필요가 없다**.

---

## 6. 재현 명령

```bash
# §2 서식 조합 — 위 표를 그대로 낸다
.venv/bin/python - <<'PY'
import re, glob
from collections import Counter
HAS   = re.compile(r'구\s*성.{0,40}?비\s*고', re.S)
A_OPEN= re.compile(r"^\s*<\s*표\s*\d+\s*>\s*$")
A_ROW = re.compile(r"구성\s*\d+\s*[-–]\s*[가-힣0-9]+")
B_HEAD= re.compile(r"구성\s*청구항\s*\d+\s*발명\s*인용발명\s*\d+")
C_ROW = re.compile(r'^\s*\d{1,2}\s+.*?\s(동일|차이|유사|대응)\s*$')
doc = Counter(); n_has = 0
for f in sorted(glob.glob('data/sources/opinion_notices/txt/*.txt')):
    t = open(f, encoding='utf-8', errors='replace').read()
    has = bool(HAS.search(t)); n_has += has
    in_a = False; ra = rc = 0
    for ln in t.split('\n'):
        if A_OPEN.match(ln): in_a = True; continue
        if in_a and not ln.strip(): in_a = False; continue
        if in_a and A_ROW.search(ln): ra += 1
        if C_ROW.match(ln): rc += 1
    k = (ra > 0, bool(B_HEAD.search(t)), rc > 0)
    doc[k] += 1
    if has: doc[('HAS',) + k] += 1
print('HAS =', n_has)
for k in sorted(doc, key=lambda x: (len(x), -doc[x])): print(k, doc[k])
PY

# §3.1·§3.3 정밀도와 구조 키 · §4 누출 범위 적용
.venv/bin/python - <<'PY'
import json, re, glob
scope = json.load(open('data/sources/harvest_scope_dev_train.json'))
norm = lambda s: re.sub(r'\D', '', str(s))
apps = {norm(a) for a in scope['application_numbers']}
A_OPEN = re.compile(r"^\s*<\s*표\s*\d+\s*>\s*$")
J = r"(실질적\s*동일|주지관용|설계변경|동일|차이|유사|대응)"
LOOSE  = re.compile(r"구성\s*\d+\s*[-–]\s*[가-힣0-9]+")
STRICT = re.compile(rf"^\s*구성\s*(\d+)\s*[-–]\s*(\d+)\s+(.*?)\s*{J}\s*$")
C_ROW  = re.compile(rf"^\s*(\d{{1,2}})\s+(.*?)\s*{J}\s*$")
loose = strict = short = c_all = c_in = a_in = 0
docs_a = set(); docs_c = set(); docs_a_in = set(); docs_c_in = set()
for f in sorted(glob.glob('data/sources/opinion_notices/txt/*.txt')):
    app = norm(f.split('/')[-1].split('_')[0]); inside = app in apps
    in_a = False
    for ln in open(f, encoding='utf-8', errors='replace'):
        ln = ln.rstrip('\n')
        if A_OPEN.match(ln): in_a = True; continue
        if in_a and not ln.strip(): in_a = False; continue
        if in_a and LOOSE.search(ln):
            loose += 1
            m = STRICT.match(ln)
            if m:
                strict += 1; docs_a.add(app); short += len(m.group(3)) < 4
                if inside: a_in += 1; docs_a_in.add(app)
        if C_ROW.match(ln):
            c_all += 1; docs_c.add(app)
            if inside: c_in += 1; docs_c_in.add(app)
print(f"느슨 {loose} → 엄격 {strict} ({strict/loose:.1%}) · 본문 4자 미만 {short}")
print(f"엄격 A : 전수 {strict}행/{len(docs_a)}출원 · scope {a_in}행/{len(docs_a_in)}출원")
print(f"C 경로 : 전수 {c_all}행/{len(docs_c)}출원 · scope {c_in}행/{len(docs_c_in)}출원")
PY

# §5 결정서 대조
.venv/bin/python - <<'PY'
import json, glob, pandas as pd
dec = {}; n = 0
for f in glob.glob('data/sources/rejection_decisions/structured/*.json'):
    d = json.load(open(f)); m = d.get('cited_evidence_map')
    if m: dec[str(d.get('application_number'))] = m; n += len(m)
notice = set(pd.read_parquet('data/patents/notice_legal_basis.parquet')['application_number'].astype(str))
print(f"결정서 map {len(dec)}문서 · 항목 {n} · 통지서 {len(notice)}출원 "
      f"· 교집합 {len(set(dec) & notice)} · 결정서만 {len(set(dec) - notice)} · 통지서만 {len(notice - set(dec))}")
PY
```

---

## 7. 보정 — 앞 숫자는 청구항 번호가 아니다 (2026-09-06 · 4단계 중 발견)

**§0-3 이 처음 `구성 <청구항번호>-<구성번호>` 라 적은 것은 틀렸다.** 구현 중 사람 대조
시트에 표 블록을 넣으면서 드러났다.

`1020127009380` 한 문서 안에서:

```
51 | 1. 청구항 1 발명과 인용발명1, 2를 비교해 보면 아래 표1과 같습니다.
52 | <표1>
56 | 구성 1-1 순도 99.99% 구리 | 구리 순도 6N 이상 | 실질적 동일

95 | 3. 청구항 3 발명과 인용발명1, 2를 비교해 보면 아래 표2와 같습니다.
96 | <표2>
100 | 구성 2-1 순도 99.99% 구리 | 구리 순도 6N 이상 | 실질적 동일
```

`<표2>` 의 `구성 2-N` 은 **청구항 3** 의 구성이다. 앞 숫자는 **표 단위 구성 그룹 번호**이며
청구항 번호는 **캡션**에 있다.

| 전수 대조 (캡션 = 표 여는 줄 앞 5줄 + 블록 안 6줄) | 행 | 비율 |
|---|---:|---:|
| 캡션과 앞 숫자 일치 | 258 | 84.6% |
| **불일치** | **9** | **3.0%** |
| 캡션 없음 | 38 | 12.5% |

검색창을 넓혀도 회복이 멈춘다 — 앞 3줄/5줄은 동일하고, 블록 안 6줄을 더하면 캡션없음이
41 → 38 로 줄어든 뒤 앞 8줄+안 8줄에서도 38 그대로다.

재현은 `scripts/build_notice_element_judgments.py` 를 돌려
`data/reports/notice_element_judgments_report.json` 의 `caption_claim_resolved`(267) 와
`caption_differs_from_group`(9) 을 읽으면 된다 — 생성기가 이 두 수를 상시 싣는다.

**교훈은 규칙이 아니라 시트에 있다.** 초판 대조 시트는 행 한 줄만 담았고, 그러면 사람이
`구성 2-3` 의 `2` 가 무엇인지 볼 수 없다 — **대조할 수 없는 시트는 게이트가 아니라
서명란이다.** 지금 시트는 캡션 줄과 `<표 N>` 블록(최대 45줄)을 함께 싣는다.
