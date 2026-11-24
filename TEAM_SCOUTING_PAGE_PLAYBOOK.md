# Team Scouting Page — Full Playbook

This document records exactly how the Eintracht Frankfurt (SGE) scouting page was built inside VETO_ARCHITECT, and serves as a step-by-step replication guide for any future team. When we onboard a new team, work through this document top to bottom.

---

## Part 1 — Sample Logic

### Map Selection

Only analyse maps Vincent has **explicitly stated are important** for the current target. Never assume. Always confirm the map list before touching data.

> SGE example: Bind, Lotus, Split, Pearl were the confirmed relevant maps.

### Sample Size Rules

**Rule A — Primary window:** Collect all matches from **2026-04-01 onwards** on the relevant maps.

**Rule B — Minimum sample supplement:** If a map has fewer than 3 games from April 1st, go back in time and add the most recent pre-April-1st games for that map until the total reaches exactly 3. Stop at 3.

| Games from April 1st | Action |
|---|---|
| ≥ 3 | Use April 1st+ games only |
| < 3 | Supplement with most recent pre-April-1st games until total = 3 |

**Applied example — SGE Split:**
- April 1st onwards: 2 games (vs ATN 2026-04-07, vs RZN 2026-04-14)
- 2 < 3 → Rule B: pull most recent pre-April-1st Split → 2026-03-21 vs TL
- Final sample: 3 Split games

---

## Part 2 — Raw Data Acquisition

### Step 1: Check what raw data already exists

```bash
# Check for existing JSONL file for the team
ls data/raw/{tag}_2026_raw_responses.jsonl
```

Each team has one JSONL file. Each line is a full match JSON from the Valolytics API.

### Step 2: Identify how to fetch the team's data

The Valolytics API requires a PUUID per player. The workflow:

1. Find the team's player names and tags (from Liquipedia or DACH tournament page)
2. Resolve each to a PUUID:
   ```
   GET /api/riot/account/v1/accounts/by-riot-id/esports/{name}/{tag}
   ```
3. Fetch match history per PUUID:
   ```
   GET /api/riot/match/v1/matchlists/by-puuid/esports/{puuid}
   ```
4. Fetch each match in full:
   ```
   GET /api/matches/esports/{matchId}
   ```

The script `scripts/fetch_sge_matches_since.py --start-date YYYY-MM-DD` does this end-to-end for SGE. For a new team, clone this script and update the player list and output file path.

### Step 3: Verify the raw data

After fetching, check the map coverage:

```python
import json, datetime
with open('data/raw/{tag}_2026_raw_responses.jsonl') as f:
    matches = [json.loads(l) for l in f if l.strip()]

for m in matches:
    ts = m.get('matchInfo', {}).get('gameStartMillis', 0)
    dt = datetime.datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d')
    map_name = m.get('matchInfo', {}).get('map')  # ALWAYS use matchInfo.map, NOT matchInfo.mapId
    print(dt, map_name)
```

**Critical warning:** The raw data has two map fields:
- `matchInfo.map` → human-readable name like `"Lotus"` — **use this one**
- `matchInfo.mapId` → internal Riot code like `"/Game/Maps/Bonsai/Bonsai"` — **ignore this, it is misleading and has changed over time**

Apply the sample logic from Part 1 to decide which matches to include per map.

---

## Part 3 — Analysis Scripts

The analysis pipeline runs in two stages.

### Stage 1: Generate early-positioning analysis JSONs

Script: `scripts/analyze_sge_early_positioning_batch.py`

This script reads the raw JSONL, finds the 3 selected matches per map/side, and for each round extracts:
- The timestamp of the first kill in that round
- The position of every team player at that moment
- Grouped into three time buckets: **<10s**, **<20s**, **<30s** from round start

Output (one file per map per side):
```
data/analysis/{tag}_{map}_{side}_early_team_positioning_last3.json
```

