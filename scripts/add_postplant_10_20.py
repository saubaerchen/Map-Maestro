"""Patch all CT retake position JSONs with postPlant10_20 snapshot data.

For every existing *_ct_retake_positions_last3.json in the publish data dir,
reads kill events from the raw JSONL that fall 10-20s after the spike plant
and embeds them as 'postPlant10_20' in the JSON.

Run: python scripts/add_postplant_10_20.py
Re-run freely — it overwrites whatever postPlant10_20 was there before.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "veto-history-site-publish" / "data"
RAW_DIR = ROOT / "data" / "raw"

TEAM_CONFIG = {
    "sge":  ("SGE ",),
    "fks":  ("FKS ",),
    "rzn":  ("RZN ",),
    "ep":   ("EP ",),
    "jl":   ("JL ",),
    "wip":  ("WIP ",),
    "nvj":  ("NVJ ",),
    "tl":   ("TL ",),
    "m1r":  ("M1R ",),
    "bar":  ("BAR ",),
    "bjk":  ("BJK ",),
    "rb":   ("RB ",),
    "ucam": ("UCAM ",),
}

MAP_TRANSFORMS = {
    "Ascent":   {"xMultiplier": 7.0e-05,  "yMultiplier": 7.0e-05,   "xScalarToAdd": 0.426758,  "yScalarToAdd": 0.813895, "swap_xy": True},
    "Bind":     {"xMultiplier": 5.9e-05,  "yMultiplier": -5.9e-05,  "xScalarToAdd": 0.576941,  "yScalarToAdd": 0.967566},
    "Breeze":   {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.465123,  "yScalarToAdd": 0.833078},
    "Corrode":  {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.526158,  "yScalarToAdd": 0.5},
    "Fracture": {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.556952,  "yScalarToAdd": 1.155886},
    "Haven":    {"xMultiplier": 7.5e-05,  "yMultiplier": -7.5e-05,  "xScalarToAdd": 1.09345,   "yScalarToAdd": 0.642728},
    "Lotus":    {"xMultiplier": 7.2e-05,  "yMultiplier": -7.2e-05,  "xScalarToAdd": 0.454789,  "yScalarToAdd": 0.917752},
    "Pearl":    {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.480469,  "yScalarToAdd": 0.916016},
    "Split":    {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.842188,  "yScalarToAdd": 0.697578},
}

POST_PLANT_MIN_MS = 10_000
POST_PLANT_MAX_MS = 20_000


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    t = MAP_TRANSFORMS[map_name]
    if t.get("swap_xy"):
        x, y = y, x
    return (y * t["xMultiplier"] + t["xScalarToAdd"]) * 100, (x * t["yMultiplier"] + t["yScalarToAdd"]) * 100


def load_jsonl(path: Path) -> dict[str, dict]:
    matches: dict[str, dict] = {}
    if not path.exists():
        return matches
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
                mid = m.get("matchInfo", {}).get("matchId")
                if mid:
                    matches[mid] = m
            except json.JSONDecodeError:
                pass
    return matches


def clean_name(game_name: str, prefixes: tuple[str, ...]) -> str:
    for pfx in prefixes:
        if game_name.startswith(pfx):
            return game_name[len(pfx):]
    return game_name


def extract_postplant_snapshots(
    match_obj: dict,
    map_name: str,
    team_puuids: set[str],
    puuid_to_name: dict[str, str],
    selected_match_ids: set[str],
) -> dict[str, list[dict]]:
    """Return per-site round data with 10-20s post-plant snapshots for this match."""
    rounds_by_site: dict[str, dict[int, dict]] = defaultdict(dict)

    for rr in match_obj.get("roundResults", []):
        plant_time = rr.get("plantRoundTime")
        if not plant_time:
            continue
        planter = rr.get("bombPlanter")
        if not planter or planter in team_puuids:
            continue

        site = str(rr.get("plantSite") or "").upper()
        if site not in ("A", "B", "C"):
            continue

        round_num = rr.get("roundNum")
        snapshots: list[dict] = []

        for stat in rr.get("playerStats", []):
            for kill in stat.get("kills", []):
                tr = kill.get("timeSinceRoundStartMillis")
                if tr is None:
                    continue
                since_plant = tr - plant_time
                if not (POST_PLANT_MIN_MS <= since_plant <= POST_PLANT_MAX_MS):
                    continue
                locs = kill.get("playerLocations") or []
                players_at_snap = []
                for entry in locs:
                    puuid = entry.get("puuid")
                    if puuid not in team_puuids:
                        continue
                    loc = entry.get("location") or {}
                    x, y = loc.get("x"), loc.get("y")
                    if x is None or y is None:
                        continue
                    nx, ny = normalize_xy(map_name, x, y)
                    players_at_snap.append({
                        "player": puuid_to_name.get(puuid, puuid),
                        "normX": round(nx, 4),
                        "normY": round(ny, 4),
                    })
                if players_at_snap:
                    snapshots.append({
                        "timeSincePlantMs": since_plant,
                        "players": players_at_snap,
                    })

        if not snapshots:
            continue

        snapshots.sort(key=lambda s: s["timeSincePlantMs"])

        if round_num not in rounds_by_site[site]:
            rounds_by_site[site][round_num] = {
                "roundNum": round_num,
                "snapshots": snapshots,
            }
        else:
            rounds_by_site[site][round_num]["snapshots"].extend(snapshots)
            rounds_by_site[site][round_num]["snapshots"].sort(key=lambda s: s["timeSincePlantMs"])

    return {site: list(rounds.values()) for site, rounds in rounds_by_site.items()}


def process_file(json_path: Path, team_prefix: str, player_prefixes: tuple[str, ...]) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    map_name = data.get("map", "")
    if map_name not in MAP_TRANSFORMS:
        print(f"  SKIP: unknown map '{map_name}'")
        return

    selected_maps = data.get("selectedMaps", [])
    if not selected_maps:
        print(f"  SKIP: no selectedMaps")
        return

    jsonl_path = RAW_DIR / f"{team_prefix}_2026_raw_responses.jsonl"
    matches_by_id = load_jsonl(jsonl_path)
    if not matches_by_id:
        print(f"  SKIP: JSONL not found or empty at {jsonl_path.name}")
        return

    selected_ids = {s["matchId"] for s in selected_maps}
    sample_meta = {s["matchId"]: s for s in selected_maps}

    postplant_by_site: dict[str, list] = defaultdict(list)

    for match_id in selected_ids:
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            print(f"  WARNING: match {match_id[:8]}... not in JSONL")
            continue

        team_id = None
        for player in match_obj.get("players", []):
            if player.get("isObserver"):
                continue
            if player.get("gameName", "").startswith(player_prefixes):
                team_id = player.get("teamId")
                break
        if team_id is None:
            continue

        team_players = [
            p for p in match_obj.get("players", [])
            if not p.get("isObserver") and p.get("teamId") == team_id
        ]
        team_puuids = {p["puuid"] for p in team_players if p.get("puuid")}
        puuid_to_name = {
            p["puuid"]: clean_name(p.get("gameName", ""), player_prefixes)
            for p in team_players
        }

        meta = sample_meta[match_id]
        site_rounds = extract_postplant_snapshots(match_obj, map_name, team_puuids, puuid_to_name, selected_ids)

        for site, rounds in site_rounds.items():
            for rnd in rounds:
                rnd["matchId"] = match_id
                rnd["date"] = meta.get("date", "")
                rnd["opponent"] = meta.get("opponent", "")
                rnd["score"] = meta.get("score", "")
                postplant_by_site[site].append(rnd)

    total_rounds = sum(len(v) for v in postplant_by_site.values())
    total_snaps = sum(len(rnd["snapshots"]) for rounds in postplant_by_site.values() for rnd in rounds)

    data["postPlant10_20"] = {
        site: {"rounds": rounds}
        for site, rounds in postplant_by_site.items()
    }

    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  OK: {total_rounds} rounds, {total_snaps} snapshots across sites {list(postplant_by_site.keys())}")


def main() -> None:
    ct_files = sorted(DATA_DIR.glob("*_ct_retake_positions_last3.json"))
    print(f"Found {len(ct_files)} CT retake files.\n")

    for json_path in ct_files:
        stem = json_path.stem
        parts = stem.split("_")
        team_prefix = parts[0]
        if team_prefix not in TEAM_CONFIG:
            print(f"SKIP {json_path.name}: unknown team '{team_prefix}'")
            continue
        player_prefixes = TEAM_CONFIG[team_prefix]
        print(f"Processing {json_path.name} ...")
        process_file(json_path, team_prefix, player_prefixes)

    print("\nDone.")


if __name__ == "__main__":
    main()
