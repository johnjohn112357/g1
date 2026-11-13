import os, json, time, hashlib, concurrent.futures, xml.etree.ElementTree as ET, threading, subprocess, sys
from datetime import datetime, timezone
import psycopg, requests, feedparser
from flask import Flask, jsonify, request, send_from_directory
from psycopg.rows import dict_row

app=Flask(__name__,static_folder="static")
DATABASE_URL=os.getenv("DATABASE_URL")
HTTP=requests.Session()
HTTP.headers.update({"User-Agent":"GlobalIntelligenceWatch/1.0 (public-source research dashboard)"})
CACHE={}
CACHE_TTL=300
FEEDS=[
 {"id":"bbc-world","name":"BBC World","url":"https://feeds.bbci.co.uk/news/world/rss.xml","type":"media","region":"Global"},
 {"id":"bbc-europe","name":"BBC Europe","url":"https://feeds.bbci.co.uk/news/world/europe/rss.xml","type":"media","region":"Europe"},
 {"id":"guardian-world","name":"The Guardian World","url":"https://www.theguardian.com/world/rss","type":"media","region":"Global"},
 {"id":"dw-world","name":"Deutsche Welle","url":"https://rss.dw.com/rdf/rss-en-world","type":"media","region":"Global"},
 {"id":"france24","name":"France 24","url":"https://www.france24.com/en/rss","type":"media","region":"Global"},
 {"id":"aljazeera","name":"Al Jazeera","url":"https://www.aljazeera.com/xml/rss/all.xml","type":"media","region":"Global"},
 {"id":"un-news","name":"UN News","url":"https://news.un.org/feed/subscribe/en/news/all/rss.xml","type":"multilateral","region":"Global"},
 {"id":"nato","name":"NATO News","url":"https://www.nato.int/cps/en/natohq/news.htm?query=&search=1&display_mode=rss","type":"official","region":"Global"},
 {"id":"eu-council","name":"Council of the EU","url":"https://www.consilium.europa.eu/en/press/press-releases/rss/","type":"official","region":"Europe"},
 {"id":"uk-gov","name":"UK Government","url":"https://www.gov.uk/government/announcements.atom","type":"official","region":"UK"},
 {"id":"uk-ncsc","name":"UK NCSC","url":"https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml","type":"cyber","region":"UK"},
 {"id":"cisa","name":"US CISA","url":"https://www.cisa.gov/news.xml","type":"cyber","region":"US"},
{"id":"eeas","name":"EU External Action Service","url":"https://www.eeas.europa.eu/rss_en.xml","type":"official","region":"Europe"},
 {"id":"eu-commission","name":"European Commission","url":"https://ec.europa.eu/commission/presscorner/api/rss?language=en","type":"official","region":"Europe"},
 {"id":"eu-parliament","name":"European Parliament","url":"https://www.europarl.europa.eu/rss/doc/top-stories/en.xml","type":"official","region":"Europe"},
 {"id":"who","name":"WHO News","url":"https://www.who.int/rss-feeds/news-english.xml","type":"health","region":"Global"},
 {"id":"reliefweb","name":"ReliefWeb Updates","url":"https://reliefweb.int/updates/rss.xml","type":"humanitarian","region":"Global"},
 {"id":"rferl","name":"Radio Free Europe/Radio Liberty","url":"https://www.rferl.org/api/z-pqpiev-qpp","type":"media","region":"Global"},
 {"id":"euronews","name":"Euronews","url":"https://www.euronews.com/rss?level=theme&name=news","type":"media","region":"Europe"},
 {"id":"npr-world","name":"NPR World","url":"https://feeds.npr.org/1004/rss.xml","type":"media","region":"Global"},
 {"id":"sky","name":"Sky News","url":"https://feeds.skynews.com/feeds/rss/world.xml","type":"media","region":"Global"},
 {"id":"kyiv-independent","name":"The Kyiv Independent","url":"https://kyivindependent.com/feed/","type":"media","region":"Ukraine"},
 {"id":"defensenews","name":"Defense News","url":"https://www.defensenews.com/arc/outboundfeeds/rss/","type":"specialist","region":"Global"},
 {"id":"bellingcat","name":"Bellingcat","url":"https://www.bellingcat.com/feed/","type":"investigative","region":"Global"},
 {"id":"gdacs","name":"GDACS Disasters","url":"https://www.gdacs.org/xml/rss.xml","type":"hazard","region":"Global"},
 {"id":"usgs","name":"USGS Earthquakes (GeoJSON)","url":"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson","type":"hazard","region":"Global"}
]
def db():
 return psycopg.connect(DATABASE_URL,row_factory=dict_row) if DATABASE_URL else None
