-- GIW PostgreSQL schema. Safe/idempotent; does not delete or overwrite existing rows.
CREATE TABLE IF NOT EXISTS events (
 id BIGSERIAL PRIMARY KEY,
 url TEXT UNIQUE NOT NULL,
 title TEXT NOT NULL,
 domain TEXT,
 source TEXT,
 category TEXT,
 language TEXT,
 sourcecountry TEXT,
 seendate TEXT,
 latitude DOUBLE PRECISION,
 longitude DOUBLE PRECISION,
 first_seen TIMESTAMPTZ DEFAULT now(),
 last_seen TIMESTAMPTZ DEFAULT now(),
 payload JSONB DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS event_revisions (
 id BIGSERIAL PRIMARY KEY,
 event_id BIGINT REFERENCES events(id),
 observed_at TIMESTAMPTZ DEFAULT now(),
 payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS events_last_seen_idx ON events(last_seen DESC);
CREATE INDEX IF NOT EXISTS revisions_event_idx ON event_revisions(event_id,observed_at DESC);
