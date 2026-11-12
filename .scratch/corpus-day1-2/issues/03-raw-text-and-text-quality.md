# 03: Raw text and Text quality

**What to build:** For a downloaded year, PDFs are streamed out of the year's English tar (using its index to map entries to Judgments). The embedded PDF text layer is extracted page by page to a raw text file on disk, and each Judgment gets its raw text hash and Text quality saved in Postgres. There is no OCR. Text quality is a structural check: `ocr` when pages are full-page images under an invisible text layer, otherwise `born_digital`.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Extraction is deterministic: the same PDF gives the same raw text and hash.
- [ ] Unreadable PDFs are recorded as errors on the Judgment, and the run continues.
- [ ] Golden tests: known scanned (pre-2010) and known born-digital gate-sample PDFs get the correct Text quality.
- [ ] Mixed documents follow a documented rule, for example majority of pages, with a test.
- [ ] Tests run on a committed mini tar of a few gate-sample PDFs.
