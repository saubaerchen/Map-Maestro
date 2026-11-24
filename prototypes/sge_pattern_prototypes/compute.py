"""PROTOTYPE — throwaway. Computes Eintracht-only pattern data for the 7 feature prototypes.

Input:  data/site/sge_2026_raw_responses.jsonl (13 official maps, names normalised to 'SGE <pro>')
        data/registry/vlr/sge.json (VLR vetoes)
        maps_api_cache.json (valorant-api.com maps: transforms + callouts)
Output: dict consumed by build.py
"""
import json
import os
import sys
from collections import Counter, defaultdict
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "live"))
from lib.stats_engine import get_team_side_per_round  # noqa: E402
from site_config import MAP_TRANSFORMS  # noqa: E402
from lib.constants import AGENT_MAP  # noqa: E402

AGENT_NAMES = {k.lower(): v for k, v in AGENT_MAP.items()}

TAG = "SGE "
JSONL = os.path.join(ROOT, "data", "site", "sge_2026_raw_responses.jsonl")
VLR = os.path.join(ROOT, "data", "registry", "vlr", "sge.json")
TRADE_MS = 5000

API = {m["displayName"]: m for m in json.load(open(os.path.join(HERE, "maps_api_cache.json"), encoding="utf-8"))["data"]}
_W = json.load(open(os.path.join(HERE, "weapons_cache.json"), encoding="utf-8"))["data"]
WEAPONS = {w["uuid"].upper(): (w["displayName"], ((w.get("shopData") or {}).get("category") or "Sidearm").replace("Sniper Rifles", "Sniper")) for w in _W}


def norm_xy(map_name, x, y):
    t = MAP_TRANSFORMS[map_name]
    if t.get("swap_xy"):
        x, y = y, x
    return (y * t["xMultiplier"] + t["xScalarToAdd"]) * 100, (x * t["yMultiplier"] + t["yScalarToAdd"]) * 100


SUPER = {"Attacker Side": "T Spawn", "Defender Side": "CT Spawn"}


def callouts(map_name):
    out = []
    for c in API[map_name].get("callouts") or []:
        sup = SUPER.get(c["superRegionName"], c["superRegionName"])
        label = sup if sup.endswith("Spawn") else f'{sup} {c["regionName"]}'
        nx, ny = norm_xy(map_name, c["location"]["x"], c["location"]["y"])
        out.append({"label": label, "zone": sup, "x": c["location"]["x"], "y": c["location"]["y"], "nx": nx, "ny": ny})
    return out


_CALL = {}


def nearest(map_name, x, y):
    if map_name not in _CALL:
        _CALL[map_name] = callouts(map_name)
    best = min(_CALL[map_name], key=lambda c: (c["x"] - x) ** 2 + (c["y"] - y) ** 2)
    return best["label"], best["zone"]


def tier(avg, rnum):
    if rnum in (0, 12):
        return "pistol"
    if avg < 2000:
        return "eco"
    if avg < 3800:
        return "force"
    return "full"


