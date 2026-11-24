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
TARGET_PLAYER = "QutionerX"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def make_bucket() -> dict[str, int]:
    return {"rounds": 0, "wins": 0}


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    target_lower = TARGET_PLAYER.lower()

    target_bucket = make_bucket()
    teammate_bucket = make_bucket()
    target_first_death_rounds = 0
    teammate_first_death_rounds = 0
    individual_teammates: dict[str, dict[str, int]] = {}

    total_t_rounds = 0
    total_team_entry_rounds = 0

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
            if sides.get(round_num) != "atk":
                continue

            total_t_rounds += 1

            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))

            if not all_kills:
                continue

            first_kill = all_kills[0]
            killer = first_kill["killer"]
            victim = first_kill["victim"]
            won = rr["winningTeam"] == md.team_id

            if killer in target_puuids:
                total_team_entry_rounds += 1
                target_bucket["rounds"] += 1
                if won:
                    target_bucket["wins"] += 1
            elif killer in team_puuids:
                total_team_entry_rounds += 1
                teammate_bucket["rounds"] += 1
                if won:
                    teammate_bucket["wins"] += 1
                killer_name = names_by_puuid.get(killer, killer)
                if killer_name not in individual_teammates:
                    individual_teammates[killer_name] = make_bucket()
                individual_teammates[killer_name]["rounds"] += 1
                if won:
                    individual_teammates[killer_name]["wins"] += 1

            if victim in target_puuids:
                target_first_death_rounds += 1
            elif victim in team_puuids:
                teammate_first_death_rounds += 1
                victim_name = names_by_puuid.get(victim, victim)
                if victim_name not in individual_teammates:
                    individual_teammates[victim_name] = make_bucket()
                individual_teammates[victim_name].setdefault("first_deaths", 0)
                individual_teammates[victim_name]["first_deaths"] += 1

    teammate_rows = []
    for player_name, data in sorted(
        individual_teammates.items(),
        key=lambda item: (
            -(
                item[1]["rounds"]
                / max(item[1]["rounds"] + item[1].get("first_deaths", 0), 1)
            ),
            -item[1]["rounds"],
            item[0].lower(),
        ),
    ):
        first_deaths = data.get("first_deaths", 0)
        opening_duels = data["rounds"] + first_deaths
        teammate_rows.append(
            {
                "player": player_name,
                "entry_frags": data["rounds"],
                "first_deaths": first_deaths,
                "opening_duel_success_pct": pct(data["rounds"], opening_duels),
                "wins": data["wins"],
                "rounds": data["rounds"],
                "win_pct": pct(data["wins"], data["rounds"]),
            }
        )

    target_opening_duels = target_bucket["rounds"] + target_first_death_rounds
    teammate_opening_duels = teammate_bucket["rounds"] + teammate_first_death_rounds

    output = {
        "scope": {
            "team": TEAM_NAME,
            "player": TARGET_PLAYER,
            "side": "T-side",
            "economy_filter": "all",
            "valid_maps": len(matches),
            "total_t_rounds": total_t_rounds,
            "total_team_entry_rounds": total_team_entry_rounds,
        },
        "target_entry": {
            "entry_frags": target_bucket["rounds"],
            "first_deaths": target_first_death_rounds,
            "opening_duel_success_pct": pct(target_bucket["rounds"], target_opening_duels),
            "wins": target_bucket["wins"],
            "rounds": target_bucket["rounds"],
            "win_pct": pct(target_bucket["wins"], target_bucket["rounds"]),
        },
        "teammates_combined": {
            "entry_frags": teammate_bucket["rounds"],
            "first_deaths": teammate_first_death_rounds,
            "opening_duel_success_pct": pct(teammate_bucket["rounds"], teammate_opening_duels),
            "wins": teammate_bucket["wins"],
            "rounds": teammate_bucket["rounds"],
            "win_pct": pct(teammate_bucket["wins"], teammate_bucket["rounds"]),
        },
        "difference_vs_teammates_pp": round(
            pct(target_bucket["wins"], target_bucket["rounds"])
            - pct(teammate_bucket["wins"], teammate_bucket["rounds"]),
            2,
        ),
        "teammates_individual": teammate_rows,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
