"""개념 도식 — 산출물 구조와 층간 지표 불일치 (그림 규격 [F-v1](../../../paper/FIGURE-SPEC.md)).

**왜 별도 모듈인가.** `figures.py` 는 v0.5 패러다임의 서사 도식과 v0.9 데이터 플롯을 함께
갖고 있고, 그 서사 도식은 **구 패러다임 산출물이라 인용이 금지**돼 있다(CLAUDE.md 정본 회귀).
그 파일에 새 개념 그림을 섞으면 살아 있는 그림과 죽은 그림이 한 파일에서 구분되지 않는다.
**스타일 헬퍼는 재사용하고 내용만 새로 세운다** — 두 갈래가 한 벌로 읽혀야 하기 때문이다.

여기의 네 장은 논문 앞부분(서론·이론적 배경·산출물)이 지고 있던 시각 자료 공백을 메운다.

- `fig_overview` — 산출물 셋과 승인 절차, 그리고 네 평가 에피소드가 측정하는 지점.
- `fig_layer_mismatch` — 세 층의 지표와 층 사이에서 실제로 관측된 어긋남 셋.
- `fig_tbox_views` — 공유 T-Box 위의 세 태스크 뷰와 교차 태스크 결합 통로 (표 하나를 대체).
- `fig_gate_flow` — 승인 절차와 각 항의 미충족 시 처리, 그리고 실제 판정 (표 하나를 대체).

**수치는 한 개도 이 파일에 적혀 있지 않다**(규격 F6) — 전부 `figdata.load()` 가 동결
JSON 에서 읽어 오며, 그 JSON 은 산출물에서 기계로 추출된다.
"""
from __future__ import annotations

import re
from pathlib import Path

from sdkb_paper.config import FIGURES
from sdkb_paper.viz import figdata
from sdkb_paper.viz.figures import (
    ASIS,
    ASIS_EDGE,
    ASIS_FILL,
    BORDER,
    GOLD,
    GREEN,
    GREEN_FILL,
    INK,
    MUTE,
    TOBE,
    TOBE_EDGE,
    TOBE_FILL,
    _arrow,
    _canvas,
    _chip,
    _rbox,
    _save,
)

# 단색 인쇄 안전 (규격 F1) — 색은 보조 부호이고 판정은 기호가 진다.
PASS_MARK = "통과"
FAIL_MARK = "거부"


def _sig(v: float, nd: int = 4) -> str:
    """부호를 명시한 소수 표기. 음수는 유니코드 마이너스로 — 본문 표기와 같게 맞춘다."""
    s = f"{abs(v):.{nd}f}"
    return f"+{s}" if v >= 0 else f"−{s}"


