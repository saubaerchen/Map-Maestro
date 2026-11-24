from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.stats_engine import get_team_side_per_round


API_BASE = "https://api.valolytics.gg"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
OUTPUT_DIR = ROOT / "data" / "analysis"
OUTPUT_JSON = OUTPUT_DIR / "sge_bind_offensive_early_team_positioning_last3.json"
OUTPUT_PNG = ROOT / "sge_bind_offensive_early_team_positioning_last3.png"

TIMEZONE = ZoneInfo("Europe/Berlin") if ZoneInfo else dt.timezone.utc
TEAM_NAME = "Eintracht Frankfurt"
TEAM_PREFIXES = ("SGE ",)
LOCAL_SEED_FILES = (
    ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl",
    ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl",
)
TARGET_MAP = "Bind"
BIND_TRANSFORM = {
    "xMultiplier": 5.9e-05,
    "yMultiplier": -5.9e-05,
    "xScalarToAdd": 0.576941,
    "yScalarToAdd": 0.967566,
}
HISTORY_MATCH_LIMIT = 18
TARGET_MAP_COUNT = 3
THRESHOLDS_SEC = (10, 20, 30)
DOT_COLORS = [
    "#e53935",
    "#f1d500",
    "#76d7ff",
    "#111111",
    "#1f4fd6",
    "#ff7f0e",
    "#2ca02c",
    "#9467bd",
]
MAP_ASSET = ROOT / "maps" / "Bind.png"


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


def discover_reference_players() -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for path in LOCAL_SEED_FILES:
        for match in load_jsonl(path):
            for player in match.get("players", []):
                if player.get("isObserver"):
                    continue
                game_name = player.get("gameName", "")
                if not game_name.startswith(TEAM_PREFIXES):
                    continue
                puuid = player.get("puuid")
                if not puuid or puuid in seen:
                    continue
                seen.add(puuid)
                found.append(
                    {
                        "puuid": puuid,
                        "gameName": game_name,
                        "tagLine": player.get("tagLine", ""),
                    }
                )
    if not found:
        raise RuntimeError("Could not find SGE players in local seed files.")
    return found


def local_dt_from_ms(ts_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=TIMEZONE)


def player_prefix(name: str) -> str:
    return name.split(" ")[0] if " " in name else name


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
    opp_players = []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)
        else:
            opp_players.append(player)

    opp_prefix = Counter(player_prefix(p.get("gameName", "")) for p in opp_players).most_common(1)[0][0]
    return {
        "teamId": team_id,
        "teamPlayers": team_players,
        "oppPrefix": opp_prefix,
    }


def match_score(match_obj: dict, team_id: str) -> str:
    team_score = 0
    opp_score = 0
    for team in match_obj.get("teams", []):
        if team.get("teamId") == team_id:
            team_score = team.get("roundsWon", 0)
        else:
            opp_score = team.get("roundsWon", 0)
    return f"{team_score}-{opp_score}"


def collect_first_kill(round_result: dict) -> dict | None:
    first = None
    for player_stats in round_result.get("playerStats", []):
        for kill in player_stats.get("kills", []):
            ts = kill.get("timeSinceRoundStartMillis")
            if ts is None:
                continue
            if first is None or ts < first.get("timeSinceRoundStartMillis", 10**9):
                first = kill
    return first


def normalize_bind_xy(x: float, y: float) -> tuple[float, float]:
    norm_x = (y * BIND_TRANSFORM["xMultiplier"] + BIND_TRANSFORM["xScalarToAdd"]) * 100
    norm_y = (x * BIND_TRANSFORM["yMultiplier"] + BIND_TRANSFORM["yScalarToAdd"]) * 100
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


