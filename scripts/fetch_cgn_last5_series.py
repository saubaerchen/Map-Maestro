from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
GAME_NAME = "CGN DaviH"
TAG_LINE = "epval"
LOCAL_TZ = "Europe/Berlin"


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


def local_dt(ts_ms: int) -> dt.datetime:
    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo is not None else dt.timezone.utc
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz)


def opponent_tag(match_obj: dict) -> str:
    cgn_team_id = None
    for p in match_obj.get("players", []):
        if p.get("isObserver"):
            continue
        if str(p.get("gameName", "")).startswith("CGN "):
            cgn_team_id = p.get("teamId")
            break
    if cgn_team_id is None:
        return "???"
    for p in match_obj.get("players", []):
        if p.get("isObserver"):
            continue
        if p.get("teamId") == cgn_team_id:
            continue
        name = str(p.get("gameName", ""))
        return name.split(" ")[0] if " " in name else name
    return "???"


def cgn_score(match_obj: dict) -> tuple[int, int]:
    cgn_team_id = None
    for p in match_obj.get("players", []):
        if p.get("isObserver"):
            continue
        if str(p.get("gameName", "")).startswith("CGN "):
            cgn_team_id = p.get("teamId")
            break
    if cgn_team_id is None:
        return (0, 0)
    own = opp = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == cgn_team_id:
            own = team.get("roundsWon", 0)
        else:
            opp = team.get("roundsWon", 0)
    return own, opp


def main() -> None:
    api_key = load_api_key()
    account = api_get_json(
        "/api/riot/account/v1/accounts/by-riot-id/esports/"
        + urllib.parse.quote(GAME_NAME, safe="")
        + "/"
        + urllib.parse.quote(TAG_LINE, safe=""),
        api_key,
    )
    puuid = account["puuid"]
    history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
    recent = sorted(history.get("history", []), key=lambda h: h["gameStartTimeMillis"], reverse=True)

    series = []
    seen_series = set()
    fetched = 0

    for item in recent:
        match = api_get_json(f"/api/matches/esports/{item['matchId']}", api_key)
        fetched += 1
        dt_local = local_dt(match["matchInfo"]["gameStartMillis"])
        date_key = dt_local.strftime("%Y-%m-%d")
        opp = opponent_tag(match)
        key = (date_key, opp)
        if key in seen_series:
            continue
        seen_series.add(key)

        own, enemy = cgn_score(match)
        series.append(
            {
                "date": date_key,
                "time": dt_local.strftime("%H:%M"),
                "opponent": opp,
                "latest_map": match["matchInfo"]["map"].split("/")[-1],
                "score": f"{own}-{enemy}",
                "match_id": item["matchId"],
            }
        )
        if len(series) >= 5:
            break

    print(
        json.dumps(
            {
                "riot_id": f"{GAME_NAME}#{TAG_LINE}",
                "local_timezone": LOCAL_TZ,
                "fetched_matches": fetched,
                "last_5_series": series,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
