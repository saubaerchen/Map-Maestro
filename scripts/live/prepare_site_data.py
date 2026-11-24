"""Prepare site-ready JSONL: official games with both teams' players renamed to '{VLR tag} {pro name}'.

The legacy build scripts identify a team's players by gameName prefix (e.g. 'SGE ').
Main-account names don't follow that, so this step rewrites names using the VLR match
(K/D/A-verified in discover_accounts.py). Unmodified API responses stay in data/cache/matches/.

Usage: python scripts/live/prepare_site_data.py [--team eintracht ...]
Writes data/site/{prefix}_2026_raw_responses.jsonl (official games only, chronological).
"""
import argparse
import copy
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import VLR_DIR, load_registry, match_detail  # noqa: E402
from discover_accounts import try_match, vlr_maps  # noqa: E402
from core import core_info, passes  # noqa: E402
from site_config import NAME_ALIASES, SITE_RAW_DIR, TEAMS, site_jsonl, team_min_date  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", action="append")
    a = ap.parse_args()
    os.makedirs(SITE_RAW_DIR, exist_ok=True)
    reg = load_registry()
    for key in a.team or list(TEAMS):
        cfg = TEAMS[key]
        pre, tag = cfg["prefix"], cfg["tag"]
        if cfg.get("esports_source"):
            # tournament-account data: names are already '{TAG} {name}', no core/date rule
            lo = team_min_date(cfg)
            rows = []
            for line in open(cfg["esports_source"], encoding="utf-8"):
                d = json.loads(line)
                ts = d["matchInfo"]["gameStartMillis"]
                if datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc).strftime("%Y-%m-%d") >= lo:
                    # tournament lobbies list admins/observers ('VCT Observer 11', isObserver, teamId Neutral);
                    # drop them, otherwise they outvote the 5 enemy players when the opponent tag is derived
                    d["players"] = [p for p in d["players"] if not p.get("isObserver") and p.get("teamId") in ("Red", "Blue")]
                    rows.append((ts, d))
            rows.sort(key=lambda r: r[0])
            with open(site_jsonl(pre), "w", encoding="utf-8") as f:
                for _, d in rows:
                    f.write(json.dumps(d) + "\n")
            print(f"{key:10} {len(rows)} games (esports source) -> {site_jsonl(pre)}")
            continue
        vpath = os.path.join(VLR_DIR, f"{pre}.json")
        vm = vlr_maps(json.load(open(vpath, encoding="utf-8"))) if os.path.exists(vpath) else []
        rows, problems = [], []
        info = core_info(pre)
        for mid, meta in reg["teams"].get(pre, {}).get("official", {}).items():
            if not passes(info, meta["gameId"], meta.get("date")):
                continue
            d = match_detail(mid)
            res = try_match(d, vm)
            if not res:
                problems.append(mid)
                continue
            _, assign = res
            out = copy.deepcopy(d)
            tags = {}
            for team_id, (t, names) in assign.items():
                tags[team_id] = t
                for p in out["players"]:
                    if p["puuid"] in names:
                        pro = names[p["puuid"]] or reg["accounts"].get(p["puuid"], {}).get("proName") or p["gameName"].split(" ")[-1]
                        pro = NAME_ALIASES.get(pro, pro) if t == tag else pro
                        p["originalGameName"] = p["gameName"]
                        p["gameName"] = f"{t} {pro}"
            if tag not in tags.values():
                problems.append(mid)
                continue
            rows.append((out["matchInfo"]["gameStartMillis"], out))
        rows.sort(key=lambda r: r[0])
        with open(site_jsonl(pre), "w", encoding="utf-8") as f:
            for _, d in rows:
                f.write(json.dumps(d) + "\n")
        print(f"{key:10} {len(rows)} games -> {site_jsonl(pre)}" + (f"  PROBLEMS: {problems}" if problems else ""))


if __name__ == "__main__":
    main()
