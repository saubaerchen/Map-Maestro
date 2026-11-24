"""
Export last-N VODs + per-map Twitch timestamps for a team's target maps to Excel.

Usage:
    python scripts/export_map_vods_excel.py --team bar --maps Haven Split Ascent Fracture Pearl Lotus --games 2
    python scripts/export_map_vods_excel.py --team bar --maps Lotus Pearl --games 3
"""

import argparse
import json
import datetime
import re
import urllib.request
from pathlib import Path
from collections import defaultdict

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT     = Path(__file__).resolve().parents[1]
JSONL_DIR = ROOT / "data" / "raw"
OUT_DIR   = ROOT / "output"

TWITCH_GQL       = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

VLR_EVENT_ID   = "2925"
VLR_EVENT_SLUG = "challengers-2026-emea-stage-2"

CHANNELS = [
    "valorant_emea", "valorant_fr", "valorantleague_dach",
    "lvpes2", "valorant_tur", "valorantesports_ar",
]
CHANNEL_PRIORITY = {
    "valorant_emea": 30, "valorantleague_dach": 12, "valorant_fr": 9,
    "lvpes2": 6, "valorant_tur": 4, "valorantesports_ar": 2,
}
_OFF_TOPIC = [" GC ", " VCT ", "GAME CHANGERS"]

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
    "cgn":  {"jsonl": "cgn_2026_raw_responses.jsonl",  "prefix": "CGN ",  "names": ["CGN"],                                       "vlr_id": 5214,  "vlr_kw": "cgn-esports"},
    "atn":  {"jsonl": "atn_2026_raw_responses.jsonl",  "prefix": "ATN ",  "names": ["ALTERNATE", "ATTAX", "ATN"],                 "vlr_id": None,  "vlr_kw": "alternate-attax"},
}

_PREFIX_TO_KEY = {cfg["prefix"].strip().upper(): key for key, cfg in TEAM_CONFIG.items()}
_PREFIX_OVERRIDES = {"TLA": "tl", "GLS": "gho"}


def cfg_for_opp_tag(tag: str):
    t = tag.upper()
    key = _PREFIX_OVERRIDES.get(t) or _PREFIX_TO_KEY.get(t) or t.lower()
    return TEAM_CONFIG.get(key)


# ─── helpers ──────────────────────────────────────────────────────────────────

def fetch_html(url, timeout=14):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible)", "Accept-Language": "en"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fmt_ts(total_seconds):
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


# ─── JSONL loading ─────────────────────────────────────────────────────────────

