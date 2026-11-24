"""
Build per-site statistics for any team on their relevant maps.

T-side: plant rate, win rate, avg/min/max plant time, FK→plant time
CT-side: defuse share, defuse win rate, avg defuse time, FK after plant

Match IDs are sourced from the team's analysis JSONs (same sample as early positioning).
Writes: veto-history-site-publish/data/{prefix}_{map}_site_stats.json

Usage:
    python scripts/build_team_site_stats_bundle.py --team fks
    python scripts/build_team_site_stats_bundle.py --team rzn
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

APRIL_CUTOFF = "2026-04-01"
API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = Path(__file__).resolve().parents[1] / "API_REFERENCE.md"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round

ANALYSIS_DIR = ROOT / "data" / "analysis"
OUTPUT_DIR = ROOT / "veto-history-site-publish" / "data"


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not m:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return m.group(1)


def api_fetch_match(match_id: str, api_key: str) -> dict | None:
    url = f"{API_BASE}/api/matches/esports/{match_id}"
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "Accept": "application/json", "User-Agent": "curl/8.0.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"  WARNING: API fetch failed for {match_id}: {e}")
        return None


def get_analysis_match_ids(prefix: str, map_name: str) -> set[str]:
    ids: set[str] = set()
    for side in ("ct", "t"):
        path = ANALYSIS_DIR / f"{prefix}_{map_name.lower()}_{side}_early_team_positioning_last3.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data.get("selectedMaps", []):
                mid = entry.get("matchId")
                if mid:
                    ids.add(mid)
        except Exception:
            pass
    return ids

TEAM_CONFIG = {
    "fks": {
        "name": "FOKUS",
        "prefix": "fks",
        "jsonl": ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl",
        "player_prefix": "FKS ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "rzn": {
        "name": "Rasenmaeher",
        "prefix": "rzn",
        "jsonl": ROOT / "data" / "raw" / "rzn_2026_raw_responses.jsonl",
        "player_prefix": "RZN ",
        "maps": {
            "Bind":   ["A", "B"],
            "Breeze": ["A", "B"],
            "Haven":  ["A", "B", "C"],
            "Lotus":  ["A", "B", "C"],
            "Split":  ["A", "B"],
        },
    },
    "ep": {
        "name": "Enterprise",
        "prefix": "ep",
        "jsonl": ROOT / "data" / "raw" / "ep_2026_raw_responses.jsonl",
        "player_prefix": "EP ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "jl": {
        "name":          "JOBlife",
        "prefix":        "jl",
        "jsonl":         ROOT / "data" / "raw" / "jl_2026_raw_responses.jsonl",
        "player_prefix": "JL ",
        "min_date":      "2026-04-18",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "wip": {
        "name":          "WIP Esports",
        "prefix":        "wip",
        "jsonl":         ROOT / "data" / "raw" / "wip_2026_raw_responses.jsonl",
        "player_prefix": "WIP ",
        "maps": {
            "Bind":     ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "nvj": {
        "name":          "NAVI Junior",
        "prefix":        "nvj",
        "jsonl":         ROOT / "data" / "raw" / "nvj_2026_raw_responses.jsonl",
        "player_prefix": "NVJ ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "tl": {
        "name":          "Team Liquid Academy",
        "prefix":        "tl",
        "jsonl":         ROOT / "data" / "raw" / "tl_2026_raw_responses.jsonl",
        "player_prefix": "TL ",
        "maps": {
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Split":    ["A", "B"],
        },
    },
    "m1r": {
        "name":          "MIR",
        "prefix":        "m1r",
        "jsonl":         ROOT / "data" / "raw" / "m1r_2026_raw_responses.jsonl",
        "player_prefix": "M1R ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "bar": {
        "name":          "Barcelona",
        "prefix":        "bar",
        "jsonl":         ROOT / "data" / "raw" / "bar_2026_raw_responses.jsonl",
        "player_prefix": "BAR ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "bjk": {
        "name":          "Besiktas",
        "prefix":        "bjk",
        "jsonl":         ROOT / "data" / "raw" / "bjk_2026_raw_responses.jsonl",
        "player_prefix": "BJK ",
        "maps": {
            "Bind":     ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "rb": {
        "name":          "REBORN",
        "prefix":        "rb",
        "jsonl":         ROOT / "data" / "raw" / "rb_2026_raw_responses.jsonl",
        "player_prefix": "RB ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "ucam": {
        "name":          "UCAM",
        "prefix":        "ucam",
        "jsonl":         ROOT / "data" / "raw" / "ucam_2026_raw_responses.jsonl",
        "player_prefix": "UCAM ",
        "maps": {
            "Bind":     ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "mdr": {
        "name":          "Mandatory",
        "prefix":        "mdr",
        "jsonl":         ROOT / "data" / "raw" / "mdr_2026_raw_responses.jsonl",
        "player_prefix": "MDR ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "misa": {
        "name":          "Misa Esports",
        "prefix":        "misa",
        "jsonl":         ROOT / "data" / "raw" / "misa_2026_raw_responses.jsonl",
        "player_prefix": "MISA ",
        "maps": {
            "Ascent":   ["A", "B"],
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
    "plm": {
        "name":          "Pixel Lumina",
        "prefix":        "plm",
        "jsonl":         ROOT / "data" / "raw" / "plm_2026_raw_responses.jsonl",
        "player_prefix": "PXL ",
        "maps": {
            "Bind":   ["A", "B"],
            "Haven":  ["A", "B", "C"],
            "Split":  ["A", "B"],
        },
    },
    "aqd": {
        "name":          "AlQadsiah",
        "prefix":        "aqd",
        "jsonl":         ROOT / "data" / "raw" / "aqd_2026_raw_responses.jsonl",
        "player_prefix": "QAD ",
        "maps": {
            "Breeze": ["A", "B"],
            "Haven":  ["A", "B", "C"],
            "Lotus":  ["A", "B", "C"],
            "Split":  ["A", "B"],
        },
    },
    "gho": {
        "name":          "Ghools",
        "prefix":        "gho",
        "jsonl":         ROOT / "data" / "raw" / "gho_2026_raw_responses.jsonl",
        "player_prefix": "GHS ",
        "maps": {
            "Bind":   ["A", "B"],
        },
    },
    "cgn": {
        "name":          "CGN Esports",
        "prefix":        "cgn",
        "jsonl":         ROOT / "data" / "raw" / "cgn_2026_raw_responses.jsonl",
        "player_prefix": "CGN ",
        "maps": {
            "Breeze":   ["A", "B"],
            "Fracture": ["A", "B"],
            "Haven":    ["A", "B", "C"],
            "Lotus":    ["A", "B", "C"],
            "Pearl":    ["A", "B"],
            "Split":    ["A", "B"],
        },
    },
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


def detect_team_id(match_obj: dict, player_prefix: str) -> str | None:
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(player_prefix):
            return player.get("teamId")
    return None


def get_team_puuids(match_obj: dict, team_id: str) -> set[str]:
    return {
        p["puuid"]
        for p in match_obj.get("players", [])
        if not p.get("isObserver") and p.get("teamId") == team_id and p.get("puuid")
    }


def avg(lst: list) -> float | None:
    return round(sum(lst) / len(lst), 1) if lst else None


def pct(a: int, b: int) -> float | None:
    return round(a / b * 100, 1) if b else None


def compute_stats(
    map_name: str,
    sites: list[str],
    match_ids: set[str],
    all_matches: dict,
    player_prefix: str,
) -> dict:
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

        non_obs = [p for p in match_obj.get("players", []) if not p.get("isObserver")]
        if len(non_obs) < 10:
            print(f"  SKIP {match_id}: only {len(non_obs)} players (scrim/practice)")
            continue
        team_id = detect_team_id(match_obj, player_prefix)
        if not team_id:
            print(f"  WARNING: could not detect team in match {match_id}")
            continue
        team_puuids = get_team_puuids(match_obj, team_id)
        round_results = match_obj.get("roundResults", [])
        sides = get_team_side_per_round(SimpleNamespace(round_results=round_results), team_puuids)

        for rr in round_results:
            round_num = rr.get("roundNum")
            side = sides.get(round_num)
            winning_team = rr.get("winningTeam")
            team_won = (winning_team == team_id)
            result_code = rr.get("roundResultCode", "")
            plant_site = str(rr.get("plantSite") or "").upper()
            plant_time_ms = rr.get("plantRoundTime") or 0
            defuse_time_ms = rr.get("defuseRoundTime") or 0

            team_kills_ms = sorted(
                kill["timeSinceRoundStartMillis"]
                for ps in rr.get("playerStats", [])
                if ps.get("puuid") in team_puuids
                for kill in ps.get("kills", [])
                if kill.get("timeSinceRoundStartMillis") is not None
            )

            if side == "atk":
                t_rounds_total += 1
                if team_kills_ms:
                    t_fk_times.append(team_kills_ms[0] / 1000)
                if team_won:
                    if result_code == "Elimination":
                        t_won_by_kills += 1
                    elif result_code == "Detonate":
                        t_won_by_explosion += 1
                if plant_site in sites and plant_time_ms > 0:
                    s = t_site[plant_site]
                    s["plant_count"] += 1
                    if team_won:
                        s["win_count"] += 1
                    s["plant_times"].append(plant_time_ms / 1000)
                    if team_kills_ms and team_kills_ms[0] < plant_time_ms:
                        s["fk_to_plant"].append((plant_time_ms - team_kills_ms[0]) / 1000)

            elif side == "def":
                ct_rounds_total += 1
                if team_kills_ms:
                    ct_fk_times.append(team_kills_ms[0] / 1000)
                if team_won and result_code == "Elimination":
                    ct_won_by_kills += 1
                if plant_site in sites and plant_time_ms > 0:
                    s = ct_site[plant_site]
                    s["plant_count"] += 1
                    if team_won:
                        s["win_count"] += 1
                        if defuse_time_ms > plant_time_ms:
                            s["defuse_times"].append((defuse_time_ms - plant_time_ms) / 1000)
                    kills_after_plant = [t for t in team_kills_ms if t > plant_time_ms]
                    if kills_after_plant:
                        s["fk_after_plant"].append((kills_after_plant[0] - plant_time_ms) / 1000)

    total_plants = sum(t_site[s]["plant_count"] for s in sites)
    total_defuses = sum(ct_site[s]["win_count"] for s in sites)
    t_rounds_won = t_won_by_kills + t_won_by_explosion
    ct_rounds_won = ct_won_by_kills + total_defuses

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, choices=list(TEAM_CONFIG.keys()))
    args = parser.parse_args()

    cfg = TEAM_CONFIG[args.team]
    prefix = cfg["prefix"]
    player_prefix = cfg["player_prefix"]
    print(f"Building site stats for {cfg['name']} ({args.team})...\n")

    api_key: str | None = None

    print("Loading raw JSONL...")
    all_matches_list = load_jsonl(cfg["jsonl"])
    all_matches = {
        m["matchInfo"]["matchId"]: m
        for m in all_matches_list
        if m.get("matchInfo", {}).get("matchId")
    }
    print(f"Loaded {len(all_matches)} raw matches.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_appended: list[dict] = []

    for map_name, sites in cfg["maps"].items():
        map_matches = []
        for m in all_matches_list + jsonl_appended:
            mi = m.get("matchInfo", {})
            if mi.get("map", "") != map_name:
                continue
            ts = mi.get("gameStartMillis", 0)
            if isinstance(ts, str):
                ts = int(ts)
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if date < cfg.get("min_date", APRIL_CUTOFF):
                continue
            if not any(p.get("gameName", "").startswith(player_prefix) for p in m.get("players", [])):
                continue
            non_obs = [p for p in m.get("players", []) if not p.get("isObserver")]
            if len(non_obs) < 10:
                continue
            opp_names = [p.get("gameName", "").split()[0] for p in m.get("players", [])
                         if not p.get("gameName", "").startswith(player_prefix)]
            opp = Counter(opp_names).most_common(1)[0][0] if opp_names else "?"
            map_matches.append({"date": date, "opponent": opp, "matchId": mi["matchId"]})

        existing_ids = {mm["matchId"] for mm in map_matches}
        analysis_ids = get_analysis_match_ids(prefix, map_name)
        missing_ids = analysis_ids - existing_ids

        if missing_ids:
            if api_key is None:
                api_key = load_api_key()
            for mid in missing_ids:
                print(f"  Fetching {map_name} match from API: {mid}")
                m_obj = api_fetch_match(mid, api_key)
                if m_obj and m_obj.get("matchInfo", {}).get("matchId"):
                    all_matches[mid] = m_obj
                    jsonl_appended.append(m_obj)
                    mi = m_obj["matchInfo"]
                    ts = mi.get("gameStartMillis", 0)
                    if isinstance(ts, str):
                        ts = int(ts)
                    date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    opp_names = [p.get("gameName", "").split()[0] for p in m_obj.get("players", [])
                                 if not p.get("gameName", "").startswith(player_prefix)]
                    opp = Counter(opp_names).most_common(1)[0][0] if opp_names else "?"
                    map_matches.append({"date": date, "opponent": opp, "matchId": mid})
                    with open(cfg["jsonl"], "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(m_obj) + "\n")
                    print(f"    -> appended to JSONL")

        map_matches.sort(key=lambda x: x["date"], reverse=True)

        if not map_matches:
            print(f"SKIP {map_name}: no data available")
            continue

        match_ids = {m["matchId"] for m in map_matches}
        print(f"[{map_name}] {len(map_matches)} matches:")
        for m in map_matches:
            print(f"  {m['date']} vs {m['opponent']}")

        result = compute_stats(map_name, sites, match_ids, all_matches, player_prefix)
        result["team"] = cfg["name"]
        result["map"] = map_name
        result["matches"] = map_matches

        output_path = OUTPUT_DIR / f"{cfg['prefix']}_{map_name.lower()}_site_stats.json"
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
