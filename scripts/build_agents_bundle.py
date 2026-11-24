"""
Build per-team agent composition data for the Agents modal.

For each team, reads the raw JSONL and outputs one JSON file:
  veto-history-site-publish/data/{prefix}_agents.json

Includes all matches from 2026-04-01 onwards, grouped by map.

Structure:
  {
    "team": "Enterprise Esports",
    "Split": [
      {
        "agents":    ["Raze", "Omen", "Fade", "Killjoy", "Viper"],
        "agent_ids": ["uuid1", ..., "uuid5"],
        "games": [
          { "date": "2026-05-01", "opponent": "MDR", "matchId": "...", "players": ["EP Lime", ...] }
        ]
      },
      ...
    ],
    ...
  }

Agents within each comp are sorted by role (Duelist → Initiator → Controller → Sentinel)
so identical comps always hash the same way regardless of pick order.
Comps are sorted most-recent-first (by most recent game in the comp).

Usage:
    python scripts/build_agents_bundle.py --team ep
    python scripts/build_agents_bundle.py --team all
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import AGENT_MAP, AGENT_ROLE

OUTPUT_DIR = ROOT / "veto-history-site-publish" / "data"
APRIL_CUTOFF = "2026-01-01"
COMPETITIVE_MAPS = {"Bind", "Breeze", "Fracture", "Haven", "Lotus", "Pearl", "Split", "Abyss", "Icebox", "Ascent", "Sunset", "Corrode"}

ROLE_ORDER = {"Duelist": 0, "Initiator": 1, "Controller": 2, "Sentinel": 3}

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


def agent_sort_key(agent_name: str) -> int:
    return ROLE_ORDER.get(AGENT_ROLE.get(agent_name, ""), 99)


def build_for_team(cfg: dict) -> dict:
    matches = load_jsonl(cfg["jsonl"])
    player_prefix = cfg["player_prefix"]

    games_by_map: dict[str, list[dict]] = {}

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

        map_name = mi.get("map", "")
        if not map_name or map_name not in COMPETITIVE_MAPS:
            continue

        players = m.get("players", [])
        team_players = [
            p for p in players
            if not p.get("isObserver") and p.get("gameName", "").startswith(player_prefix)
        ]
        if not team_players:
            continue

        opp_names = [
            p.get("gameName", "").split()[0]
            for p in players
            if not p.get("gameName", "").startswith(player_prefix) and not p.get("isObserver")
        ]
        opponent = Counter(opp_names).most_common(1)[0][0] if opp_names else "?"

        comp_raw = []
        for p in team_players:
            char_id = p.get("characterId", "")
            agent_name = AGENT_MAP.get(char_id, char_id)
            comp_raw.append({"player": p.get("gameName", ""), "agent": agent_name, "agent_id": char_id})
        comp_raw.sort(key=lambda x: (agent_sort_key(x["agent"]), x["agent"]))

        games_by_map.setdefault(map_name, []).append({
            "date": date,
            "opponent": opponent,
            "matchId": mid,
            "agents": [x["agent"] for x in comp_raw],
            "agent_ids": [x["agent_id"] for x in comp_raw],
            "players": [x["player"] for x in comp_raw],
        })

    result: dict[str, list[dict]] = {}
    for map_name, games in games_by_map.items():
        games.sort(key=lambda g: g["date"], reverse=True)
        groups: dict[tuple, dict] = {}
        for g in games:
            key = tuple(g["agents"])
            if key not in groups:
                groups[key] = {"agents": g["agents"], "agent_ids": g["agent_ids"], "games": []}
            groups[key]["games"].append({
                "date": g["date"],
                "opponent": g["opponent"],
                "matchId": g["matchId"],
                "players": g["players"],
            })
        result[map_name] = sorted(
            groups.values(),
            key=lambda c: c["games"][0]["date"],
            reverse=True,
        )

    return {"team": cfg["name"], **result}


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
        print(f"Building agents for {cfg['name']}...")
        data = build_for_team(cfg)
        maps_found = [k for k in data if k != "team"]
        for m in maps_found:
            comps = data[m]
            total_games = sum(len(c["games"]) for c in comps)
            print(f"  {m}: {len(comps)} comp(s), {total_games} game(s)")
        out = OUTPUT_DIR / f"{cfg['prefix']}_agents.json"
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  -> {out.name}\n")

    print("NOTE: If new games were added, bump AGENTS_DATA_VERSION in app.js to bust browser cache.")


if __name__ == "__main__":
    main()