# ═══════════════════════════════════════════════════════════════════════════
# 그림 1 — 연구 개요도
# ═══════════════════════════════════════════════════════════════════════════
def fig_overview(out: Path | None = None) -> Path:
    """산출물 셋 · 승인 절차 · 평가 에피소드의 측정 지점을 한 장에 담는다.

    읽는 순서는 위에서 아래다. 위 띠가 **무엇을 만들었는가**(A1), 가운데 띠가 **변경을
    어떻게 승인하는가**(A2), 아래 띠가 **그 둘을 무엇으로 평가하였는가**(A3)이다.
    """
    out = out or FIGURES / "concept_overview.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 6.6)

    # ── A1 · 산출물 자원 (위 띠) ──────────────────────────────────────────────
    _rbox(ax, 0.035, 0.715, 0.60, 0.245,
          title="A1 · SDKB 데이터셋 — 공유 T-Box 하나 위의 세 태스크 뷰",
          body="", fill="#FFFFFF", edge=BORDER, ts=11)
    ax.text(0.058, 0.855, "공유 코어 어휘", ha="left", va="center", fontsize=9,
            fontweight="bold", color=MUTE)
    ax.text(0.058, 0.826, "Process · Material · Equipment · Organization · 분류기호",
            ha="left", va="center", fontsize=8.2, color=MUTE)
    for x, label, color, fill in (
        (0.170, "전문가 매칭", MUTE, "#F1F3F6"),
        (0.350, "선행기술조사", TOBE, TOBE_FILL),
        (0.530, "기술예측", MUTE, "#F1F3F6"),
    ):
        _chip(ax, x, 0.772, label, color=color, fill=fill)
    ax.text(0.350, 0.737, "정량 검증 대상", ha="center", va="center",
            fontsize=7.6, color=TOBE)

    # 변경 유입 — 자원은 고정된 것이 아니라 갱신된다.
    _rbox(ax, 0.680, 0.740, 0.285, 0.190,
          title="자원 변경 ΔG", body="상류 교정 · 어휘 확장\n새 A-Box 유입",
          fill="#FFFFFF", edge=BORDER, ts=10.5, bs=8.4)
    _arrow(ax, 0.822, 0.735, 0.822, 0.625, color=INK, lw=1.8)

    # ── A2 · 승인 게이트 (가운데 띠) ─────────────────────────────────────────
    _rbox(ax, 0.035, 0.330, 0.930, 0.290, title="", body="",
          fill="#FBFCFD", edge=BORDER)
    ax.text(0.055, 0.585, "A2 · 릴리스 승인 게이트 — 앞 단계가 실패하면 뒤를 실행하지 않는다",
            ha="left", va="center", fontsize=11, fontweight="bold", color=INK)

    stages = [
        (0.055, 0.200, "L0–L3", "신선도 · 구조 · 논리\n주 태스크 CQ", "#FFFFFF", BORDER, INK),
        (0.288, 0.170, "누출 차단 색인", "금지 간선 마스킹\n시점 · 패밀리 분리", "#FFFFFF", BORDER, INK),
        (0.491, 0.195, "T1 · T2", "검색 비열등성\n하위집단 안전성", TOBE_FILL, TOBE_EDGE, TOBE),
        (0.719, 0.140, "T3", "다른 태스크 CQ\n비회귀", TOBE_FILL, TOBE_EDGE, TOBE),
        (0.892, 0.073, "판정", "승인\n또는 거부", GREEN_FILL, GREEN, GREEN),
    ]
    for x, w, title, body, fill, edge, tcolor in stages:
        _rbox(ax, x, 0.395, w, 0.150, title=title, body=body,
              fill=fill, edge=edge, tcolor=tcolor, ts=10, bs=8.2)
    for x1, x2 in ((0.259, 0.285), (0.461, 0.488), (0.689, 0.716),
                   (0.862, 0.889)):
        _arrow(ax, x1, 0.470, x2, 0.470, color=INK, lw=1.6, ms=12)

    # T4 는 승인식 밖이다 — 점선과 별도 자리가 그 지위를 진다(§4.5.1).
    ax.annotate("", xy=(0.928, 0.372), xytext=(0.928, 0.393),
                arrowprops=dict(arrowstyle="-|>", linestyle=(0, (3, 2)),
                                color=GOLD, lw=1.4))
    ax.text(0.916, 0.352, "T4 · 하류 생성 층 비회귀 — 설계와 판정 1회 · 승인식 미편입",
            ha="right", va="center", fontsize=8, color=GOLD)

    # ── A3 · 평가 벤치마크 (아래 띠) ─────────────────────────────────────────
    # **화살표를 쓰지 않는다.** 네 에피소드의 측정 대상이 위 두 띠에 흩어져 있어 선으로
    # 이으면 교차가 생기고, 교차한 선은 단색 인쇄에서 읽히지 않는다(규격 F1). 대상은
    # 상자 안의 한 줄이 지시한다.
    ax.text(0.055, 0.262, "A3 · 다층 평가 벤치마크 — 네 평가 에피소드와 각각의 측정 대상",
            ha="left", va="center", fontsize=11, fontweight="bold", color=INK)
    episodes = [
        (0.153, "EP1 · 표현 감사", "A1 자원",
         "세 태스크 어휘와 CQ 가\n자원에 실재하는가"),
        (0.385, "EP2 · 게이트 판별력", "A2 게이트",
         f"홀드아웃 결함 {v['ep2.t3_only']} 를 T3 가 단독 검출\n"
         f"정상 델타 오거부 {v['ep2.false_positive']}"),
        (0.617, "EP3 · 통제된 자원 교체", "ΔG → A2 판정",
         f"자원만 교체 → T1 {FAIL_MARK}\n승인 = 0"),
        (0.849, "EP4 · 검색 효용과 경계", "T1 의 주 지표",
         f"질의 {v['ep4.n_queries']} · 확증 분할 둘\nfamily Recall@100"),
    ]
    for x, title, target, body in episodes:
        _rbox(ax, x - 0.108, 0.045, 0.216, 0.170, title=title, body="",
              fill="#FFFFFF", edge=BORDER, ts=9.2)
        ax.text(x, 0.148, f"측정 대상 · {target}", ha="center", va="center",
                fontsize=8, fontweight="bold", color=TOBE)
        ax.text(x, 0.092, body, ha="center", va="center", fontsize=7.8,
                color=MUTE, linespacing=1.45)
    return _save(fig, out)


# ═══════════════════════════════════════════════════════════════════════════
# 그림 2 — 3층 지표 구조와 층간 불일치
# ═══════════════════════════════════════════════════════════════════════════
LAYER_H = 0.185
OBS_H = 0.215


def _layer(ax, y: float, tag: str, title: str, body: str, fill: str, edge: str) -> None:
    _rbox(ax, 0.045, y, 0.40, LAYER_H, title=title, body=body,
          fill=fill, edge=edge, ts=10.5, bs=8.4, align="left")
    ax.text(0.033, y + LAYER_H / 2, tag, ha="right", va="center", fontsize=9,
            fontweight="bold", color=MUTE, rotation=90)


def _observation(ax, y: float, num: str, head: str, body: str,
                 status: str, color: str, fill: str, edge: str) -> None:
    """오른쪽 관측 칸 — 어긋남 하나. `status` 는 확증 지위를 그림 안에서 명시한다."""
    _rbox(ax, 0.520, y, 0.455, OBS_H, title=f"{num} {head}", body=body,
          fill=fill, edge=edge, tcolor=color, ts=9.6, bs=8.2, align="left")
    ax.text(0.966, y + 0.014, f"지위 · {status}", ha="right", va="bottom",
            fontsize=7.6, style="italic", color=MUTE)


