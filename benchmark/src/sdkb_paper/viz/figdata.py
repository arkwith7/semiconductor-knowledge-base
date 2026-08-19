"""개념 그림이 인용하는 수치의 단일 원천 (CLAUDE.md §1-1 · 그림 규격 F6).

**왜 이 모듈이 있는가.** 데이터 플롯은 CSV 를 그리므로 수치가 저절로 정합한다. 그러나
개념 도식은 사정이 다르다 — `−0.0293`·`2.4배`·`12/45` 같은 값이 **그림 코드 안에 손으로**
적히면, 재측정으로 본문이 갱신돼도 그림은 옛 값을 계속 보여준다. 본문과 그림의 수치
불일치는 심사에서 자주 지적되는 결함이며, 사람의 주의력으로는 막히지 않는다.

그래서 값을 **산출물에서 기계로 뽑아** `paper/figures/data/concept_values.json` 에 동결하고,
그림은 그 파일만 읽는다. 각 값은 자기 **출처 파일과 추출 방식**을 함께 갖는다.

**출처를 왜 이렇게 골랐는가.** 원칙은 하나다 — **원고가 인용하는 바로 그 산출물**을 읽는다.
같은 값이 여러 곳에 있어도 파생본을 읽지 않는다. 특히 EP3(통제된 자원 교체)의 값은
`data/processed/` 에 남아 있지 않다: 디스크의 최종 상태는 O′ 팔 하나뿐이고 O 팔의 수치는
사전등록 문서에만 기록돼 있다(메모리 `disk-resource-is-oprime-manuscript-is-o-arm`).
따라서 EP3 의 원천은 **사전등록 문서 PLAN-035** 이며, 이는 감사 기록이므로 재실행으로
바뀌지 않는다.

**우연의 일치를 조심한다.** 같은 숫자 문자열이 다른 뜻으로 다른 표에 있다 — 예컨대
`ir_performance_test.md` 에도 `-0.0293` 이 있으나 그것은 EP3 의 ΔR₁₀₀ 이 아니라 P1 의
nDCG 계열 델타다. 그래서 아래 패턴은 전부 **행 전체를 앵커로** 잡는다. 숫자만 찾는 패턴은
쓰지 않는다.

사용:
    make figure-data      # 산출물 → JSON 재동결 (표류하면 diff 로 드러난다)
    load()                # 그림 코드가 읽는 진입점
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdkb_paper.config import FIGURES, ROOT

FROZEN = FIGURES / "data" / "concept_values.json"

# 출처 파일 — 전부 저장소 안의 산출물이다.
_PLAN035 = "01.code_spec/archive/PLAN-035-h2-linker-preregistration.md"
_FAULT_V4 = "paper/tables/fault_matrix_v4.md"
_EFFORT = "paper/tables/ir_effort_test.md"
_INCREMENT = "data/processed/ir/ir_increment_delta_test.csv"
_T4 = "data/processed/ir/rag/scores/rag_t4_verdict_test_b.json"
_S5 = "paper/supplementary/S5-submission-full-v2.md"
_TGATE = "data/processed/tgate_report_test.json"
# 실험 구성도(PLAN-056)가 쓰는 값의 출처. 설계 상수는 **코드가 원천**이다 — 산문에 적힌
# 숫자를 읽으면 코드가 바뀌어도 그림이 따라오지 않는다.
_SYSTEMS = "src/sdkb_paper/retrieval/systems.py"
_HYBRID = "src/sdkb_paper/retrieval/hybrid.py"
_PERF = "data/processed/ir/ir_performance_test.csv"
_PERF_B = "data/processed/ir/ir_performance_test_b.csv"
_CEILING = "data/processed/ir/rerank_ceiling_test.json"
# 표 3(세 태스크 뷰)의 앵커 — 캡션이 아니라 바로 앞 문장을 잡는다. 캡션 문자열은
# 파생본 재편으로 번호가 바뀌지만 이 문장은 동결 전문의 것이라 움직이지 않는다.
_S5_VIEW_ANCHOR = r"각 \(V_t=(C_t,R_t,Q_t)\)는 태스크별"


@dataclass(frozen=True)
class Rule:
    """값 하나를 산출물에서 뽑는 방법. `how` 는 JSON 에 그대로 기록된다."""

    key: str
    source: str
    how: str
    pattern: str | None = None          # regex 규칙
    group: int = 1
    json_path: tuple[str, ...] = ()     # json 규칙
    csv_match: tuple[str, str] = ()     # csv 규칙 — (열, 부분문자열)
    csv_field: str = ""
    row_key: str = ""                   # 표 행 규칙 — 첫 칸의 값
    glob: str = ""                      # 파일 묶음 규칙 — 헤더를 세는 대상
    suite: str = ""
    cast: str = "float"


# CQ 스위트 계수에서 제외하는 질의 — CQ29·30·31 은 **측정용**이며 게이트가 세는 28개에
# 들어가지 않는다(원고 §4.4 "합집합이 CQ 28개 전량"). 파일에는 `pa` 로 적혀 있으므로
# 제외하지 않으면 pa 가 8 로 세어진다.
CQ_MEASUREMENT_ONLY = ("CQ29", "CQ30", "CQ31")


# ── 규칙표 ────────────────────────────────────────────────────────────────────
# 순서는 그림에서 읽히는 순서(자원 층 → 검색 층 → 생성 층)를 따른다.
RULES: list[Rule] = [
    # ① 자원 층 → 검색 층 · EP3 통제된 자원 교체 (사전등록 PLAN-035 · O vs O′)
    Rule("ep3.concepts_per_doc.before", _PLAN035, "자원 델타 표 · 문서당 개념 (O 팔)",
         pattern=r"\|\s*코퍼스 문서당 개념\s*\|\s*([\d.]+)\s*\|"),
    Rule("ep3.concepts_per_doc.after", _PLAN035, "자원 델타 표 · 문서당 개념 (O′ 팔)",
         pattern=r"\|\s*코퍼스 문서당 개념\s*\|\s*[\d.]+\s*\|\s*\*\*([\d.]+)\*\*\s*\|"),
    Rule("ep3.concept_vocab.before", _PLAN035, "자원 델타 표 · 개념 어휘 (O 팔)",
         pattern=r"\|\s*개념 어휘\s*\|\s*(\d+)\s*\|", cast="int"),
    Rule("ep3.concept_vocab.after", _PLAN035, "자원 델타 표 · 개념 어휘 (O′ 팔)",
         pattern=r"\|\s*개념 어휘\s*\|\s*\d+\s*\|\s*\*\*(\d+)\*\*\s*\|", cast="int"),
    Rule("ep3.b5.before", _PLAN035, "절대값 표 · B5 온톨로지 단독 R@100 (O 팔)",
         pattern=r"\|\s*\*\*B5 \(온톨로지 단독\)\*\*\s*\|\s*([\d.]+)\s*→"),
    Rule("ep3.b5.after", _PLAN035, "절대값 표 · B5 온톨로지 단독 R@100 (O′ 팔)",
         pattern=r"\|\s*\*\*B5 \(온톨로지 단독\)\*\*\s*\|\s*[\d.]+\s*→\s*\*\*([\d.]+)\*\*"),
    Rule("ep3.p1.before", _PLAN035, "T1 판정행 · 교체 대상 구성 R@100 (O 팔)",
         pattern=r"\*\*T1\*\* family Recall@100[^|]*\|\s*([\d.]+)\s*→"),
    Rule("ep3.p1.after", _PLAN035, "T1 판정행 · 교체 대상 구성 R@100 (O′ 팔)",
         pattern=r"\*\*T1\*\* family Recall@100[^|]*\|\s*[\d.]+\s*→\s*\*\*([\d.]+)\*\*"),
    Rule("ep3.p1.delta", _PLAN035, "T1 판정행 · ΔR₁₀₀ (부호는 음수)",
         pattern=r"\*\*T1\*\* family Recall@100.*?Δ\s*\*\*−([\d.]+)\*\*", cast="neg_float"),
    Rule("ep3.p1.ci_lo", _PLAN035, "T1 판정행 · 95% CI 하한",
         pattern=r"\*\*T1\*\* family Recall@100.*?95% CI \[−([\d.]+),", cast="neg_float"),
    Rule("ep3.p1.ci_hi", _PLAN035, "T1 판정행 · 95% CI 상한",
         pattern=r"\*\*T1\*\* family Recall@100.*?95% CI \[−[\d.]+, −([\d.]+)\]", cast="neg_float"),
    Rule("ep3.t2_max_drop", _PLAN035, "T2 판정행 · 하위집단 최대 하락",
         pattern=r"\*\*T2\*\* 하위집단[^|]*\|\s*max drop \*\*\+([\d.]+)\*\*"),
    # ② 검색 층 · EP4 증분 (봉인 분할 확증 · A층)
    Rule("ep4.p1_gain.delta", _INCREMENT, "증분 CSV · 온톨로지 추가 행",
         csv_match=("label", "온톨로지 추가"), csv_field="delta"),
    Rule("ep4.p1_gain.lb95", _INCREMENT, "증분 CSV · 온톨로지 추가 행",
         csv_match=("label", "온톨로지 추가"), csv_field="lb95"),
    Rule("ep4.p1_gain.ub95", _INCREMENT, "증분 CSV · 온톨로지 추가 행",
         csv_match=("label", "온톨로지 추가"), csv_field="ub95"),
    Rule("ep4.p1_gain.p", _INCREMENT, "증분 CSV · 온톨로지 추가 행",
         csv_match=("label", "온톨로지 추가"), csv_field="p_two_sided"),
    Rule("ep4.n_queries", _INCREMENT, "증분 CSV · 평가 질의 수",
         csv_match=("label", "온톨로지 추가"), csv_field="n_queries", cast="int"),
    # ②′ 검색 층 · EP4 두 번째 확증 분할 (B층). **A층과 같은 키를 돌려 쓰지 않는다** —
    # 두 분할은 통합하지도 평균하지도 않으므로(원고 §5.4.1 주의) 값도 따로 선다.
    Rule("ep4b.p1_gain.delta", _PERF_B, "성능 CSV(B층) · 부차 구성의 Δ family Recall@100",
         csv_match=("system", "P1"), csv_field="d_recall"),
    Rule("ep4b.p1_gain.lb95", _PERF_B, "성능 CSV(B층) · 부차 구성의 95% CI 하한",
         csv_match=("system", "P1"), csv_field="lb_recall"),
    # ② 검색 층 → 운용 단위 · 검토 건수 (탐색적)
    Rule("effort.median_reduction_pct", _EFFORT, "Candidate Reduction 표 · R=0.5 행",
         pattern=r"\|\s*R=0\.5\s*\|\s*\d+\s*\|\s*([\d.]+)%"),
    Rule("effort.win_tie_loss", _EFFORT, "Candidate Reduction 표 · R=0.5 행",
         pattern=r"\|\s*R=0\.5\s*\|\s*\d+\s*\|\s*[\d.]+%\s*\|\s*(\d+/\d+/\d+)", cast="str"),
    # ③ 검색 층 → 생성 층 · T4 판정 (B층 확증)
    Rule("t4.citation_precision.delta", _T4, "T4 판정 JSON · 주 지표 점추정",
         json_path=("stats", "citation_precision", "delta")),
    Rule("t4.citation_precision.lb95", _T4, "T4 판정 JSON · 주 지표 95% CI 하한",
         json_path=("stats", "citation_precision", "lb95")),
    Rule("t4.eps", _T4, "T4 판정 JSON · 동결 마진 ε_T4",
         json_path=("verdict", "eps_t4")),
    Rule("t4.hallucination.delta", _T4, "T4 판정 JSON · 환각률 점추정",
         json_path=("stats", "hallucination_rate", "delta")),
    Rule("t4.precision_noninferior", _T4, "T4 판정 JSON · 인용 정확도 비열등 조건",
         json_path=("verdict", "cond_precision_noninferior"), cast="bool"),
    Rule("t4.hallucination_bounded", _T4, "T4 판정 JSON · 환각률 상한 조건",
         json_path=("verdict", "cond_hallucination_bounded"), cast="bool"),
    # EP2 게이트 판별력 (홀드아웃 확증 · 주 τ=0.05)
    Rule("ep2.t3_only", _FAULT_V4, "τ 민감도 표 · 주 τ=0.05 행 · T3 단독 검출",
         pattern=r"\|\s*0\.05\s*\|\s*(\d+/\d+)\s*\|", cast="str"),
    Rule("ep2.t3_detected", _FAULT_V4, "τ 민감도 표 · 주 τ=0.05 행 · T3 검출",
         pattern=r"\|\s*0\.05\s*\|\s*\d+/\d+\s*\|\s*(\d+/\d+)\s*\|", cast="str"),
    Rule("ep2.l3_detected", _FAULT_V4, "τ 민감도 표 · 주 τ=0.05 행 · L3 검출",
         pattern=r"\|\s*0\.05\s*\|\s*\d+/\d+\s*\|\s*\d+/\d+\s*\|\s*(\d+/\d+)\s*\|", cast="str"),
    Rule("ep2.false_positive", _FAULT_V4, "τ 민감도 표 · 주 τ=0.05 행 · 위양성",
         pattern=r"\|\s*0\.05\s*\|(?:\s*\d+/\d+\s*\|){3}\s*(\d+/\d+)\s*\|", cast="str"),
    Rule("ep2.mcnemar_p", _FAULT_V4, "τ 민감도 표 · 주 τ=0.05 행 · McNemar p",
         pattern=r"\|\s*0\.05\s*\|(?:\s*\d+/\d+\s*\|){4}\s*([\d.]+)\s*\|"),
    # 승인식의 동결 임계 — T4 의 ε 와 값이 같으나 **출처가 다르다**. 같은 숫자라는 이유로
    # 한 키를 돌려 쓰면 T1 의 마진이 T4 산출물에 매달린다.
    Rule("gate.epsilon", _TGATE, "T-gate 판정 보고 · T1 비열등 마진",
         json_path=("epsilon",)),
    Rule("gate.delta", _TGATE, "T-gate 판정 보고 · T2 하위집단 임계",
         json_path=("delta",)),
    # T3 교차 태스크 CQ 스위트 — 판정행의 계수와 같아야 한다(em 6 · tf 5 · core 12).
    Rule("ep3.t3_suites", _PLAN035, "T3 판정행 · 스위트별 통과율",
         pattern=r"\*\*T3\*\* 교차 태스크 CQ \|\s*([^|]+?)\s*\|", cast="str"),
    # 세 태스크 뷰 — 그림이 표를 대체하므로 표의 칸을 그대로 읽는다(손으로 옮겨 적지 않는다).
    Rule("views.match", _S5, "표 3 · 전문가 매칭 행", pattern=_S5_VIEW_ANCHOR,
         row_key="전문가 매칭", cast="cells"),
    Rule("views.priorart", _S5, "표 3 · 선행기술조사 행", pattern=_S5_VIEW_ANCHOR,
         row_key="선행기술조사", cast="cells"),
    Rule("views.foresight", _S5, "표 3 · 기술예측 행", pattern=_S5_VIEW_ANCHOR,
         row_key="기술예측", cast="cells"),
    # 실험 구성도 — 파이프라인의 설계 상수와 재순위화 상한 (PLAN-056 §6.4).
    # 상한 값의 지위는 **탐색적 기술통계 · 문서 단위**이며 주 지표를 대체하지 않는다.
    Rule("flow.pool_depth", _SYSTEMS, "재랭크 풀 깊이 상수 POOL_K",
         pattern=r"\nPOOL_K = (\d+)", cast="int"),
    Rule("flow.rrf_c", _HYBRID, "순위 융합 상수 RRF_C",
         pattern=r"\nRRF_C = (\d+)", cast="int"),
    Rule("flow.b4_r100", _PERF, "성능 CSV · 분류 단독 구성의 family Recall@100",
         csv_match=("system", "B4_ipc"), csv_field="R@100"),
    Rule("ceiling.pool_ratio", _CEILING, "상한 JSON · 후보 풀 안의 정답 비율 (문서 단위)",
         json_path=("values", "pool_ceiling", "ratio")),
    Rule("ceiling.pool_hits", _CEILING, "상한 JSON · 후보 풀 안의 정답 엣지 수",
         json_path=("values", "pool_ceiling", "hits"), cast="int"),
    Rule("ceiling.edges", _CEILING, "상한 JSON · 분모 (확증 분할의 정답 엣지)",
         json_path=("denominator", "edges"), cast="int"),
    # CQ 스위트 크기 — 질의 파일의 머리글에서 센다(원고 산문이 아니라 실물이 원천).
    Rule("cq.pa", "queries/cq", "L3 가 관찰하는 주 태스크 스위트",
         glob="queries/cq/*.rq", suite="pa", cast="int"),
    Rule("cq.em", "queries/cq", "T3 스위트 · 전문가 매칭",
         glob="queries/cq/*.rq", suite="em", cast="int"),
    Rule("cq.tf", "queries/cq", "T3 스위트 · 기술예측",
         glob="queries/cq/*.rq", suite="tf", cast="int"),
    Rule("cq.core", "queries/cq", "T3 스위트 · 공유 코어",
         glob="queries/cq/*.rq", suite="core", cast="int"),
    Rule("cq.total", "queries/cq", "게이트가 세는 CQ 전량",
         glob="queries/cq/*.rq", suite="*", cast="int"),
]


def _cast(raw: Any, kind: str) -> Any:
    if kind == "int":
        return int(str(raw).replace(",", ""))
    if kind == "float":
        return float(raw)
    if kind == "neg_float":            # 문서가 유니코드 마이너스로 적은 값
        return -float(raw)
    if kind == "bool":
        return bool(raw)
    if kind == "cells":
        return [str(c) for c in raw]
    return str(raw)


def _table_row(path: Path, anchor: str, row_key: str) -> list[str]:
    """앵커 아래 표에서 첫 칸이 `row_key` 인 행의 칸들을 돌려준다.

    **표를 다시 타자하지 않기 위한 장치다**(`build_submission_stage3.py` 의 표 복사와 같은
    원칙). 그림이 표를 대체할 때 표의 글자를 손으로 옮겨 적으면 대체가 아니라 사본이 된다.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines) if anchor in ln]
    if len(hits) != 1:
        raise ValueError(f"앵커가 {len(hits)}회 매치 — 정확히 1회여야 한다: {anchor!r}")
    rows = [
        [c.strip() for c in ln.strip().strip("|").split("|")]
        for ln in lines[hits[0]:hits[0] + 30]
        if ln.lstrip().startswith("|")
    ]
    picked = [r for r in rows if r and r[0] == row_key]
    if len(picked) != 1:
        raise ValueError(f"행 '{row_key}' 이 {len(picked)}개 — 정확히 1개여야 한다")
    return picked[0]


