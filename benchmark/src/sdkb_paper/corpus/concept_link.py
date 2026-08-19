"""개념 적용기 — 사전을 특허 본문에 적용해 개념 링크를 만든다 (PLAN-034 §3.4 신규② · D-19).

**왜 이 모듈이 있는가.** 상류가 CR-007 로 개념 사전을 냈지만 하류에 적용기가 없어
`ir_corpus_v09.parquet` 의 서명이 한 바이트도 변하지 않았고, 그래서 O 대 O′ 의 ΔR₁₀₀ 이
정의상 0 이 되어 **H2(갱신 승인 안전성)가 공허하게 통과**했다(D-19). 이 모듈이 그 통로다.

**규칙(3단계 설계에서 동결 · 결과를 본 뒤 바꾸지 않는다):**

1. **정규화** — 문서·표면형 모두 R1-NORMALIZE 한 번(`ontology.concept_dict.normalize`).
2. **경계(BOUND)** — 라틴/숫자를 포함한 표면형은 양끝이 `[a-z0-9]` 가 아닐 것을 요구한다.
   2단계 실측: 경계 없이 보면 영어 문서가 문서당 9.962 개념을 얻지만 그것은 이득이 아니라
   위양성이다(`al` ⊂ *metal* · `co` ⊂ *coating*). 한글 전용 표면형은 부분문자열.
3. **표면형 독립 판정** — 한 표면형의 발화는 다른 표면형과 무관하게 정한다. 정규식 교체로
   훑으면 먼저 매치한 표면형이 뒤 문자를 소비해 **사전 순서에 결과가 의존**한다(S1 위반).
4. **역할 무관** — `match()` 는 질의/후보를 구분하는 인자를 받지 않는다. 질의·후보 비대칭은
   T1 을 오염시키므로 **구조로** 막는다(PLAN-034 §3.1 결정 D).
5. **가중 없음** — confidence 는 사이드카에 기록만 하고 점수에 반영하지 않는다(결정 B).
   점수식을 건드리면 재측정이 아니라 새 방법이다.

**경계:** 사전이 비면 아무것도 하지 않는다(O 팔 · 무작동 동치성). 사전의 오링크(D-20 `hf` →
불산)는 하류에서 고치지 않는다 — 우회 패치는 스냅샷 출처를 거짓으로 만든다(§0.1).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .. import config
from ..ontology import concept_dict
from ..ontology.concept_dict import Surface

# 경계 문자 집합 = 정규식 `[a-z0-9]`. 정규화 후 텍스트는 소문자이므로 ASCII 만 본다.
_BOUND_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")


def _as_set(cell) -> set[str]:
    """`concepts` 셀(list · numpy 배열 · None)을 집합으로. 배열에 `or` 를 쓰면 터진다."""
    if cell is None:
        return set()
    if hasattr(cell, "tolist"):
        cell = cell.tolist()
    return {str(x) for x in cell}


def _fires(text: str, surface: Surface) -> bool:
    """정규화된 텍스트에 표면형이 (경계 규칙을 지키며) 나타나는가."""
    needle = surface.text
    if not needle or not text:
        return False
    if not surface.bound:
        return needle in text
    n = len(needle)
    i = text.find(needle)
    while i != -1:
        left_ok = i == 0 or text[i - 1] not in _BOUND_CHARS
        j = i + n
        right_ok = j >= len(text) or text[j] not in _BOUND_CHARS
        if left_ok and right_ok:
            return True
        i = text.find(needle, i + 1)
    return False


def match(text: str, surfaces: tuple[Surface, ...]) -> tuple[Surface, ...]:
    """텍스트(원문)에 발화한 표면형 — 사전 순서 그대로(정렬됨). **역할 인자 없음.**"""
    norm = concept_dict.normalize(text)
    if not norm:
        return ()
    return tuple(s for s in surfaces if _fires(norm, s))


def concept_ids(fired: tuple[Surface, ...]) -> frozenset[str]:
    """발화 표면형 → concept_id 집합(접두어 포함 · 사이드카용)."""
    return frozenset(e.concept_id for s in fired for e in s.entries)


def slugs(fired: tuple[Surface, ...]) -> frozenset[str]:
    """발화 표면형 → 지역명 집합(코퍼스 `concepts` 열의 키 · 결정 A)."""
    return frozenset(e.slug for s in fired for e in s.entries)


def link_corpus(texts, doc_ids, surfaces: tuple[Surface, ...]):
    """문서별 (지역명 집합) 과 감사 사이드카를 만든다.

    반환: `(list[frozenset[str]], pandas.DataFrame)`. 사전이 비면 빈 집합들과 빈 DF.
    사이드카 행: doc_id · concept_id · slug · axis(사전 concept_type) · surface · rule_id ·
    confidence · ambiguous. 행 순서는 (doc_id, concept_id, surface) 사전순으로 결정적이다.
    """
    import pandas as pd

    cols = ["doc_id", "concept_id", "slug", "axis", "surface", "rule_id",
            "confidence", "ambiguous"]
    per_doc: list[frozenset[str]] = []
    rows: list[tuple] = []
    if not surfaces:
        return [frozenset() for _ in range(len(doc_ids))], pd.DataFrame(columns=cols)

    for doc_id, text in zip(doc_ids, texts):
        fired = match(text, surfaces)
        per_doc.append(slugs(fired))
        for s in fired:
            for e in s.entries:
                rows.append((str(doc_id), e.concept_id, e.slug, e.concept_type,
                             s.text, e.rule_id, e.confidence, e.ambiguous))
    df = pd.DataFrame(rows, columns=cols)
    if len(df):
        df = (df.sort_values(["doc_id", "concept_id", "surface"])
                .reset_index(drop=True))
    return per_doc, df


def apply_to_corpus(corpus, surfaces: tuple[Surface, ...] | None = None):
    """코퍼스의 `concepts` 열을 **제자리에서** 그래프 링크 ∪ 적용기 링크로 바꾼다(Q4 합집합).

    사전이 비면 **열을 건드리지 않는다** — 그래야 O 팔의 코퍼스가 바이트 단위로 재현된다
    (PLAN-034 §3.3). 반환은 감사 사이드카 DataFrame.
    """
    import pandas as pd

    surfaces = concept_dict.load() if surfaces is None else surfaces
    before = corpus["concepts"].map(len).tolist()
    if not surfaces:
        print("      개념 사전 없음 — 적용기 무작동(스냅샷에 concept_mapping.json 이 없다)",
              flush=True)
        empty = pd.DataFrame(columns=["doc_id", "concept_id", "slug", "axis", "surface",
                                      "rule_id", "confidence", "ambiguous"])
        empty.attrs["before_counts"] = before
        return empty

    linked, sidecar = link_corpus(corpus["text_main"], corpus["doc_id"], surfaces)
    # parquet 왕복 후에는 `concepts` 셀이 numpy 배열이다 — `or` 는 배열에 쓸 수 없다.
    corpus["concepts"] = [sorted(_as_set(old) | new)
                          for old, new in zip(corpus["concepts"], linked)]
    sidecar.attrs["before_counts"] = before
    after = corpus["concepts"].map(len)
    print(f"      개념 적용기: 표면형 {len(surfaces):,} · 링크 {len(sidecar):,}건 "
          f"· 문서당 개념 {pd.Series(before).mean():.3f} → {after.mean():.3f}", flush=True)
    return sidecar


def write_sidecar(sidecar) -> None:
    """감사 사이드카를 쓴다. `attrs`(before_counts)는 산출물에 넣지 않는다 — 프로파일용 임시값."""
    config.IR_DIR.mkdir(parents=True, exist_ok=True)
    out = sidecar.copy()
    out.attrs = {}
    out.to_parquet(config.IR_CONCEPT_LINKS, index=False)


# --- §4 데이터 프로파일 -------------------------------------------------------

# 하류가 고치지 않고 **보고만 하는** 사전 결함(§0.1 · 상류 CR 대상).
KNOWN_DEFECTS = (
    ("hf", "material:hf_acid", "D-20(P1) 반도체 특허의 단독 Hf 는 하프늄(high-k)이다 — 불산 오링크"),
    ("co", "material:cobalt", "D-20 부수 위험: CO(일산화탄소)·Co.(회사명) 혼입 가능"),
    ("high k", "material:hfO2", "D-20 부수: 부류(high-k)를 특정 물질로 축소하는 과대특정"),
)


def write_profile(corpus, sidecar, surfaces: tuple[Surface, ...],
                  before: list[int] | None = None) -> None:
    """`data/profiles/concept_link.md` (CLAUDE.md §4 의무 4항목). 커밋 대상 = 집계뿐."""
    import pandas as pd

    out = config.DATA / "profiles" / "concept_link.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    s = concept_dict.summary(surfaces)
    n_docs = len(corpus)
    n_after = corpus["concepts"].map(len)
    fired_surfaces = sidecar["surface"].nunique() if len(sidecar) else 0
    vocab_after = sorted({c for cs in corpus["concepts"] for c in cs})

    lines = [
        "# 개념 적용기 프로파일 — concept_link (PLAN-034 · D-19)",
        "",
        "> 코드 생성물. 재생성: `make corpus`. 원문은 담지 않는다 — 표면형은 **사전의 어휘**이지",
        "> 특허 본문이 아니다(CLAUDE.md §1-5·§4).",
        "",
        f"- 생성(UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- 지지 주장: **C3**(O/O′ 개념 링크 델타를 0 이 아니게 만들어 H2 를 검정 가능하게) · C0(D-19)",
        f"- 사전: `{config.SDKB_CONCEPT_MAP.name}` 프로파일 `{concept_dict.PROFILE}`",
        "",
        "## 1. 구조 (사이드카 컬럼·목적)",
        "| 컬럼 | 목적 |",
        "|---|---|",
        "| doc_id | 코퍼스 문서 식별자 |",
        "| **concept_id** | 접두어(축) 포함 정본 식별자 — 코퍼스 `concepts` 열은 지역명만 보관하므로 **축은 여기에만 남는다** |",
        "| slug | 지역명 = 코퍼스 `concepts` 의 키(결정 A) |",
        "| axis | 사전 `concept_type` |",
        "| surface | 발화한 정규화 표면형 |",
        "| rule_id·confidence·ambiguous | 상류 규칙 출처 — **점수에 반영하지 않는다**(결정 B) |",
        "",
        "## 2. 형태",
        f"- 사전: 표면형 **{s['n_surfaces']:,}** (경계요구 {s['n_bound']:,} · 한글전용 "
        f"{s['n_hangul_only']:,}) · 항목 {s['n_entries']:,} · 개념 {s['n_concepts']:,} "
        f"· 지역명 {s['n_slugs']:,} · 다의 표면형 {s['n_ambiguous_surfaces']:,}",
        f"- 발화 표면형: **{fired_surfaces:,}/{s['n_surfaces']:,}** "
        f"(무발화 {s['n_surfaces'] - fired_surfaces:,} — 특허 산문에 안 나오는 장비 모델명·"
        f"Vendor 중심. **결함이 아니다**(설계 결정 C))",
        f"- 신규 링크: **{len(sidecar):,}건** · 문서 {n_docs:,}",
        f"- 문서당 개념(합집합): 평균 **{n_after.mean():.3f}** · 중앙값 {n_after.median():.0f} "
        f"· 보유율 {(n_after > 0).mean():.1%}",
        f"- 개념 어휘(합집합): **{len(vocab_after)}**",
    ]
    if before is not None:
        b = pd.Series(before)
        lines.append(f"- 적용 전: 문서당 평균 {b.mean():.3f} · 보유율 {(b > 0).mean():.1%}")

    lines += ["", "## 3. 기술통계", "", "### 3.1 언어별 (T2 하위집단의 사전 관측)",
              "| lang | 문서 | 적용기 링크 | 문서당 신규 | 합집합 문서당 |", "|---|---:|---:|---:|---:|"]
    per_doc_new = sidecar.groupby("doc_id")["slug"].nunique() if len(sidecar) else pd.Series(dtype=int)
    tmp = pd.DataFrame({
        "lang": corpus["lang"].values,
        "doc_id": corpus["doc_id"].astype(str).values,
        "after": n_after.values,
    })
    tmp["new"] = tmp["doc_id"].map(per_doc_new).fillna(0).astype(int)
    for lg, g in tmp.groupby("lang"):
        lines.append(f"| {lg} | {len(g):,} | {int(g['new'].sum()):,} | {g['new'].mean():.3f} "
                     f"| {g['after'].mean():.3f} |")
    lines += [
        "",
        "> **일본어는 이 모듈로 열리지 않는다** — 사전의 `lang: ja` 표면형이 0개라 구조적 0이다.",
        "> D-21(CR-003 후속) 대상이며, 여기 수치가 그 사실의 관측이다(PLAN-034 §6 위험 A 확증).",
        "",
        "### 3.2 축 분포 (적용기 신규 링크 기준)",
        "| 축 | 링크 | 비율 |", "|---|---:|---:|",
    ]
    if len(sidecar):
        ax = Counter(sidecar["axis"])
        tot = sum(ax.values())
        for a, c in ax.most_common():
            lines.append(f"| {a or '(미상)'} | {c:,} | {c / tot:.1%} |")
        lines += [
            "",
            "> D-15 는 전문가용 사전을 특허에 적용하면 Skill 축이 18.1 % 를 먹는다고 경고했다. "
            "`patent-text` 프로파일에서 그 값이 얼마인지가 **상류 교정(CR-007)이 작동했는지의 "
            "하류 확인**이다.",
            "",
            "### 3.3 다의 표면형 (Q3: 후보 전부 유지)",
            "| 표면형 | 문서 | 개념 |", "|---|---:|---|",
        ]
        amb = sidecar[sidecar["ambiguous"]]
        if len(amb):
            for surf, g in sorted(amb.groupby("surface"), key=lambda kv: -kv[1]["doc_id"].nunique())[:15]:
                lines.append(f"| `{surf}` | {g['doc_id'].nunique():,} | "
                             f"{', '.join(sorted(set(g['concept_id'])))} |")
        else:
            lines.append("| (없음) | 0 | — |")
        lines += ["", "### 3.4 df 상위 표면형", "| 표면형 | 문서 | 개념 |", "|---|---:|---|"]
        top = (sidecar.groupby("surface")["doc_id"].nunique().sort_values(ascending=False).head(15))
        for surf, cnt in top.items():
            cids = sorted(set(sidecar.loc[sidecar["surface"] == surf, "concept_id"]))
            lines.append(f"| `{surf}` | {cnt:,} | {', '.join(cids)} |")

    lines += [
        "",
        "## 4. 알려진 사전 결함 — **하류에서 고치지 않는다**",
        "",
        "우회 패치는 스냅샷 출처를 거짓으로 만든다(CLAUDE.md §0.1). 그대로 통과시키고 상류 CR 로 회신한다.",
        "",
        "| 표면형 | 매핑 | 문서 | 문제 |", "|---|---|---:|---|",
    ]
    for surf, cid, why in KNOWN_DEFECTS:
        n = (sidecar[(sidecar["surface"] == surf) & (sidecar["concept_id"] == cid)]["doc_id"]
             .nunique() if len(sidecar) else 0)
        lines.append(f"| `{surf}` | `{cid}` | {n:,} | {why} |")

    lines += [
        "",
        "## 5. 사용 목적",
        "- 코퍼스 `concepts` 열 → 온톨로지 재랭크팔(P0★·P1)·B5 독립팔의 입력.",
        "- 사이드카 `concept_id` → 축 지도 확장(A2/A3/A8 절제가 신규 개념을 누락하지 않게).",
        "- 언어별 표 → T2 하위집단 해석의 사전 관측(판정은 `make gate` 가 한다).",
        "- **점수 가중에는 쓰지 않는다** — confidence·rule_id 는 감사·회신 전용(결정 B).",
        "",
        "## 6. 누출 통제",
        "- 사전은 온톨로지 개념 어휘에서만 유도되며 인용 간선(`hasPriorArt*`)을 보지 않는다.",
        "  그 진술을 믿지 않고 `make leakage` 가 사전 파일을 직접 열어 재확인한다(L-2).",
        "- 질의·후보에 **같은 함수·같은 사전**이 적용된다 — `match()` 는 역할 인자를 받지 않는다.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"프로파일: {out}")
