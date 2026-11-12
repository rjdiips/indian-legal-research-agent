# 08: Extraction count includes cross-year duplicate PDFs; two Judgments without an English PDF

**What to build:** Make the extraction numbers match. `legal-agent extract-text` reported 9,001 extracted (2,083 ocr / 6,918 born_digital), but Postgres holds 8,998 Judgments with raw text (2,081 / 6,917). There are two reasons:

- **Three PDFs are in two years' tars**, so they were extracted twice under the same `path`: 2016_9_771_799 (tars 2015 and 2016), 2017_5_160_276 (2016 and 2017) and 2019_10_133_142 (2018 and 2019). The counts double them, and the second write wins. Harmless now, but the CLI count overstates.
- **Two Judgments in Reporter years 2015–2026 have no English PDF in any index**: 2023_10_160_288 and 2023_3_30_compressed. The second `path` looks malformed (`_compressed`). This is probably an upstream bucket gap; confirm and record it.

Also seen: 2017_5_160_276 has decision_date 2017-01-01 (a public holiday), which is worth a check against the PDF.

**Blocked by:** none

**Status:** resolved

- [x] `extract-text` counts each `path` once (or reports cross-year duplicates separately).
- [x] The two PDF-less Judgments are checked upstream and noted (in the report or as a known bucket gap).

## Comments

- `extract-text` now counts each `path` once (the last write, as saved in Postgres). A new count `cross_year_duplicates` lists the paths seen in two years' tars; the CLI prints each one. On the real corpus this should give 8,998 extracted (2,081 ocr / 6,917 born_digital) and 3 cross-year duplicates. The coordinator re-runs to confirm.
- The run report has a new section, "Judgments without an English PDF". It lists Judgments in the tar years that have no raw text under the Snapshot. A read-only query on the live store gives exactly 2023_10_160_288 and 2023_3_30_compressed.
- Upstream check (2026-11-12): both are an upstream gap. Neither has an English PDF in `english.tar`/`english.index.json` (2023) or under `data/pdf/year=2023/english/`. The regional index has only `<path>_PUN.pdf`, though the metadata says `ENG,PUN`. Recorded in `docs/known-bucket-gaps.md`.
- 2017_5_160_276: the metadata (both 2016 and 2017 parquet) and the PDF header both say "JANUARY 01, 2017". The date matches its source, so we keep it.

### Coordinator: final run

`extract-text` on main now prints extracted 8,998 (ocr 2,081 / born_digital 6,917) and cross_year_duplicates 3, which matches Postgres. The report lists the two PDF-less Judgments and points to `docs/known-bucket-gaps.md`.
