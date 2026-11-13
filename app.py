import os, json, psycopg, requests
from flask import Flask, jsonify, request, send_from_directory
from psycopg.rows import dict_row
app=Flask(__name__, static_folder="static")
DATABASE_URL=os.getenv("DATABASE_URL")
def db():
    if not DATABASE_URL: return None
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
def init_db():
    c=db()
    if not c:return
    with c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS events(
          id BIGSERIAL PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          domain TEXT, language TEXT, sourcecountry TEXT, seendate TEXT,
          first_seen TIMESTAMPTZ DEFAULT now(), last_seen TIMESTAMPTZ DEFAULT now(),
          payload JSONB DEFAULT '{}'::jsonb)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS event_revisions(
          id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id),
          observed_at TIMESTAMPTZ DEFAULT now(), payload JSONB NOT NULL)""")
@app.get("/")
def home(): return send_from_directory("static","index.html")
@app.get("/api/health")
def health():
    try:
        c=db()
        if c:
            with c,c.cursor() as cur: cur.execute("SELECT 1")
        return jsonify(status="ok",database=bool(c))
    except Exception as e:return jsonify(status="degraded",error=str(e)),503
@app.get("/api/search")
def search():
    q=request.args.get("q","conflict OR military OR cyberattack OR sanctions OR terrorism OR infrastructure")
    days=request.args.get("days","7")
    url="https://api.gdeltproject.org/api/v2/doc/doc"
    try:
        r=requests.get(url,params={"query":q,"mode":"ArtList","format":"json","maxrecords":75,"timespan":f"{days}d","sort":"HybridRel"},timeout=25)
        r.raise_for_status(); data=r.json()
        return jsonify(articles=data.get("articles",[]),source="GDELT",retrieved_at=data.get("queryDate"))
    except Exception as e:return jsonify(error="Upstream GDELT query failed",detail=str(e)),502
@app.get("/api/events")
def events():
    c=db()
    if not c:return jsonify(events=[],note="Database not configured")
    with c,c.cursor() as cur:
        cur.execute("SELECT id,url,title,domain,language,sourcecountry,seendate,first_seen,last_seen FROM events ORDER BY last_seen DESC LIMIT 500")
        return jsonify(events=cur.fetchall())
@app.get("/api/history/<int:event_id>")
def history(event_id):
    c=db()
    if not c:return jsonify(history=[],note="Database not configured")
    with c,c.cursor() as cur:
        cur.execute("SELECT observed_at,payload FROM event_revisions WHERE event_id=%s ORDER BY observed_at DESC LIMIT 100",(event_id,))
        return jsonify(history=cur.fetchall())
if os.getenv("DATABASE_URL"): 
    try:init_db()
    except Exception as e: print("DB init:",e)
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000)))
