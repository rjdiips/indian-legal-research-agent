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
A paragraph's decimal sub-paragraphs (`7.1`, `7.2`) stay inside it, as printed.

Opinions (ADR-0003): a run may restart at 1 where a new Opinion begins (`SANJAY KISHAN KAUL, J.`
then `1.`, or `V. GOPALA GOWDA, J. 1. I have ...` on one line). A restart counts only after an
author line at most `_AUTHOR_REACH` before it, so a numbered list quoted in a paragraph
(witnesses, a schedule, an Act) stays inside it. A restart costs `_RESTART_COST` markers, so each
side of it needs two or more. A first run under `_HEADNOTE_RUN` markers with no author line,
before a restart, is the headnote's points or an index (the delivery line was not found), and is
dropped. Each paragraph carries its Opinion's number; the author line (`NAME, J.`, `NAME, CJI`
ending its line, `(Per Nariman, J.)`) ends the paragraph before it, starts the new Opinion and is
kept as its author, else the author is None.

Bench size: the coram block is the first bracketed list of judges ending in `J.`, `JJ.`, `CJ.`
or `CJI` on the Judgment's first page (`[M.M. PUNCHHI AND K. VENKATASWAMI, JJ.]`), not preceded
by prose (a lowercase word, as in "the High Court (Falshaw and Soni JJ.)"). Judges are counted by
splitting on commas, `and` and `&` after dropping titles. The count is kept only when it agrees
with the ending (`JJ.` needs two or more, `J.` or `CJ.` alone exactly one) and is at most 15;
otherwise, or with no block, Bench size is unknown (`None`). The block is kept as evidence.
A block of one judge is often an Opinion's author (`[DIPAK MISRA, CJI]` in a connected case's
title, `(Per Nariman, J.)`), so it counts only when no later block follows (one that names two
or more judges, or one that fails to parse and so leaves Bench size unknown); a block
starting `Per` is never the coram. OCR forms of `CJI` (`CJJ`, `CJT`, `CJl`, `C.J.l`) are titles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_BENCH = 15

