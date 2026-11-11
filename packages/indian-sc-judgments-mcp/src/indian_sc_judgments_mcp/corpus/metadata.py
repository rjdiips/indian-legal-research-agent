"""One year's metadata, end to end: list, snapshot, download, load (Day 1).

Storage-agnostic (ADR-0001): returns records and the saved manifest path;
the caller persists the Judgments wherever it likes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from indian_sc_judgments_mcp.corpus.download import Pacer, PoliteFetcher, list_objects, object_url
from indian_sc_judgments_mcp.corpus.loader import LoadResult, load_judgments
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot


@dataclass(frozen=True)
class YearMetadata:
    year: int
    snapshot: Snapshot
    load: LoadResult
    manifest_path: Path


def metadata_prefix(year: int) -> str:
    return f"metadata/parquet/year={year}/"


def fetch_year_metadata(
    year: int, *, client: httpx.Client, data_home: Path, pacer: Pacer | None = None
) -> YearMetadata:
    """`year` is the Reporter year (bucket partition), not a Decision date.

    List the year's metadata parquet, record a Snapshot, download it and load deduplicated Judgments."""
    pacer = pacer or Pacer()
    prefix = metadata_prefix(year)
    objects = [o for o in list_objects(client, prefix, pacer=pacer) if o.key.endswith(".parquet")]
    if len(objects) != 1:
        raise LookupError(f"expected one metadata parquet under {prefix}, found {len(objects)}")
    (obj,) = objects

    snapshot = Snapshot.from_listing(objects)
    url = object_url(obj.key)
    fetched = PoliteFetcher(client, pacer=pacer).fetch(url, Path(data_home) / "raw" / obj.key)
    if fetched.etag != obj.etag:
        raise RuntimeError(
            f"{obj.key} changed between listing and download (ETag {obj.etag} listed, "
            f"{fetched.etag} fetched); rerun to take a fresh Snapshot"
        )
    load = load_judgments(fetched.path, snapshot_id=snapshot.snapshot_id, source_uri=url)
    manifest_path = snapshot.save(data_home, dedup=load.counts())
    return YearMetadata(year=year, snapshot=snapshot, load=load, manifest_path=manifest_path)
