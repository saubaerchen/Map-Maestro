from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import AGENT_MAP, TEAMS
from lib.match_parser import load_team_matches


TARGET_DATE = "2026-03-26"
TOP4_TAGS = {"EP", "MISA", "MDR", "UCAM"}
MATCH_IDS = {
    "318a8b6e-36d6-4ba2-8024-bf8675973a65",
    "5d62d424-a04c-49c0-8620-9aff76e2f156",
    "7bcd576f-0fe8-4777-af6b-c781cf832861",
    "96b68747-35a5-4093-b080-ff799df47e4c",
    "d0e27b16-a4af-4c34-8807-b931bd92927d",
    "d9e9f061-ea4f-4fd6-b7ad-9add979afbfd",
}


def agent_name(player: dict) -> str:
    return AGENT_MAP.get(player.get("characterId"), player.get("characterId") or "Unknown")


def strip_prefix(name: str, tag: str) -> str:
    prefix = f"{tag} "
    return name[len(prefix) :] if name.startswith(prefix) else name


def main() -> None:
    history: dict[tuple[str, str], list[dict]] = defaultdict(list)
    mar26_rows: list[dict] = []

    for team in TEAMS:
        if team["tag"] not in TOP4_TAGS:
            continue

        matches = load_team_matches(team["tag"], team["name"], team["data_file"])
        for md in matches:
            for player in md.team_players:
                player_name = strip_prefix(player.get("gameName", ""), team["tag"])
                row = {
                    "team": team["tag"],
                    "player": player_name,
                    "date": md.date,
                    "map": md.map,
                    "match_id": md.match_id,
                    "agent": agent_name(player),
                }
                history[(team["tag"], player_name)].append(row)
                if md.date == TARGET_DATE and md.match_id in MATCH_IDS:
                    mar26_rows.append(row)

    first_time = []
    low_sample = []

    for row in mar26_rows:
        prior_agent_maps = [
            h for h in history[(row["team"], row["player"])]
            if h["date"] < TARGET_DATE and h["agent"] == row["agent"]
        ]
        prior_total_maps = [
            h for h in history[(row["team"], row["player"])]
            if h["date"] < TARGET_DATE
        ]
        result = {
            **row,
            "prior_agent_maps": len(prior_agent_maps),
            "prior_total_maps": len(prior_total_maps),
        }
        if not prior_agent_maps:
            first_time.append(result)
        elif len(prior_agent_maps) <= 2:
            low_sample.append(result)

    output = {
        "date": TARGET_DATE,
        "first_time_agent_picks": sorted(
            first_time,
            key=lambda r: (r["team"], r["player"], r["map"]),
        ),
        "rare_agent_picks_1_or_2_prior_maps": sorted(
            low_sample,
            key=lambda r: (r["team"], r["player"], r["prior_agent_maps"], r["map"]),
        ),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
