"""
Build map control + rotation pattern data for any team.

For each map/side:
  - Map control: player snapshots from kill events, bucketed by time window (0-10s, 10-20s, 20-30s)
  - Rotations: ordered position snapshots per player per round (movement trails)

Match selection: all post-April-1 matches for each map (no sample cap).

Usage:
    python scripts/build_map_control_bundle.py --team fks
    python scripts/build_map_control_bundle.py --team ep
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
APRIL_CUTOFF = "2026-04-01"

OPERATOR_UUID   = "A03B24D3-4319-996D-0F8C-94BBFBA1DFC7"
OUTLAW_UUID     = "5F0AAF7A-4289-3998-D5FF-EB9A5CF7EF5C"
OP_OUTLAW_UUIDS = {OPERATOR_UUID.upper(), OUTLAW_UUID.upper()}

MAP_TRANSFORMS = {
    "Ascent":   {"xMul": 7.0e-05,  "yMul": 7.0e-05,   "xAdd": 0.426758, "yAdd": 0.813895, "swap_xy": True},
    "Bind":     {"xMul": 5.9e-05,  "yMul": -5.9e-05,  "xAdd": 0.576941, "yAdd": 0.967566},
    "Breeze":   {"xMul": 7.0e-05,  "yMul": -7.0e-05,  "xAdd": 0.465123, "yAdd": 0.833078},
    "Fracture": {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.556952, "yAdd": 1.155886},
    "Haven":    {"xMul": 7.5e-05,  "yMul": -7.5e-05,  "xAdd": 1.09345,  "yAdd": 0.642728},
    "Lotus":    {"xMul": 7.2e-05,  "yMul": -7.2e-05,  "xAdd": 0.454789, "yAdd": 0.917752},
    "Pearl":    {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.480469, "yAdd": 0.916016},
    "Split":    {"xMul": 7.8e-05,  "yMul": -7.8e-05,  "xAdd": 0.842188, "yAdd": 0.697578},
}

WINDOWS = [
    {"key": "0_10",  "label": "0–10s",  "min_ms": 0,     "max_ms": 10000},
    {"key": "10_20", "label": "10–20s", "min_ms": 10000, "max_ms": 20000},
    {"key": "20_30", "label": "20–30s", "min_ms": 20000, "max_ms": 30000},
]

TEAM_CONFIG = {
    "sge": {
        "player_prefix": ("SGE ",),
        "jsonl":         ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "map-control-data.js",
        "js_var":        "mapControlData",
        "maps":          ["Bind", "Breeze", "Fracture", "Lotus", "Pearl", "Split"],
    },
    "fks": {
        "player_prefix": ("FKS ",),
        "jsonl":         ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "fks-map-control-data.js",
        "js_var":        "fksMapControlData",
        "maps":          ["Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "rzn": {
        "player_prefix": ("RZN ",),
        "jsonl":         ROOT / "data" / "raw" / "rzn_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "rzn-map-control-data.js",
        "js_var":        "rznMapControlData",
        "maps":          ["Bind", "Breeze", "Haven", "Lotus", "Split"],
    },
    "ep": {
        "player_prefix": ("EP ",),
        "jsonl":         ROOT / "data" / "raw" / "ep_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "ep-map-control-data.js",
        "js_var":        "epMapControlData",
        "maps":          ["Ascent", "Bind", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "jl": {
        "player_prefix": ("JL ",),
        "jsonl":         ROOT / "data" / "raw" / "jl_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "jl-map-control-data.js",
        "js_var":        "jlMapControlData",
        "min_date":      "2026-04-18",
        "maps":          ["Breeze", "Haven", "Lotus", "Pearl", "Split"],
    },
    "wip": {
        "player_prefix": ("WIP ",),
        "jsonl":         ROOT / "data" / "raw" / "wip_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "wip-map-control-data.js",
        "js_var":        "wipMapControlData",
        "maps":          ["Bind", "Breeze", "Fracture", "Lotus", "Pearl", "Split"],
    },
    "nvj": {
        "player_prefix": ("NVJ ",),
        "jsonl":         ROOT / "data" / "raw" / "nvj_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "nvj-map-control-data.js",
        "js_var":        "nvjMapControlData",
        "maps":          ["Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "tl": {
        "player_prefix": ("TL ",),
        "jsonl":         ROOT / "data" / "raw" / "tl_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "tl-map-control-data.js",
        "js_var":        "tlMapControlData",
        "maps":          ["Breeze", "Fracture", "Haven", "Lotus", "Split"],
    },
    "m1r": {
        "player_prefix": ("M1R ",),
        "jsonl":         ROOT / "data" / "raw" / "m1r_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "m1r-map-control-data.js",
        "js_var":        "m1rMapControlData",
        "maps":          ["Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "bar": {
        "player_prefix": ("BAR ",),
        "jsonl":         ROOT / "data" / "raw" / "bar_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "bar-map-control-data.js",
        "js_var":        "barMapControlData",
        "maps":          ["Ascent", "Bind", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "bjk": {
        "player_prefix": ("BJK ",),
        "jsonl":         ROOT / "data" / "raw" / "bjk_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "bjk-map-control-data.js",
        "js_var":        "bjkMapControlData",
        "maps":          ["Bind", "Breeze", "Fracture", "Lotus", "Pearl", "Split"],
    },
    "rb": {
        "player_prefix": ("RB ",),
        "jsonl":         ROOT / "data" / "raw" / "rb_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "rb-map-control-data.js",
        "js_var":        "rbMapControlData",
        "maps":          ["Bind", "Breeze", "Haven", "Lotus", "Split"],
    },
    "ucam": {
        "player_prefix": ("UCAM ",),
        "jsonl":         ROOT / "data" / "raw" / "ucam_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "ucam-map-control-data.js",
        "js_var":        "ucamMapControlData",
        "maps":          ["Bind", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "mdr": {
        "player_prefix": ("MDR ",),
        "jsonl":         ROOT / "data" / "raw" / "mdr_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "mdr-map-control-data.js",
        "js_var":        "mdrMapControlData",
        "maps":          ["Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "misa": {
        "player_prefix": ("MISA ",),
        "jsonl":         ROOT / "data" / "raw" / "misa_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "misa-map-control-data.js",
        "js_var":        "misaMapControlData",
        "maps":          ["Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split"],
    },
    "plm": {
        "player_prefix": ("PXL ",),
        "jsonl":         ROOT / "data" / "raw" / "plm_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "plm-map-control-data.js",
        "js_var":        "plmMapControlData",
        "maps":          ["Bind", "Haven", "Split"],
    },
    "aqd": {
        "player_prefix": ("QAD ",),
        "jsonl":         ROOT / "data" / "raw" / "aqd_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "aqd-map-control-data.js",
        "js_var":        "aqdMapControlData",
        "maps":          ["Breeze", "Haven", "Lotus", "Split"],
    },
    "gho": {
        "player_prefix": ("GHS ",),
        "jsonl":         ROOT / "data" / "raw" / "gho_2026_raw_responses.jsonl",
        "output_file":   ROOT / "veto-history-site-publish" / "gho-map-control-data.js",
        "js_var":        "ghoMapControlData",
        "maps":          ["Bind"],
    },
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        print(f"WARNING: JSONL not found at {path}")
        return rows
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
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE).strftime("%Y-%m-%d")


def detect_team_context(match_obj: dict, player_prefix: tuple[str, ...]) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(player_prefix):
            team_id = player.get("teamId")
            break
    if team_id is None:
        return None
    team_players = [p for p in match_obj.get("players", [])
                    if not p.get("isObserver") and p.get("teamId") == team_id]
    opp_players  = [p for p in match_obj.get("players", [])
                    if not p.get("isObserver") and p.get("teamId") != team_id]
    opp_prefix = Counter(
        p.get("gameName", "").split(" ")[0] for p in opp_players
    ).most_common(1)[0][0] if opp_players else ""
    return {"teamId": team_id, "teamPlayers": team_players, "oppPrefix": opp_prefix}


def clean_name(game_name: str, player_prefix: tuple[str, ...]) -> str:
    for pfx in player_prefix:
        if game_name.startswith(pfx):
            return game_name[len(pfx):]
    return game_name


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    if t.get("swap_xy"):
        x, y = y, x
    return (y * t["xMul"] + t["xAdd"]) * 100, (x * t["yMul"] + t["yAdd"]) * 100


def select_matches(all_matches: list[dict], map_name: str, player_prefix: tuple[str, ...], min_date: str = APRIL_CUTOFF) -> list[tuple[str, dict, dict]]:
    candidates = []
    for match_obj in all_matches:
        if match_obj.get("matchInfo", {}).get("map", "") != map_name:
            continue
        ctx = detect_team_context(match_obj, player_prefix)
        if ctx is None:
            continue
        ts_ms = match_obj.get("matchInfo", {}).get("gameStartMillis", 0)
        date = local_date_from_ms(ts_ms) if ts_ms else "1970-01-01"
        if date < min_date:
            continue
        candidates.append((date, match_obj, ctx))
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates


def process_map_side(
    selected: list[tuple[str, dict, dict]],
    map_name: str,
    side_key: str,
    player_prefix: tuple[str, ...],
) -> dict:
    map_ctrl: dict[str, list] = {w["key"]: [] for w in WINDOWS}
    rotation_rounds: list[list] = []
    selected_maps = []
    sniper_round_keys: list[str] = []

    for date, match_obj, ctx in selected:
        team_id = ctx["teamId"]
        team_puuids = {p["puuid"] for p in ctx["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_name(p.get("gameName", ""), player_prefix)
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

            if any(
                str(ps.get("economy", {}).get("weapon", "")).upper() in OP_OUTLAW_UUIDS
                for ps in rr.get("playerStats", [])
                if ps.get("puuid") in team_puuids
            ):
                sniper_round_keys.append(f"{match_id}|{round_num}")

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
                                "plantSite": rr.get("plantSite"),
                                "roundNum": round_num,
                                "matchId": match_id,
                                "date": date,
                                "opponent": opp,
                            })
                        break

            plant_t_ms = rr.get("plantRoundTime")
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
                if trail:
                    round_trails.append({
                        "player": puuid_to_name.get(puuid, puuid),
                        "snapshots": trail,
                        "plantTimeMs": plant_t_ms,
                        "plantSite": rr.get("plantSite"),
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
        "sniperRoundKeys": sniper_round_keys,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, choices=list(TEAM_CONFIG.keys()))
    args = parser.parse_args()

    cfg = TEAM_CONFIG[args.team]
    player_prefix = cfg["player_prefix"]

    print(f"Loading JSONL...")
    all_matches = load_jsonl(cfg["jsonl"])
    print(f"Loaded {len(all_matches)} records.")

    payload: dict[str, dict] = {}

    for map_name in cfg["maps"]:
        selected = select_matches(all_matches, map_name, player_prefix, min_date=cfg.get("min_date", APRIL_CUTOFF))
        if not selected:
            print(f"\n[{map_name}] No April+ matches found, skipping.")
            continue

        print(f"\n[{map_name}] {len(selected)} matches:")
        for date, _, ctx in selected:
            print(f"  {date} vs {ctx['oppPrefix']}")

        payload[map_name] = {}
        for side_code, side_key in [("ct", "def"), ("t", "atk")]:
            data = process_map_side(selected, map_name, side_key, player_prefix)
            payload[map_name][side_code] = data

            ctrl = data["mapControl"]
            rot  = data["rotations"]
            print(f"  {side_code.upper()}: 0-10s={len(ctrl['0_10'])} 10-20s={len(ctrl['10_20'])} 20-30s={len(ctrl['20_30'])} | rotations={len(rot)}")

    output_file = cfg["output_file"]
    js_var = cfg["js_var"]
    output_file.write_text(
        f"const {js_var} = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"\nWrote: {output_file}")


if __name__ == "__main__":
    main()
