# 09: Cleaning leaves OCR noise blocks, misread margin letters and some page headers

**What to fix:** Cleaned text still holds three kinds of page furniture that ticket 04's rules miss. Example: `data/sc-judgments/text/clean/2014_14_185_186.txt` (raw lines 54–101 become two lines of symbols at the end of the cleaned text).

1. **OCR noise blocks.** A stamp or smudge on a scanned page comes out as many lines of symbols in the middle of a page. Today only short noise lines at the top or bottom of a page are removed. Measured on Snapshot 0679ec43: 532 of 8,998 cleaned texts have lines that are mostly symbols (fewer than 40% letters or digits, 8 or more characters), 1,330 lines in total. Tables of dates and figures must stay: test on letters plus digits, not letters alone.
2. **Misread margin letters.** Clean uppercase margin letters A–H are removed, but OCR variants stay: lowercase (`h`, `c`), with a trailing mark (`s·`, `A·..`), or at the start of a text line (`B Nidhi Jain`). No reliable count yet; a loose scan matched about half the corpus, so measure properly first.
3. **Page headers.** 196 cleaned texts still contain a header line such as `[2017] 5 S.C.R.` or an OCR'd `SUPREME COURT REP<?RTS`.

Keep cleaning reversible: only drop raw characters, so the offset map stays exact. OCR misreadings inside words (`Wl1H`, `Retitions`) are out of scope (spec decision 9: no OCR).

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Golden test on `2014_14_185_186` (or a fixture made from it): no noise block, no `h`, `s·` or leading `B` margin letters, offset map still exact.
- [ ] Symbol-noise lines drop from 1,330 to near zero on the real corpus; table lines with dates and figures stay.
- [ ] Leftover page-header lines drop from 196 to near zero.
- [ ] Re-run `clean-text` and the report; note any change in paragraph or Bench size numbers.
