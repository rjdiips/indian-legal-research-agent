---
Status: accepted
---

# Our own httpx downloader, not bharat-courts

PRD-004 §4 lists `bharat-courts` as an optional loader. We use our own anonymous S3 downloader built on `httpx` instead. bharat-courts' `ArchiveClient` reads the live bucket through DuckDB `httpfs` and fetches year tars on demand, which rules it out for four reasons:

- It records no ETags or manifest, so it can't produce a Snapshot.
- It doesn't deduplicate the 5,181 repeated `path` rows.
- It isn't built for a resumable bulk pull of the 22.7 GB of English tars.
- Most of the package is eCourts scraping and CAPTCHA solving (bs4, lxml, pydantic-settings, optional OCR), which would ship in our published package. It's also pre-1.0 with a single maintainer.

Revisit it as an optional adapter when a High Court is added, because it already handles the High Court bucket layout and single-PDF fetches there.
