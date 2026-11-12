"""Write corpus records (Snapshots, Judgments, raw text results) to Postgres. Idempotent."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import astuple, fields

import psycopg
from psycopg.types.json import Jsonb

from indian_sc_judgments_mcp.corpus.extract import Extracted
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


_SAVE_RAW_TEXT = (
    "UPDATE judgments SET raw_text_sha256 = %s, text_quality = %s, page_count = %s, scanned_pages = %s,"
    " text_error = %s, text_extracted_at = now(), updated_at = now() WHERE path = %s"
)


def save_raw_text(conn: psycopg.Connection, extracted: Extracted) -> bool:
    """Record one Judgment's raw text hash and Text quality (or its error). False when no
    Judgment has that `path`."""
    e = extracted
    quality = e.text_quality.value if e.text_quality else None
    cur = conn.execute(_SAVE_RAW_TEXT, [e.sha256, quality, e.pages, e.scanned_pages, e.error, e.path])
    return cur.rowcount > 0
