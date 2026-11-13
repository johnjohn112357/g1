# Global Intelligence Watch (GIW)

Public-source intelligence discovery desk. **A lead collector, not an automated truth/attribution engine or emergency-alert system.**

## Live dashboard
https://global-intelligence-watch.onrender.com

## Current functionality
- Combined on-demand GDELT DOC 2.0 news search and public RSS/Atom source ingestion.
- Curated source-health registry with last-check status and per-feed errors.
- Keyword-filtered cross-source search, source labels, article timestamps, source links.
- Leaflet world map: explicitly approximate title-keyword regions for news (not incident geolocation) and exact reported coordinates for USGS earthquake features.
- USGS real-time GeoJSON earthquake feed and event links.
- Flask JSON endpoints: `/api/health`, `/api/search`, `/api/feeds`, `/api/sources`, `/api/hazards/earthquakes`, `/api/events`, `/api/history/<id>`.
- PostgreSQL schema for event deduplication, first/last seen and event revision snapshots.\n- Transparent headline triage, heuristic priority leads, title-similarity clusters and archive-based brief (`/api/analysis/brief`, `/api/analysis/triage`, `/api/analysis/clusters`).\n- CISA Known Exploited Vulnerabilities catalogue on demand (`/api/cyber/kev`) and persistent CVE snapshots in the collector.\n- Browser-opt-in notifications for newly observed archived high/critical keyword leads (only while the dashboard is open).\n- Region filters (Europe, UK, Middle East, Indo-Pacific, Africa, Americas) over title-keyword matches.
- Collector script (`python collector.py`) and a no-cost background polling thread: snapshots sources about every 15 minutes while the Render web instance is awake.
- Render Blueprint links the existing PostgreSQL connection string into the web service.

## Included source catalogue
Media: BBC World/Europe, Guardian World, Deutsche Welle, France 24, Al Jazeera, Euronews, NPR World, Sky News, Radio Free Europe/Radio Liberty.
Official/multilateral: UN News, NATO, Council of the EU, European Commission, UK Government, IAEA, US State Department, US Department of Defense.
Specialist / investigative: UK NCSC, US CISA, Defense News, Bellingcat.
Humanitarian/health/disaster: WHO, GDACS, USGS earthquake GeoJSON; ReliefWeb is linked manually (API requires approved appname).
Aggregator: GDELT DOC 2.0 (not itself a primary source).

Feeds are opportunistic, not guaranteed. The catalogue is a maintained starting set—not all internet sources. Sources may move/retire endpoints, block automated requests, publish only selected content, or be delayed. Feed health is displayed.

## Deployment and collection
- Web service is Render Free in Frankfurt; it can sleep when idle and cold-start on next request.
- Existing Render PostgreSQL is Free and has a stated expiry of **13 December 2026**; export/upgrade before that if you need durable retention.
- Database connection is provisioned by the Render Blueprint. Confirm service environment contains DATABASE_URL and `/api/health` reports database=true.
- A no-cost in-process collector runs about every 15 minutes while the web instance is awake. Render Free suspends the web instance after inactivity, so collection pauses while it sleeps and resumes after traffic. This is best-effort, not an always-on SLA. A continuously running collector requires paid always-on infrastructure or an external scheduler.
- Do not activate paid resources without explicit cost approval.

## Setup locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql://...'
python app.py
# In a second terminal:
python collector.py
```

## Analytic integrity / limitations
- A headline/article is not proof that an event happened.
- Official statements can be authoritative about what an institution said, but not automatically independent verification of its claims.
- Distinguish occurrence, attribution, intent, coordination, impact and forecast.
- Syndication/duplicate articles are not independent corroboration.
- News map regions are inferred from title keywords and may be false positives; never use as precise coordinates.
- No universal crawl: APIs, RSS/Atom, public accessibility, licensing, language coverage, robots/terms, paywalls, rate limits and provider outages constrain coverage. Do not scrape restricted services or bypass access controls.
- The brief, triage and clustering are transparent deterministic heuristics—not AI intelligence, validated risk scores, event confirmation or forecasting. Region assignment is title-keyword filtering and can be wrong. Notifications require the page to remain open; they are not push infrastructure or emergency warnings. CISA KEV inclusion means a CVE is known exploited in the wild somewhere, not that a local asset is affected. Tests cover analysis helper behavior, not provider availability or operational uptime. Human source checking remains required.
- Not classified intelligence, professional security advice, or a substitute for official emergency instructions.

## Source references / documentation
- [GDELT data and API overview](https://www.gdeltproject.org/data.html) — global news/event discovery and dataset descriptions.
- [ReliefWeb API documentation](https://apidoc.reliefweb.int/) — humanitarian reporting/disaster data; API use requires approved appname.
- [USGS GeoJSON feeds](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) — machine-readable earthquake data and feed update cadence.
- [UK NCSC advisories](https://www.ncsc.gov.uk/section/keep-up-to-date/reports-advisories)
- [CISA](https://www.cisa.gov/news.xml)
- [EU Council RSS](https://www.consilium.europa.eu/en/about-site/rss/)
- [UK Emergency Alerts](https://www.gov.uk/alerts) — actual life-threatening public warnings; GIW is not a replacement.
