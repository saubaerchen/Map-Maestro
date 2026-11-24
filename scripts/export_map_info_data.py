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

from lib.constants import OPERATOR_UUID
from lib.stats_engine import get_team_side_per_round


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
OUTPUT = ROOT / "veto-history-site" / "map-info-data.js"
TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
CURRENT_MAP_POOL = ["Bind", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"]
KNOWN_MAPS = set(CURRENT_MAP_POOL + ["Abyss", "Corrode", "Sunset", "Icebox"])
HISTORY_MATCH_LIMIT = 14
LAST_MAP_COUNT = 10
TEAM_CONFIGS = {
    "dortmund": {
        "name": "Dortmund eSports",
        "prefixes": ("DXG ", "DoeS "),
    },
    "eintracht": {
        "name": "Eintracht Frankfurt",
        "prefixes": ("SGE ",),
    },
    "eco": {
        "name": "eSports Cologne",
        "prefixes": ("ECO ",),
    },
}
MAP_TRANSFORMS = {
    "Bind": {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Corrode": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.526158, "yScalarToAdd": 0.5},
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


def discover_reference_players(prefixes: tuple[str, ...]) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for path in (ROOT / "data" / "raw").glob("*raw_responses.jsonl"):
        for match in load_jsonl(path):
            for player in match.get("players", []):
                if player.get("isObserver"):
                    continue
                game_name = player.get("gameName", "")
                if not game_name.startswith(prefixes):
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
        raise RuntimeError(f"Could not find seed players for prefixes: {prefixes}")
    return found


def local_dt_from_ms(ts_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE)


def player_prefix(name: str) -> str:
    return name.split(" ")[0] if " " in name else name


def detect_team_context(match_obj: dict, prefixes: tuple[str, ...]) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(prefixes):
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


def location_for_puuid(entries: list[dict] | None, puuid: str) -> dict | None:
    if not entries:
        return None
    for entry in entries:
        if entry.get("puuid") == puuid:
            return entry.get("location")
    return None


def add_location(bounds: dict[str, list[int]], map_name: str, loc: dict | None) -> None:
    if not loc:
        return
    x = loc.get("x")
    y = loc.get("y")
    if x is None or y is None:
        return
    bounds.setdefault(map_name, []).append((x, y))


def collect_first_kill(rr: dict) -> dict | None:
    first = None
    for ps in rr.get("playerStats", []):
        for kill in ps.get("kills", []):
            ts = kill.get("timeSinceRoundStartMillis")
            if ts is None:
                continue
            if first is None or ts < first.get("timeSinceRoundStartMillis", 10**9):
                first = kill
    return first


def normalize_xy(map_name: str, x: float, y: float, extent: dict[str, float]) -> tuple[float, float]:
    transform = MAP_TRANSFORMS.get(map_name)
    if transform:
        norm_x = (y * transform["xMultiplier"] + transform["xScalarToAdd"]) * 100
        norm_y = (x * transform["yMultiplier"] + transform["yScalarToAdd"]) * 100
    else:
        width = max(extent["maxX"] - extent["minX"], 1)
        height = max(extent["maxY"] - extent["minY"], 1)
        norm_x = ((x - extent["minX"]) / width) * 100
        norm_y = ((y - extent["minY"]) / height) * 100
    return norm_x, norm_y


def normalize_points(points: list[dict], map_name: str, extent: dict[str, float]) -> list[dict]:
    normalized = []
    for point in points:
        norm_x, norm_y = normalize_xy(map_name, point["x"], point["y"], extent)
        payload = {**point, "normX": norm_x, "normY": norm_y}
        victim_x = point.get("victimX")
        victim_y = point.get("victimY")
        if victim_x is not None and victim_y is not None:
            victim_norm_x, victim_norm_y = normalize_xy(map_name, victim_x, victim_y, extent)
            payload["victimNormX"] = victim_norm_x
            payload["victimNormY"] = victim_norm_y
        normalized.append(payload)
    return normalized


def build_team_payload(team_key: str, team_name: str, prefixes: tuple[str, ...], api_key: str) -> dict:
    reference_players = discover_reference_players(prefixes)
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
            history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{player['puuid']}", api_key)
            for item in history.get("history", [])[:HISTORY_MATCH_LIMIT]:
                match_id = item["matchId"]
                ts = item.get("gameStartTimeMillis", 0)
                if ts > match_times.get(match_id, 0):
                    match_times[match_id] = ts
                if match_id not in fetched_matches:
                    try:
                        fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
                    except urllib.error.HTTPError as exc:
                        if exc.code == 404:
                            continue
                        raise
                context = detect_team_context(fetched_matches[match_id], prefixes)
                if context is None:
                    continue
                for team_player in context["teamPlayers"]:
                    puuid = team_player.get("puuid")
                    if puuid and puuid not in players_by_puuid:
                        players_by_puuid[puuid] = {
                            "puuid": puuid,
                            "gameName": team_player.get("gameName", ""),
                            "tagLine": team_player.get("tagLine", ""),
                        }

    ordered_matches = []
    for match_id, ts in sorted(match_times.items(), key=lambda item: item[1], reverse=True):
        match_obj = fetched_matches[match_id]
        context = detect_team_context(match_obj, prefixes)
        if context is None:
            continue
        map_name = match_obj["matchInfo"]["map"].split("/")[-1]
        if map_name not in KNOWN_MAPS:
            continue
        ordered_matches.append((ts, match_obj, context))

    last_maps = ordered_matches[:LAST_MAP_COUNT]
    point_buckets: dict[str, dict[str, list[dict]]] = {}
    bounds_source: dict[str, list[tuple[int, int]]] = {}
    sample_maps: list[dict] = []

    for ts, match_obj, context in last_maps:
        map_name = match_obj["matchInfo"]["map"].split("/")[-1]
        local_date = local_dt_from_ms(ts).strftime("%Y-%m-%d")
        team_puuids = {p["puuid"] for p in context["teamPlayers"]}
        puuid_to_name = {p["puuid"]: p["gameName"] for p in context["teamPlayers"]}
        all_puuid_to_name = {p.get("puuid"): p.get("gameName", "") for p in match_obj.get("players", []) if p.get("puuid")}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj["roundResults"]), team_puuids)
        score = match_score(match_obj, context["teamId"])

        sample_maps.append(
            {
                "date": local_date,
                "map": map_name,
                "opponent": context["oppPrefix"],
                "score": score,
            }
        )

        point_buckets.setdefault(
            map_name,
            {"OP_CT": [], "OP_T": [], "ALL_CT": [], "ALL_T": []},
        )

        for rr in match_obj.get("roundResults", []):
            add_location(bounds_source, map_name, rr.get("plantLocation"))
            add_location(bounds_source, map_name, rr.get("defuseLocation"))
            for loc_entry in rr.get("plantPlayerLocations") or []:
                add_location(bounds_source, map_name, loc_entry.get("location"))
            for loc_entry in rr.get("defusePlayerLocations") or []:
                add_location(bounds_source, map_name, loc_entry.get("location"))

            first_kill = collect_first_kill(rr)
            if not first_kill:
                continue

            killer_puuid = first_kill.get("killer")
            if killer_puuid in team_puuids:
                side_key = "T" if sides.get(rr.get("roundNum")) == "atk" else "CT"
                killer_loc = location_for_puuid(first_kill.get("playerLocations"), killer_puuid)
                victim_loc = first_kill.get("victimLocation")
                add_location(bounds_source, map_name, killer_loc)
                add_location(bounds_source, map_name, victim_loc)
                if killer_loc:
                    payload = {
                        "x": killer_loc["x"],
                        "y": killer_loc["y"],
                        "roundNum": rr.get("roundNum"),
                        "date": local_date,
                        "opponent": context["oppPrefix"],
                        "player": puuid_to_name.get(killer_puuid, killer_puuid),
                        "score": score,
                        "victim": all_puuid_to_name.get(first_kill.get("victim"), first_kill.get("victim")),
                    }
                    if victim_loc:
                        payload["victimX"] = victim_loc.get("x")
                        payload["victimY"] = victim_loc.get("y")
                    point_buckets[map_name][f"ALL_{side_key}"].append(payload)

                    killer_ps = next((ps for ps in rr.get("playerStats", []) if ps.get("puuid") == killer_puuid), None)
                    if (
                        killer_ps
                        and str(killer_ps.get("economy", {}).get("weapon", "")).upper() == OPERATOR_UUID
                        and str(first_kill.get("finishingDamage", {}).get("damageItem", "")).upper() == OPERATOR_UUID
                    ):
                        point_buckets[map_name][f"OP_{side_key}"].append(payload)

            for ps in rr.get("playerStats", []):
                for kill in ps.get("kills", []):
                    add_location(bounds_source, map_name, kill.get("victimLocation"))
                    for loc_entry in kill.get("playerLocations") or []:
                        add_location(bounds_source, map_name, loc_entry.get("location"))

    extent_by_map = {}
    for map_name, coords in bounds_source.items():
        if not coords:
            extent_by_map[map_name] = {"minX": 0, "maxX": 100, "minY": 0, "maxY": 100}
            continue
        xs = [coord[0] for coord in coords]
        ys = [coord[1] for coord in coords]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        pad_x = max((max_x - min_x) * 0.08, 500)
        pad_y = max((max_y - min_y) * 0.08, 500)
        extent_by_map[map_name] = {
            "minX": round(min_x - pad_x, 2),
            "maxX": round(max_x + pad_x, 2),
            "minY": round(min_y - pad_y, 2),
            "maxY": round(max_y + pad_y, 2),
        }

    maps_output = {}
    for map_name in CURRENT_MAP_POOL:
        extent = extent_by_map.get(map_name, {"minX": 0, "maxX": 100, "minY": 0, "maxY": 100})
        ct_points = normalize_points(point_buckets.get(map_name, {}).get("OP_CT", []), map_name, extent)
        t_points = normalize_points(point_buckets.get(map_name, {}).get("OP_T", []), map_name, extent)
        all_ct_points = normalize_points(point_buckets.get(map_name, {}).get("ALL_CT", []), map_name, extent)
        all_t_points = normalize_points(point_buckets.get(map_name, {}).get("ALL_T", []), map_name, extent)
        maps_output[map_name] = {
            "extent": extent,
            "ct": {"count": len(ct_points), "points": ct_points},
            "t": {"count": len(t_points), "points": t_points},
            "all_ct": {"count": len(all_ct_points), "points": all_ct_points},
            "all_t": {"count": len(all_t_points), "points": all_t_points},
        }

    sample_map_names = [row["map"] for row in sample_maps]
    sample_map_set = {name for name in sample_map_names if name in CURRENT_MAP_POOL}
    missing_pool_maps = [name for name in CURRENT_MAP_POOL if name not in sample_map_set]

    return {
        "name": team_name,
        "sampleSize": LAST_MAP_COUNT,
        "currentMapPool": CURRENT_MAP_POOL,
        "sampleMaps": sample_maps,
        "sampleMapNames": sample_map_names,
        "missingCurrentPoolMaps": missing_pool_maps,
        "maps": maps_output,
    }


def main() -> None:
    api_key = load_api_key()
    payload = {
        team_key: build_team_payload(team_key, team_cfg["name"], team_cfg["prefixes"], api_key)
        for team_key, team_cfg in TEAM_CONFIGS.items()
    }
    OUTPUT.write_text("const mapInfoData = " + json.dumps(payload, indent=2) + ";\n", encoding="utf-8")
    print(json.dumps({key: payload[key]["sampleMaps"] for key in payload}, indent=2))


if __name__ == "__main__":
    main()