def load_map_games(jsonl_path, prefix, target_maps, n_games):
    by_map = defaultdict(list)
    with open(jsonl_path, encoding="utf-8") as f:
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
            if map_name not in target_maps:
                continue
            dt = datetime.datetime.fromtimestamp(
                int(ts) / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")
            if dt < "2026-04-01":
                continue
            players = d.get("players", [])
            tp = [p for p in players if p.get("gameName", "").startswith(prefix)]
            if not tp:
                continue
            tid = tp[0].get("teamId")
            op = [p for p in players if p.get("teamId") != tid
                  and not p.get("isObserver") and p.get("gameName", "")]
            opp = op[0].get("gameName", "").split(" ")[0] if op else "?"
            by_map[map_name].append({"date": dt, "opp": opp})

    result = {}
    for m in target_maps:
        games = sorted(by_map[m], key=lambda x: x["date"], reverse=True)[:n_games]
        result[m] = games
    return result


# ─── Twitch ───────────────────────────────────────────────────────────────────

def fetch_vods_batch(channels, per_channel=50):
    fields = " ".join(
        f'ch{i}: user(login: "{ch}") {{'
        f'  videos(first: {per_channel}, type: ARCHIVE, sort: TIME) {{'
        f'    edges {{ node {{ id title createdAt lengthSeconds }} }}'
        f'  }}'
        f'}}'
        for i, ch in enumerate(channels)
    )
    body = json.dumps({"query": "{ " + fields + " }"}).encode()
    req = urllib.request.Request(
        TWITCH_GQL, data=body,
        headers={"Client-Id": TWITCH_CLIENT_ID, "Content-Type": "application/json",
                 "User-Agent": "curl/8.0.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read())
    result = {}
    for i, ch in enumerate(channels):
        user = (data.get("data") or {}).get(f"ch{i}")
        result[ch] = (
            [e["node"] for e in user["videos"]["edges"] if e["node"]["lengthSeconds"] > 300]
            if user else []
        )
    return result


def score_vod(vod, opp_tag, team_names, channel):
    title = vod["title"].upper()
    sc = CHANNEL_PRIORITY.get(channel, 0)
    for mk in _OFF_TOPIC:
        if mk in title:
            sc -= 40
            break
    for nm in team_names:
        if nm.upper() in title:
            sc += 10
            break
    opp_cfg = cfg_for_opp_tag(opp_tag)
    if opp_cfg:
        for nm in opp_cfg["names"]:
            if nm.upper() in title:
                sc += 5
                break
    return sc


def best_vod(date, opp_tag, team_names, vods_by_channel):
    cands = []
    for ch, vods in vods_by_channel.items():
        for v in vods:
            if v["createdAt"][:10] == date:
                cands.append((score_vod(v, opp_tag, team_names, ch), ch, v))
    cands.sort(key=lambda x: -x[0])
    return cands[0] if cands else None


# ─── VLR + YouTube timestamps ─────────────────────────────────────────────────

def load_vlr_links(team_vlr_id, event_id, event_slug):
    team_links, event_links = [], []
    try:
        html = fetch_html(f"https://www.vlr.gg/team/{team_vlr_id}")
        team_links = re.findall(r'href="(/\d{4,7}/[^"?#\s]+)"', html)
    except Exception:
        pass
    try:
        html = fetch_html(f"https://www.vlr.gg/event/matches/{event_id}/{event_slug}/")
        event_links = re.findall(r'href="(/\d{4,7}/[^"?#\s]+)"', html)
    except Exception:
        pass
    return team_links, event_links


def find_vlr_url(opp_kw, team_kw, team_links, event_links):
    for link in team_links:
        if opp_kw in link:
            return "https://www.vlr.gg" + link
    for link in event_links:
        if team_kw in link and opp_kw in link:
            return "https://www.vlr.gg" + link
    return None


def get_yt_pairs(vlr_url):
    try:
        html = fetch_html(vlr_url)
        pairs = re.findall(r"youtu\.be/([A-Za-z0-9_-]+)\?t=(\d+)", html)
        seen, out = set(), []
        for vid, t in pairs:
            k = (vid, int(t))
            if k not in seen:
                seen.add(k)
                out.append((vid, int(t)))
        return out
    except Exception:
        return []


_yt_cache = {}


def get_yt_start(vid):
    if vid in _yt_cache:
        return _yt_cache[vid]
    try:
        html = fetch_html(f"https://www.youtube.com/watch?v={vid}")
        m = re.search(r'"startTimestamp":"([^"]+)"', html)
        if m:
            dt = datetime.datetime.fromisoformat(m.group(1))
            _yt_cache[vid] = dt
            return dt
    except Exception:
        pass
    _yt_cache[vid] = None
    return None


def compute_twitch_offset(yt_start, yt_off_s, vod_created_at):
    vod_start = datetime.datetime.fromisoformat(vod_created_at.replace("Z", "+00:00"))
    return max(0, int((yt_start + datetime.timedelta(seconds=yt_off_s) - vod_start).total_seconds()))


# ─── per-series map-order lookup from JSONL ────────────────────────────────────

def map_play_order(jsonl_path, prefix, date, opp_tag):
    """Return maps played in chronological order for a given date+opponent."""
    games = []
    with open(jsonl_path, encoding="utf-8") as f:
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
            dt = datetime.datetime.fromtimestamp(
                int(ts) / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")
            if dt != date:
                continue
            map_name = mi.get("map", "?")
            players = d.get("players", [])
            tp = [p for p in players if p.get("gameName", "").startswith(prefix)]
            if not tp:
                continue
            tid = tp[0].get("teamId")
            op = [p for p in players if p.get("teamId") != tid
                  and not p.get("isObserver") and p.get("gameName", "")]
            opp = op[0].get("gameName", "").split(" ")[0] if op else "?"
            if opp == opp_tag:
                games.append((int(ts), map_name))
    games.sort()
    return [m for _, m in games]


# ─── Excel export ─────────────────────────────────────────────────────────────

MAP_COLORS = {
    "Haven":   "3D6B8C",
    "Split":   "7B3D8C",
    "Ascent":  "8C6A3D",
    "Fracture":"3D8C5A",
    "Pearl":   "3D7A8C",
    "Lotus":   "8C3D4F",
}
DEFAULT_COLOR = "4A4A5A"
HEADER_BG     = "1E1E2E"
ROW_BG_EVEN   = "252535"
ROW_BG_ODD    = "1C1C2C"
TEXT_COLOR     = "E8E8F0"
MUTED_COLOR    = "8888AA"
LINK_COLOR     = "7EB5FF"


def hex_fill(hex_color):
    return PatternFill(fill_type="solid", fgColor=hex_color)


def make_border(color="444466"):
    side = Side(style="thin", color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def write_excel(rows, team_tag, n_games, out_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{team_tag.upper()} Map VODs"
    ws.sheet_view.showGridLines = False

    header_font  = Font(name="Calibri", bold=True, color=TEXT_COLOR, size=11)
    label_font   = Font(name="Calibri", bold=True, color=TEXT_COLOR, size=10)
    data_font    = Font(name="Calibri", color=TEXT_COLOR, size=10)
    link_font    = Font(name="Calibri", color=LINK_COLOR, size=10, underline="single")
    muted_font   = Font(name="Calibri", color=MUTED_COLOR, size=9, italic=True)
    map_font     = Font(name="Calibri", bold=True, color="FFFFFF", size=11)

    center  = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left    = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    vcenter = Alignment(horizontal="center", vertical="center")

    border = make_border()

    # ── column layout ─────────────────────────────────────────────────────────
    # A: Map  | B: Game# | C: Date | D: Opponent | E: VOD Link | F: Timestamp
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 8
    ws.column_dimensions["C"].width = 13
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 50
    ws.column_dimensions["F"].width = 16

    # ── title row ─────────────────────────────────────────────────────────────
    ws.merge_cells("A1:F1")
    tc = ws["A1"]
    tc.value = f"{team_tag.upper()} — Last {n_games} VODs per Map"
    tc.font  = Font(name="Calibri", bold=True, color="FFFFFF", size=14)
    tc.fill  = hex_fill(HEADER_BG)
    tc.alignment = center
    ws.row_dimensions[1].height = 28

    # ── column headers ────────────────────────────────────────────────────────
    headers = ["Map", "Game", "Date", "Opponent", "VOD (Twitch)", "Timestamp"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font      = header_font
        cell.fill      = hex_fill(HEADER_BG)
        cell.alignment = center
        cell.border    = border
    ws.row_dimensions[2].height = 20

    # ── data rows ─────────────────────────────────────────────────────────────
    excel_row = 3
    for map_name, game_entries in rows:
        map_color = MAP_COLORS.get(map_name, DEFAULT_COLOR)
        n = len(game_entries)

        # merge Map cell vertically across all games for this map
        if n > 1:
            ws.merge_cells(
                start_row=excel_row, start_column=1,
                end_row=excel_row + n - 1, end_column=1
            )
        map_cell = ws.cell(row=excel_row, column=1, value=map_name)
        map_cell.font      = map_font
        map_cell.fill      = hex_fill(map_color)
        map_cell.alignment = center
        map_cell.border    = border

        for g_idx, entry in enumerate(game_entries):
            row_fill = hex_fill(ROW_BG_EVEN if g_idx % 2 == 0 else ROW_BG_ODD)
            ws.row_dimensions[excel_row].height = 22

            game_cell = ws.cell(row=excel_row, column=2, value=f"Game {g_idx + 1}")
            game_cell.font      = label_font
            game_cell.fill      = row_fill
            game_cell.alignment = vcenter
            game_cell.border    = border

            date_cell = ws.cell(row=excel_row, column=3, value=entry.get("date", ""))
            date_cell.font      = data_font
            date_cell.fill      = row_fill
            date_cell.alignment = center
            date_cell.border    = border

            opp_cell = ws.cell(row=excel_row, column=4, value=entry.get("opp", ""))
            opp_cell.font      = data_font
            opp_cell.fill      = row_fill
            opp_cell.alignment = center
            opp_cell.border    = border

            vod_url = entry.get("vod_url")
            ts_str  = entry.get("timestamp")

            if vod_url:
                full_url = vod_url + (f"?t={ts_str}" if ts_str else "")
                vod_cell = ws.cell(row=excel_row, column=5, value=full_url)
                vod_cell.hyperlink = full_url
                vod_cell.font      = link_font
                vod_cell.fill      = row_fill
                vod_cell.alignment = left
                vod_cell.border    = border
            else:
                vod_cell = ws.cell(row=excel_row, column=5, value="VOD not found")
                vod_cell.font      = muted_font
                vod_cell.fill      = row_fill
                vod_cell.alignment = center
                vod_cell.border    = border

            ts_cell = ws.cell(row=excel_row, column=6, value=ts_str if ts_str else "—")
            ts_cell.font      = data_font if ts_str else muted_font
            ts_cell.fill      = row_fill
            ts_cell.alignment = center
            ts_cell.border    = border

            excel_row += 1

    # freeze header rows
    ws.freeze_panes = "A3"

    wb.save(out_path)
    print(f"\nSaved: {out_path}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team",  required=True, choices=list(TEAM_CONFIG.keys()))
    parser.add_argument("--maps",  nargs="+", required=True, help="Maps to include")
    parser.add_argument("--games", type=int, default=2, help="Games per map (default: 2)")
    args = parser.parse_args()

    cfg         = TEAM_CONFIG[args.team]
    team_names  = cfg["names"]
    team_kw     = cfg["vlr_kw"]
    team_vlr_id = cfg["vlr_id"]
    jsonl_path  = JSONL_DIR / cfg["jsonl"]
    prefix      = cfg["prefix"]
    target_maps = args.maps
    n_games     = args.games

    print(f"Team: {args.team.upper()}  Maps: {target_maps}  Games/map: {n_games}")

    print("\n[1/5] Loading JSONL...")
    map_games = load_map_games(jsonl_path, prefix, target_maps, n_games)
    for m, games in map_games.items():
        for g in games:
            print(f"  {m}: {g['date']} vs {g['opp']}")

    unique_series = {}
    for m, games in map_games.items():
        for g in games:
            key = (g["date"], g["opp"])
            unique_series.setdefault(key, set()).add(m)

    print(f"\n[2/5] Fetching Twitch VODs ({len(CHANNELS)} channels)...")
    vods_by_channel = fetch_vods_batch(CHANNELS)
    for ch, vods in vods_by_channel.items():
        print(f"  {ch}: {len(vods)} VODs")

    print("\n[3/5] Loading VLR match links...")
    team_links, event_links = load_vlr_links(team_vlr_id, VLR_EVENT_ID, VLR_EVENT_SLUG)
    print(f"  Team profile: {len(team_links)} links | Event page: {len(event_links)} links")

    print("\n[4/5] Resolving VODs + timestamps per series...")
    series_resolved = {}

    for (date, opp) in sorted(unique_series.keys()):
        print(f"  {date} vs {opp}")

        result = best_vod(date, opp, team_names, vods_by_channel)
        if not result:
            print(f"    no VOD found")
            series_resolved[(date, opp)] = {"vod_url": None, "timestamps": {}}
            continue

        _, ch, vod = result
        vod_id  = vod["id"]
        vod_url = f"https://www.twitch.tv/videos/{vod_id}"
        print(f"    VOD [{ch}]: {vod_url}")

        opp_cfg = cfg_for_opp_tag(opp)
        opp_kw  = opp_cfg["vlr_kw"] if opp_cfg else opp.lower()
        vlr_url = find_vlr_url(opp_kw, team_kw, team_links, event_links)

        timestamps = {}
        if vlr_url:
            print(f"    VLR: {vlr_url.split('vlr.gg')[1]}")
            yt_pairs   = get_yt_pairs(vlr_url)
            play_order = map_play_order(jsonl_path, prefix, date, opp)
            for idx, (yt_id, yt_off) in enumerate(yt_pairs):
                if idx >= len(play_order):
                    break
                map_name = play_order[idx]
                yt_start = get_yt_start(yt_id)
                if yt_start:
                    offset_s = compute_twitch_offset(yt_start, yt_off, vod["createdAt"])
                    timestamps[map_name] = fmt_ts(offset_s)
                    print(f"    {map_name}: {timestamps[map_name]}")
        else:
            print(f"    VLR match page not found (opp_kw={opp_kw})")

        series_resolved[(date, opp)] = {"vod_url": vod_url, "timestamps": timestamps}

    print("\n[5/5] Building Excel...")
    rows = []
    for map_name in target_maps:
        games = map_games.get(map_name, [])
        game_entries = []
        for g in games:
            key  = (g["date"], g["opp"])
            info = series_resolved.get(key, {})
            game_entries.append({
                "date":      g["date"],
                "opp":       g["opp"],
                "vod_url":   info.get("vod_url"),
                "timestamp": info.get("timestamps", {}).get(map_name),
            })
        rows.append((map_name, game_entries))

    OUT_DIR.mkdir(exist_ok=True)
    maps_slug = "_".join(m[:3].lower() for m in target_maps)
    out_path  = OUT_DIR / f"{args.team}_{maps_slug}_vods_g{n_games}.xlsx"
    write_excel(rows, args.team, n_games, out_path)


if __name__ == "__main__":
    main()
