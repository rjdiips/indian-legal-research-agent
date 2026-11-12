"""Clean a Judgment's raw text, keeping an offset map back to raw (Day 2).

Raw text is PyMuPDF's page text joined with `\\f` (see `raw_text.py`). Cleaning works line by
line and only ever drops raw characters or replaces a line break, so every cleaned character is
either copied from raw or is a separator (`" "` or `"\\n"`) standing in for a dropped break.
The offset map records the copied runs, so any cleaned span maps back to a raw span.

What is removed:
- page headers and footers: page numbers, "SUPREME COURT REPORTS" lines, Reporter citation
  lines such as `[2015] 10 S.C.R.`, running titles (`A v. B`, `... [SINHA, J.]`) at the top of a
  page, and short noise lines at a page's top or bottom;
- margin letters (`A` to `H` beside the text of the S.C.R. page): lines holding only them, a
  letter before lowercase text or a paragraph number at line start, and a letter after
  lowercase text at line end;
- hyphenation at line end (the hyphen is dropped unless the document spells the word with a
  hyphen elsewhere) and line-wrap breaks (replaced by a space);
- the Judgment's own citation line on its first page (`[2017] 7 S.C.R. 348`).

A line break is kept (as `"\\n"`) before a line that starts with a number, letter or roman
numeral marker such as `2.` or `(iv)`, around a `JUDGMENT` or `ORDER` heading, and after a
short line ending a sentence, so paragraph
markers stay at line start. Footnotes, side notes and the headnote stay.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
import statistics
from dataclasses import dataclass, field

from indian_sc_judgments_mcp.corpus.raw_text import PAGE_BREAK

# Characters dropped wherever they occur: C0 controls other than tab and newline.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")

_PAGE_NUMBER = re.compile(r"[\W_]{0,3}\d{1,4}[\W_]{0,3}")
_REPORTS = re.compile(r"SUPR\S*\s*C[O0]\S*\s*\S{1,3}P|Digital\s+Supreme\s+Court\s+Reports", re.I)
_SCR = r"S\s?\.?\s?C\s?\.?\s?R\s?\.?"
# A line that is nothing but a Reporter citation: `[2015] 10 S.C.R. 1013`, `IJ983) 3 S.C.R.`,
# `[2024] 4 S.C.R. 598 : 2024 INSC 315`, `S.C.R.`, or a bare `. [1961]`.
_SCR_LINE = re.compile(
    rf"\S?[\W\dIlJO]*(?:SUPP\S*[\W\dIl]*)?{_SCR}[\W\d]*(?:\d{{4}}\s+INSC\s+\d+[\W]*)?"
    r"|[\W_]*[\[\(][\dIl]{4}[\]\)][\W_]*",
    re.I,
)
_FOOTNOTE = re.compile(r"\(\s*[\dIl!]{1,2}\s*\)")
_VERSUS = re.compile(r"v\s*\.|\bvs\b|\bversus\b", re.I)
_BRACKETED_JUDGE = re.compile(r"[\[\(][^\[\]\(\)]{2,40}J\s*\.?\s*[\]\)]?\s*\d{0,4}\s*$")
_NOISE = re.compile(r"[\W_]{0,3}[A-Za-z]{0,2}[\W_]{0,3}")
_MARGIN_LINE = re.compile(r"[\W_]*(?:[A-Hc0][.,]?\s*){1,8}[\W_]*")
_LEAD_MARGIN = re.compile(r"[B-H]\s+(?=[a-z]|\d{1,3}\s*\.\s)")
_TRAIL_MARGIN = re.compile(r"(?<=[a-z,;.\-)])\s+[A-H]$")
# Lowercase words that are often followed by a letter label (`clause A`), so a trailing capital
# after them is not a margin letter.
_LABEL_WORDS = frozenset(
    [
        "clause",
        "schedule",
        "annexure",
        "part",
        "exhibit",
        "form",
        "appendix",
        "group",
        "category",
        "class",
        "type",
        "grade",
        "item",
        "list",
        "table",
        "section",
        "para",
        "paragraph",
        "rule",
        "article",
        "order",
        "column",
        "no.",
        "ex.",
        "letter",
        "mark",
        "marked",
        "block",
        "sector",
        "ward",
        "plot",
        "wing",
        "tower",
        "phase",
        "zone",
        "series",
    ]
)
# A line starting a numbered or lettered item: `2.`, `12.`, `(iv)`, `a)`, `(b)`.
_MARKER_START = re.compile(
    r"(?:[\dIl](?: ?[\dIlOo]){0,2}\s*[.,](?!\d)|\(?[ivxlIVXL]{1,5}\)|\(?[a-z]\)|\(\d{1,3}\))"
)
_PARA_NUMBER = re.compile(r"\d{1,3}\s*[.,]|\(?[ivxlIVXL]{1,5}\)|\(?[a-z]\)|\(\d{1,3}\)")
# A heading line opening the body (`JUDGMENT`, `O R D E R`), kept on a line of its own.
_HEADING = re.compile(r"(?:J\s?U\s?D\s?G\s?M\s?E\s?N\s?T|O\s?R\s?D\s?E\s?R|Judgment|Order)\s*:?")
_SENTENCE_END = re.compile(r"[.:;?!\"”'’]$")
# How far from a page's top or bottom furniture is looked for, not counting margin letters and noise.
_TOP_LINES = 6
_BOTTOM_LINES = 4
_OWN_CITATION_LINES = 15


@dataclass(frozen=True)
class CleanText:
    text: str
    # Copied runs: (clean_start, raw_start, length), in order. Characters of `text` outside
    # every run are separators standing in for a dropped line break.
    segments: tuple[tuple[int, int, int], ...]
    # Cleaned offset where each raw page begins (page N of raw is `raw.split("\\f")[N]`).
    page_starts: tuple[int, ...] = field(default=(0,))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def raw_span(self, start: int, end: int) -> tuple[int, int]:
        """The raw span holding cleaned `text[start:end]`: from the first copied character at or
        after `start` to just past the last copied character before `end`. A span with no copied
        character maps to an empty raw span where it would be."""
        segs = self.segments
        starts = [s[0] for s in segs]
        i = bisect.bisect_right(starts, start) - 1
        if i >= 0 and start < segs[i][0] + segs[i][2]:
            raw_start = segs[i][1] + start - segs[i][0]
        else:
            i += 1
            raw_start = segs[i][1] if i < len(segs) else self._raw_end()
        j = bisect.bisect_left(starts, end) - 1
        if j < 0:
            return raw_start, raw_start
        cs, rs, n = segs[j]
        raw_end = rs + min(end - cs, n)
        return raw_start, max(raw_start, raw_end)

    def _raw_end(self) -> int:
        if not self.segments:
            return 0
        _, rs, n = self.segments[-1]
        return rs + n

    def page_end(self, page: int) -> int:
        """Cleaned offset where raw page `page` ends."""
        return self.page_starts[page + 1] if page + 1 < len(self.page_starts) else len(self.text)

    def offset_map_json(self) -> str:
        return json.dumps({"segments": self.segments, "page_starts": self.page_starts}, separators=(",", ":"))

    @classmethod
    def from_offset_map(cls, text: str, offset_map: str) -> CleanText:
        data = json.loads(offset_map)
        return cls(text, tuple(tuple(s) for s in data["segments"]), tuple(data["page_starts"]))


@dataclass
class _Line:
    page: int
    pieces: list[tuple[int, int]]  # raw spans kept, in order

    def text(self, raw: str) -> str:
        return "".join(raw[a:b] for a, b in self.pieces)


def _lines(raw: str) -> list[list[_Line]]:
    """Raw text as pages of lines; each line keeps its raw spans without control characters and
    without leading or trailing whitespace. Empty lines are left out."""
    pages: list[list[_Line]] = []
    offset = 0
    for number, page in enumerate(raw.split(PAGE_BREAK)):
        lines: list[_Line] = []
        pos = offset
        for line in page.split("\n"):
            pieces: list[tuple[int, int]] = []
            last = 0
            for m in _CONTROL.finditer(line):
                if m.start() > last:
                    pieces.append((pos + last, pos + m.start()))
                last = m.end()
            if last < len(line):
                pieces.append((pos + last, pos + len(line)))
            pieces = _strip(raw, pieces)
            if pieces:
                lines.append(_Line(number, pieces))
            pos += len(line) + 1
        pages.append(lines)
        offset += len(page) + 1
    return pages


def _strip(raw: str, pieces: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out = [(a, b) for a, b in pieces if raw[a:b].strip()]
    if not out:
        return []
    a, b = out[0]
    out[0] = (a + len(raw[a:b]) - len(raw[a:b].lstrip()), b)
    a, b = out[-1]
    out[-1] = (a, b - (len(raw[a:b]) - len(raw[a:b].rstrip())))
    return out


def _cut_front(line: _Line, n: int) -> None:
    """Drop the first `n` characters of a line."""
    while n > 0 and line.pieces:
        a, b = line.pieces[0]
        if b - a <= n:
            line.pieces.pop(0)
            n -= b - a
        else:
            line.pieces[0] = (a + n, b)
            n = 0


def _cut_back(line: _Line, n: int) -> None:
    while n > 0 and line.pieces:
        a, b = line.pieces[-1]
        if b - a <= n:
            line.pieces.pop()
            n -= b - a
        else:
            line.pieces[-1] = (a, b - n)
            n = 0


def _is_page_number(t: str, pages: range | None) -> bool:
    """A page number line. `12.` could be a paragraph number instead; it counts as a page
    number only when it falls in the Judgment's own page range (from its `path`)."""
    m = _PAGE_NUMBER.fullmatch(t)
    if not m:
        return False
    if pages is not None and int(re.sub(r"\D", "", t)) in pages:
        return True
    return not _PARA_NUMBER.fullmatch(t)


