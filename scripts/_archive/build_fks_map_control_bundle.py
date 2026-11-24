"""Build map control + rotation pattern data from FKS raw JSONL.

For each map/side:
  - Map control: ALL player snapshots from kill events, bucketed by time window
      window 1: 0–10s
      window 2: 10–20s
      window 3: 20–30s
  - Rotations: ordered position snapshots per player per round (connect with lines on frontend)

Uses the same match selection logic as build_sge_map_control_bundle.py.
Writes: veto-history-site-publish/fks-map-control-data.js
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

RAW_JSONL = ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl"
OUTPUT_FILE = ROOT / "veto-history-site-publish" / "fks-map-control-data.js"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_PREFIXES = ("FKS ",)
APRIL_CUTOFF = "2026-04-01"
MIN_MAP_COUNT = 3

MAP_TRANSFORMS = {
    "Bind":     {"xMul": 5.9e-05,  "yMul": -5.9e-05,  "xAdd": 0.576941, "yAdd": 0.967566},
    "Breeze":   {"xMul": 7.0e-05,  "yMul": -7.0e-05,  "xAdd": 0.465123, "yAdd": 0.833078},
    "Fracture": {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.556952, "yAdd": 1.155886},
    "Lotus":    {"xMul": 7.2e-05,  "yMul": -7.2e-05,  "xAdd": 0.454789, "yAdd": 0.917752},
    "Pearl":    {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.480469, "yAdd": 0.916016},
    "Split":    {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.842188, "yAdd": 0.697578},
}

WINDOWS = [
    {"key": "0_10",  "label": "0\u201310s",  "min_ms": 0,     "max_ms": 10000},
    {"key": "10_20", "label": "10\u201320s", "min_ms": 10000, "max_ms": 20000},
    {"key": "20_30", "label": "20\u201330s", "min_ms": 20000, "max_ms": 30000},
]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def local_date_from_ms(ts_ms: int) -> str:
    tz = TIMEZONE
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz).strftime("%Y-%m-%d")


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
    team_players = [p for p in match_obj.get("players", [])
                    if not p.get("isObserver") and p.get("teamId") == team_id]
    opp_players  = [p for p in match_obj.get("players", [])
                    if not p.get("isObserver") and p.get("teamId") != team_id]
    from collections import Counter
    opp_prefix = Counter(
        p.get("gameName", "").split(" ")[0] for p in opp_players
    ).most_common(1)[0][0] if opp_players else ""
    return {"teamId": team_id, "teamPlayers": team_players, "oppPrefix": opp_prefix}


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    return (y * t["xMul"] + t["xAdd"]) * 100, (x * t["yMul"] + t["yAdd"]) * 100


def clean_name(game_name: str) -> str:
    for pfx in TEAM_PREFIXES:
        if game_name.startswith(pfx):
            return game_name[len(pfx):]
    return game_name


def select_matches(all_matches: list[dict], map_name: str) -> list[tuple[str, dict, dict]]:
    candidates = []
    for match_obj in all_matches:
        if match_obj.get("matchInfo", {}).get("map", "") != map_name:
            continue
        ctx = detect_team_context(match_obj)
        if ctx is None:
            continue
        ts_ms = match_obj.get("matchInfo", {}).get("gameStartMillis", 0)
        date = local_date_from_ms(ts_ms) if ts_ms else "1970-01-01"
        candidates.append((date, match_obj, ctx))
    candidates.sort(key=lambda t: t[0], reverse=True)
    april = [c for c in candidates if c[0] >= APRIL_CUTOFF]
    pre   = [c for c in candidates if c[0] < APRIL_CUTOFF]
    selected = list(april)
    if len(selected) < MIN_MAP_COUNT:
        selected.extend(pre[:MIN_MAP_COUNT - len(selected)])
    return selected


def process_map_side(selected: list[tuple[str, dict, dict]], map_name: str, side_key: str) -> dict:
    map_ctrl: dict[str, list] = {w["key"]: [] for w in WINDOWS}
    rotation_rounds: list[list] = []
    selected_maps = []

    for date, match_obj, ctx in selected:
        team_id   = ctx["teamId"]
        team_puuids = {p["puuid"] for p in ctx["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_name(p.get("gameName", ""))
                         for p in ctx["teamPlayers"]}
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match_obj.get("roundResults", [])),
            team_puuids
        )
        match_id = match_obj.get("matchInfo", {}).get("matchId", "")
        opp = ctx["oppPrefix"]
        team_score = opp_score = 0
        for team in match_obj.get("teams", []):
            if team.get("teamId") == team_id:
                team_score = team.get("roundsWon", 0)
            else:
                opp_score = team.get("roundsWon", 0)
        score = f"{team_score}-{opp_score}"

        selected_maps.append({"date": date, "opponent": opp, "matchId": match_id, "score": score})

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            if sides.get(round_num) != side_key:
                continue

            kill_events: list[tuple[int, list]] = []
            for ps in rr.get("playerStats", []):
                for kill in ps.get("kills", []):
                    t_ms = kill.get("timeSinceRoundStartMillis")
                    locs = kill.get("playerLocations") or []
                    if t_ms is not None and locs:
                        kill_events.append((t_ms, locs))
            kill_events.sort(key=lambda e: e[0])

            if not kill_events:
                continue

            for t_ms, locs in kill_events:
                for w in WINDOWS:
                    if w["min_ms"] <= t_ms < w["max_ms"]:
                        for entry in locs:
                            puuid = entry.get("puuid")
                            if puuid not in team_puuids:
                                continue
                            loc = entry.get("location") or {}
                            x, y = loc.get("x"), loc.get("y")
                            if x is None or y is None:
                                continue
                            nx, ny = normalize_xy(map_name, x, y)
                            map_ctrl[w["key"]].append({
                                "player": puuid_to_name.get(puuid, puuid),
                                "normX": round(nx, 4),
                                "normY": round(ny, 4),
                                "timeMs": t_ms,
                                "roundNum": round_num,
                                "matchId": match_id,
                                "date": date,
                                "opponent": opp,
                            })
                        break

            plant_t_ms: int | None = rr.get("plantRoundTime")
            plant_locs = rr.get("plantPlayerLocations") or []

            all_events: list[tuple[int, list]] = list(kill_events)
            if plant_t_ms is not None and plant_locs:
                all_events.append((plant_t_ms, plant_locs))
            all_events.sort(key=lambda e: e[0])

            player_trail: dict[str, list] = defaultdict(list)
            seen: dict[str, set] = defaultdict(set)
            for t_ms, locs in all_events:
                for entry in locs:
                    puuid = entry.get("puuid")
                    if puuid not in team_puuids:
                        continue
                    if t_ms in seen[puuid]:
                        continue
                    seen[puuid].add(t_ms)
                    loc = entry.get("location") or {}
                    x, y = loc.get("x"), loc.get("y")
                    if x is None or y is None:
                        continue
                    nx, ny = normalize_xy(map_name, x, y)
                    player_trail[puuid].append({
                        "normX": round(nx, 4),
                        "normY": round(ny, 4),
                        "timeMs": t_ms,
                    })

            round_trails = []
            for puuid, trail in player_trail.items():
                if len(trail) >= 1:
                    round_trails.append({
                        "player": puuid_to_name.get(puuid, puuid),
                        "snapshots": trail,
                        "plantTimeMs": plant_t_ms,
                        "roundNum": round_num,
                        "matchId": match_id,
                        "date": date,
                        "opponent": opp,
                    })
            if round_trails:
                rotation_rounds.append(round_trails)

    return {
        "selectedMaps": selected_maps,
        "mapControl": map_ctrl,
        "rotations": rotation_rounds,
    }


def main() -> None:
    print(f"Loading JSONL from {RAW_JSONL} ...")
    all_matches = load_jsonl(RAW_JSONL)
    print(f"Loaded {len(all_matches)} records.")

    payload: dict[str, dict] = {}

    for map_name in MAP_TRANSFORMS:
        selected = select_matches(all_matches, map_name)
        if not selected:
            print(f"\n[{map_name}] No matches found — skipping")
            continue

        april_n = sum(1 for d, _, _ in selected if d >= APRIL_CUTOFF)
        print(f"\n[{map_name}] {len(selected)} matches ({april_n} April+, {len(selected)-april_n} backfill)")
        for d, _, ctx in selected:
            print(f"  {d} vs {ctx['oppPrefix']}")

        payload[map_name] = {}
        for side_code, side_key in [("ct", "def"), ("t", "atk")]:
            data = process_map_side(selected, map_name, side_key)
            payload[map_name][side_code] = data

            ctrl = data["mapControl"]
            rot  = data["rotations"]
            print(f"  {side_code.upper()}: map_ctrl points "
                  f"0-10s={len(ctrl['0_10'])} "
                  f"10-20s={len(ctrl['10_20'])} "
                  f"20-30s={len(ctrl['20_30'])} | "
                  f"rotation rounds={len(rot)}")

    OUTPUT_FILE.write_text(
        "const fksMapControlData = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"\nWrote: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
