"""Golden tests for Pinpoint paragraphs and Bench size, over cleaned text of the golden raw texts
(1950s to 2020s, `ocr` and `born_digital`; see golden/README.md)."""

from pathlib import Path

import pytest

from indian_sc_judgments_mcp.corpus.clean import clean_text
from indian_sc_judgments_mcp.corpus.parse import Bench, bench_size, paragraphs

GOLDEN = Path(__file__).parent / "golden"
ALL = sorted(p.stem for p in GOLDEN.glob("*.txt"))


def cleaned(path: str):
    return clean_text((GOLDEN / f"{path}.txt").read_text(encoding="utf-8"), path=path)


def first_page(path: str) -> str:
    text = cleaned(path)
    return text.text[: text.page_end(0)]


# --- Bench size -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "size", "evidence"),
    [
        ("2015_2_37_50", 1, "[RANJAN GOGOi, J.]"),  # single judge (arbitration, s. 11(6))
        ("S_1996_4_314_315", 2, "[M.M. PUNCHHI, AND K. VENKATASWAMI, JJ.]"),
        ("2017_7_348_348", 2, "[R. BANUMATHI AND A. M. KHANWILKAR, JJ.)"),
        ("1983_3_321_336", 2, "[E.S. VENKA'fARAMIAH AND V. BALAKRISHNA ERADI, JJ.)"),
        ("2016_4_157_170", 2, "[T. S. THAKUR, CJI AND R. BANUMATHI, JJ.)"),
        ("2019_18_990_994", 2, "[DEEPAK GUPTA AND SANJIV KHANNA, JJ.]"),
        ("2024_4_598_605", 2, "[Vikram Nath* and K.V. Viswanathan, JJ.]"),
        ("S_2003_2_63_65", 3, "[V.N.KHARE, CJ., K.G. BALAKRISHNAN AND S.B. SINHA, JJ.]"),
        ("1961_3_813_820", 3, "(J. L. KAPUR, M. HIDAYATULLAH and J.C. SHAH, JJ.)"),
        ("2015_7_1_9", 3, "[T. S. THAKUR, R. K. AGRAWAL AND ADARSH KUMAR GOEL, JJ.]"),
        # constitution benches
        ("1950_1_453_459", 5,
         "[SAIYID FAZL ALI, PATANJALI SASTRI, MEHR CHAND MAHAJAN, MUKHERJEA and DAS, JJ.]"),
        ("2023_4_585_595", 5,
         "[K. M. JOSEPH, AJAY RASTOGI, ANIRUDDHA BOSE, HRISHIKESH ROY AND C. T. RAVIKUMAR, JJ.]"),
    ],
)  # fmt: skip
def test_golden_bench_size_and_its_evidence(path, size, evidence):
    assert bench_size(first_page(path)) == Bench(size, evidence)


def test_bench_size_is_unknown_when_the_coram_has_no_judges_title():
    # "[K. M. JOSEPH AND B. V. NAGARATHNA]": no "JJ." to say these are the judges.
    assert bench_size(first_page("2023_1_1105_1110")) == Bench(None, None)


def test_a_high_court_bench_named_in_prose_is_not_the_coram():
    assert bench_size("from a judgment of the High Court at Simla (Falshaw and Soni JJ.) dated") == Bench(
        None, None
    )


@pytest.mark.parametrize(
    "coram",
    [
        "[ANIL R. DAVE AND DIPAK MISRA, J.]",  # two names but "J."
        "[1. C. SHAH, K. S. HEGDE AND A. N. GROVER, J]",
        "[M. Y. EQBAL, JJ.]",  # one name but "JJ."
    ],
)
def test_bench_size_is_unknown_when_the_count_disagrees_with_the_title_but_evidence_is_kept(coram):
    assert bench_size(f"JANUARY 6, 2015\n{coram}\nPenal Code") == Bench(None, coram)