def _suite_count(pattern: str, suite: str) -> int:
    """질의 파일의 `# suite:` 머리글을 세어 스위트 크기를 얻는다."""
    total = 0
    for path in sorted(ROOT.glob(pattern)):
        if path.name[:4] in CQ_MEASUREMENT_ONLY:
            continue
        head = re.search(r"^#\s*suite:\s*(\w+)", path.read_text(encoding="utf-8"), re.M)
        if head and (suite == "*" or head.group(1) == suite):
            total += 1
    return total


def _apply(rule: Rule) -> Any:
    if rule.glob:
        return _suite_count(rule.glob, rule.suite)
    path = ROOT / rule.source
    if not path.exists():
        raise FileNotFoundError(str(path))
    if rule.row_key:
        return _table_row(path, rule.pattern or "", rule.row_key)
    if rule.json_path:
        node: Any = json.loads(path.read_text(encoding="utf-8"))
        for step in rule.json_path:
            node = node[step]
        return _cast(node, rule.cast)
    if rule.csv_match:
        col, needle = rule.csv_match
        with path.open(encoding="utf-8") as fh:
            hits = [r for r in csv.DictReader(fh) if needle in r[col]]
        if len(hits) != 1:
            raise ValueError(f"{rule.key}: '{needle}' 행이 {len(hits)}개 — 정확히 1개여야 한다")
        return _cast(hits[0][rule.csv_field], rule.cast)
    text = path.read_text(encoding="utf-8")
    found = re.findall(rule.pattern or "", text, flags=re.DOTALL)
    if len(found) != 1:
        raise ValueError(f"{rule.key}: 패턴이 {len(found)}회 매치 — 정확히 1회여야 한다 ({rule.source})")
    return _cast(found[0], rule.cast)


