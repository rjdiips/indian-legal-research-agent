# Corpus foundation (PRD-004 Days 1–2)

Settled in a grilling session on 2026-11-11. See [GLOSSARY.md](../../GLOSSARY.md), [ADR-0001](../../docs/adr/0001-postgres-in-docker-single-store.md) and [ADR-0002](../../docs/adr/0002-own-httpx-downloader-not-bharat-courts.md).

## Goal

A reproducible, deduplicated local corpus of English Supreme Court Judgments: each one with metadata, cleaned text, Pinpoint paragraphs, Text quality and Bench size, tied to the Snapshot it came from.

## Decisions

| # | Decision |
|---|---|
| 1 | "Repo" from Day 1 is done (scaffold commit). Days 1–2 are corpus work only. |
| 2 | Corpus code lives in `packages/indian-sc-judgments-mcp/.../corpus/` and is storage-agnostic. `legal_agent` imports it and persists to Postgres. |
| 3 | Downloader: own `httpx` client on the anonymous S3 HTTP endpoint (`https://indian-supreme-court-judgments.s3.amazonaws.com/`). Polite pacing, conditional GET, resume. Ported from `project-prds/data-gates/scripts/` (`s3_list.py`, `polite_fetch.py`, `01_download_metadata.py`). Not bharat-courts. |
| 4 | Snapshot = JSON manifest (fetch time; every used key with size and ETag; dedup counts). `snapshot_id` = hash of the manifest content. Every derived artefact records its `snapshot_id`. |
| 5 | Scope: all metadata parquet; English tars for 2015–2026 first; older years backfilled later, resumable. |
| 6 | Store: Postgres (docker-compose, :5440). Plain numbered SQL in `migrations/` plus a small `legal-agent migrate` runner. No Alembic or ORM. Single store for the whole app (ADR-0001). |
| 7 | Text on disk under `DATA_DIR` (raw and clean, one file each per Judgment). Postgres holds metadata, paragraph offsets and text hashes. |
| 8 | Deduplicate on `path`. All date logic uses `decision_date`, never the bucket's `year` (Reporter year). |
| 9 | Text comes from the embedded PDF text layer (PyMuPDF). No OCR. |
| 10 | `text_quality`: structural check. `ocr` if pages are full-page images under an invisible (render mode 3) text layer; otherwise `born_digital`. No score. A full-page image with no text layer at all also counts as a scanned page (e.g. page 4 of `2017_9_766_790`, a corpus PDF), as in `raw_text._is_scanned`. |
| 11 | Cleaning (reversible, with an offset map to raw text): page headers and footers, margin letters, hyphenation and line-wrap breaks, the Judgment's own citation line. Headnote and section splitting are deferred until after Day 3. |
| 12 | Paragraphs: `(number, text, char_start, char_end)` over cleaned text, from numbered markers at line start. With no markers, one unnumbered block. |
| 13 | `bench_size` from the coram block. `NULL` when unsure, never a default of 1. Keep the evidence string. |
| 14 | Tests first (TDD). Unit tests on small committed fixtures (a tiny parquet, a mini tar, a few gate-sample PDFs). Golden tests for paragraphs, `bench_size` and `text_quality`. One live bucket test behind an opt-in marker, not run in CI. |

## Out of scope

Citations (Day 3), headnote and section split, OCR, High Courts, regional-language text.
