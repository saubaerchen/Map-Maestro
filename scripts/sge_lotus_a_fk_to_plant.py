"""
For SGE on Lotus T-side:
When SGE wins the round's first kill AND the killer is inside one of
{A-Root, A-Rubble, A-Main, A-Stairs} (Voronoi callout zones from valorant-api),
how often does the round end with a plant on A?

Also reports B-plant / C-plant / no-plant for the same FK zone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from scipy.spatial import cKDTree

from lib.stats_engine import get_team_side_per_round

MAPS_API = ROOT / "data" / "maps_api.json"
RAW = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
TARGET_CALLOUTS = {"Root/A", "Rubble/A", "Main/A", "Stairs/A"}
SGE_PREFIX = "SGE "
MIN_DATE_MS = None  # filter handled downstream if needed


def load_lotus_callouts():
    maps = json.loads(MAPS_API.read_text(encoding="utf-8"))["data"]
    lotus = next(m for m in maps if m.get("displayName") == "Lotus")
    pts, labels = [], []
    for c in lotus["callouts"]:
        loc = c["location"]
        pts.append((loc["x"], loc["y"]))
        labels.append(f"{c['regionName']}/{c['superRegionName']}")
    return np.array(pts, dtype=np.float32), labels


def killer_location(kill_event: dict) -> tuple[float, float] | None:
    killer = kill_event.get("killer")
    for p in kill_event.get("playerLocations", []) or []:
        if p.get("puuid") == killer:
            loc = p.get("location") or {}
            return (loc.get("x"), loc.get("y"))
    return None


def first_kill_in_round(rr: dict) -> dict | None:
    best = None
    for ps in rr.get("playerStats", []) or []:
        for k in ps.get("kills", []) or []:
            t = k.get("timeSinceRoundStartMillis")
            if t is None:
                continue
            if best is None or t < best["timeSinceRoundStartMillis"]:
                best = k
    return best


def detect_sge(match_obj: dict) -> dict | None:
    team_id = None
    for pl in match_obj.get("players", []):
        if pl.get("isObserver"):
            continue
        if pl.get("gameName", "").startswith(SGE_PREFIX):
            team_id = pl.get("teamId")
            break
    if team_id is None:
        return None
    team_puuids = {pl["puuid"] for pl in match_obj.get("players", [])
                   if not pl.get("isObserver") and pl.get("teamId") == team_id}
    puuid_to_name = {pl["puuid"]: pl.get("gameName", "").replace(SGE_PREFIX, "")
                     for pl in match_obj.get("players", []) if pl.get("teamId") == team_id}
    opp = None
    for pl in match_obj.get("players", []):
        if pl.get("isObserver") or pl.get("teamId") == team_id:
            continue
        nm = pl.get("gameName", "").split(" ")[0]
        opp = nm
        break
    return {"teamId": team_id, "puuids": team_puuids, "names": puuid_to_name, "opp": opp}


def iter_sge_lotus_matches():
    lines = RAW.read_text(encoding="utf-8").splitlines()
    seen_ids = set()
    for ln in lines:
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        r = obj.get("response") or obj
        mi = r.get("matchInfo") or {}
        if mi.get("map") != "Lotus":
            continue
        mid = mi.get("matchId")
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)
        # date filter: project scope >= 2026-04-01
        start_ms = mi.get("gameStartMillis") or 0
        if start_ms and start_ms < 1743465600000:  # 2026-04-01 UTC
            continue
        yield mid, r, mi


def main():
    anchor_pts, labels = load_lotus_callouts()
    tree = cKDTree(anchor_pts)

    qualifying = []  # list of dicts: per-round record for A-approach FK wins
    all_t_rounds = 0
    all_t_fk_wins = 0
    per_match = []

    for mid, match, mi in iter_sge_lotus_matches():
        ctx = detect_sge(match)
        if not ctx:
            continue
        team_puuids = ctx["puuids"]

        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match.get("roundResults", [])),
            team_puuids,
        )

        m_t_rounds = 0
        m_fk_wins = 0
        m_qualifying = 0

        for rr in match.get("roundResults", []):
            rnum = rr["roundNum"]
            if sides.get(rnum) != "atk":
                continue
            m_t_rounds += 1
            all_t_rounds += 1

            fk = first_kill_in_round(rr)
            if not fk:
                continue
            if fk.get("killer") not in team_puuids:
                continue  # SGE lost the FK
            m_fk_wins += 1
            all_t_fk_wins += 1

            loc = killer_location(fk)
            if not loc or loc[0] is None:
                continue
            dist, idx = tree.query(np.array(loc, dtype=np.float32), k=1)
            callout = labels[int(idx)]
            if callout not in TARGET_CALLOUTS:
                continue

            m_qualifying += 1
            qualifying.append({
                "matchId": mid,
                "opponent": ctx["opp"],
                "round": rnum,
                "killerPuuid": fk["killer"],
                "killerName": ctx["names"].get(fk["killer"], "?"),
                "timeMs": fk["timeSinceRoundStartMillis"],
                "location": {"x": loc[0], "y": loc[1]},
                "callout": callout,
                "plantSite": rr.get("plantSite"),
                "bombPlanter": rr.get("bombPlanter"),
                "planterIsSGE": rr.get("bombPlanter") in team_puuids if rr.get("bombPlanter") else False,
                "winningTeamId": rr.get("winningTeam"),
                "sgeWonRound": rr.get("winningTeam") == ctx["teamId"],
            })

        per_match.append({
            "matchId": mid, "opp": ctx["opp"],
            "t_rounds": m_t_rounds, "fk_wins": m_fk_wins, "qualifying": m_qualifying,
        })

    # ----- reporting -----
    print("=" * 72)
    print("SGE on Lotus — T-side rounds where SGE won the First Kill")
    print("  AND killer's position maps to A-Root / A-Rubble / A-Main / A-Stairs")
    print("=" * 72)
    print(f"Matches checked: {len(per_match)}")
    for m in per_match:
        print(f"  vs {m['opp']:<6} {m['matchId'][:8]}  T-rounds={m['t_rounds']:>2}  FK-wins={m['fk_wins']:>2}  A-approach-FK-wins={m['qualifying']:>2}")
    print()
    print(f"Total T-side rounds:          {all_t_rounds}")
    print(f"Total T-side rounds SGE won FK: {all_t_fk_wins}")
    print(f"...of which FK in A-approach zones: {len(qualifying)}")
    print()

    if not qualifying:
        print("No qualifying rounds found.")
        return

    by_zone = Counter(q["callout"] for q in qualifying)
    print("Breakdown by FK zone:")
    for z, n in by_zone.most_common():
        print(f"  {z:<12} {n:>3}")
    print()

    plant_counter = Counter()
    zone_to_plant = defaultdict(Counter)
    round_win_when_plant_A = {"yes": 0, "no": 0}
    for q in qualifying:
        ps = q["plantSite"] or "NO_PLANT"
        plant_counter[ps] += 1
        zone_to_plant[q["callout"]][ps] += 1
        if ps == "A":
            if q["sgeWonRound"]:
                round_win_when_plant_A["yes"] += 1
            else:
                round_win_when_plant_A["no"] += 1

    total_q = len(qualifying)
    print("Plant outcome (after A-approach FK win):")
    for site in ["A", "B", "C", "NO_PLANT"]:
        n = plant_counter.get(site, 0)
        pct = 100 * n / total_q if total_q else 0
        label = f"plant {site}" if site != "NO_PLANT" else "no plant"
        print(f"  {label:<10} {n:>3}  ({pct:5.1f} %)")
    print()

    print("Per-zone plant breakdown:")
    print(f"  {'zone':<12} {'n':>3}   A    B    C   none")
    for z, _ in by_zone.most_common():
        row = zone_to_plant[z]
        n = sum(row.values())
        a = row.get("A", 0); b = row.get("B", 0); c = row.get("C", 0); np_ = row.get("NO_PLANT", 0)
        print(f"  {z:<12} {n:>3}  {a:>3}  {b:>3}  {c:>3}   {np_:>3}")
    print()

    print("A-plant round-win rate (after A-approach FK win + plant A):")
    tot_a = round_win_when_plant_A["yes"] + round_win_when_plant_A["no"]
    if tot_a:
        print(f"  {round_win_when_plant_A['yes']}/{tot_a}  "
              f"({100*round_win_when_plant_A['yes']/tot_a:.1f} %)")
    print()

    print("Round-by-round detail:")
    print(f"  {'match':<12} {'opp':<6} {'rd':>3} {'killer':<12} {'zone':<10} {'plant':<6} {'won?':<4}")
    for q in qualifying:
        print(f"  {q['matchId'][:10]:<12} {q['opponent']:<6} {q['round']:>3} "
              f"{q['killerName']:<12} {q['callout']:<10} "
              f"{(q['plantSite'] or '-'):<6} {'Y' if q['sgeWonRound'] else 'N':<4}")


if __name__ == "__main__":
    main()
