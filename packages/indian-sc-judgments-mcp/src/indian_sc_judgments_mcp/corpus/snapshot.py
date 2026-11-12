"""Record the bucket snapshot used (Day 1).

A Snapshot is a manifest of the bucket objects a build used (key, size, ETag).
`snapshot_id` is the SHA-256 of the canonical JSON of those objects only, so the
same listing always gives the same id, and any changed ETag gives a new one.
Fetch time and dedup counts are recorded in the manifest but not hashed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indian_sc_judgments_mcp.corpus.download import S3Object


@dataclass(frozen=True)
class Snapshot:
    objects: tuple[S3Object, ...]
    fetched_at: str
    snapshot_id: str

    @classmethod
    def from_listing(cls, objects: Iterable[S3Object], fetched_at: str | None = None) -> Snapshot:
        ordered = tuple(sorted(objects, key=lambda o: o.key))
        canonical = json.dumps(
            [_object_dict(o) for o in ordered], sort_keys=True, separators=(",", ":")
        ).encode()
        return cls(
            objects=ordered,
            fetched_at=fetched_at or dt.datetime.now(dt.UTC).isoformat(),
            snapshot_id=hashlib.sha256(canonical).hexdigest(),
        )

    def manifest(self, dedup: Mapping[str, object] | None = None) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "fetched_at": self.fetched_at,
            "objects": [_object_dict(o) for o in self.objects],
            "dedup": dict(dedup or {}),
        }

    def save(self, data_home: Path, dedup: Mapping[str, object] | None = None) -> Path:
        path = Path(data_home) / "snapshots" / f"{self.snapshot_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():  # a listing seen before keeps its first fetch time
            path.write_text(json.dumps(self.manifest(dedup), indent=2) + "\n")
        return path


def _object_dict(o: S3Object) -> dict:
    return {"key": o.key, "size": o.size, "etag": o.etag}
