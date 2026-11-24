from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
CGN_SUMMARY_FILE = ROOT / "data" / "raw" / "cgn_2026_matches_detail.json"
PLAYER_NAME = "CGN Wolfen"


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


def identify_cgn(match_obj: dict) -> tuple[str, list[dict], set[str]]:
    team_id = None
    team_players = []
    team_puuids: set[str] = set()
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if str(player.get("gameName", "")).startswith("CGN "):
            team_id = player.get("teamId")
            break
    if team_id is None:
        raise RuntimeError("Could not identify CGN in match")
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
            team_puuids.add(player["puuid"])
    return team_id, team_players, team_puuids


def main() -> None:
    api_key = load_api_key()
    with CGN_SUMMARY_FILE.open("r", encoding="utf-8") as handle:
        rows = json.load(handle)

    match_ids = [row["matchId"] for row in rows]

    ct_rounds = 0
    first_kills = 0
    first_deaths = 0
    counted_matches = 0
    wolfen_puuid = None

    for match_id in match_ids:
        match = api_get_json(f"/api/matches/esports/{match_id}", api_key)
        _, team_players, team_puuids = identify_cgn(match)
        if wolfen_puuid is None:
            for player in team_players:
                if player.get("gameName") == PLAYER_NAME:
                    wolfen_puuid = player["puuid"]
                    break
        if wolfen_puuid is None:
            continue

        md = SimpleNamespace(round_results=match["roundResults"], team_players=team_players)
        sides = get_team_side_per_round(md, team_puuids)
        counted_matches += 1

        for rr in match.get("roundResults", []):
            if sides.get(rr["roundNum"], "atk") != "def":
                continue
            ct_rounds += 1
            kills = []
            for ps in rr.get("playerStats", []):
                for kill in ps.get("kills", []):
                    kills.append(kill)
            kills.sort(key=lambda item: item.get("timeSinceRoundStartMillis", 999999))
            if not kills:
                continue
            first = kills[0]
            if first.get("killer") == wolfen_puuid:
                first_kills += 1
            if first.get("victim") == wolfen_puuid:
                first_deaths += 1

    result = {
        "player": PLAYER_NAME,
        "matches_checked": counted_matches,
        "ct_rounds": ct_rounds,
        "ct_first_kills": first_kills,
        "ct_first_deaths": first_deaths,
        "ct_fk_rate": round(first_kills * 100.0 / ct_rounds, 2) if ct_rounds else None,
        "ct_fd_rate": round(first_deaths * 100.0 / ct_rounds, 2) if ct_rounds else None,
        "ct_opening_involvement_rate": round((first_kills + first_deaths) * 100.0 / ct_rounds, 2) if ct_rounds else None,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
