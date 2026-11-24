# Map-Info Panels — Architecture & Implementation Reference

This document covers every panel in the Map-Info view of the VETO_ARCHITECT scouting site: where the data comes from, how it is processed, what scripts produce it, and how `app.js` renders it on the page.

---

## Overview

The Map-Info view is a scouting tool that shows per-team, per-map, per-side spatial data derived from professional Valorant match telemetry. There are **seven distinct panel types**, each driven by a different slice of the same underlying data.

```
Valolytics API
  └─ raw JSONL per team  (data/raw/{tag}_2026_raw_responses.jsonl)
       ├─ analyze_{tag}_early_positioning_batch.py  → data/analysis/{tag}_{map}_{side}_early_team_positioning_last3.json
       ├─ build_sge_defensive_early_bundle.py        → veto-history-site-publish/defensive-early-data.js
       ├─ build_map_control_bundle.py                → veto-history-site-publish/{tag}-map-control-data.js
       ├─ build_retake_postplant_bundle.py            → veto-history-site-publish/data/{tag}_{map}_{side}_retake_positions_last3.json
       ├─ build_economy_bundle.py                    → veto-history-site-publish/data/{prefix}_economy.json
       └─ build_agents_bundle.py                     → veto-history-site-publish/data/{prefix}_agents.json
```

All output files are loaded by `index.html` as `<script>` tags or fetched at runtime by `app.js`.

---

## Data Source: The Valolytics API

**Base URL:** `https://api.valolytics.gg`  
**Auth:** `x-api-key` header, value read from `API_REFERENCE.md`

Three endpoints are used:

| Endpoint | Purpose |
|---|---|
| `/api/riot/account/v1/accounts/by-riot-id/esports/{name}/{tag}` | Resolve player PUUID |
| `/api/riot/match/v1/matchlists/by-puuid/esports/{puuid}` | Fetch match history for a player |
| `/api/matches/esports/{matchId}` | Fetch full match detail (round results, kill events, player locations, economy) |

**Fetch script:** `scripts/fetch_sge_matches_since.py` (and per-team variants `fetch_{tag}_matches_since.py`).  
Each script accepts `--start-date YYYY-MM-DD`, discovers all PUUIDs from the existing JSONL, pulls match history for each, deduplicates by `matchId`, and appends new matches to the raw JSONL file.

**Raw storage:** one JSONL file per team at `data/raw/{tag}_2026_raw_responses.jsonl`. Each line is one complete match object exactly as returned by the API.

**Important field:** always use `matchInfo.map` (human-readable, e.g. `"Lotus"`) — never `matchInfo.mapId` (internal Riot path, unreliable).

---

## Shared Library: `lib/`

| File | Purpose |
|---|---|
| `lib/constants.py` | `OPERATOR_UUID`, `AGENT_MAP`, `AGENT_ROLE`, team `TEAMS` list |
| `lib/stats_engine.py` | `get_team_side_per_round()` — maps each `roundNum` to `"atk"` or `"def"` for a given team by reading `roundResults` |
| `lib/match_parser.py` | `load_team_matches()` — shared JSONL loader with date filters |

`get_team_side_per_round` is used by every analysis and build script to correctly assign CT/T roles per round (sides swap at halftime, OT rounds handled automatically).

---

## Coordinate System & Map Transforms

Riot's API returns raw `x`/`y` coordinates in an internal game-world unit system. Each map has a unique affine transform to convert these to `normX`/`normY` in the range `[0, 100]` (percentage of map image width/height).

**Standard transform (most maps):**
```python
norm_x = (raw_y * xMultiplier + xScalarToAdd) * 100
norm_y = (raw_x * yMultiplier + yScalarToAdd) * 100
```
Note the axes are swapped (`raw_y → norm_x`, `raw_x → norm_y`), which accounts for Valorant's coordinate orientation.

