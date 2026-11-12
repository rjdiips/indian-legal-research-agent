"""Pinpoint paragraphs and Bench size from cleaned text (Day 2).

Paragraphs: a paragraph starts at a number marker at the start of a cleaned line (`12.`, `12)`,
OCR's `I 0.`; or `(12)` in Judgments numbered that way), searched from the body of the Judgment
("The Judgment of the Court was delivered by", "JUDGMENT", ...) so the headnote's numbered `HELD`
points don't count. Paragraph 1 may also follow the author's name (`T.S. THAKUR, J. 1. Leave
granted.`). Of the markers, the longest run whose numbers rise by 1 (or by up to 3 where one was
lost) and starts at 1 or 2 is taken, so numbers inside a paragraph (a quoted paragraph 27, a
list, a wrapped citation) don't split it. A run of fewer than 5 that doesn't start right after
the delivery line is a list, not paragraphs. A paragraph runs to the next taken marker (or the
end of the text), trailing whitespace trimmed. With no run the whole text is one unnumbered block.
Known gap: a second opinion that restarts at 1 stays inside the first opinion's last paragraph
(ticket 10). A paragraph's decimal sub-paragraphs (`7.1`, `7.2`) stay inside it, as printed.

Bench size: the coram block is the first bracketed list of judges ending in `J.`, `JJ.`, `CJ.`
or `CJI` on the Judgment's first page (`[M.M. PUNCHHI AND K. VENKATASWAMI, JJ.]`), not preceded
by prose (a lowercase word, as in "the High Court (Falshaw and Soni JJ.)"). Judges are counted by
splitting on commas, `and` and `&` after dropping titles. The count is kept only when it agrees
with the ending (`JJ.` needs two or more, `J.` or `CJ.` alone exactly one) and is at most 15;
otherwise, or with no block, Bench size is unknown (`None`). The block is kept as evidence.
A block of one judge is often an Opinion's author (`[DIPAK MISRA, CJI]` in a connected case's
title, `(Per Nariman, J.)`), so it counts only when no later block names two or more; a block
starting `Per` is never the coram. OCR forms of `CJI` (`CJJ`, `CJT`, `CJl`, `C.J.l`) are titles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_BENCH = 15

_BODY_START = re.compile(
    r"(?:judgments?|orders?)\s+of\s+the\s+c\S{3,5}\.?\s+(?:was|were)\s+(?:delivered|passed|pronounced)"
    r"|following\s+(?:judgments?|orders?)\s+(?:of\s+the\s+court\s+)?(?:was|were)\s+delivered"
    r"|Judgment\s*/\s*Order\s+of\s+the\s+Supreme\s+Court"
    r"|^\s*(?:J\s?U\s?D\s?G\s?M\s?E\s?N\s?T|O\s?R\s?D\s?E\s?R)\s*$",
    re.I | re.M,
)
# A paragraph number at line start, with OCR's `I`/`l` for 1 and `O` for 0: `12.`, `I 0.`, `l.`
_LINE_MARKER = re.compile(r"^[ \t]*([\dIl](?: ?[\dIlOo]){0,2})\s*(?:\.(?!\d)|\))", re.M)
# `THAKUR, J. 1.This`, `J.: 1.`, `J .. 1.`, `J.· 1.`, `J. 1 The`, `J. 1) The`
# The same in brackets, as some Judgments number their paragraphs: `(3) The applicant ...`
_BRACKET_MARKER = re.compile(r"^[ \t]*\(([\dIl](?: ?[\dIlOo]){0,2})\)", re.M)
_AFTER_AUTHOR = re.compile(r"\bJ\s*[.:][\W_]{0,4}?\s*(1|l|I)(?:\s*[.,)](?!\d)|\s+(?=[A-Z]))")


@dataclass(frozen=True)
class Paragraph:
    ordinal: int  # 1, 2, ... in document order
    number: int | None  # the Pinpoint number; None for the single unnumbered block
    start: int  # offsets into cleaned text
    end: int
    text: str


@dataclass(frozen=True)
class Bench:
    size: int | None  # None when unsure, never assumed to be 1
    evidence: str | None  # the coram block as found (whitespace collapsed), None when none


def body_start(text: str) -> int:
    """Offset where the Judgment's body begins (after the delivery line), 0 if not found."""
    m = _BODY_START.search(text)
    return m.end() if m else 0


