from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "data" / "analysis" / "sge_lotus_defensive_early_team_positioning_last3.json"
OUTPUT_PNG = ROOT / "sge_lotus_random_round_samples.png"
OUTPUT_JSON = ROOT / "data" / "analysis" / "sge_lotus_random_round_samples.json"
MAP_ASSET = ROOT / "maps" / "Lotus.png"
PANEL_COUNT = 3
RANDOM_SEED = 20260413


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


def group_points_by_round(points: list[dict]) -> dict[tuple, list[dict]]:
    grouped: dict[tuple, list[dict]] = {}
    for point in points:
        key = (
            point["matchId"],
            int(point["roundNum"]),
            point["date"],
            point["opponent"],
            point["score"],
            int(point["firstKillTimeMs"]),
        )
        grouped.setdefault(key, []).append(point)
    return grouped


def main() -> None:
    if not INPUT_JSON.exists():
        raise RuntimeError(f"Missing input dataset: {INPUT_JSON}")
    if not MAP_ASSET.exists():
        raise RuntimeError(f"Missing map asset: {MAP_ASSET}")

    dataset = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    points = dataset["thresholds"]["lt30s"]["points"]
    grouped = group_points_by_round(points)
    keys = list(grouped.keys())
    if len(keys) < PANEL_COUNT:
        raise RuntimeError(f"Not enough rounds in dataset. Found {len(keys)}.")

    random.seed(RANDOM_SEED)
    sampled_keys = random.sample(keys, PANEL_COUNT)

    legend_lookup = {row["player"]: row["color"] for row in dataset.get("legend", [])}

    base_map = Image.open(MAP_ASSET).convert("RGBA")
    bbox = detect_playable_bbox(base_map)
    gray = ImageOps.grayscale(base_map)
    map_img = ImageOps.colorize(gray, black="#6f6f6f", white="#f0f0f0").convert("RGBA")

    canvas_w, canvas_h = 1980, 760
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(canvas)

    draw.rectangle([0, 0, canvas_w, 36], fill=(78, 78, 78, 255))
    draw.text((12, 2), "SGE Lotus - random round verification samples", fill=(255, 255, 255, 255), font=load_font(34, bold=True))
    draw.text((24, 54), f"Seed {RANDOM_SEED} | Source: <30s defensive FK rounds", fill=(65, 65, 65, 255), font=load_font(22))

    margin_x = 24
    panel_top = 100
    panel_gap = 18
    panel_w = (canvas_w - margin_x * 2 - panel_gap * 2) // PANEL_COUNT
    panel_h = 620

    map_w = panel_w - 30
    map_h = int(map_w * 772 / 1318)
    title_font = load_font(18, bold=True)
    info_font = load_font(17, bold=False)

    selected_rounds = []
    for idx, key in enumerate(sampled_keys):
        match_id, round_num, date, opp, score, fk_ms = key
        round_points = grouped[key]
        selected_rounds.append(
            {
                "matchId": match_id,
                "roundNum": round_num,
                "date": date,
                "opponent": opp,
                "score": score,
                "firstKillTimeMs": fk_ms,
                "playersInSnapshot": [p["player"] for p in round_points],
            }
        )

        left = margin_x + idx * (panel_w + panel_gap)
        right = left + panel_w
        draw.rectangle([left, panel_top, right, panel_top + panel_h], outline=(190, 190, 190, 255), width=1)

        draw.text((left + 12, panel_top + 12), f"{date} vs {opp} ({score})", fill=(30, 30, 30, 255), font=title_font)
        draw.text((left + 12, panel_top + 38), f"Match: {match_id[:8]}... | Round {round_num} | FK {fk_ms/1000:.2f}s", fill=(70, 70, 70, 255), font=info_font)

        map_x = left + 12
        map_y = panel_top + 72
        panel_map = map_img.resize((map_w, map_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(panel_map, (map_x, map_y))

        src_x0, src_y0, src_x1, src_y1 = bbox
        box_x0 = map_x + (src_x0 / map_img.width) * map_w
        box_x1 = map_x + (src_x1 / map_img.width) * map_w
        box_y0 = map_y + (src_y0 / map_img.height) * map_h
        box_y1 = map_y + (src_y1 / map_img.height) * map_h

        for point in round_points:
            px = int(box_x0 + (point["normX"] / 100.0) * (box_x1 - box_x0))
            py = int(box_y0 + (point["normY"] / 100.0) * (box_y1 - box_y0))
            color = legend_lookup.get(point["player"], "#333333")
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=color, outline=(255, 255, 255, 255), width=1)

        names = sorted({p["player"] for p in round_points})
        name_y = map_y + map_h + 10
        draw.text((left + 12, name_y), "Players:", fill=(45, 45, 45, 255), font=title_font)
        for j, name in enumerate(names):
            y = name_y + 24 + j * 22
            color = legend_lookup.get(name, "#333333")
            draw.ellipse([left + 12, y + 4, left + 20, y + 12], fill=color, outline=(255, 255, 255, 255), width=1)
            draw.text((left + 28, y), name, fill=(45, 45, 45, 255), font=info_font)

    canvas.convert("RGB").save(OUTPUT_PNG, format="PNG", optimize=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps({"seed": RANDOM_SEED, "rounds": selected_rounds}, indent=2), encoding="utf-8")

    print(f"Saved PNG : {OUTPUT_PNG}")
    print(f"Saved JSON: {OUTPUT_JSON}")
    print(json.dumps({"seed": RANDOM_SEED, "rounds": selected_rounds}, indent=2))


if __name__ == "__main__":
    main()

