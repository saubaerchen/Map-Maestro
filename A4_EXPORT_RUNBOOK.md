# A4 Export Runbook

Produces two print-ready A4 PNG files (2480×3508 px, 300 DPI) from any team/map/side view on the VETO_ARCHITECT scouting site.

---

## Prerequisites

- Local server running at `http://127.0.0.1:4173/` (see `LOCALHOST_RUNBOOK.md`)
- Python packages: `playwright`, `Pillow`, `requests`

---

## Command

```powershell
python scripts/capture_a4.py --team eintracht --map Bind --side t
```

| Argument | Values | Example |
|---|---|---|
| `--team` | `eintracht`, `fokus`, `alternate`, `dortmund`, `eco` | `eintracht` |
| `--map` | `Bind`, `Breeze`, `Lotus`, `Pearl`, `Split`, `Corrode` | `Bind` |
| `--side` | `ct`, `t` | `t` |

Output files are written to the **project root**:
- `sge_bind_t_p1_a4.png`
- `sge_bind_t_p2_a4.png`

---

## How it works

### 1. Logo
Downloaded at runtime from VLR.gg CDN (`https://owcdn.net/img/659d1013d5cf5.png`), resized to 150×150 px. Composited onto the bottom-left of every page (30px margin).

### 2. Screenshot
Playwright headless Chromium, **viewport 1240px wide + `deviceScaleFactor=2`**.

- Output screenshot is exactly **2480px wide** (A4 at 300 DPI).
- Why 1240px: the site's `.page-shell` CSS rule caps content at `min(1480px, 100vw - 40px)`. At 1240px viewport that resolves to 1200px CSS = 2400px screen pixels — 97% of A4 width with minimal side margin.
- State is set directly via `page.evaluate()`: sets `activeSideView`, `activeMap`, calls `render()`.
- 3-second wait after render for all map canvases to finish drawing.

### 3. Split point
The page is split into two halves at the **"Map Control" heading**:
- Find `h3.defensive-topic-title` with text `"Map Control"` via `getBoundingClientRect().top + window.scrollY` (CSS pixels).
- Multiply by `SCALE (2)` to convert to screen pixels.

### 4. Page 1
- Crop: `y=0` → `split_y`
- Pad bottom with background colour to fill A4 height (3508px)
- Composite logo bottom-left

**Contains:** site header · team stats · Position at First Kill (×3) · Sniper Kills · All First Kills

### 5. Page 2
- Crop: `split_y` → end of screenshot
- Place on A4 canvas at **y=60px** (breathing room at top)
- Pad remainder with background colour
- Composite logo bottom-left

**Contains:** Map Control (×3) · Rotation Patterns · Post-Plant positioning · last-3-maps sample chips

### 6. Output
Both pages saved as PNG with embedded DPI metadata `(300, 300)`.

---

## Tuning constants (in `scripts/capture_a4.py`)

| Constant | Current value | Purpose |
|---|---|---|
| `SCALE` | `2` | `deviceScaleFactor` — controls output resolution |
| `VIEWPORT_W` | `A4_W // SCALE = 1240` | Browser viewport width in CSS px |
| `LOGO_SIZE` | `150` | Logo dimensions in screen px |
| `LOGO_MARGIN` | `30` | Distance from page edges |
| `top_padding` (p2) | `60` | Y-offset of content on page 2 |
