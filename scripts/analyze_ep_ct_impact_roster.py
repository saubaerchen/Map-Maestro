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


def make_bucket() -> dict[str, int]:
    return {"rounds": 0, "wins": 0}


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)

    total_ct_rounds = 0
    total_ct_round_wins = 0
    team_first_kill = make_bucket()
    team_first_death = make_bucket()
    team_multikill = make_bucket()

    player_metrics: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "first_kill": make_bucket(),
            "first_death": make_bucket(),
            "opening_involved_rounds": 0,
            "multikill_2plus": make_bucket(),
            "site_first_kill": defaultdict(make_bucket),
            "site_first_death": defaultdict(make_bucket),
        }
    )

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

            first_killer = all_kills[0]["killer"] if all_kills else None
            first_victim = all_kills[0]["victim"] if all_kills else None

            site = rr.get("plantSite") or ""
            site_key = f"{md.map}:{site}" if site else None

            kill_counts = defaultdict(int)
            for ps in rr.get("playerStats", []):
                kill_counts[ps["puuid"]] += len(ps.get("kills", []))

            if first_killer in team_puuids:
                team_first_kill["rounds"] += 1
                if won:
                    team_first_kill["wins"] += 1
                player_name = names_by_puuid.get(first_killer, first_killer)
                player_metrics[player_name]["first_kill"]["rounds"] += 1
                if won:
                    player_metrics[player_name]["first_kill"]["wins"] += 1
                player_metrics[player_name]["opening_involved_rounds"] += 1
                if site_key:
                    player_metrics[player_name]["site_first_kill"][site_key]["rounds"] += 1
                    if won:
                        player_metrics[player_name]["site_first_kill"][site_key]["wins"] += 1

            elif first_victim in team_puuids:
                team_first_death["rounds"] += 1
                if won:
                    team_first_death["wins"] += 1
                player_name = names_by_puuid.get(first_victim, first_victim)
                player_metrics[player_name]["first_death"]["rounds"] += 1
                if won:
                    player_metrics[player_name]["first_death"]["wins"] += 1
                player_metrics[player_name]["opening_involved_rounds"] += 1
                if site_key:
                    player_metrics[player_name]["site_first_death"][site_key]["rounds"] += 1
                    if won:
                        player_metrics[player_name]["site_first_death"][site_key]["wins"] += 1

            for puuid, count in kill_counts.items():
                if puuid not in team_puuids or count < 2:
                    continue
                team_multikill["rounds"] += 1
                if won:
                    team_multikill["wins"] += 1
                player_name = names_by_puuid.get(puuid, puuid)
                player_metrics[player_name]["multikill_2plus"]["rounds"] += 1
                if won:
                    player_metrics[player_name]["multikill_2plus"]["wins"] += 1

    team_ct_win_pct = pct(total_ct_round_wins, total_ct_rounds)
    team_fk_pct = pct(team_first_kill["wins"], team_first_kill["rounds"])
    team_fd_pct = pct(team_first_death["wins"], team_first_death["rounds"])
    team_swing = round(team_fk_pct - team_fd_pct, 2)
    roster_avg_opening_rate = round(
        sum((data["opening_involved_rounds"] / total_ct_rounds) * 100 for data in player_metrics.values())
        / max(len(player_metrics), 1),
        2,
    )
    team_multikill_pct = pct(team_multikill["wins"], team_multikill["rounds"])

    players_out = []
    for player_name, data in sorted(player_metrics.items(), key=lambda item: item[0].lower()):
        fk_rounds = data["first_kill"]["rounds"]
        fk_wins = data["first_kill"]["wins"]
        fd_rounds = data["first_death"]["rounds"]
        fd_wins = data["first_death"]["wins"]
        mk_rounds = data["multikill_2plus"]["rounds"]
        mk_wins = data["multikill_2plus"]["wins"]
        opening_rate = round((data["opening_involved_rounds"] / total_ct_rounds) * 100, 2) if total_ct_rounds else 0.0

        top_site_fk = None
        if data["site_first_kill"]:
            site_name, site_data = max(
                data["site_first_kill"].items(),
                key=lambda item: (item[1]["rounds"], item[1]["wins"]),
            )
            top_site_fk = {
                "site": site_name,
                "rounds": site_data["rounds"],
                "wins": site_data["wins"],
                "win_pct": pct(site_data["wins"], site_data["rounds"]),
            }

        top_site_fd = None
        if data["site_first_death"]:
            site_name, site_data = max(
                data["site_first_death"].items(),
                key=lambda item: (item[1]["rounds"], item[1]["wins"]),
            )
            top_site_fd = {
                "site": site_name,
                "rounds": site_data["rounds"],
                "wins": site_data["wins"],
                "win_pct": pct(site_data["wins"], site_data["rounds"]),
            }

        players_out.append(
            {
                "player": player_name,
                "ct_fk_conversion_pct": pct(fk_wins, fk_rounds),
                "ct_fk_rounds": fk_rounds,
                "ct_fd_salvage_pct": pct(fd_wins, fd_rounds),
                "ct_fd_rounds": fd_rounds,
                "ct_opening_swing_pp": round(pct(fk_wins, fk_rounds) - pct(fd_wins, fd_rounds), 2),
                "ct_opening_duel_rate_pct": opening_rate,
                "ct_multikill_conversion_pct": pct(mk_wins, mk_rounds),
                "ct_multikill_rounds": mk_rounds,
                "site_specific_top_fk": top_site_fk,
                "site_specific_top_fd": top_site_fd,
            }
        )

    output = {
        "scope": {
            "team": TEAM_NAME,
            "valid_maps": len(matches),
            "total_ct_rounds": total_ct_rounds,
        },
        "team_baselines": {
            "overall_ct_round_win_pct": team_ct_win_pct,
            "ct_fk_conversion_pct": team_fk_pct,
            "ct_fd_salvage_pct": team_fd_pct,
            "ct_opening_swing_pp": team_swing,
            "average_player_opening_duel_rate_pct": roster_avg_opening_rate,
            "ct_multikill_conversion_pct": team_multikill_pct,
            "site_specific_note": (
                "Top site-specific rows are the player's most frequent planted-site CT first-kill "
                "and first-death buckets; elimination rounds without a plant are excluded."
            ),
        },
        "players": players_out,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
