"""Build the Veto view data (data.js) for the site teams from scraped VLR matches.

VLR veto line, e.g.:
  "SGE ban Sunset; JL ban Haven; SGE pick Summit; JL pick Abyss; SGE ban Ascent; JL ban Split; Lotus remains"
Only the standard Bo3 pattern (ban, ban, pick, pick, ban, ban, remains) fits the site's table;
other formats (Bo1 multi-ban, Bo5) are reported and skipped.

Usage: python scripts/live/build_vetoes.py
Writes veto-history-site-publish/data.js (vetoHistoryData) and empties extra-data.js (extraVetoHistoryData).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import VLR_DIR, norm  # noqa: E402
from site_config import PUBLISH_DIR, TEAMS  # noqa: E402
from core import core_info, passes  # noqa: E402

PATTERN = ["ban", "ban", "pick", "pick", "ban", "ban"]
SLOTS = ["ban1", "ban2", "pick1", "pick2", "ban3", "ban4"]


def parse_veto(text):
    steps, remains = [], None
    for part in [p.strip() for p in text.split(";") if p.strip()]:
        m = re.match(r"^(.*)\s+(ban|pick)\s+(\S+)$", part)
        if m:
            steps.append((m.group(1).strip(), m.group(2), m.group(3)))
            continue
        m = re.match(r"^(\S+)\s+remains$", part)
        if m:
            remains = m.group(1)
    return steps, remains


def build_team(key, cfg):
    path = os.path.join(VLR_DIR, f"{cfg['prefix']}.json")
    vlr = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"matches": []}
    info = core_info(cfg["prefix"])
    tag = cfg["tag"]
    rows, skipped = [], []
    for m in vlr["matches"]:
        if not cfg.get("ignore_core") and not any(passes(info, mp["gameId"], m.get("listDate")) for mp in m["maps"]):
            continue   # baseline-core / date rule: veto only from matches the core played
        own_name, opp_name = m["listTeams"][0], m["listTeams"][1]
        opp_tag = m["listTags"][1] if len(m.get("listTags", [])) > 1 else opp_name[:4].upper()
        if not m.get("veto"):
            skipped.append((m["listDate"], opp_name, "no veto on VLR"))
            continue
        steps, remains = parse_veto(m["veto"][0])
        if [s[1] for s in steps] != PATTERN or not remains:
            skipped.append((m["listDate"], opp_name, f"not Bo3 format ({len(steps)} steps)"))
            continue
        own_tokens = {norm(tag), norm(own_name), norm(m["listTags"][0])}
        scores = {}
        for mp in m["maps"]:
            own_idx = 0 if norm(mp["teams"][0]) == norm(own_name) else 1
            scores[mp["map"]] = f'{mp["score"][own_idx]}:{mp["score"][1 - own_idx]}'
        row = {
            "date": m["listDate"], "opponent": opp_name, "opponentAbbr": opp_tag,
            "score": f'{m["result"][0]} - {m["result"][1]}' if len(m["result"]) == 2 else "",
            "source": "https://www.vlr.gg" + m["url"], "event": m.get("event", ""),
            "decider": remains, "deciderScore": scores.get(remains, ""), "deciderLabel": "DECIDER",
            "deciderTeamStartSide": "",
        }
        for slot, (who, kind, mp) in zip(SLOTS, steps):
            is_team = norm(who) in own_tokens
            label = tag if is_team else opp_tag
            entry = {"map": mp, "type": kind, "ownerLabel": label, "ownerKind": "team" if is_team else "opp"}
            if kind == "pick":
                entry.update({"score": scores.get(mp, ""), "pickLabel": f"{tag} PICK" if is_team else "OPPONENT PICK",
                              "teamStartSide": ""})
            row[slot] = entry
        rows.append(row)
    sub = (f"Old roster — official vetoes since {cfg['min_date']} (VLR)" if cfg.get("ignore_core")
           else "VCT 2027 Kickoff prep — official vetoes since 2026-09-01 (VLR)")
    return {"name": cfg["name"], "ownerLabel": tag, "subtitle": sub,
            "rows": rows}, skipped


def _local_games(ids):
    """Map-game details for the given Riot match ids from local data only (cache + raw JSONL)."""
    from common import ROOT
    games, want = {}, set(ids)
    cache = os.path.join(ROOT, "data", "cache", "esports_matches")
    for mid in want:
        p = os.path.join(cache, f"{mid}.json")
        if os.path.exists(p):
            games[mid] = json.load(open(p, encoding="utf-8"))
    missing = want - set(games)
    if missing:
        for folder in (os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "archive", "data", "raw")):
            for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                if not fn.endswith(".jsonl"):
                    continue
                for line in open(os.path.join(folder, fn), encoding="utf-8"):
                    m = re.search(r'"matchId":\s*"([0-9a-f\-]{36})"', line[:4000])
                    if m and m.group(1) in missing:
                        games[m.group(1)] = json.loads(line)
                        missing.discard(m.group(1))
    return games


def _map_scores(game_ids, games, tag, opp_tag):
    """{map name: 'own:opp'} for one series; own side = players named '<tag> ...'."""
    scores = {}
    for gid in game_ids:
        g = games.get(gid)
        if not g:
            continue
        sides = {}
        for p in g.get("players", []):
            prefix = (p.get("gameName") or "").split(" ")[0].upper()
            sides.setdefault(p.get("teamId"), set()).add(prefix)
        own = next((t for t, pre in sides.items() if tag.upper() in pre), None)
        if own is None:
            opp = next((t for t, pre in sides.items() if opp_tag.upper() in pre), None)
            own = {"Red": "Blue", "Blue": "Red"}.get(opp)
        won = {t["teamId"]: t.get("roundsWon") for t in g.get("teams", [])}
        if own in won:
            other = "Blue" if own == "Red" else "Red"
            scores[g["matchInfo"]["map"]] = f"{won[own]}:{won.get(other)}"
    return scores


def build_team_liquipedia(cfg):
    """Rows from scripts/fetch_liquipedia_team_vetoes.py output (any format: Bo2/Bo3/Bo5).

    Steps fill the six slots in chronological order; each cell renders by its own type, so a Bo5's
    picks 3+4 sit in the 'Ban 3/4' columns and a Bo2's bans 3+4 in 'Pick 1/2' (row shows the format).
    """
    src = json.load(open(cfg["liquipedia_vetoes"], encoding="utf-8"))
    tag = cfg["tag"]
    games = _local_games([i for r in src if r["veto"] for i in r["veto"].get("mapIds", [])])
    rows, skipped = [], []
    for r in src:
        v = r["veto"]
        if not v or v["focusSlot"] is None:
            skipped.append((r["date"], r["opponentAbbr"], "no veto on Liquipedia" if not v else "team not found"))
            continue
        opp_tag = r["opponentAbbr"]
        scores = _map_scores(v.get("mapIds", []), games, tag, opp_tag)
        steps = [s for s in v["steps"] if s["action"] in ("ban", "pick")]
        n_picks = sum(s["action"] == "pick" for s in steps)
        decider = v["decider"]
        label = "DECIDER"
        if not decider:
            left = [m for m in r.get("mapPool", []) if m not in {s["map"] for s in steps}]
            decider = left[0] if len(left) == 1 else "-"
            label = "REMAINING"
        # Maps played = picks then decider, cut to the number of maps in the series score (e.g. 2:1 -> 3).
        # Works without per-map scores (not every game is in local data); None for forfeits etc.
        try:
            n_played = sum(int(x) for x in r["score"].split(":"))
        except ValueError:
            n_played = None
        order = [s["map"] for s in steps if s["action"] == "pick"] + ([v["decider"]] if v["decider"] else [])
        played = order[:n_played] if n_played is not None else None
        row = {
            "date": r["date"], "opponent": r["opponent"], "opponentAbbr": opp_tag,
            "score": r["score"].replace(":", " - "),
            "source": f"https://liquipedia.net/valorant/{r['matchPage']}", "sourceLabel": "liquipedia",
            "event": r["tournament"], "format": f"Bo{n_picks + (1 if v['decider'] else 0)}",
            "mapPool": r.get("mapPool", []), "mapPoolNote": r.get("mapPoolNote", ""),
            "mapPoolSource": r.get("mapPoolSource", ""),
            "decider": decider, "deciderScore": scores.get(decider, "") if v["decider"] else "",
            "deciderLabel": label, "deciderTeamStartSide": "",
        }
        if played is not None:
            row["playedMaps"] = played
            row["deciderPlayed"] = bool(v["decider"]) and v["decider"] in played
        for slot, s in zip(SLOTS, steps):
            is_team = s["by"] == "team"
            entry = {"map": s["map"], "type": s["action"], "ownerLabel": tag if is_team else opp_tag,
                     "ownerKind": "team" if is_team else "opp"}
            if s["action"] == "pick":
                entry.update({"score": scores.get(s["map"], ""),
                              "pickLabel": f"{tag} PICK" if is_team else "OPPONENT PICK", "teamStartSide": ""})
            row[slot] = entry
        if len(steps) > len(SLOTS):
            skipped.append((r["date"], opp_tag, f"{len(steps)} steps, only {len(SLOTS)} shown"))
        rows.append(row)
    return {"name": cfg["name"], "ownerLabel": tag, "subtitle": cfg.get("veto_subtitle", "Official vetoes (Liquipedia)"),
            "rows": rows}, skipped


MANUAL_VETOES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_vetoes.json")


def _flip(r, src_cfg):
    """The same manual veto seen from the opponent's side (for opponents that are site teams)."""
    flip = {"team": "opp", "opp": "team"}
    a, b = r["score"].split(" - ")
    return {**r, "opponent": src_cfg["name"], "opponentAbbr": src_cfg["tag"], "score": f"{b} - {a}",
            "steps": [[flip[w], k, m] for w, k, m in r["steps"]],
            "scores": {m: ":".join(s.split(":")[::-1]) for m, s in r["scores"].items()}}


