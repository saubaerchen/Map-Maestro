from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_KEY_FILE = ROOT / "API_REFERENCE.md"
API_BASE = "https://api.valolytics.gg"
USER_AGENT = "Codex/1.0"

MONTH_NAMES = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


@dataclass
class MatchRow:
    date: str
    opponent: str
    opponent_abbr: str
    score: str
    link: str


def fetch_text(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    safe_path = urllib.parse.quote(parsed.path, safe="/:@!$&'()*+,;=")
    safe_url = urllib.parse.urlunparse(parsed._replace(path=safe_path))
    req = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_api_key() -> str:
    text = API_KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"x-api-key:\s*([A-Za-z0-9]+)", text)
    if not m:
        raise RuntimeError("Could not find x-api-key in API_REFERENCE.md")
    return m.group(1)


def api_get_json(path: str, api_key: str, _retries: int = 3) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        headers={"x-api-key": api_key, "Accept": "application/json", "User-Agent": "curl/8.0.0"},
    )
    for attempt in range(_retries):
        try:
            time.sleep(0.4)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retries - 1:
                wait = 5 * (attempt + 1)
                print(f" [429, waiting {wait}s]", file=sys.stderr, end="", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("api_get_json: exceeded retries")


def parse_team_page(url: str, from_date: str) -> list[MatchRow]:
    html = fetch_text(url)
    rows = re.findall(r'<tr class="table2&#95;&#95;row--body.*?</tr>', html, flags=re.S)
    parsed: list[MatchRow] = []
    for row in rows:
        visible_date = re.search(r">([A-Za-z]+ \d{1,2}, \d{4})", row)
        if not visible_date:
            continue
        m = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})", visible_date.group(1))
        if not m:
            continue
        month_name, day, year_str = m.groups()
        month_index = MONTH_NAMES.get(month_name)
        if not month_index:
            continue
        date = f"{year_str}-{month_index:02d}-{int(day):02d}"
        if date < from_date:
            continue

        score_match = re.search(
            r'<td data-align="center" data-nowrap=""><span(?: style="font-weight:bold")?>(\d+)</span>'
            r'&#160;&#58;&#160;<span(?: style="font-weight:bold")?>(\d+)</span></td>',
            row,
        )
        if not score_match:
            continue
        score = f"{score_match.group(1)} - {score_match.group(2)}"

        sorts = re.findall(r'data-sort-value="([^"]+)"', row)
        opponent = html_lib.unescape(sorts[-1].strip()) if sorts else ""

        abbr_matches = re.findall(r'<span class="name"[^>]*><a [^>]*>([^<]+)</a></span>', row)
        opponent_abbr = html_lib.unescape(abbr_matches[-1].strip()) if abbr_matches else opponent

        link_match = re.search(r'href="(/valorant/Match:ID_[^"]+)"', row)
        if not link_match:
            continue

        parsed.append(MatchRow(
            date=date,
            opponent=opponent,
            opponent_abbr=opponent_abbr,
            score=score,
            link="https://liquipedia.net" + link_match.group(1),
        ))
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
        p.get("puuid")
        for p in match_obj.get("players", [])
        if not p.get("isObserver") and p.get("teamId") == focused_team_id
    }
    round_results = sorted(match_obj.get("roundResults", []), key=lambda rr: rr.get("roundNum", 0))

    team_started_atk = None
    for rr in round_results:
        if rr.get("roundNum", 0) >= 12:
            break
        planter = rr.get("bombPlanter")
        if planter:
            team_started_atk = planter in team_puuids
            break

    if team_started_atk is None:
        for rr in round_results:
            if rr.get("roundNum", 0) < 12:
                continue
            planter = rr.get("bombPlanter")
            if planter:
                team_started_atk = planter not in team_puuids
                break

    if team_started_atk is None:
        team_started_atk = True

    return "T-SIDE" if team_started_atk else "CT-SIDE"