def fig_layer_mismatch(out: Path | None = None) -> Path:
    """세 층의 지표와 그 사이에서 관측된 어긋남 셋 — 본 연구의 중심 관측(§7.5).

    왼쪽이 층의 구조이고 오른쪽이 각 층 사이에서 실제로 관측된 결과다. 층 사이의 화살표에
    붙은 번호가 오른쪽 관측 번호와 대응한다.
    """
    out = out or FIGURES / "concept_layer_mismatch.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 7.2)

    ratio = v["ep3.concepts_per_doc.after"] / v["ep3.concepts_per_doc.before"]

    # ── 왼쪽 · 세 층 ─────────────────────────────────────────────────────────
    _layer(ax, 0.770, "자원 층", "자원 지표",
           f"문서당 개념 {v['ep3.concepts_per_doc.before']} → "
           f"{v['ep3.concepts_per_doc.after']} ({ratio:.1f}배)\n"
           f"개념 어휘 {v['ep3.concept_vocab.before']} → {v['ep3.concept_vocab.after']}\n"
           f"형식 검증 L0–L3 전부 {PASS_MARK}",
           fill="#FFFFFF", edge=BORDER)
    _layer(ax, 0.430, "검색 층", "검색 지표",
           f"family Recall@100 (부차 구성)\n"
           f"{_sig(v['ep4.p1_gain.delta'])} "
           f"[{_sig(v['ep4.p1_gain.lb95'])}, {_sig(v['ep4.p1_gain.ub95'])}]\n"
           f"질의 {v['ep4.n_queries']} · 확증 분할",
           fill=TOBE_FILL, edge=TOBE_EDGE)
    _layer(ax, 0.090, "생성 층", "생성 지표",
           f"인용 정확도 · 환각률\n"
           f"검색팔만 교체 · 생성기 고정\n"
           f"마진 ε = {v['t4.eps']} 사전 동결",
           fill="#FFFFFF", edge=BORDER)

    # ── 층 사이 화살표 ───────────────────────────────────────────────────────
    for y1, y2, num, note in (
        (0.765, 0.622, "①", "다음 층에서 승인 여부를 확인한다"),
        (0.425, 0.282, "③", "다음 층으로 전달되는지 확인한다"),
    ):
        _arrow(ax, 0.135, y1, 0.135, y2, color=INK, lw=1.8)
        ax.text(0.120, (y1 + y2) / 2, num, ha="right", va="center",
                fontsize=11, fontweight="bold", color=INK)
        ax.text(0.160, (y1 + y2) / 2, note, ha="left", va="center",
                fontsize=8, color=MUTE)

    # ② 는 층이 아니라 같은 층의 다른 단위다 — 옆으로 뻗는다.
    _arrow(ax, 0.450, 0.523, 0.512, 0.523, color=INK, lw=1.6, ms=12)
    ax.text(0.481, 0.548, "②", ha="center", va="bottom", fontsize=10,
            fontweight="bold", color=INK)

    # ── 오른쪽 · 관측된 어긋남 셋 ────────────────────────────────────────────
    _observation(
        ax, 0.765, "①", "자원 지표 개선 · 검색 지표 저하",
        f"자원만 교체한 두 팔에서 교체 대상 구성의 회수가 저하되었다.\n"
        f"ΔRecall@100 = {_sig(v['ep3.p1.delta'])} · 95% CI "
        f"[{_sig(v['ep3.p1.ci_lo'])}, {_sig(v['ep3.p1.ci_hi'])}] → T1 {FAIL_MARK} · 승인 = 0\n"
        f"온톨로지 단독 팔은 오히려 향상되었다 "
        f"({v['ep3.b5.before']:.4f} → {v['ep3.b5.after']:.4f}) — 원인은 미구분",
        "개봉 분할 · 승인 규칙의 적용", ASIS, ASIS_FILL, ASIS_EDGE)
    _observation(
        ax, 0.425, "②", "주 지표 개선 · 검토 건수 불변",
        f"같은 이득을 검토 건수 단위로 환산하면 중앙 감소율이 "
        f"{v['effort.median_reduction_pct']:.1f}%이다.\n"
        f"질의별 승·무·패는 {v['effort.win_tie_loss']}로 균형에 가깝다.\n"
        f"재순위화는 후보 풀 밖의 문헌을 회수하지 못한다.",
        "탐색적 기술통계", GOLD, "#FBF3E4", "#DCC08A")
    _observation(
        ax, 0.085, "③", "점추정의 우위 · 비열등 판정의 실패",
        f"인용 정확도의 점추정은 온톨로지를 포함한 팔이 앞섰다"
        f"({_sig(v['t4.citation_precision.delta'])}).\n"
        f"그러나 95% CI 하한이 {_sig(v['t4.citation_precision.lb95'])} 로 마진 "
        f"−{v['t4.eps']} 를 초과하여 T4 판정은 실패이다.\n"
        f"전달의 부재인지 검정력의 부족인지는 미구분이다.",
        "확증 · 판정 1회", ASIS, ASIS_FILL, ASIS_EDGE)

    # ── 결론 띠 ──────────────────────────────────────────────────────────────
    ax.text(0.5, 0.022,
            "세 관측을 관통하는 명제 — 자원 지표가 개선되고 형식 검증을 통과한 변경도 "
            "다음 층의 성능을 보장하지 않는다.",
            ha="center", va="center", fontsize=9.4, fontweight="bold", color=INK,
            bbox=dict(boxstyle="round,pad=0.5", fc="#F7F9FB", ec=BORDER, lw=1.0))
    return _save(fig, out)