def _is_header(t: str, page: int, recurring: set[str], title_seen: bool, pages: range | None) -> bool:
    if _is_page_number(t, pages):
        return True
    if _PARA_NUMBER.fullmatch(t):
        return False
    if _MARGIN_LINE.fullmatch(t) or _NOISE.fullmatch(t):
        return True
    if len(t) < 80 and _REPORTS.search(t):
        return True
    if _SCR_LINE.fullmatch(t) and not _FOOTNOTE.match(t):
        return True
    if page > 0 and len(t) < 120:
        if _BRACKETED_JUDGE.search(t) or _norm(t) in recurring:
            return True
        if _VERSUS.search(t) and _upper_share(t) >= 0.6:
            return True
        if title_seen and len(t) < 60 and not re.search(r"[a-z]", t):
            return True
    return False


def _is_noise(t: str) -> bool:
    return bool(_MARGIN_LINE.fullmatch(t) or _NOISE.fullmatch(t)) and not _PAGE_NUMBER.fullmatch(t)


def _is_footer(t: str, pages: range | None) -> bool:
    if _is_page_number(t, pages):
        return True
    if _PARA_NUMBER.fullmatch(t):
        return False
    if _SCR_LINE.fullmatch(t) and not _FOOTNOTE.match(t):
        return True
    return bool(_MARGIN_LINE.fullmatch(t) or _NOISE.fullmatch(t))


