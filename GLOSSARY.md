# Indian Legal Research Agent

Answers Indian legal research questions from Supreme Court judgments, cites passages, and warns when a cited judgment may no longer be good law.

## Corpus

**Judgment**:
One Supreme Court decision in the corpus, identified by its source `path`. Rows repeating a `path` are the same Judgment.
_Avoid_: Case, order, document

**Snapshot**:
A recorded state of the public judgment bucket, fixed by a content-hashed manifest of the files used. Every derived artefact names the Snapshot it was built from.
_Avoid_: Version, dump, release

**Decision date**:
The date a Judgment was decided. It is the only date used for date logic.
_Avoid_: Year, judgment year

**Reporter year**:
The year of the law report a Judgment appears in, as used in the bucket's partitions. Never used for date logic.
_Avoid_: Decision year

**Text quality**:
Whether a Judgment's text came from existing OCR over a scanned page (`ocr`) or was produced digitally (`born_digital`). OCR text is readable but not guaranteed exact character for character.
_Avoid_: Text confidence, scan quality

**Bench size**:
The number of judges who heard a Judgment, read from its coram block. Unknown when it can't be read, never assumed to be one.
_Avoid_: Judge count, panel size

**Pinpoint paragraph**:
A numbered paragraph of a Judgment's cleaned text, the unit a citation or quote points to.
_Avoid_: Passage number, para ref
