"""논증층 판단의 일관성 검사 — 추출 결과를 본문의 **다른 읽기**와 대조해, 어긋나면 그 부분을 보류한다(PLAN-005 §20.23 c).

추출기(`build_abox_argument.py`)의 정규식을 import 하지 않는다. 같은 정규식을 쓰면 같은 곳에서 같이 틀린다.
공유하는 것은 정본 파서(`build_notice_evidence`)의 청구항 번호 해석·문헌 번호 정규화뿐이며, 이 둘은 **공통 맹점**이다.

검사가 잡는다는 증거는 결함 주입 시험까지다(tests/test_argument_consistency.py). 공통 맹점이 없다는 증명은 아니다 —
남는 한계는 BLIND_SPOTS 에 적고 리포트에 싣는다.
"""
from __future__ import annotations

import re
from collections import Counter

import build_notice_evidence as N

BLIND_SPOTS = [
    "청구항 번호 해석(N.parse_claim_refs)·문헌 번호 정규화(N.normalize_cited)는 추출기와 공유한다 — 거기서 틀리면 함께 틀린다.",
    "좌표 귀속은 추출기가 해소한 (라벨, 번호) → 문헌 대응을 쓴다 — 그 대응이 틀리면 C6 도 따라 틀린다(C3·C4 가 일부를 막는다).",
    "같은 국가의 다른 문헌으로 라벨을 잇고 그 문헌의 명시적 정의가 통지서에 없으면 C3·C4 모두 통과한다.",
    "논거 종류의 표현(설계 변경 · 효과 예측)은 추출기와 같은 낱말로 찾는다 — 표현 자체를 놓치면(누락) 검사도 모른다.",
]

# ── 공통 읽기 ────────────────────────────────────────────────────────
_NUM = r"(?:제\s*)?\d{1,3}(?:\s*항)?"
CLREF = (r"(?:청구항|제)\s*" + _NUM + r"(?:\s*(?:,|및|내지|~|∼|-|–|ㆍ|·|와|과|또는)\s*(?:청구항\s*)?" + _NUM + r")*")
CLREF_RX = re.compile(CLREF)
_CITED_BEFORE = re.compile(r"(?:인\s*용|비\s*교\s*대\s*상|선\s*행)\s*(?:발\s*명|문\s*헌)\s*\d{0,2}\s*(?:의|에서|에|\()?\s*$")
_LOC_PAREN = re.compile(r"\([^()]{0,60}(?:단락|식별번호|문단|도\s*\d|참조|\[\d{3,5})[^()]{0,60}\)")
_PARENT_TAIL = (r"\s*(?:의\s*)?(?:직\s*[·ㆍ]?\s*간접\s*(?:적으로\s*)?)?(?:을|를)?\s*"
                r"(?:인용(?!\s*(?:발명|문헌))|종속|에\s*있어서|을\s*더\s*한정|를\s*더\s*한정)")
_PARENT = re.compile(r"(" + CLREF + r")" + _PARENT_TAIL)
_PARENT_TAIL_RX = re.compile(_PARENT_TAIL)
_PAGE = re.compile(r"-\s*\d{1,3}\s*-\s*10-\d{4}-\d{7}")
_SENT = re.compile(r"(?:다|음|함|임)\s*\.|\n\s*\n")


def _norm(s: str) -> str:
    s = re.sub(r"(?<!조)(?<!조\s)제\s*(\d{1,3})\s*[-–]\s*(\d{1,3})\s*항", r"청구항 \1 내지 \2", s)
    s = re.sub(r"(?<!조)(?<!조\s)제\s*(\d{1,3})((?:\s*(?:,|및|ㆍ|·)\s*\d{1,3})+)\s*항", r"청구항 \1\2", s)   # `제3, 5항`
    s = re.sub(r"(?<!조)(?<!조\s)(?<!청구항)(?<!청구항\s)제\s*(\d{1,3})\s*항", r"청구항 \1", s)
    s = re.sub(r"(청구항\s*\d{1,3})\s*[-–]\s*(\d{1,3})(?!\d)", r"\1 내지 \2", s)
    s = re.sub(r"(?<=\d)\s*[·ㆍ+]\s*(?=\d)", ", ", s)
    s = re.sub(r"청\s+구\s*항|청구\s+항", "청구항", s)
    return _PAGE.sub(" ", s)


def claims_of(s: str) -> set[int]:
    return set(N.parse_claim_refs(_norm(s)))


def _blank_loc_parens(s: str) -> str:
    """문헌 위치 괄호(`(청구항 1, 단락 [0013] 참조)`)는 인용문헌의 청구항이다 — 같은 길이의 공백으로 지운다."""
    return _LOC_PAREN.sub(lambda m: " " * len(m.group(0)), s)


def parents(s: str) -> set[int]:
    return {n for m in _PARENT.finditer(_norm(s)) for n in N.parse_claim_refs(m.group(1))}


