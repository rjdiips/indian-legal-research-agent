# 02: Full download, metadata and English tars, resumable

**What to build:** The ingest command now covers all years of metadata, and English tars for a chosen year range (default 2015–2026). Tars join the Snapshot manifest. Downloads use conditional GET with ETags, resume partial files, pace requests politely and keep a fetch log. Size and ETag are checked against the manifest. A rerun downloads nothing, and the backfill of older years is the same command with a wider range. After this ticket, start the real 2015–2026 pull.

**Blocked by:** 01

**Status:** resolved

- [x] A rerun with unchanged ETags downloads nothing (304 or skip).
- [x] An interrupted tar download resumes, not restarts.
- [x] A size or ETag mismatch against the manifest fails loudly.
- [x] A live metadata run gives about 38,392 Judgments with about 5,181 duplicates dropped, and the counts are reported.
- [x] Tests use a mocked HTTP transport. One live test against the real bucket sits behind an opt-in marker and doesn't run in CI.

## Comments

Live run 2026-11-12 (`legal-agent ingest --tar-years none`, 77 metadata parquets, 3 min 51 s): 43,578 rows read, 38,397 Judgments, 5,181 duplicates dropped, no missing or bad decision dates (1950-03-14 to 2026-10-06). The data gate's 38,392 is the subset with an English PDF in a year index, so about 5 Judgments have metadata but no English PDF. A rerun downloads 0 bytes. English tars for 2015–2026 total 4,018,288,640 bytes (12 tars); all 77 English tars total 22,694,338,560 bytes. `ingest-metadata --year` is replaced by `ingest [--tar-years FROM-TO|YEAR|none]`; the live test runs with `uv run pytest -m bucket`.
