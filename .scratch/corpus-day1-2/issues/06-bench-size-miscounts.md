# 06: Bench size miscounts in the real run

**What to build:** Fix the Bench size cases that the first corpus report (`reports/corpus-0679ec43c648.md`, Snapshot `0679ec43c648…`) shows as wrong or unknown. Sizes 1, 4, 6 and 8 together cover 14 Judgments, and every one checked is wrong or doubtful:

- **Opinion header taken as coram (size 1, 9 Judgments).** `[DIPAK MISRA, CJI]` (2018_5_1125_1126, 2018_5_1127_1150, 2018_5_829_1124, 2018_7_379_746, which runs 368 pages and so is a large bench), `[V. RAMASUBRAMANIAN, J.]` (2021_3_881_902), `[K. V. VISWANATHAN, J.]` (2023_15_83_96), `[RANJAN GOGOi, J.]` (2015_2_37_50), `[T. S. THAKUR, C.J.l` (2017_1_158_260), `(Per Nariman, J.)` (2017_9_797_1158). A one-name block is most likely the author line of an opinion, not the coram. (Glossary: Bench size is never assumed to be one.)
- **OCR'd "CJI" not recognised, so the CJI's name splits into two (sizes 4 and 6).** `[T. S. THAKUR, CJJ, DR. D. Y. CHANDRACIIUD AND L. NAGESWARA RAO, .JJ.J` (2016_11_244_262) → 4 (should be 3); `[DIPAK MISRA, CJJ, R. BANUMATHI AND ASHOK BHUSHAN, JJ.)` (2017_14_618_638) → 4 (3); `[DIPAK MISRA, CJT, …]` (2017_13_1009_1052) → 6 (5); `[Dr Dnhananjaya Y Chandrachud,* CJl, 8 R Gavai, …]` (2024_2_420_616) → 6 (5).
- **Size 8 (2024_8_540_560).** Eight names are listed, but Supreme Court benches are almost always odd. Check whether a ninth judge (for example a dissent) appears elsewhere on page 1.
- **Unknown, 130 Judgments (1.4%).** 108 have no coram block found, 22 have a block that didn't parse. 2010s parse rate is 96.9% against 99.8% for the 2020s, so OCR is the main cause. Includes the ticket 04 gap of coram without "JJ.".

**Blocked by:** none

**Status:** ready-for-agent

- [ ] A one-name block (`J.`, `CJI`) is not read as the coram; the parser looks for the bench block, or leaves NULL.
- [ ] OCR variants of `CJI` (`CJJ`, `CJT`, `CJl`, `C.J.l`) are read as `CJI`.
- [ ] Re-run `legal-agent clean-text` and `legal-agent report`: no size 1, 4, 6 or 8 left unexplained; sample the 130 unknowns and record why they are unknown.

## Comments

**Fix (commit 4738fdf). I measured it read-only over all 8,998 raw texts in the main tree.** Each text was cleaned in memory and `bench_size` was run on page 1. The database and the report are not re-run yet.

| Bench size | Before | After |
|---|---|---|
| unknown | 130 | 55 |
| 1 | 9 | 3 |
| 2 | 7,308 | 7,368 |
| 3 | 1,453 | 1,472 |
| 4 | 2 | 0 |
| 5 | 82 | 87 |
| 6 | 2 | 0 |
| 7 | 7 | 8 |
| 8 | 1 | 1 |
| 9 | 4 | 4 |

Only the 10 Judgments this ticket names changed from one known size to another. I checked a sample of 25 of the 75 newly read blocks by eye. All are correct.

What changed in `parse.py`:
- A one-judge block counts only when no later block on page 1 names two or more judges. A block that starts with `Per` (`(Per Nariman, J.)`) is never the coram. This fixes three cases. The first is the `[DIPAK MISRA, CJI]` titles of connected cases (4 Judgments). The second is `[T. S. THAKUR, C.J.l`, where OCR read the title as the end of the block. The third is Shayara Bano, whose block ends `JJ,j` and is now read as 5.
- `CJJ`, `CJT`, `CJl` and `C.J.l` are read as `CJI`. This fixes the sizes 4 and 6. They are now 3, 3, 5 and 5.
- After `JJ.`, any one mark closes the block (`JJ.I`, `JJ.f`, `JJ.[`, `JJ.(`, `JJ.t`). `EQBALANDAMITAVA`, `A~D` and `~ND` are split as AND. This reads 75 of the 130 unknowns.

The sizes 1 and 8 that remain are correct:
- 2015_2_37_50 `[RANJAN GOGOi, J.]`: an arbitration application under s. 11(6). One judge heard it.
- 2021_3_881_902 `[V. RAMASUBRAMANIAN, J.]`: a transfer petition. One judge heard it.
- 2023_15_83_96 `[K. V. VISWANATHAN, J.]`: an order of the Judge In-Chambers. It ends "placed before Hon'ble the Chief Justice of India".
- 2024_8_540_560: the order on prospective effect that followed the 9-judge Mineral Area judgment. Page 1 names eight judges and no ninth. The ninth judge dissented in the main judgment and did not sign this order.

Why 55 stay unknown:
- 9 have names but no `JJ.` title (`[K. M. JOSEPH AND B. V. NAGARATHNA]`, 2019 to 2023). Or the title is in the wrong place (`[M. R. SHAH, JJ. AND KRISHNA MURARI]`). This is the gap from ticket 04. The parser leaves them unknown by design, because nothing marks the block as a list of judges.
- 9 have a block, but the count disagrees with the title. In some, the title is wrong: `[ANIL R. DAVE AND DIPAK MISRA, J.]` (3 Judgments), `;J.l`, `J;J.`. In others, OCR damaged the names: `ANDASllOKBHUSHAN`, `Al' 0.ABHAY`, `(iAPPAN, JJ.]`, `{. llANlJMATlll`, `(JI)`.
- About 25 have a damaged block that the parser does not find:
  - The title has no dot, or a mark replaces the dot (`JJ~]`, `JJ_]`, `JJ!`, `JJJ`, `JJ;I`, `.TJ.]`).
  - OCR read the opening bracket as letters (`rr.s. THAKUR`, `IDIPAK`, `11"· K. SIKRI`).
  - A stray bracket sits inside the names (`R. }'. NARIMAN`, `[.)'. CHELAMESWAR`).
  - Noise before the bracket looks like prose (`2015 . .j [`, `2017 , [`, `~-J-, [`).
  - A line break or page break cuts the block (`[KURIAN JOSEPH AND R. BANUMATHI, J.`, `[JAGDISH SINGH KHEHAR, (:`).
- About 10 have no coram on page 1 at all. Page 1 holds only the case title and the case number, or it is a cover page (`20161 JO S.C.R.`, `16 A`).

Open: a rule tied to the date could read the damaged blocks. It would take the names after the date, up to `JJ`. That is a bigger change, and each case needs its own check, so this ticket does not make it.
