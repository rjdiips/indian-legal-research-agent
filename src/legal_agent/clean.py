"""Clean extracted raw text, save Pinpoint paragraphs, Opinions and Bench size (issue 04).

Every Judgment with raw text (`raw_text_sha256` set by `legal-agent extract-text`) is cleaned:
the cleaned text and its offset map go to `<data_home>/text/clean/`, and its hash, paragraph
offsets, Bench size and `clean_snapshot_id` (the raw text's Snapshot), or its error, to
Postgres. A raw file that no longer matches its recorded hash is an error on that Judgment.
Rerunning re-cleans everything and gives the same hashes. The corpus logic lives in the
storage-agnostic package; this module only persists it (ADR-0001).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from indian_sc_judgments_mcp.corpus.structure import Structured, structure_judgment
from legal_agent.db.corpus import save_structure
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate

_BATCH = 200  # Judgments per transaction


@dataclass
class CleanReport:
    counts: dict[str, int]
    errors: dict[str, str] = field(default_factory=dict)  # path -> error


def clean_texts(
    conn: psycopg.Connection,
    *,
    data_home: Path,
    migrations_dir: Path = MIGRATIONS_DIR,
    progress: Callable[[Structured], None] | None = None,
) -> CleanReport:
    migrate(conn, migrations_dir)
    todo = conn.execute(
        "SELECT path, raw_text_sha256, raw_snapshot_id FROM judgments"
        " WHERE raw_text_sha256 IS NOT NULL ORDER BY path"
    ).fetchall()
    report = CleanReport(counts={})
    tally: Counter[str] = Counter()
    batch: list[tuple[Structured, str | None]] = []
    for path, raw_sha256, snapshot_id in todo:
        result = structure_judgment(data_home, path, raw_sha256=raw_sha256)
        if result.error:
            tally["errors"] += 1
            report.errors[path] = result.error
        else:
            tally["cleaned"] += 1
            numbered = any(p.number is not None for p in result.paragraphs)
            tally["numbered" if numbered else "unnumbered"] += 1
            tally["bench_known" if result.bench and result.bench.size else "bench_unknown"] += 1
            tally["paragraphs"] += len(result.paragraphs)
            tally["multi_opinion"] += len(result.opinions) > 1
        batch.append((result, snapshot_id))
        if progress:
            progress(result)
        if len(batch) >= _BATCH:
            _save(conn, batch)
    _save(conn, batch)
    keys = ["cleaned", "errors", "numbered", "unnumbered", "bench_known", "bench_unknown", "paragraphs",
            "multi_opinion"]  # fmt: skip
    report.counts = {k: tally[k] for k in keys}
    return report


def _save(conn: psycopg.Connection, batch: list[tuple[Structured, str | None]]) -> None:
    with conn.transaction():
        for result, snapshot_id in batch:
            save_structure(conn, result, snapshot_id)
    batch.clear()
