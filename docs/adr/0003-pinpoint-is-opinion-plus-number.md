---
Status: accepted
---

# A Pinpoint is (Opinion, paragraph number), not a paragraph number alone

In a Judgment with several Opinions, each Opinion often restarts its paragraph numbers at 1 (the same-sex marriage Judgment, 2023_16_1209_1524, has four). So "paragraph 12" alone can point to four different places. We identify a Pinpoint paragraph by its Opinion (counted in order of appearance, with the author when it can be read) plus its number. A Judgment with one Opinion has Opinion 1, so most Pinpoints are unchanged.

Note: this ADR first said five Opinions for 2023_16_1209_1524. The printed Judgment has four. S. Ravindra Bhat, J. writes for himself and Hima Kohli, J., so Kohli J. has no Opinion of her own (see ticket 10's comments).

## Considered Options

- **Renumber all paragraphs across the Judgment.** Rejected: the numbers would no longer match the printed Judgment, and citations quote the printed numbers.
- **Keep one run per Judgment and ignore restarts.** Rejected: that is the current bug (ticket 07); a restarted Opinion is swallowed into the previous paragraph.

## Consequences

Indian citations usually name the author with the number ("para 342, per Chandrachud CJ"), so Day 3 citation resolution can match on author as well as Opinion order.