def _applicant_mentions(s: str, keep_parents: bool = False) -> list[tuple[int, int, set[int]]]:
    """출원 청구항 언급 (시작, 끝, 번호) — 인용문헌의 청구항(`인용발명 1 의 청구항 3`)·위치 괄호는 뺀다.
    부모항은 **언급 단위**로 뺀다: `제4항(제3항의 종속항)` 의 3 은 부모지만, 같은 문장의 `제3, 5항` 의 3 은 주어다."""
    t = _blank_loc_parens(_norm(s))
    out = []
    for m in CLREF_RX.finditer(t):
        if _CITED_BEFORE.search(t[max(0, m.start() - 25):m.start()]):
            continue
        if not keep_parents and _PARENT_TAIL_RX.match(t, m.end()):
            continue
        out.append((m.start(), m.end(), set(N.parse_claim_refs(m.group(0)))))
    return out


_SUBJ_TAIL = re.compile(r"\s*(?:\([^)]{0,30}\))?\s*(?:에\s*기재된\s*)?(?:발명)?\s*"
                        r"(?:의\s*(?:[가-힣]{1,10}\s*){1,3}?(?:들)?\s*)?(?:은|는)\s"
                        # §20.24 C1′ — `제10항 발명에 부가된(한정된) 제 1, 2 소자 분리막의 두께의 구성은`
                        r"|\s*(?:발명)?\s*에\s*(?:부가|한정|추가)(?:된|한|되어\s*있는)\s*[^.。\n]{0,40}?(?:은|는)\s"
                        r"|\s*(?:발명)?\s*(?:을|를)\s*(?:쉽게|용이하게)"
                        r"|\s*(?:발명)?\s*에\s*서\s*한정")


def subjects(s: str) -> set[int]:
    """판단 주어로 나온 출원 청구항 — `청구항 N (발명)(의 X)은/는` · `N 을 쉽게` · `N 발명에서 한정`."""
    t = _blank_loc_parens(_norm(s))
    ms = _applicant_mentions(s)
    out: set[int] = set()
    for i, (a, b, nums) in enumerate(ms):
        if _SUBJ_TAIL.match(t, b):
            out |= nums
            # 병렬 주어 `제2항(…) 및 제3항(…)의 X는` — 앞 언급이 괄호·나열 접속만 두고 이어지면 함께 주어다.
            j = i
            while j > 0 and _CHAIN.fullmatch(t[ms[j - 1][1]:ms[j][0]]):
                j -= 1
                out |= ms[j][2]
    return out


_CHAIN = re.compile(r"\s*(?:\([^()]{0,40}\))?\s*(?:,|및|와|과|또는)\s*")


def _body(r: dict) -> str:
    t = r["text"]
    nl = t.find("\n")
    return t[nl + 1:] if nl != -1 else ""


# ── C1 · C2 · C5 블록 ─────────────────────────────────────────────────
def c1_claims(r: dict) -> list[str]:
    own = set(r["claims"])
    out = []
    # 머리줄까지 읽는다 — 문장 꼴 머리줄(`2. 제2항(…) 및 제3항(…)의 X는`)의 주어가 블록 청구항과 어긋날 수 있다(검토 12행).
    if subjects(r["text"]) - own:
        out.append("C1_foreign_subject")
    mentioned = set().union(*[n for _, _, n in _applicant_mentions(r["text"], keep_parents=True)] or [set()])
    if own - mentioned:
        out.append("C1_excess_claim")
    return out


_MARK = r"(?:\d+\s*[-.]\s*\d+(?:\s*[-.]\s*\d+)?\s*\.?|\d+\s*[.)]|[가-하]\s*[.)]|\(\s*(?:\d+|[가-하])\s*\)|[①-⑳])"
_OPEN_RX = re.compile(r"^[ \t]*" + _MARK + r"[ \t]*[<\[(【]?[ \t]*(?:특허\s*청구\s*범위\s*)?(?:(?:독립|종속)\s*)?"
                      r"(?:청구항\s*(?:제\s*)?\d|청구하\s*(?:제\s*)?\d|제\s*\d{1,3}(?:\s*[-–,]\s*\d{1,3})*\s*항)", re.M)


def c2_new_judgment(r: dict) -> list[str]:
    """본문 안에서 출원 청구항의 새 판단을 여는 표지 줄 — 그 줄의 청구항(부모항 제외)이 블록 밖이면."""
    body = _PAGE.sub(" ", _body(r)).replace("청구하", "청구항")
    own = set(r["claims"])
    for m in _OPEN_RX.finditer(body):
        line = body[m.start(): body.find("\n", m.start()) if "\n" in body[m.start():] else len(body)]
        first = _applicant_mentions(line)
        # 그 줄이 여는 청구항 = 표지 바로 뒤의 첫 나열. 같은 줄의 참조 대상(`제18항(제17항의 제조방법…)` 의 17)은 아니다.
        nums = first[0][2] if first and first[0][0] <= 20 else set()
        if nums and not nums <= own:
            return ["C2_new_judgment"]
    return []