**Ascent special case (90° CW rotation):**
Ascent's map PNG is pre-rotated 90° CW. The transform uses `swap_xy: True`, which swaps `raw_x` and `raw_y` before applying the multipliers:
```python
"Ascent": {"xMultiplier": 7.0e-05, "yMultiplier": 7.0e-05, "xScalarToAdd": 0.426758, "yScalarToAdd": 0.813895, "swap_xy": True}
```
Both multipliers are positive `7e-5`. `swap_xy` is supported in all four pipeline scripts.

The `MAP_TRANSFORMS` dict is duplicated in each pipeline script and in `normalize_xy()` helper functions — all copies must stay in sync.

**Frontend rotation:** `app.js` uses `MAP_ROTATE_COORDS_CW` and `rotCW90()` for any final coordinate rotation applied at render time. This is separate from the Ascent `swap_xy` — do not conflate them.

---

## Panel 1 & 2: Position at First Kill (3 threshold cards)

### What it shows
Player positions at the exact moment the first kill of the round occurs, grouped into three timing windows: `<10s`, `<20s`, `<30s` from round start. One card per window, each a map canvas with colored dots (one per player per round).

### Data flow

**Step 1 — Analysis script** (`scripts/analyze_{tag}_early_positioning_batch.py`):
- Reads raw JSONL for the team
- For each map/side combination (CT and T), selects the **last 3 maps** played (configurable via `TARGET_MAP_COUNT = 3`)
- For Ascent only: applies `MAP_DATE_CUTOFFS = {"Ascent": 1776038400000}` (2026-04-13 UTC cutoff) — only last-8-weeks games used
- For each qualifying round:
  - Finds the first kill event (earliest `timeSinceRoundStartMillis` across all player kill logs)
  - Captures the `playerLocations` snapshot from that kill event — this is a list of all 10 players' positions at that exact game tick
  - Filters to only the team's 5 players
  - Normalizes coordinates with `normalize_xy()`
  - Tags each point with `player`, `roundNum`, `matchId`, `date`, `opponent`, `score`, `fkOwner` ("team" / "enemy")
- Buckets points into three threshold sets (`lt10s`, `lt20s`, `lt30s`)
- Writes per-map-side JSON to `data/analysis/{tag}_{map}_{side}_early_team_positioning_last3.json`

**Step 2 — Bundle script** (`scripts/build_sge_defensive_early_bundle.py`):
- Reads all per-team per-map-side analysis JSONs listed in `TEAM_SOURCES`
- Merges them into a single nested JS object keyed `[teamKey][side][mapName]`
- Also computes **sniper kills** and **all-first-kills** from the raw JSONL (see Panels 3 & 4 below)
- Writes `veto-history-site-publish/defensive-early-data.js` as `const defensiveEarlyData = {...};`

**Frontend** (`app.js: renderDefensivePanels()`):
- Reads `defensiveEarlyData[activeTeam][activeSideView][activeMap].thresholds`
- For each threshold key (`lt10s`, `lt20s`, `lt30s`): renders a `.defensive-card` article
- Each card contains a `.heat-layer-frame` with the map image and colored `<span class="heat-point">` dots
- Dot position: `style="left:{normX}%; top:{normY}%"`
- Player colors come from `TEAMS_CONFIG[team].playerColors` via `getPlayerColor()`
- Player filter sidebar (left column chips) controls which dots are visible via `selectedPlayers` set

---

## Panel 3: Sniper Kills

### What it shows
Map positions where the team's players landed kills with the Operator, Outlaw, or Marshal. Both killer position and victim position are shown, connected by a line.

### Data flow

**Computed in** `build_sge_defensive_early_bundle.py` (`build_sge_sniper_points_for_dataset()`):
- Iterates over every round in every match in the `selectedMaps` list from the analysis JSON
- Filters by side (CT = `"def"`, T = `"atk"`)
- For each kill event: checks `finishingDamage.damageItem` UUID against `SNIPER_UUIDS = {OPERATOR_UUID, MARSHAL_UUID, OUTLAW_UUID}`
- Extracts killer `playerLocations` entry for that PUUID, normalizes to `normX`/`normY`
- Also extracts `victimLocation` (a separate top-level field on the kill event) and normalizes it to `victimNormX`/`victimNormY`
- Stores both coordinates so the frontend can draw killer → victim lines

