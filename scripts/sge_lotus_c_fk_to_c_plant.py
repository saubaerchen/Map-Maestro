"""
SGE on Lotus T-side: when FK victim was in C super-region, how often did the round
end with a C-plant, and how long after the FK did the plant happen?
"""
from __future__ import annotations

import json, sys
from pathlib import Path
from types import SimpleNamespace
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from scipy.spatial import cKDTree
from lib.stats_engine import get_team_side_per_round

MAPS_API = ROOT / "data" / "maps_api.json"
RAW = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
SGE_PREFIX = "SGE "


def load_callouts():
    lotus = next(m for m in json.loads(MAPS_API.read_text(encoding="utf-8"))["data"]
                 if m.get("displayName") == "Lotus")
    pts, labels = [], []
    for c in lotus["callouts"]:
        pts.append((c["location"]["x"], c["location"]["y"]))
        labels.append(f"{c['regionName']}/{c['superRegionName']}")
    return np.array(pts, dtype=np.float32), labels


def first_kill(rr):
    best = None
    for ps in rr.get("playerStats", []) or []:
        for k in ps.get("kills", []) or []:
            t = k.get("timeSinceRoundStartMillis")
            if t is None: continue
            if best is None or t < best["timeSinceRoundStartMillis"]:
                best = k
    return best


def detect_sge(mo):
    tid = None
    for pl in mo.get("players", []):
        if not pl.get("isObserver") and pl.get("gameName", "").startswith(SGE_PREFIX):
            tid = pl.get("teamId"); break
    if tid is None: return None
    return {
        "tid": tid,
        "puuids": {pl["puuid"] for pl in mo.get("players", [])
                   if not pl.get("isObserver") and pl.get("teamId") == tid},
        "names": {pl["puuid"]: pl.get("gameName", "").replace(SGE_PREFIX, "")
                  for pl in mo.get("players", []) if pl.get("teamId") == tid},
    }


def iter_lotus():
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
        if start_ms and start_ms < 1743465600000: continue
        yield mid, r


def opp_of(mo, tid):
    for pl in mo.get("players", []):
        if not pl.get("isObserver") and pl.get("teamId") != tid:
            return pl.get("gameName", "").split(" ")[0]
    return "?"


def main():
    pts, labels = load_callouts()
    tree = cKDTree(pts)

    c_fks = []  # all T-side FK-wins where victim zone ends in "/C"

    for mid, match in iter_lotus():
        ctx = detect_sge(match)
        if not ctx: continue
        opp = opp_of(match, ctx["tid"])
        sides = get_team_side_per_round(
            SimpleNamespace(round_results=match.get("roundResults", [])),
            ctx["puuids"],
        )
        for rr in match.get("roundResults", []):
            rnum = rr["roundNum"]
            if sides.get(rnum) != "atk": continue
            fk = first_kill(rr)
            if not fk or fk.get("killer") not in ctx["puuids"]: continue
            vloc = fk.get("victimLocation") or {}
            vx, vy = vloc.get("x"), vloc.get("y")
            if vx is None: continue
            _, idx = tree.query(np.array([vx, vy], dtype=np.float32), k=1)
            zone = labels[int(idx)]
            if not zone.endswith("/C"): continue

            c_fks.append({
                "match": mid[:8], "opp": opp, "round": rnum,
                "killer": ctx["names"].get(fk["killer"], "?"),
                "victim_zone": zone,
                "fk_ms": fk["timeSinceRoundStartMillis"],
                "plantSite": rr.get("plantSite"),
                "plantRoundTime": rr.get("plantRoundTime"),
                "planterIsSGE": rr.get("bombPlanter") in ctx["puuids"] if rr.get("bombPlanter") else False,
                "sgeWon": rr.get("winningTeam") == ctx["tid"],
            })

    n_total = len(c_fks)
    c_plants = [e for e in c_fks if e["plantSite"] == "C"]
    other_plants = Counter(e["plantSite"] or "NO_PLANT" for e in c_fks)

    print("=" * 72)
    print("SGE Lotus T-side — rounds where SGE won the FK with victim in C-side")
    print("=" * 72)
    print(f"Total such rounds:           {n_total}")
    print()
    print("Plant outcome:")
    for site in ["A", "B", "C", "NO_PLANT"]:
        n = other_plants.get(site, 0)
        pct = 100 * n / n_total if n_total else 0
        lbl = f"plant {site}" if site != "NO_PLANT" else "no plant"
        print(f"  {lbl:<10} {n:>3}  ({pct:5.1f} %)")
    print()

    if c_plants:
        deltas = []
        print("C-plant rounds (FK -> plant timing):")
        print(f"  {'match':<10} {'opp':<6} {'rd':>3} {'killer':<12} {'victim':<10} "
              f"{'FK_s':>6} {'plant_s':>8} {'delta_s':>8} {'won':<3}")
        for e in sorted(c_plants, key=lambda x: (x["match"], x["round"])):
            fk_s = e["fk_ms"] / 1000
            pl_s = e["plantRoundTime"] / 1000
            delta = pl_s - fk_s
            deltas.append(delta)
            print(f"  {e['match']:<10} {e['opp']:<6} {e['round']:>3} {e['killer']:<12} "
                  f"{e['victim_zone']:<10} {fk_s:>6.1f} {pl_s:>8.1f} {delta:>6.1f} "
                  f"{'Y' if e['sgeWon'] else 'N':<3}")
        print()
        print(f"n C-plants after C-FK: {len(c_plants)} / {n_total} "
              f"({100*len(c_plants)/n_total:.1f} %)")
        import statistics
        print(f"Time from FK to plant (seconds):")
        print(f"  min  = {min(deltas):.1f}")
        print(f"  mean = {statistics.mean(deltas):.1f}")
        print(f"  med  = {statistics.median(deltas):.1f}")
        print(f"  max  = {max(deltas):.1f}")


if __name__ == "__main__":
    main()
