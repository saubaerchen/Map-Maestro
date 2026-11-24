from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round


TEAM_NAME = "Eintracht Frankfurt"
TEAM_PREFIXES = ("SGE ",)
TARGET_MAP = "Lotus"
SITE_ORDER = ("A", "B", "C")
API_BASE = "https://api.valolytics.gg"

API_KEY_FILE = ROOT / "API_REFERENCE.md"
INPUT_SAMPLE_JSON = ROOT / "data" / "analysis" / "sge_lotus_ct_early_team_positioning_last3.json"
INPUT_RAW_JSONL = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
MAP_ASSET = ROOT / "maps" / "Lotus.png"

OUTPUT_JSON = ROOT / "data" / "analysis" / "sge_lotus_ct_retake_positions_last3.json"
OUTPUT_PNG = ROOT / "sge_lotus_ct_retake_positions_last3.png"

LOTUS_TRANSFORM = {
    "xMultiplier": 7.2e-05,
    "yMultiplier": -7.2e-05,
    "xScalarToAdd": 0.454789,
    "yScalarToAdd": 0.917752,
}

DOT_COLORS = [
    "#e53935",  # red
    "#f1d500",  # yellow
    "#76d7ff",  # cyan
    "#111111",  # black
    "#1f4fd6",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#9467bd",  # purple
]


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return match.group(1)


def api_get_json(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def clean_player_name(game_name: str) -> str:
    for prefix in TEAM_PREFIXES:
        if game_name.startswith(prefix):
            return game_name[len(prefix) :]
    return game_name


def detect_team_context(match_obj: dict) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(TEAM_PREFIXES):
            team_id = player.get("teamId")
            break
    if team_id is None:
        return None

    team_players = []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)

    return {
        "teamId": team_id,
        "teamPlayers": team_players,
    }


def normalize_lotus_xy(x: float, y: float) -> tuple[float, float]:
    norm_x = (y * LOTUS_TRANSFORM["xMultiplier"] + LOTUS_TRANSFORM["xScalarToAdd"]) * 100
    norm_y = (x * LOTUS_TRANSFORM["yMultiplier"] + LOTUS_TRANSFORM["yScalarToAdd"]) * 100
    return norm_x, norm_y


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                r"C:\Windows\Fonts\arialbd.ttf",
                r"C:\Windows\Fonts\segoeuib.ttf",
                r"C:\Windows\Fonts\bahnschrift.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\segoeui.ttf",
                r"C:\Windows\Fonts\bahnschrift.ttf",
            ]
        )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_selected_maps() -> list[dict]:
    if not INPUT_SAMPLE_JSON.exists():
        raise RuntimeError(f"Missing sample file: {INPUT_SAMPLE_JSON}")
    payload = json.loads(INPUT_SAMPLE_JSON.read_text(encoding="utf-8"))
    selected = payload.get("selectedMaps", [])
    if not selected:
        raise RuntimeError("No selectedMaps found in lotus sample JSON.")
    return selected


