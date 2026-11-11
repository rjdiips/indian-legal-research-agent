from pathlib import Path

import httpx
import pytest

from indian_sc_judgments_mcp.corpus.download import Pacer, PoliteFetcher, S3Object, list_objects

FIXTURES = Path(__file__).parent / "fixtures"


def _replay(pages: dict[str | None, str], seen: list[httpx.Request]) -> httpx.Client:
    """A client that answers ListObjectsV2 requests from recorded XML, keyed by continuation token."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        token = request.url.params.get("continuation-token")
        return httpx.Response(200, content=(FIXTURES / pages[token]).read_bytes())

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_lists_one_year_from_recorded_response():
    seen: list[httpx.Request] = []
    client = _replay({None: "s3_list_metadata_year2020.xml"}, seen)

    objects = list_objects(client, "metadata/parquet/year=2020/", pacer=Pacer(0))

    assert objects == [
        S3Object(
            key="metadata/parquet/year=2020/metadata.parquet",
            size=627923,
            etag='"21db805de751fc62a16d02b3026a5f6f"',
        )
    ]
    assert seen[0].url.params["list-type"] == "2"
    assert seen[0].url.params["prefix"] == "metadata/parquet/year=2020/"
    assert "authorization" not in seen[0].headers


def test_follows_continuation_tokens_politely():
    seen: list[httpx.Request] = []
    sleeps: list[float] = []
    client = _replay({None: "s3_list_paged_1.xml", "TOKEN-PAGE-2": "s3_list_paged_2.xml"}, seen)

    clock = iter([0.0, 1.0]).__next__  # when each request is sent
    pacer = Pacer(3.0, sleep=sleeps.append, clock=clock)

    objects = list_objects(client, "metadata/parquet/", pacer=pacer)

    assert [o.key for o in objects] == [
        "metadata/parquet/year=1950/metadata.parquet",
        "metadata/parquet/year=1951/metadata.parquet",
    ]
    assert len(seen) == 2
    assert sleeps == [2.0]  # the second page waited out the 3 s gap


def test_fetch_downloads_then_revalidates_with_etag(tmp_path):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=b"PAR1-bytes", headers={"ETag": '"v1"'})

    clock = iter([0.0, 0.5]).__next__  # when each request is sent
    sleeps: list[float] = []
    pacer = Pacer(3.0, sleep=sleeps.append, clock=clock)
    fetcher = PoliteFetcher(httpx.Client(transport=httpx.MockTransport(handler)), pacer=pacer)
    dest = tmp_path / "metadata" / "year=2020" / "metadata.parquet"

    first = fetcher.fetch("https://bucket.example/k", dest)
    second = fetcher.fetch("https://bucket.example/k", dest)

    assert (first.status, second.status) == (200, 304)
    assert dest.read_bytes() == b"PAR1-bytes"
    assert first.etag == second.etag == '"v1"'
    assert "if-none-match" not in seen[0].headers
    assert seen[1].headers["if-none-match"] == '"v1"'
    assert sleeps == [2.5]  # second request waited out the 3 s gap


def test_fetch_raises_on_server_error(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    fetcher = PoliteFetcher(client, pacer=Pacer(0))

    with pytest.raises(httpx.HTTPStatusError):
        fetcher.fetch("https://bucket.example/k", tmp_path / "x.parquet")
    assert not (tmp_path / "x.parquet").exists()
