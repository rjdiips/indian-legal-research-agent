import json
from pathlib import Path

import httpx
import pytest

from indian_sc_judgments_mcp.corpus.download import (
    ManifestMismatch,
    Pacer,
    PoliteFetcher,
    S3Object,
    list_objects,
)

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


class _BreaksAfter(httpx.SyncByteStream):
    """A response body that delivers `body[:n]` then drops the connection."""

    def __init__(self, body: bytes, n: int) -> None:
        self._body, self._n = body, n

    def __iter__(self):
        yield self._body[: self._n]
        raise httpx.ReadError("connection dropped")


TAR = b"0123456789" * 10  # a 100-byte stand-in for an English tar
TAR_OBJ = S3Object("data/tar/year=2015/english/english.tar", len(TAR), '"tar-v1-5"')


def test_an_interrupted_download_resumes_from_where_it_stopped(tmp_path):
    seen: list[httpx.Request] = []
    calls = iter(["drop", "rest"])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if next(calls) == "drop":
            return httpx.Response(200, stream=_BreaksAfter(TAR, 40), headers={"ETag": TAR_OBJ.etag})
        return httpx.Response(
            206,
            content=TAR[40:],
            headers={"ETag": TAR_OBJ.etag, "Content-Range": f"bytes 40-99/{len(TAR)}"},
        )

    fetcher = PoliteFetcher(httpx.Client(transport=httpx.MockTransport(handler)), pacer=Pacer(0))
    dest = tmp_path / TAR_OBJ.key

    with pytest.raises(httpx.ReadError):
        fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)
    assert not dest.exists()
    resumed = fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)

    assert seen[1].headers["range"] == "bytes=40-"
    assert seen[1].headers["if-range"] == TAR_OBJ.etag
    assert resumed.status == 206
    assert resumed.resumed_from == 40
    assert dest.read_bytes() == TAR


def _serving(body: bytes, etag: str) -> PoliteFetcher:
    handler = lambda r: httpx.Response(200, content=body, headers={"ETag": etag})  # noqa: E731
    return PoliteFetcher(httpx.Client(transport=httpx.MockTransport(handler)), pacer=Pacer(0))


def test_a_download_whose_size_differs_from_the_manifest_fails_loudly(tmp_path):
    dest = tmp_path / TAR_OBJ.key

    with pytest.raises(ManifestMismatch, match=r"size.*100.*99"):
        _serving(TAR[:99], TAR_OBJ.etag).fetch("https://bucket.example/t", dest, expected=TAR_OBJ)
    assert not dest.exists()


def test_a_download_whose_etag_differs_from_the_manifest_fails_loudly(tmp_path):
    dest = tmp_path / TAR_OBJ.key

    with pytest.raises(ManifestMismatch, match="ETag"):
        _serving(TAR, '"tar-v2-5"').fetch("https://bucket.example/t", dest, expected=TAR_OBJ)
    assert not dest.exists()


def test_a_local_copy_matching_the_manifest_is_not_requested_again(tmp_path):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=TAR, headers={"ETag": TAR_OBJ.etag})

    fetcher = PoliteFetcher(httpx.Client(transport=httpx.MockTransport(handler)), pacer=Pacer(0))
    dest = tmp_path / TAR_OBJ.key
    fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)

    again = fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)

    assert len(seen) == 1
    assert again.status == 304
    assert again.etag == TAR_OBJ.etag


def test_each_fetch_is_appended_to_the_fetch_log(tmp_path):
    log = tmp_path / "fetch_log.jsonl"
    handler = lambda r: httpx.Response(200, content=TAR, headers={"ETag": TAR_OBJ.etag})  # noqa: E731
    fetcher = PoliteFetcher(httpx.Client(transport=httpx.MockTransport(handler)), pacer=Pacer(0), log=log)
    dest = tmp_path / TAR_OBJ.key

    fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)
    fetcher.fetch("https://bucket.example/t", dest, expected=TAR_OBJ)

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(r["url"], r["status"], r["bytes"], r["requested"]) for r in records] == [
        ("https://bucket.example/t", 200, 100, True),
        ("https://bucket.example/t", 304, 0, False),
    ]
    assert all(r["fetched_at"] for r in records)
