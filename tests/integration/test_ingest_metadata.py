import datetime as dt
import json
from pathlib import Path

import httpx
import pytest

from indian_sc_judgments_mcp.corpus.download import Pacer
from legal_agent.ingest import ingest_year_metadata

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[2] / "packages" / "indian-sc-judgments-mcp" / "tests" / "fixtures"
KEY = "metadata/parquet/year=2020/metadata.parquet"
ETAG = '"21db805de751fc62a16d02b3026a5f6f"'


def fake_bucket() -> httpx.Client:
    """Serves the recorded 2020 listing and the tiny parquet in place of the real object."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list-type") == "2":
            return httpx.Response(200, content=(FIXTURES / "s3_list_metadata_year2020.xml").read_bytes())
        if request.url.path == "/" + KEY:
            if request.headers.get("if-none-match") == ETAG:
                return httpx.Response(304)
            body = (FIXTURES / "metadata_tiny.parquet").read_bytes()
            return httpx.Response(200, content=body, headers={"ETag": ETAG})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _ingest(conn, tmp_path):
    return ingest_year_metadata(conn, 2020, client=fake_bucket(), data_home=tmp_path, pacer=Pacer(0))


def test_after_one_run_the_years_judgments_can_be_queried(conn, tmp_path):
    report = _ingest(conn, tmp_path)

    rows = conn.execute(
        "SELECT path, decision_date, reporter_year, snapshot_id, source_uri, license, attribution"
        " FROM judgments ORDER BY path"
    ).fetchall()
    assert len(rows) == 5
    by_path = {r[0]: r for r in rows}
    assert by_path["2020_1_10_20"][1:3] == (dt.date(2019, 11, 27), 2020)
    assert {r[3] for r in rows} == {report.snapshot_id}
    assert {r[4] for r in rows} == {"https://indian-supreme-court-judgments.s3.amazonaws.com/" + KEY}
    assert {r[5] for r in rows} == {"CC-BY-4.0"}
    assert all("CC-BY-4.0" in r[6] for r in rows)
    (manifest_etag,) = conn.execute(
        "SELECT manifest->'objects'->0->>'etag' FROM snapshots WHERE snapshot_id = %s", [report.snapshot_id]
    ).fetchone()
    assert manifest_etag == ETAG


def test_report_counts_duplicates_and_date_problems(conn, tmp_path):
    report = _ingest(conn, tmp_path)

    assert report.counts["rows_read"] == 6
    assert report.counts["duplicates"] == 1
    assert report.counts["missing_decision_dates"] == 1
    assert report.counts["bad_decision_dates"] == 2
    assert report.upserted == 5


def test_running_twice_leaves_the_row_count_unchanged(conn, tmp_path):
    first = _ingest(conn, tmp_path)
    second = _ingest(conn, tmp_path)

    assert second.snapshot_id == first.snapshot_id
    assert conn.execute("SELECT count(*) FROM judgments").fetchone() == (5,)
    assert conn.execute("SELECT count(*) FROM snapshots").fetchone() == (1,)
    (db_manifest,) = conn.execute("SELECT manifest FROM snapshots").fetchone()
    assert db_manifest == json.loads(second.manifest_path.read_text())  # disk and DB agree after a rerun
