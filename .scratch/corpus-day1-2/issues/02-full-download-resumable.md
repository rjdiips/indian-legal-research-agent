# 02: Full download, metadata and English tars, resumable

**What to build:** The ingest command now covers all years of metadata, and English tars for a chosen year range (default 2015–2026). Tars join the Snapshot manifest. Downloads use conditional GET with ETags, resume partial files, pace requests politely and keep a fetch log. Size and ETag are checked against the manifest. A rerun downloads nothing, and the backfill of older years is the same command with a wider range. After this ticket, start the real 2015–2026 pull.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A rerun with unchanged ETags downloads nothing (304 or skip).
- [ ] An interrupted tar download resumes, not restarts.
- [ ] A size or ETag mismatch against the manifest fails loudly.
- [ ] A live metadata run gives about 38,392 Judgments with about 5,181 duplicates dropped, and the counts are reported.
- [ ] Tests use a mocked HTTP transport. One live test against the real bucket sits behind an opt-in marker and doesn't run in CI.