def _number(token: str) -> int:
    return int(token.translate(_OCR_NUMERALS).replace(" ", ""))


_OCR_NUMERALS = str.maketrans("IlOo", "1100")


def paragraphs(text: str) -> list[Paragraph]:
    begin = body_start(text)
    plain = [(m.start(1), _number(m[1])) for m in _LINE_MARKER.finditer(text, begin)]
    m = _AFTER_AUTHOR.search(text, begin)
    if m:
        plain.append((m.start(1), 1))
    bracketed = [(m.start(), _number(m[1])) for m in _BRACKET_MARKER.finditer(text, begin)]
    starts = _numbered_chain(sorted(plain))
    if _far(starts, begin) and len(starts) < _SHORT_CHAIN:
        starts = []  # a short numbered list inside an unnumbered Judgment, not its paragraphs
    # One numbering style per Judgment: `12.` unless `(12)` gives a longer run starting right
    # after the delivery line (numbered footnotes `(1)`, `(2)` run through many old Judgments).
    in_brackets = _numbered_chain(bracketed)
    if len(in_brackets) > max(len(starts), _SHORT_CHAIN - 1) and not _far(in_brackets, begin):
        starts = in_brackets
    if not starts:
        start = len(text) - len(text.lstrip())
        end = len(text.rstrip())
        return [Paragraph(1, None, start, end, text[start:end])] if end > start else []

    out = []
    for i, (start, number) in enumerate(starts):
        stop = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        end = start + len(text[start:stop].rstrip())
        out.append(Paragraph(i + 1, number, start, end, text[start:end]))
    return out


def _far(starts: list[tuple[int, int]], begin: int) -> bool:
    return not begin or not starts or starts[0][0] - begin > _FIRST_MARKER_REACH


