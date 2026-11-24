"""
Capture a Map-Info page view as two A4 PNG files (2480x3508 each, 300 DPI).
Usage: python scripts/capture_a4.py --team eintracht --map Bind --side t
Outputs: sge_bind_t_p1_a4.png, sge_bind_t_p2_a4.png (in project root)
"""

import argparse
import io
import urllib.request
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

A4_W = 2480
A4_H = 3508
SCALE = 2          # deviceScaleFactor — viewport width = A4_W / SCALE = 1240px
VIEWPORT_W = A4_W // SCALE   # 1240px; content fills min(1480, 1200) = 1200 CSS px → 2400 screen px (97%)
LOGO_SIZE = 150
LOGO_MARGIN = 30

TEAM_FILE_PREFIX = {
    "eintracht": "sge",
    "fokus": "fks",
    "alternate": "atn",
    "dortmund": "dxg",
    "rizon": "rzn",
    "eco": "eco",
}

TEAM_LOGO_URL = {
    "eintracht": "https://owcdn.net/img/659d1013d5cf5.png",
    "fokus":     "https://owcdn.net/img/627934cd0b505.png",
    "rizon":     "https://owcdn.net/img/657eca10317fb.png",
}

SIDE_LABEL = {"ct": "ct", "t": "t"}


def download_logo(team: str) -> Image.Image:
    url = TEAM_LOGO_URL.get(team, TEAM_LOGO_URL["eintracht"])
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    return img


def take_screenshot(team: str, map_name: str, side: str) -> tuple[Image.Image, int | None]:
    """Returns (full_page_image, map_control_y) where map_control_y is the split point."""
    url = f"http://127.0.0.1:4173/#map-info/{team}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": VIEWPORT_W, "height": 900},
            device_scale_factor=SCALE,
        )
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Set state and re-render via JS
        page.evaluate(f"""
            activeSideView = '{side}';
            activeMap = '{map_name}';
            activeDefensiveMap = '{map_name}';
            render();
        """)

        # Wait for canvases to render
        page.wait_for_timeout(3000)

        # Find the y-position of the "Map Control" heading (CSS pixels — multiply by SCALE for screen pixels)
        split_y_css = page.evaluate("""
            (() => {
                const headings = document.querySelectorAll('h3.defensive-topic-title');
                for (const h of headings) {
                    if (h.textContent.trim() === 'Map Control') {
                        return h.getBoundingClientRect().top + window.scrollY;
                    }
                }
                return null;
            })()
        """)
        split_y = int(split_y_css * SCALE) if split_y_css is not None else None
        if split_y is not None:
            print(f"Map Control heading found at y={split_y_css}px CSS -> {split_y}px screen")

        screenshot_bytes = page.screenshot(full_page=True)
        browser.close()

    return Image.open(io.BytesIO(screenshot_bytes)).convert("RGB"), split_y


def composite_logo(page_img: Image.Image, logo: Image.Image, align: str = "left") -> Image.Image:
    out = page_img.copy().convert("RGBA")
    x = A4_W - LOGO_SIZE - LOGO_MARGIN if align == "right" else LOGO_MARGIN
    y = A4_H - LOGO_SIZE - LOGO_MARGIN
    out.paste(logo, (x, y), logo)
    return out.convert("RGB")


def make_a4_page(full_img: Image.Image, start_y: int, end_y: int, logo: Image.Image, fname: str, top_padding: int = 0, logo_align: str = "left"):
    crop = full_img.crop((0, start_y, A4_W, end_y))
    bg_colour = full_img.getpixel((A4_W // 2, min(start_y + 5, full_img.height - 1)))
    canvas = Image.new("RGB", (A4_W, A4_H), bg_colour)
    canvas.paste(crop, (0, top_padding))
    page = composite_logo(canvas, logo, align=logo_align)
    page.save(fname, dpi=(300, 300))
    print(f"Saved {fname}")


def split_to_a4(full_img: Image.Image, split_y: int | None, logo: Image.Image, out_prefix: str, logo_align: str = "left"):
    total_h = full_img.height

    if split_y is None:
        make_a4_page(full_img, 0, total_h, logo, f"{out_prefix}_p1_a4.png", logo_align=logo_align)
        return

    make_a4_page(full_img, 0, split_y, logo, f"{out_prefix}_p1_a4.png", logo_align=logo_align)
    make_a4_page(full_img, split_y, total_h, logo, f"{out_prefix}_p2_a4.png", top_padding=60, logo_align=logo_align)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="eintracht")
    parser.add_argument("--map", default="Bind")
    parser.add_argument("--side", default="t", choices=["ct", "t"])
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = TEAM_FILE_PREFIX.get(args.team, args.team[:3])
    out_prefix = str(out_dir / f"{prefix}_{args.map.lower()}_{args.side}")

    print(f"Downloading logo for {args.team}...")
    logo = download_logo(args.team)
    logo_align = "left"

    print(f"Capturing {args.team} / {args.map} / {args.side.upper()}...")
    full_img, split_y = take_screenshot(args.team, args.map, args.side)
    print(f"Full screenshot size: {full_img.size}")

    split_to_a4(full_img, split_y, logo, out_prefix, logo_align=logo_align)
    print("Done.")


if __name__ == "__main__":
    main()
