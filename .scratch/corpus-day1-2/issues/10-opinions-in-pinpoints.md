# 10: Opinions: each Opinion gets its own Pinpoint paragraph run

**What to build:** Split each Judgment's cleaned text into Opinions and number paragraphs within each Opinion, as decided in [ADR-0003](../../../docs/adr/0003-pinpoint-is-opinion-plus-number.md) (see **Opinion** and **Pinpoint paragraph** in GLOSSARY.md). Today a second Opinion that restarts at 1 is swallowed into the first Opinion's last paragraph: in 2023_16_1209_1524 (same-sex marriage, five Opinions), the CJI's para 342 is 251,635 characters because it holds Kaul J.'s whole Opinion.

An Opinion starts where paragraph numbering restarts at 1 after a run, usually after an author line such as `S. K. KAUL, J.` or `(Per Nariman, J.)`. Store each Opinion's order and its author when it can be read, plus character offsets into the cleaned text. A Judgment with no detected restart has one Opinion. Schema changes go in a new numbered migration.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] Every paragraph belongs to exactly one Opinion; Opinions are numbered from 1 in order of appearance, with the author stored when readable and NULL otherwise.
- [ ] Golden test on 2023_16_1209_1524: five Opinions, each starting at paragraph 1, with no paragraph over 20,000 characters.
- [ ] A single-Opinion Judgment is unchanged apart from carrying Opinion 1.
- [ ] Paragraph N of Opinion K can be fetched, and its text equals the cleaned-text slice.
- [ ] Re-run `clean-text` and the report; the report adds the share of Judgments with more than one Opinion.

## Comments

**Four Opinions, not five, in 2023_16_1209_1524.** The printed Judgment has four Opinions: the CJI, Kaul J., Bhat J. (who writes for himself and Hima Kohli J.) and Narasimha J. No author line for Kohli J. appears after the coram. The golden test checks four runs: 1–342, 1–33, 1–166 and 1–20. On the full text the longest paragraph is now 8,383 characters (it was 251,635).

**How a restart is found** (`parse.py`). The paragraph run may restart at 1 only when an author line comes before the `1.`, at most 5,000 characters before it. An author line is a judge's name with `, J.`, `, CJI` or `, C.J.` at the end of its line (or directly before `1.`), or `(Per Nariman, J.)`. A running header in brackets (`[S. RAVINDRA BHAT, J.]`) does not count. Without that rule, quoted lists of witnesses, schedules and Act sections split 594 Judgments, nearly all falsely. A restart costs 1.5 markers, so each Opinion needs two or more paragraphs. The author line ends the paragraph before it and starts the new Opinion. Two smaller fixes came with it:
- `J. 1.` on one line now starts paragraph 1 anywhere, not only for the first Opinion (2015_14_927_974: `... larger Bench. V. GOPALA GOWDA, J. 1. I have ...`).
- The delivery line now also matches `Judgement`, `Judgments*`, `Judgments and Order`, `Ccurt`, `<;:ourt`, `delievered`. Also, when a first run of fewer than 10 markers has no author line and a restart follows, it is dropped. It was the headnote's numbered points or an index. This changes 3 single-Opinion Judgments (2017_8_388_427, 2023_7_26_84, 2025_4_829_834).

**Schema** (`migrations/0006_opinions.sql`). There is a new `opinions` table (path, number, author, char_start, char_end). Opinions cover the whole cleaned text, with no gaps. `paragraphs.opinion` is added (default 1, foreign key to opinions), and the index is now (path, opinion, number). The migration gives each existing Judgment an Opinion 1 until `clean-text` runs again.

**API.** Use `legal_agent.db.corpus.pinpoint_paragraph(conn, data_home, path, number, opinion=1)`. It returns the cleaned-text slice, or None. `clean_texts` counts `multi_opinion`. The report adds the row "With more than one Opinion | N (share)".

**Measured** read-only over the main tree's 8,998 raw texts, cleaned in memory with ticket 09's cleaning (main e114261):
- Judgments with more than one Opinion: 179 (2 Opinions: 152, 3: 18, 4: 6, 6: 2, 7: 1). Every restart has an author line. All 90 distinct authors read are Supreme Court judges. Some names have OCR spaces (`AB HAY MANO HAR SAPRE, J.`), and one has a glued heading (`ORDER ON REFERENCE Nagarathna, J.`).
- Over-long paragraphs (over 20,000 characters): 438 before, 366 after. 73 are fixed and 1 is added: 2025_11_136_196, where Nagarathna J.'s Opinion is now found and her para 16 has a missed marker inside one Opinion.
- Single-Opinion Judgments: apart from the 3 named above, no single-Opinion Judgment changes its paragraphs. No Judgment loses its numbered paragraphs, and 1 gains them (2015_14_927_974).
- Numbered paragraphs: 271,567 before, 281,317 after.

**Left open.**
- In the remaining over-long paragraphs, 77 hold a `1. 2. 3. 4.` run. Samples are mostly quoted lists, Acts and reports, which is correct. Some real restarts have no author line that the rule reads. One is 2018_8_1_1076 (Aadhaar), where only the previous Opinion's bracketed signature `[A. K. SIKRI, J.]` comes before Bhushan J.'s `1.`.
- A one-paragraph Opinion stays inside the paragraph before it.
- When one judge's writing restarts at 1 (an Order after the Opinion, or a second part), it becomes a separate Opinion with the same author (for example 2023_6_655_668). The Pinpoint stays unique, which ADR-0003 needs.
- Opinion 1's author is often None, because its author is on the delivery line, not on a line of its own.
- A table-of-contents `I.` is still read as paragraph 1 (the CJI's and Bhat J.'s Opinions in 2023_16_1209_1524). This is older behavior, not changed here.
