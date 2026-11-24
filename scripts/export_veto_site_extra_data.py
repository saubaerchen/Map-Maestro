from __future__ import annotations

import html as html_lib
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "veto-history-site" / "extra-data.js"
PICK_META_OUTPUT = ROOT / "veto-history-site" / "extra-pick-meta.js"
API_KEY_FILE = ROOT / "API_REFERENCE.md"
API_BASE = "https://api.valolytics.gg"

USER_AGENT = "Codex/1.0"

TEAM_CONFIG = {
    "attax": {
        "name": "ALTERNATE aTTaX",
        "ownerLabel": "ATN",
        "subtitle": "2026 raw-order veto history",
        "matches_url": "https://liquipedia.net/valorant/ALTERNATE_aTTaX/Matches",
    },
    "dortmund": {
        "name": "Dortmund eSports",
        "ownerLabel": "DoeS",
        "subtitle": "2026 raw-order veto history",
        "matches_url": "https://liquipedia.net/valorant/Dortmund_eSports/Matches",
    },
}


@dataclass
class MatchRow:
    date: str
    opponent: str
    opponent_abbr: str
    score: str
    link: str


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return match.group(1)


def api_get_json(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse_team_page(url: str) -> list[MatchRow]:
    html = fetch_text(url)
    rows = re.findall(r'<tr class="table2&#95;&#95;row--body.*?</tr>', html, flags=re.S)
    parsed: list[MatchRow] = []
    for row in rows:
        visible_date = re.search(r">([A-Za-z]+ \d{1,2}, 2026)", row)
        if not visible_date:
            continue
        month_name, day, year_str = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})", visible_date.group(1)).groups()
        month_index = {
            "January": 1,
            "February": 2,
            "March": 3,
            "April": 4,
            "May": 5,
            "June": 6,
            "July": 7,
            "August": 8,
            "September": 9,
            "October": 10,
            "November": 11,
            "December": 12,
        }[month_name]
        date = f"{year_str}-{month_index:02d}-{int(day):02d}"
        if not date.startswith("2026-"):
            continue

        score_match = re.search(
            r'<td data-align="center" data-nowrap=""><span(?: style="font-weight:bold")?>(\d+)</span>&#160;&#58;&#160;<span(?: style="font-weight:bold")?>(\d+)</span></td>',
            row,
        )
        if not score_match:
            continue
        score = f"{score_match.group(1)} - {score_match.group(2)}"

        sorts = re.findall(r'data-sort-value="([^"]+)"', row)
        opponent = html_lib.unescape(sorts[-1].strip()) if sorts else ""

        opponent_abbr_matches = re.findall(
            r'<span class="name"[^>]*><a [^>]*>([^<]+)</a></span>',
            row,
        )
        opponent_abbr = html_lib.unescape(opponent_abbr_matches[-1].strip()) if opponent_abbr_matches else opponent

        link_match = re.search(r'href="(/valorant/Match:ID_[^"]+)"', row)
        if not link_match:
            continue

        parsed.append(
            MatchRow(
                date=date,
                opponent=opponent,
                opponent_abbr=opponent_abbr,
                score=score,
                link="https://liquipedia.net" + link_match.group(1),
            )
        )
    return parsed


def extract_map_match_ids(raw: str) -> list[str]:
    map_ids: list[str] = []
    for index in range(1, 6):
        map_block = re.search(rf"(?s)\|map{index}=\{{\{{ApiMap(.*?)\}}\}}", raw)
        if not map_block:
            continue
        block = map_block.group(1)
        match_id = re.search(r"\|matchid=([0-9a-f\-]+)", block)
        finished = re.search(r"\|finished=([^\r\n|}]+)", block)
        if finished and finished.group(1).strip().lower() == "skip":
            continue
        if match_id:
            map_ids.append(match_id.group(1).strip())
    return map_ids


def infer_team_start_side(match_obj: dict, focused_team_id: str) -> str:
    team_puuids = {
        player.get("puuid")
        for player in match_obj.get("players", [])
        if not player.get("isObserver") and player.get("teamId") == focused_team_id
    }
    round_results = sorted(match_obj.get("roundResults", []), key=lambda rr: rr.get("roundNum", 0))

    team_started_atk = None
    for rr in round_results:
        rnum = rr.get("roundNum", 0)
        if rnum >= 12:
            break
        planter = rr.get("bombPlanter")
        if planter:
            team_started_atk = planter in team_puuids
            break

    if team_started_atk is None:
        for rr in round_results:
            rnum = rr.get("roundNum", 0)
            if rnum < 12:
                continue
            planter = rr.get("bombPlanter")
            if planter:
                team_started_atk = planter not in team_puuids
                break

    if team_started_atk is None:
        team_started_atk = True

    return "T-SIDE" if team_started_atk else "CT-SIDE"


