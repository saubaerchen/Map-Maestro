from __future__ import annotations

import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "haven_asset_comparison.png"

LOCAL_HAVEN = ROOT / "maps" / "Haven.png"
RIOT_HAVEN = "https://media.valorant-api.com/maps/2bee0dc9-4ffe-519b-1cbd-7fbe763a6047/displayicon.png"
LIQUIPEDIA_HAVEN = "https://liquipedia.net/commons/images/7/73/Haven_Map.png"

# Raw Riot/Valolytics-transformed Haven points currently in the dataset.
RAW_POINTS = [
    {"label": "1", "x": 53.03500000000001, "y": 12.320300000000007},
    {"label": "2", "x": 39.1225, "y": 88.5503},
    {"label": "3", "x": 43.92250000000001, "y": 52.30279999999999},
    {"label": "4", "x": 35.072500000000005, "y": 83.5478},
]


def fetch_image(url: str) -> Image.Image:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return Image.open(io.BytesIO(data)).convert("RGBA")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        ROOT / "stitch" / "fonts" / "Inter-Bold.ttf" if bold else ROOT / "stitch" / "fonts" / "Inter-Regular.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def fit_image(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (11, 16, 20, 255))
    source = img.copy()
    source.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - source.width) // 2
    y = (size[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


def plot_points(base: Image.Image, points: list[dict]) -> Image.Image:
    img = base.copy()
    draw = ImageDraw.Draw(img)
    label_font = load_font(28, bold=True)
    for point in points:
        px = int((point["x"] / 100) * img.width)
        py = int((point["y"] / 100) * img.height)
        glow = 34
        draw.ellipse((px - glow, py - glow, px + glow, py + glow), fill=(255, 70, 70, 58))
        r = 9
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(184, 22, 22, 255), outline=(255, 255, 255, 235), width=3)
        tx, ty, tx2, ty2 = draw.textbbox((0, 0), point["label"], font=label_font)
        tw = tx2 - tx
        th = ty2 - ty
        lx = px - tw // 2
        ly = py - 46 - th // 2
        draw.rounded_rectangle((lx - 8, ly - 4, lx + tw + 8, ly + th + 4), radius=8, fill=(8, 12, 16, 228), outline=(255, 255, 255, 200), width=1)
        draw.text((lx, ly), point["label"], fill=(255, 255, 255, 255), font=label_font)
    return img


def build_panel(title: str, subtitle: str, image: Image.Image, size: tuple[int, int]) -> Image.Image:
    pad = 24
    title_font = load_font(34, bold=True)
    sub_font = load_font(20, bold=False)
    header_h = 96
    panel = Image.new("RGBA", (size[0] + pad * 2, size[1] + header_h + pad * 2), (255, 255, 255, 255))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=0, outline=(15, 18, 20, 70), width=1)
    draw.text((pad, pad - 2), title, fill=(17, 22, 26, 255), font=title_font)
    draw.text((pad, pad + 44), subtitle, fill=(89, 98, 105, 255), font=sub_font)
    panel.alpha_composite(image, (pad, header_h))
    return panel


def main() -> None:
    local_img = Image.open(LOCAL_HAVEN).convert("RGBA")
    riot_img = fetch_image(RIOT_HAVEN)
    liqui_img = fetch_image(LIQUIPEDIA_HAVEN)

    target_size = (780, 457)
    candidates = [
        ("Current local Haven.png", f"{local_img.width}x{local_img.height}", local_img),
        ("Riot displayIcon", f"{riot_img.width}x{riot_img.height}", riot_img),
        ("Liquipedia Haven_Map", f"{liqui_img.width}x{liqui_img.height}", liqui_img),
    ]

    panels = []
    for title, subtitle, img in candidates:
        fitted = fit_image(img, target_size)
        plotted = plot_points(fitted, RAW_POINTS)
        panels.append(build_panel(title, subtitle, plotted, target_size))

    title_font = load_font(48, bold=True)
    sub_font = load_font(22, bold=False)
    legend_font = load_font(20, bold=False)

    gap = 24
    header_h = 150
    footer_h = 92
    width = max(panel.width for panel in panels) * len(panels) + gap * (len(panels) - 1) + 48
    height = header_h + max(panel.height for panel in panels) + footer_h
    sheet = Image.new("RGBA", (width, height), (247, 249, 250, 255))
    draw = ImageDraw.Draw(sheet)

    draw.text((24, 20), "Haven Asset Comparison", fill=(17, 22, 26, 255), font=title_font)
    draw.text((24, 76), "Same 4 Dortmund CT Operator first-kill points plotted on each candidate asset.", fill=(84, 92, 98, 255), font=sub_font)
    draw.text((24, 108), "Labels reflect your manual callout intent: 1=C Long, 2=Attacker Spawn, 3=A Long, 4=C Garage.", fill=(84, 92, 98, 255), font=legend_font)

    x = 24
    y = header_h
    for panel in panels:
      sheet.alpha_composite(panel, (x, y))
      x += panel.width + gap

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
