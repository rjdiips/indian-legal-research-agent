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
