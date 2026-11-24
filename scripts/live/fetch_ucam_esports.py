"""One-off: all UCAM games on the esports (tournament-account) route since 2026-05-01, any roster.

Seeds: UCAM #epval accounts seen in archived data + current roster names resolved on the esports route.
Snowballs: any 'UCAM ...' player found in a fetched game is added as a seed.
Output: data/raw/ucam_esports_since_2026-05_raw_responses.jsonl (kept separate from the core-filtered site data).
"""
import datetime, glob, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, api_get

CUTOFF_MS = int(datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
OUT = os.path.join(ROOT, "data", "raw", "ucam_esports_since_2026-05_raw_responses.jsonl")
CACHE = os.path.join(ROOT, "data", "cache", "esports_matches")
os.makedirs(CACHE, exist_ok=True)
ROSTER = ["BULD", "Filu", "Flickless", "kamyk", "waddle"]


def is_ucam(p):
    return (p.get("gameName") or "").upper().startswith("UCAM ")


seeds = {}
for f in glob.glob(os.path.join(ROOT, "archive", "data", "raw", "*.jsonl")) + glob.glob(os.path.join(ROOT, "data", "raw", "*.jsonl")):
    for line in open(f, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        for p in d.get("players", []):
            if is_ucam(p) and p.get("tagLine") == "epval":
                seeds[p["puuid"]] = p["gameName"]
for name in ROSTER:
    acc = api_get("/api/riot/account/v1/accounts/by-riot-id/esports/" + urllib.parse.quote("UCAM " + name) + "/epval")
    print("resolve UCAM", name, "->", "ok" if acc else "not found", flush=True)
    if acc and acc.get("puuid"):
        seeds[acc["puuid"]] = acc.get("gameName", "UCAM " + name)

done, ids = set(), {}
while True:
    todo = [p for p in seeds if p not in done]
    if not todo:
        break
    for puuid in todo:
        done.add(puuid)
        hist = (api_get("/api/riot/match/v1/matchlists/by-puuid/esports/" + puuid) or {}).get("history", [])
        new = [m for m in hist if m.get("gameStartTimeMillis", 0) >= CUTOFF_MS]
        print(f"{seeds[puuid]}: {len(hist)} in history, {len(new)} since cutoff", flush=True)
        for m in new:
            ids[m["matchId"]] = m["gameStartTimeMillis"]
    for mid in sorted(ids, key=ids.get):
        path = os.path.join(CACHE, mid + ".json")
        if os.path.exists(path):
            d = json.load(open(path, encoding="utf-8"))
        else:
            d = api_get("/api/matches/esports/" + mid)
            if not d:
                print("  no detail:", mid, flush=True)
                continue
            json.dump(d, open(path, "w", encoding="utf-8"))
        for p in d.get("players", []):
            if is_ucam(p) and p["puuid"] not in seeds:
                seeds[p["puuid"]] = p["gameName"]
                print("  new UCAM account:", p["gameName"], flush=True)

rows = []
for mid in ids:
    path = os.path.join(CACHE, mid + ".json")
    if os.path.exists(path):
        d = json.load(open(path, encoding="utf-8"))
        if any(is_ucam(p) for p in d.get("players", [])):
            rows.append(d)
rows.sort(key=lambda d: d["matchInfo"].get("gameStartMillis", 0))
with open(OUT, "w", encoding="utf-8") as f:
    for d in rows:
        f.write(json.dumps(d) + "\n")
print("wrote", len(rows), "games ->", OUT)
