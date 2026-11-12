"""Against the real public bucket. Opt in: `uv run pytest -m bucket`. Not run in CI.

Uses the smallest metadata parquet (year=1950, about 60 KB) to check that the real S3
endpoint behaves as the downloader assumes: listing, ETags, 304 revalidation and 206 resume.
"""

import json

import httpx
import pytest

from indian_sc_judgments_mcp.corpus.download import Pacer, PoliteFetcher, list_objects, object_url

pytestmark = pytest.mark.bucket

PREFIX = "metadata/parquet/year=1950/"


def test_real_bucket_lists_downloads_revalidates_and_resumes(tmp_path):
    with httpx.Client() as client:
        pacer = Pacer()  # the real polite pace
        (obj,) = list_objects(client, PREFIX, pacer=pacer)
        fetcher = PoliteFetcher(client, pacer=pacer, log=tmp_path / "fetch_log.jsonl")
        dest = tmp_path / obj.key

        first = fetcher.fetch(object_url(obj.key), dest, expected=obj)
        assert (first.status, dest.stat().st_size, first.etag) == (200, obj.size, obj.etag)

        unconditional = PoliteFetcher(client, pacer=pacer).fetch(object_url(obj.key), dest)
        assert unconditional.status == 304  # S3 honours If-None-Match

        body = dest.read_bytes()
        dest.unlink()
        dest.with_name(dest.name + ".part").write_bytes(body[:1000])  # as if cut off at 1000 bytes
        resumed = fetcher.fetch(object_url(obj.key), dest, expected=obj)
        assert (resumed.status, resumed.resumed_from) == (206, 1000)
        assert dest.read_bytes() == body

    log = [json.loads(line) for line in (tmp_path / "fetch_log.jsonl").read_text().splitlines()]
    assert [r["status"] for r in log] == [200, 206]