def load_rounds():
    rounds, matches = [], []
    for line in open(JSONL, encoding="utf-8"):
        d = json.loads(line)
        mi = d["matchInfo"]
        mp = mi["map"]
        sge = [p for p in d["players"] if p["gameName"].startswith(TAG)]
        team_id = sge[0]["teamId"]
        puuids = {p["puuid"] for p in sge}
        name = {p["puuid"]: p["gameName"][len(TAG):] for p in d["players"] if p["puuid"] in puuids}
        agent_of = {p["puuid"]: p["characterId"] for p in sge}
        opp = Counter(p["gameName"].split(" ")[0] for p in d["players"] if p["teamId"] not in (team_id, "Neutral") and " " in p["gameName"]).most_common(1)
        opp = opp[0][0] if opp else "?"
        team_of = {p["puuid"]: p["teamId"] for p in d["players"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=d["roundResults"]), puuids)
        rw = {t["teamId"]: t["roundsWon"] for t in d["teams"]}
        date = __import__("datetime").datetime.fromtimestamp(mi["gameStartMillis"] / 1000).strftime("%Y-%m-%d")
        mrec = {"matchId": mi["matchId"], "map": mp, "date": date, "opp": opp,
                "score": f'{rw.get(team_id, 0)}-{sum(v for k, v in rw.items() if k != team_id)}'}
        matches.append(mrec)
        prev_won = None
        prev = None
        score = [0, 0]
        for rr in d["roundResults"]:
            rn = rr["roundNum"]
            kills = sorted([k for ps in rr["playerStats"] for k in (ps.get("kills") or [])], key=lambda k: k["timeSinceRoundStartMillis"])
            loads = [ps["economy"]["loadoutValue"] for ps in rr["playerStats"] if ps["puuid"] in puuids and ps.get("economy")]
            avg = sum(loads) / len(loads) if loads else 0
            oloads = [ps["economy"]["loadoutValue"] for ps in rr["playerStats"] if ps["puuid"] not in puuids and ps.get("economy") and team_of.get(ps["puuid"]) not in ("Neutral", None)]
            oavg = sum(oloads) / len(oloads) if oloads else 0
            weap = {}
            for ps in rr["playerStats"]:
                if ps["puuid"] in puuids and ps.get("economy"):
                    weap[name[ps["puuid"]]] = WEAPONS.get((ps["economy"].get("weapon") or "").upper(), ("?", "?"))
            opp_snipers = sum(1 for ps in rr["playerStats"] if ps["puuid"] not in puuids and ps.get("economy")
                              and WEAPONS.get((ps["economy"].get("weapon") or "").upper(), ("", ""))[1] == "Sniper")
            won = rr.get("winningTeam") == team_id
            fk = kills[0] if kills else None
            snap = []
            if fk:
                for pl in fk.get("playerLocations") or []:
                    if pl["puuid"] in puuids:
                        snap.append((pl["puuid"], pl["location"]["x"], pl["location"]["y"]))
                if fk["victim"] in puuids and fk.get("victimLocation"):
                    snap.append((fk["victim"], fk["victimLocation"]["x"], fk["victimLocation"]["y"]))
            pts = []
            for pu, x, y in snap:
                nx, ny = norm_xy(mp, x, y)
                lab, zone = nearest(mp, x, y)
                pts.append({"p": name[pu], "nx": round(nx, 2), "ny": round(ny, 2), "call": lab, "zone": zone})
            fk_info = None
            if fk:
                kx = next((pl["location"] for pl in fk.get("playerLocations") or [] if pl["puuid"] == fk["killer"]), None)
                vx = fk.get("victimLocation")
                fk_info = {"t": round(fk["timeSinceRoundStartMillis"] / 1000, 1),
                           "killer": name.get(fk["killer"]), "victim": name.get(fk["victim"]),
                           "sgeKill": fk["killer"] in puuids,
                           "killerCall": nearest(mp, kx["x"], kx["y"])[0] if kx else None,
                           "victimCall": nearest(mp, vx["x"], vx["y"])[0] if vx else None}
                traded = False
                if fk["victim"] in puuids:
                    traded = any(k["victim"] == fk["killer"] and k["timeSinceRoundStartMillis"] - fk["timeSinceRoundStartMillis"] <= TRADE_MS for k in kills[1:])
                fk_info["traded"] = traded
            ctx = "pistol" if rn in (0, 12) else ("after win" if prev_won else "after loss")
            rounds.append({
                "matchId": mi["matchId"], "map": mp, "date": date, "opp": opp, "round": rn + 1,
                "side": "CT" if sides.get(rn) == "def" else "T", "won": won, "tier": tier(avg, rn), "ctx": ctx,
                "avgLoadout": round(avg), "plantSite": rr.get("plantSite") or None,
                "plantT": round(rr["plantRoundTime"] / 1000, 1) if rr.get("plantSite") else None,
                "plantedBySge": rr.get("bombPlanter") in puuids if rr.get("bombPlanter") else None,
                "fk": fk_info, "snap": pts, "fkT": round(kills[0]["timeSinceRoundStartMillis"] / 1000, 1) if kills else None,
                "agents": {name[pu]: agent_of[pu] for pu in puuids},
                "weapons": {p: w[0] for p, w in weap.items()}, "wcat": {p: w[1] for p, w in weap.items()},
                "agentNames": {name[pu]: AGENT_NAMES.get(agent_of[pu].lower(), "?") for pu in puuids},
                "plantXY": ([round(v, 2) for v in norm_xy(mp, rr["plantLocation"]["x"], rr["plantLocation"]["y"])]
                            if rr.get("plantSite") and rr.get("plantLocation") else None),
                "oppTier": tier(oavg, rn), "oppAvg": round(oavg), "oppSnipers": opp_snipers,
                "scoreBefore": list(score), "half": "1st" if rn < 12 else ("2nd" if rn < 24 else "OT"),
                "prevPlant": prev["plantSite"] if prev and prev["side"] == ("CT" if sides.get(rn) == "def" else "T") else None,
                "prevSameSideWon": prev["won"] if prev and prev["side"] == ("CT" if sides.get(rn) == "def" else "T") else None,
            })
            prev = {"plantSite": rr.get("plantSite") or None, "side": "CT" if sides.get(rn) == "def" else "T", "won": won}
            score[0 if won else 1] += 1
            prev_won = won
    return rounds, matches


def fingerprint(snap):
    c = Counter(p["zone"] for p in snap)
    order = ["A", "Mid", "B", "C", "CT Spawn", "T Spawn"]
    return " · ".join(f"{z} {c[z]}" for z in order if c.get(z))


def compute():
    rounds, matches = load_rounds()
    maps = sorted({r["map"] for r in rounds}, key=lambda m: -sum(1 for x in matches if x["map"] == m))
    calls = {m: callouts(m) for m in maps}
    for r in rounds:
        r["fp"] = fingerprint(r["snap"]) if r["snap"] else None
    vetoes = json.load(open(VLR, encoding="utf-8"))["matches"]
    return {"team": "Eintracht Frankfurt", "maps": maps, "matches": matches, "rounds": rounds,
            "callouts": calls, "vetoes": [{"date": m["listDate"], "opp": m["listTeams"][1], "oppTag": (m.get("listTags") or ["", "?"])[1],
                                            "event": m["event"], "veto": (m.get("veto") or [None])[0], "result": m["result"],
                                            "maps": [{"map": mp["map"], "teams": mp["teams"], "score": mp["score"]} for mp in m["maps"]]}
                                           for m in vetoes]}


if __name__ == "__main__":
    d = compute()
    print(len(d["rounds"]), "rounds;", d["maps"], Counter((r["map"], r["side"]) for r in d["rounds"]))
    print(Counter(r["fp"] for r in d["rounds"] if r["side"] == "CT" and r["map"] == "Split").most_common(5))
