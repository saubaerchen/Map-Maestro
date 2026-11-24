"""Build SGE CT retake position JSONs for all maps from local JSONL.

Scope rule per map (same as early positioning):
  1. All matches from 2026-04-01 (Europe/Berlin) for that map.
  2. If fewer than 3 April matches, backfill with the most recent pre-April matches
     until reaching exactly 3 total.

Reads from: data/raw/sge_2026_raw_responses.jsonl
Writes to:  data/analysis/sge_{map}_ct_retake_positions_last3.json
            veto-history-site-publish/data/sge_{map}_ct_retake_positions_last3.json
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

RAW_JSONL = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
ANALYSIS_DIR = ROOT / "data" / "analysis"
PUBLISH_DATA_DIR = ROOT / "veto-history-site-publish" / "data"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_NAME = "Eintracht Frankfurt"
TEAM_PREFIXES = ("SGE ",)
APRIL_CUTOFF = "2026-04-01"
MIN_MAP_COUNT = 3

MAP_SITES: dict[str, tuple[str, ...]] = {
    "Bind":   ("A", "B"),
    "Breeze": ("A", "B"),
    "Lotus":  ("A", "B", "C"),
    "Pearl":  ("A", "B"),
    "Split":  ("A", "B"),
}

MAP_TRANSFORMS = {
    "Abyss":   {"xMultiplier": 8.8e-05,  "yMultiplier": -7.2e-05,  "xScalarToAdd": 0.497,    "yScalarToAdd": 0.560},
    "Bind":    {"xMultiplier": 5.9e-05,  "yMultiplier": -5.9e-05,  "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze":  {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Corrode": {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.526158, "yScalarToAdd": 0.5},
    "Haven":   {"xMultiplier": 7.5e-05,  "yMultiplier": -7.5e-05,  "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":   {"xMultiplier": 7.2e-05,  "yMultiplier": -7.2e-05,  "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl":   {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split":   {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}

DOT_COLORS = [
    "#e53935", "#f1d500", "#76d7ff", "#111111",
    "#1f4fd6", "#ff7f0e", "#2ca02c", "#9467bd",
]


# ---------------------------------------------------------------------------
# Helpers
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
    team_players = [
        p for p in match_obj.get("players", [])
        if not p.get("isObserver") and p.get("teamId") == team_id
    ]
    return {"teamId": team_id, "teamPlayers": team_players}


def match_score(match_obj: dict, team_id: str) -> str:
    team_score = opp_score = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            team_score = team.get("roundsWon", 0)
        else:
            opp_score = team.get("roundsWon", 0)
    return f"{team_score}-{opp_score}"


def opponent_prefix(match_obj: dict, team_id: str) -> str:
    opp_names = [
        p.get("gameName", "")
        for p in match_obj.get("players", [])
        if not p.get("isObserver") and p.get("teamId") != team_id
    ]
    if not opp_names:
        return "?"
    return Counter(n.split(" ")[0] for n in opp_names if " " in n).most_common(1)[0][0]


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    norm_x = (y * t["xMultiplier"] + t["xScalarToAdd"]) * 100
    norm_y = (x * t["yMultiplier"] + t["yScalarToAdd"]) * 100
    return norm_x, norm_y


# ---------------------------------------------------------------------------
# Match selection (same rule as early positioning)
# ---------------------------------------------------------------------------

def select_matches(all_matches: list[dict], map_name: str) -> list[tuple[str, dict, dict]]:
    candidates: list[tuple[str, dict, dict]] = []
    for match_obj in all_matches:
        if match_obj.get("matchInfo", {}).get("map", "") != map_name:
            continue
        ctx = detect_team_context(match_obj)
        if ctx is None:
            continue
        ts_ms = match_obj.get("matchInfo", {}).get("gameStartMillis", 0)
        date_str = local_date_from_ms(ts_ms) if ts_ms else "1970-01-01"
        candidates.append((date_str, match_obj, ctx))

    candidates.sort(key=lambda t: t[0], reverse=True)
    april = [c for c in candidates if c[0] >= APRIL_CUTOFF]
    pre = [c for c in candidates if c[0] < APRIL_CUTOFF]
    selected = list(april)
    needed = MIN_MAP_COUNT - len(selected)
    if needed > 0:
        selected.extend(pre[:needed])
    return selected


# ---------------------------------------------------------------------------
# Retake dataset builder
# ---------------------------------------------------------------------------

def build_retake_dataset(selected: list[tuple[str, dict, dict]], map_name: str) -> dict:
    site_order = MAP_SITES[map_name]
    points_by_site: dict[str, list[dict]] = {s: [] for s in site_order}
    rounds_by_site: dict[str, set[str]] = {s: set() for s in site_order}
    selected_maps: list[dict] = []

    for date_str, match_obj, ctx in selected:
        match_id = match_obj.get("matchInfo", {}).get("matchId", "")
        team_id = ctx["teamId"]
        team_puuids = {p.get("puuid") for p in ctx["teamPlayers"] if p.get("puuid")}
        puuid_to_name = {p.get("puuid"): clean_player_name(p.get("gameName", "")) for p in ctx["teamPlayers"]}
        opp = opponent_prefix(match_obj, team_id)
        score = match_score(match_obj, team_id)
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids
        )

        selected_maps.append({"date": date_str, "opponent": opp, "matchId": match_id, "score": score})

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            if sides.get(round_num) != "def":
                continue

            planter = rr.get("bombPlanter")
            if not planter or planter in team_puuids:
                continue

            site = str(rr.get("plantSite") or "").upper()
            if site not in site_order:
                continue

            plant_snapshot = rr.get("plantPlayerLocations") or []
            if not plant_snapshot:
                continue

            round_key = f"{match_id}|{round_num}"
            round_has_point = False
            for entry in plant_snapshot:
                puuid = entry.get("puuid")
                if puuid not in team_puuids:
                    continue
                location = entry.get("location") or {}
                x = location.get("x")
                y = location.get("y")
                if x is None or y is None:
                    continue
                norm_x, norm_y = normalize_xy(map_name, x, y)
                points_by_site[site].append({
                    "site": site,
                    "player": puuid_to_name.get(puuid, puuid),
                    "puuid": puuid,
                    "x": x, "y": y,
                    "normX": norm_x, "normY": norm_y,
                    "roundNum": round_num,
                    "plantRoundTimeMs": rr.get("plantRoundTime"),
                    "date": date_str,
                    "opponent": opp,
                    "matchId": match_id,
                    "score": score,
                })
                round_has_point = True

            if round_has_point:
                rounds_by_site[site].add(round_key)

    all_points = [pt for s in site_order for pt in points_by_site[s]]
    player_counts = Counter(pt["player"] for pt in all_points)
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {p: DOT_COLORS[i % len(DOT_COLORS)] for i, p in enumerate(ordered_players)}

    sites_payload = {
        s: {
            "roundCount": len(rounds_by_site[s]),
            "pointCount": len(points_by_site[s]),
            "points": points_by_site[s],
        }
        for s in site_order
    }

    return {
        "team": TEAM_NAME,
        "name": TEAM_NAME,
        "map": map_name,
        "side": "ct",
        "sampleSize": len(selected_maps),
        "selectedMaps": selected_maps,
        "sites": sites_payload,
        "legend": [{"player": p, "color": color_by_player[p]} for p in ordered_players],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Loading JSONL from {RAW_JSONL} ...")
    all_matches = load_jsonl(RAW_JSONL)
    print(f"Loaded {len(all_matches)} match records.")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISH_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for map_name in sorted(MAP_SITES):
        selected = select_matches(all_matches, map_name)
        if not selected:
            print(f"\n[{map_name}] No matches — skipping.")
            continue

        april_count = sum(1 for d, _, _ in selected if d >= APRIL_CUTOFF)
        back_count = len(selected) - april_count
        print(f"\n[{map_name}] {len(selected)} matches ({april_count} April+, {back_count} backfill)")
        for date_str, mo, ctx in selected:
            marker = "[April+]" if date_str >= APRIL_CUTOFF else "[backfill]"
            opp = opponent_prefix(mo, ctx["teamId"])
            print(f"  {date_str} vs {opp}  {marker}")

        dataset = build_retake_dataset(selected, map_name)
        fname = f"sge_{map_name.lower()}_ct_retake_positions_last3.json"
        content = json.dumps(dataset, indent=2)

        analysis_path = ANALYSIS_DIR / fname
        publish_path = PUBLISH_DATA_DIR / fname
        analysis_path.write_text(content, encoding="utf-8")
        publish_path.write_text(content, encoding="utf-8")

        sites_summary = {
            s: f"{dataset['sites'][s]['roundCount']}R/{dataset['sites'][s]['pointCount']}P"
            for s in MAP_SITES[map_name]
        }
        print(f"  Wrote {fname}  |  sites: {sites_summary}")

    print("\nDone.")


if __name__ == "__main__":
    main()
