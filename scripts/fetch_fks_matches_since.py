"""Fetch all FKS matches from a given start date and append new ones to the raw JSONL."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
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

FKS_CFG = next(t for t in TEAMS if t["tag"] == "FKS")
RAW_JSONL = ROOT / FKS_CFG["data_file"]


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
    parser = argparse.ArgumentParser(description="Fetch FKS matches from a start date into the raw JSONL")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD (inclusive, Europe/Berlin)")
    args = parser.parse_args()

    api_key = load_api_key()
    start = args.start_date

    # Use stable roster players — shinnok/MOLSI/pa1ze have been on FKS all of 2026.
    # Avoid using cullum (joined Apr 14) or pyrolll (left Apr 14) as reference to
    # prevent missing matches when the roster rotates.
    STABLE_PLAYERS = [
        ("FKS shinnok", "epval"),
        ("FKS MOLSI", "epval"),
        ("FKS pa1ze", "epval"),
    ]

    all_items: list = []
    for game_name, tag_line in STABLE_PLAYERS:
        account = api_get(
            "/api/riot/account/v1/accounts/by-riot-id/esports/"
            + urllib.parse.quote(game_name, safe="")
            + "/"
            + urllib.parse.quote(tag_line, safe=""),
            api_key,
        )
        puuid = account["puuid"]
        history = api_get(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
        items = history.get("history", [])
        print(f"Reference player: {game_name}#{tag_line}  ({len(items)} total matches in history)")
        all_items.extend(items)

    # De-duplicate across players
    seen: set[str] = set()
    deduped = []
    for item in all_items:
        mid = item["matchId"]
        if mid not in seen:
            seen.add(mid)
            deduped.append(item)
    all_items = deduped
    print(f"Total matches in history: {len(all_items)}")

    # Filter to start date
    candidates = [
        item for item in all_items
        if local_date(item["gameStartTimeMillis"]) >= start
    ]
    print(f"Matches on/after {start}: {len(candidates)}")

    known = existing_ids()
    new_items = [item for item in candidates if item["matchId"] not in known]
    print(f"Already in JSONL: {len(candidates) - len(new_items)} | New to fetch: {len(new_items)}")

    appended = []
    skipped = []
    for item in new_items:
        match_id = item["matchId"]
        date = local_date(item["gameStartTimeMillis"])
        print(f"  Fetching {match_id} ({date}) ...", end=" ", flush=True)
        try:
            match_obj = api_get(f"/api/matches/esports/{match_id}", api_key)
        except Exception as e:
            print(f"SKIP (API error: {e})")
            skipped.append(match_id)
            continue
        # Verify FKS is actually in this match
        has_fks = any(
            p.get("gameName", "").startswith("FKS ")
            for p in match_obj.get("players", [])
            if not p.get("isObserver")
        )
        if not has_fks:
            print("SKIP (FKS not in match)")
            skipped.append(match_id)
            continue
        map_name = match_obj.get("matchInfo", {}).get("map", "unknown")
        append_match(match_obj)
        appended.append({"matchId": match_id, "date": date, "map": map_name})
        print(f"OK ({map_name})")

    print(f"\nDone. Appended {len(appended)} new matches, skipped {len(skipped)}.")
    for m in appended:
        print(f"  + {m['date']}  {m['map']}  {m['matchId']}")


if __name__ == "__main__":
    main()