_CONCL_RX = re.compile(r"(?:따라서|그러므로|결국|이상과\s*같이)\s*,?[^.\n]{0,40}?(" + CLREF + r")")


def c5_conclusion(r: dict) -> list[str]:
    """본문(종합 결론 제외)의 결론 문장 첫 청구항 나열이 블록 청구항 밖을 포함하면."""
    body = _norm(r["text"])
    own = set(r["claims"])
    for m in _CONCL_RX.finditer(body):
        if _CITED_BEFORE.search(body[max(0, m.start(1) - 25):m.start(1)]):
            continue
        if _PARENT_TAIL_RX.match(body, m.end(1)):
            continue
        nums = set(N.parse_claim_refs(m.group(1)))
        if nums and not nums <= own:
            return ["C5_conclusion"]
    return []


# ── C3 · C4 문헌 ─────────────────────────────────────────────────────
_TERM = r"(?:인\s*용\s*발\s*명|비\s*교\s*대\s*상\s*발\s*명|선\s*행\s*발\s*명|인\s*용\s*문\s*헌)"
_SEP = r"(?:,|및|와|과|또는|혹은|내지|~|∼|ㆍ|·|\+|-|–)"
# 나열 사이 공백은 줄바꿈도 받고, 구분자는 둘까지(`1, 2, 또는 3`). 구분자 없는 숫자(`Al O⏎2 3`)는 나열이 아니다.
_LABEL_SEQ_RX = re.compile(_TERM + r"\s*(\d{1,2})(?!\d)((?:\s*" + _SEP + r"(?:\s*" + _SEP + r")?\s*(?:" + _TERM + r"\s*)?\d{1,2}(?!\d))*)")


def label_numbers_used(s: str) -> set[int]:
    """본문이 쓰는 라벨 번호 — 구분자가 있는 나열만(화학식 아래첨자 `Al O\\n2 3` 은 나열이 아니다)."""
    out: set[int] = set()
    for m in _LABEL_SEQ_RX.finditer(s):
        if s[m.end():m.end() + 1] == "들":
            continue
        seq = re.sub(_TERM, " ", m.group(1) + (m.group(2) or ""))
        nums = [int(x) for x in re.findall(r"\d{1,2}", seq)]
        out.update(nums)
        for a, b in re.findall(r"(\d{1,2})\s*(?:내지|~|∼|-|–)\s*(\d{1,2})", seq):
            if int(a) < int(b) <= int(a) + 10:
                out.update(range(int(a), int(b) + 1))
    return out


# `이라` · `로 칭` 은 뒤 꼴(`(…, 이하 '인용발명1'이라 함)`) 표지다 — 앞 꼴로 읽지 않는다(§20.24 · 정의 계약).
_DEF_FWD_RX = re.compile(r"(?<!이하)(?<!이하\s)[\[【(]?\s*(" + _TERM + r")\s*(\d{1,2})(?!\d)\s*[\]】)]?\s*(?:[:：=]|은|는)")
_DEF_BACK_RX = re.compile(r"이하\s*[,'‘\"“]?\s*(" + _TERM + r")\s*(\d{1,2})(?!\d)")


def _by_position(win: str, docs: dict[str, str]) -> list[str]:
    """창 안 문헌을 번호가 나온 위치 순으로."""
    def at(nid: str) -> int:
        tail = nid.split("-")[-1][-5:].lstrip("0")
        i = win.find(tail) if tail else -1
        return i if i >= 0 else len(win)
    return sorted(docs, key=at)


def definition_windows(text: str, app: str) -> dict[int, list[tuple[int, str, str]]]:
    """통지서 전체의 명시적 정의 — 번호 → [(위치, 문헌, 문헌 번호가 든 창)]. 추출기와 다른 읽기: 정의 줄 모양만 본다.
    앞 꼴 `인용발명 1 : 미국 …호` 과 뒤 꼴 `미국 …호(이하 인용발명 1)` 을 모두 본다."""
    out: dict[int, list[tuple[int, str, str]]] = {}
    for m in _DEF_FWD_RX.finditer(text):
        win = text[m.end():m.end() + 80].split("\n")[0]
        docs = N.cited_in_section(win, app)
        if docs:
            out.setdefault(int(m.group(2)), []).append((m.start(), _by_position(win, docs)[0], win))
    for m in _DEF_BACK_RX.finditer(text):
        win = text[max(0, m.start() - 80):m.start()].split("\n")[-1]
        docs = N.cited_in_section(win, app)
        if docs:
            out.setdefault(int(m.group(2)), []).append((m.start(), _by_position(win, docs)[-1], win))
    return out


def definitions(text: str, app: str) -> dict[int, list[tuple[int, str]]]:
    return {n: [(p, d) for p, d, _ in v] for n, v in definition_windows(text, app).items()}


