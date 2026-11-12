import datetime as dt
import json
from pathlib import Path

import pytest
from fake_bucket import FakeBucket

from indian_sc_judgments_mcp.corpus.download import Pacer
from legal_agent.ingest import ingest_corpus

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[2] / "packages" / "indian-sc-judgments-mcp" / "tests" / "fixtures"
BUCKET_URL = "https://indian-supreme-court-judgments.s3.amazonaws.com/"
META_2020 = "metadata/parquet/year=2020/metadata.parquet"
META_2021 = "metadata/parquet/year=2021/metadata.parquet"
TAR_2021 = "data/tar/year=2021/english/english.tar"


def fake_bucket() -> FakeBucket:
    return FakeBucket(
        {
            META_2020: (FIXTURES / "metadata_tiny.parquet").read_bytes(),
            META_2021: (FIXTURES / "metadata_tiny_2021.parquet").read_bytes(),
            TAR_2021: b"english tar 2021" * 50,
            "data/tar/year=2021/english/english.index.json": b'{"year": 2021, "parts": []}',
        }
    )


def _ingest(conn, tmp_path, bucket=None):
    bucket = bucket or fake_bucket()
    return ingest_corpus(conn, client=bucket.client(), data_home=tmp_path, tar_years=[2021], pacer=Pacer(0))


def test_after_one_run_every_years_judgments_can_be_queried(conn, tmp_path):
    report = _ingest(conn, tmp_path)

    rows = conn.execute(
        "SELECT path, decision_date, reporter_year, snapshot_id, source_uri, license FROM judgments"
    ).fetchall()
    by_path = {r[0]: r for r in rows}
    assert len(rows) == 6
    assert by_path["2020_1_10_20"][1:3] == (dt.date(2019, 11, 27), 2020)
    assert by_path["2020_4_552_564"][2:] == (2021, report.snapshot_id, BUCKET_URL + META_2021, "CC-BY-4.0")
    assert {r[3] for r in rows} == {report.snapshot_id}
    (keys,) = conn.execute(
        "SELECT array_agg(o->>'key' ORDER BY o->>'key')"
        " FROM snapshots, jsonb_array_elements(manifest->'objects') o WHERE snapshot_id = %s",
        [report.snapshot_id],
    ).fetchone()
    assert TAR_2021 in keys and META_2020 in keys


def test_report_counts_judgments_duplicates_and_date_problems(conn, tmp_path):
    report = _ingest(conn, tmp_path)

    assert report.counts["rows_read"] == 8
    assert report.counts["judgments"] == 6
    assert report.counts["duplicates"] == 2
    assert report.counts["missing_decision_dates"] == 1
    assert report.counts["bad_decision_dates"] == 2
    assert report.upserted == 6
    assert report.tar_years == (2021,)


def test_running_twice_downloads_nothing_and_leaves_the_row_count_unchanged(conn, tmp_path):
    bucket = fake_bucket()
    first = _ingest(conn, tmp_path, bucket)
    downloads = bucket.downloads()

    second = _ingest(conn, tmp_path, bucket)

    assert bucket.downloads() == downloads
    assert second.downloaded_bytes == 0
    assert second.snapshot_id == first.snapshot_id
    assert conn.execute("SELECT count(*) FROM judgments").fetchone() == (6,)
    assert conn.execute("SELECT count(*) FROM snapshots").fetchone() == (1,)
    (db_manifest,) = conn.execute("SELECT manifest FROM snapshots").fetchone()
    assert db_manifest == json.loads(second.manifest_path.read_text())  # disk and DB agree after a rerun
