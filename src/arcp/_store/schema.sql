CREATE TABLE IF NOT EXISTS events (
    session_id  TEXT NOT NULL,
    event_seq   INTEGER NOT NULL,
    job_id      TEXT,
    type        TEXT NOT NULL,
    envelope    TEXT NOT NULL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (session_id, event_seq)
);

CREATE INDEX IF NOT EXISTS events_session_idx ON events (session_id, event_seq);
CREATE INDEX IF NOT EXISTS events_job_idx ON events (job_id);
