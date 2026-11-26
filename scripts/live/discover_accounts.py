"""Steps 2-5: seed account -> customs -> match against VLR -> registry.

Two passes: private main accounts (route 'eu', customs) first; then, if VLR maps are still missing,
Riot tournament accounts (route 'esports', '{TAG} {name}#epval') used in later qualifier stages.
Registry entries record the route ('official'[matchId].route, accounts[puuid].route).

Usage:
  python scripts/live/discover_accounts.py --prefix sge [--seed "Name#TAG"] [--since 2026-09-01]

Needs data/registry/vlr/{prefix}.json (run vlr_matches.py first).
Seeds: --seed and/or accounts already confirmed for this team in data/registry/teams.json.
After a seed's games confirm its teammates, their accounts are scanned too.
"""
import argparse
import datetime
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ROOT, VLR_DIR, import_jsonl_to_cache, load_registry, match_detail,  # noqa: E402
                    match_history, norm, resolve_account, resolve_tournament_account, save_registry)

DAY_MS = 86400000


def vlr_maps(vlr):
    out = []
    for m in vlr["matches"]:
        if not m.get("utc"):
            continue
        ts = datetime.datetime.fromisoformat(m["utc"]).replace(tzinfo=datetime.UTC).timestamp() * 1000
        for mp in m["maps"]:
            groups = {}
            for p in mp["players"]:
                groups.setdefault(p["teamTag"], []).append(p)
            out.append({"ts": ts, "map": mp["map"], "score": sorted(mp["score"]), "groups": groups,
                        "url": m["url"], "event": m["event"], "teams": m["teams"], "gameId": mp["gameId"],
                        "teamNameByTag": {}})
    return out


def kda(p):
    s = p["stats"]
    return (s["kills"], s["deaths"], s["assists"])


