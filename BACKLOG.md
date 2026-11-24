# Map Maestro — Backlog

Noted items, newest first.

## ✅ Done 2026-11-24
- **Abyss + Corrode rotated 90° CW**: added to `ROTATED_MAPS_CW` (image + dots + lines rotate as one frame). Checked visually: MIR Abyss CT dots on both sites, Barça Corrode T dots in the lanes.
- **Sample card** now shows `10-22 vs SGE` (map name removed in both chip variants).
- **T-side Post-Plant `+10-20s` button**: `build_postplant_10_20(..., team_planted=True)` now also writes `postPlant10_20` into the T post-plant files (57 files, 475 rounds); the Post-Plant panel shows trails + dots 10–20s after the team's own plant (shares the toggle with CT Retake; respects site chips + economy filter).

## Original notes (2026-11-24, from Vincent's screenshots of the live site)

### 1. Abyss and Corrode are rotated the wrong way
- **What:** on Map-Info, Abyss and Corrode should be shown **rotated 90° clockwise**.
- **Requirement:** after rotating, the dots must still sit where the players actually were. Image and dots must rotate together, not image only.
- **Where:** `veto-history-site-publish/app.js` → `ROTATED_MAPS_CW = new Set(["Haven", "Split"])` (≈ line 223). Maps in this set are drawn rotated 90° CW as a whole frame (image + dots + lines together), so alignment is preserved. Likely fix: add `"Abyss"` and `"Corrode"` there.
- **Watch out:** do **not** use `MAP_ROTATE_COORDS_CW` (rotates only the coordinates) or change the coordinate transforms in `scripts/live/site_config.py`. The dots are currently correctly aligned with the unrotated image (checked: 0.7% / 1.1% of positions off-map).
- **Verify after the fix:** dots land in the same callouts as before (e.g. B-site plants still on B site), check every panel (FK cards, sniper/all-FK lines, map control, rotations, retake/post-plant) on both sides, plus the agent-icon mode.

### 2. Sample card: remove the map name
- **What:** the floating "LAST N MAPS IN SAMPLE" card shows `10-22 Abyss vs SGE`. The map is already selected, so it should read **`10-22 vs SGE`**.
- **Where:** `app.js` ≈ line 586: `` `${item.date.slice(5)} ${item.map} vs ${item.opponent}` `` → drop `${item.map}`. Check whether the same chip markup is used elsewhere (where the map name might be needed).

### 3. Post-plant "+10s" button for the T-side Post-Plant panel
- **What:** Vincent remembers a **+10 second** button in an earlier version. It shows where players are **after** the spike is planted (10–20s after plant), not at the moment of the plant, so you can see where they go to hold the post-plant.
- **Current state:**
  - The button **exists on the CT Retake panel** (`+10-20s`, `toggleRetakePostPlantMode`, `app.js` ≈ lines 1459–1550, data field `postPlant10_20`).
  - The **T-side Post-Plant panel has no such button.** Its data files (`data/{prefix}_{map}_t_postplant_positions_last3.json`) **don't contain `postPlant10_20`**. Only the 57 CT retake files have it.
- **Likely fix:**
  1. `scripts/build_retake_postplant_bundle.py`: also compute `postPlant10_20` for the T side (positions of the planting team 10–20s after plant).
  2. `app.js`: show the same `+10-20s` toggle on the Post-Plant panel.
  3. Rebuild with `scripts/live/build_site.py`.
- **Reference:** earlier site versions are in `archive/site_publish_snapshot_2026-11-22/app.js` and `archive/veto-history-site/app.js` (both contain the 10–20s logic). The screenshot Vincent used came from an older version (Pearl, old FOKUS roster).

## Open decisions (from earlier)
- Vetoes for the open-qualifier teams: left open (VLR doesn't record Open Qualifier vetoes; Liquipedia could be a source).
- Invited-team core baseline: Liquipedia Kickoff roster applied (MIR loses 3 of 27 games). Confirm or change.
- La Masia: 8 September games with only 3/5 core (TITOUNE + azume as stand-ins) are kept. Keep or require 4/5?
- Default team on page load is now Aurora Gaming (alphabetical). Should it always open on Eintracht?
