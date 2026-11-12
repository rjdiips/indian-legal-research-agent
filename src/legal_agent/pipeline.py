"""The whole corpus pipeline in one call, and its run report (issue 05).

`run_corpus` chains ingest, raw text extraction and cleaning, then `write_report` writes
`<reports_dir>/corpus-<snapshot_id[:12]>.md` from Postgres. Judgment counts are of the Judgments
in that Snapshot; raw text, Text quality, cleaned text, paragraphs and Bench size only where they
were derived under it (`raw_snapshot_id`, `clean_snapshot_id`). The report has no timestamps, so a
rerun over the same Snapshot gives the same file.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import httpx
import psycopg

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.fetch import DEFAULT_TAR_YEARS, tar_year
from legal_agent.clean import clean_texts
from legal_agent.db.corpus import snapshot_manifest
from legal_agent.extract import extract_text
from legal_agent.ingest import ingest_corpus

REPORTS_DIR = Path(__file__).parents[2] / "reports"
_LISTED = 50  # errors listed by path before truncating


def run_corpus(
    conn: psycopg.Connection,
    *,
    client: httpx.Client,
    data_home: Path,
    tar_years: Iterable[int] = DEFAULT_TAR_YEARS,
    reports_dir: Path = REPORTS_DIR,
    pacer: Pacer | None = None,
) -> Path:
    ingested = ingest_corpus(conn, client=client, data_home=data_home, tar_years=tar_years, pacer=pacer)
    extract_text(conn, data_home=data_home, years=ingested.tar_years, snapshot_id=ingested.snapshot_id)
    clean_texts(conn, data_home=data_home)
    return write_report(conn, reports_dir, ingested.snapshot_id)


def write_report(
    conn: psycopg.Connection, reports_dir: Path = REPORTS_DIR, snapshot_id: str | None = None
) -> Path:
    """Report on Snapshot `snapshot_id`, or the latest one (by first fetch time)."""
    manifest = snapshot_manifest(conn, snapshot_id)
    snapshot_id = manifest["snapshot_id"]
    q = _Query(conn, snapshot_id)
    tars = sorted(tar_year(o["key"]) for o in manifest["objects"] if o["key"].endswith(".tar"))
    tar_span = f"{tars[0]}–{tars[-1]}" if tars else "none"
    dedup = manifest.get("dedup", {})

    total, in_tars, attempted, extracted, text_errors, cleaned, clean_errors = q.one(
        "SELECT count(*) FILTER (WHERE snapshot_id = %(s)s),"
        " count(*) FILTER (WHERE snapshot_id = %(s)s AND reporter_year = ANY(%(tars)s)),"
        " count(*) FILTER (WHERE raw_snapshot_id = %(s)s),"
        " count(raw_text_sha256) FILTER (WHERE raw_snapshot_id = %(s)s),"
        " count(text_error) FILTER (WHERE raw_snapshot_id = %(s)s),"
        " count(clean_text_sha256) FILTER (WHERE clean_snapshot_id = %(s)s),"
        " count(clean_error) FILTER (WHERE clean_snapshot_id = %(s)s)"
        " FROM judgments",
        tars=tars,
    )
    lines = [
        f"# Corpus run: Snapshot `{snapshot_id}`",
        "",
        f"English tars for Reporter years {tar_span}; metadata for every year. Decades are by Decision date.",
        "",
        "## Judgment counts",
        "",
        "| | Judgments |",
        "|---|---|",
        f"| Judgments | {total} |",
        f"| Duplicate metadata rows dropped | {dedup.get('duplicates', 0)} |",
        f"| In those Reporter years | {in_tars} |",
        f"| English PDF found (extraction attempted) | {attempted} |",
        f"| Raw text extracted | {extracted} |",
        f"| Extraction errors | {text_errors} |",
        f"| Cleaned | {cleaned} |",
        f"| Cleaning errors | {clean_errors} |",
        "",
        "## Text quality",
        "",
        "Share of Judgments whose English PDF was found.",
        "",
        "| Text quality | Judgments | Share |",
        "|---|---|---|",
        *(
            f"| {quality} | {n} | {_pct(n, attempted)} |"
            for quality, n in q.all(
                "SELECT coalesce(text_quality, 'extraction error'), count(*) FROM judgments"
                " WHERE raw_snapshot_id = %(s)s GROUP BY text_quality ORDER BY text_quality DESC NULLS LAST"
            )
        ),
        "",
        "## Bench size parse rate and paragraph coverage, by decade",
        "",
        "Over cleaned Judgments. Paragraph coverage = share with numbered (Pinpoint) paragraphs.",
        "",
        "| Decade | Cleaned | Bench size known | Numbered paragraphs | ocr share |",
        "|---|---|---|---|---|",
        *(
            f"| {decade} | {n} | {_pct(bench, n)} | {_pct(numbered, n)} | {_pct(ocr, n)} |"
            for decade, n, bench, numbered, ocr in q.all(
                "SELECT coalesce((extract(decade FROM decision_date) * 10)::int || 's', 'no date'), count(*),"
                " count(bench_size),"
                " count(*) FILTER (WHERE EXISTS"
                "   (SELECT 1 FROM paragraphs p WHERE p.path = j.path AND p.number IS NOT NULL)),"
                " count(*) FILTER (WHERE text_quality = 'ocr')"
                " FROM judgments j WHERE clean_snapshot_id = %(s)s AND clean_text_sha256 IS NOT NULL"
                " GROUP BY 1 ORDER BY 1"
            )
        ),
        "",
        "| Bench size | Judgments |",
        "|---|---|",
        *(
            f"| {size or 'unknown'} | {n} |"
            for size, n in q.all(
                "SELECT bench_size, count(*) FROM judgments"
                " WHERE clean_snapshot_id = %(s)s AND clean_text_sha256 IS NOT NULL"
                " GROUP BY 1 ORDER BY 1 NULLS LAST"
            )
        ),
        "",
        "## Extraction errors",
        "",
        *_errors(q, "text_error", "raw_snapshot_id"),
        "",
        "## Cleaning errors",
        "",
        *_errors(q, "clean_error", "clean_snapshot_id"),
        "",
    ]
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"corpus-{snapshot_id[:12]}.md"
    out.write_text("\n".join(lines))
    return out


class _Query:
    """Runs SQL with the Snapshot's id bound to `%(s)s`."""

    def __init__(self, conn: psycopg.Connection, snapshot_id: str) -> None:
        self.conn, self.snapshot_id = conn, snapshot_id

    def all(self, sql: str, **params: object) -> list[tuple]:
        return self.conn.execute(sql, {**params, "s": self.snapshot_id}).fetchall()

    def one(self, sql: str, **params: object) -> tuple:
        return self.all(sql, **params)[0]


def _errors(q: _Query, column: str, snapshot_column: str) -> list[str]:
    rows = q.all(
        f"SELECT path, {column} FROM judgments WHERE {snapshot_column} = %(s)s AND {column} IS NOT NULL"
        " ORDER BY path"
    )
    if not rows:
        return ["None."]
    listed = [f"- `{path}`: {error}" for path, error in rows[:_LISTED]]
    return listed + ([f"- … and {len(rows) - _LISTED} more"] if len(rows) > _LISTED else [])


def _pct(n: int, of: int) -> str:
    return f"{100 * n / of:.1f}%" if of else "–"
