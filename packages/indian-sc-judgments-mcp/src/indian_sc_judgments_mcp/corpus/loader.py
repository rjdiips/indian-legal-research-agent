"""Deduplicating metadata loader (Day 1).

Reads a bucket metadata parquet into plain `Judgment` records. Storage-agnostic
(ADR-0001): callers decide where the records go.

- One Judgment per `path`. When a `path` repeats, the row with the latest
  `scraped_at` wins (ties: the first row read).
- The Decision date comes only from `decision_date`. The parquet's `year`
  column is the Reporter year and is kept as `reporter_year`, never used for dates.
- Missing or unparseable decision dates are kept as `None` and reported.

DuckDB is used only as a Parquet reader: an in-memory connection, one SELECT,
nothing written. It is not a store; Postgres is the only store (ADR-0001, PRD §7).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

LICENSE = "CC-BY-4.0"
ATTRIBUTION = (
    "Indian Supreme Court Judgments, AWS Open Data Registry "
    "(s3://indian-supreme-court-judgments), licensed CC-BY-4.0"
)

_TEXT_COLUMNS = (
    "title", "petitioner", "respondent", "description", "judge", "author_judge", "citation",
    "case_id", "cnr", "disposal_nature", "court", "available_languages", "nc_display", "scraped_at",
)  # fmt: skip
_DATE_FORMATS = ("%d-%m-%Y", "%Y-%m-%d")


@dataclass(frozen=True)
class Judgment:
    path: str
    decision_date: dt.date | None
    reporter_year: int | None
    title: str | None
    petitioner: str | None
    respondent: str | None
    description: str | None
    judge: str | None
    author_judge: str | None
    citation: str | None
    case_id: str | None
    cnr: str | None
    disposal_nature: str | None
    court: str | None
    available_languages: str | None
    nc_display: str | None
    scraped_at: str | None
    snapshot_id: str
    source_uri: str
    license: str = LICENSE
    attribution: str = ATTRIBUTION


@dataclass
class LoadResult:
    judgments: list[Judgment]
    rows_read: int
    duplicates: int
    rows_without_path: int = 0
    missing_dates: list[str] = field(default_factory=list)
    bad_dates: dict[str, str] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "rows_read": self.rows_read,
            "judgments": len(self.judgments),
            "duplicates": self.duplicates,
            "rows_without_path": self.rows_without_path,
            "missing_decision_dates": len(self.missing_dates),
            "bad_decision_dates": len(self.bad_dates),
        }


def parse_decision_date(raw: str | None) -> dt.date | None:
    """Parse a bucket `decision_date` (DD-MM-YYYY). Returns None if it can't be read."""
    if raw is None or not raw.strip():
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def load_judgments_from(sources: Sequence[tuple[Path, str]], *, snapshot_id: str) -> LoadResult:
    """Load several metadata parquets, given as `(file, source_uri)`, deduplicating on `path`
    across all of them. Rows are read in the order given, which settles `scraped_at` ties."""
    columns = ", ".join(("path", "decision_date", "year", *_TEXT_COLUMNS))
    rows: list[dict] = []
    con = duckdb.connect()
    try:
        for parquet, source_uri in sources:
            cursor = con.execute(f"SELECT {columns} FROM read_parquet(?)", [str(parquet)])
            names = [d[0] for d in cursor.description]
            for r in cursor.fetchall():
                rows.append({**dict(zip(names, r, strict=True)), "_source_uri": source_uri})
    finally:
        con.close()

    latest: dict[str, dict] = {}
    rows_without_path = 0
    for row in rows:
        path = row["path"]
        if not path:
            rows_without_path += 1
            continue
        kept = latest.get(path)
        if kept is None or (row["scraped_at"] or "") > (kept["scraped_at"] or ""):
            latest[path] = row

    result = LoadResult(
        judgments=[],
        rows_read=len(rows),
        duplicates=len(rows) - rows_without_path - len(latest),
        rows_without_path=rows_without_path,
    )
    for path, row in latest.items():
        raw_date = row["decision_date"]
        decision_date = parse_decision_date(raw_date)
        if decision_date is None:
            if raw_date is None or not raw_date.strip():
                result.missing_dates.append(path)
            else:
                result.bad_dates[path] = raw_date
        result.judgments.append(
            Judgment(
                path=path,
                decision_date=decision_date,
                reporter_year=row["year"],
                snapshot_id=snapshot_id,
                source_uri=row["_source_uri"],
                **{c: row[c] for c in _TEXT_COLUMNS},
            )
        )
    return result