def summary_part_for(summary: str, claims: set[int]) -> str:
    """종합 결론에서 블록 청구항을 모두 덮는 주어 묶음의 구간만 — 검사 자신의 읽기(주어 언급 사이를 나눈다)."""
    t = _blank_loc_parens(_norm(summary))
    subj = [(a, n) for a, b, n in _applicant_mentions(summary) if _SUBJ_TAIL.match(t, b)]
    parts = []
    for i, (a, n) in enumerate(subj):
        z = subj[i + 1][0] if i + 1 < len(subj) else len(t)
        if claims <= n:
            parts.append(t[a:z])
    return "\n".join(parts)


def c3_documents(r: dict, defs: dict[int, list[tuple[int, str]]]) -> list[str]:
    out = []
    t = r["text"] + ("\n" + summary_part_for(r["summary"], set(r["claims"])) if r.get("summary") else "")
    used = label_numbers_used(t)
    linked: dict[int, set[str]] = {}
    direct = 0
    for nid, vias in r.get("how", {}).items():
        for v in vias:
            if v == "direct":
                direct += 1
            elif v[2] is not None:
                linked.setdefault(v[2], set()).add(nid)
                if v[0] == "single_section_document" and {d for _, d in defs.get(v[2], [])} != {nid}:
                    out.append("C3_substitution")
    if used - set(linked) and len(used) > len(linked) + direct:
        out.append("C3_label_gap")
    lo, hi = r.get("sec_span", (0, 0))
    for n, nids in linked.items():
        cands = defs.get(n, [])
        in_sec = {d for p, d in cands if lo <= p < hi}
        scope = in_sec or {d for _, d in cands}
        if not scope:
            continue                        # 이 읽기로는 정의를 못 찾았다 — 판단하지 않는다(맹점 · BLIND_SPOTS)
        if len(scope) > 1:
            out.append("C3_definition_conflict")
        elif nids - scope:
            out.append("C3_definition_mismatch")
    return sorted(set(out))


_FOREIGN = re.compile(r"미국|일본|유럽|중국|독일|대만|\bUS\b|\bJP\b|\bEP\b|\bCN\b|\bWO\b|U\.S|특개|특표|特開|국제\s*공개")


def c4_country(r: dict, wins: dict[int, list[tuple[int, str, str]]]) -> list[str]:
    """KR 로 이은 라벨의 **정의 창**에서, 그 문헌 번호 바로 앞(30자)에 외국 표기가 있으면."""
    for nid, vias in r.get("how", {}).items():
        if not nid.startswith("KR-"):
            continue
        tail = nid.split("-")[-1][-5:].lstrip("0")
        for v in vias:
            if v == "direct" or v[2] is None:
                continue
            for _, doc, win in wins.get(v[2], []):
                at = win.find(tail) if doc == nid else -1
                if at >= 0 and _FOREIGN.search(win[max(0, at - 30):at]):
                    return ["C4_country"]
    return []


# ── C6 좌표 ─────────────────────────────────────────────────────────
_PARA_RX = re.compile(r"(?:(?:식별\s*번호|단락|문단)\s*)?[\[【]\s*(?:(?:식별\s*번호|단락|문단)\s*)?(\d{3,5})\s*(?:[-–~∼]\s*(\d{3,5})\s*)?((?:,\s*\d{3,5}\s*)*)[\]】]"
                      r"(?:\s*(?:~|∼|-|–|내지|부터)\s*[\[【]\s*(\d{3,5})\s*[\]】])?"
                      # §20.24 C6′ — 키워드가 있으면 자릿수를 묻지 않는다(`[단락 84, 도면 8]`). 추출기보다 넓게 읽는다.
                      r"|(?:식별\s*번호|단락|문단)\s*(\d{1,5})(?:\s*(?:[-–~∼]|내지)\s*(\d{1,5}))?((?:\s*,\s*\d{1,5})*)")
_FIG_RX = re.compile(r"(?<![가-힣])도(?:면)?\s*(\d{1,3})([A-Za-z]?)"
                     r"((?:\s*(?:,|및|ㆍ|·|와|과)\s*(?:도(?:면)?\s*)?(?:\d{1,3}[A-Za-z]?|[A-Za-z])(?![A-Za-z0-9]))*)"
                     r"(?:\s*(?:~|∼|내지)\s*(?:도(?:면)?\s*)?(\d{1,3})([A-Za-z]?))?(?!\s*[%℃°]|\s*(?:mm|nm|μm|um))")
_APPL_RX = re.compile(r"본원|이\s*출원|출원\s*발명|본\s*발명|청구항")
_LABEL_ONE_RX = re.compile(_TERM + r"\s*(\d{1,2})(?!\d)(?!\s*" + _SEP + r"\s*\d)")
_LABEL_LIST_RX = re.compile(_TERM + r"\s*\d{1,2}\s*" + _SEP + r"\s*\d{1,2}")
_LABEL_BARE_RX = re.compile(_TERM + r"(?!\s*\d)(?!\s*들)")      # §20.24 C6′ — 번호 없는 `비교대상발명` 도 기준점
_MAX_RANGE = 300