Structure of each output file:
```json
{
  "team": "Eintracht Frankfurt",
  "map": "Lotus",
  "side": "ct",
  "sampleSize": 3,
  "selectedMaps": [
    { "date": "2026-04-07", "opponent": "ATN", "matchId": "...", "score": "13-5" }
  ],
  "thresholds": {
    "lt10s": { "roundCount": 6, "pointCount": 29, "points": [...] },
    "lt20s": { "roundCount": 12, "pointCount": 58, "points": [...] },
    "lt30s": { "roundCount": 18, "pointCount": 87, "points": [...] }
  },
  "legend": [
    { "player": "Jamelinho", "color": "#e53935" },
    { "player": "Fizzy", "color": "#f1d500" }
  ]
}
```

Each point in a threshold:
```json
{
  "x": 5000, "y": 3200,
  "normX": 45.2, "normY": 52.1,
  "player": "MONSTEERR",
  "roundNum": 8,
  "date": "2026-04-07",
  "opponent": "ATN",
  "matchId": "..."
}
```

For a new team: clone the script, update the team tag, player prefix, and output path. The coordinate normalization transforms are already stored per map inside the script.

### Stage 2: Build the JS data bundle

Script: `scripts/build_sge_defensive_early_bundle.py`

This script reads:
- All analysis JSONs from Stage 1 (for the thresholds/early-positioning layer)
- The raw JSONL (for the sniper kill layer and all-FK layer)

And writes a single JS file:
```
veto-history-site-publish/defensive-early-data.js
```

**Why two stages?** Early positioning only needs the analysis JSONs. Sniper kill data and all-FK data must be re-read from raw JSONL at build time because they weren't pre-extracted in the analysis step.

**Important:** If the raw JSONL is missing a match (e.g., a match was fetched after the JSONL was last written), sniper kill counts will appear as 0 even though early positioning looks correct. Always verify the JSONL is up to date before building the bundle.

The bundle adds two additional data layers on top of the analysis JSON thresholds:

**Sniper layer:** Operator + Marshal kills by the team on the given side. Extracts killer position and victim position, normalized to 0-100 scale. Used for the "Position OP-Kill" panel.

**All-FK layer:** The earliest kill of each round (any weapon) by the team. Used for the "All First Kills" panel.

---

## Part 4 — What the Site Shows (Panel by Panel)

This section describes every panel in the Map-Info view for a team like SGE, in the order they appear.

### Panel: Position at First Kill (3 cards)

**Data source:** `thresholds.lt10s`, `lt20s`, `lt30s` from the analysis JSON.

**What it shows:** Where each player was positioned at the exact moment the first kill of the round happened — grouped by how early that kill occurred.

- **<10s card:** Rounds where FK happened in the first 10 seconds. Fewest rounds, most aggressive early info.
- **<20s card:** Rounds where FK happened in the first 20 seconds.
- **<30s card:** All rounds with FK under 30 seconds. Largest sample.

Each card shows the map image with colored dots per player. The player sidebar (left of the map) lets you toggle individual players on/off. This filter applies **only** to this panel — sniper and FK panels are never filtered by player.

Round count and point count are displayed on each card.

### Panel: Position OP-Kill + All First Kills (side by side)

**Data source:** `sniper` and `all_fk` from the defensive bundle.

**What it shows:**
- **OP-Kill (left):** Positions where the team took a sniper kill (Operator or Marshal). Red dot = killer position, cyan dot = victim position, red line connects them.
- **All First Kills (right):** Same layout but for any-weapon first kills.

These panels show the full match sample and cannot be filtered by player.

### Panel: Retake Positions (CT side) / Post-Plant Positions (T side)

**Data source:** `data/sge_{map}_{side}_retake_positions_last3.json` (built by `build_sge_retake_postplant_bundle.py`).

**What it shows:** Where CT players were positioned at the moment the spike was planted, grouped by plant site (A / B / C). Site chips are clickable to show/hide individual sites.

Retake position data is built and working for all relevant SGE maps: Bind, Breeze, Lotus, Pearl, Split. Each map loads its own JSON file from `veto-history-site-publish/data/sge_{map}_ct_retake_positions_last3.json`.

### Panel: Lotus Site Stats (Lotus only)

**Data source:** `data/sge_lotus_site_stats.json` (built by `build_sge_site_stats_bundle.py`).

