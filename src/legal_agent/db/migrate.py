"""A small migrate runner: plain numbered SQL files, no ORM (spec decision 6).

Files are named `NNNN_description.sql` and applied in numeric order. Each file
runs in its own transaction together with its row in `schema_migrations`, so a
failing file leaves no trace and is retried on the next run. Rerunning is safe:
applied files are skipped. An advisory lock keeps two runners from racing.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
from psycopg import sql

_NAME = re.compile(r"^(\d+)_[\w-]+\.sql$")
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
_LOCK_KEY = 4_004_001  # arbitrary, unique to this project's migrations


def migration_files(migrations_dir: Path) -> list[Path]:
    numbered: dict[int, Path] = {}
    for path in Path(migrations_dir).iterdir():
        match = _NAME.match(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number in numbered:
            raise ValueError(f"two migrations share number {number}: {numbered[number].name}, {path.name}")
        numbered[number] = path
    return [numbered[n] for n in sorted(numbered)]


def migrate(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    """Apply pending migrations. Returns the file names applied, in order."""
    files = migration_files(migrations_dir)
    applied_now: list[str] = []
    conn.execute("SELECT pg_advisory_lock(%s)", [_LOCK_KEY])
    try:
        with conn.transaction():
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " filename text PRIMARY KEY,"
                " applied_at timestamptz NOT NULL DEFAULT now())"
            )
        done = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
        for path in files:
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(sql.SQL(path.read_text()))  # type: ignore[arg-type]
                conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", [path.name])
            applied_now.append(path.name)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_KEY])
    return applied_now
