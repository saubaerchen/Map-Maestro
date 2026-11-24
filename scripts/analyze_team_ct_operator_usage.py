from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import OPERATOR_UUID, TEAMS
from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


def pct(num: int, den: int) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def main() -> None:
    rows = []

    for team in TEAMS:
        matches = load_team_matches(team["tag"], team["name"], team["data_file"])
        ct_player_rounds = 0
        ct_operator_player_rounds = 0
        ct_rounds = 0

        for md in matches:
            team_puuids = {p["puuid"] for p in md.team_players}
            sides = get_team_side_per_round(md, team_puuids)

            for rr in md.round_results:
                if sides.get(rr["roundNum"]) != "def":
                    continue

                ct_rounds += 1
                for ps in rr.get("playerStats", []):
                    if ps.get("puuid") not in team_puuids:
                        continue
                    ct_player_rounds += 1
                    weapon = ps.get("economy", {}).get("weapon", "").upper()
                    if weapon == OPERATOR_UUID:
                        ct_operator_player_rounds += 1

        rows.append(
            {
                "team": team["name"],
                "tag": team["tag"],
                "valid_maps": len(matches),
                "ct_rounds": ct_rounds,
                "ct_player_rounds": ct_player_rounds,
                "ct_op_player_rounds": ct_operator_player_rounds,
                "ct_op_usage_pct": pct(ct_operator_player_rounds, ct_player_rounds),
            }
        )

    rows.sort(key=lambda row: (row["ct_op_usage_pct"], row["team"]))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
