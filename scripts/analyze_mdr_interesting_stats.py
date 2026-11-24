from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import TEAMS
from lib.match_parser import load_team_matches
from lib.stats_engine import compute_team_stats
from lib.json_builder import build_stats_json


TARGET_TAG = "MDR"
TARGET_TEAM = "Mandatory"
VETO_FILE = "vetoData.ts"


def rank_desc(items: list[tuple[str, float]]) -> dict[str, int]:
    ordered = sorted(items, key=lambda item: (-item[1], item[0]))
    return {name: idx + 1 for idx, (name, _value) in enumerate(ordered)}


def parse_mdr_vetoes() -> dict[str, object]:
    text = open(VETO_FILE, "r", encoding="utf-8").read()
    block_match = re.search(r"const MDR_MATCHES: VetoMatch\[\] = \[(.*?)\n\]\n", text, re.S)
    if not block_match:
        return {}

    block = block_match.group(1)
    match_entries = re.findall(
        r"\{ date: '([^']+)', opponent: '([^']+)', tournament: '([^']+)', score: '([^']+)', format: '([^']+)', vetoes: \[(.*?)\] \}",
        block,
        re.S,
    )

    series = []
    first_bans = Counter()
    first_picks = Counter()
    deciders = Counter()

    for date, opponent, tournament, score, fmt, veto_blob in match_entries:
        steps = re.findall(r"\['([^']+)','([^']+)','([^']+)'\]", veto_blob)
        vetoes = [{"action": a, "team": t, "map": m} for a, t, m in steps]
        series.append(
            {
                "date": date,
                "opponent": opponent,
                "tournament": tournament,
                "score": score,
                "format": fmt,
                "vetoes": vetoes,
            }
        )

        for step in vetoes:
            if step["action"].startswith("Ban") and step["team"] == TARGET_TAG:
                first_bans[step["map"]] += 1
                break
        for step in vetoes:
            if step["action"].startswith("Pick") and step["team"] == TARGET_TAG:
                first_picks[step["map"]] += 1
                break
        for step in vetoes:
            if step["action"] == "Decider":
                deciders[step["map"]] += 1

    return {
        "series_count": len(series),
        "first_bans": first_bans,
        "first_picks": first_picks,
        "deciders": deciders,
        "recent_series": sorted(series, key=lambda row: row["date"], reverse=True)[:5],
    }


