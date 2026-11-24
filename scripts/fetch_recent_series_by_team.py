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
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import TEAMS
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


def local_dt(ts_ms: int, tz_name: str) -> dt.datetime:
    tz = ZoneInfo(tz_name) if ZoneInfo is not None else dt.timezone.utc
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz)


def latest_reference_player(team_cfg: dict) -> tuple[str, str]:
    matches = load_team_matches(team_cfg["tag"], team_cfg["name"], team_cfg["data_file"], start_date=None)
    if not matches:
        raise RuntimeError(f"No local matches found for {team_cfg['tag']}")
    latest = max(matches, key=lambda m: (m.dt, m.match_id))
    player = latest.team_players[0]
    return player["gameName"], player["tagLine"]


def identify_team(match_obj: dict, team_tag: str) -> tuple[str | None, str]:
    team_id = None
    opponent = "???"
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        name = str(player.get("gameName", ""))
        prefix = name.split(" ")[0] if " " in name else name
        if prefix == team_tag:
            team_id = player.get("teamId")
            break
    if team_id is None:
        return None, opponent
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            continue
        name = str(player.get("gameName", ""))
        opponent = name.split(" ")[0] if " " in name else name
        break
    return team_id, opponent


def scoreline(match_obj: dict, team_id: str) -> tuple[int, int]:
    own = opp = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            own = team.get("roundsWon", 0)
        else:
            opp = team.get("roundsWon", 0)
    return own, opp


def fetch_recent_series(team_tag: str, n: int, timezone: str, api_key: str) -> dict:
    team_cfg = next((team for team in TEAMS if team["tag"] == team_tag), None)
    if team_cfg is None:
        raise RuntimeError(f"Unknown team tag: {team_tag}")

    game_name, tag_line = latest_reference_player(team_cfg)
    account = api_get_json(
        "/api/riot/account/v1/accounts/by-riot-id/esports/"
        + urllib.parse.quote(game_name, safe="")
        + "/"
        + urllib.parse.quote(tag_line, safe=""),
        api_key,
    )
    puuid = account["puuid"]
    history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
    recent = sorted(history.get("history", []), key=lambda h: h["gameStartTimeMillis"], reverse=True)

    series = []
    seen = {}
    fetched_maps = 0

    for item in recent:
        match = api_get_json(f"/api/matches/esports/{item['matchId']}", api_key)
        fetched_maps += 1
        team_id, opponent = identify_team(match, team_tag)
        if team_id is None:
            continue
        dt_local = local_dt(match["matchInfo"]["gameStartMillis"], timezone)
        date_key = dt_local.strftime("%Y-%m-%d")
        key = (date_key, opponent)
        if key not in seen:
            seen[key] = {
                "date": date_key,
                "opponent": opponent,
                "maps": [],
            }
            series.append(seen[key])
        own, opp = scoreline(match, team_id)
        seen[key]["maps"].append(
            {
                "time": dt_local.strftime("%H:%M"),
                "map": match["matchInfo"]["map"].split("/")[-1],
                "score": f"{own}-{opp}",
                "result": "W" if own > opp else "L",
                "match_id": item["matchId"],
            }
        )
        if len(series) >= n and all(len(s["maps"]) >= 2 for s in series[:n]):
            # good enough for typical Bo3 series; keep simple
            pass
        if len(series) >= n + 1:
            break

    out_series = []
    for s in series[:n]:
        maps_sorted = sorted(s["maps"], key=lambda m: m["time"])
        wins = sum(1 for m in maps_sorted if m["result"] == "W")
        losses = len(maps_sorted) - wins
        out_series.append(
            {
                "date": s["date"],
                "opponent": s["opponent"],
                "series_record": f"{wins}-{losses}",
                "maps": maps_sorted,
            }
        )

    return {
        "team": team_cfg["name"],
        "tag": team_tag,
        "reference_riot_id": f"{game_name}#{tag_line}",
        "fetched_maps": fetched_maps,
        "recent_series": out_series,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch most recent Valolytics series for one or more teams")
    parser.add_argument("--teams", nargs="+", required=True, help="Team tags, e.g. SGE FKS")
    parser.add_argument("--series-count", type=int, default=2, help="Number of recent series per team")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Timezone for date grouping")
    args = parser.parse_args()

    api_key = load_api_key()
    report = {
        "timezone": args.timezone,
        "series_count": args.series_count,
        "teams": [fetch_recent_series(tag, args.series_count, args.timezone, api_key) for tag in args.teams],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