def build_map_meta_lookup(
    map_match_ids: list[str],
    api_key: str,
    focused_abbr: str,
    opponent_abbr: str,
    issues: list[str],
    match_ctx: str,
) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    not_found_count = 0
    label_miss_count = 0

    for match_id in map_match_ids:
        try:
            match_obj = api_get_json(f"/api/matches/esports/{match_id}", api_key)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                not_found_count += 1
                print(f" [404]", file=sys.stderr, end="", flush=True)
            else:
                issues.append(f"{match_ctx}: HTTP {e.code} fetching map game {match_id}")
                print(f" [HTTP {e.code}]", file=sys.stderr, end="", flush=True)
            continue

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
        for team_id, counts in team_prefix_counts.items():
            if counts.get(focused_abbr.upper(), 0):
                focused_team_id = team_id
                break
        if focused_team_id is None:
            for team_id, counts in team_prefix_counts.items():
                if counts.get(opponent_abbr.upper(), 0):
                    focused_team_id = "Blue" if team_id == "Red" else "Red"
                    break
        if focused_team_id is None:
            label_miss_count += 1
            continue

        team_rows = {
            tr["teamId"]: tr
            for tr in match_obj.get("teams", [])
            if tr.get("teamId") in {"Red", "Blue"}
        }
        focused_row = team_rows.get(focused_team_id)
        opponent_row = team_rows.get("Blue" if focused_team_id == "Red" else "Red")
        if not focused_row or not opponent_row:
            continue

        lookup[match_obj["matchInfo"]["map"]] = {
            "score": f"{focused_row['roundsWon']}:{opponent_row['roundsWon']}",
            "teamStartSide": infer_team_start_side(match_obj, focused_team_id),
        }

    if not_found_count:
        issues.append(
            f"{match_ctx}: {not_found_count} map game(s) not in Valolytics (HTTP 404) — "
            f"score/side will be empty. League probably not covered by API."
        )
    if label_miss_count:
        issues.append(
            f"{match_ctx}: label '{focused_abbr}' not matched in Valolytics player names for "
            f"{label_miss_count} map game(s) — score/side will be empty. Check label in config."
        )

    return lookup


def parse_raw_match(
    raw: str,
    focused_team: str,
    focused_label: str,
    opponent_label: str,
    api_key: str,
    issues: list[str],
    match_ctx: str,
) -> dict | None:
    opponent1 = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}|]+)", raw)
    opponent2 = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}|]+)", raw)
    if not opponent1 or not opponent2:
        return None

    team1 = opponent1.group(1).strip()
    team2 = opponent2.group(1).strip()

    veto_match = re.search(r"(?s)\|mapveto=\{\{MapVeto(.*?)\}\}", raw)
    if not veto_match:
        issues.append(f"{match_ctx}: no MapVeto block in Liquipedia wikitext — match skipped")
        return None
    block = veto_match.group(1)

    firstpick_match = re.search(r"\|firstpick=(\d+)", block)
    firstpick = int(firstpick_match.group(1)) if firstpick_match else 1

    def team_matches(wiki_name: str) -> bool:
        return wiki_name.lower() == focused_team.lower()

    if team_matches(team1):
        team_field_order = [("t1", team1), ("t2", team2)]
    elif team_matches(team2):
        team_field_order = [("t2", team2), ("t1", team1)]
    else:
        issues.append(
            f"{match_ctx}: wikiName '{focused_team}' not matched in wikitext "
            f"(found '{team1}' vs '{team2}') — ownerKind/label may be wrong. "
            f"Update 'wikiName' in config."
        )
        team_field_order = [("t1", team1), ("t2", team2)] if firstpick == 1 else [("t2", team2), ("t1", team1)]

    slot_types = {"ban1": "ban", "ban2": "ban", "pick1": "pick", "pick2": "pick", "ban3": "ban", "ban4": "ban"}
    slot_pairs = [("ban1", "ban2", "map1"), ("pick1", "pick2", "map2"), ("ban3", "ban4", "map3")]

    slots = {}
    for first_slot, second_slot, suffix in slot_pairs:
        ordered = [
            (first_slot, team_field_order[0][0], team_field_order[0][1]),
            (second_slot, team_field_order[1][0], team_field_order[1][1]),
        ]
        for slot_key, prefix, owner_team in ordered:
            field_match = re.search(rf"\|{prefix}{suffix}=([^\r\n|}}]+)", block)
            owner_kind = "team" if owner_team == team_field_order[0][1] else "opp"
            slots[slot_key] = {
                "map": field_match.group(1).strip() if field_match else "-",
                "type": slot_types[slot_key],
                "ownerLabel": focused_label if owner_kind == "team" else opponent_label,
                "ownerKind": owner_kind,
            }

    decider_match = re.search(r"\|decider=([^\r\n|}]+)", block)
    decider = decider_match.group(1).strip() if decider_match else "-"

    map_meta = build_map_meta_lookup(
        extract_map_match_ids(raw), api_key, focused_label, opponent_label, issues, match_ctx
    )

    for slot_key in ("pick1", "pick2"):
        meta = map_meta.get(slots[slot_key]["map"], {})
        slots[slot_key]["score"] = meta.get("score", "")
        slots[slot_key]["pickLabel"] = (
            f"{focused_label} PICK" if slots[slot_key]["ownerKind"] == "team" else "OPPONENT PICK"
        )
        slots[slot_key]["teamStartSide"] = (
            f"{focused_label} {meta['teamStartSide']}" if meta.get("teamStartSide") else ""
        )

    decider_meta = map_meta.get(decider, {})
    return {
        "slots": slots,
        "decider": decider,
        "deciderScore": decider_meta.get("score", ""),
        "deciderLabel": "DECIDER" if decider != "-" else "REMAINING",
        "deciderTeamStartSide": (
            f"{focused_label} {decider_meta['teamStartSide']}" if decider_meta.get("teamStartSide") else ""
        ),
    }


