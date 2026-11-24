"""
Generate early-positioning analysis JSONs for RZN.
Loads directly from the local JSONL (no API calls).
Uses hardcoded match IDs per map based on the agreed sample.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

OUTPUT_DIR = ROOT / "data" / "analysis"
RAW_JSONL = ROOT / "data" / "raw" / "rzn_2026_raw_responses.jsonl"
TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc

TEAM_NAME = "RIZON"
TEAM_PREFIXES = ("RZN ",)
SIDES = (("ct", "def"), ("t", "atk"))
THRESHOLDS_SEC = (10, 20, 30)

MAP_TRANSFORMS = {
    "Bind":   {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Haven":  {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":  {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Split":  {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}

# Newest-first per map; pre-April supplements at the end
MAP_MATCH_IDS: dict[str, list[str]] = {
    "Bind": [
        "6f46764b-09e1-404e-b195-398aae7ff291",  # 2026-04-18
        "6a31aae8-bf63-4e8f-ad67-761499578a66",  # 2026-04-11
        "f6c3a1e8-4268-4caf-8b26-463c1557640b",  # 2026-04-07
        "40a10cb2-2c5b-48ce-a3f0-9915cd8dda09",  # 2026-04-04
    ],
    "Breeze": [
        "50838009-f7bc-4124-943a-6e6d6fdada46",  # 2026-04-26
        "47bca094-569c-4fd0-b49f-49d1895202e4",  # 2026-03-09 (supplement)
        "1bad02fe-ec46-47d4-960d-a572c95df2f1",  # 2026-03-07 (supplement)
    ],
    "Haven": [
        "ba0cf320-229d-47a0-9029-49740aa21229",  # 2026-04-26
        "0a4eac40-0b98-4fda-a1ea-cf49d9522d13",  # 2026-04-25
        "66514075-1283-4122-85cb-4d3a7b6e2d8a",  # 2026-04-07
        "a8d5abe2-4ac1-48d1-a5c2-4de4517f94b7",  # 2026-04-04
    ],
    "Lotus": [
        "520d3d4c-0e03-4e1d-bd94-24b039b13179",  # 2026-04-25
        "7d332eca-1ea4-4bea-bb37-6df00a89ccaa",  # 2026-04-18
        "31bd242d-e54f-4f6f-a0db-df046cd33a60",  # 2026-04-14
        "ac2960a5-2503-4ca5-8973-b699a39ed09d",  # 2026-04-11
    ],
    "Split": [
        "3cc1127c-3135-4a5c-a503-f09d664c602d",  # 2026-04-14
        "56aec96e-d9c4-4e20-99b4-c64fd3cf8215",  # 2026-04-07
        "895733bb-a2ab-4a25-95e1-85d469a2e7a8",  # 2026-04-04
    ],
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        raise FileNotFoundError(f"JSONL not found: {path}")
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    norm_x = (y * t["xMultiplier"] + t["xScalarToAdd"]) * 100
    norm_y = (x * t["yMultiplier"] + t["yScalarToAdd"]) * 100
    return norm_x, norm_y


def local_dt_from_ms(ts_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE)


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
    team_players, opp_players = [], []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
        else:
            opp_players.append(player)
    opp_prefix = Counter(
        p.get("gameName", "").split(" ")[0] for p in opp_players
    ).most_common(1)[0][0] if opp_players else "OPP"
    return {"teamId": team_id, "teamPlayers": team_players, "oppPrefix": opp_prefix}


def clean_player_name(game_name: str) -> str:
    for prefix in TEAM_PREFIXES:
        if game_name.startswith(prefix):
            return game_name[len(prefix):]
    return game_name


def match_score(match_obj: dict, team_id: str) -> str:
    team_score, opp_score = 0, 0
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


def build_dataset(map_name: str, side_code: str, side_key: str, matches_by_id: dict) -> dict:
    match_ids = MAP_MATCH_IDS[map_name]
    points_by_threshold: dict[int, list[dict]] = {sec: [] for sec in THRESHOLDS_SEC}
    rounds_by_threshold: dict[int, set[str]] = {sec: set() for sec in THRESHOLDS_SEC}
    selected_maps = []

    for match_id in match_ids:
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            print(f"  WARNING: {match_id} not in JSONL")
            continue
        context = detect_team_context(match_obj)
        if context is None:
            print(f"  WARNING: RZN not found in {match_id}")
            continue

        ts = match_obj.get("matchInfo", {}).get("gameStartMillis", 0)
        date_str = local_dt_from_ms(ts).strftime("%Y-%m-%d")
        score = match_score(match_obj, context["teamId"])
        opponent = context["oppPrefix"]
        team_puuids = {p["puuid"] for p in context["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_player_name(p.get("gameName", "")) for p in context["teamPlayers"]}

        selected_maps.append({
            "date": date_str,
            "opponent": opponent,
            "matchId": match_id,
            "score": score,
        })

        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids
        )

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            if sides.get(round_num) != side_key:
                continue
            first_kill = collect_first_kill(rr)
            if not first_kill:
                continue
            time_ms = first_kill.get("timeSinceRoundStartMillis")
            if time_ms is None or time_ms >= THRESHOLDS_SEC[-1] * 1000:
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
                x, y = location.get("x"), location.get("y")
                if x is None or y is None:
                    continue
                norm_x, norm_y = normalize_xy(map_name, x, y)
                round_points.append({
                    "player": puuid_to_name.get(puuid, puuid),
                    "puuid": puuid,
                    "x": x, "y": y,
                    "normX": norm_x, "normY": norm_y,
                    "roundNum": round_num,
                    "firstKillTimeMs": time_ms,
                    "date": date_str,
                    "opponent": opponent,
                    "matchId": match_id,
                    "score": score,
                    "fkOwner": fk_owner,
                    "plantSite": rr.get("plantSite"),
                })

            if not round_points:
                continue
            for sec in THRESHOLDS_SEC:
                if time_ms < sec * 1000:
                    rounds_by_threshold[sec].add(round_key)
                    points_by_threshold[sec].extend(round_points)

    player_counts = Counter(p["player"] for p in points_by_threshold[30])
    ordered_players = [name for name, _ in player_counts.most_common()]
    dot_colors = ["#e53935", "#f1d500", "#76d7ff", "#111111", "#1f4fd6", "#ff7f0e", "#2ca02c", "#9467bd"]
    color_by_player = {name: dot_colors[i % len(dot_colors)] for i, name in enumerate(ordered_players)}

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
        "legend": [{"player": p, "color": color_by_player[p]} for p in ordered_players],
    }


def main() -> None:
    print("Loading RZN JSONL...")
    all_matches = load_jsonl(RAW_JSONL)
    matches_by_id = {
        m["matchInfo"]["matchId"]: m
        for m in all_matches
        if m.get("matchInfo", {}).get("matchId")
    }
    print(f"Loaded {len(matches_by_id)} matches.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for map_name in MAP_MATCH_IDS:
        for side_code, side_key in SIDES:
            print(f"[{map_name} {side_code.upper()}]")
            dataset = build_dataset(map_name, side_code, side_key, matches_by_id)
            out_path = OUTPUT_DIR / f"rzn_{map_name.lower()}_{side_code}_early_team_positioning_last3.json"
            out_path.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
            fk30 = dataset["thresholds"]["lt30s"]
            print(f"  Matches: {len(dataset['selectedMaps'])}  |  Rounds(30s): {fk30['roundCount']}  |  Points: {fk30['pointCount']}")
            print(f"  -> {out_path.name}")
        print()


if __name__ == "__main__":
    main()
