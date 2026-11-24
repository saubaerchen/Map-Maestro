from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import PLAYOFF_MATCH_IDS
from lib.match_parser import load_team_matches


TEAM_TAG = "MISA"
TEAM_NAME = "Misa Esports"
DATA_FILE = "data/raw/misa_2026_raw_responses.jsonl"
TARGET_MATCH_IDS = {
    "5cadffcf-1f28-4e7e-9eaf-ed57375868b4",
    "ea6e413d-f95f-404d-a8f6-7da51c5befdf",
    "1c4f285c-f4e1-411a-94ae-48bdd9a50167",
    "0cafb898-666e-4980-a856-61772ca83ff4",
}


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE, match_ids=PLAYOFF_MATCH_IDS)
    rows = []
    wins = 0
    losses = 0
    for md in matches:
        if md.match_id not in TARGET_MATCH_IDS:
            continue
        mw = 0
        ml = 0
        for rr in md.round_results:
            all_puuids = {ps["puuid"] for ps in rr.get("playerStats", [])}
            team_puuids = {p["puuid"] for p in md.team_players if p["puuid"] in all_puuids}
            opp_puuids = all_puuids - team_puuids
            all_kills = []
            for ps in rr.get("playerStats", []):
                all_kills.extend(ps.get("kills", []))
            all_kills.sort(key=lambda k: k.get("timeSinceRoundStartMillis", 0))

            seen = set()
            fc, oc = len(team_puuids), len(opp_puuids)
            if fc == 1 and oc == 1:
                seen.add((1, 1))
                if rr["winningTeam"] == md.team_id:
                    mw += 1
                else:
                    ml += 1
            for k in all_kills:
                v = k["victim"]
                if v in team_puuids:
                    team_puuids.discard(v)
                elif v in opp_puuids:
                    opp_puuids.discard(v)
                fc, oc = len(team_puuids), len(opp_puuids)
                if fc == 0 or oc == 0:
                    break
                if (fc, oc) == (1, 1) and (1, 1) not in seen:
                    seen.add((1, 1))
                    if rr["winningTeam"] == md.team_id:
                        mw += 1
                    else:
                        ml += 1
        wins += mw
        losses += ml
        rows.append(
            {
                "date": md.date,
                "opponent": md.opp,
                "map": md.map,
                "wins": mw,
                "losses": ml,
            }
        )

    print(json.dumps({"wins": wins, "losses": losses, "by_map": rows}, indent=2))


if __name__ == "__main__":
    main()