**What it shows:** A stats table for Lotus broken down by site (A / B / C):
- Plant % — how often the spike was planted at each site
- Win % — CT win rate when spike was planted at that site
- Average plant time (seconds from round start)
- Average FK-to-plant time (how quickly the plant happened after the first kill)

This panel is Lotus-specific because of the 3-site structure. Other maps may get similar panels in the future.

---

## Part 5 — Coordinate Normalization

All raw Valorant positions are in an internal coordinate space (e.g., x=10082, y=-5595). The site uses normalized 0-100 coordinates for rendering on the map image.

Each map has a stored transform:

```python
# Example for Bind
xNorm = x * 5.9e-05 + 0.576941
yNorm = y * -5.9e-05 + 0.967566
```

These transforms are defined inside the build/analysis scripts. When adding a new map, the transforms must be derived by cross-referencing known landmark coordinates against the map image pixel positions. This is iterative work — use the site's calibration mode to fine-tune after an initial estimate.

**Calibration mode:** In the site, there is a toggle that makes heatmap dots draggable. When a dot is dragged to its correct position, the override is stored. This was used to correct individual points that fell slightly off due to rounding or edge-case coordinates.

---

## Part 6 — Veto Data (Manual Entry)

The Veto view is populated from manually entered JavaScript data files:

| File | Content |
|---|---|
| `data.js` | Primary veto history (SGE, FKS, base teams) |
| `extra-data.js` | Additional teams (ATN, ECO, DXG) |
| `extra-pick-meta.js` | Which side each team started on per map |
| `extra-score-meta.js` | Match scores |
| `extra-row-meta.js` | Row-level metadata overrides |

Each veto row has this structure:

```javascript
{
  "date": "2026-04-12",
  "opponent": "FOKUS",
  "opponentAbbr": "FKS",
  "source": "https://liquipedia.net/...",
  "sourceLabel": "match page",
  "decider": "Split",
  "ban1": { "map": "Haven", "type": "ban", "ownerLabel": "SGE", "ownerKind": "team" },
  "ban2": { "map": "Fracture", "type": "ban", "ownerLabel": "FKS", "ownerKind": "opp" },
  "pick1": { "map": "Lotus", "type": "pick", "ownerKind": "team", "teamStartSide": "SGE T-SIDE" },
  "pick2": { "map": "Bind", "type": "pick", "ownerKind": "opp" },
  "ban3": { "map": "Pearl", "type": "ban", "ownerKind": "team" },
  "ban4": { "map": "Split", "type": "ban", "ownerKind": "opp" }
}
```

Source for veto data: Liquipedia match pages. Check the series page, not the match detail — the series page lists the full pick/ban order.

---

## Part 7 — Frontend Design System

The site uses vanilla JS, no build step. Everything runs from a Python HTTP server locally and deploys to GitHub Pages.

### Fonts

- **Space Grotesk** (weights 500, 700): brand name, map names, table headers, insight cards
- **Inter** (weights 400, 500, 600, 700): all body text, labels, metadata

Both loaded from Google Fonts in `index.html`.

### Color System

```css
--bg: #f8f9fa          /* page background, very light gray */
--surface: #ffffff     /* card/panel background */
--ink: #191c1d         /* primary text */
--accent: #356b00      /* green, SGE brand color */

/* Veto table pills */
--ban-team:  #f34444   /* team's own ban — bright red */
--ban-opp:   #ffd3d3   /* opponent ban — soft red */
--pick-team: #22c55e   /* team pick — green */
--pick-opp:  #bbf7d0   /* opponent pick — soft green */
--decider:   #bae6fd   /* decider map — light blue */
```

### Layout Structure

```
<header class="masthead">      ← brand + tab switcher (Veto / Map-Info)
<header class="hero">          ← team name + live status dot
<main class="panel">
  <div id="main-toolbar">      ← team selector, side toggle (CT/T)
  <div id="veto-view">         ← hidden when Map-Info is active
  <div id="map-view">          ← hidden when Veto is active
```

The two views are toggled by adding/removing a `hidden` class — no routing, no SPA framework.

### Veto Table Pills

