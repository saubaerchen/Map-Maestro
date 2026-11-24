# Advanced Veto Architect — Conditional Pattern Method

How the conditional behaviours (e.g. *"foe with a sniper on Split CT plays B; without one, A"*) were found,
which conditions exist in the data, and how the data sources connect to produce and prove them.

- **Status:** prototype, built and tested on **Eintracht Frankfurt only** (13 official maps since 2026-09-01, 278 rounds), 2026-11-23.
- **Prototype code:** `prototypes/sge_pattern_prototypes/` (`compute.py`, `conditions.py`, `build.py`, `serve.py`)
- **Live views:** `python prototypes/sge_pattern_prototypes/serve.py`, then **:4188** (all conditional findings) and **:4189** (the 8 behaviours with overlay and full evidence)

---

## 1. The idea in one paragraph

A scouting dot map shows *where* a team plays. A conditional pattern says **under which measurable circumstance** a player or the team plays somewhere else. We take every round, describe it with facts that are knowable at round start (weapons, both teams' economy, score, previous round, agent), record where each player stood when the round's first fight happened, and then test, condition by condition, whether the position changes. A change only counts if it is large, has enough rounds behind it, and passes a significance test. Every claim stays linked to the exact rounds that prove it.

---

## 2. Data sources and how they connect

```
VLR.gg (official matches, vetoes, per-map K/D/A)
        │  date + map + round score + K/D/A match
        ▼
Valolytics main-account API  ──►  data/cache/matches/{matchId}.json   (raw, unmodified)
        │  scripts/live/prepare_site_data.py  (players renamed "SGE <pro name>" via registry)
        ▼
data/site/sge_2026_raw_responses.jsonl   (official games only)
        │  prototypes/.../compute.py
        ▼
Round model (one record per round, section 3)  ◄── valorant-api.com: map transforms, callouts, weapons
        │  conditions.py
        ▼
Findings (condition → outcome, counts, p, q, evidence round keys)  →  pages :4188 / :4189
```

| Source | What it gives | Join key |
|---|---|---|
| **VLR.gg** (`data/registry/vlr/sge.json`) | which games are official, event, opponent, veto, per-map score and per-player K/D/A | date (±1 day) + map + round score + K/D/A |
| **Valolytics main accounts** (`/europe/` account, `/eu/` matchlist + detail) | every round: kills with `playerLocations` (all alive players' x/y at that moment), `victimLocation`, weapon used, per-player economy (`loadoutValue`, `weapon`), plant site/time/location, planter, winning team | `matchId`, `roundNum`, `puuid` |
| **Registry** (`data/registry/teams.json`) | PUUID → pro name and team (accounts are confirmed by K/D/A against VLR) | `puuid` |
| **valorant-api.com** (`maps_api_cache.json`, `weapons_cache.json`) | map coordinate transforms, **callouts** (named points with world x/y, grouped into A/B/C/Mid/spawns), weapon names and categories (Rifle, Sniper, SMG…) | map name, weapon UUID |
| **`lib/stats_engine.get_team_side_per_round`** | whether SGE attack or defend in each round (via the planter's team, halves and overtime) | round list + team PUUIDs |

**Evidence key:** every finding stores the rounds it is based on as `"{matchId}|{round}"`. The overlay uses these keys to show each round, highlight it on the map, and list all five positions. Nothing is aggregated without keeping its evidence.

---

## 3. The round model (built in `compute.py`)

One record per round, from SGE's perspective:

| Field | Meaning | Derived from |
|---|---|---|
| `map`, `side` (CT/T), `round`, `half` | context | matchInfo + side detection |
| `won` | did SGE win the round | `winningTeam` |
| `tier` | SGE buy: pistol (rounds 1 and 13), eco (<2000 avg loadout), force (<3800), full | avg `economy.loadoutValue` of SGE players |
| `oppTier`, `oppAvg` | **enemy** buy, same thresholds | avg loadout of the other team |
| `weapons`, `wcat` | each SGE player's primary weapon and its category | `economy.weapon` → weapons cache |
| `oppSnipers` | number of enemy players with a sniper | enemy `economy.weapon` |
| `agentNames` | agent each SGE player is on | `characterId` → `lib.constants.AGENT_MAP` |
| `scoreBefore` | score at round start | running count |
| `ctx` | pistol / after win / after loss | previous round result |
| `prevPlant`, `prevSameSideWon` | previous round **on the same side**: where the bomb was planted, and whether that round was won | previous round record |
| `plantSite`, `plantT`, `plantXY` | plant site, time in seconds, location on the map | `plantSite`, `plantRoundTime`, `plantLocation` |
| `fk` | first kill: time, killer, victim, both callouts, whether SGE won it, whether an SGE first death was traded within 5s | earliest kill of the round |
| `snap` | **position snapshot**: each SGE player's position at the first kill (alive players plus the victim), with map position, **callout** (nearest named point) and **zone** (A/B/C/Mid/CT Spawn/T Spawn) | first kill's `playerLocations` + callouts |
| `fkT` | time of the first kill | first kill |

### Why positions come from the first kill
The API has no continuous movement data. Positions exist only at moments when something happens (every kill, the plant, the defuse). The first kill is the earliest snapshot in a round, so it is the closest thing to "the setup".

### The 35-second rule
If the first kill happens late (e.g. at 0:55), players have already rotated, so the snapshot no longer shows the setup. **Position-based findings only use rounds whose first kill is within 35 seconds.** On Split CT that keeps 25 of 35 rounds. Plant-based findings use all rounds.

### Callouts and zones
Every position is mapped to the **nearest valorant-api.com callout** by world distance, e.g. `B Back`, `Mid Vent`, `A Main`. The callout's group gives the zone (A, B, C, Mid, CT Spawn, T Spawn). On CT, being at a `Lobby`, `Main` or `T Spawn` callout counts as **forward** (attacker space).

---

## 4. Conditions (the "when …")

All are knowable at or before round start, so they work as scouting cues.

| Group | Conditions |
|---|---|
| **Own weapon** | player has a sniper (Operator/Marshal/Outlaw) · player has the Operator · player on SMG/shotgun |
| **Team weapon** | a teammate has the Operator · SGE have an Operator |
| **Own economy** | SGE pistol / eco / force / full buy |
| **Enemy economy** | enemy pistol / eco / force / full buy · enemy has a sniper |
| **Round flow** | after a win · after a loss · won/lost the previous round on this side |
| **Score** | SGE leading · trailing · tied |
| **Time** | 1st half · 2nd half · overtime |
| **Agent** | player on agent X (only when they played 2+ agents on that map) |
| **Previous round, same side** | attackers planted X (on CT) · SGE planted X (on T) · after a **successful** / **failed** hit on X (on T) |

## 5. Outcomes (the "… they do Y")

| Level | Outcome | Rounds used |
|---|---|---|
| Player | plays zone A / B / C / Mid | early rounds (first kill ≤35s) where the player is in the snapshot |
| Player | plays forward (attacker space) — CT only | same |
| Team, CT | 3+ players stacked in one zone | early rounds |
| Team, T | plants A / B / C (of planted rounds) · no plant · hits the same site as the previous T round | all T rounds |

---

## 6. How a finding is decided (`conditions.py`)

For every **map × side × subject (player or team) × outcome × condition**:

1. **Split** the eligible rounds into *in condition* and *not in condition*.
2. **Count** how often the outcome happens in each group → a 2×2 table.
3. **Minimum support:** at least 3 rounds in each group.
4. **Minimum effect:** the outcome rate must differ by **≥30 percentage points** (e.g. 53% vs 10%).
5. **Significance:** Fisher's exact test (suited to small samples). Kept if **p ≤ 0.15**; shown by default at **p ≤ 0.05**.
6. **Mirror de-duplication:** conditions that split the rounds the same way ("after a win" = "won previous round on this side", "1st half" vs "2nd half", "Omen" vs "Harbor") are merged into one finding.
7. **Multiple-testing correction:** about 2,600 unique tests were run, so some p<0.05 results are luck. Benjamini–Hochberg **q-values** are computed over all tests. A finding is **strong** only if q ≤ 0.10, **lean** if p ≤ 0.05.
8. **Corroboration:** findings on the same map, side and condition where **2+ subjects** shift in the same direction are grouped as a *corroborated pattern* (e.g. three players all avoid A after a won B hit). This is the most useful signal at small sample sizes. Caveat: players moving together in the same rounds reflect **one team decision**, not independent proof.

### Reading a finding
`foe plays B much more when foe has a sniper: 8/15 (53%) vs 1/10 (10%) otherwise · p=0.040`
→ in 15 early Split CT rounds with a sniper foe was on B 8 times; in 10 rounds without a sniper, once.

---

## 7. The 8 behaviours found for Eintracht

The definitions are explicit and auditable in `prototypes/sge_pattern_prototypes/build.py` (`PAGES["9_explained"]`, array `B`).

| # | Map / side | Condition → behaviour | With | Without |
|---|---|---|---|---|
| 1 | Split CT | **foe has a sniper** → foe plays **B** (otherwise Mid); without one foe plays **A** (7/10) | 8/15 on B | 1/10 on B |
| 2 | Ascent CT | **SGE eco** → foe, musashi, azury, H1ber play **forward** | 3/3 (foe) | 2/17 |
| 3 | Split T | **after a successful B hit** → foe, musashi, H1ber **avoid A** | 0/8 (foe) | 13/21 |
| 4 | Split T | **previous T round planted A** → foe, musashi, H1ber **play A again** | 9/12 (foe) | 4/17 |
| 5 | Ascent T | **enemy has a sniper** → Fizzy, azury, foe shift to **A**, avoid Mid | 4/8 (Fizzy on A) | 0/6 |
| 6 | Lotus T | **enemy force buy** → SGE **plant B** | 6/9 | 1/14 |
| 7 | Split CT | **enemy force buy** → **3-man B stack** | 3/4 | 0/21 |
| 8 | Lotus CT | **Fizzy's agent**: Omen → **A**, Harbor → **B** | 12/19 on A | 1/10 on A |

Only one finding survives the strict q ≤ 0.10 correction on its own: *SGE never plant on ecos (Split, 6/6)*. The eight above are **leads**, chosen because they are large, logical and mostly corroborated across players.

**Example of what the evidence view adds:** in behaviour 6, one "B hit" round (vs HABO, R19) has all five players at **C Mound at 0:29** and the plant on **B at 1:34**: a C fake into B, which no aggregate count shows.

---

## 8. Limitations — read before acting on a finding

- **Small samples.** 1–4 maps per map name for Eintracht. Treat findings as leans to check in VODs, not rules.
- **Confounding.** Conditions overlap: *enemy has a sniper* ≈ *enemy full buy*; *player has a sniper* ≈ *own full buy*; *2nd half* can simply mean *a different game*. Two findings may be the same effect.
- **One snapshot per round.** Positions are only known at kill moments. Utility usage is not available (ability effects are empty in the API).
- **Callout = nearest point.** A player standing between two areas can get the neighbouring name.
- **Official games only.** Scrims and warm-ups are excluded by design. Events played on Riot tournament servers under unknown account names (e.g. Monsters Reloaded) are missing.
- **Overstatement risk.** Wording must follow the evidence. Behaviour 1 was first written as "with a sniper foe plays B"; the evidence showed Mid 4 of 15 times, so it was corrected. Always check a claim against its evidence tab.

---

## 9. Reproduce / extend to another team

1. Make sure the team's official games are in `data/site/{prefix}_2026_raw_responses.jsonl` (main-account workflow: `scripts/live/vlr_matches.py` → `discover_accounts.py` → `fetch_official_games.py` → `prepare_site_data.py`).
2. In `compute.py` change `TAG` and `JSONL` (and `VLR`) to the team; in `conditions.py` and `build.py` (`COLORS`) set the team's players.
3. `python prototypes/sge_pattern_prototypes/conditions.py` prints all findings with p and q.
4. `python prototypes/sge_pattern_prototypes/serve.py` serves the views; :4188 lists findings, :4189 explains curated behaviours.
5. To add a curated behaviour, add an entry to the `B` array (condition function, outcome function, labels, plain-language read). Counts, maps and evidence are generated from it.

**Recommended next step:** run this on a team with a larger sample (Barça 32 maps, WIP 29, MIR 27). More rounds turn leads into conclusions that survive the correction, which is the real test of whether this belongs in VETO_ARCHITECT.

### Ideas not yet implemented
- Conditions: man-advantage after the first kill, timeout called, opponent identity, utility count.
- Outcomes: OP position and angle, time of the first fight per zone, retake vs save after plant.
- A second snapshot per round (e.g. the first kill after 20s) to see setup → rotation.
