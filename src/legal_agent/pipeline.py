"""The whole corpus pipeline in one call, and its run report (issue 05).

`run_corpus` chains ingest, raw text extraction and cleaning, then `write_report` writes
`<reports_dir>/corpus-<snapshot_id[:12]>.md` from Postgres. The report has no timestamps, so a
rerun over the same Snapshot gives the same file.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import httpx
import psycopg

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.fetch import DEFAULT_TAR_YEARS
from legal_agent.clean import clean_texts
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
    extract_text(conn, data_home=data_home, years=ingested.tar_years)
    clean_texts(conn, data_home=data_home)
    return write_report(conn, reports_dir)


def write_report(conn: psycopg.Connection, reports_dir: Path = REPORTS_DIR) -> Path:
    """Report on the latest Snapshot's Judgments."""
    snapshot_id, manifest = conn.execute(
        "SELECT snapshot_id, manifest FROM snapshots ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    q = _Query(conn, snapshot_id)
    tars = sorted(
        int(o["key"].split("year=")[1].split("/")[0])
        for o in manifest["objects"]
        if o["key"].endswith(".tar")
    )
    tar_span = f"{tars[0]}–{tars[-1]}" if tars else "none"
    dedup = manifest.get("dedup", {})

    total, in_tars, attempted, extracted, text_errors, cleaned, clean_errors = q.one(
        "SELECT count(*), count(*) FILTER (WHERE reporter_year = ANY(%s)), count(text_extracted_at),"
        " count(raw_text_sha256), count(text_error), count(clean_text_sha256), count(clean_error)"
        " FROM judgments WHERE snapshot_id = %s",
        tars,
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
        "| Text quality | Judgments | Share |",
        "|---|---|---|",
        *(
            f"| {quality} | {n} | {_pct(n, extracted)} |"
            for quality, n in q.all(
                "SELECT text_quality, count(*) FROM judgments"
                " WHERE snapshot_id = %s AND text_quality IS NOT NULL"
                " GROUP BY 1 ORDER BY 1 DESC"
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
                " FROM judgments j WHERE snapshot_id = %s AND clean_text_sha256 IS NOT NULL"
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
                " WHERE snapshot_id = %s AND clean_text_sha256 IS NOT NULL"
                " GROUP BY 1 ORDER BY 1 NULLS LAST"
            )
        ),
        "",
        "## Extraction errors",
        "",
        *_errors(q, "text_error"),
        "",
        "## Cleaning errors",
        "",
        *_errors(q, "clean_error"),
        "",
    ]
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"corpus-{snapshot_id[:12]}.md"
    out.write_text("\n".join(lines))
    return out


class _Query:
    def __init__(self, conn: psycopg.Connection, snapshot_id: str) -> None:
        self.conn, self.snapshot_id = conn, snapshot_id

    def all(self, sql: str, *params: object) -> list[tuple]:
        return self.conn.execute(sql, [*params, self.snapshot_id]).fetchall()

    def one(self, sql: str, *params: object) -> tuple:
        return self.all(sql, *params)[0]


def _errors(q: _Query, column: str) -> list[str]:
    rows = q.all(
        f"SELECT path, {column} FROM judgments WHERE snapshot_id = %s AND {column} IS NOT NULL ORDER BY path"
    )
    if not rows:
        return ["None."]
    listed = [f"- `{path}`: {error}" for path, error in rows[:_LISTED]]
    return listed + ([f"- … and {len(rows) - _LISTED} more"] if len(rows) > _LISTED else [])


def _pct(n: int, of: int) -> str:
    return f"{100 * n / of:.1f}%" if of else "–"