@pytest.mark.parametrize(
    ("coram", "size"),
    [
        ("[H.L. DATTU, CJI AND ARUN MISHRA, J.]", 2),
        ("[M.Y. EQBALAND C. NAGAPPAN, JJ.]", 2),  # OCR ran AND into a name
        ("[JAGDISH SINGH KHEHAR ANDS.A. BOBDE, JJ.]", 2),
        ("[S. R. DAS C. J., BHAGWATI, VENKATARAMA AYYAR, B. P. SINHA and S. K. DAs J J.]", 5),
        ("[M. HIDAYATULLAH, S. M. S!KRI AND RAGHUBAR DAYAL, JJ.j", 3),
        ("[ P.N. BHAGWATI, A.C. GUPTA, S. MURTAZA FAZAL Au V.D. TULZAPURKAR, D.A. DESAI, R.S. PATHAK AND "
         "E.S. VENKATARAMIAH, JJ. ]", 7),
        ("[DR. DHANANJAYA Y CHANDRACHUD, CJI, SANJAY KISHAN KAUL, SANJIV KHANNA, B R GAVAI, SURYA KANT, "
         "J B PARDIWALA AND MANOJ MISRA, JJ.]", 7),
    ],
)  # fmt: skip
def test_bench_size_reads_common_coram_forms(coram, size):
    assert bench_size(f"OCTOBER 16, 2015\n{coram}\nService Law").size == size


@pytest.mark.parametrize(
    ("coram", "size"),
    [
        ("[T. S. THAKUR, CJJ, DR. D. Y. CHANDRACIIUD AND L. NAGESWARA RAO, .JJ.J", 3),
        ("[DIPAK MISRA, CJJ, R. BANUMATHI AND ASHOK BHUSHAN, JJ.)", 3),
        ("[DIPAK MISRA, CJT, A. K. SIKRI, A. M. KHANWILKAR, DR. D. Y. CHANDRACHUD AND ASHOK BHUSHAN, "
         "JJ.]", 5),
        ("[Dr Dnhananjaya Y Chandrachud,* CJl, 8 R Gavai, Surya Kant, J B Pardiwala and Manoj Misra, "
         "JJ.]", 5),
        ("[DIPAK MISRA CJI, AMITAVA ROY AND A. M. KHANWILKAR, JJ.]", 3),
    ],
)  # fmt: skip
def test_ocr_forms_of_cji_are_a_title_not_a_judge(coram, size):
    assert bench_size(f"FEBRUARY 16, 2018 {coram} Inter-State Water Disputes:").size == size


# First pages from the real corpus where a one-judge block comes before the bench's coram.
@pytest.mark.parametrize(
    ("page", "size", "evidence"),
    [
        (  # 2018_5_1127_1150: a connected case's title carries its author
            "STATE OF KARNATAKA BY ITS CHIEF SECRETARY v. STATE OF T. N. BY ITS CHIEF SECRETARY "
            "[DIPAK MISRA, CJI] STATE OF TAMIL NADU v.\nP. K. SINHA AND ANR.\n(Contempt Petition (Civil) "
            "No. 898 of 2018 In Civil Appeal No. 2453 of 2007) MAY 18, 2018 [DIPAK MISRA, CJI, "
            "A. M. KHANWILKAR AND DR. D.Y. CHANDRACHUD, JJ.] Inter-State Water Disputes:",
            3,
            "[DIPAK MISRA, CJI, A. M. KHANWILKAR AND DR. D.Y. CHANDRACHUD, JJ.]",
        ),
        (  # 2017_1_158_260: OCR read the CJI's title as the block's end
            "(Civil Appeal No. 37of1992) JANUARY 02, 2017 [T. S. THAKUR, C.J.l., MADAN B. LOKUR, "
            "S. A. BOBDE, ADARSH KUMAR GOEL, UDAY UMESH LALIT, DR. D.Y. CHANDRACHUD AND "
            "L. NAGESWARA RAO, JJ.) Representation of the People Act, 1951:",
            7,
            "[T. S. THAKUR, C.J.l., MADAN B. LOKUR, S. A. BOBDE, ADARSH KUMAR GOEL, UDAY UMESH LALIT, "
            "DR. D.Y. CHANDRACHUD AND L. NAGESWARA RAO, JJ.)",
        ),
        (  # 2017_9_797_1158: the coram ends `JJ,j`; the headnote names each opinion's author
            "AUGUST 22, 2017 [JAGDISH SINGH KHEHAR, CJI, KURIAN JOSEPH, R. F. NARIMAN, UDAY .UMESH LALIT "
            "AND S. ABDUL NAZEER, JJ,j MAJORITY OPINION Muslim Law: Talaq-e-biddat - set aside. "
            "(Per Court) Art.13(1). (Per Nariman, J.) Muslim Law: Sunnis - Discussed.",
            5,
            "[JAGDISH SINGH KHEHAR, CJI, KURIAN JOSEPH, R. F. NARIMAN, UDAY .UMESH LALIT AND "
            "S. ABDUL NAZEER, JJ,j",
        ),
    ],
)  # fmt: skip
def test_a_one_judge_block_gives_way_to_a_later_bench_block(page, size, evidence):
    assert bench_size(page) == Bench(size, evidence)