Each veto step is rendered as a `.map-pill` div. CSS classes control color:
- `.ban.team` → red
- `.ban.opp` → soft red
- `.pick.team` → green
- `.pick.opp` → soft green
- `.decider` → light blue

Minimum height: 116px. Content is centered (flexbox). Map name uses Space Grotesk bold.

### Heatmap Canvas

- Container uses `aspect-ratio: 1318/772` (standard Valorant minimap ratio)
- Map image set as CSS background via `--map-bg` custom property
- Kill lines rendered as SVG overlaid on the container
- Dots rendered as absolutely positioned `<button>` elements
- Killer dot: 10px red circle
- Victim dot: 5px cyan circle with glow
- Line: SVG `<line>` with `stroke: #f34444`, `stroke-width: 2`, `opacity: 0.6`

### Defensive Panels Layout

```
[Player sidebar]  [Map canvas]
                  ↑ 3 threshold cards (10s / 20s / 30s) stacked below
                  ↑ OP-Kill + All FK side by side
                  ↑ Retake panel (per site)
```

Player sidebar is positioned to the left of the map canvas using `right: 100%` offset. Width: 150px. Each chip has a colored dot matching the player's canonical color.

### Player Colors (SGE)

| Player | Color |
|---|---|
| Jamelinho | #e53935 (red) |
| Fizzy | #f1d500 (yellow) |
| MONSTEERR | #00e676 (green) |
| azury | #ff4dac (pink) |
| musashi | #1f4fd6 (blue) |
| Ben1 | #ff7f0e (orange) |

These are consistent across all panels on the site. When adding a new team, define a color palette before running the build scripts — the palette is referenced in both the Python builder and the JS renderer.

### Map Image Assets

Map images are stored in `veto-history-site-publish/maps/` as PNGs. File names match the map name exactly (e.g., `Lotus.png`, `Split.png`). The script `scripts/fetch_sge_maps_backfill.py` can fetch missing assets.

---

## Part 7b — UI Text Removed by Design

The following texts were explicitly removed from the site and must **not** be re-added when onboarding a new team:

| Text | Location | Reason removed |
|---|---|---|
| `"Defensive Early Positioning"` eyebrow label | `index.html`, above the team name in the defensive module header | Redundant — the section context is already clear |
| `"Defender/Attacker positions at first-kill time, sniper-kill positions, and retake (spike planted) positions from the last N maps."` | `app.js`, written to `#defensive-copy` below the team name | Too verbose, removed entirely |
| `"Coverage warning: CT/T early-positioning, retake-positioning, and sniper-kill views currently cover [Map] only."` | `app.js`, written to `#map-warning` in the defensive header | Replaced by a cleaner map-pool warning only shown when relevant |

The `#map-warning` element and its map-pool warning (missing maps from current pool) **are** still active — only the defensive-coverage warning was removed.

---

## Part 7c — Terminology for Prompting Claude

Use these terms when asking Claude to build or modify features on the scouting page. Ambiguous language causes Claude to under-scope work.

### Panels
Each named section in the Map-Info view is a **panel**. Current panels per team:

| Panel name | Data source |
|---|---|
| Position at First Kill (×3 cards: <10s / <20s / <30s) | `thresholds` in `defensive-early-data.js` |
| Sniper Kills | `sniper` in `defensive-early-data.js` |
| All First Kills | `all_fk` in `defensive-early-data.js` |
| Map Control (×3 time windows) | `mapControl` in `fks-map-control-data.js` |
| Rotation Patterns | `rotations` in `fks-map-control-data.js` |
| Retake Positions (CT) / Post-Plant (T) | `data/{tag}_{map}_{side}_retake_positions_last3.json` |

### Map canvas
The actual map image with colored dots rendered on top of it, inside a panel. Each panel contains one map canvas.

### Saying "filter all panels"
When you want a filter or toggle to affect everything visible on the page, say:

> *"Filter every panel on the page — every map canvas and its dot data."*

**Do not** say "the maps and tables" — Claude will interpret "maps" as the map names (Bind/Lotus/etc.) and "tables" as the sample chip rows, not the dot visualizations.

