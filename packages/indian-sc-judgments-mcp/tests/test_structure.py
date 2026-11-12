import hashlib
import shutil
from pathlib import Path

from indian_sc_judgments_mcp.corpus.clean import CleanText
from indian_sc_judgments_mcp.corpus.extract import raw_text_path
from indian_sc_judgments_mcp.corpus.parse import Bench
from indian_sc_judgments_mcp.corpus.structure import clean_text_path, offset_map_path, structure_judgment

GOLDEN = Path(__file__).parent / "golden"


def _home_with_raw(tmp_path: Path, *paths: str) -> Path:
    for path in paths:
        dest = raw_text_path(tmp_path, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GOLDEN / f"{path}.txt", dest)
    return tmp_path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_judgment_gets_cleaned_text_its_offset_map_paragraphs_and_bench_size(tmp_path):
    home = _home_with_raw(tmp_path, "2019_18_990_994")

    result = structure_judgment(
        home, "2019_18_990_994", raw_sha256=_sha(raw_text_path(home, "2019_18_990_994"))
    )

    assert result.error is None
    clean_file = clean_text_path(home, "2019_18_990_994")
    assert result.clean_text_path == clean_file
    assert result.clean_sha256 == _sha(clean_file)
    assert result.bench == Bench(2, "[DEEPAK GUPTA AND SANJIV KHANNA, JJ.]")
    assert [p.number for p in result.paragraphs] == list(range(1, 12))
    text = clean_file.read_text(encoding="utf-8")
    assert all(p.text == text[p.start : p.end] for p in result.paragraphs)

    # the map on disk takes a cleaned span back to raw
    mapped = CleanText.from_offset_map(text, offset_map_path(home, "2019_18_990_994").read_text())
    start = text.index("[DEEPAK GUPTA")
    rs, re_ = mapped.raw_span(start, start + 13)
    assert raw_text_path(home, "2019_18_990_994").read_text(encoding="utf-8")[rs:re_] == "[DEEPAK GUPTA"


def test_rerunning_gives_the_same_cleaned_text_and_hash(tmp_path):
    home = _home_with_raw(tmp_path, "2024_4_598_605")

    first = structure_judgment(home, "2024_4_598_605")
    second = structure_judgment(home, "2024_4_598_605")

    assert first == second


def test_missing_raw_text_is_an_error_and_writes_nothing(tmp_path):
    result = structure_judgment(tmp_path, "2099_1_1_1")

    assert result.error
    assert (result.clean_sha256, result.bench, result.paragraphs) == (None, None, [])
    assert not clean_text_path(tmp_path, "2099_1_1_1").exists()


def test_raw_text_that_changed_since_extraction_is_an_error(tmp_path):
    home = _home_with_raw(tmp_path, "2017_7_348_348")

    result = structure_judgment(home, "2017_7_348_348", raw_sha256="0" * 64)

    assert "changed" in result.error
    assert not clean_text_path(home, "2017_7_348_348").exists()