# From the real corpus (mostly 2017 OCR): the bracket closing a `JJ.` block read as another mark.
@pytest.mark.parametrize(
    ("coram", "size"),
    [
        ("[DIPAK MISRA AND R. BANUMATHI, JJ.I", 2),
        ("[DIPAK MISRA AND A.M. KHANWILKAR, JJ.f", 2),
        ("[KURIAN JOSEPH AND R. BANUMATHI, JJ.[", 2),
        ("[JAGDISH SINGH KHEHAR, CJI, DR. D.Y. CHANDRACHUD AND L. NAGESWARA RAO, JJ.t", 3),
        ("(ANIL R. DAVE, KURIAN JOSEPH AND AMITAVA ROY, JJ.(", 3),
        ("[M.Y. EQBALANDAMITAVA ROY, JJ.]", 2),  # OCR ran AND into both names
        ("[SHIVA KIRTI SINGH A~D R. BANUMATHI, JJ.]", 2),
        ("[RANJAN GOGOi ~ND ASIIOK BHUSIIAN, JJ.)", 2),
    ],
)  # fmt: skip
def test_bench_size_reads_ocr_damaged_coram_blocks(coram, size):
    assert bench_size(f"FEBRUARY 14, 2017 {coram} Penal Code, 1860 - ss. 300").size == size


def test_an_opinion_author_line_is_not_a_coram():
    assert bench_size("Discussed. (Per Nariman, J.) Muslim Law: Sunnis - Discussed.") == Bench(None, None)


def test_bench_size_is_never_a_default_of_one():
    assert bench_size("No coram block on this page at all.") == Bench(None, None)


# --- Pinpoint paragraphs ----------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL)
def test_each_paragraphs_text_is_its_slice_of_cleaned_text(path):
    text = cleaned(path).text
    paras = paragraphs(text)

    assert paras
    for p in paras:
        assert p.text == text[p.start : p.end]
        assert p.text.strip() == p.text
    assert [p.ordinal for p in paras] == list(range(1, len(paras) + 1))
    assert all(a.end <= b.start for a, b in zip(paras, paras[1:], strict=False))


@pytest.mark.parametrize(
    ("path", "count", "first"),
    [
        ("2015_2_37_50", 11, "1. A works contract No.3AAA E dated"),
        ("2015_7_1_9", 10, "1.\nLeave granted."),
        ("2016_4_157_170", 23, "I. Leave granted."),
        ("2019_18_990_994", 11, "1. The short question involved in this appeal"),
        ("2023_1_1105_1110", 18, "(1) The relief sought for in the transfer petition"),
        ("2023_4_585_595", 27, "(1) Applications for intervention and impleadment are allowed."),
        ("2024_4_598_605", 10, "1. The Appellant-State of Madhya Pradesh"),
        ("2025_4_2742_2752", 25, "1) Leave granted."),  # `1)` alone on its line, text on the next
    ],
)
def test_golden_numbered_paragraphs(path, count, first):
    paras = paragraphs(cleaned(path).text)

    assert [p.number for p in paras] == list(range(1, count + 1))
    assert paras[0].text.startswith(first)


