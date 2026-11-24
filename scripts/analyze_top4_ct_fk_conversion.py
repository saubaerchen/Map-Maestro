from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import PLAYOFF_TEAMS
from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


def strip_prefix(team_tag: str, name: str) -> str:
    prefix = f"{team_tag} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def main() -> None:
    rows: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"rounds": 0, "wins": 0, "name": ""}
    )

    for team_cfg in PLAYOFF_TEAMS:
        matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])

        for md in matches:
            team_puuids = {p["puuid"] for p in md.team_players}
            sides = get_team_side_per_round(md, team_puuids)
            names_by_puuid = {
                p["puuid"]: strip_prefix(team_cfg["tag"], p.get("gameName", ""))
                for p in md.team_players
            }

            for rr in md.round_results:
                round_num = rr["roundNum"]
                if sides.get(round_num) != "def":
                    continue

                all_kills = []
                for ps in rr.get("playerStats", []):
                    all_kills.extend(ps.get("kills", []))
                all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))
                if not all_kills:
                    continue

                first_killer = all_kills[0]["killer"]
                if first_killer not in team_puuids:
                    continue

                player_name = names_by_puuid.get(first_killer, first_killer)
                key = (team_cfg["tag"], player_name.lower())
                rows[key]["name"] = player_name
                rows[key]["rounds"] += 1
                if rr["winningTeam"] == md.team_id:
                    rows[key]["wins"] += 1

    output = []
    for (team_tag, _player_key), stats in rows.items():
        output.append(
            {
                "team": team_tag,
                "player": stats["name"],
                "rounds": stats["rounds"],
                "wins": stats["wins"],
                "win_pct": pct(stats["wins"], stats["rounds"]),
            }
        )

    output.sort(key=lambda row: (-row["win_pct"], -row["rounds"], row["team"], row["player"].lower()))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
