from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.json_builder import build_stats_json
from lib.match_parser import load_team_matches
from lib.stats_engine import compute_team_stats


TEAM_TAG = "UCAM"
TEAM_NAME = "UCAM Esports"
DATA_FILE = "data/raw/ucam_2026_raw_responses.jsonl"


def phase_for(date_str: str) -> str:
    if date_str <= "2026-02-08":
        return "Spain Rising Stage 1"
    if date_str <= "2026-02-25":
        return "EMEA Clash"
    if date_str <= "2026-03-07":
        return "Spain Stage 2"
    return "EMEA Stage 1"


def pct(v: float) -> float:
    return round(v * 100, 2)


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    by_phase = defaultdict(list)
    series_by_phase = defaultdict(set)

    for md in matches:
        phase = phase_for(md.date)
        by_phase[phase].append(md)
        series_by_phase[phase].add((md.date, md.opp))

    phase_order = [
        "Spain Rising Stage 1",
        "EMEA Clash",
        "Spain Stage 2",
        "EMEA Stage 1",
    ]

    rows = []
    previous = None
    for phase in phase_order:
        phase_matches = by_phase[phase]
        stats = compute_team_stats(phase_matches, TEAM_TAG, TEAM_NAME)
        result = build_stats_json(
            {
                TEAM_TAG: {
                    "name": TEAM_NAME,
                    "tag": TEAM_TAG,
                    **stats,
                }
            }
        )
        team = result["teams"][0]
        all_maps = team["allMaps"]
        series_rows = [
            {"date": date, "opponent": opp}
            for date, opp in sorted(series_by_phase[phase], reverse=True)
        ]

        current = {
            "phase": phase,
            "maps": all_maps["plays"],
            "series": len(series_rows),
            "series_list": series_rows,
            "t_side_win_pct": pct(all_maps["atk_rW_pct"]),
            "ct_side_win_pct": pct(all_maps["def_rW_pct"]),
            "postplant_win_pct": pct(all_maps["post_rW_pct"]),
            "retake_win_pct": pct(all_maps["ret_rW_pct"]),
        }
        if previous is not None:
            current["change_vs_prev_pp"] = {
                "t_side_win_pct": round(current["t_side_win_pct"] - previous["t_side_win_pct"], 2),
                "ct_side_win_pct": round(current["ct_side_win_pct"] - previous["ct_side_win_pct"], 2),
                "postplant_win_pct": round(current["postplant_win_pct"] - previous["postplant_win_pct"], 2),
                "retake_win_pct": round(current["retake_win_pct"] - previous["retake_win_pct"], 2),
            }
        previous = current
        rows.append(current)

    print(json.dumps({"team": TEAM_NAME, "phases": rows}, indent=2))


if __name__ == "__main__":
    main()