def load_existing_js(path: Path, js_var: str) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    text = re.sub(rf"^const {re.escape(js_var)}\s*=\s*", "", text.strip()).rstrip(";").rstrip()
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Warning: could not parse existing {path}: {e}", file=sys.stderr)
        return {}


def process_team(
    key: str,
    config: dict,
    existing_data: dict,
    api_key: str,
    from_date: str,
    issues: list[str],
    dry_run: bool = False,
) -> tuple[dict, dict]:
    name = config["name"]
    wiki_name = config.get("wikiName", name)
    label = config["label"]
    matches_url = config["matchesUrl"]
    subtitle = config.get("subtitle", "2026 raw-order veto history")

    existing_team = existing_data.get(key, {})
    existing_rows = existing_team.get("rows", [])
    known_sources = {row["source"] for row in existing_rows}

    matches = parse_team_page(matches_url, from_date)
    new_matches = [m for m in matches if m.link not in known_sources]

    print(
        f"  {key}: {len(matches)} matches >= {from_date}, {len(new_matches)} new to fetch",
        file=sys.stderr,
    )

    if dry_run:
        for m in new_matches:
            print(f"    [dry-run] {m.date} vs {m.opponent_abbr}  {m.link}", file=sys.stderr)
        team_data = dict(existing_team) if existing_team else {
            "name": name, "ownerLabel": label, "subtitle": subtitle, "rows": existing_rows,
        }
        return team_data, {}

    new_rows = []
    pick_meta_entries: dict = {}
    for match in new_matches:
        match_ctx = f"[{key}] {match.date} vs {match.opponent_abbr}"
        print(f"    {match.date} vs {match.opponent_abbr} ...", file=sys.stderr, end=" ", flush=True)
        raw = fetch_text(match.link + "?action=raw")
        parsed = parse_raw_match(raw, wiki_name, label, match.opponent_abbr, api_key, issues, match_ctx)
        if not parsed:
            print("SKIP", file=sys.stderr)
            continue
        row = {
            "date": match.date,
            "opponent": match.opponent,
            "opponentAbbr": match.opponent_abbr,
            "score": match.score,
            "source": match.link,
            "decider": parsed["decider"],
            "deciderScore": parsed["deciderScore"],
            "deciderLabel": parsed["deciderLabel"],
            "deciderTeamStartSide": parsed["deciderTeamStartSide"],
        }
        row.update(parsed["slots"])
        new_rows.append(row)
        pick_meta_entries[match.link] = {
            "pick1": {"teamStartSide": row.get("pick1", {}).get("teamStartSide", "")},
            "pick2": {"teamStartSide": row.get("pick2", {}).get("teamStartSide", "")},
            "decider": {"teamStartSide": parsed["deciderTeamStartSide"]},
        }
        print("OK", file=sys.stderr)

    all_rows = existing_rows + new_rows
    all_rows.sort(key=lambda r: (r["date"], r["source"]), reverse=True)

    team_data = {
        "name": existing_team.get("name", name),
        "ownerLabel": existing_team.get("ownerLabel", label),
        "subtitle": existing_team.get("subtitle", subtitle),
        "rows": all_rows,
    }
    return team_data, pick_meta_entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Liquipedia veto data for any teams and merge into a JS data file."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--config", metavar="FILE", help="JSON config file with team definitions")
    source_group.add_argument("--key", metavar="KEY", help="Single team key (use with --name/--label/--matches-url)")

    parser.add_argument("--name", help="Team display name (single-team mode)")
    parser.add_argument("--label", help="Team abbreviation label (single-team mode)")
    parser.add_argument("--wiki-name", dest="wiki_name", help="Exact team name in Liquipedia wikitext (defaults to --name)")
    parser.add_argument("--matches-url", dest="matches_url", help="Liquipedia /Matches URL (single-team mode)")

    parser.add_argument("--output", required=True, metavar="FILE", help="Output JS file (veto data)")
    parser.add_argument("--js-var", dest="js_var", default="vetoHistoryData", help="JS variable name in output file")
    parser.add_argument("--pick-meta-output", dest="pick_meta_output", metavar="FILE", help="Output JS file for pick-meta")
    parser.add_argument("--pick-meta-var", dest="pick_meta_var", default="vetoPickMeta", help="JS variable name for pick-meta")

    parser.add_argument("--from-date", dest="from_date", default="2026-04-01", metavar="YYYY-MM-DD",
                        help="Only include matches on or after this date (default: 2026-04-01)")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="List matches that would be fetched without actually fetching them")
    args = parser.parse_args()

    if args.key:
        if not (args.name and args.label and args.matches_url):
            parser.error("--name, --label, and --matches-url are required in single-team mode")
        team_configs: dict = {
            args.key: {
                "name": args.name,
                "label": args.label,
                "wikiName": args.wiki_name or args.name,
                "matchesUrl": args.matches_url,
            }
        }
    else:
        team_configs = json.loads(Path(args.config).read_text(encoding="utf-8"))

    output_path = Path(args.output)
    existing_data = load_existing_js(output_path, args.js_var)

    pick_meta_path = Path(args.pick_meta_output) if args.pick_meta_output else None
    existing_pick_meta: dict = {}
    if pick_meta_path:
        existing_pick_meta = load_existing_js(pick_meta_path, args.pick_meta_var)

    api_key = load_api_key() if not args.dry_run else ""
    output_data = dict(existing_data)
    output_pick_meta = dict(existing_pick_meta)
    issues: list[str] = []

    def save_outputs() -> None:
        output_path.write_text(
            f"const {args.js_var} = " + json.dumps(output_data, ensure_ascii=False, indent=2) + ";\n",
            encoding="utf-8",
        )
        if pick_meta_path:
            pick_meta_path.write_text(
                f"const {args.pick_meta_var} = " + json.dumps(output_pick_meta, ensure_ascii=False, indent=2) + ";\n",
                encoding="utf-8",
            )

    for key, config in team_configs.items():
        print(f"\n[{key}]", file=sys.stderr)
        team_data, pick_meta_entries = process_team(
            key, config, existing_data, api_key, args.from_date, issues, dry_run=args.dry_run
        )
        output_data[key] = team_data
        if pick_meta_entries:
            output_pick_meta.setdefault(key, {}).update(pick_meta_entries)
        if not args.dry_run:
            save_outputs()
            print(f"  [saved]", file=sys.stderr)

    if args.dry_run:
        print("\n[dry-run] No files written.", file=sys.stderr)
        return

    print(f"\nDone. Wrote {output_path}", file=sys.stderr)
    if pick_meta_path:
        print(f"      and {pick_meta_path}", file=sys.stderr)

    if issues:
        print(f"\n{'─' * 60}", file=sys.stderr)
        print(f"⚠  {len(issues)} ISSUE(S) TO REVIEW:", file=sys.stderr)
        print(f"{'─' * 60}", file=sys.stderr)
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}", file=sys.stderr)
        print(f"{'─' * 60}", file=sys.stderr)
    else:
        print("✓  No issues.", file=sys.stderr)


if __name__ == "__main__":
    main()