# ═══════════════════════════════════════════════════════════════════════════
# 그림 3 — 공유 T-Box와 세 태스크 뷰
# ═══════════════════════════════════════════════════════════════════════════
def _terms(cell: str, per_line: int) -> str:
    """표의 어휘 칸(백틱·가운뎃점 구분)을 그림용 여러 줄로 접는다."""
    items = [t.strip().strip("`") for t in cell.split("·") if t.strip()]
    lines = ["·".join(items[i:i + per_line]) for i in range(0, len(items), per_line)]
    return "\n".join(lines)


def _plain(cell: str) -> str:
    """표 칸의 마크다운 강조와 절 참조를 걷어낸다.

    절 번호를 그대로 옮기지 않는 이유는 하나다 — 출처가 축약 전 전문(S5)이라 그 번호는
    파생본의 절 번호와 다르다. 그림이 죽은 참조를 나르면 `submission-check` 가 잡지 못한다.
    """
    return re.sub(r"\s*\(§[^)]*\)", "", cell.replace("**", "")).strip()


def _status(cell: str) -> str:
    """지위 칸에서 괄호 보충을 걷어낸다 — 상자 폭에 들어가지 않으면 다른 칸을 침범한다."""
    return re.sub(r"\s*\([^)]*\)", "", _plain(cell)).strip()


def fig_tbox_views(out: Path | None = None) -> Path:
    """공유 T-Box 하나 위의 세 태스크 뷰와 교차 태스크 결합 통로.

    이 그림은 세 뷰의 지위표를 대체한다. 표가 보여주지 못하던 것을 보여주기 때문이다 —
    세 뷰는 배타적 모듈이 아니라 공유 어휘를 통해 서로 이어져 있으며, 그 이어짐이 교차
    태스크 회귀가 실재하는 이유이다.
    """
    out = out or FIGURES / "concept_tbox_views.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 6.8)

    views = [
        (0.030, v["views.match"], MUTE, "#F1F3F6", "#D7DBE0"),
        (0.352, v["views.priorart"], TOBE, TOBE_FILL, TOBE_EDGE),
        (0.674, v["views.foresight"], MUTE, "#F1F3F6", "#D7DBE0"),
    ]
    for x, cells, color, fill, edge in views:
        name, classes, cqs, abox, status = cells[0], cells[1], cells[2], cells[3], cells[4]
        _rbox(ax, x, 0.560, 0.296, 0.400, title=name, body="",
              fill=fill, edge=edge, tcolor=color, ts=11)
        ax.text(x + 0.016, 0.878, _terms(classes, 2), ha="left", va="top",
                fontsize=7.6, color=INK, linespacing=1.5)
        ax.text(x + 0.016, 0.700, f"대표 역량질문 · {_plain(cqs)}", ha="left", va="top",
                fontsize=7.6, color=MUTE)
        ax.text(x + 0.016, 0.668, f"A-Box · {_terms(_plain(abox), 2)}", ha="left",
                va="top", fontsize=7.2, color=MUTE, linespacing=1.5)
        ax.text(x + 0.016, 0.588, "본 논문의 지위", ha="left", va="center",
                fontsize=7.4, color=MUTE)
        ax.text(x + 0.016, 0.568, _terms(_status(status), 2), ha="left", va="center",
                fontsize=8, fontweight="bold", color=color, linespacing=1.5)

    # ── 결합 통로 ────────────────────────────────────────────────────────────
    # 공유 어휘가 **어느 두 뷰를** 잇는지가 이 그림의 요점이다. 그래서 통로마다 선을 그
    # 두 열의 중심으로만 보낸다 — 세 열 전부에 뻗으면 "공유"와 "결합"이 구분되지 않는다.
    ax.text(0.5, 0.510, "교차 태스크 결합 통로 — 공유 어휘가 두 뷰를 잇는다",
            ha="center", va="center", fontsize=9.5, fontweight="bold", color=INK,
            bbox=dict(boxstyle="square,pad=0.35", fc="#FFFFFF", ec="none"), zorder=5)
    cols = (0.178, 0.500, 0.822)

    def _link(x: float, y: float, label: str, left: float, right: float) -> None:
        _chip(ax, x, y, label, color=GOLD, fill="#FBF3E4")
        for tx in (left, right):
            ax.annotate("", xy=(tx, 0.556), xytext=(x, y + 0.030),
                        arrowprops=dict(arrowstyle="-", linestyle=(0, (2, 2)),
                                        color=GOLD, lw=1.2))

    _link(0.339, 0.445, "Material · Equipment · Organization", cols[0], cols[1])
    _link(0.800, 0.445, "분류 기호", cols[1], cols[2])

    # Process·SubProcess 는 1열과 3열을 잇는다 — 가운데 열을 건너뛰므로 선이 아니라
    # **바깥으로 도는 괄호**로 그린다. 직선으로 이으면 위 두 통로의 선과 엉킨다.
    for tx in (0.090, 0.910):
        ax.annotate("", xy=(tx, 0.556), xytext=(tx, 0.322),
                    arrowprops=dict(arrowstyle="-", linestyle=(0, (2, 2)),
                                    color=GOLD, lw=1.2))
        ax.annotate("", xy=(tx, 0.322), xytext=(0.5, 0.322),
                    arrowprops=dict(arrowstyle="-", linestyle=(0, (2, 2)),
                                    color=GOLD, lw=1.2))
    _chip(ax, 0.500, 0.322, "Process · SubProcess", color=GOLD, fill="#FBF3E4")

    # ── 공유 코어 ────────────────────────────────────────────────────────────
    _rbox(ax, 0.030, 0.055, 0.940, 0.190,
          title="공유 코어 T_core — 세 뷰가 함께 서는 자리",
          body="", fill="#FFFFFF", edge=BORDER, ts=10.5)
    ax.text(0.5, 0.170,
            "T_SDKB = T_core ∪ V_match ∪ V_priorart ∪ V_foresight",
            ha="center", va="center", fontsize=10, color=INK)
    ax.text(0.5, 0.120,
            f"게이트가 관찰하는 역량질문 {v['cq.total']}개 — 주 태스크 {v['cq.pa']} · "
            f"전문가 매칭 {v['cq.em']} · 기술예측 {v['cq.tf']} · 공유 코어 {v['cq.core']}",
            ha="center", va="center", fontsize=8.6, color=MUTE)
    ax.text(0.5, 0.085,
            "둘 이상의 뷰를 잇는 역량질문은 공유 코어에 귀속한다",
            ha="center", va="center", fontsize=8, color=MUTE)
    return _save(fig, out)


