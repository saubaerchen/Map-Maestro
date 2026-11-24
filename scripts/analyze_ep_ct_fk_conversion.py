from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


TEAM_TAG = "EP"
TEAM_NAME = "Enterprise Esports"
DATA_FILE = "data/raw/ep_2026_raw_responses.jsonl"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)

    total_ct_rounds = 0
    total_ct_round_wins = 0
    team_ct_fk_rounds = 0
    team_ct_fk_wins = 0
    player_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"rounds": 0, "wins": 0})

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        names_by_puuid = {
            p["puuid"]: strip_prefix(p.get("gameName", ""))
            for p in md.team_players
        }

        for rr in md.round_results:
            round_num = rr["roundNum"]
            if sides.get(round_num) != "def":
                continue

            total_ct_rounds += 1
            won = rr["winningTeam"] == md.team_id
            if won:
                total_ct_round_wins += 1

            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))
            if not all_kills:
                continue

            first_killer = all_kills[0]["killer"]
            if first_killer not in team_puuids:
                continue

            team_ct_fk_rounds += 1
            if won:
                team_ct_fk_wins += 1

            player_name = names_by_puuid.get(first_killer, first_killer)
            player_stats[player_name]["rounds"] += 1
            if won:
                player_stats[player_name]["wins"] += 1

    player_rows = []
    for player_name, stats in sorted(
        player_stats.items(),
        key=lambda item: (-pct(item[1]["wins"], item[1]["rounds"]), -item[1]["rounds"], item[0].lower()),
    ):
        player_rows.append(
            {
                "player": player_name,
                "rounds": stats["rounds"],
                "wins": stats["wins"],
                "win_pct": pct(stats["wins"], stats["rounds"]),
            }
        )

    output = {
        "scope": {
            "team": TEAM_NAME,
            "valid_maps": len(matches),
            "total_ct_rounds": total_ct_rounds,
            "team_ct_round_win_pct": pct(total_ct_round_wins, total_ct_rounds),
            "team_ct_first_kill_rounds": team_ct_fk_rounds,
            "team_ct_first_kill_win_pct": pct(team_ct_fk_wins, team_ct_fk_rounds),
        },
        "players": player_rows,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
