-- Every derived artefact records the Snapshot it was derived under (spec decision 4), apart from
-- judgments.snapshot_id, which each ingest moves on. extract-text sets raw_snapshot_id (raw text,
-- Text quality, or the extraction error); clean-text copies it to clean_snapshot_id (cleaned text,
-- offset map, paragraphs, Bench size, or the cleaning error). NULL until that step has run.

ALTER TABLE judgments
    ADD COLUMN raw_snapshot_id    text REFERENCES snapshots (snapshot_id),
    ADD COLUMN clean_snapshot_id  text REFERENCES snapshots (snapshot_id);
