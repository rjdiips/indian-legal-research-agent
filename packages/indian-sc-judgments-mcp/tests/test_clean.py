"""Golden tests for cleaning. Raw texts in `golden/` are PyMuPDF page text joined by `\\f`, as
`raw_text.extract_raw_text` writes it (see golden/README.md for where each came from)."""

import random
import re
from pathlib import Path

import pytest

from indian_sc_judgments_mcp.corpus.clean import CleanText, clean_text

GOLDEN = Path(__file__).parent / "golden"
ALL = sorted(p.stem for p in GOLDEN.glob("*.txt"))


def raw(path: str) -> str:
    return (GOLDEN / f"{path}.txt").read_text(encoding="utf-8")


def clean(path: str) -> CleanText:
    return clean_text(raw(path), path=path)


def test_a_garbled_citation_in_cleaned_text_maps_back_to_the_same_raw_span():
    text = clean("1983_3_321_336")

    start = text.text.index("[196112 S.C.R. 537")
    rs, re_ = text.raw_span(start, start + len("[196112 S.C.R. 537"))

    assert raw("1983_3_321_336")[rs:re_] == "[196112 S.C.R. 537"


@pytest.mark.parametrize("path", ALL)
def test_every_cleaned_span_maps_back_to_a_raw_span_holding_the_same_characters(path):
    text, source = clean(path), raw(path)
    rng = random.Random(path)
    for _ in range(300):
        start = rng.randrange(len(text.text))
        end = rng.randrange(start, min(len(text.text), start + 400)) + 1
        rs, re_ = text.raw_span(start, end)
        piece = text.text[start:end]
        # Cleaning only drops raw characters and swaps line breaks for separators, so the
        # cleaned characters appear in the raw span in order, and its ends are copied ones.
        assert _subsequence(re.sub(r"\s", "", piece), source[rs:re_]), (start, end)
        if not piece[0].isspace():
            assert source[rs] == piece[0]
        if not piece[-1].isspace():
            assert source[re_ - 1] == piece[-1]


def _subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(c in it for c in needle)


def test_the_offset_map_round_trips_through_json():
    text = clean("2024_4_598_605")

    again = CleanText.from_offset_map(text.text, text.offset_map_json())

    assert again == text
    assert again.raw_span(100, 200) == text.raw_span(100, 200)


@pytest.mark.parametrize(
    ("path", "furniture"),
    [
        # page headers: "SUPREME COURT REPORTS", Reporter citation lines, running titles
        ("1983_3_321_336", ["SUPREME COURT REPORT", "IJ983) 3 S.C.R.", "(1983) 3 s.c.R.",
                            "RAM NATH v. MUNICIPAL"]),
        ("1961_3_813_820", ["SUPREME COURT HEPORTS", "3 s.c.R."]),
        ("S_2003_2_63_65", ["SUPREME COURT REPORTS [2003]", "STATEv. LOCHAN"]),
        ("2015_7_1_9", ["SUPREME COURT REPORTS", "[2015] 7 S.C.R.",
                        "ABDUL RAZAK & ORS. v. THE STATE OF KARNATAKA"]),
        ("2019_18_990_994", ["SUPREME COURT REPORTS", "[2019] 18 S.C.R."]),
        ("2024_4_598_605", ["Digital Supreme Court Reports", "[2024] 4 S.C.R.",
                            "\nThe State of Madhya Pradesh v. Satish Jain (Dead) by Lrs & Ors.\n"]),
        # the Judgment's own citation line on its first page
        ("2017_7_348_348", ["[2017] 7 S.C.R. 348"]),
    ],
)  # fmt: skip
def test_page_headers_and_the_own_citation_line_are_removed(path, furniture):
    text = clean(path).text
    for line in furniture:
        assert line not in text


def test_page_headers_below_the_top_of_a_page_are_removed():
    raw_text = (
        "[2017] 9 S.C.R. 797\nFirst page.\f798\nA\nB\n1-1\nSUPREME COURT REP<?RTS\n[2017] 9 S.C.R.\n"
        'the court held so.\nAnd God is Exalted in Power\nWise."\n[2017] 9 S.C.R.\n'
        "Verse 224, as held in\n[1978] 2 S.C.R.\nand also in [2017] 9 S.C.R. 1200 it was said."
    )
    text = clean_text(raw_text, path="2017_9_797_1158").text

    assert "REP<?RTS" not in text
    assert text.count("[2017] 9 S.C.R.") == 1  # the citation to page 1200 of the same volume stays
    assert "[1978] 2 S.C.R." in text  # a citation wrapped before its page number stays
    assert 'Wise." Verse 224' in text.replace("\n", " ")


