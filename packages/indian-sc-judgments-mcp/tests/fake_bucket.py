"""An in-memory stand-in for the public S3 bucket, served through `httpx.MockTransport`.

Answers ListObjectsV2 (by prefix, one page), GET with `If-None-Match` (304) and
`Range` with `If-Range` (206). Every request is kept in `requests`.
"""

from __future__ import annotations

import hashlib
from xml.sax.saxutils import escape

import httpx

_LIST_ITEM = (
    "<Contents><Key>{key}</Key><LastModified>2026-04-11T13:53:43.000Z</LastModified>"
    "<ETag>{etag}</ETag><Size>{size}</Size><StorageClass>INTELLIGENT_TIERING</StorageClass></Contents>"
)


class FakeBucket:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)
        self.requests: list[httpx.Request] = []
        self._sent: list[str] = []

    def etag(self, key: str) -> str:
        return '"' + hashlib.md5(self.objects[key]).hexdigest() + '"'

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle))

    def downloads(self) -> list[str]:
        """Keys whose body was sent (200 or 206), in order."""
        return list(self._sent)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.params.get("list-type") == "2":
            prefix = request.url.params.get("prefix", "")
            items = "".join(
                _LIST_ITEM.format(key=escape(k), etag=escape(self.etag(k)), size=len(v))
                for k, v in sorted(self.objects.items())
                if k.startswith(prefix)
            )
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>\n<ListBucketResult '
                'xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>indian-supreme-court-judgments</Name>'
                f"<Prefix>{escape(prefix)}</Prefix><IsTruncated>false</IsTruncated>{items}</ListBucketResult>"
            )
            return httpx.Response(200, content=body.encode())

        key = request.url.path.lstrip("/")
        if key not in self.objects:
            return httpx.Response(404)
        body, etag = self.objects[key], self.etag(key)
        if request.headers.get("if-none-match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        start = 0
        if "range" in request.headers and request.headers.get("if-range") == etag:
            start = int(request.headers["range"].removeprefix("bytes=").rstrip("-"))
        self._sent.append(key)
        if start:
            headers = {"ETag": etag, "Content-Range": f"bytes {start}-{len(body) - 1}/{len(body)}"}
            return httpx.Response(206, content=body[start:], headers=headers)
        return httpx.Response(200, content=body, headers={"ETag": etag})