# ═══════════════════════════════════════════════════════════════════════════
# 그림 4 — T-gate 절차와 실제 판정
# ═══════════════════════════════════════════════════════════════════════════
def fig_gate_flow(out: Path | None = None) -> Path:
    """승인 절차의 순서와 각 항의 미충족 시 처리, 그리고 실제 거부 사례의 판정.

    오른쪽 열은 통제된 자원 교체(EP3)에서 각 항이 실제로 낸 판정이다. 형식 검증을 전부
    통과한 변경이 성능 조건 하나에서 거부되었다는 사실이 이 열에서 읽힌다.
    """
    out = out or FIGURES / "concept_gate_flow.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 7.4)

    ax.text(0.175, 0.960, "승인 절차", ha="center", va="center",
            fontsize=10, fontweight="bold", color=INK)
    ax.text(0.560, 0.960, "미충족 시의 처리", ha="center", va="center",
            fontsize=10, fontweight="bold", color=INK)
    ax.text(0.860, 0.960, "통제된 자원 교체에서의 판정", ha="center", va="center",
            fontsize=10, fontweight="bold", color=INK)

    ci = f"[{_sig(v['ep3.p1.ci_lo'])}, {_sig(v['ep3.p1.ci_hi'])}]"
    rows = [
        ("자원 변경 ΔG", "", "", "", "#FFFFFF", BORDER, INK),
        (f"L0–L3 · 형식·기능 검증\n주 태스크 역량질문 {v['cq.pa']}개",
         "최신 상태·구조 제약·논리 일관·필수 응답 가운데\n하나라도 어긋나면 즉시 거부",
         PASS_MARK, "전부 통과", "#FFFFFF", BORDER, INK),
        ("누출 차단 검색 색인",
         "금지 간선 마스킹·시점 유효·패밀리 분리.\n누출 감사가 0이 아니면 T1 판정은 무효이다",
         PASS_MARK, "위반 0", "#FFFFFF", BORDER, INK),
        ("T1 · 검색 비열등성",
         f"회수의 95% 신뢰구간 하한이 허용 폭 ε = {v['gate.epsilon']} 를\n초과하여 저하되면 거부",
         FAIL_MARK, f"ΔRecall@100 {_sig(v['ep3.p1.delta'])} · 95% CI {ci}",
         ASIS_FILL, ASIS_EDGE, ASIS),
        ("T2 · 하위집단 안전성",
         f"한 집단이라도 δ = {v['gate.delta']} 이상 저하되면 거부.\n"
         "질의 수가 과소한 집단은 차단에 쓰지 않는다",
         PASS_MARK, f"최대 하락 +{v['ep3.t2_max_drop']:.4f}", TOBE_FILL, TOBE_EDGE, TOBE),
        (f"T3 · 교차 태스크 역량질문 비회귀\n다른 태스크와 공유 코어 "
         f"{v['cq.em'] + v['cq.tf'] + v['cq.core']}개",
         "다른 태스크의 통과율이 하나라도 저하되면 거부.\n예외는 명시적 waiver 로만 허용한다",
         PASS_MARK, str(v["ep3.t3_suites"]).split("—")[0].strip(),
         TOBE_FILL, TOBE_EDGE, TOBE),
        ("병합·릴리스", "", "", "", GREEN_FILL, GREEN, GREEN),
    ]

    top, h, gap = 0.905, 0.093, 0.032
    for i, (title, rule, mark, detail, fill, edge, tcolor) in enumerate(rows):
        y = top - i * (h + gap) - h
        _rbox(ax, 0.030, y, 0.290, h, title=title, body="",
              fill=fill, edge=edge, tcolor=tcolor, ts=9.6)
        if rule:
            ax.text(0.348, y + h / 2, rule, ha="left", va="center",
                    fontsize=8, color=MUTE, linespacing=1.5)
        if mark:
            color = ASIS if mark == FAIL_MARK else GREEN
            _chip(ax, 0.760, y + h / 2, mark, color=color,
                  fill=ASIS_FILL if mark == FAIL_MARK else GREEN_FILL)
            ax.text(0.800, y + h / 2, detail, ha="left", va="center",
                    fontsize=8, color=color if mark == FAIL_MARK else MUTE)
        if i < len(rows) - 1:
            _arrow(ax, 0.175, y - 0.004, 0.175, y - gap + 0.004, color=INK, lw=1.6, ms=12)

    ax.text(0.030, 0.030,
            "승인식은 곱이므로 한 항이라도 미충족이면 승인은 0이다. "
            "이 사례의 승인 결과는 거부이며 미충족 조건은 T1 하나이다. "
            "T4 는 이 식에 포함되지 않는다.",
            ha="left", va="center", fontsize=8.6, color=INK)
    return _save(fig, out)


