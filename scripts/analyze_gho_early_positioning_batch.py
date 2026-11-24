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
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
OUTPUT_DIR = ROOT / "data" / "analysis"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_NAME = "Ghools"
TEAM_PREFIXES = ("GHS ",)
LOCAL_SEED_FILES = (
    ROOT / "data" / "raw" / "gho_2026_raw_responses.jsonl",
)
TARGET_MAPS = ("Bind",)
SIDES = (("ct", "def"), ("t", "atk"))
HISTORY_MATCH_LIMIT = 20
TARGET_MAP_COUNT = 3
THRESHOLDS_SEC = (10, 20, 30)
DOT_COLORS = [
    "#e53935", "#f1d500", "#76d7ff", "#111111",
    "#1f4fd6", "#ff7f0e", "#2ca02c", "#9467bd",
]

MAP_TRANSFORMS = {
    "Bind": {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
}


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not m:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return m.group(1)

def api_get_json(path: str, api_key: str) -> dict:
    req = urllib.request.Request(API_BASE + path, headers={"x-api-key": api_key, "Accept": "application/json", "User-Agent": "curl/8.0.0"})
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
    found, seen = [], set()
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
                found.append({"puuid": puuid, "gameName": game_name, "tagLine": player.get("tagLine", "")})
    if not found:
        raise RuntimeError(f"Could not find {TEAM_NAME} players in local seed files.")
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
    team_players, opp_players = [], []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
        else:
            opp_players.append(player)
    opp_prefix = Counter(player_prefix(p.get("gameName", "")) for p in opp_players).most_common(1)[0][0]
    return {"teamId": team_id, "teamPlayers": team_players, "oppPrefix": opp_prefix}

def match_score(match_obj: dict, team_id: str) -> str:
    ts, os_ = 0, 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            ts = team.get("roundsWon", 0)
        else:
            os_ = team.get("roundsWon", 0)
    return f"{ts}-{os_}"

def collect_first_kill(round_result: dict) -> dict | None:
    first = None
    for ps in round_result.get("playerStats", []):
        for kill in ps.get("kills", []):
            t = kill.get("timeSinceRoundStartMillis")
            if t is None:
                continue
            if first is None or t < first.get("timeSinceRoundStartMillis", 10**9):
                first = kill
    return first

def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    tr = MAP_TRANSFORMS[map_name]
    return (y * tr["xMultiplier"] + tr["xScalarToAdd"]) * 100, (x * tr["yMultiplier"] + tr["yScalarToAdd"]) * 100

def fetch_team_matches(api_key: str) -> tuple[dict[str, dict], dict[str, int]]:
    reference_players = discover_reference_players()
    players_by_puuid = {p["puuid"]: p for p in reference_players}
    processed: set[str] = set()
    fetched_matches: dict[str, dict] = {}
    match_times: dict[str, int] = {}
    while True:
        pending = [p for puuid, p in players_by_puuid.items() if puuid not in processed]
        if not pending:
            break
        for player in pending:
            processed.add(player["puuid"])
            try:
                history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{player['puuid']}", api_key)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
            for item in history.get("history", [])[:HISTORY_MATCH_LIMIT]:
                mid = item["matchId"]
                ts = item.get("gameStartTimeMillis", 0)
                if ts > match_times.get(mid, 0):
                    match_times[mid] = ts
                if mid not in fetched_matches:
                    try:
                        fetched_matches[mid] = api_get_json(f"/api/matches/esports/{mid}", api_key)
                    except (urllib.error.HTTPError, urllib.error.URLError):
                        continue
            for teammate in history.get("teammates", []):
                puuid = teammate.get("puuid")
                if not puuid or puuid in players_by_puuid:
                    continue
                if teammate.get("gameName", "").startswith(TEAM_PREFIXES):
                    players_by_puuid[puuid] = teammate
    for seed_path in LOCAL_SEED_FILES:
        for match_obj in load_jsonl(seed_path):
            ctx = detect_team_context(match_obj)
            if ctx is None:
                continue
            mid = match_obj.get("matchInfo", {}).get("matchId")
            if not mid:
                continue
            ts = match_obj.get("matchInfo", {}).get("gameStartMillis") or match_obj.get("matchInfo", {}).get("gameStartTimeMillis") or 0
            if ts > match_times.get(mid, 0):
                match_times[mid] = ts
            if mid not in fetched_matches:
                fetched_matches[mid] = match_obj
    return fetched_matches, match_times

def build_dataset_for_map_side(fetched_matches, match_times, map_name, side_code, side_key):
    target_matches = []
    for mid, ts in sorted(match_times.items(), key=lambda x: x[1], reverse=True):
        match_obj = fetched_matches.get(mid)
        if not match_obj:
            continue
        ctx = detect_team_context(match_obj)
        if ctx is None:
            continue
        if match_obj.get("matchInfo", {}).get("map", "").split("/")[-1] != map_name:
            continue
        if len([p for p in match_obj.get("players", []) if not p.get("isObserver")]) < 10:
            continue
        target_matches.append((ts, match_obj, ctx))
    selected = target_matches[:TARGET_MAP_COUNT]
    if not selected:
        raise RuntimeError(f"No {map_name} maps found for {TEAM_NAME}.")
    points_by_threshold = {sec: [] for sec in THRESHOLDS_SEC}
    rounds_by_threshold = {sec: set() for sec in THRESHOLDS_SEC}
    selected_maps = []
    for ts, match_obj, ctx in selected:
        team_puuids = {p["puuid"] for p in ctx["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_player_name(p.get("gameName", "")) for p in ctx["teamPlayers"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)
        date_str = local_dt_from_ms(ts).strftime("%Y-%m-%d")
        mid = match_obj.get("matchInfo", {}).get("matchId", "")
        score = match_score(match_obj, ctx["teamId"])
        opponent = ctx["oppPrefix"]
        selected_maps.append({"date": date_str, "opponent": opponent, "matchId": mid, "score": score})
        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            fk = collect_first_kill(rr)
            if not fk:
                continue
            time_ms = fk.get("timeSinceRoundStartMillis")
            if time_ms is None or sides.get(round_num) != side_key or time_ms >= THRESHOLDS_SEC[-1] * 1000:
                continue
            killer_puuid = fk.get("killer")
            killer_team_id = fk.get("killerTeamId")
            if killer_puuid:
                fk_owner = "team" if killer_puuid in team_puuids else "enemy"
            elif killer_team_id is not None:
                fk_owner = "team" if killer_team_id == ctx["teamId"] else "enemy"
            else:
                fk_owner = "unknown"
            snapshot = fk.get("playerLocations") or []
            if not snapshot:
                continue
            round_key = f"{mid}|{round_num}"
            round_points = []
            for entry in snapshot:
                puuid = entry.get("puuid")
                if puuid not in team_puuids:
                    continue
                loc = entry.get("location") or {}
                x, y = loc.get("x"), loc.get("y")
                if x is None or y is None:
                    continue
                nx, ny = normalize_xy(map_name, x, y)
                round_points.append({
                    "player": puuid_to_name.get(puuid, puuid), "puuid": puuid,
                    "x": x, "y": y, "normX": nx, "normY": ny,
                    "roundNum": round_num, "firstKillTimeMs": time_ms,
                    "date": date_str, "opponent": opponent, "matchId": mid,
                    "score": score, "fkOwner": fk_owner, "plantSite": rr.get("plantSite"),
                })
            if not round_points:
                continue
            for sec in THRESHOLDS_SEC:
                if time_ms < sec * 1000:
                    rounds_by_threshold[sec].add(round_key)
                    points_by_threshold[sec].extend(round_points)
    player_counts = Counter(pt["player"] for pt in points_by_threshold[30])
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {name: DOT_COLORS[i % len(DOT_COLORS)] for i, name in enumerate(ordered_players)}
    thresholds_payload = {
        f"lt{sec}s": {"roundCount": len(rounds_by_threshold[sec]), "pointCount": len(points_by_threshold[sec]), "points": points_by_threshold[sec]}
        for sec in THRESHOLDS_SEC
    }
    return {
        "team": TEAM_NAME, "name": TEAM_NAME, "map": map_name, "side": side_code,
        "sampleSize": len(selected_maps), "selectedMaps": selected_maps,
        "thresholds": thresholds_payload,
        "legend": [{"player": p, "color": color_by_player[p]} for p in ordered_players],
    }

def main() -> None:
    api_key = load_api_key()
    fetched_matches, match_times = fetch_team_matches(api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries, skipped = [], []
    for map_name in TARGET_MAPS:
        for side_code, side_key in SIDES:
            try:
                dataset = build_dataset_for_map_side(fetched_matches, match_times, map_name, side_code, side_key)
            except RuntimeError as exc:
                skipped.append({"map": map_name, "side": side_code.upper(), "reason": str(exc)})
                print(f"Skipped {map_name} {side_code.upper()}: {exc}")
                continue
            json_name = f"gho_{map_name.lower()}_{side_code}_early_team_positioning_last3.json"
            out = OUTPUT_DIR / json_name
            out.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
            fk30 = dataset["thresholds"]["lt30s"]
            owner_counts = Counter(pt.get("fkOwner", "unknown") for pt in fk30["points"])
            summaries.append({"map": map_name, "side": side_code.upper(), "lt30Rounds": fk30["roundCount"], "teamFK": owner_counts.get("team", 0)})
            print(f"Saved: {out.name}")
    print(json.dumps(summaries, indent=2))
    if skipped:
        print("Skipped:", json.dumps(skipped, indent=2))

if __name__ == "__main__":
    main()
