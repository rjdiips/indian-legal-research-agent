"""Download metadata and selected years from AWS Open Data (Day 1).

Anonymous HTTP against the public S3 endpoint, at a polite pace (ADR-0002).
Ported from the data-gate scripts `s3_list.py` and `polite_fetch.py`.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class FetchResult:
    url: str
    path: Path
    status: int  # 200 downloaded, 304 the local copy is current
    etag: str | None


class PoliteFetcher:
    """GET files at no more than one request per `delay` seconds, revalidating local copies.

    A `<file>.meta.json` sidecar keeps the ETag and Last-Modified of each download, so a
    rerun sends a conditional GET and skips unchanged files (HTTP 304). Downloads go to a
    temporary file first, so an interrupted fetch never leaves a half-written file behind.
    """

    def __init__(self, client: httpx.Client, *, pacer: Pacer | None = None) -> None:
        self._client = client
        self._pacer = pacer or Pacer()

    def fetch(self, url: str, dest: Path) -> FetchResult:
        dest = Path(dest)
        meta_path = dest.with_name(dest.name + ".meta.json")
        headers = {"User-Agent": USER_AGENT}
        meta: dict = {}
        if dest.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("etag"):
                headers["If-None-Match"] = meta["etag"]
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = meta["last_modified"]

        self._pacer.wait()
        with self._client.stream("GET", url, headers=headers, timeout=60, follow_redirects=True) as r:
            if r.status_code == 304:
                return FetchResult(url, dest, 304, meta.get("etag"))
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            try:
                with tmp.open("wb") as f:
                    for chunk in r.iter_bytes(65536):
                        f.write(chunk)
                tmp.replace(dest)
            finally:
                tmp.unlink(missing_ok=True)
            etag = r.headers.get("etag")
            meta_path.write_text(
                json.dumps({"url": url, "etag": etag, "last_modified": r.headers.get("last-modified")})
            )
            return FetchResult(url, dest, 200, etag)
