"""Compute per-site stats for SGE on Lotus (T-side and CT-side).

T-side:
  %PLANT  — rounds planted at this site / total SGE T-side rounds
  %WIN    — SGE wins / rounds planted at this site
  avg_plant_time  — avg seconds from round start to plant
  min_plant_time / max_plant_time
  fk_to_plant_avg — avg seconds from SGE's first kill to plant (rounds where SGE kills before plant)

CT-side:
  %DEFUSE — SGE wins / rounds enemy planted at this site
  avg_defuse_time — avg seconds from plant to defuse (won rounds only)
  fk_after_plant_avg — avg seconds from plant to SGE's first kill after the plant

Uses the same match IDs as the Lotus analysis JSONs.
Writes: data/sge_lotus_site_stats.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

TEAM_PREFIXES = ("SGE ",)
RAW_JSONL = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
ANALYSIS_JSON = ROOT / "data" / "analysis" / "sge_lotus_ct_early_team_positioning_last3.json"
OUTPUT = ROOT / "veto-history-site-publish" / "data" / "sge_lotus_site_stats.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
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


def main() -> None:
    # Load target match IDs from the analysis JSON
    analysis = json.loads(ANALYSIS_JSON.read_text(encoding="utf-8"))
    target_ids = {m["matchId"] for m in analysis.get("selectedMaps", [])}
    print(f"Target match IDs ({len(target_ids)}):")
    for m in analysis.get("selectedMaps", []):
        print(f"  {m['date']} vs {m['opponent']}  {m['matchId']}")

    # Load matching raw records
    all_matches = {
        obj["matchInfo"]["matchId"]: obj
        for obj in load_jsonl(RAW_JSONL)
        if obj.get("matchInfo", {}).get("matchId") in target_ids
    }
    print(f"\nLoaded {len(all_matches)} raw match records for Lotus.\n")

    # Accumulators per side / site
    SITES = ["A", "B", "C"]

    t_rounds_total = 0
    t_site: dict[str, dict] = {s: {"plant_count": 0, "win_count": 0,
                                    "plant_times": [], "fk_to_plant": []} for s in SITES}

    ct_rounds_total = 0
    ct_site: dict[str, dict] = {s: {"plant_count": 0, "win_count": 0,
                                     "defuse_times": [], "fk_after_plant": []} for s in SITES}

    for match_id, match_obj in all_matches.items():
        sge_team_id = detect_sge_team_id(match_obj)
        if sge_team_id is None:
            continue
        sge_puuids = get_sge_puuids(match_obj, sge_team_id)
        round_results = match_obj.get("roundResults", [])
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=round_results), sge_puuids
        )

        for rr in round_results:
            round_num = rr.get("roundNum")
            side = sides.get(round_num)  # "atk" or "def"
            winning_team = rr.get("winningTeam")
            sge_won = (winning_team == sge_team_id)

            plant_site = rr.get("plantSite") or ""
            plant_time_ms = rr.get("plantRoundTime") or 0  # 0 means no plant
            defuse_time_ms = rr.get("defuseRoundTime") or 0

            # Collect all kills by SGE players this round, sorted by time
            sge_kills_ms: list[int] = sorted(
                kill["timeSinceRoundStartMillis"]
                for ps in rr.get("playerStats", [])
                if ps.get("puuid") in sge_puuids
                for kill in ps.get("kills", [])
                if kill.get("timeSinceRoundStartMillis") is not None
            )

            # ── T-SIDE ──────────────────────────────────────────────
            if side == "atk":
                t_rounds_total += 1
                if plant_site in SITES and plant_time_ms > 0:
                    s = t_site[plant_site]
                    s["plant_count"] += 1
                    if sge_won:
                        s["win_count"] += 1
                    s["plant_times"].append(plant_time_ms / 1000)

                    # SGE's first kill of the round (anywhere), if it occurred before the plant
                    if sge_kills_ms and sge_kills_ms[0] < plant_time_ms:
                        s["fk_to_plant"].append((plant_time_ms - sge_kills_ms[0]) / 1000)

            # ── CT-SIDE ─────────────────────────────────────────────
            elif side == "def":
                ct_rounds_total += 1
                if plant_site in SITES and plant_time_ms > 0:
                    s = ct_site[plant_site]
                    s["plant_count"] += 1
                    if sge_won:
                        s["win_count"] += 1
                        if defuse_time_ms > plant_time_ms:
                            s["defuse_times"].append((defuse_time_ms - plant_time_ms) / 1000)

                    # SGE's first kill AFTER the plant
                    kills_after_plant = [t for t in sge_kills_ms if t > plant_time_ms]
                    if kills_after_plant:
                        s["fk_after_plant"].append((kills_after_plant[0] - plant_time_ms) / 1000)

    def avg(lst: list[float]) -> float | None:
        return round(sum(lst) / len(lst), 1) if lst else None

    def pct(a: int, b: int) -> float | None:
        return round(a / b * 100, 1) if b else None

    total_plants = sum(t_site[s]["plant_count"] for s in SITES)
    t_output = {}
    for site in SITES:
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
        print(f"T-side site {site}: {s['plant_count']} plants / {t_rounds_total} rounds "
              f"| wins={s['win_count']} | plant_times={pt} | fk_to_plant={s['fk_to_plant']}")

    total_defuses = sum(ct_site[s]["win_count"] for s in SITES)
    ct_output = {}
    for site in SITES:
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
        print(f"CT-side site {site}: {s['plant_count']} plants | wins={s['win_count']} "
              f"| defuse_times={s['defuse_times']} | fk_after={s['fk_after_plant']}")

    result = {
        "team": "Eintracht Frankfurt",
        "map": "Lotus",
        "matches": analysis.get("selectedMaps", []),
        "t_side": {
            "total_rounds": t_rounds_total,
            "sites": t_output,
        },
        "ct_side": {
            "total_rounds": ct_rounds_total,
            "sites": ct_output,
        },
    }

    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote: {OUTPUT}")


if __name__ == "__main__":
    main()
