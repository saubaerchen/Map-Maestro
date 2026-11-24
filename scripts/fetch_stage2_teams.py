"""Fetch 2026 match data for all VCL EMEA Stage 2 teams into their raw JSONL files.

Teams covered:
  New:      CGN, WIP, BJK
  Refresh:  JL, EP, TL, BAR, M1R, FKS

NAVI Junior and REBORN skipped — player Riot IDs not resolvable via Valolytics API.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
API_KEY_FILE = ROOT / "API_REFERENCE.md"
API_BASE = "https://api.valolytics.gg"
TIMEZONE = "Europe/Berlin"

# Team configs: tag, name-prefix used in gameName, stable player list, output file
TEAM_CONFIGS = [
    {
        "tag": "CGN",
        "prefix": "CGN",
        "players": [
            ("CGN DaviH",   "epval"),
            ("CGN Wolfen",  "epval"),
            ("CGN Vince",   "epval"),
            ("CGN samed",   "epval"),
            ("CGN Zyppan",  "epval"),
        ],
        "out": ROOT / "data/raw/cgn_2026_raw_responses.jsonl",
    },
    {
        "tag": "WIP",
        "prefix": "WIP",
        "players": [
            ("WIP hoody",  "epval"),
            ("WIP H1ber",  "epval"),
            ("WIP Yuta",   "epval"),
            ("WIP 77even", "epval"),
        ],
        "out": ROOT / "data/raw/wip_2026_raw_responses.jsonl",
    },
    {
        "tag": "BJK",
        "prefix": "BJK",
        "players": [
            ("BJK oroni",  "epval"),
            ("BJK Docent", "epval"),
            ("BJK influx", "epval"),
            ("BJK ho1ly",  "epval"),
        ],
        "out": ROOT / "data/raw/bjk_2026_raw_responses.jsonl",
    },
    {
        "tag": "JL",
        "prefix": "JL",
        "players": [
            ("JL chiwa",  "epval"),
            ("JL runneR", "epval"),
            ("JL Doma",   "epval"),
        ],
        "out": ROOT / "data/raw/jl_2026_raw_responses.jsonl",
    },
    {
        "tag": "EP",
        "prefix": "EP",
        "players": [
            ("EP kozzy",  "epval"),
            ("EP MAGNUM", "epval"),
            ("EP iluri",  "epval"),
        ],
        "out": ROOT / "data/raw/ep_2026_raw_responses.jsonl",
    },
    {
        "tag": "TL",
        "prefix": "TLA",
        "players": [
            ("TLA Wanzeru", "epval"),
            ("TLA Kicks",   "epval"),
            ("TLA Prti",    "epval"),
            ("TLA GSR",     "epval"),
        ],
        "out": ROOT / "data/raw/tl_2026_raw_responses.jsonl",
    },
    {
        "tag": "BAR",
        "prefix": "BAR",
        "players": [
            ("BAR Fit1nho", "epval"),
            ("BAR globeX",  "epval"),
            ("BAR Kajuks",  "epval"),
        ],
        "out": ROOT / "data/raw/bar_2026_raw_responses.jsonl",
    },
    {
        "tag": "M1R",
        "prefix": "M1R",
        "players": [
            ("M1R Raz",     "epval"),
            ("M1R kospa1n", "epval"),
            ("M1R reblyik", "epval"),
        ],
        "out": ROOT / "data/raw/m1r_2026_raw_responses.jsonl",
    },
    {
        "tag": "NVJ",
        "prefix": "NVJ",
        "players": [
            ("NVJ avey",     "epval"),
            ("NVJ Javelin",  "epval"),
            ("NVJ metroneo", "epval"),
            ("NVJ k9lyos",   "epval"),
            ("NVJ Darxcio",  "epval"),
        ],
        "out": ROOT / "data/raw/nvj_2026_raw_responses.jsonl",
    },
    {
        "tag": "RB",
        "prefix": "RB",
        "players": [
            ("RB reazy",    "epval"),
            ("RB batujnax", "epval"),
            ("RB Kachoww",  "epval"),
            ("RB hezacoil", "epval"),
            ("RB Deadink",  "epval"),
        ],
        "out": ROOT / "data/raw/rb_2026_raw_responses.jsonl",
    },
    {
        "tag": "FKS",
        "prefix": "FKS",
        "players": [
            ("FKS shinnok", "epval"),
            ("FKS MOLSI",   "epval"),
            ("FKS pa1ze",   "epval"),
        ],
        "out": ROOT / "data/raw/fks_2026_raw_responses.jsonl",
    },
]


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not m:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return m.group(1)


def api_get(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={"x-api-key": api_key, "Accept": "application/json", "User-Agent": "curl/8.0.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def local_date(ts_ms: int) -> str:
    tz = ZoneInfo(TIMEZONE) if ZoneInfo else dt.timezone.utc
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=tz).strftime("%Y-%m-%d")


def existing_ids(jsonl_path: Path) -> set[str]:
    ids: set[str] = set()
    if not jsonl_path.exists():
        return ids
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                mid = obj.get("matchInfo", {}).get("matchId")
                if mid:
                    ids.add(mid)
            except json.JSONDecodeError:
                continue
    return ids


def append_match(jsonl_path: Path, match_obj: dict) -> None:
    with jsonl_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(match_obj, separators=(",", ":")))
        f.write("\n")


def fetch_team(cfg: dict, start_date: str, api_key: str) -> None:
    tag = cfg["tag"]
    prefix = cfg["prefix"]
    out = cfg["out"]
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"TEAM: {tag}  ->  {out.name}")
    print(f"{'='*60}")

    # Step 1: resolve PUUIDs
    all_items: list = []
    for game_name, tag_line in cfg["players"]:
        try:
            account = api_get(
                "/api/riot/account/v1/accounts/by-riot-id/esports/"
                + urllib.parse.quote(game_name, safe="")
                + "/"
                + urllib.parse.quote(tag_line, safe=""),
                api_key,
            )
            puuid = account["puuid"]
        except Exception as e:
            print(f"  SKIP player {game_name}#{tag_line}: {e}")
            continue

        # Step 2: match history
        try:
            history = api_get(f"/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}", api_key)
            items = history.get("history", [])
            print(f"  {game_name}#{tag_line}: {len(items)} matches in history")
            all_items.extend(items)
        except Exception as e:
            print(f"  SKIP history for {game_name}: {e}")

    # De-duplicate
    seen: set[str] = set()
    deduped = []
    for item in all_items:
        mid = item["matchId"]
        if mid not in seen:
            seen.add(mid)
            deduped.append(item)
    print(f"  Total unique match IDs: {len(deduped)}")

    # Filter to start date
    candidates = [item for item in deduped if local_date(item["gameStartTimeMillis"]) >= start_date]
    print(f"  On/after {start_date}: {len(candidates)}")

    known = existing_ids(out)
    new_items = [item for item in candidates if item["matchId"] not in known]
    print(f"  Already in JSONL: {len(candidates) - len(new_items)} | New to fetch: {len(new_items)}")

    # Step 3: fetch and append
    appended = []
    skipped = []
    for item in new_items:
        match_id = item["matchId"]
        date = local_date(item["gameStartTimeMillis"])
        print(f"  Fetching {match_id} ({date}) ...", end=" ", flush=True)
        try:
            match_obj = api_get(f"/api/matches/esports/{match_id}", api_key)
        except Exception as e:
            print(f"SKIP (API error: {e})")
            skipped.append(match_id)
            continue

        # Verify the team is actually in this match
        has_team = any(
            p.get("gameName", "").startswith(prefix + " ")
            for p in match_obj.get("players", [])
            if not p.get("isObserver")
        )
        if not has_team:
            print(f"SKIP ({prefix} not in match)")
            skipped.append(match_id)
            continue

        map_name = match_obj.get("matchInfo", {}).get("map", "unknown")
        append_match(out, match_obj)
        appended.append({"matchId": match_id, "date": date, "map": map_name})
        print(f"OK ({map_name})")

    print(f"\n  Done: +{len(appended)} new, {len(skipped)} skipped")

    # Step 4: verify summary
    print(f"\n  === {tag} coverage summary ===")
    map_counts: dict[str, int] = {}
    dates = []
    with out.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            m = json.loads(line)
            ts = m.get("matchInfo", {}).get("gameStartMillis", 0)
            d = local_date(ts)
            map_name = m.get("matchInfo", {}).get("map", "unknown")
            map_counts[map_name] = map_counts.get(map_name, 0) + 1
            dates.append(d)
    dates.sort()
    print(f"  Total maps in file: {len(dates)}")
    if dates:
        print(f"  Date range: {dates[0]} to {dates[-1]}")
    for mn, cnt in sorted(map_counts.items()):
        flag = " (<3)" if cnt < 3 else ""
        print(f"    {mn}: {cnt}{flag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Stage 2 team match data")
    parser.add_argument("--start-date", default="2026-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--teams", nargs="*", help="Limit to specific tags e.g. CGN WIP BJK")
    args = parser.parse_args()

    api_key = load_api_key()

    configs = TEAM_CONFIGS
    if args.teams:
        wanted = {t.upper() for t in args.teams}
        configs = [c for c in TEAM_CONFIGS if c["tag"] in wanted]
        if not configs:
            print(f"No matching teams for: {args.teams}")
            sys.exit(1)

    for cfg in configs:
        fetch_team(cfg, args.start_date, api_key)

    print("\n\nAll teams done.")


if __name__ == "__main__":
    main()