def _expand_para(a: str, b: str | None) -> set[tuple[str, str]]:
    lo, hi = int(a), int(b) if b else int(a)
    if not lo <= hi <= lo + _MAX_RANGE:
        hi = lo
    return {("Paragraph", str(n)) for n in range(lo, hi + 1)}


def tokens(text: str) -> list[tuple[int, set[tuple[str, str]]]]:
    """원문 좌표 표기 → (위치, {(종류, 전개된 번호)})."""
    out = []
    for m in _PARA_RX.finditer(text):
        if m.group(1):
            vals = _expand_para(m.group(1), m.group(2) or m.group(4))
            vals |= {("Paragraph", str(int(x))) for x in re.findall(r"\d{3,5}", m.group(3) or "")}
        else:
            vals = _expand_para(m.group(5), m.group(6))
            vals |= {("Paragraph", str(int(x))) for x in re.findall(r"\d{3,5}", m.group(7) or "")}
        out.append((m.start(), vals))
    for m in _FIG_RX.finditer(text):
        base, suf = m.group(1), m.group(2).upper()
        vals = {("Figure", base + suf)}
        last = base
        for it in re.findall(r"(?:도(?:면)?\s*)?(\d{1,3}[A-Za-z]?|[A-Za-z])(?![A-Za-z0-9])", m.group(3) or ""):
            if it.isalpha():
                vals.add(("Figure", last + it.upper()))
            else:
                last = re.match(r"\d+", it).group(0)
                vals.add(("Figure", it.upper()))
        if m.group(4):
            lo, hi = int(base), int(m.group(4))
            if not suf and not m.group(5) and lo < hi <= lo + 50:
                vals |= {("Figure", str(n)) for n in range(lo, hi + 1)}
            else:
                vals.add(("Figure", m.group(4) + m.group(5).upper()))
        out.append((m.start(), vals))
    return out


def expand_loaded(locs: dict[str, set]) -> set[tuple[str, str, str]]:
    """추출기 좌표 값(`[0071]~[0073]` · `도4A` · `도6~10`) → (문헌, 종류, 번호)."""
    out = set()
    for nid, items in locs.items():
        for t_, v in items:
            if t_ == "Paragraph":
                a, _, b = v.partition("~")
                out |= {(nid, *x) for x in _expand_para(a.strip("[]"), b.strip("[]") or None)}
            else:
                a, _, b = v[1:].partition("~")
                if b and a.isdigit() and b.isdigit() and int(a) < int(b) <= int(a) + 50:
                    out |= {(nid, "Figure", str(n)) for n in range(int(a), int(b) + 1)}
                else:
                    out |= {(nid, "Figure", a.upper())} | ({(nid, "Figure", b.upper())} if b else set())
    return out


_FIG_HYPHEN_RX = re.compile(r"(?<![가-힣])도(?:면)?\s*\d{1,3}[A-Za-z]?\s*[-–]\s*\d")


def expected_locators(r: dict) -> tuple[set[tuple[str, str, str]], int]:
    """원문 좌표를 **문장 안에서** 가장 가까운 앞 라벨의 문헌에 귀속한다. 귀속 못 한 표기 수도 낸다."""
    text = r["text"]
    by_label: dict[int, str] = {}
    for nid, vias in r.get("how", {}).items():
        for v in vias:
            if v != "direct" and v[2] is not None:
                by_label[v[2]] = nid
    single = next(iter(r["labels"])) if len(r.get("labels", {})) == 1 else None
    anchors = [(m.end(), by_label.get(int(m.group(1)))) for m in _LABEL_ONE_RX.finditer(text)]
    anchors += [(m.end(), None) for m in _LABEL_LIST_RX.finditer(text)]          # 나열 뒤 좌표는 어느 문헌 것인지 모른다
    # 번호 없는 라벨은 문헌이 하나뿐일 때만 그 문헌이다(데이터행 81·82·84 — 본원 쪽으로 오분류하던 원인).
    anchors += [(m.end(), single) for m in _LABEL_BARE_RX.finditer(text)]
    for nid in r.get("labels", {}):
        tail = nid.split("-")[-1][-5:].lstrip("0")
        anchors += [(m.end(), nid) for m in re.finditer(re.escape(tail) + r"(?!\d)", text)] if tail else []
    anchors.sort()
    bounds = [0] + [m.end() for m in _SENT.finditer(text)]
    exp, unattr = set(), 0
    # 도면 하이픈(`도 1-5`)은 범위인지 복합 번호인지 모른다 — 집합을 확정할 수 없으므로 귀속 못 한 표기로 센다.
    unattr += len(_FIG_HYPHEN_RX.findall(text))
    for at, vals in tokens(text):
        start = max(b for b in bounds if b <= at)
        near = [a for a in anchors if start <= a[0] <= at]
        appl = [m.end() for m in _APPL_RX.finditer(text, start, at)]
        if appl and (not near or appl[-1] > near[-1][0]):
            continue                                                     # 본원 명세서의 좌표
        nid = near[-1][1] if near else single
        if nid is None:
            unattr += 1
            continue
        exp |= {(nid, *v) for v in vals}
    return exp, unattr


