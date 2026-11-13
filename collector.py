"""GIW periodic collector. Requires DATABASE_URL; snapshots source records and revisions."""
import os,requests,feedparser,hashlib,concurrent.futures
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
("US CISA","https://www.cisa.gov/news.xml","cyber"),
("EU EEAS","https://www.eeas.europa.eu/rss_en.xml","official"),
("European Commission","https://ec.europa.eu/commission/presscorner/api/rss?language=en","official"),
("European Parliament","https://www.europarl.europa.eu/rss/doc/top-stories/en.xml","official"),
("WHO","https://www.who.int/rss-feeds/news-english.xml","health"),

("RFE/RL","https://www.rferl.org/api/z-pqpiev-qpp","media"),
("Euronews","https://www.euronews.com/rss?level=theme&name=news","media"),
("NPR World","https://feeds.npr.org/1004/rss.xml","media"),
("Sky News","https://feeds.skynews.com/feeds/rss/world.xml","media"),
("Kyiv Independent","https://kyivindependent.com/feed/","media"),
("Defense News","https://www.defensenews.com/arc/outboundfeeds/rss/","specialist"),
("Bellingcat","https://www.bellingcat.com/feed/","investigative"),
("GDACS","https://www.gdacs.org/xml/rss.xml","hazard"),]
def entries(url,name,cat):
 r=requests.get(url,headers=H,timeout=20);r.raise_for_status()
 f=feedparser.parse(r.content)
 if f.bozo and not f.entries:raise ValueError(str(f.bozo_exception)[:150])
 out=[]
 for e in f.entries[:50]:
  title=(e.get("title") or "").strip();link=e.get("link","")
  if title and link:out.append({"title":title,"url":link,"domain":name,"source":name,"category":cat,"seendate":e.get("published",e.get("updated","")),"kind":"feed"})
 return out
records=[];errors=[]
q=os.getenv("GIW_QUERY","(conflict OR military OR cyberattack OR sanctions OR terrorism OR infrastructure)")
try:
 d=requests.get("https://api.gdeltproject.org/api/v2/doc/doc",params={"query":q,"mode":"ArtList","format":"json","maxrecords":250,"timespan":"24h","sort":"HybridRel"},headers=H,timeout=40).json()
 records += [{**a,"source":"GDELT","category":"news","kind":"gdelt"} for a in d.get("articles",[])]
except Exception as e:errors.append("GDELT "+str(e)[:150])
def getfeed(spec):
 name,url,cat=spec
 try:return entries(url,name,cat),None
 except Exception as e:return [],name+" "+str(e)[:120]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for rec,err in ex.map(getfeed,FEEDS):
  records+=rec
  if err:errors.append(err)
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
