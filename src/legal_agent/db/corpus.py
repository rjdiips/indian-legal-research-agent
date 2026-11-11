"""Write corpus records (Snapshots, Judgments) to Postgres. Upserts are idempotent."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import astuple, fields

import psycopg
from psycopg.types.json import Jsonb

from indian_sc_judgments_mcp.corpus.loader import Judgment
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot

_COLUMNS = [f.name for f in fields(Judgment)]
_UPSERT_JUDGMENT = (
    f"INSERT INTO judgments ({', '.join(_COLUMNS)}) VALUES ({', '.join(['%s'] * len(_COLUMNS))}) "
    "ON CONFLICT (path) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "path")
    + ", updated_at = now()"
)


def save_snapshot(conn: psycopg.Connection, snapshot: Snapshot, dedup: Mapping[str, object]) -> None:
    conn.execute(
        "INSERT INTO snapshots (snapshot_id, fetched_at, manifest) VALUES (%s, %s, %s) "
        "ON CONFLICT (snapshot_id) DO UPDATE"
        " SET fetched_at = EXCLUDED.fetched_at, manifest = EXCLUDED.manifest",
        [snapshot.snapshot_id, snapshot.fetched_at, Jsonb(snapshot.manifest(dedup))],
    )


def upsert_judgments(conn: psycopg.Connection, judgments: Iterable[Judgment]) -> int:
    rows = [astuple(j) for j in judgments]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_JUDGMENT, rows)  # type: ignore[arg-type]
    return len(rows)
