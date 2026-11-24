"""Extract SGE vs CGN Lotus (2026-04-19) match into a replay data JS bundle."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSONL = ROOT / "data/raw/sge_2026_raw_responses.jsonl"
OUT   = ROOT / "veto-history-site-publish/lotus-replay-data.js"

MAP_TRANSFORM = {
    "xMul": 7.2e-05,  "yMul": -7.2e-05,
    "xAdd": 0.454789, "yAdd":  0.917752,
}

WEAPONS = {
    "9C82E19D-4575-0200-1A81-3EACF00CF872": "Phantom",
    "EE8E8D15-496B-07AC-E5F6-8FAE5D4C7B1A": "Vandal",
    "EE8362C6-4735-098D-5447-8F8EFFF4C0DB": "Vandal",
    "AE3DE142-4D85-2547-DD26-4E90BED35CF7": "Sheriff",
    "A03B24D3-4319-996D-0F8C-94BBFBA1DFC7": "Operator",
    "44D4E95C-4157-0037-81B2-17841BF2E8E3": "Guardian",
    "910BE174-449B-C412-AB22-D0873436B21B": "Ghost",
    "29A0CFAB-485B-F5D5-779A-B59F85E204A8": "Classic",
    "462080D1-4035-2937-7C09-27AA2A5C27A7": "Frenzy",
    "462080D1-4035-2937-7C09-27AA2A08C7FB": "Frenzy",
    "42DA8CCC-40D5-AFFC-BEEC-15AA47B42EDA": "Odin",
    "63E6C2B6-4A8E-869C-3D4C-E38355226584": "Ares",
    "55D8A0F4-4274-CA67-FE2C-06AB45EFDF58": "Bulldog",
    "F7E1B454-4AD4-1063-EC0A-159E56B58941": "Marshal",
    "D3615EDE-4066-4B22-A6F1-E48BF6E67B25": "Outlaw",
    "2F59173C-4BED-B6C3-2191-DEA9B58BE9C7": "Bucky",
    "EC845BF4-4F79-DDDA-A3DA-0DB3D5FB9896": "Judge",
    "C4883E50-4494-202C-3EC3-6B8A9284F00B": "Shorty",
    "707B0AB2-4EDA-6F00-EDA4-69AF04FB9F06": "Stinger",
    "F9DB80BA-4853-6BA3-F692-13F6BBE8C18A": "Spectre",
    "1BAA85B4-4C70-1284-64BB-6481DFC3BB4E": "Knife",
    "410B2E0B-4CEB-1321-1727-20858F7F3477": "Knife",
    "4ADE7FAA-4CF1-8376-95EF-39884480959B": "Knife",
    "5F0AAF7A-4289-3998-D5FF-EB9A5CF7EF5C": "Knife",
    "E336C6B8-418D-9340-D77F-7A9E4CFE0702": "Knife",
}

SGE_COLORS = {
    "SGE Jamelinho": "#e53935",
    "SGE Fizzy":     "#f1d500",
    "SGE MONSTEERR": "#00e676",
    "SGE azury":     "#ff4dac",
    "SGE musashi":   "#1f4fd6",
}
CGN_COLORS = ["#ff6b35", "#a855f7", "#06b6d4", "#f97316", "#84cc16"]

def normalize(rx, ry):
    t = MAP_TRANSFORM
    nx = round((ry * t["xMul"] + t["xAdd"]) * 100, 3)
    ny = round((rx * t["yMul"] + t["yAdd"]) * 100, 3)
    return nx, ny

def fmt(ms):
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"

with open(JSONL) as f:
    matches = [json.loads(l) for l in f if l.strip()]

m = next(x for x in matches if x["matchInfo"]["matchId"].startswith("885a842b"))

# Players (exclude Neutral/observer)
raw_players = [p for p in m.get("players", []) if p.get("teamId") in ("Red", "Blue")]
cgn_i = 0
player_list = []
puuid_map = {}
for p in raw_players:
    name = p.get("gameName", "?")
    team = p.get("teamId")
    if team == "Blue":
        color = SGE_COLORS.get(name, "#888")
    else:
        color = CGN_COLORS[cgn_i % len(CGN_COLORS)]
        cgn_i += 1
    short = name.split()[-1] if name else "?"
    entry = {"puuid": p["puuid"], "name": name, "short": short, "team": team, "color": color}
    player_list.append(entry)
    puuid_map[p["puuid"]] = entry

def make_positions(locs):
    out = []
    for loc in (locs or []):
        if loc["puuid"] not in puuid_map:
            continue
        nx, ny = normalize(loc["location"]["x"], loc["location"]["y"])
        out.append({"puuid": loc["puuid"], "x": nx, "y": ny,
                    "angle": round(loc.get("viewRadians", 0), 3)})
    return out

rounds_out = []
for r in m.get("roundResults", []):
    events = []

    # Kills
    for ps in r.get("playerStats", []):
        for k in ps.get("kills", []):
            fd = k.get("finishingDamage", {})
            w_uuid = fd.get("damageItem", "").upper()
            w_type = fd.get("damageType", "")
            if w_type == "Ability":
                weapon = "Ability"
            elif w_type == "Bomb":
                weapon = "Spike"
            else:
                weapon = WEAPONS.get(w_uuid, "Unknown")
            events.append({
                "type": "kill",
                "timeMs": k["timeSinceRoundStartMillis"],
                "time": fmt(k["timeSinceRoundStartMillis"]),
                "killer": k["killer"],
                "victim": k["victim"],
                "weapon": weapon,
                "positions": make_positions(k.get("playerLocations", [])),
            })

    # Plant
    pt = r.get("plantRoundTime")
    if pt:
        events.append({
            "type": "plant",
            "timeMs": pt,
            "time": fmt(pt),
            "site": r.get("plantSite", "?"),
            "positions": make_positions(r.get("plantPlayerLocations") or []),
        })

    # Defuse
    dt_ = r.get("defuseRoundTime")
    if dt_:
        events.append({
            "type": "defuse",
            "timeMs": dt_,
            "time": fmt(dt_),
            "positions": make_positions(r.get("defusePlayerLocations") or []),
        })

    events.sort(key=lambda e: e["timeMs"])
    winner = r.get("winningTeam", "")
    rounds_out.append({
        "roundNum": r["roundNum"] + 1,
        "winner": winner,
        "winnerTeam": "SGE" if winner == "Blue" else "CGN",
        "planted": bool(pt),
        "defused": bool(dt_),
        "site": r.get("plantSite"),
        "events": events,
    })

data = {
    "matchId": m["matchInfo"]["matchId"],
    "map": "Lotus",
    "date": "2026-04-19",
    "teams": {
        "Blue": {"name": "SGE", "label": "Eintracht Frankfurt"},
        "Red":  {"name": "CGN", "label": "CGN Esports"},
    },
    "players": player_list,
    "rounds": rounds_out,
}

OUT.write_text(f"const lotusReplayData = {json.dumps(data, indent=2)};\n", encoding="utf-8")
print(f"Written {OUT}")
print(f"Rounds: {len(rounds_out)}")
for rd in rounds_out:
    e_summary = ", ".join(
        f"{e['type']}@{e['time']}" + (f"({e['site']})" if e['type']=='plant' else "")
        for e in rd['events']
    )
    print(f"  R{rd['roundNum']:2d} {rd['winnerTeam']} | {e_summary}")
