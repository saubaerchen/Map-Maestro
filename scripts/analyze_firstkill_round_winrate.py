from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.match_parser import load_team_matches
from lib.stats_engine import classify_round_economy, get_team_side_per_round


TEAM_TAG = "UCAM"
TEAM_NAME = "UCAM Esports"
DATA_FILE = "data/raw/ucam_2026_raw_responses.jsonl"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def main() -> None:
    target_player = sys.argv[1] if len(sys.argv) > 1 else "B1SK"
    side_filter = sys.argv[2] if len(sys.argv) > 2 else "def"
    econ_filter = sys.argv[3] if len(sys.argv) > 3 else "all"
    target_lower = target_player.lower()

    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    qualifying_rounds = []
    wins = 0

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        names_by_puuid = {
            p["puuid"]: strip_prefix(p.get("gameName", ""))
            for p in md.team_players
        }
        target_puuids = {
            puuid for puuid, name in names_by_puuid.items() if name.lower() == target_lower
        }

        for rr in md.round_results:
            round_num = rr["roundNum"]
            if sides.get(round_num) != side_filter:
                continue

            econ = classify_round_economy(rr, round_num, team_puuids)
            if econ_filter != "all" and econ != econ_filter:
                continue

            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))
            if not all_kills:
                continue

            first_kill = all_kills[0]
            killer = first_kill["killer"]
            if killer not in target_puuids:
                continue

            won = rr["winningTeam"] == md.team_id
            qualifying_rounds.append(
                {
                    "match_id": md.match_id,
                    "date": md.date,
                    "map": md.map,
                    "round_num": round_num,
                    "economy": econ,
                    "won": won,
                }
            )
            if won:
                wins += 1

    output = {
        "team": TEAM_NAME,
        "player": target_player,
        "side": side_filter,
        "economy_filter": econ_filter,
        "valid_maps": len(matches),
        "qualifying_rounds": len(qualifying_rounds),
        "round_wins": wins,
        "round_win_pct": pct(wins, len(qualifying_rounds)),
        "examples": qualifying_rounds[:10],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
