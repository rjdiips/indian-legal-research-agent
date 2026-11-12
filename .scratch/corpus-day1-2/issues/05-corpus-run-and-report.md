# 05: Corpus run over 2015–2026, plus report

**What to build:** The full pipeline runs over every downloaded year: metadata, raw text, Text quality, cleaned text, Pinpoint paragraphs and Bench size. It saves results idempotently and writes a run report stamped with the `snapshot_id`. This is the Day 1–2 demo: one Snapshot of the corpus in Postgres plus disk, with its quality measured.

**Blocked by:** 04

**Status:** resolved

- [x] An end-to-end integration test runs the fixture corpus into `testcontainers` Postgres. A rerun changes nothing.
- [x] The report gives Judgment counts, the Text quality split, Bench size parse rate by decade, paragraph coverage (share of Judgments with numbered paragraphs) and extraction errors.
- [x] The report goes in the reports folder and names the Snapshot it describes.
- [x] The real 2015–2026 run completes. Report numbers that look wrong are noted as follow-up tickets, not fixed silently.
