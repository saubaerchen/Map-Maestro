"""Steps 6-7: registry -> data/raw/{prefix}_2026_raw_responses.jsonl + coverage report.

Usage:
  python scripts/live/fetch_official_games.py --prefix sge

Writes only VLR-matched official games (from data/registry/teams.json -> teams[prefix].official).
The JSONL is regenerated from the registry each run, so it never contains scrims/warm-ups.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW_DIR, REGISTRY_DIR, VLR_DIR, load_registry, match_detail  # noqa: E402
from core import EXCLUDED_TEAMS, MIN_CORE, core_info, passes  # noqa: E402

ACTIVE_POOL = {"Abyss", "Bind", "Corrode", "Haven", "Lotus", "Summit", "Sunset"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    a = ap.parse_args()
    if a.prefix in EXCLUDED_TEAMS:
        print(f"{a.prefix}: excluded team (core.EXCLUDED_TEAMS) — nothing written")
        return
    reg = load_registry()
    team = reg["teams"].get(a.prefix)
    if not team or not team.get("official"):
        print("no official games in registry for", a.prefix)
        return
    official = team["official"]
    info = core_info(a.prefix)
    rows, excluded = [], []
    for mid, meta in official.items():
        d = match_detail(mid, meta.get("route", "eu"))
        if not d:
            continue
        if not passes(info, meta["gameId"], meta.get("date")):
            excluded.append((meta["date"], meta["map"], info["byGame"].get(meta["gameId"]), meta.get("event", "")))
            continue
        rows.append((d["matchInfo"]["gameStartMillis"], mid, d, meta))
    rows.sort()
    if info["core"]:
        print(f"baseline core (Open Qualifier, {info['coreMaps']} maps): {', '.join(info['core'])} — "
              f"kept {len(rows)}, excluded {len(excluded)} games with < {MIN_CORE}/5 core players")
    else:
        print("WARNING: no Open Qualifier games — baseline core undefined, all official games kept")
    path = os.path.join(RAW_DIR, f"{a.prefix}_2026_raw_responses.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for _, _, d, _ in rows:
            f.write(json.dumps(d) + "\n")

    own_tag = team.get("vlrTag")
    per_map = Counter(meta["map"] for *_, meta in rows)
    # Lineups and accounts come from each game's VLR scoreboard (team side), not from the registry's
    # single 'team' field, which is overwritten when a player has played for several teams.
    vlr_path = os.path.join(VLR_DIR, f"{a.prefix}.json")
    vlr = json.load(open(vlr_path, encoding="utf-8")) if os.path.exists(vlr_path) else {"matches": []}
    own_names = {mp["gameId"]: sorted(p["name"] for p in mp["players"] if p["teamTag"] == info["tag"])
                 for m in vlr["matches"] for mp in m["maps"]}
    kept_ids = {mid for _, mid, _, _ in rows}
    lineups = defaultdict(list)
    played = Counter()
    for _, mid, d, meta in rows:
        names = own_names.get(meta["gameId"], [])
        played.update(names)
        lineups[" / ".join(names)].append(f'{meta["date"]} {meta["map"]}')
    accounts = {}
    for pu, acc in reg["accounts"].items():
        if acc.get("status") == "confirmed" and acc.get("proName") in played and any(e["matchId"] in kept_ids for e in acc.get("evidence", [])):
            accounts[pu] = acc

    missing = []
    if vlr["matches"]:
        found = {meta["gameId"] for meta in official.values()}
        for m in vlr["matches"]:
            for mp in m["maps"]:
                if mp["gameId"] not in found and passes(info, mp["gameId"]):
                    missing.append(f'{m.get("listDate")} {mp["map"]} {mp["score"][0]}-{mp["score"][1]} ({m["event"]}) https://www.vlr.gg{m["url"]}')

    core_line = (f"Baseline core (Kickoff Open Qualifier, {info['coreMaps']} maps): **{', '.join(info['core'])}** — "
                 f"games need ≥{MIN_CORE}/5 core players; {len(excluded)} official games excluded"
                 if info["core"] else "⚠ No Open Qualifier games — baseline core undefined, all official games kept")
    lines = [f"# Coverage — {team.get('name')} [{own_tag}]", "", core_line, "",
             f"Official games written: **{len(rows)}** -> `data/raw/{a.prefix}_2026_raw_responses.jsonl`", "",
             "## Per map", "", "| Map | Games | In active pool |", "|---|---|---|"]
    for m, c in sorted(per_map.items(), key=lambda x: -x[1]):
        lines.append(f"| {m} | {c} | {'yes' if m in ACTIVE_POOL else 'no'} |")
    lines += ["", "## Players and confirmed accounts (in the kept games)", "", "| Player | Core | Riot ID | Kept maps played |", "|---|---|---|---|"]
    for pu, acc in sorted(accounts.items(), key=lambda x: -played[x[1]["proName"]]):
        core_mark = "✓" if info["core"] and acc["proName"] in info["core"] else ""
        lines.append(f"| {acc['proName']} | {core_mark} | `{acc['riotId']}` | {played[acc['proName']]} |")
    lines += ["", "## Lineups seen", ""]
    for lu, games in lineups.items():
        lines.append(f"- **{lu}** — {len(games)} maps ({games[0]} … {games[-1]})")
    lines += ["", "## VLR maps not found in main-account data", ""]
    lines += [f"- {m}" for m in missing] or ["- none"]
    rep = os.path.join(REGISTRY_DIR, f"coverage_{a.prefix}.md")
    open(rep, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