@pytest.mark.parametrize(
    "path", ["1950_1_453_459", "1961_3_813_820", "1983_3_321_336", "S_1996_4_314_315", "S_2003_2_63_65",
             "2017_7_348_348"],
)  # fmt: skip
def test_a_judgment_with_no_paragraph_markers_is_one_unnumbered_block(path):
    text = cleaned(path).text

    [block] = paragraphs(text)

    assert block.number is None
    assert block.text == text.strip()


def test_paragraph_n_can_be_fetched():
    paras = {p.number: p for p in paragraphs(cleaned("2019_18_990_994").text)}

    assert paras[9].text.startswith("9. As pointed out above, both Regulation 37(a) and Para 8.2")
    assert paras[9].text.endswith("there would be no question of rounding off.")


def test_numbers_inside_a_paragraph_do_not_split_it():
    paras = paragraphs(cleaned("2024_4_598_605").text)

    # paragraph 1 quotes paragraph 27 of the impugned order, and paragraph 2 lists (i) to (xviii)
    assert '"27.' in paras[0].text and "Therefore, the order under revision is set aside" in paras[0].text
    assert "(xviii)." in paras[1].text


def test_the_headnotes_numbered_held_points_are_not_paragraphs():
    paras = paragraphs(cleaned("2019_18_990_994").text)

    assert "HELD" not in paras[0].text
    assert paras[1].text.startswith("2. We may make reference to the Defence Service Regulations")


def test_an_ocr_misread_paragraph_number_is_taken():
    paras = {p.number: p for p in paragraphs(cleaned("2016_4_157_170").text)}

    assert paras[10].text.startswith("I 0. Even though there were ten participants")


def test_a_bracket_numbered_paragraph_after_a_full_line_and_a_margin_letter_is_taken():
    # From 2015_5_542_578 (renumbered): its `7)` was joined onto paragraph 6's last line, so 6 ran
    # 47,654 characters and swallowed paragraphs 7 to the end.
    raw = (
        "JUDGMENT\nA. K. SIKRI, J.\n1) Leave granted.\n"
        "2) Simultaneously, second set of notifications were issued \n"
        "for acquisition of land for development of residential urban \n"
        "estate to adjust oustees of the above said road. According \n"
        "necessary to acquire the land for development of residential \n"
        "urban estate to rehabilitate such oustees. \nD \n"
        "3) Insofar as first notification is concerned, it was \n"
        "challenged on various grounds including the plea that the said \n"
    )
    paras = paragraphs(clean_text(raw).text)

    assert [p.number for p in paras] == [1, 2, 3]
    assert paras[-1].text.startswith("3) Insofar as first notification")


@pytest.mark.parametrize("bracket", ["(para \n51)", "(Pg. \n183)"])  # 2016_5_884_892, 2022_12_761_796
def test_a_wrapped_bracket_ending_in_a_number_does_not_hide_the_next_paragraph(bracket):
    raw = (
        "JUDGMENT\nDIPAK MISRA, J.\n1. Leave granted.\n"
        "2. The applicant moved this Court. The facts are as under. It was observed that \n"
        f'the judgment adversely affects the petitioner." {bracket} \n'
        "3. The said jurisdiction because of its very nature has attracted the terminology \n"
    )
    paras = paragraphs(clean_text(raw).text)

    assert [p.number for p in paras] == [1, 2, 3]
    assert paras[1].text.endswith(" ".join(bracket.split()))


def test_a_short_numbered_list_deep_in_an_unnumbered_judgment_is_not_paragraphs():
    text = (
        "The Judgment of the Court was delivered by\nSHAH J. The appellant was assessed for the year. "
        + "The facts are long. " * 60
        + "The questions referred were:\n1. Whether the sums received were income.\n"
        "2. Whether depreciation is allowable.\nWe answer both in the negative."
    )

    [block] = paragraphs(text)

    assert block.number is None


def test_empty_text_has_no_paragraphs():
    assert paragraphs("") == []
