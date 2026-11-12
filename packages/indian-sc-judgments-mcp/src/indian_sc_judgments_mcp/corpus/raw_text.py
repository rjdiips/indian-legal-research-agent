"""Raw text and Text quality from a judgment PDF (Day 2, spec decisions 9 and 10).

Text comes only from the PDF's embedded text layer (PyMuPDF), page by page, joined with a
form feed (`\\f`). There is no OCR. The same PDF bytes always give the same text and hash.

Text quality is a structural check, with no score:

- A page is *scanned* when one image covers at least 90% of it and it has no visible text:
  every character is invisible (render mode 3, the layer OCR software lays under a scan),
  or there are no characters at all (a blank or un-OCRed scanned page).
- Mixed documents follow the majority of pages: a Judgment is `ocr` when strictly more than
  half of its pages are scanned, otherwise `born_digital`. So a digital judgment with a
  scanned annexure stays `born_digital`, and a scanned one with a blank or typed page stays
  `ocr`. A tie goes to `born_digital`.

Storage-agnostic (ADR-0001): returns values; the caller writes files and rows.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)

PAGE_BREAK = "\f"
FULL_PAGE_IMAGE = 0.9  # share of the page one image must cover
_INVISIBLE = 3  # PDF text render mode 3: neither fill nor stroke


class TextQuality(StrEnum):
    OCR = "ocr"
    BORN_DIGITAL = "born_digital"


class UnreadablePdf(Exception):
    """The bytes can't be opened or read as a PDF."""


@dataclass(frozen=True)
class RawText:
    text: str  # pages joined with PAGE_BREAK
    sha256: str  # of the UTF-8 text
    text_quality: TextQuality
    pages: int
    scanned_pages: int


def text_quality(scanned_pages: int, pages: int) -> TextQuality:
    """The mixed-document rule: `ocr` only when scanned pages are a strict majority."""
    return TextQuality.OCR if scanned_pages * 2 > pages else TextQuality.BORN_DIGITAL


def _is_scanned(page: pymupdf.Page) -> bool:
    area = abs(page.rect)
    if not area:
        return False
    covered = max(
        (abs(pymupdf.Rect(info["bbox"]) & page.rect) / area for info in page.get_image_info()),
        default=0.0,
    )
    if covered < FULL_PAGE_IMAGE:
        return False
    return all(span["type"] == _INVISIBLE for span in page.get_texttrace() if span["chars"])


def extract_raw_text(pdf: bytes) -> RawText:
    try:
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            if doc.needs_pass:
                raise UnreadablePdf("encrypted PDF")
            if doc.page_count == 0:
                raise UnreadablePdf("PDF has no pages")
            texts: list[str] = []
            scanned = 0
            for page in doc:
                texts.append(page.get_text("text"))
                scanned += _is_scanned(page)
    except UnreadablePdf:
        raise
    except Exception as exc:  # MuPDF raises several types for damaged files
        raise UnreadablePdf(f"{type(exc).__name__}: {exc}") from exc
    text = PAGE_BREAK.join(texts)
    return RawText(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text_quality=text_quality(scanned, len(texts)),
        pages=len(texts),
        scanned_pages=scanned,
    )