def detect_playable_bbox(map_image: Image.Image) -> tuple[int, int, int, int]:
    arr = np.array(map_image.convert("RGB"))
    bg = arr[0, 0].astype(np.int32)
    dist = np.sqrt(((arr.astype(np.int32) - bg) ** 2).sum(axis=2))
    mask = dist > 10
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (0, 0, map_image.width - 1, map_image.height - 1)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def build_playable_mask(map_image: Image.Image) -> np.ndarray:
    arr = np.array(map_image.convert("RGB"))
    bg = arr[0, 0].astype(np.int32)
    dist = np.sqrt(((arr.astype(np.int32) - bg) ** 2).sum(axis=2))
    return dist > 10


def snap_to_mask(px: int, py: int, mask: np.ndarray, mask_coords: np.ndarray) -> tuple[int, int]:
    h, w = mask.shape
    px = min(max(px, 0), w - 1)
    py = min(max(py, 0), h - 1)
    if mask[py, px]:
        return px, py
    if mask_coords.size == 0:
        return px, py
    deltas_x = mask_coords[:, 1] - px
    deltas_y = mask_coords[:, 0] - py
    idx = np.argmin(deltas_x * deltas_x + deltas_y * deltas_y)
    return int(mask_coords[idx, 1]), int(mask_coords[idx, 0])


def build_dataset(api_key: str) -> dict:
    reference_players = discover_reference_players()
    players_by_puuid = {player["puuid"]: player for player in reference_players}
    processed: set[str] = set()
    fetched_matches: dict[str, dict] = {}
    match_times: dict[str, int] = {}

    while True:
        pending = [player for puuid, player in players_by_puuid.items() if puuid not in processed]
        if not pending:
            break
        for player in pending:
            processed.add(player["puuid"])
            try:
                history = api_get_json(f"/api/riot/match/v1/matchlists/by-puuid/esports/{player['puuid']}", api_key)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
            for item in history.get("history", [])[:HISTORY_MATCH_LIMIT]:
                match_id = item["matchId"]
                ts = item.get("gameStartTimeMillis", 0)
                if ts > match_times.get(match_id, 0):
                    match_times[match_id] = ts
                if match_id not in fetched_matches:
                    try:
                        fetched_matches[match_id] = api_get_json(f"/api/matches/esports/{match_id}", api_key)
                    except urllib.error.HTTPError as exc:
                        if exc.code == 404:
                            continue
                        raise
                    except urllib.error.URLError:
                        continue
                context = detect_team_context(fetched_matches[match_id])
                if context is None:
                    continue
                for team_player in context["teamPlayers"]:
                    puuid = team_player.get("puuid")
                    if puuid and puuid not in players_by_puuid:
                        players_by_puuid[puuid] = {
                            "puuid": puuid,
                            "gameName": team_player.get("gameName", ""),
                            "tagLine": team_player.get("tagLine", ""),
                        }

    bind_matches: list[tuple[int, dict, dict]] = []
    for match_id, ts in sorted(match_times.items(), key=lambda item: item[1], reverse=True):
        match_obj = fetched_matches.get(match_id)
        if not match_obj:
            continue
        context = detect_team_context(match_obj)
        if context is None:
            continue
        map_name = match_obj.get("matchInfo", {}).get("map", "").split("/")[-1]
        if map_name != TARGET_MAP:
            continue
        bind_matches.append((ts, match_obj, context))

    selected = bind_matches[:TARGET_MAP_COUNT]
    if not selected:
        raise RuntimeError("No Bind maps found for Eintracht Frankfurt.")

    points_by_threshold: dict[int, list[dict]] = {sec: [] for sec in THRESHOLDS_SEC}
    rounds_by_threshold: dict[int, set[str]] = {sec: set() for sec in THRESHOLDS_SEC}
    selected_maps = []

    for ts, match_obj, context in selected:
        team_puuids = {p["puuid"] for p in context["teamPlayers"]}
        puuid_to_name = {p["puuid"]: clean_player_name(p.get("gameName", "")) for p in context["teamPlayers"]}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)
        date_str = local_dt_from_ms(ts).strftime("%Y-%m-%d")
        match_id = match_obj.get("matchInfo", {}).get("matchId", "")
        score = match_score(match_obj, context["teamId"])
        opponent = context["oppPrefix"]

        selected_maps.append(
            {
                "date": date_str,
                "opponent": opponent,
                "matchId": match_id,
                "score": score,
            }
        )

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            first_kill = collect_first_kill(rr)
            if not first_kill:
                continue
            time_ms = first_kill.get("timeSinceRoundStartMillis")
            if time_ms is None:
                continue
            if sides.get(round_num) != "atk":
                continue
            if time_ms >= THRESHOLDS_SEC[-1] * 1000:
                continue

            killer_puuid = first_kill.get("killer")
            killer_team_id = first_kill.get("killerTeamId")
            if killer_puuid:
                fk_owner = "team" if killer_puuid in team_puuids else "enemy"
            elif killer_team_id is not None:
                fk_owner = "team" if killer_team_id == context["teamId"] else "enemy"
            else:
                fk_owner = "unknown"

            snapshot = first_kill.get("playerLocations") or []
            if not snapshot:
                continue

            round_key = f"{match_id}|{round_num}"
            round_points = []
            for entry in snapshot:
                puuid = entry.get("puuid")
                if puuid not in team_puuids:
                    continue
                location = entry.get("location") or {}
                x = location.get("x")
                y = location.get("y")
                if x is None or y is None:
                    continue
                norm_x, norm_y = normalize_bind_xy(x, y)
                round_points.append(
                    {
                        "player": puuid_to_name.get(puuid, puuid),
                        "puuid": puuid,
                        "x": x,
                        "y": y,
                        "normX": norm_x,
                        "normY": norm_y,
                        "roundNum": round_num,
                        "firstKillTimeMs": time_ms,
                        "date": date_str,
                        "opponent": opponent,
                        "matchId": match_id,
                        "score": score,
                        "fkOwner": fk_owner,
                    }
                )

            if not round_points:
                continue

            for sec in THRESHOLDS_SEC:
                if time_ms < sec * 1000:
                    rounds_by_threshold[sec].add(round_key)
                    points_by_threshold[sec].extend(round_points)

    player_counts = Counter(point["player"] for point in points_by_threshold[30])
    ordered_players = [name for name, _ in player_counts.most_common()]
    color_by_player = {}
    for idx, player_name in enumerate(ordered_players):
        color_by_player[player_name] = DOT_COLORS[idx % len(DOT_COLORS)]

    thresholds_payload = {}
    for sec in THRESHOLDS_SEC:
        thresholds_payload[f"lt{sec}s"] = {
            "roundCount": len(rounds_by_threshold[sec]),
            "pointCount": len(points_by_threshold[sec]),
            "points": points_by_threshold[sec],
        }

    return {
        "team": TEAM_NAME,
        "map": TARGET_MAP,
        "selectedMaps": selected_maps,
        "thresholds": thresholds_payload,
        "legend": [{"player": player, "color": color_by_player[player]} for player in ordered_players],
    }


