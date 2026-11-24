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
TARGET_PLAYERS = ("Proxh", "Lime")


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def make_bucket() -> dict[str, int]:
    return {"rounds": 0, "wins": 0}


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    players = {player: player.lower() for player in TARGET_PLAYERS}

    total_ct_rounds = 0
    total_ct_round_wins = 0

    metrics: dict[str, dict[str, object]] = {}
    for player in TARGET_PLAYERS:
        metrics[player] = {
            "first_kill": make_bucket(),
            "first_death": make_bucket(),
            "opening_involved_rounds": 0,
            "multikill_2plus": make_bucket(),
            "site_first_kill": defaultdict(make_bucket),
            "site_first_death": defaultdict(make_bucket),
        }

    for md in matches:
        team_puuids = {p["puuid"] for p in md.team_players}
        sides = get_team_side_per_round(md, team_puuids)
        names_by_puuid = {
            p["puuid"]: strip_prefix(p.get("gameName", ""))
            for p in md.team_players
        }
        puuids_by_player = {
            player: {
                puuid for puuid, name in names_by_puuid.items() if name.lower() == player_lower
            }
            for player, player_lower in players.items()
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

            site = rr.get("plantSite") or ""
            site_key = f"{md.map}:{site}" if site else None

            kill_counts = defaultdict(int)
            for ps in rr.get("playerStats", []):
                kill_counts[ps["puuid"]] += len(ps.get("kills", []))

            for player in TARGET_PLAYERS:
                target_puuids = puuids_by_player[player]
                player_metrics = metrics[player]

                if first_killer in target_puuids:
                    player_metrics["first_kill"]["rounds"] += 1
                    if won:
                        player_metrics["first_kill"]["wins"] += 1
                    player_metrics["opening_involved_rounds"] += 1
                    if site_key:
                        player_metrics["site_first_kill"][site_key]["rounds"] += 1
                        if won:
                            player_metrics["site_first_kill"][site_key]["wins"] += 1
                elif first_victim in target_puuids:
                    player_metrics["first_death"]["rounds"] += 1
                    if won:
                        player_metrics["first_death"]["wins"] += 1
                    player_metrics["opening_involved_rounds"] += 1
                    if site_key:
                        player_metrics["site_first_death"][site_key]["rounds"] += 1
                        if won:
                            player_metrics["site_first_death"][site_key]["wins"] += 1

                if any(kill_counts.get(puuid, 0) >= 2 for puuid in target_puuids):
                    player_metrics["multikill_2plus"]["rounds"] += 1
                    if won:
                        player_metrics["multikill_2plus"]["wins"] += 1

    output = {
        "scope": {
            "team": TEAM_NAME,
            "valid_maps": len(matches),
            "total_ct_rounds": total_ct_rounds,
            "team_ct_round_wins": total_ct_round_wins,
            "team_ct_round_win_pct": pct(total_ct_round_wins, total_ct_rounds),
            "site_specific_note": (
                "Site-specific metrics use CT rounds with a labeled plant site; "
                "elimination rounds without a plant are not site-attributed."
            ),
        },
        "players": {},
    }

    for player in TARGET_PLAYERS:
        player_metrics = metrics[player]
        fk_rounds = player_metrics["first_kill"]["rounds"]
        fk_wins = player_metrics["first_kill"]["wins"]
        fd_rounds = player_metrics["first_death"]["rounds"]
        fd_wins = player_metrics["first_death"]["wins"]
        mk_rounds = player_metrics["multikill_2plus"]["rounds"]
        mk_wins = player_metrics["multikill_2plus"]["wins"]
        opening_involved = player_metrics["opening_involved_rounds"]

        site_fk = []
        for site_name, data in sorted(
            player_metrics["site_first_kill"].items(), key=lambda item: (-item[1]["rounds"], item[0])
        ):
            site_fk.append(
                {
                    "site": site_name,
                    "rounds": data["rounds"],
                    "wins": data["wins"],
                    "win_pct": pct(data["wins"], data["rounds"]),
                }
            )

        site_fd = []
        for site_name, data in sorted(
            player_metrics["site_first_death"].items(), key=lambda item: (-item[1]["rounds"], item[0])
        ):
            site_fd.append(
                {
                    "site": site_name,
                    "rounds": data["rounds"],
                    "wins": data["wins"],
                    "win_pct": pct(data["wins"], data["rounds"]),
                }
            )

        output["players"][player] = {
            "ct_fk_conversion": {
                "rounds": fk_rounds,
                "wins": fk_wins,
                "win_pct": pct(fk_wins, fk_rounds),
                "uplift_vs_team_ct_baseline_pp": round(
                    pct(fk_wins, fk_rounds) - pct(total_ct_round_wins, total_ct_rounds), 2
                ),
            },
            "ct_fd_salvage": {
                "rounds": fd_rounds,
                "wins": fd_wins,
                "win_pct": pct(fd_wins, fd_rounds),
                "drop_vs_team_ct_baseline_pp": round(
                    pct(fd_wins, fd_rounds) - pct(total_ct_round_wins, total_ct_rounds), 2
                ),
            },
            "ct_opening_swing_pp": round(
                pct(fk_wins, fk_rounds) - pct(fd_wins, fd_rounds), 2
            ),
            "ct_opening_duel_rate": {
                "rounds_involved": opening_involved,
                "pct_of_all_ct_rounds": pct(opening_involved, total_ct_rounds),
            },
            "ct_multikill_conversion_2plus": {
                "rounds": mk_rounds,
                "wins": mk_wins,
                "win_pct": pct(mk_wins, mk_rounds),
            },
            "site_specific_ct_first_kill": site_fk,
            "site_specific_ct_first_death": site_fd,
        }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
