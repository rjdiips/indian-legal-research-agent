-- Postgres holds paragraph offsets, not their text (spec decision 7): a paragraph's text is
-- clean[char_start:char_end] of the cleaned-text file on disk.

ALTER TABLE paragraphs DROP COLUMN text;