def c6_locators(r: dict) -> list[str]:
    exp, unattr = expected_locators(r)
    got = expand_loaded(r.get("locs", {}))
    if unattr or exp != got:
        return ["C6_locators"]
    return []


# ── C7 논거 ─────────────────────────────────────────────────────────
RATIONALE_TERMS = {
    "DesignChoice": re.compile(r"설계\s*(?:변경|사항|적\s*선택)"),
    "PredictableEffect": re.compile(r"효과[^.]{0,40}?(?:예측|예상)"),
}
_SUBJ_PREFIX_RX = re.compile(r"^(.{0,200}?)(?:은|는)\s", re.S)


def rationale_scope(r: dict, kind: str) -> set[int]:
    """그 종류의 표현이 든 문장마다, 문장 머리(첫 `은/는` 앞)의 출원 청구항 전부 — 병렬 주어를 합친다."""
    body = r["text"]
    bounds = [0] + [m.end() for m in _SENT.finditer(body)] + [len(body)]
    out: set[int] = set()
    for m in RATIONALE_TERMS[kind].finditer(body):
        a = max(b for b in bounds if b <= m.start())
        z = min(b for b in bounds if b > m.start())
        sent = body[a:z]
        marks = list(re.finditer(r"(?:^|\n)[ \t]*" + _MARK + r"|\([가-하]\)", sent))
        if marks and marks[-1].start() < m.start() - a:
            sent = sent[marks[-1].end():]                       # 머리줄·소항목 표지 뒤부터가 그 문장이다
        pm = _SUBJ_PREFIX_RX.match(sent)
        if pm:
            out |= set().union(*[n for _, _, n in _applicant_mentions(pm.group(1))] or [set()])
        out |= subjects(sent)                                   # `제2항은 …, 제3항은 …` 열거
    return out


def c7_rationale(r: dict) -> dict[str, list[str]]:
    own = set(r["claims"])
    out = {}
    for kind in r.get("rat", []):
        sc = rationale_scope(r, kind)
        if sc and sc != own:
            out[kind] = ["C7_scope_partial" if sc < own else "C7_scope_mismatch"]
    return out


# ── §20.24 추가 검사 ─────────────────────────────────────────────────
_DOC_NUM_RX = re.compile(r"(?:\d{2}\s*-\s*\d{4}\s*-\s*\d{5,7}|\d{4}\s*[-/]\s*\d{4,7}|(?<!\d)\d{6,8}(?!\d))")
_BACK_DEF_RX = re.compile(r"이하\s*[,'‘\"“]?\s*(" + _TERM + r")\s*(\d{1,2})(?!\d)")


def c3_position(r: dict, text: str) -> list[str]:
    """C3′ — 연결 문헌의 원문 위치에서 **앞으로** 나아가 처음 만나는 `이하 라벨` 괄호가 그 라벨이어야 한다.
    다음 문헌 번호나 절 경계를 넘어서는 찾지 않는다(정의 꼴 `A ⏎(…, 이하 '인용발명1'이라 함), B`)."""
    lo, hi = r.get("sec_span", (0, len(text)))
    for nid, vias in r.get("how", {}).items():
        ns = {v[2] for v in vias if v != "direct" and v[2] is not None}
        if not ns:
            continue
        if len(ns) > 1:
            return ["C3_one_document_many_labels"]                    # 한 문헌이 라벨 번호 여럿 — 정의 대응이 무너졌다
        tail = nid.split("-")[-1][-5:].lstrip("0")
        if not tail:
            continue
        seen_ok, seen_bad = False, False
        for m in re.finditer(re.escape(tail) + r"(?!\d)", text):
            stop = min(len(text), m.end() + 160)
            nxt = _DOC_NUM_RX.search(text, m.end(), stop)           # 다음 문헌 번호에서 멈춘다
            if nxt:
                stop = nxt.start()
            if m.start() < hi <= stop:                               # 절 경계를 넘지 않는다
                stop = hi
            d = _BACK_DEF_RX.search(text, m.end(), stop)
            if d:
                (seen_ok := True) if int(d.group(2)) in ns else None
                seen_bad = seen_bad or int(d.group(2)) not in ns
        if seen_bad and not seen_ok:
            return ["C3_definition_position"]
    return []