def init_db():
 c=db()
 if not c:return
 with c,c.cursor() as cur:
  cur.execute("""CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY,url TEXT UNIQUE NOT NULL,title TEXT NOT NULL,domain TEXT,source TEXT,category TEXT,language TEXT,sourcecountry TEXT,seendate TEXT,latitude DOUBLE PRECISION,longitude DOUBLE PRECISION,first_seen TIMESTAMPTZ DEFAULT now(),last_seen TIMESTAMPTZ DEFAULT now(),payload JSONB DEFAULT '{}'::jsonb)""")
  cur.execute("""CREATE TABLE IF NOT EXISTS event_revisions(id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id),observed_at TIMESTAMPTZ DEFAULT now(),payload JSONB NOT NULL)""")
  cur.execute("CREATE INDEX IF NOT EXISTS events_last_seen_idx ON events(last_seen DESC)")
  cur.execute("CREATE INDEX IF NOT EXISTS revisions_event_idx ON event_revisions(event_id,observed_at DESC)")
def clean_text(x):
 return " ".join((x or "").split())[:2000]
def parse_feed(src):
 now=time.time();cached=CACHE.get(src["id"])
 if cached and now-cached[0]<CACHE_TTL:return cached[1]
 try:
  r=HTTP.get(src["url"],timeout=15);r.raise_for_status()
  parsed=feedparser.parse(r.content)
  if parsed.bozo and not parsed.entries:raise ValueError(str(parsed.bozo_exception)[:150])
  out=[]
  for e in parsed.entries[:50]:
   title=clean_text(e.get("title",""));link=e.get("link","")
   if title and link:out.append({"title":title,"url":link,"domain":src["name"],"source":src["id"],"category":src["type"],"region":src["region"],"seendate":e.get("published",e.get("updated","")),"snippet":clean_text(e.get("summary",""))[:500],"kind":"feed"})
  result={"status":"ok","articles":out,"checked":datetime.now(timezone.utc).isoformat(),"warning":str(parsed.bozo_exception)[:120] if parsed.bozo else None}
 except Exception as e:result={"status":"error","articles":[],"error":str(e)[:180],"checked":datetime.now(timezone.utc).isoformat()}
 CACHE[src["id"]]=(now,result);return result
@app.get("/")
def home():return send_from_directory("static","index.html")
@app.get("/api/health")
def health():
 try:
  c=db()
  if c:
   with c,c.cursor() as cur:cur.execute("SELECT 1")
  return jsonify(status="ok",database=bool(c),sources=len(FEEDS),version="1.1")
 except Exception as e:return jsonify(status="degraded",error=str(e)[:180]),503
@app.get("/api/sources")
def sources():
 statuses=[]
 for s in FEEDS:
  c=CACHE.get(s["id"])
  statuses.append({**s,"last_checked":datetime.fromtimestamp(c[0],timezone.utc).isoformat() if c else None,"status":c[1]["status"] if c else "not_checked","items":len(c[1]["articles"]) if c else None,"error":c[1].get("error") if c else None})
 statuses.insert(0,{"id":"gdelt","name":"GDELT DOC 2.0","url":"https://api.gdeltproject.org/api/v2/doc/doc","type":"aggregator","region":"Global","status":"on_demand","description":"Global multilingual news index; not a primary source"})
 statuses.insert(1,{"id":"usgs-live","name":"USGS earthquake GeoJSON","url":"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson","type":"hazard","region":"Global","status":"on_demand"})
 return jsonify(sources=statuses,source_count=len(statuses),note="Source availability is tested on fetch; this is a curated starter catalogue, not every online source.")