def _norm(t: str) -> str:
    return re.sub(r"[\W\d_]+", "", t).lower()


def _upper_share(t: str) -> float:
    letters = [c for c in t if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def _own_citation(path: str | None) -> tuple[str, str] | None:
    """(Reporter year, first page) from a `path` like `2017_7_348_348` or `S_1975_1_169_201`."""
    m = _PATH.match(path or "")
    return (m[1], m[2]) if m else None


def _page_range(path: str | None) -> range | None:
    m = _PATH.match(path or "")
    return range(int(m[2]), int(m[3]) + 1) if m and int(m[2]) <= int(m[3]) else None


_PATH = re.compile(r"(?:S_)?(\d{4})_\d+_(\d+)_(\d+)")


def _is_own_citation_line(t: str, own: tuple[str, str] | None) -> bool:
    if not _SCR_LINE.fullmatch(t) or _FOOTNOTE.match(t) or not re.search(_SCR, t, re.I):
        return False
    if own is None:
        return True
    numbers = re.findall(r"\d+", t)
    return own[0] in numbers and own[1] in numbers


def _drop_page_furniture(raw: str, pages: list[list[_Line]], path: str | None) -> None:
    tops = [{_norm(ln.text(raw)) for ln in lines[: 2 * _TOP_LINES + 8]} for lines in pages[1:]]
    recurring = {t for t in set().union(*tops) if len(t) >= 8 and sum(t in top for top in tops) >= 2}
    page_range = _page_range(path)
    for number, lines in enumerate(pages):
        keep_from, budget, title_seen = 0, _TOP_LINES, False
        for i, line in enumerate(lines):
            t = line.text(raw)
            if budget == 0 or not _is_header(t, number, recurring, title_seen, page_range):
                break
            if not _is_noise(t):
                budget -= 1
            title_seen = title_seen or bool(_VERSUS.search(t) or _BRACKETED_JUDGE.search(t))
            keep_from = i + 1
        keep_to, budget = len(lines), _BOTTOM_LINES
        for i in range(len(lines) - 1, keep_from - 1, -1):
            t = lines[i].text(raw)
            if budget == 0 or not _is_footer(t, page_range):
                break
            if not _is_noise(t):
                budget -= 1
            keep_to = i
        lines[:] = lines[keep_from:keep_to]
    if pages:
        own = _own_citation(path)
        first = pages[0]
        for i, line in enumerate(first[:_OWN_CITATION_LINES]):
            if _is_own_citation_line(line.text(raw), own):
                del first[i]
                break


def _drop_margin_letters(raw: str, pages: list[list[_Line]]) -> None:
    for lines in pages:
        kept = []
        for line in lines:
            t = line.text(raw)
            if (_MARGIN_LINE.fullmatch(t) and not _PARA_NUMBER.fullmatch(t)) or not re.search(r"\w", t):
                continue
            m = _LEAD_MARGIN.match(t)
            if m:
                _cut_front(line, m.end())
            t = line.text(raw)
            m = _TRAIL_MARGIN.search(t)
            if m:
                before = t[: m.start()].split()
                if not before or before[-1].lower() not in _LABEL_WORDS:
                    _cut_back(line, len(t) - m.start())
            line.pieces = _strip(raw, line.pieces)
            if line.pieces:
                kept.append(line)
        lines[:] = kept


def clean_text(raw: str, path: str | None = None) -> CleanText:
    """Clean raw text (see module docstring). `path` (the Judgment's `path`, e.g.
    `2017_7_348_348`) identifies its own citation line; without it, the first citation-only line
    on page 1 is taken as its own."""
    pages = _lines(raw)
    _drop_page_furniture(raw, pages, path)
    _drop_margin_letters(raw, pages)

    lengths = [len(ln.text(raw)) for lines in pages for ln in lines]
    short = 0.7 * statistics.median(lengths) if lengths else 0

    out: list[str] = []
    segments: list[tuple[int, int, int]] = []
    page_starts = [0] * len(pages)
    size = 0

    def copy(a: int, b: int) -> None:
        nonlocal size
        if b <= a:
            return
        if segments and segments[-1][0] + segments[-1][2] == size and segments[-1][1] + segments[-1][2] == a:
            cs, rs, n = segments[-1]
            segments[-1] = (cs, rs, n + b - a)
        else:
            segments.append((size, a, b - a))
        out.append(raw[a:b])
        size += b - a

    def insert(s: str) -> None:
        nonlocal size
        out.append(s)
        size += len(s)

    prev: _Line | None = None
    prev_text = ""
    page_seen = -1
    for lines in pages:
        for line in lines:
            t = line.text(raw)
            pieces = list(line.pieces)
            if prev is not None:
                joined = _hyphen_join(raw, prev_text, t)
                if joined is not None:
                    if not joined:  # drop the hyphen: it was the last copied character
                        _uncopy_last(out, segments)
                        size -= 1
                elif _PARA_NUMBER.fullmatch(prev_text):
                    insert(" ")
                elif (
                    _MARKER_START.match(t)
                    or _HEADING.fullmatch(t)
                    or _HEADING.fullmatch(prev_text)
                    or _SENTENCE_END.search(prev_text)
                    and len(prev_text) < short
                ):
                    insert("\n")
                else:
                    insert(" ")
            while page_seen < line.page:
                page_seen += 1
                page_starts[page_seen] = size
            for a, b in pieces:
                copy(a, b)
            prev, prev_text = line, t
    while page_seen < len(pages) - 1:
        page_seen += 1
        page_starts[page_seen] = size
    return CleanText("".join(out), tuple(segments), tuple(page_starts))


def _uncopy_last(out: list[str], segments: list[tuple[int, int, int]]) -> None:
    out[-1] = out[-1][:-1]
    cs, rs, n = segments[-1]
    if n == 1:
        segments.pop()
    else:
        segments[-1] = (cs, rs, n - 1)


def _hyphen_join(raw: str, prev: str, nxt: str) -> str | None:
    """For a word hyphenated across lines: `""` to drop the hyphen, `"-"` to keep it, `None`
    when the break is not a hyphenation."""
    a = re.search(r"([A-Za-z]+)-$", prev)
    b = re.match(r"([a-z]+)", nxt)
    if not a or not b or prev.endswith("--"):
        return None
    left, right = a[1], b[1]
    if re.search(rf"\b{left}{right}", raw, re.I):
        return ""
    if re.search(rf"\b{left}-[a-z]", raw.replace(f"{left}-\n", ""), re.I):
        return "-"
    return ""
