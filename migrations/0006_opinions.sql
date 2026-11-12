-- Opinions (ticket 10, ADR-0003): a Pinpoint paragraph is (Opinion, number), because each Opinion
-- of a Judgment may restart its paragraph numbers at 1. Opinions tile the cleaned text:
-- Opinion 1 starts at 0, each next one at its author line (or first paragraph), the last ends at
-- the text's end. Existing paragraphs are all Opinion 1 until clean-text runs again.

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
