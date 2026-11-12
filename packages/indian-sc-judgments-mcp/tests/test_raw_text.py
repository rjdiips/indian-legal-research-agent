import hashlib
import tarfile
from pathlib import Path

import pymupdf
import pytest

from indian_sc_judgments_mcp.corpus.raw_text import TextQuality, UnreadablePdf, extract_raw_text

MINI_TAR = Path(__file__).parent / "fixtures" / "english_mini.tar"


def pdf(name: str) -> bytes:
    with tarfile.open(MINI_TAR) as tar:
        return tar.extractfile(name).read()


@pytest.mark.parametrize(
    ("name", "quality"),
    [
        ("S_1996_4_314_315_EN.pdf", TextQuality.OCR),
        ("S_2003_2_63_65_EN.pdf", TextQuality.OCR),
        ("2017_7_348_348_EN.pdf", TextQuality.OCR),
        ("2024_4_598_605_EN.pdf", TextQuality.BORN_DIGITAL),
    ],
)
def test_golden_gate_samples_get_the_right_text_quality(name, quality):
    assert extract_raw_text(pdf(name)).text_quality is quality


def test_extraction_is_deterministic_page_by_page_text_from_the_embedded_layer():
    first = extract_raw_text(pdf("2024_4_598_605_EN.pdf"))
    second = extract_raw_text(pdf("2024_4_598_605_EN.pdf"))

    assert first == second
    assert first.pages == 8
    assert first.text.count("\f") == 7  # one form feed between pages
    assert "The State of Madhya Pradesh" in first.text
    assert first.sha256 == hashlib.sha256(first.text.encode("utf-8")).hexdigest()


def test_scanned_pages_keep_their_existing_ocr_text():
    raw = extract_raw_text(pdf("S_1996_4_314_315_EN.pdf"))

    assert (raw.pages, raw.scanned_pages) == (2, 2)
    assert "BIBI JABRUNNISSA" in raw.text


@pytest.mark.parametrize("data", [b"this is not a pdf\n" * 4, b"", b"%PDF-1.4\n%%EOF\n"])
def test_unreadable_bytes_raise_unreadable_pdf(data):
    with pytest.raises(UnreadablePdf):
        extract_raw_text(data)


def _combine(*parts: tuple[str, int]) -> bytes:
    """A PDF made of whole pages of the fixture PDFs: (name, number of its first pages)."""
    out = pymupdf.open()
    for name, pages in parts:
        with pymupdf.open(stream=pdf(name), filetype="pdf") as src:
            out.insert_pdf(src, from_page=0, to_page=pages - 1)
    return out.tobytes()


@pytest.mark.parametrize(
    ("parts", "scanned", "quality"),
    [
        # a digital judgment with a scanned annexure: 8 digital pages, 2 scanned
        ([("2024_4_598_605_EN.pdf", 8), ("S_1996_4_314_315_EN.pdf", 2)], 2, TextQuality.BORN_DIGITAL),
        # a scanned judgment with one digital page: 3 scanned, 1 digital
        ([("S_2003_2_63_65_EN.pdf", 3), ("2024_4_598_605_EN.pdf", 1)], 3, TextQuality.OCR),
        # a tie goes to born_digital
        ([("S_1996_4_314_315_EN.pdf", 2), ("2024_4_598_605_EN.pdf", 2)], 2, TextQuality.BORN_DIGITAL),
    ],
)
def test_mixed_documents_follow_the_strict_majority_of_pages(parts, scanned, quality):
    raw = extract_raw_text(_combine(*parts))

    assert raw.scanned_pages == scanned
    assert raw.text_quality is quality
