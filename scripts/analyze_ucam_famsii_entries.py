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
    target_player = sys.argv[1] if len(sys.argv) > 1 else "Famsii"
    target_player_lower = target_player.lower()
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    buckets: dict[str, dict[str, object]] = {
        "target": {"rounds": 0, "wins": 0, "examples": []},
        "teammate": {"rounds": 0, "wins": 0, "examples": []},
    }

    total_tside_gun_rounds = 0
    total_ucam_entry_rounds = 0

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        famsii_puuids = {
            p["puuid"]
            for p in md.team_players
            if strip_prefix(p.get("gameName", "")).lower() == target_player_lower
        }
        names_by_puuid = {
            p["puuid"]: strip_prefix(p.get("gameName", ""))
            for p in md.team_players
        }

        for rr in md.round_results:
            round_num = rr["roundNum"]
            if sides.get(round_num) != "atk":
                continue

            econ = classify_round_economy(rr, round_num, team_puuids)
            if econ != "gun":
                continue

            total_tside_gun_rounds += 1

            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))

            if not all_kills:
                continue

            first_kill = all_kills[0]
            killer = first_kill["killer"]
            if killer not in team_puuids:
                continue

            total_ucam_entry_rounds += 1
            bucket = "target" if killer in famsii_puuids else "teammate"
            won = rr["winningTeam"] == md.team_id

            buckets[bucket]["rounds"] += 1
            if won:
                buckets[bucket]["wins"] += 1

            examples = buckets[bucket]["examples"]
            if len(examples) < 5:
                examples.append(
                    {
                        "match_id": md.match_id,
                        "map": md.map,
                        "date": md.date,
                        "round_num": round_num,
                        "killer": names_by_puuid.get(killer, killer),
                        "won": won,
                    }
                )

    output = {
        "scope": {
            "team": TEAM_NAME,
            "player": target_player,
            "side": "T-side",
            "economy_filter": "gun",
            "valid_maps": len(matches),
            "total_tside_gun_rounds": total_tside_gun_rounds,
            "total_ucam_entry_rounds": total_ucam_entry_rounds,
        },
        "target_entry": {
            "rounds": buckets["target"]["rounds"],
            "wins": buckets["target"]["wins"],
            "win_pct": pct(buckets["target"]["wins"], buckets["target"]["rounds"]),
            "examples": buckets["target"]["examples"],
        },
        "teammate_entry": {
            "rounds": buckets["teammate"]["rounds"],
            "wins": buckets["teammate"]["wins"],
            "win_pct": pct(buckets["teammate"]["wins"], buckets["teammate"]["rounds"]),
            "examples": buckets["teammate"]["examples"],
        },
        "difference_pp": round(
            pct(buckets["target"]["wins"], buckets["target"]["rounds"])
            - pct(buckets["teammate"]["wins"], buckets["teammate"]["rounds"]),
            2,
        ),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
