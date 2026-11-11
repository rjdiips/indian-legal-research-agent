-- Corpus store (ADR-0001): Snapshots and Judgments.

CREATE TABLE snapshots (
    snapshot_id  text PRIMARY KEY,           -- sha256 of the manifest's object list
    fetched_at   timestamptz NOT NULL,
    manifest     jsonb NOT NULL,             -- keys, sizes, ETags, dedup counts
    recorded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE judgments (
    path                 text PRIMARY KEY,   -- the Judgment's identity in the bucket
    decision_date        date,               -- NULL when missing or unreadable; the only date for date logic
    reporter_year        integer,            -- the bucket's `year` partition; never used for date logic
    title                text,
    petitioner           text,
    respondent           text,
    description          text,
    judge                text,
    author_judge         text,
    citation             text,
    case_id              text,
    cnr                  text,
    disposal_nature      text,
    court                text,
    available_languages  text,
    nc_display           text,
    scraped_at           text,
    snapshot_id          text NOT NULL REFERENCES snapshots (snapshot_id),
    source_uri           text NOT NULL,
    license              text NOT NULL,
    attribution          text NOT NULL,
    ingested_at          timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX judgments_decision_date_idx ON judgments (decision_date);
CREATE INDEX judgments_snapshot_id_idx ON judgments (snapshot_id);
