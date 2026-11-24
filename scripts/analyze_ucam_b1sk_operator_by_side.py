from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import OPERATOR_UUID
from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


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

    counts = {
        "atk": {"rounds": 0, "operator_rounds": 0},
        "def": {"rounds": 0, "operator_rounds": 0},
    }

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        target_puuids = {
            p["puuid"]
            for p in md.team_players
            if strip_prefix(p.get("gameName", "")).lower() == PLAYER_NAME.lower()
        }

        for rr in md.round_results:
            side = sides.get(rr["roundNum"])
            if side not in counts:
                continue

            target_stats = None
            for ps in rr.get("playerStats", []):
                if ps["puuid"] in target_puuids:
                    target_stats = ps
                    break
            if target_stats is None:
                continue

            counts[side]["rounds"] += 1
            weapon = target_stats.get("economy", {}).get("weapon")
            if weapon == OPERATOR_UUID:
                counts[side]["operator_rounds"] += 1

    output = {
        "team": TEAM_NAME,
        "player": PLAYER_NAME,
        "valid_maps": len(matches),
        "t_side": {
            "operator_rounds": counts["atk"]["operator_rounds"],
            "rounds": counts["atk"]["rounds"],
            "operator_pct": pct(counts["atk"]["operator_rounds"], counts["atk"]["rounds"]),
        },
        "ct_side": {
            "operator_rounds": counts["def"]["operator_rounds"],
            "rounds": counts["def"]["rounds"],
            "operator_pct": pct(counts["def"]["operator_rounds"], counts["def"]["rounds"]),
        },
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
