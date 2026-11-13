"""GIW periodic collector. Requires DATABASE_URL; snapshots source records and revisions."""
import os,requests,xml.etree.ElementTree as ET,hashlib
from datetime import datetime,timezone
import psycopg
from psycopg.types.json import Jsonb
DB=os.getenv("DATABASE_URL")
if not DB:raise SystemExit("DATABASE_URL required")
H={"User-Agent":"GlobalIntelligenceWatch/1.0 (source monitoring)"}
FEEDS=[
("BBC World","https://feeds.bbci.co.uk/news/world/rss.xml","media"),
("BBC Europe","https://feeds.bbci.co.uk/news/world/europe/rss.xml","media"),
("Guardian World","https://www.theguardian.com/world/rss","media"),
("DW","https://rss.dw.com/rdf/rss-en-world","media"),
("France 24","https://www.france24.com/en/rss","media"),
("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml","media"),
("UN News","https://news.un.org/feed/subscribe/en/news/all/rss.xml","multilateral"),
("NATO","https://www.nato.int/cps/en/natohq/news.htm?query=&search=1&display_mode=rss","official"),
("EU Council","https://www.consilium.europa.eu/en/press/press-releases/rss/","official"),
("UK Government","https://www.gov.uk/government/announcements.atom","official"),
("UK NCSC","https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml","cyber"),
("US CISA","https://www.cisa.gov/news.xml","cyber")]
def entries(url,name,cat):
 out=[];root=ET.fromstring(requests.get(url,headers=H,timeout=15).content)
 items=root.findall(".//item") or root.findall(".//{*}entry")
 for it in items[:50]:
  def val(tag):
   el=it.find(tag) or it.find("{*}"+tag);return (el.text or "").strip() if el is not None else ""
  link=val("link")
  if not link:
   el=it.find("{*}link");link=el.attrib.get("href","") if el is not None else ""
  title=val("title")
  if title and link:out.append({"title":title,"url":link,"domain":name,"source":name,"category":cat,"seendate":val("pubDate") or val("updated"),"kind":"feed"})
 return out
records=[];errors=[]
q=os.getenv("GIW_QUERY","conflict OR military OR cyberattack OR sanctions OR terrorism OR infrastructure")
try:
 d=requests.get("https://api.gdeltproject.org/api/v2/doc/doc",params={"query":q,"mode":"ArtList","format":"json","maxrecords":250,"timespan":"24h","sort":"HybridRel"},headers=H,timeout=40).json()
 records += [{**a,"source":"GDELT","category":"news","kind":"gdelt"} for a in d.get("articles",[])]
except Exception as e:errors.append("GDELT "+str(e)[:150])
for name,url,cat in FEEDS:
 try:records+=entries(url,name,cat)
 except Exception as e:errors.append(name+" "+str(e)[:120])
try:
 z=requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",headers=H,timeout=20).json()
 for x in z.get("features",[]):
  p=x.get("properties",{});g=x.get("geometry",{});coords=g.get("coordinates",[])
  records.append({"title":p.get("title","Earthquake"),"url":p.get("url"),"domain":"USGS","source":"USGS","category":"hazard","seendate":datetime.fromtimestamp(p.get("time",0)/1000,timezone.utc).isoformat(),"latitude":coords[1] if len(coords)>1 else None,"longitude":coords[0] if coords else None,"payload":x,"kind":"geojson"})
except Exception as e:errors.append("USGS "+str(e)[:150])
with psycopg.connect(DB) as c:
 with c.cursor() as cur:
  cur.execute("""CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY,url TEXT UNIQUE NOT NULL,title TEXT NOT NULL,domain TEXT,source TEXT,category TEXT,language TEXT,sourcecountry TEXT,seendate TEXT,latitude DOUBLE PRECISION,longitude DOUBLE PRECISION,first_seen TIMESTAMPTZ DEFAULT now(),last_seen TIMESTAMPTZ DEFAULT now(),payload JSONB DEFAULT '{}'::jsonb)""")
  cur.execute("""CREATE TABLE IF NOT EXISTS event_revisions(id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id),observed_at TIMESTAMPTZ DEFAULT now(),payload JSONB NOT NULL)""")
  for a in records:
   url=a.get("url");title=a.get("title")
   if not url or not title:continue
   cur.execute("""INSERT INTO events(url,title,domain,source,category,language,sourcecountry,seendate,latitude,longitude,payload)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT(url) DO UPDATE SET title=excluded.title,domain=excluded.domain,source=excluded.source,category=excluded.category,language=excluded.language,sourcecountry=excluded.sourcecountry,seendate=excluded.seendate,latitude=excluded.latitude,longitude=excluded.longitude,last_seen=now(),payload=excluded.payload RETURNING id""",
    (url,title,a.get("domain"),a.get("source"),a.get("category"),a.get("language"),a.get("sourcecountry"),a.get("seendate"),a.get("latitude"),a.get("longitude"),Jsonb(a)))
   eid=cur.fetchone()[0]
   cur.execute("INSERT INTO event_revisions(event_id,payload) VALUES(%s,%s)",(eid,Jsonb(a)))
print("GIW collector:",len(records),"records;",len(errors),"source errors")
for e in errors:print("SOURCE ERROR:",e)
