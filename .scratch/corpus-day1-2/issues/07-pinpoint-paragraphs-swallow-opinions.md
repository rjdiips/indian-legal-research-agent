# 07: Over-long Pinpoint paragraphs from missed markers

**What to build:** The first corpus report (`reports/corpus-0679ec43c648.md`) gives 99.2% paragraph coverage, but that figure hides bad paragraph boundaries. 446 cleaned Judgments (379 born_digital, 67 ocr) have a numbered paragraph longer than 20,000 characters. The median numbered paragraph is 719 characters and the 99th percentile is 8,653. Two causes are seen:

- **Multi-opinion restart: moved to ticket 10.** 2023_16_1209_1524 (same-sex marriage, 5 opinions): the CJI's para 342 is 251,635 characters, because it swallows Kaul J.'s whole opinion, which restarts at 1.
- **Markers missed inside a single opinion.** 2021_6_573_598: para 7 runs 20,866 characters and swallows paras 8–13 (a `14.` marker appears at line start inside it). Similar cases: 2023_14_1_27 para 2, 2018_9_1_105 para 2.

A Pinpoint into these Judgments points at the wrong text, so this matters for citations.

**Blocked by:** none

**Status:** resolved

- [x] Find out why 2021_6_573_598's paras 8–13 were missed, and fix it.
- [x] The report adds an "over-long paragraph" count (a numbered paragraph over 20,000 characters), so a regression shows up. Record how many of the 446 remain, and how many of those are multi-opinion cases left for ticket 10.

## Comments

**Root cause (2021_6_573_598).** No markers were missed there. Para 7 really is 20,866 characters. It holds its own sub-paragraphs 7.1 to 7.6 and a long quote from another Judgment. The `13.` to `19.` lines inside it are that quote's paragraph numbers. The parser was right to skip them, and the real para 8 is found. The other two named cases are the same kind: 2023_14_1_27 para 2 holds sub-paragraphs 2.1 to 2.13, and 2018_9_1_105 para 2 quotes two whole magazine articles. All three match the printed Judgment, so they stay as they are.

**A real missed-marker cause, now fixed.** Some Judgments number their paragraphs `7)` instead of `7.`. The parser accepted `7)`, but cleaning did not keep a line break before it. So `7)` was joined onto the end of the line before it whenever that line was long (2015_5_542_578: para 6 ran 47,654 characters and held paras 7 to the end). A `3)` alone on its own line (2025_4_2742_2752) was not joined to the text after it either. Cleaning now keeps a line break before `N)` after a sentence end. A wrapped bracket such as `(para\n51)` or `(Pg.\n183)` does not count as a marker.

**Report.** The run report now has a "With a numbered paragraph over 20,000 characters" row.

**Measured** over the main tree's 8,998 raw texts. Each was cleaned again in memory with the new code and parsed. Nothing was written.

- Over-long Judgments: 446 before, 438 after. The fix repairs 9: 2015_4_640_675, 2015_5_542_578, 2015_8_289_305, 2015_8_728_744, 2022_19_100_148, 2025_2_1588_1607, 2025_4_2742_2752, 2025_7_2148_2160 and 2026_3_358_392. It adds 1: 2023_5_1092_1151, where a quoted legal notice numbered `6)`, `7)` now takes paras 6 and 7. A rule of one marker style per Judgment fixed that case, but it broke 3 others, so I left it out.
- No Judgment loses a numbered paragraph. 34 Judgments gain some. Judgments with numbered paragraphs go from 8,929 to 8,930.
- The 438 that remain, sorted by a rough rule (the first over-long paragraph in each Judgment):
  - about 165 are multi-opinion restarts (a run 1, 2, 3, 4 or 2, 3, 4, 5 inside the paragraph). These are for ticket 10, and 2023_16_1209_1524 is one of them.
  - about 80 are paragraphs with printed sub-paragraphs (N.1, N.2, ...).
  - about 173 have no marker inside them. Samples were real long paragraphs that quote statutes, reports or earlier opinions.
  - about 20 have an `N+1` mid-line, and most of those are numbered sub-sections of a quoted statute.

So most of what remains is correct by printed numbering or belongs to ticket 10. A 20,000-character limit will always flag some real paragraphs.

### Coordinator: final run

Final run on main (ca6057c, Snapshot 0679ec43c648, `clean-text` + `report` on 2026-11-12): the report row "With a numbered paragraph over 20,000 characters" shows 366 (446 before; 438 after this ticket alone; ticket 10 fixed 73 and added 1). The case 2021_6_573_598 was not a missed-marker bug (see above); the real cause, `N)` markers joined to the line before, is fixed.