def main() -> None:
    all_team_data = {}
    for team_cfg in TEAMS:
        matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])
        stats = compute_team_stats(matches, team_cfg["tag"], team_cfg["name"])
        all_team_data[team_cfg["tag"]] = {
            "name": team_cfg["name"],
            "tag": team_cfg["tag"],
            **stats,
        }

    result = build_stats_json(all_team_data)

    teams = result["teams"]
    team_by_tag = {team["tag"]: team for team in teams}
    mdr = team_by_tag[TARGET_TAG]
    all_maps = mdr["allMaps"]

    team_metric_labels = {
        "rW_pct": "overall_round_win_pct",
        "atk_rW_pct": "t_side_win_pct",
        "def_rW_pct": "ct_side_win_pct",
        "pistol_rW_pct": "pistol_win_pct",
        "pistol_atk_rW_pct": "t_pistol_win_pct",
        "pistol_def_rW_pct": "ct_pistol_win_pct",
        "gun_rW_pct": "gun_round_win_pct",
        "antieco_rW_pct": "anti_eco_win_pct",
        "eco_rW_pct": "eco_win_pct",
        "post_rW_pct": "postplant_win_pct",
        "ret_rW_pct": "retake_win_pct",
        "post_per_map": "postplants_per_map",
        "ret_per_map": "retakes_per_map",
    }

    metric_ranks = {}
    for raw_key, label in team_metric_labels.items():
        ranking = rank_desc([(team["tag"], team["allMaps"][raw_key]) for team in teams])
        metric_ranks[label] = {
            "value": round(all_maps[raw_key] * 100, 2) if raw_key.endswith("_pct") else round(all_maps[raw_key], 2),
            "rank": ranking[TARGET_TAG],
        }

    notable_team_metrics = {
        label: data
        for label, data in metric_ranks.items()
        if data["rank"] <= 3 or data["rank"] >= 12
    }

    played_maps = [row for row in mdr["maps"] if row["plays"] > 0]
    best_map = max(played_maps, key=lambda row: (row["rW_pct"], row["plays"]))
    worst_map = min(played_maps, key=lambda row: (row["rW_pct"], -row["plays"]))
    best_ct_map = max(played_maps, key=lambda row: (row["def_rW_pct"], row["plays"]))
    best_t_map = max(played_maps, key=lambda row: (row["atk_rW_pct"], row["plays"]))

    leaderboard_hits = []
    for board_name, board in result["leaderboards"].items():
        for entry in board["entries"]:
            if entry["team"] == TARGET_TEAM and entry["rank"] <= 10:
                leaderboard_hits.append(
                    {
                        "leaderboard": board_name,
                        "rank": entry["rank"],
                        "player": entry["ign"],
                        "value": entry["value"],
                    }
                )
    leaderboard_hits.sort(key=lambda row: (row["rank"], row["leaderboard"], row["player"]))

    mdr_players = [player for player in result["players"] if player["team"] == TARGET_TEAM]
    top_player_by_vlr = max(mdr_players, key=lambda row: row["vlr_rating"])
    top_player_by_adr = max(mdr_players, key=lambda row: row["adr"])
    top_player_by_kast = max(mdr_players, key=lambda row: row["kast"])

    league_xvy = defaultdict(list)
    for team in teams:
        for row in team["xvy"]:
            league_xvy[row["situation"]].append(row["win_pct"])
    league_xvy_avg = {
        situation: round(sum(values) / len(values), 3) if values else 0
        for situation, values in league_xvy.items()
    }

    mdr_xvy = []
    for row in mdr["xvy"]:
        league_avg = league_xvy_avg.get(row["situation"], 0)
        delta = round((row["win_pct"] - league_avg) * 100, 2)
        sample = row["wins"] + row["losses"]
        if sample >= 8:
            mdr_xvy.append(
                {
                    "situation": row["situation"],
                    "sample": sample,
                    "win_pct": round(row["win_pct"] * 100, 2),
                    "league_avg_pct": round(league_avg * 100, 2),
                    "delta_pp": delta,
                }
            )
    best_xvy = sorted(mdr_xvy, key=lambda row: (-row["delta_pp"], -row["sample"]))[:3]
    worst_xvy = sorted(mdr_xvy, key=lambda row: (row["delta_pp"], -row["sample"]))[:3]

    veto = parse_mdr_vetoes()
    first_bans = [
        {"map": name, "count": count}
        for name, count in veto.get("first_bans", Counter()).most_common()
    ]
    first_picks = [
        {"map": name, "count": count}
        for name, count in veto.get("first_picks", Counter()).most_common()
    ]
    deciders = [
        {"map": name, "count": count}
        for name, count in veto.get("deciders", Counter()).most_common()
    ]

    out = {
        "team_summary": {
            "team": mdr["name"],
            "maps": all_maps["plays"],
            "map_record": {"wins": all_maps["wins"], "losses": all_maps["losses"]},
            "series_record": mdr["series_record"],
            "form": mdr["form"],
        },
        "league_ranks": notable_team_metrics,
        "map_insights": {
            "best_map_overall": {
                "map": best_map["map"],
                "plays": best_map["plays"],
                "record": f'{best_map["wins"]}-{best_map["losses"]}',
                "round_win_pct": round(best_map["rW_pct"] * 100, 2),
            },
            "worst_map_overall": {
                "map": worst_map["map"],
                "plays": worst_map["plays"],
                "record": f'{worst_map["wins"]}-{worst_map["losses"]}',
                "round_win_pct": round(worst_map["rW_pct"] * 100, 2),
            },
            "best_ct_map": {
                "map": best_ct_map["map"],
                "ct_win_pct": round(best_ct_map["def_rW_pct"] * 100, 2),
                "plays": best_ct_map["plays"],
            },
            "best_t_map": {
                "map": best_t_map["map"],
                "t_win_pct": round(best_t_map["atk_rW_pct"] * 100, 2),
                "plays": best_t_map["plays"],
            },
        },
        "player_leaderboards": leaderboard_hits,
        "player_highlights": {
            "best_vlr_rating": {
                "player": top_player_by_vlr["ign"],
                "value": top_player_by_vlr["vlr_rating"],
            },
            "best_adr": {
                "player": top_player_by_adr["ign"],
                "value": top_player_by_adr["adr"],
            },
            "best_kast": {
                "player": top_player_by_kast["ign"],
                "value": top_player_by_kast["kast"],
            },
        },
        "xvy_highlights": {
            "best": best_xvy,
            "worst": worst_xvy,
        },
        "veto_tendencies": {
            "series_count": veto.get("series_count", 0),
            "first_bans": first_bans,
            "first_picks": first_picks,
            "deciders": deciders,
            "recent_series": veto.get("recent_series", []),
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
