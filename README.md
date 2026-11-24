# Map Maestro — VETO_ARCHITECT

Valorant scouting site for the **VCT 2027 EMEA Kickoff – Europe** qualifier field (15 teams).

**Site:** https://saubaerchen.github.io/Map-Maestro/

- **Veto** view: official vetoes (from VLR where recorded).
- **Map-Info** view: per team / map / side — positions at first kill, sniper kills, all first kills, map control, rotations, retake / post-plant, with economy and plant-site filters.

## What data is used
- Official games only (matched against VLR), from **2026-09-01** onwards.
- Only games played by the team's **baseline core** (its five players in the Kickoff Open Qualifier, or the Liquipedia Kickoff roster for invited teams): at least 3 of 5 must play.

## Repo layout
| Path | Content |
|---|---|
| `veto-history-site-publish/` | the static site (deployed by `.github/workflows/pages.yml`) |
| `scripts/live/` | new-season pipeline: VLR scrape → account discovery → official games → site build |
| `scripts/` , `lib/` | analysis / bundle scripts and shared helpers |
| `prototypes/` | throwaway pattern-recognition prototypes |
| `Advanced Veto Architect/` | method notes for conditional pattern analysis |

Raw match data, the API key and players' account mapping are kept locally and are **not** part of this repo.
