"""Conservative incident grouping and evidence summaries for GIW.

This is deterministic headline similarity, not semantic verification. Publisher
diversity is deliberately kept separate from independent corroboration.
"""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STOP = {"the","and","for","with","from","that","this","after","over","into","says","said","report","reported","reports","according","update","updates","breaking","near","amid","during","about","have","has","was","were","are"}

def tokens(title):
    return set(re.findall(r"[a-z0-9]{3,}", (title or "").lower())) - STOP

def similarity(a, b):
    """Jaccard similarity avoids treating a short subset as a perfect match."""
    aa, bb = tokens(a), tokens(b)
    return len(aa & bb) / max(1, len(aa | bb))

def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw=str(value).strip()
    # GDELT timestamps are commonly YYYYMMDDHHMMSS, not ISO 8601.
    if re.fullmatch(r"\d{14}", raw):
        try:return datetime.strptime(raw,"%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            dt=parsedate_to_datetime(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError,ValueError,OverflowError):return None

def group_reports(reports, threshold=0.72, max_age_days=14):
    """Greedy candidate groups. Reports should be newest-first."""
    groups=[]
    for report in reports:
        title=report.get("title") or ""
        if not tokens(title):continue
        date=parse_date(report.get("last_seen") or report.get("first_seen") or report.get("seendate"))
        placed=False
        for group in groups:
            if similarity(title,group["representative"]) < threshold:continue
            anchor=group.get("anchor_date")
            if date and anchor and abs((date-anchor).total_seconds()) > max_age_days*86400:continue
            group["reports"].append(report);placed=True;break
        if not placed:groups.append({"representative":title,"anchor_date":date,"reports":[report]})
    return [g for g in groups if len(g["reports"])>=2]

def incident_key(reports):
    # Stable while the smallest event ID remains in the candidate group.
    anchor=min((int(r["id"]) for r in reports if r.get("id") is not None),default=0)
    return "inc-"+str(anchor)

def summarize_group(group):
    reports=group["reports"]
    publishers=sorted({(r.get("domain") or r.get("source") or "unknown").strip().lower() for r in reports})
    dated=[(parse_date(r.get("seendate")) or parse_date(r.get("last_seen")) or parse_date(r.get("first_seen")),r) for r in reports]
    dated=[(dt,r) for dt,r in dated if dt]
    dated.sort(key=lambda x:x[0])
    timeline=[]
    for _,r in sorted(dated,key=lambda x:x[0]):
        timeline.append({"event_id":r.get("id"),"title":r.get("title"),"publisher":r.get("domain") or r.get("source"),"url":r.get("url"),"reported_at":(parse_date(r.get("seendate")) or parse_date(r.get("last_seen")) or parse_date(r.get("first_seen"))).isoformat()})
    return {
        "id":incident_key(reports),"headline":group["representative"],"report_count":len(reports),
        "publisher_count":len(publishers),"publishers":publishers,
        "first_reported":dated[0][0].isoformat() if dated else None,
        "last_reported":dated[-1][0].isoformat() if dated else None,"timeline":timeline,
        "evidence_note":"Publisher count is descriptive only. Syndication, shared wire copy, common sourcing and source independence have not been verified. Similar headlines may describe different events; analyst review is required.",
        "method":"Greedy Jaccard title-token similarity (threshold 0.72), 14-day anchor window; no semantic or factual verification."
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

def rebuild(conn,reports):
    """Rebuild only the current archive window; remove stale memberships/groups."""
    groups=group_reports(reports)
    summaries=[summarize_group(g) for g in groups]
    ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM giw_incident_reports")
        cur.execute("DELETE FROM giw_incidents")
        for s in summaries:
            cur.execute("""INSERT INTO giw_incidents(id,headline,first_reported,last_reported,report_count,publisher_count,evidence_note,method)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (s["id"],s["headline"],s["first_reported"],s["last_reported"],s["report_count"],s["publisher_count"],s["evidence_note"],s["method"]))
            for item in s["timeline"]:
                if item["event_id"] is not None:
                    cur.execute("INSERT INTO giw_incident_reports(event_id,incident_id) VALUES(%s,%s)",(item["event_id"],s["id"]))
    return summaries
