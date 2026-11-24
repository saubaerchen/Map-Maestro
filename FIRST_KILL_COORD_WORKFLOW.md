# First-Kill + Coordinate Workflow

This file documents the exact process we used to retrieve **team first kills** with **raw world coordinates** (killer and victim), including filters like:

- last `N` series
- kill timing threshold (for example `<= 20s`)
- split by `map`, `T/CT side`, and `economy`

Use this as the default playbook when asked for this analysis again.

---

## 1) Data Source Rules

- Primary source: **Valolytics API**
- Auth header: `x-api-key` (read from `API_REFERENCE.md`)
- Do not use Liquipedia for kill-coordinate truth

Relevant endpoints:

- `GET /api/riot/match/v1/matchlists/by-puuid/esports/{puuid}`
- `GET /api/matches/esports/{matchId}`

---

## 2) Team Discovery

1. Find one seed `puuid` for the team (from local raw cache if available, e.g. names starting with `ECO `).
2. Pull match history for that seed player.
3. Fetch match details for recent match IDs.
4. Keep only matches where the target team appears.

Team detection convention:

- Target team players identified by prefix (example: `ECO `)
- Team side in match identified by `teamId` of those players
- Opponent short tag inferred from opposing player name prefix

---

## 3) Series Scope (Last N Series)

Definition used:

- One series key = `(date, opponent_prefix)`
- Date derived from `gameStartMillis` in local timezone display
- Series recency based on latest map timestamp in that series

Workflow:

1. Group all candidate maps by `(date, opponent)`
2. Sort groups by latest timestamp descending
3. Keep first `N` groups (example: `N=8`)
4. Analyze all maps that belong to those selected groups

---

## 4) First-Kill Event Extraction

For each selected map:

1. Iterate each round in `roundResults`
2. Build the round's first-kill event:
   - earliest `timeSinceRoundStartMillis` across all `playerStats[].kills[]`
3. Keep event only if:
   - killer belongs to target team
   - `timeSinceRoundStartMillis <= threshold` (example `20000`)

Round-time filter:

- Threshold is milliseconds
- `20000` means first 20 seconds

---

## 5) Side + Economy Classification

Use existing project logic for consistency:

- `get_team_side_per_round(...)` from `lib/stats_engine.py`
- `classify_round_economy(...)` from `lib/stats_engine.py`

Mapping:

- side result `'atk'` => `T`
- side result `'def'` => `CT`

Economy outputs used directly:

- `pistol`
- `antieco`
- `eco`
- `force`
- `gun`

---

## 6) Coordinate Extraction

For each qualifying first-kill event, store:

- killer raw world location:
  - from `first_kill.playerLocations[]` entry where `puuid == killer`
  - fields: `killerX`, `killerY`
- victim raw world location:
  - from `first_kill.victimLocation`
  - fields: `victimX`, `victimY`

If killer location snapshot is missing, keep event but set killer coords to `null`.

---

## 7) Required Output Schema

Per event row:

- `date`
- `opponent`
- `matchId`
- `map`
- `round`
- `timeSinceRoundStartMillis`
- `side` (`T`/`CT`)
- `economy`
- `killer`
- `victim`
- `killerX`, `killerY`
- `victimX`, `victimY`

Summary:

- selected series list
- total qualifying events
- grouped counts by `(map, side, economy)`

---

## 8) Grouping Format We Used

For reporting counts:

- group key: `(map, side, economy)`
- measure: count of qualifying first-kill events

This is the exact format requested in:

- "sort them by map, T/CT-Side and Economy"

---

## 9) Map Plotting (Optional)

When asked for a screenshot of first-kill location:

1. Use Riot display icon map asset (`veto-history-site/maps/{Map}.png`)
2. Use map transform constants (if plotting normalized point):
   - for example in `scripts/export_map_info_data.py`
3. Draw marker on map image and export PNG

Important renderer pitfall we hit:

- Dot placement must align with the **contained image frame**, not the full canvas area.

---

## 10) Known Pitfalls / Checks

- Do not trust local stale raw cache for "recent match" queries without validating date/opponent.
- Match history may include missing/unavailable match IDs; skip safely.
- Some maps/events may have incomplete `playerLocations` snapshots.
- Always verify target match by:
  - date
  - map
  - both team prefixes present

Quick sanity checks before final answer:

1. Do grouped totals sum to `total qualifying events`?
2. Are all rows within the requested series scope?
3. Are all rows `<= time threshold`?
4. Are coordinates present for both killer and victim where available?

---

## 11) Reusable Command Pattern

When re-running this process, do:

1. Pull recent matches for team seed `puuid`
2. Build last-`N` series set
3. Filter first kills by `<= threshold`
4. Add side + economy via `lib/stats_engine.py`
5. Export detailed rows JSON (or CSV) + grouped summary

Current reference export file example:

- `eco_last8_fk_lte20_with_coords.json`