def try_match(d, vmaps):
    """Return (vlr_map, {teamId: (tag, {puuid: proName})}) or None."""
    mi = d.get("matchInfo", {})
    rounds = d.get("roundResults") or []
    if len(rounds) < 10:
        return None
    rw = {t["teamId"]: t["roundsWon"] for t in d.get("teams", [])}
    score = sorted(rw.values())
    sides = {}
    for p in d["players"]:
        if p.get("teamId") in rw:
            sides.setdefault(p["teamId"], []).append(p)
    for vm in vmaps:
        if abs(vm["ts"] - mi.get("gameStartMillis", 0)) > 1.5 * DAY_MS:
            continue
        if norm(vm["map"]) != norm(mi.get("map")) or vm["score"] != score:
            continue
        assign = {}
        for team_id, plist in sides.items():
            got = Counter(kda(p) for p in plist)
            for tag, rows in vm["groups"].items():
                want = Counter((r["k"], r["d"], r["a"]) for r in rows)
                if got == want and len(rows) == len(plist):
                    names = {}
                    for p in plist:
                        cands = [r["name"] for r in rows if (r["k"], r["d"], r["a"]) == kda(p)]
                        names[p["puuid"]] = cands[0] if len(cands) == 1 else None
                    assign[team_id] = (tag, names)
                    break
        if assign:
            return vm, assign
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--since", default="2026-09-01")
    a = ap.parse_args()

    staged = glob.glob(os.path.join(ROOT, "data", "staging", "*.jsonl"))
    for f in staged:
        import_jsonl_to_cache(f)

    vlr = json.load(open(os.path.join(VLR_DIR, f"{a.prefix}.json"), encoding="utf-8"))
    vmaps = vlr_maps(vlr)
    tag_counts = Counter()
    for m in vlr["matches"]:
        if m.get("listTags"):
            tag_counts[m["listTags"][0]] += 1
    own_tag = tag_counts.most_common(1)[0][0] if tag_counts else None
    own_name = vlr["matches"][0]["listTeams"][0] if vlr["matches"] else a.prefix
    print(f"VLR: {len(vmaps)} maps for {own_name} [{own_tag}] since {a.since}")

    reg = load_registry()
    team = reg["teams"].setdefault(a.prefix, {})
    team.update({"name": own_name, "vlrTag": own_tag, "vlrTeamId": vlr.get("teamId")})
    team.setdefault("official", {})

    since_ms = datetime.datetime.fromisoformat(a.since).replace(tzinfo=datetime.UTC).timestamp() * 1000
    queue, scanned = [], set()
    for rid in a.seed:
        acc = resolve_account(rid)
        if not acc:
            print("seed not found:", rid)
            continue
        queue.append(acc["puuid"])
        reg["accounts"].setdefault(acc["puuid"], {"riotId": f'{acc["gameName"]}#{acc["tagLine"]}', "status": "candidate", "team": a.prefix, "evidence": []})
    for pu, acc in reg["accounts"].items():
        if own_tag and acc.get("team") == f"vlr:{own_tag}" and acc.get("status") == "confirmed":
            acc["team"] = a.prefix
        if acc.get("team") == a.prefix and acc.get("status") == "confirmed" and acc.get("route", "eu") == "eu":
            queue.append(pu)

    matched_games = {}

    def missing_maps():
        found = {v["gameId"] for v in team["official"].values()}
        return [vm for vm in vmaps if vm["gameId"] not in found]

    def scan(route, queue):
        # 'eu': private main accounts, official games are customs (queueId '').
        # 'esports': tournament accounts, which only play tournament games — every game is a candidate.
        while queue:
            pu = queue.pop(0)
            if pu in scanned:
                continue
            scanned.add(pu)
            hist = match_history(pu, route)
            games = [h["matchId"] for h in hist if h["gameStartTimeMillis"] >= since_ms
                     and (route == "esports" or h.get("queueId") == "")]
            who = reg["accounts"].get(pu, {}).get("riotId", pu[:10])
            print(f"scan [{route}] {who}: {len(games)} {'games' if route == 'esports' else 'customs'} since {a.since}")
            scan_games(route, games, queue)
            save_registry(reg)

    def scan_games(route, games, queue):
        for mid in games:
            if mid in matched_games:
                continue
            d = match_detail(mid, route)
            if not d:
                continue
            if route == "esports":
                # tournament lobbies list referees/observers (teamId Neutral); keep only the 10 players
                d = dict(d, players=[p for p in d["players"] if not p.get("isObserver") and p.get("teamId") in ("Red", "Blue")])
            res = try_match(d, vmaps)
            if not res:
                continue
            vm, assign = res
            matched_games[mid] = vm
            pmap = {p["puuid"]: p for p in d["players"]}
            for team_id, (tag, names) in assign.items():
                team_name = next((t for t in vm["teams"] if tag == own_tag and t == own_name), None)
                key = a.prefix if tag == own_tag else None
                for puuid, pro in names.items():
                    p = pmap[puuid]
                    acc = reg["accounts"].setdefault(puuid, {"evidence": []})
                    acc["riotId"] = f'{p["gameName"]}#{p["tagLine"]}'
                    acc.setdefault("seenAs", [])
                    if acc["riotId"] not in acc["seenAs"]:
                        acc["seenAs"].append(acc["riotId"])
                    acc["vlrTag"] = tag
                    acc["route"] = route
                    if pro:
                        acc["proName"] = pro
                    acc["status"] = "confirmed"
                    if key:
                        acc["team"] = key
                    elif "team" not in acc or acc.get("team") is None:
                        acc["team"] = f"vlr:{tag}"
                    ev = {"matchId": mid, "vlr": vm["url"], "map": vm["map"]}
                    if ev not in acc["evidence"]:
                        acc["evidence"].append(ev)
                    if key and puuid not in scanned and puuid not in queue:
                        queue.append(puuid)
            if any(tag == own_tag for tag, _ in assign.values()):
                team["official"][mid] = {"vlr": vm["url"], "gameId": vm["gameId"], "map": vm["map"],
                                         "event": vm["event"], "teams": vm["teams"], "route": route,
                                         "date": datetime.datetime.fromtimestamp(d["matchInfo"]["gameStartMillis"] / 1000, datetime.UTC).strftime("%Y-%m-%d")}

    scan("eu", queue)

    # Tournament accounts: later qualifier stages are played on Riot tournament accounts, not main accounts.
    # Seeds = this team's confirmed tournament accounts (also ones learned as opponents in other teams' games);
    # if there are none, try '{TAG} {VLR name}#epval' for the names on the team's VLR scoreboards.
    if missing_maps():
        tq = [pu for pu, acc in reg["accounts"].items()
              if acc.get("team") == a.prefix and acc.get("status") == "confirmed" and acc.get("route") == "esports"]
        if not tq and own_tag:
            names = []
            for vm in sorted(missing_maps(), key=lambda v: -v["ts"]):
                for r in vm["groups"].get(own_tag, []):
                    if r["name"] not in names:
                        names.append(r["name"])
            for n in names:
                acc = resolve_tournament_account(f"{own_tag} {n}#epval")
                print(f"tournament account {own_tag} {n}#epval:", "found" if acc else "not found")
                if acc:
                    tq.append(acc["puuid"])   # names that don't follow the pattern are found through the games
        scan("esports", tq)

    found ={v["gameId"] for v in team["official"].values()}
    print(f"\nofficial maps matched: {len(found)} / {len(vmaps)}")
    for vm in vmaps:
        if vm["gameId"] not in found:
            print(f"  MISSING {datetime.datetime.fromtimestamp(vm['ts']/1000, datetime.UTC):%Y-%m-%d} {vm['map']} {vm['score']} {vm['url']}")
    print("\nconfirmed accounts for", own_name)
    for pu, acc in reg["accounts"].items():
        if acc.get("team") == a.prefix and acc.get("status") == "confirmed":
            print(f'  {acc.get("proName", "?"):14} {acc["riotId"]:28} maps={len(acc["evidence"])}')
    others = Counter(acc.get("vlrTag") for acc in reg["accounts"].values() if acc.get("team", "").startswith("vlr:"))
    if others:
        print("opponent accounts confirmed by tag:", dict(others))
    save_registry(reg)


if __name__ == "__main__":
    main()
