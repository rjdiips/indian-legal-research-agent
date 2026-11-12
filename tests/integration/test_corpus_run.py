"""End to end: the fixture corpus through ingest, raw text, cleaning, and the run report (issue 05)."""

from pathlib import Path

import pytest
from fake_bucket import FakeBucket
from fixtures.make_tiny_parquet import write

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.fetch import english_tar_keys
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot
from legal_agent.db.corpus import save_snapshot
from legal_agent.extract import extract_text
from legal_agent.ingest import ingest_corpus
from legal_agent.pipeline import run_corpus, write_report

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[2] / "packages" / "indian-sc-judgments-mcp" / "tests" / "fixtures"
YEAR = 2099
# The mini tar's PDFs (its README): three scanned, one born-digital, one unreadable, one absent from the tar.
DECIDED = {
    "S_1996_4_314_315": "10-04-1996",
    "S_2003_2_63_65": "06-01-2003",
    "2017_7_348_348": "03-05-2017",
    "2024_4_598_605": "05-04-2024",
    "2099_1_1_1": "01-01-2024",
    "2099_1_2_2": None,
}


def _bucket(tmp_path: Path) -> FakeBucket:
    parquet = tmp_path / "metadata.parquet"
    write(
        parquet,
        [dict(path=p, decision_date=d, scraped_at="2025-06-12T21:51:58") for p, d in DECIDED.items()],
        YEAR,
    )
    index_key, tar_key = english_tar_keys(YEAR)
    return FakeBucket(
        {
            f"metadata/parquet/year={YEAR}/metadata.parquet": parquet.read_bytes(),
            index_key: (FIXTURES / "english_mini.index.json").read_bytes(),
            tar_key: (FIXTURES / "english_mini.tar").read_bytes(),
        }
    )


def _state(conn):
    judgments = conn.execute(
        "SELECT path, snapshot_id, raw_text_sha256, text_quality, text_error, clean_text_sha256, bench_size,"
        " clean_error FROM judgments ORDER BY path"
    ).fetchall()
    paragraphs = conn.execute("SELECT * FROM paragraphs ORDER BY path, ordinal").fetchall()
    # The manifest's fetched_at is when the listing was first seen; compare the content.
    snapshots = conn.execute("SELECT snapshot_id, manifest - 'fetched_at' FROM snapshots").fetchall()
    return judgments, paragraphs, snapshots


@pytest.fixture
def bucket(tmp_path):
    return _bucket(tmp_path)


@pytest.fixture
def run(conn, tmp_path, bucket):
    home, reports = tmp_path / "home", tmp_path / "reports"
    return lambda: run_corpus(
        conn, client=bucket.client(), data_home=home, tar_years=[YEAR], reports_dir=reports, pacer=Pacer(0)
    )


def test_the_report_names_its_snapshot_and_measures_the_corpus(conn, run):
    report_path = run()

    (snapshot_id,) = conn.execute("SELECT snapshot_id FROM snapshots").fetchone()
    assert report_path.name == f"corpus-{snapshot_id[:12]}.md"
    report = report_path.read_text()
    assert f"Snapshot `{snapshot_id}`" in report
    assert "| Judgments | 6 |" in report
    assert "| In those Reporter years | 6 |" in report
    assert "| English PDF found (extraction attempted) | 5 |" in report  # 2099_1_2_2 is not in the tar
    assert "| Raw text extracted | 4 |" in report
    assert "| Extraction errors | 1 |" in report
    # Shares are of the 5 attempted, so they add up with the error.
    assert "| ocr | 3 | 60.0% |" in report
    assert "| born_digital | 1 | 20.0% |" in report
    assert "| extraction error | 1 | 20.0% |" in report
    assert "`2099_1_1_1`" in report  # the unreadable PDF is listed
    assert "| 1990s | 1 |" in report  # Bench size and paragraph rows by decade of Decision date
    assert "| 2020s | 1 |" in report


def test_the_report_counts_judgments_with_an_over_long_paragraph(conn, run, tmp_path):
    assert "| With a numbered paragraph over 20,000 characters | 0 |" in run().read_text()
    # A missed marker leaves a paragraph that swallows the ones after it.
    conn.execute(
        "UPDATE paragraphs SET char_end = char_start + 20001"
        " WHERE path = '2024_4_598_605' AND number IN (1, 2)"
    )

    report = write_report(conn, tmp_path / "reports").read_text()

    assert "| With a numbered paragraph over 20,000 characters | 1 |" in report


def test_the_report_lists_judgments_in_those_years_without_an_english_pdf(conn, run):
    report = run().read_text()

    section = report.split("## Judgments without an English PDF")[1].split("##")[0]
    assert "`2099_1_2_2`" in section  # in the metadata, not in the tar
    assert "`2024_4_598_605`" not in section


def test_a_rerun_changes_nothing(conn, run):
    first_path = run()
    first = _state(conn), first_path.read_text()

    second_path = run()

    assert second_path == first_path
    assert (_state(conn), second_path.read_text()) == first


def test_reingesting_an_old_listing_does_not_make_it_the_latest_snapshot(conn, run, tmp_path):
    run_path = run()
    save_snapshot(conn, Snapshot.from_listing([], fetched_at="2000-01-01T00:00:00+00:00"), {})

    save_snapshot(conn, Snapshot.from_listing([]), {})  # that old listing ingested again, now

    assert write_report(conn, tmp_path / "reports") == run_path


def test_the_report_counts_only_text_derived_under_its_snapshot(conn, run, bucket, tmp_path):
    run()
    rescraped = tmp_path / "rescraped.parquet"
    write(
        rescraped,
        [dict(path=p, decision_date=d, scraped_at="2026-01-01T00:00:00") for p, d in DECIDED.items()],
        YEAR,
    )
    # A new ETag on the metadata, so the next ingest is a new Snapshot.
    bucket.objects[f"metadata/parquet/year={YEAR}/metadata.parquet"] = rescraped.read_bytes()
    home = tmp_path / "home"
    newer = ingest_corpus(conn, client=bucket.client(), data_home=home, tar_years=[], pacer=Pacer(0))

    report = write_report(conn, tmp_path / "reports").read_text()

    assert f"Snapshot `{newer.snapshot_id}`" in report
    assert "| Judgments | 6 |" in report
    assert "| English PDF found (extraction attempted) | 0 |" in report
    assert "| Raw text extracted | 0 |" in report
    assert "| Cleaned | 0 |" in report
    with pytest.raises(LookupError, match=f"year={YEAR}"):  # its listing has no tar for that year
        extract_text(conn, data_home=home, years=[YEAR])
