"""The whole corpus download: all metadata, plus English tars for a range of years (Day 1–2).

One Snapshot covers every object used: each year's metadata parquet, and the English
`english.tar` with its `english.index.json` for each chosen Reporter year. Downloads are
checked against that manifest, resumable, and skipped when the local copy already matches,
so a rerun downloads nothing and a wider year range (the older-years backfill) fetches only
the new tars.

Files land under `<data_home>/raw/<bucket key>`, the fetch log at `<data_home>/fetch_log.jsonl`
and the manifest at `<data_home>/snapshots/<snapshot_id>.json`.

Storage-agnostic (ADR-0001): returns records and paths; the caller persists the Judgments.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

from indian_sc_judgments_mcp.corpus.download import (
    FetchResult,
    Pacer,
    PoliteFetcher,
    S3Object,
    list_objects,
    object_url,
)
from indian_sc_judgments_mcp.corpus.loader import LoadResult, load_judgments_from
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot

METADATA_PREFIX = "metadata/parquet/"
TAR_PREFIX = "data/tar/"
DEFAULT_TAR_YEARS = range(2015, 2027)


def english_tar_keys(year: int) -> tuple[str, str]:
    """The index and tar keys for one Reporter year's English PDFs."""
    base = f"{TAR_PREFIX}year={year}/english/"
    return base + "english.index.json", base + "english.tar"


def tar_year(key: str) -> int | None:
    """The Reporter year of a key under `data/tar/year=<YEAR>/`; None for any other key."""
    m = re.match(rf"{TAR_PREFIX}year=(\d+)/", key)
    return int(m[1]) if m else None


def local_path(data_home: Path, key: str) -> Path:
    """Where a bucket object is kept on disk."""
    return Path(data_home) / "raw" / key


@dataclass(frozen=True)
class CorpusFetch:
    snapshot: Snapshot
    load: LoadResult
    manifest_path: Path
    tar_years: tuple[int, ...]
    fetches: list[FetchResult]


def fetch_corpus(
    *,
    client: httpx.Client,
    data_home: Path,
    tar_years: Iterable[int] = DEFAULT_TAR_YEARS,
    pacer: Pacer | None = None,
) -> CorpusFetch:
    """`tar_years` are Reporter years (bucket partitions), not Decision dates. Empty: metadata only."""
    pacer = pacer or Pacer()
    data_home = Path(data_home)
    years = tuple(sorted(set(tar_years)))

    metadata = [o for o in list_objects(client, METADATA_PREFIX, pacer=pacer) if o.key.endswith(".parquet")]
    if not metadata:
        raise LookupError(f"no metadata parquet under {METADATA_PREFIX}")
    tars: list[S3Object] = []
    if years:
        listed = {o.key: o for o in list_objects(client, TAR_PREFIX, pacer=pacer)}
        for year in years:
            for key in english_tar_keys(year):
                if key not in listed:
                    raise LookupError(f"no {key} in the bucket")
                tars.append(listed[key])

    snapshot = Snapshot.from_listing([*metadata, *tars])
    fetcher = PoliteFetcher(client, pacer=pacer, log=data_home / "fetch_log.jsonl")
    # Metadata first (small, and enough for an ingest), then each year's index and tar.
    fetches = [
        fetcher.fetch(object_url(o.key), local_path(data_home, o.key), expected=o)
        for o in [*sorted(metadata, key=lambda o: o.key), *tars]
    ]
    load = load_judgments_from(
        [(local_path(data_home, o.key), object_url(o.key)) for o in sorted(metadata, key=lambda o: o.key)],
        snapshot_id=snapshot.snapshot_id,
    )
    manifest_path = snapshot.save(data_home, dedup=load.counts())
    return CorpusFetch(snapshot, load, manifest_path, years, fetches)
