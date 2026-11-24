"""
Render Lotus map with official Valorant callouts as Voronoi regions.

Sources:
  - Map image + transform constants + callouts: https://valorant-api.com/v1/maps (cached at data/maps_api.json)
  - FK point overlay: data/analysis/sge_lotus_ct_early_team_positioning_last3.json

Output:
  - out/lotus_callouts.png  (labeled callout region map)
  - out/lotus_callouts_with_fk.png  (same + SGE CT FK-moment positions overlaid)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
MAPS_API = ROOT / "data" / "maps_api.json"
MAP_IMAGE = ROOT / "out" / "lotus_displayicon.png"
FK_JSON = ROOT / "data" / "analysis" / "sge_lotus_ct_early_team_positioning_last3.json"
OUT_DIR = ROOT / "out"


def transform_xy(x: float, y: float, xm: float, ym: float, xs: float, ys: float, w: int, h: int) -> tuple[int, int]:
    px = y * xm + xs
    py = x * ym + ys
    return int(round(px * w)), int(round(py * h))


def distinct_colors(n: int) -> list[tuple[int, int, int]]:
    import colorsys
    out = []
    for i in range(n):
        h = (i * 0.6180339887) % 1.0
        s = 0.55 + 0.15 * ((i * 7) % 3) / 2
        v = 0.95
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


def main() -> None:
    maps = json.loads(MAPS_API.read_text(encoding="utf-8"))["data"]
    lotus = next(m for m in maps if m.get("displayName") == "Lotus")
    xm = lotus["xMultiplier"]
    ym = lotus["yMultiplier"]
    xs = lotus["xScalarToAdd"]
    ys = lotus["yScalarToAdd"]
    callouts = lotus["callouts"]

    base = Image.open(MAP_IMAGE).convert("RGBA")
    W, H = base.size

    # project callouts to pixels
    anchors: list[tuple[int, int, str]] = []
    for c in callouts:
        loc = c["location"]
        px, py = transform_xy(loc["x"], loc["y"], xm, ym, xs, ys, W, H)
        label = f"{c['regionName']} / {c['superRegionName']}"
        anchors.append((px, py, label))

    anchor_pts = np.array([(a[0], a[1]) for a in anchors], dtype=np.float32)
    tree = cKDTree(anchor_pts)

    # rasterize nearest-anchor labels at every pixel
    ys_grid, xs_grid = np.mgrid[0:H, 0:W]
    query = np.stack([xs_grid.ravel(), ys_grid.ravel()], axis=1)
    _, idx = tree.query(query, k=1)
    label_map = idx.reshape(H, W).astype(np.int32)

    palette = distinct_colors(len(anchors))
    color_arr = np.zeros((H, W, 4), dtype=np.uint8)
    for i, (r, g, b) in enumerate(palette):
        mask = label_map == i
        color_arr[mask] = (r, g, b, 110)

    overlay = Image.fromarray(color_arr, mode="RGBA")
    composed = Image.alpha_composite(base, overlay)

    # draw region boundaries (where neighbors differ)
    draw = ImageDraw.Draw(composed)
    diff_h = label_map[:, 1:] != label_map[:, :-1]
    diff_v = label_map[1:, :] != label_map[:-1, :]
    border = np.zeros((H, W), dtype=bool)
    border[:, :-1] |= diff_h
    border[:-1, :] |= diff_v
    ys_b, xs_b = np.where(border)
    border_px = np.zeros((H, W, 4), dtype=np.uint8)
    border_px[ys_b, xs_b] = (0, 0, 0, 180)
    composed = Image.alpha_composite(composed, Image.fromarray(border_px, mode="RGBA"))
    draw = ImageDraw.Draw(composed)

    # font
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # draw anchor dots + labels
    for (px, py, label) in anchors:
        r = 5
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
        text = label.split(" / ")[0] + " " + label.split(" / ")[1]
        tw = draw.textlength(text, font=font_small)
        tx, ty = px + 8, py - 10
        draw.rectangle([tx - 3, ty - 2, tx + tw + 3, ty + 16], fill=(0, 0, 0, 190))
        draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font_small)

    # title strip
    title = Image.new("RGBA", (W, 56), (15, 20, 25, 235))
    tdraw = ImageDraw.Draw(title)
    tdraw.text((16, 10), "Lotus — Official Valorant API callouts (nearest-anchor regions)",
               fill=(255, 255, 255, 255), font=font)
    tdraw.text((16, 32), f"{len(anchors)} callouts · source: valorant-api.com/v1/maps",
               fill=(180, 190, 200, 255), font=font_small)
    final = Image.new("RGBA", (W, H + 56), (0, 0, 0, 255))
    final.paste(title, (0, 0))
    final.paste(composed, (0, 56))
    OUT_DIR.mkdir(exist_ok=True)
    out1 = OUT_DIR / "lotus_callouts.png"
    final.save(out1)
    print(f"wrote {out1}")

    # second image: overlay SGE CT FK-moment points and tag each with its callout
    fk = json.loads(FK_JSON.read_text(encoding="utf-8"))
    pts = fk["thresholds"]["lt10s"]["points"] + fk["thresholds"]["lt20s"]["points"] + fk["thresholds"]["lt30s"]["points"]

    composed2 = composed.copy()
    draw2 = ImageDraw.Draw(composed2)
    mapped: list[tuple[str, str]] = []
    for p in pts:
        wx, wy = p["x"], p["y"]
        px, py = transform_xy(wx, wy, xm, ym, xs, ys, W, H)
        if not (0 <= px < W and 0 <= py < H):
            continue
        aidx = label_map[py, px]
        callout_label = anchors[aidx][2]
        mapped.append((p["player"], callout_label))
        color = (255, 60, 60, 255) if p.get("fkOwner") == "enemy" else (60, 180, 255, 255)
        r = 4
        draw2.ellipse([px - r, py - r, px + r, py + r], fill=color, outline=(0, 0, 0, 255), width=1)

    final2 = Image.new("RGBA", (W, H + 56), (0, 0, 0, 255))
    t2 = Image.new("RGBA", (W, 56), (15, 20, 25, 235))
    t2d = ImageDraw.Draw(t2)
    t2d.text((16, 10), "Lotus callouts + SGE CT first-kill team positions (last 4 maps)",
             fill=(255, 255, 255, 255), font=font)
    t2d.text((16, 32), "blue = FK won by SGE   ·   red = FK lost   ·   dot = player position at FK moment",
             fill=(180, 190, 200, 255), font=font_small)
    final2.paste(t2, (0, 0))
    final2.paste(composed2, (0, 56))
    out2 = OUT_DIR / "lotus_callouts_with_fk.png"
    final2.save(out2)
    print(f"wrote {out2}")

    # summary table
    from collections import Counter
    counts = Counter(cl for _, cl in mapped)
    print(f"\nFK-moment positions mapped: {len(mapped)}")
    print("Top callouts by frequency:")
    for label, n in counts.most_common(12):
        print(f"  {n:>3}  {label}")


if __name__ == "__main__":
    main()