**Output structure:** `defensiveEarlyData[team][side][map].sniper = { count, points: [...] }`

**Frontend** (`app.js: renderDefensivePanels()`):
- Reads `info.sniper.points`
- Renders killer dots (`<span class="heat-point">`) colored by player
- Renders victim dots (`<span class="heat-victim-point">`) as grey/light markers
- Draws SVG `<line>` elements connecting killer → victim positions
- No player sidebar filter applied to sniper (it shows all players)

---

## Panel 4: All First Kills

### What it shows
Every round where the team secured the first kill — the killer's position and victim's position, connected by a line. Unlike the threshold panels, there is no timing split — all rounds in the sample are shown.

### Data flow

**Computed in** `build_sge_defensive_early_bundle.py` (`build_sge_all_fk_points_for_dataset()`):
- For each round: collects all kill events, sorts by `timeSinceRoundStartMillis`, takes the earliest
- Only keeps rounds where the **team** player got the first kill (`first_killer_puuid in team_puuids`)
- Extracts killer position from `playerLocations`, victim from `victimLocation`
- Also captures `plantSite` from `roundResult.plantSite` (used by the T-side plant site filter buttons)

**Output structure:** `defensiveEarlyData[team][side][map].all_fk = { count, points: [...] }`

**Frontend** (`app.js: renderDefensivePanels()`):
- Reads `info.all_fk.points`
- Same SVG line + killer dot + victim dot rendering as the Sniper panel
- T-side: plant site filter (`activePlantSites` Set) applied via `applyPlantSiteFilter()`

---

## Panel 5: Map Control (3 time-window cards)

### What it shows
Player positions across three time windows into the round: `0–10s`, `10–20s`, `20–30s`. Unlike the first-kill panels, these are not FK-triggered snapshots — every round is sampled, and player positions are taken from all kill events within that time window (wherever any kill happened on the map that round).

### Data flow

**Build script:** `scripts/build_map_control_bundle.py --team {tag}`

- Reads raw JSONL directly (not the analysis JSONs)
- Uses **all post-2026-04-01 matches** for each map (no 3-game sample cap — full dataset)
- For each round/side: iterates all kill events and extracts `playerLocations` snapshots
- For each snapshot: buckets each player position into the appropriate time window based on `timeSinceRoundStartMillis`
- Normalizes coordinates with the same `MAP_TRANSFORMS`
- Also builds the `sniperRoundKeys` list (rounds where the team had an Op/Outlaw in loadout, used by the rotation sniper filter)
- Output per team: `veto-history-site-publish/{tag}-map-control-data.js` as `const {tag}MapControlData = {...};`

**Data structure:**
```javascript
{tag}MapControlData[mapName][side] = {
  mapControl: {
    "0_10":  [ { player, normX, normY, matchId, roundNum, date, opponent, timeMs }, ... ],
    "10_20": [...],
    "20_30": [...]
  },
  rotations: [ roundTrails ],   // see Panel 6
  sniperRoundKeys: ["matchId|roundNum", ...]
}
```

**Frontend** (`app.js: buildMapControlMarkup()`):
- Called from `renderDefensivePanels()` — rendered as a separate section below the FK panels
- Three `.defensive-card` articles, one per time window
- Player visibility controlled by the same sidebar chips as the FK panels
- Economy filter and plant site filter both applied

---

## Panel 6: Rotation Patterns

### What it shows
Per-round player movement trails — ordered position snapshots for each player across a round, shown as colored polylines. Rounds can be filtered by time window (`1:40–1:20`, `1:20–1:00`, `1:00–End`, Afterplant/Retake) and individual trails can be isolated by clicking.

### Data flow

**Same build script as Map Control** (`build_map_control_bundle.py`):
- For each round, collects ordered `playerLocations` snapshots from every kill event in the round, sorted by time
- Groups by player into a "trail" object: `{ player, snapshots: [{normX, normY, timeMs},...], matchId, roundNum, date, opponent, plantTimeMs }`
- Trails are grouped by round: `rotations[roundIndex][playerIndex]`

