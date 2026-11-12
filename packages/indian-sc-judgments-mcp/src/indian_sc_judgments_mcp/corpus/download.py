"""Download metadata and selected years from AWS Open Data (Day 1).

Anonymous HTTP against the public S3 endpoint, at a polite pace (ADR-0002).
Ported from the data-gate scripts `s3_list.py` and `polite_fetch.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

BUCKET = "indian-supreme-court-judgments"
BUCKET_URL = f"https://{BUCKET}.s3.amazonaws.com/"
USER_AGENT = "sc-judgments-corpus/0.1 (low-rate bulk download; generic client)"
DEFAULT_DELAY = 3.0  # seconds between requests to the bucket

_NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}


class Pacer:
    """Keeps at least `delay` seconds between requests. Share one per host."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._delay = delay
        self._sleep = sleep
        self._clock = clock
        self._last_sent: float | None = None

    def wait(self) -> None:
        """Call just before sending a request."""
        now = self._clock()
        if self._last_sent is not None:
            gap = self._last_sent + self._delay - now
            if gap > 0:
                self._sleep(gap)
                now += gap
        self._last_sent = now


@dataclass(frozen=True)
class S3Object:
    key: str
    size: int
    etag: str


def object_url(key: str) -> str:
    return BUCKET_URL + key


def list_objects(
    client: httpx.Client,
    prefix: str,
    *,
    pacer: Pacer | None = None,
) -> list[S3Object]:
    """List every object under `prefix` (ListObjectsV2, following continuation tokens)."""
    pacer = pacer or Pacer()
    objects: list[S3Object] = []
    token: str | None = None
    while True:
        pacer.wait()
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        response = client.get(BUCKET_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        for item in root.findall("s:Contents", _NS):
            objects.append(
                S3Object(
                    key=item.findtext("s:Key", "", _NS),
                    size=int(item.findtext("s:Size", "0", _NS)),
                    etag=item.findtext("s:ETag", "", _NS),
                )
            )
        token = root.findtext("s:NextContinuationToken", None, _NS)
        if not token:
            return objects


class ManifestMismatch(RuntimeError):
    """A download's size or ETag disagrees with the Snapshot manifest."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    path: Path
    status: int  # 200 downloaded, 206 resumed, 304 the local copy is current
    etag: str | None
    resumed_from: int = 0  # bytes already on disk when a 206 resume started
    bytes_received: int = 0
    requested: bool = True  # False: the local copy matched the manifest, so nothing was sent


class PoliteFetcher:
    """GET files at no more than one request per `delay` seconds, revalidating local copies.

    A `<file>.meta.json` sidecar keeps the ETag and Last-Modified of each download, so a
    rerun sends a conditional GET and skips unchanged files (HTTP 304). Downloads go to a
    `<file>.part` first, so the destination is never half-written. If a download breaks off,
    the `.part` stays, and the next fetch asks for the rest (`Range` plus `If-Range` on the
    ETag): a 206 appends, a 200 (the object changed) starts again.

    With `expected` (the object as listed in the Snapshot manifest), a local copy with the
    same ETag and size is not requested at all, and a download whose ETag or size differs
    raises `ManifestMismatch`. With `log`, every fetch is appended to a JSONL fetch log.
    """

    def __init__(self, client: httpx.Client, *, pacer: Pacer | None = None, log: Path | None = None) -> None:
        self._client = client
        self._pacer = pacer or Pacer()
        self._log = Path(log) if log else None

    def fetch(self, url: str, dest: Path, *, expected: S3Object | None = None) -> FetchResult:
        record: dict = {"url": url, "fetched_at": dt.datetime.now(dt.UTC).isoformat(), "dest": str(dest)}
        try:
            result = self._fetch(url, Path(dest), expected)
        except Exception as e:
            record.update(status=None, error=repr(e))
            raise
        else:
            record.update(
                status=result.status,
                etag=result.etag,
                bytes=result.bytes_received,
                resumed_from=result.resumed_from,
                requested=result.requested,
            )
            return result
        finally:
            if self._log:
                self._log.parent.mkdir(parents=True, exist_ok=True)
                with self._log.open("a") as f:
                    f.write(json.dumps(record) + "\n")

    def _fetch(self, url: str, dest: Path, expected: S3Object | None) -> FetchResult:
        meta_path = dest.with_name(dest.name + ".meta.json")
        part = dest.with_name(dest.name + ".part")
        headers = {"User-Agent": USER_AGENT}
        meta: dict = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        offset = 0
        if expected and dest.exists() and meta.get("etag") == expected.etag:
            if dest.stat().st_size != expected.size:
                raise ManifestMismatch(
                    f"{dest}: size {expected.size} in the manifest, {dest.stat().st_size} on disk; "
                    "delete it to download again"
                )
            return FetchResult(url, dest, 304, expected.etag, requested=False)
        if dest.exists():
            if meta.get("etag"):
                headers["If-None-Match"] = meta["etag"]
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = meta["last_modified"]
        elif part.exists() and meta.get("etag"):
            offset = part.stat().st_size
            headers["Range"] = f"bytes={offset}-"
            headers["If-Range"] = meta["etag"]

        self._pacer.wait()
        with self._client.stream("GET", url, headers=headers, timeout=60, follow_redirects=True) as r:
            if r.status_code == 304:
                return FetchResult(url, dest, 304, meta.get("etag"))
            r.raise_for_status()
            etag = r.headers.get("etag")
            resumed = r.status_code == 206
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Record the ETag before the body, so a broken-off `.part` can be resumed.
            meta = {"url": url, "etag": etag, "last_modified": r.headers.get("last-modified")}
            meta_path.write_text(json.dumps(meta))
            if expected and etag != expected.etag:
                part.unlink(missing_ok=True)
                raise ManifestMismatch(
                    f"{url}: ETag {etag} does not match the manifest's {expected.etag}; "
                    "the object changed since the Snapshot was taken, rerun to take a fresh one"
                )
            received = 0
            with part.open("ab" if resumed else "wb") as f:
                for chunk in r.iter_bytes():  # as received: a chunk size would hold back bytes
                    f.write(chunk)
                    received += len(chunk)
            if expected and part.stat().st_size != expected.size:
                got = part.stat().st_size
                part.unlink()
                raise ManifestMismatch(f"{url}: size {expected.size} in the manifest, {got} downloaded")
            part.replace(dest)
            return FetchResult(url, dest, r.status_code, etag, offset if resumed else 0, received)