def build_dataset() -> dict:
    api_key = load_api_key()
    selected_maps = load_selected_maps()
    selected_by_match_id = {row.get("matchId"): row for row in selected_maps if row.get("matchId")}
    if not selected_by_match_id:
        raise RuntimeError("No valid matchIds in selectedMaps.")

    raw_matches = load_jsonl(INPUT_RAW_JSONL)
    matches_by_id = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in raw_matches
        if match.get("matchInfo", {}).get("matchId")
    }
    missing_ids = [match_id for match_id in selected_by_match_id if match_id not in matches_by_id]
    for match_id in missing_ids:
        try:
            matches_by_id[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
        except (urllib.error.HTTPError, urllib.error.URLError):
            continue

    points_by_site: dict[str, list[dict]] = {site: [] for site in SITE_ORDER}
    rounds_by_site: dict[str, set[str]] = {site: set() for site in SITE_ORDER}

    for match_id, sample in selected_by_match_id.items():
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            continue
        map_name = str(match_obj.get("matchInfo", {}).get("map", "")).split("/")[-1]
        if map_name != TARGET_MAP:
            continue

        context = detect_team_context(match_obj)
        if context is None:
            continue

        team_puuids = {p.get("puuid") for p in context["teamPlayers"] if p.get("puuid")}
        puuid_to_name = {p.get("puuid"): clean_player_name(p.get("gameName", "")) for p in context["teamPlayers"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            if sides.get(round_num) != "def":
                continue

            planter = rr.get("bombPlanter")
            if not planter or planter in team_puuids:
                continue

            site = str(rr.get("plantSite") or "").upper()
            if site not in SITE_ORDER:
                continue

            plant_snapshot = rr.get("plantPlayerLocations") or []
            if not plant_snapshot:
                continue

            round_key = f"{match_id}|{round_num}"
            round_has_point = False
            for entry in plant_snapshot:
                puuid = entry.get("puuid")
                if puuid not in team_puuids:
                    continue
                location = entry.get("location") or {}
                x = location.get("x")
                y = location.get("y")
                if x is None or y is None:
                    continue

                norm_x, norm_y = normalize_lotus_xy(x, y)
                points_by_site[site].append(
                    {
                        "site": site,
                        "player": puuid_to_name.get(puuid, puuid),
                        "puuid": puuid,
                        "x": x,
                        "y": y,
                        "normX": norm_x,
                        "normY": norm_y,
                        "roundNum": round_num,
                        "plantRoundTimeMs": rr.get("plantRoundTime"),
                        "date": sample.get("date"),
                        "opponent": sample.get("opponent"),
                        "matchId": match_id,
                        "score": sample.get("score"),
                    }
                )
                round_has_point = True

            if round_has_point:
                rounds_by_site[site].add(round_key)

    player_counts = Counter(point["player"] for site in SITE_ORDER for point in points_by_site[site])
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {player: DOT_COLORS[idx % len(DOT_COLORS)] for idx, player in enumerate(ordered_players)}

    sites_payload = {}
    for site in SITE_ORDER:
        sites_payload[site] = {
            "roundCount": len(rounds_by_site[site]),
            "pointCount": len(points_by_site[site]),
            "points": points_by_site[site],
        }

    return {
        "team": TEAM_NAME,
        "name": TEAM_NAME,
        "map": TARGET_MAP,
        "side": "ct",
        "sampleSize": len(selected_maps),
        "selectedMaps": selected_maps,
        "sites": sites_payload,
        "legend": [{"player": player, "color": color_by_player[player]} for player in ordered_players],
    }


def build_visual(dataset: dict) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    if not MAP_ASSET.exists():
        raise RuntimeError(f"Map asset not found: {MAP_ASSET}")

    map_img = Image.open(MAP_ASSET).convert("RGBA")
    gray = ImageOps.grayscale(map_img)
    map_img = ImageOps.colorize(gray, black="#6f6f6f", white="#f0f0f0").convert("RGBA")

    canvas_w, canvas_h = 1980, 760
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(40, bold=True)
    sub_font = load_font(21, bold=False)
    panel_title_font = load_font(25, bold=True)
    legend_font = load_font(17, bold=False)

    draw.rectangle([0, 0, canvas_w, 36], fill=(78, 78, 78, 255))
    draw.text((12, 2), "Defensive retake team positioning (spike planted)", fill=(255, 255, 255, 255), font=load_font(34, bold=True))

    draw.text(
        (24, 54),
        f"{TEAM_NAME} - last {len(dataset['selectedMaps'])} {TARGET_MAP} maps",
        fill=(30, 30, 30, 255),
        font=title_font,
    )
    map_line = " | ".join([f"{row['date']} vs {row['opponent']} ({row['score']})" for row in dataset["selectedMaps"]])
    draw.text((24, 105), map_line, fill=(70, 70, 70, 255), font=sub_font)

    margin_x = 24
    panel_top = 150
    panel_gap = 18
    panel_w = (canvas_w - margin_x * 2 - panel_gap * 2) // 3
    panel_h = 560

    map_w = panel_w - 160
    map_h = int(map_w * 772 / 1318)
    map_y = panel_top + 72

    legend_items = dataset["legend"]
    legend_lookup = {item["player"]: item["color"] for item in legend_items}

    for idx, site in enumerate(SITE_ORDER):
        left = margin_x + idx * (panel_w + panel_gap)
        right = left + panel_w
        draw.rectangle([left, panel_top, right, panel_top + panel_h], outline=(190, 190, 190, 255), width=1)

        panel_title = f"Retake Site {site} (plant snapshot)"
        draw.text((left + 14, panel_top + 16), panel_title, fill=(40, 40, 40, 255), font=panel_title_font)

        points = dataset["sites"][site]["points"]
        round_count = dataset["sites"][site]["roundCount"]
        draw.text(
            (left + 14, panel_top + 46),
            f"Rounds: {round_count} | Points: {len(points)}",
            fill=(90, 90, 90, 255),
            font=legend_font,
        )

        map_x = left + 14
        panel_map = map_img.resize((map_w, map_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(panel_map, (map_x, map_y))

        for point in points:
            px = int(map_x + (point["normX"] / 100.0) * map_w)
            py = int(map_y + (point["normY"] / 100.0) * map_h)
            color = legend_lookup.get(point["player"], "#333333")
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=color, outline=(255, 255, 255, 255), width=1)

        legend_x = map_x + map_w + 16
        legend_y = map_y + 10
        draw.rectangle(
            [legend_x - 8, legend_y - 8, right - 12, legend_y + 24 + len(legend_items) * 24],
            outline=(200, 200, 200, 255),
            width=1,
        )
        draw.text((legend_x, legend_y), "Players", fill=(35, 35, 35, 255), font=legend_font)
        for j, item in enumerate(legend_items):
            y = legend_y + 24 + j * 22
            draw.ellipse([legend_x, y + 5, legend_x + 8, y + 13], fill=item["color"], outline=(255, 255, 255, 255), width=1)
            draw.text((legend_x + 16, y), item["player"], fill=(45, 45, 45, 255), font=legend_font)

    canvas.convert("RGB").save(OUTPUT_PNG, format="PNG", optimize=True)


def main() -> None:
    dataset = build_dataset()
    build_visual(dataset)
    print(f"Saved JSON: {OUTPUT_JSON}")
    print(f"Saved PNG : {OUTPUT_PNG}")
    print(json.dumps({"selectedMaps": dataset["selectedMaps"]}, indent=2))


if __name__ == "__main__":
    main()
