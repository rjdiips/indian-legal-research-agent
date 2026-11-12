import datetime as dt
import hashlib
import shutil
from pathlib import Path

import pytest

from indian_sc_judgments_mcp.corpus.extract import Extracted, raw_text_path
from indian_sc_judgments_mcp.corpus.loader import Judgment
from indian_sc_judgments_mcp.corpus.raw_text import TextQuality
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot
from indian_sc_judgments_mcp.corpus.structure import clean_text_path
from legal_agent.clean import clean_texts
from legal_agent.db.corpus import save_raw_text, save_snapshot, upsert_judgments
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate

pytestmark = pytest.mark.integration

GOLDEN = Path(__file__).parents[2] / "packages" / "indian-sc-judgments-mcp" / "tests" / "golden"
WITH_RAW = ["2019_18_990_994", "S_1996_4_314_315", "2023_1_1105_1110"]
NOT_EXTRACTED = "2099_1_2_2"


def _judgment(path: str, snapshot_id: str) -> Judgment:
    fields = dict.fromkeys(
        ["title", "petitioner", "respondent", "description", "judge", "author_judge", "citation", "case_id",
         "cnr", "disposal_nature", "court", "available_languages", "nc_display", "scraped_at"],
    )  # fmt: skip
    return Judgment(
        path=path, decision_date=dt.date(2000, 1, 1), reporter_year=2099,
        snapshot_id=snapshot_id, source_uri="fixture", **fields,
    )  # fmt: skip


@pytest.fixture
def corpus(conn, tmp_path):
    """A store whose Judgments have raw text extracted (one has none), and the raw files."""
    migrate(conn, MIGRATIONS_DIR)
    snapshot = Snapshot.from_listing([])
    save_snapshot(conn, snapshot, {})
    upsert_judgments(conn, [_judgment(p, snapshot.snapshot_id) for p in [*WITH_RAW, NOT_EXTRACTED]])
    for path in WITH_RAW:
        dest = raw_text_path(tmp_path, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GOLDEN / f"{path}.txt", dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        save_raw_text(conn, Extracted(path, sha, TextQuality.OCR, 1, 1, dest))
    return tmp_path


def _rows(conn):
    rows = conn.execute(
        "SELECT path, clean_text_sha256, bench_size, bench_evidence, clean_error, cleaned_at IS NOT NULL"
        " FROM judgments"
    ).fetchall()
    return {r[0]: r[1:] for r in rows}


def _paragraphs(conn, path):
    return conn.execute(
        "SELECT ordinal, number, char_start, char_end, text FROM paragraphs WHERE path = %s ORDER BY ordinal",
        [path],
    ).fetchall()


def test_each_judgment_gets_its_cleaned_text_hash_bench_size_and_paragraphs(conn, corpus):
    report = clean_texts(conn, data_home=corpus)

    rows = _rows(conn)
    sha, size, evidence, error, stamped = rows["2019_18_990_994"]
    clean_file = clean_text_path(corpus, "2019_18_990_994")
    assert sha == hashlib.sha256(clean_file.read_bytes()).hexdigest()
    assert (size, evidence) == (2, "[DEEPAK GUPTA AND SANJIV KHANNA, JJ.]")
    assert (error, stamped) == (None, True)

    text = clean_file.read_text(encoding="utf-8")
    paras = _paragraphs(conn, "2019_18_990_994")
    assert [p[1] for p in paras] == list(range(1, 12))
    assert all(body == text[start:end] for _, _, start, end, body in paras)
    assert report.counts == {
        "cleaned": 3, "errors": 0, "numbered": 2, "unnumbered": 1, "bench_known": 2, "bench_unknown": 1,
        "paragraphs": 11 + 1 + 18,
    }  # fmt: skip


def test_an_unnumbered_judgment_is_one_block_and_an_unsure_bench_is_null(conn, corpus):
    clean_texts(conn, data_home=corpus)

    rows = _rows(conn)
    assert rows["S_1996_4_314_315"][1:3] == (2, "[M.M. PUNCHHI, AND K. VENKATASWAMI, JJ.]")
    [(ordinal, number, start, _, _)] = _paragraphs(conn, "S_1996_4_314_315")
    assert (ordinal, number, start) == (1, None, 0)
    assert rows["2023_1_1105_1110"][1:3] == (None, None)  # Bench size unknown, never 1


def test_a_judgment_without_raw_text_is_left_alone(conn, corpus):
    clean_texts(conn, data_home=corpus)

    assert _rows(conn)[NOT_EXTRACTED] == (None, None, None, None, False)


def test_raw_text_changed_since_extraction_is_an_error_on_its_judgment(conn, corpus):
    raw_text_path(corpus, "2019_18_990_994").write_text("edited by hand", encoding="utf-8")

    report = clean_texts(conn, data_home=corpus)

    sha, size, _, error, stamped = _rows(conn)["2019_18_990_994"]
    assert (sha, size, stamped) == (None, None, True)
    assert "changed" in error
    assert _paragraphs(conn, "2019_18_990_994") == []
    assert report.counts["errors"] == 1
    assert "2019_18_990_994" in report.errors


def test_rerunning_replaces_paragraphs_and_gives_the_same_hashes(conn, corpus):
    clean_texts(conn, data_home=corpus)
    first = _rows(conn), _paragraphs(conn, "2023_1_1105_1110")

    clean_texts(conn, data_home=corpus)

    again = _rows(conn), _paragraphs(conn, "2023_1_1105_1110")
    assert {p: r[:4] for p, r in again[0].items()} == {p: r[:4] for p, r in first[0].items()}
    assert again[1] == first[1]
