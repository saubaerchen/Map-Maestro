from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import OPERATOR_UUID
from lib.match_parser import load_team_matches


TEAM_TAG = "UCAM"
TEAM_NAME = "UCAM Esports"
DATA_FILE = "data/raw/ucam_2026_raw_responses.jsonl"
PLAYER_NAME = "B1SK"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(num: int, den: int) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)

    total_rounds = 0
    op_kill_rounds = 0
    op_kill_round_wins = 0

    for md in matches:
        target_puuids = {
            p["puuid"]
            for p in md.team_players
            if strip_prefix(p.get("gameName", "")).lower() == PLAYER_NAME.lower()
        }

        for rr in md.round_results:
            total_rounds += 1
            found_op_kill = False

            for ps in rr.get("playerStats", []):
                if ps["puuid"] not in target_puuids:
                    continue
                for kill in ps.get("kills", []):
                    damage_item = kill.get("finishingDamage", {}).get("damageItem")
                    if damage_item == OPERATOR_UUID:
                        found_op_kill = True
                        break
                if found_op_kill:
                    break

            if not found_op_kill:
                continue

            op_kill_rounds += 1
            if rr["winningTeam"] == md.team_id:
                op_kill_round_wins += 1

    output = {
        "team": TEAM_NAME,
        "player": PLAYER_NAME,
        "valid_maps": len(matches),
        "total_rounds": total_rounds,
        "operator_kill_rounds": op_kill_rounds,
        "operator_kill_round_pct": pct(op_kill_rounds, total_rounds),
        "operator_kill_round_wins": op_kill_round_wins,
        "operator_kill_round_win_pct": pct(op_kill_round_wins, op_kill_rounds),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
