# Known bucket gaps

Gaps in the public bucket `indian-supreme-court-judgments`. We do not fix them. The run report lists them.

Checked on 2026-11-12, against Snapshot `0679ec43c648`.

## Judgments without an English PDF

The metadata lists these Judgments with `available_languages` `ENG,PUN`. But the bucket has no English PDF for them. The English tar, `english.index.json` and `data/pdf/year=2023/english/` do not have them. The regional tar has only the Punjabi PDF (`<path>_PUN.pdf`).

| path | Citation | Decision date |
|---|---|---|
| `2023_10_160_288` | [2023] 10 S.C.R. 160 (2023 INSC 605) | 2023-07-06 |
| `2023_3_30_compressed` | [2023] 3 S.C.R. 30 (2023 INSC 157) | 2023-02-24 |

The `path` `2023_3_30_compressed` is malformed upstream. Other paths end in the last page number.

## PDFs in two years' tars

Some PDFs are in the tars of two Reporter years. Examples: `2016_9_771_799` (2015, 2016), `2017_5_160_276` (2016, 2017), `2019_10_133_142` (2018, 2019). `extract-text` counts each `path` once and lists these as `cross_year_duplicates`.

## Decision date of `2017_5_160_276`

The metadata gives 2017-01-01, a public holiday. The PDF header also says "JANUARY 01, 2017", so we keep that date.