**Important data structure note:** `rotations` is a nested list — each element is a round (list of per-player trails). Filtering by `p.opponent` must use `p[0]?.opponent` (the first trail in the round), not `p.opponent` (which would access `opponent` on the array itself).

**Frontend** (`app.js: buildRotationMarkup()` / `computeRotationLayers()` / `updateRotationCardInPlace()`):
- `buildRotationMarkup()` builds the initial HTML for the card including SVG overlay and dot layer
- `computeRotationLayers()` recalculates SVG polylines + dots for the current filter state
- `updateRotationCardInPlace()` diffs the DOM in-place when a player chip or match chip is toggled (avoids full re-render)
- **Critical guard:** if `#rotation-panel-card` is not in the DOM (e.g. map has no rotation data), only calls `renderMapInfo()` if rotation data actually exists for that map — bare fallback was a bug that broke button interactivity on maps without rotation data

---

## Panel 7: Retake / Post-Plant Positions

### What it shows
- **CT side (Retake):** Defender positions at the moment the spike is planted. Shows where players are positioned when they need to retake, grouped by plant site (A/B/C).
- **T side (Post-Plant):** Attacker positions at the moment they plant the spike. Shows default post-plant setups, grouped by plant site.

### Data flow

**Build script:** `scripts/build_retake_postplant_bundle.py --team {tag}`

- Uses `selectedMaps` from the CT-side early positioning analysis JSON (same 3-game sample) as the match selector
- For CT retake: finds rounds where the **opponent** planted, reads all player position snapshots at `plantTimeMs`, captures team player positions
- For T post-plant: finds rounds where the **team** planted, captures team player positions at plant time
- Normalizes coordinates with `MAP_TRANSFORMS`
- Groups points by plant site (`A`, `B`, `C`)
- Writes JSON files to `veto-history-site-publish/data/{tag}_{map}_{side}_retake_positions_last3.json`

**Special case:** SGE Lotus CT retake is generated by a dedicated script `analyze_sge_lotus_retake_positions.py` (more granular analysis, `skip_ct: ["Lotus"]` in the batch config).

**Frontend** (`app.js`):
- Files are fetched at runtime via `fetch('./data/{tag}_{map}_{side}_retake_positions_last3.json')` on team/map change
- Stored in `allDefensiveRetake[teamKey][side][mapName]`
- Rendered as a section within `renderDefensivePanels()` using `getRetakeInfo()` + `collectRetakePoints()`
- Plant site A/B/C buttons in the floating sample card filter via `activePlantSites` Set (exclusive single-select)
- C-site button only rendered on maps in `MAPS_WITH_C_SITE = new Set(["Lotus", "Haven"])`

---

## Supporting Data: Economy Filter

**Build script:** `scripts/build_economy_bundle.py --team {tag|all}`

For each match and round, classifies the team's economic state:
- `pistol` — round 0 or round 12 (first round of each half)
- `eco` — average loadout value per player `< 2000`
- `force` — `2000 ≤ avg < 3800`
- `full` — `avg ≥ 3800`
- `teamHasOp` — any team player's `economy.weapon` UUID matches `OPERATOR_UUID`

Output: `{prefix}_economy.json` keyed `matchId → roundNum → { teamTier, oppTier, teamHasOp }`.

Loaded at startup via `preloadEconomyData(teamKey)`. Applied to all 7 panel types via `applyEconomyFilter()`. After running the script, bump `ECONOMY_DATA_VERSION` in `app.js` to bust the browser cache.

---

## Supporting Data: Agent Icons

**Build script:** `scripts/build_agents_bundle.py --team {tag|all}`

For each match, records the agent comp (agent names and UUIDs, sorted by role: Duelist → Initiator → Controller → Sentinel). Output: `{prefix}_agents.json` grouped by map, comps sorted most-recent-first.

Used by `app.js` when `agentIconMode` is enabled — dots are replaced by agent icon images (`heat-point--icon` class). After running the script, bump `AGENTS_DATA_VERSION` in `app.js`.

---

## Frontend Architecture (`app.js`)

