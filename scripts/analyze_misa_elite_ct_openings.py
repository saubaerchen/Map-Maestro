from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


TEAM_TAG = "MISA"
TEAM_NAME = "Misa Esports"
DATA_FILE = "data/raw/misa_2026_raw_responses.jsonl"
PLAYER_NAME = "Elite"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)

    total_ct_rounds = 0
    total_ct_round_wins = 0
    fk_rounds = 0
    fk_wins = 0
    fd_rounds = 0
    fd_wins = 0

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        names_by_puuid = {
            p["puuid"]: strip_prefix(p.get("gameName", ""))
            for p in md.team_players
        }
        target_puuids = {
            puuid for puuid, name in names_by_puuid.items() if name.lower() == PLAYER_NAME.lower()
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

            first_killer = all_kills[0]["killer"] if all_kills else None
            first_victim = all_kills[0]["victim"] if all_kills else None

            if first_killer in target_puuids:
                fk_rounds += 1
                if won:
                    fk_wins += 1
            elif first_victim in target_puuids:
                fd_rounds += 1
                if won:
                    fd_wins += 1

    result = {
        "team": TEAM_NAME,
        "player": PLAYER_NAME,
        "valid_maps": len(matches),
        "team_ct_round_win_pct": pct(total_ct_round_wins, total_ct_rounds),
        "ct_first_kill_win_pct": pct(fk_wins, fk_rounds),
        "ct_first_kill_wins": fk_wins,
        "ct_first_kill_rounds": fk_rounds,
        "ct_first_death_win_pct": pct(fd_wins, fd_rounds),
        "ct_first_death_wins": fd_wins,
        "ct_first_death_rounds": fd_rounds,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
