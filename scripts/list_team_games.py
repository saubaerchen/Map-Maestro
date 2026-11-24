from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import TEAMS
from lib.match_parser import load_team_matches


def main() -> None:
    team_tag = sys.argv[1] if len(sys.argv) > 1 else "EP"
    team_cfg = next((team for team in TEAMS if team["tag"] == team_tag), None)
    if team_cfg is None:
        raise SystemExit(f"Unknown team tag: {team_tag}")

    matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])
    rows = []
    for md in sorted(matches, key=lambda m: (m.date, m.match_id), reverse=True):
        rows.append(
            {
                "date": md.date,
                "map": md.map,
                "opponent": md.opp,
                "score": f"{md.team_score}-{md.opp_score}",
                "result": "W" if md.team_won else "L",
                "match_id": md.match_id,
            }
        )

    print(json.dumps({"team": team_cfg["name"], "tag": team_cfg["tag"], "maps": rows}, indent=2))


if __name__ == "__main__":
    main()