def extract() -> dict[str, dict[str, Any]]:
    """산출물에서 값을 새로 뽑는다. 하나라도 실패하면 예외로 멈춘다 — 조용한 폴백은 없다."""
    return {
        r.key: {"value": _apply(r), "source": r.source, "how": r.how}
        for r in RULES
    }


def freeze(out: Path | None = None) -> Path:
    """산출물 → 동결 JSON. `make figure-data` 의 본체다."""
    out = out or FROZEN
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": (
            "개념 그림이 인용하는 수치의 동결본. 손으로 고치지 않는다 — "
            "산출물을 갱신한 뒤 `make figure-data` 로 재동결한다 (CLAUDE.md §1-1 · 그림 규격 F6)."
        ),
        "values": extract(),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def load(verify: bool = True) -> dict[str, Any]:
    """동결 JSON 을 읽어 `{key: value}` 로 돌려준다.

    산출물이 손에 있으면(개발 환경) **다시 뽑아 대조**한다. 표류하면 그림을 그리지 않고
    멈춘다 — 낡은 수치를 그린 그림은 없는 그림보다 나쁘다.
    """
    if not FROZEN.exists():
        raise FileNotFoundError(f"{FROZEN} 없음 — `make figure-data` 를 먼저 실행한다")
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))["values"]
    if verify:
        try:
            fresh = extract()
        except FileNotFoundError:
            fresh = {}          # 산출물이 없는 환경(CI 체크아웃)에서는 동결본을 신뢰한다
        drift = [k for k, v in fresh.items() if frozen.get(k, {}).get("value") != v["value"]]
        if drift:
            raise ValueError(
                "동결 수치가 산출물과 어긋난다 — `make figure-data` 로 재동결하고 "
                f"본문 수치도 함께 확인한다: {', '.join(sorted(drift))}"
            )
    return {k: v["value"] for k, v in frozen.items()}


def main() -> None:
    out = freeze()
    values = json.loads(out.read_text(encoding="utf-8"))["values"]
    print(f"✓ {out.relative_to(ROOT)} — 값 {len(values)}개")
    for key, meta in values.items():
        print(f"  {key:38s} = {meta['value']!r:>24}  ← {meta['source']}")


if __name__ == "__main__":
    main()
