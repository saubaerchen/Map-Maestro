"""
Find Twitch VOD links + per-map timestamps for a team's recent matches.

Timestamp algorithm:
  1. Search VLR for the match page (team profile page first, event page fallback)
  2. Extract per-map YouTube timestamps from the VLR VODs section
  3. Fetch YouTube video page -> extract live stream startTimestamp metadata
  4. Compute: (yt_stream_start + yt_offset) - twitch_vod_start = Twitch offset

Usage:
    python scripts/find_vod_links.py --team jl
    python scripts/find_vod_links.py --team bar --count 5
"""

import argparse
import json
import datetime
import re
import urllib.parse
import urllib.request
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
JSONL_DIR = ROOT / "data" / "raw"

TWITCH_GQL = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

VLR_EVENT_ID   = "2925"
VLR_EVENT_SLUG = "challengers-2026-emea-stage-2"

# Checked in priority order — EMEA primary first, regional after
CHANNELS = [
    "valorant_emea",
    "valorant_fr",
    "valorantleague_dach",
    "lvpes2",
    "valorant_tur",
    "valorantesports_ar",
]

CHANNEL_PRIORITY = {
    "valorant_emea":       30,
    "valorantleague_dach": 12,
    "valorant_fr":          9,
    "lvpes2":               6,
    "valorant_tur":         4,
    "valorantesports_ar":   2,
}

# Terms that indicate the VOD is NOT a Challengers broadcast
_OFF_TOPIC = [" GC ", "GAME CHANGERS", " VCT "]
_OFF_TOPIC_PENALTY = -40

# names     = keywords found in Twitch VOD titles (valorant_fr titles each match by name)
# vlr_id    = VLR team profile numeric ID (for fetching their match list)
# vlr_kw    = slug keyword that appears in VLR match page URLs (e.g. "bar-a", "joblife")
TEAM_CONFIG = {
    "sge":  {"jsonl": "sge_2026_raw_responses.jsonl",  "prefix": "SGE ",  "names": ["EINTRACHT", "FRANKFURT", "SGE"],              "vlr_id": None,  "vlr_kw": "eintracht"},
    "fks":  {"jsonl": "fks_2026_raw_responses.jsonl",  "prefix": "FKS ",  "names": ["FOKUS", "FKS"],                              "vlr_id": None,  "vlr_kw": "fokus"},
    "jl":   {"jsonl": "jl_2026_raw_responses.jsonl",   "prefix": "JL ",   "names": ["JOBLIFE"],                                   "vlr_id": 11232, "vlr_kw": "joblife"},
    "bar":  {"jsonl": "bar_2026_raw_responses.jsonl",  "prefix": "BAR ",  "names": ["BARCA", "BARCELONA"],                        "vlr_id": 14461, "vlr_kw": "bar-a"},
    "ep":   {"jsonl": "ep_2026_raw_responses.jsonl",   "prefix": "EP ",   "names": ["ENTERPRISE"],                                "vlr_id": None,  "vlr_kw": "enterprise"},
    "bjk":  {"jsonl": "bjk_2026_raw_responses.jsonl",  "prefix": "BJK ",  "names": ["BESIKTAS", "BJK"],                           "vlr_id": None,  "vlr_kw": "be-ikta"},
    "rzn":  {"jsonl": "rzn_2026_raw_responses.jsonl",  "prefix": "RZN ",  "names": ["REZON", "RIZON", "RZN"],                    "vlr_id": None,  "vlr_kw": "rizon"},
    "wip":  {"jsonl": "wip_2026_raw_responses.jsonl",  "prefix": "WIP ",  "names": ["WIP"],                                       "vlr_id": None,  "vlr_kw": "wip"},
    "nvj":  {"jsonl": "nvj_2026_raw_responses.jsonl",  "prefix": "NVJ ",  "names": ["NAVI", "NATUS VINCERE", "NVJ"],              "vlr_id": None,  "vlr_kw": "natus-vincere"},
    "tl":   {"jsonl": "tl_2026_raw_responses.jsonl",   "prefix": "TL ",   "names": ["LIQUID ACADEMY", "TEAM LIQUID", "LIQUID"],   "vlr_id": 17297, "vlr_kw": "liquid"},
    "m1r":  {"jsonl": "m1r_2026_raw_responses.jsonl",  "prefix": "M1R ",  "names": ["MIR", "M1R"],                               "vlr_id": None,  "vlr_kw": "mir"},
    "rb":   {"jsonl": "rb_2026_raw_responses.jsonl",   "prefix": "RB ",   "names": ["REBORN"],                                    "vlr_id": 21841, "vlr_kw": "reborn"},
    "ucam": {"jsonl": "ucam_2026_raw_responses.jsonl", "prefix": "UCAM ", "names": ["UCAM"],                                      "vlr_id": 4616,  "vlr_kw": "ucam"},
    "mdr":  {"jsonl": "mdr_2026_raw_responses.jsonl",  "prefix": "MDR ",  "names": ["MDR"],                                       "vlr_id": None,  "vlr_kw": "mdr"},
    "misa": {"jsonl": "misa_2026_raw_responses.jsonl", "prefix": "MISA ", "names": ["MISA"],                                      "vlr_id": None,  "vlr_kw": "misa"},
    "plm":  {"jsonl": "plm_2026_raw_responses.jsonl",  "prefix": "PXL ",  "names": ["PIXELEUM", "PXL", "PLM"],                   "vlr_id": None,  "vlr_kw": "pixeleum"},
    "aqd":  {"jsonl": "aqd_2026_raw_responses.jsonl",  "prefix": "QAD ",  "names": ["ALQADISAH", "AL-QADISAH", "QAD", "AQD"],   "vlr_id": None,  "vlr_kw": "alqadsiah"},
    "gho":  {"jsonl": "gho_2026_raw_responses.jsonl",  "prefix": "GHS ",  "names": ["GHOOLS", "GHO"],                             "vlr_id": 13589, "vlr_kw": "ghools"},
    "cgn":  {"jsonl": "cgn_2026_raw_responses.jsonl",  "prefix": "CGN ",  "names": ["CGN"],                                          "vlr_id": 5214,  "vlr_kw": "cgn-esports"},
    "atn":  {"jsonl": "atn_2026_raw_responses.jsonl",  "prefix": "ATN ",  "names": ["ALTERNATE", "ATTAX", "ATN"],                     "vlr_id": None,  "vlr_kw": "alternate-attax"},
}

