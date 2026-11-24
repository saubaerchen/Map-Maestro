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
    op_start_rounds = 0
    op_start_round_wins = 0
    op_kill_rounds = 0
    op_kill_round_wins = 0
    op_start_and_kill_rounds = 0
    op_start_and_kill_wins = 0
    total_kills_in_op_start_rounds = 0
    operator_kills_in_op_start_rounds = 0

    for md in matches:
        target_puuids = {
            p["puuid"]
            for p in md.team_players
            if strip_prefix(p.get("gameName", "")).lower() == PLAYER_NAME.lower()
        }

        for rr in md.round_results:
            total_rounds += 1
            won = rr["winningTeam"] == md.team_id

            target_stats = None
            for ps in rr.get("playerStats", []):
                if ps["puuid"] in target_puuids:
                    target_stats = ps
                    break
            if target_stats is None:
                continue

            started_op = target_stats.get("economy", {}).get("weapon") == OPERATOR_UUID
            if started_op:
                op_start_rounds += 1
                if won:
                    op_start_round_wins += 1

            got_op_kill = False
            for kill in target_stats.get("kills", []):
                damage_item = kill.get("finishingDamage", {}).get("damageItem")
                if started_op:
                    total_kills_in_op_start_rounds += 1
                    if damage_item == OPERATOR_UUID:
                        operator_kills_in_op_start_rounds += 1
                if damage_item == OPERATOR_UUID:
                    got_op_kill = True
            if started_op and not target_stats.get("kills", []):
                total_kills_in_op_start_rounds += 0

            if got_op_kill:
                op_kill_rounds += 1
                if won:
                    op_kill_round_wins += 1

            if started_op and got_op_kill:
                op_start_and_kill_rounds += 1
                if won:
                    op_start_and_kill_wins += 1

    output = {
        "total_rounds": total_rounds,
        "op_start_rounds": op_start_rounds,
        "op_start_round_wins": op_start_round_wins,
        "op_start_round_win_pct": pct(op_start_round_wins, op_start_rounds),
        "op_kill_rounds": op_kill_rounds,
        "op_kill_round_wins": op_kill_round_wins,
        "op_kill_round_win_pct": pct(op_kill_round_wins, op_kill_rounds),
        "op_start_and_kill_rounds": op_start_and_kill_rounds,
        "op_start_and_kill_round_pct_of_op_starts": pct(op_start_and_kill_rounds, op_start_rounds),
        "op_start_and_kill_round_wins": op_start_and_kill_wins,
        "op_start_and_kill_round_win_pct": pct(op_start_and_kill_wins, op_start_and_kill_rounds),
        "total_kills_in_op_start_rounds": total_kills_in_op_start_rounds,
        "operator_kills_in_op_start_rounds": operator_kills_in_op_start_rounds,
        "operator_kill_share_in_op_start_rounds": pct(operator_kills_in_op_start_rounds, total_kills_in_op_start_rounds),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
