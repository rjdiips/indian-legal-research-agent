# 08: Extraction count includes cross-year duplicate PDFs; two Judgments without an English PDF

**What to build:** Make the extraction numbers match. `legal-agent extract-text` reported 9,001 extracted (2,083 ocr / 6,918 born_digital), but Postgres holds 8,998 Judgments with raw text (2,081 / 6,917). There are two reasons:

- **Three PDFs are in two years' tars**, so they were extracted twice under the same `path`: 2016_9_771_799 (tars 2015 and 2016), 2017_5_160_276 (2016 and 2017) and 2019_10_133_142 (2018 and 2019). The counts double them, and the second write wins. Harmless now, but the CLI count overstates.
- **Two Judgments in Reporter years 2015–2026 have no English PDF in any index**: 2023_10_160_288 and 2023_3_30_compressed. The second `path` looks malformed (`_compressed`). This is probably an upstream bucket gap; confirm and record it.

Also seen: 2017_5_160_276 has decision_date 2017-01-01 (a public holiday), which is worth a check against the PDF.

**Blocked by:** none

**Status:** needs-triage

- [ ] `extract-text` counts each `path` once (or reports cross-year duplicates separately).
- [ ] The two PDF-less Judgments are checked upstream and noted (in the report or as a known bucket gap).