# ═══════════════════════════════════════════════════════════════════════════
# 그림 5 — 실무 흐름과 실험 구성의 대응 (PLAN-056)
# ═══════════════════════════════════════════════════════════════════════════
def fig_experiment_flow(out: Path | None = None) -> Path:
    """선행기술조사 실무의 단계와 본 실험의 구성을 나란히 놓고 대응을 표시한다.

    **대응이 없는 자리를 함께 표시하는 것이 이 그림의 요점이다.** 실무의 서지 조건에
    대응하는 구성은 주 기준선에 융합되어 있지 않고, 실무의 순차 검토와 달리 본 실험의
    재순위화는 후보 풀을 넘지 못한다. 결손을 가리는 그림이 아니라 드러내는 그림이다.
    """
    out = out or FIGURES / "concept_experiment_flow.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 7.4)

    ax.text(0.215, 0.945, "선행기술조사 실무의 절차", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=MUTE)
    ax.text(0.700, 0.945, "본 실험의 구성", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=INK)

    rows = [
        ("대상 출원의 청구항을 읽는다",
         "독립항 전문 추출", "질의 본문 · claims_independent", TOBE_FILL, TOBE_EDGE, TOBE),
        ("검색식을 세운다 — 키워드와 서지 조건",
         "질의 표현 1종 고정", "4종을 준비하였으나 비교는 실행하지 않았다",
         "#FFFFFF", BORDER, INK),
        ("특허 데이터베이스를 검색한다",
         "어휘 · 의미 · 개념의 세 경로",
         "BM25(nori) · Dense(Titan v2) · 개념 단독", "#FFFFFF", BORDER, INK),
        ("결과를 합쳐 후보 목록을 만든다",
         "순위 융합과 후보 풀",
         f"reciprocal rank fusion 상수 {v['flow.rrf_c']} → 상위 "
         f"{v['flow.pool_depth']:,}건", "#FFFFFF", BORDER, INK),
        ("후보를 순차로 검토한다",
         "온톨로지 재순위화", "풀 안에서만 재정렬 — 후보를 확대하지 않는다",
         TOBE_FILL, TOBE_EDGE, TOBE),
        ("심사관이 인용할 문헌에 도달한다",
         "family Recall@100 으로 채점", "정답은 심사관 인용", GREEN_FILL, GREEN, GREEN),
    ]

    top, h, gap = 0.900, 0.108, 0.026
    ys = []
    for i, (task, title, body, fill, edge, tcolor) in enumerate(rows):
        y = top - i * (h + gap) - h
        ys.append(y)
        _rbox(ax, 0.030, y, 0.370, h, title=task, body="",
              fill="#F1F3F6", edge="#D7DBE0", tcolor=MUTE, ts=9.4)
        _rbox(ax, 0.470, y, 0.460, h, title=title, body=body,
              fill=fill, edge=edge, tcolor=tcolor, ts=9.6, bs=8.0)
        _arrow(ax, 0.404, y + h / 2, 0.466, y + h / 2, color=MUTE,
               lw=1.2, style="-", ms=10)
        if i < len(rows) - 1:
            _arrow(ax, 0.700, y - 0.002, 0.700, y - gap + 0.002, color=INK,
                   lw=1.5, ms=11)

    # 대응이 없는 자리 둘 — 오른쪽 여백에 표시한다.
    ax.text(0.945, ys[1] + h / 2,
            f"주 기준선에 융합되지 않음\n분류 신호 단독의 회수는 {v['flow.b4_r100']:.3f}",
            ha="left", va="center", fontsize=7.6, color=ASIS, linespacing=1.5)
    ax.text(0.945, ys[4] + h / 2,
            f"풀 밖은 회수되지 않음\n정답의 {v['ceiling.pool_ratio'] * 100:.1f}%만 풀 안에 있다\n"
            f"({v['ceiling.pool_hits']}/{v['ceiling.edges']} · 문서 단위 · 탐색적)",
            ha="left", va="center", fontsize=7.6, color=ASIS, linespacing=1.5)

    # 전제 상자 — 본 장의 수치가 성립하는 조건이다.
    ax.text(0.5, 0.028,
            "전제 · 질의 특허는 이미 온톨로지에 등재되어 있다. 자유 텍스트 질의를 개념에 "
            "연결하는 적용기는 이후 세대에서 구현되었으며 본 장의 수치에 포함되지 않는다.",
            ha="center", va="center", fontsize=8.6, color=INK,
            bbox=dict(boxstyle="round,pad=0.5", fc="#F7F9FB", ec=BORDER, lw=1.0))
    return _save(fig, out)


