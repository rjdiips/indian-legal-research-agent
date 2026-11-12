from pathlib import Path

import psycopg
import pytest

from legal_agent.db.migrate import migrate

pytestmark = pytest.mark.integration


def _write(d: Path, files: dict[str, str]) -> Path:
    for name, sql in files.items():
        (d / name).write_text(sql)
    return d


def test_applies_numbered_files_in_numeric_order_and_records_them(conn, tmp_path):
    d = _write(
        tmp_path,
        {
            "0010_add_column.sql": "ALTER TABLE t ADD COLUMN note text;",
            "0002_create.sql": "CREATE TABLE t (id int);",
            "README.md": "not a migration",
        },
    )

    applied = migrate(conn, d)

    assert applied == ["0002_create.sql", "0010_add_column.sql"]
    conn.execute("INSERT INTO t (id, note) VALUES (1, 'ok')")


def test_rerun_applies_nothing_and_new_files_apply_once(conn, tmp_path):
    d = _write(tmp_path, {"0001_create.sql": "CREATE TABLE t (id int);"})
    migrate(conn, d)

    assert migrate(conn, d) == []

    _write(d, {"0002_more.sql": "CREATE TABLE u (id int);"})
    assert migrate(conn, d) == ["0002_more.sql"]
    assert migrate(conn, d) == []


def test_a_failing_file_is_rolled_back_and_not_recorded(conn, tmp_path):
    d = _write(
        tmp_path,
        {
            "0001_ok.sql": "CREATE TABLE t (id int);",
            "0002_broken.sql": "CREATE TABLE half (id int); SELECT * FROM no_such_table;",
        },
    )

    with pytest.raises(psycopg.errors.UndefinedTable):
        migrate(conn, d)

    assert conn.execute("SELECT to_regclass('half')").fetchone() == (None,)
    _write(d, {"0002_broken.sql": "CREATE TABLE half (id int);"})
    assert migrate(conn, d) == ["0002_broken.sql"]


def test_opinions_migration_gives_each_cleaned_judgment_an_opinion_one(conn, tmp_path):
    repo_migrations = Path(__file__).parents[2] / "migrations"
    files = sorted(repo_migrations.glob("*.sql"))
    before = [f for f in files if f.name < "0006"]
    _write(tmp_path, {f.name: f.read_text() for f in before})
    migrate(conn, tmp_path)
    conn.execute("INSERT INTO snapshots VALUES ('s', now(), '{}')")
    for path in ("a", "b"):
        conn.execute(
            "INSERT INTO judgments (path, snapshot_id, source_uri, license, attribution)"
            " VALUES (%s, 's', 'u', 'l', 'x')",
            [path],
        )
    conn.execute("INSERT INTO paragraphs VALUES ('a', 1, 1, 5, 40), ('a', 2, 2, 41, 90)")

    _write(tmp_path, {"0006_opinions.sql": (repo_migrations / "0006_opinions.sql").read_text()})
    assert migrate(conn, tmp_path) == ["0006_opinions.sql"]

    # Opinion 1 covers the paragraphs; Judgment b has no paragraphs, so no Opinion until clean-text.
    assert conn.execute("SELECT path, number, author, char_start, char_end FROM opinions").fetchall() == [
        ("a", 1, None, 0, 90)
    ]
    rows = conn.execute("SELECT ordinal, opinion FROM paragraphs ORDER BY ordinal").fetchall()
    assert rows == [(1, 1), (2, 1)]


def test_repo_migrations_apply_cleanly(conn):
    repo_migrations = Path(__file__).parents[2] / "migrations"

    assert migrate(conn, repo_migrations)
    assert migrate(conn, repo_migrations) == []
