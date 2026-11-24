"""Build all Map-Info data files for the new-season teams by driving the legacy build scripts
with configuration from site_config.py (the legacy scripts themselves are not edited).

Run after prepare_site_data.py and analyze_early_positioning.py.
Usage: python scripts/live/build_site.py [--team eintracht ...]

Outputs (veto-history-site-publish/):
  defensive-early-data.js                      (all site teams; thresholds + sniper + all_fk)
  {prefix}-map-control-data.js                 ({prefix}MapControlData)
  data/{prefix}_{map}_site_stats.json
  data/{prefix}_{map}_{ct_retake|t_postplant}_positions_last3.json
  data/{prefix}_economy.json, data/{prefix}_agents.json
"""
import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_config import (KICKOFF_POOL, MAP_SITES, MAP_TRANSFORMS, PUBLISH_DIR, ROOT, TEAMS,  # noqa: E402
                         site_jsonl, transforms_short)

SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
MIN_DATE = "2026-09-01"


def load_module(name):
    spec = importlib.util.spec_from_file_location("legacy_" + name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def team_maps(prefix):
    c = Counter()
    for line in open(site_jsonl(prefix), encoding="utf-8"):
        c[json.loads(line)["matchInfo"]["map"]] += 1
    return [m for m in KICKOFF_POOL if c.get(m)]


def run_main(mod, args):
    old = sys.argv
    sys.argv = ["build"] + args
    try:
        mod.main()
    finally:
        sys.argv = old


def build_defensive(keys):
    mod = load_module("build_sge_defensive_early_bundle")
    mod.MAP_TRANSFORMS = MAP_TRANSFORMS
    payload, missing = {}, []
    for key in keys:
        cfg = TEAMS[key]
        pre, prefixes = cfg["prefix"], (cfg["tag"] + " ",)
        payload[key] = {"ct": {}, "t": {}}
        matches = {m["matchInfo"]["matchId"]: m for m in mod.load_jsonl(Path(site_jsonl(pre)))}
        for map_name in team_maps(pre):
            for side in ("ct", "t"):
                path = mod.ANALYSIS_DIR / f"{pre}_{map_name.lower()}_{side}_early_team_positioning_last3.json"
                if not path.exists():
                    missing.append(path.name)
                    continue
                ds = json.loads(path.read_text(encoding="utf-8"))
                ds["sniper"] = mod.build_sge_sniper_points_for_dataset(ds, side, matches, prefixes)
                ds["all_fk"] = mod.build_sge_all_fk_points_for_dataset(ds, side, matches, prefixes)
                ds["sniperRoundKeys"] = mod.build_sniper_round_keys(ds, side, matches, prefixes)
                payload[key][side][map_name] = ds
        print(f"defensive {key}: " + ", ".join(f"{m}" for m in payload[key]["ct"]))
    out = Path(PUBLISH_DIR) / "defensive-early-data.js"
    out.write_text("const defensiveEarlyData = " + json.dumps(payload, indent=2) + ";\n", encoding="utf-8")
    print(f"wrote {out}" + (f" (missing: {missing})" if missing else ""))


def build_per_team(key):
    cfg = TEAMS[key]
    pre, tag = cfg["prefix"], cfg["tag"]
    maps = team_maps(pre)
    jsonl = Path(site_jsonl(pre))

    m = load_module("build_team_site_stats_bundle")
    m.TEAM_CONFIG = {pre: {"name": cfg["name"], "prefix": pre, "jsonl": jsonl, "player_prefix": tag + " ",
                           "min_date": MIN_DATE, "maps": {mp: MAP_SITES[mp] for mp in maps}}}
    run_main(m, ["--team", pre])

    m = load_module("build_map_control_bundle")
    m.MAP_TRANSFORMS = transforms_short()
    m.TEAM_CONFIG = {pre: {"player_prefix": (tag + " ",), "jsonl": jsonl,
                           "output_file": Path(PUBLISH_DIR) / f"{pre}-map-control-data.js",
                           "js_var": f"{pre}MapControlData", "min_date": MIN_DATE, "maps": maps}}
    run_main(m, ["--team", pre])

    m = load_module("build_retake_postplant_bundle")
    m.MAP_TRANSFORMS = MAP_TRANSFORMS
    m.MAP_SITES = MAP_SITES
    m.TEAM_CONFIG = {pre: {"prefix": pre, "player_prefix": (tag + " ",), "jsonl": jsonl, "maps": maps, "skip_ct": []}}
    run_main(m, ["--team", pre])

    for name in ("build_economy_bundle", "build_agents_bundle"):
        m = load_module(name)
        if hasattr(m, "COMPETITIVE_MAPS"):
            m.COMPETITIVE_MAPS = set(KICKOFF_POOL) | {"Ascent", "Split"}
        m.TEAM_CONFIG = {pre: {"name": cfg["name"], "prefix": pre, "player_prefix": tag + " ", "jsonl": jsonl}}
        run_main(m, ["--team", pre])
    return maps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", action="append")
    a = ap.parse_args()
    keys = a.team or list(TEAMS)
    with_data = [k for k in TEAMS if os.path.exists(site_jsonl(TEAMS[k]["prefix"])) and team_maps(TEAMS[k]["prefix"])]
    build_defensive(with_data)
    summary = {}
    for key in keys:
        if key not in with_data:
            print(f"\n################ {key}: no official games with its core — skipped (shown as 'no data yet')")
            continue
        print(f"\n################ {key}")
        summary[key] = build_per_team(key)
    strip_puuids(with_data)
    print("\nmaps per team:", json.dumps(summary))


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k != "puuid"}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def strip_puuids(keys):
    """Remove player PUUIDs from every published data file (the site never uses them; they map to private accounts)."""
    pub = Path(PUBLISH_DIR)
    files = [pub / "defensive-early-data.js"] + [pub / f"{TEAMS[k]['prefix']}-map-control-data.js" for k in keys]
    files += [f for k in keys for f in (pub / "data").glob(f"{TEAMS[k]['prefix']}_*.json")]
    n = 0
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        if '"puuid"' not in text:
            continue
        if f.suffix == ".js":
            head, _, body = text.partition("=")
            obj = json.loads(body.strip().rstrip(";"))
            f.write_text(head + "= " + json.dumps(_strip(obj)) + ";\n", encoding="utf-8")
        else:
            f.write_text(json.dumps(_strip(json.loads(text))), encoding="utf-8")
        n += 1
    print(f"stripped puuids from {n} files")


if __name__ == "__main__":
    main()
