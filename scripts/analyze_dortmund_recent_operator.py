from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import OPERATOR_UUID


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
SERIES_TO_FETCH = 3
TEAM_PREFIX_CANDIDATES = ("DXG ", "DoeS ")
LOCAL_SEED_FILES = (
    ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl",
    ROOT / "data" / "raw" / "cgn_2026_matches_detail.json",
)
HISTORY_MATCH_LIMIT = 12


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


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def discover_reference_players() -> list[dict]:
    seen: set[str] = set()
    found: list[dict] = []
    for path in LOCAL_SEED_FILES:
        if path.suffix == ".jsonl":
            matches = load_jsonl(path)
        else:
            matches = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        for match in matches:
            players = match.get("players", [])
            for player in players:
                if player.get("isObserver"):
                    continue
                game_name = player.get("gameName", "")
                if game_name.startswith(TEAM_PREFIX_CANDIDATES):
                    puuid = player["puuid"]
                    if puuid in seen:
                        continue
                    seen.add(puuid)
                    found.append(
                        {
                            "puuid": puuid,
                            "gameName": game_name,
                            "tagLine": player.get("tagLine", ""),
                        }
                    )
    if found:
        return found
    raise RuntimeError("Could not find a Dortmund/DXG player in local seed files")


def local_dt_from_ms(ts_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE)


def player_prefix(name: str) -> str:
    return name.split(" ")[0] if " " in name else name


def detect_team_context(match_obj: dict) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(TEAM_PREFIX_CANDIDATES):
            team_id = player.get("teamId")
            break
    if team_id is None:
        return None

    team_players = []
    opp_players = []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
        else:
            opp_players.append(player)

    team_prefix = Counter(player_prefix(p.get("gameName", "")) for p in team_players).most_common(1)[0][0]
    opp_prefix = Counter(player_prefix(p.get("gameName", "")) for p in opp_players).most_common(1)[0][0]
    return {
        "teamId": team_id,
        "teamPlayers": team_players,
        "oppPlayers": opp_players,
        "teamPrefix": team_prefix,
        "oppPrefix": opp_prefix,
    }


def match_score(match_obj: dict, team_id: str) -> tuple[int, int]:
    team_score = 0
    opp_score = 0
    for team in match_obj.get("teams", []):
        rounds_won = team.get("roundsWon", 0)
        if team.get("teamId") == team_id:
            team_score = rounds_won
        else:
            opp_score = rounds_won
    return team_score, opp_score


def location_for_puuid(entries: list[dict] | None, puuid: str) -> dict | None:
    if not entries:
        return None
    for entry in entries:
        if entry.get("puuid") == puuid:
            return entry.get("location")
    return None


def analyze_round(
    rr: dict,
    team_id: str,
    team_puuids: set[str],
    puuid_to_name: dict[str, str],
) -> dict:
    holders = []
    for ps in rr.get("playerStats", []):
        if ps.get("puuid") not in team_puuids:
            continue
        if str(ps.get("economy", {}).get("weapon", "")).upper() == OPERATOR_UUID:
            holders.append(ps.get("puuid"))

    info = {
        "hasTeamOperator": bool(holders),
        "holders": holders,
        "roundWon": rr.get("winningTeam") == team_id,
        "teamOperatorKill": False,
        "opHolderPositionSources": defaultdict(set),
        "opKillSamples": [],
    }

    if not holders:
        return info

    for holder in holders:
        plant_loc = location_for_puuid(rr.get("plantPlayerLocations"), holder)
        if plant_loc:
            info["opHolderPositionSources"][holder].add("plant")
        defuse_loc = location_for_puuid(rr.get("defusePlayerLocations"), holder)
        if defuse_loc:
            info["opHolderPositionSources"][holder].add("defuse")

    all_kills = []
    for ps in rr.get("playerStats", []):
        for kill in ps.get("kills", []):
            all_kills.append(kill)

    for kill in all_kills:
        killer = kill.get("killer")
        victim = kill.get("victim")
        damage_item = str(kill.get("finishingDamage", {}).get("damageItem", "")).upper()

        for holder in holders:
            if location_for_puuid(kill.get("playerLocations"), holder):
                info["opHolderPositionSources"][holder].add("kill_snapshot")
            if victim == holder and kill.get("victimLocation"):
                info["opHolderPositionSources"][holder].add("victim_location")

        if killer in holders and damage_item == OPERATOR_UUID:
            info["teamOperatorKill"] = True
            killer_loc = location_for_puuid(kill.get("playerLocations"), killer)
            if killer_loc:
                info["opHolderPositionSources"][killer].add("operator_kill")
                info["opKillSamples"].append(
                    {
                        "player": puuid_to_name.get(killer, killer),
                        "roundNum": rr.get("roundNum"),
                        "timeSinceRoundStartMillis": kill.get("timeSinceRoundStartMillis"),
                        "location": killer_loc,
                    }
                )

    return info


