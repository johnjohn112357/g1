"""GIW transparent heuristic analysis helpers. No LLM claims or hidden confidence scores."""
import re
from collections import Counter
from datetime import datetime, timezone

RISK_TERMS = {
    "critical": ["nuclear", "radiological", "chemical weapon", "biological weapon", "mass casualty", "strategic attack"],
    "high": ["invasion", "missile", "airstrike", "drone strike", "mobilization", "coup", "terror attack", "cyberattack", "blackout", "pipeline explosion", "submarine cable", "hostage", "naval blockade"],
    "medium": ["sanction", "military exercise", "troops", "detained", "protest", "election", "ceasefire", "evacuation", "earthquake", "flood", "wildfire"],
}
THEMES = {
    "Conflict & military": ["war", "military", "army", "troops", "missile", "drone", "strike", "attack", "frontline", "battle", "navy", "air force"],
    "Diplomacy & governance": ["minister", "president", "summit", "diplomacy", "election", "government", "parliament", "sanction", "treaty", "ceasefire"],
    "Cyber & technology": ["cyber", "hack", "ransomware", "malware", "vulnerability", "internet", "data breach", "satellite", "gnss"],
    "Critical infrastructure": ["power", "electricity", "grid", "pipeline", "port", "rail", "airport", "cable", "water", "telecom", "blackout"],
    "Humanitarian & health": ["humanitarian", "displaced", "refugee", "hospital", "outbreak", "health", "aid", "famine", "casualties"],
    "Disasters": ["earthquake", "flood", "wildfire", "storm", "cyclone", "volcano", "tsunami"],
}
def classify(title):
    t=(title or "").lower()
    levels=[(level,terms) for level,terms in RISK_TERMS.items()]
    for level,terms in levels:
        hits=[x for x in terms if x in t]
        if hits:return {"heuristic_level":level,"matched_terms":hits,"method":"keyword screen"}
    return {"heuristic_level":"routine","matched_terms":[],"method":"keyword screen"}
def theme(title):
    t=(title or "").lower()
    return [name for name,terms in THEMES.items() if any(x in t for x in terms)] or ["General"]
def cluster_events(events):
    """Conservative title-token similarity clusters; never asserts event identity."""
    stop={"the","and","for","with","from","that","this","after","over","into","says","said","report","reported","reports","according","update","updates","breaking"}
    groups=[]
    for e in events:
        title=e.get("title") or ""
        words=set(re.findall(r"[a-z0-9]{3,}",title.lower()))-stop
        if not words:continue
        match=None
        for g in groups:
            overlap=len(words & g["tokens"])/max(1,min(len(words),len(g["tokens"])))
            if overlap>=0.70:
                match=g;break
        if match:
            match["items"].append(e);match["tokens"]|=words
        else:groups.append({"tokens":words,"items":[e]})
    out=[]
    for g in groups:
        items=g["items"]
        if len(items)<2:continue
        out.append({"label":items[0].get("title","Related reports"),"reports":len(items),"sources":sorted({str(x.get("source") or x.get("domain") or "unknown") for x in items}),"items":items[:8],"note":"Title-token similarity only; review before treating as one incident."})
    return sorted(out,key=lambda x:(x["reports"],len(x["sources"])),reverse=True)[:40]
def build_brief(events):
    now=datetime.now(timezone.utc)
    counts=Counter();levels=Counter();themes=Counter();highlights=[]
    for e in events:
        title=e.get("title","")
        c=classify(title);levels[c["heuristic_level"]]+=1
        for t in theme(title):themes[t]+=1
        counts[str(e.get("category") or "uncategorized")]+=1
        if c["heuristic_level"] in ("critical","high"):
            highlights.append({"title":title,"source":e.get("source") or e.get("domain"),"url":e.get("url"),"level":c["heuristic_level"],"terms":c["matched_terms"],"seendate":e.get("seendate")})
    highlights=highlights[:20]
    return {"generated_at":now.isoformat(),"sample_size":len(events),"method":"Transparent keyword-based triage of stored headlines; not AI analysis, verified facts, or a forecast.","headline":"Stored reporting is concentrated in "+(", ".join(f"{k} ({v})" for k,v in themes.most_common(3)) or "general coverage")+".","category_counts":dict(counts),"heuristic_counts":dict(levels),"theme_counts":dict(themes),"priority_leads":highlights,"caveat":"Keyword matches are triage signals only. Headlines can omit context, contain false claims, or use terms metaphorically. Check primary documents and independent reporting."}

def build_evidence(events):
    """Evidence review index: source diversity and time spread, not truth scoring."""
    clusters=cluster_events(events)
    out=[]
    for c in clusters:
        items=c["items"]
        domains=sorted({str(x.get("domain") or x.get("source") or "unknown").lower() for x in items})
        dates=[]
        for x in items:
            raw=x.get("seendate") or x.get("last_seen") or x.get("first_seen")
            if raw:
                try: dates.append(datetime.fromisoformat(str(raw).replace("Z","+00:00")))
                except Exception: pass
        spread=(max(dates)-min(dates)).total_seconds()/3600 if len(dates)>1 else 0
        out.append({"headline":c["label"],"reports":len(items),"distinct_source_labels":len(domains),"source_labels":domains[:12],"time_spread_hours":round(spread,1),"priority":classify(c["label"])["heuristic_level"],"matched_terms":classify(c["label"])["matched_terms"],"report_links":[{"title":x.get("title"),"source":x.get("source") or x.get("domain"),"url":x.get("url"),"date":x.get("seendate") or x.get("last_seen")} for x in items[:8]],"assessment":"Multiple stored reports with similar headline wording; source independence and factual corroboration have not been verified."})
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"method":"Title similarity + distinct source labels + reported timestamp spread. No claim verification, source-independence audit, or truth probability.","items":out[:30],"caveat":"Syndicated stories can appear under different outlets; source labels are not proof of independent corroboration. Open source documents and compare facts."}