# ═══════════════════════════════════════════════════════════════════════════
# 그림 6 — 평가 에피소드와 승인식 구성요소의 대응 (결과 장의 요약 맵)
# ═══════════════════════════════════════════════════════════════════════════
NONE_MARK = "·"
OBS_MARK = "감사"
UNCONF_MARK = "미확증"

# 열 = 승인식의 구성요소. 맨 왼쪽만 게이트가 아니라 자원이다 — EP1 이 재는 대상이
# 게이트가 아니기 때문이며, 이 열이 없으면 EP1 행이 전부 빈칸이 되어 에피소드 넷이
# 한 축 위에 놓이지 않는다.
MATRIX_COLS = [
    ("자원 A1", "표현 감사"),
    ("L0–L3", "형식 · 기능"),
    ("T1", "검색 비열등성"),
    ("T2", "하위집단"),
    ("T3", "교차 태스크"),
    ("T4*", "생성 층"),
]


def _cell(ax, cx: float, cy: float, mark: str, note: str = "") -> None:
    """칸 하나 — 판정 부호와 그 근거 한 줄. 부호가 색보다 앞선다(규격 F1)."""
    if mark == NONE_MARK:
        ax.text(cx, cy, NONE_MARK, ha="center", va="center", fontsize=13,
                color=BORDER)
        return
    color, fill = GREEN, GREEN_FILL
    if mark in (FAIL_MARK, UNCONF_MARK):
        color, fill = ASIS, ASIS_FILL
    elif mark == OBS_MARK:
        color, fill = MUTE, "#F1F3F6"
    elif "/" in mark:
        color, fill = TOBE, TOBE_FILL
    _chip(ax, cx, cy + 0.026, mark, color=color, fill=fill)
    if note:
        ax.text(cx, cy - 0.036, note, ha="center", va="center", fontsize=6.6,
                color=MUTE, linespacing=1.45)