def build_visual(dataset: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    if not MAP_ASSET.exists():
        raise RuntimeError(f"Map asset not found: {MAP_ASSET}")

    map_img = Image.open(MAP_ASSET).convert("RGBA")
    map_bbox_src = detect_playable_bbox(map_img)
    gray = ImageOps.grayscale(map_img)
    map_img = ImageOps.colorize(gray, black="#6f6f6f", white="#f0f0f0").convert("RGBA")

    canvas_w, canvas_h = 1980, 760
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(40, bold=True)
    sub_font = load_font(21, bold=False)
    panel_title_font = load_font(22, bold=True)
    legend_font = load_font(17, bold=False)

    draw.rectangle([0, 0, canvas_w, 36], fill=(78, 78, 78, 255))
    draw.text((12, 2), "Offensive early team positioning", fill=(255, 255, 255, 255), font=load_font(36, bold=True))

    draw.text(
        (24, 54),
        f"{TEAM_NAME} - last {len(dataset['selectedMaps'])} {TARGET_MAP} maps",
        fill=(30, 30, 30, 255),
        font=title_font,
    )
    map_line = " | ".join(
        [f"{row['date']} vs {row['opponent']} ({row['score']})" for row in dataset["selectedMaps"]]
    )
    draw.text((24, 105), map_line, fill=(70, 70, 70, 255), font=sub_font)

    margin_x = 24
    panel_top = 150
    panel_gap = 18
    panel_w = (canvas_w - margin_x * 2 - panel_gap * 2) // 3
    panel_h = 560

    map_w = panel_w - 160
    map_h = int(map_w * 772 / 1318)
    map_y = panel_top + 72
    src_mask = build_playable_mask(Image.open(MAP_ASSET).convert("RGBA"))
    mask_img = Image.fromarray((src_mask.astype(np.uint8) * 255), mode="L").resize((map_w, map_h), Image.Resampling.NEAREST)
    mask_arr = np.array(mask_img) > 127
    mask_coords = np.argwhere(mask_arr)

    legend_items = dataset["legend"]
    legend_lookup = {item["player"]: item["color"] for item in legend_items}

    for idx, sec in enumerate(THRESHOLDS_SEC):
        left = margin_x + idx * (panel_w + panel_gap)
        right = left + panel_w
        draw.rectangle([left, panel_top, right, panel_top + panel_h], outline=(190, 190, 190, 255), width=1)

        key = f"lt{sec}s"
        panel_title = f"Attacking Team Positioning at the first kill (<{sec}s)"
        draw.text((left + 14, panel_top + 16), panel_title, fill=(40, 40, 40, 255), font=panel_title_font)

        points = dataset["thresholds"][key]["points"]
        round_count = dataset["thresholds"][key]["roundCount"]
        draw.text(
            (left + 14, panel_top + 46),
            f"Rounds: {round_count} | Points: {len(points)}",
            fill=(90, 90, 90, 255),
            font=legend_font,
        )

        map_x = left + 14
        panel_map = map_img.resize((map_w, map_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(panel_map, (map_x, map_y))

        src_x0, src_y0, src_x1, src_y1 = map_bbox_src
        box_x0 = map_x + (src_x0 / map_img.width) * map_w
        box_x1 = map_x + (src_x1 / map_img.width) * map_w
        box_y0 = map_y + (src_y0 / map_img.height) * map_h
        box_y1 = map_y + (src_y1 / map_img.height) * map_h

        for point in points:
            px = int(box_x0 + (point["normX"] / 100.0) * (box_x1 - box_x0))
            py = int(box_y0 + (point["normY"] / 100.0) * (box_y1 - box_y0))
            local_x = px - map_x
            local_y = py - map_y
            local_x, local_y = snap_to_mask(local_x, local_y, mask_arr, mask_coords)
            px = map_x + local_x
            py = map_y + local_y
            color = legend_lookup.get(point["player"], "#333333")
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=color, outline=(255, 255, 255, 255), width=1)

        legend_x = map_x + map_w + 16
        legend_y = map_y + 10
        draw.rectangle([legend_x - 8, legend_y - 8, right - 12, legend_y + 24 + len(legend_items) * 24], outline=(200, 200, 200, 255), width=1)
        draw.text((legend_x, legend_y), "Players", fill=(35, 35, 35, 255), font=legend_font)
        for j, item in enumerate(legend_items):
            y = legend_y + 24 + j * 22
            draw.ellipse([legend_x, y + 5, legend_x + 8, y + 13], fill=item["color"], outline=(255, 255, 255, 255), width=1)
            draw.text((legend_x + 16, y), item["player"], fill=(45, 45, 45, 255), font=legend_font)

    canvas.convert("RGB").save(OUTPUT_PNG, format="PNG", optimize=True)


def main() -> None:
    api_key = load_api_key()
    dataset = build_dataset(api_key)
    build_visual(dataset)
    print(f"Saved JSON: {OUTPUT_JSON}")
    print(f"Saved PNG : {OUTPUT_PNG}")
    print(json.dumps({"selectedMaps": dataset["selectedMaps"]}, indent=2))


if __name__ == "__main__":
    main()
