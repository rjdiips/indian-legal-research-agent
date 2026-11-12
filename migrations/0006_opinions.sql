-- Opinions (ticket 10, ADR-0003): a Pinpoint paragraph is (Opinion, number), because each Opinion
-- of a Judgment may restart its paragraph numbers at 1. After clean-text, the Opinions cover the
-- whole cleaned text with no gaps. Opinion 1 starts at 0. Each next Opinion starts at its author
-- line (or its first paragraph). The last Opinion ends at the end of the text.
--
-- Back-fill: the database does not store the length of the cleaned text. So each Judgment that has
-- paragraphs gets one Opinion 1 from 0 to the end of its last paragraph, and all its paragraphs are
-- Opinion 1. This covers the paragraphs, not the whole text. The next clean-text run replaces it.

CREATE TABLE opinions (
    path        text     NOT NULL REFERENCES judgments (path) ON DELETE CASCADE,
    number      smallint NOT NULL CHECK (number >= 1),  -- 1, 2, ... in order of appearance
    author      text,                                   -- the author line as read; NULL when not found
    char_start  integer  NOT NULL,                      -- offsets into the cleaned text
    char_end    integer  NOT NULL,
    PRIMARY KEY (path, number),
    CHECK (0 <= char_start AND char_start < char_end)
);

INSERT INTO opinions (path, number, char_start, char_end)
SELECT path, 1, 0, max(char_end) FROM paragraphs GROUP BY path;

ALTER TABLE paragraphs
    ADD COLUMN opinion smallint NOT NULL DEFAULT 1,
    ADD FOREIGN KEY (path, opinion) REFERENCES opinions (path, number) ON DELETE CASCADE;

DROP INDEX paragraphs_number_idx;
CREATE INDEX paragraphs_number_idx ON paragraphs (path, opinion, number);
