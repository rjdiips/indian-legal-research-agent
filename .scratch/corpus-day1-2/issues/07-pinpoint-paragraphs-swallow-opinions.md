# 07: Over-long Pinpoint paragraphs from missed markers

**What to build:** The first corpus report (`reports/corpus-0679ec43c648.md`) gives 99.2% paragraph coverage, but that figure hides bad paragraph boundaries. 446 cleaned Judgments (379 born_digital, 67 ocr) have a numbered paragraph longer than 20,000 characters. The median numbered paragraph is 719 characters and the 99th percentile is 8,653. Two causes are seen:

- **Multi-opinion restart: moved to ticket 10.** 2023_16_1209_1524 (same-sex marriage, 5 opinions): the CJI's para 342 is 251,635 characters, because it swallows Kaul J.'s whole opinion, which restarts at 1.
- **Markers missed inside a single opinion.** 2021_6_573_598: para 7 runs 20,866 characters and swallows paras 8–13 (a `14.` marker appears at line start inside it). Similar cases: 2023_14_1_27 para 2, 2018_9_1_105 para 2.

A Pinpoint into these Judgments points at the wrong text, so this matters for citations.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] Find out why 2021_6_573_598's paras 8–13 were missed, and fix it.
- [ ] The report adds an "over-long paragraph" count (a numbered paragraph over 20,000 characters), so a regression shows up. Record how many of the 446 remain, and how many of those are multi-opinion cases left for ticket 10.
