# Full Map-Info Onboarding Pipeline

Complete instructions for adding a brand new national team to the scouting site, including all six map panels.

Use `{tag}` as a placeholder for the lowercase nation tag (e.g. `nor`, `por`, `fra`, `aut`).  
All scripts live in `scripts/`. All paths are relative to the repo root.

---

## Step 0 — Decide on player identity mode

National teams have players from different clubs, so there is no shared team prefix.

**Use `player_exact_names` + `player_name_map` in every config block** (not `player_prefix`).

Each player needs two name entries:
- Their **club account** gameName (used for proxy/historical data, e.g. `"CGN DaviH"`)
- Their **ENC tournament account** gameName (e.g. `"POR DaviH"`) — `{TAG} {IGN}` format created at tournament start (2026-06-26)

Both must appear in every `player_exact_names` frozenset and every `player_name_map` dict, mapping to the same short display name.

---

## Step 1 — Register players in `fetch_nation_matches.py`

`fetch_nation_matches.py` has a top-level `NATIONS` dict. Add a new entry:

```python
"{TAG}": [
    ("{TAG} Player1",  "epval"),  # ENC tournament account
    ("Club Player1",   "epval"),  # Club account (proxy data)
    # ... repeat for all 5–7 players
],
```

Then fetch data:

```powershell
python scripts/fetch_nation_matches.py --team {TAG} --start-date 2026-02-01
```

Output: `data/raw/{tag}_2026_raw_responses.jsonl`

Use `--start-date 2026-06-26` to fetch ENC-only matches. Use `2026-02-01` or earlier to also get club proxy data.

---

## Step 2 — Create the analysis batch script

Copy `scripts/analyze_por_early_positioning_batch.py` → `scripts/analyze_{tag}_early_positioning_batch.py`.

Edit the new file:

```python
LOCAL_SEED_FILE = ROOT / "data" / "raw" / "{tag}_2026_raw_responses.jsonl"
TEAM_NAME = "{Country Name}"

PLAYER_GAME_NAMES: dict[str, str] = {
    "Club Player1":    "Player1",   # club account
    "{TAG} Player1":   "Player1",   # ENC account
    # ... all players, both accounts
}
PLAYER_EXACT_NAMES: frozenset[str] = frozenset(PLAYER_GAME_NAMES.keys())

TARGET_MAPS = ("Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Split")

# Ascent: only use matches from last 8 weeks
MAP_DATE_CUTOFFS: dict[str, int] = {
    "Ascent": 1776038400000,  # 2026-04-13 UTC
}
```

Map transforms — copy these exactly (already correct for all ENC maps):

```python
MAP_TRANSFORMS = {
    "Ascent":   {"xMultiplier": 7.0e-05, "yMultiplier": 7.0e-05,  "xScalarToAdd": 0.426758, "yScalarToAdd": 0.813895, "swap_xy": True},
    "Breeze":   {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven":    {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":    {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Split":    {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}
```

> **Ascent note:** The PNG is pre-rotated 90° CW. `swap_xy: True` handles the coordinate swap. Both multipliers are positive `7e-5`. Do NOT add Ascent to `ROTATED_MAPS_CW`.

---

## Step 3 — Add `{tag}` to all five build scripts

Each script has a central config dict. Add a `"{tag}"` entry to **all five**:

### 3a. `build_sge_defensive_early_bundle.py`

Add at the top (with the other `*_RAW_FILE` and `*_EXACT_NAMES` / `*_NAME_MAP` constants):

```python
{TAG}_RAW_FILE = ROOT / "data" / "raw" / "{tag}_2026_raw_responses.jsonl"

{TAG}_EXACT_NAMES: frozenset[str] = frozenset({
    "Club Player1", "Club Player2", ...,
    "{TAG} Player1", "{TAG} Player2", ...,
})
{TAG}_NAME_MAP: dict[str, str] = {
    "Club Player1":   "Player1",
    "{TAG} Player1":  "Player1",
    # ...
}
```

Then wire it into the team loop (follow the `por` / `fra` / `nor` pattern in the script body).

### 3b. `build_map_control_bundle.py`

Add to `TEAM_CONFIG`:

```python
"{tag}": {
    "player_exact_names": frozenset({
        "Club Player1", ..., "{TAG} Player1", ...,
    }),
    "player_name_map": {
        "Club Player1":  "Player1",
        "{TAG} Player1": "Player1",
        # ...
    },
    "jsonl":       ROOT / "data" / "raw" / "{tag}_2026_raw_responses.jsonl",
    "output_file": ROOT / "veto-history-site-publish" / "{tag}-map-control-data.js",
    "js_var":      "{tag}MapControlData",
    "maps":        ["Ascent", "Breeze", "Fracture", "Haven", "Lotus", "Split"],
},
```

### 3c. `build_retake_postplant_bundle.py`

