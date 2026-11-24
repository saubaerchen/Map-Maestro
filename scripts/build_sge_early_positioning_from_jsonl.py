"""Build SGE early positioning JSONs from local JSONL, applying the correct scope rule.

Scope rule per map:
  1. Collect all matches from 2026-04-01 (Europe/Berlin) for that map.
  2. If fewer than 3 April matches exist, backfill with the most recent pre-April matches
     until reaching exactly 3 total (or all available if fewer than 3 exist in total).

Reads from: data/raw/sge_2026_raw_responses.jsonl
Writes to:  data/analysis/sge_{map}_{side}_early_team_positioning_last3.json
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
RAW_JSONL = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_NAME = "Eintracht Frankfurt"
TEAM_PREFIXES = ("SGE ",)
APRIL_CUTOFF = "2026-04-01"
MIN_MAP_COUNT = 3
THRESHOLDS_SEC = (10, 20, 30)
SIDES = (("ct", "def"), ("t", "atk"))
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
    "Abyss": {"xMultiplier": 8.8e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.497, "yScalarToAdd": 0.560},
    "Bind": {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Corrode": {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.526158, "yScalarToAdd": 0.5},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven": {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345, "yScalarToAdd": 0.642728},
    "Lotus": {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def local_date_from_ms(ts_ms: int) -> str:
    tz = TIMEZONE
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Team detection helpers (identical to existing script)
# ---------------------------------------------------------------------------

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
    norm_x = (y * transform["xMultiplier"] + transform["xScalarToAdd"]) * 100
    norm_y = (x * transform["yMultiplier"] + transform["yScalarToAdd"]) * 100
    return norm_x, norm_y


# ---------------------------------------------------------------------------
# Match selection with scope rule
# ---------------------------------------------------------------------------

def select_matches_for_map(all_matches: list[dict], map_name: str) -> list[tuple[str, dict, dict]]:
    """Return (date, match_obj, context) tuples for map_name, applying scope rule.

    Scope rule:
      1. All April 2026+ matches (date >= APRIL_CUTOFF), most recent first.
      2. Backfill with pre-April matches (most recent first) until MIN_MAP_COUNT reached.
    """
    candidates: list[tuple[str, dict, dict]] = []
    for match_obj in all_matches:
        match_map = match_obj.get("matchInfo", {}).get("map", "")
        if match_map != map_name:
            continue
        context = detect_team_context(match_obj)
        if context is None:
            continue
        ts_ms = match_obj.get("matchInfo", {}).get("gameStartMillis", 0)
        date_str = local_date_from_ms(ts_ms) if ts_ms else "1970-01-01"
        candidates.append((date_str, match_obj, context))

    # Sort by date descending (most recent first)
    candidates.sort(key=lambda t: t[0], reverse=True)

    april_matches = [c for c in candidates if c[0] >= APRIL_CUTOFF]
    pre_april = [c for c in candidates if c[0] < APRIL_CUTOFF]

    selected = list(april_matches)
    needed = MIN_MAP_COUNT - len(selected)
    if needed > 0:
        selected.extend(pre_april[:needed])

    return selected


# ---------------------------------------------------------------------------
# Dataset builder (same logic as existing, but with pre-selected matches)
# ---------------------------------------------------------------------------

def build_dataset_for_map_side(selected: list[tuple[str, dict, dict]], map_name: str, side_code: str, side_key: str) -> dict:
    points_by_threshold: dict[int, list[dict]] = {sec: [] for sec in THRESHOLDS_SEC}
    rounds_by_threshold: dict[int, set[str]] = {sec: set() for sec in THRESHOLDS_SEC}
    selected_maps = []

    for date_str, match_obj, context in selected:
        team_puuids = {p["puuid"] for p in context["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_player_name(p.get("gameName", "")) for p in context["teamPlayers"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)
        match_id = match_obj.get("matchInfo", {}).get("matchId", "")
        score = match_score(match_obj, context["teamId"])
        opponent = context["oppPrefix"]

        selected_maps.append({
            "date": date_str,
            "opponent": opponent,
            "matchId": match_id,
            "score": score,
        })

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
                round_points.append({
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
                })

            if not round_points:
                continue

            for sec in THRESHOLDS_SEC:
                if time_ms < sec * 1000:
                    rounds_by_threshold[sec].add(round_key)
                    points_by_threshold[sec].extend(round_points)

    player_counts = Counter(point["player"] for point in points_by_threshold[30])
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {name: DOT_COLORS[idx % len(DOT_COLORS)] for idx, name in enumerate(ordered_players)}

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Loading JSONL from {RAW_JSONL} ...")
    all_matches = load_jsonl(RAW_JSONL)
    print(f"Loaded {len(all_matches)} match records.")

    # Discover all maps present in the JSONL
    map_names: list[str] = []
    seen: set[str] = set()
    for match_obj in all_matches:
        m = match_obj.get("matchInfo", {}).get("map", "")
        if m and m not in seen:
            seen.add(m)
            map_names.append(m)
    print(f"Maps found in JSONL: {sorted(map_names)}")

    # Only process maps that have a known transform (i.e. we can normalise coordinates)
    processable = [m for m in map_names if m in MAP_TRANSFORMS]
    if len(processable) < len(map_names):
        skipped = sorted(set(map_names) - set(processable))
        print(f"Skipping maps with no transform: {skipped}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for map_name in sorted(processable):
        selected = select_matches_for_map(all_matches, map_name)
        if not selected:
            print(f"\n[{map_name}] No matches found — skipping.")
            continue

        april_count = sum(1 for d, _, _ in selected if d >= APRIL_CUTOFF)
        backfill_count = len(selected) - april_count
        print(f"\n[{map_name}] Using {len(selected)} matches "
              f"({april_count} from April+, {backfill_count} backfilled)")
        for date_str, match_obj, ctx in selected:
            match_id = match_obj.get("matchInfo", {}).get("matchId", "?")
            opp = ctx["oppPrefix"]
            marker = " [April+]" if date_str >= APRIL_CUTOFF else " [backfill]"
            print(f"  {date_str} vs {opp}  {match_id}{marker}")

        for side_code, side_key in SIDES:
            dataset = build_dataset_for_map_side(selected, map_name, side_code, side_key)
            json_name = f"sge_{map_name.lower()}_{side_code}_early_team_positioning_last3.json"
            output_json = OUTPUT_DIR / json_name
            output_json.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

            fk30 = dataset["thresholds"]["lt30s"]
            print(f"  [{side_code.upper()}] sampleSize={dataset['sampleSize']}  "
                  f"rounds={fk30['roundCount']}  points={fk30['pointCount']}  "
                  f"-> {json_name}")

    print("\nDone. All analysis JSONs written.")


if __name__ == "__main__":
    main()
