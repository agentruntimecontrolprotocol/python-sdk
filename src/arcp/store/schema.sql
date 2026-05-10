-- ARCP event log schema. Append-only by design.
--
-- Each row represents one envelope observed by the runtime. The event log is
-- the source of truth for resume (RFC §19) and subscription backfill (§13.3).
-- ``id`` (the envelope id) is the transport idempotency key (§6.4) and is
-- unique within a session; ``rowid`` provides the canonical replay order.

CREATE TABLE IF NOT EXISTS events (
    rowid           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    id              TEXT NOT NULL,
    type            TEXT NOT NULL,
    job_id          TEXT,
    stream_id       TEXT,
    subscription_id TEXT,
    trace_id        TEXT,
    correlation_id  TEXT,
    causation_id    TEXT,
    timestamp       TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'normal',
    envelope        TEXT NOT NULL  -- canonical JSON serialization
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_id_session ON events(session_id, id);
CREATE INDEX IF NOT EXISTS idx_events_session_rowid ON events(session_id, rowid);
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_events_causation ON events(causation_id);
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

-- Logical-intent idempotency table per RFC §6.4.
CREATE TABLE IF NOT EXISTS idempotency_results (
    principal       TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    result_envelope TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (principal, idempotency_key)
);

-- Artifact storage (§16). Inline base64 in v0.1.
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id  TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    media_type   TEXT NOT NULL,
    size         INTEGER NOT NULL,
    sha256       TEXT,
    expires_at   TEXT,
    released     INTEGER NOT NULL DEFAULT 0,
    blob         BLOB NOT NULL
);
