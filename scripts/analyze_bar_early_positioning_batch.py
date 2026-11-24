from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
OUTPUT_DIR = ROOT / "data" / "analysis"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_NAME = "Barcelona"
TEAM_PREFIXES = ("BAR ",)
LOCAL_SEED_FILES = (
    ROOT / "data" / "raw" / "bar_2026_raw_responses.jsonl",
)
TARGET_MAPS = ("Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split")
SIDES = (("ct", "def"), ("t", "atk"))
HISTORY_MATCH_LIMIT = 20
TARGET_MAP_COUNT = 3
MAP_DATE_CUTOFFS = {"Ascent": 1776038400000}
THRESHOLDS_SEC = (10, 20, 30)
DOT_COLORS = [
    "#e53935",
    "#f1d500",
    "#76d7ff",
    "#111111",
    "#1f4fd6",
    "#ff7f0e",
    "#2ca02c",
    "#9467bd",
]

MAP_TRANSFORMS = {
    "Ascent": {"xMultiplier": 7.0e-05, "yMultiplier": 7.0e-05, "xScalarToAdd": 0.426758, "yScalarToAdd": 0.813895, "swap_xy": True},
    "Breeze": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven": {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345, "yScalarToAdd": 0.642728},
    "Lotus": {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}


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
    found: list[dict] = []
    seen: set[str] = set()
    for path in LOCAL_SEED_FILES:
        for match in load_jsonl(path):
            for player in match.get("players", []):
                if player.get("isObserver"):
                    continue
                game_name = player.get("gameName", "")
                if not game_name.startswith(TEAM_PREFIXES):
                    continue
                puuid = player.get("puuid")
                if not puuid or puuid in seen:
                    continue
                seen.add(puuid)
                found.append(
                    {
                        "puuid": puuid,
                        "gameName": game_name,
                        "tagLine": player.get("tagLine", ""),
                    }
                )
    if not found:
        raise RuntimeError("Could not find Barcelona players in local seed files.")
    return found


def local_dt_from_ms(ts_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE)


def player_prefix(name: str) -> str:
    return name.split(" ")[0] if " " in name else name


def clean_player_name(game_name: str) -> str:
    for prefix in TEAM_PREFIXES:
        if game_name.startswith(prefix):
            return game_name[len(prefix):]
    return game_name


def detect_team_context(match_obj: dict) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(TEAM_PREFIXES):
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

    opp_prefix = Counter(player_prefix(p.get("gameName", "")) for p in opp_players).most_common(1)[0][0]
    return {
        "teamId": team_id,
        "teamPlayers": team_players,
        "oppPrefix": opp_prefix,
    }


def match_score(match_obj: dict, team_id: str) -> str:
    team_score = 0
    opp_score = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            team_score = team.get("roundsWon", 0)
        else:
            opp_score = team.get("roundsWon", 0)
    return f"{team_score}-{opp_score}"


def collect_first_kill(round_result: dict) -> dict | None:
    first = None
    for player_stats in round_result.get("playerStats", []):
        for kill in player_stats.get("kills", []):
            ts = kill.get("timeSinceRoundStartMillis")
            if ts is None:
                continue
            if first is None or ts < first.get("timeSinceRoundStartMillis", 10**9):
                first = kill
    return first


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    transform = MAP_TRANSFORMS.get(map_name)
    if not transform:
        raise RuntimeError(f"Missing transform for map {map_name}")
    if transform.get("swap_xy"):
        x, y = y, x
    norm_x = (y * transform["xMultiplier"] + transform["xScalarToAdd"]) * 100
    norm_y = (x * transform["yMultiplier"] + transform["yScalarToAdd"]) * 100
    return norm_x, norm_y


def fetch_bar_matches(api_key: str) -> tuple[dict[str, dict], dict[str, int]]:
    reference_players = discover_reference_players()
    players_by_puuid = {player["puuid"]: player for player in reference_players}
    processed: set[str] = set()
    fetched_matches: dict[str, dict] = {}
    match_times: dict[str, int] = {}

    while True:
        pending = [player for puuid, player in players_by_puuid.items() if puuid not in processed]
        if not pending:
            break
        for player in pending:
            processed.add(player["puuid"])
            try:
                history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{player['puuid']}", api_key)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
            for item in history.get("history", [])[:HISTORY_MATCH_LIMIT]:
                match_id = item["matchId"]
                ts = item.get("gameStartTimeMillis", 0)
                if ts > match_times.get(match_id, 0):
                    match_times[match_id] = ts
                if match_id not in fetched_matches:
                    try:
                        fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
                    except (urllib.error.HTTPError, urllib.error.URLError):
                        continue
            for teammate in history.get("teammates", []):
                puuid = teammate.get("puuid")
                if not puuid or puuid in players_by_puuid:
                    continue
                game_name = teammate.get("gameName", "")
                if not game_name.startswith(TEAM_PREFIXES):
                    continue
                players_by_puuid[puuid] = teammate

    # Backfill from local raw seed files so map coverage is not truncated by history paging.
    for seed_path in LOCAL_SEED_FILES:
        for match_obj in load_jsonl(seed_path):
            context = detect_team_context(match_obj)
            if context is None:
                continue
            match_id = match_obj.get("matchInfo", {}).get("matchId")
            if not match_id:
                continue
            ts = (
                match_obj.get("matchInfo", {}).get("gameStartMillis")
                or match_obj.get("matchInfo", {}).get("gameStartTimeMillis")
                or 0
            )
            if ts > match_times.get(match_id, 0):
                match_times[match_id] = ts
            if match_id not in fetched_matches:
                fetched_matches[match_id] = match_obj

    return fetched_matches, match_times


def build_dataset_for_map_side(fetched_matches: dict[str, dict], match_times: dict[str, int], map_name: str, side_code: str, side_key: str) -> dict:
    target_matches: list[tuple[int, dict, dict]] = []
    for match_id, ts in sorted(match_times.items(), key=lambda item: item[1], reverse=True):
        match_obj = fetched_matches.get(match_id)
        if not match_obj:
            continue
        context = detect_team_context(match_obj)
        if context is None:
            continue
        match_map = match_obj.get("matchInfo", {}).get("map", "").split("/")[-1]
        if match_map != map_name:
            continue
        target_matches.append((ts, match_obj, context))

    cutoff_ms = MAP_DATE_CUTOFFS.get(map_name)
    if cutoff_ms:
        target_matches = [(ts, mo, ctx) for ts, mo, ctx in target_matches if ts >= cutoff_ms]
    selected = target_matches[:TARGET_MAP_COUNT]
    if not selected:
        raise RuntimeError(f"No {map_name} maps found for {TEAM_NAME}.")

    points_by_threshold: dict[int, list[dict]] = {sec: [] for sec in THRESHOLDS_SEC}
    rounds_by_threshold: dict[int, set[str]] = {sec: set() for sec in THRESHOLDS_SEC}
    selected_maps = []

    for ts, match_obj, context in selected:
        team_puuids = {p["puuid"] for p in context["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_player_name(p.get("gameName", "")) for p in context["teamPlayers"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)
        date_str = local_dt_from_ms(ts).strftime("%Y-%m-%d")
        match_id = match_obj.get("matchInfo", {}).get("matchId", "")
        score = match_score(match_obj, context["teamId"])
        opponent = context["oppPrefix"]

        selected_maps.append(
            {
                "date": date_str,
                "opponent": opponent,
                "matchId": match_id,
                "score": score,
            }
        )

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            first_kill = collect_first_kill(rr)
            if not first_kill:
                continue
            time_ms = first_kill.get("timeSinceRoundStartMillis")
            if time_ms is None:
                continue
            if sides.get(round_num) != side_key:
                continue
            if time_ms >= THRESHOLDS_SEC[-1] * 1000:
                continue

            killer_puuid = first_kill.get("killer")
            killer_team_id = first_kill.get("killerTeamId")
            if killer_puuid:
                fk_owner = "team" if killer_puuid in team_puuids else "enemy"
            elif killer_team_id is not None:
                fk_owner = "team" if killer_team_id == context["teamId"] else "enemy"
            else:
                fk_owner = "unknown"

            snapshot = first_kill.get("playerLocations") or []
            if not snapshot:
                continue

            round_key = f"{match_id}|{round_num}"
            round_points = []
            for entry in snapshot:
                puuid = entry.get("puuid")
                if puuid not in team_puuids:
                    continue
                location = entry.get("location") or {}
                x = location.get("x")
                y = location.get("y")
                if x is None or y is None:
                    continue
                norm_x, norm_y = normalize_xy(map_name, x, y)
                round_points.append(
                    {
                        "player": puuid_to_name.get(puuid, puuid),
                        "puuid": puuid,
                        "x": x,
                        "y": y,
                        "normX": norm_x,
                        "normY": norm_y,
                        "roundNum": round_num,
                        "firstKillTimeMs": time_ms,
                        "date": date_str,
                        "opponent": opponent,
                        "matchId": match_id,
                        "score": score,
                        "fkOwner": fk_owner,
                        "plantSite": rr.get("plantSite"),
                    }
                )

            if not round_points:
                continue

            for sec in THRESHOLDS_SEC:
                if time_ms < sec * 1000:
                    rounds_by_threshold[sec].add(round_key)
                    points_by_threshold[sec].extend(round_points)

    player_counts = Counter(point["player"] for point in points_by_threshold[30])
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {}
    for idx, player_name in enumerate(ordered_players):
        color_by_player[player_name] = DOT_COLORS[idx % len(DOT_COLORS)]

    thresholds_payload = {}
    for sec in THRESHOLDS_SEC:
        thresholds_payload[f"lt{sec}s"] = {
            "roundCount": len(rounds_by_threshold[sec]),
            "pointCount": len(points_by_threshold[sec]),
            "points": points_by_threshold[sec],
        }

    return {
        "team": TEAM_NAME,
        "name": TEAM_NAME,
        "map": map_name,
        "side": side_code,
        "sampleSize": len(selected_maps),
        "selectedMaps": selected_maps,
        "thresholds": thresholds_payload,
        "legend": [{"player": player, "color": color_by_player[player]} for player in ordered_players],
    }



def main() -> None:
    api_key = load_api_key()
    fetched_matches, match_times = fetch_bar_matches(api_key)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    skipped = []

    for map_name in TARGET_MAPS:
        for side_code, side_key in SIDES:
            try:
                dataset = build_dataset_for_map_side(fetched_matches, match_times, map_name, side_code, side_key)
            except RuntimeError as exc:
                skipped.append({"map": map_name, "side": side_code.upper(), "reason": str(exc)})
                print(f"Skipped {map_name} {side_code.upper()}: {exc}")
                continue
            json_name = f"bar_{map_name.lower()}_{side_code}_early_team_positioning_last3.json"
            output_json = OUTPUT_DIR / json_name
            output_json.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

            fk30_points = dataset["thresholds"]["lt30s"]["points"]
            fk30_rounds = dataset["thresholds"]["lt30s"]["roundCount"]
            owner_counts = Counter(point.get("fkOwner", "unknown") for point in fk30_points)
            summaries.append(
                {
                    "map": map_name,
                    "side": side_code.upper(),
                    "sampleMaps": len(dataset.get("selectedMaps", [])),
                    "lt30Rounds": fk30_rounds,
                    "lt30Points": len(fk30_points),
                    "teamFKPoints": owner_counts.get("team", 0),
                    "enemyFKPoints": owner_counts.get("enemy", 0),
                    "json": str(output_json),
                }
            )

            print(f"Saved JSON: {output_json}")

    print("\nSummary:")
    print(json.dumps(summaries, indent=2))
    if skipped:
        print("\nSkipped:")
        print(json.dumps(skipped, indent=2))


if __name__ == "__main__":
    main()