def build_map_meta_lookup(map_match_ids: list[str], api_key: str, focused_abbr: str, opponent_abbr: str) -> dict[str, dict[str, str]]:
    map_meta_lookup: dict[str, dict[str, str]] = {}
    for match_id in map_match_ids:
        match_obj = api_get_json(f"/api/matches/esports/{match_id}", api_key)
        team_prefix_counts: dict[str, dict[str, int]] = {}
        for player in match_obj.get("players", []):
            if player.get("isObserver"):
                continue
            team_id = player.get("teamId")
            if team_id not in {"Red", "Blue"}:
                continue
            prefix = str(player.get("gameName", "")).split(" ")[0].upper()
            team_prefix_counts.setdefault(team_id, {})
            team_prefix_counts[team_id][prefix] = team_prefix_counts[team_id].get(prefix, 0) + 1

        focused_team_id = None
        for team_id, prefix_counts in team_prefix_counts.items():
            if prefix_counts.get(focused_abbr.upper(), 0):
                focused_team_id = team_id
                break
        if focused_team_id is None:
            for team_id, prefix_counts in team_prefix_counts.items():
                if prefix_counts.get(opponent_abbr.upper(), 0):
                    focused_team_id = "Blue" if team_id == "Red" else "Red"
                    break
        if focused_team_id is None:
            continue

        team_rows = {team_row["teamId"]: team_row for team_row in match_obj.get("teams", []) if team_row.get("teamId") in {"Red", "Blue"}}
        focused_row = team_rows.get(focused_team_id)
        opponent_team_id = "Blue" if focused_team_id == "Red" else "Red"
        opponent_row = team_rows.get(opponent_team_id)
        if not focused_row or not opponent_row:
            continue
        map_meta_lookup[match_obj["matchInfo"]["map"]] = {
            "score": f"{focused_row['roundsWon']}:{opponent_row['roundsWon']}",
            "teamStartSide": infer_team_start_side(match_obj, focused_team_id),
        }
    return map_meta_lookup


def parse_raw_match(raw: str, focused_team: str, focused_label: str, opponent_label: str, api_key: str) -> dict | None:
    opponent1 = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}]+)\}\}", raw)
    opponent2 = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}]+)\}\}", raw)
    if not opponent1 or not opponent2:
        return None

    team1 = opponent1.group(1)
    team2 = opponent2.group(1)

    veto_match = re.search(r"(?s)\|mapveto=\{\{MapVeto(.*?)\}\}", raw)
    if not veto_match:
        return None
    block = veto_match.group(1)

    firstpick_match = re.search(r"\|firstpick=(\d+)", block)
    firstpick = int(firstpick_match.group(1)) if firstpick_match else 1

    slot_types = {
        "ban1": "ban",
        "ban2": "ban",
        "pick1": "pick",
        "pick2": "pick",
        "ban3": "ban",
        "ban4": "ban",
    }

    slots = {}
    team_field_order = [("t1", team1), ("t2", team2)] if firstpick == 1 else [("t2", team2), ("t1", team1)]
    slot_pairs = [
        ("ban1", "ban2", "map1"),
        ("pick1", "pick2", "map2"),
        ("ban3", "ban4", "map3"),
    ]

    for first_slot, second_slot, suffix in slot_pairs:
        first_prefix, first_owner = team_field_order[0]
        second_prefix, second_owner = team_field_order[1]
        ordered_fields = [
            (first_slot, first_prefix, first_owner),
            (second_slot, second_prefix, second_owner),
        ]
        for slot_key, prefix, owner_label in ordered_fields:
            field_match = re.search(rf"\|{prefix}{suffix}=([^\r\n|}}]+)", block)
            owner_kind = "team" if owner_label == focused_team else "opp"
            slots[slot_key] = {
                "map": field_match.group(1).strip() if field_match else "-",
                "type": slot_types[slot_key],
                "ownerLabel": focused_label if owner_kind == "team" else opponent_label,
                "ownerKind": owner_kind,
            }

    decider_match = re.search(r"\|decider=([^\r\n|}]+)", block)
    decider = decider_match.group(1).strip() if decider_match else "-"

    map_meta_lookup = build_map_meta_lookup(extract_map_match_ids(raw), api_key, focused_label, opponent_label)
    for slot_key in ("pick1", "pick2"):
        slot_meta = map_meta_lookup.get(slots[slot_key]["map"], {})
        slots[slot_key]["score"] = slot_meta.get("score", "")
        slots[slot_key]["teamStartSide"] = (
            f"{focused_label} {slot_meta['teamStartSide']}" if slot_meta.get("teamStartSide") else ""
        )

    decider_meta = map_meta_lookup.get(decider, {})
    decider_score = decider_meta.get("score", "")

    return {
        "slots": slots,
        "decider": decider,
        "deciderScore": decider_score,
        "deciderLabel": "DECIDER" if decider != "-" else "REMAINING",
        "deciderTeamStartSide": f"{focused_label} {decider_meta['teamStartSide']}" if decider_meta.get("teamStartSide") else "",
    }


def build_payload() -> tuple[dict, dict]:
    api_key = load_api_key()
    payload = {}
    pick_meta = {}
    for key, config in TEAM_CONFIG.items():
        rows = []
        team_meta = {}
        for match in parse_team_page(config["matches_url"]):
            raw = fetch_text(match.link + "?action=raw")
            parsed = parse_raw_match(raw, config["name"], config["ownerLabel"], match.opponent_abbr, api_key)
            if not parsed:
                continue
            row = {
                "date": match.date,
                "opponent": match.opponent,
                "opponentAbbr": match.opponent_abbr,
                "score": match.score,
                "source": match.link,
                "decider": parsed["decider"],
                "deciderScore": parsed["deciderScore"],
            }
            row.update(parsed["slots"])
            rows.append(row)
            team_meta[match.link] = {
                "pick1": {"teamStartSide": row["pick1"].get("teamStartSide", "")},
                "pick2": {"teamStartSide": row["pick2"].get("teamStartSide", "")},
                "decider": {"teamStartSide": parsed["deciderTeamStartSide"]},
            }

        rows.sort(key=lambda item: (item["date"], item["source"]), reverse=True)
        payload[key] = {
            "name": config["name"],
            "ownerLabel": config["ownerLabel"],
            "subtitle": config["subtitle"],
            "rows": rows,
        }
        pick_meta[key] = team_meta
    return payload, pick_meta


def main() -> None:
    payload, pick_meta = build_payload()
    OUTPUT.write_text(
        "const extraVetoHistoryData = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    PICK_META_OUTPUT.write_text(
        "const extraVetoPickMeta = " + json.dumps(pick_meta, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
