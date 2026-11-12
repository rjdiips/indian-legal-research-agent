-- Cleaned text, Pinpoint paragraphs and Bench size per Judgment (issue 04). The cleaned text and its
-- offset map back to raw live on disk at <data_home>/text/clean/<path>.txt and <path>.map.json;
-- Postgres holds the hash, the paragraphs (offsets into the cleaned text) and Bench size.

ALTER TABLE judgments
    ADD COLUMN clean_text_sha256    text,          -- sha256 of the UTF-8 cleaned text file; NULL until cleaned or on error
    ADD COLUMN bench_size           smallint CHECK (bench_size BETWEEN 1 AND 15),  -- NULL when unsure, never a default
    ADD COLUMN bench_evidence       text,          -- the coram block as read; NULL when none was found
    ADD COLUMN clean_error          text,          -- why cleaning failed; NULL on success
    ADD COLUMN cleaned_at           timestamptz;   -- last cleaning attempt, success or error

CREATE TABLE paragraphs (
    path        text    NOT NULL REFERENCES judgments (path) ON DELETE CASCADE,
    ordinal     integer NOT NULL,                  -- 1, 2, ... in document order
    number      integer,                           -- the Pinpoint paragraph number; NULL for the one unnumbered block
    char_start  integer NOT NULL,                  -- offsets into the cleaned text: text = clean[char_start:char_end]
    char_end    integer NOT NULL,
    text        text    NOT NULL,
    PRIMARY KEY (path, ordinal),
    CHECK (0 <= char_start AND char_start < char_end)
);

CREATE INDEX paragraphs_number_idx ON paragraphs (path, number);
