"""
Build per-team economy data for the economy filter UI.

For each team, reads the raw JSONL and outputs one JSON file:
  veto-history-site-publish/data/{prefix}_economy.json

Structure:
  {
    "matchId": {
      "0":  { "teamTier": "pistol", "oppTier": "pistol", "teamHasOp": false },
      "1":  { "teamTier": "eco",    "oppTier": "full",   "teamHasOp": false },
      "5":  { "teamTier": "full",   "oppTier": "full",   "teamHasOp": true  }
    }
  }

Tier thresholds (team average loadoutValue per player):
  pistol  — roundNum 0 or 12 (first round of each half)
  eco     — avg < 2000  (and not pistol)
  force   — 2000 <= avg < 3800
  full    — avg >= 3800

teamHasOp — any team player's economy.weapon UUID matches OPERATOR_UUID

Usage:
    python scripts/build_economy_bundle.py --team jl
    python scripts/build_economy_bundle.py --team all
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import OPERATOR_UUID

OUTPUT_DIR = ROOT / "veto-history-site-publish" / "data"
APRIL_CUTOFF = "2026-04-01"

OPERATOR_UUID_UPPER = OPERATOR_UUID.upper()

PISTOL_ROUNDS = {0, 12}

TEAM_CONFIG = {
    "sge":  {"name": "Eintracht Frankfurt",  "prefix": "sge",  "player_prefix": "SGE ",  "jsonl": ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"},
    "fks":  {"name": "FOKUS",                "prefix": "fks",  "player_prefix": "FKS ",  "jsonl": ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl"},
    "rzn":  {"name": "Rasenmaeher",          "prefix": "rzn",  "player_prefix": "RZN ",  "jsonl": ROOT / "data" / "raw" / "rzn_2026_raw_responses.jsonl"},
    "ep":   {"name": "Enterprise Esports",   "prefix": "ep",   "player_prefix": "EP ",   "jsonl": ROOT / "data" / "raw" / "ep_2026_raw_responses.jsonl"},
    "jl":   {"name": "JOBlife",              "prefix": "jl",   "player_prefix": "JL ",   "jsonl": ROOT / "data" / "raw" / "jl_2026_raw_responses.jsonl"},
    "wip":  {"name": "WIP Esports",          "prefix": "wip",  "player_prefix": "WIP ",  "jsonl": ROOT / "data" / "raw" / "wip_2026_raw_responses.jsonl"},
    "nvj":  {"name": "NAVI Junior",          "prefix": "nvj",  "player_prefix": "NVJ ",  "jsonl": ROOT / "data" / "raw" / "nvj_2026_raw_responses.jsonl"},
    "tl":   {"name": "Team Liquid Academy",  "prefix": "tl",   "player_prefix": "TL ",   "jsonl": ROOT / "data" / "raw" / "tl_2026_raw_responses.jsonl"},
    "m1r":  {"name": "MIR",                  "prefix": "m1r",  "player_prefix": "M1R ",  "jsonl": ROOT / "data" / "raw" / "m1r_2026_raw_responses.jsonl"},
    "bar":  {"name": "Barcelona",            "prefix": "bar",  "player_prefix": "BAR ",  "jsonl": ROOT / "data" / "raw" / "bar_2026_raw_responses.jsonl"},
    "bjk":  {"name": "Besiktas",             "prefix": "bjk",  "player_prefix": "BJK ",  "jsonl": ROOT / "data" / "raw" / "bjk_2026_raw_responses.jsonl"},
    "rb":   {"name": "REBORN",               "prefix": "rb",   "player_prefix": "RB ",   "jsonl": ROOT / "data" / "raw" / "rb_2026_raw_responses.jsonl"},
    "ucam": {"name": "UCAM",                 "prefix": "ucam", "player_prefix": "UCAM ", "jsonl": ROOT / "data" / "raw" / "ucam_2026_raw_responses.jsonl"},
    "cgn":  {"name": "CGN Esports",          "prefix": "cgn",  "player_prefix": "CGN ",  "jsonl": ROOT / "data" / "raw" / "cgn_2026_raw_responses.jsonl"},
    "misa": {"name": "Misa Esports",         "prefix": "misa", "player_prefix": "MISA ", "jsonl": ROOT / "data" / "raw" / "misa_2026_raw_responses.jsonl"},
    "mdr":  {"name": "Mandatory",            "prefix": "mdr",  "player_prefix": "MDR ",  "jsonl": ROOT / "data" / "raw" / "mdr_2026_raw_responses.jsonl"},
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        print(f"  WARNING: JSONL not found at {path}")
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def classify_tier(avg_loadout: float, round_num: int) -> str:
    if round_num in PISTOL_ROUNDS:
        return "pistol"
    if avg_loadout < 2000:
        return "eco"
    if avg_loadout < 3800:
        return "force"
    return "full"


def build_for_team(cfg: dict) -> dict:
    matches = load_jsonl(cfg["jsonl"])
    player_prefix = cfg["player_prefix"]

    result: dict[str, dict] = {}
    seen_ids: set[str] = set()

    for m in matches:
        mi = m.get("matchInfo", {})
        mid = mi.get("matchId", "")
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)

        ts = mi.get("gameStartMillis", 0)
        if isinstance(ts, str):
            ts = int(ts)
        date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if date < APRIL_CUTOFF:
            continue

        players = m.get("players", [])
        team_puuids = {
            p["puuid"] for p in players
            if not p.get("isObserver") and p.get("gameName", "").startswith(player_prefix)
        }
        if not team_puuids:
            continue

        round_results = m.get("roundResults", [])
        match_data: dict[str, dict] = {}

        for rnd in round_results:
            round_num = rnd.get("roundNum", 0)
            player_stats = rnd.get("playerStats", [])

            team_stats = [ps for ps in player_stats if ps.get("puuid") in team_puuids]
            opp_stats  = [ps for ps in player_stats if ps.get("puuid") not in team_puuids]

            if not team_stats:
                continue

            team_loadouts = [ps.get("economy", {}).get("loadoutValue", 0) for ps in team_stats]
            opp_loadouts  = [ps.get("economy", {}).get("loadoutValue", 0) for ps in opp_stats] if opp_stats else [0]

            team_avg = sum(team_loadouts) / len(team_loadouts)
            opp_avg  = sum(opp_loadouts)  / len(opp_loadouts)

            team_has_op = any(
                ps.get("economy", {}).get("weapon", "").upper() == OPERATOR_UUID_UPPER
                for ps in team_stats
            )

            match_data[str(round_num)] = {
                "teamTier":   classify_tier(team_avg, round_num),
                "oppTier":    classify_tier(opp_avg,  round_num),
                "teamHasOp":  team_has_op,
            }

        if match_data:
            result[mid] = match_data

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, help="team key or 'all'")
    args = parser.parse_args()

    teams = list(TEAM_CONFIG.keys()) if args.team == "all" else [args.team]
    for team_key in teams:
        cfg = TEAM_CONFIG.get(team_key)
        if not cfg:
            print(f"Unknown team: {team_key}")
            continue
        print(f"Building economy for {cfg['name']}...")
        data = build_for_team(cfg)
        match_count = len(data)
        round_count = sum(len(v) for v in data.values())
        print(f"  {match_count} match(es), {round_count} round(s)")
        out = OUTPUT_DIR / f"{cfg['prefix']}_economy.json"
        out.write_text(json.dumps(data), encoding="utf-8")
        print(f"  -> {out.name}\n")

    print("NOTE: After running, bump ECONOMY_DATA_VERSION in app.js if data changed.")


if __name__ == "__main__":
    main()
