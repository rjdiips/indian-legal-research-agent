# 03: Raw text and Text quality

**What to build:** For a downloaded year, PDFs are streamed out of the year's English tar (using its index to map entries to Judgments). The embedded PDF text layer is extracted page by page to a raw text file on disk, and each Judgment gets its raw text hash and Text quality saved in Postgres. There is no OCR. Text quality is a structural check: `ocr` when pages are full-page images under an invisible text layer, otherwise `born_digital`.

**Blocked by:** 02

**Status:** resolved

- [x] Extraction is deterministic: the same PDF gives the same raw text and hash.
- [x] Unreadable PDFs are recorded as errors on the Judgment, and the run continues.
- [x] Golden tests: known scanned (pre-2010) and known born-digital gate-sample PDFs get the correct Text quality.
- [x] Mixed documents follow a documented rule, for example majority of pages, with a test.
- [x] Tests run on a committed mini tar of a few gate-sample PDFs.

## Resolution

- Package: `corpus/raw_text.py` (`extract_raw_text(pdf_bytes) -> RawText`, the Text quality rule) and
  `corpus/extract.py` (`extract_year` / `extract_tar` stream the tar and write `<data_home>/text/raw/<path>.txt`).
- Store: `migrations/0002_raw_text.sql` adds `raw_text_sha256`, `text_quality`, `page_count`, `scanned_pages`,
  `text_error`, `text_extracted_at` to `judgments`. `legal_agent.extract.extract_text`; CLI `legal-agent extract-text`.
- Mixed-document rule: a page is scanned when one image covers at least 90% of it and it has no visible text
  (all render mode 3, or none). The Judgment is `ocr` when scanned pages are a strict majority; ties go to
  `born_digital`.
