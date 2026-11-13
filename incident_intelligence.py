"""Conservative incident grouping and evidence summaries for GIW.

This is deterministic headline similarity, not semantic verification. It intentionally
labels publisher diversity separately from independent corroboration.
"""
import hashlib
import re
from datetime import datetime, timezone, timedelta

STOP = {"the","and","for","with","from","that","this","after","over","into","says","said","report","reported","reports","according","update","updates","breaking","near","amid","during","about","have","has","was","were","are"}

def tokens(title):
    return set(re.findall(r"[a-z0-9]{3,}", (title or "").lower())) - STOP

def similarity(a, b):
    aa, bb = tokens(a), tokens(b)
    return len(aa & bb) / max(1, min(len(aa), len(bb)))

def group_reports(reports, threshold=0.72, max_age_days=14):
    """Greedy, conservative groups. Reports are expected newest-first."""
    groups=[]
    for report in reports:
        title=report.get("title") or ""
        if not tokens(title):
            continue
        date=report.get("last_seen") or report.get("first_seen")
        placed=False
        for group in groups:
            if similarity(title, group["representative"]) < threshold:
                continue
            gdate=group.get("anchor_date")
            if date and gdate:
                try:
                    dt=date if isinstance(date,datetime) else datetime.fromisoformat(str(date).replace("Z","+00:00"))
                    gd=gdate if isinstance(gdate,datetime) else datetime.fromisoformat(str(gdate).replace("Z","+00:00"))
                    if abs((dt-gd).total_seconds()) > max_age_days*86400:
                        continue
                except Exception:
                    pass
            group["reports"].append(report)
            placed=True
            break
        if not placed:
            groups.append({"representative":title,"anchor_date":date,"reports":[report]})
    return [g for g in groups if len(g["reports"]) >= 2]

def incident_key(reports):
    # Stable for a group as long as its earliest report remains the anchor.
    anchor=min((int(r["id"]) for r in reports if r.get("id") is not None), default=0)
    return "inc-"+str(anchor)

def summarize_group(group):
    reports=group["reports"]
    publishers=sorted({(r.get("domain") or r.get("source") or "unknown").strip().lower() for r in reports})
    dates=[]
    for r in reports:
        value=r.get("seendate") or r.get("last_seen") or r.get("first_seen")
        try:
            if value: dates.append(value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00")))
        except Exception: pass
    dates.sort()
    return {
        "id":incident_key(reports),
        "headline":group["representative"],
        "report_count":len(reports),
        "publisher_count":len(publishers),
        "publishers":publishers,
        "first_reported":dates[0].isoformat() if dates else None,
        "last_reported":dates[-1].isoformat() if dates else None,
        "timeline":[{"event_id":r.get("id"),"title":r.get("title"),"publisher":r.get("domain") or r.get("source"),"url":r.get("url"),"reported_at":r.get("seendate") or (r.get("last_seen").isoformat() if isinstance(r.get("last_seen"),datetime) else r.get("last_seen"))} for r in sorted(reports,key=lambda x:str(x.get("seendate") or x.get("last_seen") or ""))],
        "evidence_note":"Publisher count is descriptive only. Syndication, shared wire copy, common sourcing and source independence have not been verified. Similar headlines may describe different events; analyst review is required.",
        "method":"Greedy title-token similarity (minimum overlap ratio 0.72), 14-day anchor window; no semantic or factual verification."
    }

def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS giw_incidents (
          id TEXT PRIMARY KEY, headline TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), first_reported TIMESTAMPTZ,
          last_reported TIMESTAMPTZ, report_count INTEGER NOT NULL DEFAULT 0,
          publisher_count INTEGER NOT NULL DEFAULT 0, evidence_note TEXT NOT NULL,
          method TEXT NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS giw_incident_reports (
          event_id BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
          incident_id TEXT NOT NULL REFERENCES giw_incidents(id) ON DELETE CASCADE,
          linked_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        cur.execute("CREATE INDEX IF NOT EXISTS giw_incidents_updated_idx ON giw_incidents(updated_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS giw_incident_reports_incident_idx ON giw_incident_reports(incident_id)")

def rebuild(conn, reports):
    groups=group_reports(reports)
    summaries=[summarize_group(g) for g in groups]
    ensure_schema(conn)
    with conn.cursor() as cur:
        for s in summaries:
            cur.execute("""INSERT INTO giw_incidents(id,headline,first_reported,last_reported,report_count,publisher_count,evidence_note,method)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET headline=excluded.headline,updated_at=now(),
                first_reported=excluded.first_reported,last_reported=excluded.last_reported,
                report_count=excluded.report_count,publisher_count=excluded.publisher_count,
                evidence_note=excluded.evidence_note,method=excluded.method""",
                (s["id"],s["headline"],s["first_reported"],s["last_reported"],s["report_count"],s["publisher_count"],s["evidence_note"],s["method"]))
            for item in s["timeline"]:
                if item["event_id"] is not None:
                    cur.execute("""INSERT INTO giw_incident_reports(event_id,incident_id) VALUES(%s,%s)
                    ON CONFLICT(event_id) DO UPDATE SET incident_id=excluded.incident_id,linked_at=now()""",(item["event_id"],s["id"]))
    return summaries