def fig_ep_gate_matrix(out: Path | None = None) -> Path:
    """네 평가 에피소드가 승인식의 어느 항을 검증하였고 그 판정이 무엇인가.

    가로로 읽으면 한 에피소드의 검증 범위가 보이고, 세로로 읽으면 같은 항이 서로 다른
    실험에서 낸 판정이 보인다. **이 그림의 요점은 두 행에 있다** — EP3 행에서 형식 검증을
    전부 통과한 변경이 T1 에서 거부되었고, EP4 행에서 T1 을 통과한 구성이 T4 에서 비열등을
    보이지 못하였다. 층간 지표 불일치가 산문의 도움 없이 표면에 드러난다.
    """
    out = out or FIGURES / "concept_ep_gate_matrix.svg"
    v = figdata.load()
    fig, ax = _canvas(11.0, 6.6)

    ratio = v["ep3.concepts_per_doc.after"] / v["ep3.concepts_per_doc.before"]
    t3_cq = v["cq.em"] + v["cq.tf"] + v["cq.core"]   # T3 가 관찰하는 스위트의 합

    rows = [
        ("EP1", "표현 감사", "관측 사실",
         [(OBS_MARK, f"역량질문 {v['cq.total']}개\n세 태스크 어휘"),
          (NONE_MARK, ""), (NONE_MARK, ""), (NONE_MARK, ""),
          (NONE_MARK, ""), (NONE_MARK, "")],
         "세 태스크의 어휘·관계·역량질문이 자원에 실재한다.\n"
         "다만 표현 범위는 검색 준비도와 동일하지 않다."),
        ("EP2", "게이트 판별력", "홀드아웃 확증",
         [(NONE_MARK, ""),
          (str(v["ep2.l3_detected"]), "주 태스크 CQ\n검출"),
          (NONE_MARK, ""), (NONE_MARK, ""),
          (str(v["ep2.t3_only"]), "교차 결함\n단독 검출"),
          (NONE_MARK, "")],
         f"교차 태스크 결함은 T3 가 단독으로 검출하였고 정상 델타의\n"
         f"오거부는 {v['ep2.false_positive']} 이다 (단측 McNemar p = {v['ep2.mcnemar_p']:.4f})."),
        ("EP3", "통제된 자원 교체", "별도 사전등록",
         [(f"{ratio:.1f}배", f"문서당 개념\n{v['ep3.concepts_per_doc.before']} → "
                             f"{v['ep3.concepts_per_doc.after']}"),
          (PASS_MARK, "전부 통과"),
          (FAIL_MARK, f"ΔR@100\n{_sig(v['ep3.p1.delta'])}"),
          (PASS_MARK, f"최대 하락\n+{v['ep3.t2_max_drop']:.4f}"),
          (PASS_MARK, f"CQ {t3_cq}개\n통과율 유지"),
          (NONE_MARK, "")],
         "자원 지표가 개선되고 형식 검증을 통과한 변경을 성능 조건\n"
         "하나가 차단하였다. 승인식은 곱이므로 승인 결과는 거부이다."),
        ("EP4", "검색 효용과 경계", "확증 · 분할 둘",
         [(NONE_MARK, ""), (NONE_MARK, ""),
          (PASS_MARK, f"A {_sig(v['ep4.p1_gain.delta'])}\n"
                      f"B {_sig(v['ep4b.p1_gain.delta'])}"),
          (PASS_MARK, "국소 회귀\n없음"),
          (NONE_MARK, ""),
          (UNCONF_MARK, f"하한 {_sig(v['t4.citation_precision.lb95'])}\n"
                        f"마진 −{v['t4.eps']} 초과")],
         "깊은 회수의 개선은 두 확증 분할에서 반복 관측되었다.\n"
         "사전등록된 복합 기준의 동시 충족은 두 분할에서 확인되지 않았다."),
    ]

    # ── 열 머리글 ────────────────────────────────────────────────────────────
    x0, cw, cgap = 0.175, 0.072, 0.004
    centers = [x0 + cw / 2 + i * (cw + cgap) for i in range(len(MATRIX_COLS))]
    for cx, (head, sub) in zip(centers, MATRIX_COLS):
        ax.text(cx, 0.930, head, ha="center", va="center", fontsize=9.6,
                fontweight="bold", color=INK)
        ax.text(cx, 0.900, sub, ha="center", va="center", fontsize=6.8, color=MUTE)
    ax.text(0.020, 0.930, "평가 에피소드", ha="left", va="center", fontsize=9.6,
            fontweight="bold", color=INK)
    ax.text(0.645, 0.930, "판정 요약", ha="left", va="center", fontsize=9.6,
            fontweight="bold", color=INK)
    ax.plot([0.020, 0.985], [0.876, 0.876], color=BORDER, lw=1.0)

    # ── 행 ───────────────────────────────────────────────────────────────────
    top, h, gap = 0.865, 0.145, 0.025
    for i, (tag, name, status, cells, verdict) in enumerate(rows):
        y = top - i * (h + gap) - h
        _rbox(ax, 0.020, y, 0.145, h, title=tag, body=name,
              fill="#FFFFFF", edge=BORDER, ts=10, bs=7.8)
        _rbox(ax, x0 - 0.004, y, len(cells) * (cw + cgap), h, title="", body="",
              fill="#FBFCFD", edge=BORDER)
        for cx, (mark, note) in zip(centers, cells):
            _cell(ax, cx, y + h / 2, mark, note)
        ax.text(0.985, y + h - 0.014, f"지위 · {status}", ha="right", va="top",
                fontsize=6.8, style="italic", color=MUTE)
        ax.text(0.645, y + h / 2 - 0.012, verdict, ha="left", va="center",
                fontsize=7.8, color=INK, linespacing=1.6)

    # ── 읽는 법 띠 ───────────────────────────────────────────────────────────
    ax.text(0.5, 0.055,
            "가로로 읽으면 한 에피소드가 승인식의 어느 항을 검증하였는지 보이고, 세로로 "
            "읽으면 같은 항이 다른 실험에서 낸 판정이 보인다.\n"
            "EP3 행에서는 형식 검증을 전부 통과한 변경이 T1 에서 거부되었고, EP4 행에서는 "
            "T1 을 통과한 구성이 T4 에서 비열등을 보이지 못하였다.\n"
            "* T4 는 승인식에 포함되지 않는다 — 설계와 판정 1회의 기록이다.",
            ha="center", va="center", fontsize=8.2, color=INK, linespacing=1.7,
            bbox=dict(boxstyle="round,pad=0.55", fc="#F7F9FB", ec=BORDER, lw=1.0))
    return _save(fig, out)


def main() -> None:
    """개념 도식 전량을 동결 수치에서 결정적으로 재생성한다."""
    for fn in (fig_overview, fig_layer_mismatch, fig_tbox_views, fig_gate_flow,
               fig_experiment_flow, fig_ep_gate_matrix):
        print(f"  ✓ {fn().relative_to(FIGURES.parent.parent)}")


if __name__ == "__main__":
    main()