Add to its `TEAM_CONFIG` (same shape — `player_exact_names`, `player_name_map`, `jsonl`, `maps`).

### 3d. `build_economy_bundle.py`

Add to its team config. Economy data keys on player round-economy, so the same `player_exact_names` pattern applies.

### 3e. `build_agents_bundle.py`

Add to its team config. Agents are per-match, so the same exact-names pattern applies.

---

## Step 4 — Run the full pipeline

Run all six steps in order:

```powershell
python scripts/analyze_{tag}_early_positioning_batch.py
python scripts/build_sge_defensive_early_bundle.py
python scripts/build_map_control_bundle.py --team {tag}
python scripts/build_retake_postplant_bundle.py --team {tag}
python scripts/build_economy_bundle.py --team {tag}
python scripts/build_agents_bundle.py --team {tag}
```

**After step 5 (economy):** bump `ECONOMY_DATA_VERSION` in `veto-history-site-publish/app.js`.  
**After step 6 (agents):** bump `AGENTS_DATA_VERSION` in `veto-history-site-publish/app.js`.

Do not skip any step. Each step covers different panel types:

| Step | Panels covered |
|---|---|
| `analyze_{tag}_batch.py` | Generates analysis JSONs (input to next step) |
| `build_sge_defensive_early_bundle.py` | Position at First Kill (×3), Sniper Kills, All First Kills |
| `build_map_control_bundle.py` | Map Control (×3 windows), Rotation Patterns |
| `build_retake_postplant_bundle.py` | Retake / Post-Plant positions |
| `build_economy_bundle.py` | Economy filter (all panels) |
| `build_agents_bundle.py` | Agent comp icons |

---

## Step 5 — Wire up the site

### `veto-history-site-publish/index.html`

Add a script tag for the map-control output (keep with the other team map-control scripts):

```html
<script src="./{tag}-map-control-data.js"></script>
```

### `veto-history-site-publish/app.js`

**1. Add to `TEAMS_CONFIG`:**

```javascript
"{tag}": {
    label: "{Country Name}",
    flag: "{tag}",        // used for flag image lookup
    filePrefix: "{tag}",  // used by TEAM_FILE_PREFIX
},
```

**2. Add to `ACTIVE_TEAMS`:**

```javascript
const ACTIVE_TEAMS = [..., "{tag}"];
```

**3. Add to `TEAM_FILE_PREFIX`** (if it doesn't auto-derive from the tag):

```javascript
const TEAM_FILE_PREFIX = {
    ...,
    "{tag}": "{tag}",
};
```

---

## Step 6 — Veto data (optional)

National teams have no veto history — `app.js` handles this gracefully and falls back to the map-info view. No entry in `extra-data.js` is needed unless you have explicit veto rounds to track.

---

## Checklist

- [ ] Players added to `fetch_nation_matches.py` (both club + ENC account names)
- [ ] Data fetched → `data/raw/{tag}_2026_raw_responses.jsonl` exists and is non-empty
- [ ] `scripts/analyze_{tag}_early_positioning_batch.py` created (copied from `por`, player names updated)
- [ ] `{tag}` added to `build_sge_defensive_early_bundle.py` (RAW_FILE constant + EXACT_NAMES + NAME_MAP + team loop)
- [ ] `{tag}` added to `build_map_control_bundle.py` (`TEAM_CONFIG`)
- [ ] `{tag}` added to `build_retake_postplant_bundle.py` (`TEAM_CONFIG`)
- [ ] `{tag}` added to `build_economy_bundle.py` (`TEAM_CONFIG`)
- [ ] `{tag}` added to `build_agents_bundle.py` (`TEAM_CONFIG`)
- [ ] All 6 pipeline commands run without errors
- [ ] `ECONOMY_DATA_VERSION` bumped in `app.js`
- [ ] `AGENTS_DATA_VERSION` bumped in `app.js`
- [ ] `<script src="./{tag}-map-control-data.js">` added to `index.html`
- [ ] Team entry added to `TEAMS_CONFIG` and `ACTIVE_TEAMS` in `app.js`
- [ ] Site loads team in browser, all panels show data

---

## Common pitfalls

**Missing ENC account names** — players rename to `{TAG} {IGN}#epval` on 2026-06-26. If you only add club names, all tournament matches return 0 data.

**Partial pipeline runs** — skipping any build script leaves that panel type empty. Always run all six.

**Wrong Ascent transform** — Ascent uses `swap_xy: True` with both multipliers positive `7e-5`. The old constants (`xScalarToAdd: 0.813895, yScalarToAdd: 0.573242`) are wrong; the PNG is rotated.

**`build_sge_defensive_early_bundle.py` rebuilds ALL teams** — running it without the new team registered will not remove existing teams, but the new team's panels will be empty until the constants and loop body are updated.

**`allSiteStats` and other data stores must be team-keyed** — never store retake/site data under just a map key. Always `data[teamKey][mapName]`.