### Lesson learned — filter scope (2026-04-22)
A NEW ROSTER toggle was built that initially missed the Map Control and Rotation Patterns panels because those use a separate data file (`fks-map-control-data.js`) from the early-positioning panels (`defensive-early-data.js`). The prompt said *"the maps and tables only take into account the maps played"* — Claude scoped this to the panels it had already explored rather than asking which panels existed.

**Rule:** When a filter or toggle is requested, Claude must first enumerate every panel currently rendered for that team/view, confirm the scope covers all of them, and only then implement.

### Lesson learned — rotation data structure (2026-04-22)
The `rotations` array in `fks-map-control-data.js` is **nested**: it is a list of rounds, where each round is itself a list of player trails (one per player). Structure:
```
rotations = [
  [ {player, snapshots, opponent, ...}, ... ],  // round 1 — 5 player trails
  [ ... ],                                       // round 2
]
```
Filtering by `p.opponent` fails silently when `p` is an inner array. The correct filter reads `p[0]?.opponent` for rotation rounds. Claude must inspect the data structure before applying any filter to a new data source.

---

## Part 8 — Challenges Encountered and Solutions

### 1. Map ID confusion in raw JSONL

**Problem:** Raw match data contains two map fields. `matchInfo.mapId` looks like a path (e.g., `"/Game/Maps/Bonsai/Bonsai"`) but does NOT reliably map to a human-readable name. The codes have changed across Valorant patches and do not follow a consistent naming convention.

**Solution:** Always use `matchInfo.map` which returns the correct human-readable name (e.g., `"Lotus"`). All scripts have been updated to use this field.

### 2. Sniper data showing 0 despite correct early positioning

**Problem:** The site would show early positioning dots correctly but sniper kill count was 0 on some maps.

**Solution:** Sniper data is not pre-extracted in the analysis JSON — it is computed at bundle-build time by reading the raw JSONL. If the JSONL file was incomplete or a match hadn't been fetched yet, the sniper count would silently be 0. Fix: always verify the raw JSONL contains all selected matches before running the bundle builder.

### 3. Coordinate normalization drift

**Problem:** Normalized dot positions on the map image were slightly off from the actual in-game positions, especially near edges of the map.

**Solution:** Each map has its own linear transform stored in the build scripts. For initial setup, use known landmark positions (bombsites, CT spawn corners) to calibrate. Then use the site's built-in calibration mode (drag-to-reposition) to fine-tune individual points. Calibration overrides are stored in memory during the session and exported to a JSON object that can be pasted back into the script as permanent fixes.

---

## Part 9 — Replication Checklist for a New Team

When onboarding a new team, go through these steps in order:

- [ ] Confirm with Vincent which maps are relevant for this team
- [ ] Apply sample logic: count April 1st+ games per map, supplement pre-April if <3
- [ ] Identify players and fetch PUUIDs from Valolytics API
- [ ] Fetch all matches into `data/raw/{tag}_2026_raw_responses.jsonl`
- [ ] Verify map coverage with a quick Python check (use `matchInfo.map`)
- [ ] Clone `analyze_sge_early_positioning_batch.py`, update team tag + player prefix, run for each map/side
- [ ] Verify analysis JSONs look correct (check selectedMaps, roundCount, pointCount)
- [ ] Clone `build_sge_defensive_early_bundle.py`, update paths, run to produce `defensive-early-data.js`
- [ ] Clone `build_sge_retake_postplant_bundle.py`, run for all relevant maps (verify retake bug is fixed first)
- [ ] Define player color palette for the new team
- [ ] Add player colors to `getPlayerColor()` in `app.js`
- [ ] Add the new team's entry to `defensiveEarlyData` object (generated by build script)
- [ ] Add veto history rows to `data.js` or `extra-data.js` manually from Liquipedia
- [ ] Add pick-meta, score-meta, row-meta entries as needed
- [ ] Add the team to the team selector in `index.html` and `app.js`
- [ ] Test locally at `http://127.0.0.1:4173/`
- [ ] Sync changes from `veto-history-site/` to `veto-history-site-publish/`
- [ ] Deploy to GitHub Pages