_BODY_START = re.compile(
    # OCR and typing slips seen: `Judgement`, `Judgments*`, `Ccurt`, `<;:ourt`, `delievered`
    r"(?:judge?ments?\*?|orders?)(?:\s+and\s+orders?)?\s+of\s+the\s+\S{4,7}\s+(?:was|were)\s+"
    r"(?:del\w{5,8}|passed|pronounced)"
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
    opinion: int = 1  # the Opinion it belongs to, 1, 2, ... in order of appearance


@dataclass(frozen=True)
class Opinion:
    number: int  # 1, 2, ... in order of appearance
    author: str | None  # the author line as read (`SANJAY KISHAN KAUL, J.`); None when not found
    start: int  # offsets into cleaned text; Opinions tile the whole text
    end: int


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
    plain += [(m.start(1), 1) for m in _AFTER_AUTHOR.finditer(text, begin)]
    bracketed = [(m.start(), _number(m[1])) for m in _BRACKET_MARKER.finditer(text, begin)]
    starts = _numbered_chain(sorted(set(plain)), text)
    if _far(starts, begin) and len(starts) < _SHORT_CHAIN:
        starts = []  # a short numbered list inside an unnumbered Judgment, not its paragraphs
    # One numbering style per Judgment: `12.` unless `(12)` gives a longer run starting right
    # after the delivery line (numbered footnotes `(1)`, `(2)` run through many old Judgments).
    in_brackets = _numbered_chain(bracketed, text)
    if len(in_brackets) > max(len(starts), _SHORT_CHAIN - 1) and not _far(in_brackets, begin):
        starts = in_brackets
    first = [s for s in starts if s[2] == 1]
    if len(first) < min(len(starts), _HEADNOTE_RUN) and not _author(text, begin, starts[0][0]):
        starts = [(start, number, opinion - 1) for start, number, opinion in starts[len(first) :]]
    if not starts:
        start = len(text) - len(text.lstrip())
        end = len(text.rstrip())
        return [Paragraph(1, None, start, end, text[start:end])] if end > start else []

    out = []
    for i, (start, number, opinion) in enumerate(starts):
        stop = len(text)
        if i + 1 < len(starts):
            stop, _, next_opinion = starts[i + 1]
            if next_opinion != opinion:  # the next Opinion's author line ends this paragraph
                author = _author(text, start, stop)
                stop = author.start() if author else stop
        end = start + len(text[start:stop].rstrip())
        out.append(Paragraph(i + 1, number, start, end, text[start:end], opinion))
    return out


def opinions(text: str, paras: list[Paragraph]) -> list[Opinion]:
    """The Opinions of `paras` (from `paragraphs(text)`): each runs from its author line (or first
    paragraph) to the next Opinion; the first starts at 0 and the last ends at the end of the text."""
    firsts = [p for i, p in enumerate(paras) if i == 0 or p.opinion != paras[i - 1].opinion]
    out = []
    for k, first in enumerate(firsts):
        if k == 0:
            start, author = 0, _author(text, body_start(text), first.start)
        else:
            start = paras[first.ordinal - 2].end
            start += len(text[start : first.start]) - len(text[start : first.start].lstrip())
            author = _author(text, start, first.start)
        out.append(Opinion(k + 1, author and " ".join(author[0].split()), start, len(text)))
    return [
        Opinion(o.number, o.author, o.start, out[i + 1].start if i + 1 < len(out) else len(text))
        for i, o in enumerate(out)
    ]


# An Opinion's author line: `SANJAY KISHAN KAUL, J.`, `DR. D.Y. CHANDRACHUD, CJI`,
# `Bela M. Trivedi, J.` ending its line (or followed by paragraph 1), or `(Per Nariman, J.)`;
# not a running header's `[S. RAVINDRA BHAT, J.]` nor a judge named in prose ("Sikri, J. held").
_AUTHOR = re.compile(
    r"(?<![\w.\[])(?:(?:DR|Dr)\.\s*)?(?:[A-Z](?:\.\s*|[ \t]+)|[A-Z][A-Za-z'’-]+[ \t]+)*[A-Z][A-Za-z'’-]+"
    r",\s*(?:CJI|C\.\s?J\.|J\.)[ \t]*(?:$|(?=1\s*[.)]))"
    r"|\(\s*Per\s+[^()]{2,60}?,?\s*(?:CJI|C\.\s?J\.|JJ?\.)\s*\)",
    re.M,
)


def _author(text: str, lo: int, hi: int) -> re.Match[str] | None:
    """The last author line in text[lo:hi], the one nearest the Opinion's first paragraph."""
    *_, last = [None, *_AUTHOR.finditer(text, lo, hi)]
    return last


def _far(starts: list[tuple[int, int, int]], begin: int) -> bool:
    return not begin or not starts or starts[0][0] - begin > _FIRST_MARKER_REACH


def _numbered_chain(candidates: list[tuple[int, int]], text: str) -> list[tuple[int, int, int]]:
    """The best run of markers in document order whose numbers rise by 1, or by up to
    `_MAX_STEP` where a marker was lost (OCR, a page break), starting at 1 or 2, and restarting
    at 1 after an author line in `text`, where a new Opinion begins. Best = most markers, less
    `_RESTART_COST` per restart, then fewest skipped numbers. A list of numbers quoted inside a
    paragraph rarely beats the Judgment's own run. Returns (offset, number, Opinion) per taken marker."""
    best: dict[int, tuple[float, int]] = {}  # number -> (score, candidate index) of best chain end
    links: list[tuple[float, int, bool]] = []  # per candidate: (score, previous index or -1, restart)
    done = (float("-inf"), -1)  # the best chain ending at any earlier candidate
    for i, (_, number) in enumerate(candidates):
        score, prev, restart = (1.0, -1, False) if number in (1, 2) else (float("-inf"), -1, False)
        at = candidates[i][0]
        if (
            number == 1
            and done[0] + 1 - _RESTART_COST > score
            and _author(text, max(candidates[done[1]][0], at - _AUTHOR_REACH), at)
        ):
            score, prev, restart = done[0] + 1 - _RESTART_COST, done[1], True
        for step in range(1, _MAX_STEP + 1):
            if number - step in best:
                s, j = best[number - step]
                s += 1 - 0.1 * (step - 1)
                if s > score:
                    score, prev, restart = s, j, False
        links.append((score, prev, restart))
        if score > float("-inf") and (number not in best or score > best[number][0]):
            best[number] = (score, i)
            done = max(done, (score, i))
    if not best:
        return []
    i = done[1]
    chain = []
    while i >= 0:
        chain.append(i)
        i = links[i][1]
    chain.reverse()
    out, opinion = [], 1
    for i in chain:
        opinion += links[i][2]
        out.append((*candidates[i], opinion))
    return out


_MAX_STEP = 3
# What starting a new Opinion's run costs, in markers: an Opinion needs more paragraphs than this.
# shortcut: a one-paragraph Opinion stays in the paragraph before it; lower this if they matter.
_RESTART_COST = 1.5
# How far before a restart's `1.` its author line may be (an index may come between).
_AUTHOR_REACH = 5000
# A first run shorter than this, with no author line, before a restart is not an Opinion.
_HEADNOTE_RUN = 10
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
    lone = None  # the first one-judge block: the coram only when no later block exists
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
        if bench.size == 1:
            lone = lone or bench
            continue
        return bench
    return lone or Bench(None, None)


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
