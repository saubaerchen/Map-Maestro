from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import TEAMS
from lib.match_parser import load_team_matches
from lib.stats_engine import compute_team_stats


def pct(num: int, denom: int) -> float:
    return round((num / denom) * 100, 2) if denom else 0.0


def main() -> None:
    team_tag = sys.argv[1] if len(sys.argv) > 1 else "EP"
    mode = sys.argv[2] if len(sys.argv) > 2 else "won_both"
    team_cfg = next((team for team in TEAMS if team["tag"] == team_tag), None)
    if team_cfg is None:
        raise SystemExit(f"Unknown team tag: {team_tag}")
    if mode not in {"won_both", "lost_both"}:
        raise SystemExit(f"Unknown mode: {mode}")

    matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])
    stats = compute_team_stats(matches, team_cfg["tag"], team_cfg["name"])
    match_rows = stats["match_rows"]

    selected_maps = []
    for row in match_rows:
        pistols_won = row["team1_atk_pistol"] + row["team1_def_pistol"]
        include = pistols_won == 2 if mode == "won_both" else pistols_won == 0
        if include:
            selected_maps.append(
                {
                    "match_id": row["match_id"],
                    "date": row["date"],
                    "map": row["map"],
                    "opponent": row["team2"],
                    "score": f'{row["team1_score"]}-{row["team2_score"]}',
                    "won_map": row["winner"] == team_cfg["name"],
                }
            )

    selected_count = len(selected_maps)
    selected_wins = sum(1 for row in selected_maps if row["won_map"])
    rate_key = (
        "map_win_pct_when_winning_both_pistols"
        if mode == "won_both"
        else "map_win_pct_when_losing_both_pistols"
    )
    count_key = "maps_with_both_pistols" if mode == "won_both" else "maps_with_no_pistols"
    wins_key = (
        "maps_won_with_both_pistols"
        if mode == "won_both"
        else "maps_won_when_losing_both_pistols"
    )

    output = {
        "team": team_cfg["name"],
        "team_tag": team_cfg["tag"],
        "valid_maps": len(match_rows),
        count_key: selected_count,
        wins_key: selected_wins,
        rate_key: pct(selected_wins, selected_count),
        "overall_map_win_pct": pct(
            sum(1 for row in match_rows if row["winner"] == team_cfg["name"]), len(match_rows)
        ),
        "examples": selected_maps[:10],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
