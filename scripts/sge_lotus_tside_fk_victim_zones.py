"""
SGE on Lotus T-side: in which callout do VICTIMS stand when SGE wins the round's first kill?
I.e. the opening-pick location (where the CT defender was caught).
"""
from __future__ import annotations

import json, sys
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
SGE_PREFIX = "SGE "


def load_callouts():
    maps = json.loads(MAPS_API.read_text(encoding="utf-8"))["data"]
    lotus = next(m for m in maps if m.get("displayName") == "Lotus")
    pts, labels = [], []
    for c in lotus["callouts"]:
        loc = c["location"]
        pts.append((loc["x"], loc["y"]))
        labels.append(f"{c['regionName']}/{c['superRegionName']}")
    return np.array(pts, dtype=np.float32), labels


def first_kill_in_round(rr):
    best = None
    for ps in rr.get("playerStats", []) or []:
        for k in ps.get("kills", []) or []:
            t = k.get("timeSinceRoundStartMillis")
            if t is None: continue
            if best is None or t < best["timeSinceRoundStartMillis"]:
                best = k
    return best


def detect_sge(match_obj):
    team_id = None
    for pl in match_obj.get("players", []):
        if pl.get("isObserver"): continue
        if pl.get("gameName", "").startswith(SGE_PREFIX):
            team_id = pl.get("teamId"); break
    if team_id is None: return None
    return {
        "teamId": team_id,
        "puuids": {pl["puuid"] for pl in match_obj.get("players", [])
                   if not pl.get("isObserver") and pl.get("teamId") == team_id},
        "names": {pl["puuid"]: pl.get("gameName", "").replace(SGE_PREFIX, "")
                  for pl in match_obj.get("players", []) if pl.get("teamId") == team_id},
    }


def iter_lotus_matches():
    seen = set()
    for ln in RAW.read_text(encoding="utf-8").splitlines():
        try: obj = json.loads(ln)
        except Exception: continue
        r = obj.get("response") or obj
        mi = r.get("matchInfo") or {}
        if mi.get("map") != "Lotus": continue
        mid = mi.get("matchId")
        if not mid or mid in seen: continue
        seen.add(mid)
        start_ms = mi.get("gameStartMillis") or 0
        if start_ms and start_ms < 1743465600000: continue  # 2026-04-01
        yield mid, r, mi


def opp_of(match_obj, team_id):
    for pl in match_obj.get("players", []):
        if pl.get("isObserver") or pl.get("teamId") == team_id: continue
        return pl.get("gameName", "").split(" ")[0]
    return "?"


def main():
    anchor_pts, labels = load_callouts()
    tree = cKDTree(anchor_pts)

    events = []
    totals = {"t_rounds": 0, "fk_wins": 0}

    for mid, match, mi in iter_lotus_matches():
        ctx = detect_sge(match)
        if not ctx: continue
        opp = opp_of(match, ctx["teamId"])
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match.get("roundResults", [])),
            ctx["puuids"],
        )
        for rr in match.get("roundResults", []):
            rnum = rr["roundNum"]
            if sides.get(rnum) != "atk": continue
            totals["t_rounds"] += 1
            fk = first_kill_in_round(rr)
            if not fk: continue
            if fk.get("killer") not in ctx["puuids"]: continue
            totals["fk_wins"] += 1
            vloc = fk.get("victimLocation") or {}
            vx, vy = vloc.get("x"), vloc.get("y")
            if vx is None: continue
            _, idx = tree.query(np.array([vx, vy], dtype=np.float32), k=1)
            events.append({
                "match": mid[:8], "opp": opp, "round": rnum,
                "killer": ctx["names"].get(fk["killer"], "?"),
                "time_ms": fk["timeSinceRoundStartMillis"],
                "victim_zone": labels[int(idx)],
                "plantSite": rr.get("plantSite"),
                "sgeWon": rr.get("winningTeam") == ctx["teamId"],
            })

    print("=" * 70)
    print("SGE on Lotus T-side — where the VICTIM stood when SGE won the FK")
    print("=" * 70)
    print(f"T-rounds total: {totals['t_rounds']}    SGE FK-wins: {totals['fk_wins']}    "
          f"with victim location: {len(events)}")
    print()

    zone_ct = Counter(e["victim_zone"] for e in events)
    print(f"{'zone':<14} {'n':>3}  {'%':>6}")
    for z, n in zone_ct.most_common():
        print(f"  {z:<12} {n:>3}  {100*n/len(events):>5.1f}%")
    print()

    # group by super-region (site)
    site_ct = Counter()
    for e in events:
        site = e["victim_zone"].split("/")[1]
        site_ct[site] += 1
    print("Grouped by super-region:")
    for s, n in site_ct.most_common():
        print(f"  {s:<8} {n:>3}  {100*n/len(events):>5.1f}%")
    print()

    print("Detail:")
    print(f"  {'match':<10} {'opp':<6} {'rd':>3}  {'t_ms':>6}  {'killer':<12} {'victim_zone':<14} {'plant':<6} {'won':<3}")
    for e in sorted(events, key=lambda x: (x["match"], x["round"])):
        print(f"  {e['match']:<10} {e['opp']:<6} {e['round']:>3}  {e['time_ms']:>6}  "
              f"{e['killer']:<12} {e['victim_zone']:<14} {(e['plantSite'] or '-'):<6} "
              f"{'Y' if e['sgeWon'] else 'N':<3}")


if __name__ == "__main__":
    main()
