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

## Comments

Measured on the 8,998 raw texts of Snapshot 0679ec43, with `clean_text` run in a script (main at 9037c16 before, this branch after). The live database and `data/sc-judgments/text/clean` were not changed.

**Symbol-noise lines** (a cleaned line with 8 or more non-space characters, fewer than 40% letters or digits; this is the ticket's measure):

- Ticket's measure: 1,331 lines in 532 texts before, 1,257 in 502 after. The measure stays high because about 1,200 of these lines are real text: tables of contents with dot leaders (`Submissions ........ 7`), ellipses (`(a) …`), rules (`_____`) and masked numbers (`××××`).
- Same measure, with dot leaders, rules, ellipses, masks and brackets left out: 50 lines in 30 texts before, 3 lines in 2 texts after. The 3 lines left are short noise lines on their own, each under 8 characters.
- Raw lines that the new noise rule drops: 587 lines in 119 texts. A check of every dropped line with a word of 4 letters or 2 digits found only OCR noise and unreadable text.

**Leftover page headers** (a "SUPREME COURT REPORTS" line, or `[YYYY] N S.C.R.` with no page number after it): 571 matches in 242 texts before, 18 in 16 after. Of the 18, 8 are real text that names the Supreme Court Reports. The rest are the Judgment's own citation line with an unreadable page number (`S79 579`, `~~O`), or a header joined to other text on one line.

**Misread margin letters**, counted in cleaned text, before → after:

- a lone `b`–`h` or `s` between lowercase words (ligature splits such as `speciﬁ c` and s p a c e d letters are not counted): 3,402 → 1,271
- a letter with a stray mark (`s·`, `A·`, `A..`): 54 → 22
- `B`–`H` before a capitalised word at the start of a raw line, in scans: 5,004 → 0
- a trailing letter after lowercase text or a mark, label words such as `clause` not counted: 819 → 279

A "scan" here is a text where margin letters are glued to lines on half its pages or more (1,089 texts, almost all from 2015–2017). The capitalised-word, mid-line `c` and colon or mark rules apply only to these texts. Born-digital texts use headings such as `B Grounds of challenge` and illustrations such as `A concerts with B`, so they keep their 839 lines that start with `B`–`H` and a capitalised word.

**Real text lost**: of 52.4 million words of 3 or more letters, 841 words in 170 texts are gone. They are "SUPREME COURT REPORTS" or "Digital Supreme Court Reports" header words, OCR noise, or word halves that now join (`Offic ers` → `Officers`, `show- c cause` → `show-cause`, `time- s lag` → `time-lag`).

**Open**: about 1,300 lone `c` margin letters stay in 2016–2017 texts that glue too few margin letters to count as scans. The paragraph and Bench size numbers are not measured here. They come with the re-run of `clean-text` and the report.
