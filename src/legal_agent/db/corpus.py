"""Write corpus records (Snapshots, Judgments, raw text, cleaned text results) to Postgres. Idempotent."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import astuple, fields
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from indian_sc_judgments_mcp.corpus.extract import Extracted
from indian_sc_judgments_mcp.corpus.loader import Judgment
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot
from indian_sc_judgments_mcp.corpus.structure import Structured, clean_text_path

_COLUMNS = [f.name for f in fields(Judgment)]
_UPSERT_JUDGMENT = (
    f"INSERT INTO judgments ({', '.join(_COLUMNS)}) VALUES ({', '.join(['%s'] * len(_COLUMNS))}) "
    "ON CONFLICT (path) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "path")
    + ", updated_at = now()"
)


def save_snapshot(conn: psycopg.Connection, snapshot: Snapshot, dedup: Mapping[str, object]) -> None:
    conn.execute(
        # A listing seen before keeps its first fetch time, so the latest Snapshot is the newest
        # bucket state, not whichever listing was ingested last.
        "INSERT INTO snapshots (snapshot_id, fetched_at, manifest) VALUES (%s, %s, %s) "
        "ON CONFLICT (snapshot_id) DO NOTHING",
        [snapshot.snapshot_id, snapshot.fetched_at, Jsonb(snapshot.manifest(dedup))],
    )


def snapshot_manifest(conn: psycopg.Connection, snapshot_id: str | None = None) -> dict:
    """The manifest of Snapshot `snapshot_id`, or of the latest one (by first fetch time)."""
    row = conn.execute(
        "SELECT manifest FROM snapshots WHERE snapshot_id = %s"
        if snapshot_id
        else "SELECT manifest FROM snapshots ORDER BY fetched_at DESC LIMIT 1",
        [snapshot_id] if snapshot_id else [],
    ).fetchone()
    if row is None:
        raise LookupError(f"no Snapshot {snapshot_id}" if snapshot_id else "no Snapshot yet; run ingest")
    return row[0]


def upsert_judgments(conn: psycopg.Connection, judgments: Iterable[Judgment]) -> int:
    rows = [astuple(j) for j in judgments]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_JUDGMENT, rows)  # type: ignore[arg-type]
    return len(rows)


_SAVE_RAW_TEXT = (
    "UPDATE judgments SET raw_text_sha256 = %s, text_quality = %s, page_count = %s, scanned_pages = %s,"
    " text_error = %s, raw_snapshot_id = %s, text_extracted_at = now(), updated_at = now() WHERE path = %s"
)


def save_raw_text(conn: psycopg.Connection, extracted: Extracted, snapshot_id: str) -> bool:
    """Record one Judgment's raw text hash and Text quality (or its error), extracted from Snapshot
    `snapshot_id`'s tar. False when no Judgment has that `path`."""
    e = extracted
    quality = e.text_quality.value if e.text_quality else None
    cur = conn.execute(
        _SAVE_RAW_TEXT, [e.sha256, quality, e.pages, e.scanned_pages, e.error, snapshot_id, e.path]
    )
    return cur.rowcount > 0


_SAVE_STRUCTURE = (
    "UPDATE judgments SET clean_text_sha256 = %s, bench_size = %s, bench_evidence = %s,"
    " clean_error = %s, clean_snapshot_id = %s, cleaned_at = now(), updated_at = now() WHERE path = %s"
)
_INSERT_OPINION = (
    "INSERT INTO opinions (path, number, author, char_start, char_end) VALUES (%s, %s, %s, %s, %s)"
)
_INSERT_PARAGRAPH = (
    "INSERT INTO paragraphs (path, ordinal, number, opinion, char_start, char_end)"
    " VALUES (%s, %s, %s, %s, %s, %s)"
)


def save_structure(conn: psycopg.Connection, structured: Structured, snapshot_id: str | None) -> bool:
    """Record one Judgment's cleaned text hash, Bench size, Opinions and paragraph offsets (or its
    cleaning error), derived from raw text of Snapshot `snapshot_id`, replacing any from an earlier
    run. False when no Judgment has that `path`."""
    s = structured
    bench = s.bench
    cur = conn.execute(
        _SAVE_STRUCTURE,
        [
            s.clean_sha256,
            bench.size if bench else None,
            bench.evidence if bench else None,
            s.error,
            snapshot_id,
            s.path,
        ],
    )
    if cur.rowcount == 0:
        return False
    conn.execute("DELETE FROM opinions WHERE path = %s", [s.path])  # cascades to paragraphs
    with conn.cursor() as c:
        c.executemany(_INSERT_OPINION, [(s.path, o.number, o.author, o.start, o.end) for o in s.opinions])
        c.executemany(
            _INSERT_PARAGRAPH,
            [(s.path, p.ordinal, p.number, p.opinion, p.start, p.end) for p in s.paragraphs],
        )
    return True


def pinpoint_paragraph(
    conn: psycopg.Connection, data_home: Path, path: str, number: int, opinion: int = 1
) -> str | None:
    """The text of paragraph `number` of Opinion `opinion` (ADR-0003): its slice of the cleaned-text
    file. None when the Judgment has no such paragraph."""
    row = conn.execute(
        "SELECT char_start, char_end FROM paragraphs WHERE path = %s AND opinion = %s AND number = %s",
        [path, opinion, number],
    ).fetchone()
    if row is None:
        return None
    return clean_text_path(data_home, path).read_text(encoding="utf-8")[row[0] : row[1]]
