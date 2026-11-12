"""Ingest the corpus into Postgres: migrate, fetch, save (issues 01–02).

All years of metadata, plus English tars for a range of Reporter years. The corpus logic
lives in the storage-agnostic package; this module only persists it (ADR-0001).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.fetch import DEFAULT_TAR_YEARS, fetch_corpus
from legal_agent.db.corpus import save_snapshot, upsert_judgments
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate


@dataclass(frozen=True)
class IngestReport:
    snapshot_id: str
    manifest_path: Path
    tar_years: tuple[int, ...]
    counts: dict[str, int]
    missing_dates: list[str]
    bad_dates: dict[str, str]
    upserted: int
    downloaded_bytes: int  # 0 on a rerun with unchanged ETags
    objects: int  # bucket objects in the Snapshot


def ingest_corpus(
    conn: psycopg.Connection,
    *,
    client: httpx.Client,
    data_home: Path,
    tar_years: Iterable[int] = DEFAULT_TAR_YEARS,
    migrations_dir: Path = MIGRATIONS_DIR,
    pacer: Pacer | None = None,
) -> IngestReport:
    migrate(conn, migrations_dir)
    fetched = fetch_corpus(client=client, data_home=data_home, tar_years=tar_years, pacer=pacer)
    counts = fetched.load.counts()
    with conn.transaction():
        save_snapshot(conn, fetched.snapshot, counts)
        upserted = upsert_judgments(conn, fetched.load.judgments)
    return IngestReport(
        snapshot_id=fetched.snapshot.snapshot_id,
        manifest_path=fetched.manifest_path,
        tar_years=fetched.tar_years,
        counts=counts,
        missing_dates=fetched.load.missing_dates,
        bad_dates=fetched.load.bad_dates,
        upserted=upserted,
        downloaded_bytes=sum(f.bytes_received for f in fetched.fetches),
        objects=len(fetched.snapshot.objects),
    )
