"""Extract raw text and Text quality for downloaded years and save them (issue 03).

For each Reporter year, the English tar listed in the Snapshot (the latest, unless named) and
already in the data home (from `legal-agent ingest`) is streamed once; each PDF's raw text goes
to `<data_home>/text/raw/<path>.txt` and its hash, Text quality, page counts and
`raw_snapshot_id` (or its error) to the Judgment's row. No OCR. Rerunning re-extracts and gives
the same hashes. The corpus logic lives in the storage-agnostic package;
this module only persists it (ADR-0001).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from indian_sc_judgments_mcp.corpus.extract import Extracted, extract_year
from legal_agent.db.corpus import save_raw_text, snapshot_manifest
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate

_BATCH = 200  # rows per transaction


@dataclass
class ExtractReport:
    snapshot_id: str
    years: tuple[int, ...]
    counts: dict[str, int]
    errors: dict[str, str] = field(default_factory=dict)  # path -> error
    without_judgment: list[str] = field(default_factory=list)  # PDFs whose path isn't a Judgment
    missing_from_tar: list[str] = field(default_factory=list)  # index names absent from the tar
    unindexed: list[str] = field(default_factory=list)  # tar entries not in the index
    cross_year_duplicates: list[str] = field(default_factory=list)  # paths in more than one year's tar


def extract_text(
    conn: psycopg.Connection,
    *,
    data_home: Path,
    years: Iterable[int],
    migrations_dir: Path = MIGRATIONS_DIR,
    snapshot_id: str | None = None,
    progress: Callable[[int, Extracted], None] | None = None,
) -> ExtractReport:
    """LookupError, before extracting anything, when a year's tar isn't in the Snapshot or the
    downloaded copy doesn't match it."""
    migrate(conn, migrations_dir)
    manifest = snapshot_manifest(conn, snapshot_id)
    years = tuple(sorted(set(years)))
    runs = [(year, extract_year(data_home, year, manifest)) for year in years]  # check every year first
    report = ExtractReport(snapshot_id=manifest["snapshot_id"], years=years, counts={})
    latest: dict[str, Extracted] = {}  # a path in two years' tars is saved twice; the last write wins
    for year, run in runs:
        batch: list[Extracted] = []
        for extracted in run.results:
            if extracted.path in latest:
                report.cross_year_duplicates.append(extracted.path)
            latest[extracted.path] = extracted
            batch.append(extracted)
            if progress:
                progress(year, extracted)
            if len(batch) >= _BATCH:
                _save(conn, batch, report)
        _save(conn, batch, report)
        report.missing_from_tar += run.missing_from_tar
        report.unindexed += run.unindexed
    report.errors = {e.path: e.error for e in latest.values() if e.error}
    report.without_judgment = list(dict.fromkeys(report.without_judgment))
    tally = Counter(str(e.text_quality) for e in latest.values() if not e.error)
    report.counts = {
        "extracted": len(latest) - len(report.errors),
        "errors": len(report.errors),
        "ocr": tally["ocr"],
        "born_digital": tally["born_digital"],
        "without_judgment": len(report.without_judgment),
        "missing_from_tar": len(report.missing_from_tar),
        "unindexed": len(report.unindexed),
        "cross_year_duplicates": len(report.cross_year_duplicates),
    }
    return report


def _save(conn: psycopg.Connection, batch: list[Extracted], report: ExtractReport) -> None:
    with conn.transaction():
        for extracted in batch:
            if not save_raw_text(conn, extracted, report.snapshot_id):
                report.without_judgment.append(extracted.path)
    batch.clear()
