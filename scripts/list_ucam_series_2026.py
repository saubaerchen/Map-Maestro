from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.match_parser import load_team_matches


TEAM_TAG = "UCAM"
TEAM_NAME = "UCAM Esports"
DATA_FILE = "data/raw/ucam_2026_raw_responses.jsonl"


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    series = defaultdict(list)

    for md in matches:
        series[(md.date, md.opp)].append(md)

    rows = []
    for (date, opp), items in sorted(series.items(), key=lambda item: (item[0][0], item[0][1]), reverse=True):
        rows.append(
            {
                "date": date,
                "opponent": opp,
                "maps": len(items),
                "map_record": f"{sum(1 for m in items if m.team_won)}-{sum(1 for m in items if not m.team_won)}",
            }
        )

    print(json.dumps({"team": TEAM_NAME, "series": rows}, indent=2))


if __name__ == "__main__":
    main()
