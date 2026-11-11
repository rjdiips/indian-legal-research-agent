"""Ingest one year's metadata into Postgres: migrate, fetch, save (issue 01).

The corpus logic lives in the storage-agnostic package; this module only persists it (ADR-0001).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.metadata import fetch_year_metadata
from legal_agent.db.corpus import save_snapshot, upsert_judgments
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate


@dataclass(frozen=True)
class IngestReport:
    year: int
    snapshot_id: str
    manifest_path: Path
    counts: dict[str, int]
    missing_dates: list[str]
    bad_dates: dict[str, str]
    upserted: int


def ingest_year_metadata(
    conn: psycopg.Connection,
    year: int,
    *,
    client: httpx.Client,
    data_home: Path,
    migrations_dir: Path = MIGRATIONS_DIR,
    pacer: Pacer | None = None,
) -> IngestReport:
    migrate(conn, migrations_dir)
    fetched = fetch_year_metadata(year, client=client, data_home=data_home, pacer=pacer)
    counts = fetched.load.counts()
    with conn.transaction():
        save_snapshot(conn, fetched.snapshot, counts)
        upserted = upsert_judgments(conn, fetched.load.judgments)
    return IngestReport(
        year=year,
        snapshot_id=fetched.snapshot.snapshot_id,
        manifest_path=fetched.manifest_path,
        counts=counts,
        missing_dates=fetched.load.missing_dates,
        bad_dates=fetched.load.bad_dates,
        upserted=upserted,
    )
