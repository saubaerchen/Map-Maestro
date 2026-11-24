# VCL EMEA 2026 — Map-Info Data Guide

This document describes the data pipeline for the **Map-Info tab** of VETO_ARCHITECT (`http://127.0.0.1:4173/`). It covers only what is actually built and rendered today.

---

## Overview

The Map-Info tab is a vanilla-JS scouting tool. It has **no build step** — the browser loads static JS/JSON files directly. All positional data is pre-computed by Python scripts and written into those files.

**Three teams are fully supported on the Map-Info tab:**

| App key | File prefix | Team name |
|---------|-------------|-----------|
| `eintracht` | `sge` | Eintracht Frankfurt |
| `fokus` | `fks` | FOKUS |
| `rizon` | `rzn` | Rizon |

The mapping lives in `TEAM_FILE_PREFIX` in `app.js`.

---

## Raw Source Data

```
data/raw/{tag}_2026_raw_responses.jsonl
```

One JSON object per line = one map played. Key fields used by the pipeline:

| Field | Used for |
|-------|----------|
| `matchInfo.map` | Map name (e.g. `"Lotus"`) — **always use this** |
| `matchInfo.gameStartMillis` | Date filtering (≥ 2026-04-01) |
| `players[].gameName` / `tagLine` | Player identification |
| `players[].teamId` | Red/Blue → resolved to actual team via name prefix |
| `roundResults[].kills[]` | Kill timing, weapon, positions |
| `roundResults[].plantPlayerLocations[]` | CT/T positions at spike plant moment |
| `roundResults[].defusePlayerLocations[]` | CT/T positions at defuse moment |

> `matchInfo.mapId` is an internal Riot code (e.g. `"/Game/Maps/Bonsai/Bonsai"`) — do not use it.

---

## Panels and Their Data Sources

### Panel 1 — Position at First Kill (×3 time cards)

**What it shows:** Where each player was standing at the moment the round's first kill happened. Three cards: < 10 s, < 20 s, < 30 s.

**Source file:** `veto-history-site-publish/defensive-early-data.js`

**JS variable:** `defensiveEarlyData[teamKey][side][map].thresholds`

```
thresholds: {
  lt10s: { roundCount, pointCount, points[] }
  lt20s: { roundCount, pointCount, points[] }
  lt30s: { roundCount, pointCount, points[] }
}
```

**Per point:** `player`, `normX`, `normY` (0–100 normalized), `roundNum`, `firstKillTimeMs`, `date`, `opponent`, `score`, `fkOwner` ("team" | "opponent")

---

### Panel 2 — Sniper Kills (Operator / Marshal)

**What it shows:** Every Operator or Marshal kill made by the team on that side/map. Shows both killer and victim positions.

**Source file:** `veto-history-site-publish/defensive-early-data.js`

**JS variable:** `defensiveEarlyData[teamKey][side][map].sniper`

```
sniper: {
  count,
  points[]: { player, normX, normY, victim, victimNormX, victimNormY, roundNum,
               timeSinceRoundStartMillis, date, opponent, score, matchId }
}
```

> Sniper data is computed directly from the raw JSONL at build time. If a match is missing from the JSONL, its kills will not appear even if the other panels look correct.

---

### Panel 3 — All First Kills

**What it shows:** Every first-kill event (any weapon) made by the team on that side/map.

**Source file:** `veto-history-site-publish/defensive-early-data.js`

**JS variable:** `defensiveEarlyData[teamKey][side][map].all_fk`

```
all_fk: {
  count,
  points[]: { player, normX, normY, roundNum, timeSinceRoundStartMillis,
               date, opponent, score, matchId }
}
```

---

### Panel 4 — Map Control (×3 time windows)

**What it shows:** Player positions captured at three time snapshots: 0–10 s, 10–20 s, 20–30 s into the round.

**Source files:**

| Team | File | JS variable |
|------|------|-------------|
| eintracht | `map-control-data.js` | `mapControlData` |
| fokus | `fks-map-control-data.js` | `fksMapControlData` |
| rizon | `rzn-map-control-data.js` | `rznMapControlData` |

**Structure:** `{mapName}.{side}.mapControl["0_10" | "10_20" | "20_30"]`

```
mapControl["0_10"][]: { player, normX, normY, timeMs, roundNum, date, opponent, matchId }
```

---

### Panel 5 — Rotation Patterns

**What it shows:** Full player movement trails per round — how players move from their starting position toward a site or rotation.

**Source files:** Same map-control data files as Panel 4.

**Structure:** `{mapName}.{side}.rotations[roundIndex][playerIndex]`

```
rotations[r][p]: { player, snapshots[], opponent, date, roundNum, plantTimeMs }
snapshots[]: { normX, normY, timeMs }
```

