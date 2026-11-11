import json
from pathlib import Path

import httpx
import pytest

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.metadata import fetch_year_metadata

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "metadata/parquet/year=2020/metadata.parquet"


def fake_bucket(listing: str = "s3_list_metadata_year2020.xml") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list-type") == "2":
            return httpx.Response(200, content=(FIXTURES / listing).read_bytes())
        if request.url.path == "/" + KEY:
            return httpx.Response(
                200,
                content=(FIXTURES / "metadata_tiny.parquet").read_bytes(),
                headers={"ETag": '"21db805de751fc62a16d02b3026a5f6f"'},  # as listed
            )
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_one_year_is_listed_snapshotted_downloaded_and_loaded(tmp_path):
    year = fetch_year_metadata(2020, client=fake_bucket(), data_home=tmp_path, pacer=Pacer(0))

    assert len(year.load.judgments) == 5
    assert {j.snapshot_id for j in year.load.judgments} == {year.snapshot.snapshot_id}
    assert {j.source_uri for j in year.load.judgments} == {
        "https://indian-supreme-court-judgments.s3.amazonaws.com/" + KEY
    }
    manifest = json.loads(year.manifest_path.read_text())
    assert year.manifest_path.parent == tmp_path / "snapshots"
    assert manifest["objects"][0]["etag"] == '"21db805de751fc62a16d02b3026a5f6f"'
    assert manifest["dedup"]["duplicates"] == 1
    assert manifest["dedup"]["bad_decision_dates"] == 2
    assert manifest["dedup"]["missing_decision_dates"] == 1


def test_a_year_with_no_metadata_parquet_is_an_error(tmp_path):
    with pytest.raises(LookupError, match="year=1949"):
        fetch_year_metadata(1949, client=fake_bucket("s3_list_empty.xml"), data_home=tmp_path, pacer=Pacer(0))


def test_download_that_does_not_match_the_listed_etag_is_rejected(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list-type") == "2":
            return httpx.Response(200, content=(FIXTURES / "s3_list_metadata_year2020.xml").read_bytes())
        return httpx.Response(200, content=b"changed", headers={"ETag": '"0000"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match="ETag"):
        fetch_year_metadata(2020, client=client, data_home=tmp_path, pacer=Pacer(0))
