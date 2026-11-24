"""
Build CT-retake and T-postplant positioning data for Enterprise (EP) on all relevant maps.

CT retake: opponent planted spike → EP positions at plant time (retake scenario).
T post-plant: EP planted spike → EP positions at plant time (post-plant scenario).

Uses the same match selection as the early positioning analysis JSONs.

Outputs to veto-history-site-publish/data/:
  ep_bind_ct_retake_positions_last3.json
  ep_bind_t_postplant_positions_last3.json
  ep_fracture_ct_retake_positions_last3.json
  ep_fracture_t_postplant_positions_last3.json
  ep_haven_ct_retake_positions_last3.json
  ep_haven_t_postplant_positions_last3.json
  ep_lotus_ct_retake_positions_last3.json
  ep_lotus_t_postplant_positions_last3.json
  ep_pearl_ct_retake_positions_last3.json
  ep_pearl_t_postplant_positions_last3.json
  ep_split_ct_retake_positions_last3.json
  ep_split_t_postplant_positions_last3.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

ANALYSIS_DIR = ROOT / "data" / "analysis"
RAW_JSONL = ROOT / "data" / "raw" / "ep_2026_raw_responses.jsonl"
OUTPUT_DIR = ROOT / "veto-history-site-publish" / "data"
TEAM_PREFIXES = ("EP ",)

MAP_TRANSFORMS = {
    "Bind":     {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven":    {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":    {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl":    {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split":    {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}

MAP_SITES = {
    "Bind":     ["A", "B"],
    "Fracture": ["A", "B"],
    "Haven":    ["A", "B", "C"],
    "Lotus":    ["A", "B", "C"],
    "Pearl":    ["A", "B"],
    "Split":    ["A", "B"],
}

TARGETS = [
    ("Bind",     "ct"), ("Bind",     "t"),
    ("Fracture", "ct"), ("Fracture", "t"),
    ("Haven",    "ct"), ("Haven",    "t"),
    ("Lotus",    "ct"), ("Lotus",    "t"),
    ("Pearl",    "ct"), ("Pearl",    "t"),
    ("Split",    "ct"), ("Split",    "t"),
]


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
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


def clean_name(game_name: str) -> str:
    for pfx in TEAM_PREFIXES:
        if game_name.startswith(pfx):
            return game_name[len(pfx):]
    return game_name


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    return (y * t["xMultiplier"] + t["xScalarToAdd"]) * 100, (x * t["yMultiplier"] + t["yScalarToAdd"]) * 100


def build_dataset(map_name: str, side_code: str, matches_by_id: dict, selected_maps: list) -> dict:
    sites = MAP_SITES[map_name]
    points_by_site: dict[str, list] = {s: [] for s in sites}
    rounds_by_site: dict[str, set] = {s: set() for s in sites}

    for sample in selected_maps:
        match_id = sample.get("matchId")
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            print(f"  WARNING: match {match_id} not in JSONL — skipping")
            continue

        context = detect_team_context(match_obj)
        if not context:
            continue

        team_puuids = {p["puuid"] for p in context["teamPlayers"] if p.get("puuid")}
        puuid_to_name = {
            p["puuid"]: clean_name(p.get("gameName", ""))
            for p in context["teamPlayers"]
        }
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids
        )

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            round_side = sides.get(round_num)

            if side_code == "ct" and round_side != "def":
                continue
            if side_code == "t" and round_side != "atk":
                continue

            planter = rr.get("bombPlanter")
            if not planter:
                continue

            site = str(rr.get("plantSite") or "").upper()
            if site not in sites:
                continue

            ep_planted = planter in team_puuids
            if side_code == "ct" and ep_planted:
                continue
            if side_code == "t" and not ep_planted:
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
                x, y = location.get("x"), location.get("y")
                if x is None or y is None:
                    continue

                norm_x, norm_y = normalize_xy(map_name, x, y)
                points_by_site[site].append({
                    "site": site,
                    "player": puuid_to_name.get(puuid, puuid),
                    "normX": round(norm_x, 4),
                    "normY": round(norm_y, 4),
                    "roundNum": round_num,
                    "plantRoundTimeMs": rr.get("plantRoundTime"),
                    "date": sample.get("date"),
                    "opponent": sample.get("opponent"),
                    "matchId": match_id,
                    "score": sample.get("score"),
                })
                round_has_point = True

            if round_has_point:
                rounds_by_site[site].add(round_key)

    return {
        "map": map_name,
        "side": side_code,
        "selectedMaps": selected_maps,
        "sites": {
            site: {
                "roundCount": len(rounds_by_site[site]),
                "pointCount": len(points_by_site[site]),
                "points": points_by_site[site],
            }
            for site in sites
        },
    }


def main() -> None:
    print("Loading raw JSONL...")
    all_matches = load_jsonl(RAW_JSONL)
    matches_by_id = {
        m["matchInfo"]["matchId"]: m
        for m in all_matches
        if m.get("matchInfo", {}).get("matchId")
    }
    print(f"Loaded {len(matches_by_id)} raw matches.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for map_name, side_code in TARGETS:
        analysis_json = ANALYSIS_DIR / f"ep_{map_name.lower()}_ct_early_team_positioning_last3.json"
        if not analysis_json.exists():
            print(f"SKIP {map_name} {side_code.upper()}: missing {analysis_json.name}")
            continue

        analysis = json.loads(analysis_json.read_text(encoding="utf-8"))
        selected_maps = analysis.get("selectedMaps", [])
        if not selected_maps:
            print(f"SKIP {map_name} {side_code.upper()}: no selectedMaps in analysis JSON")
            continue

        print(f"[{map_name} {side_code.upper()}] {len(selected_maps)} matches:")
        for m in selected_maps:
            print(f"  {m['date']} vs {m['opponent']} ({m.get('score', '?')})")

        dataset = build_dataset(map_name, side_code, matches_by_id, selected_maps)

        if side_code == "ct":
            filename = f"ep_{map_name.lower()}_ct_retake_positions_last3.json"
        else:
            filename = f"ep_{map_name.lower()}_t_postplant_positions_last3.json"

        output_path = OUTPUT_DIR / filename
        output_path.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

        for site in MAP_SITES[map_name]:
            sd = dataset["sites"][site]
            print(f"  Site {site}: {sd['roundCount']}R / {sd['pointCount']}P")
        print(f"  -> {output_path.name}\n")


if __name__ == "__main__":
    main()