def c4_serial(r: dict, text: str) -> list[str]:
    """C4′ — 정의 꼴과 무관하게, KR 로 이은 문헌의 일련번호를 원문에서 찾아(쉼표·공백·앞자리 0 허용) 바로 앞 30자의 국가 표기를 본다."""
    flat = re.sub(r"(?<=\d)[,\s](?=\d)", "", text)
    for nid in r.get("labels", {}):
        if not nid.startswith("KR-G-"):                             # 등록번호(국가 표기 없이 숫자만 남는 꼴)
            continue
        serial = nid.split("-")[-1].lstrip("0")
        if len(serial) < 6:
            continue
        for m in re.finditer(r"(?<!\d)0*" + re.escape(serial) + r"(?!\d)", flat):
            if _FOREIGN.search(flat[max(0, m.start() - 30):m.start()].split("\n")[-1]):
                return ["C4_country_serial"]
    return []


_CITED_SUBJ_RX = re.compile(r"^\s*(?:또한|한편|그리고)?\s*,?\s*" + _TERM + r"\s*\d{0,2}\s*(?:의\s*[가-힣\s]{0,20})?(?:은|는|에는|에서는)\s")
_MARK_LINE_RX = re.compile(r"\n[ \t]*" + _MARK + r"[ \t]*\S")


def rationale_scope2(r: dict, kind: str) -> tuple[set[int], bool]:
    """C7′ — 종류별 적용 범위. 주어 없는 논거 문장은 **같은 판단 구간**의 앞 문장 주어를 잇는다.
    머리줄·인용문헌 설명 문장을 건너야 하거나 이을 주어가 둘 이상이면 (집합, 모호=True)."""
    body = r["text"]
    bounds = [0] + [m.end() for m in _SENT.finditer(body)] + [len(body)]
    sents = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    def subj_of(a, z):
        sent = body[a:z]
        marks = list(re.finditer(r"(?:^|\n)[ \t]*" + _MARK + r"|\([가-하]\)", sent))
        if marks:
            sent = sent[marks[-1].end():]
        out = set()
        pm = _SUBJ_PREFIX_RX.match(sent)
        if pm:
            out |= set().union(*[n for _, _, n in _applicant_mentions(pm.group(1))] or [set()])
        return out | subjects(sent)
    scope, ambiguous = set(), False
    for m in RATIONALE_TERMS[kind].finditer(body):
        idx = max(i for i, (a, z) in enumerate(sents) if a <= m.start())
        own = subj_of(*sents[idx])
        if own:
            scope |= own
            continue
        inherited = None
        for j in range(idx - 1, -1, -1):
            a, z = sents[j]
            if _MARK_LINE_RX.search(body, a, z + 1) or _CITED_SUBJ_RX.match(body[a:z]):
                break                                               # 새 제목·인용문헌 설명을 넘지 않는다
            sj = subj_of(a, z)
            if sj:
                inherited = sj
                break
        if inherited is None:
            if len(r["claims"]) > 1:
                ambiguous = True                                    # 블록에 청구항이 여럿인데 대상이 불명확하다
        else:
            scope |= inherited
    return scope, ambiguous


def c7_rationale2(r: dict) -> dict[str, list[str]]:
    own = set(r["claims"])
    out = {}
    for kind in r.get("rat", []):
        sc, amb = rationale_scope2(r, kind)
        if amb:
            out[kind] = ["C7_scope_unclear"]
        elif sc and sc != own:
            out[kind] = ["C7_scope_partial" if sc < own else "C7_scope_mismatch"]
    return out


_JUDGE_WORDS = re.compile(r"동일|쉽게|용이|차이|신규성|진보성|대응|개시|부정|발명할\s*수|도출|주지|관용|볼\s*수|해당|불과|자명|같습니다|같다|공지")


def c9_judgment_statement(r: dict) -> list[str]:
    """C9 — 판단 서술이 없는 블록(도입문·표 머리만 남은 조각)."""
    t = _PAGE.sub(" ", r["text"])
    # `아래 표 1과 같습니다` · `다음과 같습니다` 는 비교를 예고할 뿐 판단이 아니다(5단계 20행).
    t = re.sub(r"(?:아래|다음|하기)\s*(?:의\s*)?(?:<?\s*표\s*\d*\s*>?\s*)?(?:과|와)\s*같(?:습니다|다|이)", " ", t)
    return [] if _JUDGE_WORDS.search(t) else ["C9_no_judgment"]


_OPEN2_RX = re.compile(r"^[ \t]*" + _MARK + r"[ \t]*[<\[(【]?[ \t]*(?:본원\s*(?:의\s*)?)?(?:특허\s*청구\s*(?:범위\s*)?)?(?:(?:독립|종속)\s*)?"
                       r"(?:청구항\s*(?:제\s*)?\d|청구하\s*(?:제\s*)?\d|제\s*\d{1,3}(?:\s*[-–~,]\s*\d{1,3})*\s*항)", re.M)


