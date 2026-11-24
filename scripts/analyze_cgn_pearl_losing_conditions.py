from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import classify_round_economy, get_team_side_per_round


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
CGN_GAME_NAME = "CGN DaviH"
CGN_TAG_LINE = "epval"
CGN_PREFIX = "CGN "
CGN_SUMMARY_FILE = ROOT / "data" / "raw" / "cgn_2026_matches_detail.json"


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return match.group(1)


def api_get_json(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def identify_cgn_context(match_obj: dict) -> tuple[str, list[dict], list[dict], set[str]]:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if str(player.get("gameName", "")).startswith(CGN_PREFIX):
            team_id = player.get("teamId")
            break
    if team_id is None:
        raise RuntimeError("Could not identify CGN team in fetched match")

    team_players = []
    opp_players = []
    team_puuids = set()
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
            team_puuids.add(player["puuid"])
        else:
            opp_players.append(player)
    return team_id, team_players, opp_players, team_puuids


def blank_metrics() -> dict:
    return {
        "rounds": 0,
        "wins": 0,
        "losses": 0,
        "by_side": {
            "atk": {
                "rounds": 0,
                "wins": 0,
                "plants": 0,
                "postplants_won": 0,
                "postplants_total": 0,
                "plant_time_sum": 0,
                "plant_time_count": 0,
            },
            "def": {"rounds": 0, "wins": 0, "enemy_plants": 0, "retake_wins": 0, "retake_total": 0},
        },
        "pistols": {"rounds": 0, "wins": 0},
        "openings": {
            "fk_rounds": 0,
            "fk_wins": 0,
            "fd_rounds": 0,
            "fd_wins": 0,
            "side": {
                "atk": {"fk_rounds": 0, "fk_wins": 0, "fd_rounds": 0, "fd_wins": 0},
                "def": {"fk_rounds": 0, "fk_wins": 0, "fd_rounds": 0, "fd_wins": 0},
            },
        },
        "economy": {
            "gun": {"rounds": 0, "wins": 0},
            "non_gun": {"rounds": 0, "wins": 0},
        },
        "maps": [],
        "postplant_rounds": [],
    }


def pct(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num * 100.0 / den, 2)


def summarize_metrics(metrics: dict) -> dict:
    atk = metrics["by_side"]["atk"]
    deff = metrics["by_side"]["def"]
    openings = metrics["openings"]
    gun = metrics["economy"]["gun"]
    non_gun = metrics["economy"]["non_gun"]
    return {
        "map_count": len(metrics["maps"]),
        "round_win_rate": pct(metrics["wins"], metrics["rounds"]),
        "t_side_win_rate": pct(atk["wins"], atk["rounds"]),
        "ct_side_win_rate": pct(deff["wins"], deff["rounds"]),
        "pistol_win_rate": pct(metrics["pistols"]["wins"], metrics["pistols"]["rounds"]),
        "fk_rate": pct(openings["fk_rounds"], metrics["rounds"]),
        "fk_conversion": pct(openings["fk_wins"], openings["fk_rounds"]),
        "fd_salvage": pct(openings["fd_wins"], openings["fd_rounds"]),
        "t_fk_conversion": pct(openings["side"]["atk"]["fk_wins"], openings["side"]["atk"]["fk_rounds"]),
        "ct_fk_conversion": pct(openings["side"]["def"]["fk_wins"], openings["side"]["def"]["fk_rounds"]),
        "t_fd_salvage": pct(openings["side"]["atk"]["fd_wins"], openings["side"]["atk"]["fd_rounds"]),
        "ct_fd_salvage": pct(openings["side"]["def"]["fd_wins"], openings["side"]["def"]["fd_rounds"]),
        "postplant_rate_on_t": pct(atk["postplants_total"], atk["rounds"]),
        "postplant_win_rate": pct(atk["postplants_won"], atk["postplants_total"]),
        "avg_t_plant_time_ms": round(atk["plant_time_sum"] / atk["plant_time_count"], 2) if atk["plant_time_count"] else None,
        "enemy_plant_rate_on_ct": pct(deff["enemy_plants"], deff["rounds"]),
        "retake_success": pct(deff["retake_wins"], deff["retake_total"]),
        "gun_round_win_rate": pct(gun["wins"], gun["rounds"]),
        "non_gun_round_win_rate": pct(non_gun["wins"], non_gun["rounds"]),
        "postplant_breakdown": summarize_postplants(metrics["postplant_rounds"]),
        "raw": metrics,
    }


def alive_counts_at_time(rr: dict, team_puuids: set[str], cutoff_ms: int) -> tuple[int, int]:
    team_alive = set(team_puuids)
    opp_alive = set()
    for ps in rr.get("playerStats", []):
        puuid = ps.get("puuid")
        if puuid not in team_puuids:
            opp_alive.add(puuid)

    for ps in rr.get("playerStats", []):
        for kill in ps.get("kills", []):
            if kill.get("timeSinceRoundStartMillis", 999999) > cutoff_ms:
                continue
            victim = kill.get("victim")
            team_alive.discard(victim)
            opp_alive.discard(victim)

    return len(team_alive), len(opp_alive)


def summarize_postplants(rounds: list[dict]) -> dict:
    if not rounds:
        return {"count": 0}

    won = [r for r in rounds if r["won"]]
    lost = [r for r in rounds if not r["won"]]

    def avg(rows: list[dict], key: str) -> float | None:
        if not rows:
            return None
        return round(sum(r[key] for r in rows) / len(rows), 2)

    def count_if(rows: list[dict], pred) -> int:
        return sum(1 for r in rows if pred(r))

    site_counts = defaultdict(lambda: {"won": 0, "lost": 0})
    plant_state_counts = defaultdict(lambda: {"won": 0, "lost": 0})
    for row in rounds:
        site_counts[row["site"]]["won" if row["won"] else "lost"] += 1
        state_label = f"{row['team_alive_at_plant']}v{row['opp_alive_at_plant']}"
        plant_state_counts[state_label]["won" if row["won"] else "lost"] += 1

    return {
        "count": len(rounds),
        "win_rate": pct(len(won), len(rounds)),
        "won": {
            "count": len(won),
            "avg_plant_time_ms": avg(won, "plant_time"),
            "avg_team_alive_at_plant": avg(won, "team_alive_at_plant"),
            "avg_opp_alive_at_plant": avg(won, "opp_alive_at_plant"),
            "first_postplant_kill_rate": pct(count_if(won, lambda r: r["first_postplant_kill_by_team"] is True), len(won)),
            "defuse_loss_rate": pct(count_if(won, lambda r: r["ended_by_defuse"]), len(won)),
            "avg_postplant_kill_diff": avg(won, "postplant_kill_diff"),
        },
        "lost": {
            "count": len(lost),
            "avg_plant_time_ms": avg(lost, "plant_time"),
            "avg_team_alive_at_plant": avg(lost, "team_alive_at_plant"),
            "avg_opp_alive_at_plant": avg(lost, "opp_alive_at_plant"),
            "first_postplant_kill_rate": pct(count_if(lost, lambda r: r["first_postplant_kill_by_team"] is True), len(lost)),
            "defuse_loss_rate": pct(count_if(lost, lambda r: r["ended_by_defuse"]), len(lost)),
            "avg_postplant_kill_diff": avg(lost, "postplant_kill_diff"),
        },
        "by_site": dict(site_counts),
        "by_numbers_at_plant": dict(plant_state_counts),
        "loss_details": lost,
    }


def analyze_match(match_obj: dict) -> tuple[str, dict]:
    team_id, team_players, _, team_puuids = identify_cgn_context(match_obj)
    md = SimpleNamespace(round_results=match_obj["roundResults"], team_players=team_players)
    sides = get_team_side_per_round(md, team_puuids)
    metrics = blank_metrics()
    info = match_obj["matchInfo"]
    map_name = info["map"].split("/")[-1]

    own_score = opp_score = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            own_score = team.get("roundsWon", 0)
        else:
            opp_score = team.get("roundsWon", 0)

    metrics["maps"].append(
        {
            "date": info["gameStartMillis"],
            "match_id": info["matchId"],
            "score": f"{own_score}-{opp_score}",
        }
    )

    for rr in match_obj.get("roundResults", []):
        rnum = rr["roundNum"]
        side = sides.get(rnum, "atk")
        won = rr.get("winningTeam") == team_id

        metrics["rounds"] += 1
        metrics["wins"] += 1 if won else 0
        metrics["losses"] += 0 if won else 1
        metrics["by_side"][side]["rounds"] += 1
        metrics["by_side"][side]["wins"] += 1 if won else 0

        if rnum in (0, 12):
            metrics["pistols"]["rounds"] += 1
            metrics["pistols"]["wins"] += 1 if won else 0

        econ = classify_round_economy(rr, rnum, team_puuids)
        econ_bucket = "gun" if econ in {"gun", "force"} else "non_gun"
        metrics["economy"][econ_bucket]["rounds"] += 1
        metrics["economy"][econ_bucket]["wins"] += 1 if won else 0

        planter = rr.get("bombPlanter")
        if planter and side == "atk" and planter in team_puuids:
            metrics["by_side"]["atk"]["plants"] += 1
            metrics["by_side"]["atk"]["postplants_total"] += 1
            metrics["by_side"]["atk"]["postplants_won"] += 1 if won else 0
            plant_time = rr.get("plantRoundTime")
            if plant_time:
                metrics["by_side"]["atk"]["plant_time_sum"] += plant_time
                metrics["by_side"]["atk"]["plant_time_count"] += 1
                team_alive_at_plant, opp_alive_at_plant = alive_counts_at_time(rr, team_puuids, plant_time)
                postplant_kills = []
                for ps in rr.get("playerStats", []):
                    for kill in ps.get("kills", []):
                        if kill.get("timeSinceRoundStartMillis", -1) > plant_time:
                            postplant_kills.append(kill)
                postplant_kills.sort(key=lambda item: item.get("timeSinceRoundStartMillis", 999999))
                team_postplant_kills = sum(1 for kill in postplant_kills if kill.get("killer") in team_puuids)
                opp_postplant_kills = len(postplant_kills) - team_postplant_kills
                first_postplant_kill_by_team = None
                if postplant_kills:
                    first_postplant_kill_by_team = postplant_kills[0].get("killer") in team_puuids
                metrics["postplant_rounds"].append(
                    {
                        "round_num": rnum + 1,
                        "won": won,
                        "site": rr.get("plantSite", "?"),
                        "plant_time": plant_time,
                        "team_alive_at_plant": team_alive_at_plant,
                        "opp_alive_at_plant": opp_alive_at_plant,
                        "first_postplant_kill_by_team": first_postplant_kill_by_team,
                        "team_postplant_kills": team_postplant_kills,
                        "opp_postplant_kills": opp_postplant_kills,
                        "postplant_kill_diff": team_postplant_kills - opp_postplant_kills,
                        "ended_by_defuse": bool(rr.get("defuseRoundTime")),
                        "round_result": rr.get("roundResult"),
                    }
                )
        elif planter and side == "def" and planter not in team_puuids:
            metrics["by_side"]["def"]["enemy_plants"] += 1
            metrics["by_side"]["def"]["retake_total"] += 1
            metrics["by_side"]["def"]["retake_wins"] += 1 if won else 0

        kills = []
        for ps in rr.get("playerStats", []):
            for kill in ps.get("kills", []):
                kills.append(kill)
        kills.sort(key=lambda item: item.get("timeSinceRoundStartMillis", 999999))
        if not kills:
            continue

        first = kills[0]
        killer_in_team = first.get("killer") in team_puuids
        if killer_in_team:
            metrics["openings"]["fk_rounds"] += 1
            metrics["openings"]["fk_wins"] += 1 if won else 0
            metrics["openings"]["side"][side]["fk_rounds"] += 1
            metrics["openings"]["side"][side]["fk_wins"] += 1 if won else 0
        else:
            metrics["openings"]["fd_rounds"] += 1
            metrics["openings"]["fd_wins"] += 1 if won else 0
            metrics["openings"]["side"][side]["fd_rounds"] += 1
            metrics["openings"]["side"][side]["fd_wins"] += 1 if won else 0

    return map_name, metrics


def merge_into(target: dict, src: dict) -> None:
    target["rounds"] += src["rounds"]
    target["wins"] += src["wins"]
    target["losses"] += src["losses"]
    target["pistols"]["rounds"] += src["pistols"]["rounds"]
    target["pistols"]["wins"] += src["pistols"]["wins"]
    target["maps"].extend(src["maps"])

    for side in ("atk", "def"):
        for key in target["by_side"][side]:
            target["by_side"][side][key] += src["by_side"][side][key]
        for key in target["openings"]["side"][side]:
            target["openings"]["side"][side][key] += src["openings"]["side"][side][key]

    for key in ("fk_rounds", "fk_wins", "fd_rounds", "fd_wins"):
        target["openings"][key] += src["openings"][key]

    for bucket in ("gun", "non_gun"):
        for key in ("rounds", "wins"):
            target["economy"][bucket][key] += src["economy"][bucket][key]
    target["postplant_rounds"].extend(src["postplant_rounds"])


def main() -> None:
    api_key = load_api_key()
    account = api_get_json(
        "/api/riot/account/v1/accounts/by-riot-id/esports/"
        + urllib.parse.quote(CGN_GAME_NAME, safe="")
        + "/"
        + urllib.parse.quote(CGN_TAG_LINE, safe=""),
        api_key,
    )
    _ = account["puuid"]

    with CGN_SUMMARY_FILE.open("r", encoding="utf-8") as handle:
        summary_rows = json.load(handle)

    pearl_rows = [row for row in summary_rows if row.get("map") == "Pearl"]

    overall = blank_metrics()
    wins = blank_metrics()
    losses = blank_metrics()
    per_map = []

    for row in pearl_rows:
        match = api_get_json(f"/api/matches/esports/{row['matchId']}", api_key)
        map_name, metrics = analyze_match(match)
        if map_name != "Pearl":
            continue
        merge_into(overall, metrics)
        if row.get("result") == "W":
            merge_into(wins, metrics)
        else:
            merge_into(losses, metrics)
        per_map.append(
            {
                "date": row["date"],
                "opponent": row["opponent"],
                "result": row["result"],
                "score": f"{row['cgn_score']}-{row['opp_score']}",
                "summary": summarize_metrics(metrics),
            }
        )

    report = {
        "pearl_match_ids": [row["matchId"] for row in pearl_rows],
        "t_loss_postplant_focus": summarize_postplants(losses["postplant_rounds"]),
        "overall": summarize_metrics(overall),
        "wins_only": summarize_metrics(wins),
        "losses_only": summarize_metrics(losses),
        "per_map": per_map,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