def manual_rows(key, cfg):
    """Hand-entered vetoes (manual_vetoes.json) for matches VLR does not list.

    A team also gets every manual veto entered under another team whose opponentAbbr is its tag (flipped).
    """
    if not os.path.exists(MANUAL_VETOES):
        return []
    src = json.load(open(MANUAL_VETOES, encoding="utf-8"))
    entries = list(src.get(key, []))
    for other, lst in src.items():
        if other != key and other in TEAMS:
            entries += [_flip(r, TEAMS[other]) for r in lst if r["opponentAbbr"] == cfg["tag"]]
    tag, rows = cfg["tag"], []
    for r in entries:
        row = {"date": r["date"], "opponent": r["opponent"], "opponentAbbr": r["opponentAbbr"],
               "score": r["score"], "source": r.get("source", ""), "sourceLabel": r.get("sourceLabel", "screenshot"),
               "event": r.get("event", ""), "decider": r["decider"],
               "deciderScore": r["scores"].get(r["decider"], ""), "deciderLabel": "DECIDER",
               "deciderTeamStartSide": ""}
        for slot, (who, kind, mp) in zip(SLOTS, r["steps"]):
            is_team = who == "team"
            entry = {"map": mp, "type": kind, "ownerLabel": tag if is_team else r["opponentAbbr"],
                     "ownerKind": "team" if is_team else "opp"}
            if kind == "pick":
                entry.update({"score": r["scores"].get(mp, ""), "pickLabel": f"{tag} PICK" if is_team else "OPPONENT PICK",
                              "teamStartSide": ""})
            row[slot] = entry
        rows.append(row)
    return rows


