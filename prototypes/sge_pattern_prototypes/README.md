# PROTOTYPE — throwaway (2026-11-22)

Seven pattern-recognition feature tests built on **Eintracht Frankfurt data only**
(13 official maps since 2026-09-01, `data/site/sge_2026_raw_responses.jsonl`; vetoes from `data/registry/vlr/sge.json`).
Not part of the site. Delete this folder once the features are decided.

Run: `python prototypes/sge_pattern_prototypes/serve.py` (Ctrl+C to stop)

| Port | Feature | Question |
|---|---|---|
| 4181 | Callout translation | Can positions be read as named callouts instead of dots? |
| 4182 | CT setup fingerprints | Does SGE repeat the same defensive spread, and when do they change it? |
| 4183 | Player anchor maps | Who holds the same spot every round, who rotates? |
| 4184 | T-side tendencies by round type | Where/how fast do they hit on pistol/eco/force/full, after wins vs losses? |
| 4185 | Opening-duel profile | Who takes first fights, from where, does it pay off? |
| 4186 | All-games vs last-3 | How different is the picture with every official game vs the site's last-3 window? |
| 4187 | Veto tendencies | First bans, picks, deciders, map records |

Method notes: positions are the snapshot at each round's first kill (all alive SGE players + the victim);
callouts = nearest valorant-api.com callout point; buy type by SGE average loadout (pistol rounds 1/13, eco <2000, force <3800, full).