@pytest.mark.parametrize("line", ["[2016) 11 S.C.R. I 03", "[2016] 11 S.C.R. IO3", "[2016] 11 S.C.R. l 03"])
def test_the_own_citation_line_with_an_ocr_misread_page_number_is_removed(line):
    text = clean_text(f"{line}\nP. M. ABUBAKAR v. STATE", path="2016_11_103_128").text

    assert text == "P. M. ABUBAKAR v. STATE"


def test_page_numbers_are_removed_but_footnotes_stay():
    text = clean("1983_3_321_336").text

    assert not re.search(r"(?m)^(322|324|325|327|328)\s*$", text)
    assert "(1) [196112 S.C.R. 537." in text  # a footnote is the Judgment's text, not furniture


def test_margin_letters_are_removed():
    text = clean("S_1996_4_314_315").text

    assert not re.search(r"(?m)^[A-Hc]\s*$", text)
    assert "an oral gift by a father" in text  # was "an oral\nG gift by a father"
    assert "to be transferred by means" in text  # was "to be B\ntransferred"


def test_a_block_of_ocr_symbol_noise_is_removed():
    text = clean("2014_14_185_186").text

    assert text.rstrip().endswith("Crl.MPs allowed.")  # the stamp's symbol lines followed it
    assert "The following Order of the Court was passed" in text


def test_tables_of_figures_and_contents_are_not_noise():
    table = [
        "12.03.2001 - 15.04.2002",
        "Rs. 1,20,000/- (31.03.2005)",
        "Submissions ........................................ 7",
        "(e.g. 33 ××××××)",
        "(t), (u), (v), (w), (x), (y), (z), (za),",
    ]
    noise = ["( ~ :. ,,.._; _:_~~;-::;;\\:·-~ ~", "• 1-", "~ ~:"]
    text = clean_text("The figures are as follows.\n" + "\n".join(table + noise) + "\nThat ends it.").text

    for line in table:
        assert line in text
    assert "~" not in text and "• 1-" not in text


def test_misread_margin_letters_are_removed():
    text = clean("2014_14_185_186").text

    assert "of 2015) (Criminal Appeal" in text  # was "of 2015)\nh\n(Criminal Appeal"
    assert "allowed. CRIMINALAPPELLATE" in text  # was "allowed.\nA\ns·\nc\nCRIMINALAPPELLATE"
    assert "accordingly. Nidhi Jain" in text  # was "B Nidhi Jain"


def test_a_margin_letter_inside_a_line_of_a_scan_is_removed():
    # A scan whose text layer glues margin letters to its lines, one page.
    raw_text = (
        "the court held B\nC that the rule applies, which c included\nthe right to be heard. D\n"
        "That ends the matter."
    )
    text = clean_text(raw_text)

    assert "which included the right" in text.text
    start = text.text.index("which included")
    assert text.raw_span(start, start + len("which included")) == (
        raw_text.index("which c"),
        raw_text.index("which c") + len("which c included"),
    )


def test_hyphenation_and_line_wraps_are_joined():
    text = clean("1983_3_321_336").text

    assert "Code of Criminal Procedure" in text  # "Proce-\ndure"
    assert "accordingly pleased" in text  # "accor-\ndingly"


def test_a_hyphen_the_judgment_writes_elsewhere_is_kept():
    text = clean("S_1996_4_314_315").text

    assert "plaintiff-rcspondcnt" in text  # "plaintiff-\nrcspondcnt"; "plaintiff-respondent" occurs


def test_paragraph_markers_stay_at_line_start():
    text = clean("2015_7_1_9").text

    assert "\n2. These appeals by special leave" in text
    assert "\n9. The Trial Court appraised" in text


def test_cleaned_text_hash_is_of_its_utf8_bytes():
    import hashlib

    text = clean("2024_4_598_605")

    assert text.sha256 == hashlib.sha256(text.text.encode("utf-8")).hexdigest()


def test_cleaning_is_deterministic():
    assert clean("2015_7_1_9") == clean("2015_7_1_9")


def test_page_starts_mark_where_each_raw_page_begins_in_cleaned_text():
    text = clean("2024_4_598_605")

    assert len(text.page_starts) == raw("2024_4_598_605").count("\f") + 1
    first_page = text.text[: text.page_end(0)].rstrip()
    assert first_page.endswith("no occasion for the plaintiff to further act upon the agreement since")


def test_empty_raw_text_cleans_to_empty():
    text = clean_text("")

    assert (text.text, text.segments) == ("", ())
    assert text.raw_span(0, 0) == (0, 0)
