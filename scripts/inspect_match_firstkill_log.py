from __future__ import annotations

import json
import re
import urllib.request
from types import SimpleNamespace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.stats_engine import get_team_side_per_round


MATCH_ID = "84691e05-9363-4a3d-bd9b-56d2e0290c68"


def load_api_key() -> str:
    text = open("API_REFERENCE.md", "r", encoding="utf-8", errors="ignore").read()
    match = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return match.group(1)


def first_kill(round_result: dict) -> dict | None:
    first = None
    for player_stats in round_result.get("playerStats", []):
        for kill in player_stats.get("kills", []):
            ts = kill.get("timeSinceRoundStartMillis")
            if ts is None:
                continue
            if first is None or ts < first.get("timeSinceRoundStartMillis", 10**9):
                first = kill
    return first


def main() -> None:
    api_key = load_api_key()
    req = urllib.request.Request(
        f"https://api.valolytics.gg/api/matches/esports/{MATCH_ID}",
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    match_obj = json.load(urllib.request.urlopen(req, timeout=30))

    team_players = [
        p
        for p in match_obj.get("players", [])
        if (not p.get("isObserver")) and str(p.get("gameName", "")).startswith("SGE ")
    ]
    team_puuids = {p["puuid"] for p in team_players}
    name_by_puuid = {
        p["puuid"]: p.get("gameName", p["puuid"])
        for p in match_obj.get("players", [])
        if not p.get("isObserver")
    }

    sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)

    print(f"match={MATCH_ID}")
    for rr in match_obj.get("roundResults", []):
        rnum = rr.get("roundNum")
        fk = first_kill(rr)
        if not fk:
            continue
        ms = fk.get("timeSinceRoundStartMillis", 0)
        owner = "SGE" if fk.get("killer") in team_puuids else "ENEMY"
        killer = name_by_puuid.get(fk.get("killer"), "?")
        victim = name_by_puuid.get(fk.get("victim"), "?")
        print(
            f"R{int(rnum):02d} side={sides.get(rnum)} fk={owner} t={ms/1000:.3f}s killer={killer} victim={victim}"
        )


if __name__ == "__main__":
    main()
