from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.match_parser import load_team_matches
from lib.stats_engine import get_team_side_per_round


TEAM_TAG = "MDR"
TEAM_NAME = "Mandatory"
DATA_FILE = str(ROOT / "data" / "raw" / "mdr_2026_raw_responses.jsonl")
PLAYER_ALIASES = {"takas", "takaas"}


def blank() -> dict:
    return {
        "maps": 0,
        "rounds": 0,
        "score": 0,
        "damage": 0,
        "kills": 0,
        "deaths": 0,
        "fk": 0,
        "fd": 0,
        "match_labels": [],
    }


def merge_player_name(game_name: str) -> str:
    base = game_name.replace(f"{TEAM_TAG} ", "").strip()
    return base.lower()


def add_match(acc: dict, md, side_filter: str) -> None:
    team_puuids = {p["puuid"] for p in md.team_players}
    sides = get_team_side_per_round(md, team_puuids)
    target_puuids = {
        p["puuid"]
        for p in md.team_players
        if merge_player_name(p.get("gameName", "")) in PLAYER_ALIASES
    }
    if not target_puuids:
        return

    acc["maps"] += 1
    acc["match_labels"].append(
        {
            "date": md.date,
            "opponent": md.opp,
            "map": md.map,
            "score": f"{md.team_score}-{md.opp_score}",
        }
    )

    for rr in md.round_results:
        if sides.get(rr["roundNum"], "atk") != side_filter:
            continue

        acc["rounds"] += 1

        all_kills = []
        for ps in rr.get("playerStats", []):
            for kill in ps.get("kills", []):
                all_kills.append(kill)
        all_kills.sort(key=lambda item: item.get("timeSinceRoundStartMillis", 999999))
        if all_kills:
            first = all_kills[0]
            if first.get("killer") in target_puuids:
                acc["fk"] += 1
            if first.get("victim") in target_puuids:
                acc["fd"] += 1

        for ps in rr.get("playerStats", []):
            if ps.get("puuid") not in target_puuids:
                continue
            acc["score"] += ps.get("score", 0)
            acc["kills"] += len(ps.get("kills", []))
            dmg = sum(d.get("damage", 0) for d in ps.get("damage", []))
            acc["damage"] += dmg
            victims = {kill.get("victim") for kill in all_kills}
            if ps.get("puuid") in victims:
                acc["deaths"] += 1


def finalize(acc: dict) -> dict:
    fk = acc["fk"]
    fd = acc["fd"]
    rounds = acc["rounds"]
    kills = acc["kills"]
    deaths = acc["deaths"]
    return {
        "maps": acc["maps"],
        "rounds": rounds,
        "acs": round(acc["score"] / rounds, 1) if rounds else 0.0,
        "adr": round(acc["damage"] / rounds, 1) if rounds else 0.0,
        "fk": fk,
        "fd": fd,
        "fk_fd_ratio": round(fk / max(fd, 1), 3),
        "kd": round(kills / max(deaths, 1), 3),
        "kills": kills,
        "deaths": deaths,
        "match_labels": acc["match_labels"],
    }


def main() -> None:
    matches = load_team_matches(TEAM_TAG, TEAM_NAME, DATA_FILE)
    matches = sorted(matches, key=lambda m: (m.dt, m.match_id), reverse=True)

    report = {
        "player_aliases": sorted(PLAYER_ALIASES),
        "recent_sample_definition": "last 5 maps",
    }

    for side_key, label in (("atk", "t_side"), ("def", "ct_side")):
        all_acc = blank()
        recent_acc = blank()
        for md in matches:
            add_match(all_acc, md, side_key)
        for md in matches[:5]:
            add_match(recent_acc, md, side_key)
        report[f"recent_5_maps_{label}"] = finalize(recent_acc)
        report[f"all_2026_{label}"] = finalize(all_acc)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
