"""Baseline-core rule (Vincent, 2026-11-24).

The baseline core of a team = the five players it used in the VCT 2027 EMEA Kickoff - Europe Open Qualifier
(most frequent five names on the team's side of the VLR scoreboards in those maps).
A game only counts if at least MIN_CORE of those five played it. Everything else is excluded,
even when it is an official game.

Teams without Open Qualifier games (the invited teams) have no derived core: core_info() returns core=None
and callers keep all games but must flag that the rule could not be applied.
"""
import json
import os
from collections import Counter

from common import VLR_DIR

MIN_CORE = 3
CORE_EVENT = ("Kickoff", "Open Quali")
CUTOFF_DATE = "2026-09-01"   # rule (Vincent, 2026-11-24): never use games before this, even with the core
EXCLUDED_TEAMS = {"cgn"}     # rule (Vincent, 2026-11-24): CGN is not analysed


def _own_tag(vlr):
    c = Counter(m["listTags"][0] for m in vlr["matches"] if m.get("listTags"))
    return c.most_common(1)[0][0] if c else None


# Invited teams never played the Open Qualifier: their baseline core is the Liquipedia Kickoff roster
# (VLR scoreboard spellings: Indra = xserten, sizo = sizovskyy, Darxcioo = Darxcio). Eintracht has only 3 listed players.
ROSTER_CORE = {
    "sge": ["azury", "musashi", "Fizzy"],
    "mir": ["Bishepss", "reblyik", "innersavage", "kospa1n", "Indra"],
    "jl": ["westside", "WanZeru", "Sevire", "hoody", "al0rante"],
    "nvj": ["avey", "Darxcioo", "Javelin", "Kolosha", "sizo"],
    "gx": ["globeX", "sickrey", "Vitie", "WACKIE", "ZachKappa"],
    "ucam": ["BULD", "Filu", "Flickless", "kamyk", "waddle"],
    "mdr": ["Veqaj", "starxo", "runneR", "Kicks", "MiniBoo"],
    # Enterprise: the five who played every Qualifier Playoffs map (VLR, 2026-11-25/26); added 2026-11-27
    "ep": ["sh1n", "rexxtoned", "iluri", "koshmaras", "stonezy"],
}


def core_info(prefix):
    """Return {'tag', 'core' (list|None), 'coreSource', 'coreMaps', 'byGame' {gameId: n_core_players}}."""
    path = os.path.join(VLR_DIR, f"{prefix}.json")
    vlr = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"matches": []}
    tag = _own_tag(vlr)
    oq = [mp for m in vlr["matches"] if all(k in m.get("event", "") for k in CORE_EVENT) for mp in m["maps"]]
    names = Counter(p["name"] for mp in oq for p in mp["players"] if p["teamTag"] == tag)
    core = [n for n, _ in names.most_common(5)] if oq else ROSTER_CORE.get(prefix)
    source = "Kickoff Open Qualifier" if oq else ("Liquipedia Kickoff roster" if core else None)
    by_game = {}
    for m in vlr["matches"]:
        for mp in m["maps"]:
            own = [p["name"] for p in mp["players"] if p["teamTag"] == tag]
            by_game[mp["gameId"]] = sum(n in core for n in own) if core else None
    return {"tag": tag, "core": core, "coreSource": source, "coreMaps": len(oq), "byGame": by_game}


def passes(info, game_id, date=None):
    """True if the game is on/after CUTOFF_DATE and has >= MIN_CORE core players (or no core could be derived)."""
    if date and date < CUTOFF_DATE:
        return False
    if not info["core"]:
        return True
    return (info["byGame"].get(game_id) or 0) >= min(MIN_CORE, len(info["core"]))
