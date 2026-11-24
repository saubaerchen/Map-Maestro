"""
Patch all T-side early-positioning analysis JSONs with plantSite from raw JSONL.

For each point in thresholds.ltXs.points, looks up plantSite using matchId + roundNum
from the corresponding raw JSONL file. Writes back in place.

Usage:
    python scripts/enrich_analysis_with_plant_site.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "data" / "analysis"
RAW_DIR = ROOT / "data" / "raw"

TEAM_RAW_FILES = {
    "sge":  "sge_2026_raw_responses.jsonl",
    "fks":  "fks_2026_raw_responses.jsonl",
    "rzn":  "rzn_2026_raw_responses.jsonl",
    "ep":   "ep_2026_raw_responses.jsonl",
    "jl":   "jl_2026_raw_responses.jsonl",
    "wip":  "wip_2026_raw_responses.jsonl",
    "nvj":  "nvj_2026_raw_responses.jsonl",
    "tl":   "tl_2026_raw_responses.jsonl",
    "m1r":  "m1r_2026_raw_responses.jsonl",
    "bar":  "bar_2026_raw_responses.jsonl",
    "bjk":  "bjk_2026_raw_responses.jsonl",
    "rb":   "rb_2026_raw_responses.jsonl",
    "ucam": "ucam_2026_raw_responses.jsonl",
}


def load_plant_site_lookup(jsonl_path: Path) -> dict[str, dict[int, str | None]]:
    lookup: dict[str, dict[int, str | None]] = {}
    if not jsonl_path.exists():
        return lookup
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                match = json.loads(line)
            except json.JSONDecodeError:
                continue
            match_id = match.get("matchInfo", {}).get("matchId")
            if not match_id:
                continue
            rounds = match.get("roundResults", [])
            lookup[match_id] = {rr.get("roundNum"): rr.get("plantSite") for rr in rounds}
    return lookup


def enrich_json(path: Path, lookup: dict[str, dict[int, str | None]]) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    thresholds = data.get("thresholds", {})
    for key in ("lt10s", "lt20s", "lt30s"):
        for point in thresholds.get(key, {}).get("points", []):
            if "plantSite" in point:
                continue
            match_id = point.get("matchId")
            round_num = point.get("roundNum")
            if match_id and round_num is not None:
                point["plantSite"] = lookup.get(match_id, {}).get(round_num)
                changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return changed


def main() -> None:
    for tag, raw_file in TEAM_RAW_FILES.items():
        raw_path = RAW_DIR / raw_file
        lookup = load_plant_site_lookup(raw_path)
        if not lookup:
            print(f"  {tag}: no raw JSONL, skipping")
            continue

        t_files = sorted(ANALYSIS_DIR.glob(f"{tag}_*_t_early_team_positioning_last3.json"))
        for path in t_files:
            changed = enrich_json(path, lookup)
            print(f"  {path.name}: {changed} points enriched")

    print("Done.")


if __name__ == "__main__":
    main()
