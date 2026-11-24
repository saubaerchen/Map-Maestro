"""Generic, local-only early-positioning analysis (replaces the per-team analyze_{tag}_early_positioning_batch.py).

Reuses the calculation from scripts/analyze_nvj_early_positioning_batch.py unchanged, but:
- reads only the prepared site JSONL (data/site/{prefix}_...), no esports API calls
- team, prefix, maps and transforms come from site_config.py

Usage: python scripts/live/analyze_early_positioning.py --team eintracht
Writes data/analysis/{prefix}_{map}_{side}_early_team_positioning_last3.json
"""
import argparse
import importlib.util
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_config import MAP_TRANSFORMS, ROOT, TEAMS, site_jsonl, team_pool  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "legacy_analyze", os.path.join(ROOT, "scripts", "analyze_nvj_early_positioning_batch.py"))
legacy = importlib.util.module_from_spec(_spec)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
_spec.loader.exec_module(legacy)


def load_local(path):
    matches, times = {}, {}
    for m in legacy.load_jsonl(legacy.Path(path)):
        mid = m.get("matchInfo", {}).get("matchId")
        if mid:
            matches[mid] = m
            times[mid] = m["matchInfo"].get("gameStartMillis", 0)
    return matches, times


def run(team_key):
    cfg = TEAMS[team_key]
    pre = cfg["prefix"]
    legacy.TEAM_NAME = cfg["name"]
    legacy.TEAM_PREFIXES = (cfg["tag"] + " ",)
    legacy.MAP_TRANSFORMS = MAP_TRANSFORMS
    legacy.MAP_DATE_CUTOFFS = {}
    matches, times = load_local(site_jsonl(pre))
    maps_present = Counter(m["matchInfo"]["map"] for m in matches.values())
    out_dir = legacy.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for map_name in team_pool(cfg):
        if not maps_present.get(map_name):
            continue
        for side_code, side_key in legacy.SIDES:
            try:
                ds = legacy.build_dataset_for_map_side(matches, times, map_name, side_code, side_key)
            except RuntimeError as e:
                print(f"  skip {map_name} {side_code}: {e}")
                continue
            path = out_dir / f"{pre}_{map_name.lower()}_{side_code}_early_team_positioning_last3.json"
            path.write_text(json.dumps(ds, indent=2), encoding="utf-8")
            t30 = ds["thresholds"]["lt30s"]
            written.append((map_name, side_code))
            print(f"  {map_name:8} {side_code}: sample={ds['sampleSize']} rounds<30s={t30['roundCount']} points={t30['pointCount']}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", action="append")
    a = ap.parse_args()
    for key in a.team or list(TEAMS):
        print(f"== {key}")
        run(key)


if __name__ == "__main__":
    main()
