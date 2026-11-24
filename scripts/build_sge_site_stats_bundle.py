"""
Build per-site statistics for SGE on all relevant maps.

T-side: plant rate, win rate, avg/min/max plant time, FK→plant time
CT-side: defuse share, defuse win rate, avg defuse time, FK after plant

Uses the same match IDs as the early positioning analysis JSONs.
Writes: veto-history-site-publish/data/sge_{map}_site_stats.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

APRIL_CUTOFF = "2026-04-01"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

ANALYSIS_DIR = ROOT / "data" / "analysis"
RAW_JSONL = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
OUTPUT_DIR = ROOT / "veto-history-site-publish" / "data"
TEAM_PREFIXES = ("SGE ",)

TARGET_MAPS_SITES = {
    "Bind": ["A", "B"],
    "Breeze": ["A", "B"],
    "Fracture": ["A", "B"],
    "Lotus": ["A", "B", "C"],
    "Pearl": ["A", "B"],
    "Split": ["A", "B"],
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        print(f"WARNING: JSONL not found at {path}")
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


def detect_sge_team_id(match_obj: dict) -> str | None:
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(TEAM_PREFIXES):
            return player.get("teamId")
    return None


def get_sge_puuids(match_obj: dict, sge_team_id: str) -> set[str]:
    return {
        p["puuid"]
        for p in match_obj.get("players", [])
        if not p.get("isObserver") and p.get("teamId") == sge_team_id and p.get("puuid")
    }


def avg(lst: list) -> float | None:
    return round(sum(lst) / len(lst), 1) if lst else None


def pct(a: int, b: int) -> float | None:
    return round(a / b * 100, 1) if b else None


def compute_stats(map_name: str, sites: list[str], match_ids: set[str], all_matches: dict) -> dict:
    t_rounds_total = 0
    t_won_by_kills = 0
    t_won_by_explosion = 0
    t_fk_times: list[float] = []
    t_site: dict[str, dict] = {s: {"plant_count": 0, "win_count": 0, "plant_times": [], "fk_to_plant": []} for s in sites}
    ct_rounds_total = 0
    ct_won_by_kills = 0
    ct_fk_times: list[float] = []
    ct_site: dict[str, dict] = {s: {"plant_count": 0, "win_count": 0, "defuse_times": [], "fk_after_plant": []} for s in sites}

    for match_id in match_ids:
        match_obj = all_matches.get(match_id)
        if not match_obj:
            print(f"  WARNING: match {match_id} not found in JSONL")
            continue

        sge_team_id = detect_sge_team_id(match_obj)
        if not sge_team_id:
            continue
        sge_puuids = get_sge_puuids(match_obj, sge_team_id)
        round_results = match_obj.get("roundResults", [])
        sides = get_team_side_per_round(SimpleNamespace(round_results=round_results), sge_puuids)

        for rr in round_results:
            round_num = rr.get("roundNum")
            side = sides.get(round_num)
            winning_team = rr.get("winningTeam")
            sge_won = (winning_team == sge_team_id)
            result_code = rr.get("roundResultCode", "")
            plant_site = str(rr.get("plantSite") or "").upper()
            plant_time_ms = rr.get("plantRoundTime") or 0
            defuse_time_ms = rr.get("defuseRoundTime") or 0

            sge_kills_ms = sorted(
                kill["timeSinceRoundStartMillis"]
                for ps in rr.get("playerStats", [])
                if ps.get("puuid") in sge_puuids
                for kill in ps.get("kills", [])
                if kill.get("timeSinceRoundStartMillis") is not None
            )

            if side == "atk":
                t_rounds_total += 1
                if sge_kills_ms:
                    t_fk_times.append(sge_kills_ms[0] / 1000)
                if sge_won:
                    if result_code == "Elimination":
                        t_won_by_kills += 1
                    elif result_code == "Detonate":
                        t_won_by_explosion += 1
                if plant_site in sites and plant_time_ms > 0:
                    s = t_site[plant_site]
                    s["plant_count"] += 1
                    if sge_won:
                        s["win_count"] += 1
                    s["plant_times"].append(plant_time_ms / 1000)
                    if sge_kills_ms and sge_kills_ms[0] < plant_time_ms:
                        s["fk_to_plant"].append((plant_time_ms - sge_kills_ms[0]) / 1000)

            elif side == "def":
                ct_rounds_total += 1
                if sge_kills_ms:
                    ct_fk_times.append(sge_kills_ms[0] / 1000)
                if sge_won and result_code == "Elimination":
                    ct_won_by_kills += 1
                if plant_site in sites and plant_time_ms > 0:
                    s = ct_site[plant_site]
                    s["plant_count"] += 1
                    if sge_won:
                        s["win_count"] += 1
                        if defuse_time_ms > plant_time_ms:
                            s["defuse_times"].append((defuse_time_ms - plant_time_ms) / 1000)
                    kills_after_plant = [t for t in sge_kills_ms if t > plant_time_ms]
                    if kills_after_plant:
                        s["fk_after_plant"].append((kills_after_plant[0] - plant_time_ms) / 1000)

    total_defuses = sum(ct_site[s]["win_count"] for s in sites)
    t_rounds_won = t_won_by_kills + t_won_by_explosion
    ct_rounds_won = ct_won_by_kills + total_defuses

    total_plants = sum(t_site[s]["plant_count"] for s in sites)
    t_output: dict[str, dict] = {}
    for site in sites:
        s = t_site[site]
        pt = s["plant_times"]
        t_output[site] = {
            "plant_count": s["plant_count"],
            "pct_plant": pct(s["plant_count"], total_plants),
            "pct_win": pct(s["win_count"], s["plant_count"]),
            "avg_plant_time": avg(pt),
            "min_plant_time": round(min(pt), 1) if pt else None,
            "max_plant_time": round(max(pt), 1) if pt else None,
            "fk_to_plant_avg": avg(s["fk_to_plant"]),
            "fk_to_plant_n": len(s["fk_to_plant"]),
        }

    ct_output: dict[str, dict] = {}
    for site in sites:
        s = ct_site[site]
        ct_output[site] = {
            "plant_count": s["plant_count"],
            "defuse_count": s["win_count"],
            "pct_defuse_win": pct(s["win_count"], s["plant_count"]),
            "pct_defuse_share": pct(s["win_count"], total_defuses),
            "avg_defuse_time": avg(s["defuse_times"]),
            "fk_after_plant_avg": avg(s["fk_after_plant"]),
            "fk_after_plant_n": len(s["fk_after_plant"]),
        }

    return {
        "team": "Eintracht Frankfurt",
        "map": map_name,
        "t_side": {
            "total_rounds": t_rounds_total,
            "rounds_won": t_rounds_won,
            "pct_rounds_won": pct(t_rounds_won, t_rounds_total),
            "won_by_kills": t_won_by_kills,
            "pct_won_by_kills": pct(t_won_by_kills, t_rounds_total),
            "won_by_explosion": t_won_by_explosion,
            "pct_won_by_explosion": pct(t_won_by_explosion, t_rounds_total),
            "avg_fk_time": avg(t_fk_times),
            "sites": t_output,
        },
        "ct_side": {
            "total_rounds": ct_rounds_total,
            "rounds_won": ct_rounds_won,
            "pct_rounds_won": pct(ct_rounds_won, ct_rounds_total),
            "won_by_kills": ct_won_by_kills,
            "pct_won_by_kills": pct(ct_won_by_kills, ct_rounds_total),
            "won_by_defuse": total_defuses,
            "pct_won_by_defuse": pct(total_defuses, ct_rounds_total),
            "avg_fk_time": avg(ct_fk_times),
            "sites": ct_output,
        },
    }


def main() -> None:
    print("Loading raw JSONL...")
    all_matches_list = load_jsonl(RAW_JSONL)
    all_matches = {
        m["matchInfo"]["matchId"]: m
        for m in all_matches_list
        if m.get("matchInfo", {}).get("matchId")
    }
    print(f"Loaded {len(all_matches)} raw matches.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for map_name, sites in TARGET_MAPS_SITES.items():
        map_matches = []
        for m in all_matches_list:
            mi = m.get("matchInfo", {})
            if mi.get("map", "") != map_name:
                continue
            ts = mi.get("gameStartMillis", 0)
            if isinstance(ts, str):
                ts = int(ts)
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if date < APRIL_CUTOFF:
                continue
            if not any(p.get("gameName", "").startswith(TEAM_PREFIXES) for p in m.get("players", [])):
                continue
            opp_names = [p.get("gameName", "").split()[0] for p in m.get("players", [])
                         if not p.get("gameName", "").startswith(TEAM_PREFIXES)]
            opp = Counter(opp_names).most_common(1)[0][0] if opp_names else "?"
            map_matches.append({"date": date, "opponent": opp, "matchId": mi["matchId"]})
        map_matches.sort(key=lambda x: x["date"], reverse=True)

        if not map_matches:
            print(f"SKIP {map_name}: no matches in JSONL")
            continue

        match_ids = {m["matchId"] for m in map_matches}
        print(f"[{map_name}] {len(map_matches)} matches:")
        for m in map_matches:
            print(f"  {m['date']} vs {m['opponent']}")

        result = compute_stats(map_name, sites, match_ids, all_matches)
        result["matches"] = map_matches

        output_path = OUTPUT_DIR / f"sge_{map_name.lower()}_site_stats.json"
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"  -> {output_path.name}")

        for site in sites:
            ts = result["t_side"]["sites"][site]
            cs = result["ct_side"]["sites"][site]
            print(f"  T/{site}: {ts['plant_count']} plants | {ts['pct_plant']}% plant | win={ts['pct_win']}% | avg={ts['avg_plant_time']}s")
            print(f"  CT/{site}: {cs['plant_count']} plants | defuse_win={cs['pct_defuse_win']}% | avg_defuse={cs['avg_defuse_time']}s")
        print()


if __name__ == "__main__":
    main()
