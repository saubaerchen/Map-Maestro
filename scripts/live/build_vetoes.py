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
        if not any(passes(info, mp["gameId"], m.get("listDate")) for mp in m["maps"]):
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
    return {"name": cfg["name"], "ownerLabel": tag, "subtitle": "VCT 2027 Kickoff prep — official vetoes since 2026-09-01 (VLR)",
            "rows": rows}, skipped


def main():
    data = {}
    for key, cfg in TEAMS.items():
        data[key], skipped = build_team(key, cfg)
        print(f"{key:10} vetoes: {len(data[key]['rows'])}" + (f"  skipped: {skipped}" if skipped else ""))
    open(os.path.join(PUBLISH_DIR, "data.js"), "w", encoding="utf-8").write(
        "const vetoHistoryData = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n")
    open(os.path.join(PUBLISH_DIR, "extra-data.js"), "w", encoding="utf-8").write(
        "// Old-season vetoes archived in archive/site_publish_snapshot_2026-11-22/extra-data.js\nconst extraVetoHistoryData = {};\n")
    print("wrote data.js and extra-data.js")


if __name__ == "__main__":
    main()
