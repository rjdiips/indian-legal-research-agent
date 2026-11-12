# 04: Cleaned text, Pinpoint paragraphs and Bench size

**What to build:** Each raw text becomes cleaned text on disk. Cleaning removes repeated page headers and footers, margin letters, hyphenation and line-wrap breaks, and the Judgment's own citation line, and keeps an offset map from cleaned text back to raw. From cleaned text, the pipeline saves Pinpoint paragraphs (number plus character offsets), so paragraph N of a Judgment can be fetched. It also saves Bench size parsed from the coram block, with the evidence string. Headnote and section splitting stay out of scope.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] For any span of cleaned text, the offset map recovers the matching raw span. Golden tests cover headers such as `[196112 S.C.R. 537`.
- [ ] Each stored paragraph's text equals the matching slice of the cleaned text. A Judgment with no paragraph markers gets one unnumbered block.
- [ ] Numbers inside paragraphs (citations, inline lists) don't create false paragraph splits in the golden set.
- [ ] Bench size is `NULL` when unsure, never a default of 1. The evidence string is stored.
- [ ] Golden tests across decades and both Text qualities cover paragraphs and single, division and constitution benches.
- [ ] The cleaned text hash is stored, and the new schema is added through a new numbered migration.
