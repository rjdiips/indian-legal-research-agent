# 06: Bench size miscounts in the real run

**What to build:** Fix the Bench size cases that the first corpus report (`reports/corpus-0679ec43c648.md`, Snapshot `0679ec43c648…`) shows as wrong or unknown. Sizes 1, 4, 6 and 8 together cover 14 Judgments, and every one checked is wrong or doubtful:

- **Opinion header taken as coram (size 1, 9 Judgments).** `[DIPAK MISRA, CJI]` (2018_5_1125_1126, 2018_5_1127_1150, 2018_5_829_1124, 2018_7_379_746, which runs 368 pages and so is a large bench), `[V. RAMASUBRAMANIAN, J.]` (2021_3_881_902), `[K. V. VISWANATHAN, J.]` (2023_15_83_96), `[RANJAN GOGOi, J.]` (2015_2_37_50), `[T. S. THAKUR, C.J.l` (2017_1_158_260), `(Per Nariman, J.)` (2017_9_797_1158). A one-name block is most likely the author line of an opinion, not the coram. (Glossary: Bench size is never assumed to be one.)
- **OCR'd "CJI" not recognised, so the CJI's name splits into two (sizes 4 and 6).** `[T. S. THAKUR, CJJ, DR. D. Y. CHANDRACIIUD AND L. NAGESWARA RAO, .JJ.J` (2016_11_244_262) → 4 (should be 3); `[DIPAK MISRA, CJJ, R. BANUMATHI AND ASHOK BHUSHAN, JJ.)` (2017_14_618_638) → 4 (3); `[DIPAK MISRA, CJT, …]` (2017_13_1009_1052) → 6 (5); `[Dr Dnhananjaya Y Chandrachud,* CJl, 8 R Gavai, …]` (2024_2_420_616) → 6 (5).
- **Size 8 (2024_8_540_560).** Eight names are listed, but Supreme Court benches are almost always odd. Check whether a ninth judge (for example a dissent) appears elsewhere on page 1.
- **Unknown, 130 Judgments (1.4%).** 108 have no coram block found, 22 have a block that didn't parse. 2010s parse rate is 96.9% against 99.8% for the 2020s, so OCR is the main cause. Includes the ticket 04 gap of coram without "JJ.".

**Blocked by:** none

**Status:** needs-triage

- [ ] A one-name block (`J.`, `CJI`) is not read as the coram; the parser looks for the bench block, or leaves NULL.
- [ ] OCR variants of `CJI` (`CJJ`, `CJT`, `CJl`, `C.J.l`) are read as `CJI`.
- [ ] Re-run `legal-agent clean-text` and `legal-agent report`: no size 1, 4, 6 or 8 left unexplained; sample the 130 unknowns and record why they are unknown.
