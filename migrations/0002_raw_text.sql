-- Raw text and Text quality per Judgment (issue 03). The text itself lives on disk at
-- <data_home>/text/raw/<path>.txt; Postgres holds its hash and the structural Text quality.

ALTER TABLE judgments
    ADD COLUMN raw_text_sha256    text,            -- sha256 of the UTF-8 raw text file; NULL until extracted or on error
    ADD COLUMN text_quality       text CHECK (text_quality IN ('ocr', 'born_digital')),
    ADD COLUMN page_count         integer,
    ADD COLUMN scanned_pages      integer,         -- full-page image under invisible (or no) text
    ADD COLUMN text_error         text,            -- why the PDF couldn't be read; NULL on success
    ADD COLUMN text_extracted_at  timestamptz;     -- last extraction attempt, success or error

CREATE INDEX judgments_text_quality_idx ON judgments (text_quality);