@app.get("/api/feeds")
def feeds():
 ids=request.args.get("sources","").split(",") if request.args.get("sources") else [s["id"] for s in FEEDS]
 selected=[s for s in FEEDS if s["id"] in ids]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: results=list(ex.map(parse_feed,selected))
 articles=[a for r in results for a in r["articles"]]
 return jsonify(articles=articles,feeds=[{"id":s["id"],"status":r["status"],"count":len(r["articles"]),"error":r.get("error")} for s,r in zip(selected,results)],retrieved_at=datetime.now(timezone.utc).isoformat())
@app.get("/api/search")
def search():
 q=request.args.get("q","conflict OR military OR cyberattack OR sanctions OR terrorism OR infrastructure")
 days=max(1,min(30,int(request.args.get("days","7"))))
 limit=max(10,min(250,int(request.args.get("limit","100"))))
 try:
  r=HTTP.get("https://api.gdeltproject.org/api/v2/doc/doc",params={"query":q,"mode":"ArtList","format":"json","maxrecords":limit,"timespan":f"{days}d","sort":"HybridRel"},timeout=30);r.raise_for_status();data=r.json()
  gd=[{**a,"source":"gdelt","category":"news","kind":"gdelt"} for a in data.get("articles",[])]
 except Exception as e:gd=[];gd_error=str(e)[:180]
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:rs=list(ex.map(parse_feed,FEEDS))
  feed=[a for z in rs for a in z["articles"]]
 except Exception:feed=[]
 terms=[x.lower() for x in q.replace(" OR "," ").replace(" AND "," ").split() if len(x)>2 and x.upper() not in ("OR","AND","NOT")]
 if terms:feed=[a for a in feed if any(t in (a["title"]+" "+a.get("snippet","")).lower() for t in terms)]
 merged={a.get("url"):a for a in feed+gd if a.get("url")}
 articles=sorted(merged.values(),key=lambda x:x.get("seendate",""),reverse=True)
 return jsonify(articles=articles[:limit],counts={"gdelt":len(gd),"feeds":len(feed),"merged":len(articles)},source="GDELT + public RSS/Atom feeds",retrieved_at=datetime.now(timezone.utc).isoformat(),gdelt_error=locals().get("gd_error"))
@app.get("/api/hazards/earthquakes")
def quakes():
 try:
  r=HTTP.get(FEEDS[-1]["url"],timeout=15);r.raise_for_status();return jsonify(r.json())
 except Exception as e:return jsonify(error=str(e)[:180]),502
@app.get("/api/events")
def events():
 c=db()
 if not c:return jsonify(events=[],note="PostgreSQL not connected; live feeds still work")
 with c,c.cursor() as cur:
  cur.execute("SELECT id,url,title,domain,source,category,sourcecountry,seendate,first_seen,last_seen FROM events ORDER BY last_seen DESC LIMIT 500")
  return jsonify(events=cur.fetchall())
@app.get("/api/history/<int:event_id>")
def history(event_id):
 c=db()
 if not c:return jsonify(history=[],note="Database not connected")
 with c,c.cursor() as cur:
  cur.execute("SELECT observed_at,payload FROM event_revisions WHERE event_id=%s ORDER BY observed_at DESC LIMIT 100",(event_id,))
  return jsonify(history=cur.fetchall())
if DATABASE_URL:
 try:init_db()
 except Exception as e:print("DB init failed:",str(e)[:200])
# No extra paid worker: collect periodically while the free web instance is awake.
def background_collection():
 interval=max(300,int(os.getenv("GIW_COLLECT_INTERVAL_SECONDS","900")))
 time.sleep(10)
 while True:
  try:
   p=subprocess.run([sys.executable,"collector.py"],capture_output=True,text=True,timeout=480)
   print("GIW background collector:",(p.stdout or p.stderr)[-1800:])
  except Exception as e:print("GIW background collector error:",str(e)[:300])
  time.sleep(interval)
if DATABASE_URL and os.getenv("GIW_BACKGROUND_COLLECTOR","true").lower() in ("1","true","yes"):
 threading.Thread(target=background_collection,name="giw-collector",daemon=True).start()
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000)))
