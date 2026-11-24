"""Fetch all SGE matches for specific maps from full history and append new ones to raw JSONL."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import TEAMS
from lib.match_parser import load_team_matches

API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
TIMEZONE = "Europe/Berlin"

SGE_CFG = next(t for t in TEAMS if t["tag"] == "SGE")
RAW_JSONL = ROOT / SGE_CFG["data_file"]


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not m:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return m.group(1)


def api_get(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={"x-api-key": api_key, "Accept": "application/json", "User-Agent": "curl/8.0.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def local_date(ts_ms: int) -> str:
    tz = ZoneInfo(TIMEZONE) if ZoneInfo else dt.timezone.utc
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz).strftime("%Y-%m-%d")


def existing_ids() -> set[str]:
    ids: set[str] = set()
    if not RAW_JSONL.exists():
        return ids
    with RAW_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                mid = obj.get("matchInfo", {}).get("matchId")
                if mid:
                    ids.add(mid)
            except json.JSONDecodeError:
                continue
    return ids


def append_match(match_obj: dict) -> None:
    with RAW_JSONL.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(match_obj, separators=(",", ":")))
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill SGE matches for specific maps from full history")
    parser.add_argument("--maps", nargs="+", required=True, help="Map names to target e.g. Breeze Split Pearl")
    parser.add_argument("--min-date", default="2026-01-01", help="Ignore matches before this date (default: 2026-01-01)")
    parser.add_argument("--delay", type=float, default=1.2, help="Seconds between API calls (default: 1.2)")
    args = parser.parse_args()

    target_maps = set(args.maps)
    min_date = args.min_date
    delay = args.delay
    api_key = load_api_key()

    # Get reference player
    matches = load_team_matches("SGE", "Eintracht Frankfurt", str(RAW_JSONL), start_date=None)
    if not matches:
        raise RuntimeError("No existing SGE matches in JSONL to derive reference player")
    latest = max(matches, key=lambda m: (m.dt, m.match_id))
    ref = latest.team_players[0]
    game_name, tag_line = ref["gameName"], ref["tagLine"]
    print(f"Reference player: {game_name}#{tag_line}")

    # Resolve PUUID
    account = api_get(
        "/api/riot/account/v1/accounts/by-riot-id/esports/"
        + urllib.parse.quote(game_name, safe="")
        + "/"
        + urllib.parse.quote(tag_line, safe=""),
        api_key,
    )
    puuid = account["puuid"]

    # Full match history
    history = api_get(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
    all_items = history.get("history", [])
    print(f"Total matches in history: {len(all_items)}")

    known = existing_ids()
    new_items = [
        item for item in all_items
        if item["matchId"] not in known
        and local_date(item["gameStartTimeMillis"]) >= min_date
    ]
    print(f"Not yet in JSONL (from {min_date}): {len(new_items)} — fetching details to check map...")

    appended: dict[str, list] = {m: [] for m in target_maps}
    skipped_map = 0
    skipped_no_sge = 0

    for i, item in enumerate(new_items):
        match_id = item["matchId"]
        date = local_date(item["gameStartTimeMillis"])
        if i > 0:
            time.sleep(delay)
        match_obj = api_get(f"/api/matches/esports/{match_id}", api_key)

        map_name = match_obj.get("matchInfo", {}).get("map", "")

        if map_name not in target_maps:
            skipped_map += 1
            continue

        has_sge = any(
            p.get("gameName", "").startswith("SGE ")
            for p in match_obj.get("players", [])
            if not p.get("isObserver")
        )
        if not has_sge:
            skipped_no_sge += 1
            continue

        opp = ""
        for p in match_obj.get("players", []):
            if p.get("isObserver"):
                continue
            name = p.get("gameName", "")
            tag = name.split(" ")[0] if " " in name else name
            if tag != "SGE":
                opp = tag
                break

        append_match(match_obj)
        appended[map_name].append({"matchId": match_id, "date": date, "opponent": opp})
        print(f"  + {date} | {map_name} | vs {opp}")

    print(f"\n--- Summary ---")
    for map_name in target_maps:
        print(f"{map_name}: +{len(appended[map_name])} new")
        for m in appended[map_name]:
            print(f"    {m['date']} vs {m['opponent']}  {m['matchId']}")
    print(f"Skipped (wrong map): {skipped_map} | Skipped (no SGE): {skipped_no_sge}")


if __name__ == "__main__":
    main()
