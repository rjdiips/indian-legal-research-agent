import shutil
from pathlib import Path

import pytest

from indian_sc_judgments_mcp.corpus.download import S3Object
from indian_sc_judgments_mcp.corpus.extract import TarExtraction, extract_year, raw_text_path
from indian_sc_judgments_mcp.corpus.fetch import english_tar_keys, local_path
from indian_sc_judgments_mcp.corpus.raw_text import TextQuality
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot

FIXTURES = Path(__file__).parent / "fixtures"
MINI_TAR = FIXTURES / "english_mini.tar"
MINI_INDEX = FIXTURES / "english_mini.index.json"


def test_each_indexed_pdf_becomes_one_raw_text_file_named_by_judgment_path(tmp_path):
    results = {r.path: r for r in TarExtraction(MINI_TAR, MINI_INDEX, tmp_path).results}

    assert set(results) == {
        "S_1996_4_314_315", "S_2003_2_63_65", "2017_7_348_348", "2024_4_598_605", "2099_1_1_1",
    }  # fmt: skip
    digital = results["2024_4_598_605"]
    assert digital.text_quality is TextQuality.BORN_DIGITAL
    assert digital.pages == 8
    assert digital.raw_text_path == tmp_path / "text" / "raw" / "2024_4_598_605.txt"
    assert raw_text_path(tmp_path, "2024_4_598_605") == digital.raw_text_path
    text = digital.raw_text_path.read_bytes().decode("utf-8")
    assert "The State of Madhya Pradesh" in text
    assert results["S_1996_4_314_315"].text_quality is TextQuality.OCR


def test_an_unreadable_pdf_is_recorded_as_an_error_and_the_run_continues(tmp_path):
    results = {r.path: r for r in TarExtraction(MINI_TAR, MINI_INDEX, tmp_path).results}

    bad = results["2099_1_1_1"]
    assert bad.error
    assert (bad.sha256, bad.text_quality, bad.raw_text_path) == (None, None, None)
    assert not raw_text_path(tmp_path, "2099_1_1_1").exists()
    assert sum(r.error is None for r in results.values()) == 4


def test_index_entries_missing_from_the_tar_and_unindexed_entries_are_reported(tmp_path):
    run = TarExtraction(MINI_TAR, MINI_INDEX, tmp_path)
    list(run.results)

    assert run.missing_from_tar == ["2099_1_2_2_EN.pdf"]
    assert run.unindexed == ["README.txt"]


def test_extracting_twice_gives_byte_identical_files_and_hashes(tmp_path):
    first = {r.path: r.sha256 for r in TarExtraction(MINI_TAR, MINI_INDEX, tmp_path / "a").results}
    second = {r.path: r.sha256 for r in TarExtraction(MINI_TAR, MINI_INDEX, tmp_path / "b").results}

    assert first == second
    for path, sha in first.items():
        if sha:
            assert (
                raw_text_path(tmp_path / "a", path).read_bytes()
                == raw_text_path(tmp_path / "b", path).read_bytes()
            )


def _downloaded(home: Path, year: int = 2099) -> dict:
    """Put the mini tar and index in the data home as `year`'s download; return a manifest listing them."""
    index_key, tar_key = english_tar_keys(year)
    for src, key in [(MINI_INDEX, index_key), (MINI_TAR, tar_key)]:
        local_path(home, key).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, local_path(home, key))
    listing = [S3Object(key, local_path(home, key).stat().st_size, "etag") for key in (index_key, tar_key)]
    return Snapshot.from_listing(listing).manifest()


def test_extract_year_reads_the_snapshots_tar_and_index_from_the_data_home(tmp_path):
    manifest = _downloaded(tmp_path)

    results = list(extract_year(tmp_path, 2099, manifest).results)

    assert len(results) == 5
    assert raw_text_path(tmp_path, "2017_7_348_348").exists()


def test_extract_year_refuses_a_year_whose_tar_is_not_in_the_snapshot(tmp_path):
    _downloaded(tmp_path)
    manifest = Snapshot.from_listing([]).manifest()

    with pytest.raises(LookupError, match="year=2099"):
        extract_year(tmp_path, 2099, manifest)


def test_extract_year_refuses_a_downloaded_tar_that_does_not_match_the_snapshot(tmp_path):
    manifest = _downloaded(tmp_path)
    with local_path(tmp_path, english_tar_keys(2099)[1]).open("ab") as tar:
        tar.write(b"changed since the Snapshot")

    with pytest.raises(LookupError, match="english.tar"):
        extract_year(tmp_path, 2099, manifest)
