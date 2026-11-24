from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import PLAYOFF_MATCH_IDS
from lib.match_parser import load_team_matches


TEAM_TAG = "MISA"
TEAM_NAME = "Misa Esports"
DATA_FILE = "data/raw/misa_2026_raw_responses.jsonl"
PLAYER_NAME = "QutionerX"


def strip_prefix(name: str) -> str:
    prefix = f"{TEAM_TAG} "
    return name[len(prefix):] if name.startswith(prefix) else name


def pct(num: int, den: int) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE, match_ids=PLAYOFF_MATCH_IDS)

    total_fk = 0
    total_fd = 0
    by_match: dict[str, dict[str, object]] = defaultdict(lambda: {"date": "", "map": "", "opponent": "", "fk": 0, "fd": 0})

    for md in matches:
        target_puuids = {
            p["puuid"]
            for p in md.team_players
            if strip_prefix(p.get("gameName", "")).lower() == PLAYER_NAME.lower()
        }

        key = md.match_id
        by_match[key]["date"] = md.date
        by_match[key]["map"] = md.map
        by_match[key]["opponent"] = md.opp

        for rr in md.round_results:
            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 999999))
            if not all_kills:
                continue

            first = all_kills[0]
            if first["killer"] in target_puuids:
                total_fk += 1
                by_match[key]["fk"] += 1
            elif first["victim"] in target_puuids:
                total_fd += 1
                by_match[key]["fd"] += 1

    rows = []
    for row in sorted(by_match.values(), key=lambda r: (r["date"], r["opponent"], r["map"]), reverse=True):
        opening_duels = row["fk"] + row["fd"]
        rows.append(
            {
                "date": row["date"],
                "opponent": row["opponent"],
                "map": row["map"],
                "first_kills": row["fk"],
                "first_deaths": row["fd"],
                "opening_duel_success_pct": pct(row["fk"], opening_duels),
            }
        )

    output = {
        "team": TEAM_NAME,
        "player": PLAYER_NAME,
        "scope": "Most recent tournament maps vs Eintracht Frankfurt and Team Liquid Academy",
        "maps": len(matches),
        "first_kills": total_fk,
        "first_deaths": total_fd,
        "opening_duel_success_pct": pct(total_fk, total_fk + total_fd),
        "by_map": rows,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
