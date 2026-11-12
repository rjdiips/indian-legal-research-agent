# 01: Ingest one year's metadata end to end

**What to build:** A single command, given one year, does the whole path. It lists that year's metadata parquet anonymously from the public bucket and writes a Snapshot manifest (keys, sizes, ETags) with a content-hashed `snapshot_id`. It downloads the parquet, deduplicates on `path`, creates the Postgres schema through a small migrate runner (plain numbered SQL, no ORM), and saves the Judgments, each stamped with its `snapshot_id`, source URI and CC-BY-4.0 attribution. The tracer bullet: after one run, Judgments for that year can be queried in Postgres.

Corpus logic stays storage-agnostic in the published package; only the research app writes to Postgres (ADR-0001). The downloader uses `httpx` against the anonymous S3 endpoint, not bharat-courts (ADR-0002); port the listing and polite-fetch logic from the data-gate scripts.

**Blocked by:** None (can start immediately)

**Status:** resolved (032cd3f)

- [x] The same bucket listing gives the same `snapshot_id`; a changed ETag gives a different one. The manifest is saved under the package data home.
- [x] Rows with a repeated `path` produce one Judgment. The Decision date comes only from `decision_date`, never from the bucket's Reporter year.
- [x] Missing or bad decision dates are counted and reported, not silently dropped.
- [x] The migrate runner applies numbered SQL files in order, tracks applied files, and is safe to rerun.
- [x] Running the command twice leaves the row count unchanged (idempotent upsert).
- [x] Tests come first: unit tests on a recorded S3 listing fixture and a tiny parquet fixture with no network, plus an integration test against `testcontainers` Postgres.
