import os,requests,psycopg,json,time
from psycopg.types.json import Jsonb
DB=os.getenv("DATABASE_URL")
if not DB: raise SystemExit("DATABASE_URL required")
q=os.getenv("GIW_QUERY","conflict OR military OR cyberattack OR sanctions OR terrorism OR infrastructure")
data=requests.get("https://api.gdeltproject.org/api/v2/doc/doc",params={"query":q,"mode":"ArtList","format":"json","maxrecords":250,"timespan":"24h","sort":"HybridRel"},timeout=40).json()
with psycopg.connect(DB) as c:
 with c.cursor() as cur:
  for a in data.get("articles",[]):
   url=a.get("url"); title=a.get("title")
   if not url or not title: continue
   cur.execute("""INSERT INTO events(url,title,domain,language,sourcecountry,seendate,payload)
    VALUES(%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT(url) DO UPDATE SET title=excluded.title,domain=excluded.domain,
    language=excluded.language,sourcecountry=excluded.sourcecountry,seendate=excluded.seendate,
    last_seen=now(),payload=excluded.payload RETURNING id""",
    (url,title,a.get("domain"),a.get("language"),a.get("sourcecountry"),a.get("seendate"),Jsonb(a)))
   eid=cur.fetchone()[0]
   cur.execute("INSERT INTO event_revisions(event_id,payload) VALUES(%s,%s)",(eid,Jsonb(a)))
 print("Ingested",len(data.get("articles",[])),"records")
