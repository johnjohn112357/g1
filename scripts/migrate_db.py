"""One-time GIW PostgreSQL migration: Render source -> Neon target.
Run locally with GIW_SOURCE_DATABASE_URL and GIW_DATABASE_URL set.
Does not delete or alter source data. Safe to rerun (upserts by event URL; revisions copied once by ID).
"""
import os, sys
import psycopg
from psycopg.rows import tuple_row

SRC=os.getenv("GIW_SOURCE_DATABASE_URL")
DST=os.getenv("GIW_DATABASE_URL")
if not SRC or not DST:
    sys.exit("Set GIW_SOURCE_DATABASE_URL (Render external connection) and GIW_DATABASE_URL (Neon connection).")
if SRC==DST: sys.exit("Source and target connection strings must differ.")

SCHEMA="""
CREATE TABLE IF NOT EXISTS events (
 id BIGSERIAL PRIMARY KEY,url TEXT UNIQUE NOT NULL,title TEXT NOT NULL,domain TEXT,source TEXT,category TEXT,language TEXT,sourcecountry TEXT,seendate TEXT,latitude DOUBLE PRECISION,longitude DOUBLE PRECISION,first_seen TIMESTAMPTZ DEFAULT now(),last_seen TIMESTAMPTZ DEFAULT now(),payload JSONB DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS event_revisions (
 id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id),observed_at TIMESTAMPTZ DEFAULT now(),payload JSONB NOT NULL);
CREATE INDEX IF NOT EXISTS events_last_seen_idx ON events(last_seen DESC);
CREATE INDEX IF NOT EXISTS revisions_event_idx ON event_revisions(event_id,observed_at DESC);
"""
def copy_table(src,dst,table,cols,conflict):
    names=",".join(cols); placeholders=",".join(["%s"]*len(cols))
    with src.cursor() as cur:
        cur.execute(f"SELECT {names} FROM {table ORDER BY id")
        count=0
        while batch:=cur.fetchmany(500):
            with dst.cursor() as out:
                out.executemany(f"INSERT INTO {table} ({names}) VALUES ({placeholders}) {conflict}",batch)
            count+=len(batch)
    return count
with psycopg.connect(SRC,row_factory=tuple_row) as src, psycopg.connect(DST) as dst:
    dst.execute(SCHEMA)
    events=copy_table(src,dst,"events",["id","url","title","domain","source","category","language","sourcecountry","seendate","latitude","longitude","first_seen","last_seen","payload"],"ON CONFLICT(url) DO UPDATE SET title=excluded.title,domain=excluded.domain,source=excluded.source,category=excluded.category,language=excluded.language,sourcecountry=excluded.sourcecountry,seendate=excluded.seendate,latitude=excluded.latitude,longitude=excluded.longitude,last_seen=excluded.last_seen,payload=excluded.payload")
    revisions=copy_table(src,dst,"event_revisions",["id","event_id","observed_at","payload"],"ON CONFLICT(id) DO NOTHING")
    dst.execute("SELECT setval(pg_get_serial_sequence('events','id'),GREATEST(COALESCE((SELECT MAX(id) FROM events),1),1),true)")
    dst.execute("SELECT setval(pg_get_serial_sequence('event_revisions','id'),GREATEST(COALESCE((SELECT MAX(id) FROM event_revisions),1),1),true)")
    dst.commit()
print(f"Migration finished: {events} event rows and {revisions} revision rows copied. Source unchanged.")