# Game name prefix → TEAM_CONFIG key (handles mismatches like TLA→tl, GLS→gho)
_PREFIX_TO_KEY = {cfg["prefix"].strip().upper(): key for key, cfg in TEAM_CONFIG.items()}
# Manual overrides for teams whose in-game prefix differs from config prefix
_PREFIX_OVERRIDES = {
    "TLA": "tl",
    "GLS": "gho",
}


def cfg_for_opp_tag(opp_tag: str) -> dict | None:
    tag = opp_tag.upper()
    key = _PREFIX_OVERRIDES.get(tag) or _PREFIX_TO_KEY.get(tag) or tag.lower()
    return TEAM_CONFIG.get(key)


# ─── generic helpers ──────────────────────────────────────────────────────────

def fetch_html(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible)", "Accept-Language": "en"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def safe_title(title: str, length: int = 70) -> str:
    return title.encode("ascii", errors="replace").decode("ascii")[:length]


def fmt_ts(total_seconds: int) -> str:
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def extract_match_links(html: str) -> list[str]:
    return re.findall(r'href="(/\d{4,7}/[^"?#\s]+)"', html)


# ─── JSONL loading ────────────────────────────────────────────────────────────

def load_series(jsonl_path: Path, team_prefix: str, count: int) -> list[dict]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL not found: {jsonl_path}")

    by_date: dict[str, dict] = defaultdict(lambda: {"maps": [], "opp_tags": set()})

    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            mi = d.get("matchInfo", {})
            ts = mi.get("gameStartMillis", 0)
            map_name = mi.get("map", "?")
            dt = datetime.datetime.fromtimestamp(
                int(ts) / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")

            players = d.get("players", [])
            team_players = [p for p in players if p.get("gameName", "").startswith(team_prefix)]
            if not team_players:
                continue

            team_id = team_players[0].get("teamId")
            opp_players = [
                p for p in players
                if p.get("teamId") != team_id
                and not p.get("isObserver")
                and p.get("gameName", "")
            ]
            opp_tag = opp_players[0].get("gameName", "").split(" ")[0] if opp_players else "?"

            by_date[dt]["maps"].append(map_name)
            by_date[dt]["opp_tags"].add(opp_tag)

    series = [
        {"date": dt, "maps": info["maps"], "opp_tag": next(iter(info["opp_tags"]), "?")}
        for dt, info in sorted(by_date.items(), reverse=True)
    ]
    return series[:count]


# ─── Twitch VOD fetching ──────────────────────────────────────────────────────

def fetch_vods_batch(channels: list[str], per_channel: int = 40) -> dict[str, list[dict]]:
    fields = " ".join(
        f'ch{i}: user(login: "{ch}") {{'
        f'  videos(first: {per_channel}, type: ARCHIVE, sort: TIME) {{'
        f'    edges {{ node {{ id title createdAt lengthSeconds }} }}'
        f'  }}'
        f'}}'
        for i, ch in enumerate(channels)
    )
    query = "{ " + fields + " }"
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        TWITCH_GQL,
        data=body,
        headers={
            "Client-Id": TWITCH_CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": "curl/8.0.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())

    result: dict[str, list[dict]] = {}
    for i, ch in enumerate(channels):
        user = (data.get("data") or {}).get(f"ch{i}")
        if not user:
            result[ch] = []
            continue
        result[ch] = [
            e["node"] for e in user["videos"]["edges"]
            if e["node"]["lengthSeconds"] > 300
        ]
    return result


def score_vod(vod: dict, opp_tag: str, team_names: list[str], channel: str) -> int:
    title = vod["title"].upper()
    score = CHANNEL_PRIORITY.get(channel, 0)

    for marker in _OFF_TOPIC:
        if marker in title:
            score += _OFF_TOPIC_PENALTY
            break

    for name in team_names:
        if name.upper() in title:
            score += 10
            break

    opp_cfg = cfg_for_opp_tag(opp_tag)
    if opp_cfg:
        for name in opp_cfg["names"]:
            if name.upper() in title:
                score += 5
                break

    return score


# ─── VLR match page lookup ────────────────────────────────────────────────────

_vlr_event_links_cache: list[str] | None = None


def get_vlr_event_links() -> list[str]:
    """Fetch all match links from the VLR event page (cached for the run)."""
    global _vlr_event_links_cache
    if _vlr_event_links_cache is not None:
        return _vlr_event_links_cache
    try:
        url = f"https://www.vlr.gg/event/matches/{VLR_EVENT_ID}/{VLR_EVENT_SLUG}/"
        _vlr_event_links_cache = extract_match_links(fetch_html(url))
    except Exception:
        _vlr_event_links_cache = []
    return _vlr_event_links_cache


def get_vlr_team_links(team_vlr_id: int) -> list[str]:
    """Fetch match links from the team's VLR profile page."""
    try:
        return extract_match_links(fetch_html(f"https://www.vlr.gg/team/{team_vlr_id}"))
    except Exception:
        return []


def find_vlr_match_url(team_kw: str, opp_kw: str, team_vlr_id: int | None) -> str | None:
    """
    Find a VLR match page URL for team vs opponent.
    Tries team profile page first (covers playoffs), then event page (group stage pool).
    """
    # Step 1: team profile page — most complete, covers all stages
    if team_vlr_id:
        for link in get_vlr_team_links(team_vlr_id):
            if opp_kw in link:
                return f"https://www.vlr.gg{link}"

    # Step 2: event page — group stage pool, no team ID needed
    for link in get_vlr_event_links():
        if team_kw in link and opp_kw in link:
            return f"https://www.vlr.gg{link}"

    return None


# ─── YouTube timestamp extraction ─────────────────────────────────────────────

def get_vlr_yt_timestamps(vlr_url: str) -> list[tuple[str, int]]:
    """
    Fetch VLR match page and return (youtube_video_id, offset_seconds) per map.
    Ordered by appearance on page, deduplicated.
    """
    try:
        html = fetch_html(vlr_url)
        pairs = re.findall(r"youtu\.be/([A-Za-z0-9_-]+)\?t=(\d+)", html)
        seen: set = set()
        result: list[tuple[str, int]] = []
        for vid_id, t in pairs:
            key = (vid_id, int(t))
            if key not in seen:
                seen.add(key)
                result.append((vid_id, int(t)))
        return result
    except Exception:
        return []


def get_yt_stream_start(video_id: str) -> datetime.datetime | None:
    """Return the live stream start time from YouTube video page metadata."""
    try:
        html = fetch_html(f"https://www.youtube.com/watch?v={video_id}")
        m = re.search(r'"startTimestamp":"([^"]+)"', html)
        if m:
            return datetime.datetime.fromisoformat(m.group(1))
    except Exception:
        pass
    return None


def compute_twitch_offset(yt_start: datetime.datetime, yt_offset_s: int, vod_created_at: str) -> int:
    """Return seconds into the Twitch VOD where the map starts."""
    vod_start = datetime.datetime.fromisoformat(vod_created_at.replace("Z", "+00:00"))
    actual_time = yt_start + datetime.timedelta(seconds=yt_offset_s)
    return max(0, int((actual_time - vod_start).total_seconds()))


# ─── main ─────────────────────────────────────────────────────────────────────

def find_vods(team_tag: str, count: int) -> None:
    cfg = TEAM_CONFIG.get(team_tag)
    if not cfg:
        print(f"Unknown team: {team_tag}. Known: {', '.join(TEAM_CONFIG)}")
        return

    jsonl_path = JSONL_DIR / cfg["jsonl"]
    team_names = cfg["names"]
    team_kw    = cfg["vlr_kw"]
    team_vlr_id = cfg["vlr_id"]

    print(f"Loading recent series for {team_tag.upper()} from JSONL...")
    series_list = load_series(jsonl_path, cfg["prefix"], count)

    if not series_list:
        print("No matches found in JSONL.")
        return

    dates_str = ", ".join(s["date"] for s in series_list)
    print(f"Found {len(series_list)} series: {dates_str}")
    print(f"Querying {len(CHANNELS)} Twitch channels in one batch...\n")
    vods_by_channel = fetch_vods_batch(CHANNELS)

    counts_str = "  ".join(f"{ch}={len(v)}" for ch, v in vods_by_channel.items())
    print(f"VODs fetched: {counts_str}\n")

    for series in series_list:
        date    = series["date"]
        opp     = series["opp_tag"]
        maps    = series["maps"]

        print(f"{'='*65}")
        print(f"  {date}  vs {opp}  [{', '.join(maps)}]")
        print(f"{'='*65}")

        # ── Step 1: find best VOD ─────────────────────────────────────────
        candidates = []
        for channel, vods in vods_by_channel.items():
            for vod in vods:
                if vod["createdAt"][:10] != date:
                    continue
                sc = score_vod(vod, opp, team_names, channel)
                candidates.append((sc, channel, vod))
        candidates.sort(key=lambda x: -x[0])

        if not candidates:
            print("  No VOD found on any channel for this date.\n")
            continue

        best_score, best_ch, best_vod = candidates[0]
        mins = best_vod["lengthSeconds"] // 60
        print(f"  VOD   [{best_ch}]  ({mins} min)")
        print(f"        {safe_title(best_vod['title'])}")
        print(f"        https://www.twitch.tv/videos/{best_vod['id']}")

        if len(candidates) > 1:
            print(f"  OTHER OPTIONS:")
            for _, ch, vod in candidates[1:]:
                m_alt = vod["lengthSeconds"] // 60
                print(f"    [{ch}] https://www.twitch.tv/videos/{vod['id']}  ({m_alt} min)")
                print(f"           {safe_title(vod['title'], 60)}")

        # ── Step 2: VLR → YouTube → Twitch timestamps ─────────────────────
        print()
        opp_cfg = cfg_for_opp_tag(opp)
        opp_kw  = opp_cfg["vlr_kw"] if opp_cfg else opp.lower()

        vlr_url = find_vlr_match_url(team_kw, opp_kw, team_vlr_id)
        if not vlr_url:
            print(f"  Timestamps: VLR match page not found (team_kw={team_kw}, opp_kw={opp_kw}).\n")
            continue

        yt_pairs = get_vlr_yt_timestamps(vlr_url)
        if not yt_pairs:
            print(f"  Timestamps: no YouTube VODs on VLR page.")
            print(f"  VLR: {vlr_url}\n")
            continue

        # Fetch YouTube stream start — one request per unique video ID
        yt_starts: dict[str, datetime.datetime | None] = {}
        for yt_id, _ in yt_pairs:
            if yt_id not in yt_starts:
                yt_starts[yt_id] = get_yt_stream_start(yt_id)

        print(f"  Timestamps  (VLR: {vlr_url.split('vlr.gg')[1]})")
        any_printed = False
        for i, (yt_id, yt_offset) in enumerate(yt_pairs):
            map_name = maps[i] if i < len(maps) else f"Map {i + 1}"
            yt_start = yt_starts.get(yt_id)
            if not yt_start:
                print(f"    {map_name}: could not resolve YouTube start time")
                continue
            offset_s = compute_twitch_offset(yt_start, yt_offset, best_vod["createdAt"])
            ts = fmt_ts(offset_s)
            print(f"    {map_name:10s}  https://www.twitch.tv/videos/{best_vod['id']}?t={ts}")
            any_printed = True

        if not any_printed:
            print(f"    (no timestamps computed)")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Twitch VOD links + per-map timestamps for recent matches"
    )
    parser.add_argument("--team", required=True, choices=list(TEAM_CONFIG.keys()))
    parser.add_argument("--count", type=int, default=3, help="Number of recent series (default: 3)")
    args = parser.parse_args()
    find_vods(args.team, args.count)


if __name__ == "__main__":
    main()
