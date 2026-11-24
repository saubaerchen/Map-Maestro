from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.match_parser import load_team_matches


TEAM_TAG = "MDR"
TEAM_NAME = "Mandatory"
DATA_FILE = "data/raw/mdr_2026_raw_responses.jsonl"
PLAYER_NAME = "Sevire"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix) :] if name.startswith(prefix) else name


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    series = defaultdict(list)

    for md in matches:
        key = (md.date, md.opp)
        player_stats = None
        for p in md.raw.get("players", []):
            if p.get("isObserver"):
                continue
            if p.get("teamId") != md.team_id:
                continue
            if strip_prefix(p.get("gameName", "")).lower() == PLAYER_NAME.lower():
                player_stats = p.get("stats", {})
                break
        if player_stats is None:
            continue

        rounds = player_stats.get("roundsPlayed", 0)
        score = player_stats.get("score", 0)
        acs = round(score / rounds, 2) if rounds else 0.0
        series[key].append(
            {
                "map": md.map,
                "acs": acs,
                "score": f"{md.team_score}-{md.opp_score}",
            }
        )

    rows = []
    for (date, opp), maps in series.items():
        avg_acs = round(sum(m["acs"] for m in maps) / len(maps), 2) if maps else 0.0
        rows.append(
            {
                "date": date,
                "opponent": opp,
                "maps": maps,
                "maps_played": len(maps),
                "avg_acs": avg_acs,
            }
        )

    rows.sort(key=lambda r: (-r["avg_acs"], r["date"], r["opponent"]))
    print(json.dumps({"best_series": rows[0], "top_series": rows[:10]}, indent=2))


if __name__ == "__main__":
    main()
