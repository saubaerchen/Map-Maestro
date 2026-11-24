from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import PLAYOFF_TAGS, PLAYOFF_TEAMS
from lib.match_parser import load_team_matches


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return match.group(1)


def api_get_json(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def detect_team_tags(match_obj: dict) -> set[str]:
    tags: set[str] = set()
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        name = player.get("gameName", "")
        tag = name.split(" ")[0] if " " in name else name
        if tag in PLAYOFF_TAGS:
            tags.add(tag)
    return tags


def existing_match_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            match_id = obj.get("matchInfo", {}).get("matchId")
            if match_id:
                ids.add(match_id)
    return ids


def latest_reference_player(team_cfg: dict) -> tuple[str, str]:
    matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"])
    if not matches:
        raise RuntimeError(f"No local matches found for {team_cfg['tag']}")
    latest = max(matches, key=lambda m: (m.dt, m.match_id))
    player = latest.team_players[0]
    return player["gameName"], player["tagLine"]


def local_date_from_millis(ts_ms: int, tz_name: str) -> str:
    if ZoneInfo is None:
        timezone = dt.timezone.utc
    else:
        timezone = ZoneInfo(tz_name)
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=timezone).strftime("%Y-%m-%d")


def append_jsonl(path: Path, match_obj: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(match_obj, separators=(",", ":")))
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Top4 Valolytics matches for a given local date")
    parser.add_argument("--date", required=True, help="Local date in YYYY-MM-DD")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Timezone for local date filtering")
    args = parser.parse_args()

    api_key = load_api_key()

    teams = [team for team in PLAYOFF_TEAMS]
    known_ids = {team["tag"]: existing_match_ids(ROOT / team["data_file"]) for team in teams}

    candidates_by_team: dict[str, list[dict]] = {}
    unique_match_ids: set[str] = set()
    ref_players: dict[str, dict] = {}

    for team in teams:
        game_name, tag_line = latest_reference_player(team)
        ref_players[team["tag"]] = {"gameName": game_name, "tagLine": tag_line}
        account = api_get_json(
            "/api/riot/account/v1/accounts/by-riot-id/esports/"
            + urllib.parse.quote(game_name, safe="")
            + "/"
            + urllib.parse.quote(tag_line, safe=""),
            api_key,
        )
        puuid = account["puuid"]
        history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
        rows = []
        for item in history.get("history", []):
            if local_date_from_millis(item["gameStartTimeMillis"], args.timezone) != args.date:
                continue
            rows.append(item)
            unique_match_ids.add(item["matchId"])
        candidates_by_team[team["tag"]] = rows

    fetched_matches: dict[str, dict] = {}
    for match_id in sorted(unique_match_ids):
        fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)

    appended: dict[str, list[str]] = {team["tag"]: [] for team in teams}
    touched_matches: dict[str, list[str]] = {}

    for match_id, match_obj in fetched_matches.items():
        tags_in_match = detect_team_tags(match_obj)
        touched_matches[match_id] = sorted(tags_in_match)
        for team in teams:
            tag = team["tag"]
            if tag not in tags_in_match:
                continue
            if match_id in known_ids[tag]:
                continue
            append_jsonl(ROOT / team["data_file"], match_obj)
            known_ids[tag].add(match_id)
            appended[tag].append(match_id)

    summary = {
        "date": args.date,
        "timezone": args.timezone,
        "referencePlayers": ref_players,
        "candidateMatchesByTeam": {
            tag: [
                {
                    "matchId": item["matchId"],
                    "gameStartTime": item.get("gameStartTime"),
                }
                for item in rows
            ]
            for tag, rows in candidates_by_team.items()
        },
        "fetchedMatchCount": len(fetched_matches),
        "fetchedMatches": touched_matches,
        "appendedByTeam": appended,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
