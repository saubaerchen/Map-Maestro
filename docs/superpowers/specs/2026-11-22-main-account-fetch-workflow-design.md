# Main-Account Fetch Workflow — Design

Date: 2026-11-22 · Status: draft for Vincent's approval

## Why

The Valolytics **esports** route (`/esports/` matchlists) stops at Jul/Aug 2026 for every player checked, so it can't feed the new season. Players' **main accounts** (`/europe/` account, `/eu/` matchlist and detail) are current to the day. Official third-party and open-qualifier games show up there as custom games (`queueId ''`) with full round, position and economy data. This was proven twice:
- Barça: 32/32 Kickoff Open Qualifier maps
- Eintracht: 13/13 Project Blender maps

In both cases date, map, round score and all 5 players' K/D/A matched VLR exactly.

Goal: a repeatable workflow that turns "team X" into a verified roster of main accounts plus a JSONL of **official games only**, ready for the Map-Info pipeline.

## Scope

- **In:** roster discovery, account verification, fetching official games, the team registry, the coverage report.
- **Out (separate later work):** rebuilding `TEAMS_CONFIG`, generalising the per-team analysis/build scripts, map images and transforms for Summit/Sunset/Abyss/Corrode.
- **Anti-goals:**
  - Scrims or warm-ups in the data (they distort scouting and aren't official).
  - Accounts assigned to a player without proof.
  - Any team's data written into another team's file.

## Approaches considered

1. **One script that does everything per team.** Simple to call, but discovery and verification need judgement (name changes, old tags, missing VLR games), and a single script hides those decisions.
2. **Registry + two steps (chosen):**
   - a *discover/verify* step builds and updates a team registry (who is who, with evidence);
   - a *fetch* step reads only confirmed accounts and writes official games.

   Each step is re-runnable, and Vincent can review the registry between them.
3. **Manual per team (what we did today).** Works but doesn't scale to 15 teams, and the evidence gets lost in chat.

Chosen: **2**, because verification needs to be reviewable and repeatable, and the registry builds up over time (opponents seen in one team's games seed the next team).

## The workflow

### Step 0 — Roster (source: Liquipedia)
Read the event's participant list through the Liquipedia API (`api.php?action=parse&prop=wikitext`; the HTML page returns 403). Store the pro names per team. Current list: `KICKOFF_2027_EUROPE_ROSTERS.md`.

### Step 1 — Official matches (source: VLR)
For each team, from `vlr.gg/team/matches/{id}/{slug}`, store every match since the cutoff (default **2026-09-01**):
- event, date, opponent
- every map with its round score
- each player's per-map agent and K/D/A on both teams
- the veto, if shown

VLR times are CET/CEST; match dates allow ±1 day against UTC.

### Step 2 — Seed account
We need one main Riot ID on the team. In order of preference:
1. **The registry already has one**: e.g. a team's player appeared as an opponent in another team's confirmed official game.
2. **Lobby scan**: search the ranked lobbies of known accounts for current roster names or team tags (e.g. `TAG player#tag`). This only produces a *candidate*.
3. **Vincent supplies a tracker.gg link.**

Deathmatch details return 404, so the lobby scan reads ranked games only.

### Step 3 — Pull customs
Get the seed's main-account match list. Download every custom game since the cutoff. Ignore deathmatch, ranked and other queue types.

### Step 4 — Match against VLR
A custom game counts as **official** when all of these hold:
- the date is within ±1 day of a VLR match;
- `matchInfo.map` equals the VLR map name;
- the round score is the same;
- all 5 players on the seed's side have K/D/A equal to the 5 VLR rows for that map.

If all five rows match, the account→pro-name mapping is proven for all five. The opponent's 5 rows are matched the same way, which confirms the opponent team's accounts too.

Customs that don't match (scrims, one-round warm-ups, aborted games) are **dropped**.

### Step 5 — Registry update
Write to `data/registry/teams.json`. For each team: name, VLR id, Liquipedia roster, and for each player:
- pro name, main Riot ID, PUUID
- status: `confirmed` (K/D/A matched on at least one official map) or `candidate` (lobby scan only)
- evidence: matchId and VLR match URL

Accounts are keyed by PUUID, because Riot IDs change (a player's account can be renamed when they change teams, e.g. `OLDTAG name#tag` → `NEWTAG othername#tag`). Opponents confirmed in step 4 are added under their own team.

### Step 6 — Fetch and write official games
For each team, collect the official games found from **all** confirmed accounts on the team (one account can miss games played on another account). Deduplicate by matchId. Append to `data/raw/{prefix}_2026_raw_responses.jsonl` (same naming the existing pipeline reads). Only official, VLR-matched games are written. Each line is the unmodified API response.

### Step 7 — Coverage report
Print and save to `data/registry/coverage_{prefix}.md`:
- VLR maps found vs missing. Missing usually means the game was on a tournament server or another account (e.g. SGE vs SAMCRO, 16 Sep).
- Per-map counts, split into *in the active pool* and *not in the pool*.
- The lineup in each game (roster changes show up here; e.g. H1ber moved from SGE to F9).

## Rules carried over
- Headers on every call: `x-api-key`, `Accept: application/json`, `User-Agent: curl/8.0.0`.
- Rate limit 100: about 3s between calls; wait 60s on 429; 404s count against the limit.
- Use `matchInfo.map`, never `mapId`.
- Write only to the named team's files.
- Liquipedia: identify with a generic User-Agent, no personal details; respect its API rate limits.

## Files
- `scripts/live/vlr_matches.py`: step 1 (VLR scrape → `data/registry/vlr/{prefix}.json`)
- `scripts/live/discover_accounts.py`: steps 2–5 (seed → customs → match → registry)
- `scripts/live/fetch_official_games.py`: steps 6–7 (registry → raw JSONL + coverage)
- `data/registry/teams.json`: the registry
- `data/staging/`: the already-confirmed Barça and Eintracht games are imported on the first run

## Left to the builder
- How VLR HTML is parsed. Per-map stat cells pack All/Attack/Defend values together. Check that All = Attack + Defend for K/D/A.
- Caching downloaded match details so reruns don't call the API again.

## Open (for later designs, not this one)
- Rebuilding `TEAMS_CONFIG` from the registry.
- Generalising the analysis and build scripts so they're not per-team.
- Whether customs played with the full lineup but missing from VLR (likely scrims) should ever be used, e.g. for lineup detection only. Current rule: never written to the data files.