def merge_manual(team, extra):
    """Add manual rows not already present (same date + opponent), newest first; stable for same-day rows."""
    have = {(r["date"], r["opponent"].lower()) for r in team["rows"]}
    team["rows"] += [r for r in extra if (r["date"], r["opponent"].lower()) not in have]
    team["rows"].sort(key=lambda r: r["date"], reverse=True)


def main():
    data = {}
    for key, cfg in TEAMS.items():
        if cfg.get("liquipedia_vetoes") and os.path.exists(cfg["liquipedia_vetoes"]):
            data[key], skipped = build_team_liquipedia(cfg)
        else:
            data[key], skipped = build_team(key, cfg)
        merge_manual(data[key], manual_rows(key, cfg))
        print(f"{key:10} vetoes: {len(data[key]['rows'])}" + (f"  skipped: {skipped}" if skipped else ""))
    open(os.path.join(PUBLISH_DIR, "data.js"), "w", encoding="utf-8").write(
        "const vetoHistoryData = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n")
    open(os.path.join(PUBLISH_DIR, "extra-data.js"), "w", encoding="utf-8").write(
        "// Old-season vetoes archived in archive/site_publish_snapshot_2026-11-22/extra-data.js\nconst extraVetoHistoryData = {};\n")
    print("wrote data.js and extra-data.js")


if __name__ == "__main__":
    main()
