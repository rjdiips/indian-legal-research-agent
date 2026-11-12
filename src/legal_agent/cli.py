"""Pipeline commands.

legal-agent migrate
legal-agent ingest                       # all metadata + English tars 2015-2026
legal-agent ingest --tar-years none      # all metadata only
legal-agent ingest --tar-years 1950-2026 # backfill older years (only new tars are fetched)
"""

from __future__ import annotations

import argparse
import re
import sys

import httpx
import psycopg

from indian_sc_judgments_mcp.config import data_home
from indian_sc_judgments_mcp.corpus.fetch import DEFAULT_TAR_YEARS
from legal_agent.config import Settings
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate
from legal_agent.ingest import ingest_corpus

_DEFAULT_TAR_YEARS = f"{DEFAULT_TAR_YEARS.start}-{DEFAULT_TAR_YEARS.stop - 1}"


def tar_years(value: str) -> tuple[int, ...]:
    """`FROM-TO` (inclusive), a single `YEAR`, or `none`."""
    if value.strip().lower() == "none":
        return ()
    m = re.fullmatch(r"\s*(\d{4})\s*(?:-\s*(\d{4})\s*)?", value)
    if not m:
        raise argparse.ArgumentTypeError(f"expected FROM-TO, YEAR or none, got {value!r}")
    start, end = int(m[1]), int(m[2] or m[1])
    if end < start:
        raise argparse.ArgumentTypeError(f"range runs backwards: {value!r}")
    return tuple(range(start, end + 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legal-agent")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply pending SQL migrations")
    ingest = commands.add_parser(
        "ingest", help="ingest all judgment metadata and download English tars (resumable, rerun-safe)"
    )
    ingest.add_argument(
        "--tar-years",
        type=tar_years,
        default=tar_years(_DEFAULT_TAR_YEARS),
        metavar="FROM-TO|YEAR|none",
        help=f"Reporter years (bucket partitions, not Decision dates) whose English tar to fetch "
        f"(default {_DEFAULT_TAR_YEARS})",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        if args.command == "migrate":
            applied = migrate(conn, MIGRATIONS_DIR)
            print(f"applied {len(applied)} migration(s)" + "".join(f"\n  {name}" for name in applied))
            return 0

        with httpx.Client() as client:
            report = ingest_corpus(
                conn,
                client=client,
                data_home=settings.sc_judgments_home or data_home(),
                tar_years=args.tar_years,
            )
    years = f"{report.tar_years[0]}-{report.tar_years[-1]}" if report.tar_years else "none"
    print(f"snapshot {report.snapshot_id}  ({report.objects} objects, English tars: {years})")
    print(f"manifest {report.manifest_path}")
    print(f"  {'downloaded_bytes':<24}{report.downloaded_bytes}")
    for name, value in report.counts.items():
        print(f"  {name:<24}{value}")
    for path in report.missing_dates:
        print(f"  missing decision_date: {path}", file=sys.stderr)
    for path, raw in report.bad_dates.items():
        print(f"  bad decision_date {raw!r}: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