> `rotations` is a nested list: each element is a round, and each round is a list of player trails. Filter by `round[0]?.opponent`, not by the inner trail object directly.

---

### Panel 6 — Retake (CT) / Post-Plant (T)

**What it shows:**
- **CT side:** Where the defending team is standing when the spike is planted (retake setup positions).
- **T side:** Where the attacking team is standing after planting the spike (post-plant positions).

**Source files:** Loaded at runtime via `fetch()` from the `data/` directory.

```
data/{tag}_{map}_ct_retake_positions_last3.json
data/{tag}_{map}_t_postplant_positions_last3.json
```

**Structure:**

```json
{
  "team", "name", "map", "side",
  "sampleSize", "selectedMaps[],
  "sites": {
    "A": { "roundCount", "pointCount", "points[]" },
    "B": { ... },
    "C": { ... }
  },
  "legend[]"
}
```

**Per point:** `player`, `normX`, `normY`, `roundNum`, `plantRoundTimeMs`, `site`, `date`, `opponent`, `score`

**Maps covered per team:**

| Team | CT retake maps | T post-plant maps |
|------|---------------|-------------------|
| eintracht | Bind, Breeze, Fracture, Lotus, Pearl, Split | same |
| fokus | Bind, Breeze, Fracture, Lotus, Pearl, Split | same |
| rizon | Bind, Breeze, Haven, Lotus, Split | same |

---

### Panel 7 — Site Stats

**What it shows:** Per-site statistics across the sample — plant frequency, win rate, timing, and first-kill timing.

**Source files:** Loaded at runtime via `fetch()` from the `data/` directory.

```
data/{tag}_{map}_site_stats.json
```

**Structure:**

```json
{
  "team", "map",
  "t_side": {
    "total_rounds",
    "sites": {
      "A": { "plant_count", "pct_plant", "pct_win", "avg_plant_time",
              "min_plant_time", "max_plant_time", "fk_to_plant_avg", "fk_to_plant_n" }
    }
  },
  "ct_side": {
    "total_rounds",
    "sites": {
      "A": { "plant_count", "defuse_count", "pct_defuse_win", "pct_defuse_share",
              "avg_defuse_time", "fk_after_plant_avg", "fk_after_plant_n" }
    }
  },
  "matches[]"
}
```

---

## Data Pipeline

```
data/raw/{tag}_2026_raw_responses.jsonl
  │
  ├─► analyze_{tag}_early_positioning_batch.py
  │       → data/analysis/{tag}_{map}_{side}_early_team_positioning_last3.json
  │
  ├─► build_sge_defensive_early_bundle.py        (reads analysis JSONs + raw JSONL)
  │       → defensive-early-data.js              [Panels 1, 2, 3 — all 3 teams]
  │
  ├─► analyze_sge_retake_positions_batch.py      (and equivalent for fks, rzn)
  │       → data/analysis/{tag}_{map}_{side}_retake_positions_last3.json
  │
  ├─► build_{tag}_retake_postplant_bundle.py
  │       → data/{tag}_{map}_{side}_retake_positions_last3.json     [Panel 6]
  │         data/{tag}_{map}_{side}_postplant_positions_last3.json
  │
  ├─► build_{tag}_map_control_bundle.py          (reads raw JSONL directly)
  │       → {tag}-map-control-data.js            [Panels 4, 5]
  │
  └─► build_team_site_stats_bundle.py            (reads raw JSONL directly)
          → data/{tag}_{map}_site_stats.json     [Panel 7]
```

**Important:** Panels 1 / 3 (early positioning) use the intermediate analysis JSONs and do **not** need the raw JSONL to display correctly. Panel 2 (sniper kills) is computed fresh from the raw JSONL at bundle build time.

---

## Coordinate System

All positional data is stored as `normX` / `normY` — values in the range 0–100 representing a percentage of map width/height. The raw game coordinates (`x`, `y`) are also stored but are not used by the renderer.

Two maps are rotated clockwise 90° before display: **Haven** and **Split**. The renderer applies `rotCW90(x, y) → [y, 100 - x]` to their coordinates automatically.

---

## Sample Selection Rule

All panels use the **last 3 maps** played on that map (from 2026-04-01 onwards). If fewer than 3 maps exist in the recent window, older maps from Stage 1 / pre-season are supplemented to reach 3. The selected matches are listed in `selectedMaps[]` on each data object.

---

## Adding a New Team

1. Add raw JSONL to `data/raw/{tag}_2026_raw_responses.jsonl`.
2. Add team key to `TEAM_FILE_PREFIX` in `app.js`.
3. Add team to `teamOrder` in `app.js`.
4. Run the relevant `analyze_*` and `build_*` scripts for the panels you want.
5. Sync output files to `veto-history-site-publish/`.
