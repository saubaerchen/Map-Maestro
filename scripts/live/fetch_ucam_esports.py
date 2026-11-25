"""One-off: all UCAM games on the esports (tournament-account) route since 2026-05-01, any roster.

Seeds: UCAM #epval accounts seen in archived data + current roster names resolved on the esports route.
Snowballs: any 'UCAM ...' player found in a fetched game is added as a seed.
Output: data/raw/ucam_esports_since_2026-05_raw_responses.jsonl (kept separate from the core-filtered site data).

Extra window (appends, never rewrites): --since/--until/--map, e.g. the March 2026 Abyss games
  python scripts/live/fetch_ucam_esports.py --since 2026-03-01 --until 2026-04-01 --map Abyss
"""
import argparse, datetime, glob, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, api_get


def _ms(day):
    return int(datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


_ap = argparse.ArgumentParser()
_ap.add_argument("--since", default="2026-05-01")
_ap.add_argument("--until", help="exclusive end date; with it the run appends to OUT instead of rewriting")
_ap.add_argument("--map", action="append", help="keep only games on these maps (matchInfo.map)")
ARGS = _ap.parse_args()
CUTOFF_MS = _ms(ARGS.since)
UNTIL_MS = _ms(ARGS.until) if ARGS.until else None
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
        ml = api_get("/api/riot/match/v1/matchlists/by-puuid/esports/" + puuid)
        if ml is None:
            # api_get returns None after repeated 429s too; treating that as "no games" silently drops data
            sys.exit(f"matchlist failed for {seeds[puuid]} (rate limit or 404) — aborting, nothing written")
        hist = ml.get("history", [])
        new = [m for m in hist if m.get("gameStartTimeMillis", 0) >= CUTOFF_MS
               and (UNTIL_MS is None or m.get("gameStartTimeMillis", 0) < UNTIL_MS)]
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
        if any(is_ucam(p) for p in d.get("players", [])) and (not ARGS.map or d["matchInfo"].get("map") in ARGS.map):
            rows.append(d)
rows.sort(key=lambda d: d["matchInfo"].get("gameStartMillis", 0))
if UNTIL_MS is not None:
    have = {json.loads(l)["matchInfo"]["matchId"] for l in open(OUT, encoding="utf-8")} if os.path.exists(OUT) else set()
    add = [d for d in rows if d["matchInfo"]["matchId"] not in have]
    with open(OUT, "a", encoding="utf-8") as f:
        for d in add:
            f.write(json.dumps(d) + "\n")
    for d in add:
        ts = datetime.datetime.fromtimestamp(d["matchInfo"]["gameStartMillis"] / 1000, datetime.timezone.utc)
        print("appended", ts.strftime("%Y-%m-%d"), d["matchInfo"]["map"], d["matchInfo"]["matchId"])
    print(f"appended {len(add)} games ({len(rows) - len(add)} already present) -> {OUT}")
    sys.exit(0)
# keep games older than --since (e.g. the appended March Abyss window) when rewriting
older = [json.loads(l) for l in open(OUT, encoding="utf-8")] if os.path.exists(OUT) else []
older = [d for d in older if d["matchInfo"].get("gameStartMillis", 0) < CUTOFF_MS]
rows = older + rows
with open(OUT, "w", encoding="utf-8") as f:
    for d in rows:
        f.write(json.dumps(d) + "\n")
print("wrote", len(rows), "games ->", OUT)