def main() -> None:
    api_key = load_api_key()
    initial_players = discover_reference_players()
    reference_players_by_puuid = {player["puuid"]: player for player in initial_players}
    match_times: dict[str, int] = {}
    fetched_matches: dict[str, dict] = {}
    processed_players: set[str] = set()

    while True:
        pending = [player for puuid, player in reference_players_by_puuid.items() if puuid not in processed_players]
        if not pending:
            break
        for player in pending:
            processed_players.add(player["puuid"])
            history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{player['puuid']}", api_key)
            for item in history.get("history", [])[:HISTORY_MATCH_LIMIT]:
                match_id = item["matchId"]
                ts = item.get("gameStartTimeMillis", 0)
                if ts > match_times.get(match_id, 0):
                    match_times[match_id] = ts
                if match_id not in fetched_matches:
                    fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
                context = detect_team_context(fetched_matches[match_id])
                if context is None:
                    continue
                for team_player in context["teamPlayers"]:
                    puuid = team_player["puuid"]
                    if puuid not in reference_players_by_puuid:
                        reference_players_by_puuid[puuid] = {
                            "puuid": puuid,
                            "gameName": team_player.get("gameName", ""),
                            "tagLine": team_player.get("tagLine", ""),
                        }

    items = sorted(
        ({"matchId": match_id, "gameStartTimeMillis": ts} for match_id, ts in match_times.items()),
        key=lambda row: row.get("gameStartTimeMillis", 0),
        reverse=True,
    )

    selected_series: list[tuple[str, str]] = []
    series_matches: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for item in items:
        match_id = item["matchId"]
        if match_id not in fetched_matches:
            fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
        match_obj = fetched_matches[match_id]
        context = detect_team_context(match_obj)
        if context is None:
            continue
        local_date = local_dt_from_ms(match_obj["matchInfo"]["gameStartMillis"]).strftime("%Y-%m-%d")
        series_key = (local_date, context["oppPrefix"])

        if series_key not in selected_series:
            if len(selected_series) >= SERIES_TO_FETCH:
                break
            selected_series.append(series_key)
        series_matches[series_key].append({"match": match_obj, "context": context})

    aggregate = {
        "series": [],
        "operatorRounds": 0,
        "operatorKillRounds": 0,
        "operatorKillRoundWins": 0,
        "positionCoverage": Counter(),
        "opUsageByPlayer": Counter(),
        "opKillRoundsByPlayer": Counter(),
        "opKillSamples": [],
    }

    for series_key in selected_series:
        entries = sorted(
            series_matches[series_key],
            key=lambda row: row["match"]["matchInfo"].get("gameStartMillis", 0),
        )
        series_summary = {
            "date": series_key[0],
            "opponent": series_key[1],
            "maps": [],
        }

        for entry in entries:
            match_obj = entry["match"]
            context = entry["context"]
            team_puuids = {p["puuid"] for p in context["teamPlayers"]}
            puuid_to_name = {p["puuid"]: p["gameName"] for p in context["teamPlayers"]}
            team_score, opp_score = match_score(match_obj, context["teamId"])
            map_name = match_obj["matchInfo"]["map"].split("/")[-1]

            series_summary["maps"].append(
                {
                    "matchId": match_obj["matchInfo"]["matchId"],
                    "map": map_name,
                    "score": f"{team_score}-{opp_score}",
                }
            )

            for rr in match_obj.get("roundResults", []):
                round_info = analyze_round(rr, context["teamId"], team_puuids, puuid_to_name)
                if not round_info["hasTeamOperator"]:
                    continue

                aggregate["operatorRounds"] += 1
                holders = round_info["holders"]
                for holder in holders:
                    aggregate["opUsageByPlayer"][puuid_to_name.get(holder, holder)] += 1

                    sources = round_info["opHolderPositionSources"].get(holder, set())
                    if sources:
                        aggregate["positionCoverage"]["with_any_snapshot"] += 1
                    else:
                        aggregate["positionCoverage"]["without_snapshot"] += 1

                    if "operator_kill" in sources:
                        aggregate["positionCoverage"]["with_operator_kill_location"] += 1
                    if "kill_snapshot" in sources or "victim_location" in sources:
                        aggregate["positionCoverage"]["with_kill_event_snapshot"] += 1
                    if "plant" in sources or "defuse" in sources:
                        aggregate["positionCoverage"]["with_plant_or_defuse_snapshot"] += 1

                if round_info["teamOperatorKill"]:
                    aggregate["operatorKillRounds"] += 1
                    if round_info["roundWon"]:
                        aggregate["operatorKillRoundWins"] += 1
                    seen_players = set()
                    for sample in round_info["opKillSamples"]:
                        name = sample["player"]
                        if name not in seen_players:
                            aggregate["opKillRoundsByPlayer"][name] += 1
                            seen_players.add(name)
                        if len(aggregate["opKillSamples"]) < 12:
                            aggregate["opKillSamples"].append(
                                {
                                    "date": series_key[0],
                                    "opponent": series_key[1],
                                    "map": map_name,
                                    "roundNum": sample["roundNum"],
                                    "player": sample["player"],
                                    "timeSinceRoundStartMillis": sample["timeSinceRoundStartMillis"],
                                    "location": sample["location"],
                                }
                            )

        aggregate["series"].append(series_summary)

    op_rounds = aggregate["operatorRounds"]
    op_kill_rounds = aggregate["operatorKillRounds"]
    win_pct = round((aggregate["operatorKillRoundWins"] / op_kill_rounds) * 100, 2) if op_kill_rounds else 0.0

    output = {
        "referencePlayers": list(reference_players_by_puuid.values()),
        "seriesAnalyzed": aggregate["series"],
        "operatorRounds": op_rounds,
        "operatorKillRounds": op_kill_rounds,
        "operatorKillRoundWins": aggregate["operatorKillRoundWins"],
        "operatorKillRoundWinPct": win_pct,
        "operatorUsageByPlayer": aggregate["opUsageByPlayer"].most_common(),
        "operatorKillRoundsByPlayer": aggregate["opKillRoundsByPlayer"].most_common(),
        "positionCoverage": dict(aggregate["positionCoverage"]),
        "sampleOperatorKillLocations": aggregate["opKillSamples"],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
