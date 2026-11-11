"""Pipeline commands.

legal-agent migrate
legal-agent ingest-metadata --year 2020
"""

from __future__ import annotations

import argparse
import sys

import httpx
import psycopg

from indian_sc_judgments_mcp.config import data_home
from legal_agent.config import Settings
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate
from legal_agent.ingest import ingest_year_metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legal-agent")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply pending SQL migrations")
    ingest = commands.add_parser("ingest-metadata", help="ingest one year's judgment metadata")
    ingest.add_argument(
        "--year",
        type=int,
        required=True,
        help="Reporter year: the bucket partition metadata/parquet/year=N (not the Decision date)",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        if args.command == "migrate":
            applied = migrate(conn, MIGRATIONS_DIR)
            print(f"applied {len(applied)} migration(s)" + "".join(f"\n  {name}" for name in applied))
            return 0

        with httpx.Client() as client:
            report = ingest_year_metadata(
                conn, args.year, client=client, data_home=settings.sc_judgments_home or data_home()
            )
    print(f"year {report.year}  snapshot {report.snapshot_id}")
    print(f"manifest {report.manifest_path}")
    for name, value in report.counts.items():
        print(f"  {name:<24}{value}")
    for path in report.missing_dates:
        print(f"  missing decision_date: {path}", file=sys.stderr)
    for path, raw in report.bad_dates.items():
        print(f"  bad decision_date {raw!r}: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