def c10_multiple_openings(r: dict) -> list[str]:
    """C10 — 한 단위 안에 판단을 여는 표지 줄(표지 + 출원 청구항)이 둘 이상이고 그 청구항 집합이 서로 다르면 보류.
    같은 청구항을 문헌별로 비교하는 소항목(청구항 없음 · 같은 청구항)은 병합이 아니다."""
    t = _PAGE.sub(" ", r["text"]).replace("청구하", "청구항")
    sets, titles = [], []
    for m in _OPEN2_RX.finditer(t):
        line = t[m.start(): t.find("\n", m.start()) if "\n" in t[m.start():] else len(t)]
        first = _applicant_mentions(re.sub(r"특허\s*청구\s*(?:범위\s*)?", "", line))
        if not (first and first[0][0] <= 25):
            continue
        # 제목만 있는 줄(서술 없음 · 짧음)은 판단을 여는 줄이 아니라 상위 제목이다(사용자 조건 10-05 — 주변 제목·범위를 함께 본다).
        if len(line.strip()) <= 40 and not re.search(r"(?:은|는|이|가)\s|다\s*\.|하여|대하여", line):
            titles.append(frozenset(first[0][2]))
            continue
        sets.append(frozenset(first[0][2]))
    if len(set(sets)) >= 2:
        return ["C10_multiple_openings"]
    own = set(r["claims"])
    if len(sets) == 1 and titles and own > set(sets[0]):
        return ["C10_title_range"]                       # 블록 청구항이 실제로 여는 줄보다 넓다 — 상위 제목 범위가 남았다
    return []


_CK_SENT_RX = re.compile(r"(?:통상의\s*기술자|당업자)[^.。]{0,80}?(?:잘\s*알려|널리\s*알려|알려져|주지|관용|통상적인\s*기술|기술\s*상식|일반적인\s*기술|기술\s*범주)"
                         r"|(?:잘\s*알려|널리\s*알려|주지|관용|기술\s*상식)[^.。]{0,60}?(?:통상의\s*기술자|당업자)")


def c11_common_knowledge(r: dict) -> list[str]:
    """C11 — 상식 서술(통상의 기술자 + 앎·범주 술어)이 본문에 있는데 상식 표시가 없으면 보류. 쪽 바꿈 표기를 지우고 읽는다."""
    t = re.sub(r"\s+", " ", _PAGE.sub("", r["text"]))
    return ["C11_common_knowledge"] if _CK_SENT_RX.search(t) and not r.get("ck") else []


def c12_section_conclusion(r: dict, text: str, recs: list[dict]) -> list[str]:
    """C12 — 같은 절의 결론 문장(검사 자신의 읽기) 중 블록 청구항 **전체**를 덮는 묶음이 **하나**일 때, 그 묶음 구간의 라벨 번호가
    블록에 이어진 라벨 번호 안에 있어야 한다."""
    lo, hi = r.get("sec_span", (0, 0))
    if hi <= lo:
        return []
    sec = text[lo:hi]
    own = set(r["claims"])
    covers = []
    for m in re.finditer(r"(?:따라서|그러므로|결국|이상과\s*같이)", sec):
        ends = [x.end() for x in _SENT.finditer(sec, m.end())]
        z = ends[0] if ends else len(sec)
        part = summary_part_for(sec[m.start():z], own)
        if part and not re.search(r"또는|혹은", part):            # 대안 결합 결론은 공통 문헌 집합이 아니다(재판정 10-05)
            covers.append(label_numbers_used(part))
    if len(covers) != 1:
        return []
    linked = {v[2] for vs in r.get("how", {}).values() for v in vs if v != "direct" and v[2] is not None}
    direct = sum(1 for vs in r.get("how", {}).values() if "direct" in vs)
    return ["C12_section_conclusion"] if covers[0] - linked and len(covers[0]) > len(linked) + direct else []


# ── 묶음 ────────────────────────────────────────────────────────────
def check_notice(text: str, app: str, recs: list[dict]) -> dict[str, dict]:
    """통지서 하나의 판단들 → key → {block, locators, rationale}. 관계(C8)는 build 가 블록 보류로 전파한다."""
    wins = definition_windows(text, app)
    defs = {n: [(p, d) for p, d, _ in v] for n, v in wins.items()}
    out = {}
    for r in recs:
        block = c1_claims(r) + c2_new_judgment(r) + c5_conclusion(r) + c3_documents(r, defs) + c4_country(r, wins)
        block += (c3_position(r, text) + c4_serial(r, text) + c9_judgment_statement(r) + c10_multiple_openings(r)
                  + c11_common_knowledge(r) + c12_section_conclusion(r, text, recs))
        out[r["key"]] = {"block": sorted(set(block)), "locators": c6_locators(r), "rationale": c7_rationale2(r)}
    return out


def summarize(holds: dict[str, dict]) -> Counter:
    c = Counter()
    for h in holds.values():
        c.update(h["block"])
        c.update(h["locators"])
        for v in h["rationale"].values():
            c.update(v)
    return c