### Loading sequence
1. `defensive-early-data.js` loaded as a `<script>` tag — sets `defensiveEarlyData` global
2. Per-team map control `.js` files loaded as `<script>` tags — set `{tag}MapControlData` globals
3. `TEAMS_CONFIG` reads all these globals into `mapControl` fields at startup
4. On team/map change: retake JSON and economy/agents JSON fetched dynamically

### Key rendering functions

| Function | Purpose |
|---|---|
| `renderMapInfo()` | Top-level: picks the active info object, calls `renderDefensivePanels()` |
| `renderDefensivePanels(info)` | Builds all panel HTML for a given map/side/team |
| `buildMapControlMarkup()` | Generates the 3-card Map Control section |
| `buildRotationMarkup()` | Generates the Rotation Patterns card |
| `computeRotationLayers()` | Recalculates SVG + dots for current rotation filter state |
| `updateRotationCardInPlace()` | Incremental DOM update for rotation on player/match toggle |
| `renderHeatmap()` | Generic heatmap renderer used by the Sniper and All-FK panels |
| `projectHeatmapPoint()` | Applies `MAP_ROTATE_COORDS_CW` runtime rotation to normalized coords |
| `applyEconomyFilter()` | Filters any point/trail array by active economy tier |
| `applyPlantSiteFilter()` | Filters any point/trail array by active plant site |
| `applyNewRosterFilter()` | FOKUS-specific: filters to new-roster opponents when toggle is on |

### Team configuration (`TEAMS_CONFIG`)

All team-specific data (file prefix, player colors, player order, available maps, map control data reference) lives in `TEAMS_CONFIG` at the top of `app.js`. Adding a new team requires only one entry there — all panels, retake loading, site stats, and economy data derive from it automatically via `TEAM_FILE_PREFIX`.

### Coordinate pipeline summary

```
API raw_x, raw_y
  → normalize_xy() in Python (swap axes, apply per-map affine transform)
  → normX, normY stored in JSON (0–100 range)
  → projectHeatmapPoint() in JS (applies CW rotation for ROTATED_MAPS_CW if needed)
  → final left%, top% CSS for dot placement
```

---

## Full Update Workflow (new matches for a team)

When new matches are fetched, all six scripts must run — partial updates leave panels out of sync:

```
1. python scripts/analyze_{tag}_early_positioning_batch.py
2. python scripts/build_sge_defensive_early_bundle.py
3. python scripts/build_map_control_bundle.py --team {tag}
4. python scripts/build_retake_postplant_bundle.py --team {tag}
5. python scripts/build_economy_bundle.py --team {tag}    → bump ECONOMY_DATA_VERSION in app.js
6. python scripts/build_agents_bundle.py --team {tag}     → bump AGENTS_DATA_VERSION in app.js
```

Then copy updated files from `veto-history-site/` to `veto-history-site-publish/` and push to GitHub Pages.

---

## File Map Summary

| File / Directory | Role |
|---|---|
| `data/raw/{tag}_2026_raw_responses.jsonl` | Raw match data from Valolytics API, one match per line |
| `data/analysis/{tag}_{map}_{side}_early_team_positioning_last3.json` | Pre-computed early positioning data for FK panels |
| `veto-history-site-publish/defensive-early-data.js` | Bundled FK + sniper + all-FK data for all teams |
| `veto-history-site-publish/{tag}-map-control-data.js` | Map control + rotation data per team |
| `veto-history-site-publish/data/{tag}_{map}_{side}_retake_positions_last3.json` | Retake/post-plant positions, fetched at runtime |
| `veto-history-site-publish/data/{prefix}_economy.json` | Round-by-round economy tiers, fetched at runtime |
| `veto-history-site-publish/data/{prefix}_agents.json` | Agent compositions per map, fetched at runtime |
| `veto-history-site/app.js` | All rendering logic, ~1400 lines, no build step |
| `veto-history-site/index.html` | Shell, loads script tags, two views (Veto / Map-Info) |
| `lib/stats_engine.py` | `get_team_side_per_round()` — shared side-assignment logic |
| `lib/constants.py` | `OPERATOR_UUID`, `AGENT_MAP`, `AGENT_ROLE`, team list |
