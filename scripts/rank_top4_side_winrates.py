from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import PLAYOFF_TAGS, TEAMS
from lib.match_parser import load_team_matches
from lib.stats_engine import compute_team_stats
from lib.json_builder import build_stats_json


def main() -> None:
    all_team_data = {}

    for team_cfg in TEAMS:
        if team_cfg["tag"] not in PLAYOFF_TAGS:
            continue
        matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])
        stats = compute_team_stats(matches, team_cfg["tag"], team_cfg["name"])
        all_team_data[team_cfg["tag"]] = {
            "name": team_cfg["name"],
            "tag": team_cfg["tag"],
            **stats,
        }

    result = build_stats_json(all_team_data)

    teams = []
    for team in result["teams"]:
        all_maps = team["allMaps"]
        teams.append(
            {
                "team": team["name"],
                "tag": team["tag"],
                "t_side_winrate": round(all_maps["atk_rW_pct"] * 100, 2),
                "ct_side_winrate": round(all_maps["def_rW_pct"] * 100, 2),
            }
        )

    t_ranked = sorted(teams, key=lambda row: (-row["t_side_winrate"], row["team"]))
    ct_ranked = sorted(teams, key=lambda row: (-row["ct_side_winrate"], row["team"]))

    t_ranks = {row["tag"]: idx + 1 for idx, row in enumerate(t_ranked)}
    ct_ranks = {row["tag"]: idx + 1 for idx, row in enumerate(ct_ranked)}

    output = []
    for row in sorted(teams, key=lambda row: row["team"]):
        output.append(
            {
                "team": row["team"],
                "tag": row["tag"],
                "t_side_winrate": row["t_side_winrate"],
                "t_side_rank_among_top4": t_ranks[row["tag"]],
                "ct_side_winrate": row["ct_side_winrate"],
                "ct_side_rank_among_top4": ct_ranks[row["tag"]],
            }
        )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
