# Plant-Site Filter for T-Side Panels

**Date:** 2026-05-21
**Status:** Approved

---

## Summary

Add A-PLANT / B-PLANT / C-PLANT toggle buttons to the three T-side panels in the Map-Info view:
- **Map Control**
- **Rotation Patterns**
- **Position at First Kill** (all three threshold cards)

When no filter is active, all rounds are shown — including A-plant, B-plant, C-plant, and no-plant rounds.
When one or more filters are active, only rounds where the spike was planted on a selected site are shown.
Round outcome (win/loss) is irrelevant to the filter.

---

## Data Layer

### Source field

`plantSite` is a round-level field already present in the raw JSONL (`roundResults[].plantSite`). Values: `"A"`, `"B"`, `"C"`, or absent/null (no plant that round).

### Changes to `build_map_control_bundle.py`

For every T-side round processed:

**Rotations** — add `plantSite` to each player's round trail object:
```python
{
  "player": ...,
  "snapshots": [...],
  "plantTimeMs": ...,
  "plantSite": rr.get("plantSite"),   # NEW — null if no plant
  "roundNum": ...,
  "matchId": ...,
  "date": ...,
  "opponent": ...,
}
```

**Map Control snapshots** — add `plantSite` to each entry in the time-window buckets (`0_10`, `10_20`, `20_30`):
```python
{
  "player": ...,
  "normX": ...,
  "normY": ...,
  "timeMs": ...,
  "plantSite": rr.get("plantSite"),   # NEW — null if no plant
  "roundNum": ...,
  "matchId": ...,
  "date": ...,
  "opponent": ...,
}
```

CT-side rounds are not touched. The field is `null`/absent for rounds where no spike was planted.

### Changes to early positioning analysis scripts

For every T-side FK point, add `plantSite` from the round record:
```python
{
  "player": ...,
  "normX": ..., "normY": ...,
  "roundNum": ...,
  "firstKillTimeMs": ...,
  "plantSite": round_data.get("plantSite"),   # NEW
  ...
}
```

Affected scripts: all `analyze_{team}_early_positioning_batch.py` scripts (T-side only; CT-side JSONs are not rebuilt).

---

## Rebuild Scope

| Step | Command | Scope |
|---|---|---|
| Rebuild map-control bundles | `python scripts/build_map_control_bundle.py --team {tag}` | All 13 teams |
| Rebuild T-side early positioning JSONs | `python scripts/analyze_{team}_early_positioning_batch.py` | All teams with an analyze script |
| Rebuild defensive-early-data.js | `python scripts/build_sge_defensive_early_bundle.py` | Once, after all analysis JSONs are updated |

No CT-side analysis JSONs are rebuilt. No site stats JSONs are affected.

---

## UI Layer

### Button placement

The A-PLANT / B-PLANT / C-PLANT buttons appear in the panel control row on T-side only. They are not shown on CT-side. C-PLANT appears only for maps with three bombsites: **Lotus** and **Haven**.

### Toggle behaviour

- Buttons are independent toggles — any combination can be active simultaneously
- Default state: all off → all rounds displayed (A-plant + B-plant + C-plant + no-plant rounds)
- One or more active → render only rounds where `plantSite` matches any active selection
- A round with no plant (`plantSite` null) is **never** shown when any filter is active
- Toggling a button off while others remain active narrows/widens the set immediately

### Per-panel filter logic

**Rotation Patterns** — filter at the round level. Each element of `rotations` is a round (array of player trails). A round passes if `round[0].plantSite` is in the active set.

**Map Control** — filter at the snapshot level. Each dot in `mapControl["0_10"]` etc. passes if its `plantSite` is in the active set.

**Position at First Kill** — filter at the point level. Each dot in `thresholds.lt10s.points` etc. passes if its `plantSite` is in the active set.

### Visual design

Buttons match the style of existing filter chips (opponent chips). Active state uses the same highlight treatment already used elsewhere in the panel controls. No new CSS classes needed beyond toggling the existing active class.

---

## What Does Not Change

- CT-side panels — untouched
- Opponent filter chips — continue to work independently; plant filter stacks with them
- Site stats summary table — unaffected
- Sniper Kills panel — unaffected (no round-level filtering exists there)
- All FK panel — unaffected (separate from Position at First Kill threshold cards)
- Data for rounds with no plant is preserved when no filter is active

---

## Edge Cases

| Case | Behaviour |
|---|---|
| Map with 2 sites (Bind, Breeze, Split, Pearl, Fracture) | Only A-PLANT and B-PLANT buttons rendered |
| Map with 3 sites (Lotus, Haven) | A-PLANT, B-PLANT, C-PLANT all rendered |
| All filters active (A + B + C) | Equivalent to "planted rounds only" — no-plant rounds hidden |
| Round where plant data is missing from raw JSONL | `plantSite` stored as null; round hidden when any filter active |
| Team has no T-side data for a map | Buttons render but filter finds no matches (empty canvas) |