def _numbered_chain(candidates: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The best run of markers in document order whose numbers rise by 1, or by up to
    `_MAX_STEP` where a marker was lost (OCR, a page break), starting at 1 or 2. Best = most
    markers, then fewest skipped numbers. A list of numbers quoted inside a paragraph rarely
    beats the Judgment's own run."""
    best: dict[int, tuple[float, int]] = {}  # number -> (score, candidate index) of best chain end
    links: list[tuple[float, int]] = []  # per candidate: (score, previous candidate index or -1)
    for i, (_, number) in enumerate(candidates):
        score, prev = (1.0, -1) if number in (1, 2) else (float("-inf"), -1)
        for step in range(1, _MAX_STEP + 1):
            if number - step in best:
                s, j = best[number - step]
                s += 1 - 0.1 * (step - 1)
                if s > score:
                    score, prev = s, j
        links.append((score, prev))
        if score > float("-inf") and (number not in best or score > best[number][0]):
            best[number] = (score, i)
    if not best:
        return []
    _, i = max(best.values())
    chain = []
    while i >= 0:
        chain.append(candidates[i])
        i = links[i][1]
    return chain[::-1]


_MAX_STEP = 3
# How far after the delivery line the first paragraph marker may be (the author's name and a
# case number or two come between).
_FIRST_MARKER_REACH = 600
# A run this long is taken as paragraphs even when it doesn't start right after the delivery line.
_SHORT_CHAIN = 5


# `JJ.`, `J.`, `CJ.`, `CJI` and their OCR forms, closing the coram block: `JJ.]`, `JJ .]`,
# `JJ.)`, `JJ.J`, `JJ.j`, `JJ,j`, `JJ;]`; after `JJ.` any one mark: `JJ.I`, `JJ.f`, `JJ.(`.
_CORAM_END = re.compile(
    r"\b(J\s?\.?\s?J|JI|C\.?\s?J\.?\s?I|CJI|C\.?\s?J|J)(?:\s*[,;:]?\s*[\]\)\}|]|\s*[.,]\s*[;:]?\s*(?:[\]\)\}|]|[Jjl]\b))"
    r"|\b(J\s?J)\s*\.\s*\S(?=\s)"
)
_OPEN = re.compile(r"[\[\(\{]|\bI(?=[A-Z][.\s])")
# `CJI` with OCR's `J`, `T` or `l` for `I`: `CJJ`, `CJT`, `CJl`, `C.J.l`.
_TITLES = re.compile(r"\b(?:C\.?\s?J\.?\s?[IJTl]|C\.?\s?J|Dr|Mr|Mrs|Ms|Hon'?ble)\b\.?", re.I)
_SPLIT = re.compile(r",|;\s|\s&\s|\band\b", re.I)
# A missing comma before a judge with two or more initials: `FAZAL ALI V.D. TULZAPURKAR`.
_RUN_ON = re.compile(r"(?<=[A-Za-z]{2})\s+(?=[A-Z]\.\s?[A-Z]\.\s?[A-Z]{2})")
# `AND` run into a name by OCR: `EQBALAND C. NAGAPPAN`, `ANDS.A. BOBDE`, `MISRAAND R.`,
# `EQBALANDAMITAVA`; or misread: `A~D`, `~ND`.
_GLUED_AND = re.compile(
    r"AND(?=\s|[A-Z]\.)|(?<=[A-Z]\.)AND|(?<=[A-Z]{4})AND(?=[A-Z]{4})|\s(?:A\WD|\W{1,2}ND)\s"
)


def bench_size(first_page: str) -> Bench:
    """Bench size from the coram block on a Judgment's first page of cleaned text."""
    first = None
    for end in _CORAM_END.finditer(first_page):
        head = first_page[max(0, end.start() - 400) : end.start()]
        opens = list(_OPEN.finditer(head))
        if not opens:
            continue
        opening = opens[-1]
        content = head[opening.end() :]
        if re.search(r"[\]\)\}]", content) or re.match(r"\s*Per\b", content):
            continue  # `(Per Nariman, J.)` names an Opinion's author
        before = head[: opening.start()].rstrip()
        if before and (before[-1].islower() or before[-1] == ","):
            continue
        evidence = " ".join(first_page[max(0, end.start() - 400) + opening.start() : end.end()].split())
        bench = Bench(_count(content, end[1] or end[2]), evidence)
        if bench.size == 1 or (first and bench.size is None):
            first = first or bench
            continue
        return bench
    return first or Bench(None, None)


def _count(content: str, ending: str) -> int | None:
    kind = re.sub(r"[\s.]", "", ending).upper()
    kind = "JJ" if kind in ("JJ", "JI") else kind
    has_chief = bool(re.search(r"\bC\.?\s?J\.?\s?[IJTl]?\b", content, re.I))
    stripped = _TITLES.sub(" ", content)
    n = _names(stripped)
    if not _agrees(n, kind, has_chief):
        n = _names(_GLUED_AND.sub(",", stripped))
    return n if _agrees(n, kind, has_chief) else None


def _names(content: str) -> int:
    return sum(1 for n in _SPLIT.split(_RUN_ON.sub(",", content)) if re.search(r"[A-Za-z]{3}", n))


def _agrees(n: int, kind: str, has_chief: bool) -> bool:
    if not 1 <= n <= MAX_BENCH:
        return False
    if kind == "JJ":
        return n >= 2
    if kind == "J":  # `[X, J.]` alone, or `[A, CJI AND B, J.]`
        return n == 2 if has_chief else n == 1
    return n == 1  # CJ or CJI closing the block: the Chief Justice sitting alone
